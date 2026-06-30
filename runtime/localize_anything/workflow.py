from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from . import PROTOCOL_VERSION
from .io_utils import read_json, sha256_file, write_json
from .workflow_hardening import (
    append_workflow_checkpoint,
    acquire_workflow_lock,
    build_workflow_idempotency_report,
    record_workflow_transaction,
    release_workflow_lock,
)


WORKFLOW_RUN_PLAN_JSON = "workflow-run-plan.json"
WORKFLOW_STAGE_STATUS_JSON = "workflow-stage-status.json"
WORKFLOW_EXECUTION_RESULT_JSON = "workflow-execution-result.json"
WORKFLOW_READINESS_SUMMARY_JSON = "workflow-readiness-summary.json"
WORKFLOW_DEPENDENCY_GRAPH_JSON = "workflow-dependency-graph.json"

WORKFLOW_MODES = {
    "diagnose_only",
    "preflight_only",
    "review_ready_document",
    "delivery_readiness_check",
    "apply_readiness_check",
    "knowledge_pack_export",
    "knowledge_consumption_check",
    "knowledge_repair_cycle",
    "full_evidence_refresh",
    "custom",
}

STAGE_STATUS_VALUES = {
    "current",
    "missing",
    "stale",
    "ready_to_run",
    "completed",
    "skipped",
    "blocked",
    "failed",
    "requires_human_action",
    "requires_provider_action",
    "not_applicable",
}


def _stage(
    stage_type: str,
    name: str,
    *,
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
    dependencies: tuple[str, ...] = (),
    builder: str | None = None,
    human: bool = False,
    provider: bool = False,
) -> dict[str, Any]:
    return {
        "stage_id": f"workflow-stage-{stage_type}",
        "stage_type": stage_type,
        "stage_name": name,
        "input_artifacts": list(inputs),
        "output_artifacts": list(outputs),
        "dependency_stage_ids": [f"workflow-stage-{item}" for item in dependencies],
        "builder": builder,
        "deterministic": not provider and not human,
        "may_write_artifacts": bool(outputs),
        "may_call_provider": provider,
        "may_mutate_target_files": False,
        "requires_human_action": human,
        "requires_provider_action": provider,
    }


STAGES: tuple[dict[str, Any], ...] = (
    _stage("source_discovery", "Source discovery", outputs=("project-intake-report.json", "source-inventory.json")),
    _stage("coverage_diagnostics", "Coverage diagnostics", inputs=("source-inventory.json",), outputs=("coverage-report.json",), dependencies=("source_discovery",)),
    _stage("localization_brief", "Localization brief", inputs=("source-inventory.json",), outputs=("localization-brief.json",), dependencies=("source_discovery",)),
    _stage("term_governance", "Term governance", inputs=("localization-brief.json",), outputs=("term-registry.csv", "term-decisions.jsonl", "forbidden-translations.csv"), dependencies=("localization_brief",), human=True),
    _stage("termbase_preflight", "Termbase preflight", inputs=("localization-brief.json",), outputs=("termbase-preflight-report.json",), dependencies=("localization_brief", "term_governance")),
    _stage("generation_strategy", "Generation strategy", inputs=("localization-brief.json", "termbase-preflight-report.json"), outputs=("generation-strategy.json",), dependencies=("termbase_preflight",)),
    _stage("resolution_gate", "Resolution gate", inputs=("generation-strategy.json",), outputs=("blocking-questions.json", "user-resolution-decisions.jsonl"), dependencies=("generation_strategy",), human=True),
    _stage("provider_evidence", "Provider evidence", inputs=("generation-handoff-decision.json",), outputs=("provider-execution-policy.json", "provider-handoff-request.json", "provider-execution-ledger.jsonl", "provider-evidence-reconciliation.json"), dependencies=("resolution_gate",), builder="provider_evidence"),
    _stage("generation_handoff", "Generation handoff", inputs=("generation-handoff-decision.json", "provider-evidence-reconciliation.json"), outputs=("generated-segments.jsonl",), dependencies=("provider_evidence",), provider=True),
    _stage("artifact_state", "Artifact state", outputs=("artifact-state.json",), builder="artifact_state"),
    _stage("segment_staleness", "Segment staleness", inputs=("generated-segments.jsonl",), outputs=("stale-segments.jsonl",), dependencies=("generation_handoff",)),
    _stage("reuse_decision", "Reuse decision", inputs=("stale-segments.jsonl",), outputs=("reuse-decision.json",), dependencies=("segment_staleness",)),
    _stage("repair_planning", "Segment repair planning", inputs=("reuse-decision.json",), outputs=("segment-regeneration-plan.json", "repair-request.json"), dependencies=("reuse_decision",)),
    _stage("repair_result_intake", "Repair result intake", inputs=("repair-request.json",), outputs=("repair-result.json",), dependencies=("repair_planning",), human=True),
    _stage("repair_qa_reconciliation", "Repair QA reconciliation", inputs=("repair-result.json",), outputs=("repair-history.jsonl",), dependencies=("repair_result_intake",)),
    _stage("evaluation_scorecard", "Evaluation scorecard", inputs=("artifact-state.json",), outputs=("evaluation-scorecard.json",), dependencies=("artifact_state",), builder="evaluation_scorecard"),
    _stage("human_review", "Human review", inputs=("evaluation-scorecard.json",), outputs=("human-review-evidence.jsonl",), dependencies=("evaluation_scorecard",), human=True),
    _stage("claim_acceptance", "Claim acceptance", inputs=("evaluation-scorecard.json", "human-review-evidence.jsonl"), outputs=("claim-acceptance-decision.json",), dependencies=("human_review",), human=True),
    _stage("signoff", "Signoff", inputs=("claim-acceptance-decision.json",), outputs=("signoff-record.json",), dependencies=("claim_acceptance",), human=True),
    _stage("document_evidence_pack", "Document evidence pack", inputs=("generated-segments.jsonl",), outputs=("document-evidence-manifest.json",), dependencies=("generation_handoff",)),
    _stage("document_decision_resolution", "Document decision resolution", inputs=("document-evidence-manifest.json",), outputs=("document-claim-resolution.json", "document-signoff-summary.json"), dependencies=("document_evidence_pack",), builder="document_decision_resolution"),
    _stage("knowledge_pack_export", "Knowledge pack export", inputs=("signoff-record.json",), outputs=("knowledge-packs",), dependencies=("signoff",), human=True),
    _stage("knowledge_pack_selection", "Knowledge pack selection", inputs=("localization-brief.json",), outputs=("knowledge-pack-selection.json",), dependencies=("localization_brief",), human=True),
    _stage("working_context_packet", "Working context packet", inputs=("knowledge-pack-selection.json",), outputs=("knowledge-eligibility-report.json", "working-context-packet.json"), dependencies=("knowledge_pack_selection",), builder="working_context_packet"),
    _stage("knowledge_usage_audit", "Knowledge usage audit", inputs=("working-context-packet.json", "generated-segments.jsonl"), outputs=("knowledge-usage-report.json", "constraint-application-audit.json", "knowledge-conflict-report.json"), dependencies=("working_context_packet", "generation_handoff"), builder="knowledge_usage_audit"),
    _stage("knowledge_audit_enforcement", "Knowledge audit enforcement", inputs=("constraint-application-audit.json", "knowledge-conflict-report.json"), outputs=("knowledge-audit-enforcement-decision.json",), dependencies=("knowledge_usage_audit",), builder="knowledge_audit_enforcement"),
    _stage("knowledge_review_confirmation", "Knowledge review confirmation", inputs=("knowledge-audit-enforcement-decision.json",), outputs=("knowledge-assurance-summary.json", "knowledge-conflict-resolution.json"), dependencies=("knowledge_audit_enforcement",), human=True),
    _stage("knowledge_repair_planning", "Knowledge repair planning", inputs=("knowledge-audit-enforcement-decision.json",), outputs=("knowledge-repair-plan.json", "knowledge-repair-request.json", "knowledge-repair-impact-report.json"), dependencies=("knowledge_audit_enforcement",), builder="knowledge_repair_planning"),
    _stage("knowledge_repair_result_reconciliation", "Knowledge repair result reconciliation", inputs=("knowledge-repair-request.json", "knowledge-repair-result-intake.jsonl"), outputs=("knowledge-repair-qa-report.json", "knowledge-repair-reconciliation.json"), dependencies=("knowledge_repair_planning",), builder="knowledge_repair_result_reconciliation"),
    _stage("knowledge_repair_closure_recompute", "Knowledge repair closure recompute", inputs=("knowledge-repair-reconciliation.json",), outputs=("knowledge-recompute-plan.json", "knowledge-recompute-result.json", "knowledge-repair-closure-decision.json", "knowledge-readiness-impact-report.json"), dependencies=("knowledge_repair_result_reconciliation",), builder="knowledge_repair_closure_recompute"),
    _stage(
        "readiness_authorization",
        "Readiness authorization",
        inputs=("artifact-state.json", "evaluation-scorecard.json", "claim-acceptance-decision.json", "signoff-record.json", "document-evidence-manifest.json", "knowledge-audit-enforcement-decision.json", "knowledge-repair-closure-decision.json", "generation-handoff-decision.json", "provider-evidence-reconciliation.json"),
        outputs=("readiness-authorization-matrix.json", "manual-followup-gap-report.json", "delivery-readiness-report.json", "apply-readiness-report.json"),
        dependencies=("artifact_state", "evaluation_scorecard", "claim_acceptance", "signoff", "document_decision_resolution", "knowledge_audit_enforcement", "knowledge_repair_closure_recompute"),
        builder="readiness_authorization",
    ),
    _stage("workbench_projection", "Workbench projection", inputs=("readiness-authorization-matrix.json", "manual-followup-gap-report.json"), outputs=("workbench-readiness-action-queue.json", "workbench-review-queue.json", "workbench-claim-queue.json", "workbench-signoff-summary.json"), dependencies=("readiness_authorization",), builder="workbench_projection"),
    _stage("delivery_package", "Delivery package", inputs=("readiness-authorization-matrix.json", "signoff-record.json"), outputs=("delivery-manifest.json",), dependencies=("readiness_authorization", "signoff")),
    _stage("apply_plan", "Apply plan", inputs=("apply-readiness-report.json", "delivery-manifest.json"), outputs=("apply-plan.json",), dependencies=("readiness_authorization", "delivery_package")),
)

