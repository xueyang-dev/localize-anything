from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, sha256_file, write_json, write_jsonl
from .provider_dry_run import (
    PROVIDER_DATA_DISCLOSURE_REPORT_JSON,
    PROVIDER_DRY_RUN_PLAN_JSON,
    PROVIDER_REAL_EXECUTION_BLOCKERS_JSON,
)
from .provider_evidence import (
    PROVIDER_EXECUTION_POLICY_JSON,
    PROVIDER_FORBIDDEN_CLAIMS,
    PROVIDER_HANDOFF_REQUEST_JSON,
)
from .provider_safety import (
    PROVIDER_CREDENTIAL_POLICY_REPORT_JSON,
    PROVIDER_EXECUTION_SAFETY_DECISION_JSON,
    PROVIDER_NETWORK_BOUNDARY_REPORT_JSON,
    PROVIDER_REDACTION_AUDIT_JSON,
)


PROVIDER_CONSENT_ACTIONS_JSONL = "provider-consent-actions.jsonl"
PROVIDER_CONSENT_RESOLUTION_REPORT_JSON = "provider-consent-resolution-report.json"
PROVIDER_EXECUTION_AUTHORIZATION_DECISION_JSON = "provider-execution-authorization-decision.json"
PROVIDER_CONSENT_SCOPE_DIFF_JSON = "provider-consent-scope-diff.json"
PROVIDER_EXECUTION_PREFLIGHT_GATE_JSON = "provider-execution-preflight-gate.json"
PROVIDER_CONSENT_AUDIT_LOG_JSONL = "provider-consent-audit-log.jsonl"

PROVIDER_CONSENT_ASSETS = {
    "provider_consent_actions": PROVIDER_CONSENT_ACTIONS_JSONL,
    "provider_consent_resolution_report": PROVIDER_CONSENT_RESOLUTION_REPORT_JSON,
    "provider_execution_authorization_decision": PROVIDER_EXECUTION_AUTHORIZATION_DECISION_JSON,
    "provider_consent_scope_diff": PROVIDER_CONSENT_SCOPE_DIFF_JSON,
    "provider_execution_preflight_gate": PROVIDER_EXECUTION_PREFLIGHT_GATE_JSON,
    "provider_consent_audit_log": PROVIDER_CONSENT_AUDIT_LOG_JSONL,
}

CONSENT_ACTIONS = {"grant", "deny", "revoke", "expire", "confirm_dry_run_only"}
SCOPE_FIELDS = (
    "run_id",
    "provider_id",
    "provider_profile",
    "model_name",
    "source_locale",
    "target_locale",
    "source_hash",
    "handoff_hash",
    "batch_ids",
)
PRIVACY_COMPATIBLE = {
    "approved_external",
    "external_allowed",
    "external_provider_allowed",
    "provider_allowed",
    "public",
    "standard",
}


