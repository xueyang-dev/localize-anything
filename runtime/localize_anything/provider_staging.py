from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json, write_jsonl


PROVIDER_EXECUTION_ATTEMPT_LEDGER_JSONL = "provider-execution-attempt-ledger.jsonl"
PROVIDER_EXECUTION_ATTEMPT_SUMMARY_JSON = "provider-execution-attempt-summary.json"
PROVIDER_RESULT_STAGING_ADMISSION_JSON = "provider-result-staging-admission.json"
PROVIDER_RESULT_QUARANTINE_REPORT_JSON = "provider-result-quarantine-report.json"
PROVIDER_RESULT_STAGING_MANIFEST_JSON = "provider-result-staging-manifest.json"
PROVIDER_STAGING_CLAIM_BOUNDARY_JSON = "provider-staging-claim-boundary.json"

PROVIDER_STAGING_ASSETS = {
    "provider_execution_attempt_ledger": PROVIDER_EXECUTION_ATTEMPT_LEDGER_JSONL,
    "provider_execution_attempt_summary": PROVIDER_EXECUTION_ATTEMPT_SUMMARY_JSON,
    "provider_result_staging_admission": PROVIDER_RESULT_STAGING_ADMISSION_JSON,
    "provider_result_quarantine_report": PROVIDER_RESULT_QUARANTINE_REPORT_JSON,
    "provider_result_staging_manifest": PROVIDER_RESULT_STAGING_MANIFEST_JSON,
    "provider_staging_claim_boundary": PROVIDER_STAGING_CLAIM_BOUNDARY_JSON,
}

ATTEMPT_TYPES = {
    "blocked_before_execution",
    "dry_run_only",
    "mock_execution",
    "external_result_import",
    "skipped",
    "failed_policy_check",
    "future_real_execution_placeholder",
}
RESULT_STATES = {
    "no_execution",
    "blocked",
    "success",
    "failure",
    "timeout",
    "malformed_response",
    "partial_response",
    "empty_output",
    "fallback_attempted",
    "quarantined",
}
PROVIDER_CLAIMS = {
    "provider_backed_quality",
    "provider_execution_complete",
    "provider_repair_complete",
    "model_repair_complete",
}


def build_provider_execution_attempt_ledger(state_dir: Path, *, write: bool = True) -> list[dict[str, Any]]:
    state_dir = state_dir.resolve()
    existing = _optional_jsonl(state_dir / PROVIDER_EXECUTION_ATTEMPT_LEDGER_JSONL)
    by_result = {str(item.get("result_id") or ""): item for item in existing if item.get("result_id")}
    records = [item for item in existing if not item.get("result_id")]
    authorization = _optional_json(state_dir / "provider-execution-authorization-decision.json")
    preflight = _optional_json(state_dir / "provider-execution-preflight-gate.json")
    request = _optional_json(state_dir / "provider-handoff-request.json")
    for intake in _optional_jsonl(state_dir / "provider-result-intake.jsonl"):
        result_id = str(intake.get("result_id") or "")
        record = by_result.get(result_id) or _attempt_from_intake(intake, authorization, preflight, request)
        records.append(record)
    if not records:
        records.append(_empty_attempt(authorization, preflight, request))
    records = sorted(records, key=lambda item: str(item.get("attempt_id") or ""))
    if write:
        write_jsonl(state_dir / PROVIDER_EXECUTION_ATTEMPT_LEDGER_JSONL, records)
    return records


