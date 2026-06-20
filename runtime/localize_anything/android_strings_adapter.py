from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

from . import PROTOCOL_VERSION
from .json_adapter import extract_placeholders, source_hash


ANDROID_STRING_TAGS = {"string", "string-array", "plurals"}
ESCAPE_SIGNATURE_ORDER = ("\\'", '"', "\\n", "\\t", "%%")
VALID_BACKSLASH_ESCAPES = {"'", '"', "n", "t", "\\", "@", "?"}
SUPPORTED_INLINE_TAGS = ("b", "i", "u")
ATTRIBUTE_TAGS = {"a": {"href"}}  # tag → required-attrs set, attrs must match EXACTLY
POSITIONAL_FORMAT_RE = re.compile(r"%\d+\$[#0 +\-]*\d*(?:\.\d+)?(?:hh|h|ll|l|L|z|j|t)?[A-Za-z@]")
FORMAT_RE = re.compile(r"%[#0 +\-]*\d*(?:\.\d+)?(?:hh|h|ll|l|L|z|j|t)?[A-Za-z@]")
INLINE_TAG_RE = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9:_-]*)([^>]*)>")
CDATA_STRING_RE = re.compile(r"<string\b(?P<attrs>[^>]*)>\s*<!\[CDATA\[", re.DOTALL)
NAME_ATTR_RE = re.compile(r"\bname\s*=\s*(['\"])(?P<name>.*?)\1")


def extract_segments(path: Path, source_locale: str, source_path: str | None = None) -> list[dict[str, Any]]:
    logical_path = source_path or path.as_posix()
    document = _read_document(path)
    return [_segment(logical_path, source_locale, resource) for resource in document["resources"]]


def rebuild(
    source_path: Path,
    translated_segments: list[dict[str, Any]],
    output: Path,
    preserve_target_only_from: Path | None = None,
) -> dict[str, Any]:
    document = _read_document(source_path)
    by_key = _targets_by_resource_key(translated_segments)
    existing_by_key = (
        {
            resource["key"]: resource
            for resource in _read_preservable_target_resources(preserve_target_only_from)
        }
        if preserve_target_only_from is not None and preserve_target_only_from.is_file()
        else {}
    )
    preserved_review_required: list[str] = []
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<resources>"]
    index = 0
    resources = document["resources"]
    while index < len(resources):
        resource = resources[index]
        resource_type = resource["type"]
        if resource_type == "string":
            if _owner_review_required(resource):
                preserved = existing_by_key.get(resource["key"], resource)
                attrs = _target_attributes(preserved["attributes"])
                attrs["name"] = resource["name"]
                lines.extend(_render_resource_comments(preserved, "    "))
                lines.append(f"    <string {_format_attributes(attrs)}>{_render_resource_value(preserved)}</string>")
                preserved_review_required.append(resource["key"])
                index += 1
                continue
            segment = by_key.get(resource["key"])
            if segment and "target" in segment:
                attrs = _target_attributes(resource["attributes"])
                attrs["name"] = resource["name"]
                lines.extend(_render_resource_comments(resource, "    "))
                lines.append(f"    <string {_format_attributes(attrs)}>{_render_segment_value(segment, cdata=bool(resource.get('cdata')))}</string>")
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
                rendered_items.append(f"        <item quantity={quoteattr(item['quantity'])}>{_render_segment_value(segment)}</item>")
            else:
                rendered_items.append(f"        <item>{_render_segment_value(segment)}</item>")
        if rendered_items:
            attrs = _target_attributes(resource["attributes"])
            attrs["name"] = resource["name"]
            lines.extend(_render_resource_comments(resource, "    "))
            lines.append(f"    <{resource_type} {_format_attributes(attrs)}>")
            lines.extend(rendered_items)
            lines.append(f"    </{resource_type}>")
    preserved_target_only = _target_only_resources(resources, preserve_target_only_from)
    if preserved_target_only:
        lines.append("    <!-- Target-only resources preserved for owner review. -->")
        lines.extend(_render_existing_resources(preserved_target_only))
    lines.append("</resources>")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return {
        "preserved_target_only_count": len(preserved_target_only),
        "preserved_target_only_keys": [resource["key"] for resource in preserved_target_only],
        "preserved_review_required_count": len(preserved_review_required),
        "preserved_review_required_keys": preserved_review_required,
    }


