from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json


LOCALE_CAPABILITY_REPORT_JSON = "locale-capability-report.json"
LOCALE_RISK_REPORT_JSON = "locale-risk-report.json"
LOCALE_READINESS_IMPACT_JSON = "locale-readiness-impact.json"

LOCALE_CLAIMS = {
    "locale_complete",
    "rtl_safe",
    "plural_complete",
    "locale_formatting_complete",
    "full_product_localization",
}

RTL_LANGUAGES = {"ar", "fa", "he", "ur"}
NO_PLURAL_LANGUAGES = {"ja", "ko", "th", "vi", "zh"}
SIMPLE_PLURAL_LANGUAGES = {"de", "en", "es", "it", "pt"}
COMPLEX_PLURAL_PROFILES = {
    "ar": ["zero", "one", "two", "few", "many", "other"],
    "pl": ["one", "few", "many", "other"],
    "ru": ["one", "few", "many", "other"],
    "uk": ["one", "few", "many", "other"],
}
SIMPLE_PLURAL_CATEGORIES = ["one", "other"]
NO_PLURAL_CATEGORIES = ["other"]

ADAPTER_PLURAL_SUPPORT = {
    "core.android-strings": {
        "status": "supported",
        "evidence": "Android plurals resources preserve plural quantities mechanically.",
    },
    "core.ios-strings": {
        "status": "supported",
        "evidence": "iOS .stringsdict resources preserve plural variants mechanically when present.",
    },
    "core.xcstrings": {
        "status": "supported",
        "evidence": "Xcode String Catalog variation paths are preserved mechanically when present.",
    },
    "core.gettext-po": {
        "status": "partial",
        "evidence": "Gettext plural forms are checked mechanically, but locale rule coverage is seed-level.",
    },
}


def build_locale_capability_reports(
    state_dir: Path,
    *,
    target_locale: str | None = None,
    adapters: list[str] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    capability = build_locale_capability_report(
        state_dir,
        target_locale=target_locale,
        adapters=adapters,
        run_id=run_id,
        write=write,
    )
    risk = build_locale_risk_report(state_dir, capability=capability, run_id=run_id, write=write)
    impact = build_locale_readiness_impact(state_dir, capability=capability, risk=risk, run_id=run_id, write=write)
    return {
        "locale_capability_report": capability,
        "locale_risk_report": risk,
        "locale_readiness_impact": impact,
    }


def build_locale_capability_report(
    state_dir: Path,
    *,
    target_locale: str | None = None,
    adapters: list[str] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    evidence = _state_evidence(state_dir)
    locale = _normalize_locale(target_locale or _target_locale_from_evidence(evidence))
    adapter_list = sorted(set(adapters or _adapters_from_evidence(evidence)))
    profile = _locale_profile(locale)
    adapter_matches = [_adapter_match(adapter, profile) for adapter in adapter_list]
    has_plural_source = _has_plural_source(evidence)
    plural_support_status = _plural_support_status(profile, adapter_matches, has_plural_source)
    formatting = {
        "date_time": "unknown",
        "number": "unknown",
        "currency": "unknown",
        "evidence": "locale-aware formatting evidence is not implemented in this seed",
    }
    capability_status = _capability_status(profile, adapter_matches, plural_support_status)
    unsupported_claims = _unsupported_claims(profile, plural_support_status, formatting, adapter_matches)
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-locale-capability-report-v1",
        "artifact": LOCALE_CAPABILITY_REPORT_JSON,
        "status": capability_status,
        "run_id": run_id or evidence.get("run_id"),
        "target_locale": locale or "unknown",
        "normalized_language": _language(locale),
        "locale_profile": profile,
        "adapter_capability_matches": adapter_matches,
        "plural_support": {
            "source_has_plural_resources": has_plural_source,
            "status": plural_support_status,
            "expected_categories": profile["expected_plural_categories"],
            "adapter_evidence": [item for item in adapter_matches if item["plural_support_status"] != "unknown"],
        },
        "formatting_support": formatting,
        "unicode_bidi_risk_flags": _unicode_bidi_flags(profile),
        "unsupported_claims": sorted(unsupported_claims),
        "source_artifacts": _source_artifacts(state_dir),
        "limitations": [
            "locale capability report is seed-level engineering evidence, not full CLDR support",
            "locale capability report is not translation quality evidence",
            "formatting support defaults to unknown unless explicit adapter/runtime evidence exists",
        ],
    }
    if write:
        write_json(state_dir / LOCALE_CAPABILITY_REPORT_JSON, report)
    return report


def read_locale_capability_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / LOCALE_CAPABILITY_REPORT_JSON)


