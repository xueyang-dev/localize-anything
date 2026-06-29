from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, sha256_file, write_json
from .knowledge_consumption import (
    KNOWLEDGE_ELIGIBILITY_REPORT_JSON,
    KNOWLEDGE_PACK_SELECTION_JSON,
    WORKING_CONTEXT_PACKET_JSON,
)
from .knowledge_usage import (
    CONSTRAINT_APPLICATION_AUDIT_JSON,
    KNOWLEDGE_CONFLICT_REPORT_JSON,
    KNOWLEDGE_USAGE_REPORT_JSON,
)
from .localization_brief import LOCALIZATION_BRIEF_JSON
from .termbase_preflight import TERMBASE_PREFLIGHT_REPORT_JSON


GENERATION_STRATEGY_JSON = "generation-strategy.json"


def build_generation_strategy(
    state_dir: Path,
    batch_plan: dict[str, Any],
    *,
    source_locale: str | None = None,
    target_locale: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    operating_mode = str(batch_plan.get("operating_mode") or "greenfield_localization")
    reference_policy = str(batch_plan.get("reference_policy") or "style_only")
    source_locale = source_locale or str(batch_plan.get("source_locale") or "")
    target_locale = target_locale or _first_target_locale(batch_plan)

    brief = _read_optional_json(state_dir / LOCALIZATION_BRIEF_JSON)
    term_report = _read_optional_json(state_dir / TERMBASE_PREFLIGHT_REPORT_JSON)
    knowledge_gate = _knowledge_gate(state_dir, operating_mode)

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    reason_codes: list[str] = []

    term_gate = _term_gate(term_report)
    if term_gate["conflict_count"]:
        blockers.append(
            {
                "code": "term_conflict",
                "message": "Termbase preflight has unresolved terminology conflicts.",
                "count": term_gate["conflict_count"],
                "artifact": TERMBASE_PREFLIGHT_REPORT_JSON,
            }
        )
        reason_codes.append("term_conflict")
    elif term_gate["high_risk_unreviewed_count"]:
        warnings.append(
            {
                "code": "unreviewed_high_risk_terms",
                "message": "High-risk terminology still needs review before full terminology assurance.",
                "count": term_gate["high_risk_unreviewed_count"],
                "artifact": TERMBASE_PREFLIGHT_REPORT_JSON,
            }
        )
        reason_codes.append("unreviewed_high_risk_terms")
    elif term_gate["review_required_count"]:
        warnings.append(
            {
                "code": "term_review_incomplete",
                "message": "Terminology review is incomplete; generation must not claim full terminology assurance.",
                "count": term_gate["review_required_count"],
                "artifact": TERMBASE_PREFLIGHT_REPORT_JSON,
            }
        )
        reason_codes.append("term_review_incomplete")
    elif term_gate["status"] == "not_run":
        warnings.append(
            {
                "code": "termbase_preflight_not_run",
                "message": "Termbase preflight report is missing.",
                "artifact": TERMBASE_PREFLIGHT_REPORT_JSON,
            }
        )
        reason_codes.append("termbase_preflight_not_run")

    brief_gate = _brief_gate(brief)
    if brief_gate["required_human_confirmation_count"]:
        warnings.append(
            {
                "code": "localization_brief_confirmation_required",
                "message": "Localization brief still contains required human confirmations.",
                "count": brief_gate["required_human_confirmation_count"],
                "artifact": LOCALIZATION_BRIEF_JSON,
            }
        )
        reason_codes.append("localization_brief_confirmation_required")
    elif brief_gate["status"] == "not_found":
        warnings.append(
            {
                "code": "localization_brief_missing",
                "message": "Localization brief is missing.",
                "artifact": LOCALIZATION_BRIEF_JSON,
            }
        )
        reason_codes.append("localization_brief_missing")

    if knowledge_gate["status"] == "blocked":
        blockers.append(
            {
                "code": "knowledge_context_blocked",
                "message": "Working Context Packet is stale, mode-mismatched, or contains hard-constraint conflicts.",
                "artifact": WORKING_CONTEXT_PACKET_JSON,
                "reasons": knowledge_gate["blocking_reasons"],
            }
        )
        reason_codes.append("knowledge_context_blocked")
    elif knowledge_gate["status"] == "review_required":
        warnings.append(
            {
                "code": "knowledge_context_review_required",
                "message": "Selected pack knowledge is not eligible for constraint-backed assurance.",
                "artifact": WORKING_CONTEXT_PACKET_JSON,
                "reasons": knowledge_gate["warning_reasons"],
            }
        )
        reason_codes.append("knowledge_context_review_required")

    if blockers:
        status = "blocked"
        route = "blocked"
        assurance = "blocked"
        allow_generation = False
    elif warnings:
        status = "review_required"
        route = "high_assurance_handoff" if term_gate["high_risk_unreviewed_count"] else "standard_handoff"
        assurance = "partial"
        allow_generation = True
    else:
        status = "ready"
        route = "standard_handoff"
        assurance = "standard"
        allow_generation = True

    batch_count = len(batch_plan.get("batches", []))
    segment_count = sum(int(batch.get("segment_count", 0)) for batch in batch_plan.get("batches", []))
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-generation-strategy-v1",
        "run_id": run_id,
        "source_locale": source_locale,
        "target_locale": target_locale,
        "operating_mode": operating_mode,
        "reference_policy": reference_policy,
        "status": status,
        "generation_readiness": status,
        "route": {
            "mode": route,
            "assurance": assurance,
            "reason_codes": sorted(set(reason_codes)),
        },
        "scope": {
            "batch_count": batch_count,
            "segment_count": segment_count,
        },
        "gates": {
            "localization_brief": brief_gate,
            "terminology": term_gate,
            "knowledge": knowledge_gate,
        },
        "work_packet_policy": {
            "allow_generation": allow_generation,
            "include_hard_constraints": True,
            "include_terminology_review": True,
            "include_generation_strategy": True,
            "include_working_context_packet": knowledge_gate["enabled"],
            "knowledge_classes_allowed": knowledge_gate["allowed_classes"],
            "blocked_reason_codes": [item["code"] for item in blockers],
            "warning_codes": [item["code"] for item in warnings],
        },
        "draft_request_policy": {
            "provider_agnostic": True,
            "provider_call_performed": False,
            "quality_claim": "no_full_assurance_until_reviews_complete" if warnings or blockers else "strategy_ready",
            "knowledge_backed_quality_claim_allowed": False,
        },
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": _generation_strategy_asset_paths(state_dir, brief, term_report, knowledge_gate),
        "limitations": [
            "strategy is deterministic and does not perform translation",
            "review_required still permits handoff generation but cannot claim full review or terminology assurance",
            "blocked strategy prevents generation handoff until blocking governance conflicts are resolved",
            "knowledge context is structured and does not imply knowledge-augmented quality",
        ],
    }


