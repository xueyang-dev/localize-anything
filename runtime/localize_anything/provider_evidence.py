from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, sha256_file, write_json, write_jsonl


PROVIDER_EXECUTION_POLICY_JSON = "provider-execution-policy.json"
PROVIDER_HANDOFF_REQUEST_JSON = "provider-handoff-request.json"
PROVIDER_EXECUTION_LEDGER_JSONL = "provider-execution-ledger.jsonl"
PROVIDER_RESULT_INTAKE_JSONL = "provider-result-intake.jsonl"
PROVIDER_EVIDENCE_RECONCILIATION_JSON = "provider-evidence-reconciliation.json"

PROVIDER_FORBIDDEN_CLAIMS = {
    "provider_backed_quality",
    "provider_execution_complete",
    "provider_repair_complete",
    "model_repair_complete",
}
EXECUTION_MODES = {"disabled", "dry_run", "synthetic_test", "mock", "real_provider", "external_import_only"}
REQUEST_MODES = {"dry_run", "synthetic_test", "mock", "real_provider", "external_import"}
LEDGER_OUTCOMES = {"planned", "dry_run", "skipped", "blocked", "failed", "mock", "synthetic", "external_imported", "completed"}
RESULT_SOURCES = {"real_provider", "external_provider_result", "external_model_result", "synthetic", "mock", "dry_run", "skipped", "failed", "unknown"}


def build_provider_execution_policy(
    state_dir: Path,
    policy: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    payload = policy or {}
    mode = _enum(payload, "execution_mode", EXECUTION_MODES, "disabled")
    safe = bool(payload.get("safe") or payload.get("provider_policy_safe"))
    allow_real = bool(payload.get("allow_real_provider") or payload.get("real_provider_allowed"))
    status = "disabled" if mode == "disabled" else "dry_run" if mode == "dry_run" else "synthetic_test" if mode in {"synthetic_test", "mock"} else "allowed" if mode == "real_provider" and safe and allow_real else "external_import_only" if mode == "external_import_only" else "blocked"
    provider_backed_allowed = status == "allowed"
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-execution-policy-v1",
        "artifact": PROVIDER_EXECUTION_POLICY_JSON,
        "run_id": run_id,
        "status": status,
        "execution_mode": mode,
        "provider_name": str(payload.get("provider_name") or payload.get("provider") or ""),
        "model_name": str(payload.get("model_name") or payload.get("model") or ""),
        "safe": safe,
        "allow_real_provider": allow_real,
        "provider_backed_execution_allowed": provider_backed_allowed,
        "synthetic_or_mock_allowed": mode in {"synthetic_test", "mock", "dry_run"},
        "external_result_intake_allowed": mode in {"external_import_only", "real_provider", "dry_run"},
        "forbidden_claims": [] if provider_backed_allowed else sorted(PROVIDER_FORBIDDEN_CLAIMS),
        "policy_reason": str(payload.get("policy_reason") or _policy_reason(mode, status)),
        "source_artifact_references": _source_artifacts(state_dir),
        "provider_or_model_called": False,
        "limitations": [
            "provider policy is evidence only and does not execute providers",
            "synthetic, mock, dry-run, skipped, failed, or unverified imported output cannot support provider-backed claims",
        ],
    }
    if write:
        write_json(state_dir / PROVIDER_EXECUTION_POLICY_JSON, result)
    return result


def read_provider_execution_policy(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / PROVIDER_EXECUTION_POLICY_JSON)


