from __future__ import annotations

import hashlib
import json
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
    pending = [
        _compact_plan_segment(item)
        for item in plan.get("segments", [])
        if item.get("action") in {REGENERATE, TARGETED_REPAIR, HUMAN_CONFIRM, BLOCKED}
        or item.get("requires_deterministic_qa")
    ]
    return {
        "status": plan.get("status", "not_checked"),
        "artifact": SEGMENT_REGENERATION_PLAN_JSON,
        "repair_request_artifact": REPAIR_REQUEST_JSON if (state_dir / REPAIR_REQUEST_JSON).is_file() else None,
        "repair_result_artifact": REPAIR_RESULT_JSON if (state_dir / REPAIR_RESULT_JSON).is_file() else None,
        "repair_history_artifact": REPAIR_HISTORY_JSONL if (state_dir / REPAIR_HISTORY_JSONL).is_file() else None,
        "summary": plan.get("summary", {}),
        "decisions": plan.get("decisions", {}),
        "quality_claims_forbidden": plan.get("quality_claims_forbidden", []),
        "pending_segments": pending[:50],
        "next_actions": plan.get("next_actions", []),
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
        }
        for item in results
    ]


def _append_history(path: Path, records: list[dict[str, Any]]) -> None:
    existing = read_jsonl(path) if path.is_file() else []
    write_jsonl(path, existing + records)


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
