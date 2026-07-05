from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, write_json
from .provider_attempt_semantics import build_provider_execution_evidence_classification


PROVIDER_SMOKE_CLOSURE_REPORT_JSON = "provider-smoke-closure-report.json"
PROVIDER_SMOKE_RELEASE_BOUNDARY_AUDIT_JSON = "provider-smoke-release-boundary-audit.json"
PROVIDER_SMOKE_EVIDENCE_MANIFEST_JSON = "provider-smoke-evidence-manifest.json"
PROVIDER_SMOKE_REMAINING_BLOCKERS_JSON = "provider-smoke-remaining-blockers.json"
PROVIDER_SMOKE_NEXT_STEP_DECISION_JSON = "provider-smoke-next-step-decision.json"

PROVIDER_SMOKE_CLOSURE_ASSETS = {
    "provider_smoke_closure_report": PROVIDER_SMOKE_CLOSURE_REPORT_JSON,
    "provider_smoke_release_boundary_audit": PROVIDER_SMOKE_RELEASE_BOUNDARY_AUDIT_JSON,
    "provider_smoke_evidence_manifest": PROVIDER_SMOKE_EVIDENCE_MANIFEST_JSON,
    "provider_smoke_remaining_blockers": PROVIDER_SMOKE_REMAINING_BLOCKERS_JSON,
    "provider_smoke_next_step_decision": PROVIDER_SMOKE_NEXT_STEP_DECISION_JSON,
}

FORBIDDEN_CLAIMS = {
    "full_product_localization",
    "locale_complete",
    "production_ready",
    "provider_backed_quality",
}

SAFE_EVIDENCE_FILES = (
    "provider-real-smoke-evidence.json",
    "provider-real-smoke-summary.md",
    "provider-real-smoke-sanitized-result.json",
    "provider-real-smoke-claim-boundary.json",
    "provider-real-smoke-followup-actions.json",
)


def build_provider_smoke_evidence_manifest(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    evidence = _optional_json(state_dir / "provider-real-smoke-evidence.json")
    classification = build_provider_execution_evidence_classification(state_dir, write=write)
    acceptance = _optional_json(state_dir / "provider-result-acceptance-decision.json")
    reconciliation = _optional_json(state_dir / "provider-evidence-reconciliation.json")
    qa = _optional_json(state_dir / "provider-result-qa-report.json")
    admission = _optional_json(state_dir / "provider-result-staging-admission.json")
    claim_review = _optional_json(state_dir / "provider-real-smoke-claim-review.json")
    manual = next(
        (
            item
            for item in classification.get("classifications", [])
            if item.get("attempt_type") == "manual_controlled_real_provider_smoke"
        ),
        {},
    )
    sanitized_status = _sanitized_status(evidence)
    acceptance_status = str(evidence.get("acceptance_status") or acceptance.get("status") or "missing")
    gate_summary = {
        "intake": str(evidence.get("intake_status") or "missing"),
        "reconciliation": str(evidence.get("reconciliation_status") or reconciliation.get("status") or "missing"),
        "qa": str(evidence.get("qa_status") or qa.get("status") or "missing"),
        "acceptance": acceptance_status,
        "staging_admission": str(evidence.get("staging_admission_status") or admission.get("status") or "missing"),
    }
    forbidden = set(FORBIDDEN_CLAIMS)
    forbidden.update(classification.get("forbidden_claims", []))
    forbidden.update(claim_review.get("forbidden_claims", []))
    complete = bool(
        evidence
        and manual.get("provider_path_smoke_supported")
        and sanitized_status == "safe"
        and acceptance_status == "accepted_with_limitations"
        and gate_summary["reconciliation"] == "clear"
        and gate_summary["qa"] == "passed"
        and gate_summary["staging_admission"] == "admitted"
    )
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-smoke-evidence-manifest-v1",
        "artifact": PROVIDER_SMOKE_EVIDENCE_MANIFEST_JSON,
        "status": "complete_with_limitations" if complete else "unsafe" if sanitized_status == "unsafe" else "incomplete",
        "provider_id": str(evidence.get("provider_id") or ""),
        "provider_profile": str(evidence.get("provider_profile") or ""),
        "model_name": str(evidence.get("model_name") or ""),
        "run_id": str(evidence.get("run_id") or ""),
        "fixture_id": str(evidence.get("fixture_id") or ""),
        "source_locale": str(evidence.get("source_locale") or ""),
        "target_locale": str(evidence.get("target_locale") or ""),
        "segment_count": int(evidence.get("segment_count") or 0),
        "attempt_type": str(manual.get("attempt_type") or "missing"),
        "evidence_class": str(manual.get("evidence_class") or "missing"),
        "gate_summary": gate_summary,
        "accepted_with_limitations": acceptance_status == "accepted_with_limitations",
        "raw_output_policy": {
            "local_only": evidence.get("raw_output_local_only") is True,
            "committed": evidence.get("raw_output_committed") is True,
            "referenced_by_manifest": False,
        },
        "sanitized_evidence_status": sanitized_status,
        "sanitized_artifact_references": _existing_names(state_dir, *SAFE_EVIDENCE_FILES) if sanitized_status == "safe" else [],
        "claim_boundary": {
            "provider_path_smoke_supported": classification.get("provider_path_smoke_supported") is True,
            "runtime_real_provider_execution_available": classification.get("runtime_real_provider_execution_available") is True,
            "provider_backed_quality_supported": False,
            "benchmark_expansion_allowed": False,
            "forbidden_claims": sorted(forbidden),
        },
        "provider_or_model_called_by_runtime": False,
        "historical_manual_provider_call_recorded": evidence.get("real_provider_call_executed") is True,
        "target_files_mutated": False,
        "source_artifact_references": _existing_names(
            state_dir,
            "provider-real-smoke-evidence.json",
            "provider-execution-evidence-classification.json",
            "provider-result-acceptance-decision.json",
            "provider-evidence-reconciliation.json",
            "provider-result-qa-report.json",
            "provider-result-staging-admission.json",
            "provider-real-smoke-claim-review.json",
        ),
    }
    if write:
        write_json(state_dir / PROVIDER_SMOKE_EVIDENCE_MANIFEST_JSON, manifest)
    return manifest


