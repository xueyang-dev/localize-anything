from __future__ import annotations

import os
import re
import socket
import ssl
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, write_json
from .provider_evidence import (
    PROVIDER_EXECUTION_POLICY_JSON,
    PROVIDER_FORBIDDEN_CLAIMS,
    PROVIDER_HANDOFF_REQUEST_JSON,
)


PROVIDER_EXECUTION_READINESS_REPORT_JSON = "provider-execution-readiness-report.json"
PROVIDER_CREDENTIAL_POLICY_REPORT_JSON = "provider-credential-policy-report.json"
PROVIDER_FAILURE_TAXONOMY_JSON = "provider-failure-taxonomy.json"
PROVIDER_NETWORK_BOUNDARY_REPORT_JSON = "provider-network-boundary-report.json"
PROVIDER_REDACTION_AUDIT_JSON = "provider-redaction-audit.json"
PROVIDER_EXECUTION_SAFETY_DECISION_JSON = "provider-execution-safety-decision.json"

PROVIDER_SAFETY_ASSETS = {
    "provider_execution_readiness_report": PROVIDER_EXECUTION_READINESS_REPORT_JSON,
    "provider_credential_policy_report": PROVIDER_CREDENTIAL_POLICY_REPORT_JSON,
    "provider_failure_taxonomy": PROVIDER_FAILURE_TAXONOMY_JSON,
    "provider_network_boundary_report": PROVIDER_NETWORK_BOUNDARY_REPORT_JSON,
    "provider_redaction_audit": PROVIDER_REDACTION_AUDIT_JSON,
    "provider_execution_safety_decision": PROVIDER_EXECUTION_SAFETY_DECISION_JSON,
}

_SECRET_RE = re.compile(r"(?:sk-[A-Za-z0-9]{16,}|gh[op]_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})")
_FAILURES = {
    "timeout": ("retryable", "provider_timeout"),
    "rate_limit": ("retryable", "provider_rate_limit"),
    "auth_failure": ("non_retryable", "provider_auth_failure"),
    "ssl_error": ("retryable", "provider_ssl_or_tls_failure"),
    "network_error": ("retryable", "provider_network_failure"),
    "malformed_response": ("non_retryable", "provider_malformed_response"),
    "partial_response": ("retryable", "provider_partial_response"),
    "provider_schema_drift": ("non_retryable", "provider_schema_drift"),
    "unknown": ("unknown", "provider_unknown_failure"),
}


