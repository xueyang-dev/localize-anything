from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json, write_jsonl


TRANSLATION_PROVENANCE_JSONL = "translation-provenance.jsonl"
SEGMENT_EVIDENCE_VIEW_JSON = "segment-evidence-view.json"
PROVENANCE_COVERAGE_REPORT_JSON = "provenance-coverage-report.json"
TRANSLATION_CLAIM_PROVENANCE_REPORT_JSON = "translation-claim-provenance-report.json"

PROVENANCE_CLAIMS = {
    "provider_backed_quality",
    "knowledge_backed_quality",
    "knowledge_constraints_applied",
    "full_terminology_assurance",
    "review_complete",
    "locale_complete",
    "rtl_safe",
    "plural_complete",
    "locale_formatting_complete",
    "full_product_localization",
    "delivery_ready",
    "apply_ready",
    "production_ready",
}


def build_translation_provenance_views(state_dir: Path, *, run_id: str | None = None, write: bool = True) -> dict[str, Any]:
    provenance = build_translation_provenance(state_dir, run_id=run_id, write=write)
    view = build_segment_evidence_view(state_dir, provenance=provenance, run_id=run_id, write=write)
    coverage = build_provenance_coverage_report(state_dir, provenance=provenance, run_id=run_id, write=write)
    claims = build_translation_claim_provenance_report(state_dir, provenance=provenance, coverage=coverage, run_id=run_id, write=write)
    return {
        "translation_provenance": provenance,
        "segment_evidence_view": view,
        "provenance_coverage_report": coverage,
        "translation_claim_provenance_report": claims,
    }


def build_translation_provenance(state_dir: Path, *, run_id: str | None = None, write: bool = True) -> list[dict[str, Any]]:
    state_dir = state_dir.resolve()
    artifacts = _artifacts(state_dir)
    generated = artifacts["generated_segments"]
    records = [_segment_record(segment, artifacts, run_id=run_id) for segment in generated]
    if write:
        write_jsonl(state_dir / TRANSLATION_PROVENANCE_JSONL, records)
    return records


def read_translation_provenance(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / TRANSLATION_PROVENANCE_JSONL
    return read_jsonl(path) if path.is_file() else []


def build_segment_evidence_view(
    state_dir: Path,
    *,
    provenance: list[dict[str, Any]] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    provenance = provenance if provenance is not None else read_translation_provenance(state_dir) or build_translation_provenance(state_dir, run_id=run_id, write=False)
    by_status = _count_evidence(provenance, "evidence_status")
    by_type = _count_evidence(provenance, "evidence_type")
    view = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-segment-evidence-view-v1",
        "artifact": SEGMENT_EVIDENCE_VIEW_JSON,
        "run_id": run_id or _run_id_from_records(provenance),
        "status": "missing_segments" if not provenance else "ready",
        "segments": provenance,
        "grouped_by_segment_id": {str(item.get("segment_id") or ""): item for item in provenance},
        "summary": {
            "segment_count": len(provenance),
            "evidence_count": sum(len(item.get("evidence", [])) for item in provenance),
            "by_evidence_status": by_status,
            "by_evidence_type": by_type,
        },
        "limitations": [
            "segment evidence view is a projection over artifacts and does not prove semantic quality",
            "segment-level provenance does not imply full-run readiness",
        ],
    }
    if write:
        write_json(state_dir / SEGMENT_EVIDENCE_VIEW_JSON, view)
    return view


def read_segment_evidence_view(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / SEGMENT_EVIDENCE_VIEW_JSON)


def build_provenance_coverage_report(
    state_dir: Path,
    *,
    provenance: list[dict[str, Any]] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    provenance = provenance if provenance is not None else read_translation_provenance(state_dir) or build_translation_provenance(state_dir, run_id=run_id, write=False)
    missing = _missing_evidence(provenance)
    stale = _evidence_by_status(provenance, {"stale", "superseded"})
    reference_only = _evidence_by_status(provenance, {"reference_only"})
    synthetic = [item for item in _all_evidence(provenance) if item.get("provider_source") in {"synthetic", "mock", "dry_run", "failed", "local_draft"}]
    status = "blocked" if stale else "review_required" if missing or reference_only or synthetic else "covered"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provenance-coverage-report-v1",
        "artifact": PROVENANCE_COVERAGE_REPORT_JSON,
        "run_id": run_id or _run_id_from_records(provenance),
        "status": status,
        "summary": {
            "segment_count": len(provenance),
            "missing_evidence_count": len(missing),
            "stale_evidence_count": len(stale),
            "reference_only_evidence_count": len(reference_only),
            "synthetic_or_unverified_provider_evidence_count": len(synthetic),
        },
        "missing_or_limited_evidence": missing,
        "stale_evidence": stale,
        "reference_only_evidence": reference_only,
        "synthetic_or_unverified_provider_evidence": synthetic,
        "limitations": [
            "coverage means provenance visibility, not quality acceptance",
            "reference-only, stale, synthetic, failed, or missing evidence cannot support strong claims",
        ],
    }
    if write:
        write_json(state_dir / PROVENANCE_COVERAGE_REPORT_JSON, report)
    return report


def read_provenance_coverage_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / PROVENANCE_COVERAGE_REPORT_JSON)