def record_provider_consent_action(state_dir: Path, action: dict[str, Any]) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    if not isinstance(action, dict):
        raise ValueError("provider consent action must be a JSON object")
    action_name = str(action.get("action") or "")
    if action_name not in CONSENT_ACTIONS:
        raise ValueError(f"action must be one of: {', '.join(sorted(CONSENT_ACTIONS))}")
    actor_role = str(action.get("actor_role") or "").strip()
    actor_reference = str(action.get("actor_reference") or "").strip()
    if not actor_role or not actor_reference:
        raise ValueError("actor_role and actor_reference are required")
    scope = _normalize_scope(action.get("consent_scope"))
    missing = [field for field in SCOPE_FIELDS if not scope.get(field)]
    if missing:
        raise ValueError(f"consent_scope is missing required fields: {', '.join(missing)}")
    expires_at = str(action.get("expires_at") or "")
    if expires_at:
        _parse_time(expires_at)
    identity = {
        "action": action_name,
        "actor_role": actor_role,
        "actor_reference": actor_reference,
        "consent_scope": scope,
        "expires_at": expires_at,
        "rationale": str(action.get("rationale") or ""),
    }
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-consent-action-v1",
        "artifact": PROVIDER_CONSENT_ACTIONS_JSONL,
        "action_id": str(action.get("action_id") or _stable_id("provider-consent", identity)),
        **identity,
        "recorded_at": str(action.get("recorded_at") or _now()),
        "status": "recorded",
        "source_artifact_references": _existing_names(
            state_dir,
            PROVIDER_DRY_RUN_PLAN_JSON,
            PROVIDER_HANDOFF_REQUEST_JSON,
            PROVIDER_DATA_DISCLOSURE_REPORT_JSON,
        ),
        "provider_or_model_called": False,
        "limitations": ["consent action intake does not execute a provider or support provider-backed quality"],
    }
    records = read_provider_consent_actions(state_dir)
    existing = next((item for item in records if item.get("action_id") == record["action_id"]), None)
    if existing:
        return existing
    records.append(record)
    write_jsonl(state_dir / PROVIDER_CONSENT_ACTIONS_JSONL, records)
    build_provider_consent_artifacts(state_dir)
    return record


def read_provider_consent_actions(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / PROVIDER_CONSENT_ACTIONS_JSONL
    return read_jsonl(path) if path.is_file() else []


def build_provider_consent_scope_diff(
    state_dir: Path,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    expected = _expected_scope(state_dir, run_id=run_id)
    actions = read_provider_consent_actions(state_dir)
    latest = actions[-1] if actions else {}
    provided = _normalize_scope(latest.get("consent_scope")) if latest else {}
    differences = []
    for field in SCOPE_FIELDS:
        if expected.get(field) != provided.get(field):
            differences.append(
                {
                    "field": field,
                    "expected": expected.get(field),
                    "provided": provided.get(field),
                    "reason": "stale_evidence" if field in {"source_hash", "handoff_hash"} else "scope_mismatch",
                }
            )
    stale_fields = [item["field"] for item in differences if item["reason"] == "stale_evidence" and item.get("provided")]
    mismatch_fields = [item["field"] for item in differences if item["reason"] == "scope_mismatch" and item.get("provided")]
    missing_fields = [item["field"] for item in differences if not item.get("provided")]
    status = "no_action" if not latest else "incomplete" if missing_fields else "stale" if stale_fields else "scope_mismatch" if mismatch_fields else "exact_match"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-consent-scope-diff-v1",
        "artifact": PROVIDER_CONSENT_SCOPE_DIFF_JSON,
        "run_id": run_id or expected.get("run_id"),
        "status": status,
        "action_id": str(latest.get("action_id") or ""),
        "expected_scope": expected,
        "provided_scope": provided,
        "differences": differences,
        "stale_fields": stale_fields,
        "mismatch_fields": mismatch_fields,
        "missing_fields": missing_fields,
        "exact_match": status == "exact_match",
        "source_artifact_references": _existing_names(state_dir, PROVIDER_CONSENT_ACTIONS_JSONL, PROVIDER_DRY_RUN_PLAN_JSON, PROVIDER_HANDOFF_REQUEST_JSON),
        "provider_or_model_called": False,
    }
    if write:
        write_json(state_dir / PROVIDER_CONSENT_SCOPE_DIFF_JSON, report)
    return report


def read_provider_consent_scope_diff(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_CONSENT_SCOPE_DIFF_JSON)


def build_provider_consent_resolution_report(
    state_dir: Path,
    scope_diff: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    actions = read_provider_consent_actions(state_dir)
    latest = actions[-1] if actions else {}
    scope_diff = scope_diff or build_provider_consent_scope_diff(state_dir, run_id=run_id, write=False)
    action_name = str(latest.get("action") or "")
    blockers: list[str] = []
    if not latest:
        status = "pending"
        blockers.append("provider_consent_action_missing")
    elif scope_diff.get("status") == "stale":
        status = "stale"
        blockers.append("provider_consent_scope_stale")
    elif scope_diff.get("status") != "exact_match":
        status = "scope_mismatch"
        blockers.append("provider_consent_scope_mismatch")
    elif action_name == "grant" and _is_expired(str(latest.get("expires_at") or "")):
        status = "expired"
        blockers.append("provider_consent_expired")
    else:
        status = {
            "grant": "granted",
            "deny": "denied",
            "revoke": "revoked",
            "expire": "expired",
            "confirm_dry_run_only": "dry_run_only",
        }.get(action_name, "pending")
        if status != "granted":
            blockers.append(f"provider_consent_{status}")
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-consent-resolution-report-v1",
        "artifact": PROVIDER_CONSENT_RESOLUTION_REPORT_JSON,
        "run_id": run_id or scope_diff.get("run_id"),
        "status": status,
        "effective_action_id": str(latest.get("action_id") or ""),
        "effective_action": action_name,
        "consent_granted": status == "granted",
        "consent_scope": scope_diff.get("expected_scope", {}),
        "expires_at": str(latest.get("expires_at") or ""),
        "actor_role": str(latest.get("actor_role") or ""),
        "actor_reference": str(latest.get("actor_reference") or ""),
        "blockers": blockers,
        "source_artifact_references": _existing_names(state_dir, PROVIDER_CONSENT_ACTIONS_JSONL, PROVIDER_CONSENT_SCOPE_DIFF_JSON),
        "provider_or_model_called": False,
        "limitations": ["resolved consent does not imply provider-backed quality"],
    }
    if write:
        write_json(state_dir / PROVIDER_CONSENT_RESOLUTION_REPORT_JSON, report)
    return report


def read_provider_consent_resolution_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_CONSENT_RESOLUTION_REPORT_JSON)


