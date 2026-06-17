from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .json_adapter import source_hash


OPEN_TAG_RE = re.compile(r"^\s*\[([A-Za-z0-9_+-]+)]\s*$")
CLOSE_TAG_RE = re.compile(r"^\s*\[/([A-Za-z0-9_+-]+)]\s*$")
ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$")


@dataclass(frozen=True)
class WmlString:
    value: str
    line: int
    index: int


def inventory(project_root: Path) -> dict[str, Any]:
    cfg_files = sorted(path for path in project_root.rglob("*.cfg") if ".git" not in path.parts)
    po_files = sorted(path for path in project_root.rglob("*.po") if ".git" not in path.parts)
    pot_files = sorted(path for path in project_root.rglob("*.pot") if ".git" not in path.parts)
    scenario_files = [path for path in cfg_files if "scenarios" in {part.lower() for part in path.parts}]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "adapter": "scenario.wesnoth",
        "project_root": project_root.resolve().as_posix(),
        "campaign_main_files": [_relative(path, project_root) for path in cfg_files if path.name == "_main.cfg"],
        "scenario_files": [_relative(path, project_root) for path in scenario_files],
        "other_wml_files": [_relative(path, project_root) for path in cfg_files if path not in scenario_files],
        "po_files": [_relative(path, project_root) for path in po_files],
        "pot_files": [_relative(path, project_root) for path in pot_files],
    }


def extract_segments(project_root: Path, source_locale: str = "en-US") -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    cfg_files = sorted(path for path in project_root.rglob("*.cfg") if ".git" not in path.parts)
    context_indexes: dict[Path, dict[int, dict[str, str]]] = {}
    for path in cfg_files:
        relative = _relative(path, project_root)
        text = path.read_text(encoding="utf-8")
        strings = _extract_translatable_strings(text)
        if not strings:
            continue
        context_indexes[path] = _wml_line_context(path)
        for item in strings:
            context = _nearest_context(context_indexes[path], item.line) or {
                "campaign": project_root.name,
                "content_unit": f"wesnoth:{path.stem}",
                "content_type": "game_text",
            }
            context = {**context, "occurrences": [{"path": relative, "line": item.line}]}
            segments.append(
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "segment_id": _wml_segment_id(relative, item),
                    "source": item.value,
                    "source_locale": source_locale,
                    "source_path": relative,
                    "source_hash": source_hash(item.value),
                    "context": context,
                    "constraints": {"placeholders": _wml_placeholders(item.value), "markup": []},
                    "status": "new",
                }
            )
    return segments


def enrich_segments(segments: list[dict[str, Any]], project_root: Path) -> list[dict[str, Any]]:
    indexes: dict[str, dict[int, dict[str, str]]] = {}
    enriched: list[dict[str, Any]] = []
    for segment in segments:
        copied = {**segment, "context": dict(segment.get("context", {}))}
        occurrences = copied["context"].get("occurrences", [])
        matches: list[dict[str, str]] = []
        for occurrence in occurrences if isinstance(occurrences, list) else []:
            if not isinstance(occurrence, dict) or not occurrence.get("path"):
                continue
            relative = str(occurrence["path"]).replace("\\", "/")
            candidate = project_root / relative
            if not candidate.exists() or candidate.suffix.lower() != ".cfg":
                continue
            if relative not in indexes:
                indexes[relative] = _wml_line_context(candidate)
            line_number = occurrence.get("line")
            if isinstance(line_number, int):
                context = _nearest_context(indexes[relative], line_number)
                if context:
                    matches.append(context)
        if matches:
            best = matches[0]
            for key in ("campaign", "scenario", "speaker", "wml_key"):
                if best.get(key) and not copied["context"].get(key):
                    copied["context"][key] = best[key]
            for key in ("content_unit", "content_type"):
                if best.get(key):
                    copied["context"][key] = best[key]
            copied["context"]["wesnoth_occurrence_context"] = matches
        enriched.append(copied)
    return enriched


