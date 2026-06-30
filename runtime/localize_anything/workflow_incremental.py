from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, sha256_file, write_json
from .workflow import (
    STAGES,
    WORKFLOW_DEPENDENCY_GRAPH_JSON,
    WORKFLOW_EXECUTION_RESULT_JSON,
    WORKFLOW_READINESS_SUMMARY_JSON,
    WORKFLOW_RUN_PLAN_JSON,
    WORKFLOW_STAGE_STATUS_JSON,
    build_workflow_dependency_graph,
    build_workflow_stage_status,
    run_workflow,
)
from .workflow_hardening import (
    acquire_workflow_lock,
    append_workflow_checkpoint,
    build_workflow_idempotency_report,
    release_workflow_lock,
)


WORKFLOW_RESUME_PLAN_JSON = "workflow-resume-plan.json"
SELECTIVE_RECOMPUTE_PLAN_JSON = "selective-recompute-plan.json"
SELECTIVE_RECOMPUTE_RESULT_JSON = "selective-recompute-result.json"
ARTIFACT_INVALIDATION_REPORT_JSON = "artifact-invalidation-report.json"
INCREMENTAL_WORKFLOW_SUMMARY_JSON = "incremental-workflow-summary.json"

RESUME_SOURCES = {
    "workflow-execution-result",
    "workflow-stage-status",
    "artifact-state",
    "readiness-authorization-matrix",
    "manual-request",
    "unknown",
}

RECOMPUTE_STRATEGIES = {
    "minimal_safe",
    "all_stale_deterministic",
    "readiness_only",
    "knowledge_only",
    "document_only",
    "repair_only",
    "full_deterministic_refresh",
    "custom",
}


def build_artifact_invalidation_report(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    from .artifact_state import build_artifact_state

    state_dir = state_dir.resolve()
    previous = _optional_json(state_dir / "artifact-state.json")
    current = build_artifact_state(state_dir)
    previous_by_id = _artifacts_by_id(previous)
    current_by_id = _artifacts_by_id(current)
    items: list[dict[str, Any]] = []
    for artifact_id, artifact in current_by_id.items():
        status = str(artifact.get("status") or "missing")
        if status not in {"stale", "missing", "blocked"}:
            continue
        previous_artifact = previous_by_id.get(artifact_id, {})
        changed = _changed_dependencies(previous_artifact, artifact)
        changed_dependency = changed[0] if changed else ""
        dependency = current_by_id.get(changed_dependency, {})
        previous_dependency = previous_by_id.get(changed_dependency, {})
        path = str(artifact.get("path") or "")
        reason = "artifact_missing" if status == "missing" else _invalidation_reason(changed_dependency)
        items.append(
            {
                "invalidation_id": _stable_id("artifact-invalidation", [artifact_id, path, reason, changed]),
                "artifact_path": path,
                "artifact_type": str(artifact.get("artifact_type") or artifact_id),
                "previous_hash": previous_artifact.get("content_hash"),
                "current_hash": artifact.get("content_hash"),
                "invalidation_reason": reason,
                "changed_dependency": changed_dependency,
                "dependency_path": str(dependency.get("path") or changed_dependency),
                "dependency_hash_before": previous_dependency.get("content_hash") or previous_artifact.get("source_dependency_hashes", {}).get(changed_dependency),
                "dependency_hash_after": dependency.get("content_hash") or artifact.get("source_dependency_hashes", {}).get(changed_dependency),
                "affected_downstream_artifacts": list(artifact.get("downstream_affected", [])),
                "affected_workflow_stages": _affected_stage_ids(path, artifact_id),
                "affected_readiness_claims": _affected_claims(artifact),
                "severity": "blocking" if artifact.get("required_for_delivery") or status == "blocked" else "warning",
                "required_action": "Produce the missing artifact through its owning workflow." if status == "missing" else "Recompute the stale deterministic projection or preserve its pending human/provider state.",
                "source_artifact_references": ["artifact-state.json"],
            }
        )
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-artifact-invalidation-report-v1",
        "artifact": ARTIFACT_INVALIDATION_REPORT_JSON,
        "status": "blocked" if any(item["severity"] == "blocking" for item in items) else "stale" if items else "current",
        "items": items,
        "summary": {
            "invalidation_count": len(items),
            "blocking_count": sum(item["severity"] == "blocking" for item in items),
            "missing_count": sum(item["invalidation_reason"] == "artifact_missing" for item in items),
            "unknown_dependency_count": sum(item["invalidation_reason"] == "unknown_dependency_change" for item in items),
        },
        "blockers_cleared": False,
        "source_artifact_references": _existing(state_dir, ["artifact-state.json", WORKFLOW_DEPENDENCY_GRAPH_JSON]),
    }
    if write:
        write_json(state_dir / ARTIFACT_INVALIDATION_REPORT_JSON, report)
    return report


