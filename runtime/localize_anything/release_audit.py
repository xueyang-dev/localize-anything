from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, write_json


RELEASE_READINESS_AUDIT_JSON = "release-readiness-audit.json"
PUBLIC_CLAIMS_REPORT_MD = "public-claims-report.md"
PUBLIC_CLAIMS_REPORT_JSON = "public-claims-report.json"
NON_CLAIMS_MD = "non-claims.md"
RELEASE_BLOCKERS_JSON = "release-blockers.json"
RELEASE_EVIDENCE_MANIFEST_JSON = "release-evidence-manifest.json"

RELEASE_AUDIT_ASSETS = {
    "release_readiness_audit": RELEASE_READINESS_AUDIT_JSON,
    "public_claims_report": PUBLIC_CLAIMS_REPORT_JSON,
    "public_claims_report_md": PUBLIC_CLAIMS_REPORT_MD,
    "non_claims": NON_CLAIMS_MD,
    "release_blockers": RELEASE_BLOCKERS_JSON,
    "release_evidence_manifest": RELEASE_EVIDENCE_MANIFEST_JSON,
}

PUBLIC_CLAIMS = {
    "artifact_backed_workflow": "safe_public_claim",
    "deterministic_structural_qa": "safe_public_claim",
    "adapter_protocol_baseline": "limited_claim",
    "provider_handoff_contract_seed": "seed_only_claim",
    "provider_safe_mock_harness_seed": "seed_only_claim",
    "provider_execution_hardening_seed": "seed_only_claim",
    "provider_real_execution_dry_run_seed": "seed_only_claim",
    "provider_execution_authorization_gate_seed": "seed_only_claim",
    "benchmark_lab_seed": "seed_only_claim",
    "adapter_support_matrix_seed": "seed_only_claim",
    "adapter_evidence_provenance_seed": "seed_only_claim",
    "translation_provenance_seed": "seed_only_claim",
    "locale_capability_seed": "seed_only_claim",
    "knowledge_audit_seed": "seed_only_claim",
    "document_evidence_seed": "seed_only_claim",
    "provider_backed_quality": "forbidden_claim",
    "knowledge_backed_quality": "forbidden_claim",
    "locale_complete": "forbidden_claim",
    "full_product_localization": "forbidden_claim",
    "production_ready": "forbidden_claim",
    "review_complete": "forbidden_claim",
    "layout_verified": "forbidden_claim",
}

CAPABILITIES = {
    "protocol_runtime_contracts": "stable_baseline",
    "deterministic_structural_qa": "stable_baseline",
    "delivery_package_artifacts": "stable_baseline",
    "provider_execution_evidence": "implemented_seed",
    "provider_safe_mock_harness": "implemented_seed",
    "provider_execution_hardening": "implemented_seed",
    "provider_real_execution_dry_run_boundary": "implemented_seed",
    "provider_execution_authorization_gate": "implemented_seed",
    "knowledge_usage_audit": "implemented_seed",
    "locale_capability_analysis": "implemented_seed",
    "translation_provenance_view": "implemented_seed",
    "benchmark_lab": "implemented_seed",
    "adapter_release_audit": "implemented_seed",
    "adapter_evidence_provenance": "implemented_seed",
    "release_claim_boundary": "implemented_seed",
    "full_rag_generation": "not_started",
    "full_cldr_locale_support": "explicit_non_claim",
    "provider_backed_semantic_quality": "explicit_non_claim",
    "production_ready_localization": "explicit_non_claim",
}

STRONG_CLAIMS = {
    "provider_backed_quality",
    "provider_execution_complete",
    "provider_repair_complete",
    "model_repair_complete",
    "knowledge_backed_quality",
    "knowledge_review_complete",
    "locale_complete",
    "rtl_safe",
    "plural_complete",
    "locale_formatting_complete",
    "full_product_localization",
    "review_complete",
    "delivery_ready",
    "apply_ready",
    "production_ready",
    "layout_verified",
    "benchmark_quality_score",
}

