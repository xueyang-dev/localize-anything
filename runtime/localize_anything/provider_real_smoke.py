from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, sha256_file, write_json


PROVIDER_REAL_SMOKE_PLAN_JSON = "provider-real-smoke-plan.json"
PROVIDER_REAL_SMOKE_FIXTURE_MANIFEST_JSON = "provider-real-smoke-fixture-manifest.json"
PROVIDER_REAL_SMOKE_RUNBOOK_MD = "provider-real-smoke-runbook.md"
PROVIDER_REAL_SMOKE_ACCEPTANCE_CRITERIA_JSON = "provider-real-smoke-acceptance-criteria.json"
PROVIDER_REAL_SMOKE_EVIDENCE_TEMPLATE_JSON = "provider-real-smoke-evidence-template.json"
PROVIDER_REAL_SMOKE_SAFETY_CHECKLIST_JSON = "provider-real-smoke-safety-checklist.json"
PROVIDER_REAL_SMOKE_NON_CLAIMS_MD = "provider-real-smoke-non-claims.md"

PROVIDER_REAL_SMOKE_ASSETS = {
    "provider_real_smoke_plan": PROVIDER_REAL_SMOKE_PLAN_JSON,
    "provider_real_smoke_fixture_manifest": PROVIDER_REAL_SMOKE_FIXTURE_MANIFEST_JSON,
    "provider_real_smoke_runbook": PROVIDER_REAL_SMOKE_RUNBOOK_MD,
    "provider_real_smoke_acceptance_criteria": PROVIDER_REAL_SMOKE_ACCEPTANCE_CRITERIA_JSON,
    "provider_real_smoke_evidence_template": PROVIDER_REAL_SMOKE_EVIDENCE_TEMPLATE_JSON,
    "provider_real_smoke_safety_checklist": PROVIDER_REAL_SMOKE_SAFETY_CHECKLIST_JSON,
    "provider_real_smoke_non_claims": PROVIDER_REAL_SMOKE_NON_CLAIMS_MD,
}

FORBIDDEN_CLAIMS = [
    "full_product_localization",
    "locale_complete",
    "production_ready",
    "provider_backed_quality",
]

EVIDENCE_CHAIN = [
    "provider-execution-readiness-report.json",
    "provider-credential-policy-report.json",
    "provider-network-boundary-report.json",
    "provider-redaction-audit.json",
    "provider-execution-safety-decision.json",
    "provider-data-disclosure-report.json",
    "provider-consent-actions.jsonl",
    "provider-consent-resolution-report.json",
    "provider-execution-authorization-decision.json",
    "provider-execution-preflight-gate.json",
    "provider-execution-attempt-ledger.jsonl",
    "provider-result-intake.jsonl",
    "provider-evidence-reconciliation.json",
    "provider-result-qa-report.json",
    "provider-result-review-evidence.jsonl",
    "provider-result-acceptance-decision.json",
    "provider-result-staging-admission.json",
    "provider-result-quarantine-report.json",
    "evaluation-scorecard.json",
    "readiness-authorization-matrix.json",
    "release-readiness-audit.json",
]


def build_provider_real_smoke_fixture_manifest(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    fixture = Path(__file__).resolve().parents[2] / "examples" / "quickstart-json" / "locales" / "en-US.json"
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-real-smoke-fixture-manifest-v1",
        "artifact": PROVIDER_REAL_SMOKE_FIXTURE_MANIFEST_JSON,
        "fixture_id": "quickstart-json-provider-smoke-v1",
        "status": "public_safe" if fixture.is_file() else "missing",
        "source_path": "examples/quickstart-json/locales/en-US.json",
        "source_sha256": sha256_file(fixture) if fixture.is_file() else "",
        "source_locale": "en-US",
        "target_locale": "zh-CN",
        "selected_keys": ["menu.start", "menu.welcome"],
        "segment_count": 2,
        "public": True,
        "commercial_or_private_data_included": False,
        "sensitive_data_included": False,
        "safe_to_disclose": True,
        "fixture_content_embedded": False,
        "provider_or_model_called": False,
        "limitations": ["fixture selection is execution-path evidence only, not translation-quality evidence"],
    }
    if write:
        write_json(state_dir / PROVIDER_REAL_SMOKE_FIXTURE_MANIFEST_JSON, manifest)
    return manifest