def build_workflow_resume_plan(
    state_dir: Path,
    *,
    requested_workflow_mode: str = "diagnose_only",
    resume_source: str | None = None,
    selected_stages: list[str] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    from .artifact_state import build_artifact_state

    state_dir = state_dir.resolve()
    source = _resume_source(state_dir, resume_source)
    if source not in RESUME_SOURCES:
        raise ValueError(f"resume_source must be one of: {', '.join(sorted(RESUME_SOURCES))}")
    previous_status = _optional_json(state_dir / WORKFLOW_STAGE_STATUS_JSON)
    previous_execution = _optional_json(state_dir / WORKFLOW_EXECUTION_RESULT_JSON)
    previous_plan = _optional_json(state_dir / WORKFLOW_RUN_PLAN_JSON)
    if requested_workflow_mode == "custom" and not selected_stages:
        selected_stages = [str(item.get("stage_type")) for item in previous_plan.get("selected_stages", []) if item.get("stage_type")]
    current_state = build_artifact_state(state_dir)
    status = build_workflow_stage_status(
        state_dir,
        workflow_mode=requested_workflow_mode,
        selected_stages=selected_stages,
        workflow_id=str(previous_execution.get("workflow_id") or previous_status.get("workflow_id") or "") or None,
    )
    selected = [item for item in status.get("stages", []) if item.get("status") != "skipped"]
    reusable = [item for item in selected if item.get("status") == "current"]
    deterministic = [item for item in selected if item.get("deterministic") and item.get("status") in {"stale", "ready_to_run", "missing"}]
    blocked = [item for item in selected if item.get("status") in {"blocked", "failed"}]
    human = [item for item in selected if item.get("status") == "requires_human_action"]
    provider = [item for item in selected if item.get("status") == "requires_provider_action"]
    matrix = _optional_json(state_dir / "readiness-authorization-matrix.json")
    resume_status = _resume_status(deterministic, blocked, human, provider, reusable)
    plan = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-resume-plan-v1",
        "artifact": WORKFLOW_RESUME_PLAN_JSON,
        "workflow_id": str(status.get("workflow_id") or previous_execution.get("workflow_id") or _stable_id("workflow-resume", [requested_workflow_mode, run_id])),
        "previous_workflow_id": str(previous_execution.get("workflow_id") or previous_status.get("workflow_id") or ""),
        "resume_source": source,
        "requested_workflow_mode": requested_workflow_mode,
        "resume_status": resume_status,
        "previous_stage_statuses": previous_status.get("stages", []),
        "current_artifact_state_snapshot": {
            "status": current_state.get("status", "unknown"),
            "summary": current_state.get("summary", {}),
            "artifact_state_sha256": _hash_if_file(state_dir / "artifact-state.json"),
        },
        "stale_artifacts": current_state.get("stale_artifacts", []),
        "missing_artifacts": current_state.get("missing_required_artifacts", []),
        "current_artifacts_that_can_be_reused": [_stage_summary(item, "reused_current") for item in reusable],
        "blocked_stages": blocked,
        "human_pending_stages": human,
        "provider_pending_stages": provider,
        "deterministic_stages_ready_to_resume": deterministic,
        "stages_skipped_as_current": [_stage_summary(item, "skipped_current") for item in reusable],
        "stages_skipped_as_not_applicable": [
            {**_stage_summary(item, "skipped_not_applicable"), "skip_reason": item.get("skip_reason", "")}
            for item in status.get("stages", [])
            if item.get("status") in {"not_applicable", "skipped"}
        ],
        "safety_policy": _safety_policy(),
        "recommended_next_stage": deterministic[0]["stage_id"] if deterministic else "",
        "readiness_blockers": list(matrix.get("blockers", [])),
        "forbidden_claims": list(matrix.get("forbidden_claims", [])),
        "source_artifact_references": _existing(state_dir, [WORKFLOW_EXECUTION_RESULT_JSON, WORKFLOW_STAGE_STATUS_JSON, "artifact-state.json", "readiness-authorization-matrix.json"]),
    }
    if write:
        write_json(state_dir / WORKFLOW_RESUME_PLAN_JSON, plan)
    return plan