_STAGE_BY_TYPE = {stage["stage_type"]: stage for stage in STAGES}

MODE_STAGES = {
    "diagnose_only": {"artifact_state", "provider_evidence", "evaluation_scorecard", "readiness_authorization", "workbench_projection"},
    "preflight_only": {"source_discovery", "coverage_diagnostics", "localization_brief", "term_governance", "termbase_preflight", "generation_strategy", "resolution_gate", "artifact_state"},
    "review_ready_document": {"artifact_state", "evaluation_scorecard", "human_review", "claim_acceptance", "signoff", "document_evidence_pack", "document_decision_resolution", "readiness_authorization", "workbench_projection"},
    "delivery_readiness_check": {"artifact_state", "evaluation_scorecard", "claim_acceptance", "signoff", "document_decision_resolution", "knowledge_audit_enforcement", "knowledge_repair_closure_recompute", "readiness_authorization", "workbench_projection", "delivery_package"},
    "apply_readiness_check": {"artifact_state", "evaluation_scorecard", "claim_acceptance", "signoff", "knowledge_repair_closure_recompute", "readiness_authorization", "workbench_projection", "delivery_package", "apply_plan"},
    "knowledge_pack_export": {"artifact_state", "human_review", "claim_acceptance", "signoff", "knowledge_pack_export"},
    "knowledge_consumption_check": {"artifact_state", "knowledge_pack_selection", "working_context_packet", "knowledge_usage_audit", "knowledge_audit_enforcement", "knowledge_review_confirmation", "evaluation_scorecard", "readiness_authorization"},
    "knowledge_repair_cycle": {"artifact_state", "knowledge_usage_audit", "knowledge_audit_enforcement", "knowledge_review_confirmation", "knowledge_repair_planning", "knowledge_repair_result_reconciliation", "knowledge_repair_closure_recompute", "evaluation_scorecard", "readiness_authorization", "workbench_projection"},
    "full_evidence_refresh": {stage["stage_type"] for stage in STAGES},
}