def record_provider_execution_attempt(state_dir: Path, attempt: dict[str, Any]) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    if not isinstance(attempt, dict):
        raise ValueError("provider execution attempt must be a JSON object")
    attempt_type = str(attempt.get("attempt_type") or "")
    result_state = str(attempt.get("result_state") or "")
    if attempt_type not in ATTEMPT_TYPES:
        raise ValueError(f"attempt_type must be one of: {', '.join(sorted(ATTEMPT_TYPES))}")
    if result_state not in RESULT_STATES:
        raise ValueError(f"result_state must be one of: {', '.join(sorted(RESULT_STATES))}")
    scope = attempt.get("scope") if isinstance(attempt.get("scope"), dict) else {}
    authorization = _optional_json(state_dir / "provider-execution-authorization-decision.json")
    preflight = _optional_json(state_dir / "provider-execution-preflight-gate.json")
    identity = [attempt_type, result_state, attempt.get("result_id"), attempt.get("request_id"), scope]
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-execution-attempt-record-v1",
        "attempt_id": str(attempt.get("attempt_id") or _stable_id("provider-attempt", identity)),
        "attempt_type": attempt_type,
        "result_state": result_state,
        "result_id": str(attempt.get("result_id") or ""),
        "request_id": str(attempt.get("request_id") or ""),
        "authorization_decision_id": str(attempt.get("authorization_decision_id") or ""),
        "authorization_status": str(attempt.get("authorization_status") or authorization.get("status") or "missing"),
        "preflight_status": str(attempt.get("preflight_status") or preflight.get("status") or "missing"),
        "scope": scope,
        "provenance": attempt.get("provenance") if isinstance(attempt.get("provenance"), dict) else {},
        "limitations": _strings(attempt.get("limitations")),
        "source_artifact_references": _strings(attempt.get("source_artifact_references")),
        "provider_or_model_called_by_runtime": False,
    }
    records = _optional_jsonl(state_dir / PROVIDER_EXECUTION_ATTEMPT_LEDGER_JSONL)
    if not any(item.get("attempt_id") == record["attempt_id"] for item in records):
        records.append(record)
        write_jsonl(state_dir / PROVIDER_EXECUTION_ATTEMPT_LEDGER_JSONL, records)
    build_provider_staging_artifacts(state_dir)
    return record


def read_provider_execution_attempt_ledger(state_dir: Path) -> list[dict[str, Any]]:
    return _optional_jsonl(state_dir / PROVIDER_EXECUTION_ATTEMPT_LEDGER_JSONL)


def read_provider_execution_attempt_summary(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_EXECUTION_ATTEMPT_SUMMARY_JSON)


def read_provider_result_staging_admission(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_RESULT_STAGING_ADMISSION_JSON)


def read_provider_result_quarantine_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_RESULT_QUARANTINE_REPORT_JSON)


def read_provider_result_staging_manifest(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_RESULT_STAGING_MANIFEST_JSON)


def read_provider_staging_claim_boundary(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_STAGING_CLAIM_BOUNDARY_JSON)


def build_provider_execution_attempt_summary(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    records = build_provider_execution_attempt_ledger(state_dir, write=write)
    summary = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-execution-attempt-summary-v1",
        "artifact": PROVIDER_EXECUTION_ATTEMPT_SUMMARY_JSON,
        "status": "attempts_recorded" if records else "missing",
        "attempt_count": len(records),
        "attempt_type_counts": _counts(records, "attempt_type"),
        "result_state_counts": _counts(records, "result_state"),
        "result_ids": sorted({str(item.get("result_id")) for item in records if item.get("result_id")}),
        "provider_or_model_called_by_runtime": False,
        "limitations": ["authorization is not execution", "an execution attempt is not a successful or accepted result"],
        "source_artifact_references": [PROVIDER_EXECUTION_ATTEMPT_LEDGER_JSONL],
    }
    if write:
        write_json(state_dir / PROVIDER_EXECUTION_ATTEMPT_SUMMARY_JSON, summary)
    return summary


