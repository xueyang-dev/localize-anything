from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .generation_strategy import GENERATION_STRATEGY_JSON
from .io_utils import read_json, read_jsonl, write_json, write_jsonl
from .segment_staleness import REUSE_DECISION_JSON, STALE_SEGMENTS_JSONL, read_reuse_decision, read_stale_segments
from .termbase_preflight import TERM_REVIEW_QUEUE_JSON, TERMBASE_PREFLIGHT_REPORT_JSON


SEGMENT_REGENERATION_PLAN_JSON = "segment-regeneration-plan.json"
REPAIR_REQUEST_JSON = "repair-request.json"
REPAIR_RESULT_JSON = "repair-result.json"
REPAIR_HISTORY_JSONL = "repair-history.jsonl"
GENERATION_HANDOFF_DECISION_JSON = "generation-handoff-decision.json"

REUSE = "reuse"
REGENERATE = "regenerate"
RE_REVIEW = "re_review"
TARGETED_REPAIR = "targeted_repair"
HUMAN_CONFIRM = "human_confirm"
BLOCKED = "blocked"

APPLIED = "applied"
PENDING_PROVIDER = "pending_provider"
PENDING_HUMAN = "pending_human"
SKIPPED_NOT_DETERMINISTIC = "skipped_not_deterministic"
FAILED_QA = "failed_qa"
NOT_APPLICABLE = "not_applicable"

TEXT_CHANGING_REPAIR_TYPES = {"placeholder_patch", "markup_patch", "escape_patch", "term_patch"}
PROVIDER_REPAIR_TYPES = {"risk_wording_patch", "style_patch", "coverage_patch", "regenerate_segment"}
OLD_PENDING_STATUSES = {"pending_provider_or_model_repair", "pending_human_confirmation", "pending_review"}
EXECUTION_PENDING_STATUSES = {PENDING_PROVIDER, PENDING_HUMAN, BLOCKED, SKIPPED_NOT_DETERMINISTIC, FAILED_QA}


def build_segment_regeneration_plan(
    state_dir: Path,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    stale_segments = read_stale_segments(state_dir)
    reuse_decision = read_reuse_decision(state_dir)
    context = _source_context(state_dir)
    plan_segments = [_plan_segment(segment, context) for segment in stale_segments]
    summary = _summary(plan_segments)
    decisions = _decisions(summary)
    plan = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-segment-regeneration-plan-v1",
        "run_id": run_id or reuse_decision.get("run_id") or _run_id_from_context(context),
        "status": _status(summary),
        "source_artifacts": _source_artifacts(state_dir),
        "reuse_decision_status": reuse_decision.get("status"),
        "summary": summary,
        "decisions": decisions,
        "quality_claims_forbidden": _forbidden_claims(decisions),
        "segments": plan_segments,
        "next_actions": _next_actions(summary),
    }
    requests = _repair_request_document(plan, plan_segments)
    results = _repair_result_document(plan, requests["requests"])
    history = _history_records(results["results"])
    if write:
        state_dir.mkdir(parents=True, exist_ok=True)
        write_json(state_dir / SEGMENT_REGENERATION_PLAN_JSON, plan)
        write_json(state_dir / REPAIR_REQUEST_JSON, requests)
        write_json(state_dir / REPAIR_RESULT_JSON, results)
        _append_history(state_dir / REPAIR_HISTORY_JSONL, history)
    return plan


def apply_repair_plan(
    state_dir: Path,
    *,
    generated_segments_path: Path | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    plan = read_segment_regeneration_plan(state_dir)
    request_document = read_repair_request(state_dir)
    generated_path, generated_segments, generated_by_id = _load_generated_segments(state_dir, generated_segments_path)
    term_context = _term_context(state_dir)
    results: list[dict[str, Any]] = []
    changed_generated = False
    for request in request_document.get("requests", []):
        if not isinstance(request, dict):
            continue
        result, replacement = _execute_repair_request(request, generated_by_id, term_context)
        results.append(result)
        if replacement is not None:
            segment = generated_by_id.get(str(request.get("segment_id") or ""))
            if segment is not None:
                segment["target"] = replacement
                segment["repair_status"] = APPLIED
                segment["repair_id"] = request.get("repair_id")
                changed_generated = True
                result["target_artifact_updated"] = True
                result["target_artifact"] = generated_path.name if generated_path else None
    summary = _repair_execution_summary(results)
    document = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-repair-result-v1",
        "run_id": run_id or plan.get("run_id") or request_document.get("run_id"),
        "status": _repair_execution_status(summary),
        "segment_regeneration_plan_path": SEGMENT_REGENERATION_PLAN_JSON,
        "repair_request_path": REPAIR_REQUEST_JSON,
        "generated_segments_path": generated_path.name if generated_path else None,
        "summary": summary,
        "results": results,
        "limitations": [
            "deterministic repair execution does not call a provider or LLM",
            "semantic rewrites and provider/model repairs remain pending",
            "target text is never fabricated when old target text is unavailable",
        ],
    }
    if write:
        state_dir.mkdir(parents=True, exist_ok=True)
        write_json(state_dir / REPAIR_RESULT_JSON, document)
        _append_history(state_dir / REPAIR_HISTORY_JSONL, _history_records(results))
        if changed_generated and generated_path:
            write_jsonl(generated_path, generated_segments)
    return document


def read_segment_regeneration_plan(state_dir: Path) -> dict[str, Any]:
    path = state_dir / SEGMENT_REGENERATION_PLAN_JSON
    if not path.is_file():
        raise ValueError(f"Missing segment regeneration plan: {path}")
    return read_json(path)


def read_repair_request(state_dir: Path) -> dict[str, Any]:
    path = state_dir / REPAIR_REQUEST_JSON
    if not path.is_file():
        raise ValueError(f"Missing repair request: {path}")
    return read_json(path)