def build_workflow_run_plan(
    state_dir: Path,
    *,
    workflow_mode: str = "diagnose_only",
    selected_stages: list[str] | None = None,
    scenario: str | None = None,
    source_locale: str | None = None,
    target_locale: str | None = None,
    target_delivery_mode: str | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    selected = _selected_stage_types(workflow_mode, selected_stages)
    context = _workflow_context(state_dir, scenario, source_locale, target_locale, target_delivery_mode)
    statuses = _evaluate_stages(state_dir, selected)
    workflow_id = _workflow_id(workflow_mode, selected, context, run_id)
    selected_items = [item for item in statuses if item["stage_type"] in selected]
    plan = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-run-plan-v1",
        "artifact": WORKFLOW_RUN_PLAN_JSON,
        "workflow_id": workflow_id,
        "run_id": run_id,
        "workflow_mode": workflow_mode,
        **context,
        "selected_stages": selected_items,
        "skipped_stages": [item for item in statuses if item["status"] == "skipped"],
        "blocked_stages": [item for item in selected_items if item["status"] == "blocked"],
        "required_human_actions": [_pending_action(item) for item in selected_items if item["status"] == "requires_human_action"],
        "required_provider_model_actions": [_pending_action(item) for item in selected_items if item["status"] == "requires_provider_action"],
        "deterministic_stages_that_can_run_now": [item["stage_id"] for item in selected_items if item["status"] in {"ready_to_run", "stale"} and item["deterministic"]],
        "input_artifacts": _unique(item for stage in selected_items for item in stage["input_artifacts"]),
        "expected_output_artifacts": _unique(item for stage in selected_items for item in stage["output_artifacts"]),
        "dependency_order": [stage["stage_id"] for stage in STAGES if stage["stage_type"] in selected],
        "safety_policy": _safety_policy(),
        "source_artifact_references": _existing_artifacts(state_dir, [item for stage in selected_items for item in stage["input_artifacts"]]),
    }
    if write:
        state_dir.mkdir(parents=True, exist_ok=True)
        write_json(state_dir / WORKFLOW_RUN_PLAN_JSON, plan)
    return plan


def build_workflow_stage_status(
    state_dir: Path,
    *,
    workflow_mode: str = "diagnose_only",
    selected_stages: list[str] | None = None,
    workflow_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    selected = _selected_stage_types(workflow_mode, selected_stages)
    stages = _evaluate_stages(state_dir, selected)
    selected_items = [item for item in stages if item["stage_type"] in selected]
    artifact_state_hash = _hash_if_file(state_dir / "artifact-state.json")
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-stage-status-v1",
        "artifact": WORKFLOW_STAGE_STATUS_JSON,
        "workflow_id": workflow_id or _workflow_id(workflow_mode, selected, _workflow_context(state_dir, None, None, None, None), None),
        "workflow_mode": workflow_mode,
        "status": _stage_collection_status(selected_items),
        "stages": stages,
        "summary": {status: sum(item["status"] == status for item in stages) for status in sorted(STAGE_STATUS_VALUES)},
        "stale_triggers": [trigger for item in selected_items for trigger in item["stale_triggers"]],
        "artifact_state_sha256": artifact_state_hash,
        "source_artifact_references": _existing_artifacts(state_dir, ["artifact-state.json", WORKFLOW_RUN_PLAN_JSON]),
    }
    if write:
        write_json(state_dir / WORKFLOW_STAGE_STATUS_JSON, result)
    return result


def build_workflow_dependency_graph(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    edges: list[dict[str, Any]] = []
    for stage in STAGES:
        for dependency in stage["dependency_stage_ids"]:
            edges.append(_edge(dependency, stage["stage_id"], "requires", True, True, True))
        for artifact in stage["input_artifacts"]:
            edges.append(_edge(f"artifact:{artifact}", stage["stage_id"], "requires", True, True, True))
        for artifact in stage["output_artifacts"]:
            edges.append(_edge(stage["stage_id"], f"artifact:{artifact}", "refreshes", False, False, False))
    edges.extend(
        [
            _edge("artifact:generated-segments.jsonl", "workflow-stage-segment_staleness", "invalidates", True, False, True),
            _edge("artifact:signoff-record.json", "workflow-stage-readiness_authorization", "blocks", True, True, True),
            _edge("artifact:workflow-readiness-summary.json", "workflow-stage-delivery_package", "downgrades", False, False, False),
            _edge("artifact:workflow-execution-result.json", "artifact:run-summary.json", "references", False, False, False),
            _edge("artifact:working-context-packet.json", "workflow-stage-generation_handoff", "optional_context", True, False, True),
        ]
    )
    graph = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-dependency-graph-v1",
        "artifact": WORKFLOW_DEPENDENCY_GRAPH_JSON,
        "stages": [_public_stage(stage) for stage in STAGES],
        "artifacts": sorted({artifact for stage in STAGES for artifact in stage["input_artifacts"] + stage["output_artifacts"]}),
        "edges": edges,
        "supported_dependency_types": ["requires", "refreshes", "invalidates", "blocks", "downgrades", "references", "optional_context"],
        "readiness_dependencies": {
            "scorecard": "evaluation-scorecard.json",
            "artifact_state": "artifact-state.json",
            "signoff": "signoff-record.json",
            "claim_acceptance": "claim-acceptance-decision.json",
            "document_evidence": "document-evidence-manifest.json",
            "knowledge_evidence": "knowledge-audit-enforcement-decision.json",
            "repair_closure": "knowledge-repair-closure-decision.json",
            "provider_policy": "generation-handoff-decision.json",
            "coverage": "coverage-report.json",
            "qa": "review-result.json",
        },
        "safety_policy": _safety_policy(),
    }
    if write:
        write_json(state_dir / WORKFLOW_DEPENDENCY_GRAPH_JSON, graph)
    return graph


