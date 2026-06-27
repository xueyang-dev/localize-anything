from __future__ import annotations

import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from . import PROTOCOL_VERSION
from .artifact_state import artifact_state_from_delivery, artifact_state_summary_from_document
from .io_utils import read_json, sha256_file


def create_apply_plan(delivery_dir: Path, project_root: Path) -> dict[str, Any]:
    delivery_dir = delivery_dir.resolve()
    project_root = project_root.resolve()
    manifest = read_json(delivery_dir / "delivery-manifest.json")
    generation_block_reason = _provider_apply_block_reason(manifest.get("generation", {}))
    artifact_state = artifact_state_summary_from_document(artifact_state_from_delivery(delivery_dir))
    stale_block_reason = _artifact_state_apply_block_reason(artifact_state)
    operations: list[dict[str, Any]] = []
    for output in manifest.get("outputs", []):
        package_path = _safe_relative(str(output.get("package_path", "")), "package_path")
        destination_path = _safe_relative(str(output.get("destination", "")), "destination")
        source = delivery_dir / package_path
        destination = project_root / destination_path
        if not source.is_file():
            raise ValueError(f"Package output is missing: {source}")
        source_hash = sha256_file(source)
        if source_hash != output.get("sha256"):
            raise ValueError(f"Package output hash mismatch: {source}")
        current_hash = sha256_file(destination) if destination.is_file() else None
        base_hash = output.get("destination_base_sha256")
        if current_hash is None:
            action = "create"
        elif current_hash == source_hash:
            action = "unchanged"
        elif base_hash is not None and current_hash == base_hash:
            action = "replace"
        else:
            action = "conflict"
        operations.append(
            {
                "action": action,
                "source": package_path.as_posix(),
                "destination": destination_path.as_posix(),
                "source_sha256": source_hash,
                "destination_sha256": current_hash,
                "destination_base_sha256": base_hash,
                "backup_required": action in {"replace", "conflict"},
                "source_category": output.get("source_category"),
                "apply_safety": output.get("apply_safety", {}),
            }
        )
    summary = {action: sum(item["action"] == action for item in operations) for action in ("create", "replace", "unchanged", "conflict")}
    return {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": manifest["run_id"],
        "mode": "dry_run",
        "project_root": project_root.as_posix(),
        "operations": operations,
        "summary": summary,
        "requires_confirmation": any(item["action"] in {"create", "replace"} for item in operations),
        "blocked_by_conflicts": summary["conflict"] > 0,
        "blocked_by_provider_status": bool(generation_block_reason),
        "provider_apply_block_reason": generation_block_reason,
        "blocked_by_stale_artifacts": bool(stale_block_reason),
        "artifact_state_apply_block_reason": stale_block_reason,
        "artifact_state": artifact_state,
        "rollback": {"backup_required_for": [item["destination"] for item in operations if item["backup_required"]]},
    }


def render_apply_plan_markdown(plan: dict[str, Any]) -> str:
    summary = plan.get("summary", {})
    lines = [
        "# Apply Plan",
        "",
        f"- Run ID: `{plan.get('run_id')}`",
        f"- Mode: `{plan.get('mode')}`",
        f"- Project root: `{plan.get('project_root')}`",
        f"- Creates: {summary.get('create', 0)}",
        f"- Replaces: {summary.get('replace', 0)}",
        f"- Unchanged: {summary.get('unchanged', 0)}",
        f"- Conflicts: {summary.get('conflict', 0)}",
        f"- Requires confirmation: `{bool(plan.get('requires_confirmation'))}`",
        f"- Blocked by conflicts: `{bool(plan.get('blocked_by_conflicts'))}`",
        f"- Blocked by provider status: `{bool(plan.get('blocked_by_provider_status'))}`",
        f"- Blocked by stale artifacts: `{bool(plan.get('blocked_by_stale_artifacts'))}`",
        "",
        "## Operations",
        "",
    ]
    if plan.get("blocked_by_provider_status"):
        lines.extend(
            [
                "## Provider Status Block",
                "",
                str(plan.get("provider_apply_block_reason")),
                "",
            ]
        )
    if plan.get("blocked_by_stale_artifacts"):
        lines.extend(
            [
                "## Artifact State Block",
                "",
                str(plan.get("artifact_state_apply_block_reason")),
                "",
            ]
        )
    operations = plan.get("operations", [])
    if not operations:
        lines.append("No file operations are planned.")
    for operation in operations:
        action = str(operation.get("action", "unknown"))
        destination = str(operation.get("destination", ""))
        lines.extend(
            [
                f"### `{destination}`",
                "",
                f"- Action: `{action}`",
                f"- Package source: `{operation.get('source')}`",
                f"- Source sha256: `{operation.get('source_sha256')}`",
                f"- Current destination sha256: `{operation.get('destination_sha256') or 'none'}`",
                f"- Destination base sha256: `{operation.get('destination_base_sha256') or 'none'}`",
                f"- Backup required: `{bool(operation.get('backup_required'))}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Confirmation",
            "",
            "This is a dry run. It does not write to the project.",
            f"Apply only after review with `apply-delivery --confirm-run-id {plan.get('run_id')}`.",
            "",
        ]
    )
    return "\n".join(lines)


