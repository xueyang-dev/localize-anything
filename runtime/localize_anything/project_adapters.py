from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .contracts import ADAPTER_ID_RE, validate_adapter_manifest
from .io_utils import write_text_atomic


PROJECT_ADAPTER_DIRECTORY = ".localize-anything/adapters"
ADAPTER_DESCRIPTOR = "adapter.json"
PROJECT_ADAPTER_EXECUTION_MODE = "runtime_project_local_adapter"
ADAPTER_PAYLOAD_SYMLINK_CODE = "adapter_payload_symlink"
ADAPTER_PAYLOAD_SPECIAL_FILE_CODE = "adapter_payload_special_file"
ALLOWED_PROJECT_CAPABILITIES = {"detect", "inventory", "extract", "validate_source"}
ALLOWED_PROJECT_PERMISSIONS = {"read_project", "execute"}
ALLOWED_PROJECT_ROUND_TRIP = {"inspect_only", "extract_only"}
READ_ONLY_PHASES = ("detect", "inventory", "extract", "validate_source")
SHELL_META_RE = re.compile(r"[;&|<>`$]")
MAX_STDOUT_BYTES = 8_000_000
MAX_STDERR_BYTES = 16_000
DEFAULT_TIMEOUT_SECONDS = 5.0


class ProjectAdapterError(ValueError):
    def __init__(self, code: str, message: str, *, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.evidence = evidence or {}

    def blocker(self) -> dict[str, Any]:
        return {
            "severity": "blocking",
            "kind": self.code,
            "category": self.code,
            "message": str(self),
            "evidence": self.evidence,
        }


def discover_project_adapters(project: Path) -> list[dict[str, Any]]:
    base = _adapter_base(project)
    if not base.exists():
        return []
    try:
        base_resolved = _safe_resolve(base, _project(project))
    except ProjectAdapterError as exc:
        return [{"id": "", "status": "invalid", "error_code": exc.code, "message": str(exc)}]
    candidates = []
    for child in sorted(base.iterdir(), key=lambda item: item.name):
        if child.name.startswith("."):
            continue
        try:
            if not ADAPTER_ID_RE.fullmatch(child.name):
                raise ProjectAdapterError("descriptor_invalid", f"Invalid project-local adapter id: {child.name}")
            root = _safe_resolve(child, base_resolved)
            descriptor = _read_descriptor(root / ADAPTER_DESCRIPTOR)
            candidates.append(
                {
                    "id": str(descriptor.get("id") or child.name),
                    "declared_id": str(descriptor.get("id") or ""),
                    "status": "candidate",
                    "adapter_root": _relative(_project(project), root),
                    "descriptor": _relative(_project(project), root / ADAPTER_DESCRIPTOR),
                    "version": str(descriptor.get("version") or ""),
                    "round_trip_level": str(descriptor.get("round_trip_level") or ""),
                    "trust": str(descriptor.get("trust") or ""),
                    "source_scope": descriptor.get("source_scope", {}),
                }
            )
        except ProjectAdapterError as exc:
            candidates.append({"id": child.name, "status": "invalid", "error_code": exc.code, "message": str(exc)})
    return candidates


def load_project_adapter(project: Path, adapter_id: str) -> dict[str, Any]:
    project = _project(project)
    if not ADAPTER_ID_RE.fullmatch(adapter_id):
        raise ProjectAdapterError("descriptor_invalid", f"Invalid project-local adapter id: {adapter_id!r}")
    base_path = _adapter_base(project)
    if not base_path.exists():
        raise ProjectAdapterError("descriptor_invalid", "Project-local adapter directory does not exist")
    base = _safe_resolve(base_path, project)
    entry_path = base / adapter_id
    if entry_path.is_symlink():
        raise _payload_symlink_error(adapter_id, "", f"{PROJECT_ADAPTER_DIRECTORY}/{adapter_id}")
    root = _safe_resolve(entry_path, base)
    if not root.is_dir():
        raise ProjectAdapterError("descriptor_invalid", f"Project-local adapter does not exist: {adapter_id}")
    descriptor_path = _safe_resolve(root / ADAPTER_DESCRIPTOR, root)
    descriptor = _read_descriptor(descriptor_path)
    _validate_project_descriptor(project, root, descriptor_path, descriptor, adapter_id)
    _adapter_payload_files(project, root, adapter_id)
    entrypoints = {
        phase: _validated_entrypoint(project, root, descriptor, phase)
        for phase in _required_phases(descriptor)
    }
    descriptor_sha = _sha256(descriptor_path)
    entrypoint_shas = sorted({_sha256(entrypoint["script_path"]) for entrypoint in entrypoints.values()})
    return {
        "id": adapter_id,
        "version": str(descriptor["version"]),
        "name": str(descriptor["name"]),
        "adapter_type": str(descriptor.get("adapter_type", "scripted")),
        "trust": str(descriptor["trust"]),
        "round_trip_level": str(descriptor["round_trip_level"]),
        "capabilities": list(descriptor["capabilities"]),
        "permissions": list(descriptor["permissions"]),
        "runtime": descriptor["runtime"],
        "source_scope": descriptor["source_scope"],
        "provenance": descriptor.get("provenance") or descriptor.get("maintainer") or "",
        "notes": descriptor.get("notes", []),
        "limitations": descriptor.get("limitations", []),
        "project_root": project,
        "adapter_root": root,
        "adapter_root_relative": _relative(project, root),
        "descriptor_path": descriptor_path,
        "descriptor_path_relative": _relative(project, descriptor_path),
        "descriptor_sha256": descriptor_sha,
        "entrypoints": entrypoints,
        "entrypoint_sha256": entrypoint_shas[0],
    }


def adapter_matches_source(project: Path, adapter: dict[str, Any], source: str) -> bool:
    project = _project(project)
    source_path = (project / source).resolve()
    if not source_path.is_relative_to(project):
        return False
    source_rel = source_path.relative_to(project).as_posix()
    paths = adapter.get("source_scope", {}).get("paths", [])
    if not paths:
        return True
    return any(source_rel == item or source_rel.startswith(f"{item.rstrip('/')}/") for item in paths if isinstance(item, str))


def execute_extract_only_check(
    project: Path,
    state_dir: Path,
    adapter: dict[str, Any],
    *,
    source: str,
    target: str,
    source_locale: str,
    target_locale: str,
) -> dict[str, Any]:
    payload = {
        "project_root": _project(project).as_posix(),
        "source": source,
        "target": target,
        "source_locale": source_locale,
        "target_locale": target_locale,
    }
    run_artifacts = []
    try:
        detect = run_project_adapter_phase(project, state_dir, adapter, "detect", payload)
        run_artifacts.append(detect["_run"])
        if detect.get("detected") is not True:
            raise ProjectAdapterError("adapter_schema_violation", "Project-local adapter did not detect the declared source")
        inventory = run_project_adapter_phase(project, state_dir, adapter, "inventory", payload)
        run_artifacts.append(inventory["_run"])
        extracted = run_project_adapter_phase(project, state_dir, adapter, "extract", payload)
        run_artifacts.append(extracted["_run"])
        validation = run_project_adapter_phase(project, state_dir, adapter, "validate_source", payload)
        run_artifacts.append(validation["_run"])
    except ProjectAdapterError as exc:
        return {
            "status": "fail",
            "items": [exc.blocker()],
            "run_artifacts": run_artifacts + list(exc.evidence.get("run_artifacts", [])),
        }

    source_validation = validation.get("validation", {"status": validation.get("status", "pass"), "items": validation.get("items", [])})
    return {
        "status": "pass" if source_validation.get("status") != "fail" else "fail",
        "inventory": inventory["items"],
        "source_segments": extracted["source_segments"],
        "target_segments": extracted["target_segments"],
        "source_validation": source_validation,
        "run_artifacts": run_artifacts,
    }


def run_project_adapter_phase(
    project: Path,
    state_dir: Path,
    adapter: dict[str, Any],
    phase: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if phase not in READ_ONLY_PHASES:
        raise ProjectAdapterError("capability_not_allowed", f"Project-local adapter phase is not allowed: {phase}")
    entrypoint = adapter["entrypoints"].get(phase)
    if not entrypoint:
        raise ProjectAdapterError("entrypoint_missing", f"Project-local adapter has no entrypoint for {phase}")

    command = _runtime_command(entrypoint["command"])
    stdin_payload = json.dumps(
        {
            "protocol_version": PROTOCOL_VERSION,
            "phase": phase,
            "readonly": True,
            **payload,
        },
        ensure_ascii=False,
    )
    started = time.monotonic()
    run_info = _run_info(adapter, phase, command)
    readonly_snapshot = _readonly_project_snapshot(_project(project))
    with tempfile.TemporaryDirectory(prefix="localize-adapter-") as tmp:
        tmp_path = Path(tmp)
        stdout_path = tmp_path / "stdout.json"
        stderr_path = tmp_path / "stderr.txt"
        try:
            with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
                completed = subprocess.run(
                    command,
                    cwd=adapter["adapter_root"],
                    input=stdin_payload,
                    text=True,
                    encoding="utf-8",
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    timeout=DEFAULT_TIMEOUT_SECONDS,
                    env={"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": tmp},
                )
        except subprocess.TimeoutExpired as exc:
            run_info.update(_output_sizes(stdout_path, stderr_path))
            run_info.update({"status": "fail", "error_code": "adapter_timeout", "duration_ms": _duration_ms(started), "exit_code": None})
            _attach_readonly_violations(project, run_info, readonly_snapshot)
            artifact = _write_run_artifact(state_dir, adapter, phase, run_info, _read_text_prefix(stderr_path, MAX_STDERR_BYTES))
            raise ProjectAdapterError("adapter_timeout", f"Project-local adapter timed out during {phase}", evidence={"run_artifacts": [artifact]}) from exc

        run_info.update({"duration_ms": _duration_ms(started), "exit_code": completed.returncode})
        run_info.update(_output_sizes(stdout_path, stderr_path))
        stderr = _read_text_prefix(stderr_path, MAX_STDERR_BYTES)
        readonly_violations = _readonly_violations(_project(project), readonly_snapshot)
        if readonly_violations:
            run_info.update({"status": "fail", "error_code": "capability_not_allowed", "readonly_violations": readonly_violations})
            artifact = _write_run_artifact(state_dir, adapter, phase, run_info, stderr)
            raise ProjectAdapterError(
                "capability_not_allowed",
                f"Project-local adapter modified read-only project files during {phase}",
                evidence={"readonly_violations": readonly_violations, "run_artifacts": [artifact]},
            )
        if run_info["stdout_bytes"] > MAX_STDOUT_BYTES:
            run_info.update({"status": "fail", "error_code": "adapter_output_too_large"})
            artifact = _write_run_artifact(state_dir, adapter, phase, run_info, stderr)
            raise ProjectAdapterError(
                "adapter_output_too_large",
                f"Project-local adapter output exceeded the limit during {phase}: {run_info['stdout_bytes']} bytes > {MAX_STDOUT_BYTES} bytes",
                evidence={"stdout_bytes": run_info["stdout_bytes"], "max_stdout_bytes": MAX_STDOUT_BYTES, "run_artifacts": [artifact]},
            )
        if completed.returncode != 0:
            run_info.update({"status": "fail", "error_code": "adapter_nonzero_exit"})
            artifact = _write_run_artifact(state_dir, adapter, phase, run_info, stderr)
            raise ProjectAdapterError("adapter_nonzero_exit", f"Project-local adapter exited nonzero during {phase}", evidence={"run_artifacts": [artifact]})
        try:
            value = json.loads(stdout_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            run_info.update({"status": "fail", "error_code": "adapter_invalid_json"})
            artifact = _write_run_artifact(state_dir, adapter, phase, run_info, stderr)
            raise ProjectAdapterError("adapter_invalid_json", f"Project-local adapter returned invalid JSON during {phase}", evidence={"run_artifacts": [artifact]}) from exc
    errors = _validate_phase_output(phase, value)
    if errors:
        run_info.update({"status": "fail", "error_code": "adapter_schema_violation", "schema_errors": errors})
        artifact = _write_run_artifact(state_dir, adapter, phase, run_info, stderr)
        raise ProjectAdapterError("adapter_schema_violation", f"Project-local adapter output schema failed during {phase}", evidence={"errors": errors, "run_artifacts": [artifact]})
    payload_sha256 = _json_sha256(value)
    if value.get("status") == "fail":
        adapter_code = _bounded_string(value.get("code"), 200)
        adapter_reason = _bounded_string(value.get("reason") or value.get("error"), 4000)
        run_info.update(
            {
                "status": "fail",
                "error_code": "adapter_phase_failed",
                "payload_sha256": payload_sha256,
                "adapter_error_code": adapter_code,
                "adapter_error_reason": adapter_reason,
            }
        )
        artifact = _write_run_artifact(state_dir, adapter, phase, run_info, stderr)
        message = f"Project-local adapter declared failure during {phase}"
        if adapter_reason:
            message = f"{message}: {adapter_reason}"
        raise ProjectAdapterError(
            "adapter_phase_failed",
            message,
            evidence={
                "phase": phase,
                "adapter_id": adapter["id"],
                "adapter_version": adapter["version"],
                "execution_mode": PROJECT_ADAPTER_EXECUTION_MODE,
                "descriptor_sha256": adapter["descriptor_sha256"],
                "payload_sha256": payload_sha256,
                "exit_code": run_info["exit_code"],
                "adapter_code": adapter_code,
                "adapter_reason": adapter_reason,
                "run_artifacts": [artifact],
            },
        )
    run_info.update({"status": "pass", "payload_sha256": payload_sha256})
    artifact = _write_run_artifact(state_dir, adapter, phase, run_info, stderr)
    value["_run"] = artifact
    return value


def adapter_fingerprints(adapter: dict[str, Any]) -> list[dict[str, Any]]:
    project = adapter["project_root"]
    fingerprints = [
        {
            "role": "adapter_descriptor",
            "path": adapter["descriptor_path_relative"],
            "size": adapter["descriptor_path"].stat().st_size,
            "sha256": adapter["descriptor_sha256"],
        }
    ]
    seen = {adapter["descriptor_path"]}
    entrypoint_paths = {entrypoint["script_path"] for entrypoint in adapter["entrypoints"].values()}
    for relative, path in _adapter_payload_files(project, adapter["adapter_root"], adapter["id"]):
        if path in seen:
            continue
        seen.add(path)
        fingerprints.append(
            {
                "role": "adapter_entrypoint" if path in entrypoint_paths else "adapter_file",
                "path": _relative(project, path),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return fingerprints


def adapter_summary(adapter: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": adapter["id"],
        "version": adapter["version"],
        "adapter_type": adapter["adapter_type"],
        "trust": adapter["trust"],
        "round_trip_level": adapter["round_trip_level"],
        "capabilities": adapter["capabilities"],
        "permissions": adapter["permissions"],
        "checksum": adapter["entrypoint_sha256"],
        "descriptor_sha256": adapter["descriptor_sha256"],
        "adapter_root": adapter["adapter_root_relative"],
        "descriptor": adapter["descriptor_path_relative"],
        "provenance": adapter["provenance"],
        "limitations": adapter["limitations"],
    }


def _validate_project_descriptor(project: Path, root: Path, descriptor_path: Path, descriptor: dict[str, Any], adapter_id: str) -> None:
    errors = validate_adapter_manifest(descriptor_path)
    if errors:
        raise ProjectAdapterError("descriptor_invalid", "; ".join(errors))
    if descriptor.get("id") != adapter_id:
        raise ProjectAdapterError("descriptor_invalid", f"Project-local adapter id mismatch: {descriptor.get('id')!r} != {adapter_id!r}")
    if descriptor.get("trust") != "project":
        raise ProjectAdapterError("descriptor_invalid", "Project-local adapter trust must be 'project'")
    if descriptor.get("adapter_type") != "scripted":
        raise ProjectAdapterError("descriptor_invalid", "Project-local adapter adapter_type must be 'scripted'")
    if descriptor.get("round_trip_level") not in ALLOWED_PROJECT_ROUND_TRIP:
        raise ProjectAdapterError("capability_not_allowed", "Project-local adapter capability must be inspect_only or extract_only")
    capabilities = set(descriptor.get("capabilities", []))
    if capabilities - ALLOWED_PROJECT_CAPABILITIES:
        raise ProjectAdapterError("capability_not_allowed", "Project-local adapter overclaims write or round-trip capabilities")
    if descriptor.get("round_trip_level") == "inspect_only" and "extract" in capabilities:
        raise ProjectAdapterError("capability_not_allowed", "Inspect-only project-local adapters must not claim extraction")
    if set(descriptor.get("permissions", [])) - ALLOWED_PROJECT_PERMISSIONS:
        raise ProjectAdapterError("capability_not_allowed", "Project-local adapter permissions must be read-only plus execute")
    if not isinstance(descriptor.get("source_scope"), dict) or not isinstance(descriptor["source_scope"].get("paths"), list):
        raise ProjectAdapterError("descriptor_invalid", "Project-local adapter requires source_scope.paths")
    for source in descriptor["source_scope"]["paths"]:
        if not isinstance(source, str) or source.startswith("/") or ".." in Path(source).parts:
            raise ProjectAdapterError("path_escape", f"Invalid project-local adapter source scope path: {source!r}")
        _safe_resolve(project / source, project, must_exist=False)
    checksum = descriptor.get("checksum")
    if not isinstance(checksum, dict) or checksum.get("type") != "sha256" or not isinstance(checksum.get("value"), str):
        raise ProjectAdapterError("descriptor_invalid", "Project-local adapter requires checksum.type=sha256 and checksum.value")
    if not re.fullmatch(r"[0-9a-f]{64}", checksum["value"]):
        raise ProjectAdapterError("descriptor_invalid", "Project-local adapter checksum must be a lowercase SHA-256 hex digest")
    if not descriptor.get("provenance") and not descriptor.get("maintainer"):
        raise ProjectAdapterError("descriptor_invalid", "Project-local adapter requires provenance or maintainer")
    for key in ("notes", "limitations"):
        if key in descriptor and (not isinstance(descriptor[key], list) or any(not isinstance(item, str) for item in descriptor[key])):
            raise ProjectAdapterError("descriptor_invalid", f"Project-local adapter {key} must be a string list")
    for phase in _required_phases(descriptor):
        _validated_entrypoint(project, root, descriptor, phase)


def _required_phases(descriptor: dict[str, Any]) -> tuple[str, ...]:
    if descriptor.get("round_trip_level") == "inspect_only":
        return ("detect", "inventory", "validate_source")
    return READ_ONLY_PHASES


def _validated_entrypoint(project: Path, root: Path, descriptor: dict[str, Any], phase: str) -> dict[str, Any]:
    entrypoints = descriptor.get("entrypoints", {})
    command = entrypoints.get(phase)
    if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        raise ProjectAdapterError("entrypoint_missing", f"Project-local adapter entrypoint is missing for {phase}")
    if any(SHELL_META_RE.search(part) for part in command):
        raise ProjectAdapterError("entrypoint_missing", f"Project-local adapter entrypoint contains shell metacharacters for {phase}")
    runtime = descriptor.get("runtime", {})
    if runtime.get("type") != "python":
        raise ProjectAdapterError("undeclared_dependency", "Project-local adapter v1 only executes declared Python adapters")
    if command[0] not in {"python", "python3"}:
        raise ProjectAdapterError("undeclared_dependency", f"Unsupported project-local adapter executable: {command[0]}")
    if len(command) < 2:
        raise ProjectAdapterError("entrypoint_missing", f"Project-local adapter Python entrypoint is missing for {phase}")
    script = Path(command[1])
    if script.is_absolute() or ".." in script.parts:
        raise ProjectAdapterError("path_escape", f"Project-local adapter entrypoint escapes adapter root: {command[1]}")
    script_path = _safe_resolve(root / script, root)
    if not script_path.is_file():
        raise ProjectAdapterError("entrypoint_missing", f"Project-local adapter entrypoint file is missing: {command[1]}")
    expected = descriptor["checksum"]["value"]
    actual = _sha256(script_path)
    if actual != expected:
        raise ProjectAdapterError("checksum_mismatch", f"Project-local adapter checksum mismatch for {command[1]}")
    return {"command": command, "script_path": script_path, "script_path_relative": _relative(project, script_path)}


def _runtime_command(command: list[str]) -> list[str]:
    return [sys.executable if command[0] in {"python", "python3"} else command[0], *command[1:]]


def _validate_phase_output(phase: str, value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["root must be an object"]
    expected_schema = f"localize-anything-project-adapter-{phase.replace('_', '-')}-result-v1"
    errors = []
    if value.get("schema") != expected_schema:
        errors.append(f"schema must be {expected_schema!r}")
    if value.get("status") not in {"pass", "fail"}:
        errors.append("status must be pass or fail")
    if phase == "detect" and not isinstance(value.get("detected"), bool):
        errors.append("detected must be a boolean")
    if phase == "inventory" and not isinstance(value.get("items"), list):
        errors.append("items must be a list")
    if phase == "extract":
        if not isinstance(value.get("source_segments"), list):
            errors.append("source_segments must be a list")
        if not isinstance(value.get("target_segments"), list):
            errors.append("target_segments must be a list")
    if phase == "validate_source":
        validation = value.get("validation")
        if not isinstance(validation, dict) or validation.get("status") not in {"pass", "pass_with_warnings", "fail"} or not isinstance(validation.get("items"), list):
            errors.append("validation must contain status and items")
    return errors


def _output_sizes(stdout_path: Path, stderr_path: Path) -> dict[str, Any]:
    stderr_bytes = _file_size(stderr_path)
    return {
        "stdout_bytes": _file_size(stdout_path),
        "stderr_bytes": stderr_bytes,
        "max_stdout_bytes": MAX_STDOUT_BYTES,
        "max_stderr_bytes": MAX_STDERR_BYTES,
        "stderr_truncated": stderr_bytes > MAX_STDERR_BYTES,
    }


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _read_text_prefix(path: Path, max_bytes: int) -> str:
    try:
        return path.read_bytes()[:max_bytes].decode("utf-8", errors="replace")
    except OSError:
        return ""


def _json_sha256(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _bounded_string(value: Any, max_chars: int) -> str:
    if not isinstance(value, str):
        return ""
    return value[:max_chars]


def _read_descriptor(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ProjectAdapterError("descriptor_invalid", f"Project-local adapter descriptor is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectAdapterError("descriptor_invalid", f"Project-local adapter descriptor is invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ProjectAdapterError("descriptor_invalid", f"Project-local adapter descriptor root must be an object: {path}")
    return value


def _write_run_artifact(state_dir: Path, adapter: dict[str, Any], phase: str, run_info: dict[str, Any], stderr: str) -> dict[str, str]:
    run_dir = state_dir / "adapter-runs"
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    prefix = f"{timestamp}-{adapter['id'].replace('.', '-')}-{phase}"
    artifact = run_dir / f"{prefix}.json"
    stderr_path = run_dir / f"{prefix}.stderr.txt"
    write_text_atomic(stderr_path, stderr)
    payload = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-project-adapter-run-v1",
        **run_info,
        "stderr": stderr_path.name,
    }
    write_text_atomic(artifact, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return {"run_artifact": artifact.as_posix(), "stderr": stderr_path.as_posix()}


def _run_info(adapter: dict[str, Any], phase: str, command: list[str]) -> dict[str, Any]:
    return {
        "adapter_id": adapter["id"],
        "adapter_version": adapter["version"],
        "adapter_checksum": adapter["entrypoint_sha256"],
        "descriptor_sha256": adapter["descriptor_sha256"],
        "execution_mode": PROJECT_ADAPTER_EXECUTION_MODE,
        "entrypoint": adapter["entrypoints"][phase]["command"],
        "command": [Path(command[0]).name, *command[1:]],
        "phase": phase,
        "started_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def _readonly_project_snapshot(project: Path) -> dict[str, tuple[Any, ...]]:
    snapshot = {}
    for path in project.rglob("*"):
        relative = path.relative_to(project)
        if not relative.parts or relative.parts[0] in {".git", ".localize-anything"}:
            continue
        try:
            if path.is_symlink():
                stat = path.lstat()
                snapshot[relative.as_posix()] = ("symlink", os.readlink(path), stat.st_mtime_ns)
            elif path.is_file():
                stat = path.stat()
                snapshot[relative.as_posix()] = ("file", stat.st_size, stat.st_mtime_ns)
        except OSError:
            snapshot[relative.as_posix()] = ("unreadable",)
    return snapshot


def _readonly_violations(project: Path, before: dict[str, tuple[Any, ...]]) -> list[dict[str, str]]:
    after = _readonly_project_snapshot(project)
    violations = []
    for path in sorted(before.keys() | after.keys()):
        if before.get(path) != after.get(path):
            if path not in before:
                change = "created"
            elif path not in after:
                change = "deleted"
            else:
                change = "modified"
            violations.append({"path": path, "change": change})
    return violations[:20]


def _attach_readonly_violations(project: Path, run_info: dict[str, Any], snapshot: dict[str, tuple[Any, ...]]) -> None:
    violations = _readonly_violations(_project(project), snapshot)
    if violations:
        run_info["readonly_violations"] = violations


def _adapter_base(project: Path) -> Path:
    return _project(project) / PROJECT_ADAPTER_DIRECTORY


def _project(project: Path) -> Path:
    return project.resolve()


def _safe_resolve(path: Path, root: Path, *, must_exist: bool = True) -> Path:
    try:
        resolved = path.resolve(strict=must_exist)
    except FileNotFoundError as exc:
        raise ProjectAdapterError("entrypoint_missing", f"Required adapter path is missing: {path}") from exc
    root_resolved = root.resolve()
    if not resolved.is_relative_to(root_resolved):
        raise ProjectAdapterError("path_escape", f"Path escapes allowed root: {path}")
    return resolved


def _relative(project: Path, path: Path) -> str:
    return path.resolve().relative_to(project.resolve()).as_posix()


def _adapter_payload_files(project: Path, adapter_root: Path, adapter_id: str) -> list[tuple[str, Path]]:
    if adapter_root.is_symlink():
        raise _payload_symlink_error(adapter_id, "", f"{PROJECT_ADAPTER_DIRECTORY}/{adapter_id}")
    files: list[tuple[str, Path]] = []
    _walk_adapter_payload(adapter_root, "", files, adapter_id, _relative(project, adapter_root))
    return files


def _walk_adapter_payload(
    directory: Path,
    relative: str,
    files: list[tuple[str, Path]],
    adapter_id: str,
    adapter_root_relative: str,
) -> None:
    try:
        entries = sorted(os.scandir(directory), key=lambda entry: entry.name.encode("utf-8"))
    except OSError as exc:
        raise ProjectAdapterError("adapter_payload_unreadable", f"Project-local adapter payload is not readable: {relative}") from exc
    for entry in entries:
        rel = f"{relative}/{entry.name}" if relative else entry.name
        if entry.is_symlink():
            raise _payload_symlink_error(adapter_id, rel, adapter_root_relative)
        if entry.is_dir(follow_symlinks=False):
            if entry.name == "__pycache__":
                continue
            _walk_adapter_payload(Path(entry.path), rel, files, adapter_id, adapter_root_relative)
        elif entry.is_file(follow_symlinks=False):
            if entry.name == ".DS_Store" or entry.name.endswith(".pyc"):
                continue
            files.append((rel, Path(entry.path)))
        elif _is_special_file(entry):
            raise ProjectAdapterError(
                ADAPTER_PAYLOAD_SPECIAL_FILE_CODE,
                f"adapter_payload_special_file: Project-local adapter payload contains a special file: {rel}",
                evidence={
                    "adapter_id": adapter_id,
                    "relative_path": rel,
                    "entry_type": "special_file",
                    "adapter_root": adapter_root_relative,
                    "operation": "fingerprint",
                    "recommended_action": "remove the special file from the adapter payload",
                },
            )


def _is_special_file(entry: os.DirEntry[str]) -> bool:
    mode = entry.stat(follow_symlinks=False).st_mode
    return stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode) or stat.S_ISBLK(mode) or stat.S_ISCHR(mode)


def _payload_symlink_error(adapter_id: str, relative: str, adapter_root_relative: str) -> ProjectAdapterError:
    return ProjectAdapterError(
        ADAPTER_PAYLOAD_SYMLINK_CODE,
        f"adapter_payload_symlink: Project-local adapter payload contains a symlink: {relative}",
        evidence={
            "adapter_id": adapter_id,
            "relative_path": relative,
            "entry_type": "symlink",
            "adapter_root": adapter_root_relative,
            "operation": "fingerprint",
            "recommended_action": "replace the symlink with a regular vendored file or directory",
        },
    )


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _duration_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
