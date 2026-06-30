from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, sha256_file, write_json


READINESS_AUTHORIZATION_MATRIX_JSON = "readiness-authorization-matrix.json"
MANUAL_FOLLOWUP_GAP_REPORT_JSON = "manual-followup-gap-report.json"
APPLY_READINESS_REPORT_JSON = "apply-readiness-report.json"
DELIVERY_READINESS_REPORT_JSON = "delivery-readiness-report.json"

READY = "ready"
READY_WITH_WARNINGS = "ready_with_warnings"
REVIEW_REQUIRED = "review_required"
AUTHORIZATION_REQUIRED = "authorization_required"
BLOCKED = "blocked"
STALE = "stale"
PARTIAL = "partial"
NOT_APPLICABLE = "not_applicable"
UNKNOWN = "unknown"

STRONG_CLAIMS = {
    "full_quality",
    "full_coverage",
    "provider_backed_quality",
    "knowledge_backed_quality",
    "knowledge_constraints_applied",
    "knowledge_review_complete",
    "full_terminology_assurance",
    "review_complete",
    "delivery_ready",
    "apply_ready",
    "production_ready",
    "layout_verified",
}
APPLY_BLOCKING_CLAIMS = {"apply_ready", "production_ready", "provider_backed_quality", "knowledge_backed_quality"}
DELIVERY_BLOCKING_CLAIMS = {"delivery_ready", "production_ready", "provider_backed_quality", "knowledge_backed_quality"}


def build_readiness_reports(state_dir: Path, *, delivery_dir: Path | None = None, run_id: str | None = None, write: bool = True) -> dict[str, Any]:
    matrix = build_readiness_authorization_matrix(state_dir, delivery_dir=delivery_dir, run_id=run_id, write=write)
    gaps = build_manual_followup_gap_report(state_dir, delivery_dir=delivery_dir, matrix=matrix, run_id=run_id, write=write)
    apply = build_apply_readiness_report(state_dir, delivery_dir=delivery_dir, matrix=matrix, gaps=gaps, run_id=run_id, write=write)
    delivery = build_delivery_readiness_report(state_dir, delivery_dir=delivery_dir, matrix=matrix, gaps=gaps, run_id=run_id, write=write)
    return {
        "readiness_authorization_matrix": matrix,
        "manual_followup_gap_report": gaps,
        "apply_readiness_report": apply,
        "delivery_readiness_report": delivery,
    }


def build_readiness_authorization_matrix(
    state_dir: Path,
    *,
    delivery_dir: Path | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    delivery_dir = delivery_dir.resolve() if delivery_dir else None
    artifacts = _load_artifacts(state_dir, delivery_dir)
    scorecard = artifacts["evaluation_scorecard"]
    forbidden = set(_strings(scorecard.get("forbidden_claims")))
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    evidence_freshness = _freshness_status(artifacts["artifact_state"])
    signoff_status = _signoff_status(artifacts["signoff_record"], artifacts["artifact_state"])
    claim_status = _claim_status(artifacts["claim_acceptance_decision"], artifacts["artifact_state"])
    handoff_status = _handoff_status(artifacts["generation_handoff_decision"])
    repair_status = _repair_closure_status(artifacts["knowledge_repair_closure_decision"], artifacts["knowledge_recompute_result"])
    document_status = _document_status(artifacts)
    knowledge_status = _knowledge_status(artifacts)
    provider_status = _provider_status(artifacts)
    coverage_status = _coverage_status(scorecard)
    qa_status = _qa_status(artifacts)

    _collect_blockers_and_warnings(
        blockers,
        warnings,
        scorecard,
        evidence_freshness,
        signoff_status,
        claim_status,
        handoff_status,
        repair_status,
        document_status,
        knowledge_status,
        provider_status,
        coverage_status,
        qa_status,
        artifacts,
    )
    forbidden.update(_forbidden_from_statuses(evidence_freshness, handoff_status, repair_status, document_status, knowledge_status, provider_status, coverage_status, qa_status))

    delivery_status = _delivery_matrix_status(blockers, warnings, scorecard, signoff_status, claim_status, forbidden)
    apply_status = _apply_matrix_status(blockers, warnings, scorecard, signoff_status, delivery_status, forbidden)
    review_status = _review_matrix_status(scorecard, document_status, knowledge_status, warnings, forbidden)
    production_status = READY if delivery_status == READY and apply_status == READY and "production_ready" not in forbidden else BLOCKED

    matrix = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-readiness-authorization-matrix-v1",
        "artifact": READINESS_AUTHORIZATION_MATRIX_JSON,
        "run_id": run_id or _run_id(artifacts),
        "delivery_readiness_status": delivery_status,
        "apply_readiness_status": apply_status,
        "review_readiness_status": review_status,
        "production_readiness_status": production_status,
        "evidence_freshness_status": evidence_freshness["status"],
        "signoff_status": signoff_status,
        "claim_acceptance_status": claim_status,
        "repair_closure_status": repair_status,
        "document_evidence_status": document_status,
        "knowledge_evidence_status": knowledge_status,
        "provider_policy_status": provider_status,
        "coverage_status": coverage_status,
        "qa_status": qa_status,
        "authorization_requirements": _authorization_requirements(delivery_status, apply_status, signoff_status, claim_status),
        "blockers": blockers,
        "warnings": warnings,
        "forbidden_claims": sorted(forbidden),
        "limitations": _limitations(delivery_status, apply_status, forbidden, artifacts),
        "effective_scope": _effective_scope(artifacts),
        "recommended_next_actions": _recommended_next_actions(blockers, warnings, delivery_status, apply_status),
        "source_artifacts": _source_artifacts(state_dir, delivery_dir),
        "summary": {
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "forbidden_claim_count": len(forbidden),
            "delivery_ready": delivery_status == READY,
            "apply_ready": apply_status == READY,
        },
    }
    if write:
        write_json(state_dir / READINESS_AUTHORIZATION_MATRIX_JSON, matrix)
    return matrix


