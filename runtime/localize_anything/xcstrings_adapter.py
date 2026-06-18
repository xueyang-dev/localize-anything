from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from . import PROTOCOL_VERSION
from .ios_strings_adapter import locale_to_lproj
from .json_adapter import extract_placeholders, source_hash


def extract_segments(path: Path, source_locale: str, source_path: str | None = None) -> list[dict[str, Any]]:
    logical_path = source_path or path.as_posix()
    document = _read_document(path, source_language=None, fallback_to_key=True)
    return [_segment(logical_path, source_locale, document["source_language"], resource) for resource in document["resources"]]


def rebuild(source_path: Path, translated_segments: list[dict[str, Any]], output: Path, target_locale: str | None = None) -> None:
    catalog = _load_catalog(source_path)
    target_language = _target_language(target_locale, translated_segments)
    for segment in translated_segments:
        if "target" not in segment:
            continue
        context = segment.get("context", {})
        name = context.get("resource_name")
        variation_path = context.get("variation_path") or []
        if not isinstance(name, str):
            raise ValueError(f"Segment lacks context.resource_name: {segment.get('segment_id', '<unknown>')}")
        entry = catalog.setdefault("strings", {}).setdefault(name, {})
        localizations = entry.setdefault("localizations", {})
        localization = localizations.setdefault(target_language, {})
        if variation_path:
            _set_variation_value(localization, variation_path, str(segment["target"]))
        else:
            localization["stringUnit"] = {
                "state": "needs_review",
                "value": str(segment["target"]),
            }
    _dump_catalog(catalog, output)


def stage_rebuild(
    source_path: Path,
    translated_segments: list[dict[str, Any]],
    staging_dir: Path,
    target_locale: str,
    project_root: Path | None = None,
) -> dict[str, Any]:
    relative = target_resource_path(source_path, project_root)
    output = staging_dir / relative
    rebuild(source_path, translated_segments, output, target_locale)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "adapter": "core.xcstrings",
        "target_locale": target_locale,
        "catalog_language": locale_to_catalog_language(target_locale),
        "output": output.as_posix(),
        "destination": relative.as_posix(),
        "written": True,
    }


def validate_pair(source_path: Path, target_path: Path, target_locale: str | None = None) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    try:
        source = _read_document(source_path, source_language=None, fallback_to_key=True)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _parse_failure(source_path, str(exc))
    try:
        target_language = locale_to_catalog_language(target_locale) if target_locale else source["source_language"]
        target = _read_document(target_path, source_language=target_language, fallback_to_key=False)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _parse_failure(target_path, str(exc))

    source_resources = {item["key"]: item for item in source["resources"]}
    target_resources = {item["key"]: item for item in target["resources"]}
    for skipped in source["skipped"]:
        items.append(
            _qa_item(
                "unsupported_or_skipped_resource",
                "info",
                f"Skipped string catalog resource {skipped['name']}: {skipped['reason']}",
                source_path,
                skipped["name"],
            )
        )
    for key in sorted(source_resources.keys() - target_resources.keys()):
        items.append(_qa_item("translation_coverage", "warning", f"Missing target resource: {_resource_label(source_resources[key])}", target_path, key))
    for key in sorted(target_resources.keys() - source_resources.keys()):
        items.append(_qa_item("unexpected_resource", "warning", f"Unexpected target resource: {_resource_label(target_resources[key])}", target_path, key))
    for key in sorted(source_resources.keys() & target_resources.keys()):
        source_resource = source_resources[key]
        target_resource = target_resources[key]
        expected = _resource_placeholders(source_resource)
        actual = _resource_placeholders(target_resource)
        if expected != actual:
            items.append(
                _qa_item(
                    "placeholder_parity",
                    "blocking",
                    f"Placeholder mismatch for {_resource_label(source_resource)}: source={expected}, target={actual}",
                    target_path,
                    key,
                )
            )
        if not target_resource["value"] and source_resource["value"]:
            items.append(_qa_item("empty_translation", "warning", f"Empty target resource: {_resource_label(target_resource)}", target_path, key))

    blocking = sum(item["severity"] == "blocking" for item in items)
    warnings = sum(item["severity"] == "warning" for item in items)
    status = "fail" if blocking else "pass_with_warnings" if warnings else "pass"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "status": status,
        "summary": {"blocking_count": blocking, "warning_count": warnings},
        "items": items,
    }


def target_resource_path(source_path: Path, project_root: Path | None = None) -> Path:
    if project_root is not None:
        try:
            return source_path.resolve().relative_to(project_root.resolve())
        except ValueError as exc:
            raise ValueError(f"String catalog source is not inside project root: {source_path}") from exc
    if source_path.is_absolute():
        raise ValueError("project_root is required when source_path is absolute")
    return source_path


def locale_to_catalog_language(locale: str) -> str:
    return locale_to_lproj(locale)


def is_xcstrings_path(project_root: Path, path: Path) -> bool:
    return path.suffix.lower() == ".xcstrings"