def stage_rebuild(
    source_path: Path,
    translated_segments: list[dict[str, Any]],
    staging_dir: Path,
    target_locale: str,
    project_root: Path | None = None,
    preserve_target_only: bool = False,
) -> dict[str, Any]:
    relative = target_resource_path(source_path, target_locale, project_root)
    output = staging_dir / relative
    existing_target = project_root / relative if preserve_target_only and project_root is not None else None
    rebuild_result = rebuild(source_path, translated_segments, output, existing_target)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "adapter": "core.android-strings",
        "target_locale": target_locale,
        "resource_qualifier": locale_to_resource_qualifier(target_locale),
        "output": output.as_posix(),
        "destination": relative.as_posix(),
        "written": True,
        **rebuild_result,
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
        category = str(skipped.get("category") or "unsupported_or_skipped_resource")
        action = "Detected" if skipped.get("owner_review_required") else "Skipped"
        items.append(
            _qa_item(
                category,
                severity,
                f"{action} {skipped['tag']} resource {skipped['name']}: {skipped['reason']}",
                source_path,
                skipped["name"],
            )
        )
        if skipped.get("owner_review_required"):
            items.append(
                _qa_item(
                    "owner_review_required",
                    "warning",
                    f"Owner review required for unsupported Android markup: {skipped['name']}",
                    source_path,
                    skipped["name"],
                )
            )
    items.extend(_comment_qa_items(source, target, target_path))

    source_resources = {item["key"]: item for item in source["resources"]}
    target_resources = {item["key"]: item for item in target["resources"]}
    non_translatable = {
        str(item.get("key") or item.get("name"))
        for item in source["skipped"]
        if item["reason"] == "translatable_false"
    }

    for key in sorted(source_resources.keys() - target_resources.keys()):
        source_resource = source_resources[key]
        if _owner_review_required(source_resource):
            items.append(_qa_item("unsupported_markup_drift", "blocking", f"Target dropped owner-review-required markup resource: {_resource_label(source_resource)}", target_path, key))
        else:
            items.append(_qa_item("translation_coverage", "warning", f"Missing target resource: {_resource_label(source_resource)}", target_path, key))
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
        items.extend(_escape_qa_items(source_resource, target_resource, target_path, key))
        items.extend(_markup_qa_items(source_resource, target_resource, target_path, key))
        items.extend(_unsupported_markup_qa_items(source_resource, target_resource, target_path, key))
        items.extend(_cdata_qa_items(source_resource, target_resource, target_path, key))

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
    raw_text = path.read_text(encoding="utf-8")
    cdata_names = _cdata_resource_names(raw_text)
    resource_comments = _resource_comment_info(path)
    tree = ElementTree.parse(path)
    root = tree.getroot()
    if _tag(root.tag) != "resources":
        raise ValueError(f"Android strings file must have a <resources> root: {path}")

    resources: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
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
        comment_info = resource_comments.get(_container_key(tag, name), {})
        if tag == "string":
            cdata = name in cdata_names
            if list(element):
                inline = _extract_supported_inline_markup(element)
                if inline is None:
                    markup_policy = _classify_unsupported_inline_markup(element)
                    resource = _resource(
                        "string",
                        name,
                        _serialize_element_inner(element),
                        dict(element.attrib),
                        cdata=cdata,
                        comment_info=comment_info,
                        markup_policy=markup_policy,
                        markup_structure_signature=_markup_structure_signature(element),
                        preserve_inline_xml=True,
                    )
                    resources.append(resource)
                    skipped.append(
                        {
                            "tag": tag,
                            "name": resource["key"],
                            "reason": markup_policy["category"],
                            "category": markup_policy["category"],
                            "categories": markup_policy["categories"],
                            "owner_review_required": True,
                        }
                    )
                    continue
                resources.append(
                    _resource(
                        "string",
                        name,
                        inline["value"],
                        dict(element.attrib),
                        markup_signature=inline["markup_signature"],
                        cdata=cdata,
                        comment_info=comment_info,
                    )
                )
                continue
            resources.append(_resource("string", name, element.text or "", dict(element.attrib), cdata=cdata, comment_info=comment_info))
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
                resources.append(_resource("plurals", name, child.text or "", dict(element.attrib), item_index, quantity, comment_info=comment_info))
            else:
                resources.append(_resource("string-array", name, child.text or "", dict(element.attrib), item_index, comment_info=comment_info))
            item_index += 1
    return {"resources": resources, "skipped": skipped, "duplicates": duplicates, "comments": resource_comments}


def _segment(logical_path: str, locale: str, resource: dict[str, Any]) -> dict[str, Any]:
    key = resource["key"]
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    value = resource["value"]
    escape_signature = extract_escape_signature(value)
    markup_signature = list(resource.get("markup_signature", []))
    markup_policy = dict(resource.get("markup_policy", {}))
    owner_review_required = bool(markup_policy.get("owner_review_required"))
    cdata = bool(resource.get("cdata"))
    resource_comment = str(resource.get("resource_comment", ""))
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
            "resource_comment": resource_comment,
            "markup_policy": markup_policy,
        },
        "constraints": {
            "placeholders": _resource_placeholders(resource),
            "markup": markup_signature,
            "markup_signature": markup_signature,
            "escape_signature": escape_signature,
            "cdata": cdata,
            "markup_policy": markup_policy,
        },
        "escape_signature": escape_signature,
        "markup_signature": markup_signature,
        "cdata": cdata,
        "cdata_signature": {"boundary": "cdata", "original_had_cdata": True} if cdata else {},
        "resource_comment": resource_comment,
        "generation_eligible": not owner_review_required,
        "owner_review_required": owner_review_required,
        "review_required_reasons": list(markup_policy.get("categories", [])),
        "workflow_status": "owner_review_required" if owner_review_required else "generation_candidate",
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


