from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .artifact_state import ARTIFACT_STATE_JSON, artifact_state_summary
from .generation_strategy import GENERATION_STRATEGY_JSON
from .io_utils import read_json, read_jsonl, write_json
from .localization_brief import LOCALIZATION_BRIEF_JSON
from .resolution_gate import BLOCKING_QUESTIONS_JSON, RESOLUTION_OPTIONS_JSON, USER_RESOLUTION_DECISIONS_JSONL
from .segment_repair import SEGMENT_REGENERATION_PLAN_JSON, segment_repair_summary
from .termbase_preflight import TERM_REVIEW_QUEUE_JSON, TERMBASE_PREFLIGHT_REPORT_JSON


GENERATION_HANDOFF_DECISION_JSON = "generation-handoff-decision.json"

FULL_QUALITY_FORBIDDEN_CLAIM = "full_quality_generation"
NON_OVERRIDABLE_PROVIDER_REASONS = {"unsafe_provider_policy", "provider_fallback_requested"}
CONTINUATION_OPTIONS = {
    "allow_partial_coverage",
    "switch_to_source_only_mode",
    "continue_only_draft_review",
    "defer_term_continue_downgraded",
}
DOWNGRADED_MODES = {
    "draft_only",
    "review_required",
    "allowed_with_warnings",
    "source_only_with_partial_coverage_warning",
    "synthetic_test",
}


def build_generation_handoff_decision(
    state_dir: Path,
    *,
    requested_mode: str = "full_quality",
    provider_policy: dict[str, Any] | None = None,
    coverage_policy: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    strategy = _read_optional_json(state_dir / GENERATION_STRATEGY_JSON)
    questions = _read_optional_json(state_dir / BLOCKING_QUESTIONS_JSON)
    resolution_options = _read_optional_json(state_dir / RESOLUTION_OPTIONS_JSON)
    term_report = _read_optional_json(state_dir / TERMBASE_PREFLIGHT_REPORT_JSON)
    term_queue = _read_optional_json(state_dir / TERM_REVIEW_QUEUE_JSON)
    decisions = _read_jsonl_if_exists(state_dir / USER_RESOLUTION_DECISIONS_JSONL)
    provider_policy = provider_policy or {"mode": "host_agent", "provider_controlled": False}
    coverage_policy = _merged_coverage_policy(strategy, coverage_policy)

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    forbidden_claims: set[str] = set()

    _check_strategy(strategy, blockers, warnings, forbidden_claims)
    unresolved_questions = _check_questions(questions, blockers, warnings, forbidden_claims)
    continuation_decisions = _continuation_decisions(decisions)
    _check_decision_options(decisions, resolution_options, blockers)
    _check_decision_overrides(decisions, blockers)
    _check_termbase(term_report, term_queue, blockers, warnings, forbidden_claims)
    _check_brief(strategy, warnings, forbidden_claims)
    _check_coverage(coverage_policy, continuation_decisions, warnings, forbidden_claims)
    _check_artifact_state(state_dir, blockers, warnings, forbidden_claims)
    _check_segment_repair_plan(state_dir, blockers, warnings, forbidden_claims)
    provider_backed_allowed = _check_provider_policy(provider_policy, blockers, warnings, forbidden_claims)

    hard_blocked = bool(blockers)
    full_quality_allowed = not hard_blocked and not warnings and requested_mode == "full_quality"
    handoff_allowed = not hard_blocked
    handoff_mode = _handoff_mode(
        requested_mode,
        warnings,
        coverage_policy,
        continuation_decisions,
        provider_policy,
    )
    if hard_blocked:
        status = "blocked"
        handoff_mode = "blocked"
        forbidden_claims.update(
            {
                FULL_QUALITY_FORBIDDEN_CLAIM,
                "safe_apply_readiness",
                "provider_backed_quality",
            }
        )
    elif full_quality_allowed:
        status = "ready"
    else:
        status = handoff_mode
        forbidden_claims.add(FULL_QUALITY_FORBIDDEN_CLAIM)
        forbidden_claims.add("safe_apply_readiness")

    if status != "ready" and _terminology_not_full(term_report, strategy):
        forbidden_claims.add("full_terminology_assurance")
    if coverage_policy.get("partial_coverage_exists") or coverage_policy.get("visible_ui_coverage_warning"):
        forbidden_claims.add("full_source_coverage")
    if unresolved_questions:
        forbidden_claims.add("review_complete_status")
    if not provider_backed_allowed or str(provider_policy.get("mode")) in {"synthetic_test", "synthetic"}:
        forbidden_claims.add("provider_backed_quality")

    decision = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-generation-handoff-decision-v1",
        "run_id": run_id or (strategy or {}).get("run_id") or (questions or {}).get("run_id"),
        "requested_mode": requested_mode,
        "status": status,
        "handoff_mode": handoff_mode,
        "full_quality_handoff_allowed": full_quality_allowed,
        "handoff_allowed": handoff_allowed,
        "provider_backed_generation_allowed": provider_backed_allowed and handoff_allowed,
        "apply_policy": "blocked" if hard_blocked else "warn" if status != "ready" else "allowed",
        "delivery_policy": "blocked" if hard_blocked else "warn" if status != "ready" else "allowed",
        "blockers": blockers,
        "warnings": warnings,
        "unresolved_questions": unresolved_questions,
        "continuation_decisions": continuation_decisions,
        "forbidden_quality_claims": sorted(forbidden_claims),
        "source_artifacts": generation_handoff_decision_source_artifacts(state_dir),
        "limitations": [
            "generation handoff enforcement is deterministic and does not perform translation",
            "downgraded handoffs cannot claim full quality, full terminology assurance, or safe apply readiness",
            "non-overridable provider safety blockers cannot be cleared by ordinary resolution decisions",
        ],
    }
    if write:
        state_dir.mkdir(parents=True, exist_ok=True)
        write_json(state_dir / GENERATION_HANDOFF_DECISION_JSON, decision)
    return decision