def build_manual_followup_gap_report(
    state_dir: Path,
    *,
    delivery_dir: Path | None = None,
    matrix: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    delivery_dir = delivery_dir.resolve() if delivery_dir else None
    artifacts = _load_artifacts(state_dir, delivery_dir)
    matrix = matrix or build_readiness_authorization_matrix(state_dir, delivery_dir=delivery_dir, run_id=run_id, write=False)
    gaps: list[dict[str, Any]] = []

    _add_term_gaps(gaps, artifacts)
    _add_blocking_question_gaps(gaps, artifacts)
    _add_human_review_gaps(gaps, artifacts, matrix)
    _add_claim_and_signoff_gaps(gaps, artifacts, matrix)
    _add_document_gaps(gaps, artifacts)
    _add_knowledge_gaps(gaps, artifacts)
    _add_repair_closure_gaps(gaps, artifacts)
    _add_artifact_refresh_gaps(gaps, artifacts)
    _add_provider_and_coverage_gaps(gaps, matrix)
    _add_forbidden_claim_gaps(gaps, matrix)

    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-manual-followup-gap-report-v1",
        "artifact": MANUAL_FOLLOWUP_GAP_REPORT_JSON,
        "run_id": run_id or _run_id(artifacts),
        "status": BLOCKED if any(item["blocks_delivery"] or item["blocks_apply"] for item in gaps) else READY_WITH_WARNINGS if gaps else READY,
        "gaps": gaps,
        "summary": {
            "gap_count": len(gaps),
            "delivery_blocking_count": sum(bool(item["blocks_delivery"]) for item in gaps),
            "apply_blocking_count": sum(bool(item["blocks_apply"]) for item in gaps),
            "production_blocking_count": sum(bool(item["blocks_production_ready_claim"]) for item in gaps),
            "warning_count": sum(bool(item["warning_only"]) for item in gaps),
        },
        "source_artifacts": _source_artifacts(state_dir, delivery_dir),
        "limitations": ["manual follow-up gaps are projections over artifacts and do not resolve decisions by themselves"],
    }
    if write:
        write_json(state_dir / MANUAL_FOLLOWUP_GAP_REPORT_JSON, report)
    return report


def build_apply_readiness_report(
    state_dir: Path,
    *,
    delivery_dir: Path | None = None,
    matrix: dict[str, Any] | None = None,
    gaps: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    delivery_dir = delivery_dir.resolve() if delivery_dir else None
    artifacts = _load_artifacts(state_dir, delivery_dir)
    matrix = matrix or build_readiness_authorization_matrix(state_dir, delivery_dir=delivery_dir, run_id=run_id, write=False)
    gaps = gaps or build_manual_followup_gap_report(state_dir, delivery_dir=delivery_dir, matrix=matrix, run_id=run_id, write=False)
    apply_status = str(matrix.get("apply_readiness_status") or BLOCKED)
    blocking_risks = list(matrix.get("blockers", [])) + [gap for gap in gaps.get("gaps", []) if gap.get("blocks_apply")]
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-apply-readiness-report-v1",
        "artifact": APPLY_READINESS_REPORT_JSON,
        "run_id": run_id or _run_id(artifacts),
        "apply_status": apply_status,
        "apply_mode": "blocked" if apply_status in {BLOCKED, STALE, PARTIAL} else "explicit_authorization_required" if apply_status == AUTHORIZATION_REQUIRED else "dry_run_authorized",
        "target_scope": matrix.get("effective_scope", {}),
        "blocking_risks": blocking_risks,
        "stale_artifacts": _stale_artifacts(artifacts["artifact_state"]),
        "required_signoff": _required_signoff(matrix, "apply"),
        "required_claim_acceptance": _required_claim_acceptance(matrix, "apply"),
        "required_repair_closure": matrix.get("repair_closure_status", {}),
        "required_qa": matrix.get("qa_status", {}),
        "provider_policy_status": matrix.get("provider_policy_status", {}),
        "knowledge_document_evidence_status": {
            "knowledge": matrix.get("knowledge_evidence_status", {}),
            "document": matrix.get("document_evidence_status", {}),
        },
        "forbidden_claims_that_prevent_apply": sorted(set(matrix.get("forbidden_claims", [])) & APPLY_BLOCKING_CLAIMS),
        "safe_apply_limitations": _apply_limitations(matrix),
        "recommended_next_action": _first_next_action(matrix, "Resolve apply blockers, then refresh apply readiness."),
        "source_artifacts": _source_artifacts(state_dir, delivery_dir),
        "limitations": ["apply readiness is separate from delivery readiness and still requires explicit apply authorization"],
    }
    if write:
        write_json(state_dir / APPLY_READINESS_REPORT_JSON, report)
    return report


def build_delivery_readiness_report(
    state_dir: Path,
    *,
    delivery_dir: Path | None = None,
    matrix: dict[str, Any] | None = None,
    gaps: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    delivery_dir = delivery_dir.resolve() if delivery_dir else None
    artifacts = _load_artifacts(state_dir, delivery_dir)
    matrix = matrix or build_readiness_authorization_matrix(state_dir, delivery_dir=delivery_dir, run_id=run_id, write=False)
    gaps = gaps or build_manual_followup_gap_report(state_dir, delivery_dir=delivery_dir, matrix=matrix, run_id=run_id, write=False)
    delivery_status = str(matrix.get("delivery_readiness_status") or BLOCKED)
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-delivery-readiness-report-v1",
        "artifact": DELIVERY_READINESS_REPORT_JSON,
        "run_id": run_id or _run_id(artifacts),
        "delivery_status": delivery_status,
        "delivery_mode": _delivery_mode(delivery_status, matrix),
        "target_audience": "reviewer_or_project_owner" if delivery_status != READY else "authorized_recipient",
        "effective_scope": matrix.get("effective_scope", {}),
        "included_artifacts": _included_artifacts(artifacts),
        "excluded_artifacts": _excluded_artifacts(artifacts),
        "warnings": matrix.get("warnings", []),
        "blockers": list(matrix.get("blockers", [])) + [gap for gap in gaps.get("gaps", []) if gap.get("blocks_delivery")],
        "forbidden_claims": matrix.get("forbidden_claims", []),
        "limitations": matrix.get("limitations", []),
        "review_requirements": [gap for gap in gaps.get("gaps", []) if gap.get("gap_type") in {"human_review_required", "native_review_required", "professional_review_required"}],
        "signoff_requirements": _required_signoff(matrix, "delivery"),
        "recommended_next_action": _first_next_action(matrix, "Resolve delivery blockers, then refresh delivery readiness."),
        "source_artifacts": _source_artifacts(state_dir, delivery_dir),
    }
    if write:
        write_json(state_dir / DELIVERY_READINESS_REPORT_JSON, report)
    return report


