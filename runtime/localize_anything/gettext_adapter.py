from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .json_adapter import extract_placeholders, source_hash


FIELD_RE = re.compile(r'^(msgctxt|msgid_plural|msgid|msgstr(?:\[(\d+)\])?)\s+(".*")\s*$')
CONTINUATION_RE = re.compile(r'^(".*")\s*$')

PLURAL_FORMS = {
    "zh": "nplurals=1; plural=0;",
    "ja": "nplurals=1; plural=0;",
    "ko": "nplurals=1; plural=0;",
    "th": "nplurals=1; plural=0;",
    "vi": "nplurals=1; plural=0;",
    "en": "nplurals=2; plural=(n != 1);",
    "de": "nplurals=2; plural=(n != 1);",
    "es": "nplurals=2; plural=(n != 1);",
    "it": "nplurals=2; plural=(n != 1);",
    "pt": "nplurals=2; plural=(n != 1);",
    "fr": "nplurals=2; plural=(n > 1);",
    "ru": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);",
    "uk": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);",
    "ar": "nplurals=6; plural=(n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3 && n%100<=10 ? 3 : n%100>=11 && n%100<=99 ? 4 : 5);",
}


@dataclass(frozen=True)
class PoField:
    name: str
    plural_index: int | None
    start: int
    end: int
    value: str


@dataclass(frozen=True)
class PoEntry:
    start: int
    end: int
    fields: tuple[PoField, ...]
    flags: tuple[str, ...]
    occurrences: tuple[dict[str, Any], ...]
    comments: tuple[str, ...]

    def field(self, name: str) -> PoField | None:
        return next((field for field in self.fields if field.name == name), None)

    def msgstr_fields(self) -> list[PoField]:
        return [field for field in self.fields if field.name == "msgstr"]

    @property
    def msgid(self) -> str:
        field = self.field("msgid")
        return field.value if field else ""

    @property
    def msgctxt(self) -> str | None:
        field = self.field("msgctxt")
        return field.value if field else None

    @property
    def msgid_plural(self) -> str | None:
        field = self.field("msgid_plural")
        return field.value if field else None


@dataclass(frozen=True)
class PoDocument:
    lines: tuple[str, ...]
    entries: tuple[PoEntry, ...]
    newline: str


def parse_po(path: Path) -> PoDocument:
    return parse_po_text(path.read_text(encoding="utf-8"), path.as_posix())


def parse_po_text(text: str, label: str = "<memory>") -> PoDocument:
    lines = text.splitlines(keepends=True)
    if text and not lines:
        lines = [text]
    newline = "\r\n" if "\r\n" in text else "\n"
    entries: list[PoEntry] = []
    start = 0
    for index in range(len(lines) + 1):
        boundary = index == len(lines) or not lines[index].strip()
        if not boundary:
            continue
        if start < index:
            entry = _parse_entry(lines, start, index, label)
            if entry:
                entries.append(entry)
        start = index + 1
    return PoDocument(tuple(lines), tuple(entries), newline)


def extract_segments(path: Path, source_locale: str, source_path: str | None = None) -> list[dict[str, Any]]:
    logical_path = source_path or path.as_posix()
    document = parse_po(path)
    segments: list[dict[str, Any]] = []
    for entry in document.entries:
        if not entry.field("msgid") or entry.msgid == "":
            continue
        plural_indexes = sorted(
            field.plural_index for field in entry.msgstr_fields() if field.plural_index is not None
        )
        combined_source = "\0".join(part or "" for part in (entry.msgctxt, entry.msgid, entry.msgid_plural))
        placeholders = set(extract_placeholders(entry.msgid))
        if entry.msgid_plural:
            placeholders.update(extract_placeholders(entry.msgid_plural))
        segments.append(
            {
                "protocol_version": PROTOCOL_VERSION,
                "segment_id": _segment_id(logical_path, entry),
                "source": entry.msgid,
                "source_locale": source_locale,
                "source_path": logical_path,
                "source_hash": source_hash(combined_source),
                "context": {
                    "content_type": "gettext_message",
                    "msgctxt": entry.msgctxt,
                    "source_plural": entry.msgid_plural,
                    "plural_indexes": plural_indexes,
                    "flags": list(entry.flags),
                    "occurrences": list(entry.occurrences),
                    "comments": list(entry.comments),
                },
                "constraints": {
                    "placeholders": sorted(placeholders),
                    "markup": [],
                    "format_flags": [flag for flag in entry.flags if "format" in flag],
                },
                "status": "new",
            }
        )
    return segments


