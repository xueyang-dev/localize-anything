from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, sha256_file, write_json, write_jsonl


WORKFLOW_LOCK_STATE_JSON = "workflow-lock-state.json"
WORKFLOW_CHECKPOINT_LOG_JSONL = "workflow-checkpoint-log.jsonl"
WORKFLOW_TRANSACTION_MANIFEST_JSON = "workflow-transaction-manifest.json"
WORKFLOW_IDEMPOTENCY_REPORT_JSON = "workflow-idempotency-report.json"
WORKFLOW_RECOVERY_PLAN_JSON = "workflow-recovery-plan.json"
WORKFLOW_RECOVERY_RESULT_JSON = "workflow-recovery-result.json"

LOCK_FILE = ".workflow.lock"
LOCK_TTL_SECONDS = 15 * 60

LOCK_STATUSES = {"unlocked", "locked", "stale", "released", "force_released", "abandoned", "unknown"}
CHECKPOINT_TYPES = {
    "workflow_started",
    "stage_planned",
    "stage_started",
    "artifact_write_staged",
    "artifact_write_committed",
    "stage_completed",
    "stage_skipped",
    "stage_blocked",
    "stage_failed",
    "workflow_completed",
    "workflow_failed",
    "workflow_abandoned",
    "workflow_recovered",
}


def workflow_hardening_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "workflow_lock_state": WORKFLOW_LOCK_STATE_JSON,
        "workflow_checkpoint_log": WORKFLOW_CHECKPOINT_LOG_JSONL,
        "workflow_transaction_manifest": WORKFLOW_TRANSACTION_MANIFEST_JSON,
        "workflow_idempotency_report": WORKFLOW_IDEMPOTENCY_REPORT_JSON,
        "workflow_recovery_plan": WORKFLOW_RECOVERY_PLAN_JSON,
        "workflow_recovery_result": WORKFLOW_RECOVERY_RESULT_JSON,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def build_workflow_idempotency_report(
    state_dir: Path,
    *,
    workflow_mode: str,
    command: str,
    request: dict[str, Any],
    idempotency_key: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    fingerprint = _stable_hash(request)
    key = idempotency_key or _stable_id("idempotency", [command, workflow_mode, request])
    previous = _optional_json(state_dir / WORKFLOW_IDEMPOTENCY_REPORT_JSON)
    lock = read_workflow_lock_state(state_dir)
    execution = _optional_json(state_dir / "workflow-execution-result.json")
    duplicate_status = "new_request"
    replay_policy = "record_and_run_if_unlocked"
    result_reuse_status = "not_reused"
    safety_decision = "proceed"
    previous_matching_run: dict[str, Any] = {}

    if previous.get("idempotency_key") == key:
        previous_matching_run = {
            "idempotency_key": key,
            "request_fingerprint": previous.get("request_fingerprint", ""),
            "workflow_mode": previous.get("workflow_mode", ""),
            "last_status": previous.get("duplicate_status", ""),
        }
        if previous.get("request_fingerprint") != fingerprint:
            duplicate_status = "duplicate_conflicting_payload"
            replay_policy = "blocked"
            safety_decision = "blocked"
        elif lock.get("lock_status") == "locked":
            duplicate_status = "duplicate_in_progress"
            replay_policy = "blocked_until_lock_released"
            safety_decision = "blocked"
        elif execution.get("status") == "completed":
            duplicate_status = "duplicate_completed"
            replay_policy = "reuse_completed_result"
            result_reuse_status = "reused_existing_result"
            safety_decision = "reuse"
        elif execution.get("status") in {"failed", "blocked"}:
            duplicate_status = "duplicate_failed"
            replay_policy = "replay_only_after_recovery"
            safety_decision = "blocked"
        else:
            duplicate_status = "replay_safe"
            replay_policy = "safe_deterministic_replay"

    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-idempotency-report-v1",
        "artifact": WORKFLOW_IDEMPOTENCY_REPORT_JSON,
        "idempotency_key": key,
        "request_fingerprint": fingerprint,
        "workflow_mode": workflow_mode,
        "command_or_endpoint": command,
        "previous_matching_run": previous_matching_run,
        "duplicate_status": duplicate_status,
        "replay_policy": replay_policy,
        "result_reuse_status": result_reuse_status,
        "affected_artifacts": workflow_hardening_asset_paths(state_dir),
        "safety_decision": safety_decision,
        "recommended_next_action": _idempotency_next_action(duplicate_status),
        "limitations": ["idempotency evidence does not hide failed or partial previous runs"],
    }
    if write:
        write_json(state_dir / WORKFLOW_IDEMPOTENCY_REPORT_JSON, report)
    return report


