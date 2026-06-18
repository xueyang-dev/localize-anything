from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from . import PROTOCOL_VERSION
from .json_adapter import extract_placeholders, source_hash


SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def extract_segments(path: Path, source_locale: str, source_path: str | None = None) -> list[dict[str, Any]]:
    extension = path.suffix.lower()
    if extension in {".csv", ".tsv"}:
        return _extract_delimited(path, source_locale, source_path)
    if extension == ".xlsx":
        return _extract_xlsx(path, source_locale, source_path)
    raise ValueError(f"Unsupported tabular format: {extension}")


def rebuild(source_path: Path, translated_segments: list[dict[str, Any]], output: Path) -> None:
    if source_path.suffix.lower() in {".csv", ".tsv"}:
        _rebuild_delimited(source_path, translated_segments, output)
    elif source_path.suffix.lower() == ".xlsx":
        _rebuild_xlsx(source_path, translated_segments, output)
    else:
        raise ValueError(f"Unsupported tabular format: {source_path.suffix}")


def validate_pair(source_path: Path, target_path: Path) -> dict[str, Any]:
    try:
        source = _coordinate_map(extract_segments(source_path, "source", source_path.name))
        target = _coordinate_map(extract_segments(target_path, "target", source_path.name))
    except (OSError, ValueError, csv.Error, zipfile.BadZipFile, ET.ParseError) as exc:
        return _qa_result([_qa_item("parse", "blocking", str(exc), target_path)])
    items: list[dict[str, Any]] = []
    try:
        if _structural_signature(source_path) != _structural_signature(target_path):
            items.append(_qa_item("table_structure", "blocking", "Header, key column, dimensions, or formulas changed", target_path))
    except (OSError, ValueError, csv.Error, zipfile.BadZipFile, ET.ParseError) as exc:
        items.append(_qa_item("table_structure", "blocking", str(exc), target_path))
    for coordinate in sorted(source.keys() - target.keys()):
        items.append(_qa_item("cell_coverage", "blocking", f"Missing translatable cell {coordinate}", target_path, coordinate))
    for coordinate in sorted(target.keys() - source.keys()):
        items.append(_qa_item("cell_coverage", "blocking", f"Unexpected translatable cell {coordinate}", target_path, coordinate))
    for coordinate in sorted(source.keys() & target.keys()):
        expected = extract_placeholders(source[coordinate])
        actual = extract_placeholders(target[coordinate])
        if expected != actual:
            items.append(
                _qa_item(
                    "placeholder_parity",
                    "blocking",
                    f"Placeholder mismatch at {coordinate}: source={expected}, target={actual}",
                    target_path,
                    coordinate,
                )
            )
    return _qa_result(items)


def _extract_delimited(path: Path, source_locale: str, source_path: str | None) -> list[dict[str, Any]]:
    logical_path = source_path or path.as_posix()
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    text = path.read_text(encoding="utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header = rows[0] if rows else []
    segments: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows[1:], 1):
        for column_index, value in enumerate(row):
            if column_index == 0 or not value:
                continue
            coordinate = f"R{row_index + 1}C{column_index + 1}"
            context = {
                "content_type": "tabular_cell",
                "tabular_format": path.suffix.lower().lstrip("."),
                "row": row_index,
                "column": column_index,
                "coordinate": coordinate,
                "column_name": header[column_index] if column_index < len(header) else None,
                "row_key": row[0] if row else None,
                "delimiter": delimiter,
            }
            segments.append(_segment(logical_path, source_locale, coordinate, value, context))
    return segments


