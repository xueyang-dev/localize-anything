from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json, write_jsonl
from .knowledge_audit_enforcement import (
    KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON,
    WORKBENCH_KNOWLEDGE_REVIEW_QUEUE_JSON,
    read_knowledge_audit_enforcement_decision,
)
from .knowledge_consumption import KNOWLEDGE_PACK_SELECTION_JSON, WORKING_CONTEXT_PACKET_JSON
from .knowledge_usage import (
    CONSTRAINT_APPLICATION_AUDIT_JSON,
    KNOWLEDGE_CONFLICT_REPORT_JSON,
    KNOWLEDGE_USAGE_REPORT_JSON,
)


KNOWLEDGE_AUDIT_RESOLUTION_LOG_JSONL = "knowledge-audit-resolution-log.jsonl"
KNOWLEDGE_CONSTRAINT_REVIEW_EVIDENCE_JSONL = "knowledge-constraint-review-evidence.jsonl"
KNOWLEDGE_CONFLICT_RESOLUTION_JSON = "knowledge-conflict-resolution.json"
KNOWLEDGE_ASSURANCE_SUMMARY_JSON = "knowledge-assurance-summary.json"

RESOLUTION_DECISION_TYPES = {
    "accept_constraint_application",
    "reject_constraint_application",
    "accept_negative_constraint_check",
    "reject_negative_constraint_check",
    "resolve_knowledge_conflict",
    "reject_pack_knowledge",
    "prefer_project_term",
    "prefer_pack_term",
    "scope_limit_knowledge",
    "accept_reference_only_use",
    "reject_reference_only_use",
    "confirm_blind_benchmark_firewall",
    "reject_blind_benchmark_firewall",
    "request_knowledge_repair",
    "request_generation_repair",
    "accept_limited_knowledge_risk",
    "keep_blocked",
    "request_follow_up",
}

DECISION_STATUSES = {"accepted", "accepted_with_limitations", "rejected", "blocked", "requires_follow_up", "superseded", "stale"}
SUPPORTED_KNOWLEDGE_CLAIMS = {"knowledge_constraints_applied", "knowledge_review_complete", "knowledge_backed_quality"}


def record_knowledge_audit_resolution(state_dir: Path, decision: dict[str, Any], *, run_id: str | None = None) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    record = _normalize_resolution(decision, run_id=run_id)
    records = read_knowledge_audit_resolution_log(state_dir)
    records.append(record)
    write_jsonl(state_dir / KNOWLEDGE_AUDIT_RESOLUTION_LOG_JSONL, records)
    build_knowledge_conflict_resolution(state_dir)
    build_knowledge_assurance_summary(state_dir)
    return record