def run_workflow(
    state_dir: Path,
    *,
    workflow_mode: str = "diagnose_only",
    selected_stages: list[str] | None = None,
    scenario: str | None = None,
    source_locale: str | None = None,
    target_locale: str | None = None,
    target_delivery_mode: str | None = None,
    run_id: str | None = None,
    idempotency_key: str | None = None,
    force_release_stale_lock: bool = False,
    source_command: str = "workflow-run",
    use_hardening: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    initial_hashes = _state_hashes(state_dir)
    plan = build_workflow_run_plan(
        state_dir,
        workflow_mode=workflow_mode,
        selected_stages=selected_stages,
        scenario=scenario,
        source_locale=source_locale,
        target_locale=target_locale,
        target_delivery_mode=target_delivery_mode,
        run_id=run_id,
    )
    request = {
        "workflow_mode": workflow_mode,
        "selected_stages": selected_stages or [],
        "scenario": scenario,
        "source_locale": source_locale,
        "target_locale": target_locale,
        "target_delivery_mode": target_delivery_mode,
        "run_id": run_id,
    }
    idempotency = build_workflow_idempotency_report(
        state_dir,
        workflow_mode=workflow_mode,
        command=source_command,
        request=request,
        idempotency_key=idempotency_key,
    )
    if idempotency.get("duplicate_status") == "duplicate_completed" and (state_dir / WORKFLOW_EXECUTION_RESULT_JSON).is_file():
        return read_workflow_execution_result(state_dir)
    if idempotency.get("safety_decision") == "blocked" and not (force_release_stale_lock and idempotency.get("duplicate_status") != "duplicate_conflicting_payload"):
        result = _blocked_workflow_result(plan, workflow_mode, "idempotency_blocked", idempotency)
        write_json(state_dir / WORKFLOW_EXECUTION_RESULT_JSON, result)
        build_workflow_readiness_summary(state_dir, workflow_id=plan["workflow_id"])
        return result
    acquired = True
    lock_state: dict[str, Any] = {}
    if use_hardening:
        lock_state, acquired = acquire_workflow_lock(
            state_dir,
            workflow_id=plan["workflow_id"],
            run_id=run_id,
            workflow_mode=workflow_mode,
            locked_stages=[item["stage_id"] for item in plan["selected_stages"]],
            source_command=source_command,
            force_release_stale_lock=force_release_stale_lock,
        )
    if not acquired:
        append_workflow_checkpoint(
            state_dir,
            workflow_id=plan["workflow_id"],
            run_id=run_id,
            stage_id="workflow-lock",
            stage_type="workflow_lock",
            checkpoint_type="stage_blocked",
            status="blocked",
            error_summary="workflow lock is active or stale",
            recovery_hint=str(lock_state.get("recovery_recommendation") or "inspect workflow-lock-state.json"),
            source_command=source_command,
        )
        result = _blocked_workflow_result(plan, workflow_mode, "workflow_lock_blocked", lock_state)
        write_json(state_dir / WORKFLOW_EXECUTION_RESULT_JSON, result)
        build_workflow_readiness_summary(state_dir, workflow_id=plan["workflow_id"])
        return result
    append_workflow_checkpoint(
        state_dir,
        workflow_id=plan["workflow_id"],
        run_id=run_id,
        stage_id="workflow",
        stage_type="workflow",
        checkpoint_type="workflow_started",
        status="started",
        source_command=source_command,
    )
    build_workflow_dependency_graph(state_dir)
    selected = {item["stage_type"] for item in plan["selected_stages"]}
    before_hashes = dict(initial_hashes)
    before_readiness = _readiness_status(state_dir)
    builders = _builders(state_dir, run_id)
    attempted: list[str] = []
    completed: list[str] = []
    skipped: list[dict[str, str]] = []
    blocked: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    called: list[str] = []
    try:
        for stage in STAGES:
            if stage["stage_type"] not in selected:
                continue
            item = next(value for value in plan["selected_stages"] if value["stage_type"] == stage["stage_type"])
            append_workflow_checkpoint(
                state_dir,
                workflow_id=plan["workflow_id"],
                run_id=run_id,
                stage_id=stage["stage_id"],
                stage_type=stage["stage_type"],
                checkpoint_type="stage_planned",
                status=item["status"],
                output_artifact_paths=stage["output_artifacts"],
                source_command=source_command,
            )
            if item["status"] in {"current", "completed"}:
                skipped.append({"stage_id": stage["stage_id"], "reason": "outputs are current"})
                append_workflow_checkpoint(state_dir, workflow_id=plan["workflow_id"], run_id=run_id, stage_id=stage["stage_id"], stage_type=stage["stage_type"], checkpoint_type="stage_skipped", status="skipped", output_artifact_paths=stage["output_artifacts"], source_command=source_command)
                continue
            if item["status"] in {"requires_human_action", "requires_provider_action", "blocked"}:
                blocked.append({"stage_id": stage["stage_id"], "status": item["status"], "blockers": item["blocking_conditions"]})
                append_workflow_checkpoint(state_dir, workflow_id=plan["workflow_id"], run_id=run_id, stage_id=stage["stage_id"], stage_type=stage["stage_type"], checkpoint_type="stage_blocked", status=item["status"], output_artifact_paths=stage["output_artifacts"], recovery_hint=item.get("next_action", ""), source_command=source_command)
                continue
            builder_name = stage.get("builder")
            builder = builders.get(str(builder_name)) if builder_name else None
            if builder is None:
                skipped.append({"stage_id": stage["stage_id"], "reason": "no safe state-only deterministic builder is registered"})
                append_workflow_checkpoint(state_dir, workflow_id=plan["workflow_id"], run_id=run_id, stage_id=stage["stage_id"], stage_type=stage["stage_type"], checkpoint_type="stage_skipped", status="skipped", output_artifact_paths=stage["output_artifacts"], recovery_hint="no deterministic builder registered", source_command=source_command)
                continue
            attempted.append(stage["stage_id"])
            previous_output_hashes = _artifact_hashes(state_dir, stage["output_artifacts"])
            transaction = record_workflow_transaction(
                state_dir,
                workflow_id=plan["workflow_id"],
                run_id=run_id,
                stage_id=stage["stage_id"],
                artifact_paths=stage["output_artifacts"],
                transaction_status="staged",
                previous_hashes=previous_output_hashes,
            )
            append_workflow_checkpoint(state_dir, workflow_id=plan["workflow_id"], run_id=run_id, stage_id=stage["stage_id"], stage_type=stage["stage_type"], checkpoint_type="stage_started", status="started", output_artifact_paths=stage["output_artifacts"], transaction_id=transaction["transaction_id"], source_command=source_command)
            try:
                builder()
                completed.append(stage["stage_id"])
                called.append(str(builder_name))
                record_workflow_transaction(
                    state_dir,
                    workflow_id=plan["workflow_id"],
                    run_id=run_id,
                    stage_id=stage["stage_id"],
                    artifact_paths=stage["output_artifacts"],
                    transaction_status="committed",
                    transaction_id=transaction["transaction_id"],
                    previous_hashes=previous_output_hashes,
                )
                append_workflow_checkpoint(state_dir, workflow_id=plan["workflow_id"], run_id=run_id, stage_id=stage["stage_id"], stage_type=stage["stage_type"], checkpoint_type="artifact_write_committed", status="committed", output_artifact_paths=stage["output_artifacts"], transaction_id=transaction["transaction_id"], source_command=source_command)
                append_workflow_checkpoint(state_dir, workflow_id=plan["workflow_id"], run_id=run_id, stage_id=stage["stage_id"], stage_type=stage["stage_type"], checkpoint_type="stage_completed", status="completed", output_artifact_paths=stage["output_artifacts"], transaction_id=transaction["transaction_id"], source_command=source_command)
            except Exception as exc:  # deterministic builder failures are lifecycle evidence
                failed.append({"stage_id": stage["stage_id"], "reason": str(exc)})
                record_workflow_transaction(
                    state_dir,
                    workflow_id=plan["workflow_id"],
                    run_id=run_id,
                    stage_id=stage["stage_id"],
                    artifact_paths=stage["output_artifacts"],
                    transaction_status="failed",
                    transaction_id=transaction["transaction_id"],
                    previous_hashes=previous_output_hashes,
                    recovery_status="requires_recompute",
                )
                append_workflow_checkpoint(state_dir, workflow_id=plan["workflow_id"], run_id=run_id, stage_id=stage["stage_id"], stage_type=stage["stage_type"], checkpoint_type="stage_failed", status="failed", output_artifact_paths=stage["output_artifacts"], transaction_id=transaction["transaction_id"], error_summary=str(exc), recovery_hint="inspect deterministic builder failure and rerun recovery", source_command=source_command)
    finally:
        if use_hardening:
            release_workflow_lock(state_dir, status="released" if not failed else "abandoned")
    _builders(state_dir, run_id)["artifact_state"]()
    after_hashes = _state_hashes(state_dir)
    artifacts_created = sorted(path for path, digest in after_hashes.items() if digest and not before_hashes.get(path))
    artifacts_created = _unique(
        [
            *artifacts_created,
            *(
                name
                for name in (
                    WORKFLOW_RUN_PLAN_JSON,
                    WORKFLOW_DEPENDENCY_GRAPH_JSON,
                    WORKFLOW_STAGE_STATUS_JSON,
                    WORKFLOW_EXECUTION_RESULT_JSON,
                    WORKFLOW_READINESS_SUMMARY_JSON,
                )
                if name not in initial_hashes
            ),
        ]
    )
    artifacts_refreshed = sorted(path for path, digest in after_hashes.items() if before_hashes.get(path) and before_hashes[path] != digest)
    stage_status = build_workflow_stage_status(state_dir, workflow_mode=workflow_mode, selected_stages=sorted(selected), workflow_id=plan["workflow_id"])
    if failed:
        failures = {item["stage_id"]: item["reason"] for item in failed}
        for item in stage_status["stages"]:
            if item["stage_id"] in failures:
                item["status"] = "failed"
                item["failure_reason"] = failures[item["stage_id"]]
                item["next_action"] = "Inspect the deterministic builder failure and rerun this stage."
        stage_status["status"] = "failed"
        stage_status["summary"] = {status: sum(item["status"] == status for item in stage_status["stages"]) for status in sorted(STAGE_STATUS_VALUES)}
        write_json(state_dir / WORKFLOW_STAGE_STATUS_JSON, stage_status)
    matrix = _optional_json(state_dir / "readiness-authorization-matrix.json")
    artifact_state = _optional_json(state_dir / "artifact-state.json")
    marked_stale = [str(item.get("path") or item.get("artifact_id")) for item in artifact_state.get("stale_artifacts", [])]
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-execution-result-v1",
        "artifact": WORKFLOW_EXECUTION_RESULT_JSON,
        "workflow_id": plan["workflow_id"],
        "workflow_mode": workflow_mode,
        "status": "failed" if failed else "partial" if blocked or marked_stale or any(item["reason"] != "outputs are current" for item in skipped) else "completed",
        "stages_attempted": attempted,
        "stages_completed": completed,
        "stages_skipped": skipped,
        "stages_blocked": blocked,
        "stages_failed": failed,
        "artifacts_created": artifacts_created,
        "artifacts_refreshed": artifacts_refreshed,
        "artifacts_marked_stale": marked_stale,
        "deterministic_builders_called": called,
        "provider_model_actions_left_pending": plan["required_provider_model_actions"],
        "human_actions_left_pending": plan["required_human_actions"],
        "before_artifact_hashes": before_hashes,
        "after_artifact_hashes": after_hashes,
        "before_readiness_status": before_readiness,
        "after_readiness_status": _readiness_status(state_dir),
        "remaining_blockers": list(matrix.get("blockers", [])) + blocked,
        "remaining_forbidden_claims": list(matrix.get("forbidden_claims", [])),
        "next_recommended_workflow_mode": _next_mode(stage_status, matrix),
        "incremental_artifact_references": _existing_artifacts(
            state_dir,
            [
                "workflow-resume-plan.json",
                "artifact-invalidation-report.json",
                "selective-recompute-plan.json",
                "selective-recompute-result.json",
                "incremental-workflow-summary.json",
            ],
        ),
        "provider_or_model_called": False,
        "repair_applied": False,
        "target_files_mutated": False,
        "safety_policy": _safety_policy(),
    }
    write_json(state_dir / WORKFLOW_EXECUTION_RESULT_JSON, result)
    append_workflow_checkpoint(
        state_dir,
        workflow_id=plan["workflow_id"],
        run_id=run_id,
        stage_id="workflow",
        stage_type="workflow",
        checkpoint_type="workflow_failed" if failed else "workflow_completed",
        status=result["status"],
        output_artifact_paths=[WORKFLOW_EXECUTION_RESULT_JSON, WORKFLOW_READINESS_SUMMARY_JSON],
        source_command=source_command,
    )
    build_workflow_readiness_summary(state_dir, workflow_id=plan["workflow_id"])
    return result


