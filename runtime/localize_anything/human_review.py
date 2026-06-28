from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json, write_jsonl


HUMAN_REVIEW_EVIDENCE_JSONL = "human-review-evidence.jsonl"
CLAIM_ACCEPTANCE_DECISION_JSON = "claim-acceptance-decision.json"
SIGNOFF_RECORD_JSON = "signoff-record.json"

E2 = "E2_bilingual_human_spot_check"
E3 = "E3_native_language_review"
E4 = "E4_professional_localization_review"
HUMAN_EVIDENCE_LEVELS = (E2, E3, E4)

REVIEW_ROLES = {
    "project_owner": (),
    "bilingual_reviewer": (E2,),
    "native_language_reviewer": (E3,),
    "professional_localization_reviewer": (E4,),
}
CURRENT_REVIEW_STATUSES = {"accepted", "accepted_with_limitations"}
TERMINAL_REVIEW_STATUSES = CURRENT_REVIEW_STATUSES | {"rejected", "stale", "superseded", "requires_follow_up"}
CLAIMS = (
    "full_coverage",
    "provider_backed_quality",
    "full_terminology_assurance",
    "review_complete",
    "review_ready",
    "delivery_ready",
    "delivery_ready_with_warnings",
    "limited_scope_delivery_ready",
    "apply_ready",
    "production_ready",
)