def read_readiness_authorization_matrix(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / READINESS_AUTHORIZATION_MATRIX_JSON)


def read_manual_followup_gap_report(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / MANUAL_FOLLOWUP_GAP_REPORT_JSON)


def read_apply_readiness_report(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / APPLY_READINESS_REPORT_JSON)


def read_delivery_readiness_report(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / DELIVERY_READINESS_REPORT_JSON)


def readiness_authorization_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "readiness_authorization_matrix": READINESS_AUTHORIZATION_MATRIX_JSON,
        "manual_followup_gap_report": MANUAL_FOLLOWUP_GAP_REPORT_JSON,
        "apply_readiness_report": APPLY_READINESS_REPORT_JSON,
        "delivery_readiness_report": DELIVERY_READINESS_REPORT_JSON,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def _load_artifacts(state_dir: Path, delivery_dir: Path | None) -> dict[str, Any]:
    return {
        "evaluation_scorecard": _read_optional_json(_first_existing(state_dir, delivery_dir, "evaluation-scorecard.json")),
        "generation_handoff_decision": _read_optional_json(_first_existing(state_dir, delivery_dir, "generation-handoff-decision.json")),
        "delivery_decision": _read_optional_json(_first_existing(state_dir, delivery_dir, "delivery-decision.json")),
        "delivery_manifest": _read_optional_json(_first_existing(state_dir, delivery_dir, "delivery-manifest.json")),
        "artifact_state": _read_optional_json(_first_existing(state_dir, delivery_dir, "artifact-state.json")),
        "claim_acceptance_decision": _read_optional_json(_first_existing(state_dir, delivery_dir, "claim-acceptance-decision.json")),
        "signoff_record": _read_optional_json(_first_existing(state_dir, delivery_dir, "signoff-record.json")),
        "human_review_evidence": _read_optional_jsonl(_first_existing(state_dir, delivery_dir, "human-review-evidence.jsonl")),
        "blocking_questions": _read_optional_json(_first_existing(state_dir, delivery_dir, "blocking-questions.json")),
        "term_review_queue": _read_optional_json(_first_existing(state_dir, delivery_dir, "term-review-queue.json")),
        "document_evidence_manifest": _read_optional_json(_first_existing(state_dir, delivery_dir, "document-evidence-manifest.json")),
        "document_signoff_summary": _read_optional_json(_first_existing(state_dir, delivery_dir, "document-signoff-summary.json")),
        "document_claim_resolution": _read_optional_json(_first_existing(state_dir, delivery_dir, "document-claim-resolution.json")),
        "workbench_document_evidence_queue": _read_optional_json(_first_existing(state_dir, delivery_dir, "workbench-document-evidence-queue.json")),
        "knowledge_audit_enforcement_decision": _read_optional_json(_first_existing(state_dir, delivery_dir, "knowledge-audit-enforcement-decision.json")),
        "knowledge_assurance_summary": _read_optional_json(_first_existing(state_dir, delivery_dir, "knowledge-assurance-summary.json")),
        "workbench_knowledge_review_queue": _read_optional_json(_first_existing(state_dir, delivery_dir, "workbench-knowledge-review-queue.json")),
        "knowledge_repair_closure_decision": _read_optional_json(_first_existing(state_dir, delivery_dir, "knowledge-repair-closure-decision.json")),
        "knowledge_recompute_result": _read_optional_json(_first_existing(state_dir, delivery_dir, "knowledge-recompute-result.json")),
        "knowledge_readiness_impact_report": _read_optional_json(_first_existing(state_dir, delivery_dir, "knowledge-readiness-impact-report.json")),
        "repair_result": _read_optional_json(_first_existing(state_dir, delivery_dir, "repair-result.json")),
        "repair_history": _read_optional_jsonl(_first_existing(state_dir, delivery_dir, "repair-history.jsonl")),
    }


def _collect_blockers_and_warnings(
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    scorecard: dict[str, Any],
    evidence_freshness: dict[str, Any],
    signoff_status: dict[str, Any],
    claim_status: dict[str, Any],
    handoff_status: dict[str, Any],
    repair_status: dict[str, Any],
    document_status: dict[str, Any],
    knowledge_status: dict[str, Any],
    provider_status: dict[str, Any],
    coverage_status: dict[str, Any],
    qa_status: dict[str, Any],
    artifacts: dict[str, Any],
) -> None:
    if not scorecard:
        blockers.append(_issue("scorecard_missing", "evidence", "Evaluation scorecard is missing.", "evaluation-scorecard.json"))
    elif str(scorecard.get("overall_claim") or "") in {"blocked", "not_ready"} or scorecard.get("status") == "blocked":
        blockers.append(_issue("scorecard_blocked", "evidence", "Evaluation scorecard does not support delivery/apply readiness.", "evaluation-scorecard.json"))
    if evidence_freshness["status"] in {STALE, BLOCKED}:
        blockers.append(_issue("artifact_state_stale", "artifact_state", evidence_freshness["summary"], "artifact-state.json"))
    for status_name, status, artifact in (
        ("handoff_blocked", handoff_status, "generation-handoff-decision.json"),
        ("repair_closure_blocked", repair_status, "knowledge-repair-closure-decision.json"),
        ("document_evidence_blocked", document_status, "document-evidence-manifest.json"),
        ("knowledge_evidence_blocked", knowledge_status, "knowledge-audit-enforcement-decision.json"),
        ("provider_policy_blocked", provider_status, "delivery-manifest.json"),
        ("coverage_blocked", coverage_status, "evaluation-scorecard.json"),
        ("qa_blocked", qa_status, "delivery-manifest.json"),
    ):
        if status["status"] in {BLOCKED, STALE}:
            blockers.append(_issue(status_name, status.get("domain", "evidence"), status.get("summary", status["status"]), artifact))
        elif status["status"] in {REVIEW_REQUIRED, AUTHORIZATION_REQUIRED, PARTIAL, UNKNOWN}:
            warnings.append(_issue(status_name, status.get("domain", "evidence"), status.get("summary", status["status"]), artifact, severity="warning"))
    if signoff_status["status"] in {BLOCKED, STALE}:
        blockers.append(_issue("signoff_blocked", "signoff", signoff_status["summary"], "signoff-record.json"))
    elif signoff_status["status"] in {AUTHORIZATION_REQUIRED, UNKNOWN}:
        warnings.append(_issue("signoff_required", "signoff", signoff_status["summary"], "signoff-record.json", severity="warning"))
    if claim_status["status"] in {BLOCKED, STALE}:
        blockers.append(_issue("claim_acceptance_blocked", "claim_acceptance", claim_status["summary"], "claim-acceptance-decision.json"))
    elif claim_status["status"] in {AUTHORIZATION_REQUIRED, UNKNOWN}:
        warnings.append(_issue("claim_acceptance_required", "claim_acceptance", claim_status["summary"], "claim-acceptance-decision.json", severity="warning"))
    if _delivery_decision_blocked(artifacts["delivery_decision"]):
        blockers.append(_issue("delivery_decision_blocked", "delivery", "Delivery decision contains blocking decisions.", "delivery-decision.json"))