def validate_source(project_root: Path, segments: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    enriched = enrich_segments(segments, project_root)
    for before, after in zip(segments, enriched, strict=True):
        occurrences = before.get("context", {}).get("occurrences", [])
        cfg_occurrences = [
            item for item in occurrences if isinstance(item, dict) and str(item.get("path", "")).endswith(".cfg")
        ]
        if cfg_occurrences and not after.get("context", {}).get("wesnoth_occurrence_context"):
            items.append(
                {
                    "channel": "adapter",
                    "category": "source_context",
                    "severity": "warning",
                    "message": "Could not resolve WML context for gettext occurrence",
                    "segment_id": before.get("segment_id"),
                    "checked_by": "adapter",
                    "coverage": "complete",
                    "confidence": "deterministic",
                }
            )
    warnings = len(items)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "status": "pass_with_warnings" if warnings else "pass",
        "summary": {"blocking_count": 0, "warning_count": warnings},
        "items": items,
    }


def _wml_line_context(path: Path) -> dict[int, dict[str, str]]:
    stack: list[dict[str, str]] = []
    result: dict[int, dict[str, str]] = {}
    campaign = path.parts[-3] if len(path.parts) >= 3 and path.parent.name.lower() == "scenarios" else path.parent.name
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.split("#", 1)[0].strip()
        close = CLOSE_TAG_RE.match(stripped)
        if close:
            tag = close.group(1).lower()
            for index in range(len(stack) - 1, -1, -1):
                if stack[index].get("tag") == tag:
                    del stack[index:]
                    break
            continue
        opened = OPEN_TAG_RE.match(stripped)
        if opened:
            stack.append({"tag": opened.group(1).lower()})
            continue
        assignment = ASSIGNMENT_RE.match(stripped)
        key = "macro_argument"
        if assignment:
            key, raw_value = assignment.groups()
            value = _strip_wml_value(raw_value)
            if stack and key in {"id", "name", "speaker"}:
                stack[-1][key] = value
        elif "_\"" not in stripped and '_ "' not in stripped:
            continue
        context: dict[str, str] = {"campaign": campaign, "wml_key": key}
        scenario = next((item for item in reversed(stack) if item.get("tag") in {"scenario", "multiplayer"}), None)
        message = next((item for item in reversed(stack) if item.get("tag") == "message"), None)
        if scenario:
            context["scenario"] = scenario.get("id") or scenario.get("name") or path.stem
        elif "scenarios" in {part.lower() for part in path.parts}:
            context["scenario"] = path.stem
        if message and message.get("speaker"):
            context["speaker"] = message["speaker"]
        context["content_unit"] = f"wesnoth:{context.get('scenario', path.stem)}"
        context["content_type"] = "dialogue" if message or key == "message" else "game_text"
        result[number] = context
    return result


def _nearest_context(index: dict[int, dict[str, str]], line_number: int) -> dict[str, str] | None:
    if line_number in index:
        return index[line_number]
    candidates = [line for line in index if abs(line - line_number) <= 5]
    if not candidates:
        return None
    nearest = min(candidates, key=lambda line: abs(line - line_number))
    return index[nearest]


def _strip_wml_value(value: str) -> str:
    value = value.strip()
    if value.startswith("_"):
        value = value[1:].strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = value[1:-1]
    return value


def _extract_translatable_strings(text: str) -> list[WmlString]:
    strings: list[WmlString] = []
    index = 0
    while index < len(text):
        found = text.find("_", index)
        if found < 0:
            break
        before = text[found - 1] if found else ""
        if before and (before.isalnum() or before == "_"):
            index = found + 1
            continue
        cursor = found + 1
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor >= len(text) or text[cursor] != '"':
            index = found + 1
            continue
        parsed, end = _parse_wml_quoted_string(text, cursor)
        if parsed is not None:
            line = text.count("\n", 0, found) + 1
            strings.append(WmlString(parsed, line, len(strings)))
            index = end
        else:
            index = found + 1
    return strings


def _parse_wml_quoted_string(text: str, start: int) -> tuple[str | None, int]:
    value: list[str] = []
    escaped = False
    cursor = start + 1
    while cursor < len(text):
        char = text[cursor]
        if escaped:
            value.append({"n": "\n", "t": "\t", "r": "\r"}.get(char, char))
            escaped = False
            cursor += 1
            continue
        if char == "\\":
            escaped = True
            cursor += 1
            continue
        if char == '"':
            return "".join(value), cursor + 1
        value.append(char)
        cursor += 1
    return None, cursor


def _wml_segment_id(relative_path: str, item: WmlString) -> str:
    digest = source_hash(f"{relative_path}\0{item.line}\0{item.index}\0{item.value}")[:20]
    return f"wml:{relative_path}#{digest}"


def _wml_placeholders(text: str) -> list[str]:
    return sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_.]*", text)))


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
