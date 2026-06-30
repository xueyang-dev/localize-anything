from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .apply import create_apply_plan
from .artifact_state import artifact_state_from_delivery, artifact_state_summary_from_document
from .io_utils import read_json


def create_delivery_decision_report(delivery_dir: Path, project_root: Path) -> dict[str, Any]:
    delivery_dir = delivery_dir.resolve()
    project_root = project_root.resolve()
    manifest = read_json(delivery_dir / "delivery-manifest.json")
    apply_plan = create_apply_plan(delivery_dir, project_root)
    reference_plan = _load_reference_plan_for_delivery(delivery_dir)
    artifact_state = artifact_state_summary_from_document(artifact_state_from_delivery(delivery_dir))
    segment_staleness = artifact_state.get("segment_staleness", {}) if isinstance(artifact_state, dict) else {}
    segment_summary = segment_staleness.get("summary", {}) if isinstance(segment_staleness, dict) else {}
    segment_repair = artifact_state.get("segment_repair", {}) if isinstance(artifact_state, dict) else {}
    repair_summary = segment_repair.get("summary", {}) if isinstance(segment_repair, dict) else {}
    document_queue = _read_optional_json(delivery_dir / "workbench-document-evidence-queue.json")
    document_queue_summary = document_queue.get("summary", {}) if isinstance(document_queue, dict) else {}
    document_claim_resolution = _read_optional_json(delivery_dir / "document-claim-resolution.json")
    document_claim_summary = document_claim_resolution.get("summary", {}) if isinstance(document_claim_resolution, dict) else {}
    document_signoff_summary = _read_optional_json(delivery_dir / "document-signoff-summary.json")
    knowledge_assurance_summary = _read_optional_json(delivery_dir / "knowledge-assurance-summary.json")
    knowledge_repair_impact = _read_optional_json(delivery_dir / "knowledge-repair-impact-report.json")
    knowledge_repair_qa = _read_optional_json(delivery_dir / "knowledge-repair-qa-report.json")
    knowledge_repair_reconciliation = _read_optional_json(delivery_dir / "knowledge-repair-reconciliation.json")
    knowledge_repair_closure = _read_optional_json(delivery_dir / "knowledge-repair-closure-decision.json")
    knowledge_readiness_impact = _read_optional_json(delivery_dir / "knowledge-readiness-impact-report.json")
    readiness_matrix = _read_optional_json(delivery_dir / "readiness-authorization-matrix.json")
    apply_readiness = _read_optional_json(delivery_dir / "apply-readiness-report.json")
    delivery_readiness = _read_optional_json(delivery_dir / "delivery-readiness-report.json")
    qa = manifest.get("qa", {})
    unprocessed_assets = manifest.get("unprocessed_non_text_assets", [])
    decisions: list[dict[str, Any]] = []

    for item in qa.get("items", []):
        severity = str(item.get("severity") or "warning")
        decisions.append(
            {
                "id": f"qa-{len(decisions) + 1:04d}",
                "type": "qa_finding",
                "severity": severity,
                "status": "blocked" if severity == "blocking" else "requires_review",
                "recommendation": "Resolve this QA finding before applying." if severity == "blocking" else "Review this QA warning before applying.",
                "evidence": item,
            }
        )

    for operation in apply_plan.get("operations", []):
        action = operation.get("action")
        if action == "conflict":
            severity = "blocking"
            status = "blocked"
            recommendation = "Resolve the destination conflict, then create a fresh apply plan."
        elif action in {"create", "replace"}:
            severity = "warning"
            status = "requires_confirmation"
            recommendation = "Apply only after the project owner confirms the run id."
        else:
            severity = "info"
            status = "informational"
            recommendation = "No file write is needed for this destination."
        decisions.append(
            {
                "id": f"apply-{len(decisions) + 1:04d}",
                "type": "apply_operation",
                "severity": severity,
                "status": status,
                "recommendation": recommendation,
                "evidence": operation,
            }
        )

    for asset in unprocessed_assets:
        decisions.append(
            {
                "id": f"asset-{len(decisions) + 1:04d}",
                "type": "unprocessed_asset",
                "severity": "warning",
                "status": "requires_review",
                "recommendation": "Confirm this non-text asset does not need localization work in this run.",
                "evidence": asset,
            }
        )

    localization = _localization_summary(reference_plan)
    for decision in _localization_decisions(reference_plan, len(decisions)):
        decisions.append(decision)
    if apply_plan.get("blocked_by_provider_status"):
        decisions.append(
            {
                "id": f"apply-{len(decisions) + 1:04d}",
                "type": "provider_generation_status",
                "severity": "blocking",
                "status": "blocked",
                "recommendation": "Rerun provider generation successfully before applying delivery files.",
                "evidence": {"reason": apply_plan.get("provider_apply_block_reason")},
            }
        )
    if apply_plan.get("blocked_by_stale_artifacts"):
        decisions.append(
            {
                "id": f"artifact-state-{len(decisions) + 1:04d}",
                "type": "artifact_state",
                "severity": "blocking",
                "status": "blocked",
                "recommendation": "Regenerate or review stale upstream artifacts before delivery or apply.",
                "evidence": {
                    "reason": apply_plan.get("artifact_state_apply_block_reason"),
                    "artifact_state": artifact_state,
                },
            }
        )
    if apply_plan.get("blocked_by_evaluation_scorecard"):
        decisions.append(
            {
                "id": f"evaluation-scorecard-{len(decisions) + 1:04d}",
                "type": "evaluation_scorecard",
                "severity": "blocking",
                "status": "blocked",
                "recommendation": "Resolve scorecard blockers before claiming apply readiness.",
                "evidence": {"reason": apply_plan.get("evaluation_scorecard_apply_block_reason")},
            }
        )
    if apply_plan.get("blocked_by_signoff"):
        decisions.append(
            {
                "id": f"signoff-{len(decisions) + 1:04d}",
                "type": "signoff",
                "severity": "blocking",
                "status": "blocked",
                "recommendation": "Refresh signoff after scorecard and claim acceptance are ready.",
                "evidence": {"reason": apply_plan.get("signoff_apply_block_reason")},
            }
        )
    if document_queue_summary.get("item_count"):
        decisions.append(
            {
                "id": f"document-evidence-{len(decisions) + 1:04d}",
                "type": "document_evidence_queue",
                "severity": "blocking" if int(document_queue_summary.get("blocking_count", 0) or 0) else "warning",
                "status": "blocked" if int(document_queue_summary.get("blocking_count", 0) or 0) else "requires_review",
                "recommendation": "Resolve Document Evidence Queue items before claiming review, delivery, production, or apply readiness.",
                "evidence": {"summary": document_queue_summary},
            }
        )
    if document_claim_resolution and document_claim_resolution.get("status") in {"blocked", "requires_follow_up", "stale"}:
        decisions.append(
            {
                "id": f"document-decision-{len(decisions) + 1:04d}",
                "type": "document_claim_resolution",
                "severity": "blocking" if document_claim_resolution.get("status") in {"blocked", "stale"} else "warning",
                "status": "blocked" if document_claim_resolution.get("status") in {"blocked", "stale"} else "requires_review",
                "recommendation": "Resolve document claim/publicity/alignment decisions before strong delivery claims.",
                "evidence": {"status": document_claim_resolution.get("status"), "summary": document_claim_summary},
            }
        )
    if document_signoff_summary and document_signoff_summary.get("status") in {"blocked", "requires_follow_up", "stale"}:
        decisions.append(
            {
                "id": f"document-signoff-{len(decisions) + 1:04d}",
                "type": "document_signoff_summary",
                "severity": "blocking" if document_signoff_summary.get("status") in {"blocked", "stale"} else "warning",
                "status": "blocked" if document_signoff_summary.get("status") in {"blocked", "stale"} else "requires_review",
                "recommendation": "Record or refresh document leadership review/signoff before delivery/apply authorization.",
                "evidence": {"status": document_signoff_summary.get("status"), "summary": document_signoff_summary.get("summary", {})},
            }
        )
    if knowledge_assurance_summary and knowledge_assurance_summary.get("status") in {"blocked", "review_required", "stale"}:
        decisions.append(
            {
                "id": f"knowledge-assurance-{len(decisions) + 1:04d}",
                "type": "knowledge_assurance_summary",
                "severity": "blocking" if knowledge_assurance_summary.get("status") in {"blocked", "stale"} else "warning",
                "status": "blocked" if knowledge_assurance_summary.get("status") in {"blocked", "stale"} else "requires_review",
                "recommendation": "Resolve or scope knowledge audit blockers before delivery/apply authorization.",
                "evidence": {
                    "status": knowledge_assurance_summary.get("status"),
                    "forbidden_claims_remaining": knowledge_assurance_summary.get("forbidden_claims_remaining", []),
                    "readiness_impact": knowledge_assurance_summary.get("readiness_impact", {}),
                },
            }
        )
    if (
        int(knowledge_repair_impact.get("summary", {}).get("repair_item_count", 0) or 0)
        and knowledge_repair_reconciliation.get("status") != "clear"
    ):
        decisions.append(
            {
                "id": f"knowledge-repair-{len(decisions) + 1:04d}",
                "type": "knowledge_repair_impact",
                "severity": "blocking",
                "status": "blocked",
                "recommendation": "Complete knowledge repairs and matching QA-backed repair results before delivery/apply authorization.",
                "evidence": {
                    "status": knowledge_repair_impact.get("status"),
                    "summary": knowledge_repair_impact.get("summary", {}),
                    "affected_claims": knowledge_repair_impact.get("affected_claims", []),
                },
            }
        )
    if str(knowledge_repair_qa.get("status") or "") in {"blocked", "requires_human_review", "stale"} or str(
        knowledge_repair_reconciliation.get("status") or ""
    ) in {"blocked", "partial", "stale"}:
        decisions.append(
            {
                "id": f"knowledge-repair-reconciliation-{len(decisions) + 1:04d}",
                "type": "knowledge_repair_reconciliation",
                "severity": "blocking",
                "status": "blocked",
                "recommendation": "Resolve failed, stale, or incomplete knowledge repair QA before delivery/apply authorization.",
                "evidence": {
                    "qa_status": knowledge_repair_qa.get("status", "not_checked"),
                    "reconciliation_status": knowledge_repair_reconciliation.get("status", "not_checked"),
                    "remaining_blockers": knowledge_repair_reconciliation.get("summary", {}).get("remaining_blocker_count", 0),
                },
            }
        )
    if str(knowledge_repair_closure.get("status") or "") in {
        "requires_recompute",
        "requires_human_review",
        "partially_closed",
        "still_blocked",
        "stale",
    }:
        decisions.append(
            {
                "id": f"knowledge-repair-closure-{len(decisions) + 1:04d}",
                "type": "knowledge_repair_closure",
                "severity": "blocking",
                "status": "blocked",
                "recommendation": "Complete deterministic repair recomputation and renew affected authorization evidence before delivery/apply.",
                "evidence": {
                    "closure_status": knowledge_repair_closure.get("status", "not_checked"),
                    "required_recomputation": knowledge_repair_closure.get("required_recomputation", []),
                    "forbidden_claims_remaining": knowledge_repair_closure.get("forbidden_claims_remaining", []),
                    "readiness_impact_status": knowledge_readiness_impact.get("status", "not_checked"),
                },
            }
        )
    if str(readiness_matrix.get("delivery_readiness_status") or "") in {"blocked", "stale", "partial"} or str(
        readiness_matrix.get("apply_readiness_status") or ""
    ) in {"blocked", "stale", "partial"}:
        decisions.append(
            {
                "id": f"readiness-authorization-{len(decisions) + 1:04d}",
                "type": "readiness_authorization_matrix",
                "severity": "blocking",
                "status": "blocked",
                "recommendation": "Resolve readiness authorization blockers before delivery/apply claims or source apply.",
                "evidence": {
                    "delivery_readiness_status": readiness_matrix.get("delivery_readiness_status", "not_checked"),
                    "apply_readiness_status": readiness_matrix.get("apply_readiness_status", "not_checked"),
                    "forbidden_claims": readiness_matrix.get("forbidden_claims", []),
                    "blocker_count": readiness_matrix.get("summary", {}).get("blocker_count", 0),
                },
            }
        )
    if str(apply_readiness.get("apply_status") or "") in {"blocked", "stale", "partial"}:
        decisions.append(
            {
                "id": f"apply-readiness-{len(decisions) + 1:04d}",
                "type": "apply_readiness_report",
                "severity": "blocking",
                "status": "blocked",
                "recommendation": "Do not apply staged files until apply readiness is current and explicitly authorized.",
                "evidence": {"apply_status": apply_readiness.get("apply_status", "not_checked")},
            }
        )
    if str(delivery_readiness.get("delivery_status") or "") in {"blocked", "stale", "partial"}:
        decisions.append(
            {
                "id": f"delivery-readiness-{len(decisions) + 1:04d}",
                "type": "delivery_readiness_report",
                "severity": "blocking",
                "status": "blocked",
                "recommendation": "Refresh delivery readiness before handing off a delivery package as ready.",
                "evidence": {"delivery_status": delivery_readiness.get("delivery_status", "not_checked")},
            }
        )

    status = _status(decisions)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "run_id": manifest.get("run_id"),
        "status": status,
        "delivery_directory": delivery_dir.as_posix(),
        "project_root": project_root.as_posix(),
        "safety": {
            "staged_copy_required": True,
            "apply_requires_run_id_confirmation": True,
            "automatic_source_edits": False,
            "backup_required_for_replacements": True,
        },
        "summary": {
            "decision_count": len(decisions),
            "blocking_count": sum(item["status"] == "blocked" for item in decisions),
            "requires_confirmation_count": sum(item["status"] == "requires_confirmation" for item in decisions),
            "requires_review_count": sum(item["status"] == "requires_review" for item in decisions),
            "output_count": len(manifest.get("outputs", [])),
            "qa_status": qa.get("status", "not_checked"),
            "qa_blocking_count": qa.get("blocking_count", 0),
            "qa_warning_count": qa.get("warning_count", 0),
            "unprocessed_asset_count": len(unprocessed_assets),
            "apply_summary": apply_plan.get("summary", {}),
            "localization": localization,
            "artifact_state": artifact_state.get("summary", {}),
            "stale_artifact_count": len(artifact_state.get("stale_artifacts", [])),
            "stale_segment_count": segment_summary.get("stale_segment_count", 0),
            "segments_requiring_regeneration_count": segment_summary.get("needs_regeneration_count", 0),
            "segments_requiring_review_count": segment_summary.get("needs_re_review_count", 0),
            "pending_segment_repair_count": repair_summary.get("pending_repair_count", 0),
            "targeted_repair_count": repair_summary.get("targeted_repair_count", 0),
            "human_confirm_count": repair_summary.get("human_confirm_count", 0),
            "segment_repair_applied_count": repair_summary.get("applied_count", 0),
            "segment_repair_pending_provider_count": repair_summary.get("pending_provider_count", 0),
            "segment_repair_pending_human_count": repair_summary.get("pending_human_count", 0),
            "segment_repair_failed_qa_count": repair_summary.get("failed_qa_count", 0),
            "segment_repair_skipped_not_deterministic_count": repair_summary.get("skipped_not_deterministic_count", 0),
            "blocked_by_evaluation_scorecard": bool(apply_plan.get("blocked_by_evaluation_scorecard")),
            "blocked_by_signoff": bool(apply_plan.get("blocked_by_signoff")),
            "document_evidence_queue": document_queue_summary,
            "document_evidence_queue_item_count": document_queue_summary.get("item_count", 0),
            "document_evidence_queue_blocking_count": document_queue_summary.get("blocking_count", 0),
            "document_claim_resolution": document_claim_summary,
            "document_claim_resolution_status": document_claim_resolution.get("status", "not_checked"),
            "document_signoff_summary": document_signoff_summary.get("summary", {}),
            "document_signoff_status": document_signoff_summary.get("status", "not_checked"),
            "knowledge_assurance_status": knowledge_assurance_summary.get("status", "not_checked"),
            "knowledge_repair_impact_status": knowledge_repair_impact.get("status", "not_checked"),
            "pending_knowledge_repair_count": knowledge_repair_impact.get("summary", {}).get("repair_item_count", 0),
            "knowledge_repair_qa_status": knowledge_repair_qa.get("status", "not_checked"),
            "knowledge_repair_reconciliation_status": knowledge_repair_reconciliation.get("status", "not_checked"),
            "knowledge_repair_closure_status": knowledge_repair_closure.get("status", "not_checked"),
            "knowledge_readiness_impact_status": knowledge_readiness_impact.get("status", "not_checked"),
            "readiness_authorization_delivery_status": readiness_matrix.get("delivery_readiness_status", "not_checked"),
            "readiness_authorization_apply_status": readiness_matrix.get("apply_readiness_status", "not_checked"),
            "apply_readiness_report_status": apply_readiness.get("apply_status", "not_checked"),
            "delivery_readiness_report_status": delivery_readiness.get("delivery_status", "not_checked"),
        },
        "localization": localization,
        "artifact_state": artifact_state,
        "apply_plan": apply_plan,
        "decisions": decisions,
        "next_actions": _next_actions(status, apply_plan, decisions),
    }