def build_workflow_readiness_summary(state_dir: Path, *, workflow_id: str | None = None, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    matrix = _optional_json(state_dir / "readiness-authorization-matrix.json")
    stage_status = _optional_json(state_dir / WORKFLOW_STAGE_STATUS_JSON)
    execution = _optional_json(state_dir / WORKFLOW_EXECUTION_RESULT_JSON)
    artifact_state = _optional_json(state_dir / "artifact-state.json")
    gaps = _optional_json(state_dir / "manual-followup-gap-report.json")
    repairs = _optional_json(state_dir / "knowledge-repair-impact-report.json")
    incremental = _optional_json(state_dir / "incremental-workflow-summary.json")
    forbidden = list(matrix.get("forbidden_claims", execution.get("remaining_forbidden_claims", [])))
    stale = [str(item.get("path") or item.get("artifact_id")) for item in artifact_state.get("stale_artifacts", [])]
    current_artifact_state_hash = _hash_if_file(state_dir / "artifact-state.json")
    if stage_status.get("artifact_state_sha256") and stage_status.get("artifact_state_sha256") != current_artifact_state_hash:
        stale = _unique([*stale, "artifact-state.json"])
    missing = [str(item.get("path") or item.get("artifact_id")) for item in artifact_state.get("missing_required_artifacts", [])]
    blocked_stages = [item for item in stage_status.get("stages", []) if item.get("status") in {"blocked", "failed", "requires_human_action", "requires_provider_action"}]
    summary = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-readiness-summary-v1",
        "artifact": WORKFLOW_READINESS_SUMMARY_JSON,
        "workflow_id": workflow_id or execution.get("workflow_id") or stage_status.get("workflow_id"),
        "overall_workflow_status": _workflow_summary_status(execution, stale, missing, blocked_stages),
        "delivery_readiness": matrix.get("delivery_readiness_status", "missing"),
        "apply_readiness": matrix.get("apply_readiness_status", "missing"),
        "review_readiness": matrix.get("review_readiness_status", "missing"),
        "production_readiness": matrix.get("production_readiness_status", "missing"),
        "stale_artifacts": stale,
        "missing_artifacts": missing,
        "blocked_stages": blocked_stages,
        "human_follow_up_count": sum(item.get("status") == "requires_human_action" for item in blocked_stages) + len(gaps.get("gaps", [])),
        "provider_pending_count": sum(item.get("status") == "requires_provider_action" for item in blocked_stages),
        "repair_pending_count": int(repairs.get("summary", {}).get("repair_item_count", repairs.get("repair_item_count", 0)) or 0),
        "document_evidence_status": matrix.get("document_evidence_status", {"status": "missing"}),
        "knowledge_evidence_status": matrix.get("knowledge_evidence_status", {"status": "missing"}),
        "readiness_matrix_status": "missing" if not matrix else "blocked" if matrix.get("blockers") else "current",
        "forbidden_claims_remaining": forbidden,
        "recommended_next_action": _recommended_action(matrix, stale, missing, blocked_stages),
        "incremental_resume_status": incremental.get("resume_status", "not_run"),
        "selective_recompute_status": incremental.get("recompute_status", "not_run"),
        "incremental_limitations": incremental.get("limitations", []),
        "readiness_not_upgraded": True,
        "source_artifact_references": _existing_artifacts(state_dir, ["artifact-state.json", "readiness-authorization-matrix.json", "manual-followup-gap-report.json", WORKFLOW_STAGE_STATUS_JSON, WORKFLOW_EXECUTION_RESULT_JSON]),
    }
    if write:
        write_json(state_dir / WORKFLOW_READINESS_SUMMARY_JSON, summary)
    return summary


