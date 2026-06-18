from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .json_adapter import extract_placeholders, source_hash


TIMING_RE = re.compile(r"^\s*(\S+)\s+-->\s+(\S+)(.*)$")
SUBTITLE_TAG_RE = re.compile(r"</?[^>]+>|\{\\[^}]+}")


def extract_segments(path: Path, source_locale: str, source_path: str | None = None) -> list[dict[str, Any]]:
    logical_path = source_path or path.as_posix()
    format_name = "vtt" if path.suffix.lower() == ".vtt" else "srt"
    text = path.read_text(encoding="utf-8-sig")
    cues = _parse_cues(text, format_name)
    segments: list[dict[str, Any]] = []
    for cue in cues:
        identity = f"{cue['cue_id']}\0{cue['timing']}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
        value = cue["value"]
        segments.append(
            {
                "protocol_version": PROTOCOL_VERSION,
                "segment_id": f"{format_name}:{logical_path}#{digest}",
                "source": value,
                "source_locale": source_locale,
                "source_path": logical_path,
                "source_hash": source_hash(value),
                "context": {
                    "content_type": "subtitle_cue",
                    "subtitle_format": format_name,
                    **cue,
                },
                "constraints": {
                    "placeholders": extract_placeholders(value),
                    "markup": sorted(SUBTITLE_TAG_RE.findall(value)),
                    "timing": cue["timing"],
                },
                "status": "new",
            }
        )
    return segments


def rebuild(source_path: Path, translated_segments: list[dict[str, Any]], output: Path) -> None:
    text = source_path.read_text(encoding="utf-8-sig")
    edits: list[tuple[int, int, str]] = []
    for segment in translated_segments:
        if "target" not in segment:
            continue
        context = segment.get("context", {})
        start, end = context.get("char_start"), context.get("char_end")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start or end > len(text):
            raise ValueError(f"Invalid subtitle source span: {segment.get('segment_id')}")
        edits.append((start, end, str(segment["target"])))
    for start, end, value in sorted(edits, reverse=True):
        text = text[:start] + value + text[end:]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8", newline="")


def validate_pair(source_path: Path, target_path: Path) -> dict[str, Any]:
    format_name = "vtt" if source_path.suffix.lower() == ".vtt" else "srt"
    try:
        source = _parse_cues(source_path.read_text(encoding="utf-8-sig"), format_name)
        target = _parse_cues(target_path.read_text(encoding="utf-8-sig"), format_name)
    except (OSError, ValueError) as exc:
        return _qa_result([_qa_item("parse", "blocking", str(exc), target_path)])
    items: list[dict[str, Any]] = []
    if len(source) != len(target):
        items.append(_qa_item("cue_coverage", "blocking", f"Cue count changed: source={len(source)}, target={len(target)}", target_path))
    for index, (source_cue, target_cue) in enumerate(zip(source, target)):
        if (source_cue["cue_id"], source_cue["timing"]) != (target_cue["cue_id"], target_cue["timing"]):
            items.append(_qa_item("timing", "blocking", f"Cue identity or timing changed at cue {index + 1}", target_path))
        if extract_placeholders(source_cue["value"]) != extract_placeholders(target_cue["value"]):
            items.append(_qa_item("placeholder_parity", "blocking", f"Placeholder mismatch at cue {index + 1}", target_path))
        if sorted(SUBTITLE_TAG_RE.findall(source_cue["value"])) != sorted(SUBTITLE_TAG_RE.findall(target_cue["value"])):
            items.append(_qa_item("inline_markup", "blocking", f"Subtitle markup changed at cue {index + 1}", target_path))
    return _qa_result(items)


def _parse_cues(text: str, format_name: str) -> list[dict[str, Any]]:
    if format_name == "vtt" and not text.lstrip("\ufeff").startswith("WEBVTT"):
        raise ValueError("WebVTT file must start with WEBVTT")
    cues: list[dict[str, Any]] = []
    offset = 0
    for block in re.split(r"(?:\r?\n){2,}", text):
        block_start = text.find(block, offset)
        offset = block_start + len(block)
        lines = block.splitlines(keepends=True)
        plain = [line.rstrip("\r\n") for line in lines]
        if not plain or (format_name == "vtt" and plain[0].lstrip("\ufeff").startswith("WEBVTT")):
            continue
        if format_name == "vtt" and plain[0].startswith(("NOTE", "STYLE", "REGION")):
            continue
        timing_index = next((index for index, line in enumerate(plain) if TIMING_RE.match(line)), None)
        if timing_index is None:
            continue
        text_index = timing_index + 1
        if text_index >= len(lines):
            raise ValueError(f"Subtitle cue lacks text after timing {plain[timing_index]!r}")
        relative_start = sum(len(line) for line in lines[:text_index])
        value = "".join(lines[text_index:]).rstrip("\r\n")
        start = block_start + relative_start
        end = start + len(value)
        cue_id = plain[timing_index - 1] if timing_index > 0 else str(len(cues) + 1)
        cues.append(
            {
                "cue_id": cue_id,
                "timing": plain[timing_index],
                "char_start": start,
                "char_end": end,
                "value": value,
            }
        )
    return cues


def _qa_result(items: list[dict[str, Any]]) -> dict[str, Any]:
    blocking = sum(item["severity"] == "blocking" for item in items)
    warnings = sum(item["severity"] == "warning" for item in items)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "status": "fail" if blocking else "pass_with_warnings" if warnings else "pass",
        "summary": {"blocking_count": blocking, "warning_count": warnings},
        "items": items,
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