def acquire_workflow_lock(
    state_dir: Path,
    *,
    workflow_id: str,
    run_id: str | None,
    workflow_mode: str,
    locked_stages: list[str],
    source_command: str,
    force_release_stale_lock: bool = False,
) -> tuple[dict[str, Any], bool]:
    state_dir = state_dir.resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    existing = read_workflow_lock_state(state_dir)
    lock_path = state_dir / LOCK_FILE
    stale = _is_lock_stale(existing, lock_path)
    if lock_path.exists() and not stale:
        state = _lock_state(
            state_dir,
            workflow_id=workflow_id,
            run_id=run_id,
            workflow_mode=workflow_mode,
            locked_stages=locked_stages,
            source_command=source_command,
            lock_status="locked",
            stale=False,
            recommendation="wait_or_inspect_active_workflow",
            lock_id=str(existing.get("lock_id") or _stable_id("workflow-lock", [workflow_id, source_command])),
        )
        write_json(state_dir / WORKFLOW_LOCK_STATE_JSON, state)
        return state, False
    if lock_path.exists() and stale and not force_release_stale_lock:
        state = _lock_state(
            state_dir,
            workflow_id=workflow_id,
            run_id=run_id,
            workflow_mode=workflow_mode,
            locked_stages=locked_stages,
            source_command=source_command,
            lock_status="stale",
            stale=True,
            recommendation="run workflow-recover or pass explicit stale-lock release",
            lock_id=str(existing.get("lock_id") or _stable_id("workflow-lock", [workflow_id, source_command])),
        )
        write_json(state_dir / WORKFLOW_LOCK_STATE_JSON, state)
        return state, False
    if lock_path.exists() and stale and force_release_stale_lock:
        try:
            lock_path.unlink()
        except OSError:
            pass
    lock_id = _stable_id("workflow-lock", [workflow_id, run_id, source_command, _now()])
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        state = _lock_state(
            state_dir,
            workflow_id=workflow_id,
            run_id=run_id,
            workflow_mode=workflow_mode,
            locked_stages=locked_stages,
            source_command=source_command,
            lock_status="locked",
            stale=False,
            recommendation="concurrent workflow detected; retry after active lock releases",
            lock_id=lock_id,
        )
        write_json(state_dir / WORKFLOW_LOCK_STATE_JSON, state)
        return state, False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(lock_id + "\n")
    state = _lock_state(
        state_dir,
        workflow_id=workflow_id,
        run_id=run_id,
        workflow_mode=workflow_mode,
        locked_stages=locked_stages,
        source_command=source_command,
        lock_status="locked",
        stale=False,
        recommendation="release lock after workflow completion or recovery",
        lock_id=lock_id,
    )
    write_json(state_dir / WORKFLOW_LOCK_STATE_JSON, state)
    return state, True


def release_workflow_lock(state_dir: Path, *, status: str = "released") -> dict[str, Any]:
    state_dir = state_dir.resolve()
    current = read_workflow_lock_state(state_dir)
    lock_path = state_dir / LOCK_FILE
    try:
        lock_path.unlink()
    except OSError:
        pass
    state = {
        **current,
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-lock-state-v1",
        "artifact": WORKFLOW_LOCK_STATE_JSON,
        "lock_status": status if status in LOCK_STATUSES else "released",
        "updated_at": _now(),
        "heartbeat_at": _now(),
        "stale_lock_detection": {"is_stale": False, "reason": "lock released"},
        "recovery_recommendation": "no recovery required for released lock",
    }
    write_json(state_dir / WORKFLOW_LOCK_STATE_JSON, state)
    return state