def _freshness_status(artifact_state: dict[str, Any]) -> dict[str, Any]:
    if not artifact_state:
        return {"status": UNKNOWN, "summary": "artifact-state.json is missing"}
    stale = artifact_state.get("stale_artifacts", [])
    blocked = artifact_state.get("blocked_artifacts", [])
    if blocked:
        return {"status": BLOCKED, "summary": "artifact-state contains blocked artifacts", "artifacts": blocked}
    if stale or artifact_state.get("status") == "stale":
        return {"status": STALE, "summary": "artifact-state contains stale artifacts", "artifacts": stale}
    if artifact_state.get("status") in {"current", "accepted"}:
        return {"status": READY, "summary": "artifact-state is current"}
    return {"status": UNKNOWN, "summary": f"artifact-state status is {artifact_state.get('status', 'unknown')}"}


def _signoff_status(signoff: dict[str, Any], artifact_state: dict[str, Any]) -> dict[str, Any]:
    if not signoff:
        return {"status": AUTHORIZATION_REQUIRED, "summary": "signoff-record.json is missing", "delivery_authorized": False, "apply_authorized": False}
    stale = _artifact_status(artifact_state, "signoff_record") in {STALE, "superseded"}
    if stale or str(signoff.get("status") or "") in {"stale", "superseded"}:
        return {"status": STALE, "summary": "signoff is stale or superseded", "delivery_authorized": False, "apply_authorized": False}
    if str(signoff.get("status") or "") in {"rejected", "requires_follow_up"}:
        return {"status": BLOCKED, "summary": f"signoff status is {signoff.get('status')}", "delivery_authorized": False, "apply_authorized": False}
    if signoff.get("delivery_authorized") or signoff.get("apply_authorized"):
        return {
            "status": READY_WITH_WARNINGS if signoff.get("limitations_accepted") else READY,
            "summary": "signoff authorizes requested scope",
            "delivery_authorized": bool(signoff.get("delivery_authorized")),
            "apply_authorized": bool(signoff.get("apply_authorized")),
        }
    return {"status": AUTHORIZATION_REQUIRED, "summary": "signoff does not authorize delivery or apply", "delivery_authorized": False, "apply_authorized": False}


def _claim_status(claim: dict[str, Any], artifact_state: dict[str, Any]) -> dict[str, Any]:
    if not claim:
        return {"status": AUTHORIZATION_REQUIRED, "summary": "claim-acceptance-decision.json is missing", "accepted_claims": []}
    stale = _artifact_status(artifact_state, "claim_acceptance_decision") in {STALE, "superseded"}
    if stale or str(claim.get("status") or "") in {"stale", "superseded"}:
        return {"status": STALE, "summary": "claim acceptance is stale", "accepted_claims": []}
    if str(claim.get("status") or "") == "blocked":
        return {"status": BLOCKED, "summary": "claim acceptance has blocked claims", "accepted_claims": claim.get("accepted_claims", [])}
    accepted = list(claim.get("accepted_claims", [])) + list(claim.get("accepted_with_limitations", []))
    return {"status": READY_WITH_WARNINGS if claim.get("accepted_with_limitations") else READY, "summary": "claim acceptance is current", "accepted_claims": accepted}


def _handoff_status(handoff: dict[str, Any]) -> dict[str, Any]:
    if not handoff:
        return {"status": UNKNOWN, "domain": "handoff", "summary": "generation-handoff-decision.json is missing"}
    raw = str(handoff.get("status") or handoff.get("handoff_status") or handoff.get("readiness") or "")
    if raw in {"blocked", "stale"} or handoff.get("allow_generation") is False:
        return {"status": BLOCKED, "domain": "handoff", "summary": "generation handoff is blocked"}
    if raw in {"review_required", "draft_only", "allowed_with_warnings", "knowledge_review_required"}:
        return {"status": REVIEW_REQUIRED, "domain": "handoff", "summary": f"generation handoff is {raw}"}
    return {"status": READY, "domain": "handoff", "summary": "generation handoff has no blocking status"}


def _repair_closure_status(closure: dict[str, Any], recompute: dict[str, Any]) -> dict[str, Any]:
    if not closure:
        return {"status": NOT_APPLICABLE, "domain": "repair", "summary": "knowledge repair closure was not required"}
    status = str(closure.get("status") or "")
    if status in {"still_blocked", "requires_human_review"}:
        return {"status": BLOCKED, "domain": "repair", "summary": f"knowledge repair closure is {status}"}
    if status in {"stale", "requires_recompute", "partially_closed"}:
        return {"status": STALE if status == "stale" else PARTIAL, "domain": "repair", "summary": f"knowledge repair closure is {status}"}
    if status == "closed_with_warnings":
        return {"status": READY_WITH_WARNINGS, "domain": "repair", "summary": "knowledge repair closure is closed with warnings"}
    if status == "closed" and str(recompute.get("status") or "") in {"completed", ""}:
        return {"status": READY, "domain": "repair", "summary": "knowledge repair closure is closed"}
    return {"status": NOT_APPLICABLE if status == "not_applicable" else UNKNOWN, "domain": "repair", "summary": f"knowledge repair closure status is {status or 'unknown'}"}


