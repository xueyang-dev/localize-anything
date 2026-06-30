from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, sha256_file, write_json, write_jsonl
from .provider_evidence import (
    PROVIDER_EVIDENCE_RECONCILIATION_JSON,
    PROVIDER_HANDOFF_REQUEST_JSON,
    PROVIDER_RESULT_INTAKE_JSONL,
)


PROVIDER_RESULT_QA_REPORT_JSON = "provider-result-qa-report.json"
PROVIDER_RESULT_REVIEW_EVIDENCE_JSONL = "provider-result-review-evidence.jsonl"
PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON = "provider-result-acceptance-decision.json"
PROVIDER_CLAIM_SUPPORT_REPORT_JSON = "provider-claim-support-report.json"
WORKBENCH_PROVIDER_REVIEW_QUEUE_JSON = "workbench-provider-review-queue.json"

PROVIDER_CLAIMS = {
    "provider_backed_quality",
    "provider_execution_complete",
    "provider_repair_complete",
    "model_repair_complete",
}
PROVIDER_SOURCES = {"real_provider", "external_provider_result"}
REVIEW_DECISIONS = {"accepted", "accepted_with_limitations", "rejected"}
ACCEPTANCE_DECISIONS = {"accepted", "accepted_with_limitations", "rejected"}

_PLACEHOLDER = re.compile(r"(?:\{[A-Za-z_][A-Za-z0-9_.-]*\}|%\d*\$?[A-Za-z]|\$\{[^}]+\})")
_MARKUP = re.compile(r"</?([A-Za-z][A-Za-z0-9:_-]*)\b[^>]*>")
_ESCAPE = re.compile(r"(?:\\[nrt'\"]|%%|&(?:amp|lt|gt|quot|apos);)")


def build_provider_result_qa_report(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    request = _optional_json(state_dir / PROVIDER_HANDOFF_REQUEST_JSON)
    reconciliation = _optional_json(state_dir / PROVIDER_EVIDENCE_RECONCILIATION_JSON)
    reconciled = {
        str(item.get("result_id") or ""): item
        for item in reconciliation.get("reconciled_results", [])
        if isinstance(item, dict)
    }
    results: list[dict[str, Any]] = []
    qa_items: list[dict[str, Any]] = []
    for record in _optional_jsonl(state_dir / PROVIDER_RESULT_INTAKE_JSONL):
        checks = _qa_checks(state_dir, record, request, reconciled.get(str(record.get("result_id") or ""), {}))
        qa_items.extend(checks)
        status = _qa_status(checks)
        results.append(
            {
                "result_id": record.get("result_id"),
                "request_id": record.get("request_id"),
                "result_source": record.get("result_source"),
                "status": status,
                "requires_human_review": any(item["status"] == "requires_human_review" for item in checks),
                "failed_check_types": [item["check_type"] for item in checks if item["status"] in {"failed", "blocked", "stale", "provenance_mismatch"}],
                "effective_scope": record.get("scope", {}),
            }
        )
    report_status = _report_status(results)
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-result-qa-report-v1",
        "artifact": PROVIDER_RESULT_QA_REPORT_JSON,
        "status": report_status,
        "summary": {
            "result_count": len(results),
            "passed_count": sum(item["status"] == "passed" for item in results),
            "failed_count": sum(item["status"] in {"failed", "blocked", "stale", "provenance_mismatch", "excluded"} for item in results),
            "human_review_required_count": sum(bool(item["requires_human_review"]) for item in results),
        },
        "results": results,
        "qa_items": qa_items,
        "forbidden_claims": sorted(PROVIDER_CLAIMS) if report_status != "passed" else ["provider_backed_quality", "provider_repair_complete", "model_repair_complete"],
        "source_artifacts": _source_artifacts(state_dir),
        "limitations": [
            "provider result intake does not equal QA pass",
            "deterministic QA does not prove semantic quality",
            "provider-backed quality still requires scoped review evidence, acceptance, and compatible signoff",
        ],
        "provider_or_model_called_by_runtime": False,
    }
    if write:
        write_json(state_dir / PROVIDER_RESULT_QA_REPORT_JSON, report)
    return report


def read_provider_result_qa_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_RESULT_QA_REPORT_JSON)


