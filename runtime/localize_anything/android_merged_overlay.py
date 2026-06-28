from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from . import PROTOCOL_VERSION
from .android_strings_adapter import (
    _format_attributes,
    _read_document,
    _render_resource_comments,
    _render_segment_value,
    _segment,
    _target_attributes,
    target_resource_path,
    validate_pair,
)
from .io_utils import write_json


SOURCE_CATEGORY = "merged_dependency_overlay"
RESIDUAL_TEXT_CATEGORIES = [
    "runtime_filesystem_names",
    "os_strings",
    "server_content",
    "hardcoded_code_strings",
    "image_text",
]


def create_overlay_plan(
    project_root: Path,
    selected_source_files: list[str],
    app_source_segments: list[dict[str, Any]],
    source_locale: str,
    target_locale: str,
    merged_resources: Path | None = None,
    build_variant: str | None = None,
    overlay_output_name: str = "localize_anything_overlay.xml",
) -> dict[str, Any]:
    project_root = project_root.resolve()
    merged_files = _merged_resource_files(project_root, merged_resources, build_variant)
    if not merged_files:
        raise ValueError(
            "Android merged resource overlay requires --android-merged-resources "
            "or a discoverable --android-build-variant merged values.xml"
        )
    if not selected_source_files:
        raise ValueError("Android merged resource overlay requires at least one Android source file")

    overlay_source_file = _overlay_source_file(selected_source_files)
    destination = _overlay_destination(project_root, overlay_source_file, target_locale, overlay_output_name)
    logical_source = _overlay_logical_source(overlay_source_file, overlay_output_name)
    app_source_keys = {
        str(segment.get("context", {}).get("resource_key"))
        for segment in app_source_segments
        if segment.get("context", {}).get("content_type") == "android_string"
    }
    target_existing_keys = _target_existing_keys(project_root, selected_source_files, target_locale)
    included_resources: list[dict[str, Any]] = []
    included_keys: set[str] = set()
    exclusions = {
        "app_owned_duplicate": 0,
        "target_locale_existing": 0,
        "translatable_false": 0,
        "unsupported_type": 0,
        "unsafe_markup_or_placeholder": 0,
        "duplicate_merged_resource": 0,
    }
    parse_warnings: list[dict[str, str]] = []

    for merged_file in merged_files:
        document = _read_document(merged_file)
        exclusions["translatable_false"] += sum(1 for item in document.get("skipped", []) if item.get("reason") == "translatable_false")
        exclusions["unsupported_type"] += _unsupported_resource_count(merged_file)
        parse_warnings.extend(
            {"path": _display_path(project_root, merged_file), "message": str(item.get("reason", "skipped"))}
            for item in document.get("skipped", [])
            if item.get("reason") != "translatable_false"
        )
        for resource in document["resources"]:
            key = str(resource["key"])
            if key in app_source_keys:
                exclusions["app_owned_duplicate"] += 1
                continue
            if key in target_existing_keys:
                exclusions["target_locale_existing"] += 1
                continue
            if key in included_keys:
                exclusions["duplicate_merged_resource"] += 1
                continue
            if resource.get("markup_policy", {}).get("owner_review_required"):
                exclusions["unsafe_markup_or_placeholder"] += 1
                continue
            included_keys.add(key)
            included_resources.append(resource)

    segments = []
    for resource in included_resources:
        segment = _segment(logical_source, source_locale, resource)
        segment["source_category"] = SOURCE_CATEGORY
        segment.setdefault("context", {})["source_category"] = SOURCE_CATEGORY
        segment["context"]["overlay_destination"] = destination.as_posix()
        segment["context"]["overlay_output_name"] = overlay_output_name
        segment["context"]["android_merged_resource_overlay"] = True
        segments.append(segment)

    return {
        "protocol_version": PROTOCOL_VERSION,
        "source_category": SOURCE_CATEGORY,
        "coverage_mode": "source-plus-merged-overlay",
        "logical_source": logical_source,
        "destination": destination.as_posix(),
        "overlay_output_name": overlay_output_name,
        "target_locale": target_locale,
        "build_variant": build_variant or "unspecified",
        "merged_resource_files": [_display_path(project_root, path) for path in merged_files],
        "merged_dependency_resources_detected": len(included_resources) + sum(exclusions.values()),
        "merged_dependency_resources_included": len(segments),
        "merged_dependency_resources_excluded": exclusions,
        "visible_ui_coverage_warning": False,
        "residual_text_categories": RESIDUAL_TEXT_CATEGORIES,
        "parse_warnings": parse_warnings,
        "resources": included_resources,
        "segments": segments,
    }