def read_workflow_lock_state(state_dir: Path) -> dict[str, Any]:
    path = state_dir / WORKFLOW_LOCK_STATE_JSON
    if not path.is_file():
        return {
            "protocol_version": PROTOCOL_VERSION,
            "schema": "localize-anything-workflow-lock-state-v1",
            "artifact": WORKFLOW_LOCK_STATE_JSON,
            "lock_id": "",
            "workflow_id": "",
            "run_id": None,
            "owner_process_reference": "",
            "workflow_mode": "",
            "lock_status": "unlocked",
            "acquired_at": "",
            "updated_at": "",
            "heartbeat_at": "",
            "lock_ttl_seconds": LOCK_TTL_SECONDS,
            "locked_artifacts": [],
            "locked_stages": [],
            "source_command_or_api_request": "",
            "stale_lock_detection": {"is_stale": False, "reason": "no lock file"},
            "recovery_recommendation": "no active lock",
        }
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def append_workflow_checkpoint(
    state_dir: Path,
    *,
    workflow_id: str,
    run_id: str | None,
    stage_id: str,
    stage_type: str,
    checkpoint_type: str,
    status: str,
    output_artifact_paths: list[str] | None = None,
    transaction_id: str = "",
    error_summary: str = "",
    recovery_hint: str = "",
    source_command: str = "",
) -> dict[str, Any]:
    if checkpoint_type not in CHECKPOINT_TYPES:
        raise ValueError(f"checkpoint_type must be one of: {', '.join(sorted(CHECKPOINT_TYPES))}")
    state_dir = state_dir.resolve()
    outputs = output_artifact_paths or []
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-checkpoint-log-record-v1",
        "checkpoint_id": _stable_id("checkpoint", [workflow_id, stage_id, checkpoint_type, status, len(read_workflow_checkpoint_log(state_dir))]),
        "workflow_id": workflow_id,
        "run_id": run_id,
        "stage_id": stage_id,
        "stage_type": stage_type,
        "checkpoint_type": checkpoint_type,
        "status": status,
        "input_artifact_hashes": {},
        "output_artifact_paths": outputs,
        "output_artifact_hashes": _hashes(state_dir, outputs),
        "transaction_id": transaction_id,
        "started_at": _now() if checkpoint_type.endswith("started") or checkpoint_type == "workflow_started" else "",
        "finished_at": _now() if checkpoint_type.endswith(("completed", "failed", "blocked", "skipped")) or checkpoint_type in {"workflow_completed", "workflow_failed"} else "",
        "source_command_or_api_request": source_command,
        "error_summary": error_summary,
        "recovery_hint": recovery_hint,
        "source_artifact_references": _existing(state_dir, ["workflow-run-plan.json", WORKFLOW_LOCK_STATE_JSON]),
    }
    records = read_workflow_checkpoint_log(state_dir)
    records.append(record)
    write_jsonl(state_dir / WORKFLOW_CHECKPOINT_LOG_JSONL, records)
    return record