def build_translation_claim_provenance_report(
    state_dir: Path,
    *,
    provenance: list[dict[str, Any]] | None = None,
    coverage: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    provenance = provenance if provenance is not None else read_translation_provenance(state_dir) or build_translation_provenance(state_dir, run_id=run_id, write=False)
    coverage = coverage or build_provenance_coverage_report(state_dir, provenance=provenance, run_id=run_id, write=False)
    artifacts = _artifacts(state_dir)
    scorecard = artifacts["evaluation_scorecard"]
    claim_acceptance = artifacts["claim_acceptance_decision"]
    signoff = artifacts["signoff_record"]
    forbidden = set(PROVENANCE_CLAIMS)
    forbidden.update(str(item) for item in scorecard.get("forbidden_claims", []) if item)
    forbidden.update(str(item) for item in claim_acceptance.get("forbidden_claims_remaining", []) if item)
    forbidden.update(str(item) for item in signoff.get("forbidden_claims_remaining", []) if item)
    supported = set(_strings(claim_acceptance.get("accepted_claims")))
    limited = set(_strings(claim_acceptance.get("accepted_with_limitations")))
    for claim in supported | limited:
        forbidden.discard(claim)
    if coverage.get("status") in {"blocked", "review_required"}:
        forbidden.update({"provider_backed_quality", "knowledge_backed_quality", "review_complete", "delivery_ready", "apply_ready", "production_ready"})
    claims = []
    for claim in sorted(PROVENANCE_CLAIMS | supported | limited | forbidden):
        status = "forbidden" if claim in forbidden else "limited" if claim in limited else "supported" if claim in supported else "unsupported"
        claims.append(
            {
                "claim": claim,
                "status": status,
                "supporting_evidence": _claim_evidence(provenance, claim),
                "blocking_evidence": _blocking_evidence(provenance, claim) if status in {"forbidden", "unsupported"} else [],
                "limitations": _claim_limitations(claim, coverage),
            }
        )
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-translation-claim-provenance-report-v1",
        "artifact": TRANSLATION_CLAIM_PROVENANCE_REPORT_JSON,
        "run_id": run_id or _run_id_from_records(provenance) or scorecard.get("run_id"),
        "status": "blocked" if any(item["status"] == "forbidden" for item in claims) else "limited" if any(item["status"] == "limited" for item in claims) else "supported",
        "claims": claims,
        "forbidden_claims": sorted(claim for claim in forbidden if claim),
        "supported_claims": sorted(supported),
        "limited_claims": sorted(limited),
        "source_artifacts": _existing_artifacts(
            state_dir,
            [
                "evaluation-scorecard.json",
                "claim-acceptance-decision.json",
                "signoff-record.json",
                PROVENANCE_COVERAGE_REPORT_JSON,
                TRANSLATION_PROVENANCE_JSONL,
            ],
        ),
        "limitations": [
            "claim provenance explains why claims are supported, limited, unsupported, or forbidden",
            "claim provenance is not a bypass around scorecard, signoff, readiness, or artifact-state gates",
        ],
    }
    if write:
        write_json(state_dir / TRANSLATION_CLAIM_PROVENANCE_REPORT_JSON, report)
    return report


def read_translation_claim_provenance_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / TRANSLATION_CLAIM_PROVENANCE_REPORT_JSON)


def translation_provenance_asset_paths(state_dir: Path) -> dict[str, str]:
    return {
        key: name
        for key, name in {
            "translation_provenance": TRANSLATION_PROVENANCE_JSONL,
            "segment_evidence_view": SEGMENT_EVIDENCE_VIEW_JSON,
            "provenance_coverage_report": PROVENANCE_COVERAGE_REPORT_JSON,
            "translation_claim_provenance_report": TRANSLATION_CLAIM_PROVENANCE_REPORT_JSON,
        }.items()
        if (state_dir / name).is_file()
    }