def _document_status(artifacts: dict[str, Any]) -> dict[str, Any]:
    queue = artifacts["workbench_document_evidence_queue"]
    signoff = artifacts["document_signoff_summary"]
    resolution = artifacts["document_claim_resolution"]
    manifest = artifacts["document_evidence_manifest"]
    if not any((queue, signoff, resolution, manifest)):
        return {"status": NOT_APPLICABLE, "domain": "document", "summary": "document evidence not present"}
    if any(str(item.get("status") or "") in {"blocked", "stale"} for item in (signoff, resolution, manifest) if item):
        return {"status": BLOCKED, "domain": "document", "summary": "document evidence or signoff is blocked/stale"}
    queue_summary = queue.get("summary", {}) if isinstance(queue, dict) else {}
    if int(queue_summary.get("blocking_count", 0) or 0):
        return {"status": BLOCKED, "domain": "document", "summary": "document evidence queue has blocking items"}
    if int(queue_summary.get("item_count", 0) or 0) or str(signoff.get("status") or "") in {"requires_follow_up", "review_required"}:
        return {"status": REVIEW_REQUIRED, "domain": "document", "summary": "document evidence requires review or leadership signoff"}
    return {"status": READY, "domain": "document", "summary": "document evidence has no active blockers"}


def _knowledge_status(artifacts: dict[str, Any]) -> dict[str, Any]:
    enforcement = artifacts["knowledge_audit_enforcement_decision"]
    assurance = artifacts["knowledge_assurance_summary"]
    queue = artifacts["workbench_knowledge_review_queue"]
    if not any((enforcement, assurance, queue)):
        return {"status": NOT_APPLICABLE, "domain": "knowledge", "summary": "knowledge audit not present"}
    if any(str(item.get("status") or "") in {"blocked", "stale"} for item in (enforcement, assurance) if item):
        return {"status": BLOCKED, "domain": "knowledge", "summary": "knowledge audit or assurance is blocked/stale"}
    queue_summary = queue.get("summary", {}) if isinstance(queue, dict) else {}
    if int(queue_summary.get("blocking_count", 0) or 0):
        return {"status": BLOCKED, "domain": "knowledge", "summary": "knowledge review queue has blocking items"}
    if any(str(item.get("status") or "") in {"review_required", "clear_with_warnings"} for item in (enforcement, assurance) if item):
        return {"status": REVIEW_REQUIRED, "domain": "knowledge", "summary": "knowledge audit requires review or has warnings"}
    return {"status": READY, "domain": "knowledge", "summary": "knowledge evidence has no active blockers"}


def _provider_status(artifacts: dict[str, Any]) -> dict[str, Any]:
    manifest = artifacts["delivery_manifest"]
    generation = manifest.get("generation", {}) if isinstance(manifest, dict) else {}
    provider_dimension = artifacts["evaluation_scorecard"].get("provider_status", {})
    status = str(provider_dimension.get("status") or "")
    if generation.get("apply_allowed") is False or generation.get("provider_status") == "failed" or generation.get("provider_actual") == "synthetic_fallback":
        return {"status": BLOCKED, "domain": "provider", "summary": "provider policy or fallback blocks strong readiness"}
    if status == "blocked":
        return {"status": BLOCKED, "domain": "provider", "summary": "scorecard provider status is blocked"}
    if status in {"warning", "unknown", "not_provided"}:
        return {"status": REVIEW_REQUIRED, "domain": "provider", "summary": "provider-backed evidence is not proven"}
    return {"status": READY if status == "pass" else UNKNOWN, "domain": "provider", "summary": "provider status from scorecard"}


def _coverage_status(scorecard: dict[str, Any]) -> dict[str, Any]:
    coverage = scorecard.get("coverage_assurance", {}) if isinstance(scorecard, dict) else {}
    status = str(coverage.get("status") or "")
    if status == "blocked":
        return {"status": BLOCKED, "domain": "coverage", "summary": "coverage assurance is blocked"}
    if status in {"warning", "unknown", "not_provided"}:
        return {"status": REVIEW_REQUIRED, "domain": "coverage", "summary": "coverage is partial, unknown, or downgraded"}
    return {"status": READY if status == "pass" else UNKNOWN, "domain": "coverage", "summary": "coverage status from scorecard"}


def _qa_status(artifacts: dict[str, Any]) -> dict[str, Any]:
    manifest = artifacts["delivery_manifest"]
    delivery = artifacts["delivery_decision"]
    qa = manifest.get("qa", {}) if isinstance(manifest, dict) else {}
    delivery_summary = delivery.get("summary", {}) if isinstance(delivery, dict) else {}
    if str(qa.get("status") or "") in {"fail", "failed", "blocked"} or int(qa.get("blocking_count", 0) or 0):
        return {"status": BLOCKED, "domain": "qa", "summary": "delivery QA has blocking findings"}
    if int(delivery_summary.get("qa_blocking_count", 0) or 0):
        return {"status": BLOCKED, "domain": "qa", "summary": "delivery decision has blocking QA findings"}
    if str(qa.get("status") or "") in {"pass", "passed"}:
        return {"status": READY, "domain": "qa", "summary": "deterministic QA passed"}
    return {"status": UNKNOWN, "domain": "qa", "summary": "deterministic QA status is missing or unknown"}


def _delivery_matrix_status(
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    scorecard: dict[str, Any],
    signoff: dict[str, Any],
    claim: dict[str, Any],
    forbidden: set[str],
) -> str:
    if blockers:
        return BLOCKED
    if "delivery_ready" in forbidden or "production_ready" in forbidden:
        if str(scorecard.get("overall_claim") or "") in {"review_ready", "delivery_ready_with_warnings", "draft_only"}:
            return READY_WITH_WARNINGS
        return REVIEW_REQUIRED
    if signoff.get("delivery_authorized") is not True:
        return AUTHORIZATION_REQUIRED
    if claim.get("status") in {AUTHORIZATION_REQUIRED, UNKNOWN}:
        return AUTHORIZATION_REQUIRED
    if warnings:
        return READY_WITH_WARNINGS
    return READY