def build_provider_execution_authorization_decision(
    state_dir: Path,
    resolution: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    resolution = resolution or build_provider_consent_resolution_report(state_dir, run_id=run_id, write=False)
    policy = _json(state_dir / PROVIDER_EXECUTION_POLICY_JSON)
    handoff = _json(state_dir / PROVIDER_HANDOFF_REQUEST_JSON)
    plan = _json(state_dir / PROVIDER_DRY_RUN_PLAN_JSON)
    disclosure = _json(state_dir / PROVIDER_DATA_DISCLOSURE_REPORT_JSON)
    credential = _json(state_dir / PROVIDER_CREDENTIAL_POLICY_REPORT_JSON)
    network = _json(state_dir / PROVIDER_NETWORK_BOUNDARY_REPORT_JSON)
    redaction = _json(state_dir / PROVIDER_REDACTION_AUDIT_JSON)
    safety = _json(state_dir / PROVIDER_EXECUTION_SAFETY_DECISION_JSON)
    blockers = list(resolution.get("blockers") or [])
    if not policy or policy.get("execution_mode") != "real_provider" or not policy.get("allow_real_provider"):
        blockers.append("real_provider_execution_not_enabled")
    if not handoff:
        blockers.append("provider_handoff_request_missing")
    if not plan or not _plan_hash_current(plan):
        blockers.append("provider_dry_run_plan_missing_or_stale")
    elif (
        plan.get("credential_status") != credential.get("status")
        or plan.get("network_boundary_status") != network.get("status")
        or plan.get("redaction_status") != redaction.get("status")
    ):
        blockers.append("provider_dry_run_plan_stale")
    if credential.get("status") not in {"present", "not_required"}:
        blockers.append("provider_credentials_missing")
    if network.get("status") != "explicitly_enabled":
        blockers.append("provider_network_not_explicitly_enabled")
    if redaction.get("status") != "pass":
        blockers.append("provider_redaction_not_clear")
    if safety.get("status") != "ready_for_future_execution":
        blockers.append("provider_execution_safety_not_clear")
    privacy = str(disclosure.get("privacy_policy") or "")
    if disclosure.get("status") == "blocked" or privacy not in PRIVACY_COMPATIBLE:
        blockers.append("provider_privacy_policy_not_compatible")
    expected_scope = _expected_scope(state_dir, run_id=run_id)
    if any(not expected_scope.get(field) for field in SCOPE_FIELDS):
        blockers.append("provider_execution_scope_incomplete")
    blockers = sorted(set(blockers))
    resolved_status = str(resolution.get("status") or "pending")
    if resolved_status in {"revoked", "expired", "stale", "scope_mismatch", "dry_run_only"}:
        status = resolved_status
    elif resolved_status != "granted" or blockers:
        status = "blocked"
    else:
        status = "authorized"
    decision = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-execution-authorization-decision-v1",
        "artifact": PROVIDER_EXECUTION_AUTHORIZATION_DECISION_JSON,
        "run_id": run_id or expected_scope.get("run_id"),
        "status": status,
        "execution_authorized": status == "authorized",
        "authorization_scope": expected_scope,
        "consent_action_id": str(resolution.get("effective_action_id") or ""),
        "blockers": blockers,
        "forbidden_claims": sorted(PROVIDER_FORBIDDEN_CLAIMS),
        "credential_presence_grants_permission": False,
        "dry_run_readiness_grants_permission": False,
        "provider_backed_quality_supported": False,
        "source_artifact_references": _existing_names(
            state_dir,
            PROVIDER_CONSENT_RESOLUTION_REPORT_JSON,
            PROVIDER_DRY_RUN_PLAN_JSON,
            PROVIDER_DATA_DISCLOSURE_REPORT_JSON,
            PROVIDER_CREDENTIAL_POLICY_REPORT_JSON,
            PROVIDER_NETWORK_BOUNDARY_REPORT_JSON,
            PROVIDER_REDACTION_AUDIT_JSON,
            PROVIDER_EXECUTION_SAFETY_DECISION_JSON,
            PROVIDER_REAL_EXECUTION_BLOCKERS_JSON,
        ),
        "provider_or_model_called": False,
        "limitations": ["execution authorization is not provider execution or provider-backed quality evidence"],
    }
    if write:
        write_json(state_dir / PROVIDER_EXECUTION_AUTHORIZATION_DECISION_JSON, decision)
    return decision