def read_workflow_run_plan(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKFLOW_RUN_PLAN_JSON)


def read_workflow_stage_status(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKFLOW_STAGE_STATUS_JSON)


def read_workflow_execution_result(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKFLOW_EXECUTION_RESULT_JSON)


def read_workflow_readiness_summary(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKFLOW_READINESS_SUMMARY_JSON)


def read_workflow_dependency_graph(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKFLOW_DEPENDENCY_GRAPH_JSON)


def workflow_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "workflow_run_plan": WORKFLOW_RUN_PLAN_JSON,
        "workflow_stage_status": WORKFLOW_STAGE_STATUS_JSON,
        "workflow_execution_result": WORKFLOW_EXECUTION_RESULT_JSON,
        "workflow_readiness_summary": WORKFLOW_READINESS_SUMMARY_JSON,
        "workflow_dependency_graph": WORKFLOW_DEPENDENCY_GRAPH_JSON,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def _builders(state_dir: Path, run_id: str | None) -> dict[str, Callable[[], Any]]:
    from .artifact_state import build_artifact_state
    from .document_decision import build_document_claim_resolution, build_document_signoff_summary
    from .evaluation import build_evaluation_scorecard
    from .knowledge_audit_enforcement import build_knowledge_audit_enforcement_decision, build_workbench_knowledge_review_queue
    from .knowledge_consumption import build_knowledge_eligibility_report, build_working_context_packet
    from .knowledge_repair import build_knowledge_repair_impact_report, build_knowledge_repair_plan, build_knowledge_repair_request
    from .knowledge_repair_closure import build_knowledge_readiness_impact_report, build_knowledge_recompute_plan, build_knowledge_recompute_result, build_knowledge_repair_closure_decision
    from .knowledge_repair_result import build_knowledge_repair_qa_report, build_knowledge_repair_reconciliation
    from .knowledge_usage import build_constraint_application_audit, build_knowledge_conflict_report, build_knowledge_usage_report
    from .provider_evidence import build_provider_evidence_reconciliation, build_provider_execution_policy, build_provider_handoff_request
    from .readiness_action import build_workbench_readiness_action_queue
    from .readiness_authorization import build_readiness_reports
    from .workbench_queue import build_workbench_claim_queue, build_workbench_review_queue, build_workbench_signoff_summary

    def working_context() -> None:
        build_knowledge_eligibility_report(state_dir)
        build_working_context_packet(state_dir)

    def knowledge_usage() -> None:
        build_knowledge_usage_report(state_dir)
        build_constraint_application_audit(state_dir)
        build_knowledge_conflict_report(state_dir)

    def enforcement() -> None:
        build_knowledge_audit_enforcement_decision(state_dir)
        build_workbench_knowledge_review_queue(state_dir)

    def repair_planning() -> None:
        build_knowledge_repair_plan(state_dir, run_id=run_id)
        build_knowledge_repair_request(state_dir, run_id=run_id)
        build_knowledge_repair_impact_report(state_dir, run_id=run_id)

    def repair_reconciliation() -> None:
        build_knowledge_repair_qa_report(state_dir)
        build_knowledge_repair_reconciliation(state_dir)

    def repair_closure() -> None:
        build_knowledge_recompute_plan(state_dir)
        build_knowledge_recompute_result(state_dir)
        build_knowledge_repair_closure_decision(state_dir)
        build_knowledge_readiness_impact_report(state_dir)

    def document_resolution() -> None:
        build_document_claim_resolution(state_dir, run_id=run_id)
        build_document_signoff_summary(state_dir, run_id=run_id)

    def provider_evidence() -> None:
        build_provider_execution_policy(state_dir, {"execution_mode": "disabled"}, run_id=run_id)
        build_provider_handoff_request(state_dir, {"execution_mode": "dry_run"}, run_id=run_id)
        build_provider_evidence_reconciliation(state_dir, run_id=run_id)

    def workbench_projection() -> None:
        build_workbench_review_queue(state_dir)
        build_workbench_claim_queue(state_dir)
        build_workbench_signoff_summary(state_dir)
        build_workbench_readiness_action_queue(state_dir, run_id=run_id)

    return {
        "artifact_state": lambda: build_artifact_state(state_dir, run_id=run_id),
        "evaluation_scorecard": lambda: build_evaluation_scorecard(state_dir, run_id=run_id),
        "document_decision_resolution": document_resolution,
        "working_context_packet": working_context,
        "knowledge_usage_audit": knowledge_usage,
        "knowledge_audit_enforcement": enforcement,
        "knowledge_repair_planning": repair_planning,
        "knowledge_repair_result_reconciliation": repair_reconciliation,
        "knowledge_repair_closure_recompute": repair_closure,
        "provider_evidence": provider_evidence,
        "readiness_authorization": lambda: build_readiness_reports(state_dir, run_id=run_id),
        "workbench_projection": workbench_projection,
    }


