from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .generation_strategy import GENERATION_STRATEGY_JSON, read_generation_strategy
from .io_utils import read_json, read_jsonl, write_json
from .termbase_preflight import (
    TERM_REVIEW_QUEUE_JSON,
    TERMBASE_PREFLIGHT_REPORT_JSON,
    record_term_review_decision,
)


BLOCKING_QUESTIONS_JSON = "blocking-questions.json"
RESOLUTION_OPTIONS_JSON = "resolution-options.json"
USER_RESOLUTION_DECISIONS_JSONL = "user-resolution-decisions.jsonl"
RESOLUTION_SUMMARY_MD = "resolution-summary.md"

BLOCKING_SEVERITIES = {"blocking", "critical"}
REVIEW_SEVERITIES = {"review_required", "warning"}


def build_resolution_gate(
    state_dir: Path,
    generation_strategy: dict[str, Any] | None = None,
    *,
    context: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    strategy = generation_strategy or _read_generation_strategy_if_exists(state_dir)
    context = context or {}
    term_report = _read_optional_json(state_dir / TERMBASE_PREFLIGHT_REPORT_JSON)
    term_queue = _read_optional_json(state_dir / TERM_REVIEW_QUEUE_JSON)
    prior_decisions = _read_decisions(state_dir / USER_RESOLUTION_DECISIONS_JSONL)

    questions = _questions_from_strategy(strategy, term_report, term_queue)
    questions.extend(_coverage_questions(context))
    questions.extend(_provider_questions(context))
    questions.extend(_scenario_questions(strategy, context))
    questions = _dedupe_questions(questions)
    _apply_prior_decisions(questions, prior_decisions)

    options = build_resolution_options()
    options_by_id = {item["option_id"]: item for item in options["options"]}
    for question in questions:
        question["available_options"] = [
            option_id for option_id in question["available_options"] if option_id in options_by_id
        ]
        question["option_effects"] = [
            {
                "option_id": option_id,
                "effect": options_by_id[option_id]["effect"],
                "updates": options_by_id[option_id]["updates"],
                "risk_remaining": options_by_id[option_id]["risk_remaining"],
            }
            for option_id in question["available_options"]
        ]
        if question["recommended_default"] not in question["available_options"] and question["available_options"]:
            question["recommended_default"] = question["available_options"][0]

    summary = _summary(questions)
    gate = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-blocking-questions-v1",
        "run_id": run_id or strategy.get("run_id"),
        "status": _status(summary),
        "generation_strategy": {
            "status": strategy.get("status", "not_checked"),
            "generation_readiness": strategy.get("generation_readiness", "not_checked"),
            "route": strategy.get("route", {}),
            "artifact": GENERATION_STRATEGY_JSON if strategy else None,
        },
        "summary": summary,
        "questions": questions,
        "artifacts": _resolution_gate_artifacts(),
    }
    write_resolution_gate(state_dir, gate, options)
    return gate


