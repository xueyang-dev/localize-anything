from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .document_decision import record_document_decision, record_leadership_review_evidence
from .human_review import build_claim_acceptance_decision, create_signoff_record, record_human_review_evidence
from .io_utils import read_json, read_jsonl, write_json, write_jsonl
from .knowledge_repair_closure import (
    build_knowledge_readiness_impact_report,
    build_knowledge_recompute_plan,
    build_knowledge_recompute_result,
    build_knowledge_repair_closure_decision,
)
from .knowledge_repair_result import record_knowledge_repair_result
from .knowledge_review_confirmation import record_knowledge_audit_resolution, record_knowledge_constraint_review_evidence
from .readiness_authorization import (
    APPLY_READINESS_REPORT_JSON,
    DELIVERY_READINESS_REPORT_JSON,
    MANUAL_FOLLOWUP_GAP_REPORT_JSON,
    READINESS_AUTHORIZATION_MATRIX_JSON,
    build_readiness_reports,
)


WORKBENCH_READINESS_ACTION_QUEUE_JSON = "workbench-readiness-action-queue.json"
WORKBENCH_READINESS_ACTION_RESULT_JSON = "workbench-readiness-action-result.json"
WORKBENCH_READINESS_ACTION_LOG_JSONL = "workbench-readiness-action-log.jsonl"

ACTION_TYPES = {
    "record_human_review",
    "accept_claim",
    "reject_claim",
    "create_signoff",
    "reject_signoff",
    "record_document_decision",
    "record_leadership_review",
    "record_knowledge_audit_resolution",
    "record_knowledge_constraint_review",
    "record_knowledge_repair_result",
    "request_recompute",
    "acknowledge_forbidden_claim",
    "acknowledge_limitation",
    "request_follow_up",
}

GAP_ITEM_TYPES = {
    "term_decision_required": "term_decision_action_required",
    "human_review_required": "human_review_action_required",
    "native_review_required": "human_review_action_required",
    "professional_review_required": "human_review_action_required",
    "claim_acceptance_required": "claim_acceptance_action_required",
    "signoff_required": "signoff_action_required",
    "leadership_review_required": "leadership_review_action_required",
    "document_decision_required": "document_decision_action_required",
    "knowledge_review_required": "knowledge_review_action_required",
    "knowledge_conflict_resolution_required": "knowledge_conflict_resolution_action_required",
    "knowledge_repair_reconciliation_required": "knowledge_repair_result_action_required",
    "repair_closure_recompute_required": "repair_closure_recompute_action_required",
    "provider_policy_resolution_required": "provider_policy_action_required",
    "coverage_confirmation_required": "coverage_confirmation_action_required",
    "artifact_refresh_required": "artifact_refresh_action_required",
    "forbidden_claim_acknowledgement_required": "forbidden_claim_action_required",
    "apply_authorization_required": "apply_authorization_action_required",
}

AVAILABLE_ACTIONS = {
    "term_decision_action_required": ["request_follow_up"],
    "human_review_action_required": ["record_human_review", "request_follow_up"],
    "claim_acceptance_action_required": ["accept_claim", "reject_claim", "acknowledge_forbidden_claim"],
    "signoff_action_required": ["create_signoff", "reject_signoff", "request_follow_up"],
    "leadership_review_action_required": ["record_leadership_review", "request_follow_up"],
    "document_decision_action_required": ["record_document_decision", "request_follow_up"],
    "knowledge_review_action_required": ["record_knowledge_audit_resolution", "record_knowledge_constraint_review", "request_follow_up"],
    "knowledge_conflict_resolution_action_required": ["record_knowledge_audit_resolution", "request_follow_up"],
    "knowledge_repair_result_action_required": ["record_knowledge_repair_result", "request_follow_up"],
    "repair_closure_recompute_action_required": ["request_recompute", "request_follow_up"],
    "provider_policy_action_required": ["request_follow_up"],
    "coverage_confirmation_action_required": ["acknowledge_limitation", "request_follow_up"],
    "artifact_refresh_action_required": ["request_recompute", "request_follow_up"],
    "apply_authorization_action_required": ["create_signoff", "request_follow_up"],
    "delivery_authorization_action_required": ["create_signoff", "request_follow_up"],
    "forbidden_claim_action_required": ["acknowledge_forbidden_claim", "acknowledge_limitation", "request_follow_up"],
}