def build_locale_risk_report(
    state_dir: Path,
    *,
    capability: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    capability = capability or build_locale_capability_report(state_dir, run_id=run_id, write=False)
    risks = _risk_items(capability)
    blocking = [item for item in risks if item["severity"] == "blocking"]
    warnings = [item for item in risks if item["severity"] == "warning"]
    status = "blocked" if blocking else "review_required" if warnings else "clear"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-locale-risk-report-v1",
        "artifact": LOCALE_RISK_REPORT_JSON,
        "status": status,
        "run_id": run_id or capability.get("run_id"),
        "target_locale": capability.get("target_locale", "unknown"),
        "risks": risks,
        "summary": {
            "risk_count": len(risks),
            "blocking_count": len(blocking),
            "warning_count": len(warnings),
        },
        "forbidden_claims": sorted(_claims_from_risks(risks)),
        "source_artifacts": {key: value for key, value in capability.get("source_artifacts", {}).items() if value},
        "limitations": [
            "locale risk report identifies engineering risk only",
            "absence of a risk does not prove full product localization",
        ],
    }
    if write:
        write_json(state_dir / LOCALE_RISK_REPORT_JSON, report)
    return report


def read_locale_risk_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / LOCALE_RISK_REPORT_JSON)


def build_locale_readiness_impact(
    state_dir: Path,
    *,
    capability: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    capability = capability or build_locale_capability_report(state_dir, run_id=run_id, write=False)
    risk = risk or build_locale_risk_report(state_dir, capability=capability, run_id=run_id, write=False)
    forbidden = set(capability.get("unsupported_claims", [])) | set(risk.get("forbidden_claims", []))
    readiness_status = "blocked" if risk.get("status") == "blocked" else "review_required" if risk.get("status") == "review_required" else "clear_with_warnings"
    if not forbidden:
        readiness_status = "clear"
    impact = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-locale-readiness-impact-v1",
        "artifact": LOCALE_READINESS_IMPACT_JSON,
        "status": readiness_status,
        "run_id": run_id or capability.get("run_id"),
        "target_locale": capability.get("target_locale", "unknown"),
        "delivery_readiness_impact": "blocked" if "full_product_localization" in forbidden else "downgraded" if forbidden else "none",
        "apply_readiness_impact": "blocked" if risk.get("status") == "blocked" else "downgraded" if forbidden else "none",
        "scorecard_impact": "forbid_locale_claims" if forbidden else "none",
        "forbidden_claims": sorted(forbidden),
        "claim_acceptance_policy": {
            "unsupported_locale_claims_cannot_be_accepted": True,
            "limited_scope_acceptance_must_preserve_forbidden_claims": True,
        },
        "signoff_policy": {
            "signoff_cannot_override_missing_locale_capability_evidence": True,
            "locale_limitations_must_remain_visible": True,
        },
        "required_next_actions": _next_actions(capability, risk, forbidden),
        "source_artifacts": {
            "locale_capability_report": LOCALE_CAPABILITY_REPORT_JSON,
            "locale_risk_report": LOCALE_RISK_REPORT_JSON,
        },
        "limitations": [
            "locale readiness impact is a consolidation artifact and does not prove translation quality",
            "full locale completeness remains forbidden unless adapter/runtime evidence supports the required locale behavior",
        ],
    }
    if write:
        write_json(state_dir / LOCALE_READINESS_IMPACT_JSON, impact)
    return impact


def read_locale_readiness_impact(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / LOCALE_READINESS_IMPACT_JSON)


def locale_capability_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "locale_capability_report": LOCALE_CAPABILITY_REPORT_JSON,
        "locale_risk_report": LOCALE_RISK_REPORT_JSON,
        "locale_readiness_impact": LOCALE_READINESS_IMPACT_JSON,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def _state_evidence(state_dir: Path) -> dict[str, Any]:
    return {
        "config": _optional_json(state_dir / "config.json"),
        "localization_brief": _optional_json(state_dir / "localization-brief.json"),
        "delivery_manifest": _optional_json(state_dir / "delivery-manifest.json"),
        "source_inventory": _optional_json(state_dir / "source-inventory.json"),
        "generated_segments": _optional_jsonl(state_dir / "generated-segments.jsonl"),
    }


