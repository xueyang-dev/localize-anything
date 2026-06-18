from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .json_adapter import extract_placeholders, source_hash


HTML_TOKEN_RE = re.compile(r"<!--[\s\S]*?-->|<![^>]*>|<[^>]+>")
TAG_NAME_RE = re.compile(r"</?\s*([A-Za-z][A-Za-z0-9:-]*)")
MARKDOWN_PREFIX_RE = re.compile(r"^(\s*(?:(?:#{1,6}|>|[-+*]|\d+\.)\s+|\|\s*)?)(.*)$")
MARKUP_RE = re.compile(r"`+[^`]+`+|&[A-Za-z0-9#]+;|</?[A-Za-z][^>]*>")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
SKIP_HTML_TAGS = {"script", "style", "code", "pre", "svg"}


def extract_segments(path: Path, source_locale: str, source_path: str | None = None) -> list[dict[str, Any]]:
    logical_path = source_path or path.as_posix()
    text = path.read_text(encoding="utf-8")
    format_name = "html" if path.suffix.lower() in {".html", ".htm"} else "markdown"
    spans = _html_spans(text) if format_name == "html" else _markdown_spans(text)
    segments: list[dict[str, Any]] = []
    for index, span in enumerate(spans):
        coordinate = span["coordinate"]
        digest = hashlib.sha256(coordinate.encode("utf-8")).hexdigest()[:20]
        value = span["value"]
        segments.append(
            {
                "protocol_version": PROTOCOL_VERSION,
                "segment_id": f"{format_name}:{logical_path}#{digest}",
                "source": value,
                "source_locale": source_locale,
                "source_path": logical_path,
                "source_hash": source_hash(value),
                "context": {
                    "content_type": "document_text",
                    "markup_format": format_name,
                    "node_index": index,
                    **span,
                },
                "constraints": {
                    "placeholders": extract_placeholders(value),
                    "markup": _markup_tokens(value),
                },
                "status": "new",
            }
        )
    return segments


def rebuild(source_path: Path, translated_segments: list[dict[str, Any]], output: Path) -> None:
    text = source_path.read_text(encoding="utf-8")
    edits: list[tuple[int, int, str]] = []
    for segment in translated_segments:
        if "target" not in segment:
            continue
        context = segment.get("context", {})
        start, end = context.get("char_start"), context.get("char_end")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start or end > len(text):
            raise ValueError(f"Invalid markup source span: {segment.get('segment_id')}")
        edits.append((start, end, str(segment["target"])))
    for start, end, value in sorted(edits, reverse=True):
        text = text[:start] + value + text[end:]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8", newline="")


def validate_pair(source_path: Path, target_path: Path) -> dict[str, Any]:
    format_name = "html" if source_path.suffix.lower() in {".html", ".htm"} else "markdown"
    try:
        source_text = source_path.read_text(encoding="utf-8")
        target_text = target_path.read_text(encoding="utf-8")
        source_spans = _html_spans(source_text) if format_name == "html" else _markdown_spans(source_text)
        target_spans = _html_spans(target_text) if format_name == "html" else _markdown_spans(target_text)
    except OSError as exc:
        return _qa_result([_qa_item("parse", "blocking", str(exc), target_path)])
    items: list[dict[str, Any]] = []
    source_structure = _html_structure(source_text) if format_name == "html" else _markdown_structure(source_text)
    target_structure = _html_structure(target_text) if format_name == "html" else _markdown_structure(target_text)
    if source_structure != target_structure:
        items.append(_qa_item("markup_structure", "blocking", f"{format_name} structural tokens changed", target_path))
    if len(source_spans) != len(target_spans):
        items.append(
            _qa_item(
                "text_node_coverage",
                "blocking",
                f"Text node count changed: source={len(source_spans)}, target={len(target_spans)}",
                target_path,
            )
        )
    for index, (source, target) in enumerate(zip(source_spans, target_spans)):
        source_tokens = extract_placeholders(source["value"])
        target_tokens = extract_placeholders(target["value"])
        if source_tokens != target_tokens:
            items.append(
                _qa_item(
                    "placeholder_parity",
                    "blocking",
                    f"Placeholder mismatch in text node {index}: source={source_tokens}, target={target_tokens}",
                    target_path,
                )
            )
        if _markup_tokens(source["value"]) != _markup_tokens(target["value"]):
            items.append(_qa_item("inline_markup", "blocking", f"Inline markup changed in text node {index}", target_path))
    return _qa_result(items)


