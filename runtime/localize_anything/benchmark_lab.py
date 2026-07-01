from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json


BENCHMARK_RUN_MANIFEST_JSON = "benchmark-run-manifest.json"
BENCHMARK_BASELINE_REPORT_JSON = "benchmark-baseline-report.json"
BENCHMARK_CANDIDATE_REPORT_JSON = "benchmark-candidate-report.json"
BENCHMARK_COMPARISON_REPORT_JSON = "benchmark-comparison-report.json"
BENCHMARK_EVIDENCE_MATRIX_JSON = "benchmark-evidence-matrix.json"
BENCHMARK_CLAIM_BOUNDARY_REPORT_JSON = "benchmark-claim-boundary-report.json"

BENCHMARK_ASSETS = {
    "benchmark_run_manifest": BENCHMARK_RUN_MANIFEST_JSON,
    "benchmark_baseline_report": BENCHMARK_BASELINE_REPORT_JSON,
    "benchmark_candidate_report": BENCHMARK_CANDIDATE_REPORT_JSON,
    "benchmark_comparison_report": BENCHMARK_COMPARISON_REPORT_JSON,
    "benchmark_evidence_matrix": BENCHMARK_EVIDENCE_MATRIX_JSON,
    "benchmark_claim_boundary_report": BENCHMARK_CLAIM_BOUNDARY_REPORT_JSON,
}

CLAIMS_TO_COMPARE = {
    "provider_backed_quality",
    "knowledge_backed_quality",
    "full_coverage",
    "review_complete",
    "delivery_ready",
    "apply_ready",
    "production_ready",
    "locale_complete",
    "rtl_safe",
    "plural_complete",
    "locale_formatting_complete",
}

STATUS_RANK = {
    "pass": 5,
    "ready": 5,
    "clear": 5,
    "covered": 5,
    "supported": 5,
    "delivery_ready": 5,
    "apply_ready": 5,
    "ready_with_warnings": 4,
    "clear_with_warnings": 4,
    "partial": 3,
    "limited": 3,
    "review_required": 2,
    "unknown": 1,
    "missing": 1,
    "not_checked": 1,
    "stale": 0,
    "blocked": 0,
    "fail": 0,
    "failed": 0,
}