def _evaluate_stages(state_dir: Path, selected: set[str]) -> list[dict[str, Any]]:
    from .artifact_state import build_artifact_state

    artifact_state = build_artifact_state(state_dir, write=True)
    statuses = {str(item.get("path")): str(item.get("status")) for item in artifact_state.get("artifacts", [])}
    builders = set(_builders(state_dir, None))
    return [_evaluate_stage(state_dir, stage, selected, statuses, builders) for stage in STAGES]


def _evaluate_stage(state_dir: Path, stage: dict[str, Any], selected: set[str], statuses: dict[str, str], builders: set[str]) -> dict[str, Any]:
    item = _public_stage(stage)
    item["stale_triggers"] = [f"{artifact} changed" for artifact in stage["input_artifacts"]]
    item["blocking_conditions"] = []
    item["skip_reason"] = ""
    item["failure_reason"] = ""
    if stage["stage_type"] not in selected:
        item["status"] = "skipped"
        item["skip_reason"] = "stage is outside the selected workflow mode"
        item["next_action"] = "Select a workflow mode that includes this stage if it is required."
        return item
    output_statuses = [_file_status(state_dir, artifact, statuses) for artifact in stage["output_artifacts"]]
    input_statuses = [(artifact, _file_status(state_dir, artifact, statuses)) for artifact in stage["input_artifacts"]]
    if output_statuses and any(status == "stale" for status in output_statuses):
        item["status"] = "stale"
        item["next_action"] = "Run the deterministic builder if registered; otherwise refresh through the owning workflow."
        return item
    if output_statuses and all(status in {"current", "accepted"} for status in output_statuses):
        item["status"] = "current"
        item["next_action"] = "No action required unless an upstream artifact changes."
        return item
    missing_inputs = [artifact for artifact, status in input_statuses if status == "missing"]
    blocked_inputs = [artifact for artifact, status in input_statuses if status in {"blocked", "rejected"}]
    if stage["requires_provider_action"]:
        item["status"] = "requires_provider_action"
        item["blocking_conditions"] = missing_inputs + blocked_inputs or ["provider/model evidence is absent"]
        item["next_action"] = "Run provider/model work externally through an authorized path, then ingest its evidence."
        return item
    if stage["requires_human_action"]:
        item["status"] = "requires_human_action"
        item["blocking_conditions"] = missing_inputs + blocked_inputs or ["artifact-backed human evidence is absent"]
        item["next_action"] = "Record the required scoped human decision through an existing runtime writer."
        return item
    builder_name = str(stage.get("builder") or "")
    projection_builders = {"artifact_state", "evaluation_scorecard", "readiness_authorization", "workbench_projection"}
    if (blocked_inputs or missing_inputs) and builder_name not in projection_builders:
        item["status"] = "blocked"
        item["blocking_conditions"] = blocked_inputs + missing_inputs
        item["next_action"] = "Resolve or produce the listed input artifacts."
        return item
    if builder_name in builders:
        item["status"] = "ready_to_run"
        item["next_action"] = "Run the registered deterministic builder."
        return item
    item["status"] = "missing"
    item["next_action"] = "Use the owning command or provide the required external/human input."
    return item


def _public_stage(stage: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in stage.items() if key != "builder"}


def _selected_stage_types(workflow_mode: str, selected_stages: list[str] | None) -> set[str]:
    if workflow_mode not in WORKFLOW_MODES:
        raise ValueError(f"workflow_mode must be one of: {', '.join(sorted(WORKFLOW_MODES))}")
    if workflow_mode == "custom":
        selected = set(selected_stages or [])
        unknown = selected - set(_STAGE_BY_TYPE)
        if unknown:
            raise ValueError(f"Unknown workflow stages: {', '.join(sorted(unknown))}")
        if not selected:
            raise ValueError("custom workflow requires at least one selected stage")
        return selected
    return set(MODE_STAGES[workflow_mode])


def _file_status(state_dir: Path, artifact: str, statuses: dict[str, str]) -> str:
    if artifact == "knowledge-packs":
        return "current" if (state_dir / artifact).is_dir() else "missing"
    path = state_dir / artifact
    if not path.exists():
        return "missing"
    return statuses.get(artifact, "current")