def read_knowledge_audit_resolution_log(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / KNOWLEDGE_AUDIT_RESOLUTION_LOG_JSONL
    return read_jsonl(path) if path.is_file() else []


def record_knowledge_constraint_review_evidence(state_dir: Path, evidence: dict[str, Any], *, run_id: str | None = None) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    record = _normalize_constraint_review(evidence, run_id=run_id)
    records = read_knowledge_constraint_review_evidence(state_dir)
    records.append(record)
    write_jsonl(state_dir / KNOWLEDGE_CONSTRAINT_REVIEW_EVIDENCE_JSONL, records)
    build_knowledge_assurance_summary(state_dir)
    return record


def read_knowledge_constraint_review_evidence(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / KNOWLEDGE_CONSTRAINT_REVIEW_EVIDENCE_JSONL
    return read_jsonl(path) if path.is_file() else []


def build_knowledge_conflict_resolution(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    conflict_report = _read_optional_json(state_dir / KNOWLEDGE_CONFLICT_REPORT_JSON)
    decisions = read_knowledge_audit_resolution_log(state_dir)
    conflicts = [item for item in conflict_report.get("conflicts", []) if isinstance(item, dict)]
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    accepted_priority_decisions: list[dict[str, Any]] = []
    rejected_knowledge_items: list[str] = []
    scoped_limitations: list[dict[str, Any]] = []
    for conflict in conflicts:
        matching = _matching_resolution(conflict, decisions)
        if matching:
            resolved_item = {
                "conflict_id": str(conflict.get("conflict_id") or ""),
                "resolution_id": matching["resolution_id"],
                "decision_type": matching["decision_type"],
                "decision_status": matching["decision_status"],
                "effective_scope": matching.get("effective_scope", {}),
                "limitations": _list(matching.get("accepted_limitation")),
                "source_artifact_references": [KNOWLEDGE_AUDIT_RESOLUTION_LOG_JSONL, KNOWLEDGE_CONFLICT_REPORT_JSON],
            }
            resolved.append(resolved_item)
            accepted_priority_decisions.append(resolved_item)
            rejected_knowledge_items.extend(str(item) for item in matching.get("rejected_knowledge_items", []) if item)
            if matching.get("accepted_limitation") or matching.get("effective_scope"):
                scoped_limitations.append(resolved_item)
        else:
            unresolved.append(conflict)
    resolution = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-conflict-resolution-v1",
        "artifact": KNOWLEDGE_CONFLICT_RESOLUTION_JSON,
        "status": "blocked" if _blocking_conflicts(unresolved) else "review_required" if unresolved else "resolved",
        "resolved_conflicts": resolved,
        "unresolved_conflicts": unresolved,
        "accepted_priority_decisions": accepted_priority_decisions,
        "rejected_knowledge_items": sorted(set(rejected_knowledge_items)),
        "scoped_limitations": scoped_limitations,
        "project_local_overrides": [item for item in resolved if item["decision_type"] == "prefer_project_term"],
        "pack_overrides": [item for item in resolved if item["decision_type"] == "prefer_pack_term"],
        "blocking_conflicts_remaining": _blocking_conflicts(unresolved),
        "readiness_impact": "blocked" if _blocking_conflicts(unresolved) else "limited" if scoped_limitations else "clear",
        "required_next_actions": _conflict_next_actions(unresolved),
        "source_artifacts": _source_artifacts(
            state_dir,
            [KNOWLEDGE_CONFLICT_REPORT_JSON, KNOWLEDGE_AUDIT_RESOLUTION_LOG_JSONL, WORKBENCH_KNOWLEDGE_REVIEW_QUEUE_JSON],
        ),
    }
    if write:
        write_json(state_dir / KNOWLEDGE_CONFLICT_RESOLUTION_JSON, resolution)
    return resolution


def read_knowledge_conflict_resolution(state_dir: Path) -> dict[str, Any]:
    path = state_dir / KNOWLEDGE_CONFLICT_RESOLUTION_JSON
    if path.is_file():
        value = read_json(path)
        return value if isinstance(value, dict) else {}
    return build_knowledge_conflict_resolution(state_dir)


def build_knowledge_assurance_summary(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    enforcement = read_knowledge_audit_enforcement_decision(state_dir)
    conflict_resolution = build_knowledge_conflict_resolution(state_dir, write=write)
    review_evidence = read_knowledge_constraint_review_evidence(state_dir)
    resolution_log = read_knowledge_audit_resolution_log(state_dir)
    valid_review = _valid_constraint_review(review_evidence)
    deterministic_constraints = str(enforcement.get("status") or "") == "clear" and "knowledge_constraints_applied" not in set(enforcement.get("forbidden_claims", []))
    unresolved = conflict_resolution.get("blocking_conflicts_remaining", [])
    stale = _stale_knowledge_review_evidence(state_dir)
    # Human review can confirm deterministic audit evidence, but it must not
    # replace a clear enforcement decision or erase unresolved audit blockers.
    supports_constraints = deterministic_constraints and valid_review and not unresolved and not stale
    supports_review_complete = supports_constraints and _supports_review_complete(review_evidence)
    supported = []
    if supports_constraints:
        supported.append("knowledge_constraints_applied")
    if supports_review_complete:
        supported.append("knowledge_review_complete")
    forbidden = sorted(SUPPORTED_KNOWLEDGE_CLAIMS - set(supported))
    if unresolved or stale or (str(enforcement.get("status") or "") in {"blocked", "stale"} and not supports_constraints):
        forbidden.extend(claim for claim in ("delivery_ready", "apply_ready", "production_ready") if claim not in forbidden)
    summary = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-assurance-summary-v1",
        "artifact": KNOWLEDGE_ASSURANCE_SUMMARY_JSON,
        "status": "stale" if stale else "blocked" if unresolved or (str(enforcement.get("status") or "") == "blocked" and not supports_constraints) else "review_complete" if supports_review_complete else "constraints_applied" if supports_constraints else "review_required",
        "pack_selection_status": _artifact_status(state_dir / KNOWLEDGE_PACK_SELECTION_JSON, "not_selected"),
        "working_context_status": _artifact_status(state_dir / WORKING_CONTEXT_PACKET_JSON, "missing"),
        "usage_report_status": _artifact_status(state_dir / KNOWLEDGE_USAGE_REPORT_JSON, "missing"),
        "constraint_audit_status": _artifact_status(state_dir / CONSTRAINT_APPLICATION_AUDIT_JSON, "missing"),
        "enforcement_decision_status": str(enforcement.get("status") or "missing"),
        "human_knowledge_review_status": "provided" if review_evidence else "not_provided",
        "conflict_resolution_status": str(conflict_resolution.get("status") or "missing"),
        "constraints_accepted": _constraints_by_decision(resolution_log, {"accept_constraint_application", "accept_negative_constraint_check"}),
        "constraints_rejected": _constraints_by_decision(resolution_log, {"reject_constraint_application", "reject_negative_constraint_check"}),
        "conflicts_resolved": conflict_resolution.get("resolved_conflicts", []),
        "conflicts_remaining": conflict_resolution.get("unresolved_conflicts", []),
        "limitations": _limitations(resolution_log, review_evidence, conflict_resolution),
        "forbidden_claims_remaining": forbidden,
        "supported_claims": supported,
        "unsupported_claims": sorted(SUPPORTED_KNOWLEDGE_CLAIMS - set(supported)),
        "readiness_impact": _assurance_readiness(supports_constraints, supports_review_complete, bool(unresolved), stale),
        "source_artifacts": _source_artifacts(
            state_dir,
            [
                KNOWLEDGE_AUDIT_RESOLUTION_LOG_JSONL,
                KNOWLEDGE_CONSTRAINT_REVIEW_EVIDENCE_JSONL,
                KNOWLEDGE_CONFLICT_RESOLUTION_JSON,
                KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON,
                KNOWLEDGE_USAGE_REPORT_JSON,
                CONSTRAINT_APPLICATION_AUDIT_JSON,
                KNOWLEDGE_CONFLICT_REPORT_JSON,
            ],
        ),
    }
    if write:
        write_json(state_dir / KNOWLEDGE_ASSURANCE_SUMMARY_JSON, summary)
    return summary


def read_knowledge_assurance_summary(state_dir: Path) -> dict[str, Any]:
    path = state_dir / KNOWLEDGE_ASSURANCE_SUMMARY_JSON
    if path.is_file():
        value = read_json(path)
        return value if isinstance(value, dict) else {}
    return build_knowledge_assurance_summary(state_dir)


def knowledge_review_confirmation_asset_paths(state_dir: Path) -> dict[str, str]:
    return {
        key: name
        for key, name in (
            ("knowledge_audit_resolution_log", KNOWLEDGE_AUDIT_RESOLUTION_LOG_JSONL),
            ("knowledge_constraint_review_evidence", KNOWLEDGE_CONSTRAINT_REVIEW_EVIDENCE_JSONL),
            ("knowledge_conflict_resolution", KNOWLEDGE_CONFLICT_RESOLUTION_JSON),
            ("knowledge_assurance_summary", KNOWLEDGE_ASSURANCE_SUMMARY_JSON),
        )
        if (state_dir / name).is_file()
    }


def _normalize_resolution(decision: dict[str, Any], *, run_id: str | None) -> dict[str, Any]:
    if not isinstance(decision, dict):
        raise ValueError("knowledge audit resolution decision must be a JSON object")
    decision_type = _required_enum(decision, "decision_type", RESOLUTION_DECISION_TYPES)
    status = _required_enum(decision, "decision_status", DECISION_STATUSES)
    source_artifact_references = _list(decision.get("source_artifact_references")) or [WORKBENCH_KNOWLEDGE_REVIEW_QUEUE_JSON]
    if decision.get("related_conflict_id") and KNOWLEDGE_CONFLICT_REPORT_JSON not in source_artifact_references:
        source_artifact_references.append(KNOWLEDGE_CONFLICT_REPORT_JSON)
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-audit-resolution-log-v1",
        "resolution_id": str(decision.get("resolution_id") or _stable_id("knowledge-resolution", decision)),
        "decision_type": decision_type,
        "reviewer_role": str(decision.get("reviewer_role") or "knowledge_reviewer"),
        "reviewer_reference": str(decision.get("reviewer_reference") or "unspecified"),
        "source_artifact_references": source_artifact_references,
        "related_queue_item_id": str(decision.get("related_queue_item_id") or ""),
        "related_enforcement_decision_id": str(decision.get("related_enforcement_decision_id") or ""),
        "related_knowledge_usage_item_id": str(decision.get("related_knowledge_usage_item_id") or ""),
        "related_constraint_audit_id": str(decision.get("related_constraint_audit_id") or decision.get("related_constraint_id") or ""),
        "related_conflict_id": str(decision.get("related_conflict_id") or ""),
        "affected_knowledge_item_ids": _list(decision.get("affected_knowledge_item_ids")),
        "affected_segment_ids": _list(decision.get("affected_segment_ids")),
        "decision_status": status,
        "rationale": str(decision.get("rationale") or ""),
        "accepted_limitation": str(decision.get("accepted_limitation") or ""),
        "required_follow_up": str(decision.get("required_follow_up") or ""),
        "effective_scope": decision.get("effective_scope") if isinstance(decision.get("effective_scope"), dict) else {},
        "rejected_knowledge_items": _list(decision.get("rejected_knowledge_items")),
        "supersedes": str(decision.get("supersedes") or ""),
        "superseded_by": str(decision.get("superseded_by") or ""),
    }
    if run_id:
        record["run_id"] = run_id
    record["created_at"] = str(decision.get("created_at") or _now())
    return record


def _normalize_constraint_review(evidence: dict[str, Any], *, run_id: str | None) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise ValueError("knowledge constraint review evidence must be a JSON object")
    decision = _required_enum(evidence, "decision", DECISION_STATUSES)
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-constraint-review-evidence-v1",
        "evidence_id": str(evidence.get("evidence_id") or _stable_id("knowledge-review-evidence", evidence)),
        "reviewer_role": str(evidence.get("reviewer_role") or "knowledge_reviewer"),
        "reviewer_reference": str(evidence.get("reviewer_reference") or "unspecified"),
        "review_scope": evidence.get("review_scope") if isinstance(evidence.get("review_scope"), dict) else {},
        "reviewed_constraints": _list(evidence.get("reviewed_constraints")),
        "reviewed_negative_constraints": _list(evidence.get("reviewed_negative_constraints")),
        "reviewed_knowledge_usage_entries": _list(evidence.get("reviewed_knowledge_usage_entries")),
        "reviewed_conflicts": _list(evidence.get("reviewed_conflicts")),
        "reviewed_generated_or_staged_segments": _list(evidence.get("reviewed_generated_or_staged_segments")),
        "decision": decision,
        "limitations": _list(evidence.get("limitations")),
        "accepted_risks": _list(evidence.get("accepted_risks")),
        "rejected_knowledge_items": _list(evidence.get("rejected_knowledge_items")),
        "required_follow_up": _list(evidence.get("required_follow_up")),
        "supports_knowledge_constraints_applied": bool(evidence.get("supports_knowledge_constraints_applied")),
        "supports_knowledge_review_complete": bool(evidence.get("supports_knowledge_review_complete")),
        "supports_delivery_readiness": bool(evidence.get("supports_delivery_readiness")),
    }
    if run_id:
        record["run_id"] = run_id
    record["created_at"] = str(evidence.get("created_at") or _now())
    return record


