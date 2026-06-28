from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .human_review import CLAIMS, CLAIM_ACCEPTANCE_DECISION_JSON, HUMAN_REVIEW_EVIDENCE_JSONL, SIGNOFF_RECORD_JSON
from .io_utils import read_json, read_jsonl, write_json


WORKBENCH_REVIEW_QUEUE_JSON = "workbench-review-queue.json"
WORKBENCH_CLAIM_QUEUE_JSON = "workbench-claim-queue.json"
WORKBENCH_SIGNOFF_SUMMARY_JSON = "workbench-signoff-summary.json"

CLAIM_QUEUE_CLAIMS = tuple(dict.fromkeys((*CLAIMS, "draft_only")))

REVIEW_LEVEL_ITEMS = (
    ("E2_bilingual_human_spot_check", "human_review_required", "bilingual_reviewer"),
    ("E3_native_language_review", "native_review_required", "native_language_reviewer"),
    ("E4_professional_localization_review", "professional_review_required", "professional_localization_reviewer"),
)


def build_workbench_review_queue(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    artifacts = _load_artifacts(state_dir)
    scorecard = artifacts["evaluation_scorecard"]
    artifact_state = artifacts["artifact_state"]
    items: list[dict[str, Any]] = []
    items.extend(_review_level_items(scorecard, artifact_state))
    items.extend(_stale_review_items(artifact_state))
    items.extend(_claim_review_items(artifacts))
    items.extend(_repair_items(artifacts))
    items.extend(_handoff_items(artifacts))
    items.extend(_forbidden_claim_items(artifacts))
    items.extend(_authorization_items(artifacts))
    items = _dedupe_items(items)
    queue = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-review-queue-v1",
        "artifact": WORKBENCH_REVIEW_QUEUE_JSON,
        "status": "requires_action" if items else "empty",
        "summary": {
            "item_count": len(items),
            "blocking_count": sum(item["severity"] == "blocking" for item in items),
            "requires_human_confirmation_count": sum(bool(item.get("human_confirmation_required")) for item in items),
            "stale_item_count": sum(bool(item.get("stale_evidence_involved")) for item in items),
        },
        "items": items,
        "source_artifacts": _source_artifacts(state_dir),
    }
    if write:
        write_json(state_dir / WORKBENCH_REVIEW_QUEUE_JSON, queue)
    return queue


def read_workbench_review_queue(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKBENCH_REVIEW_QUEUE_JSON)


def build_workbench_claim_queue(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    artifacts = _load_artifacts(state_dir)
    scorecard = artifacts["evaluation_scorecard"]
    claim_decision = artifacts["claim_acceptance_decision"]
    forbidden = _forbidden_claims(artifacts)
    accepted = set(claim_decision.get("accepted_claims", []))
    limited = set(claim_decision.get("accepted_with_limitations", []))
    rejected = set(claim_decision.get("rejected_claims", []))
    items = [_claim_item(claim, scorecard, forbidden, accepted, limited, rejected) for claim in CLAIM_QUEUE_CLAIMS]
    queue = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-claim-queue-v1",
        "artifact": WORKBENCH_CLAIM_QUEUE_JSON,
        "status": "requires_action" if any(item["current_status"] in {"blocked", "rejected", "not_accepted"} for item in items) else "ready",
        "summary": {
            "claim_count": len(items),
            "acceptable_count": sum(bool(item["can_be_accepted"]) for item in items),
            "blocked_count": sum(item["current_status"] == "blocked" for item in items),
            "limited_scope_possible_count": sum(bool(item["limited_scope_acceptance_possible"]) for item in items),
            "forbidden_claim_count": len(forbidden),
        },
        "claims": items,
        "source_artifacts": _source_artifacts(state_dir),
    }
    if write:
        write_json(state_dir / WORKBENCH_CLAIM_QUEUE_JSON, queue)
    return queue


def read_workbench_claim_queue(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKBENCH_CLAIM_QUEUE_JSON)