def write_generation_strategy(state_dir: Path, strategy: dict[str, Any]) -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    write_json(state_dir / GENERATION_STRATEGY_JSON, strategy)
    return strategy


def generation_strategy_asset_paths(state_dir: Path) -> dict[str, str]:
    return {"generation_strategy": GENERATION_STRATEGY_JSON} if (state_dir / GENERATION_STRATEGY_JSON).is_file() else {}


def generation_strategy_summary(state_dir: Path) -> dict[str, Any]:
    path = state_dir / GENERATION_STRATEGY_JSON
    if not path.is_file():
        return {
            "status": "not_run",
            "generation_readiness": "not_checked",
            "route": None,
            "allow_generation": True,
            "artifact": None,
        }
    strategy = read_json(path)
    return {
        "status": strategy.get("status", "not_checked"),
        "generation_readiness": strategy.get("generation_readiness", "not_checked"),
        "route": strategy.get("route", {}),
        "allow_generation": strategy.get("work_packet_policy", {}).get("allow_generation", True),
        "blocked_reason_codes": strategy.get("work_packet_policy", {}).get("blocked_reason_codes", []),
        "warning_codes": strategy.get("work_packet_policy", {}).get("warning_codes", []),
        "terminology_assurance": strategy.get("gates", {}).get("terminology", {}).get("terminology_assurance", "not_checked"),
        "artifact": GENERATION_STRATEGY_JSON,
    }