def stage_overlay(
    overlay_plan: dict[str, Any],
    generated_segments: list[dict[str, Any]],
    staging_dir: Path,
    run_dir: Path,
) -> tuple[dict[str, Any], Path]:
    destination = Path(str(overlay_plan["destination"]))
    output = staging_dir / destination
    output.parent.mkdir(parents=True, exist_ok=True)
    source = run_dir / "android-merged-overlay-source.xml"
    generated_by_key = {
        str(segment.get("context", {}).get("resource_key")): segment
        for segment in generated_segments
        if segment.get("context", {}).get("source_category") == SOURCE_CATEGORY
    }
    resources = [
        resource
        for resource in overlay_plan.get("resources", [])
        if str(resource.get("key")) in generated_by_key
    ]
    _write_overlay_source(source, resources, overlay_plan)
    _write_overlay_target(output, resources, generated_by_key, overlay_plan)
    qa = validate_pair(source, output)
    qa_path = run_dir / "qa" / "android-merged-overlay.json"
    write_json(qa_path, qa)
    return (
        {
            "adapter": "core.android-strings",
            "source": overlay_plan["logical_source"],
            "validation_source": source.as_posix(),
            "destination": destination.as_posix(),
            "output": output.as_posix(),
            "segment_count": len(resources),
            "written": True,
            "source_category": SOURCE_CATEGORY,
            "target_locale": overlay_plan["target_locale"],
            "overlay_output_name": overlay_plan["overlay_output_name"],
        },
        qa_path,
    )


def overlay_output_metadata(overlay_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_category": SOURCE_CATEGORY,
        "target_locale": overlay_plan["target_locale"],
        "overlay_output_name": overlay_plan["overlay_output_name"],
        "android_build_variant": overlay_plan.get("build_variant", "unspecified"),
        "apply_safety": {
            "requires_explicit_run_id": True,
            "requires_clean_git_tree": True,
            "destination_policy": "android_target_locale_resource_file",
        },
    }


def _merged_resource_files(project_root: Path, merged_resources: Path | None, build_variant: str | None) -> list[Path]:
    if merged_resources is not None:
        path = merged_resources.resolve()
        if path.is_file():
            return [path]
        if path.is_dir():
            return sorted(
                item
                for item in path.rglob("*.xml")
                if item.parent.name.startswith("values") or item.name == "values.xml"
            )
        raise ValueError(f"Android merged resources path does not exist: {merged_resources}")
    if build_variant:
        token = build_variant[:1].upper() + build_variant[1:]
        pattern = f"*/build/intermediates/incremental/*/merge{token}Resources/merged.dir/values/values.xml"
        return sorted(project_root.glob(pattern))
    return sorted(project_root.glob("*/build/intermediates/incremental/*/merge*Resources/merged.dir/values/values.xml"))


def _overlay_destination(project_root: Path, source_file: str, target_locale: str, output_name: str) -> Path:
    target = target_resource_path(project_root / source_file, target_locale, project_root)
    return target.with_name(output_name)


def _overlay_source_file(selected_source_files: list[str]) -> str:
    for source_file in selected_source_files:
        normalized = source_file.replace("\\", "/")
        if "/src/main/res/" in f"/{normalized}":
            return source_file
    return selected_source_files[0]


