from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION, __version__


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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_project(project: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    unprocessed_assets: list[dict[str, Any]] = []
    ignored_parts = {".git", ".localize-anything", "localize-anything-output", "__pycache__"}
    for path in sorted(project.rglob("*")):
        if not path.is_file() or any(part in ignored_parts for part in path.parts):
            continue
        extension = path.suffix.lower()
        adapter = KNOWN_EXTENSIONS.get(extension)
        if not adapter:
            asset_type = NON_TEXT_EXTENSIONS.get(extension)
            if asset_type:
                unprocessed_assets.append(
                    {
                        "path": path.relative_to(project).as_posix(),
                        "extension": extension,
                        "asset_type": asset_type,
                        "size_bytes": path.stat().st_size,
                        "status": "not_processed",
                        "required_action": "inventory_and_review",
                    }
                )
            continue
        files.append(
            {
                "path": path.relative_to(project).as_posix(),
                "extension": path.suffix.lower(),
                "adapter": adapter,
                "sha256": file_sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    adapter_counts: dict[str, int] = {}
    for item in files:
        adapter_counts[item["adapter"]] = adapter_counts.get(item["adapter"], 0) + 1
    assessment = assess_preflight(files)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "project_root": project.resolve().as_posix(),
        "supported_files": files,
        "adapter_counts": adapter_counts,
        "unprocessed_non_text_assets": unprocessed_assets,
        "preflight_assessment": assessment,
    }


def initialize_project(
    project: Path,
    source_locale: str,
    source_files: list[str],
    target_locales: list[str],
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
    confirmed_sources = [{**inventory_by_path[path], "role": "source_of_truth"} for path in source_files]
    config = {
        "protocol_version": PROTOCOL_VERSION,
        "source_locale": source_locale,
        "source_files": source_files,
        "target_locales": target_locales,
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


def _write_json(path: Path, value: Any) -> None:
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