def execute_apply(
    delivery_dir: Path,
    project_root: Path,
    confirm_run_id: str,
    backup_root: Path | None = None,
) -> dict[str, Any]:
    plan = create_apply_plan(delivery_dir, project_root)
    if confirm_run_id != plan["run_id"]:
        raise ValueError("confirm_run_id must match the delivery run_id")
    if plan.get("blocked_by_provider_status"):
        raise ValueError(f"Apply is blocked by provider generation status: {plan.get('provider_apply_block_reason')}")
    if plan.get("blocked_by_stale_artifacts"):
        raise ValueError(f"Apply is blocked by stale artifact evidence: {plan.get('artifact_state_apply_block_reason')}")
    if plan["blocked_by_conflicts"]:
        raise ValueError("Apply is blocked by destination conflicts; create a fresh plan after resolving them")
    dirty = _git_status_short(project_root)
    if dirty:
        raise ValueError("Apply requires a clean git tree before writing files")

    delivery_dir = delivery_dir.resolve()
    project_root = project_root.resolve()
    backup_root = (backup_root or project_root / ".localize-anything" / "backups" / plan["run_id"]).resolve()
    executed: list[dict[str, Any]] = []
    for operation in plan["operations"]:
        action = operation["action"]
        destination_path = _safe_relative(operation["destination"], "destination")
        source_path = _safe_relative(operation["source"], "source")
        source = delivery_dir / source_path
        destination = project_root / destination_path
        result = dict(operation)
        if action == "unchanged":
            result["applied"] = False
            executed.append(result)
            continue
        if action not in {"create", "replace"}:
            raise ValueError(f"Unsupported apply action: {action}")
        _validate_apply_destination(operation)
        if action == "replace" and destination.exists():
            backup = backup_root / destination_path
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, backup)
            result["backup_path"] = backup.relative_to(project_root).as_posix() if _is_relative_to(backup, project_root) else backup.as_posix()
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        result["applied"] = True
        result["destination_sha256_after"] = sha256_file(destination)
        executed.append(result)

    summary = {
        "created": sum(item.get("action") == "create" and item.get("applied") for item in executed),
        "replaced": sum(item.get("action") == "replace" and item.get("applied") for item in executed),
        "unchanged": sum(item.get("action") == "unchanged" for item in executed),
    }
    return {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": plan["run_id"],
        "mode": "executed",
        "project_root": project_root.as_posix(),
        "operations": executed,
        "summary": summary,
        "backup_root": backup_root.as_posix(),
        "post_apply_git_diff": _git_diff_stat(project_root),
    }


def _safe_relative(value: str, label: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe {label}: {value!r}")
    return path


def _provider_apply_block_reason(generation: dict[str, Any]) -> str | None:
    if not isinstance(generation, dict):
        return None
    if generation.get("apply_allowed") is False:
        return "delivery generation metadata does not allow apply"
    if generation.get("provider_status") == "failed":
        return "provider generation failed"
    if generation.get("provider_actual") == "synthetic_fallback":
        return "synthetic fallback output is not provider-backed translation"
    if generation.get("quality_claim") == "none" and generation.get("provider_requested") not in {None, "", "none", "synthetic"}:
        return "provider-backed translation did not complete"
    return None


def _artifact_state_apply_block_reason(artifact_state: dict[str, Any]) -> str | None:
    decisions = artifact_state.get("decisions", {})
    if decisions.get("apply_policy") != "blocked" and decisions.get("delivery_apply_allowed") is not False:
        return None
    affected = artifact_state.get("stale_artifacts", []) or artifact_state.get("blocked_artifacts", [])
    names = ", ".join(str(item.get("artifact_id")) for item in affected[:5] if item.get("artifact_id"))
    return f"artifact state blocks apply because upstream evidence is stale or blocked: {names or 'unknown'}"


def _validate_apply_destination(operation: dict[str, Any]) -> None:
    if operation.get("source_category") != "merged_dependency_overlay":
        return
    destination = PurePosixPath(str(operation.get("destination", "")))
    parts = destination.parts
    if destination.suffix != ".xml" or len(parts) < 4:
        raise ValueError(f"Unsafe Android overlay destination: {destination.as_posix()}")
    if parts[-3] != "res" or not parts[-2].startswith("values-"):
        raise ValueError(f"Android overlay apply must target a locale values directory: {destination.as_posix()}")


def _git_status_short(project_root: Path) -> list[str]:
    if not (project_root / ".git").exists():
        return []
    result = subprocess.run(
        ["git", "-C", str(project_root), "status", "--short", "--untracked-files=all"],
        check=True,
        text=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _git_diff_stat(project_root: Path) -> str:
    if not (project_root / ".git").exists():
        return ""
    status = _git_status_short(project_root)
    result = subprocess.run(
        ["git", "-C", str(project_root), "diff", "--stat"],
        check=True,
        text=True,
        capture_output=True,
    )
    parts = []
    if status:
        parts.extend(status)
    diff = result.stdout.strip()
    if diff:
        parts.append(diff)
    return "\n".join(parts)


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False