def record_provider_result_review_evidence(state_dir: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    if not isinstance(evidence, dict):
        raise ValueError("provider result review evidence must be a JSON object")
    result_id = str(evidence.get("result_id") or "")
    intake = {str(item.get("result_id") or ""): item for item in _optional_jsonl(state_dir / PROVIDER_RESULT_INTAKE_JSONL)}
    if not result_id or result_id not in intake:
        raise ValueError("review evidence must reference an existing provider result")
    reviewer_role = str(evidence.get("reviewer_role") or "").strip()
    reviewer_reference = str(evidence.get("reviewer_reference") or "").strip()
    if not reviewer_role or not reviewer_reference:
        raise ValueError("reviewer_role and reviewer_reference are required")
    review_decision = str(evidence.get("decision") or "")
    if review_decision not in REVIEW_DECISIONS:
        raise ValueError(f"decision must be one of: {', '.join(sorted(REVIEW_DECISIONS))}")
    scope = evidence.get("review_scope") if isinstance(evidence.get("review_scope"), dict) else {}
    if not scope:
        raise ValueError("review_scope is required")
    identity = {key: value for key, value in evidence.items() if key not in {"evidence_id", "reviewed_at"}}
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-result-review-evidence-v1",
        "evidence_id": str(evidence.get("evidence_id") or _stable_id("provider-review", identity)),
        "result_id": result_id,
        "reviewer_role": reviewer_role,
        "reviewer_reference": reviewer_reference,
        "decision": review_decision,
        "review_scope": scope,
        "semantic_quality_reviewed": bool(evidence.get("semantic_quality_reviewed")),
        "high_risk_reviewed": bool(evidence.get("high_risk_reviewed")),
        "limitations": _strings(evidence.get("limitations")),
        "rationale": str(evidence.get("rationale") or ""),
        "reviewed_at": str(evidence.get("reviewed_at") or _now()),
        "source_artifact_references": [PROVIDER_RESULT_INTAKE_JSONL, PROVIDER_RESULT_QA_REPORT_JSON],
        "provider_or_model_called_by_runtime": False,
    }
    records = read_provider_result_review_evidence(state_dir)
    records.append(record)
    write_jsonl(state_dir / PROVIDER_RESULT_REVIEW_EVIDENCE_JSONL, records)
    build_workbench_provider_review_queue(state_dir)
    build_provider_claim_support_report(state_dir)
    return record


def read_provider_result_review_evidence(state_dir: Path) -> list[dict[str, Any]]:
    return _optional_jsonl(state_dir / PROVIDER_RESULT_REVIEW_EVIDENCE_JSONL)