def build_selective_recompute_plan(
    state_dir: Path,
    *,
    recompute_strategy: str = "minimal_safe",
    target_workflow_mode: str = "diagnose_only",
    selected_stages: list[str] | None = None,
    trigger_source: str = "manual-request",
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    if recompute_strategy not in RECOMPUTE_STRATEGIES:
        raise ValueError(f"recompute_strategy must be one of: {', '.join(sorted(RECOMPUTE_STRATEGIES))}")
    if recompute_strategy == "custom" and not selected_stages:
        raise ValueError("custom recompute requires at least one selected stage")
    resume = build_workflow_resume_plan(
        state_dir,
        requested_workflow_mode=target_workflow_mode,
        selected_stages=selected_stages if target_workflow_mode == "custom" else None,
        run_id=run_id,
    )
    invalidation = build_artifact_invalidation_report(state_dir)
    graph = build_workflow_dependency_graph(state_dir)
    stage_status = _optional_json(state_dir / WORKFLOW_STAGE_STATUS_JSON)
    all_stages = list(stage_status.get("stages", []))
    stages = [item for item in all_stages if item.get("status") != "skipped"]
    selected = _strategy_stage_types(recompute_strategy, stages, selected_stages)
    to_recompute = [item for item in stages if item.get("stage_type") in selected and item.get("deterministic") and item.get("status") in {"stale", "ready_to_run", "missing"}]
    reuse = [item for item in stages if item.get("status") == "current"]
    human = [item for item in stages if item.get("status") == "requires_human_action"]
    provider = [item for item in stages if item.get("status") == "requires_provider_action"]
    blocked = [item for item in stages if item.get("status") in {"blocked", "failed"}]
    dependency_order = [stage["stage_id"] for stage in STAGES if stage["stage_type"] in {item["stage_type"] for item in to_recompute}]
    plan_id = _stable_id("selective-recompute", [recompute_strategy, target_workflow_mode, dependency_order, invalidation.get("items", [])])
    plan = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-selective-recompute-plan-v1",
        "artifact": SELECTIVE_RECOMPUTE_PLAN_JSON,
        "recompute_plan_id": plan_id,
        "trigger_source": trigger_source,
        "target_workflow_mode": target_workflow_mode,
        "recompute_strategy": recompute_strategy,
        "artifacts_to_recompute": [_recompute_item(item) for item in to_recompute],
        "artifacts_to_reuse": [_recompute_item(item) for item in reuse],
        "artifacts_to_skip": [
            _recompute_item(item)
            for item in all_stages
            if item.get("status") in {"skipped", "not_applicable"}
            or (item.get("status") == "missing" and item.get("stage_type") not in selected)
        ],
        "artifacts_blocked": blocked,
        "artifacts_requiring_human_action": human,
        "artifacts_requiring_provider_action": provider,
        "dependency_order": dependency_order,
        "deterministic_builder_mapping": {item["stage_id"]: _builder_name(item["stage_type"]) for item in to_recompute},
        "safety_policy": _safety_policy(),
        "expected_readiness_impact": {
            "may_refresh_readiness_projections": any(item.get("stage_type") == "readiness_authorization" for item in to_recompute),
            "may_upgrade_readiness_without_current_matrix": False,
            "blockers_preserved": True,
            "forbidden_claims_preserved": True,
        },
        "workflow_resume_plan": WORKFLOW_RESUME_PLAN_JSON,
        "artifact_invalidation_report": ARTIFACT_INVALIDATION_REPORT_JSON,
        "workflow_dependency_graph": WORKFLOW_DEPENDENCY_GRAPH_JSON,
        "source_artifact_references": _existing(state_dir, [WORKFLOW_RESUME_PLAN_JSON, ARTIFACT_INVALIDATION_REPORT_JSON, WORKFLOW_DEPENDENCY_GRAPH_JSON]),
    }
    if write:
        write_json(state_dir / SELECTIVE_RECOMPUTE_PLAN_JSON, plan)
    return plan