def build_provider_smoke_release_boundary_audit(
    state_dir: Path,
    manifest: dict[str, Any] | None = None,
    *,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    manifest = manifest or build_provider_smoke_evidence_manifest(state_dir, write=write)
    forbidden = sorted(set(FORBIDDEN_CLAIMS).union(manifest.get("claim_boundary", {}).get("forbidden_claims", [])))
    preserved = all(claim in forbidden for claim in FORBIDDEN_CLAIMS)
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-smoke-release-boundary-audit-v1",
        "artifact": PROVIDER_SMOKE_RELEASE_BOUNDARY_AUDIT_JSON,
        "status": "limited_boundary_preserved" if preserved else "claim_boundary_conflict",
        "provider_path_evidence_only": True,
        "provider_backed_quality_supported": False,
        "production_ready_supported": False,
        "locale_complete_supported": False,
        "full_product_localization_supported": False,
        "runtime_real_provider_execution_available": False,
        "benchmark_evidence_registered": False,
        "benchmark_expansion_allowed": False,
        "release_promotion_allowed": False,
        "readiness_impact": "limited_not_ready",
        "forbidden_claims": forbidden,
        "raw_provider_output_referenced": False,
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": [PROVIDER_SMOKE_EVIDENCE_MANIFEST_JSON, "provider-execution-evidence-classification.json"],
    }
    if write:
        write_json(state_dir / PROVIDER_SMOKE_RELEASE_BOUNDARY_AUDIT_JSON, report)
    return report


def build_provider_smoke_remaining_blockers(
    state_dir: Path,
    manifest: dict[str, Any] | None = None,
    *,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    manifest = manifest or build_provider_smoke_evidence_manifest(state_dir, write=write)
    blocker_ids = [
        "no_independent_semantic_review",
        "only_two_public_fixture_segments",
        "no_benchmark_scale_run",
        "no_provider_reliability_sample",
        "no_runtime_managed_real_execution",
        "no_release_promotion_evidence",
    ]
    if manifest.get("sanitized_evidence_status") != "safe":
        blocker_ids.append("sanitized_smoke_evidence_missing_or_unsafe")
    blockers = [
        {
            "blocker_id": blocker_id,
            "status": "active",
            "blocks": ["provider_backed_quality", "production_ready", "benchmark_expansion", "release_promotion"],
        }
        for blocker_id in blocker_ids
    ]
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-smoke-remaining-blockers-v1",
        "artifact": PROVIDER_SMOKE_REMAINING_BLOCKERS_JSON,
        "status": "blockers_remaining",
        "blockers": blockers,
        "summary": {"active_count": len(blockers)},
        "forbidden_claims": sorted(FORBIDDEN_CLAIMS),
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": [PROVIDER_SMOKE_EVIDENCE_MANIFEST_JSON],
    }
    if write:
        write_json(state_dir / PROVIDER_SMOKE_REMAINING_BLOCKERS_JSON, report)
    return report


