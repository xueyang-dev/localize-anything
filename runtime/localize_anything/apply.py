from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, sha256_file


def create_apply_plan(delivery_dir: Path, project_root: Path) -> dict[str, Any]:
    delivery_dir = delivery_dir.resolve()
    project_root = project_root.resolve()
    manifest = read_json(delivery_dir / "delivery-manifest.json")
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
        "rollback": {"backup_required_for": [item["destination"] for item in operations if item["backup_required"]]},
    }


def _safe_relative(value: str, label: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe {label}: {value!r}")
    return path