def rebuild(
    source_path: Path,
    translated_segments: list[dict[str, Any]],
    output: Path,
    target_locale: str | None = None,
) -> None:
    document = parse_po(source_path)
    logical_candidates = {str(item.get("source_path")) for item in translated_segments if item.get("source_path")}
    logical_path = next(iter(logical_candidates)) if len(logical_candidates) == 1 else source_path.as_posix()
    by_id = {str(segment.get("segment_id")): segment for segment in translated_segments}
    replacements: list[tuple[int, int, list[str]]] = []

    for entry in document.entries:
        if entry.msgid == "":
            if target_locale:
                header_fields = entry.msgstr_fields()
                if header_fields:
                    header = _updated_header(header_fields[0].value, target_locale)
                    replacements.append(
                        (header_fields[0].start, header_fields[0].end, [_render_field("msgstr", header, document.newline)])
                    )
            continue
        segment = by_id.get(_segment_id(logical_path, entry))
        if not segment:
            continue
        msgstr_fields = entry.msgstr_fields()
        if entry.msgid_plural:
            plural_values = _target_plural_values(segment)
            if "target_plural" in segment:
                rendered = [
                    _render_field(f"msgstr[{index}]", value, document.newline)
                    for index, value in sorted(plural_values.items())
                ]
                if msgstr_fields:
                    replacements.append((msgstr_fields[0].start, msgstr_fields[-1].end, rendered))
                else:
                    plural_field = entry.field("msgid_plural")
                    if plural_field:
                        replacements.append((plural_field.end, plural_field.end, rendered))
            elif 0 in plural_values:
                field = next((item for item in msgstr_fields if item.plural_index == 0), None)
                if field:
                    replacements.append(
                        (field.start, field.end, [_render_field("msgstr[0]", plural_values[0], document.newline)])
                    )
        elif "target" in segment:
            if not msgstr_fields:
                msgid_field = entry.field("msgid")
                if msgid_field:
                    replacements.append(
                        (msgid_field.end, msgid_field.end, [_render_field("msgstr", str(segment["target"]), document.newline)])
                    )
            else:
                replacements.append(
                    (msgstr_fields[0].start, msgstr_fields[0].end, [_render_field("msgstr", str(segment["target"]), document.newline)])
                )

    lines = list(document.lines)
    for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
        lines[start:end] = replacement
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(lines), encoding="utf-8", newline="")