def read_generation_strategy(state_dir: Path) -> dict[str, Any]:
    path = state_dir / GENERATION_STRATEGY_JSON
    if not path.is_file():
        raise ValueError(f"Missing generation strategy: {path}")
    return read_json(path)


def _term_gate(term_report: dict[str, Any] | None) -> dict[str, Any]:
    if not term_report:
        return {
            "status": "not_run",
            "terminology_assurance": "not_checked",
            "review_required_count": 0,
            "high_risk_unreviewed_count": 0,
            "conflict_count": 0,
            "artifact": None,
        }
    summary = term_report.get("summary", {}) if isinstance(term_report.get("summary"), dict) else {}
    conflict_count = _as_int(summary.get("conflict_count"), len(term_report.get("conflicts", [])))
    high_risk_count = _as_int(summary.get("high_risk_unreviewed_count"), len(term_report.get("unreviewed_high_risk_terms", [])))
    return {
        "status": term_report.get("status", "not_checked"),
        "terminology_assurance": term_report.get("terminology_assurance", "not_checked"),
        "review_required_count": _as_int(summary.get("review_required_count"), 0),
        "high_risk_unreviewed_count": high_risk_count,
        "conflict_count": conflict_count,
        "artifact": TERMBASE_PREFLIGHT_REPORT_JSON,
    }


def _brief_gate(brief: dict[str, Any] | None) -> dict[str, Any]:
    if not brief:
        return {
            "status": "not_found",
            "required_human_confirmation_count": 0,
            "required_human_confirmations": [],
            "artifact": None,
        }
    confirmations = brief.get("required_human_confirmations", [])
    if not isinstance(confirmations, list):
        confirmations = []
    return {
        "status": brief.get("status", "draft"),
        "required_human_confirmation_count": len(confirmations),
        "required_human_confirmations": [
            str(item.get("item") or item.get("type") or item)
            for item in confirmations[:20]
        ],
        "artifact": LOCALIZATION_BRIEF_JSON,
    }


def _generation_strategy_asset_paths(
    state_dir: Path,
    brief: dict[str, Any] | None,
    term_report: dict[str, Any] | None,
    knowledge_gate: dict[str, Any],
) -> dict[str, str]:
    artifacts = {"generation_strategy": GENERATION_STRATEGY_JSON}
    if brief is not None and (state_dir / LOCALIZATION_BRIEF_JSON).is_file():
        artifacts["localization_brief"] = LOCALIZATION_BRIEF_JSON
    if term_report is not None and (state_dir / TERMBASE_PREFLIGHT_REPORT_JSON).is_file():
        artifacts["termbase_preflight_report"] = TERMBASE_PREFLIGHT_REPORT_JSON
    for key, name in (
        ("knowledge_pack_selection", KNOWLEDGE_PACK_SELECTION_JSON),
        ("knowledge_eligibility_report", KNOWLEDGE_ELIGIBILITY_REPORT_JSON),
        ("working_context_packet", WORKING_CONTEXT_PACKET_JSON),
        ("knowledge_usage_report", KNOWLEDGE_USAGE_REPORT_JSON),
        ("constraint_application_audit", CONSTRAINT_APPLICATION_AUDIT_JSON),
        ("knowledge_conflict_report", KNOWLEDGE_CONFLICT_REPORT_JSON),
    ):
        if knowledge_gate["selected"] and (state_dir / name).is_file():
            artifacts[key] = name
    return artifacts


