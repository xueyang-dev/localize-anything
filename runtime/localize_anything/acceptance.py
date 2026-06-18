from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, sha256_file, write_json


def create_acceptance(
    manifest_path: Path,
    accepted_by: str,
    accepted_scope: dict[str, list[str]],
    output: Path,
    allow_draft: bool = False,
) -> dict[str, Any]:
    if not accepted_by.strip():
        raise ValueError("accepted_by must not be empty")
    manifest = read_json(manifest_path)
    status = manifest.get("delivery_status")
    if status not in {"review_ready", "applied_draft"} and not allow_draft:
        raise ValueError(f"Cannot sign off delivery status {status!r} without explicit draft override")
    scope = {key: sorted(set(values)) for key, values in accepted_scope.items() if values}
    if not scope:
        raise ValueError("Scoped acceptance requires at least one locale, content type, file, or batch")
    allowed_keys = {"locales", "content_types", "files", "batch_ids"}
    unknown = sorted(scope.keys() - allowed_keys)
    if unknown:
        raise ValueError(f"Unsupported acceptance scope: {', '.join(unknown)}")
    project_locales = set(manifest.get("project", {}).get("target_locales", []))
    invalid_locales = sorted(set(scope.get("locales", [])) - project_locales)
    if invalid_locales:
        raise ValueError(f"Acceptance references target locales outside the manifest: {', '.join(invalid_locales)}")
    output_files = {item.get("destination") for item in manifest.get("outputs", [])}
    invalid_files = sorted(set(scope.get("files", [])) - output_files)
    if invalid_files:
        raise ValueError(f"Acceptance references files outside the manifest: {', '.join(invalid_files)}")
    if output.exists():
        raise ValueError(f"Acceptance record already exists: {output}")
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": manifest["run_id"],
        "manifest_sha256": sha256_file(manifest_path),
        "accepted_at": datetime.now(UTC).isoformat(),
        "accepted_by": accepted_by.strip(),
        "accepted_scope": scope,
        "delivery_status": "user_accepted",
        "source_delivery_status": status,
    }
    write_json(output, record)
    return record