def read_generation_handoff_decision(state_dir: Path) -> dict[str, Any]:
    path = state_dir / GENERATION_HANDOFF_DECISION_JSON
    if not path.is_file():
        raise ValueError(f"Missing generation handoff decision: {path}")
    return read_json(path)


def generation_handoff_decision_summary(state_dir: Path) -> dict[str, Any]:
    path = state_dir / GENERATION_HANDOFF_DECISION_JSON
    if not path.is_file():
        return {
            "status": "not_run",
            "handoff_mode": "not_checked",
            "handoff_allowed": True,
            "full_quality_handoff_allowed": False,
            "artifact": None,
        }
    decision = read_json(path)
    return {
        "status": decision.get("status", "not_checked"),
        "handoff_mode": decision.get("handoff_mode", "not_checked"),
        "handoff_allowed": bool(decision.get("handoff_allowed", False)),
        "full_quality_handoff_allowed": bool(decision.get("full_quality_handoff_allowed", False)),
        "provider_backed_generation_allowed": bool(decision.get("provider_backed_generation_allowed", False)),
        "apply_policy": decision.get("apply_policy"),
        "delivery_policy": decision.get("delivery_policy"),
        "forbidden_quality_claims": decision.get("forbidden_quality_claims", []),
        "unresolved_question_count": len(decision.get("unresolved_questions", [])),
        "artifact": GENERATION_HANDOFF_DECISION_JSON,
    }


def generation_handoff_decision_asset_paths(state_dir: Path) -> dict[str, str]:
    return (
        {"generation_handoff_decision": GENERATION_HANDOFF_DECISION_JSON}
        if (state_dir / GENERATION_HANDOFF_DECISION_JSON).is_file()
        else {}
    )


def generation_handoff_decision_source_artifacts(state_dir: Path) -> dict[str, str]:
    names = {
        "generation_strategy": GENERATION_STRATEGY_JSON,
        "blocking_questions": BLOCKING_QUESTIONS_JSON,
        "resolution_options": RESOLUTION_OPTIONS_JSON,
        "user_resolution_decisions": USER_RESOLUTION_DECISIONS_JSONL,
        "termbase_preflight_report": TERMBASE_PREFLIGHT_REPORT_JSON,
        "term_review_queue": TERM_REVIEW_QUEUE_JSON,
        "localization_brief": LOCALIZATION_BRIEF_JSON,
        "artifact_state": ARTIFACT_STATE_JSON,
        "segment_regeneration_plan": SEGMENT_REGENERATION_PLAN_JSON,
    }
    return {key: value for key, value in names.items() if (state_dir / value).exists()}