def read_repair_result(state_dir: Path) -> dict[str, Any]:
    path = state_dir / REPAIR_RESULT_JSON
    if not path.is_file():
        raise ValueError(f"Missing repair result: {path}")
    return read_json(path)


def read_repair_history(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / REPAIR_HISTORY_JSONL
    if not path.is_file():
        raise ValueError(f"Missing repair history: {path}")
    return read_jsonl(path)


def segment_repair_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "segment_regeneration_plan": SEGMENT_REGENERATION_PLAN_JSON,
        "repair_request": REPAIR_REQUEST_JSON,
        "repair_result": REPAIR_RESULT_JSON,
        "repair_history": REPAIR_HISTORY_JSONL,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def segment_repair_summary(state_dir: Path) -> dict[str, Any]:
    path = state_dir / SEGMENT_REGENERATION_PLAN_JSON
    if not path.is_file():
        return {
            "status": "not_run",
            "artifact": None,
            "summary": {},
            "decisions": {},
            "pending_segments": [],
            "next_actions": [],
        }
    plan = read_json(path)
    result = _read_optional_json(state_dir / REPAIR_RESULT_JSON)
    execution_summary = result.get("summary", {}) if result else {}
    pending_result_segments = _pending_result_segments(result)
    if result and not _repair_result_has_pending(result):
        summary_status = "ready"
        decisions = {
            "generation_handoff_policy": "allowed",
            "delivery_apply_policy": "allowed",
            "apply_policy": "allowed",
            "full_quality_generation_handoff_allowed": True,
            "requires_deterministic_qa": bool(execution_summary.get("deterministic_qa_required_count", 0)),
            "review_required": False,
            "pending_required_repair_count": 0,
        }
        pending: list[dict[str, Any]] = []
        next_actions: list[str] = []
    elif result:
        summary_status = _status_with_execution(plan.get("status", "not_checked"), execution_summary)
        decisions = _decisions_with_execution(plan.get("decisions", {}), execution_summary)
        pending = pending_result_segments
        next_actions = _next_actions_with_execution(plan.get("next_actions", []), execution_summary)
    else:
        summary_status = plan.get("status", "not_checked")
        decisions = plan.get("decisions", {})
        pending = [
            _compact_plan_segment(item)
            for item in plan.get("segments", [])
            if item.get("action") in {REGENERATE, TARGETED_REPAIR, HUMAN_CONFIRM, BLOCKED}
            or item.get("requires_deterministic_qa")
        ]
        next_actions = plan.get("next_actions", [])
    summary = dict(plan.get("summary", {}))
    summary.update(execution_summary)
    return {
        "status": summary_status,
        "artifact": SEGMENT_REGENERATION_PLAN_JSON,
        "repair_request_artifact": REPAIR_REQUEST_JSON if (state_dir / REPAIR_REQUEST_JSON).is_file() else None,
        "repair_result_artifact": REPAIR_RESULT_JSON if (state_dir / REPAIR_RESULT_JSON).is_file() else None,
        "repair_history_artifact": REPAIR_HISTORY_JSONL if (state_dir / REPAIR_HISTORY_JSONL).is_file() else None,
        "summary": summary,
        "execution_summary": execution_summary,
        "decisions": decisions,
        "quality_claims_forbidden": plan.get("quality_claims_forbidden", []),
        "pending_segments": pending[:50],
        "next_actions": next_actions,
    }


def _plan_segment(segment: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    action = _action(segment)
    repair_type = _repair_type(segment, action)
    reason_codes = list(segment.get("reason_codes", []))
    required_constraints = _required_constraints(segment, context)
    human_confirmation = action == HUMAN_CONFIRM or bool(segment.get("high_risk") and action in {TARGETED_REPAIR, RE_REVIEW})
    target_hash = segment.get("dependency_hashes", {}).get("previous_generated_target_hash")
    plan = {
        "segment_id": segment.get("segment_id"),
        "resource_key": segment.get("resource_key"),
        "source_path": segment.get("source_path"),
        "action": action,
        "repair_type": repair_type,
        "reason_codes": reason_codes,
        "source_text_hash": segment.get("source_text_hash"),
        "previous_target_hash": target_hash,
        "source_artifact_refs": _source_artifact_refs(context),
        "required_constraints": required_constraints,
        "risk_level": _risk_level(segment),
        "human_confirmation_required": human_confirmation,
        "deterministic_qa_required": bool(segment.get("deterministic_qa_required")),
        "targeted_repair_allowed": bool(segment.get("targeted_repair_allowed")),
        "blocks_generation_handoff": action in {REGENERATE, TARGETED_REPAIR, HUMAN_CONFIRM, BLOCKED},
        "blocks_delivery_apply": action in {REGENERATE, TARGETED_REPAIR, HUMAN_CONFIRM, BLOCKED},
    }
    if action != REUSE:
        plan["repair_id"] = _repair_id(plan)
    return plan


def _action(segment: dict[str, Any]) -> str:
    classifications = set(segment.get("classifications", []))
    reasons = set(segment.get("reason_codes", []))
    if segment.get("state") == "blocked" or "blocked" in classifications:
        return BLOCKED
    if "stale_source_changed" in classifications:
        return REGENERATE
    if "placeholder_or_markup_signature_changed" in reasons:
        return REGENERATE
    if "stale_term_policy_changed" in classifications:
        return TARGETED_REPAIR if segment.get("targeted_repair_allowed") else REGENERATE
    if segment.get("high_risk") and segment.get("review_required") and "needs_re_review" in classifications:
        return HUMAN_CONFIRM
    if "needs_regeneration" in classifications or segment.get("state") == "needs_regeneration":
        return REGENERATE
    if "needs_re_review" in classifications or segment.get("state") == "needs_re_review":
        return RE_REVIEW
    return REUSE


def _repair_type(segment: dict[str, Any], action: str) -> str:
    classifications = set(segment.get("classifications", []))
    reasons = set(segment.get("reason_codes", []))
    if action == TARGETED_REPAIR and "stale_term_policy_changed" in classifications:
        return "term_patch"
    if action == REGENERATE and "placeholder_or_markup_signature_changed" in reasons:
        return "regenerate_segment"
    if action == REGENERATE:
        return "regenerate_segment"
    if action == HUMAN_CONFIRM:
        return "review_only"
    if action == RE_REVIEW:
        if "generation_strategy_changed" in reasons:
            return "style_patch"
        if "review_policy_changed" in reasons:
            return "review_only"
        return "review_only"
    return "review_only"


def _required_constraints(segment: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    return {
        "matched_terms": segment.get("matched_terms", []),
        "deterministic_qa_required": bool(segment.get("deterministic_qa_required")),
        "generation_strategy_status": context.get("generation_strategy", {}).get("status"),
        "handoff_status": context.get("generation_handoff_decision", {}).get("status"),
        "termbase_status": context.get("termbase_preflight_report", {}).get("status"),
    }


def _risk_level(segment: dict[str, Any]) -> str:
    if segment.get("high_risk"):
        return "high"
    return "low"


def _summary(segments: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "segment_count": len(segments),
        "reuse_count": _count_action(segments, REUSE),
        "regenerate_count": _count_action(segments, REGENERATE),
        "re_review_count": _count_action(segments, RE_REVIEW),
        "targeted_repair_count": _count_action(segments, TARGETED_REPAIR),
        "human_confirm_count": _count_action(segments, HUMAN_CONFIRM),
        "blocked_count": _count_action(segments, BLOCKED),
        "deterministic_qa_required_count": sum(bool(item.get("deterministic_qa_required")) for item in segments),
        "pending_repair_count": sum(item.get("action") in {REGENERATE, TARGETED_REPAIR, HUMAN_CONFIRM} for item in segments),
        "generation_handoff_blocking_count": sum(bool(item.get("blocks_generation_handoff")) for item in segments),
        "delivery_apply_blocking_count": sum(bool(item.get("blocks_delivery_apply")) for item in segments),
    }


def _decisions(summary: dict[str, int]) -> dict[str, Any]:
    blocked = summary.get("blocked_count", 0) > 0
    pending_required = summary.get("generation_handoff_blocking_count", 0) > 0
    review_required = summary.get("re_review_count", 0) > 0
    return {
        "generation_handoff_policy": "blocked" if blocked or pending_required else "warn" if review_required else "allowed",
        "delivery_apply_policy": "blocked" if blocked or summary.get("delivery_apply_blocking_count", 0) else "warn" if review_required else "allowed",
        "apply_policy": "blocked" if blocked or summary.get("delivery_apply_blocking_count", 0) else "warn" if review_required else "allowed",
        "full_quality_generation_handoff_allowed": not blocked and not pending_required and not review_required,
        "requires_deterministic_qa": summary.get("deterministic_qa_required_count", 0) > 0,
        "review_required": review_required or summary.get("human_confirm_count", 0) > 0,
        "pending_required_repair_count": summary.get("pending_repair_count", 0),
    }


def _status(summary: dict[str, int]) -> str:
    if summary.get("blocked_count", 0):
        return "blocked"
    if summary.get("human_confirm_count", 0):
        return "requires_human_confirmation"
    if summary.get("targeted_repair_count", 0):
        return "requires_repair"
    if summary.get("regenerate_count", 0):
        return "requires_regeneration"
    if summary.get("re_review_count", 0):
        return "requires_review"
    return "ready"


def _forbidden_claims(decisions: dict[str, Any]) -> list[str]:
    claims: set[str] = set()
    if decisions.get("generation_handoff_policy") in {"blocked", "warn"}:
        claims.add("full_quality_generation")
    if decisions.get("delivery_apply_policy") == "blocked":
        claims.add("safe_apply_readiness")
    if decisions.get("review_required"):
        claims.add("review_complete_status")
    return sorted(claims)


def _next_actions(summary: dict[str, int]) -> list[str]:
    actions: list[str] = []
    if summary.get("regenerate_count", 0):
        actions.append("Regenerate stale source or placeholder-changed segments before full-quality handoff or apply.")
    if summary.get("targeted_repair_count", 0):
        actions.append("Complete targeted repair requests before claiming repaired segment readiness.")
    if summary.get("human_confirm_count", 0):
        actions.append("Collect human confirmation for high-risk unresolved segments.")
    if summary.get("re_review_count", 0):
        actions.append("Re-review affected segments before claiming review-complete status.")
    if summary.get("deterministic_qa_required_count", 0):
        actions.append("Run deterministic QA for regenerated or repaired placeholder/markup-sensitive segments.")
    return actions


def _repair_request_document(plan: dict[str, Any], plan_segments: list[dict[str, Any]]) -> dict[str, Any]:
    requests = [_repair_request(plan, item) for item in plan_segments if item.get("action") != REUSE]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-repair-request-v1",
        "run_id": plan.get("run_id"),
        "status": "blocked" if plan.get("status") == "blocked" else "pending_repairs" if requests else "ready",
        "segment_regeneration_plan_path": SEGMENT_REGENERATION_PLAN_JSON,
        "summary": {
            "request_count": len(requests),
            "human_confirmation_required_count": sum(bool(item.get("human_confirmation_required")) for item in requests),
            "provider_or_model_required_count": sum(item.get("provider_or_model_required") for item in requests),
        },
        "requests": requests,
    }


def _repair_request(plan: dict[str, Any], segment: dict[str, Any]) -> dict[str, Any]:
    provider_required = segment.get("action") in {REGENERATE, TARGETED_REPAIR}
    return {
        "repair_id": segment.get("repair_id"),
        "segment_id": segment.get("segment_id"),
        "source_artifact_refs": segment.get("source_artifact_refs", {}),
        "repair_type": segment.get("repair_type"),
        "reason": ", ".join(segment.get("reason_codes", [])) or str(segment.get("action")),
        "old_target": None,
        "previous_target_hash": segment.get("previous_target_hash"),
        "source_hash": segment.get("source_text_hash"),
        "required_constraints": segment.get("required_constraints", {}),
        "risk_level": segment.get("risk_level"),
        "human_confirmation_required": bool(segment.get("human_confirmation_required")),
        "deterministic_qa_required": bool(segment.get("deterministic_qa_required")),
        "provider_or_model_required": provider_required,
        "status": "pending_provider_or_model_repair" if provider_required else "pending_human_confirmation" if segment.get("human_confirmation_required") else "pending_review",
        "plan_status": plan.get("status"),
    }


def _repair_result_document(plan: dict[str, Any], requests: list[dict[str, Any]]) -> dict[str, Any]:
    results = [_repair_result(request) for request in requests]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-repair-result-v1",
        "run_id": plan.get("run_id"),
        "status": "blocked" if plan.get("status") == "blocked" else "pending" if results else "ready",
        "segment_regeneration_plan_path": SEGMENT_REGENERATION_PLAN_JSON,
        "repair_request_path": REPAIR_REQUEST_JSON,
        "summary": {
            "result_count": len(results),
            "completed_count": sum(item.get("repair_status") == "completed" for item in results),
            "pending_provider_or_model_repair_count": sum(item.get("repair_status") == "pending_provider_or_model_repair" for item in results),
            "pending_human_confirmation_count": sum(item.get("repair_status") == "pending_human_confirmation" for item in results),
            "pending_review_count": sum(item.get("repair_status") == "pending_review" for item in results),
        },
        "results": results,
        "limitations": [
            "deterministic planning does not call an LLM",
            "provider/model repairs remain pending instead of fabricating target text",
        ],
    }


def _repair_result(request: dict[str, Any]) -> dict[str, Any]:
    status = str(request.get("status") or "pending_review")
    return {
        "repair_id": request.get("repair_id"),
        "segment_id": request.get("segment_id"),
        "repair_type": request.get("repair_type"),
        "repair_reason": request.get("reason"),
        "repair_status": status,
        "actor_type": "runtime_deterministic" if status == "completed" else "pending_provider_or_model" if request.get("provider_or_model_required") else "human",
        "source_hash": request.get("source_hash"),
        "previous_target_hash": request.get("previous_target_hash"),
        "new_target_hash": None,
        "new_target": None,
        "deterministic_qa_required": bool(request.get("deterministic_qa_required")),
    }


def _history_records(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "protocol_version": PROTOCOL_VERSION,
            "schema": "localize-anything-repair-history-v1",
            "repair_id": item.get("repair_id"),
            "segment_id": item.get("segment_id"),
            "source_hash": item.get("source_hash"),
            "previous_target_hash": item.get("previous_target_hash"),
            "new_target_hash": item.get("new_target_hash"),
            "repair_reason": item.get("repair_reason"),
            "repair_status": item.get("repair_status"),
            "actor_type": item.get("actor_type"),
            "deterministic_rule_used": item.get("deterministic_rule_used"),
            "no_patch_reason": item.get("no_patch_reason"),
        }
        for item in results
    ]


