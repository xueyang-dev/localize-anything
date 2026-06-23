from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from . import PROTOCOL_VERSION
from .json_adapter import extract_placeholders, source_hash


SUPPORTED_EXTENSIONS = {".docx", ".dotx", ".docm", ".dotm"}
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

W_P = f"{{{W_NS}}}p"
A_P = f"{{{A_NS}}}p"
W_R = f"{{{W_NS}}}r"
A_R = f"{{{A_NS}}}r"
W_RPR = f"{{{W_NS}}}rPr"
A_RPR = f"{{{A_NS}}}rPr"
W_PPR = f"{{{W_NS}}}pPr"
A_PPR = f"{{{A_NS}}}pPr"
W_RFONTS = f"{{{W_NS}}}rFonts"
A_LATIN = f"{{{A_NS}}}latin"
A_EA = f"{{{A_NS}}}ea"
A_CS = f"{{{A_NS}}}cs"
TEXT_TAGS = {f"{{{W_NS}}}t", f"{{{A_NS}}}t"}
FONT_TAGS = {W_RFONTS, A_LATIN, A_EA, A_CS}
PROPERTY_TAGS = {W_RPR, A_RPR}
PARAGRAPH_TAGS = {W_P, A_P}
VBA_PROJECT = "word/vbaProject.bin"
LATIN_FONT_LANGUAGES = {
    "en",
    "es",
    "fr",
    "de",
    "it",
    "pt",
    "nl",
    "sv",
    "no",
    "da",
    "fi",
    "pl",
    "cs",
    "sk",
    "sl",
    "hr",
    "ro",
    "hu",
    "tr",
    "id",
    "ms",
    "vi",
}
FONT_BY_LANGUAGE = {
    "ar": "Arial",
    "bg": "Arial",
    "el": "Arial",
    "he": "Arial",
    "hi": "Nirmala UI",
    "ja": "Yu Gothic",
    "ko": "Malgun Gothic",
    "ru": "Arial",
    "th": "Tahoma",
    "uk": "Arial",
    "ur": "Nirmala UI",
}
INDIC_FONT_LANGUAGES = {"bn", "gu", "kn", "ml", "mr", "pa", "ta", "te"}

for prefix, uri in {
    "w": W_NS,
    "a": A_NS,
    "c": C_NS,
    "r": R_NS,
}.items():
    ET.register_namespace(prefix, uri)


def extract_segments(path: Path, source_locale: str, source_path: str | None = None) -> list[dict[str, Any]]:
    logical_path = source_path or path.as_posix()
    _ensure_supported_word_package(path)
    segments: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for part_name in _editable_part_names(archive):
            part_kind = _part_kind(part_name)
            if part_kind is None:
                continue
            root = ET.fromstring(archive.read(part_name))
            for group in _text_groups(root, part_name, part_kind):
                value = group["source"]
                coordinate = group["coordinate"]
                digest = hashlib.sha256(coordinate.encode("utf-8")).hexdigest()[:20]
                segments.append(
                    {
                        "protocol_version": PROTOCOL_VERSION,
                        "evidence_channels": ["adapter"],
                        "segment_id": f"word:{logical_path}#{digest}",
                        "source": value,
                        "source_locale": source_locale,
                        "source_path": logical_path,
                        "source_hash": source_hash(value),
                        "context": {
                            "content_type": "word_document_text",
                            "word_format": path.suffix.lower().lstrip("."),
                            "part_name": part_name,
                            "part_kind": part_kind,
                            "coordinate": coordinate,
                            "paragraph_index": group["paragraph_index"],
                            "group_index": group["group_index"],
                            "text_node_count": group["text_node_count"],
                            "style_signature": group["style_signature"],
                            "paragraph_preview": group["paragraph_preview"],
                        },
                        "constraints": {"placeholders": extract_placeholders(value), "markup": []},
                        "status": "new",
                    }
                )
    return segments


