from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json
from .project import load_session_index


RUN_ARTIFACTS = {
    "review_readiness": "readiness-authorization-matrix.json",
    "delivery_readiness": "delivery-readiness-report.json",
    "apply_readiness": "apply-readiness-report.json",
    "artifact_state": "artifact-state.json",
    "review_queue": "workbench-review-queue.json",
    "claim_queue": "workbench-claim-queue.json",
    "readiness_action_queue": "workbench-readiness-action-queue.json",
    "signoff": "workbench-signoff-summary.json",
}


class WorkbenchRunError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int,
        field: str | None = None,
        recoverable: bool = True,
        actions: list[str] | None = None,
        artifact: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.field = field
        self.recoverable = recoverable
        self.actions = actions or []
        self.artifact = artifact

    def envelope(self) -> dict[str, Any]:
        error: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
            "actions": self.actions,
        }
        if self.field:
            error["field"] = self.field
        if self.artifact:
            error["artifact"] = self.artifact
        return {
            "status": "fail",
            "status_code": "fail",
            "status_family": "error",
            "message_code": self.code,
            "message_params": {},
            "api_version": "workbench-v1",
            "error": error,
        }


def build_workbench_run_view(project_root: Path | str, run_id: str | None) -> dict[str, Any]:
    project_value = str(project_root or "").strip()
    if not project_value:
        raise WorkbenchRunError(
            "PROJECT_REQUIRED",
            "A project path is required for a Workbench run view.",
            status=400,
            field="project",
            actions=["OPEN_PROJECT"],
        )
    project = Path(project_value).expanduser().resolve()
    requested_run_id = str(run_id or "").strip()
    if not requested_run_id:
        raise WorkbenchRunError(
            "RUN_REQUIRED",
            "An exact run_id is required for a Workbench run view.",
            status=400,
            field="run_id",
            actions=["OPEN_SESSIONS"],
        )
    if not project.is_dir():
        raise WorkbenchRunError(
            "PROJECT_NOT_FOUND",
            "The requested project does not exist.",
            status=404,
            field="project",
            actions=["OPEN_PROJECT"],
        )

    index = load_session_index(project)
    session = next(
        (
            item
            for item in index.get("sessions", [])
            if isinstance(item, dict)
            and str(item.get("run_id") or item.get("session_id") or "") == requested_run_id
        ),
        None,
    )
    if not isinstance(session, dict):
        raise WorkbenchRunError(
            "RUN_NOT_FOUND",
            "The requested run does not exist.",
            status=404,
            field="run_id",
            actions=["OPEN_LATEST_RUN", "OPEN_SESSIONS"],
        )
    session_run_id = str(session.get("run_id") or session.get("session_id") or "")
    if session_run_id != requested_run_id:
        raise WorkbenchRunError(
            "RUN_STATE_MISMATCH",
            "The session and requested run identities do not match.",
            status=409,
            field="run_id",
            actions=["OPEN_SESSIONS"],
        )

    run_directory = _resolve_path(session.get("run_directory"))
    delivery_directory = _delivery_directory(session, run_directory, requested_run_id)
    selected_root = delivery_directory if delivery_directory.is_dir() else run_directory
    # A selected Run remains authoritative, but one malformed optional artifact
    # must not make the whole Review projection unusable.  Keep the artifact
    # error scoped to its projection so the UI can show the raw file and the
    # other cards can continue to render.
    selected_pending = _awaiting_generated_responses(session)
    selected = _snapshot(
        selected_root,
        requested_run_id,
        strict=False,
        pending_missing=selected_pending,
    )
    current_run_id = str(index.get("latest_session_id") or "").strip() or None
    current_session = next(
        (
            item
            for item in index.get("sessions", [])
            if isinstance(item, dict)
            and str(item.get("run_id") or item.get("session_id") or "") == current_run_id
        ),
        None,
    )
    current = _snapshot(
        project / ".localize-anything",
        current_run_id,
        strict=False,
        pending_missing=_awaiting_generated_responses(current_session),
    )
    summary_path = run_directory / "run-summary.json"
    summary_artifact: dict[str, Any]
    try:
        summary = _run_summary(run_directory, session, requested_run_id)
    except WorkbenchRunError as exc:
        if exc.code != "INVALID_ARTIFACT_JSON":
            raise
        # Keep the exact session identity and the last indexed summary usable,
        # while exposing the broken file as a card-level artifact error.
        summary = session.get("summary") if isinstance(session.get("summary"), dict) else {}
        summary_artifact = {
            "state": "error",
            "artifact": "run-summary.json",
            "path": summary_path.as_posix(),
            "run_id": requested_run_id,
            "reason": exc.code,
            "message": exc.message,
        }
    else:
        summary_artifact = {
            "state": "available" if summary_path.is_file() else "missing",
            "artifact": "run-summary.json",
            "path": summary_path.as_posix(),
            "run_id": requested_run_id,
            "reason": "available" if summary_path.is_file() else "ARTIFACT_MISSING",
        }
        if summary_path.is_file():
            summary_artifact["data"] = summary
    current_project_projection = _current_projection(current, current_run_id, requested_run_id)
    freshness = "current" if current_run_id == requested_run_id else "historical"
    limitations = _collect_strings(
        summary.get("limitations"),
        selected["review_readiness"].get("data", {}).get("limitations") if selected["review_readiness"]["state"] == "available" else None,
        selected["delivery_readiness"].get("data", {}).get("limitations") if selected["delivery_readiness"]["state"] == "available" else None,
        selected["apply_readiness"].get("data", {}).get("limitations") if selected["apply_readiness"]["state"] == "available" else None,
    )
    next_actions = _collect_strings(
        session.get("next_actions"),
        summary.get("next_actions"),
        selected["review_readiness"].get("data", {}).get("recommended_next_actions") if selected["review_readiness"]["state"] == "available" else None,
        selected["delivery_readiness"].get("data", {}).get("recommended_next_action") if selected["delivery_readiness"]["state"] == "available" else None,
        selected["apply_readiness"].get("data", {}).get("recommended_next_action") if selected["apply_readiness"]["state"] == "available" else None,
    )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "project_root": project.as_posix(),
        "run_id": requested_run_id,
        "snapshot_kind": "exact_run",
        "freshness": freshness,
        "newer_project_state_available": current_run_id not in {None, requested_run_id},
        "session": session,
        "summary": summary,
        "summary_artifact": summary_artifact,
        "review_readiness": selected["review_readiness"],
        "delivery_readiness": selected["delivery_readiness"],
        "apply_readiness": selected["apply_readiness"],
        "artifact_state": selected["artifact_state"],
        "queues": {
            "review": selected["review_queue"],
            "claims": selected["claim_queue"],
            "readiness_actions": selected["readiness_action_queue"],
        },
        "signoff": selected["signoff"],
        "artifacts": _artifact_pointers(session, run_directory, selected_root, project / ".localize-anything"),
        "limitations": limitations,
        "next_actions": next_actions,
        "current_project_projection": current_project_projection,
    }