def build_provider_result_staging_admission(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    from .provider_consent import (
        build_provider_consent_resolution_report,
        build_provider_consent_scope_diff,
        build_provider_execution_authorization_decision,
        build_provider_execution_preflight_gate,
    )
    from .provider_evidence import build_provider_evidence_reconciliation
    from .provider_result_gate import build_provider_claim_support_report, build_provider_result_qa_report

    attempts = {str(item.get("result_id") or ""): item for item in build_provider_execution_attempt_ledger(state_dir, write=write)}
    reconciliation_report = build_provider_evidence_reconciliation(state_dir, write=False)
    reconciliation = _by_id(reconciliation_report.get("reconciled_results", []))
    qa = _by_id(build_provider_result_qa_report(state_dir, write=False).get("results", []))
    acceptance = _optional_json(state_dir / "provider-result-acceptance-decision.json")
    accepted = set(_strings(acceptance.get("accepted_result_ids")))
    limited = set(_strings(acceptance.get("accepted_with_limitations_result_ids")))
    scope_diff = build_provider_consent_scope_diff(state_dir, write=False)
    resolution = build_provider_consent_resolution_report(state_dir, scope_diff, write=False)
    authorization = build_provider_execution_authorization_decision(state_dir, resolution, write=False)
    preflight = build_provider_execution_preflight_gate(state_dir, authorization, write=False)
    safety = _optional_json(state_dir / "provider-execution-safety-decision.json")
    claim_support = build_provider_claim_support_report(state_dir, write=False)
    items = []
    for intake in _optional_jsonl(state_dir / "provider-result-intake.jsonl"):
        result_id = str(intake.get("result_id") or "")
        attempt = attempts.get(result_id, {})
        blockers = _admission_blockers(
            intake, attempt, reconciliation.get(result_id, {}), qa.get(result_id, {}), accepted, limited,
            resolution, authorization, preflight, safety, claim_support, scope_diff,
        )
        decision = _admission_decision(intake, attempt, blockers)
        items.append({
            "result_id": result_id,
            "attempt_id": str(attempt.get("attempt_id") or ""),
            "decision": decision,
            "admitted": decision == "admitted",
            "effective_scope": intake.get("scope", {}),
            "provenance": intake.get("provenance", {}),
            "blockers": blockers,
            "source_artifact_references": _evidence_names(state_dir),
        })
    status = "admitted" if items and all(item["admitted"] for item in items) else "mixed" if any(item["admitted"] for item in items) else "blocked"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-result-staging-admission-v1",
        "artifact": PROVIDER_RESULT_STAGING_ADMISSION_JSON,
        "status": status,
        "items": items,
        "summary": {
            "result_count": len(items),
            "admitted_count": sum(item["admitted"] for item in items),
            "quarantined_count": sum(item["decision"] != "admitted" for item in items),
        },
        "staging_admission_does_not_imply_provider_backed_quality": True,
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": _evidence_names(state_dir),
    }
    if write:
        write_json(state_dir / PROVIDER_RESULT_STAGING_ADMISSION_JSON, report)
    return report


def build_provider_result_quarantine_report(state_dir: Path, admission: dict[str, Any] | None = None, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    admission = admission or build_provider_result_staging_admission(state_dir, write=write)
    items = [
        {
            "result_id": item.get("result_id"),
            "attempt_id": item.get("attempt_id"),
            "quarantine_status": item.get("decision"),
            "reasons": item.get("blockers", []),
            "inspectable": True,
            "eligible_for_delivery_or_claims": False,
        }
        for item in admission.get("items", []) if not item.get("admitted")
    ]
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-result-quarantine-report-v1",
        "artifact": PROVIDER_RESULT_QUARANTINE_REPORT_JSON,
        "status": "quarantined" if items else "clear",
        "items": items,
        "quarantined_result_count": len(items),
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": [PROVIDER_RESULT_STAGING_ADMISSION_JSON],
    }
    if write:
        write_json(state_dir / PROVIDER_RESULT_QUARANTINE_REPORT_JSON, report)
    return report


def build_provider_result_staging_manifest(state_dir: Path, admission: dict[str, Any] | None = None, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    admission = admission or build_provider_result_staging_admission(state_dir, write=write)
    intake = {str(item.get("result_id") or ""): item for item in _optional_jsonl(state_dir / "provider-result-intake.jsonl")}
    admitted = []
    for item in admission.get("items", []):
        if not item.get("admitted"):
            continue
        record = intake.get(str(item.get("result_id") or ""), {})
        admitted.append({
            "result_id": item.get("result_id"),
            "attempt_id": item.get("attempt_id"),
            "segment_ids": sorted(str(segment.get("segment_id")) for segment in record.get("segments", []) if isinstance(segment, dict) and segment.get("segment_id")),
            "effective_scope": item.get("effective_scope", {}),
            "provenance": item.get("provenance", {}),
            "evidence_references": item.get("source_artifact_references", []),
        })
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-result-staging-manifest-v1",
        "artifact": PROVIDER_RESULT_STAGING_MANIFEST_JSON,
        "status": "admitted" if admitted else "empty",
        "admitted_results": admitted,
        "admitted_result_ids": [item["result_id"] for item in admitted],
        "provider_or_model_called_by_runtime": False,
        "target_files_mutated": False,
        "source_artifact_references": [PROVIDER_RESULT_STAGING_ADMISSION_JSON, "provider-result-intake.jsonl"],
    }
    if write:
        write_json(state_dir / PROVIDER_RESULT_STAGING_MANIFEST_JSON, manifest)
    return manifest


