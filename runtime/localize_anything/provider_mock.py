from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json, write_jsonl
from .provider_evidence import (
    PROVIDER_EVIDENCE_RECONCILIATION_JSON,
    PROVIDER_EXECUTION_LEDGER_JSONL,
    PROVIDER_EXECUTION_POLICY_JSON,
    PROVIDER_FORBIDDEN_CLAIMS,
    PROVIDER_HANDOFF_REQUEST_JSON,
    PROVIDER_RESULT_INTAKE_JSONL,
    append_provider_execution_ledger_entry,
    build_provider_evidence_reconciliation,
    build_provider_execution_policy,
    build_provider_handoff_request,
    record_provider_result_intake,
)
from .provider_result_gate import (
    PROVIDER_CLAIM_SUPPORT_REPORT_JSON,
    PROVIDER_RESULT_QA_REPORT_JSON,
    build_provider_claim_support_report,
    build_provider_result_qa_report,
)


PROVIDER_MOCK_RUN_MANIFEST_JSON = "provider-mock-run-manifest.json"
PROVIDER_MOCK_RESPONSE_JSONL = "provider-mock-response.jsonl"
PROVIDER_MOCK_FAILURE_REPORT_JSON = "provider-mock-failure-report.json"
PROVIDER_MOCK_EVIDENCE_REPORT_JSON = "provider-mock-evidence-report.json"
PROVIDER_MOCK_CLAIM_BOUNDARY_JSON = "provider-mock-claim-boundary.json"

PROVIDER_MOCK_ASSETS = {
    "provider_mock_run_manifest": PROVIDER_MOCK_RUN_MANIFEST_JSON,
    "provider_mock_response": PROVIDER_MOCK_RESPONSE_JSONL,
    "provider_mock_failure_report": PROVIDER_MOCK_FAILURE_REPORT_JSON,
    "provider_mock_evidence_report": PROVIDER_MOCK_EVIDENCE_REPORT_JSON,
    "provider_mock_claim_boundary": PROVIDER_MOCK_CLAIM_BOUNDARY_JSON,
}

MOCK_SCENARIOS = {
    "success",
    "failure",
    "timeout",
    "malformed_response",
    "partial_success",
    "placeholder_drift",
    "markup_drift",
    "empty_output",
    "extra_segments",
    "fallback_attempt",
}