def run_selective_recompute(
    state_dir: Path,
    *,
    recompute_strategy: str = "minimal_safe",
    target_workflow_mode: str = "diagnose_only",
    selected_stages: list[str] | None = None,
    trigger_source: str = "manual-request",
    run_id: str | None = None,
    idempotency_key: str | None = None,
    force_release_stale_lock: bool = False,
) -> dict[str, Any]:
    from .artifact_state import build_artifact_state

    state_dir = state_dir.resolve()
    idempotency = build_workflow_idempotency_report(
        state_dir,
        workflow_mode=target_workflow_mode,
        command="selective-recompute",
        request={
            "recompute_strategy": recompute_strategy,
            "target_workflow_mode": target_workflow_mode,
            "selected_stages": selected_stages or [],
            "trigger_source": trigger_source,
            "run_id": run_id,
        },
        idempotency_key=idempotency_key,
    )
    if idempotency.get("safety_decision") == "blocked" and not (force_release_stale_lock and idempotency.get("duplicate_status") != "duplicate_conflicting_payload"):
        result = _blocked_recompute_result(state_dir, recompute_strategy, idempotency)
        write_json(state_dir / SELECTIVE_RECOMPUTE_RESULT_JSON, result)
        build_incremental_workflow_summary(state_dir)
        return result
    before_hashes = _state_hashes(state_dir)
    before_readiness = _readiness_status(state_dir)
    plan = build_selective_recompute_plan(
        state_dir,
        recompute_strategy=recompute_strategy,
        target_workflow_mode=target_workflow_mode,
        selected_stages=selected_stages,
        trigger_source=trigger_source,
        run_id=run_id,
    )
    lock_state, acquired = acquire_workflow_lock(
        state_dir,
        workflow_id=plan["recompute_plan_id"],
        run_id=run_id,
        workflow_mode=target_workflow_mode,
        locked_stages=[str(item.get("stage_id")) for item in plan["artifacts_to_recompute"]],
        source_command="selective-recompute",
        force_release_stale_lock=force_release_stale_lock,
    )
    if not acquired:
        result = _blocked_recompute_result(state_dir, recompute_strategy, lock_state)
        write_json(state_dir / SELECTIVE_RECOMPUTE_RESULT_JSON, result)
        build_incremental_workflow_summary(state_dir)
        return result
    append_workflow_checkpoint(
        state_dir,
        workflow_id=plan["recompute_plan_id"],
        run_id=run_id,
        stage_id="selective-recompute",
        stage_type="selective_recompute",
        checkpoint_type="workflow_started",
        status="started",
        source_command="selective-recompute",
    )
    stage_types = [str(item.get("stage_type")) for item in plan["artifacts_to_recompute"] if item.get("stage_type")]
    workflow_result: dict[str, Any] = {}
    try:
        if stage_types:
            workflow_result = run_workflow(
                state_dir,
                workflow_mode="custom",
                selected_stages=stage_types,
                run_id=run_id,
                source_command="selective-recompute",
                use_hardening=False,
            )
    finally:
        release_workflow_lock(state_dir, status="released")
    after_hashes = _state_hashes(state_dir)
    failed = list(workflow_result.get("stages_failed", []))
    blocked = list(plan["artifacts_blocked"]) + list(workflow_result.get("stages_blocked", []))
    current_state = build_artifact_state(state_dir)
    left_stale = list(current_state.get("stale_artifacts", []))
    matrix = _optional_json(state_dir / "readiness-authorization-matrix.json")
    completed_ids = set(workflow_result.get("stages_completed", []))
    failed_ids = {str(item.get("stage_id")) for item in failed if isinstance(item, dict)}
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-selective-recompute-result-v1",
        "artifact": SELECTIVE_RECOMPUTE_RESULT_JSON,
        "recompute_plan_id": plan["recompute_plan_id"],
        "recompute_strategy_used": recompute_strategy,
        "status": "failed" if failed else "blocked" if blocked else "stale" if left_stale else "reused_current" if not stage_types else "completed",
        "items_attempted": [
            _result_item(item, "completed" if item.get("stage_id") in completed_ids else "failed" if item.get("stage_id") in failed_ids else "not_attempted")
            for item in plan["artifacts_to_recompute"]
        ],
        "items_completed": [_result_stage_id(item, "completed") for item in workflow_result.get("stages_completed", [])],
        "items_reused": [_result_item(item, "reused_current") for item in plan["artifacts_to_reuse"]],
        "items_skipped": [_result_item(item, "skipped_not_needed") for item in plan["artifacts_to_skip"]],
        "items_blocked": blocked,
        "items_failed": failed,
        "items_requiring_human_action": plan["artifacts_requiring_human_action"],
        "items_requiring_provider_action": plan["artifacts_requiring_provider_action"],
        "artifacts_created": sorted(path for path in after_hashes if path not in before_hashes),
        "artifacts_refreshed": sorted(path for path in after_hashes if path in before_hashes and before_hashes[path] != after_hashes[path]),
        "artifacts_left_stale": left_stale,
        "before_hashes": before_hashes,
        "after_hashes": after_hashes,
        "before_readiness_status": before_readiness,
        "after_readiness_status": _readiness_status(state_dir),
        "remaining_blockers": list(matrix.get("blockers", [])) + blocked,
        "remaining_forbidden_claims": list(matrix.get("forbidden_claims", [])),
        "next_recommended_action": _next_action(plan, failed, blocked),
        "provider_or_model_called": False,
        "repair_applied": False,
        "target_files_mutated": False,
        "safety_policy": _safety_policy(),
    }
    write_json(state_dir / SELECTIVE_RECOMPUTE_RESULT_JSON, result)
    append_workflow_checkpoint(
        state_dir,
        workflow_id=plan["recompute_plan_id"],
        run_id=run_id,
        stage_id="selective-recompute",
        stage_type="selective_recompute",
        checkpoint_type="workflow_failed" if failed else "workflow_completed",
        status=result["status"],
        output_artifact_paths=[SELECTIVE_RECOMPUTE_RESULT_JSON, INCREMENTAL_WORKFLOW_SUMMARY_JSON],
        source_command="selective-recompute",
    )
    _annotate_workflow_stage_status(state_dir, result)
    build_incremental_workflow_summary(state_dir)
    return result