def build_resolution_options() -> dict[str, Any]:
    options = [
        _option(
            "keep_blocked",
            "Keep blocked",
            "Do not proceed until the blocker is resolved in its source artifact.",
            ["term_conflict", "unsafe_provider_policy", "provider_fallback_requested", "unknown_operating_mode"],
            "Generation remains blocked.",
            ["generation_strategy"],
            "No new risk is accepted; delivery remains unavailable.",
            conservative=True,
        ),
        _option(
            "approve_term",
            "Approve term",
            "Approve a reviewed source-to-target term and sync it through term governance.",
            ["term_conflict", "unreviewed_high_risk_terms", "term_review_incomplete"],
            "Writes a term review decision and can feed hard constraints.",
            ["term_governance", "term_review", "generation_strategy"],
            "Other unresolved term questions may still block or downgrade generation.",
        ),
        _option(
            "reject_term",
            "Reject term",
            "Reject the candidate term for this scope.",
            ["term_conflict", "unreviewed_high_risk_terms", "term_review_incomplete"],
            "Writes a term review decision without creating a hard constraint.",
            ["term_review", "generation_strategy"],
            "Generation may still need downgraded assurance if related terms remain unresolved.",
        ),
        _option(
            "defer_term_continue_downgraded",
            "Defer term",
            "Defer the term and continue only with downgraded terminology assurance.",
            ["unreviewed_high_risk_terms", "term_review_incomplete"],
            "Records an explicit deferral; full terminology assurance remains unavailable.",
            ["term_review", "generation_strategy"],
            "The unresolved term can still require owner review after draft generation.",
        ),
        _option(
            "require_localization_brief",
            "Require brief",
            "Stop until localization brief confirmations are supplied.",
            ["localization_brief_missing", "localization_brief_confirmation_required", "unknown_scenario"],
            "Generation remains review-blocked until task intent is explicit.",
            ["localization_brief", "generation_strategy"],
            "No task-intent risk is accepted.",
            conservative=True,
        ),
        _option(
            "continue_only_draft_review",
            "Draft review only",
            "Continue only as draft/review output with no full-quality or full-assurance claim.",
            [
                "localization_brief_missing",
                "localization_brief_confirmation_required",
                "term_review_incomplete",
                "unreviewed_high_risk_terms",
                "unsafe_provider_policy",
                "provider_fallback_requested",
                "unknown_scenario",
            ],
            "Keeps generation downgraded and visible in strategy/resolution artifacts.",
            ["generation_strategy", "delivery_decision"],
            "Human review remains required before review_ready or apply decisions.",
        ),
        _option(
            "allow_partial_coverage",
            "Allow partial coverage",
            "Allow source-only or partial coverage with explicit warning.",
            ["partial_source_coverage"],
            "Records partial coverage allowance without claiming full visible UI coverage.",
            ["coverage_policy", "generation_strategy", "delivery_decision"],
            "Some visible strings may remain untranslated.",
        ),
        _option(
            "switch_to_source_only_mode",
            "Source-only mode",
            "Keep source-only coverage and do not include merged/dependency overlay resources.",
            ["partial_source_coverage"],
            "Documents that coverage is intentionally source-only.",
            ["coverage_policy", "generation_strategy"],
            "Dependency-provided visible UI may remain in the source language.",
        ),
        _option(
            "block_provider_until_safe",
            "Block provider",
            "Do not call a real provider until provider policy is safe.",
            ["unsafe_provider_policy", "provider_fallback_requested"],
            "Provider-backed generation remains blocked.",
            ["provider_policy", "generation_strategy"],
            "No provider fallback or unsafe provider risk is accepted.",
            conservative=True,
        ),
    ]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-resolution-options-v1",
        "status": "pass",
        "options": options,
    }


def write_resolution_gate(
    state_dir: Path,
    questions: dict[str, Any],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    if not (state_dir / USER_RESOLUTION_DECISIONS_JSONL).exists():
        (state_dir / USER_RESOLUTION_DECISIONS_JSONL).write_text("", encoding="utf-8")
    options = options or build_resolution_options()
    write_json(state_dir / BLOCKING_QUESTIONS_JSON, questions)
    write_json(state_dir / RESOLUTION_OPTIONS_JSON, options)
    (state_dir / RESOLUTION_SUMMARY_MD).write_text(render_resolution_summary(questions), encoding="utf-8", newline="\n")
    return questions


def record_user_resolution_decision(state_dir: Path, decision: dict[str, Any]) -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    questions_doc = read_blocking_questions(state_dir)
    options_doc = read_resolution_options(state_dir)
    by_question = {item["question_id"]: item for item in questions_doc.get("questions", [])}
    by_option = {item["option_id"]: item for item in options_doc.get("options", [])}
    question_id = str(decision.get("question_id") or "").strip()
    option_id = str(decision.get("option_id") or "").strip()
    if question_id not in by_question:
        raise ValueError(f"Unknown blocking question: {question_id}")
    if option_id not in by_option:
        raise ValueError(f"Unknown resolution option: {option_id}")
    question = by_question[question_id]
    if option_id not in question.get("available_options", []):
        raise ValueError(f"Option {option_id} is not available for question {question_id}")
    if question.get("reason_code") in {"unsafe_provider_policy", "provider_fallback_requested"} and option_id != "block_provider_until_safe":
        raise ValueError("Unsafe provider fallback questions can only be resolved by blocking provider-backed generation")

    now = datetime.now(UTC).isoformat()
    normalized = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-user-resolution-decision-v1",
        "decision_id": str(decision.get("decision_id") or _decision_id(question_id, option_id, now)),
        "question_id": question_id,
        "option_id": option_id,
        "status": str(decision.get("status") or "accepted"),
        "decided_by": str(decision.get("decided_by") or "workbench-user"),
        "decided_at": str(decision.get("decided_at") or now),
        "notes": str(decision.get("notes") or ""),
        "reason_code": question.get("reason_code"),
        "source_artifacts": question.get("source_artifacts", []),
        "effects": by_option[option_id].get("updates", []),
        "artifacts_updated": [],
    }
    if "term_review_decision" in decision:
        normalized["term_review_decision"] = decision["term_review_decision"]
    if "coverage_policy" in decision:
        normalized["coverage_policy"] = decision["coverage_policy"]

    if option_id in {"approve_term", "reject_term", "defer_term_continue_downgraded"} and question.get("affected_terms"):
        term_result = _record_term_resolution(state_dir, question, option_id, decision)
        normalized["artifacts_updated"].extend(term_result.get("artifacts_updated", []))
        if term_result.get("term_review_decision"):
            normalized["term_review_decision"] = term_result["term_review_decision"]

    strategy_result = _update_generation_strategy_resolution(state_dir, question, normalized)
    normalized["artifacts_updated"].extend(strategy_result.get("artifacts_updated", []))
    _append_jsonl(state_dir / USER_RESOLUTION_DECISIONS_JSONL, normalized)

    _mark_question_resolved(questions_doc, normalized)
    write_resolution_gate(state_dir, questions_doc, options_doc)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": "pass",
        "decision": normalized,
        "blocking_questions": questions_doc,
        "artifacts": resolution_gate_asset_paths(state_dir),
    }


