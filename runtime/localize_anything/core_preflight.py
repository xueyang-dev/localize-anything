from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path
from typing import Any

from .android_strings_adapter import is_android_strings_path
from .ios_strings_adapter import is_ios_strings_path


CORE_PHASES = ["scan", "glossary", "check", "review", "report"]
SUPPORTED_CAPABILITIES = ["detect", "inventory", "extract", "validate", "review_packet"]
UNSUPPORTED_CAPABILITIES = ["inventory", "extract", "validate", "review_packet"]
IGNORED_DIRECTORIES = {
    ".git",
    ".localize-anything",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
}
SWIFT_CATALOG_MARKERS = (
    "struct Strings",
    "class Strings",
    "extension Strings",
    "enum AppLanguage",
    "AppLanguage",
    "CFBundleLocalizations",
)


def resolve_project(project_root: Path) -> Path:
    project = project_root.resolve()
    if not project.is_dir():
        raise ValueError(f"Project directory does not exist: {project}")
    return project


def resolve_project_file(project: Path, name: str) -> Path:
    path = (project / name).resolve()
    if not path.is_relative_to(project):
        raise ValueError(f"Project files must stay inside the project root: {name}")
    return path


def relative_path(project: Path, path: Path) -> str:
    return path.resolve().relative_to(project).as_posix()


def detect_adapter(project: Path, path: Path) -> str | None:
    if path.suffix.lower() == ".xcstrings":
        return "xcstrings"
    if is_android_strings_path(project, path):
        return "android"
    if is_ios_strings_path(project, path):
        return "ios"
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in {".po", ".pot"}:
        return "gettext"
    if suffix in {".yaml", ".yml", ".toml"}:
        return "structured"
    if suffix in {".xlf", ".xliff"}:
        return "xliff"
    return None


def describe_source(project: Path, source: str) -> dict[str, Any]:
    project = resolve_project(project)
    path = resolve_project_file(project, source)
    source_rel = relative_path(project, path)
    if not path.exists():
        return _unsupported_surface(
            source_rel,
            "unknown",
            "missing_source",
            f"Declared source path does not exist: {source}",
            [],
        )
    if path.is_dir():
        candidates = [
            relative_path(project, item)
            for item in _iter_files(path)
            if item.suffix.lower() == ".swift" and _swift_catalog_evidence(item)
        ]
        if candidates:
            return _unsupported_surface(
                source_rel,
                "code_embedded_catalog",
                "swift_typed_catalog_candidate",
                "Swift typed catalogs require an explicit project-local, syntax-aware adapter before extraction or review.",
                [f"candidate_file:{item}" for item in candidates[:10]],
            )
        return _unsupported_surface(
            source_rel,
            "unknown_directory",
            "directory_source",
            "Directory sources require an explicit adapter or supported resource files.",
            [],
        )
    adapter = detect_adapter(project, path)
    if adapter:
        return _supported_surface(source_rel, adapter)
    if path.suffix.lower() == ".swift":
        return _unsupported_swift_surface(project, path, declared=True)
    return _unsupported_surface(
        source_rel,
        "unknown",
        "unsupported_source",
        "No core adapter can inventory, extract, validate, and prepare review segments for this source.",
        [],
    )


def discover_resources(project: Path) -> list[dict[str, str]]:
    project = resolve_project(project)
    files = []
    for path in _iter_files(project):
        adapter = detect_adapter(project, path)
        if adapter:
            files.append({"path": relative_path(project, path), "adapter": adapter})
    return sorted(files, key=lambda item: item["path"])


def discover_surfaces(project: Path) -> list[dict[str, Any]]:
    project = resolve_project(project)
    surfaces = []
    for path in _iter_files(project):
        adapter = detect_adapter(project, path)
        if adapter:
            surfaces.append(_supported_surface(relative_path(project, path), adapter))
        elif path.suffix.lower() == ".swift":
            swift_surface = _unsupported_swift_surface(project, path, declared=False)
            if swift_surface["evidence"]:
                surfaces.append(swift_surface)
    return sorted(surfaces, key=lambda item: item["path"])


def select_resources(project: Path, source_files: list[str]) -> list[dict[str, str]]:
    project = resolve_project(project)
    selected = []
    for source in source_files:
        path = resolve_project_file(project, source)
        if not path.is_file():
            raise ValueError(f"Declared source file does not exist: {source}")
        adapter = detect_adapter(project, path)
        if not adapter:
            raise ValueError(f"Unsupported source file for the minimal core: {source}")
        selected.append({"path": relative_path(project, path), "adapter": adapter})
    return selected


def _iter_files(root: Path) -> Iterator[Path]:
    for current, directories, names in os.walk(root):
        directories[:] = [name for name in directories if name not in IGNORED_DIRECTORIES]
        for name in names:
            yield Path(current) / name


def _supported_surface(path: str, adapter: str) -> dict[str, Any]:
    return {
        "path": path,
        "surface_type": "resource_catalog",
        "status": "supported",
        "adapter": adapter,
        "capabilities": SUPPORTED_CAPABILITIES,
        "missing_capabilities": [],
        "allowed_phases": CORE_PHASES,
        "evidence": [f"core_adapter:{adapter}"],
    }


def _unsupported_swift_surface(project: Path, path: Path, *, declared: bool) -> dict[str, Any]:
    evidence = _swift_catalog_evidence(path)
    surface_type = "code_embedded_catalog" if evidence else "source_code"
    reason = (
        "Swift typed catalogs require an explicit project-local, syntax-aware adapter before extraction or review."
        if evidence
        else "Swift source files are not core localization resources."
    )
    if declared and not evidence:
        evidence = [f"extension:{path.suffix.lower()}"]
    return _unsupported_surface(
        relative_path(project, path),
        surface_type,
        "swift_typed_catalog_candidate" if surface_type == "code_embedded_catalog" else "swift_source",
        reason,
        evidence,
    )


def _unsupported_surface(
    path: str,
    surface_type: str,
    reason_code: str,
    reason: str,
    evidence: list[str],
) -> dict[str, Any]:
    return {
        "path": path,
        "surface_type": surface_type,
        "status": "unsupported",
        "adapter": None,
        "capabilities": ["detect"],
        "missing_capabilities": UNSUPPORTED_CAPABILITIES,
        "allowed_phases": ["scan"],
        "reason_code": reason_code,
        "reason": reason,
        "evidence": evidence,
    }


def _swift_catalog_evidence(path: Path) -> list[str]:
    evidence = []
    if path.name.startswith("Strings+"):
        evidence.append(f"filename:{path.name}")
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            text = handle.read(100_000)
    except OSError:
        return evidence
    for marker in SWIFT_CATALOG_MARKERS:
        if marker in text:
            evidence.append(f"contains:{marker}")
    return evidence
