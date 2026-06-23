from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .apply import create_apply_plan
from .io_utils import read_json


def create_delivery_decision_report(delivery_dir: Path, project_root: Path) -> dict[str, Any]:
    delivery_dir = delivery_dir.resolve()
    project_root = project_root.resolve()
    manifest = read_json(delivery_dir / "delivery-manifest.json")
    apply_plan = create_apply_plan(delivery_dir, project_root)
    reference_plan = _load_reference_plan_for_delivery(delivery_dir)
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
        },
        "localization": localization,
        "apply_plan": apply_plan,
        "decisions": decisions,
        "next_actions": _next_actions(status, apply_plan, decisions),
    }


def render_delivery_decision_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    safety = report.get("safety", {})
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