def _segment_record(segment: dict[str, Any], artifacts: dict[str, Any], *, run_id: str | None) -> dict[str, Any]:
    segment_id = str(segment.get("segment_id") or segment.get("id") or _stable_id("segment", segment))
    source = str(segment.get("source") or "")
    target = str(segment.get("target") or segment.get("target_text") or "")
    evidence = _segment_evidence(segment_id, source, target, artifacts)
    forbidden = _segment_forbidden_claims(evidence, artifacts)
    supported = _segment_supported_claims(evidence, artifacts) - forbidden
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-translation-provenance-record-v1",
        "artifact": TRANSLATION_PROVENANCE_JSONL,
        "run_id": run_id or _artifact_run_id(artifacts),
        "segment_id": segment_id,
        "source": source,
        "target_hash": _hash_text(target),
        "source_file": str(segment.get("source_file") or segment.get("path") or segment.get("file") or ""),
        "target_locale": _target_locale(artifacts),
        "scope": _segment_scope(segment_id),
        "evidence": evidence,
        "supported_claims": sorted(supported),
        "forbidden_claims": sorted(forbidden),
        "unsupported_claims": sorted(PROVENANCE_CLAIMS - supported - forbidden),
        "summary": {
            "evidence_count": len(evidence),
            "approved_evidence_count": sum(1 for item in evidence if item["evidence_status"] in {"approved", "locked", "accepted", "passed"}),
            "reference_only_evidence_count": sum(1 for item in evidence if item["evidence_status"] == "reference_only"),
            "stale_evidence_count": sum(1 for item in evidence if item["evidence_status"] == "stale"),
            "forbidden_claim_count": len(forbidden),
        },
    }