def _apply_matrix_status(blockers: list[dict[str, Any]], warnings: list[dict[str, Any]], scorecard: dict[str, Any], signoff: dict[str, Any], delivery_status: str, forbidden: set[str]) -> str:
    if blockers or delivery_status in {BLOCKED, STALE, PARTIAL}:
        return BLOCKED
    if "apply_ready" in forbidden:
        return BLOCKED
    if signoff.get("apply_authorized") is not True:
        return AUTHORIZATION_REQUIRED
    if str(scorecard.get("overall_claim") or "") != "apply_ready":
        return READY_WITH_WARNINGS if warnings else AUTHORIZATION_REQUIRED
    return READY_WITH_WARNINGS if warnings else READY


def _review_matrix_status(scorecard: dict[str, Any], document: dict[str, Any], knowledge: dict[str, Any], warnings: list[dict[str, Any]], forbidden: set[str]) -> str:
    if "review_complete" in forbidden or document["status"] in {BLOCKED, REVIEW_REQUIRED} or knowledge["status"] in {BLOCKED, REVIEW_REQUIRED}:
        return REVIEW_REQUIRED
    if str(scorecard.get("overall_claim") or "") in {"review_ready", "delivery_ready_with_warnings", "delivery_ready", "apply_ready"}:
        return READY_WITH_WARNINGS if warnings else READY
    return REVIEW_REQUIRED


def _add_term_gaps(gaps: list[dict[str, Any]], artifacts: dict[str, Any]) -> None:
    queue = artifacts["term_review_queue"]
    items = queue.get("items", queue.get("queue", [])) if isinstance(queue, dict) else []
    for item in items:
        if str(item.get("status") or "") in {"approved", "locked", "rejected"}:
            continue
        gaps.append(_gap("term_decision_required", "warning", "terminology_reviewer", "Term review item is unresolved.", "term-review-queue.json", related=item))


def _add_blocking_question_gaps(gaps: list[dict[str, Any]], artifacts: dict[str, Any]) -> None:
    questions = artifacts["blocking_questions"]
    for item in questions.get("questions", questions.get("blocking_questions", [])) if isinstance(questions, dict) else []:
        if str(item.get("status") or "open") in {"resolved", "accepted", "closed"}:
            continue
        gaps.append(_gap("human_review_required", "blocking", "project_owner", "Blocking question remains unresolved.", "blocking-questions.json", related=item))


def _add_human_review_gaps(gaps: list[dict[str, Any]], artifacts: dict[str, Any], matrix: dict[str, Any]) -> None:
    scorecard = artifacts["evaluation_scorecard"]
    review = scorecard.get("human_review_evidence", {}) if isinstance(scorecard, dict) else {}
    if "review_complete" in set(matrix.get("forbidden_claims", [])):
        gaps.append(_gap("human_review_required", "warning", "reviewer", "Review-complete claim is unsupported.", "evaluation-scorecard.json"))
    if str(review.get("highest_global_supported") or "not_provided") in {"not_provided", ""}:
        gaps.append(_gap("native_review_required", "warning", "native_language_reviewer", "Native/professional review evidence is not globally provided.", "human-review-evidence.jsonl"))


def _add_claim_and_signoff_gaps(gaps: list[dict[str, Any]], artifacts: dict[str, Any], matrix: dict[str, Any]) -> None:
    if matrix.get("claim_acceptance_status", {}).get("status") in {AUTHORIZATION_REQUIRED, UNKNOWN, BLOCKED, STALE}:
        gaps.append(_gap("claim_acceptance_required", "blocking", "project_owner", "Claim acceptance is missing, stale, or blocked.", "claim-acceptance-decision.json"))
    signoff_status = matrix.get("signoff_status", {})
    if signoff_status.get("status") in {AUTHORIZATION_REQUIRED, UNKNOWN, BLOCKED, STALE}:
        gaps.append(_gap("signoff_required", "blocking", "project_owner", "Delivery/apply signoff is missing, stale, or blocked.", "signoff-record.json"))
    if signoff_status.get("apply_authorized") is not True:
        gaps.append(_gap("apply_authorization_required", "blocking", "project_owner", "Apply authorization is not present.", "signoff-record.json", blocks_delivery=False))


def _add_document_gaps(gaps: list[dict[str, Any]], artifacts: dict[str, Any]) -> None:
    queue = artifacts["workbench_document_evidence_queue"]
    summary = queue.get("summary", {}) if isinstance(queue, dict) else {}
    if int(summary.get("item_count", 0) or 0):
        gaps.append(_gap("document_decision_required", "blocking" if int(summary.get("blocking_count", 0) or 0) else "warning", "document_reviewer", "Document evidence queue has unresolved items.", "workbench-document-evidence-queue.json"))
    signoff = artifacts["document_signoff_summary"]
    if signoff and str(signoff.get("status") or "") in {"requires_follow_up", "blocked", "stale"}:
        gaps.append(_gap("leadership_review_required", "blocking", "project_owner", "Document leadership review/signoff is not current.", "document-signoff-summary.json"))


def _add_knowledge_gaps(gaps: list[dict[str, Any]], artifacts: dict[str, Any]) -> None:
    enforcement = artifacts["knowledge_audit_enforcement_decision"]
    if enforcement and str(enforcement.get("status") or "") in {"blocked", "stale", "review_required"}:
        gaps.append(_gap("knowledge_review_required", "blocking", "knowledge_reviewer", "Knowledge audit enforcement is not clear.", "knowledge-audit-enforcement-decision.json"))
    queue = artifacts["workbench_knowledge_review_queue"]
    summary = queue.get("summary", {}) if isinstance(queue, dict) else {}
    if int(summary.get("blocking_count", 0) or 0):
        gaps.append(_gap("knowledge_conflict_resolution_required", "blocking", "knowledge_reviewer", "Knowledge review queue has blocking conflicts.", "workbench-knowledge-review-queue.json"))


