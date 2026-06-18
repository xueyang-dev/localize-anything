from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION, __version__
from .io_utils import read_json, sha256_file, write_json


CANONICAL_ASSETS = ("localization-context.md", "glossary.csv", "translation-memory.jsonl")


def package_delivery(
    state_dir: Path,
    staging_dir: Path,
    output_root: Path,
    qa_result_paths: list[Path] | None = None,
    requested_status: str = "draft_package",
    run_id: str | None = None,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    staging_dir = staging_dir.resolve()
    output_root = output_root.resolve()
    if requested_status not in {"draft_package", "review_ready", "blocked"}:
        raise ValueError(f"Unsupported package delivery status: {requested_status}")
    if not state_dir.is_dir():
        raise ValueError(f"State directory does not exist: {state_dir}")
    if not staging_dir.is_dir():
        raise ValueError(f"Staging directory does not exist: {staging_dir}")
    missing_assets = [name for name in CANONICAL_ASSETS if not (state_dir / name).is_file()]
    if missing_assets:
        raise ValueError(f"State directory lacks canonical assets: {', '.join(missing_assets)}")

    config = read_json(state_dir / "config.json")
    state_manifest = state_dir / "delivery-manifest.json"
    if not state_manifest.exists():
        state_manifest = state_dir / "current-manifest.json"
    current = read_json(state_manifest)
    qa = aggregate_qa(qa_result_paths or [])
    if requested_status == "review_ready" and qa["status"] not in {"pass", "pass_with_warnings"}:
        raise ValueError("review_ready requires completed deterministic QA without blockers")
    if requested_status == "review_ready" and qa["blocking_count"]:
        raise ValueError("review_ready cannot contain blocking QA findings")
    if requested_status == "review_ready" and not ({"runtime", "adapter"} & set(qa["evidence_channels"])):
        raise ValueError("review_ready requires runtime or adapter deterministic QA evidence")
    if requested_status == "review_ready" and "agent" not in qa["evidence_channels"]:
        raise ValueError("review_ready requires agent linguistic QA evidence")

    staged_files = _regular_staged_files(staging_dir)
    if not staged_files:
        raise ValueError("Staging directory contains no deliverable files")
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = output_root / run_id
    if destination.exists():
        raise ValueError(f"Immutable delivery snapshot already exists: {destination}")

    project_root = state_dir.parent
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{run_id}.", dir=output_root))
    try:
        for asset in CANONICAL_ASSETS:
            shutil.copy2(state_dir / asset, temporary / asset)
        outputs: list[dict[str, Any]] = []
        for staged in staged_files:
            relative = staged.relative_to(staging_dir)
            packaged = temporary / "files" / relative
            packaged.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged, packaged)
            project_destination = project_root / relative
            outputs.append(
                {
                    "package_path": (Path("files") / relative).as_posix(),
                    "destination": relative.as_posix(),
                    "sha256": sha256_file(packaged),
                    "size_bytes": packaged.stat().st_size,
                    "destination_base_sha256": sha256_file(project_destination) if project_destination.is_file() else None,
                }
            )

        unprocessed_assets = current.get("unprocessed_non_text_assets", [])
        qa_report = render_qa_report(qa, requested_status, unprocessed_assets)
        (temporary / "qa-report.md").write_text(qa_report, encoding="utf-8")
        snapshot_hash = _snapshot_hash(temporary)
        manifest = {
            "protocol_version": PROTOCOL_VERSION,
            "run_id": run_id,
            "delivery_status": requested_status,
            "project": {
                "source_locale": config["source_locale"],
                "target_locales": config["target_locales"],
                "mode": "standard_project",
            },
            "source_material": current.get("source_material", []),
            "unprocessed_non_text_assets": unprocessed_assets,
            "outputs": outputs,
            "assets": {
                "context": "localization-context.md",
                "glossary": "glossary.csv",
                "translation_memory": "translation-memory.jsonl",
                "qa_report": "qa-report.md",
            },
            "qa": {
                "status": qa["status"],
                "blocking_count": qa["blocking_count"],
                "warning_count": qa["warning_count"],
                "report": "qa-report.md",
                "evidence_files": [path.as_posix() for path in qa_result_paths or []],
                "evidence_channels": qa["evidence_channels"],
            },
            "runtime": {
                **current.get("runtime", {}),
                "name": "localize-anything-reference",
                "version": __version__,
            },
            "snapshot": {
                "content_sha256": snapshot_hash,
                "created_at": datetime.now(UTC).isoformat(),
                "immutable": True,
            },
        }
        write_json(temporary / "delivery-manifest.json", manifest)
        os.replace(temporary, destination)
        write_json(state_dir / "delivery-manifest.json", manifest)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"delivery_directory": destination.as_posix(), "manifest": manifest}


def aggregate_qa(paths: list[Path]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    evidence_channels: set[str] = set()
    for path in paths:
        value = read_json(path)
        if not isinstance(value, dict) or not isinstance(value.get("items"), list):
            raise ValueError(f"Invalid QA result: {path}")
        items.extend(value["items"])
        evidence_channels.update(str(channel) for channel in value.get("evidence_channels", []))
        evidence_channels.update(str(item.get("channel")) for item in value["items"] if item.get("channel"))
    blocking = sum(item.get("severity") == "blocking" for item in items)
    warnings = sum(item.get("severity") == "warning" for item in items)
    if not paths:
        status = "not_checked"
    elif blocking:
        status = "fail"
    elif warnings:
        status = "pass_with_warnings"
    else:
        status = "pass"
    return {
        "status": status,
        "blocking_count": blocking,
        "warning_count": warnings,
        "evidence_channels": sorted(evidence_channels),
        "items": items,
    }


def render_qa_report(
    qa: dict[str, Any], delivery_status: str, unprocessed_assets: list[dict[str, Any]] | None = None
) -> str:
    lines = [
        "# QA Report",
        "",
        "## Delivery Summary",
        "",
        f"- Delivery status: `{delivery_status}`",
        f"- QA status: `{qa['status']}`",
        f"- Blocking findings: {qa['blocking_count']}",
        f"- Warnings: {qa['warning_count']}",
        f"- Evidence channels: {', '.join(qa['evidence_channels']) or 'none'}",
        "",
        "## Findings",
        "",
    ]
    if not qa["items"]:
        lines.append("No QA findings were supplied. Deterministic QA is not considered complete." if qa["status"] == "not_checked" else "No findings.")
    for item in qa["items"]:
        severity = str(item.get("severity", "info")).upper()
        category = item.get("category", "uncategorized")
        message = str(item.get("message", "")).replace("\n", " ")
        location = item.get("path") or item.get("segment_id")
        suffix = f" (`{location}`)" if location else ""
        lines.append(f"- **{severity} / {category}:** {message}{suffix}")
    lines.extend(["", "## Unprocessed Non-Text Assets", ""])
    if unprocessed_assets:
        for asset in unprocessed_assets:
            lines.append(
                f"- `{asset.get('path')}`: {asset.get('asset_type', 'non-text')} / `{asset.get('status', 'not_processed')}`"
            )
    else:
        lines.append("No unprocessed non-text assets were detected during preflight.")
    lines.extend(
        [
            "",
            "## Acceptance",
            "",
            "This package is a draft or review artifact until the user creates a scoped sign-off record.",
            "",
        ]
    )
    return "\n".join(lines)


def _regular_staged_files(staging_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(staging_dir.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Staging symlinks are not allowed: {path}")
        if path.is_file():
            files.append(path)
    return files


def _snapshot_hash(directory: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        relative = path.relative_to(directory).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()
