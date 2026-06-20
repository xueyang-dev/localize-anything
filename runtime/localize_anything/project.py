from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION, __version__
from .android_strings_adapter import android_resource_routing, is_android_strings_path
from .ios_strings_adapter import is_ios_strings_path
from .modes import resolve_mode_policy
from .xcstrings_adapter import is_xcstrings_path


KNOWN_EXTENSIONS = {
    ".json": "core.json-locale",
    ".csv": "core.tabular",
    ".tsv": "core.tabular",
    ".xlsx": "core.tabular",
    ".yaml": "core.yaml-toml",
    ".yml": "core.yaml-toml",
    ".toml": "core.yaml-toml",
    ".md": "core.markup",
    ".markdown": "core.markup",
    ".html": "core.markup",
    ".htm": "core.markup",
    ".srt": "core.subtitles",
    ".vtt": "core.subtitles",
    ".xlf": "core.xliff",
    ".xliff": "core.xliff",
    ".po": "core.gettext-po",
    ".pot": "core.gettext-po",
    ".cfg": "scenario.wesnoth",
}

NON_TEXT_EXTENSIONS = {
    ".aac": "audio",
    ".bmp": "image",
    ".flac": "audio",
    ".gif": "image",
    ".jpeg": "image",
    ".jpg": "image",
    ".m4a": "audio",
    ".mov": "video",
    ".mp3": "audio",
    ".mp4": "video",
    ".ogg": "audio",
    ".otf": "font",
    ".png": "image",
    ".svg": "image",
    ".ttf": "font",
    ".wav": "audio",
    ".webm": "video",
    ".webp": "image",
}

IGNORED_DIRECTORY_NAMES = {
    ".git",
    ".gradle",
    ".hg",
    ".idea",
    ".localize-anything",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".swiftpm",
    ".vscode",
    "__pycache__",
    "build",
    "carthage",
    "deriveddata",
    "dist",
    "localize-anything-output",
    "node_modules",
    "pods",
    "target",
}
IGNORED_DIRECTORY_PREFIXES = ("localize-run-",)
IGNORED_FILE_GLOBS = ("*.class", "*.o", "*.pyc")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_project(project: Path) -> dict[str, Any]:
    project = project.resolve()
    files: list[dict[str, Any]] = []
    unprocessed_assets: list[dict[str, Any]] = []
    ignored_paths: list[dict[str, str]] = []
    skipped_paths: list[dict[str, str]] = []
    for path in _iter_project_files(project, ignored_paths, skipped_paths):
        try:
            extension = path.suffix.lower()
            adapter_metadata: dict[str, Any] = {}
            if is_xcstrings_path(project, path):
                adapter = "core.xcstrings"
            elif is_android_strings_path(project, path):
                adapter = "core.android-strings"
                adapter_metadata = android_resource_routing(path, project)
            elif is_ios_strings_path(project, path):
                adapter = "core.ios-strings"
            else:
                adapter = KNOWN_EXTENSIONS.get(extension)
            size_bytes = path.stat().st_size
            digest = file_sha256(path)
        except OSError as exc:
            skipped_paths.append(
                {
                    "path": _relative_project_path(project, path),
                    "reason": exc.__class__.__name__,
                    "detail": str(exc),
                }
            )
            continue
        if not adapter:
            asset_type = NON_TEXT_EXTENSIONS.get(extension)
            if asset_type:
                unprocessed_assets.append(
                    {
                        "path": _relative_project_path(project, path),
                        "extension": extension,
                        "asset_type": asset_type,
                        "size_bytes": size_bytes,
                        "status": "not_processed",
                        "required_action": "inventory_and_review",
                    }
                )
            continue
        files.append(
            {
                "path": _relative_project_path(project, path),
                "extension": path.suffix.lower(),
                "adapter": adapter,
                "sha256": digest,
                "size_bytes": size_bytes,
                **adapter_metadata,
            }
        )
    adapter_counts: dict[str, int] = {}
    for item in files:
        adapter_counts[item["adapter"]] = adapter_counts.get(item["adapter"], 0) + 1
    assessment = assess_preflight(files)
    android_generation_sources = [
        item["path"]
        for item in files
        if item["adapter"] == "core.android-strings" and item.get("android_role") == "source_candidate"
    ]
    android_locale_references = [
        item["path"]
        for item in files
        if item["adapter"] == "core.android-strings" and item.get("android_role") == "locale_reference"
    ]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "project_root": project.resolve().as_posix(),
        "supported_files": files,
        "adapter_counts": adapter_counts,
        "android_generation_source_files": sorted(android_generation_sources),
        "android_locale_reference_files": sorted(android_locale_references),
        "unprocessed_non_text_assets": unprocessed_assets,
        "scan_policy": scan_policy(),
        "ignored_path_count": len(ignored_paths),
        "ignored_paths": ignored_paths,
        "skipped_path_count": len(skipped_paths),
        "skipped_paths": skipped_paths,
        "preflight_assessment": assessment,
    }