def build_provider_mock_run(
    state_dir: Path,
    *,
    scenario: str = "success",
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    scenario = scenario if scenario in MOCK_SCENARIOS else "failure"
    policy = build_provider_execution_policy(
        state_dir,
        {"execution_mode": "mock", "provider_name": "mock", "model_name": "provider-safe-mock", "policy_reason": "provider-safe mock harness"},
        run_id=run_id,
        write=write,
    )
    scope = {"scope_type": "limited", "segment_ids": ["mock-segment-1", "mock-segment-2"]}
    request = build_provider_handoff_request(
        state_dir,
        {"execution_mode": "mock", "provider_name": "mock", "model_name": "provider-safe-mock", "scope": scope},
        run_id=run_id,
        write=write,
    )
    response_records = _mock_response_records(scenario, request["request_id"], scope, run_id)
    if write:
        write_jsonl(state_dir / PROVIDER_MOCK_RESPONSE_JSONL, response_records)
    ledger_outcome = "mock" if scenario in {"success", "partial_success", "placeholder_drift", "markup_drift", "extra_segments"} else "failed"
    if write:
        append_provider_execution_ledger_entry(
            state_dir,
            {
                "request_id": request["request_id"],
                "execution_mode": "mock",
                "outcome": ledger_outcome,
                "provider_name": "mock",
                "model_name": "provider-safe-mock",
                "result_artifact_references": [PROVIDER_MOCK_RESPONSE_JSONL],
                "source_artifact_references": [PROVIDER_MOCK_RUN_MANIFEST_JSON, PROVIDER_HANDOFF_REQUEST_JSON],
                "error_kind": _failure_kind(scenario),
            },
            run_id=run_id,
        )
        for record in response_records:
            record_provider_result_intake(state_dir, _intake_payload(record), run_id=run_id)
    reconciliation = build_provider_evidence_reconciliation(state_dir, run_id=run_id, write=write)
    qa = build_provider_result_qa_report(state_dir, write=write)
    claims = build_provider_claim_support_report(state_dir, write=write)
    manifest = _manifest(scenario, request, response_records, reconciliation, qa, run_id)
    failure = _failure_report(scenario, response_records, qa, run_id)
    evidence = _evidence_report(scenario, response_records, reconciliation, qa, claims, run_id)
    boundary = _claim_boundary(scenario, reconciliation, qa, claims, run_id)
    if write:
        write_json(state_dir / PROVIDER_MOCK_RUN_MANIFEST_JSON, manifest)
        write_json(state_dir / PROVIDER_MOCK_FAILURE_REPORT_JSON, failure)
        write_json(state_dir / PROVIDER_MOCK_EVIDENCE_REPORT_JSON, evidence)
        write_json(state_dir / PROVIDER_MOCK_CLAIM_BOUNDARY_JSON, boundary)
    return {
        "provider_mock_run_manifest": manifest,
        "provider_mock_response": {"records": response_records},
        "provider_mock_failure_report": failure,
        "provider_mock_evidence_report": evidence,
        "provider_mock_claim_boundary": boundary,
        "provider_or_model_called": False,
    }


def read_provider_mock_run_manifest(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_MOCK_RUN_MANIFEST_JSON)


def read_provider_mock_response(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / PROVIDER_MOCK_RESPONSE_JSONL
    return read_jsonl(path) if path.is_file() else []


def read_provider_mock_failure_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_MOCK_FAILURE_REPORT_JSON)


def read_provider_mock_evidence_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_MOCK_EVIDENCE_REPORT_JSON)


def read_provider_mock_claim_boundary(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_MOCK_CLAIM_BOUNDARY_JSON)


def provider_mock_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in PROVIDER_MOCK_ASSETS.items() if (state_dir / name).is_file()}


def _mock_response_records(scenario: str, request_id: str, scope: dict[str, Any], run_id: str | None) -> list[dict[str, Any]]:
    base = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-mock-response-record-v1",
        "run_id": run_id,
        "request_id": request_id,
        "scenario": scenario,
        "provider": "mock",
        "execution_mode": "provider_safe_mock",
        "quality_claim": "none",
        "provider_backed": False,
        "scope": scope,
        "provenance": {"provider_name": "mock", "execution_mode": "provider_safe_mock", "quality_claim": "none", "provider_backed": False},
        "provider_or_model_called_by_runtime": False,
    }
    if scenario in {"failure", "timeout"}:
        return [{**base, "mock_response_id": _stable_id("provider-mock-response", [scenario, "failed"]), "status": scenario, "segments": [], "retryable": scenario == "timeout"}]
    if scenario == "malformed_response":
        return [{**base, "mock_response_id": _stable_id("provider-mock-response", [scenario]), "status": "malformed_response", "segments": [], "malformed": True, "retryable": False}]
    segments = [_segment()]
    if scenario == "success":
        segments.append(_segment("mock-segment-2", "Open <b>settings</b>", "打开 <b>settings</b>"))
    elif scenario == "partial_success":
        pass
    elif scenario == "placeholder_drift":
        segments = [_segment(target="您好")]
    elif scenario == "markup_drift":
        segments = [_segment("mock-segment-2", "Open <b>settings</b>", "打开 settings")]
    elif scenario == "empty_output":
        segments = []
    elif scenario == "extra_segments":
        segments.append(_segment("mock-segment-extra", "Extra", "额外"))
    elif scenario == "fallback_attempt":
        return [
            {
                **base,
                "mock_response_id": _stable_id("provider-mock-response", [scenario]),
                "status": "synthetic_fallback_attempted",
                "result_source": "synthetic",
                "segments": [_segment()],
                "retryable": True,
            }
        ]
    return [{**base, "mock_response_id": _stable_id("provider-mock-response", [scenario]), "status": "mock_success", "segments": segments, "retryable": False}]


