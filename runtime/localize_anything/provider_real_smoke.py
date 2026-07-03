from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, sha256_file, write_json


PROVIDER_REAL_SMOKE_PLAN_JSON = "provider-real-smoke-plan.json"
PROVIDER_REAL_SMOKE_FIXTURE_MANIFEST_JSON = "provider-real-smoke-fixture-manifest.json"
PROVIDER_REAL_SMOKE_RUNBOOK_MD = "provider-real-smoke-runbook.md"
PROVIDER_REAL_SMOKE_ACCEPTANCE_CRITERIA_JSON = "provider-real-smoke-acceptance-criteria.json"
PROVIDER_REAL_SMOKE_EVIDENCE_TEMPLATE_JSON = "provider-real-smoke-evidence-template.json"
PROVIDER_REAL_SMOKE_SAFETY_CHECKLIST_JSON = "provider-real-smoke-safety-checklist.json"
PROVIDER_REAL_SMOKE_NON_CLAIMS_MD = "provider-real-smoke-non-claims.md"
PROVIDER_REAL_SMOKE_EVIDENCE_REVIEW_JSON = "provider-real-smoke-evidence-review.json"
PROVIDER_REAL_SMOKE_LEDGER_AUDIT_JSON = "provider-real-smoke-ledger-audit.json"
PROVIDER_REAL_SMOKE_ADMISSION_AUDIT_JSON = "provider-real-smoke-admission-audit.json"
PROVIDER_REAL_SMOKE_CLAIM_REVIEW_JSON = "provider-real-smoke-claim-review.json"
PROVIDER_REAL_SMOKE_EXPANSION_DECISION_JSON = "provider-real-smoke-expansion-decision.json"