def initialize_project(
    project: Path,
    source_locale: str,
    source_files: list[str],
    target_locales: list[str],
    operating_mode: str | None = None,
    reference_policy: str | None = None,
    workflow_depth: str = "ask",
    preflight_mode: str = "auto",
    privacy_mode: str = "standard",
    data_classification: str = "internal",
) -> dict[str, Any]:
    state = project / ".localize-anything"
    state.mkdir(parents=True, exist_ok=True)
    inventory = inspect_project(project)
    inventory_by_path = {item["path"]: item for item in inventory["supported_files"]}
    unknown_sources = sorted(set(source_files) - inventory_by_path.keys())
    if unknown_sources:
        raise ValueError(f"Confirmed source files were not found or are unsupported: {', '.join(unknown_sources)}")
    invalid_android_sources = sorted(
        path
        for path in source_files
        if inventory_by_path[path]["adapter"] == "core.android-strings"
        and inventory_by_path[path].get("android_role") != "source_candidate"
    )
    if invalid_android_sources:
        raise ValueError(
            "Android locale references or uncertain qualifier paths cannot be source truth: "
            + ", ".join(invalid_android_sources)
        )
    operating_mode, reference_policy = resolve_mode_policy(operating_mode, reference_policy)
    confirmed_sources = [{**inventory_by_path[path], "role": "source_of_truth"} for path in source_files]
    config = {
        "protocol_version": PROTOCOL_VERSION,
        "source_locale": source_locale,
        "source_files": source_files,
        "target_locales": target_locales,
        "operating_mode": operating_mode,
        "reference_policy": reference_policy,
        "delivery_mode": "bundle",
        "preflight_mode": preflight_mode,
        "workflow_depth": workflow_depth,
        "recommended_preflight_mode": inventory["preflight_assessment"]["recommended_preflight_mode"],
        "recommended_workflow_depth": inventory["preflight_assessment"]["recommended_workflow_depth"],
        "privacy_mode": privacy_mode,
        "data_classification": data_classification,
        "ambiguity_policy": "preserve_and_ask",
        "question_policy": "batch_by_severity",
        "pseudo_localization": False,
        "visual_qa": "when_applicable",
        "output_directory": "localize-anything-output",
        "adapter_overrides": {},
    }
    _write_json(state / "config.json", config)
    _write_if_missing(state / "localization-context.md", _context_template(source_locale, target_locales))
    _write_glossary_if_missing(state / "glossary.csv")
    _write_if_missing(state / "translation-memory.jsonl", "")

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "delivery_status": "draft_package",
        "project": {
            "source_locale": source_locale,
            "target_locales": target_locales,
            "mode": "standard_project",
            "operating_mode": operating_mode,
            "reference_policy": reference_policy,
        },
        "source_material": confirmed_sources,
        "preflight": inventory["preflight_assessment"],
        "unprocessed_non_text_assets": inventory["unprocessed_non_text_assets"],
        "outputs": [],
        "assets": {
            "context": "localization-context.md",
            "glossary": "glossary.csv",
            "translation_memory": "translation-memory.jsonl",
        },
        "qa": {
            "status": "not_checked",
            "blocking_count": 0,
            "warning_count": 0,
            "report": "qa-report.md",
        },
        "runtime": {
            "name": "localize-anything-reference",
            "version": __version__,
            "capabilities": {
                "filesystem": True,
                "code_execution": True,
                "network": False,
                "vision": False,
                "browser": False,
                "parallel_tasks": False,
                "context_limit": "unknown",
            },
        },
    }
    _write_json(state / "delivery-manifest.json", manifest)
    return {"state_directory": state.as_posix(), "inventory": inventory, "manifest": manifest}