def build_workbench_signoff_summary(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    artifacts = _load_artifacts(state_dir)
    scorecard = artifacts["evaluation_scorecard"]
    claim_decision = artifacts["claim_acceptance_decision"]
    signoff = artifacts["signoff_record"]
    artifact_state = artifacts["artifact_state"]
    forbidden = _forbidden_claims(artifacts)
    stale_signoff = _artifact_status(artifact_state, "signoff_record") in {"stale", "superseded", "blocked"}
    scorecard_blocked = str(scorecard.get("overall_claim") or "") == "blocked" or _dimension_blocked(scorecard)
    delivery_authorized = bool(signoff.get("delivery_authorized")) and not stale_signoff and not scorecard_blocked and "delivery_ready" not in forbidden
    apply_authorized = bool(signoff.get("apply_authorized")) and not stale_signoff and not scorecard_blocked and "apply_ready" not in forbidden
    warnings: list[str] = []
    if stale_signoff:
        warnings.append("signoff is stale, superseded, or blocked in artifact-state")
    if scorecard_blocked:
        warnings.append("evaluation scorecard is blocked")
    if "delivery_ready" in forbidden:
        warnings.append("delivery_ready remains forbidden")
    if "apply_ready" in forbidden:
        warnings.append("apply_ready remains forbidden")
    status = "not_provided" if not signoff else "blocked" if scorecard_blocked or stale_signoff else str(signoff.get("status") or "not_checked")
    summary = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-signoff-summary-v1",
        "artifact": WORKBENCH_SIGNOFF_SUMMARY_JSON,
        "current_signoff_status": status,
        "signer_role": signoff.get("signed_role"),
        "accepted_claims": claim_decision.get("accepted_claims", []),
        "rejected_claims": claim_decision.get("rejected_claims", []),
        "forbidden_claims_remaining": sorted(forbidden),
        "delivery_authorized": delivery_authorized,
        "apply_authorized": apply_authorized,
        "effective_scope": signoff.get("signoff_scope") if isinstance(signoff.get("signoff_scope"), dict) else {},
        "limitations": _signoff_limitations(signoff, claim_decision, warnings),
        "stale_or_superseded_signoff_warnings": warnings,
        "next_action": _signoff_next_action(status, delivery_authorized, apply_authorized, forbidden, warnings),
        "source_artifacts": _source_artifacts(state_dir),
    }
    if write:
        write_json(state_dir / WORKBENCH_SIGNOFF_SUMMARY_JSON, summary)
    return summary


def read_workbench_signoff_summary(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKBENCH_SIGNOFF_SUMMARY_JSON)