def _intake_payload(record: dict[str, Any]) -> dict[str, Any]:
    failed = record.get("status") in {"failure", "timeout", "malformed_response"}
    result_source = str(record.get("result_source") or ("failed" if failed else "mock"))
    provider_status = "failed" if failed else "synthetic_fallback" if result_source == "synthetic" else "mock_success"
    return {
        "result_id": record.get("mock_response_id"),
        "request_id": record.get("request_id"),
        "result_source": result_source,
        "provider_status": provider_status,
        "provenance": record.get("provenance", {}),
        "scope": record.get("scope", {}),
        "segments": record.get("segments", []),
        "qa_status": "not_provided",
    }


def _manifest(scenario: str, request: dict[str, Any], response_records: list[dict[str, Any]], reconciliation: dict[str, Any], qa: dict[str, Any], run_id: str | None) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-mock-run-manifest-v1",
        "artifact": PROVIDER_MOCK_RUN_MANIFEST_JSON,
        "run_id": run_id,
        "scenario": scenario,
        "status": _scenario_status(scenario, qa),
        "request_id": request.get("request_id"),
        "execution_mode": "provider_safe_mock",
        "provider": "mock",
        "provider_backed": False,
        "quality_claim": "none",
        "response_count": len(response_records),
        "source_artifact_references": [PROVIDER_EXECUTION_POLICY_JSON, PROVIDER_HANDOFF_REQUEST_JSON, PROVIDER_MOCK_RESPONSE_JSONL],
        "downstream_artifact_references": [PROVIDER_EXECUTION_LEDGER_JSONL, PROVIDER_RESULT_INTAKE_JSONL, PROVIDER_EVIDENCE_RECONCILIATION_JSON, PROVIDER_RESULT_QA_REPORT_JSON, PROVIDER_CLAIM_SUPPORT_REPORT_JSON],
        "reconciliation_status": reconciliation.get("status", "unknown"),
        "qa_status": qa.get("status", "unknown"),
        "forbidden_claims": sorted(PROVIDER_FORBIDDEN_CLAIMS),
        "provider_or_model_called": False,
        "network_calls_allowed": False,
        "limitations": ["mock provider output is deterministic harness evidence only and never provider-backed quality evidence"],
    }


def _failure_report(scenario: str, response_records: list[dict[str, Any]], qa: dict[str, Any], run_id: str | None) -> dict[str, Any]:
    failures = []
    if scenario in {"failure", "timeout", "malformed_response", "partial_success", "empty_output", "placeholder_drift", "markup_drift", "fallback_attempt"}:
        failures.append(
            {
                "failure_id": _stable_id("provider-mock-failure", [scenario]),
                "scenario": scenario,
                "failure_type": _failure_kind(scenario) or scenario,
                "retryable": scenario in {"timeout", "partial_success", "fallback_attempt"},
                "fail_closed": True,
                "provider_backed": False,
                "source_artifact_references": [PROVIDER_MOCK_RESPONSE_JSONL, PROVIDER_RESULT_QA_REPORT_JSON],
            }
        )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-mock-failure-report-v1",
        "artifact": PROVIDER_MOCK_FAILURE_REPORT_JSON,
        "run_id": run_id,
        "status": "fail_closed" if failures else "not_applicable",
        "scenario": scenario,
        "failures": failures,
        "qa_failed_check_types": sorted({check.get("check_type") for check in qa.get("qa_items", []) if check.get("status") in {"failed", "blocked", "excluded", "stale", "provenance_mismatch"}}),
        "response_count": len(response_records),
        "provider_or_model_called": False,
    }