def scan_policy() -> dict[str, Any]:
    return {
        "ignored_directory_names": sorted(IGNORED_DIRECTORY_NAMES),
        "ignored_directory_prefixes": list(IGNORED_DIRECTORY_PREFIXES),
        "ignored_file_globs": list(IGNORED_FILE_GLOBS),
        "routing_evidence": "ignored_paths and skipped_paths are emitted by inspect_project",
    }


def session_index_path(project: Path) -> Path:
    return project.resolve() / ".localize-anything" / "sessions" / "index.json"


def load_session_index(project: Path) -> dict[str, Any]:
    project = project.resolve()
    path = session_index_path(project)
    if not path.exists():
        return {
            "protocol_version": PROTOCOL_VERSION,
            "project_root": project.as_posix(),
            "updated_at": None,
            "latest_session_id": None,
            "sessions": [],
        }
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def record_project_session(
    project: Path,
    *,
    run_id: str,
    kind: str,
    status: str,
    source_locale: str,
    target_locale: str,
    selected_source_files: list[str],
    run_directory: Path | str,
    operating_mode: str | None = None,
    reference_policy: str | None = None,
    artifacts: dict[str, Any] | None = None,
    routing: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
    child_runs: dict[str, Any] | None = None,
    next_actions: list[str] | None = None,
) -> dict[str, Any]:
    project = project.resolve()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    index = load_session_index(project)
    index["protocol_version"] = PROTOCOL_VERSION
    index["project_root"] = project.as_posix()
    index["updated_at"] = now
    index["latest_session_id"] = run_id
    operating_mode, reference_policy = resolve_mode_policy(operating_mode, reference_policy)
    session = {
        "protocol_version": PROTOCOL_VERSION,
        "session_id": run_id,
        "run_id": run_id,
        "kind": kind,
        "status": status,
        "updated_at": now,
        "source_locale": source_locale,
        "target_locale": target_locale,
        "operating_mode": operating_mode,
        "reference_policy": reference_policy,
        "selected_source_files": selected_source_files,
        "run_directory": Path(run_directory).as_posix(),
        "artifacts": artifacts or {},
        "routing": routing or {},
        "summary": summary or {},
        "child_runs": child_runs or {},
        "next_actions": next_actions or [],
    }
    sessions = [item for item in index.get("sessions", []) if item.get("session_id") != run_id]
    sessions.append(session)
    index["sessions"] = sessions
    _write_json(session_index_path(project), index)
    return index


