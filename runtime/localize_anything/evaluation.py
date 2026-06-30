from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .human_review import (
    CLAIM_ACCEPTANCE_DECISION_JSON,
    HUMAN_REVIEW_EVIDENCE_JSONL,
    SIGNOFF_RECORD_JSON,
    summarize_human_review_evidence,
    summarize_signoff_record,
)
from .document_evidence import (
    CLAIM_METRIC_REPORT_JSON,
    DOCUMENT_EVIDENCE_MANIFEST_JSON,
    DOCUMENT_INTAKE_REPORT_JSON,
    OPEN_DECISIONS_MD,
    PUBLICITY_RISK_REPORT_JSON,
    SEMANTIC_ALIGNMENT_JSONL,
)
from .document_decision import DOCUMENT_CLAIM_RESOLUTION_JSON, DOCUMENT_SIGNOFF_SUMMARY_JSON
from .io_utils import read_json, read_jsonl, write_json
from .knowledge_usage import (
    CONSTRAINT_APPLICATION_AUDIT_JSON,
    KNOWLEDGE_CONFLICT_REPORT_JSON,
    KNOWLEDGE_USAGE_REPORT_JSON,
)
from .knowledge_audit_enforcement import KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON
from .knowledge_review_confirmation import KNOWLEDGE_ASSURANCE_SUMMARY_JSON
from .knowledge_repair import (
    KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON,
    KNOWLEDGE_REPAIR_PLAN_JSON,
    KNOWLEDGE_REPAIR_REQUEST_JSON,
)
from .knowledge_repair_result import (
    KNOWLEDGE_REPAIR_QA_REPORT_JSON,
    KNOWLEDGE_REPAIR_RECONCILIATION_JSON,
    KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL,
)
from .knowledge_repair_closure import (
    KNOWLEDGE_READINESS_IMPACT_REPORT_JSON,
    KNOWLEDGE_RECOMPUTE_PLAN_JSON,
    KNOWLEDGE_RECOMPUTE_RESULT_JSON,
    KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON,
)
from .provider_evidence import (
    PROVIDER_EVIDENCE_RECONCILIATION_JSON,
    PROVIDER_EXECUTION_LEDGER_JSONL,
    PROVIDER_EXECUTION_POLICY_JSON,
    PROVIDER_HANDOFF_REQUEST_JSON,
    PROVIDER_RESULT_INTAKE_JSONL,
)
from .provider_result_gate import (
    PROVIDER_CLAIMS,
    PROVIDER_CLAIM_SUPPORT_REPORT_JSON,
    PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON,
    PROVIDER_RESULT_QA_REPORT_JSON,
    PROVIDER_RESULT_REVIEW_EVIDENCE_JSONL,
    WORKBENCH_PROVIDER_REVIEW_QUEUE_JSON,
)
from .locale_capability import (
    LOCALE_CAPABILITY_REPORT_JSON,
    LOCALE_CLAIMS,
    LOCALE_READINESS_IMPACT_JSON,
    LOCALE_RISK_REPORT_JSON,
)


EVALUATION_SCORECARD_JSON = "evaluation-scorecard.json"
EVIDENCE_LEVEL_REPORT_MD = "evidence-level-report.md"

E0 = "E0_deterministic_structural_qa"
E1 = "E1_automated_semantic_or_policy_review"
E2 = "E2_bilingual_human_spot_check"
E3 = "E3_native_language_review"
E4 = "E4_professional_localization_review"
EVIDENCE_LEVELS = [E0, E1, E2, E3, E4]

DIMENSION_NAMES = [
    "structural_qa",
    "provider_status",
    "locale_assurance",
    "terminology_assurance",
    "knowledge_assurance",
    "coverage_assurance",
    "resolution_status",
    "handoff_readiness",
    "artifact_freshness",
    "segment_reuse_readiness",
    "repair_readiness",
    "review_readiness",
    "delivery_readiness",
    "apply_readiness",
]


def build_evaluation_scorecard(
    state_dir: Path,
    *,
    run_dir: Path | None = None,
    delivery_dir: Path | None = None,
    run_id: str | None = None,
    generation_metadata: dict[str, Any] | None = None,
    coverage_diagnostics: dict[str, Any] | None = None,
    qa_result_paths: list[Path] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    run_dir = run_dir.resolve() if run_dir else None
    delivery_dir = delivery_dir.resolve() if delivery_dir else None
    artifacts = _load_artifacts(state_dir, run_dir, delivery_dir, qa_result_paths)
    provider = _provider_metadata(artifacts, generation_metadata)
    coverage = coverage_diagnostics or _coverage_from_artifacts(artifacts)
    dimensions = {
        "structural_qa": _structural_qa_dimension(artifacts),
        "provider_status": _provider_dimension(provider),
        "locale_assurance": _locale_dimension(artifacts),
        "terminology_assurance": _terminology_dimension(artifacts),
        "knowledge_assurance": _knowledge_dimension(artifacts),
        "coverage_assurance": _coverage_dimension(coverage, artifacts),
        "resolution_status": _resolution_dimension(artifacts),
        "handoff_readiness": _handoff_dimension(artifacts),
        "artifact_freshness": _artifact_freshness_dimension(artifacts),
        "segment_reuse_readiness": _segment_reuse_dimension(artifacts),
        "repair_readiness": _repair_dimension(artifacts),
        "review_readiness": _review_dimension(artifacts),
        "delivery_readiness": _delivery_dimension(artifacts),
        "apply_readiness": _apply_dimension(artifacts),
    }
    forbidden_claims = _forbidden_claims(dimensions, artifacts, provider, coverage)
    evidence_level = _evidence_level(dimensions, artifacts)
    overall_claim = _overall_claim(dimensions, forbidden_claims, evidence_level, artifacts, provider)
    status = "blocked" if overall_claim == "blocked" else "pass_with_warnings" if forbidden_claims else "pass"
    scorecard = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-evaluation-scorecard-v1",
        "run_id": run_id or _run_id(artifacts),
        "status": status,
        "overall_claim": overall_claim,
        "evidence_level": evidence_level,
        "human_review_evidence": _human_review_summary(artifacts),
        "claim_acceptance": _claim_acceptance_summary(artifacts),
        "signoff": _signoff_summary(artifacts),
        **dimensions,
        "dimensions": dimensions,
        "forbidden_claims": forbidden_claims,
        "recommended_next_actions": _recommended_next_actions(dimensions, forbidden_claims, artifacts),
        "source_artifacts": _source_artifacts(state_dir, run_dir, delivery_dir),
        "limitations": [
            "evaluation scorecard summarizes existing artifacts and does not perform translation",
            "missing evidence is treated conservatively and cannot support full quality claims",
            "E2-E4 levels require explicit human-review-evidence records from qualified review roles",
            "project owner signoff can accept risk but does not create E2-E4 review evidence",
        ],
    }
    report = render_evidence_level_report(scorecard)
    if write:
        state_dir.mkdir(parents=True, exist_ok=True)
        write_json(state_dir / EVALUATION_SCORECARD_JSON, scorecard)
        (state_dir / EVIDENCE_LEVEL_REPORT_MD).write_text(report, encoding="utf-8", newline="\n")
    return scorecard


def read_evaluation_scorecard(state_dir: Path) -> dict[str, Any]:
    path = state_dir / EVALUATION_SCORECARD_JSON
    if not path.is_file():
        raise ValueError(f"Missing evaluation scorecard: {path}")
    return read_json(path)