def read_provider_execution_authorization_decision(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_EXECUTION_AUTHORIZATION_DECISION_JSON)


def build_provider_execution_preflight_gate(
    state_dir: Path,
    authorization: dict[str, Any] | None = None,
    *,
    request_context: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    authorization = authorization or build_provider_execution_authorization_decision(state_dir, run_id=run_id, write=False)
    blockers = list(authorization.get("blockers") or [])
    expected = authorization.get("authorization_scope") if isinstance(authorization.get("authorization_scope"), dict) else {}
    request_mismatches = []
    for field, value in (request_context or {}).items():
        if field in SCOPE_FIELDS and value not in (None, "") and _normalized_value(field, value) != expected.get(field):
            request_mismatches.append(field)
    if request_mismatches:
        blockers.append("provider_execution_request_scope_mismatch")
    if authorization.get("status") != "authorized":
        blockers.append("provider_execution_not_authorized")
    blockers = sorted(set(blockers))
    allowed = not blockers and authorization.get("execution_authorized") is True
    gate = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-execution-preflight-gate-v1",
        "artifact": PROVIDER_EXECUTION_PREFLIGHT_GATE_JSON,
        "run_id": run_id or authorization.get("run_id"),
        "status": "authorized" if allowed else str(authorization.get("status") or "blocked") if authorization.get("status") in {"dry_run_only", "revoked", "expired", "stale", "scope_mismatch"} else "blocked",
        "execution_allowed": allowed,
        "fail_closed": True,
        "legacy_and_direct_commands_must_use_gate": True,
        "request_scope_mismatches": request_mismatches,
        "blockers": blockers,
        "forbidden_claims": sorted(PROVIDER_FORBIDDEN_CLAIMS),
        "provider_backed_quality_supported": False,
        "source_artifact_references": _existing_names(state_dir, PROVIDER_EXECUTION_AUTHORIZATION_DECISION_JSON, PROVIDER_CONSENT_RESOLUTION_REPORT_JSON, PROVIDER_CONSENT_SCOPE_DIFF_JSON),
        "provider_or_model_called": False,
    }
    if write:
        write_json(state_dir / PROVIDER_EXECUTION_PREFLIGHT_GATE_JSON, gate)
    return gate


