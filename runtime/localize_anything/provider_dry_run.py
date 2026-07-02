from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, sha256_file, write_json
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


PROVIDER_DRY_RUN_PLAN_JSON = "provider-dry-run-plan.json"
PROVIDER_EXECUTION_CONSENT_REQUEST_MD = "provider-execution-consent-request.md"
PROVIDER_EXECUTION_CONSENT_STATE_JSON = "provider-execution-consent-state.json"
PROVIDER_DATA_DISCLOSURE_REPORT_JSON = "provider-data-disclosure-report.json"
PROVIDER_RESULT_ACCEPTANCE_POLICY_JSON = "provider-result-acceptance-policy.json"
PROVIDER_REAL_EXECUTION_BLOCKERS_JSON = "provider-real-execution-blockers.json"

PROVIDER_DRY_RUN_ASSETS = {
    "provider_dry_run_plan": PROVIDER_DRY_RUN_PLAN_JSON,
    "provider_execution_consent_request": PROVIDER_EXECUTION_CONSENT_REQUEST_MD,
    "provider_execution_consent_state": PROVIDER_EXECUTION_CONSENT_STATE_JSON,
    "provider_data_disclosure_report": PROVIDER_DATA_DISCLOSURE_REPORT_JSON,
    "provider_result_acceptance_policy": PROVIDER_RESULT_ACCEPTANCE_POLICY_JSON,
    "provider_real_execution_blockers": PROVIDER_REAL_EXECUTION_BLOCKERS_JSON,
}

CONSENT_STATUSES = {"not_requested", "pending", "granted", "denied", "expired", "revoked"}


