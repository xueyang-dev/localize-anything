from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # The YAML adapter declares this optional dependency.
    yaml = None

from . import PROTOCOL_VERSION
from .json_adapter import extract_placeholders, source_hash


YAML_KEY_RE = re.compile(r"^(\s*)([^#][^:]*?):(?:\s*)(.*?)(\r?\n)?$")
TOML_VALUE_RE = re.compile(r"^(\s*)([A-Za-z0-9_.\-\"']+)\s*=\s*(.*?)(\r?\n)?$")
TOML_SECTION_RE = re.compile(r"^\s*\[([^\]]+)]\s*(?:#.*)?$")
PLAIN_NON_STRINGS = re.compile(
    r"^(?:null|~|true|false|yes|no|on|off|[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|0x[0-9a-f]+)$",
    re.IGNORECASE,
)


def extract_segments(
    path: Path,
    source_locale: str,
    source_path: str | None = None,
    format_name: str | None = None,
) -> list[dict[str, Any]]:
    format_name = _format(path, format_name)
    logical_path = source_path or path.as_posix()
    text = path.read_text(encoding="utf-8")
    spans = _yaml_spans(text) if format_name == "yaml" else _toml_spans(text)
    return [_segment(logical_path, source_locale, format_name, span) for span in spans]


def rebuild(
    source_path: Path,
    translated_segments: list[dict[str, Any]],
    output: Path,
    format_name: str | None = None,
) -> None:
    format_name = _format(source_path, format_name)
    lines = source_path.read_text(encoding="utf-8").splitlines(keepends=True)
    replacements: dict[int, list[tuple[int, int, str]]] = {}
    for segment in translated_segments:
        if "target" not in segment:
            continue
        context = segment.get("context", {})
        if context.get("structured_format") != format_name:
            continue
        line_index = context.get("line_index")
        start = context.get("value_start")
        end = context.get("value_end")
        if not all(isinstance(item, int) for item in (line_index, start, end)):
            raise ValueError(f"Segment lacks structured source span: {segment.get('segment_id')}")
        encoded = _encode_scalar(str(segment["target"]), str(context.get("scalar_style", "double")), format_name)
        replacements.setdefault(line_index, []).append((start, end, encoded))
    for line_index, edits in replacements.items():
        if line_index < 0 or line_index >= len(lines):
            raise ValueError(f"Structured source span is outside the file: line {line_index + 1}")
        line = lines[line_index]
        for start, end, value in sorted(edits, reverse=True):
            line = line[:start] + value + line[end:]
        lines[line_index] = line
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(lines), encoding="utf-8", newline="")


def validate_pair(source_path: Path, target_path: Path, format_name: str | None = None) -> dict[str, Any]:
    format_name = _format(source_path, format_name)
    try:
        source_text = source_path.read_text(encoding="utf-8")
        target_text = target_path.read_text(encoding="utf-8")
        _parse_document(source_text, format_name)
        _parse_document(target_text, format_name)
        source = {item["pointer"]: item["value"] for item in _spans(source_text, format_name)}
        target = {item["pointer"]: item["value"] for item in _spans(target_text, format_name)}
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return _qa_result([_qa_item("parse", "blocking", str(exc), target_path)])
    items: list[dict[str, Any]] = []
    for pointer in sorted(source.keys() - target.keys()):
        items.append(_qa_item("key_coverage", "blocking", f"Missing localized value at {pointer}", target_path, pointer))
    for pointer in sorted(target.keys() - source.keys()):
        items.append(_qa_item("key_coverage", "blocking", f"Unexpected localized value at {pointer}", target_path, pointer))
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
    return _qa_result(items)


def _format(path: Path, format_name: str | None) -> str:
    if format_name:
        normalized = format_name.lower()
    else:
        normalized = path.suffix.lower().lstrip(".")
    if normalized in {"yml", "yaml"}:
        return "yaml"
    if normalized == "toml":
        return "toml"
    raise ValueError(f"Unsupported structured format: {normalized}")


def _parse_document(text: str, format_name: str) -> Any:
    if format_name == "yaml":
        if yaml is None:
            return _yaml_spans(text)
        try:
            return yaml.safe_load(text)
        except Exception as exc:
            raise ValueError(f"Invalid YAML: {exc}") from exc
    return tomllib.loads(text)


def _spans(text: str, format_name: str) -> list[dict[str, Any]]:
    return _yaml_spans(text) if format_name == "yaml" else _toml_spans(text)