def workbench_queue_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "workbench_review_queue": WORKBENCH_REVIEW_QUEUE_JSON,
        "workbench_claim_queue": WORKBENCH_CLAIM_QUEUE_JSON,
        "workbench_signoff_summary": WORKBENCH_SIGNOFF_SUMMARY_JSON,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def _review_level_items(scorecard: dict[str, Any], artifact_state: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = scorecard.get("evidence_level", {})
    levels = evidence.get("levels", {}) if isinstance(evidence, dict) else {}
    review_dimension = scorecard.get("review_readiness", {})
    review_needs_action = review_dimension.get("status") != "pass" or "review_complete" in set(scorecard.get("forbidden_claims", []))
    if not review_needs_action:
        return []
    items: list[dict[str, Any]] = []
    stale = _artifact_status(artifact_state, "human_review_evidence") in {"stale", "superseded", "blocked"}
    for level, item_type, owner in REVIEW_LEVEL_ITEMS:
        if levels.get(level, {}).get("status") == "provided":
            continue
        severity = "blocking" if level == "E2_bilingual_human_spot_check" and "review_complete" in set(scorecard.get("forbidden_claims", [])) else "warning"
        items.append(
            _item(
                item_type,
                severity,
                "open",
                owner,
                ["evaluation-scorecard.json", HUMAN_REVIEW_EVIDENCE_JSONL],
                evidence_level_impact=[level],
                forbidden_claims_affected=["review_complete", "production_ready"],
                recommended_action=f"Record explicit {owner} evidence for {level}.",
                human_confirmation_required=True,
                stale_evidence_involved=stale,
            )
        )
    return items


def _stale_review_items(artifact_state: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for artifact_id, artifact_name in (
        ("human_review_evidence", HUMAN_REVIEW_EVIDENCE_JSONL),
        ("claim_acceptance_decision", CLAIM_ACCEPTANCE_DECISION_JSON),
        ("signoff_record", SIGNOFF_RECORD_JSON),
    ):
        status = _artifact_status(artifact_state, artifact_id)
        if status in {"stale", "superseded", "blocked"}:
            items.append(
                _item(
                    "stale_review_evidence",
                    "blocking",
                    "open",
                    "project_owner",
                    ["artifact-state.json", artifact_name],
                    recommended_action=f"Refresh {artifact_name} before using it for readiness claims.",
                    human_confirmation_required=True,
                    stale_evidence_involved=True,
                )
            )
    return items


def _claim_review_items(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    claim_decision = artifacts["claim_acceptance_decision"]
    if claim_decision.get("status") in {"accepted", "accepted_with_limitations"}:
        return []
    return [
        _item(
            "claim_acceptance_required",
            "blocking" if claim_decision.get("status") == "blocked" else "warning",
            "open",
            "project_owner",
            ["evaluation-scorecard.json", CLAIM_ACCEPTANCE_DECISION_JSON],
            forbidden_claims_affected=_forbidden_claims(artifacts),
            recommended_action="Accept only scorecard-supported claims or resolve forbidden claims.",
            human_confirmation_required=True,
        )
    ]


def _repair_items(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    repair_request = artifacts["repair_request"]
    repair_result = artifacts["repair_result"]
    request_items = repair_request.get("requests", []) if isinstance(repair_request, dict) else []
    summary = repair_result.get("summary", {}) if isinstance(repair_result, dict) else {}
    pending_count = (
        int(summary.get("pending_required_repair_count", 0) or 0)
        + int(summary.get("pending_provider_or_model_repair_count", 0) or 0)
        + int(summary.get("pending_human_count", 0) or 0)
    )
    if not request_items and not pending_count:
        return []
    affected = [str(item.get("segment_id")) for item in request_items if item.get("segment_id")]
    return [
        _item(
            "pending_repair",
            "blocking",
            "open",
            "developer",
            ["repair-request.json", "repair-result.json"],
            affected_segment_ids=affected,
            forbidden_claims_affected=["delivery_ready", "apply_ready", "production_ready"],
            recommended_action="Complete deterministic repairs, provider/model repairs, or required human repair confirmation.",
            human_confirmation_required=any(bool(item.get("human_confirmation_required")) for item in request_items),
        )
    ]


def _handoff_items(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    handoff = artifacts["generation_handoff_decision"]
    scorecard = artifacts["evaluation_scorecard"]
    handoff_dimension = scorecard.get("handoff_readiness", {})
    if handoff.get("status") != "blocked" and handoff_dimension.get("status") != "blocked":
        return []
    return [
        _item(
            "blocked_handoff",
            "blocking",
            "open",
            "developer",
            ["generation-handoff-decision.json", "evaluation-scorecard.json"],
            forbidden_claims_affected=["delivery_ready", "apply_ready", "production_ready"],
            recommended_action="Resolve handoff blockers before claiming generation, delivery, or apply readiness.",
            human_confirmation_required=False,
        )
    ]


def _forbidden_claim_items(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _item(
            "forbidden_claim_remaining",
            "blocking" if claim in {"delivery_ready", "apply_ready", "production_ready"} else "warning",
            "open",
            "project_owner",
            ["evaluation-scorecard.json", CLAIM_ACCEPTANCE_DECISION_JSON],
            forbidden_claims_affected=[claim],
            recommended_action=f"Do not claim {claim}; collect or refresh supporting evidence first.",
            human_confirmation_required=claim in {"delivery_ready", "apply_ready", "production_ready"},
        )
        for claim in _forbidden_claims(artifacts)
    ]


def _authorization_items(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    scorecard = artifacts["evaluation_scorecard"]
    signoff = artifacts["signoff_record"]
    forbidden = set(_forbidden_claims(artifacts))
    overall = str(scorecard.get("overall_claim") or "")
    items: list[dict[str, Any]] = []
    if overall in {"delivery_ready", "delivery_ready_with_warnings", "apply_ready"} and "delivery_ready" not in forbidden and signoff.get("delivery_authorized") is not True:
        items.append(
            _item(
                "delivery_authorization_required",
                "warning",
                "open",
                "project_owner",
                ["signoff-record.json", "evaluation-scorecard.json"],
                recommended_action="Record project-owner delivery signoff for the supported scope.",
                human_confirmation_required=True,
            )
        )
    if overall == "apply_ready" and "apply_ready" not in forbidden and signoff.get("apply_authorized") is not True:
        items.append(
            _item(
                "apply_authorization_required",
                "blocking",
                "open",
                "project_owner",
                ["signoff-record.json", "evaluation-scorecard.json"],
                recommended_action="Record project-owner apply signoff before writing source-project files.",
                human_confirmation_required=True,
            )
        )
    if not signoff:
        items.append(
            _item(
                "signoff_required",
                "warning",
                "open",
                "project_owner",
                ["signoff-record.json", "claim-acceptance-decision.json"],
                recommended_action="Record signoff after claim acceptance is current.",
                human_confirmation_required=True,
            )
        )
    return items


def _claim_item(
    claim: str,
    scorecard: dict[str, Any],
    forbidden: set[str],
    accepted: set[str],
    limited: set[str],
    rejected: set[str],
) -> dict[str, Any]:
    overall = str(scorecard.get("overall_claim") or "not_ready")
    status = "accepted" if claim in accepted else "accepted_with_limitations" if claim in limited else "blocked" if claim in forbidden else "rejected" if claim in rejected else "not_accepted"
    can_accept = claim not in forbidden and _scorecard_supports_claim(claim, overall)
    limited_possible = claim == "limited_scope_delivery_ready" and overall == "delivery_ready_with_warnings"
    if claim == "draft_only" and overall == "draft_only":
        can_accept = True
    return {
        "claim": claim,
        "current_status": status,
        "supporting_evidence": _supporting_evidence(scorecard, claim),
        "blocking_evidence": _blocking_evidence(scorecard, claim, forbidden),
        "related_forbidden_claim": claim if claim in forbidden else None,
        "can_be_accepted": can_accept,
        "limited_scope_acceptance_possible": limited_possible,
        "recommended_next_action": _claim_next_action(claim, status, can_accept, limited_possible),
        "risk_if_accepted": _claim_risk(claim, status, forbidden),
    }


def _scorecard_supports_claim(claim: str, overall: str) -> bool:
    if claim == "draft_only":
        return overall == "draft_only"
    if claim == "review_ready":
        return overall in {"review_ready", "delivery_ready_with_warnings", "delivery_ready", "apply_ready"}
    if claim == "delivery_ready":
        return overall in {"delivery_ready", "apply_ready"}
    if claim == "apply_ready":
        return overall == "apply_ready"
    if claim == "limited_scope_delivery_ready":
        return overall == "delivery_ready_with_warnings"
    if claim == "production_ready":
        return overall == "apply_ready"
    return overall not in {"blocked", "not_ready", "draft_only"}


def _supporting_evidence(scorecard: dict[str, Any], claim: str) -> list[str]:
    support: list[str] = []
    for name in ("structural_qa", "terminology_assurance", "coverage_assurance", "review_readiness", "delivery_readiness", "apply_readiness"):
        dimension = scorecard.get(name, {})
        if isinstance(dimension, dict) and dimension.get("status") == "pass":
            support.append(name)
    if claim in {"review_complete", "review_ready"} and scorecard.get("human_review_evidence", {}).get("global_supported_levels"):
        support.append("human_review_evidence")
    return support


def _blocking_evidence(scorecard: dict[str, Any], claim: str, forbidden: set[str]) -> list[str]:
    evidence: list[str] = []
    if claim in forbidden:
        evidence.append("evaluation_scorecard.forbidden_claims")
    for name, dimension in scorecard.get("dimensions", {}).items():
        if isinstance(dimension, dict) and dimension.get("status") == "blocked":
            evidence.append(f"dimensions.{name}")
    for name in ("provider_status", "coverage_assurance", "terminology_assurance", "review_readiness", "delivery_readiness", "apply_readiness"):
        dimension = scorecard.get(name, {})
        if isinstance(dimension, dict) and dimension.get("status") in {"blocked", "warning", "not_provided", "unknown"}:
            evidence.append(name)
    return list(dict.fromkeys(evidence))


def _claim_next_action(claim: str, status: str, can_accept: bool, limited_possible: bool) -> str:
    if status in {"accepted", "accepted_with_limitations"}:
        return "No action; claim decision is already recorded."
    if can_accept:
        return f"Accept {claim} through claim-acceptance if the project owner agrees."
    if limited_possible:
        return "Accept only limited-scope delivery risk, with limitations preserved."
    return f"Collect or refresh evidence before accepting {claim}."


def _claim_risk(claim: str, status: str, forbidden: set[str]) -> str:
    if claim in forbidden:
        return "unsupported_by_current_evidence"
    if status == "accepted_with_limitations":
        return "limited_scope_must_remain_visible"
    if claim in {"delivery_ready", "apply_ready", "production_ready"}:
        return "high_if_evidence_changes_or_is_stale"
    return "normal_review_risk"


def _signoff_limitations(signoff: dict[str, Any], claim_decision: dict[str, Any], warnings: list[str]) -> list[str]:
    limitations: list[str] = []
    if signoff.get("limitations_accepted"):
        limitations.append("project owner accepted explicit limitations")
    limitations.extend(str(item) for item in claim_decision.get("accepted_with_limitations", []) if item)
    limitations.extend(warnings)
    return list(dict.fromkeys(limitations))


def _signoff_next_action(status: str, delivery_authorized: bool, apply_authorized: bool, forbidden: set[str], warnings: list[str]) -> str:
    if warnings:
        return "Refresh evidence and regenerate signoff summary before delivery or apply."
    if not delivery_authorized and "delivery_ready" not in forbidden:
        return "Record delivery signoff for the accepted scope."
    if not apply_authorized and "apply_ready" not in forbidden:
        return "Record apply signoff before writing source-project files."
    if forbidden:
        return "Resolve remaining forbidden claims before stronger readiness claims."
    return "No signoff action required."


def _load_artifacts(state_dir: Path) -> dict[str, Any]:
    return {
        "human_review_evidence": _read_jsonl(state_dir / HUMAN_REVIEW_EVIDENCE_JSONL),
        "claim_acceptance_decision": _read_json_object(state_dir / CLAIM_ACCEPTANCE_DECISION_JSON),
        "signoff_record": _read_json_object(state_dir / SIGNOFF_RECORD_JSON),
        "evaluation_scorecard": _read_json_object(state_dir / "evaluation-scorecard.json"),
        "blocking_questions": _read_json_object(state_dir / "blocking-questions.json"),
        "generation_handoff_decision": _read_json_object(state_dir / "generation-handoff-decision.json"),
        "repair_request": _read_json_object(state_dir / "repair-request.json"),
        "repair_result": _read_json_object(state_dir / "repair-result.json"),
        "artifact_state": _read_json_object(state_dir / "artifact-state.json"),
        "delivery_decision": _read_json_object(state_dir / "delivery-decision.json"),
    }


def _source_artifacts(state_dir: Path) -> dict[str, str]:
    names = (
        HUMAN_REVIEW_EVIDENCE_JSONL,
        CLAIM_ACCEPTANCE_DECISION_JSON,
        SIGNOFF_RECORD_JSON,
        "evaluation-scorecard.json",
        "evidence-level-report.md",
        "blocking-questions.json",
        "generation-handoff-decision.json",
        "repair-request.json",
        "repair-result.json",
        "artifact-state.json",
        "delivery-decision.json",
    )
    return {Path(name).stem.replace("-", "_"): name for name in names if (state_dir / name).is_file()}


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [item for item in read_jsonl(path) if isinstance(item, dict)]


def _forbidden_claims(artifacts: dict[str, Any]) -> set[str]:
    scorecard = artifacts["evaluation_scorecard"]
    claim_decision = artifacts["claim_acceptance_decision"]
    signoff = artifacts["signoff_record"]
    claims = set(str(claim) for claim in scorecard.get("forbidden_claims", []) if claim)
    claims.update(str(claim) for claim in claim_decision.get("forbidden_claims_remaining", []) if claim)
    claims.update(str(claim) for claim in signoff.get("forbidden_claims_remaining", []) if claim)
    return claims


def _artifact_status(artifact_state: dict[str, Any], artifact_id: str) -> str:
    for item in artifact_state.get("artifacts", []) if isinstance(artifact_state, dict) else []:
        if item.get("artifact_id") == artifact_id:
            return str(item.get("status") or "")
    return ""


def _dimension_blocked(scorecard: dict[str, Any]) -> bool:
    for value in scorecard.get("dimensions", {}).values():
        if isinstance(value, dict) and value.get("status") == "blocked":
            return True
    for name in ("structural_qa", "provider_status", "handoff_readiness", "repair_readiness", "delivery_readiness", "apply_readiness"):
        value = scorecard.get(name, {})
        if isinstance(value, dict) and value.get("status") == "blocked":
            return True
    return False


def _item(
    item_type: str,
    severity: str,
    status: str,
    owner_role: str,
    source_artifact_references: list[str],
    *,
    affected_segment_ids: list[str] | None = None,
    affected_scope: dict[str, Any] | None = None,
    evidence_level_impact: list[str] | None = None,
    forbidden_claims_affected: list[str] | None = None,
    recommended_action: str,
    human_confirmation_required: bool,
    stale_evidence_involved: bool = False,
) -> dict[str, Any]:
    payload = {
        "item_type": item_type,
        "source_artifact_references": sorted(source_artifact_references),
        "affected_segment_ids": sorted(affected_segment_ids or []),
        "affected_scope": affected_scope or {},
        "forbidden_claims_affected": sorted(set(forbidden_claims_affected or [])),
    }
    return {
        "item_id": _stable_id("workbench-review", payload),
        "item_type": item_type,
        "severity": severity,
        "status": status,
        "owner_role": owner_role,
        "source_artifact_references": payload["source_artifact_references"],
        "affected_segment_ids": payload["affected_segment_ids"],
        "affected_scope": payload["affected_scope"],
        "evidence_level_impact": evidence_level_impact or [],
        "forbidden_claims_affected": payload["forbidden_claims_affected"],
        "recommended_action": recommended_action,
        "human_confirmation_required": human_confirmation_required,
        "stale_evidence_involved": stale_evidence_involved,
    }


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        item_id = str(item.get("item_id"))
        if item_id in seen:
            continue
        seen.add(item_id)
        deduped.append(item)
    return sorted(deduped, key=lambda item: (str(item.get("severity")), str(item.get("item_type")), str(item.get("item_id"))))


def _stable_id(prefix: str, value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:24]}"