def build_provider_dry_run_artifacts(
    state_dir: Path,
    profile: dict[str, Any] | None = None,
    *,
    consent: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    plan = build_provider_dry_run_plan(state_dir, profile, run_id=run_id, write=write)
    disclosure = build_provider_data_disclosure_report(state_dir, plan, run_id=run_id, write=write)
    acceptance = build_provider_result_acceptance_policy(state_dir, plan, run_id=run_id, write=write)
    consent_state = build_provider_execution_consent_state(state_dir, consent, plan, run_id=run_id, write=write)
    consent_request = build_provider_execution_consent_request(state_dir, plan, disclosure, consent_state, run_id=run_id, write=write)
    blockers = build_provider_real_execution_blockers(state_dir, plan, consent_state, disclosure, acceptance, run_id=run_id, write=write)
    return {
        "provider_dry_run_plan": plan,
        "provider_execution_consent_request": consent_request,
        "provider_execution_consent_state": consent_state,
        "provider_data_disclosure_report": disclosure,
        "provider_result_acceptance_policy": acceptance,
        "provider_real_execution_blockers": blockers,
        "provider_or_model_called": False,
    }


def build_provider_dry_run_plan(
    state_dir: Path,
    profile: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    policy = _json(state_dir / PROVIDER_EXECUTION_POLICY_JSON)
    handoff = _json(state_dir / PROVIDER_HANDOFF_REQUEST_JSON)
    credential = _json(state_dir / PROVIDER_CREDENTIAL_POLICY_REPORT_JSON)
    network = _json(state_dir / PROVIDER_NETWORK_BOUNDARY_REPORT_JSON)
    redaction = _json(state_dir / PROVIDER_REDACTION_AUDIT_JSON)
    safety = _json(state_dir / PROVIDER_EXECUTION_SAFETY_DECISION_JSON)
    merged = _merge_profile(policy, handoff, profile)
    scope = _scope_summary(state_dir, handoff)
    plan = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-dry-run-plan-v1",
        "artifact": PROVIDER_DRY_RUN_PLAN_JSON,
        "run_id": run_id or policy.get("run_id") or handoff.get("run_id"),
        "status": "blocked" if _dry_run_blockers(policy, handoff, credential, network, redaction, safety) else "dry_run_ready",
        "execution_mode": str(policy.get("execution_mode") or handoff.get("execution_mode") or "disabled"),
        "dry_run_only": True,
        "real_provider_execution_enabled": False,
        "provider_profile": {
            "provider_id": str(merged.get("provider_id") or merged.get("provider_name") or merged.get("provider") or ""),
            "provider_name": str(merged.get("provider_name") or merged.get("provider") or ""),
            "profile_id": str(merged.get("provider_profile") or merged.get("provider_profile_id") or merged.get("profile_id") or ""),
            "model_name": str(merged.get("model_name") or merged.get("model") or ""),
            "endpoint_configured": bool(merged.get("endpoint") or merged.get("provider_url")),
        },
        "target_locale": str(merged.get("target_locale") or handoff.get("target_locale") or scope.get("target_locale") or ""),
        "source_files": scope["source_files"],
        "batch_count": scope["batch_count"],
        "segment_count": scope["segment_count"],
        "approximate_character_count": scope["character_count"],
        "credential_status": credential.get("status", "missing"),
        "credential_sources": _credential_sources(credential),
        "network_boundary_status": network.get("status", "missing"),
        "redaction_status": redaction.get("status", "missing"),
        "retry_policy": {
            "timeout_seconds": int(merged.get("timeout_seconds") or merged.get("timeout") or 60),
            "retry_limit": int(merged.get("retry_limit") or merged.get("retries") or 0),
        },
        "failure_policy": {
            "fail_closed": True,
            "malformed_or_partial_response_blocks_claims": True,
            "provider_failed_output_is_not_provider_backed": True,
        },
        "claim_boundary_after_execution": {
            "forbidden_claims": sorted(PROVIDER_FORBIDDEN_CLAIMS),
            "provider_backed_quality_supported": False,
            "provider_execution_complete_supported": False,
        },
        "required_user_confirmation": "explicit scoped consent bound to run_id/provider/model/locale/source_hash/batch_set",
        "blockers": _dry_run_blockers(policy, handoff, credential, network, redaction, safety),
        "source_hashes": _source_hashes(state_dir),
        "source_artifact_references": _existing_names(
            state_dir,
            PROVIDER_EXECUTION_POLICY_JSON,
            PROVIDER_HANDOFF_REQUEST_JSON,
            PROVIDER_CREDENTIAL_POLICY_REPORT_JSON,
            PROVIDER_NETWORK_BOUNDARY_REPORT_JSON,
            PROVIDER_REDACTION_AUDIT_JSON,
            PROVIDER_EXECUTION_SAFETY_DECISION_JSON,
        ),
        "provider_or_model_called": False,
        "limitations": ["dry-run is not execution and cannot support provider-backed quality"],
    }
    plan["plan_hash"] = _stable_hash({key: value for key, value in plan.items() if key != "plan_hash"})
    if write:
        write_json(state_dir / PROVIDER_DRY_RUN_PLAN_JSON, plan)
    return plan


def build_provider_execution_consent_request(
    state_dir: Path,
    plan: dict[str, Any] | None = None,
    disclosure: dict[str, Any] | None = None,
    consent_state: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> str:
    state_dir = state_dir.resolve()
    plan = plan or _json(state_dir / PROVIDER_DRY_RUN_PLAN_JSON) or build_provider_dry_run_plan(state_dir, run_id=run_id, write=False)
    disclosure = disclosure or _json(state_dir / PROVIDER_DATA_DISCLOSURE_REPORT_JSON) or build_provider_data_disclosure_report(state_dir, plan, run_id=run_id, write=False)
    consent_state = consent_state or _json(state_dir / PROVIDER_EXECUTION_CONSENT_STATE_JSON) or build_provider_execution_consent_state(state_dir, None, plan, run_id=run_id, write=False)
    profile = plan.get("provider_profile", {})
    lines = [
        "# Provider Execution Consent Request",
        "",
        "Real provider execution is not enabled by this artifact.",
        "",
        f"- provider: {profile.get('provider_id') or profile.get('provider_name') or 'unknown'}",
        f"- model/profile: {profile.get('model_name') or 'unknown'}",
        f"- run id: {plan.get('run_id') or 'unknown'}",
        f"- target locale: {plan.get('target_locale') or 'unknown'}",
        f"- source files: {len(plan.get('source_files') or [])}",
        f"- batches: {plan.get('batch_count', 0)}",
        f"- segments: {plan.get('segment_count', 0)}",
        f"- approximate characters: {plan.get('approximate_character_count', 0)}",
        f"- credential status: {plan.get('credential_status', 'unknown')}",
        f"- network boundary: {plan.get('network_boundary_status', 'unknown')}",
        f"- redaction status: {plan.get('redaction_status', 'unknown')}",
        f"- consent status: {consent_state.get('status', 'pending')}",
        "",
        "Data disclosure summary:",
        f"- categories: {', '.join(disclosure.get('data_categories', [])) or 'none'}",
        f"- private content excerpts included: {str(disclosure.get('full_private_content_included', False)).lower()}",
        "",
        "Before any future real provider call, the user must grant explicit scoped consent for this run, provider, model/profile, locale, source hash, and batch set.",
        "Execution may create privacy, cost, provider-terms, and quality risks. Provider-backed quality still requires result intake, reconciliation, QA, scoped review, acceptance, signoff, and release-audit compatibility.",
        "",
        "Example future action:",
        "`provider-execution-consent-state <state_dir> --input consent.json`",
    ]
    text = "\n".join(lines) + "\n"
    if write:
        (state_dir / PROVIDER_EXECUTION_CONSENT_REQUEST_MD).write_text(text, encoding="utf-8")
    return text


def build_provider_execution_consent_state(
    state_dir: Path,
    consent: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    plan = plan or _json(state_dir / PROVIDER_DRY_RUN_PLAN_JSON) or build_provider_dry_run_plan(state_dir, run_id=run_id, write=False)
    existing = _json(state_dir / PROVIDER_EXECUTION_CONSENT_STATE_JSON)
    payload = consent if consent is not None else existing
    requested = str(payload.get("status") or "pending")
    status = requested if requested in CONSENT_STATUSES else "pending"
    scoped = _consent_scope(plan)
    given_scope = payload.get("consent_scope") if isinstance(payload.get("consent_scope"), dict) else {}
    stale = bool(given_scope and given_scope != scoped)
    if stale and status == "granted":
        status = "expired"
    blockers: list[str] = []
    if status != "granted":
        blockers.append("provider_execution_consent_not_granted")
    if stale:
        blockers.append("provider_execution_consent_stale")
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-execution-consent-state-v1",
        "artifact": PROVIDER_EXECUTION_CONSENT_STATE_JSON,
        "run_id": run_id or plan.get("run_id"),
        "status": status,
        "consent_granted": status == "granted" and not stale,
        "consent_scope": scoped,
        "requested_scope_hash": _stable_hash(scoped),
        "provided_scope_hash": _stable_hash(given_scope) if given_scope else "",
        "stale": stale,
        "actor_role": str(payload.get("actor_role") or ""),
        "actor_reference": str(payload.get("actor_reference") or ""),
        "blockers": blockers,
        "provider_or_model_called": False,
        "limitations": ["consent is scoped and does not prove provider-backed quality"],
    }
    if write:
        write_json(state_dir / PROVIDER_EXECUTION_CONSENT_STATE_JSON, record)
    return record


def build_provider_data_disclosure_report(
    state_dir: Path,
    plan: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    plan = plan or _json(state_dir / PROVIDER_DRY_RUN_PLAN_JSON) or build_provider_dry_run_plan(state_dir, run_id=run_id, write=False)
    handoff = _json(state_dir / PROVIDER_HANDOFF_REQUEST_JSON)
    privacy = str(handoff.get("privacy_mode") or handoff.get("privacy_policy") or "")
    blockers: list[str] = []
    if privacy in {"restricted", "local_only", "no_external_provider"}:
        blockers.append("privacy_policy_conflicts_with_external_provider")
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-data-disclosure-report-v1",
        "artifact": PROVIDER_DATA_DISCLOSURE_REPORT_JSON,
        "run_id": run_id or plan.get("run_id"),
        "status": "blocked" if blockers else "summary_only",
        "data_categories": ["source_text", "resource_keys", "locale_metadata", "term_constraints", "style_context"],
        "counts": {
            "source_file_count": len(plan.get("source_files") or []),
            "batch_count": int(plan.get("batch_count") or 0),
            "segment_count": int(plan.get("segment_count") or 0),
            "approximate_character_count": int(plan.get("approximate_character_count") or 0),
        },
        "full_private_content_included": False,
        "content_excerpt_policy": "counts_and_categories_only",
        "privacy_policy": privacy or "unknown",
        "blockers": blockers,
        "source_artifact_references": _existing_names(state_dir, PROVIDER_HANDOFF_REQUEST_JSON, PROVIDER_DRY_RUN_PLAN_JSON),
        "provider_or_model_called": False,
        "limitations": ["disclosure report lists categories and counts, not full private content"],
    }
    if write:
        write_json(state_dir / PROVIDER_DATA_DISCLOSURE_REPORT_JSON, report)
    return report


def build_provider_result_acceptance_policy(
    state_dir: Path,
    plan: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    plan = plan or _json(state_dir / PROVIDER_DRY_RUN_PLAN_JSON) or build_provider_dry_run_plan(state_dir, run_id=run_id, write=False)
    policy = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-result-acceptance-policy-v1",
        "artifact": PROVIDER_RESULT_ACCEPTANCE_POLICY_JSON,
        "run_id": run_id or plan.get("run_id"),
        "status": "active",
        "required_path": [
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
        "provider_backed_quality_supported_by_policy_alone": False,
        "mock_synthetic_dry_run_failed_excluded": True,
        "forbidden_claims_until_accepted": sorted(PROVIDER_FORBIDDEN_CLAIMS),
        "provider_or_model_called": False,
        "limitations": ["acceptance policy is not result acceptance"],
    }
    if write:
        write_json(state_dir / PROVIDER_RESULT_ACCEPTANCE_POLICY_JSON, policy)
    return policy


def build_provider_real_execution_blockers(
    state_dir: Path,
    plan: dict[str, Any] | None = None,
    consent_state: dict[str, Any] | None = None,
    disclosure: dict[str, Any] | None = None,
    acceptance_policy: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    plan = plan or _json(state_dir / PROVIDER_DRY_RUN_PLAN_JSON) or build_provider_dry_run_plan(state_dir, run_id=run_id, write=False)
    consent_state = consent_state or _json(state_dir / PROVIDER_EXECUTION_CONSENT_STATE_JSON) or build_provider_execution_consent_state(state_dir, None, plan, run_id=run_id, write=False)
    disclosure = disclosure or _json(state_dir / PROVIDER_DATA_DISCLOSURE_REPORT_JSON) or build_provider_data_disclosure_report(state_dir, plan, run_id=run_id, write=False)
    safety = _json(state_dir / PROVIDER_EXECUTION_SAFETY_DECISION_JSON)
    blockers = set(plan.get("blockers") or [])
    if consent_state.get("status") != "granted" or consent_state.get("stale"):
        blockers.update(consent_state.get("blockers") or ["provider_execution_consent_not_granted"])
    if disclosure.get("status") == "blocked":
        blockers.update(disclosure.get("blockers") or ["provider_data_disclosure_blocked"])
    if safety and safety.get("status") != "ready_for_future_execution":
        blockers.add("provider_execution_safety_not_clear")
    if plan.get("credential_status") == "missing":
        blockers.add("provider_credentials_missing")
    if plan.get("network_boundary_status") != "explicitly_enabled":
        blockers.add("provider_network_not_explicitly_enabled")
    blockers.add("provider_backed_claims_forbidden_until_result_acceptance")
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-real-execution-blockers-v1",
        "artifact": PROVIDER_REAL_EXECUTION_BLOCKERS_JSON,
        "run_id": run_id or plan.get("run_id"),
        "status": "blocked" if blockers else "clear",
        "blockers": sorted(blockers),
        "forbidden_claims": sorted(PROVIDER_FORBIDDEN_CLAIMS),
        "real_provider_execution_allowed_now": False,
        "provider_backed_quality_supported": False,
        "source_artifact_references": _existing_names(
            state_dir,
            PROVIDER_DRY_RUN_PLAN_JSON,
            PROVIDER_EXECUTION_CONSENT_STATE_JSON,
            PROVIDER_DATA_DISCLOSURE_REPORT_JSON,
            PROVIDER_RESULT_ACCEPTANCE_POLICY_JSON,
            PROVIDER_EXECUTION_SAFETY_DECISION_JSON,
        ),
        "provider_or_model_called": False,
        "limitations": ["blocker report is a safety gate and does not execute providers"],
    }
    if write:
        write_json(state_dir / PROVIDER_REAL_EXECUTION_BLOCKERS_JSON, report)
    return report


def read_provider_dry_run_plan(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_DRY_RUN_PLAN_JSON)


def read_provider_execution_consent_request(state_dir: Path) -> str:
    path = state_dir / PROVIDER_EXECUTION_CONSENT_REQUEST_MD
    if not path.is_file():
        raise ValueError(f"Missing provider dry-run artifact: {path}")
    return path.read_text(encoding="utf-8")


def read_provider_execution_consent_state(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_EXECUTION_CONSENT_STATE_JSON)


def read_provider_data_disclosure_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_DATA_DISCLOSURE_REPORT_JSON)


def read_provider_result_acceptance_policy(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_RESULT_ACCEPTANCE_POLICY_JSON)


def read_provider_real_execution_blockers(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVIDER_REAL_EXECUTION_BLOCKERS_JSON)


def provider_dry_run_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in PROVIDER_DRY_RUN_ASSETS.items() if (state_dir / name).is_file()}


def _dry_run_blockers(
    policy: dict[str, Any],
    handoff: dict[str, Any],
    credential: dict[str, Any],
    network: dict[str, Any],
    redaction: dict[str, Any],
    safety: dict[str, Any],
) -> list[str]:
    blockers: set[str] = set()
    if not policy:
        blockers.add("provider_execution_policy_missing")
    if not handoff:
        blockers.add("provider_handoff_request_missing")
    if policy.get("execution_mode") != "real_provider":
        blockers.add("real_provider_execution_not_enabled")
    if credential.get("status") == "missing":
        blockers.add("provider_credentials_missing")
    if network.get("status") != "explicitly_enabled":
        blockers.add("provider_network_not_explicitly_enabled")
    if redaction.get("status") == "failed":
        blockers.add("provider_redaction_failed")
    if safety and safety.get("status") != "ready_for_future_execution":
        blockers.add("provider_execution_safety_not_clear")
    return sorted(blockers)


def _scope_summary(state_dir: Path, handoff: dict[str, Any]) -> dict[str, Any]:
    scope = handoff.get("scope") if isinstance(handoff.get("scope"), dict) else {}
    source_files = _strings(handoff.get("source_files")) or _strings(scope.get("source_files") or scope.get("files"))
    batches = handoff.get("batches") if isinstance(handoff.get("batches"), list) else []
    segments = handoff.get("segments") if isinstance(handoff.get("segments"), list) else []
    if not segments and (state_dir / "segments.jsonl").is_file():
        segments = read_jsonl(state_dir / "segments.jsonl")
    segment_count = len(segments)
    if not segment_count:
        segment_count = len(_strings(scope.get("segment_ids")))
    char_count = 0
    for segment in segments:
        if isinstance(segment, dict):
            char_count += len(str(segment.get("source_text") or segment.get("text") or ""))
    return {
        "source_files": source_files,
        "target_locale": str(handoff.get("target_locale") or scope.get("target_locale") or ""),
        "batch_count": len(batches) or int(handoff.get("batch_count") or len(_strings(scope.get("batch_ids"))) or 0),
        "segment_count": segment_count or int(handoff.get("segment_count") or 0),
        "character_count": char_count,
    }


def _consent_scope(plan: dict[str, Any]) -> dict[str, Any]:
    profile = plan.get("provider_profile", {}) if isinstance(plan.get("provider_profile"), dict) else {}
    return {
        "run_id": str(plan.get("run_id") or ""),
        "provider_id": str(profile.get("provider_id") or profile.get("provider_name") or ""),
        "model_name": str(profile.get("model_name") or ""),
        "target_locale": str(plan.get("target_locale") or ""),
        "source_hashes": plan.get("source_hashes") or {},
        "batch_count": int(plan.get("batch_count") or 0),
        "segment_count": int(plan.get("segment_count") or 0),
    }


def _source_hashes(state_dir: Path) -> dict[str, str]:
    names = [PROVIDER_EXECUTION_POLICY_JSON, PROVIDER_HANDOFF_REQUEST_JSON, "generation-handoff.json", "generation-handoff-decision.json"]
    return {name: sha256_file(state_dir / name) for name in names if (state_dir / name).is_file()}


def _credential_sources(credential: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"source_type": item.get("source_type", "env"), "source_reference": item.get("source_reference", ""), "present": bool(item.get("present"))}
        for item in credential.get("credential_sources", [])
        if isinstance(item, dict)
    ]


def _merge_profile(*sources: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        merged.update(source)
        if isinstance(source.get("provider_profile"), dict):
            merged.update(source["provider_profile"])
    return merged


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str) and value:
        return [value]
    return []


def _existing_names(state_dir: Path, *names: str) -> list[str]:
    return [name for name in names if (state_dir / name).is_file()]


def _json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing provider dry-run artifact: {path}")
    return read_json(path)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