def build_provider_smoke_closure_report(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    manifest = build_provider_smoke_evidence_manifest(state_dir, write=write)
    boundary = build_provider_smoke_release_boundary_audit(state_dir, manifest, write=write)
    blockers = build_provider_smoke_remaining_blockers(state_dir, manifest, write=write)
    closed = manifest.get("status") == "complete_with_limitations" and boundary.get("status") == "limited_boundary_preserved"
    status = "closed_with_limitations" if closed else "blocked" if manifest.get("status") == "unsafe" else "incomplete"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-smoke-closure-report-v1",
        "artifact": PROVIDER_SMOKE_CLOSURE_REPORT_JSON,
        "status": status,
        "proven": ["manual_provider_path_executed_for_two_public_fixture_segments"] if closed else [],
        "not_proven": [
            "provider_backed_quality",
            "production_ready",
            "locale_complete",
            "full_product_localization",
            "benchmark_reliability",
            "runtime_managed_real_provider_execution",
        ],
        "gates": manifest.get("gate_summary", {}),
        "local_only_evidence": ["raw_provider_response"],
        "raw_output_committable": False,
        "forbidden_claims": boundary.get("forbidden_claims", sorted(FORBIDDEN_CLAIMS)),
        "remaining_blocker_count": blockers.get("summary", {}).get("active_count", 0),
        "provider_or_model_called_by_runtime": False,
        "target_files_mutated": False,
        "source_artifact_references": [
            PROVIDER_SMOKE_EVIDENCE_MANIFEST_JSON,
            PROVIDER_SMOKE_RELEASE_BOUNDARY_AUDIT_JSON,
            PROVIDER_SMOKE_REMAINING_BLOCKERS_JSON,
        ],
    }
    if write:
        write_json(state_dir / PROVIDER_SMOKE_CLOSURE_REPORT_JSON, report)
    return report


def build_provider_smoke_next_step_decision(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    closure = build_provider_smoke_closure_report(state_dir, write=write)
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-smoke-next-step-decision-v1",
        "artifact": PROVIDER_SMOKE_NEXT_STEP_DECISION_JSON,
        "status": "repeat_same_scope_or_stop",
        "closure_status": closure.get("status"),
        "provider_scope_expansion_authorized": False,
        "automatic_provider_rerun_authorized": False,
        "small_batch_protocol_design": "future_explicit_loop_only",
        "benchmark_promotion_allowed": False,
        "provider_release_promotion_allowed": False,
        "recommended_actions": [
            "stop unless a future explicit same-scope repeat is justified",
            "design a small-batch protocol only in a separate explicitly authorized loop",
        ],
        "forbidden_claims": closure.get("forbidden_claims", sorted(FORBIDDEN_CLAIMS)),
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": [PROVIDER_SMOKE_CLOSURE_REPORT_JSON, PROVIDER_SMOKE_REMAINING_BLOCKERS_JSON],
    }
    if write:
        write_json(state_dir / PROVIDER_SMOKE_NEXT_STEP_DECISION_JSON, report)
    return report


def build_provider_smoke_closure_artifacts(state_dir: Path) -> dict[str, Any]:
    manifest = build_provider_smoke_evidence_manifest(state_dir)
    boundary = build_provider_smoke_release_boundary_audit(state_dir, manifest)
    blockers = build_provider_smoke_remaining_blockers(state_dir, manifest)
    closure = build_provider_smoke_closure_report(state_dir)
    decision = build_provider_smoke_next_step_decision(state_dir)
    return {
        "provider_smoke_evidence_manifest": manifest,
        "provider_smoke_release_boundary_audit": boundary,
        "provider_smoke_remaining_blockers": blockers,
        "provider_smoke_closure_report": closure,
        "provider_smoke_next_step_decision": decision,
        "provider_or_model_called_by_runtime": False,
    }


def read_provider_smoke_closure_artifact(state_dir: Path, name: str) -> dict[str, Any]:
    filename = PROVIDER_SMOKE_CLOSURE_ASSETS.get(name)
    if not filename:
        raise ValueError(f"unknown provider smoke closure artifact: {name}")
    return _required_json(state_dir / filename)


def provider_smoke_closure_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in PROVIDER_SMOKE_CLOSURE_ASSETS.items() if (state_dir / name).is_file()}


def _sanitized_status(evidence: dict[str, Any]) -> str:
    if not evidence:
        return "missing"
    safe = (
        evidence.get("raw_output_local_only") is True
        and evidence.get("raw_output_committed") is False
        and evidence.get("credentials_recorded") is False
        and int(evidence.get("sanitized_secret_leak_count") or 0) == 0
        and evidence.get("target_files_mutated") is False
        and evidence.get("provider_backed_quality_supported") is False
    )
    return "safe" if safe else "unsafe"


def _existing_names(state_dir: Path, *names: str) -> list[str]:
    return [name for name in names if (state_dir / name).is_file()]


def _optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"artifact not found: {path.name}")
    return read_json(path)