def _yaml_spans(text: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    stack: list[tuple[int, str]] = []
    sequence_counts: dict[tuple[int, tuple[str, ...]], int] = {}
    for line_index, line in enumerate(text.splitlines(keepends=True)):
        raw = line.rstrip("\r\n")
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = YAML_KEY_RE.match(line)
        if match:
            indent_text, raw_key, raw_value, _newline = match.groups()
            indent = len(indent_text.replace("\t", "    "))
            while stack and stack[-1][0] >= indent:
                stack.pop()
            key = _yaml_key(raw_key.strip())
            value_part, comment = _split_comment(raw_value)
            if not value_part.strip():
                stack.append((indent, key))
                continue
            decoded = _decode_scalar(value_part.strip(), "yaml")
            if decoded is None:
                continue
            value, style = decoded
            leading = len(raw_value) - len(raw_value.lstrip())
            start = match.start(3) + leading
            end = start + len(value_part.strip())
            pointer = "/" + "/".join([item[1] for item in stack] + [key])
            spans.append(_span(pointer, value, style, line_index, start, end, comment))
            continue
        stripped = raw.lstrip()
        if stripped.startswith("- "):
            indent = len(raw) - len(stripped)
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = tuple(item[1] for item in stack)
            counter_key = (indent, parent)
            index = sequence_counts.get(counter_key, 0)
            sequence_counts[counter_key] = index + 1
            raw_value = stripped[2:]
            value_part, comment = _split_comment(raw_value)
            decoded = _decode_scalar(value_part.strip(), "yaml")
            if decoded is None:
                continue
            value, style = decoded
            start = len(raw) - len(stripped) + 2 + len(raw_value) - len(raw_value.lstrip())
            end = start + len(value_part.strip())
            pointer = "/" + "/".join([*parent, str(index)])
            spans.append(_span(pointer, value, style, line_index, start, end, comment))
    return spans


def _toml_spans(text: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    section: list[str] = []
    for line_index, line in enumerate(text.splitlines(keepends=True)):
        raw = line.rstrip("\r\n")
        section_match = TOML_SECTION_RE.match(raw)
        if section_match:
            section = [_strip_quotes(part.strip()) for part in section_match.group(1).split(".")]
            continue
        match = TOML_VALUE_RE.match(line)
        if not match:
            continue
        _indent, raw_key, raw_value, _newline = match.groups()
        value_part, comment = _split_comment(raw_value)
        decoded = _decode_scalar(value_part.strip(), "toml")
        if decoded is None:
            continue
        value, style = decoded
        leading = len(raw_value) - len(raw_value.lstrip())
        start = match.start(3) + leading
        end = start + len(value_part.strip())
        key_parts = [_strip_quotes(part.strip()) for part in raw_key.split(".")]
        pointer = "/" + "/".join([*section, *key_parts])
        spans.append(_span(pointer, value, style, line_index, start, end, comment))
    return spans


def _span(pointer: str, value: str, style: str, line: int, start: int, end: int, comment: str) -> dict[str, Any]:
    return {
        "pointer": pointer,
        "value": value,
        "style": style,
        "line_index": line,
        "value_start": start,
        "value_end": end,
        "comment": comment,
    }


def _segment(logical_path: str, locale: str, format_name: str, span: dict[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(span["pointer"].encode("utf-8")).hexdigest()[:20]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "segment_id": f"{format_name}:{logical_path}#{digest}",
        "source": span["value"],
        "source_locale": locale,
        "source_path": logical_path,
        "source_hash": source_hash(span["value"]),
        "context": {
            "content_type": "locale_string",
            "structured_format": format_name,
            "pointer": span["pointer"],
            "line_index": span["line_index"],
            "value_start": span["value_start"],
            "value_end": span["value_end"],
            "scalar_style": span["style"],
            "comment": span["comment"],
        },
        "constraints": {"placeholders": extract_placeholders(span["value"]), "markup": []},
        "status": "new",
    }


def _decode_scalar(value: str, format_name: str) -> tuple[str, str] | None:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return json.loads(value), "double"
        except json.JSONDecodeError:
            if format_name == "yaml" and yaml is not None:
                loaded = yaml.safe_load(value)
                return (loaded, "double") if isinstance(loaded, str) else None
            return None
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'"), "single"
    if format_name == "toml" or PLAIN_NON_STRINGS.match(value) or value.startswith(("[", "{", "&", "*", "!", "|", ">")):
        return None
    return value, "plain"


def _encode_scalar(value: str, style: str, format_name: str) -> str:
    if style == "single":
        if format_name == "toml" and "'" in value:
            return json.dumps(value, ensure_ascii=False)
        return "'" + value.replace("'", "''") + "'"
    if style == "plain" and value and not PLAIN_NON_STRINGS.match(value) and not any(char in value for char in "#:\n\r[]{}"):
        return value
    return json.dumps(value, ensure_ascii=False)


def _split_comment(value: str) -> tuple[str, str]:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if char in {'"', "'"}:
            quote = None if quote == char else char if quote is None else quote
            continue
        if char == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip(), value[index:]
    return value.rstrip(), ""


def _yaml_key(value: str) -> str:
    return _strip_quotes(value).replace("~", "~0").replace("/", "~1")


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _qa_result(items: list[dict[str, Any]]) -> dict[str, Any]:
    blocking = sum(item["severity"] == "blocking" for item in items)
    warnings = sum(item["severity"] == "warning" for item in items)
    status = "fail" if blocking else "pass_with_warnings" if warnings else "pass"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": status,
        "summary": {"blocking_count": blocking, "warning_count": warnings},
        "items": items,
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