def build_provider_staging_claim_boundary(state_dir: Path, admission: dict[str, Any] | None = None, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    admission = admission or build_provider_result_staging_admission(state_dir, write=write)
    claims = _optional_json(state_dir / "provider-claim-support-report.json")
    admitted_ids = [str(item.get("result_id")) for item in admission.get("items", []) if item.get("admitted")]
    quality_supported = bool(admitted_ids) and claims.get("provider_backed_quality_supported") is True
    execution_supported = bool(admitted_ids) and claims.get("provider_execution_complete_supported") is True
    forbidden = set(PROVIDER_CLAIMS)
    if execution_supported:
        forbidden.discard("provider_execution_complete")
    if quality_supported:
        forbidden.discard("provider_backed_quality")
    boundary = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-staging-claim-boundary-v1",
        "artifact": PROVIDER_STAGING_CLAIM_BOUNDARY_JSON,
        "status": "supported" if quality_supported else "limited" if execution_supported else "blocked",
        "admitted_result_ids": admitted_ids,
        "supported_claims": [claim for claim, supported in (("provider_execution_complete", execution_supported), ("provider_backed_quality", quality_supported)) if supported],
        "forbidden_claims": sorted(forbidden),
        "provider_backed_quality_supported": quality_supported,
        "staging_admission_alone_supports_quality": False,
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": [PROVIDER_RESULT_STAGING_ADMISSION_JSON, "provider-claim-support-report.json"],
        "limitations": ["staging admission is not delivery, apply, release, or provider-backed quality evidence"],
    }
    if write:
        write_json(state_dir / PROVIDER_STAGING_CLAIM_BOUNDARY_JSON, boundary)
    return boundary


def build_provider_staging_artifacts(state_dir: Path) -> dict[str, Any]:
    ledger = build_provider_execution_attempt_ledger(state_dir)
    summary = build_provider_execution_attempt_summary(state_dir)
    admission = build_provider_result_staging_admission(state_dir)
    quarantine = build_provider_result_quarantine_report(state_dir, admission)
    manifest = build_provider_result_staging_manifest(state_dir, admission)
    boundary = build_provider_staging_claim_boundary(state_dir, admission)
    return {"provider_execution_attempt_ledger": ledger, "provider_execution_attempt_summary": summary, "provider_result_staging_admission": admission, "provider_result_quarantine_report": quarantine, "provider_result_staging_manifest": manifest, "provider_staging_claim_boundary": boundary, "provider_or_model_called_by_runtime": False}


def provider_staging_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in PROVIDER_STAGING_ASSETS.items() if (state_dir / name).is_file()}


def provider_result_staging_blocker(state_dir: Path | None, generated_segments: list[dict[str, Any]]) -> str | None:
    result_ids = sorted({_provider_result_id(segment) for segment in generated_segments if _provider_linked(segment)})
    if not result_ids:
        return None
    if state_dir is None:
        return "provider-linked generated segments require --state-dir and current staging admission evidence"
    admission = build_provider_result_staging_admission(state_dir)
    admitted = {str(item.get("result_id") or "") for item in admission.get("items", []) if item.get("admitted")}
    missing = [result_id for result_id in result_ids if not result_id or result_id not in admitted]
    if missing:
        return f"provider results are not admitted to staging: {', '.join(result_id or '<missing-result-id>' for result_id in missing)}"
    return None


def _provider_linked(segment: dict[str, Any]) -> bool:
    generation = segment.get("generation") if isinstance(segment.get("generation"), dict) else {}
    source = str(segment.get("result_source") or segment.get("generation_source") or generation.get("result_source") or "")
    provider = str(generation.get("provider") or "")
    return bool(_provider_result_id(segment) or source in {"real_provider", "external_provider_result", "external_model_result", "mock", "dry_run"} or provider not in {"", "host_agent", "synthetic", "local"})


