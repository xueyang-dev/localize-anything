from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .document_evidence import (
    CLAIM_METRIC_REPORT_JSON,
    DOCUMENT_EVIDENCE_MANIFEST_JSON,
    LEADERSHIP_REVIEW_BRIEF_MD,
    PUBLICITY_RISK_REPORT_JSON,
    SEMANTIC_ALIGNMENT_JSONL,
)
from .io_utils import read_json, read_jsonl, write_json, write_jsonl


DOCUMENT_DECISION_LOG_JSONL = "document-decision-log.jsonl"
LEADERSHIP_REVIEW_EVIDENCE_JSONL = "leadership-review-evidence.jsonl"
DOCUMENT_CLAIM_RESOLUTION_JSON = "document-claim-resolution.json"
DOCUMENT_SIGNOFF_SUMMARY_JSON = "document-signoff-summary.json"

DOCUMENT_DECISION_ASSETS = {
    "document_decision_log": DOCUMENT_DECISION_LOG_JSONL,
    "leadership_review_evidence": LEADERSHIP_REVIEW_EVIDENCE_JSONL,
    "document_claim_resolution": DOCUMENT_CLAIM_RESOLUTION_JSON,
    "document_signoff_summary": DOCUMENT_SIGNOFF_SUMMARY_JSON,
}

DECISION_TYPES = {
    "confirm_term",
    "confirm_institution_name",
    "confirm_partner_name",
    "confirm_project_name",
    "confirm_metric_boundary",
    "accept_claim_wording",
    "reject_claim_wording",
    "accept_publicity_risk",
    "reject_publicity_risk",
    "request_rewrite",
    "confirm_alignment_mode",
    "accept_explanatory_expansion",
    "reject_explanatory_expansion",
    "accept_source_omission",
    "reject_source_omission",
    "accept_limited_scope_delivery",
    "request_follow_up",
    "leadership_confirmation",
}

DECISION_STATUSES = {
    "accepted",
    "accepted_with_limitations",
    "rejected",
    "blocked",
    "requires_follow_up",
    "superseded",
    "stale",
}

RESOLVING_STATUSES = {"accepted", "accepted_with_limitations"}
UNRESOLVED_STATUSES = {"blocked", "requires_follow_up", "stale"}
DOCUMENT_FORBIDDEN_CLAIMS = {"review_complete", "delivery_ready", "apply_ready", "production_ready", "layout_verified"}