def _knowledge_gate(state_dir: Path, operating_mode: str) -> dict[str, Any]:
    selection = _read_optional_json(state_dir / KNOWLEDGE_PACK_SELECTION_JSON)
    eligibility = _read_optional_json(state_dir / KNOWLEDGE_ELIGIBILITY_REPORT_JSON)
    context = _read_optional_json(state_dir / WORKING_CONTEXT_PACKET_JSON)
    usage = _read_optional_json(state_dir / KNOWLEDGE_USAGE_REPORT_JSON)
    audit = _read_optional_json(state_dir / CONSTRAINT_APPLICATION_AUDIT_JSON)
    conflicts = _read_optional_json(state_dir / KNOWLEDGE_CONFLICT_REPORT_JSON)
    if not selection:
        return {
            "status": "not_selected",
            "selected": False,
            "enabled": False,
            "allowed_classes": [],
            "blocking_reasons": [],
            "warning_reasons": [],
            "knowledge_augmented_quality_claim_allowed": False,
            "artifacts": {},
        }
    blocking: list[str] = []
    warnings: list[str] = []
    if not selection.get("selected_packs"):
        warnings.append("no_valid_pack_selected")
    if not eligibility or not context:
        warnings.append("knowledge_artifacts_incomplete")
    if context and context.get("operating_mode") != operating_mode:
        blocking.append("operating_mode_changed")
    if context and context.get("status") == "blocked":
        blocking.append("hard_constraint_conflict")
    if selection.get("selected_packs") and (not usage or not audit or not conflicts):
        warnings.append("knowledge_usage_audit_missing")
    if conflicts and int(conflicts.get("summary", {}).get("blocking_conflict_count", 0) or 0):
        blocking.append("knowledge_conflict_unresolved")
    if audit and int(audit.get("summary", {}).get("checked_fail_count", 0) or 0):
        blocking.append("knowledge_constraint_check_failed")
    if context and _knowledge_inputs_changed(state_dir, eligibility or {}, context):
        blocking.append("working_context_inputs_changed")
    artifact_state = _read_optional_json(state_dir / "artifact-state.json") or {}
    context_state = next(
        (item for item in artifact_state.get("artifacts", []) if item.get("artifact_id") == "working_context_packet"),
        {},
    )
    if context_state.get("status") in {"stale", "blocked", "superseded"}:
        blocking.append("working_context_stale")
    stale_ids = {str(item.get("artifact_id")) for item in artifact_state.get("stale_artifacts", []) if isinstance(item, dict)}
    if stale_ids.intersection({"knowledge_usage_report", "constraint_application_audit", "knowledge_conflict_report"}):
        blocking.append("knowledge_usage_audit_stale")
    allowed = sorted(set((context or {}).get("knowledge_policy", {}).get("allowed_classes", [])))
    enabled = bool((context or {}).get("knowledge_policy", {}).get("enabled")) and not blocking
    constraint_count = len((context or {}).get("hard_constraints", [])) + len((context or {}).get("negative_constraints", []))
    if selection.get("selected_packs") and not constraint_count and not blocking:
        warnings.append("no_eligible_constraints")
    return {
        "status": "blocked" if blocking else "review_required" if warnings else "ready",
        "selected": True,
        "enabled": enabled,
        "allowed_classes": allowed,
        "blocking_reasons": sorted(set(blocking)),
        "warning_reasons": sorted(set(warnings)),
        "knowledge_augmented_quality_claim_allowed": False,
        "artifacts": {
            "selection": KNOWLEDGE_PACK_SELECTION_JSON,
            "eligibility": KNOWLEDGE_ELIGIBILITY_REPORT_JSON if eligibility else None,
            "working_context": WORKING_CONTEXT_PACKET_JSON if context else None,
            "usage_report": KNOWLEDGE_USAGE_REPORT_JSON if usage else None,
            "constraint_audit": CONSTRAINT_APPLICATION_AUDIT_JSON if audit else None,
            "conflict_report": KNOWLEDGE_CONFLICT_REPORT_JSON if conflicts else None,
        },
    }


def _knowledge_inputs_changed(state_dir: Path, eligibility: dict[str, Any], context: dict[str, Any]) -> bool:
    for name, expected in context.get("input_hashes", {}).items():
        path = state_dir / str(name)
        if not path.is_file() or sha256_file(path) != expected:
            return True
    for item in eligibility.get("source_artifact_hashes", []):
        path = Path(str(item.get("path") or ""))
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            return True
    return False


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = read_json(path)
    return value if isinstance(value, dict) else None


def _first_target_locale(batch_plan: dict[str, Any]) -> str:
    locales = batch_plan.get("target_locales")
    if isinstance(locales, list) and locales:
        return str(locales[0])
    for batch in batch_plan.get("batches", []):
        if isinstance(batch, dict) and batch.get("target_locale"):
            return str(batch["target_locale"])
    return ""


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
