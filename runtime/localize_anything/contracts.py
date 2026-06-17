from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION


ADAPTER_ID_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
ADAPTER_REQUIRED = {
    "protocol_version",
    "id",
    "name",
    "version",
    "implementation_status",
    "formats",
    "capabilities",
    "permissions",
    "runtime",
}
ADAPTER_STATUSES = {"implemented", "experimental", "planned"}
ADAPTER_TRUST = {"core", "project", "community", "verified"}
ADAPTER_CAPABILITIES = {
    "detect",
    "inventory",
    "extract",
    "validate_source",
    "rebuild",
    "validate_output",
    "plan_apply",
    "pseudo_localize",
}
ADAPTER_PERMISSIONS = {"read_project", "write_staging", "write_project", "network", "execute"}
ROUND_TRIP_LEVELS = {"full_round_trip", "extract_and_rebuild", "extract_only", "inspect_only", "unsupported"}


def validate_adapter_manifest(path: Path) -> list[str]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: cannot parse JSON: {exc}"]
    if not isinstance(manifest, dict):
        return [f"{path}: root must be an object"]

    errors: list[str] = []
    missing = sorted(ADAPTER_REQUIRED - manifest.keys())
    if missing:
        errors.append(f"{path}: missing required fields: {', '.join(missing)}")
    if manifest.get("protocol_version") != PROTOCOL_VERSION:
        errors.append(f"{path}: unsupported protocol_version {manifest.get('protocol_version')!r}")
    adapter_id = manifest.get("id")
    if not isinstance(adapter_id, str) or not ADAPTER_ID_RE.fullmatch(adapter_id):
        errors.append(f"{path}: invalid adapter id {adapter_id!r}")
    _check_enum(errors, path, manifest, "implementation_status", ADAPTER_STATUSES)
    if "trust" in manifest:
        _check_enum(errors, path, manifest, "trust", ADAPTER_TRUST)
    if "round_trip_level" in manifest:
        _check_enum(errors, path, manifest, "round_trip_level", ROUND_TRIP_LEVELS)
    _check_nonempty_unique_list(errors, path, manifest, "formats")
    _check_unique_enum_list(errors, path, manifest, "capabilities", ADAPTER_CAPABILITIES)
    _check_unique_enum_list(errors, path, manifest, "permissions", ADAPTER_PERMISSIONS)
    if "extensions" in manifest:
        _check_nonempty_unique_list(errors, path, manifest, "extensions", allow_empty=True)
        for extension in manifest.get("extensions", []):
            if not isinstance(extension, str) or not extension.startswith("."):
                errors.append(f"{path}: extension must start with '.': {extension!r}")

    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        errors.append(f"{path}: runtime must be an object")
    elif not isinstance(runtime.get("dependencies"), list):
        errors.append(f"{path}: runtime.dependencies must be a list")

    entrypoints = manifest.get("entrypoints", {})
    if not isinstance(entrypoints, dict):
        errors.append(f"{path}: entrypoints must be an object")
    else:
        for name, command in entrypoints.items():
            if not isinstance(name, str) or not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
                errors.append(f"{path}: entrypoint {name!r} must be a non-empty string array")
    return errors


def validate_adapter_tree(root: Path) -> dict[str, Any]:
    manifests = sorted(root.rglob("adapter.json"))
    errors = [error for path in manifests for error in validate_adapter_manifest(path)]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": "fail" if errors else "pass",
        "manifests_checked": len(manifests),
        "errors": errors,
    }


def _check_enum(errors: list[str], path: Path, value: dict[str, Any], key: str, allowed: set[str]) -> None:
    if value.get(key) not in allowed:
        errors.append(f"{path}: {key} must be one of {sorted(allowed)}, got {value.get(key)!r}")


def _check_nonempty_unique_list(
    errors: list[str], path: Path, value: dict[str, Any], key: str, allow_empty: bool = False
) -> None:
    items = value.get(key)
    if not isinstance(items, list) or (not allow_empty and not items):
        errors.append(f"{path}: {key} must be {'a' if allow_empty else 'a non-empty'} list")
        return
    if any(not isinstance(item, str) for item in items):
        errors.append(f"{path}: {key} items must be strings")
    if len(items) != len(set(items)):
        errors.append(f"{path}: {key} contains duplicates")


def _check_unique_enum_list(errors: list[str], path: Path, value: dict[str, Any], key: str, allowed: set[str]) -> None:
    _check_nonempty_unique_list(errors, path, value, key, allow_empty=True)
    items = value.get(key)
    if isinstance(items, list):
        invalid = sorted({item for item in items if isinstance(item, str) and item not in allowed})
        if invalid:
            errors.append(f"{path}: unsupported {key}: {', '.join(invalid)}")
