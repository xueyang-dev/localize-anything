from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .android_strings_adapter import stage_rebuild as stage_android_strings
from .gettext_adapter import rebuild as rebuild_po
from .ios_strings_adapter import stage_rebuild as stage_ios_strings
from .json_adapter import rebuild as rebuild_json
from .markup_adapter import rebuild as rebuild_markup
from .project import inspect_project
from .structured_adapter import rebuild as rebuild_structured
from .subtitle_adapter import rebuild as rebuild_subtitles
from .tabular_adapter import rebuild as rebuild_tabular
from .word_adapter import rebuild as rebuild_word
from .xcstrings_adapter import stage_rebuild as stage_xcstrings
from .xliff_adapter import rebuild as rebuild_xliff


def stage_generated(
    project_root: Path,
    generated_segments: list[dict[str, Any]],
    staging_dir: Path,
    source_locale: str,
    target_locale: str,
    source_files: list[str] | None = None,
    preserve_target_only: bool = False,
) -> dict[str, Any]:
    inspection = inspect_project(project_root)
    inventory = {item["path"]: item for item in inspection["supported_files"]}
    selected_files = source_files or sorted(_source_paths(generated_segments))
    unknown = sorted(path for path in selected_files if path not in inventory)
    if unknown:
        raise ValueError(f"Source files were not found or are unsupported: {', '.join(unknown)}")

    outputs: list[dict[str, Any]] = []
    for source_file in selected_files:
        source_segments = [segment for segment in generated_segments if _normal_source_path(segment) == source_file]
        if not source_segments:
            raise ValueError(f"No generated segments found for source file: {source_file}")
        source_path = project_root / source_file
        adapter = inventory[source_file]["adapter"]
        outputs.append(
            _stage_one(
                adapter,
                source_path,
                source_file,
                source_segments,
                staging_dir,
                source_locale,
                target_locale,
                project_root,
                preserve_target_only,
            )
        )

    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "status": "pass",
        "summary": {"output_count": len(outputs), "source_file_count": len(selected_files)},
        "source_locale": source_locale,
        "target_locale": target_locale,
        "staging_dir": staging_dir.as_posix(),
        "outputs": outputs,
    }


def _stage_one(
    adapter: str,
    source_path: Path,
    source_file: str,
    segments: list[dict[str, Any]],
    staging_dir: Path,
    source_locale: str,
    target_locale: str,
    project_root: Path,
    preserve_target_only: bool,
) -> dict[str, Any]:
    if adapter == "core.android-strings":
        result = stage_android_strings(source_path, segments, staging_dir, target_locale, project_root, preserve_target_only)
        return _output_record(adapter, source_file, result["destination"], result["output"], len(segments), result)
    if adapter == "core.ios-strings":
        result = stage_ios_strings(source_path, segments, staging_dir, target_locale, project_root)
        return _output_record(adapter, source_file, result["destination"], result["output"], len(segments), result)
    if adapter == "core.xcstrings":
        result = stage_xcstrings(source_path, segments, staging_dir, target_locale, project_root)
        return _output_record(adapter, source_file, result["destination"], result["output"], len(segments), result)

    destination = _target_path(Path(source_file), source_locale, target_locale, adapter)
    output = staging_dir / destination
    output.parent.mkdir(parents=True, exist_ok=True)
    if adapter == "core.json-locale":
        rebuild_json(source_path, segments, output)
    elif adapter == "core.yaml-toml":
        rebuild_structured(source_path, segments, output, _structured_format(source_path))
    elif adapter == "core.tabular":
        rebuild_tabular(source_path, segments, output)
    elif adapter == "core.word-document":
        rebuild_word(source_path, segments, output)
    elif adapter == "core.markup":
        rebuild_markup(source_path, segments, output)
    elif adapter == "core.subtitles":
        rebuild_subtitles(source_path, segments, output)
    elif adapter == "core.xliff":
        rebuild_xliff(source_path, segments, output, target_locale)
    elif adapter == "core.gettext-po":
        rebuild_po(source_path, segments, output, target_locale)
    else:
        raise ValueError(f"Adapter does not support unified staging: {adapter}")
    return _output_record(adapter, source_file, destination.as_posix(), output.as_posix(), len(segments), {})


def _target_path(source_file: Path, source_locale: str, target_locale: str, adapter: str) -> Path:
    parts = list(source_file.parts)
    source_tokens = _locale_tokens(source_locale)
    target_token = _target_token(target_locale, adapter)
    for index, part in enumerate(parts):
        if part in source_tokens:
            parts[index] = target_token
            return Path(*parts)

    stem = source_file.stem
    suffix = source_file.suffix
    for token in source_tokens:
        if stem == token:
            return source_file.with_name(f"{target_token}{suffix}")
        for separator in (".", "-", "_"):
            marker = f"{separator}{token}"
            if stem.endswith(marker):
                return source_file.with_name(f"{stem[: -len(marker)]}{separator}{target_token}{suffix}")
    return source_file.with_name(f"{stem}.{target_token}{suffix}")


def _locale_tokens(locale: str) -> set[str]:
    normalized = locale.replace("_", "-")
    language = normalized.split("-", 1)[0]
    return {
        normalized,
        normalized.lower(),
        normalized.replace("-", "_"),
        normalized.replace("-", "_").lower(),
        language,
        language.lower(),
    }


def _target_token(locale: str, adapter: str) -> str:
    if adapter == "core.gettext-po":
        return locale.replace("-", "_")
    return locale


def _structured_format(path: Path) -> str:
    return "toml" if path.suffix.lower() == ".toml" else "yaml"


def _normal_source_path(segment: dict[str, Any]) -> str:
    return str(segment.get("source_path", "")).replace("\\", "/")


def _source_paths(segments: list[dict[str, Any]]) -> set[str]:
    return {path for path in (_normal_source_path(segment) for segment in segments) if path}


def _output_record(
    adapter: str,
    source_file: str,
    destination: str,
    output: str,
    segment_count: int,
    extra: dict[str, Any],
) -> dict[str, Any]:
    record = {
        "adapter": adapter,
        "source": source_file,
        "destination": destination,
        "output": output,
        "segment_count": segment_count,
        "written": True,
    }
    for key, value in extra.items():
        if key not in {"protocol_version", "adapter", "output", "destination", "written"}:
            record[key] = value
    return record