def read_human_review_evidence(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / HUMAN_REVIEW_EVIDENCE_JSONL
    return read_jsonl(path) if path.is_file() else []


def record_human_review_evidence(
    state_dir: Path,
    evidence: dict[str, Any],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    record = _normalize_human_review_evidence(evidence, run_id=run_id)
    records = read_human_review_evidence(state_dir)
    records.append(record)
    write_jsonl(state_dir / HUMAN_REVIEW_EVIDENCE_JSONL, records)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-human-review-evidence-record-v1",
        "artifact": HUMAN_REVIEW_EVIDENCE_JSONL,
        "record": record,
        "summary": summarize_human_review_evidence(records),
    }


def human_review_summary(state_dir: Path) -> dict[str, Any]:
    return summarize_human_review_evidence(read_human_review_evidence(state_dir))


def summarize_human_review_evidence(records: list[dict[str, Any]]) -> dict[str, Any]:
    valid: list[dict[str, Any]] = []
    limited: list[dict[str, Any]] = []
    rejected_or_followup: list[dict[str, Any]] = []
    stale_or_superseded: list[dict[str, Any]] = []
    global_levels: set[str] = set()
    limited_levels: set[str] = set()
    for record in records:
        status = str(record.get("status") or "")
        if status in {"stale", "superseded"}:
            stale_or_superseded.append(record)
            continue
        if status in {"rejected", "requires_follow_up"}:
            rejected_or_followup.append(record)
            continue
        levels = [level for level in record.get("effective_evidence_levels", []) if level in HUMAN_EVIDENCE_LEVELS]
        if status not in CURRENT_REVIEW_STATUSES or not levels:
            continue
        scope = record.get("review_scope", {}) if isinstance(record.get("review_scope"), dict) else {}
        scope_type = str(scope.get("scope_type") or "limited")
        if scope_type == "full_run":
            global_levels.update(levels)
            valid.append(record)
        else:
            limited_levels.update(levels)
            limited.append(record)
    return {
        "status": "provided"
        if global_levels
        else "limited_scope"
        if limited_levels
        else "requires_follow_up"
        if rejected_or_followup
        else "stale"
        if stale_or_superseded
        else "not_provided",
        "artifact": HUMAN_REVIEW_EVIDENCE_JSONL,
        "record_count": len(records),
        "valid_global_review_count": len(valid),
        "valid_limited_review_count": len(limited),
        "rejected_or_followup_count": len(rejected_or_followup),
        "stale_or_superseded_count": len(stale_or_superseded),
        "global_supported_levels": _ordered_levels(global_levels),
        "limited_supported_levels": _ordered_levels(limited_levels),
        "highest_global_supported": _highest_level(global_levels),
        "highest_limited_supported": _highest_level(limited_levels),
        "review_evidence_ids": [str(item.get("evidence_id")) for item in valid if item.get("evidence_id")],
        "limited_review_evidence_ids": [str(item.get("evidence_id")) for item in limited if item.get("evidence_id")],
    }


def read_claim_acceptance_decision(state_dir: Path) -> dict[str, Any]:
    path = state_dir / CLAIM_ACCEPTANCE_DECISION_JSON
    if not path.is_file():
        raise ValueError(f"Missing claim acceptance decision: {path}")
    return read_json(path)


def build_claim_acceptance_decision(
    state_dir: Path,
    *,
    requested_claims: list[str] | None = None,
    accepted_risk: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    scorecard = _read_optional_json(state_dir / "evaluation-scorecard.json")
    review = human_review_summary(state_dir)
    claims = _requested_claims(requested_claims)
    forbidden = set(scorecard.get("forbidden_claims", [])) if isinstance(scorecard, dict) else set()
    overall = str(scorecard.get("overall_claim") or "not_ready")
    accepted_risk = accepted_risk or {}
    accepts_limitations = bool(accepted_risk.get("accepts_limitations") or accepted_risk.get("accepts_partial_or_limited_scope"))
    decisions = [
        _claim_decision(claim, forbidden, overall, review, accepts_limitations)
        for claim in claims
    ]
    accepted = [item["claim"] for item in decisions if item["status"] == "accepted"]
    limited = [item["claim"] for item in decisions if item["status"] == "accepted_with_limitations"]
    rejected = [item["claim"] for item in decisions if item["status"] in {"rejected", "blocked"}]
    status = "blocked" if rejected else "accepted_with_limitations" if limited else "accepted"
    decision = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-claim-acceptance-decision-v1",
        "run_id": run_id or scorecard.get("run_id"),
        "status": status,
        "artifact": CLAIM_ACCEPTANCE_DECISION_JSON,
        "scorecard_artifact": "evaluation-scorecard.json" if scorecard else None,
        "human_review_artifact": HUMAN_REVIEW_EVIDENCE_JSONL if (state_dir / HUMAN_REVIEW_EVIDENCE_JSONL).is_file() else None,
        "requested_claims": claims,
        "accepted_claims": accepted,
        "accepted_with_limitations": limited,
        "rejected_claims": rejected,
        "forbidden_claims_remaining": sorted(forbidden | set(rejected)),
        "claim_decisions": decisions,
        "accepted_risk": accepted_risk,
        "human_review_summary": review,
        "summary": {
            "requested_count": len(claims),
            "accepted_count": len(accepted),
            "accepted_with_limitations_count": len(limited),
            "rejected_count": len(rejected),
            "forbidden_remaining_count": len(forbidden | set(rejected)),
        },
    }
    if write:
        write_json(state_dir / CLAIM_ACCEPTANCE_DECISION_JSON, decision)
    return decision


def read_signoff_record(state_dir: Path) -> dict[str, Any]:
    path = state_dir / SIGNOFF_RECORD_JSON
    if not path.is_file():
        raise ValueError(f"Missing signoff record: {path}")
    return read_json(path)


def create_signoff_record(
    state_dir: Path,
    signoff: dict[str, Any],
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    if not str(signoff.get("signed_by") or "").strip():
        raise ValueError("signed_by is required")
    scorecard = _read_optional_json(state_dir / "evaluation-scorecard.json")
    claim_decision = _read_optional_json(state_dir / CLAIM_ACCEPTANCE_DECISION_JSON)
    artifact_state = _read_optional_json(state_dir / "artifact-state.json")
    requested = _authorization_requests(signoff)
    forbidden = set(scorecard.get("forbidden_claims", [])) if scorecard else set()
    overall = str(scorecard.get("overall_claim") or "not_ready")
    claim_status = str(claim_decision.get("status") or "missing")
    stale_state = str(artifact_state.get("status") or "") in {"stale", "blocked"} if artifact_state else False
    limitations_accepted = bool(signoff.get("limitations_accepted") or signoff.get("risk_accepted"))
    blocked: list[dict[str, str]] = []
    delivery_authorized = False
    apply_authorized = False
    if requested.get("delivery"):
        delivery_authorized = _delivery_authorized(overall, forbidden, claim_status, limitations_accepted, stale_state)
        if not delivery_authorized:
            blocked.append({"authorization": "delivery", "reason": _delivery_block_reason(overall, forbidden, claim_status, stale_state)})
    if requested.get("apply"):
        apply_authorized = overall == "apply_ready" and "apply_ready" not in forbidden and claim_status != "blocked" and not stale_state
        if not apply_authorized:
            blocked.append({"authorization": "apply", "reason": _apply_block_reason(overall, forbidden, claim_status, stale_state)})
    status = "requires_follow_up" if blocked else "accepted_with_limitations" if limitations_accepted else "accepted"
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-signoff-record-v1",
        "run_id": run_id or scorecard.get("run_id") or claim_decision.get("run_id"),
        "signoff_id": str(signoff.get("signoff_id") or _stable_id("signoff", signoff)[:24]),
        "status": status,
        "artifact": SIGNOFF_RECORD_JSON,
        "signed_by": str(signoff["signed_by"]).strip(),
        "signed_role": str(signoff.get("signed_role") or "project_owner"),
        "signed_at": signoff.get("signed_at") or _now(),
        "signoff_scope": signoff.get("signoff_scope") if isinstance(signoff.get("signoff_scope"), dict) else {"scope_type": "limited"},
        "requested_authorizations": requested,
        "delivery_authorized": delivery_authorized,
        "apply_authorized": apply_authorized,
        "limitations_accepted": limitations_accepted,
        "accepted_claims": claim_decision.get("accepted_claims", []),
        "accepted_with_limitations": claim_decision.get("accepted_with_limitations", []),
        "rejected_claims": claim_decision.get("rejected_claims", []),
        "forbidden_claims_remaining": sorted(forbidden | set(claim_decision.get("forbidden_claims_remaining", []))),
        "blocked_authorizations": blocked,
        "source_artifacts": {
            "evaluation_scorecard": "evaluation-scorecard.json" if scorecard else None,
            "claim_acceptance_decision": CLAIM_ACCEPTANCE_DECISION_JSON if claim_decision else None,
            "artifact_state": "artifact-state.json" if artifact_state else None,
        },
    }
    if write:
        write_json(state_dir / SIGNOFF_RECORD_JSON, record)
    return record


def signoff_summary(state_dir: Path) -> dict[str, Any]:
    path = state_dir / SIGNOFF_RECORD_JSON
    if not path.is_file():
        return {"status": "not_provided", "artifact": None, "delivery_authorized": False, "apply_authorized": False}
    return summarize_signoff_record(read_json(path))


def summarize_signoff_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": record.get("status", "not_checked"),
        "artifact": SIGNOFF_RECORD_JSON,
        "delivery_authorized": bool(record.get("delivery_authorized")),
        "apply_authorized": bool(record.get("apply_authorized")),
        "limitations_accepted": bool(record.get("limitations_accepted")),
        "blocked_authorizations": record.get("blocked_authorizations", []),
        "forbidden_claims_remaining": record.get("forbidden_claims_remaining", []),
    }