def evaluation_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "evaluation_scorecard": EVALUATION_SCORECARD_JSON,
        "evidence_level_report": EVIDENCE_LEVEL_REPORT_MD,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def render_evidence_level_report(scorecard: dict[str, Any]) -> str:
    evidence = scorecard.get("evidence_level", {})
    levels = evidence.get("levels", {}) if isinstance(evidence, dict) else {}
    lines = [
        "# Evidence Level Report",
        "",
        f"- Run ID: `{scorecard.get('run_id')}`",
        f"- Overall claim: `{scorecard.get('overall_claim')}`",
        f"- Highest evidence level: `{evidence.get('highest_supported', 'not_provided')}`",
        f"- Highest global human review level: `{evidence.get('highest_global_human_supported', 'not_provided')}`",
        "",
        "## What Passed",
        "",
    ]
    passed = [
        name
        for name in DIMENSION_NAMES
        if scorecard.get(name, {}).get("status") == "pass"
    ]
    lines.extend([f"- `{name}`" for name in passed] or ["- No fully passing dimension was proven."])
    lines.extend(["", "## Blocked", ""])
    blocked = [
        (name, scorecard.get(name, {}))
        for name in DIMENSION_NAMES
        if scorecard.get(name, {}).get("status") == "blocked"
    ]
    if blocked:
        for name, dimension in blocked:
            blockers = ", ".join(str(item) for item in dimension.get("blockers", [])) or str(dimension.get("summary", "blocked"))
            lines.append(f"- `{name}`: {blockers}")
    else:
        lines.append("- No blocking evidence was found.")
    lines.extend(["", "## Downgraded", ""])
    downgraded = [
        (name, scorecard.get(name, {}))
        for name in DIMENSION_NAMES
        if scorecard.get(name, {}).get("status") in {"warning", "unknown", "not_provided"}
    ]
    if downgraded:
        for name, dimension in downgraded:
            warnings = ", ".join(str(item) for item in dimension.get("warnings", [])) or str(dimension.get("summary", "not proven"))
            lines.append(f"- `{name}`: {warnings}")
    else:
        lines.append("- No downgraded evidence dimensions.")
    lines.extend(["", "## Evidence Levels", ""])
    for level in EVIDENCE_LEVELS:
        value = levels.get(level, {})
        lines.append(f"- `{level}`: `{value.get('status', 'not_provided')}` - {value.get('summary', '')}")
    lines.extend(["", "## Claim Acceptance", ""])
    claim_acceptance = scorecard.get("claim_acceptance", {})
    lines.append(f"- Status: `{claim_acceptance.get('status', 'not_provided')}`")
    lines.append(f"- Accepted claims: `{', '.join(claim_acceptance.get('accepted_claims', [])) or 'none'}`")
    lines.append(f"- Rejected claims: `{', '.join(claim_acceptance.get('rejected_claims', [])) or 'none'}`")
    lines.extend(["", "## Human Review And Signoff", ""])
    human_review = scorecard.get("human_review_evidence", {})
    signoff = scorecard.get("signoff", {})
    lines.append(f"- Human review status: `{human_review.get('status', 'not_provided')}`")
    lines.append(f"- Global levels: `{', '.join(human_review.get('global_supported_levels', [])) or 'none'}`")
    lines.append(f"- Limited-scope levels: `{', '.join(human_review.get('limited_supported_levels', [])) or 'none'}`")
    lines.append(f"- Signoff status: `{signoff.get('status', 'not_provided')}`")
    lines.append(f"- Delivery authorized: `{bool(signoff.get('delivery_authorized'))}`")
    lines.append(f"- Apply authorized: `{bool(signoff.get('apply_authorized'))}`")
    lines.extend(["", "## Forbidden Claims", ""])
    lines.extend([f"- `{claim}`" for claim in scorecard.get("forbidden_claims", [])] or ["- None."])
    lines.extend(["", "## Recommended Next Actions", ""])
    lines.extend([f"- {action}" for action in scorecard.get("recommended_next_actions", [])] or ["- No next action recorded."])
    return "\n".join(lines) + "\n"


def _load_artifacts(
    state_dir: Path,
    run_dir: Path | None,
    delivery_dir: Path | None,
    qa_result_paths: list[Path] | None,
) -> dict[str, Any]:
    delivery_manifest = _read_optional_json((delivery_dir / "delivery-manifest.json") if delivery_dir else state_dir / "delivery-manifest.json")
    return {
        "localization_brief": _read_optional_json(state_dir / "localization-brief.json"),
        "termbase_preflight_report": _read_optional_json(state_dir / "termbase-preflight-report.json"),
        "generation_strategy": _read_optional_json(state_dir / "generation-strategy.json"),
        "knowledge_pack_selection": _read_optional_json(state_dir / "knowledge-pack-selection.json"),
        "knowledge_eligibility_report": _read_optional_json(state_dir / "knowledge-eligibility-report.json"),
        "working_context_packet": _read_optional_json(state_dir / "working-context-packet.json"),
        "knowledge_usage_report": _read_optional_json(state_dir / KNOWLEDGE_USAGE_REPORT_JSON),
        "constraint_application_audit": _read_optional_json(state_dir / CONSTRAINT_APPLICATION_AUDIT_JSON),
        "knowledge_conflict_report": _read_optional_json(state_dir / KNOWLEDGE_CONFLICT_REPORT_JSON),
        "knowledge_audit_enforcement_decision": _read_optional_json(state_dir / KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON),
        "knowledge_assurance_summary": _read_optional_json(state_dir / KNOWLEDGE_ASSURANCE_SUMMARY_JSON),
        "knowledge_repair_plan": _read_optional_json(state_dir / KNOWLEDGE_REPAIR_PLAN_JSON),
        "knowledge_repair_request": _read_optional_json(state_dir / KNOWLEDGE_REPAIR_REQUEST_JSON),
        "knowledge_repair_impact_report": _read_optional_json(state_dir / KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON),
        "knowledge_repair_result_intake": _read_optional_jsonl(state_dir / KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL),
        "knowledge_repair_qa_report": _read_optional_json(state_dir / KNOWLEDGE_REPAIR_QA_REPORT_JSON),
        "knowledge_repair_reconciliation": _read_optional_json(state_dir / KNOWLEDGE_REPAIR_RECONCILIATION_JSON),
        "knowledge_recompute_plan": _read_optional_json(state_dir / KNOWLEDGE_RECOMPUTE_PLAN_JSON),
        "knowledge_recompute_result": _read_optional_json(state_dir / KNOWLEDGE_RECOMPUTE_RESULT_JSON),
        "knowledge_repair_closure_decision": _read_optional_json(state_dir / KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON),
        "knowledge_readiness_impact_report": _read_optional_json(state_dir / KNOWLEDGE_READINESS_IMPACT_REPORT_JSON),
        "provider_execution_policy": _read_optional_json(state_dir / PROVIDER_EXECUTION_POLICY_JSON),
        "provider_handoff_request": _read_optional_json(state_dir / PROVIDER_HANDOFF_REQUEST_JSON),
        "provider_execution_ledger": _read_optional_jsonl(state_dir / PROVIDER_EXECUTION_LEDGER_JSONL),
        "provider_result_intake": _read_optional_jsonl(state_dir / PROVIDER_RESULT_INTAKE_JSONL),
        "provider_evidence_reconciliation": _read_optional_json(state_dir / PROVIDER_EVIDENCE_RECONCILIATION_JSON),
        "provider_result_qa_report": _read_optional_json(state_dir / PROVIDER_RESULT_QA_REPORT_JSON),
        "provider_result_review_evidence": _read_optional_jsonl(state_dir / PROVIDER_RESULT_REVIEW_EVIDENCE_JSONL),
        "provider_result_acceptance_decision": _read_optional_json(state_dir / PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON),
        "provider_claim_support_report": _read_optional_json(state_dir / PROVIDER_CLAIM_SUPPORT_REPORT_JSON),
        "workbench_provider_review_queue": _read_optional_json(state_dir / WORKBENCH_PROVIDER_REVIEW_QUEUE_JSON),
        "locale_capability_report": _read_optional_json(state_dir / LOCALE_CAPABILITY_REPORT_JSON),
        "locale_risk_report": _read_optional_json(state_dir / LOCALE_RISK_REPORT_JSON),
        "locale_readiness_impact": _read_optional_json(state_dir / LOCALE_READINESS_IMPACT_JSON),
        "readiness_authorization_matrix": _read_optional_json(state_dir / "readiness-authorization-matrix.json"),
        "manual_followup_gap_report": _read_optional_json(state_dir / "manual-followup-gap-report.json"),
        "apply_readiness_report": _read_optional_json(state_dir / "apply-readiness-report.json"),
        "delivery_readiness_report": _read_optional_json(state_dir / "delivery-readiness-report.json"),
        "blocking_questions": _read_optional_json(state_dir / "blocking-questions.json"),
        "resolution_options": _read_optional_json(state_dir / "resolution-options.json"),
        "user_resolution_decisions": _read_optional_jsonl(state_dir / "user-resolution-decisions.jsonl"),
        "generation_handoff_decision": _read_optional_json(state_dir / "generation-handoff-decision.json"),
        "artifact_state": _read_optional_json(state_dir / "artifact-state.json"),
        "human_review_evidence": _read_optional_jsonl(state_dir / HUMAN_REVIEW_EVIDENCE_JSONL),
        "claim_acceptance_decision": _read_optional_json(state_dir / CLAIM_ACCEPTANCE_DECISION_JSON),
        "signoff_record": _read_optional_json(state_dir / SIGNOFF_RECORD_JSON),
        "stale_segments": _read_optional_jsonl(state_dir / "stale-segments.jsonl"),
        "reuse_decision": _read_optional_json(state_dir / "reuse-decision.json"),
        "segment_regeneration_plan": _read_optional_json(state_dir / "segment-regeneration-plan.json"),
        "repair_request": _read_optional_json(state_dir / "repair-request.json"),
        "repair_result": _read_optional_json(state_dir / "repair-result.json"),
        "repair_history": _read_optional_jsonl(state_dir / "repair-history.jsonl"),
        "document_intake_report": _read_optional_json(state_dir / DOCUMENT_INTAKE_REPORT_JSON),
        "semantic_alignment": _read_optional_jsonl(state_dir / SEMANTIC_ALIGNMENT_JSONL),
        "claim_metric_report": _read_optional_json(state_dir / CLAIM_METRIC_REPORT_JSON),
        "publicity_risk_report": _read_optional_json(state_dir / PUBLICITY_RISK_REPORT_JSON),
        "document_evidence_manifest": _read_optional_json(state_dir / DOCUMENT_EVIDENCE_MANIFEST_JSON),
        "document_claim_resolution": _read_optional_json(state_dir / DOCUMENT_CLAIM_RESOLUTION_JSON),
        "document_signoff_summary": _read_optional_json(state_dir / DOCUMENT_SIGNOFF_SUMMARY_JSON),
        "open_decisions": _read_optional_text(state_dir / OPEN_DECISIONS_MD),
        "generated_segments": _read_optional_jsonl((run_dir / "generated.jsonl") if run_dir else state_dir / "generated-segments.jsonl"),
        "review_result": _first_json(
            [
                (run_dir / "llm-review-result.json") if run_dir else state_dir / "llm-review-result.json",
                (run_dir / "review-sheet.json") if run_dir else state_dir / "review-sheet.json",
                state_dir / "review-result.json",
            ]
        ),
        "delivery_manifest": delivery_manifest,
        "delivery_decision": _read_optional_json((run_dir / "delivery-decision.json") if run_dir else state_dir / "delivery-decision.json"),
        "apply_plan": _read_optional_json((run_dir / "apply-plan.json") if run_dir else state_dir / "apply-plan.json"),
        "qa": _qa_summary(delivery_manifest, qa_result_paths),
    }