def _provider_result_id(segment: dict[str, Any]) -> str:
    generation = segment.get("generation") if isinstance(segment.get("generation"), dict) else {}
    return str(segment.get("provider_result_id") or generation.get("provider_result_id") or generation.get("result_id") or "")


def _attempt_from_intake(intake: dict[str, Any], authorization: dict[str, Any], preflight: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    source = str(intake.get("result_source") or "unknown")
    provenance = intake.get("provenance") if isinstance(intake.get("provenance"), dict) else {}
    status = str(intake.get("provider_status") or intake.get("status") or "")
    attempt_type = "external_result_import"
    if source in {"mock", "synthetic"} or provenance.get("execution_mode") == "provider_safe_mock" or provenance.get("provider_name") == "mock":
        attempt_type = "mock_execution"
    elif source == "dry_run":
        attempt_type = "dry_run_only"
    elif source == "skipped":
        attempt_type = "skipped"
    elif status in {"blocked", "rejected_shape", "rejected_provenance", "rejected_stale"}:
        attempt_type = "failed_policy_check"
    result_state = _result_state(status, intake)
    result_id = str(intake.get("result_id") or "")
    identity = [result_id, attempt_type, result_state, intake.get("request_id")]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-execution-attempt-record-v1",
        "attempt_id": _stable_id("provider-attempt", identity),
        "attempt_type": attempt_type,
        "result_state": result_state,
        "result_id": result_id,
        "request_id": str(intake.get("request_id") or request.get("request_id") or ""),
        "authorization_decision_id": str(authorization.get("decision_id") or authorization.get("consent_action_id") or ""),
        "authorization_status": str(authorization.get("status") or "missing"),
        "preflight_status": str(preflight.get("status") or "missing"),
        "scope": intake.get("scope") if isinstance(intake.get("scope"), dict) else {},
        "authorization_scope": authorization.get("authorization_scope", {}),
        "provenance": {"result_source": source, **provenance},
        "limitations": ["derived from externally supplied or mock result intake; no provider was called by this runtime"],
        "source_artifact_references": ["provider-result-intake.jsonl", "provider-execution-authorization-decision.json", "provider-execution-preflight-gate.json"],
        "provider_or_model_called_by_runtime": False,
    }


def _empty_attempt(authorization: dict[str, Any], preflight: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    authorized = authorization.get("status") == "authorized" and preflight.get("status") == "authorized"
    attempt_type = "future_real_execution_placeholder" if authorized else "blocked_before_execution"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-execution-attempt-record-v1",
        "attempt_id": _stable_id("provider-attempt", [attempt_type, request.get("request_id"), authorization.get("status")]),
        "attempt_type": attempt_type,
        "result_state": "no_execution" if authorized else "blocked",
        "result_id": "",
        "request_id": str(request.get("request_id") or ""),
        "authorization_decision_id": str(authorization.get("decision_id") or authorization.get("consent_action_id") or ""),
        "scope": authorization.get("authorization_scope", {}),
        "provenance": {},
        "limitations": ["placeholder records no real execution"],
        "source_artifact_references": _strings(authorization.get("source_artifact_references")),
        "provider_or_model_called_by_runtime": False,
    }


def _result_state(status: str, intake: dict[str, Any]) -> str:
    value = status.lower()
    segments = intake.get("segments") if isinstance(intake.get("segments"), list) else []
    if "timeout" in value:
        return "timeout"
    if "malformed" in value:
        return "malformed_response"
    if "partial" in value:
        return "partial_response"
    if "fallback" in value:
        return "fallback_attempted"
    if "failure" in value or "failed" in value:
        return "failure"
    if "blocked" in value or "rejected" in value:
        return "blocked"
    if not segments:
        return "empty_output"
    return "success"