def human_review_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "human_review_evidence": HUMAN_REVIEW_EVIDENCE_JSONL,
        "claim_acceptance_decision": CLAIM_ACCEPTANCE_DECISION_JSON,
        "signoff_record": SIGNOFF_RECORD_JSON,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def _normalize_human_review_evidence(evidence: dict[str, Any], *, run_id: str | None) -> dict[str, Any]:
    role = str(evidence.get("reviewer_role") or "").strip()
    if role not in REVIEW_ROLES:
        raise ValueError(f"reviewer_role must be one of: {', '.join(sorted(REVIEW_ROLES))}")
    status = str(evidence.get("status") or "accepted").strip()
    if status not in TERMINAL_REVIEW_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(TERMINAL_REVIEW_STATUSES))}")
    requested_levels = _requested_levels(evidence, role)
    effective_levels = [level for level in requested_levels if level in REVIEW_ROLES[role]]
    scope = evidence.get("review_scope") if isinstance(evidence.get("review_scope"), dict) else {"scope_type": "limited"}
    record = dict(evidence)
    record.update(
        {
            "protocol_version": PROTOCOL_VERSION,
            "schema": "localize-anything-human-review-evidence-v1",
            "run_id": run_id or evidence.get("run_id"),
            "evidence_id": str(evidence.get("evidence_id") or _stable_id("human-review", evidence)[:24]),
            "reviewer_role": role,
            "status": status,
            "review_scope": scope,
            "supports_evidence_levels": requested_levels,
            "effective_evidence_levels": effective_levels,
            "recorded_at": evidence.get("recorded_at") or _now(),
        }
    )
    return record


def _requested_levels(evidence: dict[str, Any], role: str) -> list[str]:
    value = evidence.get("supports_evidence_levels")
    if value is None:
        value = evidence.get("evidence_levels")
    if value is None and evidence.get("evidence_level"):
        value = [evidence["evidence_level"]]
    if value is None:
        value = list(REVIEW_ROLES[role])
    if not isinstance(value, list):
        raise ValueError("supports_evidence_levels must be a list")
    return [str(level) for level in value if str(level) in HUMAN_EVIDENCE_LEVELS]