def _structural_qa_dimension(artifacts: dict[str, Any]) -> dict[str, Any]:
    qa = artifacts.get("qa", {})
    status = str(qa.get("status") or "not_checked")
    blocking_count = int(qa.get("blocking_count", 0) or 0)
    warning_count = int(qa.get("warning_count", 0) or 0)
    if status in {"pass", "pass_with_warnings"} and not blocking_count:
        return _dimension("warning" if warning_count else "pass", E0, f"deterministic QA {status}", warnings=_count_warning(warning_count, "qa warnings"))
    if status in {"fail", "blocked"} or blocking_count:
        return _dimension("blocked", E0, "deterministic QA has blockers", blockers=["deterministic_qa_blocking"])
    return _dimension("not_provided", E0, "deterministic QA evidence was not provided", warnings=["deterministic_qa_missing"])


def _provider_dimension(provider: dict[str, Any]) -> dict[str, Any]:
    status = str(provider.get("provider_status") or "not_run")
    actual = str(provider.get("provider_actual") or provider.get("provider") or "unknown")
    reconciliation_status = str(provider.get("provider_evidence_reconciliation_status") or "")
    if reconciliation_status in {"blocked", "stale", "failed"}:
        return _dimension("blocked", E1, "provider execution evidence is blocked, stale, or failed", blockers=["provider_evidence_not_reconciled"])
    if status == "passed" and bool(provider.get("provider_execution_complete_supported")):
        return _dimension("pass", E1, f"provider execution was reconciled as {actual}")
    if status == "passed":
        return _dimension("warning", E1, f"provider output exists but execution evidence is not reconciled as provider-backed ({actual})", warnings=["provider_evidence_reconciliation_missing"])
    if status == "failed":
        return _dimension("blocked", E1, "provider failed or fallback output was detected", blockers=["provider_failed_or_fallback"])
    if status in {"synthetic_test", "not_applicable"} or actual in {"synthetic", "none", "synthetic_fallback"}:
        return _dimension("warning", E0, f"provider-backed quality not proven ({status})", warnings=["provider_backed_quality_not_proven"])
    return _dimension("not_provided", E0, "provider evidence was not provided", warnings=["provider_status_missing"])


def _locale_dimension(artifacts: dict[str, Any]) -> dict[str, Any]:
    capability = artifacts.get("locale_capability_report", {})
    risk = artifacts.get("locale_risk_report", {})
    impact = artifacts.get("locale_readiness_impact", {})
    if not capability and not risk and not impact:
        return _dimension("not_provided", E0, "locale capability evidence was not provided", warnings=["locale_capability_missing"])
    if str(impact.get("status") or "") in {"blocked", "stale"} or str(risk.get("status") or "") == "blocked":
        return _dimension("blocked", E1, "locale capability evidence blocks strong locale claims", blockers=["locale_capability_blocked"])
    if str(capability.get("status") or "") in {"unknown", "partial"} or str(risk.get("status") or "") == "review_required" or str(impact.get("status") or "") in {"review_required", "clear_with_warnings"}:
        return _dimension("warning", E1, "locale capability is partial or requires review", warnings=["locale_capability_downgraded"])
    if capability:
        return _dimension("pass", E1, "locale capability report has no active locale blockers")
    return _dimension("unknown", E0, "locale capability status is unknown", warnings=["locale_capability_unknown"])


def _terminology_dimension(artifacts: dict[str, Any]) -> dict[str, Any]:
    report = artifacts.get("termbase_preflight_report", {})
    assurance = str(report.get("terminology_assurance") or "not_checked")
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    if assurance == "reviewed":
        return _dimension("pass", E1, "terminology review is marked reviewed")
    if assurance == "blocked_by_conflict" or int(summary.get("conflict_count", 0) or 0):
        return _dimension("blocked", E1, "term conflicts are unresolved", blockers=["term_conflict"])
    if assurance == "incomplete_review_required" or int(summary.get("high_risk_unreviewed_count", 0) or 0):
        return _dimension("warning", E1, "terminology review is incomplete", warnings=["term_review_incomplete"])
    return _dimension("unknown", E0, "terminology assurance was not checked", warnings=["terminology_assurance_unknown"])


def _knowledge_dimension(artifacts: dict[str, Any]) -> dict[str, Any]:
    selection = artifacts.get("knowledge_pack_selection", {})
    eligibility = artifacts.get("knowledge_eligibility_report", {})
    context = artifacts.get("working_context_packet", {})
    usage = artifacts.get("knowledge_usage_report", {})
    audit = artifacts.get("constraint_application_audit", {})
    conflicts = artifacts.get("knowledge_conflict_report", {})
    enforcement = artifacts.get("knowledge_audit_enforcement_decision", {})
    assurance = artifacts.get("knowledge_assurance_summary", {})
    repair_impact = artifacts.get("knowledge_repair_impact_report", {})
    closure = artifacts.get("knowledge_repair_closure_decision", {})
    if not selection:
        return _dimension("not_provided", E0, "knowledge pack was not selected", warnings=["knowledge_pack_not_selected"])
    if not selection.get("selected_packs"):
        return _dimension("warning", E0, "no valid knowledge pack was selected", warnings=["knowledge_pack_invalid_or_rejected"])
    reconciliation = artifacts.get("knowledge_repair_reconciliation", {})
    repair_qa = artifacts.get("knowledge_repair_qa_report", {})
    if str(repair_qa.get("status") or "") in {"blocked", "requires_human_review", "stale"}:
        return _dimension("blocked", E1, "knowledge repair QA is not clear", blockers=["knowledge_repair_qa_blocked"])
    if str(reconciliation.get("status") or "") in {"blocked", "partial", "stale"}:
        return _dimension("blocked", E1, "knowledge repair reconciliation has active blockers", blockers=["knowledge_repair_reconciliation_blocked"])
    if int(repair_impact.get("summary", {}).get("repair_item_count", 0) or 0) and reconciliation.get("status") != "clear":
        return _dimension("blocked", E1, "required knowledge repairs are pending", blockers=["knowledge_repair_pending"])
    closure_status = str(closure.get("status") or "")
    if closure_status in {"stale", "still_blocked", "partially_closed", "requires_human_review", "requires_recompute"}:
        return _dimension("blocked", E1, "knowledge repair closure or recompute is incomplete", blockers=["knowledge_repair_closure_incomplete"])
    if assurance:
        assurance_status = str(assurance.get("status") or "")
        if assurance_status in {"blocked", "stale"}:
            return _dimension("blocked", E1, "knowledge assurance evidence is blocked or stale", blockers=["knowledge_assurance_blocked"])
        if "knowledge_constraints_applied" in set(assurance.get("supported_claims", [])):
            return _dimension(
                "pass",
                E1,
                "knowledge constraints were supported by deterministic audit or scoped human constraint review; full knowledge-backed quality is still not proven",
                warnings=["knowledge_backed_quality_not_proven"],
            )
    if enforcement:
        enforcement_status = str(enforcement.get("status") or "")
        if enforcement_status == "blocked":
            return _dimension("blocked", E1, "knowledge audit enforcement is blocked", blockers=["knowledge_audit_enforcement_blocked"])
        if enforcement_status == "stale":
            return _dimension("blocked", E1, "knowledge audit enforcement evidence is stale", blockers=["knowledge_audit_enforcement_stale"])
        if enforcement_status == "review_required":
            return _dimension("warning", E1, "knowledge audit enforcement requires review", warnings=["knowledge_audit_review_required"])
    if not eligibility or not context:
        return _dimension("blocked", E0, "knowledge consumption artifacts are incomplete", blockers=["knowledge_artifacts_incomplete"])
    if context.get("status") == "blocked":
        return _dimension("blocked", E1, "knowledge hard constraints conflict", blockers=["knowledge_constraint_conflict"])
    if conflicts and int(conflicts.get("summary", {}).get("blocking_conflict_count", 0) or 0):
        return _dimension("blocked", E1, "knowledge conflicts are unresolved", blockers=["knowledge_conflict_unresolved"])
    if audit and int(audit.get("summary", {}).get("checked_fail_count", 0) or 0):
        return _dimension("blocked", E1, "knowledge hard constraint checks failed", blockers=["knowledge_constraint_check_failed"])
    artifact_state = artifacts.get("artifact_state", {})
    stale_ids = {str(item.get("artifact_id")) for item in artifact_state.get("stale_artifacts", []) if isinstance(item, dict)}
    if stale_ids.intersection({"working_context_packet", "knowledge_eligibility_report", "knowledge_usage_report", "constraint_application_audit", "knowledge_conflict_report"}):
        return _dimension("blocked", E1, "knowledge context is stale", blockers=["knowledge_context_stale"])
    summary = eligibility.get("summary", {}) if isinstance(eligibility.get("summary"), dict) else {}
    constraint_count = int(summary.get("hard_constraint_count", 0) or 0) + int(summary.get("negative_constraint_count", 0) or 0)
    if not constraint_count:
        return _dimension("warning", E0, "selected knowledge is reference-only or ineligible", warnings=["knowledge_reference_only"])
    if not usage or not audit or not conflicts:
        return _dimension("warning", E1, "eligible knowledge constraints exist, but usage audit evidence is missing", warnings=["knowledge_usage_evidence_missing"])
    audit_summary = audit.get("summary", {}) if isinstance(audit.get("summary"), dict) else {}
    if int(audit_summary.get("pending_generation_count", 0) or 0):
        return _dimension("warning", E1, "knowledge constraints are eligible but pending generated target checks", warnings=["knowledge_constraint_audit_pending_generation"])
    if int(audit_summary.get("checked_pass_count", 0) or 0):
        return _dimension(
            "pass",
            E1,
            "knowledge constraints were deterministically applied and checked; full knowledge-backed quality is still not proven",
            warnings=["knowledge_backed_quality_not_proven"],
        )
    return _dimension(
        "warning",
        E1,
        "eligible knowledge constraints exist, but usage plus QA/review evidence was not recorded",
        warnings=["knowledge_usage_evidence_missing"],
    )


