from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from . import PROTOCOL_VERSION
from .json_adapter import extract_placeholders, source_hash


TAG_RE = re.compile(r"</?([A-Za-z_][A-Za-z0-9_.:-]*)\b[^>]*?/?>")


def extract_segments(path: Path, source_locale: str, source_path: str | None = None) -> list[dict[str, Any]]:
    logical_path = source_path or path.as_posix()
    root = ET.parse(path).getroot()
    namespace = _namespace(root.tag)
    version = root.get("version", "1.2")
    segments: list[dict[str, Any]] = []
    for unit_id, source, target, context in _units(root, namespace, version):
        value = _inner_xml(source)
        digest = hashlib.sha256(unit_id.encode("utf-8")).hexdigest()[:20]
        public_context = {key: item for key, item in context.items() if key != "parent_element"}
        segment: dict[str, Any] = {
            "protocol_version": PROTOCOL_VERSION,
            "segment_id": f"xliff:{logical_path}#{digest}",
            "source": value,
            "source_locale": source_locale,
            "source_path": logical_path,
            "source_hash": source_hash(value),
            "context": {
                "content_type": "xliff_unit",
                "xliff_version": version,
                "unit_id": unit_id,
                **public_context,
            },
            "constraints": {
                "placeholders": extract_placeholders(value),
                "markup": _tag_signature(value),
            },
            "status": "new",
        }
        if target is not None and _inner_xml(target):
            segment["existing_target"] = _inner_xml(target)
        segments.append(segment)
    return segments


def rebuild(
    source_path: Path,
    translated_segments: list[dict[str, Any]],
    output: Path,
    target_locale: str | None = None,
) -> None:
    tree = ET.parse(source_path)
    root = tree.getroot()
    namespace = _namespace(root.tag)
    if namespace:
        ET.register_namespace("", namespace)
    version = root.get("version", "1.2")
    if target_locale:
        if version.startswith("2"):
            root.set("trgLang", target_locale)
        else:
            for file_element in root.findall(f".//{_qualified(namespace, 'file')}"):
                file_element.set("target-language", target_locale)
    translations = {
        str(segment.get("context", {}).get("unit_id")): str(segment["target"])
        for segment in translated_segments
        if "target" in segment and segment.get("context", {}).get("unit_id")
    }
    for unit_id, source, target, context in _units(root, namespace, version):
        if unit_id not in translations:
            continue
        parent = context["parent_element"]
        if target is None:
            target = ET.Element(_qualified(namespace, "target"))
            children = list(parent)
            source_index = children.index(source)
            parent.insert(source_index + 1, target)
        _set_inner_xml(target, translations[unit_id])
    output.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output, encoding="utf-8", xml_declaration=True)


def validate_pair(source_path: Path, target_path: Path) -> dict[str, Any]:
    try:
        source_root = ET.parse(source_path).getroot()
        target_root = ET.parse(target_path).getroot()
        source_ns, target_ns = _namespace(source_root.tag), _namespace(target_root.tag)
        source_units = _unit_map(source_root, source_ns, source_root.get("version", "1.2"))
        target_units = _unit_map(target_root, target_ns, target_root.get("version", "1.2"))
    except (OSError, ET.ParseError, ValueError) as exc:
        return _qa_result([_qa_item("parse", "blocking", str(exc), target_path)])
    items: list[dict[str, Any]] = []
    for unit_id in sorted(source_units.keys() - target_units.keys()):
        items.append(_qa_item("unit_coverage", "blocking", f"Missing XLIFF unit {unit_id}", target_path, unit_id))
    for unit_id in sorted(target_units.keys() - source_units.keys()):
        items.append(_qa_item("unit_coverage", "blocking", f"Unexpected XLIFF unit {unit_id}", target_path, unit_id))
    for unit_id in sorted(source_units.keys() & target_units.keys()):
        original_source, _original_target = source_units[unit_id]
        rebuilt_source, rebuilt_target = target_units[unit_id]
        if original_source != rebuilt_source:
            items.append(_qa_item("source_integrity", "blocking", f"Source content changed in XLIFF unit {unit_id}", target_path, unit_id))
        if rebuilt_target is None or not rebuilt_target:
            items.append(_qa_item("translation_coverage", "warning", f"XLIFF unit {unit_id} has no target", target_path, unit_id))
            continue
        if extract_placeholders(original_source) != extract_placeholders(rebuilt_target):
            items.append(_qa_item("placeholder_parity", "blocking", f"Placeholder mismatch in XLIFF unit {unit_id}", target_path, unit_id))
        if _tag_signature(original_source) != _tag_signature(rebuilt_target):
            items.append(_qa_item("inline_markup", "blocking", f"Inline tags changed in XLIFF unit {unit_id}", target_path, unit_id))
    return _qa_result(items)


def _units(root: ET.Element, namespace: str, version: str) -> list[tuple[str, ET.Element, ET.Element | None, dict[str, Any]]]:
    result: list[tuple[str, ET.Element, ET.Element | None, dict[str, Any]]] = []
    if version.startswith("2"):
        for unit in root.findall(f".//{_qualified(namespace, 'unit')}"):
            unit_id = unit.get("id")
            for index, segment in enumerate(unit.findall(f".//{_qualified(namespace, 'segment')}")):
                source = segment.find(_qualified(namespace, "source"))
                if source is None:
                    continue
                target = segment.find(_qualified(namespace, "target"))
                identity = f"{unit_id or 'unit'}:{segment.get('id') or index}"
                result.append((identity, source, target, {"parent_element": segment}))
    else:
        for index, unit in enumerate(root.findall(f".//{_qualified(namespace, 'trans-unit')}")):
            source = unit.find(_qualified(namespace, "source"))
            if source is None:
                continue
            target = unit.find(_qualified(namespace, "target"))
            result.append((unit.get("id") or str(index), source, target, {"parent_element": unit}))
    return result


def _unit_map(root: ET.Element, namespace: str, version: str) -> dict[str, tuple[str, str | None]]:
    return {
        unit_id: (_inner_xml(source), _inner_xml(target) if target is not None else None)
        for unit_id, source, target, _context in _units(root, namespace, version)
    }


def _inner_xml(element: ET.Element | None) -> str:
    if element is None:
        return ""
    parts = [escape(element.text or "")]
    for child in element:
        parts.append(ET.tostring(child, encoding="unicode"))
    return "".join(parts)


def _set_inner_xml(element: ET.Element, value: str) -> None:
    try:
        wrapper = ET.fromstring(f"<wrapper>{value}</wrapper>")
    except ET.ParseError as exc:
        raise ValueError(f"Translated XLIFF target is not valid inline XML: {exc}") from exc
    for child in list(element):
        element.remove(child)
    element.text = wrapper.text
    for child in list(wrapper):
        wrapper.remove(child)
        element.append(child)


def _namespace(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def _qualified(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}" if namespace else name


def _tag_signature(value: str) -> list[str]:
    return sorted(match.group(1).split(":")[-1] for match in TAG_RE.finditer(value))


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