def _target_only_resources(source_resources: list[dict[str, Any]], target_path: Path | None) -> list[dict[str, Any]]:
    if target_path is None or not target_path.is_file():
        return []
    source_keys = {resource["key"] for resource in source_resources}
    return [resource for resource in _read_preservable_target_resources(target_path) if resource["key"] not in source_keys]


def _read_preservable_target_resources(path: Path) -> list[dict[str, Any]]:
    raw_text = path.read_text(encoding="utf-8")
    cdata_names = _cdata_resource_names(raw_text)
    resource_comments = _resource_comment_info(path)
    tree = ElementTree.parse(path)
    root = tree.getroot()
    if _tag(root.tag) != "resources":
        raise ValueError(f"Android strings file must have a <resources> root: {path}")
    resources: list[dict[str, Any]] = []
    for element in list(root):
        tag = _tag(element.tag)
        if tag not in ANDROID_STRING_TAGS:
            continue
        name = element.attrib.get("name", "")
        if not name:
            continue
        comment_info = resource_comments.get(_container_key(tag, name), {})
        if tag == "string":
            if list(element):
                inline = _extract_supported_inline_markup(element)
                if inline is not None:
                    resources.append(
                        _resource(
                            "string",
                            name,
                            inline["value"],
                            dict(element.attrib),
                            markup_signature=inline["markup_signature"],
                            cdata=name in cdata_names,
                            comment_info=comment_info,
                        )
                    )
                    continue
                markup_policy = _classify_unsupported_inline_markup(element)
                resources.append(
                    _resource(
                        "string",
                        name,
                        _serialize_element_inner(element),
                        dict(element.attrib),
                        cdata=name in cdata_names,
                        comment_info=comment_info,
                        markup_policy=markup_policy,
                        markup_structure_signature=_markup_structure_signature(element),
                        preserve_inline_xml=True,
                    )
                )
                continue
            resources.append(_resource("string", name, element.text or "", dict(element.attrib), cdata=name in cdata_names, comment_info=comment_info))
            continue
        item_index = 0
        for child in list(element):
            child_tag = _tag(child.tag)
            if child_tag != "item" or list(child):
                item_index += 1
                continue
            if tag == "plurals":
                quantity = child.attrib.get("quantity", "")
                if quantity:
                    resources.append(_resource("plurals", name, child.text or "", dict(element.attrib), item_index, quantity, comment_info=comment_info))
            else:
                resources.append(_resource("string-array", name, child.text or "", dict(element.attrib), item_index, comment_info=comment_info))
            item_index += 1
    return resources