def _segment_evidence(segment_id: str, source: str, target: str, artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = []
    evidence.extend(_term_evidence(source, target, artifacts))
    evidence.extend(_knowledge_evidence(segment_id, source, target, artifacts))
    evidence.extend(_repair_evidence(segment_id, artifacts))
    evidence.extend(_provider_evidence(segment_id, artifacts))
    evidence.extend(_human_review_evidence(segment_id, artifacts))
    evidence.extend(_locale_evidence(artifacts))
    evidence.extend(_run_claim_evidence(artifacts))
    return evidence


def _term_evidence(source: str, target: str, artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = []
    for row in artifacts["term_registry"]:
        term = str(row.get("source_term") or row.get("source") or "")
        target_term = str(row.get("target_term") or row.get("target") or "")
        if term and (term.casefold() in source.casefold() or target_term and target_term in target):
            status = str(row.get("status") or "approved")
            evidence.append(_evidence("term", status, "term-registry.csv", term, target_term, ["full_terminology_assurance"]))
    for row in artifacts["forbidden_translations"]:
        forbidden = str(row.get("forbidden_target") or row.get("target") or "")
        if forbidden and forbidden in target:
            evidence.append(_evidence("forbidden_translation", "blocked", "forbidden-translations.csv", str(row.get("source_term") or ""), forbidden, ["full_terminology_assurance"]))
    return evidence


def _knowledge_evidence(segment_id: str, source: str, target: str, artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = []
    for item in artifacts["knowledge_usage_report"].get("usage_entries", []):
        if not isinstance(item, dict):
            continue
        value = str(item.get("source_value") or "")
        target_value = str(item.get("target_value") or "")
        if value and value.casefold() not in source.casefold() and (not target_value or target_value not in target):
            continue
        state = str(item.get("usage_state") or "not_used")
        status = "reference_only" if state == "shown_reference_only" else "stale" if state == "excluded_stale" else "rejected" if state in {"excluded_rejected", "excluded_superseded"} else "approved" if state.startswith("applied_") else "not_used"
        evidence.append(_evidence("knowledge", status, "knowledge-usage-report.json", value, target_value, _knowledge_claims(state), knowledge_id=str(item.get("knowledge_id") or ""), usage_state=state))
    for item in artifacts["constraint_application_audit"].get("audited_constraints", []):
        if not isinstance(item, dict):
            continue
        affected = set(_strings(item.get("affected_segments")))
        if affected and segment_id not in affected:
            continue
        evidence.append(_evidence("constraint_audit", str(item.get("status") or "unknown"), "constraint-application-audit.json", str(item.get("constraint_id") or ""), str(item.get("source_knowledge_item_id") or ""), ["knowledge_constraints_applied"]))
    return evidence


def _repair_evidence(segment_id: str, artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = []
    requests = artifacts["repair_request"].get("requests", []) if isinstance(artifacts["repair_request"], dict) else []
    for item in requests:
        if isinstance(item, dict) and segment_id in set(_strings(item.get("affected_segment_ids") or item.get("segment_ids"))):
            evidence.append(_evidence("repair_request", str(item.get("status") or "pending"), "repair-request.json", str(item.get("request_id") or item.get("repair_id") or ""), "", ["review_complete"]))
    results = artifacts["repair_result"].get("results", []) if isinstance(artifacts["repair_result"], dict) else []
    for item in results:
        if isinstance(item, dict) and segment_id in set(_strings(item.get("affected_segment_ids") or item.get("segment_ids"))):
            evidence.append(_evidence("repair_result", str(item.get("status") or "unknown"), "repair-result.json", str(item.get("repair_id") or ""), "", ["review_complete"]))
    for item in artifacts["knowledge_repair_reconciliation"].get("reconciled_results", []):
        if isinstance(item, dict) and segment_id in set(_strings(item.get("affected_segment_ids"))):
            evidence.append(_evidence("knowledge_repair_reconciliation", str(item.get("status") or item.get("reconciliation_status") or "unknown"), "knowledge-repair-reconciliation.json", str(item.get("result_id") or ""), "", ["knowledge_constraints_applied"]))
    return evidence


def _provider_evidence(segment_id: str, artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = []
    accepted = set(_strings(artifacts["provider_result_acceptance_decision"].get("accepted_result_ids"))) | set(_strings(artifacts["provider_result_acceptance_decision"].get("accepted_with_limitations_result_ids")))
    qa_by_id = {str(item.get("result_id") or ""): item for item in artifacts["provider_result_qa_report"].get("results", []) if isinstance(item, dict)}
    for record in artifacts["provider_result_intake"]:
        if not isinstance(record, dict):
            continue
        segments = record.get("segments", []) if isinstance(record.get("segments"), list) else []
        if segments and segment_id not in {str(item.get("segment_id") or "") for item in segments if isinstance(item, dict)}:
            continue
        result_id = str(record.get("result_id") or "")
        source = str(record.get("result_source") or record.get("provider_status") or "unknown")
        if source in {"synthetic", "mock", "dry_run", "local_draft", "failed"}:
            status = source
        elif result_id in accepted and qa_by_id.get(result_id, {}).get("status") in {"passed", "requires_human_review"}:
            status = "accepted"
        else:
            status = str(record.get("status") or "unverified")
        evidence.append(_evidence("provider_result", status, "provider-result-intake.jsonl", result_id, "", ["provider_execution_complete", "provider_backed_quality"], provider_source=source))
    return evidence


def _human_review_evidence(segment_id: str, artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = []
    for record in artifacts["human_review_evidence"]:
        if not isinstance(record, dict):
            continue
        scope = record.get("review_scope", {}) if isinstance(record.get("review_scope"), dict) else {}
        segment_ids = set(_strings(scope.get("segment_ids") or scope.get("segments")))
        if segment_ids and segment_id not in segment_ids:
            continue
        if scope and str(scope.get("scope_type") or "") not in {"full_run", "all"} and not segment_ids:
            continue
        evidence.append(_evidence("human_review", str(record.get("status") or "unknown"), "human-review-evidence.jsonl", str(record.get("evidence_id") or ""), "", ["review_complete"]))
    return evidence


def _locale_evidence(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    impact = artifacts["locale_readiness_impact"]
    risk = artifacts["locale_risk_report"]
    if not impact and not risk:
        return []
    status = str(impact.get("status") or risk.get("status") or "unknown")
    claims = _strings(impact.get("forbidden_claims") or risk.get("forbidden_claims"))
    return [_evidence("locale", status, "locale-readiness-impact.json" if impact else "locale-risk-report.json", str(impact.get("target_locale") or risk.get("target_locale") or ""), "", claims)]


def _run_claim_evidence(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = []
    scorecard = artifacts["evaluation_scorecard"]
    if scorecard:
        evidence.append(_evidence("scorecard", str(scorecard.get("overall_claim") or scorecard.get("status") or "unknown"), "evaluation-scorecard.json", "overall_claim", str(scorecard.get("overall_claim") or ""), _strings(scorecard.get("forbidden_claims"))))
    readiness = artifacts["readiness_authorization_matrix"]
    if readiness:
        evidence.append(_evidence("readiness_matrix", str(readiness.get("delivery_readiness_status", {}).get("status") or readiness.get("status") or "unknown"), "readiness-authorization-matrix.json", "readiness", "", _strings(readiness.get("forbidden_claims"))))
    return evidence


def _segment_supported_claims(evidence: list[dict[str, Any]], artifacts: dict[str, Any]) -> set[str]:
    supported = set(_strings(artifacts["claim_acceptance_decision"].get("accepted_claims")))
    supported.update(_strings(artifacts["claim_acceptance_decision"].get("accepted_with_limitations")))
    if any(item["evidence_type"] == "term" and item["evidence_status"] in {"approved", "locked"} for item in evidence):
        supported.add("full_terminology_assurance")
    if any(item["evidence_type"] == "human_review" and item["evidence_status"] in {"accepted", "accepted_with_limitations"} for item in evidence):
        supported.add("review_complete")
    if any(item["evidence_type"] == "provider_result" and item["evidence_status"] == "accepted" for item in evidence):
        supported.add("provider_execution_complete")
    if any(item["evidence_type"] == "constraint_audit" and item["evidence_status"] == "checked_pass" for item in evidence):
        supported.add("knowledge_constraints_applied")
    return supported


def _segment_forbidden_claims(evidence: list[dict[str, Any]], artifacts: dict[str, Any]) -> set[str]:
    forbidden = set(_strings(artifacts["evaluation_scorecard"].get("forbidden_claims")))
    forbidden.update(_strings(artifacts["claim_acceptance_decision"].get("forbidden_claims_remaining")))
    forbidden.update(_strings(artifacts["signoff_record"].get("forbidden_claims_remaining")))
    for item in evidence:
        if item["evidence_status"] in {"reference_only", "stale", "rejected", "synthetic", "mock", "dry_run", "failed", "blocked", "checked_fail"}:
            forbidden.update(_strings(item.get("claims_affected")))
    return forbidden & PROVENANCE_CLAIMS


def _missing_evidence(provenance: list[dict[str, Any]]) -> list[dict[str, Any]]:
    missing = []
    for item in provenance:
        types = {str(evidence.get("evidence_type") or "") for evidence in item.get("evidence", [])}
        for evidence_type in ("term", "knowledge", "provider_result", "human_review", "locale"):
            if evidence_type not in types:
                missing.append({"segment_id": item.get("segment_id"), "evidence_type": evidence_type, "status": "missing"})
    return missing


def _claim_evidence(provenance: list[dict[str, Any]], claim: str) -> list[dict[str, Any]]:
    return [
        {"segment_id": item.get("segment_id"), "evidence_type": evidence.get("evidence_type"), "evidence_status": evidence.get("evidence_status"), "source_artifact": evidence.get("source_artifact")}
        for item in provenance
        for evidence in item.get("evidence", [])
        if claim in set(_strings(evidence.get("claims_affected"))) and evidence.get("evidence_status") in {"approved", "locked", "accepted", "passed", "checked_pass"}
    ][:50]


def _blocking_evidence(provenance: list[dict[str, Any]], claim: str) -> list[dict[str, Any]]:
    return [
        {"segment_id": item.get("segment_id"), "evidence_type": evidence.get("evidence_type"), "evidence_status": evidence.get("evidence_status"), "source_artifact": evidence.get("source_artifact")}
        for item in provenance
        for evidence in item.get("evidence", [])
        if claim in set(_strings(evidence.get("claims_affected"))) and evidence.get("evidence_status") not in {"approved", "locked", "accepted", "passed", "checked_pass"}
    ][:50]


def _claim_limitations(claim: str, coverage: dict[str, Any]) -> list[str]:
    limitations = []
    if coverage.get("status") != "covered":
        limitations.append("provenance coverage is incomplete, stale, reference-only, or includes unverified provider evidence")
    if claim in {"provider_backed_quality", "knowledge_backed_quality", "review_complete"}:
        limitations.append("provenance does not prove semantic quality by itself")
    return limitations


def _artifacts(state_dir: Path) -> dict[str, Any]:
    return {
        "generated_segments": _read_jsonl(state_dir / "generated-segments.jsonl"),
        "term_registry": _read_csv(state_dir / "term-registry.csv"),
        "forbidden_translations": _read_csv(state_dir / "forbidden-translations.csv"),
        "knowledge_usage_report": _read_json(state_dir / "knowledge-usage-report.json"),
        "constraint_application_audit": _read_json(state_dir / "constraint-application-audit.json"),
        "knowledge_assurance_summary": _read_json(state_dir / "knowledge-assurance-summary.json"),
        "repair_request": _read_json(state_dir / "repair-request.json"),
        "repair_result": _read_json(state_dir / "repair-result.json"),
        "knowledge_repair_reconciliation": _read_json(state_dir / "knowledge-repair-reconciliation.json"),
        "knowledge_repair_closure_decision": _read_json(state_dir / "knowledge-repair-closure-decision.json"),
        "provider_result_intake": _read_jsonl(state_dir / "provider-result-intake.jsonl"),
        "provider_result_qa_report": _read_json(state_dir / "provider-result-qa-report.json"),
        "provider_result_acceptance_decision": _read_json(state_dir / "provider-result-acceptance-decision.json"),
        "human_review_evidence": _read_jsonl(state_dir / "human-review-evidence.jsonl"),
        "claim_acceptance_decision": _read_json(state_dir / "claim-acceptance-decision.json"),
        "signoff_record": _read_json(state_dir / "signoff-record.json"),
        "locale_risk_report": _read_json(state_dir / "locale-risk-report.json"),
        "locale_readiness_impact": _read_json(state_dir / "locale-readiness-impact.json"),
        "evaluation_scorecard": _read_json(state_dir / "evaluation-scorecard.json"),
        "readiness_authorization_matrix": _read_json(state_dir / "readiness-authorization-matrix.json"),
        "localization_brief": _read_json(state_dir / "localization-brief.json"),
    }


def _evidence(
    evidence_type: str,
    status: str,
    source_artifact: str,
    source_value: str,
    target_value: str,
    claims: list[str],
    **extra: Any,
) -> dict[str, Any]:
    record = {
        "evidence_id": _stable_id("evidence", [evidence_type, status, source_artifact, source_value, target_value, claims, extra]),
        "evidence_type": evidence_type,
        "evidence_status": status,
        "source_artifact": source_artifact,
        "source_value": source_value,
        "target_value": target_value,
        "claims_affected": sorted(set(claims) & PROVENANCE_CLAIMS),
    }
    record.update({key: value for key, value in extra.items() if value not in (None, "", [], {})})
    return record


def _knowledge_claims(state: str) -> list[str]:
    if state in {"applied_hard_constraint", "applied_negative_constraint"}:
        return ["knowledge_constraints_applied", "knowledge_backed_quality"]
    if state == "shown_reference_only":
        return ["knowledge_backed_quality"]
    return ["knowledge_backed_quality", "knowledge_review_complete"]


def _evidence_by_status(provenance: list[dict[str, Any]], statuses: set[str]) -> list[dict[str, Any]]:
    return [
        {"segment_id": item.get("segment_id"), **evidence}
        for item in provenance
        for evidence in item.get("evidence", [])
        if evidence.get("evidence_status") in statuses
    ]


def _all_evidence(provenance: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"segment_id": item.get("segment_id"), **evidence} for item in provenance for evidence in item.get("evidence", [])]


def _count_evidence(provenance: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for evidence in _all_evidence(provenance):
        value = str(evidence.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _target_locale(artifacts: dict[str, Any]) -> str:
    brief = artifacts["localization_brief"]
    intent = brief.get("task_intent", {}) if isinstance(brief, dict) else {}
    values = intent.get("target_locales")
    return str(values[0]) if isinstance(values, list) and values else str(artifacts["locale_readiness_impact"].get("target_locale") or "")


def _segment_scope(segment_id: str) -> dict[str, Any]:
    return {"scope_type": "segment", "segment_ids": [segment_id]}


def _artifact_run_id(artifacts: dict[str, Any]) -> str | None:
    for value in artifacts.values():
        if isinstance(value, dict) and value.get("run_id"):
            return str(value["run_id"])
    return None


def _run_id_from_records(records: list[dict[str, Any]]) -> str | None:
    for item in records:
        if item.get("run_id"):
            return str(item["run_id"])
    return None


def _existing_artifacts(state_dir: Path, names: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in names:
        if not (state_dir / name).is_file():
            continue
        key = name
        for suffix in (".jsonl", ".json", ".md", ".csv"):
            key = key.removesuffix(suffix)
        result[key.replace("-", "_")] = name
    return result


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing translation provenance artifact: {path}")
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Translation provenance artifact must be a JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [item for item in read_jsonl(path) if isinstance(item, dict)]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, str) and value:
        return [value]
    return []


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, value: Any) -> str:
    payload = repr(value).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:24]}"