EVIDENCE_FILES = {
    "scorecard": "evaluation-scorecard.json",
    "readiness_matrix": "readiness-authorization-matrix.json",
    "benchmark_claim_boundary": "benchmark-claim-boundary-report.json",
    "benchmark_comparison": "benchmark-comparison-report.json",
    "benchmark_evidence_matrix": "benchmark-evidence-matrix.json",
    "benchmark_dataset_manifest": "benchmark-dataset-manifest.json",
    "benchmark_reference_boundary": "benchmark-reference-boundary-report.json",
    "benchmark_fixture_policy": "benchmark-fixture-policy.json",
    "benchmark_reproducibility": "benchmark-reproducibility-report.json",
    "adapter_support_matrix": "adapter-support-matrix.json",
    "adapter_release_audit": "adapter-release-audit.json",
    "adapter_promotion_decision": "adapter-promotion-decision.json",
    "adapter_regression_evidence": "adapter-regression-evidence-report.json",
    "adapter_evidence_provenance": "adapter-evidence-provenance.json",
    "adapter_fixture_manifest": "adapter-fixture-manifest.json",
    "adapter_regression_check": "adapter-regression-check-report.json",
    "adapter_evidence_gap": "adapter-evidence-gap-report.json",
    "adapter_promotion_readiness": "adapter-promotion-readiness-report.json",
    "translation_claim_provenance": "translation-claim-provenance-report.json",
    "provenance_coverage": "provenance-coverage-report.json",
    "locale_readiness": "locale-readiness-impact.json",
    "provider_reconciliation": "provider-evidence-reconciliation.json",
    "provider_claim_support": "provider-claim-support-report.json",
    "provider_mock_evidence": "provider-mock-evidence-report.json",
    "provider_mock_claim_boundary": "provider-mock-claim-boundary.json",
    "provider_execution_safety": "provider-execution-safety-decision.json",
    "provider_real_execution_blockers": "provider-real-execution-blockers.json",
    "provider_execution_authorization": "provider-execution-authorization-decision.json",
    "provider_execution_preflight_gate": "provider-execution-preflight-gate.json",
    "provider_redaction_audit": "provider-redaction-audit.json",
    "knowledge_assurance": "knowledge-assurance-summary.json",
    "workflow_recovery": "workflow-recovery-result.json",
    "artifact_state": "artifact-state.json",
    "delivery_manifest": "delivery-manifest.json",
    "run_summary": "run-summary.json",
}


def build_release_audit_artifacts(
    state_dir: Path,
    *,
    repo_root: Path | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    manifest = build_release_evidence_manifest(state_dir, repo_root=repo_root, run_id=run_id, write=write)
    claims = build_public_claims_report(state_dir, evidence_manifest=manifest, repo_root=repo_root, run_id=run_id, write=write)
    blockers = build_release_blockers(state_dir, evidence_manifest=manifest, public_claims=claims, run_id=run_id, write=write)
    audit = build_release_readiness_audit(
        state_dir,
        evidence_manifest=manifest,
        public_claims=claims,
        blockers=blockers,
        run_id=run_id,
        write=write,
    )
    non_claims = build_non_claims_report(state_dir, public_claims=claims, run_id=run_id, write=write)
    markdown = build_public_claims_markdown(state_dir, public_claims=claims, audit=audit, run_id=run_id, write=write)
    return {
        "release_readiness_audit": audit,
        "public_claims_report": claims,
        "public_claims_report_md": markdown,
        "non_claims": non_claims,
        "release_blockers": blockers,
        "release_evidence_manifest": manifest,
    }


def build_release_evidence_manifest(
    state_dir: Path,
    *,
    repo_root: Path | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    evidence = {key: _artifact_summary(state_dir / filename) for key, filename in EVIDENCE_FILES.items()}
    docs = _public_doc_evidence(repo_root or state_dir.parent)
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-release-evidence-manifest-v1",
        "artifact": RELEASE_EVIDENCE_MANIFEST_JSON,
        "run_id": run_id or _first_run_id(evidence),
        "status": "ready_with_warnings",
        "evidence": evidence,
        "public_docs": docs,
        "summary": {
            "present_count": sum(1 for item in evidence.values() if item["status"] != "missing"),
            "missing_count": sum(1 for item in evidence.values() if item["status"] == "missing"),
            "stale_count": _stale_count(evidence.get("artifact_state", {}).get("content", {})),
            "risky_public_doc_claim_count": len(docs["risky_claims"]),
        },
        "limitations": [
            "release evidence manifest aggregates artifacts; it does not prove release readiness by itself",
            "missing evidence downgrades public claims instead of passing silently",
        ],
    }
    if write:
        write_json(state_dir / RELEASE_EVIDENCE_MANIFEST_JSON, manifest)
    return manifest


def read_release_evidence_manifest(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / RELEASE_EVIDENCE_MANIFEST_JSON)


def build_public_claims_report(
    state_dir: Path,
    *,
    evidence_manifest: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    evidence_manifest = evidence_manifest or build_release_evidence_manifest(state_dir, repo_root=repo_root, run_id=run_id, write=False)
    forbidden_from_evidence = _forbidden_claims_from_evidence(evidence_manifest)
    claims = []
    for claim, default_classification in sorted(PUBLIC_CLAIMS.items()):
        classification = (
            "forbidden_claim"
            if claim in forbidden_from_evidence or default_classification == "forbidden_claim"
            else default_classification
        )
        claims.append(
            {
                "claim": claim,
                "classification": classification,
                "supported_by": _claim_supporting_evidence(claim, evidence_manifest),
                "blocking_evidence": _claim_blocking_evidence(claim, evidence_manifest, forbidden_from_evidence),
                "limitations": _claim_limitations(claim, classification),
            }
        )
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-public-claims-report-v1",
        "artifact": PUBLIC_CLAIMS_REPORT_JSON,
        "run_id": run_id or evidence_manifest.get("run_id"),
        "status": "blocked" if any(item["classification"] == "forbidden_claim" for item in claims) else "ready_with_warnings",
        "claim_classifications": claims,
        "capability_statuses": [{"capability": key, "status": value} for key, value in sorted(CAPABILITIES.items())],
        "forbidden_claims": sorted(
            {item["claim"] for item in claims if item["classification"] == "forbidden_claim"} | forbidden_from_evidence
        ),
        "limited_claims": sorted(item["claim"] for item in claims if item["classification"] == "limited_claim"),
        "seed_only_claims": sorted(item["claim"] for item in claims if item["classification"] == "seed_only_claim"),
        "unsupported_claims": sorted(item["claim"] for item in claims if item["classification"] == "unsupported_claim"),
        "public_docs_mismatches": evidence_manifest.get("public_docs", {}).get("risky_claims", []),
        "rules": {
            "seed_capability_is_not_stable_feature": True,
            "benchmark_artifact_existence_is_not_quality_proof": True,
            "no_release_or_tag_created_by_this_audit": True,
        },
    }
    if write:
        write_json(state_dir / PUBLIC_CLAIMS_REPORT_JSON, report)
    return report


def read_public_claims_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PUBLIC_CLAIMS_REPORT_JSON)