def _render_existing_resources(resources: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    index = 0
    while index < len(resources):
        resource = resources[index]
        resource_type = resource["type"]
        if resource_type == "string":
            attrs = _target_attributes(resource["attributes"])
            attrs["name"] = resource["name"]
            lines.extend(_render_resource_comments(resource, "    "))
            lines.append(f"    <string {_format_attributes(attrs)}>{_render_resource_value(resource)}</string>")
            index += 1
            continue

        grouped = []
        while index < len(resources) and resources[index]["type"] == resource_type and resources[index]["name"] == resource["name"]:
            grouped.append(resources[index])
            index += 1
        rendered_items = []
        for item in grouped:
            if resource_type == "plurals":
                rendered_items.append(f"        <item quantity={quoteattr(item['quantity'])}>{escape(str(item['value']))}</item>")
            else:
                rendered_items.append(f"        <item>{escape(str(item['value']))}</item>")
        if rendered_items:
            attrs = _target_attributes(resource["attributes"])
            attrs["name"] = resource["name"]
            lines.extend(_render_resource_comments(resource, "    "))
            lines.append(f"    <{resource_type} {_format_attributes(attrs)}>")
            lines.extend(rendered_items)
            lines.append(f"    </{resource_type}>")
    return lines


def _resource(
    resource_type: str,
    name: str,
    value: str,
    attributes: dict[str, str],
    item_index: int | None = None,
    quantity: str | None = None,
    markup_signature: list[dict[str, Any]] | None = None,
    cdata: bool = False,
    comment_info: dict[str, Any] | None = None,
    markup_policy: dict[str, Any] | None = None,
    markup_structure_signature: list[dict[str, Any]] | None = None,
    preserve_inline_xml: bool = False,
) -> dict[str, Any]:
    comment_entries = list((comment_info or {}).get("entries", []))
    resource_comment = "\n".join(comment_entries).strip()
    return {
        "type": resource_type,
        "name": name,
        "value": value,
        "attributes": attributes,
        "item_index": item_index,
        "quantity": quantity,
        "markup_signature": markup_signature or [],
        "markup_policy": markup_policy or {},
        "markup_structure_signature": markup_structure_signature or [],
        "preserve_inline_xml": preserve_inline_xml,
        "cdata": cdata,
        "resource_comment": resource_comment,
        "comment_entries": comment_entries,
        "comment_count": int((comment_info or {}).get("count", len(comment_entries))),
        "key": _item_key(resource_type, name, item_index, quantity),
    }


def _resource_placeholders(resource: dict[str, Any]) -> list[str]:
    if resource.get("attributes", {}).get("formatted") == "false":
        return []
    return extract_placeholders(str(resource.get("value", "")))


def _owner_review_required(resource: dict[str, Any]) -> bool:
    policy = resource.get("markup_policy", {})
    return isinstance(policy, dict) and bool(policy.get("owner_review_required"))


def _cdata_resource_names(raw_text: str) -> set[str]:
    names: set[str] = set()
    for match in CDATA_STRING_RE.finditer(raw_text):
        name_match = NAME_ATTR_RE.search(match.group("attrs"))
        if name_match:
            names.add(name_match.group("name"))
    return names


def _resource_comment_info(path: Path) -> dict[str, dict[str, Any]]:
    comments: dict[str, dict[str, Any]] = {}
    pending: list[str] = []
    for event, element in ElementTree.iterparse(path, events=("start", "comment")):
        if event == "comment":
            text = (element.text or "").strip()
            if text:
                pending.append(text)
            continue
        tag = _tag(str(element.tag))
        if tag in ANDROID_STRING_TAGS:
            name = element.attrib.get("name", "")
            if name and pending:
                entries = list(pending)
                comments[_container_key(tag, name)] = {
                    "entries": entries,
                    "comment": "\n".join(entries),
                    "count": len(entries),
                }
            pending = []
            continue
        if tag not in {"resources", "item"}:
            pending = []
    return comments


def _extract_supported_inline_markup(element: ElementTree.Element) -> dict[str, Any] | None:
    pieces: list[str] = [element.text or ""]
    signature: list[dict[str, Any]] = []
    for child in list(element):
        tag = _tag(child.tag)
        if tag in ATTRIBUTE_TAGS:
            required = ATTRIBUTE_TAGS[tag]
            attrs = dict(child.attrib)
            if set(attrs.keys()) != required or list(child):
                return None
            index = len(signature)
            raw_open = "<" + tag + " " + " ".join(k + '="' + v + '"' for k, v in sorted(attrs.items())) + ">"
            raw_close = "</" + tag + ">"
            sig_item: dict[str, Any] = {
                "type": "markup_tag",
                "tag": tag,
                "kind": "pair",
                "index": index,
                "attributes": dict(attrs),
                "open": raw_open,
                "close": raw_close,
            }
            signature.append(sig_item)
            xml_open = "<" + tag + " " + " ".join(k + "=" + quoteattr(v) for k, v in sorted(attrs.items())) + ">"
            pieces.append(xml_open)
            pieces.append(child.text or "")
            pieces.append(raw_close)
            pieces.append(child.tail or "")
            continue
        if tag not in SUPPORTED_INLINE_TAGS or child.attrib or list(child):
            return None
        index = len(signature)
        signature.append(
            {
                "type": "markup_tag",
                "tag": tag,
                "kind": "pair",
                "index": index,
                "open": f"<{tag}>",
                "close": f"</{tag}>",
            }
        )
        pieces.append(f"<{tag}>")
        pieces.append(child.text or "")
        pieces.append(f"</{tag}>")
        pieces.append(child.tail or "")
    return {"value": "".join(pieces), "markup_signature": signature}


def _classify_unsupported_inline_markup(element: ElementTree.Element) -> dict[str, Any]:
    categories: set[str] = set()

    def visit(node: ElementTree.Element, depth: int) -> None:
        tag = _tag(node.tag)
        if depth > 1:
            categories.add("complex_nested_markup")
        if tag in SUPPORTED_INLINE_TAGS:
            if node.attrib:
                categories.add("unsupported_markup_attribute")
        elif tag in ATTRIBUTE_TAGS:
            if set(node.attrib) != ATTRIBUTE_TAGS[tag]:
                categories.add("unsupported_markup_attribute")
        else:
            categories.add("unsupported_markup_tag")
        for child in list(node):
            visit(child, depth + 1)

    for child in list(element):
        visit(child, 1)
    if not categories:
        categories.add("unsupported_markup_tag")
    ordered = [
        category
        for category in ("complex_nested_markup", "unsupported_markup_tag", "unsupported_markup_attribute")
        if category in categories
    ]
    return {
        "supported": False,
        "generation_eligible": False,
        "owner_review_required": True,
        "category": ordered[0],
        "categories": [*ordered, "unsupported_markup", "owner_review_required"],
        "policy": "preserve_without_automatic_localization",
    }


def _markup_structure_signature(element: ElementTree.Element) -> list[dict[str, Any]]:
    def signature(node: ElementTree.Element) -> dict[str, Any]:
        return {
            "tag": _tag(node.tag),
            "attributes": dict(sorted(node.attrib.items())),
            "children": [signature(child) for child in list(node)],
        }

    return [signature(child) for child in list(element)]


def _serialize_element_inner(element: ElementTree.Element) -> str:
    pieces = [escape(element.text or "")]
    for child in list(element):
        pieces.append(_serialize_inline_child(child))
        pieces.append(escape(child.tail or ""))
    return "".join(pieces)


def _serialize_inline_child(element: ElementTree.Element) -> str:
    tag = _tag(element.tag)
    attrs = f" {_format_attributes(dict(element.attrib))}" if element.attrib else ""
    inner = [escape(element.text or "")]
    for child in list(element):
        inner.append(_serialize_inline_child(child))
        inner.append(escape(child.tail or ""))
    return f"<{tag}{attrs}>{''.join(inner)}</{tag}>"


def _render_resource_value(resource: dict[str, Any]) -> str:
    value = str(resource["value"])
    if resource.get("cdata"):
        return _render_cdata_value(value)
    if resource.get("preserve_inline_xml"):
        return value
    if resource.get("markup_signature"):
        return _render_inline_markup_value(value)
    return escape(value)


def _render_segment_value(segment: dict[str, Any], *, cdata: bool = False) -> str:
    value = str(segment["target"])
    if cdata:
        return _render_cdata_value(value)
    constraints = segment.get("constraints", {})
    if isinstance(constraints, dict) and constraints.get("markup_signature"):
        return _render_inline_markup_value(value)
    return escape(value)


def _render_cdata_value(value: str) -> str:
    if "]]>" in value:
        raise ValueError("CDATA target contains unsafe terminator sequence: ]]>")
    return f"<![CDATA[{value}]]>"


def _render_resource_comments(resource: dict[str, Any], indent: str) -> list[str]:
    return [f"{indent}<!-- {_safe_comment_text(comment)} -->" for comment in resource.get("comment_entries", []) if str(comment).strip()]


def _safe_comment_text(comment: str) -> str:
    return str(comment).replace("--", "- -").strip()


def _render_inline_markup_value(value: str) -> str:
    rendered: list[str] = []
    position = 0
    for match in INLINE_TAG_RE.finditer(value):
        rendered.append(escape(value[position : match.start()]))
        slash, tag, suffix = match.groups()
        token = match.group(0)
        if tag in ATTRIBUTE_TAGS and slash == "":
            # Render attribute tag open
            rendered.append(token)
        elif tag in ATTRIBUTE_TAGS and slash != "":
            rendered.append(token)
        elif tag in SUPPORTED_INLINE_TAGS and suffix == "" and token in {f"<{tag}>", f"</{tag}>"}:
            rendered.append(token)
        else:
            rendered.append(escape(token))
        position = match.end()
    rendered.append(escape(value[position:]))
    return "".join(rendered)


def extract_escape_signature(text: str) -> list[str]:
    counts = _escape_signature_counts(text)
    return [token for token in ESCAPE_SIGNATURE_ORDER if counts.get(token, 0) > 0]


def validate_escape_signatures(
    source_text: str,
    target_text: str,
    *,
    formatted: bool = True,
) -> list[dict[str, Any]]:
    source_counts = _escape_signature_counts(source_text)
    target_counts = _escape_signature_counts(target_text)
    issues: list[dict[str, Any]] = []
    for token in ESCAPE_SIGNATURE_ORDER:
        expected = source_counts.get(token, 0)
        if expected <= 0:
            continue
        actual = target_counts.get(token, 0)
        if actual >= expected:
            continue
        if token == "%%":
            issues.append(
                {
                    "category": "percent_literal_drift",
                    "severity": "warning",
                    "message": f"Target dropped literal percent escape {token}: expected at least {expected}, actual {actual}",
                    "token": token,
                    "expected": expected,
                    "actual": actual,
                }
            )
        else:
            issues.append(
                {
                    "category": "escape_missing",
                    "severity": "warning",
                    "message": f"Target dropped protected Android escape {token}: expected at least {expected}, actual {actual}",
                    "token": token,
                    "expected": expected,
                    "actual": actual,
                }
            )
    for malformed in _malformed_backslash_escapes(target_text):
        issues.append(
            {
                "category": "malformed_escape",
                "severity": "blocking",
                "message": f"Target contains malformed Android escape sequence: {malformed}",
                "token": malformed,
            }
        )
    if formatted:
        for malformed in _malformed_percent_sequences(target_text):
            issues.append(
                {
                    "category": "malformed_escape",
                    "severity": "blocking",
                    "message": f"Target contains malformed Android percent sequence: {malformed}",
                    "token": malformed,
                }
            )
    return issues


def validate_markup_signatures(
    source_text: str,
    target_text: str,
    markup_signature: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not markup_signature:
        return []
    issues = _validate_inline_attribute_signatures(target_text, markup_signature)
    expected_tags = [str(item.get("tag")) for item in markup_signature if item.get("kind") == "pair"]
    expected_counts = Counter(expected_tags)
    target = _analyze_inline_markup(target_text)
    for token in target["unsupported_tokens"]:
        issues.append(
            {
                "category": "unsupported_markup",
                "severity": "warning",
                "message": f"Target contains unsupported Android inline markup: {token}",
                "token": token,
            }
        )
    for token in target["malformed_tokens"]:
        issues.append(
            {
                "category": "malformed_markup",
                "severity": "blocking",
                "message": f"Target contains malformed Android inline markup: {token}",
                "token": token,
            }
        )
    missing = False
    for tag in SUPPORTED_INLINE_TAGS:
        expected = expected_counts.get(tag, 0)
        if expected <= 0:
            continue
        actual = target["pair_counts"].get(tag, 0)
        if actual >= expected:
            continue
        missing = True
        issues.append(
            {
                "category": "markup_missing",
                "severity": "warning",
                "message": f"Target dropped required Android inline <{tag}> pair: expected at least {expected}, actual {actual}",
                "tag": tag,
                "expected": expected,
                "actual": actual,
            }
        )
    # Also check attribute-tag pairs
    for item in markup_signature:
        tag = str(item.get("tag", ""))
        if tag in ATTRIBUTE_TAGS:
            expected = expected_counts.get(tag, 0)
            actual = target["pair_counts"].get(tag, 0)
            if actual < expected:
                issues.append(
                    {
                        "category": "markup_missing",
                        "severity": "warning",
                        "message": f"Target dropped required Android inline <{tag}> pair: expected at least {expected}, actual {actual}",
                        "tag": tag,
                        "expected": expected,
                        "actual": actual,
                    }
                )
    if not issues or all(item["severity"] != "blocking" for item in issues):
        if not target["malformed_tokens"] and target["open_sequence"] != expected_tags:
            issues.append(
                {
                    "category": "markup_order_drift",
                    "severity": "warning",
                    "message": f"Target changed Android inline markup order: expected={expected_tags}, actual={target['open_sequence']}",
                    "expected": expected_tags,
                    "actual": target["open_sequence"],
                }
            )
    return issues


def validate_cdata_target(target_text: str) -> list[dict[str, Any]]:
    if "]]>" not in target_text:
        return []
    return [
        {
            "category": "cdata_terminator_unsafe",
            "severity": "blocking",
            "message": "CDATA target contains unsafe terminator sequence: ]]>",
            "token": "]]>",
        }
    ]


def _escape_qa_items(
    source_resource: dict[str, Any],
    target_resource: dict[str, Any],
    target_path: Path,
    segment_id: str,
) -> list[dict[str, Any]]:
    formatted = source_resource.get("attributes", {}).get("formatted") != "false"
    items: list[dict[str, Any]] = []
    for issue in validate_escape_signatures(str(source_resource.get("value", "")), str(target_resource.get("value", "")), formatted=formatted):
        items.append(
            _qa_item(
                str(issue["category"]),
                str(issue["severity"]),
                str(issue["message"]),
                target_path,
                segment_id,
            )
        )
    return items


def _cdata_qa_items(
    source_resource: dict[str, Any],
    target_resource: dict[str, Any],
    target_path: Path,
    segment_id: str,
) -> list[dict[str, Any]]:
    if not source_resource.get("cdata"):
        return []
    items: list[dict[str, Any]] = []
    for issue in validate_cdata_target(str(target_resource.get("value", ""))):
        items.append(
            _qa_item(
                str(issue["category"]),
                str(issue["severity"]),
                str(issue["message"]),
                target_path,
                segment_id,
            )
        )
    if not target_resource.get("cdata"):
        items.append(
            _qa_item(
                "cdata_boundary_missing",
                "warning",
                f"Target normalized CDATA boundary for {_resource_label(source_resource)}",
                target_path,
                segment_id,
            )
        )
    return items


def _comment_qa_items(source_document: dict[str, Any], target_document: dict[str, Any], target_path: Path) -> list[dict[str, Any]]:
    source_comments: dict[str, dict[str, Any]] = source_document.get("comments", {})
    target_comments: dict[str, dict[str, Any]] = target_document.get("comments", {})
    items: list[dict[str, Any]] = []
    for key, source_info in sorted(source_comments.items()):
        expected = str(source_info.get("comment", "")).strip()
        if not expected:
            continue
        target_info = target_comments.get(key)
        actual = str((target_info or {}).get("comment", "")).strip()
        if actual == expected:
            continue
        wrong_keys = [
            target_key
            for target_key, candidate in target_comments.items()
            if target_key != key and str(candidate.get("comment", "")).strip() == expected
        ]
        if wrong_keys:
            items.append(
                _qa_item(
                    "comment_misattached",
                    "warning",
                    f"Resource comment for {key} is attached to {', '.join(sorted(wrong_keys))}",
                    target_path,
                    key,
                )
            )
        else:
            items.append(
                _qa_item(
                    "comment_missing",
                    "warning",
                    f"Missing resource comment for {key}: {expected}",
                    target_path,
                    key,
                )
            )
    for key, target_info in sorted(target_comments.items()):
        entries = [str(entry).strip() for entry in target_info.get("entries", []) if str(entry).strip()]
        source_count = int(source_comments.get(key, {}).get("count", 0))
        if len(entries) != len(set(entries)) or (source_count and len(entries) > source_count):
            items.append(
                _qa_item(
                    "comment_duplicate",
                    "warning",
                    f"Duplicate resource comment before {key}",
                    target_path,
                    key,
                )
            )
    return items


def _markup_qa_items(
    source_resource: dict[str, Any],
    target_resource: dict[str, Any],
    target_path: Path,
    segment_id: str,
) -> list[dict[str, Any]]:
    markup_signature = source_resource.get("markup_signature", [])
    if not markup_signature:
        return []
    items: list[dict[str, Any]] = []
    for issue in validate_markup_signatures(
        str(source_resource.get("value", "")),
        str(target_resource.get("value", "")),
        markup_signature,
    ):
        items.append(
            _qa_item(
                str(issue["category"]),
                str(issue["severity"]),
                str(issue["message"]),
                target_path,
                segment_id,
            )
        )
    return items


def _unsupported_markup_qa_items(
    source_resource: dict[str, Any],
    target_resource: dict[str, Any],
    target_path: Path,
    segment_id: str,
) -> list[dict[str, Any]]:
    if not _owner_review_required(source_resource):
        return []
    expected = source_resource.get("markup_structure_signature", [])
    actual = target_resource.get("markup_structure_signature", [])
    if expected == actual:
        return []
    return [
        _qa_item(
            "unsupported_markup_drift",
            "blocking",
            f"Owner-review-required Android markup structure changed for {_resource_label(source_resource)}",
            target_path,
            segment_id,
        )
    ]


def _analyze_inline_markup(text: str) -> dict[str, Any]:
    unsupported_tokens: list[str] = []
    malformed_tokens: list[str] = []
    open_sequence: list[str] = []
    pair_counts: Counter[str] = Counter()
    stack: list[str] = []
    position = 0
    for match in INLINE_TAG_RE.finditer(text):
        if _has_unparsed_markup_angle(text[position : match.start()]):
            malformed_tokens.append(text[position : match.start()])
        slash, tag, suffix = match.groups()
        token = match.group(0)
        supported = tag in SUPPORTED_INLINE_TAGS or tag in ATTRIBUTE_TAGS
        has_extra_attrs = bool(suffix.strip()) if tag in SUPPORTED_INLINE_TAGS else False
        if tag in ATTRIBUTE_TAGS:
            required = ATTRIBUTE_TAGS[tag]
            if slash != "":
                # Closing tag — skip attribute validation
                pass
            else:
                raw_attrs = suffix.strip()
                parsed_attrs = _parse_tag_attributes(raw_attrs)
                if set(parsed_attrs.keys()) != required:
                    unsupported_tokens.append(token)
                    position = match.end()
                    continue
            has_extra_attrs = False
            if tag not in ATTRIBUTE_TAGS or slash == "":
                pass  # attribute order/form — still supported
        if not supported or has_extra_attrs or (tag not in ATTRIBUTE_TAGS and suffix != ""):
            unsupported_tokens.append(token)
            position = match.end()
            continue
        if tag not in ATTRIBUTE_TAGS and token not in {f"<{tag}>", f"</{tag}>"}:
            unsupported_tokens.append(token)
            position = match.end()
            continue
        if slash == "":
            stack.append(tag)
            open_sequence.append(tag)
        else:
            if not stack or stack[-1] != tag:
                malformed_tokens.append(token)
            else:
                stack.pop()
                pair_counts[tag] += 1
        position = match.end()
    if _has_unparsed_markup_angle(text[position:]):
        malformed_tokens.append(text[position:])
    malformed_tokens.extend(f"<{tag}>" for tag in reversed(stack))
    return {
        "unsupported_tokens": unsupported_tokens,
        "malformed_tokens": malformed_tokens,
        "open_sequence": open_sequence,
        "pair_counts": pair_counts,
    }


def _parse_tag_attributes(attr_string: str) -> dict[str, str]:
    """Parse HTML-style key="value" pairs from a tag suffix string."""
    attrs: dict[str, str] = {}
    pattern = re.compile(r"""(\S+)=("[^"]*"|'[^']*')""")
    for match in pattern.finditer(attr_string):
        key = match.group(1)
        val = match.group(2)
        val = val[1:-1]  # strip quotes
        attrs[key] = val
    return attrs


def _validate_inline_attribute_signatures(
    target_text: str, markup_signature: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validate that attribute-tag href values are preserved exactly."""
    issues: list[dict[str, Any]] = []
    target_lower = target_text.lower()
    for item in markup_signature:
        tag = str(item.get("tag", ""))
        if tag not in ATTRIBUTE_TAGS:
            continue
        attrs = item.get("attributes", {})
        open_tag = str(item.get("open", ""))
        close_tag = str(item.get("close", ""))
        href_expected = attrs.get("href", "")
        href_re = re.compile(r"""href\s*=\s*["']([^"']*)["']""", re.IGNORECASE)
        # Check required tag pair exists
        open_prefix = "<" + tag
        open_in_target = target_lower.find(open_prefix)
        open_pos = target_lower.find(open_tag.lower())
        close_pos = target_lower.find(close_tag.lower())
        open_section = target_text[open_pos:open_pos + len(open_tag) + 50] if open_pos >= 0 else ""
        href_match = href_re.search(open_section) if open_section else None
        if open_pos == -1 or close_pos == -1:
            if open_in_target != -1:
                # Tag exists but attributes differ
                href_section = target_text[open_in_target:open_in_target + 100]
                href_check = href_re.search(href_section)
                if not href_check:
                    issues.append({
                        "category": "markup_attribute_missing",
                        "severity": "blocking",
                        "message": f"Target <{tag}> tag is missing required href attribute",
                        "tag": tag,
                    })
                elif href_check.group(1) != href_expected:
                    issues.append({
                        "category": "markup_url_drift",
                        "severity": "blocking",
                        "message": f"Target changed href URL: expected '...{href_expected[-20:]}', got '...{href_check.group(1)[-20:]}'",
                        "tag": tag,
                        "expected": href_expected,
                        "actual": href_check.group(1),
                    })
                else:
                    issues.append({
                        "category": "markup_missing",
                        "severity": "blocking",
                        "message": f"Target dropped required Android inline <{tag}> pair with attributes: {open_tag}",
                        "tag": tag,
                    })
            else:
                issues.append({
                    "category": "markup_missing",
                    "severity": "blocking",
                    "message": f"Target dropped required Android inline <{tag}> pair with attributes: {open_tag}",
                    "tag": tag,
                })
            continue
        if open_pos >= close_pos:
            issues.append({
                "category": "malformed_markup",
                "severity": "blocking",
                "message": f"Target has malformed <{tag}> pair: close before open",
                "token": target_text[max(0, open_pos):min(len(target_text), close_pos + len(close_tag))],
            })
            continue
        # Check href is preserved exactly (tag was found, verify attribute value)
        update_section = target_text[open_pos:open_pos + len(open_tag) + 50]
        update_match = href_re.search(update_section)
        if not update_match:
            issues.append({
                "category": "markup_attribute_missing",
                "severity": "blocking",
                "message": f"Target <{tag}> tag is missing required href attribute",
                "tag": tag,
            })
        elif href_match.group(1) != href_expected:
            issues.append({
                "category": "markup_url_drift",
                "severity": "blocking",
                "message": f"Target changed href URL: expected '...{href_expected[-20:]}', got '...{href_match.group(1)[-20:]}'",
                "tag": tag,
                "expected": href_expected,
                "actual": href_match.group(1),
            })
        # Check no unsupported attributes introduced
        extra_attr_re = re.compile(r'\b(on\w+|style|class|id)\s*=', re.IGNORECASE)
        extra_attrs = extra_attr_re.findall(target_text)
        if extra_attrs:
            issues.append({
                "category": "unsupported_markup",
                "severity": "blocking",
                "message": f"Target introduced unsupported attributes: {', '.join(sorted(set(a.lower() for a in extra_attrs)))}",
                "attrs": extra_attrs,
            })
    return issues


def _has_unparsed_markup_angle(text: str) -> bool:
    return "<" in text or ">" in text


def _escape_signature_counts(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    index = 0
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if char == "%" and nxt == "%":
            counts["%%"] += 1
            index += 2
            continue
        if char == "\\" and nxt:
            if nxt == "'":
                counts["\\'"] += 1
                index += 2
                continue
            if nxt == '"':
                counts['"'] += 1
                index += 2
                continue
            if nxt == "n":
                counts["\\n"] += 1
                index += 2
                continue
            if nxt == "t":
                counts["\\t"] += 1
                index += 2
                continue
        if char == '"':
            counts['"'] += 1
        index += 1
    return counts


def _malformed_backslash_escapes(text: str) -> list[str]:
    malformed: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != "\\":
            index += 1
            continue
        if index + 1 >= len(text):
            malformed.append("\\")
            break
        nxt = text[index + 1]
        if nxt in VALID_BACKSLASH_ESCAPES:
            index += 2
            continue
        if nxt == "u" and index + 5 < len(text) and all(char in "0123456789abcdefABCDEF" for char in text[index + 2 : index + 6]):
            index += 6
            continue
        malformed.append(text[index : index + 2])
        index += 2
    return malformed


def _malformed_percent_sequences(text: str) -> list[str]:
    malformed: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != "%":
            index += 1
            continue
        if text.startswith("%%", index):
            index += 2
            continue
        match = _format_placeholder_end(text, index)
        if match > index:
            index = match
            continue
        malformed.append(text[index : index + 2] if index + 1 < len(text) else "%")
        index += 1
    return malformed


def _format_placeholder_end(text: str, index: int) -> int:
    match = POSITIONAL_FORMAT_RE.match(text, index)
    if match:
        return match.end()
    match = FORMAT_RE.match(text, index)
    return match.end() if match else index


def _target_attributes(attributes: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in attributes.items() if key in {"formatted", "product", "translatable"}}


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