def _evidence_report(
    scenario: str,
    response_records: list[dict[str, Any]],
    reconciliation: dict[str, Any],
    qa: dict[str, Any],
    claims: dict[str, Any],
    run_id: str | None,
) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-mock-evidence-report-v1",
        "artifact": PROVIDER_MOCK_EVIDENCE_REPORT_JSON,
        "run_id": run_id,
        "status": "blocked",
        "scenario": scenario,
        "mock_result_count": len(response_records),
        "provider_backed": False,
        "provider_execution_complete_supported": False,
        "provider_backed_quality_supported": False,
        "reconciliation_status": reconciliation.get("status", "unknown"),
        "qa_status": qa.get("status", "unknown"),
        "claim_support_status": claims.get("status", "unknown"),
        "synthetic_fallback_attempted": scenario == "fallback_attempt",
        "forbidden_claims": sorted(set(PROVIDER_FORBIDDEN_CLAIMS) | set(claims.get("forbidden_claims", []))),
        "source_artifact_references": [PROVIDER_MOCK_RUN_MANIFEST_JSON, PROVIDER_MOCK_RESPONSE_JSONL, PROVIDER_EVIDENCE_RECONCILIATION_JSON, PROVIDER_RESULT_QA_REPORT_JSON, PROVIDER_CLAIM_SUPPORT_REPORT_JSON],
        "provider_or_model_called": False,
        "limitations": ["mock evidence can exercise provider workflows but cannot support provider-backed claims"],
    }


def _claim_boundary(scenario: str, reconciliation: dict[str, Any], qa: dict[str, Any], claims: dict[str, Any], run_id: str | None) -> dict[str, Any]:
    forbidden = sorted(set(PROVIDER_FORBIDDEN_CLAIMS) | set(claims.get("forbidden_claims", [])))
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-mock-claim-boundary-v1",
        "artifact": PROVIDER_MOCK_CLAIM_BOUNDARY_JSON,
        "run_id": run_id,
        "status": "blocked",
        "scenario": scenario,
        "forbidden_claims": forbidden,
        "unsupported_claims": forbidden,
        "supported_claims": [],
        "provider_backed_quality_supported": False,
        "provider_execution_complete_supported": False,
        "reconciliation_status": reconciliation.get("status", "unknown"),
        "qa_status": qa.get("status", "unknown"),
        "provider_or_model_called": False,
        "limitations": ["mock success is workflow evidence only and not provider-backed quality evidence"],
    }


def _segment(segment_id: str = "mock-segment-1", source: str = "Hello %1$s", target: str = "您好 %1$s") -> dict[str, Any]:
    return {
        "segment_id": segment_id,
        "source": source,
        "target": target,
        "constraints": {"required_terms": ["您好"] if segment_id == "mock-segment-1" else [], "forbidden_translations": ["坏"]},
        "high_risk": False,
        "semantic_change": False,
    }


def _scenario_status(scenario: str, qa: dict[str, Any]) -> str:
    if scenario == "success":
        return "mock_completed"
    if scenario == "partial_success":
        return "partial"
    if scenario in {"failure", "timeout", "malformed_response"}:
        return "failed"
    if qa.get("status") == "blocked":
        return "failed_qa"
    return "mock_completed_with_warnings"


def _failure_kind(scenario: str) -> str:
    return {
        "failure": "mock_provider_failure",
        "timeout": "mock_provider_timeout",
        "malformed_response": "mock_malformed_response",
        "partial_success": "mock_partial_success",
        "empty_output": "mock_empty_output",
        "placeholder_drift": "mock_placeholder_drift",
        "markup_drift": "mock_markup_drift",
        "fallback_attempt": "mock_synthetic_fallback_attempt",
    }.get(scenario, "")


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing provider mock artifact: {path}")
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _stable_id(prefix: str, value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:24]}"