def build_provider_handoff_request(
    state_dir: Path,
    request: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    payload = request or {}
    policy = _read_optional_json(state_dir / PROVIDER_EXECUTION_POLICY_JSON) or build_provider_execution_policy(state_dir, write=False)
    handoff = _read_optional_json(state_dir / "generation-handoff-decision.json")
    mode = _enum(payload, "execution_mode", REQUEST_MODES, "dry_run")
    blocked: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if handoff and (handoff.get("handoff_allowed") is False or handoff.get("status") == "blocked"):
        blocked.append(_issue("generation_handoff_blocked", "generation-handoff-decision.json", "Generation handoff policy blocks provider execution."))
    if mode == "real_provider" and not policy.get("provider_backed_execution_allowed"):
        blocked.append(_issue("provider_policy_not_allowed", PROVIDER_EXECUTION_POLICY_JSON, "Provider policy does not allow real provider execution."))
    if mode in {"dry_run", "synthetic_test", "mock", "external_import"}:
        warnings.append(_issue("not_provider_backed_execution", PROVIDER_EXECUTION_POLICY_JSON, f"{mode} does not prove provider-backed execution."))
    status = "blocked" if blocked else "dry_run" if mode == "dry_run" else "prepared"
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-handoff-request-v1",
        "artifact": PROVIDER_HANDOFF_REQUEST_JSON,
        "request_id": _stable_id("provider-request", [mode, payload, _hash_if_file(state_dir / "generation-handoff.json")]),
        "run_id": run_id,
        "status": status,
        "execution_mode": mode,
        "provider_name": str(payload.get("provider_name") or policy.get("provider_name") or ""),
        "model_name": str(payload.get("model_name") or policy.get("model_name") or ""),
        "generation_handoff_artifact": "generation-handoff.json" if (state_dir / "generation-handoff.json").is_file() else None,
        "generation_handoff_decision_artifact": "generation-handoff-decision.json" if handoff else None,
        "provider_backed_requested": mode == "real_provider",
        "provider_backed_claim_supported": False,
        "blockers": blocked,
        "warnings": warnings,
        "forbidden_claims": sorted(PROVIDER_FORBIDDEN_CLAIMS) if status != "prepared" or mode != "real_provider" else [],
        "request_payload_hash": _stable_hash(payload),
        "source_artifact_hashes": _hashes(state_dir, ["generation-handoff.json", "generation-handoff-decision.json", PROVIDER_EXECUTION_POLICY_JSON]),
        "provider_or_model_called": False,
        "limitations": [
            "provider handoff request is a contract artifact and does not execute providers",
            "prepared real-provider handoff still requires execution ledger, result intake, QA, review, and reconciliation before claims are supported",
        ],
    }
    if write:
        write_json(state_dir / PROVIDER_HANDOFF_REQUEST_JSON, result)
        append_provider_execution_ledger_entry(
            state_dir,
            {
                "request_id": result["request_id"],
                "execution_mode": mode,
                "outcome": "blocked" if blocked else "dry_run" if mode == "dry_run" else "planned",
                "provider_name": result["provider_name"],
                "model_name": result["model_name"],
                "source_artifact_references": [PROVIDER_HANDOFF_REQUEST_JSON, PROVIDER_EXECUTION_POLICY_JSON],
            },
            run_id=run_id,
        )
    return result


def read_provider_handoff_request(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / PROVIDER_HANDOFF_REQUEST_JSON)


def append_provider_execution_ledger_entry(
    state_dir: Path,
    entry: dict[str, Any],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-execution-ledger-record-v1",
        "ledger_id": _stable_id("provider-ledger", [entry, len(read_provider_execution_ledger(state_dir))]),
        "run_id": run_id,
        "request_id": str(entry.get("request_id") or ""),
        "execution_mode": str(entry.get("execution_mode") or "dry_run"),
        "outcome": _enum(entry, "outcome", LEDGER_OUTCOMES, "skipped"),
        "provider_name": str(entry.get("provider_name") or ""),
        "model_name": str(entry.get("model_name") or ""),
        "result_artifact_references": _strings(entry.get("result_artifact_references")),
        "source_artifact_references": _strings(entry.get("source_artifact_references")),
        "provider_or_model_called_by_runtime": False,
        "error_kind": str(entry.get("error_kind") or ""),
        "created_at": _now(),
        "limitations": ["ledger records handoff/external evidence status; this runtime did not call providers in this seed"],
    }
    records = read_provider_execution_ledger(state_dir)
    records.append(record)
    write_jsonl(state_dir / PROVIDER_EXECUTION_LEDGER_JSONL, records)
    return record