def read_blocking_questions(state_dir: Path) -> dict[str, Any]:
    path = state_dir / BLOCKING_QUESTIONS_JSON
    if not path.is_file():
        raise ValueError(f"Missing blocking questions: {path}")
    return read_json(path)


def read_resolution_options(state_dir: Path) -> dict[str, Any]:
    path = state_dir / RESOLUTION_OPTIONS_JSON
    if not path.is_file():
        raise ValueError(f"Missing resolution options: {path}")
    return read_json(path)


def resolution_gate_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: value for key, value in _resolution_gate_artifacts().items() if (state_dir / value).exists()}


def _resolution_gate_artifacts() -> dict[str, str]:
    names = {
        "blocking_questions": BLOCKING_QUESTIONS_JSON,
        "resolution_options": RESOLUTION_OPTIONS_JSON,
        "user_resolution_decisions": USER_RESOLUTION_DECISIONS_JSONL,
        "resolution_summary": RESOLUTION_SUMMARY_MD,
    }
    return names


def resolution_gate_summary(state_dir: Path) -> dict[str, Any]:
    path = state_dir / BLOCKING_QUESTIONS_JSON
    if not path.is_file():
        return {
            "status": "not_run",
            "unresolved_count": 0,
            "unresolved_blocking_count": 0,
            "artifact": None,
        }
    questions = read_json(path)
    summary = questions.get("summary", {})
    return {
        "status": questions.get("status", "not_checked"),
        "unresolved_count": summary.get("unresolved_count", 0),
        "unresolved_blocking_count": summary.get("unresolved_blocking_count", 0),
        "resolved_count": summary.get("resolved_count", 0),
        "artifact": BLOCKING_QUESTIONS_JSON,
    }


def render_resolution_summary(questions: dict[str, Any]) -> str:
    lines = [
        "# Resolution Summary",
        "",
        f"- Status: `{questions.get('status')}`",
        f"- Unresolved: {questions.get('summary', {}).get('unresolved_count', 0)}",
        f"- Blocking: {questions.get('summary', {}).get('unresolved_blocking_count', 0)}",
        "",
    ]
    if questions.get("questions"):
        lines.append("## Questions")
        lines.append("")
        for question in questions["questions"]:
            lines.append(
                f"- `{question.get('question_id')}` `{question.get('status')}` "
                f"`{question.get('severity')}`: {question.get('reason')}"
            )
    return "\n".join(lines) + "\n"