PROVIDER_REAL_SMOKE_ASSETS = {
    "provider_real_smoke_plan": PROVIDER_REAL_SMOKE_PLAN_JSON,
    "provider_real_smoke_fixture_manifest": PROVIDER_REAL_SMOKE_FIXTURE_MANIFEST_JSON,
    "provider_real_smoke_runbook": PROVIDER_REAL_SMOKE_RUNBOOK_MD,
    "provider_real_smoke_acceptance_criteria": PROVIDER_REAL_SMOKE_ACCEPTANCE_CRITERIA_JSON,
    "provider_real_smoke_evidence_template": PROVIDER_REAL_SMOKE_EVIDENCE_TEMPLATE_JSON,
    "provider_real_smoke_safety_checklist": PROVIDER_REAL_SMOKE_SAFETY_CHECKLIST_JSON,
    "provider_real_smoke_non_claims": PROVIDER_REAL_SMOKE_NON_CLAIMS_MD,
    "provider_real_smoke_evidence_review": PROVIDER_REAL_SMOKE_EVIDENCE_REVIEW_JSON,
    "provider_real_smoke_ledger_audit": PROVIDER_REAL_SMOKE_LEDGER_AUDIT_JSON,
    "provider_real_smoke_admission_audit": PROVIDER_REAL_SMOKE_ADMISSION_AUDIT_JSON,
    "provider_real_smoke_claim_review": PROVIDER_REAL_SMOKE_CLAIM_REVIEW_JSON,
    "provider_real_smoke_expansion_decision": PROVIDER_REAL_SMOKE_EXPANSION_DECISION_JSON,
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

_RAW_LOCAL_ONLY = {
    ".env",
    "provider-network-log.txt",
    "raw-provider-request.json",
    "raw-provider-response.json",
}


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


def build_provider_real_smoke_evidence_review(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    fixture = _optional_json(state_dir / PROVIDER_REAL_SMOKE_FIXTURE_MANIFEST_JSON)
    evidence = _optional_json(state_dir / "provider-real-smoke-evidence.json")
    evidence_source = "provider-real-smoke-evidence.json"
    if not evidence:
        evidence = _optional_json(state_dir / PROVIDER_REAL_SMOKE_EVIDENCE_TEMPLATE_JSON)
        evidence_source = PROVIDER_REAL_SMOKE_EVIDENCE_TEMPLATE_JSON
    chain = {
        "attempt_count": len(_optional_jsonl(state_dir / "provider-execution-attempt-ledger.jsonl")),
        "intake_count": len(_optional_jsonl(state_dir / "provider-result-intake.jsonl")),
        "reconciliation_status": _status(state_dir / "provider-evidence-reconciliation.json"),
        "qa_status": _status(state_dir / "provider-result-qa-report.json"),
        "acceptance_status": _status(state_dir / "provider-result-acceptance-decision.json"),
        "admission_status": _status(state_dir / "provider-result-staging-admission.json"),
    }
    raw_paths = sorted(name for name in _RAW_LOCAL_ONLY if (state_dir / name).exists())
    blockers = []
    if fixture.get("status") != "public_safe" or fixture.get("safe_to_disclose") is not True:
        blockers.append("fixture_not_public_safe")
    if not evidence or evidence.get("status") in {None, "", "unexecuted_template"}:
        blockers.append("sanitized_smoke_evidence_missing")
    if raw_paths:
        blockers.append("raw_local_only_artifact_present_in_review_directory")
    if chain["attempt_count"] == 0:
        blockers.append("attempt_ledger_missing")
    if chain["intake_count"] == 0:
        blockers.append("result_intake_missing")
    for field in ("reconciliation_status", "qa_status", "acceptance_status", "admission_status"):
        if chain[field] in {"missing", "blocked", "failed", "not_run", "not_applicable"}:
            blockers.append(f"{field}_not_clear")
    status = "blocked" if raw_paths else "incomplete" if blockers else "complete"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-real-smoke-evidence-review-v1",
        "artifact": PROVIDER_REAL_SMOKE_EVIDENCE_REVIEW_JSON,
        "status": status,
        "fixture_id": str(fixture.get("fixture_id") or evidence.get("fixture_id") or ""),
        "evidence_source": evidence_source if evidence else "missing",
        "evidence_status": str(evidence.get("status") or "missing"),
        "evidence_chain": chain,
        "raw_local_only_paths_detected": raw_paths,
        "sanitized_evidence_only": not raw_paths,
        "blockers": sorted(set(blockers)),
        "forbidden_claims": FORBIDDEN_CLAIMS,
        "provider_or_model_called_by_runtime": False,
        "target_files_mutated": False,
        "source_artifact_references": _existing_names(state_dir, evidence_source, PROVIDER_REAL_SMOKE_FIXTURE_MANIFEST_JSON, *EVIDENCE_CHAIN),
    }
    if write:
        write_json(state_dir / PROVIDER_REAL_SMOKE_EVIDENCE_REVIEW_JSON, report)
    return report


def build_provider_real_smoke_ledger_audit(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    ledger = _optional_jsonl(state_dir / "provider-execution-attempt-ledger.jsonl")
    intake = {str(item.get("result_id") or ""): item for item in _optional_jsonl(state_dir / "provider-result-intake.jsonl")}
    items = []
    for attempt in ledger:
        result_id = str(attempt.get("result_id") or "")
        record = intake.get(result_id, {})
        provenance = attempt.get("provenance") if isinstance(attempt.get("provenance"), dict) else {}
        source = str(record.get("result_source") or provenance.get("result_source") or "")
        attempt_type = str(attempt.get("attempt_type") or "")
        issues = []
        expected = _expected_attempt_semantics(source)
        if expected and attempt_type != expected:
            issues.append(f"attempt_type_{attempt_type or 'missing'}_does_not_match_{expected}")
        if source == "real_provider" and attempt_type == "external_result_import":
            issues.append("real_provider_execution_mislabeled_as_external_import")
        if attempt.get("result_state") == "success" and not result_id:
            issues.append("success_attempt_missing_result_id")
        if source == "real_provider" and (
            attempt.get("authorization_status") != "authorized" or attempt.get("preflight_status") != "authorized"
        ):
            issues.append("real_provider_attempt_not_bound_to_authorized_preflight")
        items.append({
            "attempt_id": str(attempt.get("attempt_id") or ""),
            "result_id": result_id,
            "result_source": source or "unknown",
            "recorded_attempt_type": attempt_type or "missing",
            "expected_semantic_type": expected or "unknown",
            "status": "semantic_mismatch" if issues else "consistent",
            "issues": sorted(set(issues)),
        })
    mismatches = [item for item in items if item["issues"]]
    status = "not_run" if not items else "semantic_mismatch" if mismatches else "consistent"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-real-smoke-ledger-audit-v1",
        "artifact": PROVIDER_REAL_SMOKE_LEDGER_AUDIT_JSON,
        "status": status,
        "items": items,
        "summary": {"attempt_count": len(items), "semantic_mismatch_count": len(mismatches)},
        "ledger_is_execution_evidence_not_quality_evidence": True,
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": _existing_names(state_dir, "provider-execution-attempt-ledger.jsonl", "provider-result-intake.jsonl"),
    }
    if write:
        write_json(state_dir / PROVIDER_REAL_SMOKE_LEDGER_AUDIT_JSON, report)
    return report


def build_provider_real_smoke_admission_audit(
    state_dir: Path,
    ledger_audit: dict[str, Any] | None = None,
    *,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    ledger_audit = ledger_audit or build_provider_real_smoke_ledger_audit(state_dir, write=write)
    admission = _optional_json(state_dir / "provider-result-staging-admission.json")
    mismatched = {str(item.get("result_id") or "") for item in ledger_audit.get("items", []) if item.get("issues")}
    items = []
    for item in admission.get("items", []):
        result_id = str(item.get("result_id") or "")
        issues = []
        if item.get("admitted") and result_id in mismatched:
            issues.append("admitted_result_has_ambiguous_attempt_semantics")
        if item.get("admitted") and item.get("blockers"):
            issues.append("admitted_result_retains_blockers")
        if not item.get("admitted") and item.get("decision") == "admitted":
            issues.append("admission_flag_and_decision_disagree")
        items.append({
            "result_id": result_id,
            "recorded_decision": str(item.get("decision") or "missing"),
            "admitted": bool(item.get("admitted")),
            "status": "review_required" if issues else "consistent",
            "issues": issues,
        })
    issues = [issue for item in items for issue in item["issues"]]
    status = "not_run" if not admission else "review_required" if issues else "consistent"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-real-smoke-admission-audit-v1",
        "artifact": PROVIDER_REAL_SMOKE_ADMISSION_AUDIT_JSON,
        "status": status,
        "items": items,
        "summary": {"result_count": len(items), "review_required_count": sum(bool(item["issues"]) for item in items)},
        "staging_admission_does_not_imply_provider_backed_quality": True,
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": _existing_names(state_dir, "provider-result-staging-admission.json", PROVIDER_REAL_SMOKE_LEDGER_AUDIT_JSON),
    }
    if write:
        write_json(state_dir / PROVIDER_REAL_SMOKE_ADMISSION_AUDIT_JSON, report)
    return report


def build_provider_real_smoke_claim_review(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    claim_support = _optional_json(state_dir / "provider-claim-support-report.json")
    staging_boundary = _optional_json(state_dir / "provider-staging-claim-boundary.json")
    supported = {
        str(item.get("claim") or "")
        for item in claim_support.get("supported_claims", [])
        if isinstance(item, dict)
    }
    unsafe_supported = sorted(supported.intersection(FORBIDDEN_CLAIMS))
    forbidden = sorted(set(FORBIDDEN_CLAIMS).union(claim_support.get("forbidden_claims", [])).union(staging_boundary.get("forbidden_claims", [])))
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-real-smoke-claim-review-v1",
        "artifact": PROVIDER_REAL_SMOKE_CLAIM_REVIEW_JSON,
        "status": "claim_conflict" if unsafe_supported else "non_claims_preserved",
        "supported_claims_reviewed": sorted(supported),
        "unsafe_supported_claims": unsafe_supported,
        "forbidden_claims": forbidden,
        "smoke_success_supports_provider_backed_quality": False,
        "limited_scope_becomes_global_readiness": False,
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": _existing_names(state_dir, "provider-claim-support-report.json", "provider-staging-claim-boundary.json", PROVIDER_REAL_SMOKE_NON_CLAIMS_MD),
    }
    if write:
        write_json(state_dir / PROVIDER_REAL_SMOKE_CLAIM_REVIEW_JSON, report)
    return report


def build_provider_real_smoke_expansion_decision(
    state_dir: Path,
    evidence_review: dict[str, Any] | None = None,
    ledger_audit: dict[str, Any] | None = None,
    admission_audit: dict[str, Any] | None = None,
    claim_review: dict[str, Any] | None = None,
    *,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    evidence_review = evidence_review or build_provider_real_smoke_evidence_review(state_dir, write=write)
    ledger_audit = ledger_audit or build_provider_real_smoke_ledger_audit(state_dir, write=write)
    admission_audit = admission_audit or build_provider_real_smoke_admission_audit(state_dir, ledger_audit, write=write)
    claim_review = claim_review or build_provider_real_smoke_claim_review(state_dir, write=write)
    blockers = []
    if evidence_review.get("status") != "complete":
        blockers.append("smoke_evidence_review_not_complete")
    if ledger_audit.get("status") != "consistent":
        blockers.append("attempt_ledger_semantics_not_consistent")
    if admission_audit.get("status") != "consistent":
        blockers.append("staging_admission_audit_not_consistent")
    if claim_review.get("status") != "non_claims_preserved":
        blockers.append("smoke_claim_boundary_conflict")
    decision = "review_before_expansion" if not blockers else "do_not_expand"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-real-smoke-expansion-decision-v1",
        "artifact": PROVIDER_REAL_SMOKE_EXPANSION_DECISION_JSON,
        "status": decision,
        "provider_scope_expansion_authorized": False,
        "new_provider_execution_authorized": False,
        "blockers": blockers,
        "required_follow_up": ["explicit human scope decision is required before any new provider run"] if not blockers else ["resolve all smoke evidence audit blockers before considering another run"],
        "forbidden_claims": claim_review.get("forbidden_claims", FORBIDDEN_CLAIMS),
        "provider_or_model_called_by_runtime": False,
        "target_files_mutated": False,
        "source_artifact_references": [PROVIDER_REAL_SMOKE_EVIDENCE_REVIEW_JSON, PROVIDER_REAL_SMOKE_LEDGER_AUDIT_JSON, PROVIDER_REAL_SMOKE_ADMISSION_AUDIT_JSON, PROVIDER_REAL_SMOKE_CLAIM_REVIEW_JSON],
    }
    if write:
        write_json(state_dir / PROVIDER_REAL_SMOKE_EXPANSION_DECISION_JSON, report)
    return report


def build_provider_real_smoke_review_artifacts(state_dir: Path) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    evidence = build_provider_real_smoke_evidence_review(state_dir)
    ledger = build_provider_real_smoke_ledger_audit(state_dir)
    admission = build_provider_real_smoke_admission_audit(state_dir, ledger)
    claims = build_provider_real_smoke_claim_review(state_dir)
    expansion = build_provider_real_smoke_expansion_decision(state_dir, evidence, ledger, admission, claims)
    return {
        "provider_real_smoke_evidence_review": evidence,
        "provider_real_smoke_ledger_audit": ledger,
        "provider_real_smoke_admission_audit": admission,
        "provider_real_smoke_claim_review": claims,
        "provider_real_smoke_expansion_decision": expansion,
        "provider_or_model_called_by_runtime": False,
    }


def read_provider_real_smoke_artifact(state_dir: Path, name: str) -> dict[str, Any]:
    filename = PROVIDER_REAL_SMOKE_ASSETS.get(name)
    if not filename or not filename.endswith(".json"):
        raise ValueError(f"unknown provider real smoke JSON artifact: {name}")
    return _required_json(state_dir / filename)


def provider_real_smoke_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in PROVIDER_REAL_SMOKE_ASSETS.items() if (state_dir / name).is_file()}


def _optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _optional_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.is_file() else []


def _status(path: Path) -> str:
    return str(_optional_json(path).get("status") or "missing")


def _existing_names(state_dir: Path, *names: str) -> list[str]:
    return [name for name in names if name and (state_dir / name).is_file()]


def _expected_attempt_semantics(source: str) -> str:
    return {
        "real_provider": "real_provider_execution",
        "external_provider_result": "external_result_import",
        "mock": "mock_execution",
        "synthetic": "mock_execution",
        "dry_run": "dry_run_only",
        "skipped": "skipped",
    }.get(source, "")


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"artifact not found: {path.name}")
    return read_json(path)