def build_benchmark_lab_reports(
    state_dir: Path,
    *,
    baseline_dir: Path | None = None,
    candidate_dir: Path | None = None,
    benchmark_track: str = "controlled",
    reference_policy: str = "not_provided",
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    manifest = build_benchmark_run_manifest(
        state_dir,
        baseline_dir=baseline_dir,
        candidate_dir=candidate_dir,
        benchmark_track=benchmark_track,
        reference_policy=reference_policy,
        run_id=run_id,
        write=write,
    )
    baseline = build_benchmark_baseline_report(state_dir, baseline_dir=baseline_dir, manifest=manifest, run_id=run_id, write=write)
    candidate = build_benchmark_candidate_report(state_dir, candidate_dir=candidate_dir, manifest=manifest, run_id=run_id, write=write)
    comparison = build_benchmark_comparison_report(state_dir, baseline=baseline, candidate=candidate, manifest=manifest, run_id=run_id, write=write)
    matrix = build_benchmark_evidence_matrix(state_dir, baseline=baseline, candidate=candidate, comparison=comparison, run_id=run_id, write=write)
    claims = build_benchmark_claim_boundary_report(state_dir, candidate=candidate, comparison=comparison, matrix=matrix, run_id=run_id, write=write)
    return {
        "benchmark_run_manifest": manifest,
        "benchmark_baseline_report": baseline,
        "benchmark_candidate_report": candidate,
        "benchmark_comparison_report": comparison,
        "benchmark_evidence_matrix": matrix,
        "benchmark_claim_boundary_report": claims,
    }


def build_benchmark_run_manifest(
    state_dir: Path,
    *,
    baseline_dir: Path | None = None,
    candidate_dir: Path | None = None,
    benchmark_track: str = "controlled",
    reference_policy: str = "not_provided",
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    baseline_dir = _default_run_dir(state_dir, "baseline", baseline_dir)
    candidate_dir = _default_run_dir(state_dir, "candidate", candidate_dir)
    baseline_evidence = _evidence(baseline_dir)
    candidate_evidence = _evidence(candidate_dir)
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-benchmark-run-manifest-v1",
        "artifact": BENCHMARK_RUN_MANIFEST_JSON,
        "run_id": run_id or _first_value(candidate_evidence, baseline_evidence, key="run_id") or "benchmark-run",
        "status": "ready",
        "benchmark_track": benchmark_track if benchmark_track in {"controlled", "agent_system"} else "controlled",
        "reference_policy": reference_policy or _reference_policy(candidate_evidence) or _reference_policy(baseline_evidence) or "not_provided",
        "baseline": _run_reference("baseline", baseline_dir, baseline_evidence),
        "candidate": _run_reference("candidate", candidate_dir, candidate_evidence),
        "evidence_contract": {
            "single_quality_score_produced": False,
            "reference_translations_are_evaluation_references": True,
            "benchmark_comparison_does_not_upgrade_release_claims": True,
            "synthetic_or_failed_provider_output_is_not_provider_backed": True,
        },
        "limitations": [
            "benchmark lab is a deterministic evidence comparison harness, not a leaderboard",
            "benchmark evidence does not prove semantic quality or release readiness by itself",
        ],
    }
    if write:
        write_json(state_dir / BENCHMARK_RUN_MANIFEST_JSON, manifest)
    return manifest


def read_benchmark_run_manifest(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / BENCHMARK_RUN_MANIFEST_JSON)


def build_benchmark_baseline_report(
    state_dir: Path,
    *,
    baseline_dir: Path | None = None,
    manifest: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    manifest = manifest or _optional_json(state_dir / BENCHMARK_RUN_MANIFEST_JSON)
    baseline_dir = _default_run_dir(state_dir, "baseline", baseline_dir)
    report = _run_report("baseline", baseline_dir, run_id=run_id or manifest.get("run_id"))
    if write:
        write_json(state_dir / BENCHMARK_BASELINE_REPORT_JSON, report)
    return report


def read_benchmark_baseline_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / BENCHMARK_BASELINE_REPORT_JSON)


def build_benchmark_candidate_report(
    state_dir: Path,
    *,
    candidate_dir: Path | None = None,
    manifest: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    manifest = manifest or _optional_json(state_dir / BENCHMARK_RUN_MANIFEST_JSON)
    candidate_dir = _default_run_dir(state_dir, "candidate", candidate_dir)
    report = _run_report("candidate", candidate_dir, run_id=run_id or manifest.get("run_id"))
    if write:
        write_json(state_dir / BENCHMARK_CANDIDATE_REPORT_JSON, report)
    return report


def read_benchmark_candidate_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / BENCHMARK_CANDIDATE_REPORT_JSON)


def build_benchmark_comparison_report(
    state_dir: Path,
    *,
    baseline: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    manifest = manifest or _optional_json(state_dir / BENCHMARK_RUN_MANIFEST_JSON)
    baseline = baseline or _optional_json(state_dir / BENCHMARK_BASELINE_REPORT_JSON)
    candidate = candidate or _optional_json(state_dir / BENCHMARK_CANDIDATE_REPORT_JSON)
    dimensions = []
    for name in [
        "structural_qa",
        "coverage",
        "forbidden_claims",
        "scorecard_readiness",
        "provider_evidence",
        "knowledge_evidence",
        "locale_capability",
        "translation_provenance",
        "repair_recompute",
        "human_review_signoff",
        "delivery_apply",
    ]:
        dimensions.append(_dimension_comparison(name, baseline, candidate))
    base_forbidden = set(_get(baseline, "forbidden_claims", default=[]))
    cand_forbidden = set(_get(candidate, "forbidden_claims", default=[]))
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-benchmark-comparison-report-v1",
        "artifact": BENCHMARK_COMPARISON_REPORT_JSON,
        "run_id": run_id or manifest.get("run_id") or _get(candidate, "run_id") or _get(baseline, "run_id"),
        "status": _comparison_status(baseline, candidate),
        "benchmark_track": manifest.get("benchmark_track", "controlled"),
        "reference_policy": manifest.get("reference_policy", "not_provided"),
        "single_quality_score": None,
        "single_quality_score_produced": False,
        "dimension_comparisons": dimensions,
        "forbidden_claim_regression": {
            "added": sorted(cand_forbidden - base_forbidden),
            "removed": sorted(base_forbidden - cand_forbidden),
            "unchanged": sorted(base_forbidden & cand_forbidden),
        },
        "provider_backed_quality_supported": bool(_get(candidate, "provider_evidence", "provider_backed_supported", default=False)),
        "claim_upgrade_policy": {
            "comparison_can_upgrade_release_claims": False,
            "comparison_can_support_provider_backed_quality": False,
        },
        "limitations": [
            "comparison reports evidence deltas and never emits a synthetic quality score",
            "controlled and agent-system benchmark tracks must be interpreted separately",
        ],
    }
    if write:
        write_json(state_dir / BENCHMARK_COMPARISON_REPORT_JSON, report)
    return report


def read_benchmark_comparison_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / BENCHMARK_COMPARISON_REPORT_JSON)