def resume_workflow(
    state_dir: Path,
    *,
    requested_workflow_mode: str = "diagnose_only",
    resume_source: str | None = None,
    recompute_strategy: str = "minimal_safe",
    selected_stages: list[str] | None = None,
    run_id: str | None = None,
    idempotency_key: str | None = None,
    force_release_stale_lock: bool = False,
) -> dict[str, Any]:
    plan = build_workflow_resume_plan(
        state_dir,
        requested_workflow_mode=requested_workflow_mode,
        resume_source=resume_source,
        selected_stages=selected_stages,
        run_id=run_id,
    )
    result = run_selective_recompute(
        state_dir,
        recompute_strategy=recompute_strategy,
        target_workflow_mode=requested_workflow_mode,
        selected_stages=selected_stages,
        trigger_source=plan["resume_source"],
        run_id=run_id,
        idempotency_key=idempotency_key,
        force_release_stale_lock=force_release_stale_lock,
    )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-resume-command-v1",
        "workflow_resume_plan": plan,
        "selective_recompute_result": result,
        "incremental_workflow_summary": read_incremental_workflow_summary(state_dir),
        "provider_or_model_called": False,
        "repair_applied": False,
        "target_files_mutated": False,
    }


def build_incremental_workflow_summary(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    resume = _optional_json(state_dir / WORKFLOW_RESUME_PLAN_JSON)
    recompute = _optional_json(state_dir / SELECTIVE_RECOMPUTE_RESULT_JSON)
    matrix = _optional_json(state_dir / "readiness-authorization-matrix.json")
    artifact_state = _optional_json(state_dir / "artifact-state.json")
    summary = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-incremental-workflow-summary-v1",
        "artifact": INCREMENTAL_WORKFLOW_SUMMARY_JSON,
        "resume_status": resume.get("resume_status", "unknown"),
        "recompute_status": recompute.get("status", "not_attempted"),
        "artifacts_reused": recompute.get("items_reused", []),
        "artifacts_recomputed": recompute.get("items_completed", []),
        "artifacts_still_stale": recompute.get("artifacts_left_stale", artifact_state.get("stale_artifacts", [])),
        "stages_completed": recompute.get("items_completed", []),
        "stages_blocked": recompute.get("items_blocked", resume.get("blocked_stages", [])),
        "human_actions_remaining": recompute.get("items_requiring_human_action", resume.get("human_pending_stages", [])),
        "provider_actions_remaining": recompute.get("items_requiring_provider_action", resume.get("provider_pending_stages", [])),
        "repair_actions_remaining": _repair_actions(state_dir),
        "readiness_before": recompute.get("before_readiness_status", _readiness_status(state_dir)),
        "readiness_after": recompute.get("after_readiness_status", _readiness_status(state_dir)),
        "delivery_status": matrix.get("delivery_readiness_status", "missing"),
        "apply_status": matrix.get("apply_readiness_status", "missing"),
        "readiness_matrix_status": "missing" if not matrix else "stale" if _artifact_status(artifact_state, "readiness_authorization_matrix") == "stale" else "blocked" if matrix.get("blockers") else "current",
        "forbidden_claims_remaining": list(matrix.get("forbidden_claims", recompute.get("remaining_forbidden_claims", resume.get("forbidden_claims", [])))),
        "limitations": [
            "incremental resume and selective recompute do not imply workflow success",
            "delivery/apply readiness requires current readiness matrix and reports",
            "provider, human, and repair execution remain external pending actions",
        ],
        "recommended_next_action": recompute.get("next_recommended_action") or resume.get("recommended_next_stage") or "Refresh current readiness evidence.",
        "readiness_not_upgraded": True,
        "source_artifact_references": _existing(state_dir, [WORKFLOW_RESUME_PLAN_JSON, SELECTIVE_RECOMPUTE_PLAN_JSON, SELECTIVE_RECOMPUTE_RESULT_JSON, ARTIFACT_INVALIDATION_REPORT_JSON, "artifact-state.json", "readiness-authorization-matrix.json"]),
    }
    if write:
        write_json(state_dir / INCREMENTAL_WORKFLOW_SUMMARY_JSON, summary)
    return summary