def read_workflow_checkpoint_log(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / WORKFLOW_CHECKPOINT_LOG_JSONL
    return read_jsonl(path) if path.is_file() else []


def record_workflow_transaction(
    state_dir: Path,
    *,
    workflow_id: str,
    run_id: str | None,
    stage_id: str,
    artifact_paths: list[str],
    transaction_status: str,
    transaction_id: str | None = None,
    previous_hashes: dict[str, str] | None = None,
    recovery_status: str = "not_needed",
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    manifest = read_workflow_transaction_manifest(state_dir)
    transaction_id = transaction_id or _stable_id("workflow-transaction", [workflow_id, stage_id, artifact_paths])
    writes = [
        {
            "artifact_path": path,
            "temp_or_staging_path": "",
            "final_artifact_path": path,
            "previous_hash": (previous_hashes or {}).get(path),
            "new_hash": _hash_if_file(state_dir / path),
        }
        for path in artifact_paths
    ]
    transaction = {
        "transaction_id": transaction_id,
        "workflow_id": workflow_id,
        "run_id": run_id,
        "stage_id": stage_id,
        "transaction_status": transaction_status,
        "artifact_writes": writes,
        "commit_order": artifact_paths,
        "rollback_or_recovery_status": recovery_status,
        "created_at": _now(),
        "committed_at": _now() if transaction_status == "committed" else "",
        "rollback_supported": "not_supported",
    }
    transactions = [item for item in manifest.get("transactions", []) if item.get("transaction_id") != transaction_id]
    transactions.append(transaction)
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-transaction-manifest-v1",
        "artifact": WORKFLOW_TRANSACTION_MANIFEST_JSON,
        "status": _manifest_status(transactions),
        "transactions": transactions,
        "summary": {
            "transaction_count": len(transactions),
            "partial_or_failed_count": sum(item.get("transaction_status") in {"partially_committed", "failed", "abandoned", "unknown"} for item in transactions),
        },
        "limitations": ["rollback is not implemented in this seed; stale or partial writes require deterministic recompute or manual inspection"],
    }
    write_json(state_dir / WORKFLOW_TRANSACTION_MANIFEST_JSON, manifest)
    return transaction


def read_workflow_transaction_manifest(state_dir: Path) -> dict[str, Any]:
    path = state_dir / WORKFLOW_TRANSACTION_MANIFEST_JSON
    if path.is_file():
        value = read_json(path)
        return value if isinstance(value, dict) else {}
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-transaction-manifest-v1",
        "artifact": WORKFLOW_TRANSACTION_MANIFEST_JSON,
        "status": "planned",
        "transactions": [],
        "summary": {"transaction_count": 0, "partial_or_failed_count": 0},
        "limitations": ["no workflow transactions have been recorded"],
    }


def build_workflow_recovery_plan(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    lock = read_workflow_lock_state(state_dir)
    checkpoints = read_workflow_checkpoint_log(state_dir)
    manifest = read_workflow_transaction_manifest(state_dir)
    artifact_state = _optional_json(state_dir / "artifact-state.json")
    last_checkpoint = checkpoints[-1] if checkpoints else {}
    partial = [item for item in manifest.get("transactions", []) if item.get("transaction_status") in {"partially_committed", "failed", "abandoned", "unknown"}]
    stale_lock = lock.get("lock_status") in {"locked", "stale"} and _is_lock_stale(lock, state_dir / LOCK_FILE)
    failed_stage = next((item for item in reversed(checkpoints) if item.get("checkpoint_type") == "stage_failed"), {})
    issue = "stale_lock" if stale_lock else "partial_transaction" if partial else "failed_stage" if failed_stage else "missing_checkpoint" if not checkpoints else "stale_artifact_state" if artifact_state.get("status") == "stale" else "unknown"
    recompute = _recompute_targets(artifact_state, partial)
    action = _recommended_recovery_action(issue, recompute)
    plan = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-recovery-plan-v1",
        "artifact": WORKFLOW_RECOVERY_PLAN_JSON,
        "recovery_id": _stable_id("workflow-recovery", [issue, lock.get("workflow_id"), last_checkpoint.get("checkpoint_id")]),
        "detected_issue": issue,
        "affected_workflow_id": lock.get("workflow_id") or last_checkpoint.get("workflow_id", ""),
        "affected_run_id": lock.get("run_id") or last_checkpoint.get("run_id"),
        "active_or_stale_lock_status": lock.get("lock_status", "unknown"),
        "last_checkpoint": last_checkpoint,
        "incomplete_stages": _incomplete_stages(checkpoints),
        "partial_transactions": partial,
        "suspect_artifacts": _suspect_artifacts(partial),
        "artifacts_safe_to_reuse": _current_artifacts(artifact_state),
        "artifacts_requiring_recompute": recompute,
        "artifacts_requiring_manual_inspection": _manual_inspection(issue, partial),
        "artifacts_requiring_provider_or_human_action": _provider_human_artifacts(artifact_state),
        "readiness_impact": "blocked_or_stale_until_recovery" if issue != "unknown" else "not_applicable",
        "recommended_recovery_action": action,
        "source_artifact_references": workflow_hardening_asset_paths(state_dir),
    }
    if write:
        write_json(state_dir / WORKFLOW_RECOVERY_PLAN_JSON, plan)
    return plan


