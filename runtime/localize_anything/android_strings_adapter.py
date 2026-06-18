from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

from . import PROTOCOL_VERSION
from .json_adapter import extract_placeholders, source_hash


ANDROID_STRING_TAGS = {"string", "string-array", "plurals"}


def extract_segments(path: Path, source_locale: str, source_path: str | None = None) -> list[dict[str, Any]]:
    logical_path = source_path or path.as_posix()
    document = _read_document(path)
    return [_segment(logical_path, source_locale, resource) for resource in document["resources"]]


def rebuild(source_path: Path, translated_segments: list[dict[str, Any]], output: Path) -> None:
    document = _read_document(source_path)
    by_key = _targets_by_resource_key(translated_segments)
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<resources>"]
    index = 0
    resources = document["resources"]
    while index < len(resources):
        resource = resources[index]
        resource_type = resource["type"]
        if resource_type == "string":
            segment = by_key.get(resource["key"])
            if segment and "target" in segment:
                attrs = _target_attributes(resource["attributes"])
                attrs["name"] = resource["name"]
                lines.append(f"    <string {_format_attributes(attrs)}>{escape(str(segment['target']))}</string>")
            index += 1
            continue

        grouped = []
        while index < len(resources) and resources[index]["type"] == resource_type and resources[index]["name"] == resource["name"]:
            grouped.append(resources[index])
            index += 1
        rendered_items = []
        for item in grouped:
            segment = by_key.get(item["key"])
            if not segment or "target" not in segment:
                continue
            if resource_type == "plurals":
                rendered_items.append(f"        <item quantity={quoteattr(item['quantity'])}>{escape(str(segment['target']))}</item>")
            else:
                rendered_items.append(f"        <item>{escape(str(segment['target']))}</item>")
        if rendered_items:
            attrs = _target_attributes(resource["attributes"])
            attrs["name"] = resource["name"]
            lines.append(f"    <{resource_type} {_format_attributes(attrs)}>")
            lines.extend(rendered_items)
            lines.append(f"    </{resource_type}>")
    lines.append("</resources>")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


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
        "adapter": "core.android-strings",
        "target_locale": target_locale,
        "resource_qualifier": locale_to_resource_qualifier(target_locale),
        "output": output.as_posix(),
        "destination": relative.as_posix(),
        "written": True,
    }