def _append_history(path: Path, records: list[dict[str, Any]]) -> None:
    existing = read_jsonl(path) if path.is_file() else []
    write_jsonl(path, existing + records)


def _execute_repair_request(
    request: dict[str, Any],
    generated_by_id: dict[str, dict[str, Any]],
    term_context: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    repair_type = str(request.get("repair_type") or "")
    old_target, old_target_source = _old_target_for_request(request, generated_by_id)
    base = _repair_execution_base(request, old_target, old_target_source)
    if _generated_target_mismatch(request, generated_by_id):
        return _finalize_execution_result(base, BLOCKED, "generated_target_does_not_match_repair_request_old_target"), None
    if _requires_human_confirmation(request) and not request.get("human_confirmed"):
        return _finalize_execution_result(base, PENDING_HUMAN, "human_confirmation_required"), None
    if repair_type in PROVIDER_REPAIR_TYPES:
        return _finalize_execution_result(base, PENDING_PROVIDER, "provider_or_model_repair_required"), None
    if repair_type == "review_only":
        return _finalize_execution_result(base, APPLIED, "review_only_no_target_change", rule="review_only_no_target_change"), None
    if repair_type not in TEXT_CHANGING_REPAIR_TYPES:
        return _finalize_execution_result(base, SKIPPED_NOT_DETERMINISTIC, "unsupported_deterministic_repair_type"), None
    if old_target is None:
        return _finalize_execution_result(base, PENDING_PROVIDER, "missing_old_target_text"), None

    if repair_type == "placeholder_patch":
        status, patched, reason, rule, qa = _apply_placeholder_patch(old_target, request)
    elif repair_type == "markup_patch":
        status, patched, reason, rule, qa = _apply_markup_patch(old_target, request)
    elif repair_type == "escape_patch":
        status, patched, reason, rule, qa = _apply_escape_patch(old_target)
    else:
        status, patched, reason, rule, qa = _apply_term_patch(old_target, request, term_context)

    result = _finalize_execution_result(base, status, reason, rule=rule, new_target=patched, qa_result=qa)
    replacement = patched if status == APPLIED and patched != old_target else None
    return result, replacement


def _repair_execution_base(request: dict[str, Any], old_target: str | None, old_target_source: str | None) -> dict[str, Any]:
    return {
        "repair_id": request.get("repair_id"),
        "segment_id": request.get("segment_id"),
        "repair_type": request.get("repair_type"),
        "repair_reason": request.get("reason"),
        "source_artifact_refs": request.get("source_artifact_refs", {}),
        "source_hash": request.get("source_hash"),
        "previous_target_hash": request.get("previous_target_hash"),
        "old_target_hash": _hash_text(old_target) if old_target is not None else None,
        "old_target_source": old_target_source,
        "new_target_hash": None,
        "new_target": None,
        "deterministic_qa_required": bool(request.get("deterministic_qa_required")),
        "target_artifact_updated": False,
    }


def _finalize_execution_result(
    result: dict[str, Any],
    status: str,
    reason: str,
    *,
    rule: str | None = None,
    new_target: str | None = None,
    qa_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = dict(result)
    updated["repair_status"] = status
    updated["actor_type"] = _actor_type_for_status(status)
    updated["no_patch_reason"] = reason if status != APPLIED else None
    updated["deterministic_rule_used"] = rule
    updated["qa_result"] = qa_result or {"status": "not_run", "checks": []}
    if status == APPLIED and new_target is not None:
        updated["new_target_hash"] = _hash_text(new_target)
        updated["new_target"] = new_target
    return updated


def _actor_type_for_status(status: str) -> str:
    if status == PENDING_PROVIDER:
        return "pending_provider_or_model"
    if status == PENDING_HUMAN:
        return "human"
    return "runtime_deterministic"


def _old_target_for_request(
    request: dict[str, Any],
    generated_by_id: dict[str, dict[str, Any]],
) -> tuple[str | None, str | None]:
    if isinstance(request.get("old_target"), str):
        return str(request.get("old_target")), "repair_request"
    segment = generated_by_id.get(str(request.get("segment_id") or ""))
    if segment and isinstance(segment.get("target"), str):
        return str(segment.get("target")), "generated_segments"
    return None, None


def _generated_target_mismatch(request: dict[str, Any], generated_by_id: dict[str, dict[str, Any]]) -> bool:
    if not isinstance(request.get("old_target"), str):
        return False
    segment = generated_by_id.get(str(request.get("segment_id") or ""))
    if not segment or not isinstance(segment.get("target"), str):
        return False
    return str(segment.get("target")) != str(request.get("old_target"))


def _requires_human_confirmation(request: dict[str, Any]) -> bool:
    risk_level = str(request.get("risk_level") or "").strip()
    return bool(request.get("human_confirmation_required")) or risk_level in {"high", "critical"}


def _apply_placeholder_patch(target: str, request: dict[str, Any]) -> tuple[str, str | None, str, str | None, dict[str, Any]]:
    placeholders = _required_placeholders(request)
    if not placeholders:
        return SKIPPED_NOT_DETERMINISTIC, None, "missing_source_placeholder_signature", None, _qa("not_run")
    if all(placeholder in target for placeholder in placeholders):
        return NOT_APPLICABLE, None, "required_placeholders_already_present", "placeholder_presence_check", _placeholder_qa(target, placeholders)
    patched = target
    changed = False
    for placeholder in placeholders:
        if placeholder in patched:
            continue
        for variant in _placeholder_variants(placeholder):
            if variant in patched:
                patched = patched.replace(variant, placeholder, 1)
                changed = True
                break
    if not changed:
        return SKIPPED_NOT_DETERMINISTIC, None, "placeholder_not_mechanically_recoverable", None, _placeholder_qa(target, placeholders)
    qa = _placeholder_qa(patched, placeholders)
    if qa["status"] != "pass":
        return FAILED_QA, None, "placeholder_qa_failed_after_patch", "placeholder_malformed_token_normalization", qa
    return APPLIED, patched, "placeholder_patch_applied", "placeholder_malformed_token_normalization", qa


def _placeholder_variants(placeholder: str) -> list[str]:
    variants: list[str] = []
    if placeholder.startswith("%"):
        variants.extend(
            [
                placeholder.replace("%", "% ", 1),
                placeholder.replace("%", "% ", 1).upper(),
                placeholder.upper(),
            ]
        )
        if "$" in placeholder:
            variants.append(placeholder.replace("$", "$ ", 1))
    if placeholder.startswith("{") and placeholder.endswith("}"):
        name = placeholder[1:-1].strip()
        variants.append("{ " + name + " }")
    return [variant for variant in dict.fromkeys(variants) if variant and variant != placeholder]


def _apply_markup_patch(target: str, request: dict[str, Any]) -> tuple[str, str | None, str, str | None, dict[str, Any]]:
    tags = _required_markup_tags(request)
    if len(tags) != 1:
        return SKIPPED_NOT_DETERMINISTIC, None, "markup_patch_requires_one_known_tag", None, _qa("not_run")
    tag = tags[0]
    open_tag = f"<{tag}>"
    close_tag = f"</{tag}>"
    if _markup_qa(target, [tag])["status"] == "pass":
        return NOT_APPLICABLE, None, "required_markup_already_present", "markup_presence_check", _markup_qa(target, [tag])
    if open_tag not in target and close_tag not in target and "<" not in target and ">" not in target:
        patched = f"{open_tag}{target}{close_tag}"
        rule = "wrap_target_with_known_markup_pair"
    elif open_tag in target and close_tag not in target:
        patched = target + close_tag
        rule = "restore_missing_closing_markup_tag"
    elif close_tag in target and open_tag not in target:
        patched = open_tag + target
        rule = "restore_missing_opening_markup_tag"
    else:
        return SKIPPED_NOT_DETERMINISTIC, None, "markup_not_structurally_recoverable", None, _markup_qa(target, [tag])
    qa = _markup_qa(patched, [tag])
    if qa["status"] != "pass":
        return FAILED_QA, None, "markup_qa_failed_after_patch", rule, qa
    return APPLIED, patched, "markup_patch_applied", rule, qa


def _apply_escape_patch(target: str) -> tuple[str, str | None, str, str | None, dict[str, Any]]:
    patched = _escape_bare_ampersands(target)
    if patched == target:
        return NOT_APPLICABLE, None, "no_mechanical_escape_issue_detected", "xml_ampersand_escape_check", _escape_qa(target)
    qa = _escape_qa(patched)
    if qa["status"] != "pass":
        return FAILED_QA, None, "escape_qa_failed_after_patch", "xml_ampersand_escape", qa
    return APPLIED, patched, "escape_patch_applied", "xml_ampersand_escape", qa


def _apply_term_patch(
    target: str,
    request: dict[str, Any],
    term_context: dict[str, Any],
) -> tuple[str, str | None, str, str | None, dict[str, Any]]:
    options = _term_replacement_options(request, term_context)
    if options.get("ambiguous"):
        return BLOCKED, None, "ambiguous_locked_or_approved_term_replacement", None, _qa("not_run")
    replacements = [
        {**item, "old_target": old_target}
        for item in options.get("items", [])
        for old_target in item.get("old_targets", [])
        if old_target and old_target in target and old_target != item.get("target_term")
    ]
    if not replacements:
        if any(item.get("target_term") and item["target_term"] in target for item in options.get("items", [])):
            return NOT_APPLICABLE, None, "approved_or_locked_term_already_present", "term_presence_check", _qa("pass")
        return SKIPPED_NOT_DETERMINISTIC, None, "no_exact_rejected_or_old_term_match", None, _qa("not_run")
    if len(replacements) != 1:
        return BLOCKED, None, "multiple_term_replacements_are_not_unambiguous", None, _qa("not_run")
    replacement = replacements[0]
    old_term = str(replacement["old_target"])
    target_term = str(replacement["target_term"])
    patched = target.replace(old_term, target_term, 1)
    if _placeholder_tokens(patched) != _placeholder_tokens(target) or _markup_tokens(patched) != _markup_tokens(target):
        return BLOCKED, None, "term_patch_would_change_placeholder_or_markup_signature", None, _qa("fail")
    qa = _term_qa(patched, target_term, old_term)
    if qa["status"] != "pass":
        return FAILED_QA, None, "term_qa_failed_after_patch", "locked_term_exact_replacement", qa
    return APPLIED, patched, "term_patch_applied", "locked_term_exact_replacement", qa


def _request_constraints(request: dict[str, Any]) -> dict[str, Any]:
    constraints = request.get("required_constraints", {})
    return constraints if isinstance(constraints, dict) else {}


def _required_placeholders(request: dict[str, Any]) -> list[str]:
    return _string_list(_request_constraints(request).get("placeholders"))


def _required_markup_tags(request: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for item in _list_value(_request_constraints(request).get("markup")):
        if isinstance(item, dict):
            value = str(item.get("tag") or item.get("name") or "").strip()
        else:
            value = str(item).strip()
        match = re.search(r"</?([A-Za-z][A-Za-z0-9:_-]*)", value)
        if match:
            value = match.group(1)
        value = value.strip("<>/ ")
        if value:
            tags.append(value)
    return list(dict.fromkeys(tags))


def _qa(status: str, checks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"status": status, "checks": checks or []}


def _placeholder_qa(target: str, placeholders: list[str]) -> dict[str, Any]:
    checks = [{"placeholder": placeholder, "present": placeholder in target} for placeholder in placeholders]
    return _qa("pass" if all(item["present"] for item in checks) else "fail", checks)


def _markup_qa(target: str, tags: list[str]) -> dict[str, Any]:
    checks = []
    for tag in tags:
        open_tag = f"<{tag}>"
        close_tag = f"</{tag}>"
        open_index = target.find(open_tag)
        close_index = target.find(close_tag)
        checks.append(
            {
                "tag": tag,
                "open_count": target.count(open_tag),
                "close_count": target.count(close_tag),
                "ordered": open_index >= 0 and close_index > open_index,
            }
        )
    return _qa(
        "pass"
        if all(item["open_count"] == item["close_count"] == 1 and item["ordered"] for item in checks)
        else "fail",
        checks,
    )


def _escape_qa(target: str) -> dict[str, Any]:
    return _qa("fail" if _BARE_AMPERSAND.search(target) else "pass", [{"bare_ampersand": bool(_BARE_AMPERSAND.search(target))}])


def _term_qa(target: str, approved_target: str, old_target: str) -> dict[str, Any]:
    checks = [
        {"check": "approved_term_present", "pass": approved_target in target},
        {"check": "old_or_forbidden_term_removed", "pass": old_target not in target},
    ]
    return _qa("pass" if all(item["pass"] for item in checks) else "fail", checks)


_BARE_AMPERSAND = re.compile(r"&(?!amp;|lt;|gt;|quot;|apos;|#[0-9]+;|#x[0-9A-Fa-f]+;)")
_PLACEHOLDER_TOKEN = re.compile(r"%\d*\$?[A-Za-z]|%[A-Za-z]|\{[A-Za-z_][A-Za-z0-9_]*\}")
_MARKUP_TOKEN = re.compile(r"</?[A-Za-z][A-Za-z0-9:_-]*(?:\s[^>]*)?>")


def _escape_bare_ampersands(target: str) -> str:
    return _BARE_AMPERSAND.sub("&amp;", target)


def _placeholder_tokens(target: str) -> list[str]:
    return _PLACEHOLDER_TOKEN.findall(target)


def _markup_tokens(target: str) -> list[str]:
    return _MARKUP_TOKEN.findall(target)


def _term_context(state_dir: Path) -> dict[str, Any]:
    approved: dict[str, set[str]] = {}
    forbidden: dict[str, set[str]] = {}
    for row in _read_csv_rows(state_dir / "term-registry.csv"):
        source_term = row.get("source_term", "").strip()
        target_term = row.get("target_term", "").strip()
        status = row.get("status", "").strip()
        if source_term and target_term and status in {"approved", "locked"}:
            approved.setdefault(source_term.casefold(), set()).add(target_term)
        if source_term and status in {"rejected", "deprecated", "obsolete"} and target_term:
            forbidden.setdefault(source_term.casefold(), set()).add(target_term)
        for forbidden_target in _split_multi_value(row.get("forbidden_targets", "")):
            forbidden.setdefault(source_term.casefold(), set()).add(forbidden_target)
    for row in _read_csv_rows(state_dir / "forbidden-translations.csv"):
        source_term = row.get("source_term", "").strip()
        forbidden_target = row.get("forbidden_target", "").strip()
        status = row.get("status", "").strip()
        if source_term and forbidden_target and (not status or status in {"approved", "locked", "rejected", "verified"}):
            forbidden.setdefault(source_term.casefold(), set()).add(forbidden_target)
    return {"approved": approved, "forbidden": forbidden}


def _term_replacement_options(request: dict[str, Any], term_context: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    ambiguous = False
    constraints = _request_constraints(request)
    request_old_targets = set(_string_list(constraints.get("old_targets")))
    request_old_targets.update(_string_list(constraints.get("forbidden_targets")))
    request_old_targets.update(_string_list(constraints.get("rejected_targets")))
    for source_term in _matched_term_names(request):
        key = source_term.casefold()
        targets = sorted(term_context.get("approved", {}).get(key, set()))
        if len(targets) != 1:
            ambiguous = True
            continue
        old_targets = set(term_context.get("forbidden", {}).get(key, set()))
        old_targets.update(request_old_targets)
        items.append({"source_term": source_term, "target_term": targets[0], "old_targets": sorted(old_targets)})
    return {"ambiguous": ambiguous, "items": items}


def _matched_term_names(request: dict[str, Any]) -> list[str]:
    constraints = _request_constraints(request)
    values = _list_value(constraints.get("matched_terms"))
    if not values:
        values = _list_value(constraints.get("source_terms"))
    if constraints.get("source_term"):
        values.append(constraints["source_term"])
    terms: list[str] = []
    for item in values:
        if isinstance(item, dict):
            value = str(item.get("source_term") or item.get("term") or item.get("text") or "").strip()
        else:
            value = str(item).strip()
        if value:
            terms.append(value)
    return list(dict.fromkeys(terms))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [
            {str(key): str(value or "").strip() for key, value in row.items() if key}
            for row in csv.DictReader(handle)
        ]


def _split_multi_value(value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []
    if value.startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    separator = "|" if "|" in value else ";"
    return [item.strip() for item in value.split(separator) if item.strip()]


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in _list_value(value) if str(item).strip()]


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _load_generated_segments(
    state_dir: Path,
    generated_segments_path: Path | None,
) -> tuple[Path | None, list[dict[str, Any]], dict[str, dict[str, Any]]]:
    candidates: list[Path] = []
    if generated_segments_path is not None:
        candidates.append(generated_segments_path.expanduser().resolve())
    else:
        candidates.extend([state_dir / "generated-segments.jsonl", state_dir / "generated.jsonl"])
    generated_path = next((path for path in candidates if path.is_file()), None)
    if generated_segments_path is not None and generated_path is None:
        raise ValueError(f"Missing generated segments artifact: {generated_segments_path}")
    if generated_path is None:
        return None, [], {}
    segments = [item for item in read_jsonl(generated_path) if isinstance(item, dict)]
    by_id = {str(item.get("segment_id") or ""): item for item in segments if item.get("segment_id")}
    return generated_path, segments, by_id


def _repair_execution_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    statuses = [str(item.get("repair_status") or "") for item in results]
    blocking_count = sum(status in {BLOCKED, FAILED_QA, SKIPPED_NOT_DETERMINISTIC} for status in statuses)
    pending_provider_count = statuses.count(PENDING_PROVIDER) + statuses.count("pending_provider_or_model_repair")
    pending_human_count = statuses.count(PENDING_HUMAN) + statuses.count("pending_human_confirmation")
    pending_review_count = statuses.count("pending_review")
    pending_required = blocking_count + pending_provider_count + pending_human_count
    return {
        "result_count": len(results),
        "completed_count": statuses.count("completed") + statuses.count(APPLIED),
        "pending_provider_or_model_repair_count": statuses.count("pending_provider_or_model_repair"),
        "pending_human_confirmation_count": statuses.count("pending_human_confirmation"),
        "pending_review_count": pending_review_count,
        "applied_count": statuses.count(APPLIED),
        "pending_provider_count": statuses.count(PENDING_PROVIDER),
        "pending_human_count": statuses.count(PENDING_HUMAN),
        "blocked_count": statuses.count(BLOCKED),
        "skipped_not_deterministic_count": statuses.count(SKIPPED_NOT_DETERMINISTIC),
        "failed_qa_count": statuses.count(FAILED_QA),
        "not_applicable_count": statuses.count(NOT_APPLICABLE),
        "deterministic_qa_required_count": sum(bool(item.get("deterministic_qa_required")) for item in results),
        "pending_required_repair_count": pending_required,
        "pending_repair_count": pending_required,
    }


def _repair_execution_status(summary: dict[str, int]) -> str:
    if summary.get("blocked_count", 0) or summary.get("failed_qa_count", 0):
        return "blocked"
    if summary.get("pending_required_repair_count", 0) or summary.get("pending_review_count", 0):
        return "pending"
    return "ready"


def _repair_result_has_pending(result: dict[str, Any]) -> bool:
    summary = result.get("summary", {}) if isinstance(result, dict) else {}
    if not isinstance(summary, dict):
        return True
    return (
        int(summary.get("pending_required_repair_count", 0))
        + int(summary.get("pending_review_count", 0))
        + int(summary.get("pending_provider_or_model_repair_count", 0))
        + int(summary.get("pending_human_confirmation_count", 0))
        > 0
    )


def _pending_result_segments(result: dict[str, Any]) -> list[dict[str, Any]]:
    if not result:
        return []
    pending: list[dict[str, Any]] = []
    for item in result.get("results", []):
        status = str(item.get("repair_status") or "")
        if status in EXECUTION_PENDING_STATUSES or status in OLD_PENDING_STATUSES:
            pending.append(_compact_repair_result(item))
    return pending


def _compact_repair_result(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "segment_id": item.get("segment_id"),
        "repair_type": item.get("repair_type"),
        "repair_id": item.get("repair_id"),
        "repair_status": item.get("repair_status"),
        "no_patch_reason": item.get("no_patch_reason"),
    }


def _decisions_with_execution(plan_decisions: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    blocked = (
        int(summary.get("pending_required_repair_count", 0))
        + int(summary.get("pending_provider_or_model_repair_count", 0))
        + int(summary.get("pending_human_confirmation_count", 0))
        > 0
    )
    review = int(summary.get("pending_review_count", 0)) > 0
    decisions = dict(plan_decisions)
    decisions.update(
        {
            "generation_handoff_policy": "blocked" if blocked else "warn" if review else "allowed",
            "delivery_apply_policy": "blocked" if blocked else "warn" if review else "allowed",
            "apply_policy": "blocked" if blocked else "warn" if review else "allowed",
            "full_quality_generation_handoff_allowed": not blocked and not review,
            "review_required": review or blocked,
            "pending_required_repair_count": int(summary.get("pending_required_repair_count", 0)),
        }
    )
    return decisions


def _status_with_execution(plan_status: str, summary: dict[str, Any]) -> str:
    if int(summary.get("blocked_count", 0)) or int(summary.get("failed_qa_count", 0)):
        return "blocked"
    if int(summary.get("pending_human_count", 0)) or int(summary.get("pending_human_confirmation_count", 0)):
        return "requires_human_confirmation"
    if int(summary.get("pending_required_repair_count", 0)):
        return "requires_repair"
    if int(summary.get("pending_review_count", 0)):
        return "requires_review"
    return plan_status


def _next_actions_with_execution(plan_actions: list[str], summary: dict[str, Any]) -> list[str]:
    actions = list(plan_actions)
    if int(summary.get("applied_count", 0)):
        actions.append("Rerun artifact state and delivery packaging so deterministic repair results are visible downstream.")
    if int(summary.get("failed_qa_count", 0)):
        actions.append("Resolve failed deterministic QA before delivery or apply.")
    if int(summary.get("skipped_not_deterministic_count", 0)):
        actions.append("Route skipped non-deterministic repairs to human review or provider/model repair.")
    if int(summary.get("pending_provider_count", 0)) or int(summary.get("pending_provider_or_model_repair_count", 0)):
        actions.append("Run provider/model repair only in a future explicit provider repair loop.")
    if int(summary.get("pending_human_count", 0)) or int(summary.get("pending_human_confirmation_count", 0)):
        actions.append("Collect human confirmation before applying high-risk repair results.")
    return list(dict.fromkeys(actions))


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _source_context(state_dir: Path) -> dict[str, Any]:
    return {
        "generation_strategy": _read_optional_json(state_dir / GENERATION_STRATEGY_JSON),
        "generation_handoff_decision": _read_optional_json(state_dir / GENERATION_HANDOFF_DECISION_JSON),
        "review_result": _read_optional_json(state_dir / "review-result.json"),
        "termbase_preflight_report": _read_optional_json(state_dir / TERMBASE_PREFLIGHT_REPORT_JSON),
        "term_review_queue": _read_optional_json(state_dir / TERM_REVIEW_QUEUE_JSON),
        "artifact_state": _read_optional_json(state_dir / "artifact-state.json"),
    }


def _source_artifacts(state_dir: Path) -> dict[str, str]:
    names = {
        "stale_segments": STALE_SEGMENTS_JSONL,
        "reuse_decision": REUSE_DECISION_JSON,
        "generation_strategy": GENERATION_STRATEGY_JSON,
        "generation_handoff_decision": GENERATION_HANDOFF_DECISION_JSON,
        "review_result": "review-result.json",
        "termbase_preflight_report": TERMBASE_PREFLIGHT_REPORT_JSON,
        "term_review_queue": TERM_REVIEW_QUEUE_JSON,
        "artifact_state": "artifact-state.json",
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def _source_artifact_refs(context: dict[str, Any]) -> dict[str, str]:
    return {key: value.get("schema", "present") for key, value in context.items() if isinstance(value, dict)}


def _run_id_from_context(context: dict[str, Any]) -> str | None:
    for value in context.values():
        if isinstance(value, dict) and value.get("run_id"):
            return str(value.get("run_id"))
    return None


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _count_action(segments: list[dict[str, Any]], action: str) -> int:
    return sum(item.get("action") == action for item in segments)


def _repair_id(segment: dict[str, Any]) -> str:
    payload = {
        "segment_id": segment.get("segment_id"),
        "action": segment.get("action"),
        "repair_type": segment.get("repair_type"),
        "source_text_hash": segment.get("source_text_hash"),
        "previous_target_hash": segment.get("previous_target_hash"),
        "reason_codes": segment.get("reason_codes", []),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "repair-" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _compact_plan_segment(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "segment_id": item.get("segment_id"),
        "resource_key": item.get("resource_key"),
        "action": item.get("action"),
        "repair_type": item.get("repair_type"),
        "repair_id": item.get("repair_id"),
        "human_confirmation_required": item.get("human_confirmation_required"),
        "blocks_generation_handoff": item.get("blocks_generation_handoff"),
        "blocks_delivery_apply": item.get("blocks_delivery_apply"),
    }