def record_provider_result_acceptance_decision(state_dir: Path, decision: dict[str, Any]) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    if not isinstance(decision, dict):
        raise ValueError("provider result acceptance decision must be a JSON object")
    requested = str(decision.get("decision") or "")
    if requested not in ACCEPTANCE_DECISIONS:
        raise ValueError(f"decision must be one of: {', '.join(sorted(ACCEPTANCE_DECISIONS))}")
    result_ids = _strings(decision.get("result_ids"))
    if not result_ids:
        raise ValueError("result_ids is required")
    decided_by = str(decision.get("decided_by") or "").strip()
    decided_role = str(decision.get("decided_role") or "").strip()
    if not decided_by or not decided_role:
        raise ValueError("decided_by and decided_role are required")
    scope = decision.get("effective_scope") if isinstance(decision.get("effective_scope"), dict) else {}
    if not scope:
        raise ValueError("effective_scope is required")
    qa = build_provider_result_qa_report(state_dir)
    qa_by_id = {str(item.get("result_id") or ""): item for item in qa.get("results", []) if isinstance(item, dict)}
    intake = {str(item.get("result_id") or ""): item for item in _optional_jsonl(state_dir / PROVIDER_RESULT_INTAKE_JSONL)}
    reviews = _latest_reviews(state_dir)
    reconciliation = _optional_json(state_dir / PROVIDER_EVIDENCE_RECONCILIATION_JSON)
    reconciled = {
        str(item.get("result_id") or ""): item
        for item in reconciliation.get("reconciled_results", [])
        if isinstance(item, dict)
    }
    accepted: list[str] = []
    limited: list[str] = []
    rejected: list[str] = []
    blockers: list[dict[str, str]] = []
    for result_id in result_ids:
        qa_result = qa_by_id.get(result_id, {})
        review = reviews.get(result_id, {})
        reasons = _acceptance_blockers(intake.get(result_id, {}), qa_result, review, reconciled.get(result_id, {}), scope)
        if requested == "rejected":
            rejected.append(result_id)
        elif reasons:
            blockers.extend({"result_id": result_id, "reason": reason} for reason in reasons)
        elif requested == "accepted_with_limitations" or review.get("decision") == "accepted_with_limitations" or _is_limited_scope(scope):
            limited.append(result_id)
        else:
            accepted.append(result_id)
    status = "rejected" if requested == "rejected" else "blocked" if blockers else "accepted_with_limitations" if limited else "accepted"
    forbidden = set(PROVIDER_CLAIMS)
    if accepted or limited:
        forbidden.discard("provider_execution_complete")
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-result-acceptance-decision-v1",
        "artifact": PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON,
        "decision_id": str(decision.get("decision_id") or _stable_id("provider-acceptance", [result_ids, requested, scope, decided_by])),
        "status": status,
        "requested_decision": requested,
        "result_ids": result_ids,
        "accepted_result_ids": accepted,
        "accepted_with_limitations_result_ids": limited,
        "rejected_result_ids": rejected,
        "effective_scope": scope,
        "decided_by": decided_by,
        "decided_role": decided_role,
        "decided_at": str(decision.get("decided_at") or _now()),
        "limitations": _strings(decision.get("limitations")),
        "rationale": str(decision.get("rationale") or ""),
        "blockers": blockers,
        "forbidden_claims_remaining": sorted(forbidden),
        "limited_scope_does_not_imply_global_readiness": True,
        "source_artifact_references": [PROVIDER_EVIDENCE_RECONCILIATION_JSON, PROVIDER_RESULT_QA_REPORT_JSON, PROVIDER_RESULT_REVIEW_EVIDENCE_JSONL],
        "provider_or_model_called_by_runtime": False,
    }
    write_json(state_dir / PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON, record)
    build_provider_claim_support_report(state_dir)
    build_workbench_provider_review_queue(state_dir)
    return record


def read_provider_result_acceptance_decision(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON)


def build_provider_claim_support_report(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    qa = _optional_json(state_dir / PROVIDER_RESULT_QA_REPORT_JSON)
    acceptance = _optional_json(state_dir / PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON)
    signoff = _optional_json(state_dir / "signoff-record.json")
    accepted = _strings(acceptance.get("accepted_result_ids"))
    limited = _strings(acceptance.get("accepted_with_limitations_result_ids"))
    qa_by_id = {str(item.get("result_id") or ""): item for item in qa.get("results", []) if isinstance(item, dict)}
    usable = [result_id for result_id in accepted + limited if qa_by_id.get(result_id, {}).get("status") in {"passed", "requires_human_review"}]
    execution_supported = bool(usable) and acceptance.get("status") in {"accepted", "accepted_with_limitations"}
    signoff_compatible = signoff.get("status") in {"accepted", "accepted_with_limitations"} and _scope_contains(signoff.get("signoff_scope", {}), acceptance.get("effective_scope", {}))
    full_scope = acceptance.get("status") == "accepted" and not _is_limited_scope(acceptance.get("effective_scope", {}))
    quality_supported = execution_supported and signoff_compatible and full_scope
    narrow_quality = execution_supported and signoff_compatible and not full_scope
    supported: list[dict[str, Any]] = []
    if execution_supported:
        supported.append({"claim": "provider_execution_complete", "support_status": "narrowly_supported" if limited else "supported", "effective_scope": acceptance.get("effective_scope", {})})
    if quality_supported:
        supported.append({"claim": "provider_backed_quality", "support_status": "supported", "effective_scope": acceptance.get("effective_scope", {})})
    narrow = []
    if narrow_quality:
        narrow.append({"claim": "provider_backed_quality", "support_status": "narrowly_supported", "effective_scope": acceptance.get("effective_scope", {}), "limitations": acceptance.get("limitations", [])})
    forbidden = set(PROVIDER_CLAIMS)
    if execution_supported:
        forbidden.discard("provider_execution_complete")
    if quality_supported:
        forbidden.discard("provider_backed_quality")
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-claim-support-report-v1",
        "artifact": PROVIDER_CLAIM_SUPPORT_REPORT_JSON,
        "status": "supported" if quality_supported else "limited" if execution_supported else "blocked",
        "supported_claims": supported,
        "narrowly_supported_claims": narrow,
        "forbidden_claims": sorted(forbidden),
        "global_forbidden_claims": ["provider_backed_quality"] if narrow_quality else [],
        "provider_execution_complete_supported": execution_supported,
        "provider_backed_quality_supported": quality_supported,
        "compatible_signoff": signoff_compatible,
        "effective_scope": acceptance.get("effective_scope", {}),
        "readiness_impact": "current" if quality_supported else "limited" if execution_supported else "blocked",
        "source_artifacts": _source_artifacts(state_dir),
        "limitations": [
            "QA pass does not equal semantic quality",
            "limited-scope provider acceptance does not become a global readiness claim",
            "provider repair and model repair claims are outside this seed",
        ],
        "provider_or_model_called_by_runtime": False,
    }
    if write:
        write_json(state_dir / PROVIDER_CLAIM_SUPPORT_REPORT_JSON, report)
    return report