def read_workflow_resume_plan(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKFLOW_RESUME_PLAN_JSON)


def read_artifact_invalidation_report(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / ARTIFACT_INVALIDATION_REPORT_JSON)


def read_selective_recompute_plan(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / SELECTIVE_RECOMPUTE_PLAN_JSON)


def read_selective_recompute_result(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / SELECTIVE_RECOMPUTE_RESULT_JSON)


def read_incremental_workflow_summary(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / INCREMENTAL_WORKFLOW_SUMMARY_JSON)


def incremental_workflow_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "workflow_resume_plan": WORKFLOW_RESUME_PLAN_JSON,
        "artifact_invalidation_report": ARTIFACT_INVALIDATION_REPORT_JSON,
        "selective_recompute_plan": SELECTIVE_RECOMPUTE_PLAN_JSON,
        "selective_recompute_result": SELECTIVE_RECOMPUTE_RESULT_JSON,
        "incremental_workflow_summary": INCREMENTAL_WORKFLOW_SUMMARY_JSON,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def _strategy_stage_types(strategy: str, stages: list[dict[str, Any]], selected: list[str] | None) -> set[str]:
    if strategy == "custom":
        known = {stage["stage_type"] for stage in STAGES}
        unknown = set(selected or []) - known
        if unknown:
            raise ValueError(f"Unknown workflow stages: {', '.join(sorted(unknown))}")
        return set(selected or [])
    if strategy == "readiness_only":
        return {"artifact_state", "evaluation_scorecard", "readiness_authorization", "workbench_projection"}
    if strategy == "knowledge_only":
        return {str(item["stage_type"]) for item in stages if "knowledge" in str(item.get("stage_type")) or item.get("stage_type") == "working_context_packet"}
    if strategy == "document_only":
        return {str(item["stage_type"]) for item in stages if "document" in str(item.get("stage_type"))}
    if strategy == "repair_only":
        return {str(item["stage_type"]) for item in stages if "repair" in str(item.get("stage_type"))}
    if strategy == "full_deterministic_refresh":
        return {str(item["stage_type"]) for item in stages if item.get("deterministic")}
    if strategy == "all_stale_deterministic":
        return {str(item["stage_type"]) for item in stages if item.get("deterministic") and item.get("status") == "stale"}
    return {
        str(item["stage_type"])
        for item in stages
        if item.get("deterministic") and item.get("status") in {"stale", "ready_to_run", "missing"}
    }