def _required_enum(value: dict[str, Any], key: str, allowed: set[str]) -> str:
    item = str(value.get(key) or "")
    if item not in allowed:
        raise ValueError(f"{key} must be one of: {', '.join(sorted(allowed))}")
    return item


def _matching_resolution(conflict: dict[str, Any], decisions: list[dict[str, Any]]) -> dict[str, Any] | None:
    conflict_id = str(conflict.get("conflict_id") or "")
    for decision in reversed(decisions):
        if decision.get("decision_status") not in {"accepted", "accepted_with_limitations"}:
            continue
        if decision.get("decision_type") not in {"resolve_knowledge_conflict", "prefer_project_term", "prefer_pack_term", "scope_limit_knowledge", "accept_limited_knowledge_risk"}:
            continue
        if not decision.get("effective_scope"):
            continue
        if KNOWLEDGE_CONFLICT_REPORT_JSON not in decision.get("source_artifact_references", []):
            continue
        if conflict_id and decision.get("related_conflict_id") == conflict_id:
            return decision
    return None


def _valid_constraint_review(records: list[dict[str, Any]]) -> bool:
    return any(
        record.get("decision") in {"accepted", "accepted_with_limitations"}
        and bool(record.get("supports_knowledge_constraints_applied"))
        and not record.get("required_follow_up")
        for record in records
    )