def assess_preflight(files: list[dict[str, Any]]) -> dict[str, Any]:
    total_bytes = sum(int(item.get("size_bytes", 0)) for item in files)
    narrative_files = [
        item
        for item in files
        if item.get("extension") in {".cfg", ".po", ".pot"}
        or any(part in item.get("path", "").lower() for part in ("scenario", "campaign", "dialog"))
    ]
    narrative_ratio = len(narrative_files) / len(files) if files else 0.0
    if narrative_ratio >= 0.4 and total_bytes > 250_000:
        recommended_preflight = "layered"
        recommended_workflow = "high_assurance"
        reason = "Large context-dependent narrative or game corpus"
    elif narrative_ratio >= 0.4:
        recommended_preflight = "full"
        recommended_workflow = "standard"
        reason = "Context-dependent narrative or game content"
    elif total_bytes > 5_000_000:
        recommended_preflight = "skip_deep"
        recommended_workflow = "standard"
        reason = "Large weakly connected practical corpus"
    elif total_bytes > 500_000:
        recommended_preflight = "layered"
        recommended_workflow = "standard"
        reason = "Corpus size benefits from bounded preflight batches"
    else:
        recommended_preflight = "light"
        recommended_workflow = "fast"
        reason = "Small weakly connected resource set"
    return {
        "supported_file_count": len(files),
        "supported_size_bytes": total_bytes,
        "context_dependency": "high" if narrative_ratio >= 0.4 else "low",
        "recommended_preflight_mode": recommended_preflight,
        "recommended_workflow_depth": recommended_workflow,
        "reason": reason,
        "requires_user_choice": True,
    }


def _iter_project_files(project: Path, ignored_paths: list[dict[str, str]], skipped_paths: list[dict[str, str]]):
    def onerror(exc: OSError) -> None:
        skipped_paths.append(
            {
                "path": _relative_project_path(project, Path(getattr(exc, "filename", project))),
                "reason": exc.__class__.__name__,
                "detail": str(exc),
            }
        )

    for root, dirs, filenames in os.walk(project, topdown=True, onerror=onerror):
        root_path = Path(root)
        kept_dirs: list[str] = []
        for directory in sorted(dirs):
            path = root_path / directory
            reason = _ignored_directory_reason(directory)
            if reason:
                ignored_paths.append({"path": _relative_project_path(project, path), "reason": reason})
            else:
                kept_dirs.append(directory)
        dirs[:] = kept_dirs
        for filename in sorted(filenames):
            path = root_path / filename
            reason = _ignored_file_reason(filename)
            if reason:
                ignored_paths.append({"path": _relative_project_path(project, path), "reason": reason})
                continue
            yield path


def _ignored_directory_reason(name: str) -> str | None:
    normalized = name.lower()
    if normalized in IGNORED_DIRECTORY_NAMES:
        return "ignored_directory"
    if any(normalized.startswith(prefix) for prefix in IGNORED_DIRECTORY_PREFIXES):
        return "localize_anything_run_output"
    return None


def _ignored_file_reason(name: str) -> str | None:
    lower = name.lower()
    for pattern in IGNORED_FILE_GLOBS:
        if lower.endswith(pattern.lstrip("*")):
            return "ignored_generated_file"
    return None


def _relative_project_path(project: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _write_if_missing(path: Path, content: str) -> None:
    if path.exists():
        return
    path.write_text(content, encoding="utf-8")


def _write_glossary_if_missing(path: Path) -> None:
    if path.exists():
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "term",
                "source_locale",
                "target_locale",
                "approved_translation",
                "status",
                "scope",
                "part_of_speech",
                "definition",
                "context",
                "do_not_translate",
                "source_provenance",
                "notes",
            ]
        )


def _context_template(source_locale: str, target_locales: list[str]) -> str:
    targets = ", ".join(target_locales)
    return f"""# Localization Context

## Memory Policy

- Always load P0 project contract, source of truth, approved decisions, hard constraints, and blockers.
- Load P1 character, entity, narrative, locale, and adapter notes only when relevant.
- Keep P2 history and rejected alternatives archived.

## Project Contract

- Source locale: {source_locale}
- Target locales: {targets}
- Delivery mode: bundle-first

## Source Of Truth

<!-- Confirm source artifacts and reference-only materials during intake. -->

## Content Strategy

<!-- Declare localization depth by content type. -->

## Approved Decisions

## Characters, Entities, And Voices

## World, Domain, And Narrative State

## Locale-Specific Notes

## Adapter And Format Constraints

## QA Contract

## Blocking Questions

## Batch Progress
"""
