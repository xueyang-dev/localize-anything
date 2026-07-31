from __future__ import annotations

import os
from pathlib import Path

from .android_strings_adapter import is_android_strings_path
from .ios_strings_adapter import is_ios_strings_path
from .xcstrings_adapter import is_xcstrings_path


IGNORED_DIRECTORIES = {
    ".git",
    ".localize-anything",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
}


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
    if is_xcstrings_path(project, path):
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


def discover_resources(project: Path) -> list[dict[str, str]]:
    project = resolve_project(project)
    files = []
    for root, directories, names in os.walk(project):
        directories[:] = [name for name in directories if name not in IGNORED_DIRECTORIES]
        for name in names:
            path = Path(root) / name
            adapter = detect_adapter(project, path)
            if adapter:
                files.append({"path": relative_path(project, path), "adapter": adapter})
    return sorted(files, key=lambda item: item["path"])


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