def build_provider_safety_artifacts(
    state_dir: Path,
    profile: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    taxonomy = build_provider_failure_taxonomy(state_dir, run_id=run_id, write=write)
    credential = build_provider_credential_policy_report(state_dir, profile, run_id=run_id, write=write)
    network = build_provider_network_boundary_report(state_dir, profile, run_id=run_id, write=write)
    redaction = build_provider_redaction_audit(state_dir, run_id=run_id, write=write)
    readiness = build_provider_execution_readiness_report(state_dir, profile, credential, network, redaction, run_id=run_id, write=write)
    decision = build_provider_execution_safety_decision(state_dir, readiness, credential, network, redaction, run_id=run_id, write=write)
    return {
        "provider_execution_readiness_report": readiness,
        "provider_credential_policy_report": credential,
        "provider_failure_taxonomy": taxonomy,
        "provider_network_boundary_report": network,
        "provider_redaction_audit": redaction,
        "provider_execution_safety_decision": decision,
        "provider_or_model_called": False,
    }


def build_provider_execution_readiness_report(
    state_dir: Path,
    profile: dict[str, Any] | None = None,
    credential_report: dict[str, Any] | None = None,
    network_report: dict[str, Any] | None = None,
    redaction_audit: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    policy = _json(state_dir / PROVIDER_EXECUTION_POLICY_JSON)
    handoff = _json(state_dir / PROVIDER_HANDOFF_REQUEST_JSON)
    merged = _profile(policy, handoff, profile)
    validation = _validate_profile(merged)
    credential_report = credential_report or build_provider_credential_policy_report(state_dir, profile, run_id=run_id, write=False)
    network_report = network_report or build_provider_network_boundary_report(state_dir, profile, run_id=run_id, write=False)
    redaction_audit = redaction_audit or build_provider_redaction_audit(state_dir, run_id=run_id, write=False)
    blockers = list(validation["blockers"])
    if policy.get("execution_mode") != "real_provider" or not policy.get("allow_real_provider"):
        blockers.append("real_provider_execution_not_explicitly_enabled")
    if credential_report.get("status") == "missing":
        blockers.append("provider_credentials_missing")
    if network_report.get("status") == "blocked":
        blockers.append("provider_network_boundary_blocked")
    if redaction_audit.get("status") == "failed":
        blockers.append("provider_secret_redaction_failed")
    status = "blocked" if blockers else "ready_for_future_execution"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-execution-readiness-report-v1",
        "artifact": PROVIDER_EXECUTION_READINESS_REPORT_JSON,
        "run_id": run_id or policy.get("run_id") or handoff.get("run_id"),
        "status": status,
        "provider_profile": validation["provider_profile"],
        "explicit_opt_in_required": True,
        "real_provider_execution_enabled": bool(policy.get("execution_mode") == "real_provider" and policy.get("allow_real_provider")),
        "credential_status": credential_report.get("status", "unknown"),
        "network_boundary_status": network_report.get("status", "unknown"),
        "redaction_status": redaction_audit.get("status", "unknown"),
        "blockers": sorted(set(blockers)),
        "warnings": validation["warnings"],
        "forbidden_claims": sorted(PROVIDER_FORBIDDEN_CLAIMS),
        "provider_backed_quality_supported": False,
        "provider_or_model_called": False,
        "source_artifact_references": _existing_names(state_dir, PROVIDER_EXECUTION_POLICY_JSON, PROVIDER_HANDOFF_REQUEST_JSON),
        "limitations": ["readiness to execute later is not provider-backed quality evidence"],
    }
    if write:
        write_json(state_dir / PROVIDER_EXECUTION_READINESS_REPORT_JSON, report)
    return report


def build_provider_credential_policy_report(
    state_dir: Path,
    profile: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    policy = _json(state_dir / PROVIDER_EXECUTION_POLICY_JSON)
    handoff = _json(state_dir / PROVIDER_HANDOFF_REQUEST_JSON)
    merged = _profile(policy, handoff, profile)
    names = _env_names(merged)
    sources = [{"source_type": "env", "source_reference": name, "present": bool(os.environ.get(name))} for name in names]
    requires_credentials = bool(merged.get("requires_credentials", True))
    status = "not_required" if not requires_credentials else "present" if any(item["present"] for item in sources) else "missing"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-credential-policy-report-v1",
        "artifact": PROVIDER_CREDENTIAL_POLICY_REPORT_JSON,
        "run_id": run_id or policy.get("run_id") or handoff.get("run_id"),
        "status": status,
        "requires_credentials": requires_credentials,
        "credential_sources": sources,
        "allowed_environment_variable_names": names,
        "secret_values_written": False,
        "provider_or_model_called": False,
        "source_artifact_references": _existing_names(state_dir, PROVIDER_EXECUTION_POLICY_JSON, PROVIDER_HANDOFF_REQUEST_JSON),
        "limitations": ["credential presence is reported without values and does not imply provider readiness or quality"],
    }
    if write:
        write_json(state_dir / PROVIDER_CREDENTIAL_POLICY_REPORT_JSON, report)
    return report


def build_provider_failure_taxonomy(state_dir: Path, *, run_id: str | None = None, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    failures = [
        {"failure_type": key, "retryability": retryability, "ledger_error_kind": error_kind, "fail_closed": True}
        for key, (retryability, error_kind) in sorted(_FAILURES.items())
    ]
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-failure-taxonomy-v1",
        "artifact": PROVIDER_FAILURE_TAXONOMY_JSON,
        "run_id": run_id,
        "status": "current",
        "failures": failures,
        "provider_or_model_called": False,
        "limitations": ["failure taxonomy classifies evidence and does not execute providers"],
    }
    if write:
        write_json(state_dir / PROVIDER_FAILURE_TAXONOMY_JSON, report)
    return report


def build_provider_network_boundary_report(
    state_dir: Path,
    profile: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    policy = _json(state_dir / PROVIDER_EXECUTION_POLICY_JSON)
    handoff = _json(state_dir / PROVIDER_HANDOFF_REQUEST_JSON)
    merged = _profile(policy, handoff, profile)
    url = str(merged.get("endpoint") or merged.get("provider_url") or "")
    parsed = urllib.parse.urlparse(url)
    loopback = is_loopback_provider_url(url)
    opt_in = bool(merged.get("allow_real_provider_network") or policy.get("allow_real_provider_network"))
    blockers: list[str] = []
    if not url:
        blockers.append("provider_endpoint_missing")
    if parsed.scheme not in {"http", "https"}:
        blockers.append("provider_endpoint_scheme_unsupported")
    if not loopback and not opt_in:
        blockers.append("non_loopback_provider_network_requires_explicit_opt_in")
    status = "blocked" if blockers else "loopback_test_only" if loopback else "explicitly_enabled"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-network-boundary-report-v1",
        "artifact": PROVIDER_NETWORK_BOUNDARY_REPORT_JSON,
        "run_id": run_id or policy.get("run_id") or handoff.get("run_id"),
        "status": status,
        "network_disabled_by_default": True,
        "explicit_opt_in_required": True,
        "loopback_test_mode": loopback,
        "real_network_explicitly_enabled": bool(opt_in and not loopback),
        "endpoint_shape": {"scheme": parsed.scheme, "host_present": bool(parsed.hostname), "path_present": bool(parsed.path)},
        "blockers": sorted(set(blockers)),
        "provider_or_model_called": False,
        "source_artifact_references": _existing_names(state_dir, PROVIDER_EXECUTION_POLICY_JSON, PROVIDER_HANDOFF_REQUEST_JSON),
        "limitations": ["network boundary report is policy evidence and does not open a provider connection"],
    }
    if write:
        write_json(state_dir / PROVIDER_NETWORK_BOUNDARY_REPORT_JSON, report)
    return report


def build_provider_redaction_audit(state_dir: Path, *, run_id: str | None = None, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    candidate_names = list(PROVIDER_SAFETY_ASSETS.values()) + [PROVIDER_EXECUTION_POLICY_JSON, PROVIDER_HANDOFF_REQUEST_JSON]
    secret_hits: list[dict[str, str]] = []
    env_values = [(name, value) for name, value in os.environ.items() if len(value) >= 8 and ("KEY" in name or "TOKEN" in name or "SECRET" in name)]
    for name in candidate_names:
        path = state_dir / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if _SECRET_RE.search(text):
            secret_hits.append({"artifact": name, "reason": "secret_pattern_detected"})
        for env_name, env_value in env_values:
            if env_value and env_value in text:
                secret_hits.append({"artifact": name, "reason": f"environment_secret_value_detected:{env_name}"})
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-redaction-audit-v1",
        "artifact": PROVIDER_REDACTION_AUDIT_JSON,
        "run_id": run_id,
        "status": "failed" if secret_hits else "pass",
        "secret_value_leak_count": len(secret_hits),
        "findings": secret_hits,
        "checked_artifacts": [name for name in candidate_names if (state_dir / name).is_file()],
        "provider_or_model_called": False,
        "limitations": ["redaction audit checks provider safety artifacts and known env secret values without recording secret values"],
    }
    if write:
        write_json(state_dir / PROVIDER_REDACTION_AUDIT_JSON, report)
    return report


def build_provider_execution_safety_decision(
    state_dir: Path,
    readiness: dict[str, Any] | None = None,
    credential: dict[str, Any] | None = None,
    network: dict[str, Any] | None = None,
    redaction: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    readiness = readiness or _json(state_dir / PROVIDER_EXECUTION_READINESS_REPORT_JSON)
    credential = credential or _json(state_dir / PROVIDER_CREDENTIAL_POLICY_REPORT_JSON)
    network = network or _json(state_dir / PROVIDER_NETWORK_BOUNDARY_REPORT_JSON)
    redaction = redaction or _json(state_dir / PROVIDER_REDACTION_AUDIT_JSON)
    blockers = set(readiness.get("blockers", []))
    if readiness.get("status") != "ready_for_future_execution":
        blockers.add("provider_execution_readiness_not_clear")
    if redaction.get("status") == "failed":
        blockers.add("provider_redaction_failed")
    status = "blocked" if blockers else "ready_for_future_execution"
    decision = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-execution-safety-decision-v1",
        "artifact": PROVIDER_EXECUTION_SAFETY_DECISION_JSON,
        "run_id": run_id or readiness.get("run_id"),
        "status": status,
        "ready_for_future_real_provider_execution": status == "ready_for_future_execution",
        "provider_backed_quality_supported": False,
        "provider_execution_complete_supported": False,
        "forbidden_claims": sorted(PROVIDER_FORBIDDEN_CLAIMS),
        "blockers": sorted(blockers),
        "credential_status": credential.get("status", "unknown"),
        "network_boundary_status": network.get("status", "unknown"),
        "redaction_status": redaction.get("status", "unknown"),
        "downstream_required_path": [
            "provider-result-intake.jsonl",
            "provider-evidence-reconciliation.json",
            "provider-result-qa-report.json",
            "provider-result-review-evidence.jsonl",
            "provider-result-acceptance-decision.json",
            "provider-claim-support-report.json",
            "evaluation-scorecard.json",
            "readiness-authorization-matrix.json",
            "signoff-record.json",
        ],
        "provider_or_model_called": False,
        "limitations": ["provider execution safety is not provider execution evidence and cannot support provider-backed quality"],
    }
    if write:
        write_json(state_dir / PROVIDER_EXECUTION_SAFETY_DECISION_JSON, decision)
    return decision


def read_provider_execution_readiness_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_EXECUTION_READINESS_REPORT_JSON)