def provider_generation_blocker(decision: dict[str, Any] | None) -> dict[str, Any] | None:
    if not decision:
        return None
    if not decision.get("handoff_allowed", False):
        return {
            "category": "generation_handoff_blocked",
            "message": "Generation handoff policy blocks provider execution.",
        }
    if not decision.get("provider_backed_generation_allowed", False):
        return {
            "category": "provider_generation_blocked",
            "message": "Generation handoff policy does not allow provider-backed generation.",
        }
    return None


def _check_strategy(
    strategy: dict[str, Any] | None,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    forbidden_claims: set[str],
) -> None:
    if not strategy:
        warnings.append(_issue("generation_strategy_missing", "Generation strategy is missing.", GENERATION_STRATEGY_JSON))
        forbidden_claims.add(FULL_QUALITY_FORBIDDEN_CLAIM)
        return
    if strategy.get("status") == "blocked" or strategy.get("generation_readiness") == "blocked":
        blockers.append(_issue("generation_strategy_blocked", "Generation strategy status is blocked.", GENERATION_STRATEGY_JSON))
    if strategy.get("work_packet_policy", {}).get("allow_generation") is False:
        blockers.append(_issue("allow_generation_false", "Generation strategy does not allow generation.", GENERATION_STRATEGY_JSON))
    if strategy.get("status") == "review_required" or strategy.get("generation_readiness") == "review_required":
        warnings.append(_issue("generation_strategy_review_required", "Generation strategy requires review before full-quality generation.", GENERATION_STRATEGY_JSON))
        forbidden_claims.add(FULL_QUALITY_FORBIDDEN_CLAIM)


def _check_questions(
    questions: dict[str, Any] | None,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    forbidden_claims: set[str],
) -> list[dict[str, Any]]:
    if not questions:
        return []
    unresolved = [item for item in questions.get("questions", []) if item.get("status") != "resolved"]
    for question in unresolved:
        issue = _issue(
            str(question.get("reason_code") or "unresolved_question"),
            str(question.get("reason") or "Resolution Gate question is unresolved."),
            BLOCKING_QUESTIONS_JSON,
            question_id=question.get("question_id"),
            severity=question.get("severity"),
        )
        if question.get("severity") in {"blocking", "critical"}:
            blockers.append(issue)
        else:
            warnings.append(issue)
    if unresolved:
        forbidden_claims.update({FULL_QUALITY_FORBIDDEN_CLAIM, "review_complete_status"})
    return [
        {
            "question_id": item.get("question_id"),
            "reason_code": item.get("reason_code"),
            "severity": item.get("severity"),
            "status": item.get("status"),
            "source_artifacts": item.get("source_artifacts", []),
        }
        for item in unresolved
    ]


