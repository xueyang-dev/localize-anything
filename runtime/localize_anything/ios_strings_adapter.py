from __future__ import annotations

import copy
import hashlib
import plistlib
from pathlib import Path, PurePosixPath
from typing import Any

from . import PROTOCOL_VERSION
from .json_adapter import extract_placeholders, source_hash


IOS_STRING_EXTENSIONS = {".strings", ".stringsdict"}
PLURAL_CATEGORIES = ("zero", "one", "two", "few", "many", "other")


def extract_segments(path: Path, source_locale: str, source_path: str | None = None) -> list[dict[str, Any]]:
    logical_path = source_path or path.as_posix()
    document = _read_document(path)
    return [_segment(logical_path, source_locale, resource) for resource in document["resources"]]


def rebuild(source_path: Path, translated_segments: list[dict[str, Any]], output: Path) -> None:
    suffix = source_path.suffix.lower()
    if suffix == ".strings":
        _rebuild_strings(source_path, translated_segments, output)
        return
    if suffix == ".stringsdict":
        _rebuild_stringsdict(source_path, translated_segments, output)
        return
    raise ValueError(f"Unsupported iOS localization resource: {source_path}")


def stage_rebuild(
    source_path: Path,
    translated_segments: list[dict[str, Any]],
    staging_dir: Path,
    target_locale: str,
    project_root: Path | None = None,
) -> dict[str, Any]:
    relative = target_resource_path(source_path, target_locale, project_root)
    output = staging_dir / relative
    rebuild(source_path, translated_segments, output)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "adapter": "core.ios-strings",
        "target_locale": target_locale,
        "lproj": locale_to_lproj(target_locale),
        "output": output.as_posix(),
        "destination": relative.as_posix(),
        "written": True,
    }