def _questions_from_strategy(
    strategy: dict[str, Any],
    term_report: dict[str, Any] | None,
    term_queue: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    target_locale = str(strategy.get("target_locale") or "")
    term_gate = strategy.get("gates", {}).get("terminology", {})
    brief_gate = strategy.get("gates", {}).get("localization_brief", {})
    codes = set(strategy.get("work_packet_policy", {}).get("blocked_reason_codes", []))
    codes.update(strategy.get("work_packet_policy", {}).get("warning_codes", []))

    if "term_conflict" in codes or int(term_gate.get("conflict_count") or 0) > 0:
        conflicts = term_report.get("conflicts", []) if term_report else []
        if not conflicts:
            conflicts = [{"source_term": "", "type": "term_conflict"}]
        for conflict in conflicts:
            source_term = str(conflict.get("source_term") or "")
            questions.append(
                _question(
                    "term_conflict",
                    "Unresolved term conflict blocks safe generation.",
                    "blocking",
                    "terminology_owner",
                    ["keep_blocked", "approve_term", "reject_term"],
                    "keep_blocked",
                    source_artifacts=[_artifact(GENERATION_STRATEGY_JSON, "/blockers"), _artifact(TERMBASE_PREFLIGHT_REPORT_JSON, "/conflicts")],
                    affected_terms=[_term_ref(source_term, conflict, target_locale)] if source_term else [],
                )
            )

    if "unreviewed_high_risk_terms" in codes or int(term_gate.get("high_risk_unreviewed_count") or 0) > 0:
        terms = term_report.get("unreviewed_high_risk_terms", []) if term_report else []
        queue_terms = term_queue.get("terms", []) if term_queue else []
        by_candidate = {str(item.get("candidate_id")): item for item in queue_terms}
        by_source = {str(item.get("source_term")): item for item in queue_terms}
        if not terms and term_queue:
            terms = [
                item
                for item in queue_terms
                if item.get("status") in {"candidate", "needs_review"} and item.get("risk_level") in {"high", "critical"}
            ]
        if not terms:
            terms = [{"source_term": "", "candidate_id": ""}]
        for term in terms:
            questions.append(
                _question(
                    "unreviewed_high_risk_terms",
                    "High-risk terminology is unreviewed; generation must stay downgraded.",
                    "review_required",
                    "terminology_owner",
                    ["approve_term", "reject_term", "defer_term_continue_downgraded"],
                    "defer_term_continue_downgraded",
                    source_artifacts=[_artifact(TERMBASE_PREFLIGHT_REPORT_JSON, "/unreviewed_high_risk_terms")],
                    affected_terms=[
                        _term_ref(
                            str(term.get("source_term") or ""),
                            {**by_source.get(str(term.get("source_term")), {}), **by_candidate.get(str(term.get("candidate_id")), {}), **term},
                            target_locale,
                        )
                    ],
                    affected_segments=_segments_from_term({**by_candidate.get(str(term.get("candidate_id")), {}), **term}),
                )
            )

    if "term_review_incomplete" in codes and not any(item.get("reason_code") == "unreviewed_high_risk_terms" for item in questions):
        questions.append(
            _question(
                "term_review_incomplete",
                "Terminology assurance is incomplete and must remain downgraded.",
                "review_required",
                "terminology_owner",
                ["defer_term_continue_downgraded", "continue_only_draft_review"],
                "defer_term_continue_downgraded",
                source_artifacts=[_artifact(GENERATION_STRATEGY_JSON, "/warnings"), _artifact(TERMBASE_PREFLIGHT_REPORT_JSON, "/summary")],
            )
        )

    if "localization_brief_missing" in codes or brief_gate.get("status") == "not_found":
        questions.append(
            _question(
                "localization_brief_missing",
                "Localization brief is missing, so task intent is not explicit.",
                "review_required",
                "project_owner",
                ["require_localization_brief", "continue_only_draft_review"],
                "require_localization_brief",
                source_artifacts=[_artifact(GENERATION_STRATEGY_JSON, "/gates/localization_brief")],
            )
        )
    elif "localization_brief_confirmation_required" in codes or int(brief_gate.get("required_human_confirmation_count") or 0) > 0:
        questions.append(
            _question(
                "localization_brief_confirmation_required",
                "Localization brief still requires human confirmation.",
                "review_required",
                "project_owner",
                ["require_localization_brief", "continue_only_draft_review"],
                "require_localization_brief",
                source_artifacts=[_artifact(GENERATION_STRATEGY_JSON, "/gates/localization_brief")],
                affected_segments=[
                    {"item": item}
                    for item in brief_gate.get("required_human_confirmations", [])
                ],
            )
        )
    return questions


def _coverage_questions(context: dict[str, Any]) -> list[dict[str, Any]]:
    coverage = context.get("android_coverage") if isinstance(context.get("android_coverage"), dict) else {}
    coverage_policy = context.get("coverage_policy") if isinstance(context.get("coverage_policy"), dict) else {}
    partial_allowed = bool(coverage_policy.get("partial_coverage_allowed") or coverage.get("partial_coverage_allowed"))
    if coverage.get("visible_ui_coverage_warning") and not partial_allowed:
        return [
            _question(
                "partial_source_coverage",
                "Source-only coverage may leave visible UI strings untranslated.",
                "warning",
                "project_owner",
                ["allow_partial_coverage", "switch_to_source_only_mode"],
                "allow_partial_coverage",
                source_artifacts=[_artifact("inspect-summary", "/android_coverage")],
                affected_segments=[
                    {
                        "coverage_mode": coverage.get("coverage_mode"),
                        "merged_dependency_strings_detected": coverage.get("merged_dependency_strings_detected", 0),
                    }
                ],
            )
        ]
    return []


def _provider_questions(context: dict[str, Any]) -> list[dict[str, Any]]:
    provider = context.get("provider_policy") if isinstance(context.get("provider_policy"), dict) else {}
    questions: list[dict[str, Any]] = []
    if provider.get("status") == "unsafe" or provider.get("unsafe"):
        questions.append(
            _question(
                "unsafe_provider_policy",
                "Provider policy is unsafe for provider-backed generation.",
                "blocking",
                "developer",
                ["block_provider_until_safe"],
                "block_provider_until_safe",
                source_artifacts=[_artifact("provider-policy", "/")],
            )
        )
    if provider.get("mode") == "real_provider" and provider.get("fallback_requested"):
        questions.append(
            _question(
                "provider_fallback_requested",
                "Synthetic fallback was requested in real provider mode and must not be allowed silently.",
                "blocking",
                "developer",
                ["block_provider_until_safe"],
                "block_provider_until_safe",
                source_artifacts=[_artifact("provider-policy", "/fallback_requested")],
            )
        )
    return questions


def _scenario_questions(strategy: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    operating_mode = str(context.get("operating_mode") or strategy.get("operating_mode") or "")
    if operating_mode and operating_mode not in {
        "blind_benchmark",
        "greenfield_localization",
        "existing_locale_maintenance",
        "rewrite_or_harmonization",
    }:
        questions.append(
            _question(
                "unknown_operating_mode",
                "Operating mode is unknown, so generation policy cannot be trusted.",
                "blocking",
                "developer",
                ["keep_blocked", "require_localization_brief"],
                "keep_blocked",
                source_artifacts=[_artifact(GENERATION_STRATEGY_JSON, "/operating_mode")],
            )
        )
    scenario = str(context.get("scenario") or "").strip()
    if scenario == "unknown":
        questions.append(
            _question(
                "unknown_scenario",
                "Localization scenario is unknown and needs explicit task confirmation.",
                "review_required",
                "project_owner",
                ["require_localization_brief", "continue_only_draft_review"],
                "require_localization_brief",
                source_artifacts=[_artifact("localization-brief.json", "/task_intent/scenario")],
            )
        )
    return questions


def _question(
    reason_code: str,
    reason: str,
    severity: str,
    owner: str,
    options: list[str],
    recommended: str,
    *,
    source_artifacts: list[dict[str, Any]],
    affected_terms: list[dict[str, Any]] | None = None,
    affected_segments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    question_id = _question_id(reason_code, affected_terms or affected_segments or source_artifacts)
    return {
        "question_id": question_id,
        "reason_code": reason_code,
        "source_artifacts": source_artifacts,
        "reason": reason,
        "severity": severity,
        "responsible_owner_type": owner,
        "affected_segments": affected_segments or [],
        "affected_terms": affected_terms or [],
        "recommended_default": recommended,
        "available_options": options,
        "option_effects": [],
        "human_confirmation_required": True,
        "status": "unresolved",
    }


def _option(
    option_id: str,
    label: str,
    description: str,
    reason_codes: list[str],
    effect: str,
    updates: list[str],
    risk_remaining: str,
    *,
    conservative: bool = False,
) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "label": label,
        "description": description,
        "applies_to_reason_codes": reason_codes,
        "effect": effect,
        "updates": updates,
        "risk_remaining": risk_remaining,
        "conservative_default": conservative,
        "requires_human_confirmation": True,
    }


def _summary(questions: list[dict[str, Any]]) -> dict[str, int]:
    unresolved = [item for item in questions if item.get("status") != "resolved"]
    blocking = [item for item in unresolved if item.get("severity") in BLOCKING_SEVERITIES]
    review = [item for item in unresolved if item.get("severity") in REVIEW_SEVERITIES]
    return {
        "question_count": len(questions),
        "unresolved_count": len(unresolved),
        "unresolved_blocking_count": len(blocking),
        "review_required_count": len(review),
        "resolved_count": len(questions) - len(unresolved),
    }


def _status(summary: dict[str, int]) -> str:
    if summary["unresolved_blocking_count"]:
        return "blocked"
    if summary["unresolved_count"]:
        return "review_required"
    return "clear"


def _record_term_resolution(
    state_dir: Path,
    question: dict[str, Any],
    option_id: str,
    decision: dict[str, Any],
) -> dict[str, Any]:
    affected = question.get("affected_terms", [])
    first_term = affected[0] if affected else {}
    term_decision = dict(decision.get("term_review_decision") or {})
    term_decision.setdefault("candidate_id", first_term.get("candidate_id", ""))
    term_decision.setdefault("source_term", first_term.get("source_term", ""))
    term_decision.setdefault("target_locale", decision.get("target_locale") or first_term.get("target_locale", ""))
    term_decision.setdefault("term_type", first_term.get("term_type", "domain_term"))
    if option_id == "approve_term":
        term_decision.setdefault("status", decision.get("term_status", "approved"))
        term_decision.setdefault("target_term", decision.get("target_term", ""))
    elif option_id == "reject_term":
        term_decision.setdefault("status", "rejected")
    else:
        term_decision.setdefault("status", "deferred")
    term_decision.setdefault("notes", decision.get("notes", ""))
    term_decision.setdefault("decided_by", decision.get("decided_by", "workbench-user"))
    result = record_term_review_decision(state_dir, term_decision)
    return {
        "artifacts_updated": [
            TERM_REVIEW_QUEUE_JSON,
            TERMBASE_PREFLIGHT_REPORT_JSON,
            *result.get("artifacts", {}).values(),
        ],
        "term_review_decision": result.get("decision", term_decision),
    }


def _update_generation_strategy_resolution(
    state_dir: Path,
    question: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    path = state_dir / GENERATION_STRATEGY_JSON
    if not path.is_file():
        return {"artifacts_updated": []}
    strategy = read_json(path)
    resolution_state = strategy.setdefault("resolution_state", {"decisions": []})
    resolution_state.setdefault("decisions", []).append(
        {
            "decision_id": decision["decision_id"],
            "question_id": decision["question_id"],
            "option_id": decision["option_id"],
            "reason_code": question.get("reason_code"),
            "decided_at": decision["decided_at"],
        }
    )
    if decision["option_id"] in {"allow_partial_coverage", "switch_to_source_only_mode"}:
        resolution_state["coverage_policy"] = {
            "partial_coverage_allowed": decision["option_id"] == "allow_partial_coverage",
            "source_only_mode": decision["option_id"] == "switch_to_source_only_mode",
            "decision_id": decision["decision_id"],
            "full_coverage_claim": False,
        }
        strategy.setdefault("work_packet_policy", {}).setdefault("warning_codes", [])
        if "partial_coverage_allowed" not in strategy["work_packet_policy"]["warning_codes"]:
            strategy["work_packet_policy"]["warning_codes"].append("partial_coverage_allowed")
    if decision["option_id"] == "continue_only_draft_review":
        resolution_state["generation_policy"] = {
            "draft_review_only": True,
            "full_quality_claim": False,
            "decision_id": decision["decision_id"],
        }
    if decision["option_id"] == "block_provider_until_safe":
        resolution_state["provider_policy"] = {
            "provider_backed_generation_allowed": False,
            "unsafe_provider_fallback_allowed": False,
            "decision_id": decision["decision_id"],
            "reason_code": question.get("reason_code"),
        }
        strategy["status"] = "blocked"
        strategy["generation_readiness"] = "blocked"
        route = strategy.setdefault("route", {})
        route["mode"] = "blocked"
        route["assurance"] = "blocked"
        reason_codes = set(route.get("reason_codes", []))
        if question.get("reason_code"):
            reason_codes.add(str(question["reason_code"]))
        route["reason_codes"] = sorted(reason_codes)
        work_packet_policy = strategy.setdefault("work_packet_policy", {})
        work_packet_policy["allow_generation"] = False
        blocked_reason_codes = set(work_packet_policy.get("blocked_reason_codes", []))
        if question.get("reason_code"):
            blocked_reason_codes.add(str(question["reason_code"]))
        work_packet_policy["blocked_reason_codes"] = sorted(blocked_reason_codes)
        strategy.setdefault("draft_request_policy", {})["quality_claim"] = "blocked_by_provider_policy"
    write_json(path, strategy)
    return {"artifacts_updated": [GENERATION_STRATEGY_JSON]}


def _mark_question_resolved(questions_doc: dict[str, Any], decision: dict[str, Any]) -> None:
    for question in questions_doc.get("questions", []):
        if question.get("question_id") != decision["question_id"]:
            continue
        question["status"] = "resolved"
        question["resolution_decision_id"] = decision["decision_id"]
        question["selected_option_id"] = decision["option_id"]
    questions_doc["summary"] = _summary(questions_doc.get("questions", []))
    questions_doc["status"] = _status(questions_doc["summary"])


def _apply_prior_decisions(questions: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> None:
    latest = {item.get("question_id"): item for item in decisions if item.get("status", "accepted") == "accepted"}
    for question in questions:
        decision = latest.get(question.get("question_id"))
        if not decision:
            continue
        question["status"] = "resolved"
        question["resolution_decision_id"] = decision.get("decision_id")
        question["selected_option_id"] = decision.get("option_id")


def _dedupe_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for question in questions:
        by_id.setdefault(question["question_id"], question)
    return sorted(by_id.values(), key=lambda item: (item["severity"] != "blocking", item["reason_code"], item["question_id"]))


def _read_generation_strategy_if_exists(state_dir: Path) -> dict[str, Any]:
    try:
        return read_generation_strategy(state_dir)
    except ValueError:
        return {
            "protocol_version": PROTOCOL_VERSION,
            "status": "not_run",
            "generation_readiness": "not_checked",
            "work_packet_policy": {"blocked_reason_codes": [], "warning_codes": []},
            "gates": {},
            "route": {},
        }


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = read_json(path)
    return value if isinstance(value, dict) else None


def _read_decisions(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        return []
    return read_jsonl(path)


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _artifact(artifact: str, pointer: str) -> dict[str, str]:
    return {"artifact": artifact, "pointer": pointer}


def _term_ref(source_term: str, value: dict[str, Any], target_locale: str = "") -> dict[str, Any]:
    item = {
        "source_term": source_term,
        "candidate_id": value.get("candidate_id", ""),
        "term_type": value.get("term_type", value.get("type", "domain_term")),
        "risk_level": value.get("risk_level", ""),
        "target_locale": value.get("target_locale", target_locale),
    }
    if value.get("target_term"):
        item["target_term"] = value["target_term"]
    if value.get("target_terms"):
        item["target_terms"] = value["target_terms"]
    return item


def _segments_from_term(term: dict[str, Any]) -> list[dict[str, Any]]:
    segments = []
    for occurrence in term.get("occurrences", []) if isinstance(term.get("occurrences"), list) else []:
        segments.append(
            {
                "segment_id": occurrence.get("segment_id"),
                "source_path": occurrence.get("source_path"),
                "resource_key": occurrence.get("resource_key"),
            }
        )
    return segments[:20]


def _question_id(reason_code: str, evidence: Any) -> str:
    payload = json.dumps({"reason_code": reason_code, "evidence": evidence}, sort_keys=True, ensure_ascii=False)
    return "bq-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _decision_id(question_id: str, option_id: str, decided_at: str) -> str:
    payload = json.dumps([question_id, option_id, decided_at], sort_keys=True)
    return "urd-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