def _check_decision_overrides(decisions: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> None:
    for decision in decisions:
        if decision.get("status", "accepted") != "accepted":
            continue
        reason_code = str(decision.get("reason_code") or "")
        option_id = str(decision.get("option_id") or "")
        if reason_code in NON_OVERRIDABLE_PROVIDER_REASONS and option_id != "block_provider_until_safe":
            blockers.append(
                _issue(
                    "non_overridable_safety_override",
                    "A user resolution decision attempted to override a non-overridable provider safety blocker.",
                    USER_RESOLUTION_DECISIONS_JSONL,
                    decision_id=decision.get("decision_id"),
                    non_overridable=True,
                )
            )


def _check_decision_options(
    decisions: list[dict[str, Any]],
    resolution_options: dict[str, Any] | None,
    blockers: list[dict[str, Any]],
) -> None:
    if not resolution_options:
        return
    known_options = {str(item.get("option_id")) for item in resolution_options.get("options", [])}
    for decision in decisions:
        if decision.get("status", "accepted") != "accepted":
            continue
        option_id = str(decision.get("option_id") or "")
        if option_id and option_id not in known_options:
            blockers.append(
                _issue(
                    "unknown_resolution_decision_option",
                    "A user resolution decision references an option that is not present in resolution-options.json.",
                    USER_RESOLUTION_DECISIONS_JSONL,
                    decision_id=decision.get("decision_id"),
                )
            )


def _check_termbase(
    term_report: dict[str, Any] | None,
    term_queue: dict[str, Any] | None,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    forbidden_claims: set[str],
) -> None:
    if not term_report:
        warnings.append(_issue("termbase_preflight_missing", "Termbase preflight report is missing.", TERMBASE_PREFLIGHT_REPORT_JSON))
        forbidden_claims.add("full_terminology_assurance")
        return
    summary = term_report.get("summary", {}) if isinstance(term_report.get("summary"), dict) else {}
    conflict_count = _as_int(summary.get("conflict_count"), len(term_report.get("conflicts", [])))
    high_risk_count = _as_int(summary.get("high_risk_unreviewed_count"), len(term_report.get("unreviewed_high_risk_terms", [])))
    review_count = _as_int(summary.get("review_required_count"), 0)
    if conflict_count:
        blockers.append(_issue("unresolved_term_conflicts", "Unresolved terminology conflicts block full-quality handoff.", TERMBASE_PREFLIGHT_REPORT_JSON, count=conflict_count))
        forbidden_claims.add("full_terminology_assurance")
    if high_risk_count:
        warnings.append(_issue("high_risk_unreviewed_terms", "High-risk unreviewed terms require human confirmation.", TERMBASE_PREFLIGHT_REPORT_JSON, count=high_risk_count))
        forbidden_claims.update({"full_terminology_assurance", "review_complete_status"})
    elif review_count:
        warnings.append(_issue("incomplete_terminology_assurance", "Terminology assurance is incomplete.", TERMBASE_PREFLIGHT_REPORT_JSON, count=review_count))
        forbidden_claims.add("full_terminology_assurance")
    if term_queue and term_queue.get("status") == "blocked_by_conflict":
        blockers.append(_issue("term_review_queue_blocked", "Term review queue is blocked by conflict.", TERM_REVIEW_QUEUE_JSON))


def _check_brief(strategy: dict[str, Any] | None, warnings: list[dict[str, Any]], forbidden_claims: set[str]) -> None:
    if not strategy:
        return
    brief = strategy.get("gates", {}).get("localization_brief", {})
    codes = set(strategy.get("work_packet_policy", {}).get("warning_codes", []))
    if brief.get("status") == "not_found" or "localization_brief_missing" in codes:
        warnings.append(_issue("localization_brief_missing", "Required localization brief is missing.", LOCALIZATION_BRIEF_JSON))
        forbidden_claims.add(FULL_QUALITY_FORBIDDEN_CLAIM)
    if _as_int(brief.get("required_human_confirmation_count"), 0):
        warnings.append(_issue("localization_brief_confirmation_required", "Localization brief still needs human confirmation.", LOCALIZATION_BRIEF_JSON))
        forbidden_claims.add(FULL_QUALITY_FORBIDDEN_CLAIM)


def _check_coverage(
    coverage_policy: dict[str, Any],
    continuation_decisions: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    forbidden_claims: set[str],
) -> None:
    if not (coverage_policy.get("partial_coverage_exists") or coverage_policy.get("visible_ui_coverage_warning")):
        return
    allowed = bool(coverage_policy.get("partial_coverage_allowed") or coverage_policy.get("source_only_mode"))
    allowed = allowed or any(item.get("option_id") in {"allow_partial_coverage", "switch_to_source_only_mode"} for item in continuation_decisions)
    warnings.append(
        _issue(
            "partial_source_coverage_allowed" if allowed else "partial_source_coverage_unaccepted",
            "Partial source coverage is present; full source coverage must not be claimed.",
            "inspect-summary",
        )
    )
    forbidden_claims.add("full_source_coverage")


def _check_provider_policy(
    provider_policy: dict[str, Any],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    forbidden_claims: set[str],
) -> bool:
    mode = str(provider_policy.get("mode") or "host_agent")
    provider_controlled = bool(provider_policy.get("provider_controlled") or mode == "real_provider")
    if mode in {"synthetic_test", "synthetic"}:
        forbidden_claims.add("provider_backed_quality")
        return False
    if provider_policy.get("fallback_requested") or provider_policy.get("synthetic_fallback_requested"):
        if mode == "real_provider":
            blockers.append(
                _issue(
                    "provider_fallback_requested",
                    "Synthetic fallback is not allowed in real provider mode.",
                    "provider-policy",
                    non_overridable=True,
                )
            )
            forbidden_claims.add("provider_backed_quality")
            return False
        warnings.append(_issue("synthetic_fallback_test_mode", "Synthetic fallback can only be used as explicit synthetic/test output.", "provider-policy"))
        forbidden_claims.add("provider_backed_quality")
        return False
    if not provider_controlled:
        return True
    if provider_policy.get("status") == "safe" or provider_policy.get("safe") is True:
        return True
    code = "unsafe_provider_policy" if provider_policy.get("status") == "unsafe" or provider_policy.get("unsafe") else "provider_policy_missing"
    blockers.append(
        _issue(
            code,
            "Provider policy is missing or unsafe for provider-controlled generation.",
            "provider-policy",
            non_overridable=True,
        )
    )
    forbidden_claims.add("provider_backed_quality")
    return False


def _check_artifact_state(
    state_dir: Path,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    forbidden_claims: set[str],
) -> None:
    summary = artifact_state_summary(state_dir)
    if summary.get("status") == "not_run":
        return
    stale_handoff = [
        item
        for item in summary.get("stale_artifacts", [])
        if item.get("artifact_id") != "generation_handoff_decision"
        and _artifact_affects_handoff(item)
    ]
    blocked_handoff = [
        item
        for item in summary.get("blocked_artifacts", [])
        if item.get("artifact_id") != "generation_handoff_decision"
        and _artifact_affects_handoff(item)
    ]
    if stale_handoff:
        blockers.append(
            _issue(
                "stale_artifacts_block_handoff",
                "Artifact state reports stale upstream evidence; regenerate affected artifacts before full-quality handoff.",
                ARTIFACT_STATE_JSON,
                stale_artifacts=stale_handoff,
            )
        )
        forbidden_claims.update({FULL_QUALITY_FORBIDDEN_CLAIM, "safe_apply_readiness", "review_complete_status"})
    if blocked_handoff:
        blockers.append(
            _issue(
                "blocked_artifacts_block_handoff",
                "Artifact state reports blocked upstream evidence; resolve it before handoff.",
                ARTIFACT_STATE_JSON,
                blocked_artifacts=blocked_handoff,
            )
        )
        forbidden_claims.update({FULL_QUALITY_FORBIDDEN_CLAIM, "safe_apply_readiness"})
    segment_staleness = summary.get("segment_staleness", {})
    segment_decisions = segment_staleness.get("decisions", {}) if isinstance(segment_staleness, dict) else {}
    segment_summary = segment_staleness.get("summary", {}) if isinstance(segment_staleness, dict) else {}
    if segment_decisions.get("generation_handoff_policy") == "blocked":
        blockers.append(
            _issue(
                "stale_segments_block_handoff",
                "Segment-level reuse decision requires regeneration or targeted repair before full-quality handoff.",
                ARTIFACT_STATE_JSON,
                segment_summary=segment_summary,
                stale_segments=segment_staleness.get("stale_segments", []),
            )
        )
        forbidden_claims.update({FULL_QUALITY_FORBIDDEN_CLAIM, "safe_apply_readiness", "review_complete_status"})
    elif segment_decisions.get("generation_handoff_policy") == "warn":
        warnings.append(
            _issue(
                "stale_segments_require_review",
                "Segment-level reuse decision requires re-review before full-quality handoff.",
                ARTIFACT_STATE_JSON,
                segment_summary=segment_summary,
                stale_segments=segment_staleness.get("stale_segments", []),
            )
        )
        forbidden_claims.update({FULL_QUALITY_FORBIDDEN_CLAIM, "review_complete_status"})


def _check_segment_repair_plan(
    state_dir: Path,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    forbidden_claims: set[str],
) -> None:
    summary = segment_repair_summary(state_dir)
    if summary.get("status") == "not_run":
        return
    decisions = summary.get("decisions", {})
    repair_summary = summary.get("summary", {})
    if decisions.get("generation_handoff_policy") == "blocked":
        blockers.append(
            _issue(
                "pending_segment_repairs_block_handoff",
                "Segment regeneration plan has pending required repairs before full-quality handoff.",
                SEGMENT_REGENERATION_PLAN_JSON,
                repair_summary=repair_summary,
                pending_segments=summary.get("pending_segments", []),
            )
        )
        forbidden_claims.update({FULL_QUALITY_FORBIDDEN_CLAIM, "safe_apply_readiness", "review_complete_status"})
    elif decisions.get("generation_handoff_policy") == "warn":
        warnings.append(
            _issue(
                "segment_repairs_require_review",
                "Segment regeneration plan requires re-review before full-quality handoff.",
                SEGMENT_REGENERATION_PLAN_JSON,
                repair_summary=repair_summary,
                pending_segments=summary.get("pending_segments", []),
            )
        )
        forbidden_claims.update({FULL_QUALITY_FORBIDDEN_CLAIM, "review_complete_status"})


def _artifact_affects_handoff(item: dict[str, Any]) -> bool:
    if item.get("artifact_id") in {
        "current_manifest",
        "source_inventory",
        "localization_brief_json",
        "candidate_terms",
        "term_review_queue",
        "term_review_decisions",
        "term_registry",
        "term_decisions",
        "forbidden_translations",
        "termbase_preflight_report",
        "generation_strategy",
        "blocking_questions",
        "resolution_options",
        "user_resolution_decisions",
        "segment_regeneration_plan",
        "repair_request",
        "repair_result",
    }:
        return True
    return "generation_handoff_decision" in item.get("downstream_affected", [])


def _handoff_mode(
    requested_mode: str,
    warnings: list[dict[str, Any]],
    coverage_policy: dict[str, Any],
    continuation_decisions: list[dict[str, Any]],
    provider_policy: dict[str, Any],
) -> str:
    if requested_mode in DOWNGRADED_MODES:
        return requested_mode
    if str(provider_policy.get("mode")) in {"synthetic_test", "synthetic"}:
        return "synthetic_test"
    if any(item.get("option_id") == "continue_only_draft_review" for item in continuation_decisions):
        return "draft_only"
    if coverage_policy.get("partial_coverage_exists") or coverage_policy.get("visible_ui_coverage_warning"):
        return "source_only_with_partial_coverage_warning"
    if warnings:
        codes = {str(item.get("code")) for item in warnings}
        if codes & {"high_risk_unreviewed_terms", "incomplete_terminology_assurance", "localization_brief_missing", "generation_strategy_review_required"}:
            return "review_required"
        return "allowed_with_warnings"
    return requested_mode


def _continuation_decisions(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "decision_id": item.get("decision_id"),
            "question_id": item.get("question_id"),
            "option_id": item.get("option_id"),
            "reason_code": item.get("reason_code"),
            "decided_by": item.get("decided_by"),
            "decided_at": item.get("decided_at"),
        }
        for item in decisions
        if item.get("status", "accepted") == "accepted" and item.get("option_id") in CONTINUATION_OPTIONS
    ]


def _merged_coverage_policy(strategy: dict[str, Any] | None, coverage_policy: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(coverage_policy or {})
    strategy_coverage = (strategy or {}).get("resolution_state", {}).get("coverage_policy", {})
    if isinstance(strategy_coverage, dict):
        merged.update({key: value for key, value in strategy_coverage.items() if key not in merged})
    if merged.get("visible_ui_coverage_warning"):
        merged["partial_coverage_exists"] = True
    return merged


def _terminology_not_full(term_report: dict[str, Any] | None, strategy: dict[str, Any] | None) -> bool:
    assurance = ""
    if term_report:
        assurance = str(term_report.get("terminology_assurance") or "")
    if not assurance and strategy:
        assurance = str(strategy.get("gates", {}).get("terminology", {}).get("terminology_assurance") or "")
    return assurance not in {"reviewed", "standard", "not_applicable"}


def _issue(code: str, message: str, artifact: str, **extra: Any) -> dict[str, Any]:
    issue = {"code": code, "message": message, "artifact": artifact}
    issue.update({key: value for key, value in extra.items() if value is not None})
    return issue


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = read_json(path)
    return value if isinstance(value, dict) else None


def _read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        return []
    return read_jsonl(path)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