def read_provider_credential_policy_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_CREDENTIAL_POLICY_REPORT_JSON)


def read_provider_failure_taxonomy(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_FAILURE_TAXONOMY_JSON)


def read_provider_network_boundary_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_NETWORK_BOUNDARY_REPORT_JSON)


def read_provider_redaction_audit(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_REDACTION_AUDIT_JSON)


def read_provider_execution_safety_decision(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_EXECUTION_SAFETY_DECISION_JSON)


def provider_safety_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in PROVIDER_SAFETY_ASSETS.items() if (state_dir / name).is_file()}


def is_loopback_provider_url(provider_url: str) -> bool:
    host = urllib.parse.urlparse(provider_url).hostname
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return bool(__import__("ipaddress").ip_address(host).is_loopback)
    except ValueError:
        return False


def provider_network_blocker(provider_url: str, *, allow_real_provider_network: bool = False) -> str:
    if is_loopback_provider_url(provider_url) or allow_real_provider_network:
        return ""
    return "real provider network execution requires explicit opt-in"


def classify_provider_failure(exc: BaseException | str) -> dict[str, Any]:
    if isinstance(exc, TimeoutError) or isinstance(exc, socket.timeout) or "timeout" in str(exc).lower():
        kind = "timeout"
    elif isinstance(exc, urllib.error.HTTPError) and exc.code in {401, 403}:
        kind = "auth_failure"
    elif isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
        kind = "rate_limit"
    elif isinstance(exc, ssl.SSLError) or "ssl" in str(exc).lower() or "certificate" in str(exc).lower():
        kind = "ssl_error"
    elif isinstance(exc, urllib.error.URLError) or isinstance(exc, OSError):
        kind = "network_error"
    elif "malformed" in str(exc).lower() or "json" in str(exc).lower():
        kind = "malformed_response"
    elif "partial" in str(exc).lower():
        kind = "partial_response"
    elif "schema" in str(exc).lower():
        kind = "provider_schema_drift"
    else:
        kind = "unknown"
    retryability, error_kind = _FAILURES[kind]
    return {"failure_type": kind, "retryability": retryability, "ledger_error_kind": error_kind, "fail_closed": True}