def read_document_decision_log(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / DOCUMENT_DECISION_LOG_JSONL
    return read_jsonl(path) if path.is_file() else []


def record_document_decision(
    state_dir: Path,
    decision: dict[str, Any],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    record = _normalize_document_decision(decision, run_id=run_id)
    records = read_document_decision_log(state_dir)
    records.append(record)
    write_jsonl(state_dir / DOCUMENT_DECISION_LOG_JSONL, records)
    resolution = build_document_claim_resolution(state_dir)
    signoff = build_document_signoff_summary(state_dir)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-document-decision-log-record-result-v1",
        "artifact": DOCUMENT_DECISION_LOG_JSONL,
        "record": record,
        "document_claim_resolution": resolution,
        "document_signoff_summary": signoff,
    }


def read_leadership_review_evidence(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / LEADERSHIP_REVIEW_EVIDENCE_JSONL
    return read_jsonl(path) if path.is_file() else []


def record_leadership_review_evidence(
    state_dir: Path,
    evidence: dict[str, Any],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    record = _normalize_leadership_review_evidence(evidence, run_id=run_id)
    records = read_leadership_review_evidence(state_dir)
    records.append(record)
    write_jsonl(state_dir / LEADERSHIP_REVIEW_EVIDENCE_JSONL, records)
    resolution = build_document_claim_resolution(state_dir)
    signoff = build_document_signoff_summary(state_dir)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-leadership-review-evidence-record-result-v1",
        "artifact": LEADERSHIP_REVIEW_EVIDENCE_JSONL,
        "record": record,
        "document_claim_resolution": resolution,
        "document_signoff_summary": signoff,
    }


def read_document_claim_resolution(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / DOCUMENT_CLAIM_RESOLUTION_JSON)


def build_document_claim_resolution(state_dir: Path, *, run_id: str | None = None, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    decisions = read_document_decision_log(state_dir)
    leadership = read_leadership_review_evidence(state_dir)
    claim_report = _read_optional_json(state_dir / CLAIM_METRIC_REPORT_JSON)
    publicity_report = _read_optional_json(state_dir / PUBLICITY_RISK_REPORT_JSON)
    alignment = _read_optional_jsonl(state_dir / SEMANTIC_ALIGNMENT_JSONL)
    manifest = _read_optional_json(state_dir / DOCUMENT_EVIDENCE_MANIFEST_JSON)
    artifact_state = _read_optional_json(state_dir / "artifact-state.json")

    claim_items = _claim_resolution_items(claim_report, decisions, leadership)
    publicity_items = _publicity_resolution_items(publicity_report, decisions, leadership)
    alignment_items = _alignment_resolution_items(alignment, decisions, leadership)
    unresolved_claims = [item for item in claim_items if item["resolution_status"] in UNRESOLVED_STATUSES]
    unresolved_publicity = [item for item in publicity_items if item["resolution_status"] in UNRESOLVED_STATUSES]
    unresolved_alignment = [item for item in alignment_items if item["resolution_status"] in UNRESOLVED_STATUSES]
    stale = _document_decision_stale(artifact_state)
    forbidden = set()
    if manifest:
        forbidden.add("layout_verified")
    if unresolved_claims or unresolved_publicity or unresolved_alignment or stale:
        forbidden.update(DOCUMENT_FORBIDDEN_CLAIMS)
    if manifest.get("status") == "unsupported":
        forbidden.update(DOCUMENT_FORBIDDEN_CLAIMS)
    limitations = sorted(
        {
            str(value)
            for record in [*decisions, *leadership]
            for value in _list_value(record.get("accepted_limitation") or record.get("limitations"))
            if str(value)
        }
    )
    effective_scope = _merged_scope([*decisions, *leadership])
    resolution = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-document-claim-resolution-v1",
        "artifact": DOCUMENT_CLAIM_RESOLUTION_JSON,
        "run_id": run_id or manifest.get("run_id"),
        "status": "stale"
        if stale
        else "blocked"
        if any(item.get("severity") == "blocking" for item in [*unresolved_claims, *unresolved_publicity])
        else "requires_follow_up"
        if unresolved_claims or unresolved_publicity or unresolved_alignment
        else "resolved",
        "resolved_claim_metric_risks": [item for item in claim_items if item["resolution_status"] in RESOLVING_STATUSES],
        "unresolved_claim_metric_risks": unresolved_claims,
        "accepted_publicity_risks": [item for item in publicity_items if item["resolution_status"] in RESOLVING_STATUSES],
        "unresolved_publicity_risks": unresolved_publicity,
        "resolved_semantic_alignment_risks": [item for item in alignment_items if item["resolution_status"] in RESOLVING_STATUSES],
        "unresolved_semantic_alignment_risks": unresolved_alignment,
        "rejected_or_blocked_claim_wording": _rejected_claim_wording(decisions),
        "accepted_limitations": limitations,
        "effective_scope": effective_scope,
        "forbidden_claims_remaining": sorted(forbidden),
        "delivery_readiness_impact": "blocked"
        if forbidden & {"delivery_ready", "production_ready"}
        else "allowed_with_document_limitations"
        if limitations
        else "allowed",
        "signoff_requirements": _signoff_requirements(unresolved_claims, unresolved_publicity, unresolved_alignment, limitations),
        "source_artifacts": _source_artifacts(state_dir),
        "summary": {
            "decision_count": len(decisions),
            "leadership_review_count": len(leadership),
            "resolved_claim_metric_count": len([item for item in claim_items if item["resolution_status"] in RESOLVING_STATUSES]),
            "unresolved_claim_metric_count": len(unresolved_claims),
            "accepted_publicity_risk_count": len([item for item in publicity_items if item["resolution_status"] in RESOLVING_STATUSES]),
            "unresolved_publicity_risk_count": len(unresolved_publicity),
            "unresolved_alignment_risk_count": len(unresolved_alignment),
            "accepted_limitation_count": len(limitations),
        },
    }
    if write:
        write_json(state_dir / DOCUMENT_CLAIM_RESOLUTION_JSON, resolution)
    return resolution


def read_document_signoff_summary(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / DOCUMENT_SIGNOFF_SUMMARY_JSON)


def build_document_signoff_summary(state_dir: Path, *, run_id: str | None = None, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    resolution = _read_optional_json(state_dir / DOCUMENT_CLAIM_RESOLUTION_JSON)
    if not resolution:
        resolution = build_document_claim_resolution(state_dir, run_id=run_id, write=write)
    leadership = read_leadership_review_evidence(state_dir)
    scorecard = _read_optional_json(state_dir / "evaluation-scorecard.json")
    signoff = _read_optional_json(state_dir / "signoff-record.json")
    artifact_state = _read_optional_json(state_dir / "artifact-state.json")
    stale = _document_decision_stale(artifact_state) or str(resolution.get("status") or "") == "stale"
    forbidden = set(scorecard.get("forbidden_claims", [])) | set(resolution.get("forbidden_claims_remaining", []))
    accepted_document_claims = _accepted_document_claims(resolution, leadership)
    unresolved_count = (
        len(resolution.get("unresolved_claim_metric_risks", []))
        + len(resolution.get("unresolved_publicity_risks", []))
        + len(resolution.get("unresolved_semantic_alignment_risks", []))
    )
    leadership_support = any(
        record.get("supports_delivery_readiness") is True and record.get("decision") in {"accepted", "accepted_with_limitations"}
        for record in leadership
    )
    delivery_authorized = (
        not stale
        and unresolved_count == 0
        and leadership_support
        and bool(signoff.get("delivery_authorized"))
        and "delivery_ready" not in forbidden
    )
    limited_delivery_authorized = (
        not stale
        and leadership_support
        and bool(signoff.get("delivery_authorized"))
        and bool(resolution.get("accepted_limitations"))
        and "production_ready" in forbidden
    )
    apply_authorized = delivery_authorized and bool(signoff.get("apply_authorized")) and "apply_ready" not in forbidden
    status = "stale" if stale else "blocked" if unresolved_count else "accepted_with_limitations" if limited_delivery_authorized else "accepted" if delivery_authorized else "requires_follow_up"
    summary = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-document-signoff-summary-v1",
        "artifact": DOCUMENT_SIGNOFF_SUMMARY_JSON,
        "run_id": run_id or resolution.get("run_id") or scorecard.get("run_id"),
        "status": status,
        "document_signoff_status": status,
        "leadership_review_status": "provided" if leadership else "not_provided",
        "accepted_document_claims": accepted_document_claims,
        "rejected_document_claims": resolution.get("rejected_or_blocked_claim_wording", []),
        "unresolved_document_risks": {
            "claim_metric": resolution.get("unresolved_claim_metric_risks", []),
            "publicity": resolution.get("unresolved_publicity_risks", []),
            "semantic_alignment": resolution.get("unresolved_semantic_alignment_risks", []),
        },
        "limitations": resolution.get("accepted_limitations", []),
        "effective_scope": resolution.get("effective_scope", {"scope_type": "limited"}),
        "delivery_authorized": delivery_authorized or limited_delivery_authorized,
        "apply_authorized": apply_authorized,
        "remaining_forbidden_claims": sorted(forbidden),
        "stale_or_superseded_warnings": ["document_decision_evidence_stale"] if stale else [],
        "next_required_action": _next_required_action(stale, unresolved_count, leadership_support, signoff),
        "source_artifacts": _source_artifacts(state_dir),
        "summary": {
            "leadership_review_count": len(leadership),
            "unresolved_document_risk_count": unresolved_count,
            "accepted_document_claim_count": len(accepted_document_claims),
            "remaining_forbidden_claim_count": len(forbidden),
        },
    }
    if write:
        write_json(state_dir / DOCUMENT_SIGNOFF_SUMMARY_JSON, summary)
    return summary


def document_decision_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: value for key, value in DOCUMENT_DECISION_ASSETS.items() if (state_dir / value).is_file()}


def _normalize_document_decision(decision: dict[str, Any], *, run_id: str | None) -> dict[str, Any]:
    decision_type = str(decision.get("decision_type") or "").strip()
    status = str(decision.get("decision_status") or decision.get("status") or "").strip()
    if decision_type not in DECISION_TYPES:
        raise ValueError(f"decision_type must be one of: {', '.join(sorted(DECISION_TYPES))}")
    if status not in DECISION_STATUSES:
        raise ValueError(f"decision_status must be one of: {', '.join(sorted(DECISION_STATUSES))}")
    reviewer_role = str(decision.get("reviewer_role") or "").strip()
    if not reviewer_role:
        raise ValueError("reviewer_role is required")
    reviewer_reference = str(decision.get("reviewer_reference") or "").strip()
    record = dict(decision)
    record.update(
        {
            "protocol_version": PROTOCOL_VERSION,
            "schema": "localize-anything-document-decision-log-record-v1",
            "run_id": run_id or decision.get("run_id"),
            "decision_id": str(decision.get("decision_id") or _stable_id("document-decision", decision)[:32]),
            "decision_type": decision_type,
            "reviewer_role": reviewer_role,
            "reviewer_reference": reviewer_reference,
            "source_artifact_references": _list_value(decision.get("source_artifact_references")),
            "affected_segment_ids": _list_value(decision.get("affected_segment_ids")),
            "affected_scope": decision.get("affected_scope") if isinstance(decision.get("affected_scope"), dict) else {"scope_type": "limited"},
            "related_open_decision_id": _optional_string(decision.get("related_open_decision_id")),
            "related_claim_metric_risk_id": _optional_string(decision.get("related_claim_metric_risk_id")),
            "related_publicity_risk_id": _optional_string(decision.get("related_publicity_risk_id")),
            "related_semantic_alignment_id": _optional_string(decision.get("related_semantic_alignment_id")),
            "decision_status": status,
            "decision_rationale": str(decision.get("decision_rationale") or ""),
            "accepted_limitation": decision.get("accepted_limitation"),
            "required_follow_up": decision.get("required_follow_up"),
            "effective_scope": decision.get("effective_scope") if isinstance(decision.get("effective_scope"), dict) else decision.get("affected_scope") if isinstance(decision.get("affected_scope"), dict) else {"scope_type": "limited"},
            "created_at": str(decision.get("created_at") or _now()),
            "supersedes": _list_value(decision.get("supersedes")),
            "superseded_by": _list_value(decision.get("superseded_by")),
        }
    )
    return record


def _normalize_leadership_review_evidence(evidence: dict[str, Any], *, run_id: str | None) -> dict[str, Any]:
    reviewer_role = str(evidence.get("reviewer_role") or "").strip()
    if not reviewer_role:
        raise ValueError("reviewer_role is required")
    decision = str(evidence.get("decision") or "").strip()
    if decision not in DECISION_STATUSES:
        raise ValueError(f"decision must be one of: {', '.join(sorted(DECISION_STATUSES))}")
    record = dict(evidence)
    record.update(
        {
            "protocol_version": PROTOCOL_VERSION,
            "schema": "localize-anything-leadership-review-evidence-record-v1",
            "run_id": run_id or evidence.get("run_id"),
            "leadership_review_evidence_id": str(evidence.get("leadership_review_evidence_id") or _stable_id("leadership-review", evidence)[:32]),
            "reviewer_role": reviewer_role,
            "reviewer_reference": str(evidence.get("reviewer_reference") or ""),
            "review_scope": evidence.get("review_scope") if isinstance(evidence.get("review_scope"), dict) else {"scope_type": "limited"},
            "reviewed_artifacts": _list_value(evidence.get("reviewed_artifacts")),
            "reviewed_risks": _list_value(evidence.get("reviewed_risks")),
            "reviewed_open_decisions": _list_value(evidence.get("reviewed_open_decisions")),
            "reviewed_claims": _list_value(evidence.get("reviewed_claims")),
            "decision": decision,
            "limitations": _list_value(evidence.get("limitations")),
            "accepted_risks": _list_value(evidence.get("accepted_risks")),
            "rejected_claims": _list_value(evidence.get("rejected_claims")),
            "required_follow_up": evidence.get("required_follow_up"),
            "supports_signoff": bool(evidence.get("supports_signoff")),
            "supports_delivery_readiness": bool(evidence.get("supports_delivery_readiness")),
            "supports_language_review_evidence_levels": [],
            "created_at": str(evidence.get("created_at") or _now()),
        }
    )
    return record


def _claim_resolution_items(report: dict[str, Any], decisions: list[dict[str, Any]], leadership: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for check in report.get("checks", []) if isinstance(report, dict) else []:
        if check.get("status") not in {"blocked", "warning", "pending"}:
            continue
        risk_id = str(check.get("check_id") or "")
        resolver = _find_decision(decisions, leadership, claim_id=risk_id)
        items.append(_resolution_item(risk_id, check, resolver))
    return items


def _publicity_resolution_items(report: dict[str, Any], decisions: list[dict[str, Any]], leadership: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for risk in report.get("risks", []) if isinstance(report, dict) else []:
        risk_id = str(risk.get("risk_id") or "")
        resolver = _find_decision(decisions, leadership, publicity_id=risk_id)
        items.append(_resolution_item(risk_id, risk, resolver))
    return items


def _alignment_resolution_items(records: list[dict[str, Any]], decisions: list[dict[str, Any]], leadership: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in records:
        if not record.get("human_confirmation_required") and not record.get("risk_flags"):
            continue
        alignment_id = str(record.get("alignment_id") or "")
        resolver = _find_decision(decisions, leadership, alignment_id=alignment_id)
        items.append(_resolution_item(alignment_id, record, resolver))
    return items


def _find_decision(
    decisions: list[dict[str, Any]],
    leadership: list[dict[str, Any]],
    *,
    claim_id: str | None = None,
    publicity_id: str | None = None,
    alignment_id: str | None = None,
) -> dict[str, Any] | None:
    for decision in reversed(decisions):
        if claim_id and decision.get("related_claim_metric_risk_id") == claim_id:
            return decision
        if publicity_id and decision.get("related_publicity_risk_id") == publicity_id:
            return decision
        if alignment_id and decision.get("related_semantic_alignment_id") == alignment_id:
            return decision
    ids = {value for value in (claim_id, publicity_id, alignment_id) if value}
    for evidence in reversed(leadership):
        reviewed = {str(value) for value in evidence.get("reviewed_risks", [])}
        if ids & reviewed:
            return evidence
    return None


def _resolution_item(item_id: str, source: dict[str, Any], resolver: dict[str, Any] | None) -> dict[str, Any]:
    if resolver:
        status = str(resolver.get("decision_status") or resolver.get("decision") or "")
        resolution_status = status if status in DECISION_STATUSES else "requires_follow_up"
        resolver_id = resolver.get("decision_id") or resolver.get("leadership_review_evidence_id")
    else:
        resolution_status = "blocked" if source.get("severity") == "blocking" or source.get("status") == "blocked" else "requires_follow_up"
        resolver_id = None
    return {
        "risk_id": item_id,
        "segment_id": source.get("segment_id"),
        "severity": source.get("severity", "warning"),
        "source_status": source.get("status"),
        "reason": source.get("reason"),
        "resolution_status": resolution_status,
        "resolution_artifact_references": [DOCUMENT_DECISION_LOG_JSONL if resolver and resolver.get("decision_id") else LEADERSHIP_REVIEW_EVIDENCE_JSONL if resolver else ""],
        "resolution_id": resolver_id,
        "accepted_limitations": _list_value(resolver.get("accepted_limitation") if resolver else None) + _list_value(resolver.get("limitations") if resolver else None),
    }


def _rejected_claim_wording(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "decision_id": item.get("decision_id"),
            "decision_type": item.get("decision_type"),
            "decision_status": item.get("decision_status"),
            "reason": item.get("decision_rationale"),
        }
        for item in decisions
        if item.get("decision_type") in {"reject_claim_wording", "request_rewrite"} or item.get("decision_status") in {"rejected", "blocked"}
    ]


def _signoff_requirements(claims: list[dict[str, Any]], publicity: list[dict[str, Any]], alignment: list[dict[str, Any]], limitations: list[str]) -> list[str]:
    requirements: list[str] = []
    if claims:
        requirements.append("resolve_claim_metric_risks")
    if publicity:
        requirements.append("resolve_publicity_risks")
    if alignment:
        requirements.append("confirm_semantic_alignment_risks")
    if limitations:
        requirements.append("accept_document_limitations_in_signoff")
    return requirements or ["document_signoff_available_after_scorecard_and_artifact_state_are_current"]


def _accepted_document_claims(resolution: dict[str, Any], leadership: list[dict[str, Any]]) -> list[str]:
    claims = {str(value) for record in leadership for value in record.get("reviewed_claims", []) if record.get("decision") in RESOLVING_STATUSES}
    if resolution.get("resolved_claim_metric_risks"):
        claims.add("document_claim_metric_risks_resolved")
    if resolution.get("accepted_publicity_risks"):
        claims.add("document_publicity_risks_accepted")
    if resolution.get("resolved_semantic_alignment_risks"):
        claims.add("document_semantic_alignment_confirmed")
    return sorted(claims)


def _document_decision_stale(artifact_state: dict[str, Any]) -> bool:
    if not isinstance(artifact_state, dict):
        return False
    stale_ids = {
        str(item.get("artifact_id"))
        for item in artifact_state.get("artifacts", [])
        if isinstance(item, dict) and item.get("status") in {"stale", "superseded", "blocked", "requires_human_review"}
    }
    return bool(stale_ids & {"document_decision_log", "leadership_review_evidence", "document_claim_resolution", "document_signoff_summary"})


def _next_required_action(stale: bool, unresolved_count: int, leadership_support: bool, signoff: dict[str, Any]) -> str:
    if stale:
        return "refresh_document_decision_evidence"
    if unresolved_count:
        return "resolve_document_risks"
    if not leadership_support:
        return "record_leadership_review_evidence"
    if not signoff:
        return "record_project_signoff"
    return "preserve_limitations_and_continue"


def _source_artifacts(state_dir: Path) -> dict[str, str]:
    names = {
        "claim_metric_report": CLAIM_METRIC_REPORT_JSON,
        "publicity_risk_report": PUBLICITY_RISK_REPORT_JSON,
        "semantic_alignment": SEMANTIC_ALIGNMENT_JSONL,
        "leadership_review_brief": LEADERSHIP_REVIEW_BRIEF_MD,
        "document_evidence_manifest": DOCUMENT_EVIDENCE_MANIFEST_JSON,
        "document_decision_log": DOCUMENT_DECISION_LOG_JSONL,
        "leadership_review_evidence": LEADERSHIP_REVIEW_EVIDENCE_JSONL,
        "evaluation_scorecard": "evaluation-scorecard.json",
        "artifact_state": "artifact-state.json",
        "signoff_record": "signoff-record.json",
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def _merged_scope(records: list[dict[str, Any]]) -> dict[str, Any]:
    if any((record.get("effective_scope") or record.get("review_scope") or {}).get("scope_type") == "full_run" for record in records if isinstance(record.get("effective_scope") or record.get("review_scope"), dict)):
        return {"scope_type": "full_run"}
    return {"scope_type": "limited", "source": "document_decision_or_leadership_review"}


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _read_optional_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [item for item in read_jsonl(path) if isinstance(item, dict)]


def _stable_id(prefix: str, value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