def _claim_decision(
    claim: str,
    forbidden: set[str],
    overall: str,
    review: dict[str, Any],
    accepts_limitations: bool,
) -> dict[str, Any]:
    if claim in forbidden:
        return {"claim": claim, "status": "blocked", "reason": "unsupported_by_evaluation_scorecard"}
    if claim == "review_complete" and not review.get("global_supported_levels"):
        return {"claim": claim, "status": "rejected", "reason": "global_human_review_evidence_missing"}
    if claim == "production_ready" and overall != "apply_ready":
        return {"claim": claim, "status": "rejected", "reason": "production_ready_requires_apply_ready"}
    if claim == "apply_ready" and overall == "apply_ready":
        return {"claim": claim, "status": "accepted", "reason": "scorecard_supports_apply_ready"}
    if claim == "delivery_ready" and overall in {"delivery_ready", "apply_ready"}:
        return {"claim": claim, "status": "accepted", "reason": "scorecard_supports_delivery_ready"}
    if claim == "review_ready" and overall in {"review_ready", "delivery_ready_with_warnings", "delivery_ready", "apply_ready"}:
        return {"claim": claim, "status": "accepted", "reason": "scorecard_supports_review_ready"}
    if claim in {"delivery_ready_with_warnings", "limited_scope_delivery_ready"} and overall == "delivery_ready_with_warnings" and accepts_limitations:
        return {"claim": claim, "status": "accepted_with_limitations", "reason": "explicit_limitations_acceptance"}
    if claim in {"full_coverage", "provider_backed_quality", "full_terminology_assurance", "review_complete"}:
        return {"claim": claim, "status": "accepted", "reason": "scorecard_does_not_forbid_claim"}
    return {"claim": claim, "status": "rejected", "reason": f"scorecard_overall_claim_is_{overall}"}


def _requested_claims(claims: list[str] | None) -> list[str]:
    if not claims:
        return list(CLAIMS)
    cleaned = [str(claim).strip() for claim in claims if str(claim).strip()]
    unknown = sorted(set(cleaned) - set(CLAIMS))
    if unknown:
        raise ValueError(f"Unsupported claims: {', '.join(unknown)}")
    return list(dict.fromkeys(cleaned))


def _authorization_requests(signoff: dict[str, Any]) -> dict[str, bool]:
    authorizations = signoff.get("authorizations")
    if isinstance(authorizations, dict):
        return {
            "delivery": bool(authorizations.get("delivery")),
            "apply": bool(authorizations.get("apply")),
        }
    return {
        "delivery": bool(signoff.get("delivery_authorized") or signoff.get("authorize_delivery")),
        "apply": bool(signoff.get("apply_authorized") or signoff.get("authorize_apply")),
    }


def _delivery_authorized(
    overall: str,
    forbidden: set[str],
    claim_status: str,
    limitations_accepted: bool,
    stale_state: bool,
) -> bool:
    if stale_state or claim_status == "blocked" or "delivery_ready" in forbidden:
        return False
    if overall in {"delivery_ready", "apply_ready"}:
        return True
    return overall == "delivery_ready_with_warnings" and limitations_accepted


def _delivery_block_reason(overall: str, forbidden: set[str], claim_status: str, stale_state: bool) -> str:
    if stale_state:
        return "artifact_state_is_stale_or_blocked"
    if claim_status == "blocked":
        return "claim_acceptance_is_blocked"
    if "delivery_ready" in forbidden:
        return "delivery_ready_claim_is_forbidden"
    return f"scorecard_overall_claim_is_{overall}"


def _apply_block_reason(overall: str, forbidden: set[str], claim_status: str, stale_state: bool) -> str:
    if stale_state:
        return "artifact_state_is_stale_or_blocked"
    if claim_status == "blocked":
        return "claim_acceptance_is_blocked"
    if "apply_ready" in forbidden:
        return "apply_ready_claim_is_forbidden"
    return f"scorecard_overall_claim_is_{overall}"


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _ordered_levels(levels: set[str]) -> list[str]:
    return [level for level in HUMAN_EVIDENCE_LEVELS if level in levels]


def _highest_level(levels: set[str]) -> str:
    ordered = _ordered_levels(levels)
    return ordered[-1] if ordered else "not_provided"


def _stable_id(prefix: str, value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
