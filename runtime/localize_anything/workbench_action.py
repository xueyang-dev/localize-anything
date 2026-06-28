from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .evaluation import build_evaluation_scorecard
from .human_review import (
    CLAIM_ACCEPTANCE_DECISION_JSON,
    HUMAN_REVIEW_EVIDENCE_JSONL,
    SIGNOFF_RECORD_JSON,
    build_claim_acceptance_decision,
    create_signoff_record,
    record_human_review_evidence,
)
from .io_utils import read_json, read_jsonl, write_json, write_jsonl
from .workbench_queue import (
    WORKBENCH_CLAIM_QUEUE_JSON,
    WORKBENCH_REVIEW_QUEUE_JSON,
    WORKBENCH_SIGNOFF_SUMMARY_JSON,
    build_workbench_claim_queue,
    build_workbench_review_queue,
    build_workbench_signoff_summary,
)


WORKBENCH_ACTION_LOG_JSONL = "workbench-action-log.jsonl"
WORKBENCH_ACTION_RESULT_JSON = "workbench-action-result.json"

ACTION_TYPES = {
    "record_human_review_evidence",
    "accept_claim",
    "reject_claim",
    "downgrade_claim",
    "create_signoff",
    "reject_signoff",
    "request_follow_up",
    "acknowledge_forbidden_claim",
    "acknowledge_limitation",
    "mark_queue_item_addressed",
}


def perform_workbench_action(
    state_dir: Path,
    action: dict[str, Any],
    *,
    run_id: str | None = None,
    write_result: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    action_type = _action_type(action)
    actor = action.get("actor") if isinstance(action.get("actor"), dict) else {}
    actor_role = str(action.get("actor_role") or actor.get("role") or "unknown").strip()
    actor_reference = str(action.get("actor_reference") or actor.get("reference") or "").strip()
    payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
    action_id = str(action.get("action_id") or _stable_id("workbench-action", {"type": action_type, "actor": actor_role, "payload": payload})[:40])
    created_at = str(action.get("created_at") or _now())
    before = _status_snapshot(state_dir)
    affected: list[str] = []
    runtime_result: dict[str, Any]
    outcome = "accepted"
    try:
        runtime_result, affected, outcome = _delegate_action(state_dir, action_type, payload, run_id or action.get("run_id"))
        refreshed = _refresh_projection_artifacts(state_dir, run_id or action.get("run_id"))
    except ValueError as exc:
        runtime_result = {"status": "blocked", "message": str(exc)}
        affected = []
        outcome = "blocked"
        refreshed = _refresh_projection_artifacts(state_dir, run_id or action.get("run_id"), tolerate_errors=True)
    after = _status_snapshot(state_dir)
    log_record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-action-log-record-v1",
        "action_id": action_id,
        "action_type": action_type,
        "actor_role": actor_role,
        "actor_reference": actor_reference,
        "input_payload_summary": _payload_summary(payload),
        "affected_artifact_references": sorted(set(affected)),
        "before_status": before,
        "after_status": after,
        "runtime_validation_result": runtime_result,
        "created_at": created_at,
        "outcome": outcome,
    }
    records = read_workbench_action_log(state_dir)
    records.append(log_record)
    write_jsonl(state_dir / WORKBENCH_ACTION_LOG_JSONL, records)
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-action-result-v1",
        "artifact": WORKBENCH_ACTION_RESULT_JSON,
        "action_id": action_id,
        "action_type": action_type,
        "outcome": outcome,
        "runtime_validation_result": runtime_result,
        "affected_artifact_references": sorted(set(affected)),
        "refreshed_artifacts": refreshed,
        "action_log_artifact": WORKBENCH_ACTION_LOG_JSONL,
        "action_log_record": log_record,
    }
    if write_result:
        write_json(state_dir / WORKBENCH_ACTION_RESULT_JSON, result)
    return result