def _overlay_logical_source(source_file: str, output_name: str) -> str:
    source = Path(source_file)
    return source.with_name(f"{Path(output_name).stem}-source.xml").as_posix()


def _target_existing_keys(project_root: Path, selected_source_files: list[str], target_locale: str) -> set[str]:
    keys: set[str] = set()
    seen_dirs: set[Path] = set()
    for source_file in selected_source_files:
        target = project_root / target_resource_path(project_root / source_file, target_locale, project_root)
        target_dir = target.parent
        if target_dir in seen_dirs or not target_dir.is_dir():
            continue
        seen_dirs.add(target_dir)
        for item in sorted(target_dir.glob("*.xml")):
            try:
                document = _read_document(item)
            except (OSError, ValueError, ElementTree.ParseError):
                continue
            keys.update(str(resource["key"]) for resource in document["resources"])
    return keys


def _unsupported_resource_count(path: Path) -> int:
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return 0
    supported = {"string", "string-array", "plurals"}
    return sum(1 for child in list(root) if _tag(child.tag) not in supported)


def _write_overlay_source(path: Path, resources: list[dict[str, Any]], overlay_plan: dict[str, Any]) -> None:
    _write_resources(path, resources, {}, overlay_plan, source=True)


def _write_overlay_target(
    path: Path,
    resources: list[dict[str, Any]],
    generated_by_key: dict[str, dict[str, Any]],
    overlay_plan: dict[str, Any],
) -> None:
    _write_resources(path, resources, generated_by_key, overlay_plan, source=False)


def _write_resources(
    path: Path,
    resources: list[dict[str, Any]],
    generated_by_key: dict[str, dict[str, Any]],
    overlay_plan: dict[str, Any],
    *,
    source: bool,
) -> None:
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<resources>"]
    lines.extend(
        [
            "    <!-- Generated by Localize Anything. -->",
            "    <!-- App-owned overlay for Gradle merged dependency resources. -->",
            f"    <!-- Target locale: {overlay_plan['target_locale']} -->",
            f"    <!-- Build variant: {overlay_plan.get('build_variant', 'unspecified')} -->",
        ]
    )
    index = 0
    while index < len(resources):
        resource = resources[index]
        resource_type = resource["type"]
        if resource_type == "string":
            attrs = _target_attributes(resource["attributes"])
            attrs["name"] = resource["name"]
            lines.extend(_render_resource_comments(resource, "    "))
            value = _render_source_or_target(resource, generated_by_key, source)
            lines.append(f"    <string {_format_attributes(attrs)}>{value}</string>")
            index += 1
            continue
        grouped = []
        while index < len(resources) and resources[index]["type"] == resource_type and resources[index]["name"] == resource["name"]:
            grouped.append(resources[index])
            index += 1
        attrs = _target_attributes(resource["attributes"])
        attrs["name"] = resource["name"]
        lines.extend(_render_resource_comments(resource, "    "))
        lines.append(f"    <{resource_type} {_format_attributes(attrs)}>")
        for item in grouped:
            value = _render_source_or_target(item, generated_by_key, source)
            if resource_type == "plurals":
                lines.append(f"        <item quantity={_quote(str(item['quantity']))}>{value}</item>")
            else:
                lines.append(f"        <item>{value}</item>")
        lines.append(f"    </{resource_type}>")
    lines.append("</resources>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _render_source_or_target(
    resource: dict[str, Any],
    generated_by_key: dict[str, dict[str, Any]],
    source: bool,
) -> str:
    if source:
        return _render_segment_value(
            {"target": resource["value"], "constraints": {"escape_signature": []}},
            cdata=bool(resource.get("cdata")),
        )
    return _render_segment_value(generated_by_key[str(resource["key"])], cdata=bool(resource.get("cdata")))


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _quote(value: str) -> str:
    return '"' + value.replace('"', "&quot;") + '"'


def _tag(value: str) -> str:
    return value.rsplit("}", 1)[-1]