def run_workflow_recovery(
    state_dir: Path,
    *,
    recovery_action: str = "recompute_stale_artifacts",
    run_id: str | None = None,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    before = _readiness_status(state_dir)
    plan = build_workflow_recovery_plan(state_dir)
    artifacts_marked_stale: list[str] = []
    artifacts_reused: list[str] = []
    artifacts_recomputed: list[str] = []
    artifacts_manual: list[str] = list(plan.get("artifacts_requiring_manual_inspection", []))
    lock_action = "none"
    if recovery_action in {"release_stale_lock", "recompute_stale_artifacts", "resume_from_checkpoint"} and plan.get("active_or_stale_lock_status") == "stale":
        release_workflow_lock(state_dir, status="force_released")
        lock_action = "force_released_stale_lock"
    manifest = read_workflow_transaction_manifest(state_dir)
    if recovery_action in {"discard_partial_outputs", "recompute_stale_artifacts", "resume_from_checkpoint"}:
        for transaction in manifest.get("transactions", []):
            if transaction.get("transaction_status") in {"partially_committed", "failed", "unknown"}:
                transaction["transaction_status"] = "abandoned"
                transaction["rollback_or_recovery_status"] = "requires_recompute"
                artifacts_marked_stale.extend(write.get("final_artifact_path", "") for write in transaction.get("artifact_writes", []))
        write_json(state_dir / WORKFLOW_TRANSACTION_MANIFEST_JSON, manifest)
    if recovery_action in {"recompute_stale_artifacts", "resume_from_checkpoint"}:
        from .artifact_state import build_artifact_state
        from .readiness_authorization import build_readiness_reports

        build_artifact_state(state_dir, run_id=run_id)
        build_readiness_reports(state_dir, run_id=run_id)
        artifacts_recomputed.extend(["artifact-state.json", "readiness-authorization-matrix.json", "manual-followup-gap-report.json", "apply-readiness-report.json", "delivery-readiness-report.json"])
    elif recovery_action == "manual_inspection_required":
        artifacts_manual.extend(plan.get("suspect_artifacts", []))
    after = _readiness_status(state_dir)
    result_status = _recovery_status(plan, recovery_action, artifacts_manual)
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-recovery-result-v1",
        "artifact": WORKFLOW_RECOVERY_RESULT_JSON,
        "recovery_id": plan["recovery_id"],
        "recovery_action_attempted": recovery_action,
        "lock_action": lock_action,
        "checkpoints_used": [plan.get("last_checkpoint", {})] if plan.get("last_checkpoint") else [],
        "transactions_repaired_or_marked_abandoned": [item for item in manifest.get("transactions", []) if item.get("transaction_status") == "abandoned"],
        "artifacts_reused": artifacts_reused,
        "artifacts_recomputed": artifacts_recomputed,
        "artifacts_marked_stale": sorted(set(filter(None, artifacts_marked_stale))),
        "artifacts_requiring_manual_review": sorted(set(filter(None, artifacts_manual))),
        "artifacts_still_blocked": plan.get("artifacts_requiring_provider_or_human_action", []),
        "readiness_before": before,
        "readiness_after": after,
        "remaining_blockers": _remaining_blockers(state_dir),
        "remaining_forbidden_claims": _remaining_forbidden_claims(state_dir),
        "result_status": result_status,
        "provider_or_model_called": False,
        "repair_applied": False,
        "target_files_mutated": False,
        "limitations": ["recovery does not imply readiness unless refreshed readiness artifacts support it"],
    }
    append_workflow_checkpoint(
        state_dir,
        workflow_id=str(plan.get("affected_workflow_id") or ""),
        run_id=run_id or plan.get("affected_run_id"),
        stage_id="workflow-recovery",
        stage_type="workflow_recovery",
        checkpoint_type="workflow_recovered",
        status=result_status,
        output_artifact_paths=[WORKFLOW_RECOVERY_RESULT_JSON],
        source_command="workflow-recover",
    )
    write_json(state_dir / WORKFLOW_RECOVERY_RESULT_JSON, result)
    return result


