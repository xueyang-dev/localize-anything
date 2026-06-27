from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .generation import import_generated_handoff
from .generation_handoff_policy import build_generation_handoff_decision
from .io_utils import read_json, write_json
from .project import inspect_project, record_project_session, session_index_path
from .provider import generate_handoff_with_http_provider
from .run import run_localize


def run_agent(
    project_root: Path,
    target_locale: str,
    source_locale: str = "en-US",
    source_files: list[str] | None = None,
    output_root: Path | None = None,
    run_id: str | None = None,
    max_segments: int = 80,
    limit_tokens: int = 4000,
    responses_dir: Path | None = None,
    generated_dir: Path | None = None,
    generated: Path | None = None,
    synthetic_draft: bool = False,
    provider_url: str | None = None,
    provider_headers: dict[str, str] | None = None,
    provider_timeout_seconds: int = 60,
    delivery_run_id: str | None = None,
    workflow_depth: str = "ask",
    preflight_mode: str = "auto",
    privacy_mode: str = "standard",
    data_classification: str = "internal",
    delivery_status: str = "draft_package",
    operating_mode: str | None = None,
    reference_policy: str | None = None,
) -> dict[str, Any]:
    """Run the first provider-agnostic localization agent workflow.

    The agent is deliberately local-first: it routes project files, creates
    parallel translation work packets, imports host LLM responses when present,
    and reflects through deterministic QA/review artifacts before any apply.
    """

    if sum(1 for value in (responses_dir, generated_dir, generated, synthetic_draft, provider_url) if value) > 1:
        raise ValueError(
            "Use only one agent generation input: --responses-dir, --generated-dir, --generated, --synthetic-draft, or --provider-url"
        )

    project_root = project_root.resolve()
    output_root = (output_root or project_root / "localize-anything-output").resolve()
    run_id = run_id or _default_agent_run_id()
    inspection = inspect_project(project_root)

    if responses_dir:
        handoff_run_id = f"{run_id}-handoff"
        handoff_result = run_localize(
            project_root,
            source_locale,
            [target_locale],
            source_files,
            output_root,
            handoff_run_id,
            max_segments,
            limit_tokens,
            True,
            None,
            None,
            False,
            workflow_depth,
            preflight_mode,
            privacy_mode,
            data_classification,
            delivery_status,
            operating_mode,
            reference_policy,
        )
        handoff_path = Path(handoff_result["artifacts"]["generation_handoff"])
        handoff = read_json(handoff_path)
        handoff_run_dir = Path(handoff_result["artifacts"]["run_directory"])
        import_path = handoff_run_dir / "response-import.json"
        generated_output = handoff_run_dir / "generated.jsonl"
        import_result = import_generated_handoff(handoff, responses_dir, generated_output)
        write_json(import_path, import_result)

        if import_result["status"] == "fail":
            summary = _agent_summary(
                run_id,
                "response_import_failed",
                project_root,
                source_locale,
                target_locale,
                inspection,
                handoff_result,
                handoff_result,
                response_import=import_result,
                response_import_path=import_path,
            )
            return _write_agent_summary(summary, handoff_run_dir)

        delivery_result = run_localize(
            project_root,
            source_locale,
            [target_locale],
            source_files,
            output_root,
            delivery_run_id or f"{run_id}-delivery",
            max_segments,
            limit_tokens,
            False,
            Path(str(handoff["generated_dir"])),
            None,
            False,
            workflow_depth,
            preflight_mode,
            privacy_mode,
            data_classification,
            delivery_status,
            operating_mode,
            reference_policy,
        )
        summary = _agent_summary(
            run_id,
            _agent_status_from_runtime(delivery_result["status"]),
            project_root,
            source_locale,
            target_locale,
            inspection,
            delivery_result,
            handoff_result,
            response_import=import_result,
            response_import_path=import_path,
        )
        return _write_agent_summary(summary, Path(delivery_result["artifacts"]["run_directory"]))

    if provider_url:
        handoff_run_id = f"{run_id}-handoff"
        handoff_result = run_localize(
            project_root,
            source_locale,
            [target_locale],
            source_files,
            output_root,
            handoff_run_id,
            max_segments,
            limit_tokens,
            True,
            None,
            None,
            False,
            workflow_depth,
            preflight_mode,
            privacy_mode,
            data_classification,
            delivery_status,
            operating_mode,
            reference_policy,
        )
        handoff_path = Path(handoff_result["artifacts"]["generation_handoff"])
        handoff = read_json(handoff_path)
        handoff_run_dir = Path(handoff_result["artifacts"]["run_directory"])
        handoff_decision = build_generation_handoff_decision(
            project_root / ".localize-anything",
            provider_policy={"mode": "real_provider", "provider_controlled": True, "status": "safe"},
            run_id=handoff_run_id,
        )
        provider_path = handoff_run_dir / "provider-generation.json"
        generated_output = handoff_run_dir / "generated.jsonl"
        provider_result = generate_handoff_with_http_provider(
            handoff,
            provider_url,
            generated_output,
            provider_headers or {},
            provider_timeout_seconds,
            handoff_decision,
        )
        write_json(provider_path, provider_result)

        if provider_result["status"] == "fail":
            summary = _agent_summary(
                run_id,
                "provider_generation_failed",
                project_root,
                source_locale,
                target_locale,
                inspection,
                handoff_result,
                handoff_result,
                provider_generation=provider_result,
                provider_generation_path=provider_path,
            )
            return _write_agent_summary(summary, handoff_run_dir)

        delivery_result = run_localize(
            project_root,
            source_locale,
            [target_locale],
            source_files,
            output_root,
            delivery_run_id or f"{run_id}-delivery",
            max_segments,
            limit_tokens,
            False,
            Path(str(handoff["generated_dir"])),
            None,
            False,
            workflow_depth,
            preflight_mode,
            privacy_mode,
            data_classification,
            delivery_status,
            operating_mode,
            reference_policy,
        )
        summary = _agent_summary(
            run_id,
            _agent_status_from_runtime(delivery_result["status"]),
            project_root,
            source_locale,
            target_locale,
            inspection,
            delivery_result,
            handoff_result,
            provider_generation=provider_result,
            provider_generation_path=provider_path,
        )
        return _write_agent_summary(summary, Path(delivery_result["artifacts"]["run_directory"]))

    if generated_dir or generated or synthetic_draft:
        runtime_result = run_localize(
            project_root,
            source_locale,
            [target_locale],
            source_files,
            output_root,
            run_id,
            max_segments,
            limit_tokens,
            False,
            generated_dir,
            generated,
            synthetic_draft,
            workflow_depth,
            preflight_mode,
            privacy_mode,
            data_classification,
            delivery_status,
            operating_mode,
            reference_policy,
        )
        summary = _agent_summary(
            run_id,
            _agent_status_from_runtime(runtime_result["status"]),
            project_root,
            source_locale,
            target_locale,
            inspection,
            runtime_result,
            runtime_result,
        )
        return _write_agent_summary(summary, Path(runtime_result["artifacts"]["run_directory"]))

    handoff_result = run_localize(
        project_root,
        source_locale,
        [target_locale],
        source_files,
        output_root,
        run_id,
        max_segments,
        limit_tokens,
        True,
        None,
        None,
        False,
        workflow_depth,
        preflight_mode,
        privacy_mode,
        data_classification,
        delivery_status,
        operating_mode,
        reference_policy,
    )
    summary = _agent_summary(
        run_id,
        "awaiting_llm_responses",
        project_root,
        source_locale,
        target_locale,
        inspection,
        handoff_result,
        handoff_result,
    )
    return _write_agent_summary(summary, Path(handoff_result["artifacts"]["run_directory"]))