def _snapshot(
    root: Path,
    expected_run_id: str | None,
    *,
    strict: bool,
    pending_missing: bool = False,
) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for key, name in RUN_ARTIFACTS.items():
        path = root / name
        if not path.is_file():
            snapshot[key] = {
                "state": "pending" if pending_missing else "missing",
                "artifact": name,
                "path": path.as_posix(),
                "run_id": expected_run_id,
                "reason": "WAITING_FOR_GENERATED_RESPONSES" if pending_missing else "ARTIFACT_MISSING",
            }
            continue
        try:
            value = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            if strict:
                raise WorkbenchRunError(
                    "INVALID_ARTIFACT_JSON",
                    "The selected run artifact is not valid JSON.",
                    status=422,
                    field=key,
                    artifact=path.as_posix(),
                    actions=["OPEN_ARTIFACT_INSPECTOR", "RETRY"],
                ) from exc
            snapshot[key] = {
                "state": "error",
                "artifact": name,
                "path": path.as_posix(),
                "run_id": expected_run_id,
                "reason": "INVALID_ARTIFACT_JSON",
                "message": "The selected run artifact is not valid JSON.",
            }
            continue
        actual_run_id = value.get("run_id") if isinstance(value, dict) else None
        if expected_run_id and actual_run_id and str(actual_run_id) != expected_run_id:
            snapshot[key] = {
                "state": "stale",
                "artifact": name,
                "path": path.as_posix(),
                "run_id": str(actual_run_id),
                "expected_run_id": expected_run_id,
                "reason": "RUN_STATE_MISMATCH",
                "data": value,
            }
            continue
        snapshot[key] = {
            "state": "available",
            "artifact": name,
            "path": path.as_posix(),
            "run_id": str(actual_run_id or expected_run_id or ""),
            "reason": "available",
            "data": value,
        }
    return snapshot