def _supports_review_complete(records: list[dict[str, Any]]) -> bool:
    return any(
        record.get("decision") == "accepted"
        and bool(record.get("supports_knowledge_review_complete"))
        and not record.get("required_follow_up")
        for record in records
    )


def _stale_knowledge_review_evidence(state_dir: Path) -> bool:
    artifact_state = _read_optional_json(state_dir / "artifact-state.json")
    stale_ids = {str(item.get("artifact_id") or "") for item in artifact_state.get("stale_artifacts", []) if isinstance(item, dict)}
    return bool(stale_ids.intersection({"knowledge_audit_resolution_log", "knowledge_constraint_review_evidence", "knowledge_conflict_resolution", "knowledge_assurance_summary"}))


def _blocking_conflicts(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in conflicts if item.get("blocking") or str(item.get("severity") or "") in {"P1", "P2"}]


def _conflict_next_actions(unresolved: list[dict[str, Any]]) -> list[str]:
    if not unresolved:
        return ["Continue deterministic audit and scoped human review before stronger knowledge-backed claims."]
    return ["Record explicit scoped knowledge conflict resolution decisions for unresolved P1/P2 conflicts."]


def _constraints_by_decision(records: list[dict[str, Any]], types: set[str]) -> list[str]:
    return sorted({str(record.get("related_constraint_audit_id") or "") for record in records if record.get("decision_type") in types and record.get("decision_status") in {"accepted", "accepted_with_limitations"} and record.get("related_constraint_audit_id")})