def _profile(policy: dict[str, Any], handoff: dict[str, Any], profile: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in (policy, handoff, profile or {}):
        if isinstance(source, dict):
            merged.update(source)
            if isinstance(source.get("provider_profile"), dict):
                merged.update(source["provider_profile"])
    return merged


def _validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    env_names = _env_names(profile)
    endpoint = str(profile.get("endpoint") or profile.get("provider_url") or "")
    provider_id = str(profile.get("provider_id") or profile.get("provider_name") or profile.get("provider") or "")
    model_name = str(profile.get("model_name") or profile.get("model") or "")
    timeout = int(profile.get("timeout_seconds") or profile.get("timeout") or 60)
    retry_limit = int(profile.get("retry_limit") or profile.get("retries") or 0)
    response_contract = str(profile.get("response_contract") or "generated_segment_json")
    blockers: list[str] = []
    warnings: list[str] = []
    if not provider_id:
        blockers.append("provider_id_missing")
    if not model_name:
        blockers.append("model_name_missing")
    if timeout <= 0:
        blockers.append("timeout_invalid")
    if retry_limit < 0:
        blockers.append("retry_limit_invalid")
    if not env_names and bool(profile.get("requires_credentials", True)):
        warnings.append("credential_environment_variable_not_declared")
    return {
        "provider_profile": {
            "provider_id": provider_id,
            "endpoint_shape": {"configured": bool(endpoint), "scheme": urllib.parse.urlparse(endpoint).scheme},
            "model_name_present": bool(model_name),
            "timeout_seconds": timeout,
            "retry_limit": retry_limit,
            "response_contract": response_contract,
            "allowed_environment_variable_names": env_names,
            "redaction_policy": "env_names_only_no_values",
        },
        "blockers": blockers,
        "warnings": warnings,
    }


def _env_names(profile: dict[str, Any]) -> list[str]:
    raw = profile.get("allowed_environment_variable_names") or profile.get("credential_env_names") or profile.get("credential_env") or profile.get("api_key_env") or []
    if isinstance(raw, str):
        raw = [raw]
    return sorted({str(item).strip() for item in raw if str(item).strip()})


def _existing_names(state_dir: Path, *names: str) -> list[str]:
    return [name for name in names if (state_dir / name).is_file()]


def _json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing provider safety artifact: {path}")
    return read_json(path)