def _awaiting_generated_responses(session: dict[str, Any] | None) -> bool:
    return isinstance(session, dict) and str(session.get("status") or "") == "awaiting_llm_responses"


def _current_projection(current: dict[str, dict[str, Any]], current_run_id: str | None, selected_run_id: str) -> dict[str, Any]:
    return {
        "snapshot_kind": "project_current",
        "run_id": current_run_id,
        "freshness": "current" if current_run_id == selected_run_id else "newer_project_state_available" if current_run_id else "no_current_run",
        "mismatch": None
        if current_run_id in {None, selected_run_id}
        else {"selected_run_id": selected_run_id, "current_run_id": current_run_id, "reason": "PROJECT_CURRENT_RUN_DIFFERS"},
        "review_readiness": current["review_readiness"],
        "delivery_readiness": current["delivery_readiness"],
        "apply_readiness": current["apply_readiness"],
        "artifact_state": current["artifact_state"],
        "queues": {
            "review": current["review_queue"],
            "claims": current["claim_queue"],
            "readiness_actions": current["readiness_action_queue"],
        },
        "signoff": current["signoff"],
    }


def _run_summary(run_directory: Path, session: dict[str, Any], run_id: str) -> dict[str, Any]:
    path = run_directory / "run-summary.json"
    if path.is_file():
        try:
            value = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise WorkbenchRunError(
                "INVALID_ARTIFACT_JSON",
                "The selected run summary is not valid JSON.",
                status=422,
                field="summary",
                artifact=path.as_posix(),
                actions=["OPEN_ARTIFACT_INSPECTOR", "RETRY"],
            ) from exc
        if isinstance(value, dict) and value.get("run_id") not in {None, run_id}:
            raise WorkbenchRunError(
                "RUN_STATE_MISMATCH",
                "The selected run summary belongs to a different run.",
                status=409,
                field="summary",
                artifact=path.as_posix(),
                actions=["OPEN_SESSIONS"],
            )
        if isinstance(value, dict):
            return value.get("summary") if isinstance(value.get("summary"), dict) else value
    return session.get("summary") if isinstance(session.get("summary"), dict) else {}


def _delivery_directory(session: dict[str, Any], run_directory: Path, run_id: str) -> Path:
    artifacts = session.get("artifacts") if isinstance(session.get("artifacts"), dict) else {}
    pointer = artifacts.get("delivery_directory")
    if pointer:
        return _resolve_path(pointer)
    return run_directory / "deliveries" / run_id


def _resolve_path(value: Any) -> Path:
    return Path(str(value or "")).expanduser().resolve()


def _artifact_pointers(session: dict[str, Any], run_directory: Path, selected_root: Path, current_root: Path) -> list[dict[str, Any]]:
    artifacts = session.get("artifacts") if isinstance(session.get("artifacts"), dict) else {}
    pointers: list[dict[str, Any]] = []
    for key, value in sorted(artifacts.items()):
        if not isinstance(value, str) or not value:
            continue
        path = _resolve_path(value)
        if path == run_directory or path == selected_root or path.is_dir():
            state = "directory" if path.is_dir() else "available"
        elif not path.exists():
            state = "missing"
        else:
            state = "available"
        scope = "selected_run" if _within(path, run_directory) or _within(path, selected_root) else "project_current" if _within(path, current_root) else "external"
        pointers.append(
            {
                "artifact_id": key,
                "path": path.as_posix(),
                "state": state,
                "scope": scope,
                "run_id": session.get("run_id") if scope == "selected_run" else None,
            }
        )
    return pointers


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _collect_strings(*values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value:
            result.append(value)
        elif isinstance(value, list):
            result.extend(str(item) for item in value if str(item))
    return list(dict.fromkeys(result))