def _limitations(resolution_log: list[dict[str, Any]], review_evidence: list[dict[str, Any]], conflict_resolution: dict[str, Any]) -> list[str]:
    limitations = []
    limitations.extend(str(record.get("accepted_limitation") or "") for record in resolution_log if record.get("accepted_limitation"))
    for record in review_evidence:
        limitations.extend(str(item) for item in record.get("limitations", []) if item)
    for item in conflict_resolution.get("scoped_limitations", []):
        limitations.extend(str(limit) for limit in item.get("limitations", []) if limit)
    return sorted(set(limitations))


def _assurance_readiness(supports_constraints: bool, supports_review_complete: bool, blocked: bool, stale: bool) -> dict[str, str]:
    if stale or blocked:
        return {"scorecard": "knowledge_claims_forbidden", "generation_handoff": "blocked", "delivery": "blocked", "apply": "blocked"}
    if supports_review_complete:
        return {"scorecard": "knowledge_review_complete_supported", "generation_handoff": "allowed_with_warnings", "delivery": "review_ready", "apply": "requires_signoff"}
    if supports_constraints:
        return {"scorecard": "knowledge_constraints_applied_supported", "generation_handoff": "allowed_with_warnings", "delivery": "review_required", "apply": "blocked"}
    return {"scorecard": "knowledge_review_required", "generation_handoff": "review_required", "delivery": "downgraded", "apply": "blocked"}


def _artifact_status(path: Path, missing: str) -> str:
    if not path.is_file():
        return missing
    try:
        value = read_json(path)
    except ValueError:
        return "present"
    if isinstance(value, dict):
        return str(value.get("status") or "present")
    return "present"


def _source_artifacts(state_dir: Path, names: list[str]) -> dict[str, str]:
    return {Path(name).stem.replace("-", "_"): name for name in names if (state_dir / name).is_file()}


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []


def _stable_id(prefix: str, value: dict[str, Any]) -> str:
    payload = {key: item for key, item in value.items() if key not in {"created_at", "resolution_id", "evidence_id"}}
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(encoded).hexdigest()[:12]}"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