def build_workbench_readiness_action_queue(state_dir: Path, *, run_id: str | None = None, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    reports = build_readiness_reports(state_dir, run_id=run_id, write=True)
    matrix = reports["readiness_authorization_matrix"]
    gaps = reports["manual_followup_gap_report"]
    apply_report = reports["apply_readiness_report"]
    delivery_report = reports["delivery_readiness_report"]
    items = [_queue_item(gap, matrix) for gap in gaps.get("gaps", []) if isinstance(gap, dict)]
    _append_authorization_items(items, matrix)
    queue = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-readiness-action-queue-v1",
        "artifact": WORKBENCH_READINESS_ACTION_QUEUE_JSON,
        "run_id": run_id or matrix.get("run_id") or gaps.get("run_id"),
        "status": "blocked" if any(item["blocking_delivery"] or item["blocking_apply"] for item in items) else "ready_with_warnings" if items else "ready",
        "items": items,
        "summary": {
            "item_count": len(items),
            "delivery_blocking_count": sum(bool(item["blocking_delivery"]) for item in items),
            "apply_blocking_count": sum(bool(item["blocking_apply"]) for item in items),
            "production_blocking_count": sum(bool(item["blocking_production_ready_claim"]) for item in items),
            "stale_evidence_count": sum(bool(item["stale_evidence_involved"]) for item in items),
        },
        "readiness_status": {
            "delivery": matrix.get("delivery_readiness_status", "unknown"),
            "apply": matrix.get("apply_readiness_status", "unknown"),
            "review": matrix.get("review_readiness_status", "unknown"),
            "production": matrix.get("production_readiness_status", "unknown"),
        },
        "forbidden_claims": matrix.get("forbidden_claims", []),
        "limitations": list(dict.fromkeys(_strings(matrix.get("limitations")) + _strings(apply_report.get("safe_apply_limitations")) + _strings(delivery_report.get("limitations")))),
        "source_artifacts": _source_artifacts(
            state_dir,
            [READINESS_AUTHORIZATION_MATRIX_JSON, MANUAL_FOLLOWUP_GAP_REPORT_JSON, APPLY_READINESS_REPORT_JSON, DELIVERY_READINESS_REPORT_JSON],
        ),
    }
    if write:
        write_json(state_dir / WORKBENCH_READINESS_ACTION_QUEUE_JSON, queue)
    return queue