def read_provider_claim_support_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_CLAIM_SUPPORT_REPORT_JSON)


def build_workbench_provider_review_queue(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    qa = _optional_json(state_dir / PROVIDER_RESULT_QA_REPORT_JSON) or build_provider_result_qa_report(state_dir)
    acceptance = _optional_json(state_dir / PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON)
    reviews = _latest_reviews(state_dir)
    accepted = set(_strings(acceptance.get("accepted_result_ids")))
    limited = set(_strings(acceptance.get("accepted_with_limitations_result_ids")))
    rejected = set(_strings(acceptance.get("rejected_result_ids")))
    items: list[dict[str, Any]] = []
    for result in qa.get("results", []):
        result_id = str(result.get("result_id") or "")
        review = reviews.get(result_id, {})
        if result_id in accepted:
            queue_status, action = "accepted", "none"
        elif result_id in limited:
            queue_status, action = "accepted_with_limitations", "preserve_scope_limit"
        elif result_id in rejected or review.get("decision") == "rejected":
            queue_status, action = "rejected", "none"
        elif result.get("status") in {"failed", "blocked", "stale", "provenance_mismatch", "excluded"}:
            queue_status, action = "blocked", "resolve_qa_or_evidence_failure"
        elif not review:
            queue_status, action = "requires_human_review", "record_provider_review_evidence"
        elif not acceptance:
            queue_status, action = "acceptance_required", "record_provider_acceptance_decision"
        else:
            queue_status, action = "pending", "review_acceptance_decision"
        items.append({"queue_item_id": _stable_id("provider-review-queue", result_id), "result_id": result_id, "qa_status": result.get("status"), "review_status": review.get("decision", "missing"), "queue_status": queue_status, "required_action": action, "effective_scope": result.get("effective_scope", {}), "source_artifact_references": [PROVIDER_RESULT_QA_REPORT_JSON, PROVIDER_RESULT_REVIEW_EVIDENCE_JSONL, PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON]})
    queue = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-provider-review-queue-v1",
        "artifact": WORKBENCH_PROVIDER_REVIEW_QUEUE_JSON,
        "status": "clear" if items and all(item["queue_status"] in {"accepted", "accepted_with_limitations", "rejected"} for item in items) else "action_required" if items else "empty",
        "items": items,
        "summary": {"item_count": len(items), "action_required_count": sum(item["queue_status"] not in {"accepted", "accepted_with_limitations", "rejected"} for item in items), "accepted_count": sum(item["queue_status"] == "accepted" for item in items), "limited_count": sum(item["queue_status"] == "accepted_with_limitations" for item in items), "rejected_count": sum(item["queue_status"] == "rejected" for item in items)},
        "provider_or_model_called_by_runtime": False,
    }
    if write:
        write_json(state_dir / WORKBENCH_PROVIDER_REVIEW_QUEUE_JSON, queue)
    return queue


def read_workbench_provider_review_queue(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / WORKBENCH_PROVIDER_REVIEW_QUEUE_JSON)