def _default_agent_run_id() -> str:
    return datetime.now(UTC).strftime("agent-%Y%m%dT%H%M%SZ")


def _agent_status_from_runtime(runtime_status: str) -> str:
    if runtime_status == "draft_package_created":
        return "draft_package_created"
    if runtime_status == "generation_failed":
        return "generation_failed"
    if runtime_status == "handoff_ready":
        return "awaiting_llm_responses"
    return runtime_status


def _agent_summary(
    run_id: str,
    status: str,
    project_root: Path,
    source_locale: str,
    target_locale: str,
    inspection: dict[str, Any],
    runtime_result: dict[str, Any],
    handoff_result: dict[str, Any],
    response_import: dict[str, Any] | None = None,
    response_import_path: Path | None = None,
    provider_generation: dict[str, Any] | None = None,
    provider_generation_path: Path | None = None,
) -> dict[str, Any]:
    runtime_summary = runtime_result.get("summary", {})
    handoff_summary = handoff_result.get("summary", {})
    runtime_project = runtime_result.get("project", {})
    delivery = _delivery_section(runtime_result)
    artifacts = dict(runtime_result.get("artifacts", {}))
    if response_import_path:
        artifacts["response_import"] = response_import_path.as_posix()
    if provider_generation_path:
        artifacts["provider_generation"] = provider_generation_path.as_posix()

    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["agent", "runtime"],
        "run_id": run_id,
        "status": status,
        "project": {
            "root": project_root.as_posix(),
            "source_locale": source_locale,
            "target_locale": target_locale,
            "mode": "standard_project",
            "operating_mode": runtime_project.get("operating_mode", "greenfield_localization"),
            "reference_policy": runtime_project.get("reference_policy", "style_only"),
        },
        "agent": {
            "architecture": "routing_parallelization_reflection",
            "provider_mode": "direct_http_provider" if provider_generation else "human_assisted_host_llm",
            "direct_model_api": bool(provider_generation),
            "phases": ["routing", "parallelization", "reflection"],
        },
        "routing": {
            "status": "pass" if inspection.get("supported_files") else "blocked",
            "supported_file_count": len(inspection.get("supported_files", [])),
            "adapter_counts": inspection.get("adapter_counts", {}),
            "selected_source_files": runtime_result.get("source_files", []),
            "unprocessed_non_text_asset_count": len(inspection.get("unprocessed_non_text_assets", [])),
            "scan_policy": inspection.get("scan_policy", {}),
            "ignored_path_count": inspection.get("ignored_path_count", 0),
            "ignored_paths_sample": inspection.get("ignored_paths", [])[:25],
            "skipped_path_count": inspection.get("skipped_path_count", 0),
            "skipped_paths_sample": inspection.get("skipped_paths", [])[:25],
            "recommended_preflight_mode": inspection.get("preflight_assessment", {}).get("recommended_preflight_mode"),
            "recommended_workflow_depth": inspection.get("preflight_assessment", {}).get("recommended_workflow_depth"),
            "reason": inspection.get("preflight_assessment", {}).get("reason"),
        },
        "parallelization": {
            "status": "handoff_ready",
            "segment_count": handoff_summary.get("segment_count", runtime_summary.get("segment_count", 0)),
            "batch_count": handoff_summary.get("batch_count", runtime_summary.get("batch_count", 0)),
            "max_segments_per_batch": "configured_by_run",
            "work_packets": handoff_result.get("artifacts", {}).get("work_packets"),
            "draft_requests": handoff_result.get("artifacts", {}).get("draft_requests"),
            "prompts": handoff_result.get("artifacts", {}).get("prompts"),
            "responses": handoff_result.get("artifacts", {}).get("responses"),
            "generation_handoff": handoff_result.get("artifacts", {}).get("generation_handoff"),
        },
        "reflection": {
            "status": _reflection_status(status),
            "response_import_status": response_import.get("status") if response_import else None,
            "response_import_blocking_count": response_import.get("summary", {}).get("blocking_count", 0) if response_import else 0,
            "provider_generation_status": provider_generation.get("status") if provider_generation else None,
            "provider_generation_blocking_count": (
                provider_generation.get("summary", {}).get("blocking_count", 0) if provider_generation else 0
            ),
            "generation_status": runtime_result.get("generation", {}).get("status"),
            "review_sheet": runtime_result.get("artifacts", {}).get("review_sheet_markdown"),
            "llm_review_request": runtime_result.get("artifacts", {}).get("llm_review_request"),
            "llm_review_prompt": runtime_result.get("artifacts", {}).get("llm_review_prompt"),
            "llm_review_status": "request_ready" if runtime_result.get("artifacts", {}).get("llm_review_request") else None,
            "qa_status": runtime_summary.get("qa_status"),
            "blocking_count": runtime_summary.get("blocking_count", 0),
            "warning_count": runtime_summary.get("warning_count", 0),
            "apply_plan": runtime_result.get("artifacts", {}).get("apply_plan_markdown"),
            "delivery_decision": delivery.get("decision_markdown"),
            "delivery_decision_status": delivery.get("decision_status"),
            "requires_user_confirmation_before_apply": True,
        },
        "delivery": delivery,
        "runs": {
            "handoff": _run_pointer(handoff_result),
            "delivery": _run_pointer(runtime_result) if runtime_result is not handoff_result else None,
        },
        "summary": {
            "source_file_count": runtime_summary.get("source_file_count", 0),
            "segment_count": runtime_summary.get("segment_count", handoff_summary.get("segment_count", 0)),
            "batch_count": runtime_summary.get("batch_count", handoff_summary.get("batch_count", 0)),
            "output_count": runtime_summary.get("output_count", 0),
            "qa_status": runtime_summary.get("qa_status", "not_checked"),
            "blocking_count": runtime_summary.get("blocking_count", 0),
            "warning_count": runtime_summary.get("warning_count", 0),
        },
        "artifacts": artifacts,
        "next_actions": _agent_next_actions(status, runtime_result),
    }