def perform_workbench_readiness_action(
    state_dir: Path,
    action: dict[str, Any],
    *,
    run_id: str | None = None,
    write_result: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    action_type = _required_action_type(action)
    payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
    actor = action.get("actor") if isinstance(action.get("actor"), dict) else {}
    actor_role = str(action.get("actor_role") or actor.get("role") or "unknown").strip()
    actor_reference = str(action.get("actor_reference") or actor.get("reference") or "").strip()
    target_queue_item_id = str(action.get("target_queue_item_id") or payload.get("target_queue_item_id") or payload.get("queue_item_id") or "")
    target_gap_id = str(action.get("target_gap_id") or payload.get("target_gap_id") or payload.get("gap_id") or "")
    action_id = str(action.get("action_id") or _stable_id("readiness-action", {"type": action_type, "target": target_queue_item_id or target_gap_id, "payload": payload})[:40])
    before = _readiness_snapshot(state_dir)
    runtime_result, affected, outcome = _delegate_action(state_dir, action_type, payload, run_id or action.get("run_id"))
    refreshed = _refresh_readiness_artifacts(state_dir, run_id or action.get("run_id"), tolerate_errors=outcome in {"blocked", "requires_follow_up"})
    queue = build_workbench_readiness_action_queue(state_dir, run_id=run_id or action.get("run_id"), write=True)
    refreshed.append(WORKBENCH_READINESS_ACTION_QUEUE_JSON)
    after = _readiness_snapshot(state_dir)
    remaining_blockers = list(after.get("matrix", {}).get("blockers", []))
    remaining_forbidden = list(after.get("matrix", {}).get("forbidden_claims", []))
    status = _result_status(outcome, runtime_result)
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-readiness-action-result-v1",
        "artifact": WORKBENCH_READINESS_ACTION_RESULT_JSON,
        "action_id": action_id,
        "requested_action_type": action_type,
        "target_queue_item_id": target_queue_item_id,
        "target_gap_id": target_gap_id,
        "actor_role": actor_role,
        "actor_reference": actor_reference,
        "status": status,
        "runtime_artifacts_written_or_updated": sorted(set(affected)),
        "source_artifact_references": _source_refs_for_action(action_type, payload, target_queue_item_id, target_gap_id),
        "refreshed_artifacts": sorted(set(refreshed)),
        "remaining_blockers": remaining_blockers,
        "remaining_forbidden_claims": remaining_forbidden,
        "readiness_impact": {
            "before": before.get("status", {}),
            "after": after.get("status", {}),
            "queue_status": queue.get("status", "unknown"),
        },
        "limitations": _result_limitations(action_type, status, remaining_forbidden),
        "next_action": _next_action(status, queue, after),
        "runtime_validation_result": runtime_result,
    }
    log_record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-readiness-action-log-record-v1",
        "action_id": action_id,
        "action_type": action_type,
        "actor_role": actor_role,
        "actor_reference": actor_reference,
        "target_gap_id": target_gap_id,
        "target_queue_item_id": target_queue_item_id,
        "input_payload_summary": _payload_summary(payload),
        "runtime_writer_delegated_to": _writer_for_action(action_type),
        "affected_artifact_references": sorted(set(affected)),
        "before_readiness_status": before.get("status", {}),
        "after_readiness_status": after.get("status", {}),
        "runtime_validation_result": runtime_result,
        "created_at": str(action.get("created_at") or _now()),
        "outcome": status,
        "limitations": result["limitations"],
        "follow_up_required": status in {"blocked", "requires_follow_up", "stale"},
    }
    records = read_workbench_readiness_action_log(state_dir)
    records.append(log_record)
    write_jsonl(state_dir / WORKBENCH_READINESS_ACTION_LOG_JSONL, records)
    result["action_log_artifact"] = WORKBENCH_READINESS_ACTION_LOG_JSONL
    result["action_log_record"] = log_record
    if write_result:
        write_json(state_dir / WORKBENCH_READINESS_ACTION_RESULT_JSON, result)
    return result


def read_workbench_readiness_action_queue(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKBENCH_READINESS_ACTION_QUEUE_JSON)


def read_workbench_readiness_action_result(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKBENCH_READINESS_ACTION_RESULT_JSON)