def validate_pair(source_path: Path, target_path: Path) -> dict[str, Any]:
    try:
        source_document = parse_po(source_path)
    except (OSError, ValueError, SyntaxError) as exc:
        return _parse_failure(source_path, str(exc))
    try:
        target_document = parse_po(target_path)
    except (OSError, ValueError, SyntaxError) as exc:
        return _parse_failure(target_path, str(exc))

    items: list[dict[str, Any]] = []
    source_entries, source_duplicates = _entry_map(source_document)
    target_entries, target_duplicates = _entry_map(target_document)
    for key in source_duplicates:
        items.append(_qa_item("duplicate_entry", "blocking", f"Duplicate source entry: {_key_label(key)}", source_path))
    for key in target_duplicates:
        items.append(_qa_item("duplicate_entry", "blocking", f"Duplicate target entry: {_key_label(key)}", target_path))

    for key in sorted(source_entries.keys() - target_entries.keys(), key=str):
        items.append(_qa_item("entry_coverage", "blocking", f"Missing target entry: {_key_label(key)}", target_path))
    for key in sorted(target_entries.keys() - source_entries.keys(), key=str):
        items.append(_qa_item("entry_coverage", "blocking", f"Unexpected target entry: {_key_label(key)}", target_path))

    for key in sorted(source_entries.keys() & target_entries.keys(), key=str):
        source_entry = source_entries[key]
        target_entry = target_entries[key]
        source_tokens = set(extract_placeholders(source_entry.msgid))
        plural_tokens = source_tokens | set(extract_placeholders(source_entry.msgid_plural or source_entry.msgid))
        target_fields = target_entry.msgstr_fields()
        if not target_fields or all(not field.value for field in target_fields):
            items.append(_qa_item("translation_coverage", "warning", f"Untranslated entry: {_key_label(key)}", target_path))
        for field in target_fields:
            expected = plural_tokens if source_entry.msgid_plural else source_tokens
            actual = set(extract_placeholders(field.value))
            if field.value and expected != actual:
                items.append(
                    _qa_item(
                        "placeholder_parity",
                        "blocking",
                        f"Placeholder mismatch for {_key_label(key)}: source={sorted(expected)}, target={sorted(actual)}",
                        target_path,
                    )
                )

    header = next((entry for entry in target_document.entries if entry.field("msgid") and entry.msgid == ""), None)
    if not header or not header.msgstr_fields():
        items.append(_qa_item("header", "warning", "Target catalog has no gettext header", target_path))
    else:
        header_value = header.msgstr_fields()[0].value
        nplurals_match = re.search(r"^Plural-Forms:\s*nplurals=(\d+);", header_value, re.MULTILINE)
        if nplurals_match:
            expected_count = int(nplurals_match.group(1))
            for key, entry in target_entries.items():
                if entry.msgid_plural and len(entry.msgstr_fields()) != expected_count:
                    items.append(
                        _qa_item(
                            "plural_forms",
                            "blocking",
                            f"{_key_label(key)} has {len(entry.msgstr_fields())} plural forms; header requires {expected_count}",
                            target_path,
                        )
                    )
        else:
            items.append(_qa_item("plural_forms", "warning", "Target header does not declare Plural-Forms", target_path))

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


def _parse_entry(lines: list[str], start: int, end: int, label: str) -> PoEntry | None:
    if all(line.lstrip().startswith("#~") for line in lines[start:end] if line.strip()):
        return None
    fields: list[PoField] = []
    flags: list[str] = []
    occurrences: list[dict[str, Any]] = []
    comments: list[str] = []
    index = start
    while index < end:
        raw = lines[index].rstrip("\r\n")
        if raw.startswith("#,"):
            flags.extend(part.strip() for part in raw[2:].split(",") if part.strip())
        elif raw.startswith("#:"):
            occurrences.extend(_parse_occurrences(raw[2:].strip()))
        elif raw.startswith("#.") or raw.startswith("# "):
            comments.append(raw[2:].strip())
        match = FIELD_RE.match(raw)
        if not match:
            index += 1
            continue
        keyword, plural_index, quoted = match.groups()
        value_parts = [_decode_quoted(quoted, label, index + 1)]
        field_end = index + 1
        while field_end < end:
            continuation = CONTINUATION_RE.match(lines[field_end].rstrip("\r\n"))
            if not continuation:
                break
            value_parts.append(_decode_quoted(continuation.group(1), label, field_end + 1))
            field_end += 1
        name = "msgstr" if keyword.startswith("msgstr") else keyword
        fields.append(PoField(name, int(plural_index) if plural_index is not None else None, index, field_end, "".join(value_parts)))
        index = field_end
    if not any(field.name == "msgid" for field in fields):
        return None
    return PoEntry(start, end, tuple(fields), tuple(sorted(set(flags))), tuple(occurrences), tuple(comments))