def render_delivery_decision_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    safety = report.get("safety", {})
    artifact_state = report.get("artifact_state", {})
    artifact_state_summary = artifact_state.get("summary", {}) if isinstance(artifact_state, dict) else {}
    lines = [
        "# Delivery Decision Report",
        "",
        f"- Run ID: `{report.get('run_id')}`",
        f"- Status: `{report.get('status')}`",
        f"- Project root: `{report.get('project_root')}`",
        f"- Delivery directory: `{report.get('delivery_directory')}`",
        f"- Decisions: {summary.get('decision_count', 0)}",
        f"- Blocking: {summary.get('blocking_count', 0)}",
        f"- Requires confirmation: {summary.get('requires_confirmation_count', 0)}",
        f"- Requires review: {summary.get('requires_review_count', 0)}",
        f"- Stale artifacts: {artifact_state_summary.get('stale_count', 0)}",
        f"- Stale segments: {summary.get('stale_segment_count', 0)}",
        f"- Pending segment repairs: {summary.get('pending_segment_repair_count', 0)}",
        f"- Applied segment repairs: {summary.get('segment_repair_applied_count', 0)}",
        f"- Failed segment repair QA: {summary.get('segment_repair_failed_qa_count', 0)}",
        "",
        "## Localization Mode",
        "",
    ]
    localization = report.get("localization", {})
    if localization:
        lines.extend(
            [
                f"- Operating mode: `{localization.get('operating_mode')}`",
                f"- Reference policy: `{localization.get('reference_policy')}`",
                f"- Generated candidates: {localization.get('generated_count', 0)}",
                f"- Preserved: {localization.get('preserved_count', 0)}",
                f"- Stale: {localization.get('stale_count', 0)}",
                f"- Missing: {localization.get('missing_count', 0)}",
                f"- Obsolete: {localization.get('obsolete_count', 0)}",
                f"- Review-required segments: {localization.get('review_required_count', 0)}",
                "",
            ]
        )
    else:
        lines.extend(["No reference-plan artifact was found for this delivery.", ""])
    lines.extend(
        [
            "## Safety",
            "",
            f"- Staged copy required: `{bool(safety.get('staged_copy_required'))}`",
            f"- Run-id confirmation required: `{bool(safety.get('apply_requires_run_id_confirmation'))}`",
            f"- Automatic source edits: `{bool(safety.get('automatic_source_edits'))}`",
            f"- Backups required for replacements: `{bool(safety.get('backup_required_for_replacements'))}`",
            "",
            "## Decisions",
            "",
        ]
    )
    decisions = report.get("decisions", [])
    if not decisions:
        lines.append("No delivery decisions are required.")
    for decision in decisions:
        evidence = decision.get("evidence", {})
        target = evidence.get("destination") or evidence.get("path") or evidence.get("segment_id") or decision.get("id")
        lines.extend(
            [
                f"### `{target}`",
                "",
                f"- Type: `{decision.get('type')}`",
                f"- Status: `{decision.get('status')}`",
                f"- Severity: `{decision.get('severity')}`",
                f"- Recommendation: {decision.get('recommendation')}",
                "",
            ]
        )
    lines.extend(["", "## Next Actions", ""])
    for action in report.get("next_actions", []):
        lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