def _resume_source(state_dir: Path, requested: str | None) -> str:
    if requested:
        return requested
    for name, value in (
        (WORKFLOW_EXECUTION_RESULT_JSON, "workflow-execution-result"),
        (WORKFLOW_STAGE_STATUS_JSON, "workflow-stage-status"),
        ("artifact-state.json", "artifact-state"),
        ("readiness-authorization-matrix.json", "readiness-authorization-matrix"),
    ):
        if (state_dir / name).is_file():
            return value
    return "unknown"


def _resume_status(deterministic: list[dict[str, Any]], blocked: list[dict[str, Any]], human: list[dict[str, Any]], provider: list[dict[str, Any]], reusable: list[dict[str, Any]]) -> str:
    if deterministic:
        return "ready_to_resume"
    if blocked:
        return "blocked"
    if human:
        return "requires_human_action"
    if provider:
        return "requires_provider_action"
    if reusable:
        return "nothing_to_do"
    return "unknown"


def _changed_dependencies(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    explicit = current.get("stale_dependency_ids")
    if isinstance(explicit, list) and explicit:
        return [str(item) for item in explicit]
    before = previous.get("source_dependency_hashes", {}) if isinstance(previous.get("source_dependency_hashes"), dict) else {}
    after = current.get("source_dependency_hashes", {}) if isinstance(current.get("source_dependency_hashes"), dict) else {}
    return sorted(key for key, value in after.items() if before.get(key) != value)


def _invalidation_reason(dependency_id: str) -> str:
    value = dependency_id.lower()
    for needle, reason in (
        ("source", "source_changed"), ("generated", "target_changed"), ("brief", "brief_changed"),
        ("term", "term_governance_changed"), ("knowledge_pack", "knowledge_pack_changed"),
        ("working_context", "working_context_changed"), ("handoff", "provider_policy_changed"),
        ("human_review", "review_evidence_changed"), ("claim_acceptance", "claim_acceptance_changed"),
        ("signoff", "signoff_changed"), ("repair_result", "repair_result_changed"),
        ("repair_closure", "repair_closure_changed"), ("document", "document_evidence_changed"),
        ("readiness", "readiness_matrix_changed"), ("workflow", "workflow_plan_changed"),
    ):
        if needle in value:
            return reason
    return "unknown_dependency_change"


def _affected_stage_ids(path: str, artifact_id: str) -> list[str]:
    return [stage["stage_id"] for stage in STAGES if path in stage["input_artifacts"] or path in stage["output_artifacts"] or artifact_id in stage["input_artifacts"]]


def _affected_claims(artifact: dict[str, Any]) -> list[str]:
    claims: list[str] = []
    if artifact.get("required_for_handoff"):
        claims.extend(["provider_backed_quality", "review_complete"])
    if artifact.get("required_for_delivery"):
        claims.extend(["delivery_ready", "apply_ready", "production_ready"])
    return list(dict.fromkeys(claims))


def _recompute_item(stage: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_id": _stable_id("recompute-item", [stage.get("stage_id"), stage.get("status")]),
        "stage_id": stage.get("stage_id"),
        "stage_type": stage.get("stage_type"),
        "status": stage.get("status"),
        "input_artifacts": stage.get("input_artifacts", []),
        "output_artifacts": stage.get("output_artifacts", []),
    }


def _builder_name(stage_type: str) -> str:
    stage = next((item for item in STAGES if item["stage_type"] == stage_type), {})
    return str(stage.get("builder") or "owning_workflow_required")


def _stage_summary(stage: dict[str, Any], status: str) -> dict[str, Any]:
    return {"stage_id": stage.get("stage_id"), "stage_type": stage.get("stage_type"), "status": status, "output_artifacts": stage.get("output_artifacts", [])}


def _result_item(item: dict[str, Any], status: str) -> dict[str, Any]:
    return {"item_id": item.get("item_id"), "stage_id": item.get("stage_id"), "stage_type": item.get("stage_type"), "status": status}


def _result_stage_id(stage_id: str, status: str) -> dict[str, Any]:
    stage = next((item for item in STAGES if item["stage_id"] == stage_id), {})
    return {"stage_id": stage_id, "stage_type": stage.get("stage_type", ""), "status": status}


def _blocked_recompute_result(state_dir: Path, recompute_strategy: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-selective-recompute-result-v1",
        "artifact": SELECTIVE_RECOMPUTE_RESULT_JSON,
        "recompute_plan_id": "",
        "recompute_strategy_used": recompute_strategy,
        "status": "blocked",
        "items_attempted": [],
        "items_completed": [],
        "items_reused": [],
        "items_skipped": [],
        "items_blocked": [{"stage_id": "selective-recompute", "status": "blocked", "blockers": [evidence]}],
        "items_failed": [],
        "items_requiring_human_action": [],
        "items_requiring_provider_action": [],
        "artifacts_created": [],
        "artifacts_refreshed": [],
        "artifacts_left_stale": [],
        "before_hashes": _state_hashes(state_dir),
        "after_hashes": _state_hashes(state_dir),
        "before_readiness_status": _readiness_status(state_dir),
        "after_readiness_status": _readiness_status(state_dir),
        "remaining_blockers": [{"type": "workflow_hardening_blocked", "evidence": evidence}],
        "remaining_forbidden_claims": ["delivery_ready", "apply_ready", "production_ready"],
        "next_recommended_action": "Inspect workflow hardening evidence before replaying selective recompute.",
        "provider_or_model_called": False,
        "repair_applied": False,
        "target_files_mutated": False,
        "safety_policy": _safety_policy(),
    }


def _annotate_workflow_stage_status(state_dir: Path, result: dict[str, Any]) -> None:
    status = _optional_json(state_dir / WORKFLOW_STAGE_STATUS_JSON)
    if not status:
        return
    completed = {item.get("stage_id") for item in result.get("items_completed", [])}
    reused = {item.get("stage_id") for item in result.get("items_reused", [])}
    for item in status.get("stages", []):
        if item.get("stage_id") in completed:
            item["incremental_status"] = "completed"
        elif item.get("stage_id") in reused:
            item["incremental_status"] = "reused_current"
        elif item.get("status") in {"blocked", "requires_human_action", "requires_provider_action", "skipped"}:
            item["incremental_status"] = item.get("status")
    write_json(state_dir / WORKFLOW_STAGE_STATUS_JSON, status)


def _repair_actions(state_dir: Path) -> list[Any]:
    impact = _optional_json(state_dir / "knowledge-repair-impact-report.json")
    return impact.get("open_decisions_or_confirmations_required", impact.get("open_decisions", []))


def _next_action(plan: dict[str, Any], failed: list[Any], blocked: list[Any]) -> str:
    if failed:
        return "Fix the failed deterministic builder and rerun selective recompute."
    if blocked:
        return "Resolve blocked, human, or provider stages through their owning evidence pathways."
    if plan.get("artifacts_requiring_human_action"):
        return "Record required scoped human evidence before resuming."
    if plan.get("artifacts_requiring_provider_action"):
        return "Run authorized provider/model work externally and ingest evidence before resuming."
    return "Refresh Artifact State and Readiness Authorization Matrix after upstream evidence changes."


def _safety_policy() -> dict[str, Any]:
    return {
        "deterministic_builders_only": True,
        "dependency_clean_reuse_required": True,
        "provider_or_model_execution_allowed": False,
        "semantic_rewrite_allowed": False,
        "repair_application_allowed": False,
        "target_file_mutation_allowed": False,
        "incremental_completion_implies_readiness": False,
    }


def _readiness_status(state_dir: Path) -> dict[str, str]:
    matrix = _optional_json(state_dir / "readiness-authorization-matrix.json")
    return {key: str(matrix.get(f"{key}_readiness_status", "missing")) for key in ("delivery", "apply", "review", "production")}


def _artifact_status(state: dict[str, Any], artifact_id: str) -> str:
    return str(_artifacts_by_id(state).get(artifact_id, {}).get("status") or "missing")


def _artifacts_by_id(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("artifact_id")): item for item in state.get("artifacts", []) if isinstance(item, dict) and item.get("artifact_id")}


def _state_hashes(state_dir: Path) -> dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(state_dir.iterdir()) if path.is_file()}


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _hash_if_file(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _existing(state_dir: Path, names: list[str]) -> dict[str, dict[str, str]]:
    return {name: {"path": name, "sha256": sha256_file(state_dir / name)} for name in names if (state_dir / name).is_file()}


def _stable_id(prefix: str, value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:24]}"