def _markdown_spans(text: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    offset = 0
    fenced = False
    section = "document"
    for line_index, line in enumerate(text.splitlines(keepends=True)):
        raw = line.rstrip("\r\n")
        stripped = raw.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fenced = not fenced
            offset += len(line)
            continue
        if fenced or not stripped or raw.startswith("    ") or re.match(r"^\s*(?:---+|\*\*\*+|___+)\s*$", raw):
            offset += len(line)
            continue
        if re.match(r"^\s*\[[^]]+]:\s+\S+", raw) or re.match(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$", raw):
            offset += len(line)
            continue
        match = MARKDOWN_PREFIX_RE.match(raw)
        if not match:
            offset += len(line)
            continue
        prefix, value = match.groups()
        if not value.strip():
            offset += len(line)
            continue
        leading = len(value) - len(value.lstrip())
        trailing = len(value) - len(value.rstrip())
        start = offset + len(prefix) + leading
        end = offset + len(raw) - trailing
        clean = text[start:end]
        if prefix.lstrip().startswith("#"):
            section = re.sub(r"[`*_]", "", clean).strip()
        spans.append(
            {
                "coordinate": f"line:{line_index + 1}",
                "char_start": start,
                "char_end": end,
                "value": clean,
                "line": line_index + 1,
                "section": section,
            }
        )
        offset += len(line)
    return spans


def _html_spans(text: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    stack: list[str] = []
    position = 0
    node_index = 0
    for match in HTML_TOKEN_RE.finditer(text):
        if match.start() > position and not any(tag in SKIP_HTML_TAGS for tag in stack):
            raw = text[position : match.start()]
            leading = len(raw) - len(raw.lstrip())
            trailing = len(raw) - len(raw.rstrip())
            if raw.strip():
                start = position + leading
                end = match.start() - trailing
                spans.append(
                    {
                        "coordinate": f"text:{node_index}",
                        "char_start": start,
                        "char_end": end,
                        "value": text[start:end],
                        "parent_tag": stack[-1] if stack else None,
                    }
                )
                node_index += 1
        token = match.group(0)
        tag_match = TAG_NAME_RE.match(token)
        if tag_match and not token.startswith(("<!--", "<!")):
            tag = tag_match.group(1).lower()
            if token.startswith("</"):
                for index in range(len(stack) - 1, -1, -1):
                    if stack[index] == tag:
                        del stack[index:]
                        break
            elif not token.rstrip().endswith("/>") and tag not in {"br", "hr", "img", "input", "meta", "link"}:
                stack.append(tag)
        position = match.end()
    if position < len(text) and not any(tag in SKIP_HTML_TAGS for tag in stack) and text[position:].strip():
        raw = text[position:]
        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw) - len(raw.rstrip())
        start, end = position + leading, len(text) - trailing
        spans.append(
            {
                "coordinate": f"text:{node_index}",
                "char_start": start,
                "char_end": end,
                "value": text[start:end],
                "parent_tag": stack[-1] if stack else None,
            }
        )
    return spans


def _markup_tokens(value: str) -> list[str]:
    tokens = MARKUP_RE.findall(value)
    tokens.extend(f"link:{match.group(1)}" for match in MARKDOWN_LINK_RE.finditer(value))
    return sorted(tokens)


def _html_structure(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", token.strip()) for token in HTML_TOKEN_RE.findall(text)]


def _markdown_structure(text: str) -> dict[str, Any]:
    return {
        "fences": [line.strip()[:3] for line in text.splitlines() if line.strip().startswith(("```", "~~~"))],
        "reference_links": [line.strip() for line in text.splitlines() if re.match(r"^\s*\[[^]]+]:\s+\S+", line)],
    }


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