def _add_repair_closure_gaps(gaps: list[dict[str, Any]], artifacts: dict[str, Any]) -> None:
    closure = artifacts["knowledge_repair_closure_decision"]
    if closure and str(closure.get("status") or "") not in {"closed", "closed_with_warnings", "not_applicable"}:
        gaps.append(_gap("repair_closure_recompute_required", "blocking", "runtime_operator", "Knowledge repair closure requires recompute, review, or remains blocked.", "knowledge-repair-closure-decision.json"))


def _add_artifact_refresh_gaps(gaps: list[dict[str, Any]], artifacts: dict[str, Any]) -> None:
    artifact_state = artifacts["artifact_state"]
    for item in _stale_artifacts(artifact_state)[:20]:
        gaps.append(_gap("artifact_refresh_required", "blocking" if item.get("affects_delivery_or_apply") else "warning", "runtime_operator", "Artifact is stale or blocked.", "artifact-state.json", related=item, warning_only=not bool(item.get("affects_delivery_or_apply"))))


def _add_provider_and_coverage_gaps(gaps: list[dict[str, Any]], matrix: dict[str, Any]) -> None:
    if matrix.get("provider_policy_status", {}).get("status") in {BLOCKED, REVIEW_REQUIRED, UNKNOWN}:
        gaps.append(_gap("provider_policy_resolution_required", "blocking", "runtime_operator", "Provider policy/status does not support strong readiness.", "evaluation-scorecard.json"))
    if matrix.get("coverage_status", {}).get("status") in {BLOCKED, REVIEW_REQUIRED, UNKNOWN}:
        gaps.append(_gap("coverage_confirmation_required", "warning", "project_owner", "Coverage is partial, source-only, stale, or unknown.", "evaluation-scorecard.json", blocks_apply=False, warning_only=True))


def _add_forbidden_claim_gaps(gaps: list[dict[str, Any]], matrix: dict[str, Any]) -> None:
    for claim in _strings(matrix.get("forbidden_claims")):
        gaps.append(_gap("forbidden_claim_acknowledgement_required", "warning", "project_owner", f"Forbidden claim remains unsupported: {claim}", READINESS_AUTHORIZATION_MATRIX_JSON, blocks_delivery=claim in DELIVERY_BLOCKING_CLAIMS, blocks_apply=claim in APPLY_BLOCKING_CLAIMS, warning_only=claim not in DELIVERY_BLOCKING_CLAIMS | APPLY_BLOCKING_CLAIMS))


def _forbidden_from_statuses(*statuses: dict[str, Any]) -> set[str]:
    forbidden: set[str] = set()
    for status in statuses:
        if status["status"] in {BLOCKED, STALE, PARTIAL, REVIEW_REQUIRED, UNKNOWN}:
            forbidden.update({"delivery_ready", "apply_ready", "production_ready"})
        if status.get("domain") == "provider" and status["status"] != READY:
            forbidden.add("provider_backed_quality")
        if status.get("domain") == "coverage" and status["status"] != READY:
            forbidden.add("full_coverage")
        if status.get("domain") == "knowledge" and status["status"] != READY:
            forbidden.update({"knowledge_backed_quality", "knowledge_review_complete"})
    return forbidden


def _authorization_requirements(delivery_status: str, apply_status: str, signoff: dict[str, Any], claim: dict[str, Any]) -> list[dict[str, str]]:
    requirements: list[dict[str, str]] = []
    if delivery_status in {AUTHORIZATION_REQUIRED, REVIEW_REQUIRED, READY_WITH_WARNINGS} and signoff.get("delivery_authorized") is not True:
        requirements.append({"authorization": "delivery", "required_artifact": "signoff-record.json", "reason": "delivery is not explicitly authorized"})
    if apply_status in {AUTHORIZATION_REQUIRED, BLOCKED} and signoff.get("apply_authorized") is not True:
        requirements.append({"authorization": "apply", "required_artifact": "signoff-record.json", "reason": "apply is not explicitly authorized"})
    if claim.get("status") in {AUTHORIZATION_REQUIRED, UNKNOWN, BLOCKED, STALE}:
        requirements.append({"authorization": "claim_acceptance", "required_artifact": "claim-acceptance-decision.json", "reason": "claim acceptance is missing, stale, or blocked"})
    return requirements


def _delivery_decision_blocked(decision: dict[str, Any]) -> bool:
    return bool(decision) and (decision.get("status") == "blocked" or int(decision.get("summary", {}).get("blocking_count", 0) or 0) > 0)


def _artifact_status(artifact_state: dict[str, Any], artifact_id: str) -> str:
    for item in artifact_state.get("artifacts", []) if isinstance(artifact_state, dict) else []:
        if item.get("artifact_id") == artifact_id:
            return str(item.get("status") or "")
    for key in ("stale_artifacts", "blocked_artifacts"):
        for item in artifact_state.get(key, []) if isinstance(artifact_state, dict) else []:
            if item.get("artifact_id") == artifact_id:
                return str(item.get("status") or key.removesuffix("_artifacts"))
    return ""