def read_workbench_readiness_action_log(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / WORKBENCH_READINESS_ACTION_LOG_JSONL
    return read_jsonl(path) if path.is_file() else []


def workbench_readiness_action_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "workbench_readiness_action_queue": WORKBENCH_READINESS_ACTION_QUEUE_JSON,
        "workbench_readiness_action_result": WORKBENCH_READINESS_ACTION_RESULT_JSON,
        "workbench_readiness_action_log": WORKBENCH_READINESS_ACTION_LOG_JSONL,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def _queue_item(gap: dict[str, Any], matrix: dict[str, Any]) -> dict[str, Any]:
    gap_type = str(gap.get("gap_type") or "manual_followup_required")
    item_type = GAP_ITEM_TYPES.get(gap_type, "artifact_refresh_action_required")
    source_refs = _strings(gap.get("source_artifact_references"))
    forbidden = _claims_for_gap(gap, matrix)
    return {
        "item_id": _stable_id("readiness-action-item", [gap.get("gap_id"), gap_type, source_refs]),
        "gap_id": str(gap.get("gap_id") or ""),
        "item_type": item_type,
        "severity": str(gap.get("severity") or "warning"),
        "status": "open",
        "owner_role": str(gap.get("owner_role") or "project_owner"),
        "affected_scope": gap.get("affected_scope") if isinstance(gap.get("affected_scope"), dict) else {"scope_type": "limited"},
        "related_readiness_dimension": _dimension_for_gap(gap_type),
        "source_artifact_references": source_refs,
        "blocking_delivery": bool(gap.get("blocks_delivery")),
        "blocking_apply": bool(gap.get("blocks_apply")),
        "blocking_production_ready_claim": bool(gap.get("blocks_production_ready_claim")),
        "forbidden_claims_affected": forbidden,
        "recommended_action": str(gap.get("recommended_action") or ""),
        "available_action_types": AVAILABLE_ACTIONS.get(item_type, ["request_follow_up"]),
        "action_endpoint_hint": "POST /api/workbench-readiness-action",
        "human_confirmation_required": item_type not in {"artifact_refresh_action_required"},
        "stale_evidence_involved": gap_type == "artifact_refresh_required" or any("stale" in str(ref).lower() for ref in source_refs),
        "limitations": ["queue item is a projection over readiness artifacts and is not resolved by UI state"],
    }


def _append_authorization_items(items: list[dict[str, Any]], matrix: dict[str, Any]) -> None:
    for requirement in matrix.get("authorization_requirements", []):
        if not isinstance(requirement, dict):
            continue
        auth = str(requirement.get("authorization") or "")
        item_type = "apply_authorization_action_required" if auth == "apply" else "delivery_authorization_action_required" if auth == "delivery" else "claim_acceptance_action_required"
        items.append(
            {
                "item_id": _stable_id("readiness-action-item", ["authorization", auth, requirement.get("reason")]),
                "gap_id": "",
                "item_type": item_type,
                "severity": "blocking" if auth in {"apply", "claim_acceptance"} else "warning",
                "status": "open",
                "owner_role": "project_owner",
                "affected_scope": matrix.get("effective_scope", {"scope_type": "limited"}),
                "related_readiness_dimension": auth,
                "source_artifact_references": _strings(requirement.get("required_artifact")),
                "blocking_delivery": auth in {"delivery", "claim_acceptance"},
                "blocking_apply": auth in {"apply", "claim_acceptance"},
                "blocking_production_ready_claim": True,
                "forbidden_claims_affected": _strings(matrix.get("forbidden_claims")),
                "recommended_action": str(requirement.get("reason") or "Record required authorization."),
                "available_action_types": AVAILABLE_ACTIONS.get(item_type, ["request_follow_up"]),
                "action_endpoint_hint": "POST /api/workbench-readiness-action",
                "human_confirmation_required": True,
                "stale_evidence_involved": False,
                "limitations": ["authorization item must be closed by signoff or claim acceptance artifacts"],
            }
        )


def _delegate_action(state_dir: Path, action_type: str, payload: dict[str, Any], run_id: str | None) -> tuple[dict[str, Any], list[str], str]:
    try:
        if action_type == "record_human_review":
            evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else payload
            result = record_human_review_evidence(state_dir, evidence, run_id=run_id)
            return {"status": "accepted", "result": result}, ["human-review-evidence.jsonl"], "accepted"
        if action_type in {"accept_claim", "reject_claim"}:
            claims = _claims_from_payload(payload)
            result = build_claim_acceptance_decision(
                state_dir,
                requested_claims=claims,
                rejected_claims=claims if action_type == "reject_claim" else None,
                accepted_risk=payload.get("accepted_risk") if isinstance(payload.get("accepted_risk"), dict) else {},
                run_id=run_id,
            )
            outcome = "blocked" if result.get("status") == "blocked" else "rejected" if action_type == "reject_claim" else "accepted"
            return {"status": result.get("status"), "result": result}, ["claim-acceptance-decision.json"], outcome
        if action_type in {"create_signoff", "reject_signoff"}:
            signoff = payload.get("signoff") if isinstance(payload.get("signoff"), dict) else payload
            if action_type == "reject_signoff":
                signoff = {**signoff, "status": "rejected", "rejected": True}
            result = create_signoff_record(state_dir, signoff, run_id=run_id)
            outcome = "requires_follow_up" if result.get("status") == "requires_follow_up" else "rejected" if result.get("status") == "rejected" else "accepted"
            return {"status": result.get("status"), "result": result}, ["signoff-record.json"], outcome
        if action_type == "record_document_decision":
            decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else payload
            result = record_document_decision(state_dir, decision, run_id=run_id)
            return {"status": "accepted", "result": result}, ["document-decision-log.jsonl", "document-claim-resolution.json", "document-signoff-summary.json"], "accepted"
        if action_type == "record_leadership_review":
            evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else payload
            result = record_leadership_review_evidence(state_dir, evidence, run_id=run_id)
            return {"status": "accepted", "result": result}, ["leadership-review-evidence.jsonl", "document-claim-resolution.json", "document-signoff-summary.json"], "accepted"
        if action_type == "record_knowledge_audit_resolution":
            decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else payload
            result = record_knowledge_audit_resolution(state_dir, decision, run_id=run_id)
            return {"status": "accepted", "result": result}, ["knowledge-audit-resolution-log.jsonl", "knowledge-conflict-resolution.json", "knowledge-assurance-summary.json"], "accepted"
        if action_type == "record_knowledge_constraint_review":
            evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else payload
            result = record_knowledge_constraint_review_evidence(state_dir, evidence, run_id=run_id)
            return {"status": "accepted", "result": result}, ["knowledge-constraint-review-evidence.jsonl", "knowledge-assurance-summary.json"], "accepted"
        if action_type == "record_knowledge_repair_result":
            result = record_knowledge_repair_result(state_dir, payload.get("result") if isinstance(payload.get("result"), dict) else payload, run_id=run_id)
            return {"status": result.get("status"), "result": result}, ["knowledge-repair-result-intake.jsonl", "knowledge-repair-qa-report.json", "knowledge-repair-reconciliation.json"], _result_status_from_record(result)
        if action_type == "request_recompute":
            plan = build_knowledge_recompute_plan(state_dir)
            recompute = build_knowledge_recompute_result(state_dir)
            closure = build_knowledge_repair_closure_decision(state_dir)
            impact = build_knowledge_readiness_impact_report(state_dir)
            return {"status": recompute.get("status"), "plan": plan, "result": recompute, "closure": closure, "impact": impact}, ["knowledge-recompute-plan.json", "knowledge-recompute-result.json", "knowledge-repair-closure-decision.json", "knowledge-readiness-impact-report.json"], "accepted" if recompute.get("status") in {"completed", "partial"} else "requires_follow_up"
        if action_type in {"acknowledge_forbidden_claim", "acknowledge_limitation", "request_follow_up"}:
            return {"status": "requires_follow_up" if action_type == "request_follow_up" else "accepted", "message": f"{action_type} recorded in readiness action log only; forbidden claims and blockers remain artifact-backed"}, [], "requires_follow_up" if action_type == "request_follow_up" else "accepted_with_limitations"
    except ValueError as exc:
        return {"status": "blocked", "message": str(exc)}, [], "blocked"
    return {"status": "blocked", "message": f"Unsupported readiness action type: {action_type}"}, [], "blocked"


def _refresh_readiness_artifacts(state_dir: Path, run_id: str | None, *, tolerate_errors: bool = False) -> list[str]:
    from .artifact_state import build_artifact_state

    refreshed: list[str] = []
    for artifact, refresh in (
        ("artifact-state.json", lambda: build_artifact_state(state_dir)),
        (READINESS_AUTHORIZATION_MATRIX_JSON, lambda: build_readiness_reports(state_dir, run_id=run_id)["readiness_authorization_matrix"]),
        (MANUAL_FOLLOWUP_GAP_REPORT_JSON, lambda: read_json(state_dir / MANUAL_FOLLOWUP_GAP_REPORT_JSON)),
        (APPLY_READINESS_REPORT_JSON, lambda: read_json(state_dir / APPLY_READINESS_REPORT_JSON)),
        (DELIVERY_READINESS_REPORT_JSON, lambda: read_json(state_dir / DELIVERY_READINESS_REPORT_JSON)),
    ):
        try:
            refresh()
            refreshed.append(artifact)
        except (OSError, ValueError, json.JSONDecodeError):
            if not tolerate_errors:
                raise
    return refreshed


def _readiness_snapshot(state_dir: Path) -> dict[str, Any]:
    matrix = _optional_json(state_dir / READINESS_AUTHORIZATION_MATRIX_JSON)
    gaps = _optional_json(state_dir / MANUAL_FOLLOWUP_GAP_REPORT_JSON)
    return {
        "matrix": matrix,
        "gap_report": gaps,
        "status": {
            "delivery": matrix.get("delivery_readiness_status", "missing"),
            "apply": matrix.get("apply_readiness_status", "missing"),
            "review": matrix.get("review_readiness_status", "missing"),
            "production": matrix.get("production_readiness_status", "missing"),
            "manual_followup": gaps.get("status", "missing"),
        },
    }


def _required_action_type(action: dict[str, Any]) -> str:
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


def _result_status(outcome: str, runtime_result: dict[str, Any]) -> str:
    raw = str(runtime_result.get("status") or outcome)
    if outcome in {"accepted", "accepted_with_limitations", "rejected", "blocked", "requires_follow_up", "stale", "not_applicable"}:
        return outcome
    if raw in {"accepted", "accepted_with_limitations", "rejected", "blocked", "requires_follow_up", "stale", "not_applicable"}:
        return raw
    return "accepted"


def _result_status_from_record(record: dict[str, Any]) -> str:
    status = str(record.get("status") or "")
    if status in {"accepted_for_qa", "received"}:
        return "requires_follow_up"
    if status.startswith("rejected"):
        return "blocked"
    if status == "requires_follow_up":
        return "requires_follow_up"
    return "accepted"


def _writer_for_action(action_type: str) -> str:
    return {
        "record_human_review": "record_human_review_evidence",
        "accept_claim": "build_claim_acceptance_decision",
        "reject_claim": "build_claim_acceptance_decision",
        "create_signoff": "create_signoff_record",
        "reject_signoff": "create_signoff_record",
        "record_document_decision": "record_document_decision",
        "record_leadership_review": "record_leadership_review_evidence",
        "record_knowledge_audit_resolution": "record_knowledge_audit_resolution",
        "record_knowledge_constraint_review": "record_knowledge_constraint_review_evidence",
        "record_knowledge_repair_result": "record_knowledge_repair_result",
        "request_recompute": "knowledge_repair_closure_deterministic_recompute",
        "acknowledge_forbidden_claim": "workbench_readiness_action_log",
        "acknowledge_limitation": "workbench_readiness_action_log",
        "request_follow_up": "workbench_readiness_action_log",
    }.get(action_type, "unsupported")


def _source_refs_for_action(action_type: str, payload: dict[str, Any], item_id: str, gap_id: str) -> list[str]:
    refs = _strings(payload.get("source_artifact_references"))
    if not refs:
        refs = [WORKBENCH_READINESS_ACTION_QUEUE_JSON, MANUAL_FOLLOWUP_GAP_REPORT_JSON, READINESS_AUTHORIZATION_MATRIX_JSON]
    if item_id:
        refs.append(f"queue_item:{item_id}")
    if gap_id:
        refs.append(f"gap:{gap_id}")
    if action_type == "record_knowledge_repair_result":
        refs.append("knowledge-repair-result-intake.jsonl")
    return list(dict.fromkeys(refs))


def _result_limitations(action_type: str, status: str, forbidden: list[str]) -> list[str]:
    limitations = ["readiness action result does not imply readiness unless refreshed readiness artifacts support it"]
    if action_type in {"acknowledge_forbidden_claim", "acknowledge_limitation"}:
        limitations.append("acknowledgement does not remove forbidden claims")
    if forbidden:
        limitations.append("forbidden claims remain visible: " + ", ".join(sorted(set(forbidden))[:12]))
    if status in {"blocked", "requires_follow_up"}:
        limitations.append("underlying artifact-backed evidence still requires follow-up")
    return limitations


def _next_action(status: str, queue: dict[str, Any], snapshot: dict[str, Any]) -> str:
    if status in {"blocked", "requires_follow_up"}:
        return "Resolve the remaining readiness action queue items with artifact-backed decisions."
    if queue.get("summary", {}).get("item_count", 0):
        return "Refresh or resolve remaining queue items; do not claim readiness until matrix and reports support it."
    after = snapshot.get("status", {})
    if after.get("apply") == "ready":
        return "Apply may proceed only through the apply gate with current authorization evidence."
    if after.get("delivery") in {"ready", "ready_with_warnings"}:
        return "Delivery may proceed within the matrix scope and limitations."
    return "Refresh readiness reports and review remaining blockers."


def _payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in ("claim", "claims", "gap_id", "queue_item_id", "target_queue_item_id"):
        if key in payload:
            summary[key] = payload[key]
    for container in ("evidence", "decision", "signoff", "result"):
        if isinstance(payload.get(container), dict):
            summary[container] = {key: payload[container].get(key) for key in sorted(payload[container])[:8]}
    return summary


def _claims_for_gap(gap: dict[str, Any], matrix: dict[str, Any]) -> list[str]:
    text = " ".join([str(gap.get("gap_type") or ""), str(gap.get("recommended_action") or "")])
    claims = [claim for claim in _strings(matrix.get("forbidden_claims")) if claim in text]
    if claims:
        return claims
    if gap.get("blocks_apply"):
        return [claim for claim in _strings(matrix.get("forbidden_claims")) if claim in {"apply_ready", "production_ready"}]
    if gap.get("blocks_delivery"):
        return [claim for claim in _strings(matrix.get("forbidden_claims")) if claim in {"delivery_ready", "production_ready"}]
    return _strings(matrix.get("forbidden_claims"))[:8]


def _dimension_for_gap(gap_type: str) -> str:
    if "apply" in gap_type:
        return "apply"
    if "delivery" in gap_type:
        return "delivery"
    if "signoff" in gap_type:
        return "signoff"
    if "claim" in gap_type or "forbidden" in gap_type:
        return "claim_acceptance"
    if "document" in gap_type or "leadership" in gap_type:
        return "document_evidence"
    if "knowledge" in gap_type:
        return "knowledge_evidence"
    if "repair" in gap_type:
        return "repair_closure"
    if "coverage" in gap_type:
        return "coverage"
    if "provider" in gap_type:
        return "provider_policy"
    return "readiness"


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _source_artifacts(state_dir: Path, names: list[str]) -> dict[str, str]:
    return {Path(name).stem.replace("-", "_"): name for name in names if (state_dir / name).is_file()}


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)] if str(value) else []


def _stable_id(prefix: str, value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