def _admission_blockers(intake: dict[str, Any], attempt: dict[str, Any], reconciled: dict[str, Any], qa: dict[str, Any], accepted: set[str], limited: set[str], resolution: dict[str, Any], authorization: dict[str, Any], preflight: dict[str, Any], safety: dict[str, Any], claims: dict[str, Any], scope_diff: dict[str, Any]) -> list[str]:
    result_id = str(intake.get("result_id") or "")
    source = str(intake.get("result_source") or "")
    blockers = []
    if resolution.get("status") != "granted":
        blockers.append("missing_or_stale_consent")
    if scope_diff.get("status") != "exact_match":
        blockers.append("stale_consent" if scope_diff.get("status") == "stale" else "scope_mismatch")
    if authorization.get("status") != "authorized" or not authorization.get("execution_authorized"):
        blockers.append("missing_authorization")
    if preflight.get("status") != "authorized" or not preflight.get("execution_allowed"):
        blockers.append("failed_preflight_gate")
    if safety.get("status") != "ready_for_future_execution":
        blockers.append("failed_execution_safety_decision")
    if not attempt:
        blockers.append("missing_execution_attempt")
    elif attempt.get("authorization_status") != "authorized" or attempt.get("preflight_status") != "authorized":
        blockers.append("attempt_not_governed_by_authorization")
    if attempt.get("result_state") in {"failure", "timeout", "malformed_response", "partial_response", "empty_output", "fallback_attempted", "blocked", "no_execution", "quarantined"}:
        blockers.append(str(attempt.get("result_state")))
    if source in {"mock", "synthetic", "dry_run", "skipped"}:
        blockers.append("mock_synthetic_or_dry_run_provenance")
    if intake.get("status") in {"rejected_shape", "rejected_stale", "rejected_provenance", "requires_follow_up"}:
        blockers.append(str(intake.get("status")))
    if reconciled.get("reconciliation_status") != "accepted_provider_execution_evidence":
        blockers.append("evidence_reconciliation_not_accepted")
    if qa.get("status") not in {"passed", "requires_human_review"}:
        blockers.append("failed_result_qa")
    if result_id not in accepted and result_id not in limited:
        blockers.append("missing_review_acceptance")
    if not claims.get("provider_execution_complete_supported"):
        blockers.append("provider_claim_support_incompatible")
    expected_scope = authorization.get("authorization_scope") if isinstance(authorization.get("authorization_scope"), dict) else {}
    provenance = intake.get("provenance") if isinstance(intake.get("provenance"), dict) else {}
    for field in ("run_id", "provider_profile", "model_name", "source_hash", "handoff_hash"):
        provided = intake.get(field) or provenance.get(field)
        if provided and str(provided) != str(expected_scope.get(field) or ""):
            blockers.append(f"{field}_mismatch")
    return sorted(set(blockers))


def _admission_decision(intake: dict[str, Any], attempt: dict[str, Any], blockers: list[str]) -> str:
    source = str(intake.get("result_source") or "")
    if source == "dry_run" or attempt.get("attempt_type") == "dry_run_only":
        return "dry_run_only"
    if source in {"mock", "synthetic"} or attempt.get("attempt_type") == "mock_execution":
        return "mock_only"
    if not blockers:
        return "admitted"
    if any(item in blockers for item in {"missing_authorization", "missing_or_stale_consent", "failed_preflight_gate"}):
        return "blocked"
    if any(item in blockers for item in {"failure", "timeout", "malformed_response", "partial_response", "empty_output", "fallback_attempted", "failed_result_qa"}):
        return "quarantined"
    if "missing_review_acceptance" in blockers:
        return "requires_review"
    return "quarantined"


def _evidence_names(state_dir: Path) -> list[str]:
    names = [
        "provider-consent-resolution-report.json", "provider-execution-authorization-decision.json",
        "provider-execution-preflight-gate.json", "provider-execution-safety-decision.json",
        PROVIDER_EXECUTION_ATTEMPT_LEDGER_JSONL, "provider-handoff-request.json", "provider-result-intake.jsonl",
        "provider-evidence-reconciliation.json", "provider-result-qa-report.json",
        "provider-result-acceptance-decision.json", "provider-claim-support-report.json",
    ]
    return [name for name in names if (state_dir / name).is_file()]


def _by_id(items: Any) -> dict[str, dict[str, Any]]:
    return {str(item.get("result_id") or ""): item for item in items if isinstance(item, dict)} if isinstance(items, list) else {}


def _counts(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for record in records:
        value = str(record.get(key) or "unknown")
        values[value] = values.get(value, 0) + 1
    return dict(sorted(values.items()))


def _optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"artifact not found: {path.name}")
    return read_json(path)


def _optional_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.is_file() else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value if str(item)] if isinstance(value, list) else []


def _stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"