def _rebuild_delimited(source_path: Path, translated_segments: list[dict[str, Any]], output: Path) -> None:
    delimiter = "\t" if source_path.suffix.lower() == ".tsv" else ","
    text = source_path.read_text(encoding="utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    for segment in translated_segments:
        if "target" not in segment:
            continue
        context = segment.get("context", {})
        row, column = context.get("row"), context.get("column")
        if not isinstance(row, int) or not isinstance(column, int) or row >= len(rows) or column >= len(rows[row]):
            raise ValueError(f"Invalid tabular cell span: {segment.get('segment_id')}")
        rows[row][column] = str(segment["target"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=delimiter, lineterminator=newline)
        writer.writerows(rows)


def _extract_xlsx(path: Path, source_locale: str, source_path: str | None) -> list[dict[str, Any]]:
    logical_path = source_path or path.as_posix()
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        occurrences: dict[int, list[dict[str, str]]] = {index: [] for index in range(len(shared))}
        inline: list[tuple[str, str, str]] = []
        for name in sorted(item for item in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", item)):
            root = ET.fromstring(archive.read(name))
            for cell in root.findall(f".//{{{SHEET_NS}}}c"):
                coordinate = cell.get("r", "")
                if cell.get("t") == "s":
                    value = cell.find(f"{{{SHEET_NS}}}v")
                    if value is not None and value.text and value.text.isdigit():
                        index = int(value.text)
                        if index in occurrences:
                            occurrences[index].append({"sheet_path": name, "cell": coordinate})
                elif cell.get("t") == "inlineStr":
                    text = "".join(node.text or "" for node in cell.findall(f".//{{{SHEET_NS}}}t"))
                    if text:
                        inline.append((name, coordinate, text))
    segments: list[dict[str, Any]] = []
    for index, value in enumerate(shared):
        if not value or not _has_translatable_cell(occurrences[index]):
            continue
        coordinate = f"sharedStrings/{index}"
        context = {
            "content_type": "tabular_cell",
            "tabular_format": "xlsx",
            "storage": "shared_string",
            "shared_string_index": index,
            "coordinate": coordinate,
            "occurrences": occurrences[index],
        }
        segments.append(_segment(logical_path, source_locale, coordinate, value, context))
    for sheet_path, cell, value in inline:
        if _is_header_or_key_cell(cell):
            continue
        coordinate = f"{sheet_path}#{cell}"
        context = {
            "content_type": "tabular_cell",
            "tabular_format": "xlsx",
            "storage": "inline_string",
            "sheet_path": sheet_path,
            "cell": cell,
            "coordinate": coordinate,
        }
        segments.append(_segment(logical_path, source_locale, coordinate, value, context))
    return segments


def _rebuild_xlsx(source_path: Path, translated_segments: list[dict[str, Any]], output: Path) -> None:
    shared_targets: dict[int, str] = {}
    inline_targets: dict[tuple[str, str], str] = {}
    for segment in translated_segments:
        if "target" not in segment:
            continue
        context = segment.get("context", {})
        if context.get("storage") == "shared_string" and isinstance(context.get("shared_string_index"), int):
            shared_targets[context["shared_string_index"]] = str(segment["target"])
        elif context.get("storage") == "inline_string" and context.get("sheet_path") and context.get("cell"):
            inline_targets[(str(context["sheet_path"]), str(context["cell"]))] = str(segment["target"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(output, "w") as target:
        shared_usage = _shared_usage(source)
        split_indexes: dict[int, int] = {}
        rendered_shared: bytes | None = None
        if shared_targets and "xl/sharedStrings.xml" in source.namelist():
            root = ET.fromstring(source.read("xl/sharedStrings.xml"))
            entries = root.findall(f"{{{SHEET_NS}}}si")
            for index, value in shared_targets.items():
                if index >= len(entries):
                    raise ValueError(f"XLSX shared string index is out of range: {index}")
                has_key_usage = any(_is_header_or_key_cell(cell) for _sheet, cell in shared_usage.get(index, []))
                has_value_usage = any(not _is_header_or_key_cell(cell) for _sheet, cell in shared_usage.get(index, []))
                if has_key_usage and has_value_usage:
                    new_entry = ET.SubElement(root, f"{{{SHEET_NS}}}si")
                    ET.SubElement(new_entry, f"{{{SHEET_NS}}}t").text = value
                    split_indexes[index] = len(entries) + len(split_indexes)
                else:
                    nodes = entries[index].findall(f".//{{{SHEET_NS}}}t")
                    if not nodes:
                        nodes = [ET.SubElement(entries[index], f"{{{SHEET_NS}}}t")]
                    nodes[0].text = value
                    for node in nodes[1:]:
                        node.text = ""
            if split_indexes:
                root.set("uniqueCount", str(len(entries) + len(split_indexes)))
            rendered_shared = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "xl/sharedStrings.xml" and rendered_shared is not None:
                data = rendered_shared
            elif info.filename.startswith("xl/worksheets/") and (inline_targets or split_indexes):
                root = ET.fromstring(data)
                changed = False
                for cell in root.findall(f".//{{{SHEET_NS}}}c"):
                    key = (info.filename, cell.get("r", ""))
                    if key in inline_targets:
                        nodes = cell.findall(f".//{{{SHEET_NS}}}t")
                        if nodes:
                            nodes[0].text = inline_targets[key]
                            for node in nodes[1:]:
                                node.text = ""
                            changed = True
                    if cell.get("t") == "s" and not _is_header_or_key_cell(cell.get("r", "")):
                        value_node = cell.find(f"{{{SHEET_NS}}}v")
                        if value_node is not None and value_node.text and int(value_node.text) in split_indexes:
                            value_node.text = str(split_indexes[int(value_node.text)])
                            changed = True
                if changed:
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            target.writestr(info, data)


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in entry.findall(f".//{{{SHEET_NS}}}t")) for entry in root.findall(f"{{{SHEET_NS}}}si")]


def _shared_usage(archive: zipfile.ZipFile) -> dict[int, list[tuple[str, str]]]:
    usage: dict[int, list[tuple[str, str]]] = {}
    for name in sorted(item for item in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", item)):
        root = ET.fromstring(archive.read(name))
        for cell in root.findall(f".//{{{SHEET_NS}}}c"):
            if cell.get("t") != "s":
                continue
            value = cell.find(f"{{{SHEET_NS}}}v")
            if value is not None and value.text and value.text.isdigit():
                usage.setdefault(int(value.text), []).append((name, cell.get("r", "")))
    return usage


def _structural_signature(path: Path) -> Any:
    if path.suffix.lower() in {".csv", ".tsv"}:
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig")), delimiter=delimiter))
        return {
            "dimensions": [len(row) for row in rows],
            "header": rows[0] if rows else [],
            "keys": [row[0] if row else "" for row in rows[1:]],
        }
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        sheets: dict[str, dict[str, Any]] = {}
        for name in sorted(item for item in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", item)):
            root = ET.fromstring(archive.read(name))
            cells: dict[str, Any] = {}
            for cell in root.findall(f".//{{{SHEET_NS}}}c"):
                coordinate = cell.get("r", "")
                formula = cell.find(f"{{{SHEET_NS}}}f")
                if formula is not None:
                    cells[coordinate] = {"formula": formula.text or ""}
                elif _is_header_or_key_cell(coordinate):
                    cells[coordinate] = {"key": _xlsx_cell_text(cell, shared)}
                else:
                    cells[coordinate] = {"type": cell.get("t", "number")}
            sheets[name] = cells
        return sheets


def _xlsx_cell_text(cell: ET.Element, shared: list[str]) -> str:
    if cell.get("t") == "s":
        value = cell.find(f"{{{SHEET_NS}}}v")
        if value is not None and value.text and value.text.isdigit() and int(value.text) < len(shared):
            return shared[int(value.text)]
    if cell.get("t") == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(f".//{{{SHEET_NS}}}t"))
    value = cell.find(f"{{{SHEET_NS}}}v")
    return value.text if value is not None and value.text else ""


def _has_translatable_cell(occurrences: list[dict[str, str]]) -> bool:
    return any(not _is_header_or_key_cell(item.get("cell", "")) for item in occurrences)


def _is_header_or_key_cell(coordinate: str) -> bool:
    match = re.fullmatch(r"([A-Z]+)(\d+)", coordinate)
    if not match:
        return False
    column, row = match.groups()
    return int(row) == 1 or column == "A"


def _segment(logical_path: str, locale: str, coordinate: str, value: str, context: dict[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(coordinate.encode("utf-8")).hexdigest()[:20]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "segment_id": f"tabular:{logical_path}#{digest}",
        "source": value,
        "source_locale": locale,
        "source_path": logical_path,
        "source_hash": source_hash(value),
        "context": context,
        "constraints": {"placeholders": extract_placeholders(value), "markup": []},
        "status": "new",
    }


def _coordinate_map(segments: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in segments:
        context = item["context"]
        if context.get("storage") == "shared_string":
            for occurrence in context.get("occurrences", []):
                if _is_header_or_key_cell(str(occurrence.get("cell", ""))):
                    continue
                coordinate = f"{occurrence.get('sheet_path')}#{occurrence.get('cell')}"
                result[coordinate] = str(item["source"])
        else:
            result[str(context["coordinate"])] = str(item["source"])
    return result


def _qa_result(items: list[dict[str, Any]]) -> dict[str, Any]:
    blocking = sum(item["severity"] == "blocking" for item in items)
    warnings = sum(item["severity"] == "warning" for item in items)
    return {
        "protocol_version": PROTOCOL_VERSION,
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