def _workflow_context(state_dir: Path, scenario: str | None, source_locale: str | None, target_locale: str | None, target_delivery_mode: str | None) -> dict[str, str]:
    brief = _optional_json(state_dir / "localization-brief.json")
    targets = brief.get("target_locales") if isinstance(brief.get("target_locales"), list) else []
    return {
        "scenario": str(scenario or brief.get("scenario") or ""),
        "source_locale": str(source_locale or brief.get("source_locale") or ""),
        "target_locale": str(target_locale or brief.get("target_locale") or (targets[0] if targets else "")),
        "target_delivery_mode": str(target_delivery_mode or brief.get("target_delivery_mode") or "review_only"),
    }


def _workflow_id(mode: str, selected: set[str], context: dict[str, str], run_id: str | None) -> str:
    payload = json.dumps([mode, sorted(selected), context, run_id], sort_keys=True, ensure_ascii=False).encode("utf-8")
    return f"workflow-{hashlib.sha256(payload).hexdigest()[:20]}"


def _edge(source: str, target: str, dependency_type: str, propagates: bool, blocks: bool, recompute: bool) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "dependency_type": dependency_type,
        "staleness_propagation_behavior": "target_becomes_stale" if propagates else "none",
        "blocking_behavior": "blocks_target" if blocks else "does_not_block",
        "recompute_requirement": "required" if recompute else "not_required",
    }


def _pending_action(stage: dict[str, Any]) -> dict[str, Any]:
    return {"stage_id": stage["stage_id"], "stage_type": stage["stage_type"], "reason": stage["blocking_conditions"], "next_action": stage["next_action"]}


def _safety_policy() -> dict[str, Any]:
    return {
        "deterministic_builders_only": True,
        "provider_or_model_execution_allowed": False,
        "semantic_rewrite_allowed": False,
        "repair_application_allowed": False,
        "target_file_mutation_allowed": False,
        "human_or_provider_evidence_may_be_fabricated": False,
        "workflow_completion_implies_readiness": False,
    }


def _stage_collection_status(items: list[dict[str, Any]]) -> str:
    statuses = {item["status"] for item in items}
    if "failed" in statuses:
        return "failed"
    if statuses & {"blocked", "requires_human_action", "requires_provider_action", "stale", "missing"}:
        return "blocked"
    if statuses <= {"current", "completed", "skipped"}:
        return "current"
    return "ready_to_run"


def _state_hashes(state_dir: Path) -> dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(state_dir.iterdir()) if path.is_file()}


def _artifact_hashes(state_dir: Path, artifacts: list[str]) -> dict[str, str]:
    return {artifact: sha256_file(state_dir / artifact) for artifact in artifacts if (state_dir / artifact).is_file()}


def _blocked_workflow_result(plan: dict[str, Any], workflow_mode: str, blocker_type: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workflow-execution-result-v1",
        "artifact": WORKFLOW_EXECUTION_RESULT_JSON,
        "workflow_id": plan["workflow_id"],
        "workflow_mode": workflow_mode,
        "status": "blocked",
        "stages_attempted": [],
        "stages_completed": [],
        "stages_skipped": [],
        "stages_blocked": [{"stage_id": "workflow", "status": "blocked", "blockers": [blocker_type]}],
        "stages_failed": [],
        "artifacts_created": [],
        "artifacts_refreshed": [],
        "artifacts_marked_stale": [],
        "deterministic_builders_called": [],
        "provider_model_actions_left_pending": plan.get("required_provider_model_actions", []),
        "human_actions_left_pending": plan.get("required_human_actions", []),
        "before_artifact_hashes": {},
        "after_artifact_hashes": {},
        "before_readiness_status": {},
        "after_readiness_status": {},
        "remaining_blockers": [{"type": blocker_type, "evidence": evidence}],
        "remaining_forbidden_claims": ["delivery_ready", "apply_ready", "production_ready"],
        "next_recommended_workflow_mode": "workflow_recovery",
        "incremental_artifact_references": {},
        "provider_or_model_called": False,
        "repair_applied": False,
        "target_files_mutated": False,
        "safety_policy": _safety_policy(),
    }


def _readiness_status(state_dir: Path) -> dict[str, str]:
    matrix = _optional_json(state_dir / "readiness-authorization-matrix.json")
    return {
        "delivery": str(matrix.get("delivery_readiness_status", "missing")),
        "apply": str(matrix.get("apply_readiness_status", "missing")),
        "review": str(matrix.get("review_readiness_status", "missing")),
        "production": str(matrix.get("production_readiness_status", "missing")),
    }


def _next_mode(stage_status: dict[str, Any], matrix: dict[str, Any]) -> str:
    stages = [item for item in stage_status.get("stages", []) if item.get("status") != "skipped"]
    if any(item.get("status") == "requires_provider_action" for item in stages):
        return "diagnose_only"
    if any(item.get("stage_type") == "knowledge_repair_result_reconciliation" and item.get("status") != "current" for item in stages):
        return "knowledge_repair_cycle"
    if matrix.get("delivery_readiness_status") != "ready":
        return "delivery_readiness_check"
    if matrix.get("apply_readiness_status") != "ready":
        return "apply_readiness_check"
    return "diagnose_only"


def _workflow_summary_status(execution: dict[str, Any], stale: list[str], missing: list[str], blocked: list[dict[str, Any]]) -> str:
    if execution.get("status") == "failed":
        return "failed"
    if stale:
        return "stale"
    if missing or blocked or execution.get("status") in {"partial", "blocked"}:
        return "blocked"
    return str(execution.get("status") or "not_run")


def _recommended_action(matrix: dict[str, Any], stale: list[str], missing: list[str], blocked: list[dict[str, Any]]) -> str:
    if stale:
        return "Refresh stale evidence before relying on workflow or readiness artifacts."
    if missing:
        return "Produce the missing required artifacts through their owning deterministic or human workflow."
    human = next((item for item in blocked if item.get("status") == "requires_human_action"), None)
    if human:
        return str(human.get("next_action"))
    provider = next((item for item in blocked if item.get("status") == "requires_provider_action"), None)
    if provider:
        return str(provider.get("next_action"))
    actions = matrix.get("recommended_next_actions")
    if isinstance(actions, list) and actions:
        return str(actions[0])
    return "Run diagnose_only after upstream evidence changes."


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _hash_if_file(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _existing_artifacts(state_dir: Path, names: list[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for name in _unique(names):
        path = state_dir / name
        if path.is_file():
            result[name] = {"path": name, "sha256": sha256_file(path)}
    return result


def _unique(items: Any) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))
