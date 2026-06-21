from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from . import PROTOCOL_VERSION
from .io_utils import write_json


ANDROID_RESOURCE_TYPES = ("string", "string-array", "plurals")


def build_inspect_summary(
    inspection: dict[str, Any],
    *,
    output_directory: Path | None = None,
) -> dict[str, Any]:
    supported_files = inspection.get("supported_files", [])
    adapter_counts = dict(sorted(inspection.get("adapter_counts", {}).items()))
    android_files = [item for item in supported_files if item.get("adapter") == "core.android-strings"]
    android_summary = _android_summary(Path(inspection["project_root"]), android_files)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-inspect-summary-v1",
        "project_path": inspection.get("project_root"),
        "detected_project_type": _detected_project_type(adapter_counts),
        "primary_adapter": _primary_adapter(adapter_counts),
        "adapters": [{"adapter": adapter, "file_count": count} for adapter, count in adapter_counts.items()],
        "supported_file_count": len(supported_files),
        "resource_files": [_resource_file_summary(item) for item in supported_files],
        "android": android_summary,
        "unprocessed_non_text_asset_count": len(inspection.get("unprocessed_non_text_assets", [])),
        "ignored_path_count": inspection.get("ignored_path_count", 0),
        "skipped_path_count": inspection.get("skipped_path_count", 0),
        "preflight_assessment": inspection.get("preflight_assessment", {}),
        "risk_review_metadata": {
            "available": False,
            "reason": "inspect summary is read-only and does not extract segments, run risk classification, or create review artifacts",
        },
        "warnings": _summary_warnings(inspection, android_summary),
        "output_directory": output_directory.resolve().as_posix() if output_directory is not None else None,
        "read_only": True,
        "read_only_statement": "inspect summary is read-only; it does not generate translations, stage files, or apply changes",
    }


def write_inspect_summary(output_directory: Path, summary: dict[str, Any]) -> dict[str, str]:
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "inspect-summary.json"
    markdown_path = output_directory / "inspect-summary.md"
    summary["artifacts"] = {
        "json": json_path.resolve().as_posix(),
        "markdown": markdown_path.resolve().as_posix(),
    }
    write_json(json_path, summary)
    markdown_path.write_text(render_inspect_summary_markdown(summary), encoding="utf-8", newline="\n")
    return summary["artifacts"]


def validate_inspect_output_directory(project_root: Path, output_directory: Path) -> None:
    project_root = project_root.resolve()
    output_directory = output_directory.resolve()
    try:
        common = Path(os.path.commonpath([project_root, output_directory]))
    except ValueError:
        return
    if common == project_root:
        raise ValueError(
            "inspect --output-dir must be outside the source project. "
            "Use a temporary evidence directory to keep inspection read-only."
        )


def render_inspect_summary_markdown(summary: dict[str, Any]) -> str:
    android = summary.get("android", {})
    lines = [
        "# Inspect Summary",
        "",
        f"- Project path: `{summary.get('project_path')}`",
        f"- Detected project type: `{summary.get('detected_project_type')}`",
        f"- Primary adapter: `{summary.get('primary_adapter')}`",
        f"- Supported file count: {summary.get('supported_file_count')}",
        f"- Output directory: `{summary.get('output_directory')}`",
        f"- Read-only: {str(summary.get('read_only')).lower()}",
        "",
        "Inspect is read-only. It does not generate translations, stage files, or apply changes.",
        "",
        "## Adapters",
        "",
    ]
    adapters = summary.get("adapters", [])
    if adapters:
        for item in adapters:
            lines.append(f"- `{item['adapter']}`: {item['file_count']}")
    else:
        lines.append("- none detected")
    lines.extend(["", "## Android", ""])
    if android.get("resource_file_count", 0):
        lines.append(f"- Android resource file count: {android['resource_file_count']}")
        lines.append(f"- Source sets: {', '.join(android.get('source_sets', [])) or 'none detected'}")
        lines.append(f"- Qualifiers: {', '.join(android.get('qualifiers', [])) or 'none detected'}")
        lines.append(f"- Existing target locales: {', '.join(android.get('existing_target_locales', [])) or 'none detected'}")
        resource_types = android.get("resource_types", {})
        lines.append("- Resource types:")
        for resource_type in ANDROID_RESOURCE_TYPES:
            lines.append(f"  - `{resource_type}`: {resource_types.get(resource_type, 0)}")
        if android.get("owner_review_required_files"):
            lines.append("- Owner-review-required files:")
            for path in android["owner_review_required_files"]:
                lines.append(f"  - `{path}`")
        if android.get("warnings"):
            lines.append("- Warnings:")
            for warning in android["warnings"]:
                lines.append(f"  - `{warning.get('path')}`: {warning.get('message')}")
    else:
        lines.append("- No Android string resources detected.")
    lines.extend(["", "## Risk And Review Metadata", ""])
    risk = summary.get("risk_review_metadata", {})
    lines.append(f"- Available during inspect: {str(risk.get('available')).lower()}")
    lines.append(f"- Reason: {risk.get('reason')}")
    lines.extend(["", "## Warnings", ""])
    warnings = summary.get("warnings", [])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _resource_file_summary(item: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "path": item.get("path"),
        "adapter": item.get("adapter"),
        "size_bytes": item.get("size_bytes"),
    }
    for key in (
        "android_role",
        "android_source_set",
        "android_res_dir",
        "android_qualifiers",
        "target_resource_path",
        "owner_review_required",
    ):
        if key in item:
            summary[key] = item[key]
    return summary