def build_benchmark_evidence_matrix(
    state_dir: Path,
    *,
    baseline: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
    comparison: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    baseline = baseline or _optional_json(state_dir / BENCHMARK_BASELINE_REPORT_JSON)
    candidate = candidate or _optional_json(state_dir / BENCHMARK_CANDIDATE_REPORT_JSON)
    comparison = comparison or _optional_json(state_dir / BENCHMARK_COMPARISON_REPORT_JSON)
    rows = [_matrix_row(item["dimension"], baseline, candidate) for item in comparison.get("dimension_comparisons", [])]
    matrix = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-benchmark-evidence-matrix-v1",
        "artifact": BENCHMARK_EVIDENCE_MATRIX_JSON,
        "run_id": run_id or comparison.get("run_id") or _get(candidate, "run_id") or _get(baseline, "run_id"),
        "status": "ready" if rows else "missing_evidence",
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "regression_count": sum(1 for row in rows if row["comparison"] == "regressed"),
            "improvement_count": sum(1 for row in rows if row["comparison"] == "improved"),
            "unknown_count": sum(1 for row in rows if row["comparison"] == "unknown"),
        },
        "limitations": ["evidence matrix is a projection over run artifacts and not a quality score"],
    }
    if write:
        write_json(state_dir / BENCHMARK_EVIDENCE_MATRIX_JSON, matrix)
    return matrix


def read_benchmark_evidence_matrix(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / BENCHMARK_EVIDENCE_MATRIX_JSON)