def _stale_artifacts(artifact_state: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(artifact_state, dict):
        return []
    return list(artifact_state.get("stale_artifacts", [])) + list(artifact_state.get("blocked_artifacts", []))


def _effective_scope(artifacts: dict[str, Any]) -> dict[str, Any]:
    signoff = artifacts.get("signoff_record", {})
    if isinstance(signoff.get("signoff_scope"), dict):
        return signoff["signoff_scope"]
    scorecard = artifacts.get("evaluation_scorecard", {})
    return {"scope_type": "full_run" if scorecard.get("overall_claim") in {"delivery_ready", "apply_ready"} else "limited"}


def _limitations(delivery_status: str, apply_status: str, forbidden: set[str], artifacts: dict[str, Any]) -> list[str]:
    limitations = [
        "readiness matrix consolidates artifacts and does not bypass scorecard, signoff, delivery, or apply gates",
        "delivery readiness and apply readiness are separate decisions",
    ]
    if delivery_status != READY:
        limitations.append("delivery is not globally production-ready")
    if apply_status != READY:
        limitations.append("apply is not authorized for unattended project mutation")
    for claim in sorted(forbidden & STRONG_CLAIMS):
        limitations.append(f"unsupported claim remains forbidden: {claim}")
    if artifacts.get("document_evidence_manifest"):
        limitations.append("document evidence existence does not imply DOCX layout verification or real-world factual truth verification")
    return limitations


def _required_signoff(matrix: dict[str, Any], scope: str) -> dict[str, Any]:
    signoff = matrix.get("signoff_status", {})
    return {
        "required": signoff.get(f"{scope}_authorized") is not True,
        "status": signoff.get("status", UNKNOWN),
        "artifact": "signoff-record.json",
    }


def _required_claim_acceptance(matrix: dict[str, Any], scope: str) -> dict[str, Any]:
    return {
        "required": scope + "_ready" in set(matrix.get("forbidden_claims", [])) or matrix.get("claim_acceptance_status", {}).get("status") != READY,
        "status": matrix.get("claim_acceptance_status", {}).get("status", UNKNOWN),
        "artifact": "claim-acceptance-decision.json",
    }


def _apply_limitations(matrix: dict[str, Any]) -> list[str]:
    limitations = ["apply requires explicit run-id confirmation and current target-file evidence"]
    if matrix.get("delivery_readiness_status") != READY:
        limitations.append("delivery readiness is not fully ready, so apply remains blocked or authorization-required")
    return limitations


def _delivery_mode(status: str, matrix: dict[str, Any]) -> str:
    if status == READY:
        return "authorized_delivery"
    if status == READY_WITH_WARNINGS:
        return "scoped_review_ready_with_warnings"
    if status == REVIEW_REQUIRED:
        return "review_package_only"
    return "draft_only_or_blocked"


def _included_artifacts(artifacts: dict[str, Any]) -> list[str]:
    names = []
    for key, value in artifacts.items():
        if value:
            names.append(key)
    return sorted(names)


def _excluded_artifacts(artifacts: dict[str, Any]) -> list[str]:
    return sorted(key for key, value in artifacts.items() if not value)


def _recommended_next_actions(blockers: list[dict[str, Any]], warnings: list[dict[str, Any]], delivery_status: str, apply_status: str) -> list[str]:
    if blockers:
        return [f"Resolve {blockers[0]['type']}: {blockers[0]['summary']}", "Refresh readiness reports after upstream evidence changes."]
    if delivery_status == AUTHORIZATION_REQUIRED or apply_status == AUTHORIZATION_REQUIRED:
        return ["Record explicit claim acceptance and signoff for the intended delivery/apply scope.", "Refresh readiness reports after authorization."]
    if warnings:
        return [f"Review warning: {warnings[0]['summary']}", "Keep limitations visible in delivery materials."]
    return ["Readiness evidence is current for the reported scope."]


def _first_next_action(matrix: dict[str, Any], fallback: str) -> str:
    actions = matrix.get("recommended_next_actions", [])
    return str(actions[0]) if actions else fallback


def _source_artifacts(state_dir: Path, delivery_dir: Path | None) -> dict[str, dict[str, str]]:
    names = [
        "evaluation-scorecard.json",
        "generation-handoff-decision.json",
        "delivery-decision.json",
        "delivery-manifest.json",
        "artifact-state.json",
        "claim-acceptance-decision.json",
        "signoff-record.json",
        "human-review-evidence.jsonl",
        "document-evidence-manifest.json",
        "document-signoff-summary.json",
        "document-claim-resolution.json",
        "knowledge-audit-enforcement-decision.json",
        "knowledge-assurance-summary.json",
        "knowledge-repair-closure-decision.json",
        "knowledge-recompute-result.json",
        "knowledge-readiness-impact-report.json",
        "repair-result.json",
        "repair-history.jsonl",
    ]
    result: dict[str, dict[str, str]] = {}
    for name in names:
        path = _first_existing(state_dir, delivery_dir, name)
        if path and path.is_file():
            result[_artifact_key(name)] = {"path": name, "sha256": sha256_file(path)}
    return result


def _gap(
    gap_type: str,
    severity: str,
    owner_role: str,
    action: str,
    artifact: str,
    *,
    related: dict[str, Any] | None = None,
    blocks_delivery: bool | None = None,
    blocks_apply: bool | None = None,
    warning_only: bool = False,
) -> dict[str, Any]:
    blocking = severity == "blocking"
    return {
        "gap_id": _stable_id("gap", [gap_type, artifact, related or action]),
        "gap_type": gap_type,
        "severity": severity,
        "owner_role": owner_role,
        "affected_scope": related.get("scope", {"scope_type": "limited"}) if isinstance(related, dict) else {"scope_type": "limited"},
        "source_artifact_references": [artifact],
        "related_queue_item": related.get("item_id") if isinstance(related, dict) else None,
        "required_decision": gap_type,
        "recommended_action": action,
        "blocks_delivery": blocking if blocks_delivery is None else blocks_delivery,
        "blocks_apply": blocking if blocks_apply is None else blocks_apply,
        "blocks_production_ready_claim": blocking,
        "warning_only": warning_only or not blocking,
    }


def _issue(issue_type: str, domain: str, summary: str, artifact: str, *, severity: str = "blocking") -> dict[str, Any]:
    return {
        "id": _stable_id("readiness", [issue_type, domain, summary, artifact]),
        "type": issue_type,
        "domain": domain,
        "severity": severity,
        "summary": summary,
        "source_artifact_references": [artifact],
    }


def _read_required(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing readiness artifact: {path}")
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _read_optional_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _read_optional_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    return read_jsonl(path)


def _first_existing(state_dir: Path, delivery_dir: Path | None, name: str) -> Path | None:
    candidates = [state_dir / name]
    if delivery_dir is not None:
        candidates.insert(0, delivery_dir / name)
    for path in candidates:
        if path.is_file():
            return path
    return candidates[-1]


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str) and value:
        return [value]
    return []


def _run_id(artifacts: dict[str, Any]) -> str | None:
    for value in artifacts.values():
        if isinstance(value, dict) and value.get("run_id"):
            return str(value.get("run_id"))
    return None


def _artifact_key(name: str) -> str:
    return name.removesuffix(".json").removesuffix(".jsonl").removesuffix(".md").replace("-", "_")


def _stable_id(prefix: str, value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return f"{prefix}-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:16]}"