def _read_document(path: Path, source_language: str | None, fallback_to_key: bool) -> dict[str, Any]:
    catalog = _load_catalog(path)
    actual_source_language = source_language or str(catalog.get("sourceLanguage") or "")
    if not actual_source_language:
        raise ValueError(f"String catalog must declare sourceLanguage: {path}")
    strings = catalog.get("strings")
    if not isinstance(strings, dict):
        raise ValueError(f"String catalog must contain a strings object: {path}")

    resources: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for name, entry in strings.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            continue
        if entry.get("shouldTranslate") is False:
            skipped.append({"name": name, "reason": "should_translate_false"})
            continue
        localization = entry.get("localizations", {}).get(actual_source_language)
        if isinstance(localization, dict):
            leaf_units = list(_iter_localization_units(localization))
            if leaf_units:
                for variation_path, value in leaf_units:
                    if value == "":
                        skipped.append({"name": _resource_key(name, variation_path), "reason": "empty_source"})
                        continue
                    resources.append(_resource(name, value, variation_path))
                continue
        if fallback_to_key and name:
            resources.append(_resource(name, name, []))
    return {"source_language": actual_source_language, "resources": resources, "skipped": skipped}


def _load_catalog(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"String catalog must be a JSON object: {path}")
    return data


def _dump_catalog(catalog: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(catalog, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _iter_localization_units(localization: dict[str, Any], path: list[dict[str, str]] | None = None) -> list[tuple[list[dict[str, str]], str]]:
    current_path = path or []
    unit = localization.get("stringUnit")
    if isinstance(unit, dict) and isinstance(unit.get("value"), str):
        return [(current_path, unit["value"])]
    variations = localization.get("variations")
    if not isinstance(variations, dict):
        return []
    result: list[tuple[list[dict[str, str]], str]] = []
    for axis, options in variations.items():
        if not isinstance(axis, str) or not isinstance(options, dict):
            continue
        for option, child in options.items():
            if not isinstance(option, str) or not isinstance(child, dict):
                continue
            result.extend(_iter_localization_units(child, [*current_path, {"axis": axis, "option": option}]))
    return result


def _set_variation_value(localization: dict[str, Any], variation_path: list[dict[str, str]], value: str) -> None:
    current = localization
    for index, step in enumerate(variation_path):
        axis = step["axis"]
        option = step["option"]
        variations = current.setdefault("variations", {})
        options = variations.setdefault(axis, {})
        child = options.setdefault(option, {})
        if index == len(variation_path) - 1:
            child["stringUnit"] = {"state": "needs_review", "value": value}
        else:
            current = child


def _segment(logical_path: str, locale: str, catalog_source_language: str, resource: dict[str, Any]) -> dict[str, Any]:
    key = resource["key"]
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    value = resource["value"]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "segment_id": f"xcstrings:{logical_path}#{digest}",
        "source": value,
        "source_locale": locale,
        "source_path": logical_path,
        "source_hash": source_hash(f"{key}\0{value}"),
        "context": {
            "content_type": "xcstrings",
            "content_unit": f"xcstrings:{PurePosixPath(logical_path).parent.as_posix()}",
            "resource_key": key,
            "resource_name": resource["name"],
            "resource_type": resource["type"],
            "catalog_source_language": catalog_source_language,
            "table": PurePosixPath(logical_path).stem,
            "variation_path": resource["variation_path"],
        },
        "constraints": {"placeholders": _resource_placeholders(resource), "markup": []},
        "status": "new",
    }


def _resource(name: str, value: str, variation_path: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "type": "variation" if variation_path else "stringUnit",
        "name": name,
        "value": value,
        "variation_path": variation_path,
        "key": _resource_key(name, variation_path),
    }


def _resource_key(name: str, variation_path: list[dict[str, str]]) -> str:
    if not variation_path:
        return f"xcstrings:{name}"
    suffix = ".".join(f"{step['axis']}={step['option']}" for step in variation_path)
    return f"xcstrings:{name}#{suffix}"


def _target_language(target_locale: str | None, segments: list[dict[str, Any]]) -> str:
    if target_locale:
        return locale_to_catalog_language(target_locale)
    for segment in segments:
        locale = segment.get("target_locale")
        if isinstance(locale, str) and locale:
            return locale_to_catalog_language(locale)
    raise ValueError("target_locale is required for rebuilding .xcstrings")


def _resource_placeholders(resource: dict[str, Any]) -> list[str]:
    return extract_placeholders(str(resource.get("value", "")))


def _resource_label(resource: dict[str, Any]) -> str:
    if resource["type"] == "variation":
        path = ".".join(f"{step['axis']}={step['option']}" for step in resource.get("variation_path", []))
        return f"xcstrings {resource['name']}[{path}]"
    return f"xcstrings {resource['name']}"


def _parse_failure(path: Path, message: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "status": "fail",
        "summary": {"blocking_count": 1, "warning_count": 0},
        "items": [_qa_item("parse", "blocking", message, path)],
    }


def _qa_item(category: str, severity: str, message: str, path: Path, segment_id: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "channel": "adapter",
        "category": category,
        "severity": severity,
        "message": message,
        "path": path.as_posix(),
        "checked_by": "adapter",
        "coverage": "complete",
        "confidence": "deterministic",
    }
    if segment_id:
        item["segment_id"] = segment_id
    return item