def build_benchmark_claim_boundary_report(
    state_dir: Path,
    *,
    candidate: dict[str, Any] | None = None,
    comparison: dict[str, Any] | None = None,
    matrix: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    candidate = candidate or _optional_json(state_dir / BENCHMARK_CANDIDATE_REPORT_JSON)
    comparison = comparison or _optional_json(state_dir / BENCHMARK_COMPARISON_REPORT_JSON)
    matrix = matrix or _optional_json(state_dir / BENCHMARK_EVIDENCE_MATRIX_JSON)
    forbidden = set(_get(candidate, "forbidden_claims", default=[]))
    forbidden.update({"benchmark_quality_score", "provider_backed_quality", "production_ready"})
    if _get(candidate, "provider_evidence", "provider_backed_supported", default=False):
        forbidden.discard("provider_backed_quality")
    if _status(_get(candidate, "knowledge_evidence", default={})) not in {"pass", "ready", "clear", "supported"}:
        forbidden.add("knowledge_backed_quality")
    if _status(_get(candidate, "coverage", default={})) not in {"pass", "ready", "clear", "covered"}:
        forbidden.add("full_coverage")
    if _status(_get(candidate, "human_review_signoff", default={})) not in {"pass", "ready", "clear", "supported"}:
        forbidden.add("review_complete")
    supported = []
    if comparison.get("status") == "compared":
        supported.extend(["benchmark_evidence_compared", "benchmark_structural_evidence_available"])
    if matrix.get("status") == "ready":
        supported.append("benchmark_evidence_matrix_available")
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-benchmark-claim-boundary-report-v1",
        "artifact": BENCHMARK_CLAIM_BOUNDARY_REPORT_JSON,
        "run_id": run_id or comparison.get("run_id") or _get(candidate, "run_id"),
        "status": "blocked" if forbidden else "limited",
        "supported_benchmark_claims": sorted(set(supported)),
        "unsupported_claims": sorted(CLAIMS_TO_COMPARE - set(supported)),
        "forbidden_claims": sorted(forbidden),
        "claim_boundaries": [
            {
                "claim": claim,
                "status": "forbidden" if claim in forbidden else "unsupported",
                "reason": _claim_reason(claim, candidate, comparison),
            }
            for claim in sorted(forbidden | (CLAIMS_TO_COMPARE - set(supported)))
        ],
        "release_claim_policy": {
            "benchmark_comparison_upgrades_delivery_or_apply_readiness": False,
            "single_quality_score_forbidden": True,
        },
        "limitations": [
            "benchmark evidence can describe deltas but cannot make release, provider-backed, review-complete, or production-ready claims by itself",
        ],
    }
    if write:
        write_json(state_dir / BENCHMARK_CLAIM_BOUNDARY_REPORT_JSON, report)
    return report


def read_benchmark_claim_boundary_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / BENCHMARK_CLAIM_BOUNDARY_REPORT_JSON)


def benchmark_lab_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in BENCHMARK_ASSETS.items() if (state_dir / name).is_file()}


def _run_report(kind: str, run_dir: Path, *, run_id: str | None) -> dict[str, Any]:
    evidence = _evidence(run_dir)
    missing = not any(evidence.values())
    forbidden = _forbidden_claims(evidence)
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": f"localize-anything-benchmark-{kind}-report-v1",
        "artifact": BENCHMARK_BASELINE_REPORT_JSON if kind == "baseline" else BENCHMARK_CANDIDATE_REPORT_JSON,
        "run_id": run_id or evidence.get("run_id"),
        "run_role": kind,
        "status": "missing_evidence" if missing else "ready",
        "run_directory": run_dir.as_posix(),
        "mode": _mode(evidence),
        "reference_policy": _reference_policy(evidence),
        "adapter_versions": _adapter_versions(evidence),
        "source_commit": _source_commit(evidence),
        "source_path": _source_path(evidence),
        "target_locale": _target_locale(evidence),
        "provider_evidence_status": _provider_status(evidence),
        "knowledge_pack_status": _knowledge_status(evidence),
        "human_review_level": _human_review_level(evidence),
        "workflow_depth": _workflow_depth(evidence),
        "structural_qa": _structural_qa(evidence),
        "coverage": _coverage(evidence),
        "forbidden_claims": forbidden,
        "scorecard_readiness": _scorecard_readiness(evidence),
        "provider_evidence": _provider_evidence(evidence),
        "knowledge_evidence": _knowledge_evidence(evidence),
        "locale_capability": _locale_capability(evidence),
        "translation_provenance": _translation_provenance(evidence),
        "repair_recompute": _repair_recompute(evidence),
        "human_review_signoff": _human_review_signoff(evidence),
        "delivery_apply": _delivery_apply(evidence),
        "source_artifacts": _source_artifacts(run_dir),
        "limitations": [
            "run report summarizes evidence only and does not produce a single quality score",
            "reference translations are evaluation references, not hidden source truth",
        ],
    }
    return report