def _target_locale_from_evidence(evidence: dict[str, Any]) -> str:
    brief = evidence.get("localization_brief", {})
    intent = brief.get("task_intent", {}) if isinstance(brief, dict) else {}
    values = intent.get("target_locales")
    if isinstance(values, list) and values:
        return str(values[0])
    config = evidence.get("config", {})
    values = config.get("target_locales")
    if isinstance(values, list) and values:
        return str(values[0])
    manifest = evidence.get("delivery_manifest", {})
    project = manifest.get("project", {}) if isinstance(manifest, dict) else {}
    values = project.get("target_locales")
    if isinstance(values, list) and values:
        return str(values[0])
    return "unknown"


def _adapters_from_evidence(evidence: dict[str, Any]) -> list[str]:
    brief = evidence.get("localization_brief", {})
    surface = brief.get("source_surface", {}) if isinstance(brief, dict) else {}
    adapter_counts = surface.get("adapter_counts") if isinstance(surface, dict) else {}
    if isinstance(adapter_counts, dict) and adapter_counts:
        return [str(adapter) for adapter in adapter_counts]
    manifest = evidence.get("delivery_manifest", {})
    source_material = manifest.get("source_material", []) if isinstance(manifest, dict) else []
    adapters = [str(item.get("adapter")) for item in source_material if isinstance(item, dict) and item.get("adapter")]
    if adapters:
        return adapters
    inventory = evidence.get("source_inventory", {})
    files = inventory.get("supported_files", []) if isinstance(inventory, dict) else []
    return [str(item.get("adapter")) for item in files if isinstance(item, dict) and item.get("adapter")]


def _locale_profile(locale: str) -> dict[str, Any]:
    language = _language(locale)
    directionality = "RTL" if language in RTL_LANGUAGES else "LTR" if language else "unknown"
    if language in NO_PLURAL_LANGUAGES:
        plural_complexity = "none"
        categories = NO_PLURAL_CATEGORIES
    elif language in SIMPLE_PLURAL_LANGUAGES:
        plural_complexity = "simple"
        categories = SIMPLE_PLURAL_CATEGORIES
    elif language in COMPLEX_PLURAL_PROFILES:
        plural_complexity = "complex"
        categories = COMPLEX_PLURAL_PROFILES[language]
    elif language:
        plural_complexity = "unknown"
        categories = []
    else:
        plural_complexity = "unknown"
        categories = []
    return {
        "directionality": directionality,
        "plural_complexity": plural_complexity,
        "expected_plural_categories": categories,
        "formatting_support_status": "unknown",
        "unicode_risk_flags": _unicode_bidi_flags({"directionality": directionality}),
        "profile_source": "built_in_seed_profile" if language else "unknown",
    }


def _adapter_match(adapter: str, profile: dict[str, Any]) -> dict[str, Any]:
    plural = ADAPTER_PLURAL_SUPPORT.get(adapter, {"status": "unknown", "evidence": "adapter plural capability is unknown"})
    directionality = profile.get("directionality")
    return {
        "adapter": adapter,
        "plural_support_status": plural["status"],
        "plural_support_evidence": plural["evidence"],
        "rtl_layout_support_status": "unknown" if directionality == "RTL" else "not_applicable",
        "formatting_support_status": "unknown",
    }


def _plural_support_status(profile: dict[str, Any], adapter_matches: list[dict[str, Any]], has_plural_source: bool) -> str:
    complexity = str(profile.get("plural_complexity") or "unknown")
    if complexity == "none":
        return "not_required"
    if complexity == "unknown":
        return "unknown"
    if not has_plural_source:
        return "not_evidenced"
    statuses = {str(item.get("plural_support_status") or "unknown") for item in adapter_matches}
    if "supported" in statuses and complexity in {"simple", "complex"}:
        return "supported"
    if "partial" in statuses:
        return "partial"
    return "unknown"


def _capability_status(profile: dict[str, Any], adapter_matches: list[dict[str, Any]], plural_status: str) -> str:
    if profile["directionality"] == "unknown" or profile["plural_complexity"] == "unknown":
        return "unknown"
    if profile["directionality"] == "RTL" or plural_status in {"unknown", "partial", "not_evidenced"}:
        return "partial"
    if any(item["formatting_support_status"] == "unknown" for item in adapter_matches) or not adapter_matches:
        return "partial"
    return "supported"


def _unsupported_claims(
    profile: dict[str, Any],
    plural_status: str,
    formatting: dict[str, Any],
    adapter_matches: list[dict[str, Any]],
) -> set[str]:
    claims = set(LOCALE_CLAIMS)
    if profile["directionality"] != "RTL":
        claims.discard("rtl_safe")
    if plural_status in {"supported", "not_required"}:
        claims.discard("plural_complete")
    if all(value == "supported" for key, value in formatting.items() if key in {"date_time", "number", "currency"}):
        claims.discard("locale_formatting_complete")
    if not adapter_matches:
        claims.add("full_product_localization")
    return claims


