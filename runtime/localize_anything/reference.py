from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from . import PROTOCOL_VERSION
from .android_strings_adapter import extract_segments as extract_android_segments
from .android_strings_adapter import target_resource_path as android_target_resource_path
from .ios_strings_adapter import extract_segments as extract_ios_segments
from .ios_strings_adapter import target_resource_path as ios_target_resource_path
from .json_adapter import extract_segments as extract_json_segments
from .modes import mode_contract
from .planning import is_generation_eligible
from .structured_adapter import extract_segments as extract_structured_segments
from .xcstrings_adapter import extract_segments as extract_xcstrings_segments
from .xcstrings_adapter import target_resource_path as xcstrings_target_resource_path


Extractor = Callable[[Path, str, str | None], list[dict[str, Any]]]

TARGET_EXTRACTORS: dict[str, Extractor] = {
    "core.android-strings": extract_android_segments,
    "core.ios-strings": extract_ios_segments,
    "core.json-locale": extract_json_segments,
    "core.yaml-toml": lambda path, locale, source_path: extract_structured_segments(path, locale, source_path, _structured_format(path)),
    "core.xcstrings": extract_xcstrings_segments,
}


def create_reference_plan(
    project_root: Path,
    inventory_by_path: dict[str, dict[str, Any]],
    source_files: list[str],
    source_locale: str,
    target_locale: str,
    source_segments: list[dict[str, Any]],
    state_dir: Path,
    operating_mode: str,
    reference_policy: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    references = _load_existing_references(project_root, inventory_by_path, source_files, source_locale, target_locale)
    reviewed_tm = _load_reviewed_tm(state_dir / "translation-memory.jsonl", target_locale)
    references_by_identity = {
        segment_identity(segment): segment
        for item in references
        for segment in item.get("segments", [])
    }
    reviewed_tm_by_identity: dict[str, list[dict[str, Any]]] = {}
    for record in reviewed_tm:
        identity = str(record.get("identity") or record.get("segment_identity") or "")
        if identity:
            reviewed_tm_by_identity.setdefault(identity, []).append(record)
        segment_id = record.get("segment_id")
        if isinstance(segment_id, str) and segment_id:
            reviewed_tm_by_identity.setdefault(f"segment_id:{segment_id}", []).append(record)

    candidates: list[dict[str, Any]] = []
    preserved: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    source_identities = {segment_identity(segment) for segment in source_segments}

    for segment in source_segments:
        identity = segment_identity(segment)
        existing = references_by_identity.get(identity)
        if not is_generation_eligible(segment):
            preserved_segment = dict(segment)
            use_existing = (
                operating_mode == "existing_locale_maintenance"
                and reference_policy == "preserve_existing"
                and existing is not None
            )
            preserved_segment["target_locale"] = target_locale
            preserved_segment["target"] = str(existing.get("source") if use_existing else segment.get("source", ""))
            preserved_segment["status"] = "new"
            preserved_segment["workflow_status"] = "owner_review_required"
            preserved_segment["owner_review_required"] = True
            preserved_segment["generation_eligible"] = False
            preserved_segment["preservation"] = {
                "policy": "preserve_without_automatic_localization",
                "reason": "unsupported_android_markup",
                "source": "existing_target" if use_existing else "source_resource",
            }
            preserved.append(preserved_segment)
            decisions.append(_decision(segment, identity, "owner_review_required", existing, "unsupported_android_markup"))
            continue
        tm_candidates = _reviewed_tm_candidates(segment, identity, reviewed_tm_by_identity)
        tm = _matching_reviewed_tm(segment, tm_candidates)
        stale_tm = _stale_reviewed_tm(segment, tm_candidates)
        if operating_mode == "existing_locale_maintenance" and reference_policy == "preserve_existing" and tm:
            preserved_segment = dict(segment)
            preserved_segment["target_locale"] = target_locale
            preserved_segment["target"] = str(tm.get("target", existing.get("source") if existing else segment.get("source", "")))
            preserved_segment["status"] = "reviewed"
            preserved_segment["preservation"] = {
                "policy": "preserve_existing",
                "reason": "reviewed_source_hash_unchanged",
                "tm_id": tm.get("id") or tm.get("segment_id"),
            }
            preserved.append(preserved_segment)
            decisions.append(_decision(segment, identity, "preserve_existing", existing, "reviewed_source_hash_unchanged"))
            continue

        candidate = dict(segment)
        candidate["localization_mode"] = {
            "operating_mode": operating_mode,
            "reference_policy": reference_policy,
            "generation_reason": _generation_reason(existing, tm, stale_tm),
        }
        candidates.append(candidate)
        decisions.append(
            _decision(
                segment,
                identity,
                candidate["localization_mode"]["generation_reason"],
                existing,
                "reviewed_source_hash_changed" if stale_tm else None,
            )
        )

    obsolete = [
        {
            "identity": identity,
            "segment_id": segment.get("segment_id"),
            "source_path": segment.get("source_path"),
            "resource_key": segment.get("context", {}).get("resource_key"),
            "resource_name": segment.get("context", {}).get("resource_name"),
            "resource_type": segment.get("context", {}).get("resource_type"),
            "target": segment.get("source"),
            "status": "obsolete_target_reference",
            "requires_owner_review": True,
        }
        for identity, segment in sorted(references_by_identity.items())
        if identity not in source_identities
    ]

    summary = {
        "source_segment_count": len(source_segments),
        "candidate_segment_count": len(candidates),
        "preserved_segment_count": len(preserved),
        "obsolete_reference_count": len(obsolete),
        "existing_reference_file_count": sum(1 for item in references if item.get("exists")),
        "missing_reference_file_count": sum(1 for item in references if not item.get("exists")),
        "blind_reference_hidden": reference_policy == "blind",
    }
    for decision in decisions:
        key = f"{decision['action']}_count"
        summary[key] = int(summary.get(key, 0)) + 1

    plan = {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "operating_mode": operating_mode,
        "reference_policy": reference_policy,
        "mode_contract": mode_contract(operating_mode, reference_policy),
        "source_locale": source_locale,
        "target_locale": target_locale,
        "summary": summary,
        "reference_files": [
            {
                "source_file": item["source_file"],
                "target_file": item["target_file"],
                "adapter": item["adapter"],
                "exists": item["exists"],
                "segment_count": item.get("segment_count", 0),
            }
            for item in references
        ],
        "decisions": decisions,
        "obsolete_references": obsolete,
    }
    return candidates, preserved, plan


def segment_identity(segment: dict[str, Any]) -> str:
    context = segment.get("context", {})
    for key in ("resource_key", "json_pointer", "msgctxt"):
        value = context.get(key)
        if isinstance(value, str) and value:
            return f"{key}:{value}"
    source_path = segment.get("source_path")
    source = segment.get("source")
    if isinstance(source_path, str) and isinstance(source, str):
        return f"source:{source_path}:{source}"
    return f"segment_id:{segment['segment_id']}"


def _load_existing_references(
    project_root: Path,
    inventory_by_path: dict[str, dict[str, Any]],
    source_files: list[str],
    source_locale: str,
    target_locale: str,
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for source_file in source_files:
        adapter = str(inventory_by_path[source_file]["adapter"])
        target = _target_path(project_root, source_file, adapter, source_locale, target_locale)
        item: dict[str, Any] = {
            "source_file": source_file,
            "target_file": target.relative_to(project_root).as_posix() if _is_relative_to(target, project_root) else target.as_posix(),
            "adapter": adapter,
            "exists": target.is_file(),
            "segments": [],
        }
        extractor = TARGET_EXTRACTORS.get(adapter)
        if target.is_file() and extractor:
            item["segments"] = extractor(target, target_locale, item["target_file"])
            item["segment_count"] = len(item["segments"])
        references.append(item)
    return references


def _target_path(project_root: Path, source_file: str, adapter: str, source_locale: str, target_locale: str) -> Path:
    source_path = project_root / source_file
    if adapter == "core.android-strings":
        return project_root / android_target_resource_path(source_path, target_locale, project_root)
    if adapter == "core.ios-strings":
        return project_root / ios_target_resource_path(source_path, target_locale, project_root)
    if adapter == "core.xcstrings":
        return project_root / xcstrings_target_resource_path(source_path, project_root)
    if adapter in {"core.json-locale", "core.yaml-toml"}:
        relative = _replace_locale_in_path(Path(source_file), source_locale, target_locale)
        return project_root / relative
    return project_root / source_file


def _replace_locale_in_path(path: Path, source_locale: str, target_locale: str) -> Path:
    source_tokens = _locale_tokens(source_locale)
    parts = list(path.parts)
    for index, part in enumerate(parts):
        lower = part.lower()
        for token in source_tokens:
            if token in lower:
                replacement = target_locale.replace("-", "_") if "_" in token else target_locale
                parts[index] = re.sub(re.escape(token), replacement, part, flags=re.IGNORECASE)
                return Path(*parts)
    return path.with_name(f"{target_locale}{path.suffix}")


def _locale_tokens(locale: str) -> list[str]:
    normalized = locale.lower().replace("_", "-")
    return [normalized, normalized.replace("-", "_"), normalized.split("-", 1)[0]]


def _load_reviewed_tm(path: Path, target_locale: str) -> list[dict[str, Any]]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [
        record
        for record in records
        if record.get("target_locale") == target_locale and record.get("status") in {"approved", "reviewed"}
    ]


def _reviewed_tm_candidates(
    segment: dict[str, Any],
    identity: str,
    reviewed_tm_by_identity: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    candidates = [
        *reviewed_tm_by_identity.get(identity, []),
        *reviewed_tm_by_identity.get(f"segment_id:{segment.get('segment_id')}", []),
    ]
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for record in candidates:
        key = (str(record.get("id") or record.get("segment_id") or ""), str(record.get("source_hash") or ""))
        if key not in seen:
            deduped.append(record)
            seen.add(key)
    return deduped


def _matching_reviewed_tm(segment: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in candidates:
        if record.get("source_hash") == segment.get("source_hash") and record.get("target"):
            return record
    return None


def _stale_reviewed_tm(segment: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in candidates:
        if record.get("source_hash") and record.get("source_hash") != segment.get("source_hash") and record.get("target"):
            return record
    return None


def _generation_reason(
    existing: dict[str, Any] | None,
    tm: dict[str, Any] | None,
    stale_tm: dict[str, Any] | None,
) -> str:
    if stale_tm:
        return "stale_reviewed_translation"
    if existing:
        return "existing_target_unreviewed_or_conflicting"
    return "missing_target_translation"


def _decision(
    segment: dict[str, Any],
    identity: str,
    action: str,
    existing: dict[str, Any] | None,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "segment_id": segment["segment_id"],
        "identity": identity,
        "source_path": segment.get("source_path"),
        "action": action,
        "reason": reason or action,
        "existing_target_present": bool(existing),
    }


def _structured_format(path: Path) -> str:
    return "toml" if path.suffix.lower() == ".toml" else "yaml"


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False