def _evidence(run_dir: Path) -> dict[str, Any]:
    return {
        "run_summary": _optional_json(run_dir / "run-summary.json"),
        "delivery_manifest": _optional_json(run_dir / "delivery-manifest.json"),
        "delivery_decision": _optional_json(run_dir / "delivery-decision.json"),
        "evaluation_scorecard": _optional_json(run_dir / "evaluation-scorecard.json"),
        "readiness_matrix": _optional_json(run_dir / "readiness-authorization-matrix.json"),
        "apply_report": _optional_json(run_dir / "apply-readiness-report.json"),
        "delivery_report": _optional_json(run_dir / "delivery-readiness-report.json"),
        "provider_evidence_reconciliation": _optional_json(run_dir / "provider-evidence-reconciliation.json"),
        "provider_claim_support_report": _optional_json(run_dir / "provider-claim-support-report.json"),
        "provider_result_intake": _optional_jsonl(run_dir / "provider-result-intake.jsonl"),
        "knowledge_usage_report": _optional_json(run_dir / "knowledge-usage-report.json"),
        "constraint_application_audit": _optional_json(run_dir / "constraint-application-audit.json"),
        "knowledge_assurance_summary": _optional_json(run_dir / "knowledge-assurance-summary.json"),
        "locale_capability_report": _optional_json(run_dir / "locale-capability-report.json"),
        "locale_readiness_impact": _optional_json(run_dir / "locale-readiness-impact.json"),
        "provenance_coverage_report": _optional_json(run_dir / "provenance-coverage-report.json"),
        "translation_claim_provenance_report": _optional_json(run_dir / "translation-claim-provenance-report.json"),
        "repair_result": _optional_json(run_dir / "repair-result.json"),
        "knowledge_repair_closure": _optional_json(run_dir / "knowledge-repair-closure-decision.json"),
        "knowledge_recompute_result": _optional_json(run_dir / "knowledge-recompute-result.json"),
        "human_review_evidence": _optional_jsonl(run_dir / "human-review-evidence.jsonl"),
        "signoff_record": _optional_json(run_dir / "signoff-record.json"),
        "artifact_state": _optional_json(run_dir / "artifact-state.json"),
    }


def _run_reference(kind: str, run_dir: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": kind,
        "state_dir": run_dir.as_posix(),
        "status": "missing" if not any(evidence.values()) else "available",
        "source_commit": _source_commit(evidence),
        "source_path": _source_path(evidence),
        "target_locale": _target_locale(evidence),
        "provider_evidence_status": _provider_status(evidence),
        "knowledge_pack_status": _knowledge_status(evidence),
        "human_review_level": _human_review_level(evidence),
        "workflow_depth": _workflow_depth(evidence),
    }