def provider_result_gate_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {"provider_result_qa_report": PROVIDER_RESULT_QA_REPORT_JSON, "provider_result_review_evidence": PROVIDER_RESULT_REVIEW_EVIDENCE_JSONL, "provider_result_acceptance_decision": PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON, "provider_claim_support_report": PROVIDER_CLAIM_SUPPORT_REPORT_JSON, "workbench_provider_review_queue": WORKBENCH_PROVIDER_REVIEW_QUEUE_JSON}
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def _qa_checks(state_dir: Path, record: dict[str, Any], request: dict[str, Any], reconciled: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    add = lambda kind, status, reason, blocking=True: checks.append(_qa_item(record, kind, status, reason, blocking))
    source = str(record.get("result_source") or "")
    add("provider_source_eligible", "passed" if source in PROVIDER_SOURCES else "excluded", "provider source is eligible" if source in PROVIDER_SOURCES else f"{source or 'unknown'} cannot support provider-backed claims")
    request_match = bool(request) and str(record.get("request_id") or "") == str(request.get("request_id") or "")
    add("request_match", "passed" if request_match else "failed", "provider request matched" if request_match else "provider request is missing or mismatched")
    reconciliation_ok = reconciled.get("reconciliation_status") == "accepted_provider_execution_evidence"
    add("reconciliation_match", "passed" if reconciliation_ok else "failed", "provider evidence reconciliation accepted the result" if reconciliation_ok else "provider evidence is not reconciled")
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    provenance_ok = bool(provenance.get("provider_name") and (provenance.get("external_reference") or provenance.get("request_id")))
    add("provenance_match", "passed" if provenance_ok else "provenance_mismatch", "provider provenance is present" if provenance_ok else "provider provenance is missing or incomplete")
    references = _strings(record.get("target_artifact_references"))
    expected_hashes = record.get("target_artifact_hashes") if isinstance(record.get("target_artifact_hashes"), dict) else {}
    current_hashes = {name: sha256_file(state_dir / name) for name in references if (state_dir / name).is_file()}
    hashes_ok = bool(references) and all(expected_hashes.get(name) == current_hashes.get(name) for name in references)
    add("target_hash_match", "passed" if hashes_ok else "stale", "provider target artifact hashes match current files" if hashes_ok else "provider target artifact is missing or stale")
    result_scope = record.get("scope") if isinstance(record.get("scope"), dict) else {}
    request_scope = request.get("scope") if isinstance(request.get("scope"), dict) else {}
    scope_ok = bool(result_scope) and _scope_contains(request_scope, result_scope)
    add("scope_match", "passed" if scope_ok else "failed", "provider result scope matches handoff request" if scope_ok else "provider result scope is missing or exceeds the handoff request")
    segments = [item for item in record.get("segments", []) if isinstance(item, dict)]
    add("result_content_available", "passed" if segments else "failed", "structured provider result segments are available" if segments else "structured provider result segments are missing")
    for segment in segments:
        source_text = str(segment.get("source") or "")
        target_text = str(segment.get("target") or "")
        constraints = segment.get("constraints") if isinstance(segment.get("constraints"), dict) else {}
        segment_id = str(segment.get("segment_id") or "unknown")
        for kind, pattern in (("placeholder_preservation", _PLACEHOLDER), ("markup_preservation", _MARKUP), ("escape_preservation", _ESCAPE)):
            status, reason = _signature_check(pattern, source_text, target_text, kind, segment_id)
            add(kind, status, reason, status not in {"passed", "not_applicable"})
        forbidden = _strings(constraints.get("forbidden_translations"))
        forbidden_hits = [term for term in forbidden if term and term in target_text]
        add("forbidden_translation_absent", "failed" if forbidden_hits else "passed", f"forbidden translations remain in {segment_id}: {', '.join(forbidden_hits)}" if forbidden_hits else f"forbidden translations are absent in {segment_id}")
        required = _strings(constraints.get("required_terms"))
        missing_terms = [term for term in required if term and term not in target_text]
        add("term_constraints_satisfied", "failed" if missing_terms else "passed", f"required terms are missing in {segment_id}: {', '.join(missing_terms)}" if missing_terms else f"term constraints are satisfied in {segment_id}")
        blind = str(request.get("operating_mode") or request_scope.get("operating_mode") or result_scope.get("operating_mode") or "") == "blind_benchmark"
        leakage = bool(segment.get("target_context_used") or segment.get("reference_target_used"))
        add("blind_benchmark_firewall", "blocked" if blind and leakage else "passed", f"blind benchmark target context leaked into {segment_id}" if blind and leakage else f"blind benchmark firewall is preserved for {segment_id}")
    high_risk = any(bool(item.get("high_risk") or item.get("semantic_change")) for item in segments)
    add("human_review_requirement", "requires_human_review" if high_risk else "not_applicable", "semantic or high-risk provider output requires scoped human review" if high_risk else "no high-risk or semantic change is declared", high_risk)
    return checks


def _qa_item(record: dict[str, Any], check_type: str, status: str, reason: str, blocking: bool) -> dict[str, Any]:
    return {"qa_item_id": _stable_id("provider-result-qa", [record.get("result_id"), check_type, reason]), "result_id": record.get("result_id"), "request_id": record.get("request_id"), "check_type": check_type, "status": status, "reason": reason, "blocking": bool(blocking and status not in {"passed", "not_applicable"}), "source_artifact_references": [PROVIDER_RESULT_INTAKE_JSONL, PROVIDER_HANDOFF_REQUEST_JSON, PROVIDER_EVIDENCE_RECONCILIATION_JSON], "target_artifact_references": record.get("target_artifact_references", [])}


def _qa_status(checks: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "") for item in checks}
    for status in ("excluded", "stale", "provenance_mismatch", "blocked", "failed"):
        if status in statuses:
            return status
    if "requires_human_review" in statuses:
        return "requires_human_review"
    return "passed" if checks else "not_run"