def _reflection_status(status: str) -> str:
    if status == "awaiting_llm_responses":
        return "pending_llm_output"
    if status == "response_import_failed":
        return "blocked_on_response_import"
    if status == "provider_generation_failed":
        return "blocked_on_provider_generation"
    if status == "generation_failed":
        return "blocked_on_generation_qa"
    return "review_artifacts_ready"


def _run_pointer(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "run_directory": result.get("artifacts", {}).get("run_directory"),
        "summary": result.get("summary", {}),
    }


def _delivery_section(runtime_result: dict[str, Any]) -> dict[str, Any]:
    artifacts = runtime_result.get("artifacts", {})
    decision_path = artifacts.get("delivery_decision")
    decision_markdown = artifacts.get("delivery_decision_markdown")
    apply_plan = artifacts.get("apply_plan_markdown")
    delivery: dict[str, Any] = {
        "status": "pending_generation",
        "decision_status": None,
        "decision_report": decision_path,
        "decision_markdown": decision_markdown,
        "apply_plan": apply_plan,
        "dashboard": artifacts.get("delivery_dashboard_markdown"),
        "requires_user_confirmation_before_apply": bool(apply_plan),
    }
    if not decision_path:
        return delivery

    decision = read_json(Path(decision_path))
    summary = decision.get("summary", {})
    delivery.update(
        {
            "status": "decision_ready",
            "decision_status": decision.get("status"),
            "blocking_count": summary.get("blocking_count", 0),
            "requires_confirmation_count": summary.get("requires_confirmation_count", 0),
            "requires_review_count": summary.get("requires_review_count", 0),
            "requires_user_confirmation_before_apply": summary.get("requires_confirmation_count", 0) > 0,
        }
    )
    return delivery