def _risk_items(capability: dict[str, Any]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    profile = capability.get("locale_profile", {})
    target = str(capability.get("target_locale") or "unknown")
    if target == "unknown" or profile.get("directionality") == "unknown" or profile.get("plural_complexity") == "unknown":
        risks.append(_risk("locale_unknown", "blocking", "unknown locale capability must downgrade claims", ["locale_complete", "full_product_localization"]))
    if profile.get("directionality") == "RTL":
        risks.append(_risk("rtl_without_layout_evidence", "blocking", "RTL locale lacks bidi/layout safety evidence", ["rtl_safe", "full_product_localization"]))
    plural = capability.get("plural_support", {})
    if plural.get("status") in {"unknown", "partial", "not_evidenced"}:
        risks.append(_risk("plural_support_not_proven", "warning", "plural support is not fully evidenced", ["plural_complete", "locale_complete"]))
    formatting = capability.get("formatting_support", {})
    if any(formatting.get(key) in {"unknown", "unsupported", "partial"} for key in ("date_time", "number", "currency")):
        risks.append(_risk("locale_formatting_not_proven", "warning", "locale-aware date/time/number/currency formatting is not evidenced", ["locale_formatting_complete", "locale_complete"]))
    if "full_product_localization" in set(capability.get("unsupported_claims", [])):
        risks.append(_risk("full_product_localization_not_proven", "warning", "non-text/runtime locale surfaces are not fully evidenced", ["full_product_localization"]))
    return risks


def _risk(risk_type: str, severity: str, summary: str, claims: list[str]) -> dict[str, Any]:
    return {
        "risk_id": f"locale-risk-{risk_type}",
        "risk_type": risk_type,
        "severity": severity,
        "summary": summary,
        "forbidden_claims_affected": claims,
        "recommended_action": "Provide adapter/runtime evidence or keep the affected locale claims forbidden.",
    }


def _claims_from_risks(risks: list[dict[str, Any]]) -> set[str]:
    claims: set[str] = set()
    for risk in risks:
        claims.update(str(claim) for claim in risk.get("forbidden_claims_affected", []) if claim)
    return claims


def _next_actions(capability: dict[str, Any], risk: dict[str, Any], forbidden: set[str]) -> list[str]:
    actions = []
    if "rtl_safe" in forbidden:
        actions.append("Collect bidi/layout evidence before claiming RTL-safe delivery.")
    if "plural_complete" in forbidden:
        actions.append("Collect adapter/runtime plural evidence for the target locale before claiming plural completeness.")
    if "locale_formatting_complete" in forbidden:
        actions.append("Collect locale-aware date/time/number/currency formatting evidence before claiming formatting completeness.")
    if "locale_complete" in forbidden or risk.get("status") != "clear":
        actions.append("Keep locale-complete and full-product claims downgraded until locale capability evidence is current.")
    return list(dict.fromkeys(actions))


def _has_plural_source(evidence: dict[str, Any]) -> bool:
    for item in evidence.get("generated_segments", []):
        if isinstance(item, dict) and (item.get("target_plural") or item.get("context", {}).get("resource_type") == "plurals"):
            return True
    manifest = evidence.get("delivery_manifest", {})
    source_material = manifest.get("source_material", []) if isinstance(manifest, dict) else []
    return any(isinstance(item, dict) and item.get("adapter") in ADAPTER_PLURAL_SUPPORT for item in source_material)


def _unicode_bidi_flags(profile: dict[str, Any]) -> list[str]:
    return ["rtl_bidi_layout_evidence_required"] if profile.get("directionality") == "RTL" else []


def _source_artifacts(state_dir: Path) -> dict[str, str]:
    names = {
        "config": "config.json",
        "localization_brief": "localization-brief.json",
        "delivery_manifest": "delivery-manifest.json",
        "source_inventory": "source-inventory.json",
        "generated_segments": "generated-segments.jsonl",
    }
    return {key: name for key, name in names.items() if (state_dir / name).is_file()}


def _normalize_locale(locale: str | None) -> str:
    value = str(locale or "").strip().replace("_", "-")
    return value or "unknown"


def _language(locale: str) -> str:
    if not locale or locale == "unknown":
        return ""
    return locale.split("-", 1)[0].lower()


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing locale artifact: {path}")
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Locale artifact must be a JSON object: {path}")
    return value


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _optional_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return read_jsonl(path)