def _dimension_comparison(name: str, baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    base = _get(baseline, name, default={})
    cand = _get(candidate, name, default={})
    return {
        "dimension": name,
        "baseline_status": _status(base),
        "candidate_status": _status(cand),
        "comparison": _compare_status(_status(base), _status(cand)),
        "baseline_summary": _summary_text(base),
        "candidate_summary": _summary_text(cand),
    }


def _matrix_row(name: str, baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    comparison = _dimension_comparison(name, baseline, candidate)
    return {
        **comparison,
        "baseline_artifacts": _dimension_artifacts(name, baseline),
        "candidate_artifacts": _dimension_artifacts(name, candidate),
    }


def _comparison_status(baseline: dict[str, Any], candidate: dict[str, Any]) -> str:
    baseline_missing = baseline.get("status") in {"", "missing_evidence"} or not baseline
    candidate_missing = candidate.get("status") in {"", "missing_evidence"} or not candidate
    if baseline_missing and candidate_missing:
        return "missing_evidence"
    if baseline_missing:
        return "candidate_only"
    if candidate_missing:
        return "baseline_only"
    return "compared"


def _compare_status(baseline: str, candidate: str) -> str:
    if baseline == candidate:
        return "unchanged"
    if baseline not in STATUS_RANK or candidate not in STATUS_RANK:
        return "unknown"
    return "improved" if STATUS_RANK[candidate] > STATUS_RANK[baseline] else "regressed"


def _structural_qa(evidence: dict[str, Any]) -> dict[str, Any]:
    manifest = evidence["delivery_manifest"]
    qa = _get(manifest, "summary", "qa_status") or _get(manifest, "qa", "status") or "unknown"
    return {"status": qa, "summary": f"structural QA status is {qa}", "artifacts": _artifact_refs("delivery-manifest.json", bool(manifest))}


def _coverage(evidence: dict[str, Any]) -> dict[str, Any]:
    scorecard = evidence["evaluation_scorecard"]
    status = _get(scorecard, "coverage_assurance", "status") or _get(scorecard, "coverage", "status") or "unknown"
    return {"status": status, "summary": f"coverage assurance status is {status}", "artifacts": _artifact_refs("evaluation-scorecard.json", bool(scorecard))}


def _scorecard_readiness(evidence: dict[str, Any]) -> dict[str, Any]:
    scorecard = evidence["evaluation_scorecard"]
    status = scorecard.get("overall_claim") or scorecard.get("status") or "unknown"
    return {
        "status": status,
        "summary": f"scorecard overall claim is {status}",
        "evidence_level": scorecard.get("evidence_level", {}),
        "artifacts": _artifact_refs("evaluation-scorecard.json", bool(scorecard)),
    }


def _provider_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    reconciliation = evidence["provider_evidence_reconciliation"]
    claim_support = evidence["provider_claim_support_report"]
    intake = evidence["provider_result_intake"]
    synthetic = any(str(item.get("result_source") or item.get("source") or "") in {"synthetic", "mock", "dry_run", "failed", "local_draft"} for item in intake)
    failed = str(reconciliation.get("status") or "") in {"failed", "blocked", "stale"}
    supported = bool(claim_support.get("provider_backed_quality_supported")) and not synthetic and not failed
    status = "supported" if supported else "blocked" if failed or synthetic else reconciliation.get("status") or "unknown"
    return {
        "status": status,
        "provider_backed_supported": supported,
        "synthetic_or_failed_output_present": synthetic or failed,
        "summary": "provider-backed quality is supported" if supported else "provider-backed quality is not supported by benchmark evidence",
        "artifacts": _artifact_refs("provider-evidence-reconciliation.json", bool(reconciliation)),
    }


def _knowledge_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    assurance = evidence["knowledge_assurance_summary"]
    usage = evidence["knowledge_usage_report"]
    audit = evidence["constraint_application_audit"]
    status = assurance.get("status") or usage.get("status") or audit.get("status") or "unknown"
    return {"status": status, "summary": f"knowledge evidence status is {status}", "artifacts": _existing_names(("knowledge-assurance-summary.json", assurance), ("knowledge-usage-report.json", usage), ("constraint-application-audit.json", audit))}


def _locale_capability(evidence: dict[str, Any]) -> dict[str, Any]:
    impact = evidence["locale_readiness_impact"]
    capability = evidence["locale_capability_report"]
    status = impact.get("status") or capability.get("status") or "unknown"
    return {"status": status, "summary": f"locale capability status is {status}", "forbidden_claims": impact.get("forbidden_claims", capability.get("unsupported_claims", [])), "artifacts": _existing_names(("locale-readiness-impact.json", impact), ("locale-capability-report.json", capability))}


def _translation_provenance(evidence: dict[str, Any]) -> dict[str, Any]:
    coverage = evidence["provenance_coverage_report"]
    claims = evidence["translation_claim_provenance_report"]
    status = coverage.get("status") or claims.get("status") or "unknown"
    return {"status": status, "summary": f"translation provenance status is {status}", "forbidden_claims": claims.get("forbidden_claims", []), "artifacts": _existing_names(("provenance-coverage-report.json", coverage), ("translation-claim-provenance-report.json", claims))}


def _repair_recompute(evidence: dict[str, Any]) -> dict[str, Any]:
    closure = evidence["knowledge_repair_closure"]
    recompute = evidence["knowledge_recompute_result"]
    repair = evidence["repair_result"]
    status = closure.get("status") or recompute.get("status") or repair.get("status") or "unknown"
    return {"status": status, "summary": f"repair/recompute status is {status}", "artifacts": _existing_names(("knowledge-repair-closure-decision.json", closure), ("knowledge-recompute-result.json", recompute), ("repair-result.json", repair))}


def _human_review_signoff(evidence: dict[str, Any]) -> dict[str, Any]:
    reviews = evidence["human_review_evidence"]
    signoff = evidence["signoff_record"]
    level = _human_review_level(evidence)
    status = signoff.get("status") or ("reviewed" if reviews else "unknown")
    return {"status": status, "summary": f"human review level is {level}; signoff status is {status}", "human_review_level": level, "review_record_count": len(reviews), "artifacts": _existing_names(("human-review-evidence.jsonl", reviews), ("signoff-record.json", signoff))}


def _delivery_apply(evidence: dict[str, Any]) -> dict[str, Any]:
    matrix = evidence["readiness_matrix"]
    delivery = evidence["delivery_report"]
    apply = evidence["apply_report"]
    delivery_status = matrix.get("delivery_readiness_status") or delivery.get("delivery_status") or delivery.get("status") or "unknown"
    apply_status = matrix.get("apply_readiness_status") or apply.get("apply_status") or apply.get("status") or "unknown"
    return {
        "status": "ready" if delivery_status == "ready" and apply_status == "ready" else "review_required" if "ready" in {delivery_status, apply_status} else "blocked" if "blocked" in {delivery_status, apply_status} else "unknown",
        "delivery_status": delivery_status,
        "apply_status": apply_status,
        "summary": f"delivery={delivery_status}; apply={apply_status}",
        "artifacts": _existing_names(("readiness-authorization-matrix.json", matrix), ("delivery-readiness-report.json", delivery), ("apply-readiness-report.json", apply)),
    }


def _forbidden_claims(evidence: dict[str, Any]) -> list[str]:
    claims: set[str] = set()
    for key, field in [
        ("evaluation_scorecard", "forbidden_claims"),
        ("readiness_matrix", "forbidden_claims"),
        ("delivery_report", "forbidden_claims"),
        ("apply_report", "forbidden_claims_that_prevent_apply"),
        ("locale_readiness_impact", "forbidden_claims"),
        ("translation_claim_provenance_report", "forbidden_claims"),
    ]:
        claims.update(str(item) for item in evidence[key].get(field, []) if item)
    if not _provider_evidence(evidence)["provider_backed_supported"]:
        claims.add("provider_backed_quality")
    return sorted(claims)


def _source_artifacts(run_dir: Path) -> dict[str, str]:
    names = [
        "evaluation-scorecard.json",
        "readiness-authorization-matrix.json",
        "delivery-manifest.json",
        "delivery-decision.json",
        "provider-evidence-reconciliation.json",
        "knowledge-usage-report.json",
        "constraint-application-audit.json",
        "knowledge-assurance-summary.json",
        "locale-readiness-impact.json",
        "provenance-coverage-report.json",
        "translation-claim-provenance-report.json",
        "repair-result.json",
        "knowledge-repair-closure-decision.json",
        "human-review-evidence.jsonl",
        "signoff-record.json",
    ]
    return {name.removesuffix(".json").replace("-", "_"): name for name in names if (run_dir / name).is_file()}


def _dimension_artifacts(name: str, report: dict[str, Any]) -> list[str]:
    value = _get(report, name, default={})
    return list(value.get("artifacts", [])) if isinstance(value, dict) else []


def _status(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("status") or value.get("overall_claim") or "unknown")
    if isinstance(value, str):
        return value
    return "unknown"


def _summary_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("summary") or value.get("status") or "unknown")
    return str(value or "unknown")


def _claim_reason(claim: str, candidate: dict[str, Any], comparison: dict[str, Any]) -> str:
    if claim == "benchmark_quality_score":
        return "single synthetic benchmark quality scores are forbidden"
    if claim == "provider_backed_quality":
        return "candidate provider evidence is not reconciled as provider-backed"
    if claim == "production_ready":
        return "benchmark comparison cannot upgrade production readiness"
    if claim in set(comparison.get("forbidden_claim_regression", {}).get("added", [])):
        return "candidate introduced this forbidden claim compared with baseline"
    return "claim is unsupported by benchmark evidence"


def _mode(evidence: dict[str, Any]) -> str:
    return _get(evidence, "run_summary", "project", "operating_mode") or _get(evidence, "delivery_manifest", "generation", "mode") or "unknown"


def _reference_policy(evidence: dict[str, Any]) -> str:
    return _get(evidence, "run_summary", "reference", "reference_policy") or _get(evidence, "delivery_manifest", "reference_policy") or "not_provided"


def _adapter_versions(evidence: dict[str, Any]) -> dict[str, str]:
    adapters = _get(evidence, "delivery_manifest", "adapters", default={})
    return adapters if isinstance(adapters, dict) else {}


def _source_commit(evidence: dict[str, Any]) -> str:
    return _get(evidence, "delivery_manifest", "source_commit") or _get(evidence, "run_summary", "project", "source_commit") or "unknown"


def _source_path(evidence: dict[str, Any]) -> str:
    return _get(evidence, "delivery_manifest", "source_path") or _get(evidence, "run_summary", "project", "root") or "unknown"


def _target_locale(evidence: dict[str, Any]) -> str:
    return _get(evidence, "locale_capability_report", "target_locale") or _get(evidence, "run_summary", "project", "target_locale") or "unknown"


def _provider_status(evidence: dict[str, Any]) -> str:
    return _provider_evidence(evidence)["status"]


def _knowledge_status(evidence: dict[str, Any]) -> str:
    return _knowledge_evidence(evidence)["status"]


def _human_review_level(evidence: dict[str, Any]) -> str:
    scorecard = evidence["evaluation_scorecard"]
    return (
        _get(scorecard, "evidence_level", "highest_supported")
        or _get(scorecard, "evidence_level", "highest_global_human_supported")
        or ("E2_or_higher_provided" if evidence["human_review_evidence"] else "not_provided")
    )


def _workflow_depth(evidence: dict[str, Any]) -> str:
    summary = evidence["run_summary"].get("summary", {})
    if summary.get("workflow_recovery_status") or summary.get("selective_recompute_status"):
        return "incremental_or_recovered"
    if evidence["translation_claim_provenance_report"]:
        return "provenance_view"
    if evidence["delivery_manifest"]:
        return "delivery_package"
    return "unknown"


def _first_value(*docs: dict[str, Any], key: str) -> Any:
    for doc in docs:
        if doc.get(key):
            return doc[key]
    return None


def _get(value: Any, *keys: str, default: Any = None) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _artifact_refs(name: str, present: bool) -> list[str]:
    return [name] if present else []


def _existing_names(*items: tuple[str, Any]) -> list[str]:
    return [name for name, value in items if bool(value)]


def _default_run_dir(state_dir: Path, name: str, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    nested = state_dir / name
    return nested.resolve() if nested.exists() else state_dir.resolve()


def _optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _optional_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.is_file() else []


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing benchmark artifact: {path}")
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Invalid benchmark artifact: {path}")
    return value