def rebuild(source_path: Path, translated_segments: list[dict[str, Any]], output: Path) -> None:
    _ensure_supported_word_package(source_path)
    targets = _targets_by_part_and_coordinate(translated_segments)
    target_font = _target_font(translated_segments)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(output, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename in targets and _part_kind(info.filename):
                root = ET.fromstring(data)
                groups = {(group["part_name"], group["coordinate"]): group for group in _text_groups(root, info.filename, _part_kind(info.filename) or "text")}
                for key, value in targets[info.filename].items():
                    group = groups.get((info.filename, key))
                    if group is None:
                        raise ValueError(f"Word text span is no longer available: {info.filename}#{key}")
                    _apply_target(group, value, target_font)
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            target.writestr(info, data)


def validate_pair(source_path: Path, target_path: Path) -> dict[str, Any]:
    try:
        _ensure_supported_word_package(source_path)
        _ensure_supported_word_package(target_path)
        source_signature = _package_signature(source_path)
        target_signature = _package_signature(target_path)
        source_segments = _segment_map(extract_segments(source_path, "source", source_path.name))
        target_segments = _segment_map(extract_segments(target_path, "target", source_path.name))
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
        return _qa_result([_qa_item("parse", "blocking", str(exc), target_path)])

    items: list[dict[str, Any]] = []
    if source_signature["names"] != target_signature["names"]:
        items.append(_qa_item("package_integrity", "blocking", "Word package entries changed", target_path))

    for name, digest in source_signature["noneditable_hashes"].items():
        if name == VBA_PROJECT:
            continue
        if target_signature["noneditable_hashes"].get(name) != digest:
            items.append(_qa_item("package_integrity", "blocking", f"Non-text package part changed: {name}", target_path))

    if VBA_PROJECT in source_signature["noneditable_hashes"]:
        if target_signature["noneditable_hashes"].get(VBA_PROJECT) != source_signature["noneditable_hashes"][VBA_PROJECT]:
            items.append(_qa_item("macro_integrity", "blocking", "VBA macro project bytes changed", target_path))

    for name, signature in source_signature["editable_structures"].items():
        if target_signature["editable_structures"].get(name) != signature:
            items.append(_qa_item("word_xml_structure", "blocking", f"Editable XML structure changed: {name}", target_path))

    for key in sorted(source_segments.keys() - target_segments.keys()):
        items.append(_qa_item("text_coverage", "blocking", f"Missing Word text span: {key[0]}#{key[1]}", target_path))
    for key in sorted(target_segments.keys() - source_segments.keys()):
        items.append(_qa_item("text_coverage", "blocking", f"Unexpected Word text span: {key[0]}#{key[1]}", target_path))

    for key in sorted(source_segments.keys() & target_segments.keys()):
        source = source_segments[key]
        target = target_segments[key]
        expected = extract_placeholders(str(source.get("source", "")))
        actual = extract_placeholders(str(target.get("source", "")))
        if expected != actual:
            items.append(
                _qa_item(
                    "placeholder_parity",
                    "blocking",
                    f"Placeholder mismatch at {key[0]}#{key[1]}: source={expected}, target={actual}",
                    target_path,
                    source.get("segment_id"),
                )
            )
        if source.get("context", {}).get("style_signature") != target.get("context", {}).get("style_signature"):
            items.append(
                _qa_item("style_integrity", "blocking", f"Run or paragraph style changed at {key[0]}#{key[1]}", target_path, source.get("segment_id"))
            )

    items.extend(_package_risk_items(source_signature, target_path))
    return _qa_result(items)


def _ensure_supported_word_package(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".doc":
        raise ValueError("Legacy binary .doc is unsupported; convert to .docx before localization")
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported Word document format: {suffix}")
    if not zipfile.is_zipfile(path):
        raise ValueError(f"Word document is not an OpenXML zip package: {path}")
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "[Content_Types].xml" not in names or "word/document.xml" not in names:
            raise ValueError(f"Word package lacks required OpenXML parts: {path}")


def _editable_part_names(archive: zipfile.ZipFile) -> list[str]:
    return sorted(name for name in archive.namelist() if _part_kind(name) is not None)


def _part_kind(name: str) -> str | None:
    if name == "word/document.xml":
        return "body"
    if re.fullmatch(r"word/header\d+\.xml", name):
        return "header"
    if re.fullmatch(r"word/footer\d+\.xml", name):
        return "footer"
    if name == "word/footnotes.xml":
        return "footnote"
    if name == "word/endnotes.xml":
        return "endnote"
    if name == "word/comments.xml":
        return "comment"
    if re.fullmatch(r"word/charts/chart\d+\.xml", name):
        return "chart"
    if re.fullmatch(r"word/diagrams/(?:data|drawing)\d+\.xml", name):
        return "diagram"
    if re.fullmatch(r"word/drawings/drawing\d+\.xml", name):
        return "drawing"
    return None


def _text_groups(root: ET.Element, part_name: str, part_kind: str) -> list[dict[str, Any]]:
    parent_map = {child: parent for parent in root.iter() for child in list(parent)}
    paragraphs = [node for node in root.iter() if node.tag == W_P]
    paragraphs.extend(node for node in root.iter() if node.tag == A_P and not _has_ancestor(node, parent_map, {W_P}))
    if not paragraphs:
        paragraphs = [root]

    groups: list[dict[str, Any]] = []
    for paragraph_index, paragraph in enumerate(paragraphs, 1):
        nodes = [
            node
            for node in paragraph.iter()
            if node.tag in TEXT_TAGS
            and node.text
            and node.text.strip()
            and _nearest_paragraph(node, parent_map) is paragraph
        ]
        if not nodes:
            continue
        paragraph_text = "".join(node.text or "" for node in nodes).strip()
        signatures = [_style_signature(node, parent_map) for node in nodes]
        node_groups = [nodes] if len(set(signatures)) == 1 else [[node] for node in nodes]
        for group_index, node_group in enumerate(node_groups, 1):
            value = "".join(node.text or "" for node in node_group)
            if not value.strip():
                continue
            style_signature = _style_signature(node_group[0], parent_map)
            coordinate = f"{part_name}:p{paragraph_index}:g{group_index}"
            groups.append(
                {
                    "part_name": part_name,
                    "part_kind": part_kind,
                    "coordinate": coordinate,
                    "paragraph_index": paragraph_index,
                    "group_index": group_index,
                    "source": value,
                    "nodes": node_group,
                    "parent_map": parent_map,
                    "text_node_count": len(node_group),
                    "style_signature": style_signature,
                    "paragraph_preview": paragraph_text[:240],
                }
            )
    return groups


def _nearest_paragraph(node: ET.Element, parent_map: dict[ET.Element, ET.Element]) -> ET.Element | None:
    current = node
    while current in parent_map:
        current = parent_map[current]
        if current.tag in PARAGRAPH_TAGS:
            return current
    return None


def _has_ancestor(node: ET.Element, parent_map: dict[ET.Element, ET.Element], tags: set[str]) -> bool:
    current = node
    while current in parent_map:
        current = parent_map[current]
        if current.tag in tags:
            return True
    return False


def _style_signature(node: ET.Element, parent_map: dict[ET.Element, ET.Element]) -> str:
    run = _nearest_ancestor(node, parent_map, {W_R, A_R})
    paragraph = _nearest_paragraph(node, parent_map)
    run_props = _first_child(run, {W_RPR, A_RPR}) if run is not None else None
    paragraph_props = _first_child(paragraph, {W_PPR, A_PPR}) if paragraph is not None else None
    payload = repr([_xml_structure(paragraph_props) if paragraph_props is not None else None, _xml_structure(run_props) if run_props is not None else None]).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _nearest_ancestor(node: ET.Element, parent_map: dict[ET.Element, ET.Element], tags: set[str]) -> ET.Element | None:
    current = node
    while current in parent_map:
        current = parent_map[current]
        if current.tag in tags:
            return current
    return None


def _first_child(node: ET.Element | None, tags: set[str]) -> ET.Element | None:
    if node is None:
        return None
    return next((child for child in list(node) if child.tag in tags), None)


def _targets_by_part_and_coordinate(segments: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    targets: dict[str, dict[str, str]] = {}
    for segment in segments:
        if "target" not in segment:
            continue
        context = segment.get("context", {})
        part_name = str(context.get("part_name") or "")
        coordinate = str(context.get("coordinate") or "")
        if not part_name or not coordinate:
            raise ValueError(f"Word segment lacks part coordinate: {segment.get('segment_id')}")
        targets.setdefault(part_name, {})[coordinate] = str(segment["target"])
    return targets


def _target_font(segments: list[dict[str, Any]]) -> str:
    locale = next((str(segment.get("target_locale") or "") for segment in segments if segment.get("target_locale")), "")
    normalized = locale.replace("_", "-").lower()
    language = normalized.split("-", 1)[0]
    if normalized.startswith("zh-hant") or language == "zh" and any(region in normalized for region in ("-tw", "-hk", "-mo")):
        return "Microsoft JhengHei"
    if language == "zh":
        return "Microsoft YaHei"
    if language in LATIN_FONT_LANGUAGES or language in INDIC_FONT_LANGUAGES:
        return "Nirmala UI" if language in INDIC_FONT_LANGUAGES else "Arial"
    return FONT_BY_LANGUAGE.get(language, "Arial")


def _apply_target(group: dict[str, Any], value: str, target_font: str) -> None:
    nodes = group["nodes"]
    if not nodes:
        return
    nodes[0].text = value
    if value[:1].isspace() or value[-1:].isspace():
        nodes[0].set(XML_SPACE, "preserve")
    _apply_font(nodes[0], group["parent_map"], target_font)
    for node in nodes[1:]:
        node.text = ""
        _apply_font(node, group["parent_map"], target_font)


def _apply_font(node: ET.Element, parent_map: dict[ET.Element, ET.Element], font: str) -> None:
    if node.tag == f"{{{W_NS}}}t":
        run = _nearest_ancestor(node, parent_map, {W_R})
        if run is None:
            return
        run_props = _ensure_child(run, W_RPR, 0)
        fonts = _ensure_child(run_props, W_RFONTS, 0)
        for name in ("ascii", "hAnsi", "eastAsia", "cs"):
            fonts.set(f"{{{W_NS}}}{name}", font)
    elif node.tag == f"{{{A_NS}}}t":
        run = _nearest_ancestor(node, parent_map, {A_R})
        if run is None:
            return
        run_props = _ensure_child(run, A_RPR, 0)
        for tag in (A_LATIN, A_EA, A_CS):
            child = _ensure_child(run_props, tag, len(list(run_props)))
            child.set("typeface", font)


def _ensure_child(node: ET.Element, tag: str, index: int) -> ET.Element:
    child = _first_child(node, {tag})
    if child is not None:
        return child
    child = ET.Element(tag)
    node.insert(index, child)
    return child


def _package_signature(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = sorted(name for name in archive.namelist() if not name.endswith("/"))
        noneditable_hashes: dict[str, str] = {}
        editable_structures: dict[str, Any] = {}
        for name in names:
            data = archive.read(name)
            if _part_kind(name) is None:
                noneditable_hashes[name] = hashlib.sha256(data).hexdigest()
            else:
                editable_structures[name] = _xml_structure(ET.fromstring(data))
        return {
            "names": names,
            "noneditable_hashes": noneditable_hashes,
            "editable_structures": editable_structures,
        }


def _xml_structure(node: ET.Element) -> Any:
    if node.tag in FONT_TAGS:
        return None
    text = "" if node.tag in TEXT_TAGS else (node.text or "").strip()
    attributes = [] if node.tag in TEXT_TAGS else sorted(node.attrib.items())
    children = [child for child in (_xml_structure(child) for child in list(node)) if child is not None]
    if node.tag in PROPERTY_TAGS and not attributes and not text and not children:
        return None
    return [
        node.tag,
        attributes,
        text,
        children,
    ]


def _segment_map(segments: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for segment in segments:
        context = segment.get("context", {})
        result[(str(context.get("part_name")), str(context.get("coordinate")))] = segment
    return result


def _package_risk_items(signature: dict[str, Any], target_path: Path) -> list[dict[str, Any]]:
    names = set(signature.get("names", []))
    items: list[dict[str, Any]] = []
    if any(name.startswith("word/media/") for name in names):
        items.append(_qa_item("visual_text_unchecked", "warning", "Images may contain text that the Word adapter cannot localize", target_path, coverage="partial"))
    if any(name.startswith("word/embeddings/") for name in names):
        items.append(_qa_item("embedded_object_unchecked", "warning", "Embedded object content was preserved but not localized", target_path, coverage="partial"))
    return items


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


def _qa_item(
    category: str,
    severity: str,
    message: str,
    path: Path,
    segment_id: object | None = None,
    coverage: str = "complete",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "channel": "adapter",
        "category": category,
        "severity": severity,
        "message": message,
        "path": path.as_posix(),
        "checked_by": "adapter",
        "coverage": coverage,
        "confidence": "deterministic",
    }
    if segment_id:
        item["segment_id"] = str(segment_id)
    return item