def validate_pair(source_path: Path, target_path: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    try:
        source = _read_document(source_path)
    except (OSError, ValueError, plistlib.InvalidFileException) as exc:
        return _parse_failure(source_path, str(exc))
    try:
        target = _read_document(target_path)
    except (OSError, ValueError, plistlib.InvalidFileException) as exc:
        return _parse_failure(target_path, str(exc))

    for duplicate in source["duplicates"]:
        items.append(_qa_item("duplicate_resource", "blocking", f"Duplicate source string resource: {duplicate}", source_path, duplicate))
    for duplicate in target["duplicates"]:
        items.append(_qa_item("duplicate_resource", "blocking", f"Duplicate target string resource: {duplicate}", target_path, duplicate))

    source_resources = {item["key"]: item for item in source["resources"]}
    target_resources = {item["key"]: item for item in target["resources"]}
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
        if not target_resource["value"]:
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


def target_resource_path(source_path: Path, target_locale: str, project_root: Path | None = None) -> Path:
    if project_root is not None:
        try:
            relative = source_path.resolve().relative_to(project_root.resolve())
        except ValueError as exc:
            raise ValueError(f"iOS source is not inside project root: {source_path}") from exc
    elif source_path.is_absolute():
        raise ValueError("project_root is required when source_path is absolute")
    else:
        relative = source_path

    parts = list(relative.parts)
    for index, part in enumerate(parts):
        if part.endswith(".lproj"):
            parts[index] = f"{locale_to_lproj(target_locale)}.lproj"
            return Path(*parts)
    raise ValueError(f"iOS strings source must be under a .lproj directory: {source_path}")


def locale_to_lproj(locale: str) -> str:
    parts = [part for part in locale.replace("_", "-").split("-") if part]
    if not parts:
        raise ValueError("target locale is required")
    language = parts[0].lower()
    lower_parts = [part.lower() for part in parts[1:]]
    if language == "zh":
        if any(part in {"hant", "tw", "hk", "mo"} for part in lower_parts):
            return "zh-Hant"
        return "zh-Hans"
    if len(parts) == 1:
        return language
    if len(parts[1]) == 4:
        return f"{language}-{parts[1].title()}"
    return f"{language}-{parts[1].upper()}"


def is_ios_strings_path(project_root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(project_root)
    except ValueError:
        relative = path
    return path.suffix.lower() in IOS_STRING_EXTENSIONS and any(part.endswith(".lproj") for part in relative.parts)


def _read_document(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".strings":
        return _read_strings(path)
    if suffix == ".stringsdict":
        return _read_stringsdict(path)
    raise ValueError(f"Unsupported iOS localization resource: {path}")


def _read_strings(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    resources: list[dict[str, Any]] = []
    duplicates: list[str] = []
    seen: set[str] = set()
    position = 0
    length = len(text)
    while True:
        start = _find_next_quoted_string(text, position)
        if start is None:
            suffix = text[position:]
            break
        prefix = text[position:start]
        key, cursor = _parse_quoted_string(text, start)
        cursor = _skip_space_and_comments(text, cursor)
        if cursor >= length or text[cursor] != "=":
            raise ValueError(f"Expected '=' after key {key!r} in {path}")
        cursor = _skip_space_and_comments(text, cursor + 1)
        if cursor >= length or text[cursor] != '"':
            raise ValueError(f"Expected quoted value for key {key!r} in {path}")
        value, cursor = _parse_quoted_string(text, cursor)
        cursor = _skip_space_and_comments(text, cursor)
        if cursor >= length or text[cursor] != ";":
            raise ValueError(f"Expected ';' after key {key!r} in {path}")
        cursor += 1
        resource_key = _strings_key(key)
        if resource_key in seen:
            duplicates.append(resource_key)
        seen.add(resource_key)
        resources.append(_resource("strings", key, value, resource_key, prefix=prefix))
        position = cursor
    return {"format": "strings", "resources": resources, "duplicates": duplicates, "suffix": suffix}


def _read_stringsdict(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        root = plistlib.load(handle)
    if not isinstance(root, dict):
        raise ValueError(f"iOS .stringsdict must contain a dictionary root: {path}")
    resources: list[dict[str, Any]] = []
    duplicates: list[str] = []
    seen: set[str] = set()
    for resource_name, resource_value in root.items():
        if not isinstance(resource_name, str) or not isinstance(resource_value, dict):
            continue
        for variable, variable_value in resource_value.items():
            if not isinstance(variable, str) or not isinstance(variable_value, dict):
                continue
            if variable.startswith("NSString"):
                continue
            for plural_category in PLURAL_CATEGORIES:
                value = variable_value.get(plural_category)
                if not isinstance(value, str):
                    continue
                resource_key = _stringsdict_key(resource_name, variable, plural_category)
                if resource_key in seen:
                    duplicates.append(resource_key)
                seen.add(resource_key)
                resources.append(
                    _resource(
                        "stringsdict_plural",
                        resource_name,
                        value,
                        resource_key,
                        variable=variable,
                        plural_category=plural_category,
                    )
                )
    return {"format": "stringsdict", "resources": resources, "duplicates": duplicates, "root": root}


def _rebuild_strings(source_path: Path, translated_segments: list[dict[str, Any]], output: Path) -> None:
    document = _read_strings(source_path)
    by_key = _targets_by_resource_key(translated_segments)
    parts: list[str] = []
    for resource in document["resources"]:
        segment = by_key.get(resource["key"])
        if not segment or "target" not in segment:
            continue
        parts.append(resource.get("prefix", ""))
        parts.append(f"\"{_escape_strings_literal(resource['name'])}\" = \"{_escape_strings_literal(str(segment['target']))}\";")
    parts.append(document.get("suffix", ""))
    text = "".join(parts)
    if text and not text.endswith("\n"):
        text += "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8", newline="\n")


def _rebuild_stringsdict(source_path: Path, translated_segments: list[dict[str, Any]], output: Path) -> None:
    document = _read_stringsdict(source_path)
    root = copy.deepcopy(document["root"])
    by_key = _targets_by_resource_key(translated_segments)
    for resource in document["resources"]:
        segment = by_key.get(resource["key"])
        if not segment or "target" not in segment:
            continue
        root[resource["name"]][resource["variable"]][resource["plural_category"]] = str(segment["target"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        plistlib.dump(root, handle, sort_keys=False)


def _segment(logical_path: str, locale: str, resource: dict[str, Any]) -> dict[str, Any]:
    key = resource["key"]
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    value = resource["value"]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "segment_id": f"ios:{logical_path}#{digest}",
        "source": value,
        "source_locale": locale,
        "source_path": logical_path,
        "source_hash": source_hash(f"{key}\0{value}"),
        "context": {
            "content_type": "ios_string",
            "content_unit": f"ios:{PurePosixPath(logical_path).parent.as_posix()}",
            "resource_key": key,
            "resource_name": resource["name"],
            "resource_type": resource["type"],
            "file_format": "stringsdict" if resource["type"].startswith("stringsdict") else "strings",
            "table": PurePosixPath(logical_path).stem,
            "variable": resource.get("variable"),
            "plural_category": resource.get("plural_category"),
        },
        "constraints": {"placeholders": _resource_placeholders(resource), "markup": []},
        "status": "new",
    }


def _targets_by_resource_key(segments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for segment in segments:
        key = segment.get("context", {}).get("resource_key")
        if isinstance(key, str):
            result[key] = segment
    return result


def _resource(
    resource_type: str,
    name: str,
    value: str,
    key: str,
    prefix: str | None = None,
    variable: str | None = None,
    plural_category: str | None = None,
) -> dict[str, Any]:
    return {
        "type": resource_type,
        "name": name,
        "value": value,
        "key": key,
        "prefix": prefix,
        "variable": variable,
        "plural_category": plural_category,
    }


def _resource_placeholders(resource: dict[str, Any]) -> list[str]:
    return extract_placeholders(str(resource.get("value", "")))


def _strings_key(name: str) -> str:
    return f"strings:{name}"


def _stringsdict_key(name: str, variable: str, plural_category: str) -> str:
    return f"stringsdict:{name}#{variable}.{plural_category}"


def _resource_label(resource: dict[str, Any]) -> str:
    if resource["type"] == "stringsdict_plural":
        return f"stringsdict {resource['name']}[{resource.get('variable')}.{resource.get('plural_category')}]"
    return f"strings {resource['name']}"


def _find_next_quoted_string(text: str, position: int) -> int | None:
    length = len(text)
    while position < length:
        if text.startswith("/*", position):
            end = text.find("*/", position + 2)
            if end == -1:
                raise ValueError("Unterminated block comment in .strings file")
            position = end + 2
            continue
        if text.startswith("//", position):
            end = text.find("\n", position + 2)
            if end == -1:
                return None
            position = end + 1
            continue
        if text[position] == '"':
            return position
        position += 1
    return None


def _skip_space_and_comments(text: str, position: int) -> int:
    length = len(text)
    while position < length:
        if text[position].isspace():
            position += 1
            continue
        if text.startswith("/*", position):
            end = text.find("*/", position + 2)
            if end == -1:
                raise ValueError("Unterminated block comment in .strings file")
            position = end + 2
            continue
        if text.startswith("//", position):
            end = text.find("\n", position + 2)
            if end == -1:
                return length
            position = end + 1
            continue
        return position
    return position


def _parse_quoted_string(text: str, position: int) -> tuple[str, int]:
    if position >= len(text) or text[position] != '"':
        raise ValueError("Expected quoted string")
    position += 1
    chars: list[str] = []
    while position < len(text):
        char = text[position]
        if char == '"':
            return "".join(chars), position + 1
        if char == "\\":
            position += 1
            if position >= len(text):
                raise ValueError("Unterminated escape sequence in .strings file")
            escaped = text[position]
            if escaped == "n":
                chars.append("\n")
            elif escaped == "r":
                chars.append("\r")
            elif escaped == "t":
                chars.append("\t")
            elif escaped in {'"', "\\"}:
                chars.append(escaped)
            elif escaped in {"u", "U"} and position + 4 < len(text):
                code = text[position + 1 : position + 5]
                try:
                    chars.append(chr(int(code, 16)))
                    position += 4
                except ValueError:
                    chars.append(escaped)
            else:
                chars.append(escaped)
        else:
            chars.append(char)
        position += 1
    raise ValueError("Unterminated quoted string in .strings file")


def _escape_strings_literal(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


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