def build_release_blockers(
    state_dir: Path,
    *,
    evidence_manifest: dict[str, Any] | None = None,
    public_claims: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    evidence_manifest = evidence_manifest or build_release_evidence_manifest(state_dir, run_id=run_id, write=False)
    public_claims = public_claims or build_public_claims_report(state_dir, evidence_manifest=evidence_manifest, run_id=run_id, write=False)
    blockers = _release_blockers(evidence_manifest, public_claims)
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-release-blockers-v1",
        "artifact": RELEASE_BLOCKERS_JSON,
        "run_id": run_id or evidence_manifest.get("run_id"),
        "status": "blocked" if blockers else "clear_with_warnings",
        "blockers": blockers,
        "summary": {
            "blocker_count": len(blockers),
            "blocking_count": sum(1 for item in blockers if item["severity"] == "blocking"),
            "warning_count": sum(1 for item in blockers if item["severity"] == "warning"),
        },
        "release_policy": {
            "release_tag_created": False,
            "release_tag_allowed_by_this_loop": False,
            "real_provider_calls_run": False,
        },
    }
    if write:
        write_json(state_dir / RELEASE_BLOCKERS_JSON, report)
    return report


def read_release_blockers(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / RELEASE_BLOCKERS_JSON)


def build_release_readiness_audit(
    state_dir: Path,
    *,
    evidence_manifest: dict[str, Any] | None = None,
    public_claims: dict[str, Any] | None = None,
    blockers: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    evidence_manifest = evidence_manifest or build_release_evidence_manifest(state_dir, run_id=run_id, write=False)
    public_claims = public_claims or build_public_claims_report(state_dir, evidence_manifest=evidence_manifest, run_id=run_id, write=False)
    blockers = blockers or build_release_blockers(
        state_dir,
        evidence_manifest=evidence_manifest,
        public_claims=public_claims,
        run_id=run_id,
        write=False,
    )
    blocking_count = blockers.get("summary", {}).get("blocking_count", 0)
    audit = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-release-readiness-audit-v1",
        "artifact": RELEASE_READINESS_AUDIT_JSON,
        "run_id": run_id or evidence_manifest.get("run_id"),
        "status": "blocked" if blocking_count else "ready_with_warnings",
        "release_candidate_ready": blocking_count == 0,
        "capability_statuses": public_claims.get("capability_statuses", []),
        "safe_public_claims": _claims_by_class(public_claims, "safe_public_claim"),
        "limited_claims": _claims_by_class(public_claims, "limited_claim"),
        "seed_only_claims": _claims_by_class(public_claims, "seed_only_claim"),
        "experimental_claims": _claims_by_class(public_claims, "experimental_claim"),
        "unsupported_claims": _claims_by_class(public_claims, "unsupported_claim"),
        "forbidden_claims": public_claims.get("forbidden_claims", []),
        "release_blockers": blockers.get("blockers", []),
        "evidence_manifest": RELEASE_EVIDENCE_MANIFEST_JSON,
        "recommended_next_actions": _release_next_actions(blockers, public_claims),
        "safety": {
            "provider_or_model_called": False,
            "release_or_tag_created": False,
            "target_project_files_mutated": False,
        },
    }
    if write:
        write_json(state_dir / RELEASE_READINESS_AUDIT_JSON, audit)
    return audit