def read_provider_execution_preflight_gate(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_EXECUTION_PREFLIGHT_GATE_JSON)


def build_provider_consent_audit_log(
    state_dir: Path,
    resolution: dict[str, Any] | None = None,
    authorization: dict[str, Any] | None = None,
    *,
    write: bool = True,
) -> list[dict[str, Any]]:
    state_dir = state_dir.resolve()
    resolution = resolution or build_provider_consent_resolution_report(state_dir, write=False)
    authorization = authorization or build_provider_execution_authorization_decision(state_dir, resolution, write=False)
    records = [
        {
            "protocol_version": PROTOCOL_VERSION,
            "schema": "localize-anything-provider-consent-audit-record-v1",
            "artifact": PROVIDER_CONSENT_AUDIT_LOG_JSONL,
            "audit_id": _stable_id("provider-consent-audit", item.get("action_id")),
            "action_id": item.get("action_id"),
            "action": item.get("action"),
            "actor_role": item.get("actor_role"),
            "actor_reference": item.get("actor_reference"),
            "recorded_at": item.get("recorded_at"),
            "consent_scope": item.get("consent_scope", {}),
            "effective_resolution": resolution.get("status") if item.get("action_id") == resolution.get("effective_action_id") else "superseded",
            "execution_authorized": bool(authorization.get("execution_authorized")) and item.get("action_id") == resolution.get("effective_action_id"),
            "provider_or_model_called": False,
        }
        for item in read_provider_consent_actions(state_dir)
    ]
    if write:
        write_jsonl(state_dir / PROVIDER_CONSENT_AUDIT_LOG_JSONL, records)
    return records