def build_provider_real_smoke_plan(state_dir: Path, *, run_id: str | None = None, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    fixture = build_provider_real_smoke_fixture_manifest(state_dir, write=write)
    policy = _optional_json(state_dir / "provider-execution-policy.json")
    handoff = _optional_json(state_dir / "provider-handoff-request.json")
    profile_id = str(handoff.get("provider_profile_id") or policy.get("provider_profile_id") or "")
    provider_id = str(policy.get("provider_name") or handoff.get("provider_name") or "")
    model_name = str(policy.get("model_name") or handoff.get("model_name") or "")
    profile_eligible = bool(provider_id and profile_id and model_name and policy.get("execution_mode") == "real_provider")
    plan = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-real-smoke-plan-v1",
        "artifact": PROVIDER_REAL_SMOKE_PLAN_JSON,
        "run_id": run_id or "provider-real-smoke-manual-001",
        "status": "protocol_ready" if fixture["status"] == "public_safe" else "blocked",
        "execution_mode": "manual_local_explicit_outside_ci",
        "execution_performed": False,
        "ci_execution_allowed": False,
        "network_access_performed": False,
        "fixture_id": fixture["fixture_id"],
        "provider_profile": {
            "provider_id": provider_id,
            "profile_id": profile_id,
            "model_name": model_name,
            "eligibility": "eligible_if_current_gates_pass" if profile_eligible else "manual_profile_selection_required",
            "credentials_embedded": False,
        },
        "scope_binding_required": ["run_id", "provider_id", "profile_id", "model_name", "source_locale", "target_locale", "source_hash", "handoff_hash", "batch_ids"],
        "required_evidence": EVIDENCE_CHAIN,
        "optional_rehearsal_evidence": ["provider-mock-evidence-report.json", "provider-mock-claim-boundary.json"],
        "local_only_outputs": ["raw-provider-request.json", "raw-provider-response.json", "provider-network-log.txt", "credential-bearing-environment"],
        "committable_after_sanitization": [PROVIDER_REAL_SMOKE_EVIDENCE_TEMPLATE_JSON, "sanitized-provider-smoke-summary.json"],
        "forbidden_claims": FORBIDDEN_CLAIMS,
        "provider_path_execution_proof_only": True,
        "provider_or_model_called": False,
        "target_files_mutated": False,
        "source_artifact_references": [PROVIDER_REAL_SMOKE_FIXTURE_MANIFEST_JSON, *[name for name in EVIDENCE_CHAIN if (state_dir / name).is_file()]],
    }
    if write:
        write_json(state_dir / PROVIDER_REAL_SMOKE_PLAN_JSON, plan)
    return plan


def build_provider_real_smoke_acceptance_criteria(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    stages = [
        ("pre_execution", ["provider_readiness", "credential_policy", "network_boundary", "redaction_audit", "execution_safety", "data_disclosure", "explicit_scoped_consent", "authorization_gate", "execution_preflight"]),
        ("execution_evidence", ["authorization_bound_attempt_ledger", "result_intake", "evidence_reconciliation"]),
        ("post_execution", ["provider_result_qa", "scoped_review_acceptance", "staging_admission_or_quarantine", "scorecard_readiness_release_propagation"]),
    ]
    criteria = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-real-smoke-acceptance-criteria-v1",
        "artifact": PROVIDER_REAL_SMOKE_ACCEPTANCE_CRITERIA_JSON,
        "status": "defined",
        "criteria": [{"stage": stage, "required_checks": checks, "required": True} for stage, checks in stages],
        "outcomes": {
            "pass": "authorized attempt completed for the exact fixture and all required evidence is current; proves provider-path execution only",
            "partial": "attempt or result exists but review, QA, admission, or downstream evidence remains incomplete or limited",
            "fail": "authorization, safety, execution, provenance, QA, or quarantine policy failed",
        },
        "successful_smoke_supports_provider_backed_quality": False,
        "forbidden_claims": FORBIDDEN_CLAIMS,
        "provider_or_model_called": False,
    }
    if write:
        write_json(state_dir / PROVIDER_REAL_SMOKE_ACCEPTANCE_CRITERIA_JSON, criteria)
    return criteria


def build_provider_real_smoke_evidence_template(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    template = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-real-smoke-evidence-template-v1",
        "artifact": PROVIDER_REAL_SMOKE_EVIDENCE_TEMPLATE_JSON,
        "status": "unexecuted_template",
        "provider_id": "",
        "profile_id": "",
        "model_name": "",
        "run_id": "",
        "fixture_id": "quickstart-json-provider-smoke-v1",
        "source_locale": "en-US",
        "target_locale": "zh-CN",
        "segment_count": 2,
        "authorization_decision": "pending",
        "attempt_state": "no_execution",
        "result_intake_status": "missing",
        "reconciliation_status": "missing",
        "qa_status": "missing",
        "review_acceptance_status": "missing",
        "staging_admission_status": "missing",
        "claim_boundary": {"forbidden_claims": FORBIDDEN_CLAIMS},
        "sanitized_summary": "",
        "local_only_raw_output_path": "",
        "raw_output_committed": False,
        "credentials_recorded": False,
        "provider_or_model_called": False,
    }
    if write:
        write_json(state_dir / PROVIDER_REAL_SMOKE_EVIDENCE_TEMPLATE_JSON, template)
    return template