def read_workflow_idempotency_report(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKFLOW_IDEMPOTENCY_REPORT_JSON)


def read_workflow_recovery_plan(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKFLOW_RECOVERY_PLAN_JSON)


def read_workflow_recovery_result(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKFLOW_RECOVERY_RESULT_JSON)


def _lock_state(
    state_dir: Path,
    *,
    workflow_id: str,
    run_id: str | None,
    workflow_mode: str,
    locked_stages: list[str],
    source_command: str,
    lock_status: str,
    stale: bool,
    recommendation: str,
    lock_id: str,
) -> dict[str, Any]:
    now = _now()
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-lock-state-v1",
        "artifact": WORKFLOW_LOCK_STATE_JSON,
        "lock_id": lock_id,
        "workflow_id": workflow_id,
        "run_id": run_id,
        "owner_process_reference": f"pid:{os.getpid()}",
        "workflow_mode": workflow_mode,
        "lock_status": lock_status,
        "acquired_at": now,
        "updated_at": now,
        "heartbeat_at": now,
        "lock_ttl_seconds": LOCK_TTL_SECONDS,
        "locked_artifacts": [],
        "locked_stages": locked_stages,
        "source_command_or_api_request": source_command,
        "stale_lock_detection": {"is_stale": stale, "reason": "ttl exceeded or abandoned lockfile" if stale else "lock heartbeat is current"},
        "recovery_recommendation": recommendation,
    }


def _is_lock_stale(lock_state: dict[str, Any], lock_path: Path) -> bool:
    if str(lock_state.get("lock_status") or "") in {"stale", "abandoned"}:
        return True
    heartbeat = str(lock_state.get("heartbeat_at") or lock_state.get("updated_at") or "")
    if heartbeat:
        try:
            return datetime.now(UTC) - datetime.fromisoformat(heartbeat) > timedelta(seconds=int(lock_state.get("lock_ttl_seconds") or LOCK_TTL_SECONDS))
        except ValueError:
            return True
    if lock_path.exists():
        return datetime.now(UTC) - datetime.fromtimestamp(lock_path.stat().st_mtime, UTC) > timedelta(seconds=LOCK_TTL_SECONDS)
    return False


def _manifest_status(transactions: list[dict[str, Any]]) -> str:
    if any(item.get("transaction_status") in {"partially_committed", "failed", "unknown"} for item in transactions):
        return "partially_committed"
    if any(item.get("transaction_status") == "abandoned" for item in transactions):
        return "abandoned"
    if transactions and all(item.get("transaction_status") == "committed" for item in transactions):
        return "committed"
    return "planned"


def _incomplete_stages(checkpoints: list[dict[str, Any]]) -> list[str]:
    started = [item for item in checkpoints if item.get("checkpoint_type") == "stage_started"]
    closed = {item.get("stage_id") for item in checkpoints if item.get("checkpoint_type") in {"stage_completed", "stage_skipped", "stage_blocked", "stage_failed"}}
    return sorted({str(item.get("stage_id")) for item in started if item.get("stage_id") not in closed})


