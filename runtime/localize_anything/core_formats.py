from __future__ import annotations

from pathlib import Path
from typing import Any

from .android_strings_adapter import extract_segments as extract_android
from .android_strings_adapter import target_resource_path, validate_pair as validate_android
from .gettext_adapter import extract_segments as extract_gettext, parse_po
from .gettext_adapter import validate_pair as validate_gettext
from .ios_strings_adapter import extract_segments as extract_ios
from .ios_strings_adapter import validate_pair as validate_ios
from .json_adapter import extract_segments as extract_json
from .json_adapter import validate_pair as validate_json
from .structured_adapter import extract_segments as extract_structured
from .structured_adapter import validate_pair as validate_structured
from .xcstrings_adapter import extract_segments as extract_xcstrings
from .xcstrings_adapter import locale_to_catalog_language, validate_pair as validate_xcstrings
from .xliff_adapter import extract_segments as extract_xliff
from .xliff_adapter import validate_pair as validate_xliff


def extract_source(adapter: str, path: Path, locale: str, logical_path: str) -> list[dict[str, Any]]:
    if adapter == "android":
        return extract_android(path, locale, logical_path)
    if adapter == "gettext":
        return extract_gettext(path, locale, logical_path)
    if adapter == "ios":
        return extract_ios(path, locale, logical_path)
    if adapter == "json":
        return extract_json(path, locale, logical_path)
    if adapter == "structured":
        return extract_structured(path, locale, logical_path)
    if adapter == "xcstrings":
        return extract_xcstrings(path, locale, logical_path)
    if adapter == "xliff":
        return extract_xliff(path, locale, logical_path)
    raise ValueError(f"Unsupported adapter: {adapter}")


def extract_target(
    adapter: str,
    path: Path,
    target_locale: str,
    logical_path: str,
) -> list[dict[str, Any]]:
    if adapter == "gettext":
        segments = extract_source(adapter, path, target_locale, logical_path)
        values = [
            "\n".join(field.value for field in entry.msgstr_fields())
            for entry in parse_po(path).entries
            if entry.msgid
        ]
        for segment, value in zip(segments, values, strict=True):
            segment["catalog_source"] = segment["source"]
            segment["source"] = value
        return segments
    if adapter == "xcstrings":
        return extract_xcstrings(
            path,
            target_locale,
            logical_path,
            catalog_language=locale_to_catalog_language(target_locale),
        )
    if adapter == "xliff":
        segments = extract_source(adapter, path, target_locale, logical_path)
        for segment in segments:
            segment["source"] = str(segment.get("existing_target", ""))
        return segments
    return extract_source(adapter, path, target_locale, logical_path)


def validate_resource_pair(
    adapter: str,
    source: Path,
    target: Path,
    target_locale: str,
) -> dict[str, Any]:
    if adapter == "android":
        return validate_android(source, target)
    if adapter == "gettext":
        return validate_gettext(source, target)
    if adapter == "ios":
        return validate_ios(source, target)
    if adapter == "json":
        return validate_json(source, target)
    if adapter == "structured":
        return validate_structured(source, target)
    if adapter == "xcstrings":
        return validate_xcstrings(source, target, target_locale)
    if adapter == "xliff":
        return validate_xliff(source, target)
    raise ValueError(f"Unsupported adapter: {adapter}")


def discover_android_merged_resources(
    project_root: Path,
    merged_resources: Path | None = None,
    build_variant: str | None = None,
) -> list[Path]:
    project_root = project_root.resolve()
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


def android_overlay_destination(
    project_root: Path,
    source_file: str,
    target_locale: str,
    output_name: str,
) -> Path:
    target = target_resource_path(project_root / source_file, target_locale, project_root)
    return target.with_name(output_name)