def _detected_project_type(adapter_counts: dict[str, int]) -> str:
    if not adapter_counts:
        return "unknown"
    platform_adapters = {
        "core.android-strings": "android",
        "core.ios-strings": "ios",
        "core.xcstrings": "xcstrings",
    }
    detected = [
        (adapter, project_type)
        for adapter, project_type in platform_adapters.items()
        if adapter_counts.get(adapter)
    ]
    if len(detected) == 1 and sum(adapter_counts.values()) == adapter_counts[detected[0][0]]:
        return detected[0][1]
    if detected:
        return "mixed"
    return "generic"


def _primary_adapter(adapter_counts: dict[str, int]) -> str | None:
    if not adapter_counts:
        return None
    return sorted(adapter_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _android_summary(project_root: Path, android_files: list[dict[str, Any]]) -> dict[str, Any]:
    resource_types: Counter[str] = Counter({resource_type: 0 for resource_type in ANDROID_RESOURCE_TYPES})
    warnings: list[dict[str, str]] = []
    for item in android_files:
        counts, parse_warnings = _android_resource_type_counts(project_root / item["path"])
        resource_types.update(counts)
        warnings.extend({"path": item["path"], "message": warning} for warning in parse_warnings)
        warnings.extend({"path": item["path"], "message": warning} for warning in item.get("warnings", []))
    return {
        "resource_file_count": len(android_files),
        "resource_types": {resource_type: resource_types.get(resource_type, 0) for resource_type in ANDROID_RESOURCE_TYPES},
        "source_sets": sorted({item.get("android_source_set") for item in android_files if item.get("android_source_set")}),
        "qualifiers": _android_qualifiers(android_files),
        "existing_target_locales": sorted(
            {
                item.get("android_qualifiers", {}).get("locale")
                for item in android_files
                if item.get("android_role") == "locale_reference" and item.get("android_qualifiers", {}).get("locale")
            }
        ),
        "generation_source_files": sorted(item["path"] for item in android_files if item.get("android_role") == "source_candidate"),
        "target_locale_files": sorted(item["path"] for item in android_files if item.get("android_role") == "locale_reference"),
        "owner_review_required_files": sorted(item["path"] for item in android_files if item.get("owner_review_required")),
        "warnings": warnings,
    }


def _android_resource_type_counts(path: Path) -> tuple[Counter[str], list[str]]:
    counts: Counter[str] = Counter()
    try:
        root = ElementTree.fromstring(path.read_text(encoding="utf-8"))
    except (OSError, ElementTree.ParseError) as exc:
        return counts, [f"resource type counts unavailable: {exc.__class__.__name__}"]
    for child in root:
        tag = child.tag.split("}", 1)[-1]
        if tag in ANDROID_RESOURCE_TYPES:
            counts[tag] += 1
    return counts, []


def _android_qualifiers(android_files: list[dict[str, Any]]) -> list[str]:
    values: set[str] = set()
    for item in android_files:
        qualifiers = item.get("android_qualifiers", {})
        for qualifier in qualifiers.get("non_locale") or []:
            values.add(qualifier)
    return sorted(values)


def _summary_warnings(inspection: dict[str, Any], android_summary: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if inspection.get("skipped_path_count", 0):
        warnings.append(f"{inspection['skipped_path_count']} paths could not be inspected")
    if android_summary.get("owner_review_required_files"):
        warnings.append("some Android resource files require owner review before generation")
    if android_summary.get("warnings"):
        warnings.append("Android routing or resource counting warnings were reported")
    return warnings