def _report_status(results: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "") for item in results}
    if statuses.intersection({"failed", "blocked", "stale", "provenance_mismatch", "excluded"}):
        return "blocked"
    if "requires_human_review" in statuses:
        return "requires_human_review"
    return "passed" if results else "not_run"


def _acceptance_blockers(record: dict[str, Any], qa: dict[str, Any], review: dict[str, Any], reconciled: dict[str, Any], scope: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not record or record.get("result_source") not in PROVIDER_SOURCES:
        reasons.append("result_is_not_provider_backed")
    if reconciled.get("reconciliation_status") != "accepted_provider_execution_evidence":
        reasons.append("provider_evidence_not_reconciled")
    if qa.get("status") not in {"passed", "requires_human_review"}:
        reasons.append("deterministic_qa_not_passed")
    if review.get("decision") not in {"accepted", "accepted_with_limitations"}:
        reasons.append("scoped_human_review_not_accepted")
    if not _scope_contains(review.get("review_scope", {}), scope):
        reasons.append("review_scope_does_not_cover_acceptance_scope")
    if qa.get("requires_human_review") and not (review.get("semantic_quality_reviewed") or review.get("high_risk_reviewed")):
        reasons.append("semantic_or_high_risk_review_missing")
    return reasons


def _latest_reviews(state_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in read_provider_result_review_evidence(state_dir):
        result[str(item.get("result_id") or "")] = item
    return result


def _signature_check(pattern: re.Pattern[str], source: str, target: str, label: str, segment_id: str) -> tuple[str, str]:
    expected = sorted(pattern.findall(source))
    if not expected:
        return "not_applicable", f"no source {label} signature in {segment_id}"
    actual = sorted(pattern.findall(target))
    return ("passed", f"{label} signature is preserved in {segment_id}") if expected == actual else ("failed", f"{label} signature changed in {segment_id}")


def _scope_contains(container: Any, requested: Any) -> bool:
    if not isinstance(container, dict) or not isinstance(requested, dict) or not requested:
        return False
    if container.get("scope_type") == "full_run":
        return True
    for key, value in requested.items():
        candidate = container.get(key)
        if isinstance(value, list):
            if not set(map(str, value)).issubset(set(map(str, candidate or []))):
                return False
        elif candidate != value:
            return False
    return True


def _is_limited_scope(scope: Any) -> bool:
    return not isinstance(scope, dict) or scope.get("scope_type") != "full_run"


def _source_artifacts(state_dir: Path) -> dict[str, str]:
    names = [PROVIDER_RESULT_INTAKE_JSONL, PROVIDER_EVIDENCE_RECONCILIATION_JSON, PROVIDER_RESULT_QA_REPORT_JSON, PROVIDER_RESULT_REVIEW_EVIDENCE_JSONL, PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON, "signoff-record.json"]
    return {name: name for name in names if (state_dir / name).is_file()}


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str) and value:
        return [value]
    return []


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _optional_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.is_file() else []


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing provider result gate artifact: {path}")
    return _optional_json(path)


def _stable_id(prefix: str, value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:24]}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