def read_provider_execution_ledger(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / PROVIDER_EXECUTION_LEDGER_JSONL
    return read_jsonl(path) if path.is_file() else []


def record_provider_result_intake(
    state_dir: Path,
    result: dict[str, Any],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    record = _normalize_result_intake(state_dir, result, run_id=run_id)
    records = read_provider_result_intake(state_dir)
    records.append(record)
    write_jsonl(state_dir / PROVIDER_RESULT_INTAKE_JSONL, records)
    build_provider_evidence_reconciliation(state_dir, run_id=run_id)
    return record


def read_provider_result_intake(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / PROVIDER_RESULT_INTAKE_JSONL
    return read_jsonl(path) if path.is_file() else []


def build_provider_evidence_reconciliation(
    state_dir: Path,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    policy = _read_optional_json(state_dir / PROVIDER_EXECUTION_POLICY_JSON)
    request = _read_optional_json(state_dir / PROVIDER_HANDOFF_REQUEST_JSON)
    ledger = read_provider_execution_ledger(state_dir)
    intake = read_provider_result_intake(state_dir)
    items: list[dict[str, Any]] = []
    for record in intake:
        status, reasons = _reconcile_intake_record(policy, request, ledger, record)
        items.append(
            {
                "result_id": record.get("result_id"),
                "request_id": record.get("request_id"),
                "result_source": record.get("result_source"),
                "reconciliation_status": status,
                "provider_backed": status == "accepted_provider_execution_evidence",
                "blocking_reasons": reasons,
                "source_artifact_references": [PROVIDER_RESULT_INTAKE_JSONL, PROVIDER_EXECUTION_POLICY_JSON, PROVIDER_HANDOFF_REQUEST_JSON, PROVIDER_EXECUTION_LEDGER_JSONL],
            }
        )
    accepted = [item for item in items if item["reconciliation_status"] == "accepted_provider_execution_evidence"]
    blockers = [item for item in items if item["blocking_reasons"]]
    if not policy:
        status = "blocked"
        blockers.append({"blocking_reasons": ["provider_execution_policy_missing"]})
    elif not request:
        status = "blocked"
        blockers.append({"blocking_reasons": ["provider_handoff_request_missing"]})
    elif str(policy.get("status") or "") in {"disabled", "blocked", "dry_run", "synthetic_test"}:
        status = "not_applicable" if policy.get("status") == "disabled" else "blocked"
    elif not intake:
        status = "blocked"
        blockers.append({"blocking_reasons": ["provider_result_intake_missing"]})
    elif accepted and not blockers:
        status = "clear"
    elif accepted:
        status = "clear_with_warnings"
    else:
        status = "blocked"
    provider_execution_complete_supported = bool(accepted) and status in {"clear", "clear_with_warnings"}
    provider_backed_quality_supported = False
    forbidden = set(PROVIDER_FORBIDDEN_CLAIMS)
    if provider_execution_complete_supported:
        forbidden.discard("provider_execution_complete")
    reconciliation = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-evidence-reconciliation-v1",
        "artifact": PROVIDER_EVIDENCE_RECONCILIATION_JSON,
        "run_id": run_id or policy.get("run_id") or request.get("run_id"),
        "status": status,
        "policy_status": policy.get("status", "missing") if isinstance(policy, dict) else "missing",
        "request_status": request.get("status", "missing") if isinstance(request, dict) else "missing",
        "summary": {
            "intake_count": len(intake),
            "accepted_provider_execution_count": len(accepted),
            "blocked_or_rejected_count": len(blockers),
            "synthetic_or_mock_count": sum(item.get("result_source") in {"synthetic", "mock", "dry_run"} for item in intake),
            "failed_count": sum(item.get("result_source") == "failed" or item.get("provider_status") == "failed" for item in intake),
        },
        "reconciled_results": items,
        "provider_execution_complete_supported": provider_execution_complete_supported,
        "provider_backed_quality_supported": provider_backed_quality_supported,
        "provider_repair_complete_supported": False,
        "model_repair_complete_supported": False,
        "forbidden_claims_remaining": sorted(forbidden),
        "readiness_impact": "clear" if status == "clear" else "review_required" if status == "clear_with_warnings" else "blocked",
        "source_artifacts": provider_evidence_asset_paths(state_dir),
        "limitations": [
            "external result intake is evidence only and does not imply quality acceptance",
            "provider-backed quality requires reconciled execution evidence plus QA/review/signoff evidence",
            "synthetic, mock, skipped, failed, dry-run, or unverified imported output cannot support provider-backed claims",
        ],
    }
    if write:
        write_json(state_dir / PROVIDER_EVIDENCE_RECONCILIATION_JSON, reconciliation)
    return reconciliation


def read_provider_evidence_reconciliation(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / PROVIDER_EVIDENCE_RECONCILIATION_JSON)


def provider_evidence_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "provider_execution_policy": PROVIDER_EXECUTION_POLICY_JSON,
        "provider_handoff_request": PROVIDER_HANDOFF_REQUEST_JSON,
        "provider_execution_ledger": PROVIDER_EXECUTION_LEDGER_JSONL,
        "provider_result_intake": PROVIDER_RESULT_INTAKE_JSONL,
        "provider_evidence_reconciliation": PROVIDER_EVIDENCE_RECONCILIATION_JSON,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def provider_evidence_summary(state_dir: Path) -> dict[str, Any]:
    reconciliation = _read_optional_json(state_dir / PROVIDER_EVIDENCE_RECONCILIATION_JSON)
    if not reconciliation:
        return {"status": "not_run", "forbidden_claims_remaining": sorted(PROVIDER_FORBIDDEN_CLAIMS)}
    return {
        "status": reconciliation.get("status", "unknown"),
        "provider_execution_complete_supported": bool(reconciliation.get("provider_execution_complete_supported")),
        "provider_backed_quality_supported": bool(reconciliation.get("provider_backed_quality_supported")),
        "forbidden_claims_remaining": reconciliation.get("forbidden_claims_remaining", []),
        "readiness_impact": reconciliation.get("readiness_impact"),
    }


def _normalize_result_intake(state_dir: Path, result: dict[str, Any], *, run_id: str | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("provider result intake must be a JSON object")
    source = _enum(result, "result_source", RESULT_SOURCES, "unknown")
    provenance = result.get("provenance") if isinstance(result.get("provenance"), dict) else {}
    has_provenance = bool(provenance.get("provider_name") or provenance.get("external_reference") or provenance.get("request_id"))
    target_artifacts = _strings(result.get("target_artifact_references"))
    hashes = {path: _hash_if_file(state_dir / path) for path in target_artifacts}
    status = "received"
    if source in {"external_provider_result", "external_model_result", "real_provider"} and not has_provenance:
        status = "rejected_provenance"
    elif source in {"synthetic", "mock", "dry_run", "skipped"}:
        status = "received_non_provider_backed"
    elif source == "failed" or result.get("provider_status") == "failed":
        status = "received_failed"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-result-intake-record-v1",
        "result_id": str(result.get("result_id") or _stable_id("provider-result", [source, result])),
        "run_id": run_id,
        "request_id": str(result.get("request_id") or ""),
        "result_source": source,
        "status": status,
        "provider_status": str(result.get("provider_status") or ""),
        "provenance": provenance,
        "target_artifact_references": target_artifacts,
        "target_artifact_hashes": hashes,
        "scope": result.get("scope") if isinstance(result.get("scope"), dict) else {},
        "qa_status": str(result.get("qa_status") or "not_provided"),
        "review_evidence": result.get("review_evidence") if isinstance(result.get("review_evidence"), dict) else {},
        "created_at": _now(),
        "provider_or_model_called_by_runtime": False,
        "limitations": ["result intake records evidence only; it does not accept quality or mutate output"],
    }


def _reconcile_intake_record(policy: dict[str, Any], request: dict[str, Any], ledger: list[dict[str, Any]], record: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    source = str(record.get("result_source") or "")
    if source in {"synthetic", "mock", "dry_run", "skipped"}:
        reasons.append(f"{source}_is_not_provider_backed")
    if source == "failed" or record.get("provider_status") == "failed":
        reasons.append("provider_execution_failed")
    if record.get("status") == "rejected_provenance":
        reasons.append("missing_or_invalid_provenance")
    if str(policy.get("status") or "") != "allowed":
        reasons.append("policy_does_not_allow_provider_backed_claim")
    if request and request.get("status") == "blocked":
        reasons.append("handoff_request_blocked")
    if source in {"real_provider", "external_provider_result"} and str(record.get("qa_status") or "") not in {"pass", "pass_with_warnings"}:
        reasons.append("qa_not_passed")
    if source == "external_model_result":
        reasons.append("external_model_result_is_not_provider_execution")
    request_id = str(record.get("request_id") or "")
    if request_id and ledger and not any(str(item.get("request_id") or "") == request_id for item in ledger):
        reasons.append("ledger_request_match_missing")
    if reasons:
        return "blocked_or_unverified", sorted(set(reasons))
    if source in {"real_provider", "external_provider_result"}:
        return "accepted_provider_execution_evidence", []
    return "not_applicable", []


def _policy_reason(mode: str, status: str) -> str:
    if status == "allowed":
        return "real provider mode is explicitly safe and allowed"
    if mode == "disabled":
        return "provider execution is disabled"
    if mode in {"dry_run", "synthetic_test", "mock"}:
        return f"{mode} mode is not provider-backed"
    return "provider policy is not sufficient for provider-backed execution"


def _source_artifacts(state_dir: Path) -> dict[str, str]:
    names = ["generation-handoff-decision.json", "generation-handoff.json", "evaluation-scorecard.json", "artifact-state.json"]
    return {name: name for name in names if (state_dir / name).is_file()}


def _issue(code: str, artifact: str, message: str) -> dict[str, str]:
    return {"code": code, "artifact": artifact, "message": message}


def _enum(payload: dict[str, Any], key: str, allowed: set[str], default: str) -> str:
    value = str(payload.get(key) or default)
    return value if value in allowed else default


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str) and value:
        return [value]
    return []


def _hashes(state_dir: Path, names: list[str]) -> dict[str, str]:
    return {name: sha256_file(state_dir / name) for name in names if (state_dir / name).is_file()}


def _hash_if_file(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _read_required(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing provider evidence artifact: {path}")
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}-{_stable_hash(value)[:24]}"


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()