def _coverage_dimension(coverage: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    handoff = artifacts.get("generation_handoff_decision", {})
    forbidden = set(handoff.get("forbidden_quality_claims", [])) if isinstance(handoff, dict) else set()
    visible_warning = bool(coverage.get("visible_ui_coverage_warning"))
    mode = str(coverage.get("coverage_mode") or "unknown")
    document_blockers = _document_evidence_blockers(artifacts)
    if any(reason in document_blockers for reason in {"document_evidence_stale", "document_evidence_unsupported"}):
        return _dimension(
            "warning",
            E0,
            f"coverage is {mode} and document evidence is not complete",
            warnings=["full_coverage_not_proven", *document_blockers],
        )
    if visible_warning or "full_source_coverage" in forbidden or mode in {"source-only", "unknown"}:
        return _dimension("warning", E0, f"coverage is {mode} or downgraded", warnings=["full_coverage_not_proven"])
    if mode == "source-plus-merged-overlay" or coverage.get("full_coverage_claim") is True:
        return _dimension("pass", E0, "coverage evidence supports current source scope")
    return _dimension("unknown", E0, "coverage diagnostics were not provided", warnings=["coverage_unknown"])


def _resolution_dimension(artifacts: dict[str, Any]) -> dict[str, Any]:
    questions = artifacts.get("blocking_questions", {})
    handoff = artifacts.get("generation_handoff_decision", {})
    summary = questions.get("summary", {}) if isinstance(questions, dict) else {}
    unresolved_blocking = _unresolved_count(questions)
    unresolved_total = int(summary.get("unresolved_count", 0) or 0)
    review_required = int(summary.get("review_required_count", 0) or 0)
    handoff_unresolved = len(handoff.get("unresolved_questions", []) or []) if isinstance(handoff, dict) else 0
    if unresolved_blocking:
        return _dimension("blocked", E1, f"{unresolved_blocking} unresolved blocking questions", blockers=["unresolved_questions"])
    if unresolved_total or review_required or handoff_unresolved:
        return _dimension("warning", E1, "resolution gate still requires review", warnings=["resolution_review_required"])
    if questions or artifacts.get("resolution_options"):
        return _dimension("pass", E1, "resolution gate has no unresolved blocking questions")
    return _dimension("not_provided", E0, "resolution gate evidence was not provided", warnings=["resolution_gate_missing"])


def _handoff_dimension(artifacts: dict[str, Any]) -> dict[str, Any]:
    handoff = artifacts.get("generation_handoff_decision", {})
    status = str(handoff.get("status") or "not_checked")
    if status == "blocked" or handoff.get("handoff_allowed") is False:
        return _dimension("blocked", E1, "generation handoff is blocked", blockers=["handoff_blocked"])
    if handoff.get("full_quality_handoff_allowed") is True:
        return _dimension("pass", E1, "full-quality handoff is allowed")
    if handoff:
        return _dimension("warning", E1, f"handoff is downgraded ({status})", warnings=["handoff_downgraded"])
    return _dimension("not_provided", E0, "handoff decision was not provided", warnings=["handoff_missing"])


def _artifact_freshness_dimension(artifacts: dict[str, Any]) -> dict[str, Any]:
    state = artifacts.get("artifact_state", {})
    status = str(state.get("status") or "not_checked")
    summary = state.get("summary", {}) if isinstance(state, dict) else {}
    stale = int(summary.get("stale_count", 0) or 0)
    blocked = int(summary.get("blocked_count", 0) or 0)
    if blocked or status == "blocked":
        return _dimension("blocked", E1, "artifact state contains blocked evidence", blockers=["artifact_state_blocked"])
    if stale or status == "stale":
        return _dimension("blocked", E1, "artifact state contains stale evidence", blockers=["artifact_state_stale"])
    if state:
        return _dimension("pass", E1, "artifact state has no stale or blocked artifacts")
    return _dimension("not_provided", E0, "artifact state was not provided", warnings=["artifact_state_missing"])


def _segment_reuse_dimension(artifacts: dict[str, Any]) -> dict[str, Any]:
    reuse = artifacts.get("reuse_decision", {})
    decisions = reuse.get("decisions", {}) if isinstance(reuse, dict) else {}
    if decisions.get("generation_handoff_policy") == "blocked" or decisions.get("delivery_apply_policy") == "blocked":
        return _dimension("blocked", E1, "segment reuse requires regeneration or repair", blockers=["segment_reuse_blocked"])
    if decisions.get("generation_handoff_policy") == "warn" or decisions.get("review_required"):
        return _dimension("warning", E1, "segment reuse requires review", warnings=["segment_reuse_review_required"])
    if reuse:
        return _dimension("pass", E1, "segment reuse decision is ready")
    return _dimension("not_provided", E0, "segment reuse evidence was not provided", warnings=["segment_reuse_missing"])


def _repair_dimension(artifacts: dict[str, Any]) -> dict[str, Any]:
    repair = artifacts.get("repair_result", {})
    summary = repair.get("summary", {}) if isinstance(repair, dict) else {}
    pending = int(summary.get("pending_required_repair_count", 0) or 0) + int(summary.get("pending_provider_or_model_repair_count", 0) or 0)
    failed = int(summary.get("failed_qa_count", 0) or 0) + int(summary.get("blocked_count", 0) or 0)
    skipped = int(summary.get("skipped_not_deterministic_count", 0) or 0)
    reconciliation = artifacts.get("knowledge_repair_reconciliation", {})
    knowledge_pending = (
        int(artifacts.get("knowledge_repair_impact_report", {}).get("summary", {}).get("repair_item_count", 0) or 0)
        if reconciliation.get("status") != "clear"
        else 0
    )
    knowledge_qa_blocked = str(artifacts.get("knowledge_repair_qa_report", {}).get("status") or "") in {
        "blocked",
        "requires_human_review",
        "stale",
    }
    closure_status = str(artifacts.get("knowledge_repair_closure_decision", {}).get("status") or "")
    closure_blocked = closure_status in {"stale", "still_blocked", "partially_closed", "requires_human_review", "requires_recompute"}
    if pending or failed or skipped or knowledge_pending or knowledge_qa_blocked or closure_blocked:
        return _dimension("blocked", E1, "required repairs are pending, blocked, skipped, or failed QA", blockers=["repair_not_ready"])
    if repair:
        return _dimension("pass", E1, "repair result has no required pending repairs")
    return _dimension("not_provided", E0, "repair result was not provided", warnings=["repair_result_missing"])


def _review_dimension(artifacts: dict[str, Any]) -> dict[str, Any]:
    human = _human_review_summary(artifacts)
    if human.get("global_supported_levels"):
        level = str(human.get("highest_global_supported") or E2)
        return _dimension("pass", level, f"explicit global {level} human review evidence was provided")
    if human.get("limited_supported_levels"):
        level = str(human.get("highest_limited_supported") or E2)
        return _dimension("warning", level, "human review evidence is limited-scope only", warnings=["human_review_limited_scope"])
    if human.get("status") in {"requires_follow_up", "stale"}:
        return _dimension("warning", E1, "human review evidence is rejected, stale, or requires follow-up", warnings=["human_review_not_current"])
    term = _terminology_dimension(artifacts)
    repair = _repair_dimension(artifacts)
    document_blockers = _document_evidence_blockers(artifacts)
    if document_blockers:
        if _document_evidence_has_blocking_condition(document_blockers):
            return _dimension("blocked", E1, "document evidence has blocking or stale review evidence", blockers=document_blockers)
        return _dimension("warning", E1, "document evidence requires review or signoff", warnings=document_blockers)
    if term["status"] in {"blocked", "warning"} or repair["status"] == "blocked":
        return _dimension("warning", E1, "review is incomplete or required", warnings=["review_required"])
    if artifacts.get("review_result") or artifacts.get("delivery_decision"):
        return _dimension("warning", E1, "automated review exists but E2-E4 human review was not provided", warnings=["human_review_not_provided"])
    return _dimension("not_provided", E0, "review evidence was not provided", warnings=["review_missing"])


def _delivery_dimension(artifacts: dict[str, Any]) -> dict[str, Any]:
    upstream_blockers = _upstream_readiness_blockers(artifacts)
    if upstream_blockers:
        return _dimension("blocked", E1, "delivery readiness is blocked by upstream evidence", blockers=upstream_blockers)
    decision = artifacts.get("delivery_decision", {})
    manifest = artifacts.get("delivery_manifest", {})
    status = str(decision.get("status") or manifest.get("delivery_status") or "not_checked")
    if status == "blocked":
        return _dimension("blocked", E1, "delivery decision is blocked", blockers=["delivery_blocked"])
    if status in {"owner_review_required", "draft_package"}:
        return _dimension("warning", E1, f"delivery is {status}", warnings=["delivery_requires_review_or_confirmation"])
    if status in {"review_ready", "ready_no_changes", "user_accepted"}:
        return _dimension("pass", E1, f"delivery status is {status}")
    return _dimension("not_provided", E0, "delivery decision was not provided", warnings=["delivery_evidence_missing"])


def _apply_dimension(artifacts: dict[str, Any]) -> dict[str, Any]:
    upstream_blockers = _upstream_readiness_blockers(artifacts)
    decision = artifacts.get("delivery_decision", {})
    manifest = artifacts.get("delivery_manifest", {})
    delivery_status = str(decision.get("status") or manifest.get("delivery_status") or "")
    if delivery_status == "blocked":
        upstream_blockers.append("delivery_blocked")
    if upstream_blockers:
        return _dimension("blocked", E1, "apply readiness is blocked by upstream evidence", blockers=upstream_blockers)
    apply_plan = artifacts.get("apply_plan", {})
    if apply_plan.get("blocked_by_provider_status") or apply_plan.get("blocked_by_stale_artifacts"):
        return _dimension("blocked", E1, "apply plan is blocked by provider or stale evidence", blockers=["apply_blocked"])
    operations = apply_plan.get("operations", []) if isinstance(apply_plan, dict) else []
    if any(item.get("action") == "conflict" for item in operations):
        return _dimension("blocked", E1, "apply plan contains destination conflicts", blockers=["apply_conflict"])
    if operations:
        return _dimension("warning", E1, "apply requires explicit run-id confirmation", warnings=["apply_requires_confirmation"])
    if apply_plan:
        return _dimension("pass", E1, "apply plan has no blocking operations")
    return _dimension("not_provided", E0, "apply plan was not provided", warnings=["apply_plan_missing"])


def _evidence_level(dimensions: dict[str, dict[str, Any]], artifacts: dict[str, Any]) -> dict[str, Any]:
    e0_status = "provided" if dimensions["structural_qa"]["status"] in {"pass", "warning"} else "blocked" if dimensions["structural_qa"]["status"] == "blocked" else "not_provided"
    automated_present = any(artifacts.get(key) for key in ("generation_strategy", "generation_handoff_decision", "artifact_state", "delivery_decision"))
    e1_blocked = any(dimensions[name]["status"] == "blocked" for name in DIMENSION_NAMES if dimensions[name].get("evidence_level") == E1)
    levels = {
        E0: {"status": e0_status, "summary": dimensions["structural_qa"]["summary"]},
        E1: {"status": "blocked" if e1_blocked else "provided" if automated_present else "not_provided", "summary": "automated policy/review artifacts summarized" if automated_present else "no automated policy evidence"},
        E2: {"status": "not_provided", "summary": "explicit bilingual human spot-check evidence was not provided"},
        E3: {"status": "not_provided", "summary": "explicit native-language review evidence was not provided"},
        E4: {"status": "not_provided", "summary": "explicit professional localization review evidence was not provided"},
    }
    human = _human_review_summary(artifacts)
    for level in human.get("global_supported_levels", []):
        levels[level] = {"status": "provided", "summary": "explicit qualified human review evidence provided"}
    for level in human.get("limited_supported_levels", []):
        if levels[level]["status"] != "provided":
            levels[level] = {"status": "provided_limited_scope", "summary": "explicit qualified human review evidence is limited-scope"}
    supported = [level for level in EVIDENCE_LEVELS if levels[level]["status"] == "provided"]
    limited_supported = [level for level in EVIDENCE_LEVELS if levels[level]["status"] == "provided_limited_scope"]
    return {
        "highest_supported": supported[-1] if supported else limited_supported[-1] if limited_supported else "not_provided",
        "highest_global_human_supported": human.get("highest_global_supported", "not_provided"),
        "highest_limited_human_supported": human.get("highest_limited_supported", "not_provided"),
        "levels": levels,
    }


def _overall_claim(
    dimensions: dict[str, dict[str, Any]],
    forbidden_claims: list[str],
    evidence_level: dict[str, Any],
    artifacts: dict[str, Any],
    provider: dict[str, Any],
) -> str:
    if any(dimension["status"] == "blocked" for dimension in dimensions.values()):
        return "blocked"
    if dimensions["structural_qa"]["status"] in {"not_provided", "unknown"}:
        return "not_ready"
    delivery_status = dimensions["delivery_readiness"]["status"]
    apply_status = dimensions["apply_readiness"]["status"]
    provider_status = str(provider.get("provider_status") or "")
    warnings = any(dimension["status"] in {"warning", "unknown", "not_provided"} for dimension in dimensions.values())
    if apply_status == "pass" and "apply_ready" not in forbidden_claims and evidence_level.get("highest_supported") in {E2, E3, E4}:
        return "apply_ready"
    if delivery_status == "pass" and not warnings:
        return "delivery_ready"
    if delivery_status == "pass":
        return "delivery_ready_with_warnings"
    if artifacts.get("delivery_decision") and dimensions["delivery_readiness"]["status"] == "warning":
        return "review_ready"
    if provider_status != "passed":
        return "draft_only"
    return "review_required" if warnings else "review_ready"


def _forbidden_claims(
    dimensions: dict[str, dict[str, Any]],
    artifacts: dict[str, Any],
    provider: dict[str, Any],
    coverage: dict[str, Any],
) -> list[str]:
    claims: set[str] = set()
    if dimensions["coverage_assurance"]["status"] != "pass":
        claims.add("full_coverage")
    if dimensions["provider_status"]["status"] != "pass" or str(provider.get("provider_status") or "") != "passed":
        claims.update({"provider_backed_quality", "provider_execution_complete", "provider_repair_complete", "model_repair_complete"})
    if not bool(provider.get("provider_backed_quality_supported")):
        claims.add("provider_backed_quality")
    reconciliation = artifacts.get("provider_evidence_reconciliation", {})
    if isinstance(reconciliation, dict) and reconciliation:
        claims.update(str(claim) for claim in reconciliation.get("forbidden_claims_remaining", []) if claim)
        if str(reconciliation.get("status") or "") in {"blocked", "stale", "failed"}:
            claims.update({"delivery_ready", "apply_ready", "production_ready"})
    claim_support = artifacts.get("provider_claim_support_report", {})
    if isinstance(claim_support, dict) and claim_support:
        claims.update(str(claim) for claim in claim_support.get("forbidden_claims", []) if claim)
        claims.update(str(claim) for claim in claim_support.get("global_forbidden_claims", []) if claim)
        if str(claim_support.get("status") or "") in {"blocked", "limited"}:
            claims.update({"delivery_ready", "apply_ready", "production_ready"})
    elif reconciliation:
        claims.update(PROVIDER_CLAIMS)
    locale_impact = artifacts.get("locale_readiness_impact", {})
    locale_risk = artifacts.get("locale_risk_report", {})
    locale_capability = artifacts.get("locale_capability_report", {})
    if dimensions["locale_assurance"]["status"] != "pass":
        claims.update(LOCALE_CLAIMS)
    for locale_artifact in (locale_capability, locale_risk, locale_impact):
        if isinstance(locale_artifact, dict) and locale_artifact:
            claims.update(str(claim) for claim in locale_artifact.get("unsupported_claims", []) if claim)
            claims.update(str(claim) for claim in locale_artifact.get("forbidden_claims", []) if claim)
    if isinstance(locale_impact, dict) and locale_impact:
        if str(locale_impact.get("status") or "") in {"blocked", "stale", "review_required"}:
            claims.update({"delivery_ready", "apply_ready", "production_ready"})
    if dimensions["terminology_assurance"]["status"] != "pass":
        claims.add("full_terminology_assurance")
    if dimensions["knowledge_assurance"]["status"] != "pass":
        claims.update({"knowledge_backed_quality", "knowledge_constraints_applied", "knowledge_review_complete"})
    else:
        claims.update({"knowledge_backed_quality", "knowledge_review_complete"})
    enforcement = artifacts.get("knowledge_audit_enforcement_decision", {})
    if isinstance(enforcement, dict) and enforcement:
        claims.update(str(claim) for claim in enforcement.get("forbidden_claims", []) if claim)
        if str(enforcement.get("status") or "") in {"blocked", "stale", "review_required"}:
            claims.update({"delivery_ready", "apply_ready", "production_ready"})
    assurance = artifacts.get("knowledge_assurance_summary", {})
    if isinstance(assurance, dict) and assurance:
        claims.update(str(claim) for claim in assurance.get("forbidden_claims_remaining", []) if claim)
        if "knowledge_constraints_applied" in set(assurance.get("supported_claims", [])):
            claims.discard("knowledge_constraints_applied")
        if str(assurance.get("status") or "") in {"blocked", "stale"}:
            claims.update({"delivery_ready", "apply_ready", "production_ready"})
    knowledge_repair = artifacts.get("knowledge_repair_impact_report", {})
    reconciliation = artifacts.get("knowledge_repair_reconciliation", {})
    if int(knowledge_repair.get("summary", {}).get("repair_item_count", 0) or 0) and reconciliation.get("status") != "clear":
        claims.update(
            {
                "knowledge_constraints_applied",
                "knowledge_review_complete",
                "review_complete",
                "delivery_ready",
                "apply_ready",
                "production_ready",
            }
        )
    closure = artifacts.get("knowledge_repair_closure_decision", {})
    if isinstance(closure, dict) and closure:
        claims.update(str(claim) for claim in closure.get("forbidden_claims_remaining", []) if claim)
        if str(closure.get("status") or "") in {"stale", "still_blocked", "partially_closed", "requires_human_review", "requires_recompute"}:
            claims.update({"knowledge_constraints_applied", "knowledge_review_complete", "review_complete", "delivery_ready", "apply_ready", "production_ready"})
        if str(closure.get("status") or "") != "closed":
            claims.add("knowledge_backed_quality")
    if dimensions["review_readiness"]["status"] != "pass":
        claims.add("review_complete")
    if dimensions["delivery_readiness"]["status"] != "pass":
        claims.add("delivery_ready")
    if dimensions["apply_readiness"]["status"] != "pass":
        claims.add("apply_ready")
    readiness_matrix = artifacts.get("readiness_authorization_matrix", {})
    if isinstance(readiness_matrix, dict) and readiness_matrix:
        claims.update(str(claim) for claim in readiness_matrix.get("forbidden_claims", []) if claim)
        if str(readiness_matrix.get("delivery_readiness_status") or "") in {"blocked", "stale", "partial"}:
            claims.update({"delivery_ready", "production_ready"})
        if str(readiness_matrix.get("apply_readiness_status") or "") in {"blocked", "stale", "partial", "authorization_required"}:
            claims.update({"apply_ready", "production_ready"})
    if any(dimension["status"] == "blocked" for dimension in dimensions.values()) or dimensions["review_readiness"]["status"] != "pass":
        claims.add("production_ready")
    if dimensions["artifact_freshness"]["status"] != "pass":
        claims.update(
            {
                "full_coverage",
                "provider_backed_quality",
                "full_terminology_assurance",
                "review_complete",
                "delivery_ready",
                "apply_ready",
                "production_ready",
            }
        )
    document_blockers = _document_evidence_blockers(artifacts)
    if artifacts.get("document_evidence_manifest"):
        claims.add("layout_verified")
    if document_blockers:
        claims.update({"review_complete", "delivery_ready", "apply_ready", "production_ready", "layout_verified"})
        if any(reason in document_blockers for reason in {"document_evidence_stale", "document_evidence_unsupported"}):
            claims.add("full_coverage")
    handoff = artifacts.get("generation_handoff_decision", {})
    for claim in handoff.get("forbidden_quality_claims", []) if isinstance(handoff, dict) else []:
        claims.update(_claim_aliases(str(claim)))
    claim_acceptance = artifacts.get("claim_acceptance_decision", {})
    if isinstance(claim_acceptance, dict):
        claims.update(str(claim) for claim in claim_acceptance.get("forbidden_claims_remaining", []) if claim)
        claims.update(str(claim) for claim in claim_acceptance.get("rejected_claims", []) if claim)
    signoff = artifacts.get("signoff_record", {})
    if isinstance(signoff, dict) and signoff:
        if str(signoff.get("status") or "") in {"rejected", "stale", "superseded", "requires_follow_up"}:
            claims.update({"delivery_ready", "apply_ready", "production_ready"})
        if signoff.get("delivery_authorized") is False:
            claims.add("delivery_ready")
        if signoff.get("apply_authorized") is False:
            claims.add("apply_ready")
    return sorted(claims)


def _recommended_next_actions(
    dimensions: dict[str, dict[str, Any]],
    forbidden_claims: list[str],
    artifacts: dict[str, Any],
) -> list[str]:
    actions: list[str] = []
    for name, dimension in dimensions.items():
        if dimension["status"] == "blocked":
            actions.append(f"Resolve blockers for {name}: {', '.join(dimension.get('blockers', [])) or 'blocked evidence'}.")
        elif dimension["status"] in {"warning", "unknown", "not_provided"}:
            actions.append(f"Collect or refresh evidence for {name}.")
    artifact_state = artifacts.get("artifact_state", {})
    actions.extend(str(item) for item in artifact_state.get("next_actions", []) if item)
    if "provider_backed_quality" in forbidden_claims:
        actions.append("Record and reconcile provider execution evidence before claiming provider-backed quality.")
    if any(claim in forbidden_claims for claim in LOCALE_CLAIMS):
        actions.append("Collect locale capability evidence before claiming locale-complete, RTL-safe, plural-complete, formatting-complete, or full-product localization.")
    if "review_complete" in forbidden_claims:
        actions.append("Record explicit qualified human review evidence before claiming review completion.")
    if _document_evidence_blockers(artifacts):
        actions.append("Resolve or refresh Document Evidence Pack blockers before document delivery, production, or layout claims.")
    if (
        int(artifacts.get("knowledge_repair_impact_report", {}).get("summary", {}).get("repair_item_count", 0) or 0)
        and artifacts.get("knowledge_repair_reconciliation", {}).get("status") != "clear"
    ):
        actions.append("Complete knowledge repair requests, record matching repair results, and rerun QA and knowledge audit evidence.")
    closure = artifacts.get("knowledge_repair_closure_decision", {})
    if isinstance(closure, dict) and closure.get("status") in {"requires_recompute", "partially_closed", "still_blocked", "requires_human_review", "stale"}:
        actions.append("Run knowledge repair recompute orchestration and renew affected scorecard, claim, signoff, delivery, or apply evidence.")
    readiness_matrix = artifacts.get("readiness_authorization_matrix", {})
    if isinstance(readiness_matrix, dict):
        actions.extend(str(item) for item in readiness_matrix.get("recommended_next_actions", []) if item)
    claim_acceptance = artifacts.get("claim_acceptance_decision", {})
    if isinstance(claim_acceptance, dict) and claim_acceptance.get("status") == "blocked":
        actions.append("Resolve blocked claim acceptance before delivery or apply readiness claims.")
    signoff = artifacts.get("signoff_record", {})
    if isinstance(signoff, dict) and signoff.get("status") == "requires_follow_up":
        actions.append("Refresh signoff after resolving blocked authorizations.")
    return list(dict.fromkeys(actions))[:12]


def _provider_metadata(artifacts: dict[str, Any], generation_metadata: dict[str, Any] | None) -> dict[str, Any]:
    if generation_metadata:
        return generation_metadata
    reconciliation = artifacts.get("provider_evidence_reconciliation", {})
    if isinstance(reconciliation, dict) and reconciliation:
        status = str(reconciliation.get("status") or "")
        qa = artifacts.get("provider_result_qa_report", {})
        claim_support = artifacts.get("provider_claim_support_report", {})
        execution_supported = bool(claim_support.get("provider_execution_complete_supported"))
        return {
            "provider_actual": "accepted_provider_result" if execution_supported else "unverified_or_non_provider",
            "provider_status": "passed" if execution_supported else "failed" if status in {"blocked", "failed"} or qa.get("status") == "blocked" else "not_run",
            "provider_evidence_reconciliation_status": status,
            "provider_execution_complete_supported": execution_supported,
            "provider_backed_quality_supported": bool(claim_support.get("provider_backed_quality_supported")),
        }
    manifest = artifacts.get("delivery_manifest", {})
    if isinstance(manifest.get("generation"), dict):
        return manifest["generation"]
    generated = artifacts.get("generated_segments", [])
    if generated:
        providers = sorted({str(item.get("generation", {}).get("provider") or "") for item in generated if isinstance(item, dict)})
        if providers == ["synthetic"]:
            return {"provider_actual": "synthetic", "provider_status": "synthetic_test"}
        if providers:
            return {"provider_actual": providers[0] if len(providers) == 1 else "mixed", "provider_status": "passed"}
    return {"provider_actual": "none", "provider_status": "not_run"}


def _coverage_from_artifacts(artifacts: dict[str, Any]) -> dict[str, Any]:
    handoff = artifacts.get("generation_handoff_decision", {})
    forbidden = set(handoff.get("forbidden_quality_claims", [])) if isinstance(handoff, dict) else set()
    if "full_source_coverage" in forbidden:
        return {"coverage_mode": "source-only", "visible_ui_coverage_warning": True}
    return {}


def _upstream_readiness_blockers(artifacts: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    qa = artifacts.get("qa", {})
    if str(qa.get("status") or "") in {"fail", "blocked"} or int(qa.get("blocking_count", 0) or 0):
        blockers.append("deterministic_qa_blocking")
    handoff = artifacts.get("generation_handoff_decision", {})
    if isinstance(handoff, dict) and (handoff.get("status") == "blocked" or handoff.get("handoff_allowed") is False):
        blockers.append("handoff_blocked")
    questions = artifacts.get("blocking_questions", {})
    if _unresolved_count(questions):
        blockers.append("unresolved_questions")
    state = artifacts.get("artifact_state", {})
    summary = state.get("summary", {}) if isinstance(state, dict) else {}
    if str(state.get("status") or "") in {"stale", "blocked"} or int(summary.get("stale_count", 0) or 0) or int(summary.get("blocked_count", 0) or 0):
        blockers.append("artifact_state_not_current")
    repair = artifacts.get("repair_result", {})
    repair_summary = repair.get("summary", {}) if isinstance(repair, dict) else {}
    if (
        int(repair_summary.get("pending_required_repair_count", 0) or 0)
        or int(repair_summary.get("pending_provider_or_model_repair_count", 0) or 0)
        or int(repair_summary.get("failed_qa_count", 0) or 0)
        or int(repair_summary.get("blocked_count", 0) or 0)
        or int(repair_summary.get("skipped_not_deterministic_count", 0) or 0)
    ):
        blockers.append("repair_not_ready")
    manifest = artifacts.get("delivery_manifest", {})
    generation = manifest.get("generation", {}) if isinstance(manifest, dict) else {}
    if str(generation.get("provider_status") or "") == "failed":
        blockers.append("provider_failed_or_fallback")
    reconciliation = artifacts.get("provider_evidence_reconciliation", {})
    if isinstance(reconciliation, dict) and str(reconciliation.get("status") or "") in {"blocked", "stale", "failed"}:
        blockers.append("provider_evidence_not_reconciled")
    locale_impact = artifacts.get("locale_readiness_impact", {})
    if isinstance(locale_impact, dict) and str(locale_impact.get("status") or "") in {"blocked", "stale"}:
        blockers.append("locale_capability_blocked")
    claim_acceptance = artifacts.get("claim_acceptance_decision", {})
    if isinstance(claim_acceptance, dict) and claim_acceptance.get("status") == "blocked":
        blockers.append("claim_acceptance_blocked")
    blockers.extend(_document_evidence_blockers(artifacts))
    signoff = artifacts.get("signoff_record", {})
    if isinstance(signoff, dict) and signoff:
        signoff_status = str(signoff.get("status") or "")
        if signoff_status in {"rejected", "stale", "superseded", "requires_follow_up"}:
            blockers.append("signoff_not_current")
        if signoff.get("delivery_authorized") is False and signoff.get("requested_authorizations", {}).get("delivery"):
            blockers.append("delivery_signoff_not_authorized")
        if signoff.get("apply_authorized") is False and signoff.get("requested_authorizations", {}).get("apply"):
            blockers.append("apply_signoff_not_authorized")
    return list(dict.fromkeys(blockers))


def _document_evidence_blockers(artifacts: dict[str, Any]) -> list[str]:
    manifest = artifacts.get("document_evidence_manifest", {})
    if not isinstance(manifest, dict) or not manifest:
        return []
    blockers: list[str] = []
    resolution = artifacts.get("document_claim_resolution", {})
    document_signoff = artifacts.get("document_signoff_summary", {})
    resolution_present = isinstance(resolution, dict) and bool(resolution)
    if resolution_present:
        if str(resolution.get("status") or "") in {"stale", "blocked"}:
            blockers.append(f"document_claim_resolution_{resolution.get('status')}")
        if resolution.get("unresolved_claim_metric_risks"):
            blockers.append("document_claim_metric_blocker")
        if resolution.get("unresolved_publicity_risks"):
            blockers.append("document_publicity_risk_blocker")
        if resolution.get("unresolved_semantic_alignment_risks"):
            blockers.append("document_semantic_alignment_review_required")
        if resolution.get("forbidden_claims_remaining") and str(resolution.get("delivery_readiness_impact") or "") == "blocked":
            blockers.append("document_resolution_forbids_delivery")
    status = str(manifest.get("status") or "not_checked")
    summary = manifest.get("summary", {}) if isinstance(manifest, dict) else {}
    if status == "unsupported":
        blockers.append("document_evidence_unsupported")
    elif status == "blocked" and not resolution_present:
        blockers.append("document_evidence_blocked")
    elif status == "requires_review" and not resolution_present:
        blockers.append("document_evidence_review_required")
    if not resolution_present and int(summary.get("claim_metric_blocking_count", 0) or 0):
        blockers.append("document_claim_metric_blocker")
    if not resolution_present and int(summary.get("blocking_decision_count", 0) or 0):
        blockers.append("document_open_decision_blocker")
    if not resolution_present and int(summary.get("open_decision_count", 0) or 0):
        blockers.append("document_open_decision_required")
    publicity = artifacts.get("publicity_risk_report", {})
    publicity_summary = publicity.get("summary", {}) if isinstance(publicity, dict) else {}
    if not resolution_present and int(publicity_summary.get("blocking_count", 0) or 0):
        blockers.append("document_publicity_risk_blocker")
    claim_report = artifacts.get("claim_metric_report", {})
    claim_summary = claim_report.get("summary", {}) if isinstance(claim_report, dict) else {}
    if not resolution_present and (int(claim_summary.get("pending_count", 0) or 0) or int(claim_summary.get("warning_count", 0) or 0)):
        blockers.append("document_claim_metric_review_required")
    alignment = artifacts.get("semantic_alignment", [])
    if not resolution_present and isinstance(alignment, list) and any(isinstance(item, dict) and item.get("human_confirmation_required") for item in alignment):
        blockers.append("document_semantic_alignment_review_required")
    if _document_evidence_stale(artifacts):
        blockers.append("document_evidence_stale")
    signoff = artifacts.get("signoff_record", {})
    document_signoff_status = str(document_signoff.get("status") or "") if isinstance(document_signoff, dict) else ""
    if document_signoff_status in {"stale", "blocked", "requires_follow_up"}:
        blockers.append(f"document_signoff_{document_signoff_status}")
    if not isinstance(signoff, dict) or not signoff:
        blockers.append("document_signoff_missing")
    return sorted(dict.fromkeys(blockers))


def _document_evidence_has_blocking_condition(blockers: list[str]) -> bool:
    return any(
        blocker
        in {
            "document_evidence_unsupported",
            "document_evidence_blocked",
            "document_claim_metric_blocker",
            "document_publicity_risk_blocker",
            "document_open_decision_blocker",
            "document_evidence_stale",
            "document_claim_resolution_stale",
            "document_claim_resolution_blocked",
            "document_resolution_forbids_delivery",
            "document_signoff_stale",
            "document_signoff_blocked",
        }
        for blocker in blockers
    )


def _document_evidence_stale(artifacts: dict[str, Any]) -> bool:
    state = artifacts.get("artifact_state", {})
    if not isinstance(state, dict):
        return False
    document_artifacts = {
        "document_intake_report",
        "semantic_alignment",
        "claim_metric_report",
        "publicity_risk_report",
        "leadership_review_brief",
        "open_decisions",
            "document_evidence_manifest",
            "document_claim_resolution",
            "document_signoff_summary",
        }
    for item in state.get("artifacts", []):
        if not isinstance(item, dict):
            continue
        if item.get("artifact_id") in document_artifacts and item.get("status") in {"stale", "superseded", "blocked", "requires_human_review"}:
            return True
    return False


def _qa_summary(delivery_manifest: dict[str, Any], qa_result_paths: list[Path] | None) -> dict[str, Any]:
    if isinstance(delivery_manifest.get("qa"), dict):
        return delivery_manifest["qa"]
    paths = qa_result_paths or []
    if not paths:
        return {}
    blocking = 0
    warning = 0
    channels: set[str] = set()
    for path in paths:
        value = _read_optional_json(path)
        blocking += int(value.get("summary", {}).get("blocking_count", value.get("blocking_count", 0)) or 0)
        warning += int(value.get("summary", {}).get("warning_count", value.get("warning_count", 0)) or 0)
        channels.update(str(item) for item in value.get("evidence_channels", []) if item)
    return {
        "status": "fail" if blocking else "pass_with_warnings" if warning else "pass",
        "blocking_count": blocking,
        "warning_count": warning,
        "evidence_channels": sorted(channels),
    }


def _human_review_summary(artifacts: dict[str, Any]) -> dict[str, Any]:
    records = artifacts.get("human_review_evidence", [])
    return summarize_human_review_evidence(records if isinstance(records, list) else [])


def _claim_acceptance_summary(artifacts: dict[str, Any]) -> dict[str, Any]:
    decision = artifacts.get("claim_acceptance_decision", {})
    if not isinstance(decision, dict) or not decision:
        return {"status": "not_provided", "artifact": None, "accepted_claims": [], "rejected_claims": []}
    return {
        "status": decision.get("status", "not_checked"),
        "artifact": CLAIM_ACCEPTANCE_DECISION_JSON,
        "accepted_claims": decision.get("accepted_claims", []),
        "accepted_with_limitations": decision.get("accepted_with_limitations", []),
        "rejected_claims": decision.get("rejected_claims", []),
        "forbidden_claims_remaining": decision.get("forbidden_claims_remaining", []),
    }


def _signoff_summary(artifacts: dict[str, Any]) -> dict[str, Any]:
    record = artifacts.get("signoff_record", {})
    if not isinstance(record, dict) or not record:
        return {"status": "not_provided", "artifact": None, "delivery_authorized": False, "apply_authorized": False}
    return summarize_signoff_record(record)


def _dimension(
    status: str,
    evidence_level: str,
    summary: str,
    *,
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "evidence_level": evidence_level,
        "summary": summary,
        "blockers": blockers or [],
        "warnings": warnings or [],
    }


def _count_warning(count: int, label: str) -> list[str]:
    return [f"{count} {label}"] if count else []


def _unresolved_count(questions: dict[str, Any]) -> int:
    summary = questions.get("summary", {}) if isinstance(questions, dict) else {}
    if "unresolved_blocking_count" in summary:
        return int(summary.get("unresolved_blocking_count", 0) or 0)
    items = questions.get("questions", []) if isinstance(questions, dict) else []
    return sum(str(item.get("status") or "unresolved") != "resolved" for item in items if isinstance(item, dict))


def _claim_aliases(claim: str) -> set[str]:
    aliases: set[str] = set()
    if claim in {"full_source_coverage", "full_visible_ui_coverage"}:
        aliases.add("full_coverage")
        if claim == "full_source_coverage":
            aliases.add(claim)
    if claim in {"review_complete_status"}:
        aliases.add("review_complete")
        aliases.add(claim)
    if claim in {"safe_apply_readiness"}:
        aliases.add("apply_ready")
        aliases.add(claim)
    if claim in {"full_quality_generation"}:
        aliases.add("production_ready")
        aliases.add(claim)
    return aliases


def _run_id(artifacts: dict[str, Any]) -> str | None:
    for value in artifacts.values():
        if isinstance(value, dict) and value.get("run_id"):
            return str(value["run_id"])
    return None


def _source_artifacts(state_dir: Path, run_dir: Path | None, delivery_dir: Path | None) -> dict[str, str]:
    candidates = {
        "localization_brief": state_dir / "localization-brief.json",
        "termbase_preflight_report": state_dir / "termbase-preflight-report.json",
        "generation_strategy": state_dir / "generation-strategy.json",
        "knowledge_usage_report": state_dir / KNOWLEDGE_USAGE_REPORT_JSON,
        "constraint_application_audit": state_dir / CONSTRAINT_APPLICATION_AUDIT_JSON,
        "knowledge_conflict_report": state_dir / KNOWLEDGE_CONFLICT_REPORT_JSON,
        "knowledge_audit_enforcement_decision": state_dir / KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON,
        "knowledge_assurance_summary": state_dir / KNOWLEDGE_ASSURANCE_SUMMARY_JSON,
        "knowledge_repair_plan": state_dir / KNOWLEDGE_REPAIR_PLAN_JSON,
        "knowledge_repair_request": state_dir / KNOWLEDGE_REPAIR_REQUEST_JSON,
        "knowledge_repair_impact_report": state_dir / KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON,
        "knowledge_repair_result_intake": state_dir / KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL,
        "knowledge_repair_qa_report": state_dir / KNOWLEDGE_REPAIR_QA_REPORT_JSON,
        "knowledge_repair_reconciliation": state_dir / KNOWLEDGE_REPAIR_RECONCILIATION_JSON,
        "knowledge_recompute_plan": state_dir / KNOWLEDGE_RECOMPUTE_PLAN_JSON,
        "knowledge_recompute_result": state_dir / KNOWLEDGE_RECOMPUTE_RESULT_JSON,
        "knowledge_repair_closure_decision": state_dir / KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON,
        "knowledge_readiness_impact_report": state_dir / KNOWLEDGE_READINESS_IMPACT_REPORT_JSON,
        "provider_execution_policy": state_dir / PROVIDER_EXECUTION_POLICY_JSON,
        "provider_handoff_request": state_dir / PROVIDER_HANDOFF_REQUEST_JSON,
        "provider_execution_ledger": state_dir / PROVIDER_EXECUTION_LEDGER_JSONL,
        "provider_result_intake": state_dir / PROVIDER_RESULT_INTAKE_JSONL,
        "provider_evidence_reconciliation": state_dir / PROVIDER_EVIDENCE_RECONCILIATION_JSON,
        "provider_result_qa_report": state_dir / PROVIDER_RESULT_QA_REPORT_JSON,
        "provider_result_review_evidence": state_dir / PROVIDER_RESULT_REVIEW_EVIDENCE_JSONL,
        "provider_result_acceptance_decision": state_dir / PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON,
        "provider_claim_support_report": state_dir / PROVIDER_CLAIM_SUPPORT_REPORT_JSON,
        "workbench_provider_review_queue": state_dir / WORKBENCH_PROVIDER_REVIEW_QUEUE_JSON,
        "locale_capability_report": state_dir / LOCALE_CAPABILITY_REPORT_JSON,
        "locale_risk_report": state_dir / LOCALE_RISK_REPORT_JSON,
        "locale_readiness_impact": state_dir / LOCALE_READINESS_IMPACT_JSON,
        "readiness_authorization_matrix": state_dir / "readiness-authorization-matrix.json",
        "manual_followup_gap_report": state_dir / "manual-followup-gap-report.json",
        "apply_readiness_report": state_dir / "apply-readiness-report.json",
        "delivery_readiness_report": state_dir / "delivery-readiness-report.json",
        "blocking_questions": state_dir / "blocking-questions.json",
        "resolution_options": state_dir / "resolution-options.json",
        "user_resolution_decisions": state_dir / "user-resolution-decisions.jsonl",
        "generation_handoff_decision": state_dir / "generation-handoff-decision.json",
        "artifact_state": state_dir / "artifact-state.json",
        "human_review_evidence": state_dir / HUMAN_REVIEW_EVIDENCE_JSONL,
        "claim_acceptance_decision": state_dir / CLAIM_ACCEPTANCE_DECISION_JSON,
        "signoff_record": state_dir / SIGNOFF_RECORD_JSON,
        "stale_segments": state_dir / "stale-segments.jsonl",
        "reuse_decision": state_dir / "reuse-decision.json",
        "segment_regeneration_plan": state_dir / "segment-regeneration-plan.json",
        "repair_request": state_dir / "repair-request.json",
        "repair_result": state_dir / "repair-result.json",
        "repair_history": state_dir / "repair-history.jsonl",
        "document_intake_report": state_dir / DOCUMENT_INTAKE_REPORT_JSON,
        "semantic_alignment": state_dir / SEMANTIC_ALIGNMENT_JSONL,
        "claim_metric_report": state_dir / CLAIM_METRIC_REPORT_JSON,
        "publicity_risk_report": state_dir / PUBLICITY_RISK_REPORT_JSON,
        "document_evidence_manifest": state_dir / DOCUMENT_EVIDENCE_MANIFEST_JSON,
        "open_decisions": state_dir / OPEN_DECISIONS_MD,
        "generated_segments": (run_dir / "generated.jsonl") if run_dir else state_dir / "generated-segments.jsonl",
        "delivery_decision": (run_dir / "delivery-decision.json") if run_dir else state_dir / "delivery-decision.json",
        "apply_plan": (run_dir / "apply-plan.json") if run_dir else state_dir / "apply-plan.json",
        "delivery_manifest": (delivery_dir / "delivery-manifest.json") if delivery_dir else state_dir / "delivery-manifest.json",
    }
    return {key: path.name for key, path in candidates.items() if path and path.is_file()}


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _first_json(paths: list[Path]) -> dict[str, Any]:
    for path in paths:
        if path.is_file():
            return _read_optional_json(path)
    return {}


def _read_optional_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [item for item in read_jsonl(path) if isinstance(item, dict)]


def _read_optional_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")