def _recompute_targets(artifact_state: dict[str, Any], partial: list[dict[str, Any]]) -> list[str]:
    targets = [str(item.get("path") or item.get("artifact_id")) for item in artifact_state.get("stale_artifacts", [])]
    for transaction in partial:
        for write in transaction.get("artifact_writes", []):
            targets.append(str(write.get("final_artifact_path") or write.get("artifact_path") or ""))
    return sorted(set(filter(None, targets)))


def _suspect_artifacts(partial: list[dict[str, Any]]) -> list[str]:
    return sorted(set(filter(None, (str(write.get("final_artifact_path") or write.get("artifact_path") or "") for transaction in partial for write in transaction.get("artifact_writes", [])))))


def _current_artifacts(artifact_state: dict[str, Any]) -> list[str]:
    return [str(item.get("path") or item.get("artifact_id")) for item in artifact_state.get("artifacts", []) if item.get("status") in {"current", "accepted"}]


def _provider_human_artifacts(artifact_state: dict[str, Any]) -> list[str]:
    return [str(item.get("path") or item.get("artifact_id")) for item in artifact_state.get("artifacts", []) if item.get("status") in {"requires_human_review", "blocked"}]


def _manual_inspection(issue: str, partial: list[dict[str, Any]]) -> list[str]:
    if issue in {"partial_transaction", "artifact_hash_mismatch"}:
        return _suspect_artifacts(partial)
    return []


def _recommended_recovery_action(issue: str, recompute: list[str]) -> str:
    if issue == "stale_lock":
        return "release_stale_lock"
    if issue == "partial_transaction":
        return "discard_partial_outputs"
    if issue == "failed_stage":
        return "rerun_deterministic_stage"
    if recompute:
        return "recompute_stale_artifacts"
    if issue == "missing_checkpoint":
        return "manual_inspection_required"
    return "not_recoverable" if issue == "unknown" else "resume_from_checkpoint"


def _recovery_status(plan: dict[str, Any], action: str, manual: list[str]) -> str:
    if action in {"block_until_human_action", "manual_inspection_required"} or manual:
        return "requires_manual_inspection"
    if plan.get("artifacts_requiring_provider_or_human_action"):
        return "partially_recovered"
    if action == "not_recoverable":
        return "failed"
    return "recovered"


def _idempotency_next_action(status: str) -> str:
    return {
        "new_request": "Proceed if no active workflow lock exists.",
        "duplicate_completed": "Reuse the previous completed result if the caller requested replay.",
        "duplicate_in_progress": "Wait for active workflow or inspect lock state.",
        "duplicate_failed": "Run recovery before replaying this request.",
        "duplicate_conflicting_payload": "Use a new idempotency key or resolve the conflicting payload.",
        "replay_safe": "Replay deterministic stages only.",
    }.get(status, "Inspect idempotency report before replay.")


def _hashes(state_dir: Path, paths: list[str]) -> dict[str, str]:
    return {path: sha256_file(state_dir / path) for path in paths if (state_dir / path).is_file()}


def _hash_if_file(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _remaining_blockers(state_dir: Path) -> list[Any]:
    matrix = _optional_json(state_dir / "readiness-authorization-matrix.json")
    return list(matrix.get("blockers", []))


def _remaining_forbidden_claims(state_dir: Path) -> list[str]:
    matrix = _optional_json(state_dir / "readiness-authorization-matrix.json")
    return [str(item) for item in matrix.get("forbidden_claims", [])]


def _readiness_status(state_dir: Path) -> dict[str, str]:
    matrix = _optional_json(state_dir / "readiness-authorization-matrix.json")
    return {key: str(matrix.get(f"{key}_readiness_status", "missing")) for key in ("delivery", "apply", "review", "production")}


def _existing(state_dir: Path, names: list[str]) -> list[str]:
    return [name for name in names if (state_dir / name).is_file()]


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}-{_stable_hash(value)[:24]}"


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()