def _status(decisions: list[dict[str, Any]]) -> str:
    if any(item["status"] == "blocked" for item in decisions):
        return "blocked"
    if any(item["status"] in {"requires_confirmation", "requires_review"} for item in decisions):
        return "owner_review_required"
    return "ready_no_changes"


def _next_actions(status: str, apply_plan: dict[str, Any], decisions: list[dict[str, Any]]) -> list[str]:
    if status == "blocked":
        if apply_plan.get("blocked_by_stale_artifacts"):
            return ["Regenerate stale upstream artifacts, then rebuild the delivery package and delivery decision report."]
        return ["Resolve blocked QA findings or apply conflicts, then regenerate the delivery decision report."]
    actions = ["Review this decision report before applying any staged files."]
    if apply_plan.get("requires_confirmation"):
        actions.append(f"Apply only with `apply-delivery --confirm-run-id {apply_plan.get('run_id')}` after owner approval.")
    if any(item["type"] == "unprocessed_asset" for item in decisions):
        actions.append("Review unprocessed assets so the run is not mistaken for full product localization.")
    return actions


def _load_reference_plan_for_delivery(delivery_dir: Path) -> dict[str, Any] | None:
    candidates = [
        delivery_dir.parent.parent / "reference-plan.json",
        delivery_dir.parent / "reference-plan.json",
    ]
    for path in candidates:
        if path.is_file():
            return read_json(path)
    return None


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _localization_summary(reference_plan: dict[str, Any] | None) -> dict[str, Any]:
    if not reference_plan:
        return {}
    summary = reference_plan.get("summary", {})
    generated_count = int(summary.get("candidate_segment_count", 0))
    stale_count = int(summary.get("stale_reviewed_translation_count", 0))
    missing_count = int(summary.get("missing_target_translation_count", 0))
    obsolete_count = int(summary.get("obsolete_reference_count", 0))
    unreviewed_count = int(summary.get("existing_target_unreviewed_or_conflicting_count", 0))
    return {
        "operating_mode": reference_plan.get("operating_mode"),
        "reference_policy": reference_plan.get("reference_policy"),
        "generated_count": generated_count,
        "preserved_count": int(summary.get("preserved_segment_count", 0)),
        "stale_count": stale_count,
        "missing_count": missing_count,
        "obsolete_count": obsolete_count,
        "review_required_count": stale_count + missing_count + obsolete_count + unreviewed_count,
        "existing_reference_file_count": int(summary.get("existing_reference_file_count", 0)),
        "missing_reference_file_count": int(summary.get("missing_reference_file_count", 0)),
        "explicit_rewrite_count": (
            generated_count if reference_plan.get("operating_mode") == "rewrite_or_harmonization" else 0
        ),
    }