def read_workbench_action_log(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / WORKBENCH_ACTION_LOG_JSONL
    return read_jsonl(path) if path.is_file() else []


def read_workbench_action_result(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKBENCH_ACTION_RESULT_JSON)


def workbench_action_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "workbench_action_log": WORKBENCH_ACTION_LOG_JSONL,
        "workbench_action_result": WORKBENCH_ACTION_RESULT_JSON,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def _delegate_action(
    state_dir: Path,
    action_type: str,
    payload: dict[str, Any],
    run_id: str | None,
) -> tuple[dict[str, Any], list[str], str]:
    if action_type == "record_human_review_evidence":
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else payload
        result = record_human_review_evidence(state_dir, evidence, run_id=run_id)
        return {"status": "accepted", "result": result}, [HUMAN_REVIEW_EVIDENCE_JSONL], "accepted"
    if action_type in {"accept_claim", "reject_claim", "downgrade_claim"}:
        claims = _claims_from_payload(payload)
        accepted_risk = payload.get("accepted_risk") if isinstance(payload.get("accepted_risk"), dict) else {}
        if action_type == "downgrade_claim":
            accepted_risk = {**accepted_risk, "accepts_limitations": True}
        decision = build_claim_acceptance_decision(
            state_dir,
            requested_claims=claims,
            rejected_claims=claims if action_type == "reject_claim" else None,
            accepted_risk=accepted_risk,
            run_id=run_id,
        )
        if action_type == "reject_claim":
            outcome = "rejected"
        elif decision.get("status") == "blocked":
            outcome = "blocked"
        else:
            outcome = "accepted"
        return {"status": decision.get("status"), "decision": decision}, [CLAIM_ACCEPTANCE_DECISION_JSON], outcome
    if action_type in {"create_signoff", "reject_signoff"}:
        signoff = payload.get("signoff") if isinstance(payload.get("signoff"), dict) else payload
        if action_type == "reject_signoff":
            signoff = {**signoff, "status": "rejected", "rejected": True}
        record = create_signoff_record(state_dir, signoff, run_id=run_id)
        outcome = "rejected" if record.get("status") == "rejected" else "requires_follow_up" if record.get("status") == "requires_follow_up" else "accepted"
        return {"status": record.get("status"), "signoff_record": record}, [SIGNOFF_RECORD_JSON], outcome
    if action_type == "mark_queue_item_addressed":
        queue = build_workbench_review_queue(state_dir)
        item_id = str(payload.get("queue_item_id") or payload.get("item_id") or "").strip()
        if not item_id:
            raise ValueError("queue_item_id is required")
        if any(item.get("item_id") == item_id for item in queue.get("items", [])):
            return {"status": "blocked", "message": "underlying artifact state still requires this queue item"}, [WORKBENCH_REVIEW_QUEUE_JSON], "blocked"
        return {"status": "accepted", "message": "queue item is absent after artifact-backed regeneration"}, [WORKBENCH_REVIEW_QUEUE_JSON], "accepted"
    if action_type in {"request_follow_up", "acknowledge_forbidden_claim", "acknowledge_limitation"}:
        return {"status": "accepted", "message": f"{action_type} recorded without mutating readiness evidence"}, [], "requires_follow_up" if action_type == "request_follow_up" else "accepted"
    raise ValueError(f"Unsupported workbench action type: {action_type}")


def _refresh_projection_artifacts(state_dir: Path, run_id: str | None, *, tolerate_errors: bool = False) -> list[str]:
    refreshed: list[str] = []
    for artifact, refresh in (
        ("evaluation-scorecard.json", lambda: build_evaluation_scorecard(state_dir, run_id=run_id)),
        (WORKBENCH_REVIEW_QUEUE_JSON, lambda: build_workbench_review_queue(state_dir)),
        (WORKBENCH_CLAIM_QUEUE_JSON, lambda: build_workbench_claim_queue(state_dir)),
        (WORKBENCH_SIGNOFF_SUMMARY_JSON, lambda: build_workbench_signoff_summary(state_dir)),
    ):
        try:
            refresh()
            refreshed.append(artifact)
        except (OSError, ValueError, json.JSONDecodeError):
            if not tolerate_errors:
                raise
    return refreshed


def _action_type(action: dict[str, Any]) -> str:
    value = str(action.get("action_type") or "").strip()
    if value not in ACTION_TYPES:
        raise ValueError(f"action_type must be one of: {', '.join(sorted(ACTION_TYPES))}")
    return value


def _claims_from_payload(payload: dict[str, Any]) -> list[str]:
    if isinstance(payload.get("claims"), list):
        return [str(item) for item in payload["claims"]]
    claim = str(payload.get("claim") or "").strip()
    if not claim:
        raise ValueError("claim or claims is required")
    return [claim]


def _status_snapshot(state_dir: Path) -> dict[str, Any]:
    return {
        "evaluation_scorecard": _json_status(state_dir / "evaluation-scorecard.json", "overall_claim"),
        "claim_acceptance_decision": _json_status(state_dir / CLAIM_ACCEPTANCE_DECISION_JSON, "status"),
        "signoff_record": _json_status(state_dir / SIGNOFF_RECORD_JSON, "status"),
        "workbench_review_queue": _json_status(state_dir / WORKBENCH_REVIEW_QUEUE_JSON, "status"),
        "workbench_claim_queue": _json_status(state_dir / WORKBENCH_CLAIM_QUEUE_JSON, "status"),
        "workbench_signoff_summary": _json_status(state_dir / WORKBENCH_SIGNOFF_SUMMARY_JSON, "current_signoff_status"),
    }


def _json_status(path: Path, key: str) -> str:
    if not path.is_file():
        return "missing"
    value = read_json(path)
    if not isinstance(value, dict):
        return "unknown"
    return str(value.get(key) or value.get("status") or "unknown")


def _payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in ("claim", "claims", "queue_item_id", "item_id"):
        if key in payload:
            summary[key] = payload[key]
    if isinstance(payload.get("evidence"), dict):
        evidence = payload["evidence"]
        summary["reviewer_role"] = evidence.get("reviewer_role")
        summary["review_scope"] = evidence.get("review_scope")
    elif "reviewer_role" in payload:
        summary["reviewer_role"] = payload.get("reviewer_role")
    if isinstance(payload.get("signoff"), dict):
        signoff = payload["signoff"]
        summary["signed_role"] = signoff.get("signed_role")
        summary["authorizations"] = signoff.get("authorizations")
    elif "signed_role" in payload:
        summary["signed_role"] = payload.get("signed_role")
    return summary


def _stable_id(prefix: str, value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