def _decode_quoted(value: str, label: str, line_number: int) -> str:
    try:
        decoded = ast.literal_eval(value)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"Invalid PO string at {label}:{line_number}: {exc}") from exc
    if not isinstance(decoded, str):
        raise ValueError(f"Invalid PO string at {label}:{line_number}")
    return decoded


def _parse_occurrences(value: str) -> list[dict[str, Any]]:
    occurrences: list[dict[str, Any]] = []
    for token in value.split():
        path, separator, line = token.rpartition(":")
        if separator and line.isdigit():
            occurrences.append({"path": path, "line": int(line)})
        else:
            occurrences.append({"path": token})
    return occurrences


def _segment_id(logical_path: str, entry: PoEntry) -> str:
    identity = "\0".join(part or "" for part in (entry.msgctxt, entry.msgid, entry.msgid_plural))
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"po:{logical_path}#{digest}"


def _render_field(keyword: str, value: str, newline: str) -> str:
    return f"{keyword} {json.dumps(value, ensure_ascii=False)}{newline}"


def _target_plural_values(segment: dict[str, Any]) -> dict[int, str]:
    raw = segment.get("target_plural")
    if isinstance(raw, list):
        return {index: str(value) for index, value in enumerate(raw)}
    if isinstance(raw, dict):
        result: dict[int, str] = {}
        for key, value in raw.items():
            try:
                index = int(key)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid target_plural index {key!r}") from exc
            result[index] = str(value)
        return result
    if "target" in segment:
        return {0: str(segment["target"])}
    return {}


def _updated_header(header: str, target_locale: str) -> str:
    normalized = target_locale.replace("-", "_")
    lines = header.splitlines()
    updates = {"Language:": f"Language: {normalized}"}
    language = target_locale.split("-", 1)[0].lower()
    if language in PLURAL_FORMS:
        updates["Plural-Forms:"] = f"Plural-Forms: {PLURAL_FORMS[language]}"
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        key = next((prefix for prefix in updates if line.startswith(prefix)), None)
        if key:
            result.append(updates[key])
            seen.add(key)
        else:
            result.append(line)
    for key, value in updates.items():
        if key not in seen:
            result.append(value)
    return "\n".join(result) + ("\n" if header.endswith("\n") or result else "")


def _entry_map(document: PoDocument) -> tuple[dict[tuple[str | None, str, str | None], PoEntry], list[tuple[str | None, str, str | None]]]:
    result: dict[tuple[str | None, str, str | None], PoEntry] = {}
    duplicates: list[tuple[str | None, str, str | None]] = []
    for entry in document.entries:
        if not entry.field("msgid") or entry.msgid == "":
            continue
        key = (entry.msgctxt, entry.msgid, entry.msgid_plural)
        if key in result:
            duplicates.append(key)
        result[key] = entry
    return result, duplicates


def _key_label(key: tuple[str | None, str, str | None]) -> str:
    context, msgid, plural = key
    label = json.dumps(msgid, ensure_ascii=False)
    if context:
        label = f"{json.dumps(context, ensure_ascii=False)} / {label}"
    if plural:
        label += f" / plural {json.dumps(plural, ensure_ascii=False)}"
    return label


def _parse_failure(path: Path, message: str) -> dict[str, Any]:
    item = _qa_item("parse", "blocking", message, path)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "status": "fail",
        "summary": {"blocking_count": 1, "warning_count": 0},
        "items": [item],
    }


def _qa_item(category: str, severity: str, message: str, path: Path) -> dict[str, Any]:
    return {
        "channel": "adapter",
        "category": category,
        "severity": severity,
        "message": message,
        "path": path.as_posix(),
        "checked_by": "adapter",
        "coverage": "complete",
        "confidence": "deterministic",
    }