def _localization_decisions(reference_plan: dict[str, Any] | None, offset: int) -> list[dict[str, Any]]:
    if not reference_plan:
        return []
    localization = _localization_summary(reference_plan)
    items: list[dict[str, Any]] = []
    decision_specs = [
        ("preserved_translation", "info", "informational", "Reviewed unchanged translations are preserved outside generation.", "preserved_count"),
        ("generated_candidate", "warning", "requires_review", "Generated candidates require human review before apply.", "generated_count"),
        ("stale_translation", "warning", "requires_review", "Stale reviewed translations need owner or translator review.", "stale_count"),
        ("obsolete_target_reference", "warning", "requires_review", "Obsolete target-only translations are flagged and not automatically deleted.", "obsolete_count"),
    ]
    obsolete_references = reference_plan.get("obsolete_references", []) if reference_plan else []
    for item_type, severity, status, recommendation, count_key in decision_specs:
        count = int(localization.get(count_key, 0))
        if count <= 0:
            continue
        evidence: dict[str, Any] = {
            "count": count,
            "operating_mode": localization.get("operating_mode"),
            "reference_policy": localization.get("reference_policy"),
        }
        if item_type == "obsolete_target_reference":
            evidence["obsolete_references"] = obsolete_references
        items.append(
            {
                "id": f"loc-{offset + len(items) + 1:04d}",
                "type": item_type,
                "severity": severity,
                "status": status,
                "recommendation": recommendation,
                "evidence": evidence,
            }
        )
    return items