def read_release_readiness_audit(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / RELEASE_READINESS_AUDIT_JSON)


def build_public_claims_markdown(
    state_dir: Path,
    *,
    public_claims: dict[str, Any] | None = None,
    audit: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> str:
    public_claims = public_claims or read_public_claims_report(state_dir)
    audit = audit or build_release_readiness_audit(state_dir, public_claims=public_claims, run_id=run_id, write=False)
    lines = [
        "# Public Claims Report",
        "",
        f"Status: `{audit.get('status', 'unknown')}`",
        "",
        "## Safe Claims",
        *_markdown_list(audit.get("safe_public_claims", [])),
        "",
        "## Limited Or Seed Claims",
        *_markdown_list(audit.get("limited_claims", []) + audit.get("seed_only_claims", [])),
        "",
        "## Forbidden Claims",
        *_markdown_list(public_claims.get("forbidden_claims", [])),
        "",
        "## Next Actions",
        *_markdown_list(audit.get("recommended_next_actions", [])),
        "",
    ]
    text = "\n".join(lines)
    if write:
        (state_dir / PUBLIC_CLAIMS_REPORT_MD).write_text(text, encoding="utf-8", newline="\n")
    return text


def build_non_claims_report(
    state_dir: Path,
    *,
    public_claims: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> str:
    public_claims = public_claims or read_public_claims_report(state_dir)
    non_claims = sorted(
        set(public_claims.get("forbidden_claims", []))
        | {"full_cldr_locale_support", "automatic_semantic_quality", "full_rag_generation"}
    )
    lines = [
        "# Non-Claims",
        "",
        "These capabilities must not be advertised as complete or stable for this run:",
        "",
        *_markdown_list(non_claims),
        "",
        "Accepted limitations or seed artifacts do not remove these boundaries without stronger evidence.",
        "",
    ]
    text = "\n".join(lines)
    if write:
        (state_dir / NON_CLAIMS_MD).write_text(text, encoding="utf-8", newline="\n")
    return text


def release_audit_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in RELEASE_AUDIT_ASSETS.items() if (state_dir / name).is_file()}


def _artifact_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": path.name, "status": "missing"}
    content: Any = {}
    if path.suffix == ".json":
        content = read_json(path)
    status = content.get("status") if isinstance(content, dict) else "present"
    return {"path": path.name, "status": status or "present", "content": content if isinstance(content, dict) else {}}


def _public_doc_evidence(repo_root: Path) -> dict[str, Any]:
    docs = [repo_root / "README.md", repo_root / "docs" / "architecture.md", repo_root / "docs" / "architecture-roadmap.md"]
    risky = []
    for path in docs:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        for phrase in [
            "provider-backed quality",
            "knowledge-backed quality",
            "locale-complete",
            "full product localization",
            "production-ready",
            "layout verified",
        ]:
            if phrase in text and not _has_caveat_near(text, phrase):
                risky.append(
                    {
                        "path": path.relative_to(repo_root).as_posix(),
                        "claim": phrase.replace("-", "_").replace(" ", "_"),
                        "reason": "public wording lacks nearby seed/non-claim caveat",
                    }
                )
    return {"checked_paths": [path.relative_to(repo_root).as_posix() for path in docs if path.is_file()], "risky_claims": risky}


def _has_caveat_near(text: str, phrase: str) -> bool:
    index = text.find(phrase)
    window = text[max(0, index - 120) : index + len(phrase) + 120]
    caveats = ["not", "non-claim", "forbid", "unsupported", "seed", "experimental", "future", "without evidence", "cannot"]
    return any(word in window for word in caveats)


def _forbidden_claims_from_evidence(manifest: dict[str, Any]) -> set[str]:
    claims: set[str] = set()
    for item in manifest.get("evidence", {}).values():
        content = item.get("content", {})
        if isinstance(content, dict):
            claims.update(str(value) for value in content.get("forbidden_claims", []) if value)
            claims.update(str(value) for value in content.get("unsupported_claims", []) if value)
            claims.update(str(value) for value in content.get("forbidden_claims_that_prevent_apply", []) if value)
    claims.update(STRONG_CLAIMS & claims)
    return claims


def _claim_supporting_evidence(claim: str, manifest: dict[str, Any]) -> list[str]:
    evidence = []
    files = manifest.get("evidence", {})
    if claim in {"artifact_backed_workflow", "deterministic_structural_qa"} and files.get("scorecard", {}).get("status") != "missing":
        evidence.append("evaluation-scorecard.json")
    if claim == "benchmark_lab_seed" and files.get("benchmark_claim_boundary", {}).get("status") != "missing":
        evidence.append("benchmark-claim-boundary-report.json")
    if claim == "locale_capability_seed" and files.get("locale_readiness", {}).get("status") != "missing":
        evidence.append("locale-readiness-impact.json")
    if claim == "translation_provenance_seed" and files.get("translation_claim_provenance", {}).get("status") != "missing":
        evidence.append("translation-claim-provenance-report.json")
    if claim == "adapter_evidence_provenance_seed" and files.get("adapter_promotion_readiness", {}).get("status") != "missing":
        evidence.append("adapter-promotion-readiness-report.json")
    if claim == "provider_safe_mock_harness_seed" and files.get("provider_mock_evidence", {}).get("status") != "missing":
        evidence.append("provider-mock-evidence-report.json")
    if claim == "provider_execution_hardening_seed" and files.get("provider_execution_safety", {}).get("status") != "missing":
        evidence.append("provider-execution-safety-decision.json")
    if claim == "provider_real_execution_dry_run_seed" and files.get("provider_real_execution_blockers", {}).get("status") != "missing":
        evidence.append("provider-real-execution-blockers.json")
    if claim == "provider_execution_authorization_gate_seed" and files.get("provider_execution_preflight_gate", {}).get("status") != "missing":
        evidence.append("provider-execution-preflight-gate.json")
    return evidence


def _claim_blocking_evidence(claim: str, manifest: dict[str, Any], forbidden: set[str]) -> list[str]:
    blockers = []
    if claim in forbidden or claim in STRONG_CLAIMS:
        for key, item in manifest.get("evidence", {}).items():
            content = item.get("content", {})
            values = []
            if isinstance(content, dict):
                values.extend(content.get("forbidden_claims", []))
                values.extend(content.get("unsupported_claims", []))
            if claim in values:
                blockers.append(item.get("path", key))
    return blockers or (["release policy boundary"] if claim in STRONG_CLAIMS else [])


def _claim_limitations(claim: str, classification: str) -> list[str]:
    if classification == "safe_public_claim":
        return ["claim is limited to released deterministic engineering behavior"]
    if classification == "seed_only_claim":
        return ["seed capability may be described as implemented seed, not stable quality assurance"]
    if classification == "limited_claim":
        return ["claim must preserve documented adapter and scope limits"]
    return ["claim requires stronger evidence before public promotion"]


def _release_blockers(manifest: dict[str, Any], public_claims: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = []
    evidence = manifest.get("evidence", {})
    if evidence.get("benchmark_claim_boundary", {}).get("status") == "missing":
        blockers.append(
            _blocker("benchmark_evidence_missing", "benchmark evidence missing", "warning", "benchmark-claim-boundary-report.json")
        )
    if evidence.get("benchmark_fixture_policy", {}).get("content", {}).get("status") == "blocked":
        blockers.append(
            _blocker("generated_external_file_risk", "benchmark fixture policy blocks committing generated or private benchmark outputs", "blocking", "benchmark-fixture-policy.json")
        )
    if evidence.get("adapter_release_audit", {}).get("content", {}).get("status") == "blocked":
        blockers.append(
            _blocker("unsupported_public_claim", "adapter release audit blocks adapter promotion claims", "blocking", "adapter-release-audit.json", claim="adapter_release_promotion_ready")
        )
    if evidence.get("adapter_promotion_readiness", {}).get("content", {}).get("status") == "blocked":
        blockers.append(
            _blocker(
                "unsupported_public_claim",
                "adapter evidence provenance leaves promotion readiness blocked",
                "blocking",
                "adapter-promotion-readiness-report.json",
                claim="adapter_promotion_readiness",
            )
        )
    if evidence.get("provider_claim_support", {}).get("status") in {"missing", "blocked", "failed", "stale"}:
        blockers.append(
            _blocker("provider_evidence_missing", "provider evidence missing", "blocking", "provider-claim-support-report.json")
        )
    if evidence.get("provider_execution_safety", {}).get("status") in {"blocked", "failed", "stale"}:
        blockers.append(
            _blocker("provider_evidence_missing", "provider execution safety is not clear", "blocking", "provider-execution-safety-decision.json")
        )
    if evidence.get("provider_real_execution_blockers", {}).get("status") in {"blocked", "failed", "stale"}:
        blockers.append(
            _blocker("provider_evidence_missing", "real provider execution blockers remain active", "blocking", "provider-real-execution-blockers.json")
        )
    if evidence.get("provider_execution_preflight_gate", {}).get("status") in {"blocked", "failed", "stale", "revoked", "expired", "scope_mismatch", "dry_run_only"}:
        blockers.append(
            _blocker("provider_execution_not_authorized", "provider execution preflight gate is not authorized", "blocking", "provider-execution-preflight-gate.json")
        )
    if evidence.get("locale_readiness", {}).get("status") in {"missing", "blocked", "review_required", "stale"}:
        blockers.append(
            _blocker("locale_capability_missing", "locale capability missing or downgraded", "blocking", "locale-readiness-impact.json")
        )
    if _stale_count(evidence.get("artifact_state", {}).get("content", {})):
        blockers.append(_blocker("stale_artifacts", "stale artifacts remain", "blocking", "artifact-state.json"))
    if "production_ready" in public_claims.get("forbidden_claims", []) or "review_complete" in public_claims.get("forbidden_claims", []):
        blockers.append(
            _blocker("human_review_missing", "production/review-complete evidence is missing", "blocking", "evaluation-scorecard.json")
        )
    for mismatch in public_claims.get("public_docs_mismatches", []):
        blockers.append(
            _blocker("release_docs_mismatch", f"public docs overclaim {mismatch.get('claim')}", "blocking", mismatch.get("path", "README.md"))
        )
    for claim in public_claims.get("forbidden_claims", []):
        blockers.append(
            _blocker(
                "unsupported_public_claim",
                f"{claim} is not supported for public release",
                "blocking",
                "public-claims-report.json",
                claim=claim,
            )
        )
    return _dedupe_blockers(blockers)


def _blocker(blocker_type: str, message: str, severity: str, artifact: str, *, claim: str | None = None) -> dict[str, Any]:
    return {
        "blocker_id": f"{blocker_type}:{claim or artifact}",
        "blocker_type": blocker_type,
        "severity": severity,
        "message": message,
        "source_artifact": artifact,
        "claim": claim,
    }


def _dedupe_blockers(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for blocker in blockers:
        key = blocker["blocker_id"]
        if key not in seen:
            seen.add(key)
            unique.append(blocker)
    return unique


def _claims_by_class(report: dict[str, Any], classification: str) -> list[str]:
    return sorted(item["claim"] for item in report.get("claim_classifications", []) if item.get("classification") == classification)


def _release_next_actions(blockers: dict[str, Any], public_claims: dict[str, Any]) -> list[str]:
    if blockers.get("blockers"):
        return [
            "remove or caveat unsupported public claims",
            "refresh missing or stale evidence",
            "collect qualified human review before production-ready claims",
        ]
    return ["keep release notes scoped to safe and limited claims", "do not create a tag until a separate release action approves it"]


def _markdown_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["- none"]


def _stale_count(artifact_state: dict[str, Any]) -> int:
    summary = artifact_state.get("summary", {}) if isinstance(artifact_state, dict) else {}
    if "stale_count" in summary:
        return int(summary.get("stale_count") or 0)
    if not isinstance(artifact_state, dict):
        return 0
    return sum(1 for item in artifact_state.get("artifacts", []) if item.get("status") == "stale")


def _first_run_id(evidence: dict[str, dict[str, Any]]) -> str | None:
    for item in evidence.values():
        content = item.get("content", {})
        if isinstance(content, dict) and content.get("run_id"):
            return str(content["run_id"])
    return None


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return read_json(path)