def build_provider_real_smoke_safety_checklist(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    checks = [
        "no_secrets_in_git",
        "no_raw_provider_output_committed",
        "no_commercial_or_private_data",
        "no_target_project_mutation",
        "no_automatic_apply",
        "explicit_network_opt_in",
        "cost_warning_acknowledged",
        "provider_terms_and_privacy_warning_acknowledged",
        "manual_local_execution_outside_ci",
        "run_and_profile_scope_binding_verified",
    ]
    checklist = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-real-smoke-safety-checklist-v1",
        "artifact": PROVIDER_REAL_SMOKE_SAFETY_CHECKLIST_JSON,
        "status": "manual_confirmation_required",
        "items": [{"check_id": check, "required": True, "confirmed": False} for check in checks],
        "all_confirmed": False,
        "execution_allowed_by_checklist_alone": False,
        "provider_or_model_called": False,
    }
    if write:
        write_json(state_dir / PROVIDER_REAL_SMOKE_SAFETY_CHECKLIST_JSON, checklist)
    return checklist


def build_provider_real_smoke_runbook(state_dir: Path, *, write: bool = True) -> str:
    lines = [
        "# Controlled Real Provider Smoke Runbook",
        "",
        "> Planning artifact only. Do not run this in CI. This builder never calls a provider.",
        "",
        "1. Use only `quickstart-json-provider-smoke-v1` and its two selected public keys.",
        "2. Select a local provider profile; never place credentials in repository files, artifacts, logs, packages, benchmarks, or releases.",
        "3. Review disclosure, redaction, provider terms/privacy, cost, and network opt-in.",
        "4. Record explicit consent bound to run id, provider id, profile/model id, locale, source hash, handoff hash, and batch ids.",
        "5. Require current authorization and preflight evidence before a manual local attempt.",
        "6. Keep raw requests, responses, and network logs local and uncommitted.",
        "7. After execution, record attempt, intake, reconciliation, QA, scoped review/acceptance, and staging admission or quarantine.",
        "8. Recompute scorecard, readiness, and release audit; never infer quality from smoke success.",
        "",
        "Pass proves only that the authorized provider path executed for the tiny fixture. Partial or failed evidence remains quarantined and blocks strong claims.",
    ]
    text = "\n".join(lines) + "\n"
    if write:
        (state_dir / PROVIDER_REAL_SMOKE_RUNBOOK_MD).write_text(text, encoding="utf-8")
    return text


def build_provider_real_smoke_non_claims(state_dir: Path, *, write: bool = True) -> str:
    text = "# Provider Real Smoke Non-Claims\n\nA successful smoke does not establish provider-backed quality, locale completeness, production readiness, or full-product localization. It does not authorize automatic apply or make raw provider output committable.\n"
    if write:
        (state_dir / PROVIDER_REAL_SMOKE_NON_CLAIMS_MD).write_text(text, encoding="utf-8")
    return text


def build_provider_real_smoke_artifacts(state_dir: Path, *, run_id: str | None = None) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    fixture = build_provider_real_smoke_fixture_manifest(state_dir)
    plan = build_provider_real_smoke_plan(state_dir, run_id=run_id)
    criteria = build_provider_real_smoke_acceptance_criteria(state_dir)
    evidence = build_provider_real_smoke_evidence_template(state_dir)
    checklist = build_provider_real_smoke_safety_checklist(state_dir)
    build_provider_real_smoke_runbook(state_dir)
    build_provider_real_smoke_non_claims(state_dir)
    return {"provider_real_smoke_plan": plan, "provider_real_smoke_fixture_manifest": fixture, "provider_real_smoke_acceptance_criteria": criteria, "provider_real_smoke_evidence_template": evidence, "provider_real_smoke_safety_checklist": checklist, "provider_or_model_called": False}


def read_provider_real_smoke_artifact(state_dir: Path, name: str) -> dict[str, Any]:
    filename = PROVIDER_REAL_SMOKE_ASSETS.get(name)
    if not filename or not filename.endswith(".json"):
        raise ValueError(f"unknown provider real smoke JSON artifact: {name}")
    return _required_json(state_dir / filename)


def provider_real_smoke_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in PROVIDER_REAL_SMOKE_ASSETS.items() if (state_dir / name).is_file()}


def _optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"artifact not found: {path.name}")
    return read_json(path)
