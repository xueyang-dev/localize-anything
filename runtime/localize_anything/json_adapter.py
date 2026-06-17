from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION


PLACEHOLDER_RE = re.compile(
    r"{{[^{}]+}}"
    r"|{[A-Za-z_][^{}]*}"
    r"|%\([^)]+\)[#0 +\-]*\d*(?:\.\d+)?[A-Za-z]"
    r"|%[#0 +\-]*\d*(?:\.\d+)?[A-Za-z]"
    r"|\$[A-Za-z_][A-Za-z0-9_.]*"
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_json(value: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_placeholders(text: str) -> list[str]:
    return sorted(set(PLACEHOLDER_RE.findall(text)))


def escape_pointer_part(part: str) -> str:
    return part.replace("~", "~0").replace("/", "~1")


def unescape_pointer_part(part: str) -> str:
    return part.replace("~1", "/").replace("~0", "~")


def iter_string_leaves(value: Any, pointer: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield pointer or "/", value
        return
    if isinstance(value, dict):
        for key, child in value.items():
            child_pointer = f"{pointer}/{escape_pointer_part(str(key))}"
            yield from iter_string_leaves(child, child_pointer)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_string_leaves(child, f"{pointer}/{index}")


def segment_id(source_path: str, pointer: str) -> str:
    return f"json:{source_path}#{pointer}"


def extract_segments(path: Path, source_locale: str, source_path: str | None = None) -> list[dict[str, Any]]:
    logical_path = source_path or path.as_posix()
    document = load_json(path)
    segments: list[dict[str, Any]] = []
    for pointer, text in iter_string_leaves(document):
        segments.append(
            {
                "protocol_version": PROTOCOL_VERSION,
                "segment_id": segment_id(logical_path, pointer),
                "source": text,
                "source_locale": source_locale,
                "source_path": logical_path,
                "source_hash": source_hash(text),
                "context": {"json_pointer": pointer, "content_type": "locale_string"},
                "constraints": {"placeholders": extract_placeholders(text), "markup": []},
                "status": "new",
            }
        )
    return segments


def pointer_parts(pointer: str) -> list[str]:
    if pointer == "/":
        return []
    if not pointer.startswith("/"):
        raise ValueError(f"Invalid JSON pointer: {pointer}")
    return [unescape_pointer_part(part) for part in pointer[1:].split("/")]


def set_pointer(document: Any, pointer: str, value: str) -> Any:
    if pointer == "/":
        return value
    current = document
    parts = pointer_parts(pointer)
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    final = parts[-1]
    if isinstance(current, list):
        current[int(final)] = value
    else:
        current[final] = value
    return document


def rebuild(path: Path, translated_segments: list[dict[str, Any]], output: Path) -> None:
    document = copy.deepcopy(load_json(path))
    for segment in translated_segments:
        if "target" not in segment:
            continue
        pointer = segment.get("context", {}).get("json_pointer")
        if not pointer:
            raise ValueError(f"Segment lacks context.json_pointer: {segment.get('segment_id', '<unknown>')}")
        document = set_pointer(document, pointer, segment["target"])
    dump_json(document, output)


def validate_pair(source_path: Path, target_path: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    try:
        source = dict(iter_string_leaves(load_json(source_path)))
    except (OSError, json.JSONDecodeError) as exc:
        return _failed_parse(source_path, str(exc))
    try:
        target = dict(iter_string_leaves(load_json(target_path)))
    except (OSError, json.JSONDecodeError) as exc:
        return _failed_parse(target_path, str(exc))

    missing = sorted(source.keys() - target.keys())
    extra = sorted(target.keys() - source.keys())
    for pointer in missing:
        items.append(_qa_item("key_coverage", "blocking", f"Missing target key at {pointer}", target_path, pointer))
    for pointer in extra:
        items.append(_qa_item("key_coverage", "blocking", f"Unexpected target key at {pointer}", target_path, pointer))

    for pointer in sorted(source.keys() & target.keys()):
        source_tokens = extract_placeholders(source[pointer])
        target_tokens = extract_placeholders(target[pointer])
        if source_tokens != target_tokens:
            items.append(
                _qa_item(
                    "placeholder_parity",
                    "blocking",
                    f"Placeholder mismatch at {pointer}: source={source_tokens}, target={target_tokens}",
                    target_path,
                    pointer,
                )
            )

    blocking = sum(item["severity"] == "blocking" for item in items)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "status": "fail" if blocking else "pass",
        "summary": {"blocking_count": blocking, "warning_count": 0},
        "items": items,
    }


def _failed_parse(path: Path, message: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "status": "fail",
        "summary": {"blocking_count": 1, "warning_count": 0},
        "items": [_qa_item("parse", "blocking", message, path)],
    }


def _qa_item(category: str, severity: str, message: str, path: Path, pointer: str | None = None) -> dict[str, Any]:
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
    if pointer:
        item["segment_id"] = pointer
    return item
