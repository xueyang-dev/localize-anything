from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json


def build_delivery_dashboard(delivery_dir: Path) -> dict[str, Any]:
    manifest = read_json(delivery_dir / "delivery-manifest.json")
    outputs = [
        {
            "destination": output.get("destination"),
            "package_path": output.get("package_path"),
            "size_bytes": output.get("size_bytes"),
            "sha256": output.get("sha256"),
            "apply_action_hint": "replace" if output.get("destination_base_sha256") else "create",
        }
        for output in manifest.get("outputs", [])
    ]
    qa = manifest.get("qa", {})
    unprocessed_assets = manifest.get("unprocessed_non_text_assets", [])
    generation = manifest.get("generation", {})
    next_actions = _next_actions(manifest, qa, outputs, unprocessed_assets)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": manifest.get("run_id"),
        "delivery_status": manifest.get("delivery_status"),
        "project": manifest.get("project", {}),
        "outputs": outputs,
        "summary": {
            "output_count": len(outputs),
            "qa_status": qa.get("status", "not_checked"),
            "blocking_count": qa.get("blocking_count", 0),
            "warning_count": qa.get("warning_count", 0),
            "unprocessed_asset_count": len(unprocessed_assets),
        },
        "qa": qa,
        "generation": generation,
        "unprocessed_non_text_assets": unprocessed_assets,
        "next_actions": next_actions,
    }


def render_dashboard_markdown(dashboard: dict[str, Any]) -> str:
    project = dashboard.get("project", {})
    summary = dashboard.get("summary", {})
    lines = [
        "# Localization Delivery Dashboard",
        "",
        f"- Run ID: `{dashboard.get('run_id')}`",
        f"- Delivery status: `{dashboard.get('delivery_status')}`",
        f"- Source locale: `{project.get('source_locale', 'unknown')}`",
        f"- Target locales: `{', '.join(project.get('target_locales', [])) or 'unknown'}`",
        f"- QA status: `{summary.get('qa_status')}`",
        f"- Blocking findings: {summary.get('blocking_count', 0)}",
        f"- Warnings: {summary.get('warning_count', 0)}",
        "",
        "## Generated Files",
        "",
    ]
    outputs = dashboard.get("outputs", [])
    if outputs:
        for output in outputs:
            lines.append(
                f"- `{output.get('destination')}` from `{output.get('package_path')}` "
                f"({output.get('size_bytes', 0)} bytes, apply hint: `{output.get('apply_action_hint')}`)"
            )
    else:
        lines.append("No generated files are recorded in this delivery.")
    lines.extend(["", "## Unprocessed Assets", ""])
    assets = dashboard.get("unprocessed_non_text_assets", [])
    if assets:
        for asset in assets:
            lines.append(f"- `{asset.get('path')}`: {asset.get('asset_type', 'non-text')}")
    else:
        lines.append("No unprocessed non-text assets were recorded.")
    lines.extend(["", "## Next Actions", ""])
    for action in dashboard.get("next_actions", []):
        lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


def _next_actions(
    manifest: dict[str, Any],
    qa: dict[str, Any],
    outputs: list[dict[str, Any]],
    unprocessed_assets: list[dict[str, Any]],
) -> list[str]:
    actions: list[str] = []
    if qa.get("blocking_count", 0):
        actions.append("Resolve blocking QA findings before applying the delivery.")
    elif qa.get("status") == "not_checked":
        actions.append("Run deterministic and agent QA before marking the package review-ready.")
    else:
        actions.append("Review generated target text and QA warnings before applying to the source project.")
    generation = manifest.get("generation", {})
    if outputs and generation.get("apply_allowed") is False:
        actions.append("Do not apply this delivery; provider generation failed or produced fallback-only output.")
    elif outputs:
        actions.append("Run `plan-apply` to inspect create/replace/conflict operations.")
        actions.append("Use `apply-delivery --confirm-run-id <run_id>` only after the project owner approves the plan.")
    if unprocessed_assets:
        actions.append("Review unprocessed non-text assets so text localization is not mistaken for full product localization.")
    if manifest.get("delivery_status") == "draft_package":
        actions.append("Import reviewer edits or add agent/human QA evidence before promoting this package.")
    return actions