def _agent_next_actions(status: str, runtime_result: dict[str, Any]) -> list[str]:
    if status == "awaiting_llm_responses":
        return [
            "Send prompts/*.md or draft-requests/*.json to the host LLM translation workflow.",
            "Save one response per batch in responses/ using the batch id, then rerun agent-run with --responses-dir.",
        ]
    if status == "response_import_failed":
        return ["Fix missing or malformed batch response files, then rerun agent-run with --responses-dir."]
    if status == "provider_generation_failed":
        return ["Fix the direct provider response or endpoint, then rerun agent-run with --provider-url."]
    if status == "generation_failed":
        return ["Fix generated batch coverage, placeholder, locale, or source-integrity issues before staging."]
    actions = list(runtime_result.get("next_actions", []))
    if actions:
        return actions
    return [
        "Review the generated review sheet, dashboard, and staged delivery.",
        "Apply only after explicit project-owner approval.",
    ]


def _write_agent_summary(summary: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    summary_path = run_dir / "agent-summary.json"
    summary.setdefault("artifacts", {})["agent_summary"] = summary_path.as_posix()
    project_root = Path(summary["project"]["root"])
    summary["artifacts"]["session_index"] = session_index_path(project_root).as_posix()
    write_json(summary_path, summary)
    record_project_session(
        project_root,
        run_id=summary["run_id"],
        kind="agent_run",
        status=summary["status"],
        source_locale=summary["project"]["source_locale"],
        target_locale=summary["project"]["target_locale"],
        operating_mode=summary["project"].get("operating_mode"),
        reference_policy=summary["project"].get("reference_policy"),
        selected_source_files=list(summary.get("routing", {}).get("selected_source_files", [])),
        run_directory=run_dir,
        artifacts=summary.get("artifacts", {}),
        routing=summary.get("routing", {}),
        summary=summary.get("summary", {}),
        child_runs=summary.get("runs", {}),
        next_actions=summary.get("next_actions", []),
    )
    return summary
