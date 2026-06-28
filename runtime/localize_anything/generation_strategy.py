from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, write_json
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
        },
        "work_packet_policy": {
            "allow_generation": allow_generation,
            "include_hard_constraints": True,
            "include_terminology_review": True,
            "include_generation_strategy": True,
            "blocked_reason_codes": [item["code"] for item in blockers],
            "warning_codes": [item["code"] for item in warnings],
        },
        "draft_request_policy": {
            "provider_agnostic": True,
            "provider_call_performed": False,
            "quality_claim": "no_full_assurance_until_reviews_complete" if warnings or blockers else "strategy_ready",
        },
        "blockers": blockers,
        "warnings": warnings,
        "artifacts": _generation_strategy_asset_paths(state_dir, brief, term_report),
        "limitations": [
            "strategy is deterministic and does not perform translation",
            "review_required still permits handoff generation but cannot claim full review or terminology assurance",
            "blocked strategy prevents generation handoff until blocking governance conflicts are resolved",
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
) -> dict[str, str]:
    artifacts = {"generation_strategy": GENERATION_STRATEGY_JSON}
    if brief is not None and (state_dir / LOCALIZATION_BRIEF_JSON).is_file():
        artifacts["localization_brief"] = LOCALIZATION_BRIEF_JSON
    if term_report is not None and (state_dir / TERMBASE_PREFLIGHT_REPORT_JSON).is_file():
        artifacts["termbase_preflight_report"] = TERMBASE_PREFLIGHT_REPORT_JSON
    return artifacts


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