def read_provider_consent_audit_log(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / PROVIDER_CONSENT_AUDIT_LOG_JSONL
    return read_jsonl(path) if path.is_file() else []


def build_provider_consent_artifacts(state_dir: Path, *, run_id: str | None = None) -> dict[str, Any]:
    scope_diff = build_provider_consent_scope_diff(state_dir, run_id=run_id)
    resolution = build_provider_consent_resolution_report(state_dir, scope_diff, run_id=run_id)
    authorization = build_provider_execution_authorization_decision(state_dir, resolution, run_id=run_id)
    preflight = build_provider_execution_preflight_gate(state_dir, authorization, run_id=run_id)
    audit = build_provider_consent_audit_log(state_dir, resolution, authorization)
    return {
        "provider_consent_actions": read_provider_consent_actions(state_dir),
        "provider_consent_resolution_report": resolution,
        "provider_execution_authorization_decision": authorization,
        "provider_consent_scope_diff": scope_diff,
        "provider_execution_preflight_gate": preflight,
        "provider_consent_audit_log": audit,
        "provider_or_model_called": False,
    }


def provider_execution_preflight_blocker(
    state_dir: Path | None,
    *,
    request_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if state_dir is None:
        return {"category": "provider_execution_authorization", "message": "Provider execution requires --state-dir and a current authorization gate."}
    gate = build_provider_execution_preflight_gate(state_dir, request_context=request_context)
    if gate.get("execution_allowed") is True:
        return None
    return {
        "category": "provider_execution_authorization",
        "message": "Provider execution blocked: " + ", ".join(gate.get("blockers") or ["authorization_missing"]),
    }


def provider_consent_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in PROVIDER_CONSENT_ASSETS.items() if (state_dir / name).is_file()}


def _expected_scope(state_dir: Path, *, run_id: str | None = None) -> dict[str, Any]:
    policy = _json(state_dir / PROVIDER_EXECUTION_POLICY_JSON)
    handoff = _json(state_dir / PROVIDER_HANDOFF_REQUEST_JSON)
    plan = _json(state_dir / PROVIDER_DRY_RUN_PLAN_JSON)
    brief = _json(state_dir / "localization-brief.json")
    profile: dict[str, Any] = {}
    for source in (policy, handoff, plan.get("provider_profile", {})):
        if isinstance(source, dict):
            profile.update(source)
            if isinstance(source.get("provider_profile"), dict):
                profile.update(source["provider_profile"])
    scope = handoff.get("scope") if isinstance(handoff.get("scope"), dict) else {}
    batches = handoff.get("batches") if isinstance(handoff.get("batches"), list) else []
    batch_ids = sorted(
        set(
            [str(item.get("batch_id") or "") for item in batches if isinstance(item, dict)]
            + [str(item) for item in scope.get("batch_ids", []) if str(item)]
        )
        - {""}
    )
    source_hashes = handoff.get("source_artifact_hashes") if isinstance(handoff.get("source_artifact_hashes"), dict) else {}
    source_hash = str(handoff.get("source_hash") or handoff.get("source_content_hash") or "")
    if not source_hash and source_hashes:
        source_hash = _stable_hash(source_hashes)
    if not source_hash and (state_dir / "current-manifest.json").is_file():
        source_hash = sha256_file(state_dir / "current-manifest.json")
    target_locales = brief.get("target_locales") if isinstance(brief.get("target_locales"), list) else []
    return {
        "run_id": str(run_id or plan.get("run_id") or policy.get("run_id") or handoff.get("run_id") or ""),
        "provider_id": str(profile.get("provider_id") or profile.get("provider_name") or profile.get("provider") or ""),
        "provider_profile": str(profile.get("provider_profile") or profile.get("profile_id") or profile.get("profile_name") or profile.get("provider_profile_id") or ""),
        "model_name": str(profile.get("model_name") or profile.get("model") or ""),
        "source_locale": str(handoff.get("source_locale") or scope.get("source_locale") or brief.get("source_locale") or ""),
        "target_locale": str(handoff.get("target_locale") or scope.get("target_locale") or plan.get("target_locale") or (target_locales[0] if target_locales else "")),
        "source_hash": source_hash,
        "handoff_hash": sha256_file(state_dir / PROVIDER_HANDOFF_REQUEST_JSON) if (state_dir / PROVIDER_HANDOFF_REQUEST_JSON).is_file() else "",
        "batch_ids": batch_ids,
    }


def _normalize_scope(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {field: _normalized_value(field, value.get(field)) for field in SCOPE_FIELDS}


def _normalized_value(field: str, value: Any) -> Any:
    if field == "batch_ids":
        return sorted(set(str(item) for item in value if str(item))) if isinstance(value, list) else []
    return str(value or "")


def _plan_hash_current(plan: dict[str, Any]) -> bool:
    expected = str(plan.get("plan_hash") or "")
    value = {key: item for key, item in plan.items() if key != "plan_hash"}
    actual = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return bool(expected) and expected == actual


def _is_expired(value: str) -> bool:
    return bool(value) and _parse_time(value) <= datetime.now(timezone.utc)


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("expires_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}-{_stable_hash(value)[:16]}"


def _json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing provider consent artifact: {path}")
    return read_json(path)


def _existing_names(state_dir: Path, *names: str) -> list[str]:
    return [name for name in names if (state_dir / name).is_file()]