def validate_pair(source_path: Path, target_path: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    try:
        source = _read_document(source_path)
    except (OSError, ValueError, ElementTree.ParseError) as exc:
        return _parse_failure(source_path, str(exc))
    try:
        target = _read_document(target_path)
    except (OSError, ValueError, ElementTree.ParseError) as exc:
        return _parse_failure(target_path, str(exc))

    for duplicate in source["duplicates"]:
        items.append(_qa_item("duplicate_resource", "blocking", f"Duplicate source string resource: {duplicate}", source_path))
    for duplicate in target["duplicates"]:
        items.append(_qa_item("duplicate_resource", "blocking", f"Duplicate target string resource: {duplicate}", target_path))
    for skipped in source["skipped"]:
        severity = "info" if skipped["reason"] == "translatable_false" else "warning"
        items.append(
            _qa_item(
                "unsupported_or_skipped_resource",
                severity,
                f"Skipped {skipped['tag']} resource {skipped['name']}: {skipped['reason']}",
                source_path,
                skipped["name"],
            )
        )

    source_resources = {item["key"]: item for item in source["resources"]}
    target_resources = {item["key"]: item for item in target["resources"]}
    non_translatable = {
        str(item.get("key") or item.get("name"))
        for item in source["skipped"]
        if item["reason"] == "translatable_false"
    }

    for key in sorted(source_resources.keys() - target_resources.keys()):
        items.append(_qa_item("translation_coverage", "warning", f"Missing target resource: {_resource_label(source_resources[key])}", target_path, key))
    for key in sorted(target_resources.keys() - source_resources.keys()):
        category = "non_translatable_resource" if key in non_translatable else "unexpected_resource"
        label = _resource_label(target_resources[key])
        items.append(_qa_item(category, "warning", f"Unexpected target resource: {label}", target_path, key))
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
            raise ValueError(f"Android source is not inside project root: {source_path}") from exc
    elif source_path.is_absolute():
        raise ValueError("project_root is required when source_path is absolute")
    else:
        relative = source_path

    parts = list(relative.parts)
    for index, part in enumerate(parts):
        if part == "values" and index > 0 and parts[index - 1] == "res":
            parts[index] = f"values-{locale_to_resource_qualifier(target_locale)}"
            return Path(*parts)
    raise ValueError(f"Android strings source must be under res/values: {source_path}")


def locale_to_resource_qualifier(locale: str) -> str:
    parts = [part for part in locale.replace("_", "-").split("-") if part]
    if not parts:
        raise ValueError("target locale is required")
    language = parts[0].lower()
    if len(parts) == 1:
        return language
    if len(parts) == 2 and (len(parts[1]) == 2 or parts[1].isdigit()):
        return f"{language}-r{parts[1].upper()}"
    return "b+" + "+".join([language, *parts[1:]])


def is_android_strings_path(project_root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(project_root)
    except ValueError:
        relative = path
    parts = relative.parts
    return (
        path.name == "strings.xml"
        and len(parts) >= 3
        and parts[-3] == "res"
        and parts[-2].startswith("values")
    )


def _read_document(path: Path) -> dict[str, Any]:
    tree = ElementTree.parse(path)
    root = tree.getroot()
    if _tag(root.tag) != "resources":
        raise ValueError(f"Android strings file must have a <resources> root: {path}")

    resources: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    duplicates: list[str] = []
    seen_names: set[str] = set()
    for element in list(root):
        tag = _tag(element.tag)
        if tag not in ANDROID_STRING_TAGS:
            continue
        name = element.attrib.get("name", "")
        if not name:
            skipped.append({"tag": tag, "name": "<missing-name>", "reason": "missing_name"})
            continue
        duplicate_key = f"{tag}:{name}"
        if duplicate_key in seen_names:
            duplicates.append(duplicate_key)
        seen_names.add(duplicate_key)
        if element.attrib.get("translatable") == "false":
            skipped.append({"tag": tag, "name": _container_key(tag, name), "reason": "translatable_false"})
            continue
        if tag == "string":
            if list(element):
                skipped.append({"tag": tag, "name": _container_key(tag, name), "reason": "inline_markup"})
                continue
            resources.append(_resource("string", name, element.text or "", dict(element.attrib)))
            continue
        item_index = 0
        for child in list(element):
            child_tag = _tag(child.tag)
            if child_tag != "item":
                continue
            if list(child):
                skipped.append({"tag": tag, "name": _item_key(tag, name, item_index, child.attrib.get("quantity")), "reason": "inline_markup"})
                item_index += 1
                continue
            if tag == "plurals":
                quantity = child.attrib.get("quantity", "")
                if not quantity:
                    skipped.append({"tag": tag, "name": _item_key(tag, name, item_index, None), "reason": "missing_quantity"})
                    item_index += 1
                    continue
                resources.append(_resource("plurals", name, child.text or "", dict(element.attrib), item_index, quantity))
            else:
                resources.append(_resource("string-array", name, child.text or "", dict(element.attrib), item_index))
            item_index += 1
    return {"resources": resources, "skipped": skipped, "duplicates": duplicates}


def _segment(logical_path: str, locale: str, resource: dict[str, Any]) -> dict[str, Any]:
    key = resource["key"]
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    value = resource["value"]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "segment_id": f"android:{logical_path}#{digest}",
        "source": value,
        "source_locale": locale,
        "source_path": logical_path,
        "source_hash": source_hash(f"{key}\0{value}"),
        "context": {
            "content_type": "android_string",
            "content_unit": f"android:{PurePosixPath(logical_path).parent.as_posix()}",
            "resource_key": key,
            "resource_name": resource["name"],
            "resource_type": resource["type"],
            "item_index": resource.get("item_index"),
            "quantity": resource.get("quantity"),
            "attributes": _target_attributes(resource["attributes"]),
        },
        "constraints": {"placeholders": _resource_placeholders(resource), "markup": []},
        "status": "new",
    }


def _targets_by_resource_key(segments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for segment in segments:
        context = segment.get("context", {})
        key = context.get("resource_key")
        if not isinstance(key, str):
            resource_type = context.get("resource_type")
            name = context.get("resource_name")
            if isinstance(resource_type, str) and isinstance(name, str):
                key = _item_key(resource_type, name, context.get("item_index"), context.get("quantity"))
        if isinstance(key, str):
            result[key] = segment
    return result


def _resource(
    resource_type: str,
    name: str,
    value: str,
    attributes: dict[str, str],
    item_index: int | None = None,
    quantity: str | None = None,
) -> dict[str, Any]:
    return {
        "type": resource_type,
        "name": name,
        "value": value,
        "attributes": attributes,
        "item_index": item_index,
        "quantity": quantity,
        "key": _item_key(resource_type, name, item_index, quantity),
    }


def _resource_placeholders(resource: dict[str, Any]) -> list[str]:
    if resource.get("attributes", {}).get("formatted") == "false":
        return []
    return extract_placeholders(str(resource.get("value", "")))


def _target_attributes(attributes: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in attributes.items() if key in {"formatted", "product"}}


def _format_attributes(attributes: dict[str, str]) -> str:
    ordered = ["name", *sorted(key for key in attributes if key != "name")]
    return " ".join(f"{key}={quoteattr(str(attributes[key]))}" for key in ordered if key in attributes)


def _container_key(resource_type: str, name: str) -> str:
    return f"{resource_type}:{name}"


def _item_key(resource_type: str, name: str, item_index: Any = None, quantity: Any = None) -> str:
    if resource_type == "plurals":
        return f"plurals:{name}#{quantity}"
    if resource_type == "string-array":
        return f"string-array:{name}[{item_index}]"
    return _container_key(resource_type, name)


def _resource_label(resource: dict[str, Any]) -> str:
    if resource["type"] == "plurals":
        return f"plurals {resource['name']}[{resource.get('quantity')}]"
    if resource["type"] == "string-array":
        return f"string-array {resource['name']}[{resource.get('item_index')}]"
    return f"string {resource['name']}"


def _tag(value: str) -> str:
    return value.rsplit("}", 1)[-1]


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
