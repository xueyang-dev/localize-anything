from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from . import PROTOCOL_VERSION
from .android_merged_overlay import (
    SOURCE_CATEGORY as ANDROID_MERGED_OVERLAY_CATEGORY,
    create_overlay_plan,
    overlay_output_metadata,
    stage_overlay,
)
from .artifact_state import ARTIFACT_STATE_JSON, build_artifact_state
from .android_strings_adapter import extract_segments as extract_android_strings
from .android_strings_adapter import validate_pair as validate_android_strings
from .apply import create_apply_plan, render_apply_plan_markdown
from .dashboard import build_delivery_dashboard, render_dashboard_markdown
from .delivery import package_delivery
from .delivery_decision import create_delivery_decision_report, render_delivery_decision_markdown
from .document_evidence import (
    CLAIM_METRIC_REPORT_JSON,
    DOCUMENT_EVIDENCE_MANIFEST_JSON,
    DOCUMENT_INTAKE_REPORT_JSON,
    LEADERSHIP_REVIEW_BRIEF_MD,
    OPEN_DECISIONS_MD,
    PUBLICITY_RISK_REPORT_JSON,
    SEMANTIC_ALIGNMENT_JSONL,
)
from .evaluation import (
    EVALUATION_SCORECARD_JSON,
    EVIDENCE_LEVEL_REPORT_MD,
    build_evaluation_scorecard,
)
from .generation import (
    collect_generated_handoff,
    create_draft_request,
    create_generation_handoff,
    render_generation_instructions,
    write_handoff_prompts,
)
from .generation_handoff_policy import (
    build_generation_handoff_decision,
    generation_handoff_decision_asset_paths,
)
from .generation_strategy import build_generation_strategy, write_generation_strategy
from .human_review import CLAIM_ACCEPTANCE_DECISION_JSON, HUMAN_REVIEW_EVIDENCE_JSONL, SIGNOFF_RECORD_JSON
from .gettext_adapter import extract_segments as extract_po_segments
from .gettext_adapter import validate_pair as validate_po_pair
from .io_utils import read_json, read_jsonl, sha256_file, write_json, write_jsonl
from .knowledge_usage import (
    CONSTRAINT_APPLICATION_AUDIT_JSON,
    KNOWLEDGE_CONFLICT_REPORT_JSON,
    KNOWLEDGE_USAGE_REPORT_JSON,
)
from .knowledge_audit_enforcement import (
    KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON,
    WORKBENCH_KNOWLEDGE_REVIEW_QUEUE_JSON,
)
from .knowledge_review_confirmation import (
    KNOWLEDGE_ASSURANCE_SUMMARY_JSON,
    KNOWLEDGE_AUDIT_RESOLUTION_LOG_JSONL,
    KNOWLEDGE_CONFLICT_RESOLUTION_JSON,
    KNOWLEDGE_CONSTRAINT_REVIEW_EVIDENCE_JSONL,
)
from .knowledge_repair import (
    KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON,
    KNOWLEDGE_REPAIR_PLAN_JSON,
    KNOWLEDGE_REPAIR_REQUEST_JSON,
    build_knowledge_repair_plan,
)
from .knowledge_repair_result import (
    KNOWLEDGE_REPAIR_QA_REPORT_JSON,
    KNOWLEDGE_REPAIR_RECONCILIATION_JSON,
    KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL,
    build_knowledge_repair_reconciliation,
)
from .knowledge_repair_closure import (
    KNOWLEDGE_READINESS_IMPACT_REPORT_JSON,
    KNOWLEDGE_RECOMPUTE_PLAN_JSON,
    KNOWLEDGE_RECOMPUTE_RESULT_JSON,
    KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON,
)
from .readiness_authorization import (
    APPLY_READINESS_REPORT_JSON,
    DELIVERY_READINESS_REPORT_JSON,
    MANUAL_FOLLOWUP_GAP_REPORT_JSON,
    READINESS_AUTHORIZATION_MATRIX_JSON,
)
from .ios_strings_adapter import extract_segments as extract_ios_strings
from .ios_strings_adapter import validate_pair as validate_ios_strings
from .json_adapter import extract_segments as extract_json_segments
from .json_adapter import validate_pair as validate_json_pair
from .markup_adapter import extract_segments as extract_markup_segments
from .markup_adapter import validate_pair as validate_markup_pair
from .modes import DEFAULT_OPERATING_MODE, DEFAULT_REFERENCE_POLICY_BY_MODE, mode_contract, resolve_mode_policy
from .planning import create_batch_plan
from .project import initialize_project, inspect_project, record_project_session, session_index_path
from .reference import create_reference_plan
from .retrieval import build_work_packet
from .reflection import create_llm_review_request, render_llm_review_prompt
from .resolution_gate import build_resolution_gate
from .review_sheet import write_review_sheet
from .segment_repair import build_segment_regeneration_plan
from .segment_staleness import build_reuse_decision
from .staging import stage_generated
from .structured_adapter import extract_segments as extract_structured_segments
from .structured_adapter import validate_pair as validate_structured_pair
from .subtitle_adapter import extract_segments as extract_subtitle_segments
from .subtitle_adapter import validate_pair as validate_subtitle_pair
from .tabular_adapter import extract_segments as extract_tabular_segments
from .tabular_adapter import validate_pair as validate_tabular_pair
from .termbase_preflight import run_termbase_preflight
from .word_adapter import extract_segments as extract_word_segments
from .workbench_action import WORKBENCH_ACTION_LOG_JSONL, WORKBENCH_ACTION_RESULT_JSON
from .readiness_action import (
    WORKBENCH_READINESS_ACTION_LOG_JSONL,
    WORKBENCH_READINESS_ACTION_QUEUE_JSON,
    WORKBENCH_READINESS_ACTION_RESULT_JSON,
)
from .workflow import (
    WORKFLOW_DEPENDENCY_GRAPH_JSON,
    WORKFLOW_EXECUTION_RESULT_JSON,
    WORKFLOW_READINESS_SUMMARY_JSON,
    WORKFLOW_RUN_PLAN_JSON,
    WORKFLOW_STAGE_STATUS_JSON,
)
from .workflow_incremental import (
    ARTIFACT_INVALIDATION_REPORT_JSON,
    INCREMENTAL_WORKFLOW_SUMMARY_JSON,
    SELECTIVE_RECOMPUTE_PLAN_JSON,
    SELECTIVE_RECOMPUTE_RESULT_JSON,
    WORKFLOW_RESUME_PLAN_JSON,
)
from .workflow_hardening import (
    WORKFLOW_CHECKPOINT_LOG_JSONL,
    WORKFLOW_IDEMPOTENCY_REPORT_JSON,
    WORKFLOW_LOCK_STATE_JSON,
    WORKFLOW_RECOVERY_PLAN_JSON,
    WORKFLOW_RECOVERY_RESULT_JSON,
    WORKFLOW_TRANSACTION_MANIFEST_JSON,
)
from .provider_evidence import (
    PROVIDER_EVIDENCE_RECONCILIATION_JSON,
    PROVIDER_EXECUTION_LEDGER_JSONL,
    PROVIDER_EXECUTION_POLICY_JSON,
    PROVIDER_HANDOFF_REQUEST_JSON,
    PROVIDER_RESULT_INTAKE_JSONL,
)
from .provider_result_gate import (
    PROVIDER_CLAIM_SUPPORT_REPORT_JSON,
    PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON,
    PROVIDER_RESULT_QA_REPORT_JSON,
    PROVIDER_RESULT_REVIEW_EVIDENCE_JSONL,
    WORKBENCH_PROVIDER_REVIEW_QUEUE_JSON,
)
from .locale_capability import (
    LOCALE_CAPABILITY_REPORT_JSON,
    LOCALE_READINESS_IMPACT_JSON,
    LOCALE_RISK_REPORT_JSON,
)
from .translation_provenance import (
    PROVENANCE_COVERAGE_REPORT_JSON,
    SEGMENT_EVIDENCE_VIEW_JSON,
    TRANSLATION_CLAIM_PROVENANCE_REPORT_JSON,
    TRANSLATION_PROVENANCE_JSONL,
)
from .document_evidence_queue import WORKBENCH_DOCUMENT_EVIDENCE_QUEUE_JSON
from .document_decision import (
    DOCUMENT_CLAIM_RESOLUTION_JSON,
    DOCUMENT_DECISION_LOG_JSONL,
    DOCUMENT_SIGNOFF_SUMMARY_JSON,
    LEADERSHIP_REVIEW_EVIDENCE_JSONL,
)
from .workbench_queue import WORKBENCH_CLAIM_QUEUE_JSON, WORKBENCH_REVIEW_QUEUE_JSON, WORKBENCH_SIGNOFF_SUMMARY_JSON
from .word_adapter import validate_pair as validate_word_pair
from .xcstrings_adapter import extract_segments as extract_xcstrings
from .xcstrings_adapter import validate_pair as validate_xcstrings
from .xliff_adapter import extract_segments as extract_xliff_segments
from .xliff_adapter import validate_pair as validate_xliff_pair


Extractor = Callable[[Path, str, str | None], list[dict[str, Any]]]


EXTRACTORS: dict[str, Extractor] = {
    "core.android-strings": extract_android_strings,
    "core.gettext-po": extract_po_segments,
    "core.ios-strings": extract_ios_strings,
    "core.json-locale": extract_json_segments,
    "core.markup": extract_markup_segments,
    "core.subtitles": extract_subtitle_segments,
    "core.tabular": extract_tabular_segments,
    "core.word-document": extract_word_segments,
    "core.yaml-toml": lambda path, source_locale, source_path: extract_structured_segments(
        path, source_locale, source_path, _structured_format(path)
    ),
    "core.xcstrings": extract_xcstrings,
    "core.xliff": extract_xliff_segments,
}


def run_localize(
    project_root: Path,
    source_locale: str,
    target_locales: list[str],
    source_files: list[str] | None = None,
    output_root: Path | None = None,
    run_id: str | None = None,
    max_segments: int = 80,
    limit_tokens: int = 4000,
    handoff_only: bool = False,
    generated_dir: Path | None = None,
    generated: Path | None = None,
    synthetic_draft: bool = False,
    workflow_depth: str = "ask",
    preflight_mode: str = "auto",
    privacy_mode: str = "standard",
    data_classification: str = "internal",
    delivery_status: str = "draft_package",
    operating_mode: str | None = None,
    reference_policy: str | None = None,
    include_android_merged_resources: bool = False,
    android_merged_resources: Path | None = None,
    android_build_variant: str | None = None,
    android_overlay_output_name: str = "localize_anything_overlay.xml",
) -> dict[str, Any]:
    if len(target_locales) != 1:
        raise ValueError("localize-run currently accepts exactly one target locale per run")
    if sum(1 for value in (generated_dir, generated, synthetic_draft) if value) > 1:
        raise ValueError("Use only one generation input: --generated-dir, --generated, or --synthetic-draft")
    if not handoff_only and not (generated_dir or generated or synthetic_draft):
        raise ValueError("No generated translation input was provided. Use --handoff-only or provide --generated-dir/--generated.")

    project_root = project_root.resolve()
    target_locale = target_locales[0]
    operating_mode, reference_policy = resolve_mode_policy(operating_mode, reference_policy)
    output_root = (output_root or project_root / "localize-anything-output").resolve()
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / run_id
    if run_dir.exists():
        raise ValueError(f"Run output already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    inspection = inspect_project(project_root)
    selected_files = _select_source_files(inspection, source_locale, source_files)
    initialized = initialize_project(
        project_root,
        source_locale,
        selected_files,
        target_locales,
        operating_mode,
        reference_policy,
        workflow_depth,
        preflight_mode,
        privacy_mode,
        data_classification,
    )
    state_dir = Path(initialized["state_directory"])

    segments = _extract_all(project_root, inspection, selected_files, source_locale)
    if not segments:
        raise ValueError("Selected source files did not produce any translatable segments")
    overlay_plan: dict[str, Any] | None = None
    if include_android_merged_resources:
        overlay_plan = create_overlay_plan(
            project_root,
            selected_files,
            segments,
            source_locale,
            target_locale,
            android_merged_resources,
            android_build_variant,
            android_overlay_output_name,
        )
        segments.extend(overlay_plan["segments"])
    segments_path = run_dir / "segments.jsonl"
    write_jsonl(segments_path, segments)
    term_preflight = run_termbase_preflight(
        state_dir,
        segments,
        source_locale=source_locale,
        target_locale=target_locale,
        run_id=run_id,
    )

    inventory_by_path = {item["path"]: item for item in inspection["supported_files"]}
    candidate_segments, preserved_segments, reference_plan = create_reference_plan(
        project_root,
        inventory_by_path,
        selected_files,
        source_locale,
        target_locale,
        segments,
        state_dir,
        operating_mode,
        reference_policy,
    )
    if overlay_plan:
        reference_plan.setdefault("android_merged_overlay", _overlay_report(overlay_plan))
    reference_plan_path = run_dir / "reference-plan.json"
    write_json(reference_plan_path, reference_plan)

    plan = create_batch_plan(candidate_segments, source_locale, target_locales, max_segments, operating_mode, reference_policy)
    plan_path = run_dir / "batch-plan.json"
    write_json(plan_path, plan)
    generation_strategy = write_generation_strategy(
        state_dir,
        build_generation_strategy(
            state_dir,
            plan,
            source_locale=source_locale,
            target_locale=target_locale,
            run_id=run_id,
        ),
    )
    resolution_gate = build_resolution_gate(
        state_dir,
        generation_strategy,
        context={
            "android_coverage": inspection.get("android_coverage", {}),
            "reference_summary": reference_plan["summary"],
        },
        run_id=run_id,
    )
    handoff_decision = build_generation_handoff_decision(
        state_dir,
        requested_mode="synthetic_test" if synthetic_draft else "full_quality",
        provider_policy={"mode": "synthetic_test"} if synthetic_draft else {"mode": "host_agent", "provider_controlled": False},
        coverage_policy=inspection.get("android_coverage", {}),
        run_id=run_id,
    )
    handoff_decision_path = state_dir / "generation-handoff-decision.json"

    packet_dir = run_dir / "work-packets"
    request_dir = run_dir / "draft-requests"
    generated_batches_dir = (generated_dir or run_dir / "generated-batches").resolve()
    if not generation_strategy["work_packet_policy"]["allow_generation"]:
        packet_dir.mkdir(parents=True, exist_ok=True)
        request_dir.mkdir(parents=True, exist_ok=True)
        generated_batches_dir.mkdir(parents=True, exist_ok=True)
        handoff = create_generation_handoff(packet_dir, request_dir, generated_batches_dir, target_locale, handoff_decision)
        handoff_path = run_dir / "generation-handoff.json"
        write_json(handoff_path, handoff)
        prompt_dir = run_dir / "prompts"
        response_dir = run_dir / "responses"
        response_dir.mkdir(parents=True, exist_ok=True)
        prompt_manifest = write_handoff_prompts(handoff, prompt_dir)
        prompt_manifest_path = run_dir / "prompt-manifest.json"
        write_json(prompt_manifest_path, prompt_manifest)
        generation_readme_path = run_dir / "generation-README.md"
        generation_readme_path.write_text(
            _render_generation_strategy_blocked(generation_strategy),
            encoding="utf-8",
            newline="\n",
        )
        artifact_state = build_artifact_state(state_dir, run_dir=run_dir, run_id=run_id)
        summary = _summary(
            run_id,
            "generation_strategy_blocked",
            project_root,
            source_locale,
            target_locale,
            selected_files,
            run_dir,
            segments_path,
            plan_path,
            handoff_path,
            len(segments),
            len(plan["batches"]),
            generation_mode="blocked_by_generation_strategy",
            reference_plan_path=reference_plan_path,
            term_preflight=term_preflight,
            generation_strategy=generation_strategy,
            resolution_gate=resolution_gate,
            generation_handoff_decision=handoff_decision,
            generation_handoff_decision_path=handoff_decision_path,
            operating_mode=operating_mode,
            reference_policy=reference_policy,
            reference_summary=reference_plan["summary"],
            prompt_manifest_path=prompt_manifest_path,
            generation_readme_path=generation_readme_path,
            generation_status="blocked",
            artifact_state=artifact_state,
            android_overlay_plan=overlay_plan,
        )
        return _write_run_summary(summary, run_dir, inspection)

    for batch in plan["batches"]:
        packet = build_work_packet(plan, batch["batch_id"], candidate_segments, state_dir, target_locale, limit_tokens, operating_mode=operating_mode, reference_policy=reference_policy)
        write_json(packet_dir / f"{batch['batch_id']}.json", packet)
        write_json(request_dir / f"{batch['batch_id']}.json", create_draft_request(packet))

    handoff = create_generation_handoff(packet_dir, request_dir, generated_batches_dir, target_locale, handoff_decision)
    handoff_path = run_dir / "generation-handoff.json"
    write_json(handoff_path, handoff)
    prompt_dir = run_dir / "prompts"
    response_dir = run_dir / "responses"
    response_dir.mkdir(parents=True, exist_ok=True)
    prompt_manifest = write_handoff_prompts(handoff, prompt_dir)
    prompt_manifest_path = run_dir / "prompt-manifest.json"
    write_json(prompt_manifest_path, prompt_manifest)
    generation_readme_path = run_dir / "generation-README.md"
    generation_readme_path.write_text(
        render_generation_instructions(handoff, prompt_dir, response_dir, run_dir / "generated.jsonl"),
        encoding="utf-8",
        newline="\n",
    )

    if handoff_only:
        artifact_state = build_artifact_state(state_dir, run_dir=run_dir, run_id=run_id)
        summary = _summary(
            run_id,
            "handoff_ready",
            project_root,
            source_locale,
            target_locale,
            selected_files,
            run_dir,
            segments_path,
            plan_path,
            handoff_path,
            len(segments),
            len(plan["batches"]),
            generation_mode="handoff_only",
            reference_plan_path=reference_plan_path,
            term_preflight=term_preflight,
            generation_strategy=generation_strategy,
            resolution_gate=resolution_gate,
            generation_handoff_decision=handoff_decision,
            generation_handoff_decision_path=handoff_decision_path,
            operating_mode=operating_mode,
            reference_policy=reference_policy,
            reference_summary=reference_plan["summary"],
            prompt_manifest_path=prompt_manifest_path,
            generation_readme_path=generation_readme_path,
            artifact_state=artifact_state,
            android_overlay_plan=overlay_plan,
        )
        return _write_run_summary(summary, run_dir, inspection)

    if synthetic_draft:
        _write_synthetic_batches(handoff, target_locale)
        generation_mode = "synthetic_draft"
    elif generated:
        _write_batches_from_combined(generated, handoff)
        generation_mode = "combined_generated"
    else:
        generation_mode = "generated_dir"

    generated_path = run_dir / "generated.jsonl"
    collect_result = collect_generated_handoff(handoff, generated_path)
    collect_path = run_dir / "generation-collect.json"
    write_json(collect_path, collect_result)
    if collect_result["status"] == "fail":
        artifact_state = build_artifact_state(state_dir, run_dir=run_dir, run_id=run_id)
        summary = _summary(
            run_id,
            "generation_failed",
            project_root,
            source_locale,
            target_locale,
            selected_files,
            run_dir,
            segments_path,
            plan_path,
            handoff_path,
            len(segments),
            len(plan["batches"]),
            generation_mode=generation_mode,
            reference_plan_path=reference_plan_path,
            term_preflight=term_preflight,
            generation_strategy=generation_strategy,
            resolution_gate=resolution_gate,
            generation_handoff_decision=handoff_decision,
            generation_handoff_decision_path=handoff_decision_path,
            operating_mode=operating_mode,
            reference_policy=reference_policy,
            reference_summary=reference_plan["summary"],
            prompt_manifest_path=prompt_manifest_path,
            generation_readme_path=generation_readme_path,
            collect_path=collect_path,
            generated_path=generated_path,
            generation_status=collect_result["status"],
            artifact_state=artifact_state,
            android_overlay_plan=overlay_plan,
        )
        return _write_run_summary(summary, run_dir, inspection)

    generated_segments = read_jsonl(generated_path)
    generation_metadata = _generation_delivery_metadata(generation_mode, generated_segments)
    generation_metadata["handoff_decision"] = _handoff_decision_metadata(handoff_decision)
    provider_failed = generation_metadata.get("provider_status") == "failed"
    delivery_segments = [*generated_segments, *preserved_segments]
    build_reuse_decision(
        state_dir,
        segments,
        generated_segments=delivery_segments,
        provider_policy={"mode": "synthetic_test"} if synthetic_draft else {"mode": "host_agent", "provider_controlled": False},
        run_id=run_id,
    )
    build_segment_regeneration_plan(state_dir, run_id=run_id)
    if (state_dir / KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON).is_file():
        build_knowledge_repair_plan(state_dir, run_id=run_id)
    if (state_dir / KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL).is_file():
        build_knowledge_repair_reconciliation(state_dir)
    review_markdown_path = run_dir / "review-sheet.md"
    review_csv_path = run_dir / "review-sheet.csv"
    review_sheet_path = run_dir / "review-sheet.json"
    review_sheet = write_review_sheet(delivery_segments, review_markdown_path, review_csv_path)
    write_json(review_sheet_path, review_sheet)
    llm_review_request = create_llm_review_request(
        delivery_segments,
        source_locale,
        target_locale,
        collect_result.get("items", []),
        run_id,
    )
    llm_review_request_path = run_dir / "llm-review-request.json"
    llm_review_prompt_path = run_dir / "llm-review-prompt.md"
    write_json(llm_review_request_path, llm_review_request)
    llm_review_prompt_path.write_text(render_llm_review_prompt(llm_review_request), encoding="utf-8", newline="\n")

    staging_dir = run_dir / "staging"
    preserve_target_only = operating_mode in {"existing_locale_maintenance", "rewrite_or_harmonization"}
    non_overlay_delivery_segments = [
        segment
        for segment in delivery_segments
        if segment.get("context", {}).get("source_category") != ANDROID_MERGED_OVERLAY_CATEGORY
    ]
    staging_result = stage_generated(
        project_root,
        non_overlay_delivery_segments,
        staging_dir,
        source_locale,
        target_locale,
        selected_files,
        preserve_target_only=preserve_target_only,
    )
    output_metadata: dict[str, dict[str, Any]] = {}
    overlay_output: dict[str, Any] | None = None
    if overlay_plan:
        overlay_output, overlay_qa_path = stage_overlay(overlay_plan, generated_segments, staging_dir, run_dir)
        staging_result["outputs"].append(overlay_output)
        staging_result["summary"]["output_count"] = len(staging_result["outputs"])
        staging_result["summary"]["merged_overlay_output_count"] = 1
        staging_result["android_merged_overlay"] = _overlay_report(overlay_plan, overlay_output)
        output_metadata[overlay_output["destination"]] = overlay_output_metadata(overlay_plan)
    staging_path = run_dir / "staging-result.json"
    write_json(staging_path, staging_result)
    qa_paths = _validate_staged_outputs(project_root, staging_result, target_locale, run_dir / "qa")
    build_artifact_state(state_dir, run_dir=run_dir, run_id=run_id)
    build_evaluation_scorecard(
        state_dir,
        run_dir=run_dir,
        run_id=run_id,
        generation_metadata=generation_metadata,
        coverage_diagnostics=inspection.get("android_coverage", {}),
        qa_result_paths=qa_paths,
    )
    packaged = package_delivery(
        state_dir,
        staging_dir,
        run_dir / "deliveries",
        qa_paths,
        "blocked" if provider_failed else delivery_status,
        run_id,
        output_metadata,
        generation_metadata,
    )
    delivery_dir = Path(packaged["delivery_directory"])
    build_artifact_state(state_dir, run_dir=run_dir, delivery_dir=delivery_dir, run_id=run_id)
    build_evaluation_scorecard(
        state_dir,
        run_dir=run_dir,
        delivery_dir=delivery_dir,
        run_id=run_id,
        generation_metadata=generation_metadata,
        coverage_diagnostics=inspection.get("android_coverage", {}),
        qa_result_paths=qa_paths,
    )
    _sync_evaluation_assets_to_delivery(state_dir, delivery_dir)
    apply_plan = create_apply_plan(delivery_dir, project_root)
    apply_plan_path = run_dir / "apply-plan.json"
    apply_plan_markdown_path = run_dir / "apply-plan.md"
    write_json(apply_plan_path, apply_plan)
    apply_plan_markdown_path.write_text(render_apply_plan_markdown(apply_plan), encoding="utf-8", newline="\n")
    dashboard = build_delivery_dashboard(delivery_dir)
    dashboard_path = run_dir / "delivery-dashboard.json"
    dashboard_md_path = run_dir / "delivery-dashboard.md"
    write_json(dashboard_path, dashboard)
    dashboard_md_path.write_text(render_dashboard_markdown(dashboard), encoding="utf-8", newline="\n")
    delivery_decision = create_delivery_decision_report(delivery_dir, project_root)
    delivery_decision_path = run_dir / "delivery-decision.json"
    delivery_decision_md_path = run_dir / "delivery-decision.md"
    write_json(delivery_decision_path, delivery_decision)
    delivery_decision_md_path.write_text(
        render_delivery_decision_markdown(delivery_decision),
        encoding="utf-8",
        newline="\n",
    )
    artifact_state = build_artifact_state(state_dir, run_dir=run_dir, delivery_dir=delivery_dir, run_id=run_id)
    evaluation_scorecard = build_evaluation_scorecard(
        state_dir,
        run_dir=run_dir,
        delivery_dir=delivery_dir,
        run_id=run_id,
        generation_metadata=generation_metadata,
        coverage_diagnostics=inspection.get("android_coverage", {}),
        qa_result_paths=qa_paths,
    )
    _sync_evaluation_assets_to_delivery(state_dir, delivery_dir)

    summary = _summary(
        run_id,
        "provider_generation_failed" if provider_failed else "draft_package_created",
        project_root,
        source_locale,
        target_locale,
        selected_files,
        run_dir,
        segments_path,
        plan_path,
        handoff_path,
        len(segments),
        len(plan["batches"]),
        generation_mode=generation_mode,
        reference_plan_path=reference_plan_path,
        term_preflight=term_preflight,
        generation_strategy=generation_strategy,
        resolution_gate=resolution_gate,
        generation_handoff_decision=handoff_decision,
        generation_handoff_decision_path=handoff_decision_path,
        operating_mode=operating_mode,
        reference_policy=reference_policy,
        reference_summary=reference_plan["summary"],
        prompt_manifest_path=prompt_manifest_path,
        generation_readme_path=generation_readme_path,
        collect_path=collect_path,
        generated_path=generated_path,
        generation_status=collect_result["status"],
        generation_metadata=generation_metadata,
        review_sheet_path=review_sheet_path,
        review_markdown_path=review_markdown_path,
        review_csv_path=review_csv_path,
        llm_review_request_path=llm_review_request_path,
        llm_review_prompt_path=llm_review_prompt_path,
        staging_path=staging_path,
        delivery_dir=delivery_dir,
        apply_plan_path=apply_plan_path,
        apply_plan_markdown_path=apply_plan_markdown_path,
        dashboard_path=dashboard_path,
        dashboard_markdown=dashboard_md_path,
        delivery_decision_path=delivery_decision_path,
        delivery_decision_markdown=delivery_decision_md_path,
        output_count=staging_result["summary"]["output_count"],
        qa_status=dashboard["summary"]["qa_status"],
        blocking_count=dashboard["summary"]["blocking_count"],
        warning_count=dashboard["summary"]["warning_count"],
        artifact_state=artifact_state,
        evaluation_scorecard=evaluation_scorecard,
        android_overlay_plan=overlay_plan,
        android_overlay_output=overlay_output,
    )
    return _write_run_summary(summary, run_dir, inspection)


def _sync_evaluation_assets_to_delivery(state_dir: Path, delivery_dir: Path) -> None:
    copied = False
    for name in (EVALUATION_SCORECARD_JSON, EVIDENCE_LEVEL_REPORT_MD):
        source = state_dir / name
        if source.is_file():
            (delivery_dir / name).write_bytes(source.read_bytes())
            copied = True
    manifest_path = delivery_dir / "delivery-manifest.json"
    if copied and manifest_path.is_file():
        manifest = read_json(manifest_path)
        manifest.setdefault("assets", {})["evaluation_scorecard"] = EVALUATION_SCORECARD_JSON
        manifest.setdefault("assets", {})["evidence_level_report"] = EVIDENCE_LEVEL_REPORT_MD
        manifest.setdefault("snapshot", {})["content_sha256"] = _delivery_snapshot_hash(delivery_dir)
        write_json(manifest_path, manifest)


def _delivery_snapshot_hash(delivery_dir: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(item for item in delivery_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(delivery_dir).as_posix()
        if relative == "delivery-manifest.json":
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _select_source_files(inspection: dict[str, Any], source_locale: str, source_files: list[str] | None) -> list[str]:
    inventory = {item["path"]: item for item in inspection["supported_files"]}
    if source_files:
        normalized = [path.replace("\\", "/") for path in source_files]
        unsupported = sorted(path for path in normalized if path not in inventory)
        if unsupported:
            raise ValueError(f"Requested source files were not found or are unsupported: {', '.join(unsupported)}")
        unsupported_adapters = sorted({inventory[path]["adapter"] for path in normalized if inventory[path]["adapter"] not in EXTRACTORS})
        if unsupported_adapters:
            raise ValueError(f"localize-run cannot extract adapters yet: {', '.join(unsupported_adapters)}")
        excluded_android = sorted(
            path
            for path in normalized
            if inventory[path]["adapter"] == "core.android-strings"
            and inventory[path].get("android_role") != "source_candidate"
        )
        if excluded_android:
            raise ValueError(
                "Android locale references or uncertain qualifier paths cannot be source truth: "
                + ", ".join(excluded_android)
            )
        return normalized

    candidates = [
        item
        for item in inspection["supported_files"]
        if item["adapter"] in EXTRACTORS
        and not (
            item["adapter"] == "core.android-strings"
            and item.get("android_role") != "source_candidate"
        )
    ]
    if not candidates:
        raise ValueError("No source files supported by localize-run were found")
    locale_matches = [item["path"] for item in candidates if _matches_source_locale(item, source_locale)]
    return sorted(locale_matches or [item["path"] for item in candidates])


def _matches_source_locale(item: dict[str, Any], source_locale: str) -> bool:
    path = str(item["path"]).replace("\\", "/")
    lower_path = path.lower().replace("_", "-")
    tokens = _locale_tokens(source_locale)
    adapter = item["adapter"]
    if adapter == "core.android-strings":
        return item.get("android_role") == "source_candidate"
    if adapter == "core.ios-strings":
        return any(f"/{token}.lproj/" in f"/{lower_path}/" for token in tokens)
    if adapter == "core.xcstrings":
        return True
    return any(token in lower_path for token in tokens)


def _locale_tokens(locale: str) -> set[str]:
    normalized = locale.lower().replace("_", "-")
    language = normalized.split("-", 1)[0]
    return {normalized, normalized.replace("-", "_"), language}


def _extract_all(project_root: Path, inspection: dict[str, Any], source_files: list[str], source_locale: str) -> list[dict[str, Any]]:
    inventory = {item["path"]: item for item in inspection["supported_files"]}
    segments: list[dict[str, Any]] = []
    for source_file in source_files:
        adapter = inventory[source_file]["adapter"]
        extractor = EXTRACTORS.get(adapter)
        if not extractor:
            raise ValueError(f"localize-run cannot extract adapter: {adapter}")
        path = project_root / source_file
        if adapter == "core.yaml-toml":
            records = extract_structured_segments(path, source_locale, source_file, _structured_format(path))
        else:
            records = extractor(path, source_locale, source_file)
        segments.extend(records)
    return segments


def _write_synthetic_batches(handoff: dict[str, Any], target_locale: str) -> None:
    for batch in handoff.get("batches", []):
        packet = read_json(Path(batch["work_packet"]))
        generated = [_synthetic_segment(segment, target_locale) for segment in packet.get("segments", [])]
        write_jsonl(Path(batch["generated"]), generated)


def _synthetic_segment(segment: dict[str, Any], target_locale: str) -> dict[str, Any]:
    generated = dict(segment)
    source = str(segment.get("source", ""))
    placeholders = [str(item) for item in segment.get("constraints", {}).get("placeholders", [])]
    plural_source = str(segment.get("context", {}).get("source_plural") or "")
    if placeholders and plural_source and any(placeholder not in source for placeholder in placeholders):
        source = plural_source
    generated["target_locale"] = target_locale
    generated["target"] = f"[{target_locale}] {source}"
    generated["status"] = "generated"
    generated["generation"] = {
        "provider": "synthetic",
        "quality_claim": "none",
        "purpose": "test_or_benchmark_only",
    }
    return generated


def _render_generation_strategy_blocked(strategy: dict[str, Any]) -> str:
    blockers = strategy.get("blockers", [])
    lines = [
        "# Generation Strategy Gate Blocked",
        "",
        "Generation handoff was not created because deterministic strategy checks found blockers.",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        for blocker in blockers:
            lines.append(f"- `{blocker.get('code')}`: {blocker.get('message')}")
    else:
        lines.append("- `unknown`: strategy status is blocked")
    lines.extend(
        [
            "",
            "Resolve the blocking review or governance artifact, then rerun `localize-run`.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_batches_from_combined(generated: Path, handoff: dict[str, Any]) -> None:
    records = read_jsonl(generated)
    expected_ids: set[str] = set()
    for batch in handoff.get("batches", []):
        packet = read_json(Path(batch["work_packet"]))
        expected_ids.update(str(segment["segment_id"]) for segment in packet.get("segments", []))
    unexpected = sorted({str(record.get("segment_id")) for record in records if str(record.get("segment_id")) not in expected_ids})
    if unexpected:
        raise ValueError(f"Generated file contains unexpected segment ids: {', '.join(unexpected)}")

    for batch in handoff.get("batches", []):
        packet = read_json(Path(batch["work_packet"]))
        batch_ids = {str(segment["segment_id"]) for segment in packet.get("segments", [])}
        write_jsonl(Path(batch["generated"]), [record for record in records if str(record.get("segment_id")) in batch_ids])


def _generation_delivery_metadata(generation_mode: str, generated_segments: list[dict[str, Any]]) -> dict[str, Any]:
    segment_count = len(generated_segments)
    fallback_segments = [
        segment
        for segment in generated_segments
        if _is_synthetic_fallback_generation(segment.get("generation", {}))
    ]
    if fallback_segments:
        first_generation = fallback_segments[0].get("generation", {})
        provider = str(first_generation.get("provider") or "")
        return {
            "provider_requested": "deepseek" if provider.startswith("deepseek") else provider or "provider",
            "provider_actual": "synthetic_fallback",
            "provider_status": "failed",
            "provider_error_kind": str(first_generation.get("provider_error_kind") or "provider_fallback_output"),
            "provider_generated_segments": 0,
            "synthetic_fallback_segments": len(fallback_segments),
            "quality_claim": "none",
            "apply_allowed": False,
        }

    if generation_mode == "synthetic_draft":
        return {
            "provider_requested": "synthetic",
            "provider_actual": "synthetic",
            "provider_status": "synthetic_test",
            "provider_generated_segments": 0,
            "synthetic_fallback_segments": 0,
            "synthetic_segments": segment_count,
            "quality_claim": "none",
            "apply_allowed": True,
        }

    providers = sorted(
        {
            str(segment.get("generation", {}).get("provider") or "generated_input")
            for segment in generated_segments
        }
    )
    quality_claims = sorted(
        {
            str(segment.get("generation", {}).get("quality_claim") or "unspecified")
            for segment in generated_segments
        }
    )
    provider = providers[0] if len(providers) == 1 else "mixed"
    quality_claim = quality_claims[0] if len(quality_claims) == 1 else "mixed"
    return {
        "provider_requested": provider,
        "provider_actual": provider,
        "provider_status": "passed",
        "provider_generated_segments": segment_count,
        "synthetic_fallback_segments": 0,
        "quality_claim": quality_claim,
        "apply_allowed": True,
    }


def _is_synthetic_fallback_generation(generation: object) -> bool:
    if not isinstance(generation, dict):
        return False
    provider = str(generation.get("provider") or "")
    return provider in {"deepseek-fallback", "synthetic_fallback"} or generation.get("purpose") == "fallback"


def _handoff_decision_metadata(decision: dict[str, Any] | None) -> dict[str, Any]:
    if not decision:
        return {
            "status": "not_checked",
            "handoff_mode": "not_checked",
            "handoff_allowed": True,
            "full_quality_handoff_allowed": False,
            "forbidden_quality_claims": [],
        }
    return {
        "artifact": "generation-handoff-decision.json",
        "status": decision.get("status"),
        "handoff_mode": decision.get("handoff_mode"),
        "handoff_allowed": decision.get("handoff_allowed"),
        "full_quality_handoff_allowed": decision.get("full_quality_handoff_allowed"),
        "provider_backed_generation_allowed": decision.get("provider_backed_generation_allowed"),
        "apply_policy": decision.get("apply_policy"),
        "delivery_policy": decision.get("delivery_policy"),
        "forbidden_quality_claims": decision.get("forbidden_quality_claims", []),
        "unresolved_question_count": len(decision.get("unresolved_questions", [])),
    }


def _artifact_state_metadata(state: dict[str, Any] | None) -> dict[str, Any]:
    if not state:
        return {
            "status": "not_checked",
            "safe_to_continue": True,
            "artifact": None,
            "summary": {},
            "stale_artifacts": [],
            "blocked_artifacts": [],
        }
    return {
        "status": state.get("status", "not_checked"),
        "safe_to_continue": bool(state.get("safe_to_continue", False)),
        "artifact": ARTIFACT_STATE_JSON,
        "summary": state.get("summary", {}),
        "stale_artifacts": state.get("stale_artifacts", []),
        "blocked_artifacts": state.get("blocked_artifacts", []),
        "decisions": state.get("decisions", {}),
        "next_actions": state.get("next_actions", []),
    }


def _validate_staged_outputs(project_root: Path, staging_result: dict[str, Any], target_locale: str, qa_dir: Path) -> list[Path]:
    qa_paths: list[Path] = []
    for index, output in enumerate(staging_result.get("outputs", []), 1):
        adapter = output["adapter"]
        source_value = Path(str(output.get("validation_source") or output["source"]))
        source = source_value if source_value.is_absolute() else project_root / source_value
        target = Path(output["output"])
        if not target.is_absolute():
            target = Path(staging_result["staging_dir"]) / output["destination"]
        if adapter == "core.android-strings":
            qa = validate_android_strings(source, target)
        elif adapter == "core.gettext-po":
            qa = validate_po_pair(source, target)
        elif adapter == "core.ios-strings":
            qa = validate_ios_strings(source, target)
        elif adapter == "core.json-locale":
            qa = validate_json_pair(source, target)
        elif adapter == "core.markup":
            qa = validate_markup_pair(source, target)
        elif adapter == "core.subtitles":
            qa = validate_subtitle_pair(source, target)
        elif adapter == "core.tabular":
            qa = validate_tabular_pair(source, target)
        elif adapter == "core.word-document":
            qa = validate_word_pair(source, target)
        elif adapter == "core.xcstrings":
            qa = validate_xcstrings(source, target, target_locale)
        elif adapter == "core.xliff":
            qa = validate_xliff_pair(source, target)
        elif adapter == "core.yaml-toml":
            qa = validate_structured_pair(source, target, _structured_format(source))
        else:
            raise ValueError(f"localize-run cannot validate adapter: {adapter}")
        qa_path = qa_dir / f"{index:03d}-{adapter.replace('.', '-').replace('_', '-')}.json"
        write_json(qa_path, qa)
        qa_paths.append(qa_path)
    return qa_paths


def _structured_format(path: Path) -> str:
    return "toml" if path.suffix.lower() == ".toml" else "yaml"


def _summary(
    run_id: str,
    status: str,
    project_root: Path,
    source_locale: str,
    target_locale: str,
    source_files: list[str],
    run_dir: Path,
    segments_path: Path,
    plan_path: Path,
    handoff_path: Path,
    segment_count: int,
    batch_count: int,
    generation_mode: str,
    prompt_manifest_path: Path | None = None,
    generation_readme_path: Path | None = None,
    collect_path: Path | None = None,
    generated_path: Path | None = None,
    generation_status: str | None = None,
    review_sheet_path: Path | None = None,
    review_markdown_path: Path | None = None,
    review_csv_path: Path | None = None,
    llm_review_request_path: Path | None = None,
    llm_review_prompt_path: Path | None = None,
    staging_path: Path | None = None,
    delivery_dir: Path | None = None,
    apply_plan_path: Path | None = None,
    apply_plan_markdown_path: Path | None = None,
    dashboard_path: Path | None = None,
    dashboard_markdown: Path | None = None,
    delivery_decision_path: Path | None = None,
    delivery_decision_markdown: Path | None = None,
    output_count: int = 0,
    qa_status: str | None = None,
    blocking_count: int = 0,
    warning_count: int = 0,
    reference_plan_path: Path | None = None,
    term_preflight: dict[str, Any] | None = None,
    generation_strategy: dict[str, Any] | None = None,
    resolution_gate: dict[str, Any] | None = None,
    generation_handoff_decision: dict[str, Any] | None = None,
    generation_handoff_decision_path: Path | None = None,
    operating_mode: str = DEFAULT_OPERATING_MODE,
    reference_policy: str = DEFAULT_REFERENCE_POLICY_BY_MODE[DEFAULT_OPERATING_MODE],
    reference_summary: dict[str, Any] | None = None,
    android_overlay_plan: dict[str, Any] | None = None,
    android_overlay_output: dict[str, Any] | None = None,
    generation_metadata: dict[str, Any] | None = None,
    artifact_state: dict[str, Any] | None = None,
    evaluation_scorecard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifacts: dict[str, str] = {
        "run_directory": run_dir.as_posix(),
        "session_index": session_index_path(project_root).as_posix(),
        "segments": segments_path.as_posix(),
        "batch_plan": plan_path.as_posix(),
        "work_packets": (run_dir / "work-packets").as_posix(),
        "draft_requests": (run_dir / "draft-requests").as_posix(),
        "prompts": (run_dir / "prompts").as_posix(),
        "responses": (run_dir / "responses").as_posix(),
        "generation_handoff": handoff_path.as_posix(),
    }
    optional = {
        "prompt_manifest": prompt_manifest_path,
        "generation_readme": generation_readme_path,
        "generation_collect": collect_path,
        "generated_segments": generated_path,
        "review_sheet": review_sheet_path,
        "review_sheet_markdown": review_markdown_path,
        "review_sheet_csv": review_csv_path,
        "llm_review_request": llm_review_request_path,
        "llm_review_prompt": llm_review_prompt_path,
        "staging_result": staging_path,
        "delivery_directory": delivery_dir,
        "apply_plan": apply_plan_path,
        "apply_plan_markdown": apply_plan_markdown_path,
        "delivery_dashboard": dashboard_path,
        "delivery_dashboard_markdown": dashboard_markdown,
        "delivery_decision": delivery_decision_path,
        "delivery_decision_markdown": delivery_decision_markdown,
        "reference_plan": reference_plan_path,
        "generation_handoff_decision": generation_handoff_decision_path,
    }
    for key, value in optional.items():
        if value is not None:
            artifacts[key] = value.as_posix()
    termbase_artifacts: dict[str, str] = {}
    if term_preflight:
        state_dir = project_root / ".localize-anything"
        for key, value in term_preflight.get("artifacts", {}).items():
            artifact_key = str(key)
            path = state_dir / str(value)
            artifacts[artifact_key] = path.as_posix()
            termbase_artifacts[artifact_key] = path.as_posix()
    strategy_artifacts: dict[str, str] = {}
    if generation_strategy:
        state_dir = project_root / ".localize-anything"
        for key, value in generation_strategy.get("artifacts", {}).items():
            artifact_key = str(key)
            path = state_dir / str(value)
            artifacts[artifact_key] = path.as_posix()
            strategy_artifacts[artifact_key] = path.as_posix()
    resolution_artifacts: dict[str, str] = {}
    if resolution_gate:
        state_dir = project_root / ".localize-anything"
        for key, value in resolution_gate.get("artifacts", {}).items():
            artifact_key = str(key)
            path = state_dir / str(value)
            artifacts[artifact_key] = path.as_posix()
            resolution_artifacts[artifact_key] = path.as_posix()
    if generation_handoff_decision:
        state_dir = project_root / ".localize-anything"
        for key, value in generation_handoff_decision_asset_paths(state_dir).items():
            path = state_dir / value
            artifacts[key] = path.as_posix()
    if artifact_state:
        artifacts["artifact_state"] = (project_root / ".localize-anything" / ARTIFACT_STATE_JSON).as_posix()
        segment_artifact = artifact_state.get("segment_staleness", {}).get("stale_segments_artifact")
        reuse_artifact = artifact_state.get("segment_staleness", {}).get("artifact")
        if segment_artifact:
            artifacts["stale_segments"] = (project_root / ".localize-anything" / str(segment_artifact)).as_posix()
        if reuse_artifact:
            artifacts["reuse_decision"] = (project_root / ".localize-anything" / str(reuse_artifact)).as_posix()
        repair_state = artifact_state.get("segment_repair", {})
        for key, artifact_key in (
            ("segment_regeneration_plan", "artifact"),
            ("repair_request", "repair_request_artifact"),
            ("repair_result", "repair_result_artifact"),
            ("repair_history", "repair_history_artifact"),
        ):
            artifact = repair_state.get(artifact_key)
            if artifact:
                artifacts[key] = (project_root / ".localize-anything" / str(artifact)).as_posix()
    state_dir = project_root / ".localize-anything"
    if (state_dir / EVALUATION_SCORECARD_JSON).is_file():
        artifacts["evaluation_scorecard"] = (state_dir / EVALUATION_SCORECARD_JSON).as_posix()
    if (state_dir / EVIDENCE_LEVEL_REPORT_MD).is_file():
        artifacts["evidence_level_report"] = (state_dir / EVIDENCE_LEVEL_REPORT_MD).as_posix()
    if (state_dir / HUMAN_REVIEW_EVIDENCE_JSONL).is_file():
        artifacts["human_review_evidence"] = (state_dir / HUMAN_REVIEW_EVIDENCE_JSONL).as_posix()
    if (state_dir / CLAIM_ACCEPTANCE_DECISION_JSON).is_file():
        artifacts["claim_acceptance_decision"] = (state_dir / CLAIM_ACCEPTANCE_DECISION_JSON).as_posix()
    if (state_dir / SIGNOFF_RECORD_JSON).is_file():
        artifacts["signoff_record"] = (state_dir / SIGNOFF_RECORD_JSON).as_posix()
    if (state_dir / WORKBENCH_ACTION_LOG_JSONL).is_file():
        artifacts["workbench_action_log"] = (state_dir / WORKBENCH_ACTION_LOG_JSONL).as_posix()
    if (state_dir / WORKBENCH_ACTION_RESULT_JSON).is_file():
        artifacts["workbench_action_result"] = (state_dir / WORKBENCH_ACTION_RESULT_JSON).as_posix()
    if (state_dir / WORKBENCH_REVIEW_QUEUE_JSON).is_file():
        artifacts["workbench_review_queue"] = (state_dir / WORKBENCH_REVIEW_QUEUE_JSON).as_posix()
    if (state_dir / WORKBENCH_CLAIM_QUEUE_JSON).is_file():
        artifacts["workbench_claim_queue"] = (state_dir / WORKBENCH_CLAIM_QUEUE_JSON).as_posix()
    if (state_dir / WORKBENCH_SIGNOFF_SUMMARY_JSON).is_file():
        artifacts["workbench_signoff_summary"] = (state_dir / WORKBENCH_SIGNOFF_SUMMARY_JSON).as_posix()
    if (state_dir / WORKBENCH_DOCUMENT_EVIDENCE_QUEUE_JSON).is_file():
        artifacts["workbench_document_evidence_queue"] = (state_dir / WORKBENCH_DOCUMENT_EVIDENCE_QUEUE_JSON).as_posix()
    for key, name in (
        ("knowledge_usage_report", KNOWLEDGE_USAGE_REPORT_JSON),
        ("constraint_application_audit", CONSTRAINT_APPLICATION_AUDIT_JSON),
        ("knowledge_conflict_report", KNOWLEDGE_CONFLICT_REPORT_JSON),
        ("knowledge_audit_enforcement_decision", KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON),
        ("workbench_knowledge_review_queue", WORKBENCH_KNOWLEDGE_REVIEW_QUEUE_JSON),
        ("knowledge_audit_resolution_log", KNOWLEDGE_AUDIT_RESOLUTION_LOG_JSONL),
        ("knowledge_constraint_review_evidence", KNOWLEDGE_CONSTRAINT_REVIEW_EVIDENCE_JSONL),
        ("knowledge_conflict_resolution", KNOWLEDGE_CONFLICT_RESOLUTION_JSON),
        ("knowledge_assurance_summary", KNOWLEDGE_ASSURANCE_SUMMARY_JSON),
        ("knowledge_repair_plan", KNOWLEDGE_REPAIR_PLAN_JSON),
        ("knowledge_repair_request", KNOWLEDGE_REPAIR_REQUEST_JSON),
        ("knowledge_repair_impact_report", KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON),
        ("knowledge_repair_result_intake", KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL),
        ("knowledge_repair_qa_report", KNOWLEDGE_REPAIR_QA_REPORT_JSON),
        ("knowledge_repair_reconciliation", KNOWLEDGE_REPAIR_RECONCILIATION_JSON),
        ("knowledge_recompute_plan", KNOWLEDGE_RECOMPUTE_PLAN_JSON),
        ("knowledge_recompute_result", KNOWLEDGE_RECOMPUTE_RESULT_JSON),
        ("knowledge_repair_closure_decision", KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON),
        ("knowledge_readiness_impact_report", KNOWLEDGE_READINESS_IMPACT_REPORT_JSON),
        ("readiness_authorization_matrix", READINESS_AUTHORIZATION_MATRIX_JSON),
        ("manual_followup_gap_report", MANUAL_FOLLOWUP_GAP_REPORT_JSON),
        ("apply_readiness_report", APPLY_READINESS_REPORT_JSON),
        ("delivery_readiness_report", DELIVERY_READINESS_REPORT_JSON),
        ("workbench_readiness_action_queue", WORKBENCH_READINESS_ACTION_QUEUE_JSON),
        ("workbench_readiness_action_result", WORKBENCH_READINESS_ACTION_RESULT_JSON),
        ("workbench_readiness_action_log", WORKBENCH_READINESS_ACTION_LOG_JSONL),
        ("workflow_run_plan", WORKFLOW_RUN_PLAN_JSON),
        ("workflow_stage_status", WORKFLOW_STAGE_STATUS_JSON),
        ("workflow_execution_result", WORKFLOW_EXECUTION_RESULT_JSON),
        ("workflow_readiness_summary", WORKFLOW_READINESS_SUMMARY_JSON),
        ("workflow_dependency_graph", WORKFLOW_DEPENDENCY_GRAPH_JSON),
        ("workflow_resume_plan", WORKFLOW_RESUME_PLAN_JSON),
        ("artifact_invalidation_report", ARTIFACT_INVALIDATION_REPORT_JSON),
        ("selective_recompute_plan", SELECTIVE_RECOMPUTE_PLAN_JSON),
        ("selective_recompute_result", SELECTIVE_RECOMPUTE_RESULT_JSON),
        ("incremental_workflow_summary", INCREMENTAL_WORKFLOW_SUMMARY_JSON),
        ("workflow_lock_state", WORKFLOW_LOCK_STATE_JSON),
        ("workflow_checkpoint_log", WORKFLOW_CHECKPOINT_LOG_JSONL),
        ("workflow_transaction_manifest", WORKFLOW_TRANSACTION_MANIFEST_JSON),
        ("workflow_idempotency_report", WORKFLOW_IDEMPOTENCY_REPORT_JSON),
        ("workflow_recovery_plan", WORKFLOW_RECOVERY_PLAN_JSON),
        ("workflow_recovery_result", WORKFLOW_RECOVERY_RESULT_JSON),
        ("provider_execution_policy", PROVIDER_EXECUTION_POLICY_JSON),
        ("provider_handoff_request", PROVIDER_HANDOFF_REQUEST_JSON),
        ("provider_execution_ledger", PROVIDER_EXECUTION_LEDGER_JSONL),
        ("provider_result_intake", PROVIDER_RESULT_INTAKE_JSONL),
        ("provider_evidence_reconciliation", PROVIDER_EVIDENCE_RECONCILIATION_JSON),
        ("provider_result_qa_report", PROVIDER_RESULT_QA_REPORT_JSON),
        ("provider_result_review_evidence", PROVIDER_RESULT_REVIEW_EVIDENCE_JSONL),
        ("provider_result_acceptance_decision", PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON),
        ("provider_claim_support_report", PROVIDER_CLAIM_SUPPORT_REPORT_JSON),
        ("workbench_provider_review_queue", WORKBENCH_PROVIDER_REVIEW_QUEUE_JSON),
        ("locale_capability_report", LOCALE_CAPABILITY_REPORT_JSON),
        ("locale_risk_report", LOCALE_RISK_REPORT_JSON),
        ("locale_readiness_impact", LOCALE_READINESS_IMPACT_JSON),
        ("translation_provenance", TRANSLATION_PROVENANCE_JSONL),
        ("segment_evidence_view", SEGMENT_EVIDENCE_VIEW_JSON),
        ("provenance_coverage_report", PROVENANCE_COVERAGE_REPORT_JSON),
        ("translation_claim_provenance_report", TRANSLATION_CLAIM_PROVENANCE_REPORT_JSON),
    ):
        if (state_dir / name).is_file():
            artifacts[key] = (state_dir / name).as_posix()
    for key, name in (
        ("document_decision_log", DOCUMENT_DECISION_LOG_JSONL),
        ("leadership_review_evidence", LEADERSHIP_REVIEW_EVIDENCE_JSONL),
        ("document_claim_resolution", DOCUMENT_CLAIM_RESOLUTION_JSON),
        ("document_signoff_summary", DOCUMENT_SIGNOFF_SUMMARY_JSON),
    ):
        if (state_dir / name).is_file():
            artifacts[key] = (state_dir / name).as_posix()
    for key, name in (
        ("document_evidence_manifest", DOCUMENT_EVIDENCE_MANIFEST_JSON),
        ("document_intake_report", DOCUMENT_INTAKE_REPORT_JSON),
        ("semantic_alignment", SEMANTIC_ALIGNMENT_JSONL),
        ("claim_metric_report", CLAIM_METRIC_REPORT_JSON),
        ("publicity_risk_report", PUBLICITY_RISK_REPORT_JSON),
        ("leadership_review_brief", LEADERSHIP_REVIEW_BRIEF_MD),
        ("open_decisions", OPEN_DECISIONS_MD),
    ):
        if (state_dir / name).is_file():
            artifacts[key] = (state_dir / name).as_posix()
    document_evidence_manifest = read_json(state_dir / DOCUMENT_EVIDENCE_MANIFEST_JSON) if (state_dir / DOCUMENT_EVIDENCE_MANIFEST_JSON).is_file() else {}
    document_evidence_queue = read_json(state_dir / WORKBENCH_DOCUMENT_EVIDENCE_QUEUE_JSON) if (state_dir / WORKBENCH_DOCUMENT_EVIDENCE_QUEUE_JSON).is_file() else {}
    document_claim_resolution = read_json(state_dir / DOCUMENT_CLAIM_RESOLUTION_JSON) if (state_dir / DOCUMENT_CLAIM_RESOLUTION_JSON).is_file() else {}
    document_signoff_summary = read_json(state_dir / DOCUMENT_SIGNOFF_SUMMARY_JSON) if (state_dir / DOCUMENT_SIGNOFF_SUMMARY_JSON).is_file() else {}

    summary = {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "run_id": run_id,
        "status": status,
        "project": {
            "root": project_root.as_posix(),
            "source_locale": source_locale,
            "target_locale": target_locale,
            "mode": "standard_project",
            "operating_mode": operating_mode,
            "reference_policy": reference_policy,
        },
        "source_files": source_files,
        "reference": {
            "operating_mode": operating_mode,
            "reference_policy": reference_policy,
            "mode_contract": mode_contract(operating_mode, reference_policy),
            "summary": reference_summary or {},
        },
        "terminology": {
            "status": (term_preflight or {}).get("status", "not_checked"),
            "terminology_assurance": (term_preflight or {}).get("terminology_assurance", "not_checked"),
            "summary": (term_preflight or {}).get("summary", {}),
            "artifacts": termbase_artifacts,
        },
        "generation": {
            "mode": generation_mode,
            "status": generation_status or "pending",
            "provider_agnostic": True,
            "strategy": {
                "status": (generation_strategy or {}).get("status", "not_checked"),
                "generation_readiness": (generation_strategy or {}).get("generation_readiness", "not_checked"),
                "route": (generation_strategy or {}).get("route", {}),
                "artifacts": strategy_artifacts,
            },
            "handoff_decision": _handoff_decision_metadata(generation_handoff_decision),
            **(generation_metadata or {}),
        },
        "resolution": {
            "status": (resolution_gate or {}).get("status", "not_checked"),
            "summary": (resolution_gate or {}).get("summary", {}),
            "artifacts": resolution_artifacts,
        },
        "artifact_state": _artifact_state_metadata(artifact_state),
        "summary": {
            "source_file_count": len(source_files),
            "segment_count": segment_count,
            "batch_count": batch_count,
            "output_count": output_count,
            "qa_status": qa_status or "not_checked",
            "blocking_count": blocking_count,
            "warning_count": warning_count,
            "terminology_assurance": (term_preflight or {}).get("terminology_assurance", "not_checked"),
            "unresolved_blocking_questions": (resolution_gate or {}).get("summary", {}).get("unresolved_blocking_count", 0),
            "unresolved_resolution_questions": (resolution_gate or {}).get("summary", {}).get("unresolved_count", 0),
            "generation_handoff_status": (generation_handoff_decision or {}).get("status", "not_checked"),
            "full_quality_handoff_allowed": bool((generation_handoff_decision or {}).get("full_quality_handoff_allowed", False)),
            "artifact_state_status": (artifact_state or {}).get("status", "not_checked"),
            "stale_artifact_count": (artifact_state or {}).get("summary", {}).get("stale_count", 0),
            "blocked_artifact_count": (artifact_state or {}).get("summary", {}).get("blocked_count", 0),
            "stale_segment_count": (artifact_state or {}).get("summary", {}).get("stale_segment_count", 0),
            "segments_requiring_regeneration": (artifact_state or {}).get("summary", {}).get("segments_requiring_regeneration_count", 0),
            "segments_requiring_review": (artifact_state or {}).get("summary", {}).get("segments_requiring_review_count", 0),
            "pending_segment_repairs": (artifact_state or {}).get("summary", {}).get("segment_repair_pending_count", 0),
            "segments_targeted_repair": (artifact_state or {}).get("summary", {}).get("segments_targeted_repair_count", 0),
            "segments_human_confirm": (artifact_state or {}).get("summary", {}).get("segments_human_confirm_count", 0),
            "segment_repairs_applied": (artifact_state or {}).get("summary", {}).get("segment_repair_applied_count", 0),
            "segment_repairs_pending_provider": (artifact_state or {}).get("summary", {}).get("segment_repair_pending_provider_count", 0),
            "segment_repairs_pending_human": (artifact_state or {}).get("summary", {}).get("segment_repair_pending_human_count", 0),
            "segment_repairs_failed_qa": (artifact_state or {}).get("summary", {}).get("segment_repair_failed_qa_count", 0),
            "segment_repairs_skipped_not_deterministic": (artifact_state or {}).get("summary", {}).get(
                "segment_repair_skipped_not_deterministic_count",
                0,
            ),
            "evaluation_status": (evaluation_scorecard or {}).get("status", "not_checked"),
            "overall_claim": (evaluation_scorecard or {}).get("overall_claim", "not_checked"),
            "highest_evidence_level": (evaluation_scorecard or {}).get("evidence_level", {}).get("highest_supported", "not_provided"),
            "highest_global_human_review_level": (evaluation_scorecard or {}).get("evidence_level", {}).get(
                "highest_global_human_supported",
                "not_provided",
            ),
            "human_review_status": (evaluation_scorecard or {}).get("human_review_evidence", {}).get("status", "not_checked"),
            "claim_acceptance_status": (evaluation_scorecard or {}).get("claim_acceptance", {}).get("status", "not_checked"),
            "signoff_status": (evaluation_scorecard or {}).get("signoff", {}).get("status", "not_checked"),
            "signoff_delivery_authorized": bool((evaluation_scorecard or {}).get("signoff", {}).get("delivery_authorized", False)),
            "signoff_apply_authorized": bool((evaluation_scorecard or {}).get("signoff", {}).get("apply_authorized", False)),
            "forbidden_claim_count": len((evaluation_scorecard or {}).get("forbidden_claims", [])),
            "knowledge_audit_enforcement_status": (
                read_json(state_dir / KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON).get("status", "not_checked")
                if (state_dir / KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON).is_file()
                else "not_checked"
            ),
            "knowledge_assurance_status": (
                read_json(state_dir / KNOWLEDGE_ASSURANCE_SUMMARY_JSON).get("status", "not_checked")
                if (state_dir / KNOWLEDGE_ASSURANCE_SUMMARY_JSON).is_file()
                else "not_checked"
            ),
            "knowledge_conflict_resolution_status": (
                read_json(state_dir / KNOWLEDGE_CONFLICT_RESOLUTION_JSON).get("status", "not_checked")
                if (state_dir / KNOWLEDGE_CONFLICT_RESOLUTION_JSON).is_file()
                else "not_checked"
            ),
            "knowledge_repair_impact_status": (
                read_json(state_dir / KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON).get("status", "not_checked")
                if (state_dir / KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON).is_file()
                else "not_checked"
            ),
            "pending_knowledge_repair_count": (
                read_json(state_dir / KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON).get("summary", {}).get("repair_item_count", 0)
                if (state_dir / KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON).is_file()
                else 0
            ),
            "knowledge_repair_qa_status": (
                read_json(state_dir / KNOWLEDGE_REPAIR_QA_REPORT_JSON).get("status", "not_checked")
                if (state_dir / KNOWLEDGE_REPAIR_QA_REPORT_JSON).is_file()
                else "not_checked"
            ),
            "knowledge_repair_reconciliation_status": (
                read_json(state_dir / KNOWLEDGE_REPAIR_RECONCILIATION_JSON).get("status", "not_checked")
                if (state_dir / KNOWLEDGE_REPAIR_RECONCILIATION_JSON).is_file()
                else "not_checked"
            ),
            "provider_evidence_reconciliation_status": (
                read_json(state_dir / PROVIDER_EVIDENCE_RECONCILIATION_JSON).get("status", "not_checked")
                if (state_dir / PROVIDER_EVIDENCE_RECONCILIATION_JSON).is_file()
                else "not_checked"
            ),
            "provider_result_qa_status": (
                read_json(state_dir / PROVIDER_RESULT_QA_REPORT_JSON).get("status", "not_checked")
                if (state_dir / PROVIDER_RESULT_QA_REPORT_JSON).is_file()
                else "not_checked"
            ),
            "provider_result_acceptance_status": (
                read_json(state_dir / PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON).get("status", "not_checked")
                if (state_dir / PROVIDER_RESULT_ACCEPTANCE_DECISION_JSON).is_file()
                else "not_checked"
            ),
            "provider_claim_support_status": (
                read_json(state_dir / PROVIDER_CLAIM_SUPPORT_REPORT_JSON).get("status", "not_checked")
                if (state_dir / PROVIDER_CLAIM_SUPPORT_REPORT_JSON).is_file()
                else "not_checked"
            ),
            "locale_capability_status": (
                read_json(state_dir / LOCALE_CAPABILITY_REPORT_JSON).get("status", "not_checked")
                if (state_dir / LOCALE_CAPABILITY_REPORT_JSON).is_file()
                else "not_checked"
            ),
            "locale_risk_status": (
                read_json(state_dir / LOCALE_RISK_REPORT_JSON).get("status", "not_checked")
                if (state_dir / LOCALE_RISK_REPORT_JSON).is_file()
                else "not_checked"
            ),
            "locale_readiness_impact_status": (
                read_json(state_dir / LOCALE_READINESS_IMPACT_JSON).get("status", "not_checked")
                if (state_dir / LOCALE_READINESS_IMPACT_JSON).is_file()
                else "not_checked"
            ),
            "provenance_coverage_status": (
                read_json(state_dir / PROVENANCE_COVERAGE_REPORT_JSON).get("status", "not_checked")
                if (state_dir / PROVENANCE_COVERAGE_REPORT_JSON).is_file()
                else "not_checked"
            ),
            "translation_claim_provenance_status": (
                read_json(state_dir / TRANSLATION_CLAIM_PROVENANCE_REPORT_JSON).get("status", "not_checked")
                if (state_dir / TRANSLATION_CLAIM_PROVENANCE_REPORT_JSON).is_file()
                else "not_checked"
            ),
            "knowledge_repair_closure_status": (
                read_json(state_dir / KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON).get("status", "not_checked")
                if (state_dir / KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON).is_file()
                else "not_checked"
            ),
            "knowledge_recompute_result_status": (
                read_json(state_dir / KNOWLEDGE_RECOMPUTE_RESULT_JSON).get("status", "not_checked")
                if (state_dir / KNOWLEDGE_RECOMPUTE_RESULT_JSON).is_file()
                else "not_checked"
            ),
            "knowledge_readiness_impact_status": (
                read_json(state_dir / KNOWLEDGE_READINESS_IMPACT_REPORT_JSON).get("status", "not_checked")
                if (state_dir / KNOWLEDGE_READINESS_IMPACT_REPORT_JSON).is_file()
                else "not_checked"
            ),
            "readiness_authorization_delivery_status": (
                read_json(state_dir / READINESS_AUTHORIZATION_MATRIX_JSON).get("delivery_readiness_status", "not_checked")
                if (state_dir / READINESS_AUTHORIZATION_MATRIX_JSON).is_file()
                else "not_checked"
            ),
            "readiness_authorization_apply_status": (
                read_json(state_dir / READINESS_AUTHORIZATION_MATRIX_JSON).get("apply_readiness_status", "not_checked")
                if (state_dir / READINESS_AUTHORIZATION_MATRIX_JSON).is_file()
                else "not_checked"
            ),
            "manual_followup_gap_count": (
                read_json(state_dir / MANUAL_FOLLOWUP_GAP_REPORT_JSON).get("summary", {}).get("gap_count", 0)
                if (state_dir / MANUAL_FOLLOWUP_GAP_REPORT_JSON).is_file()
                else 0
            ),
            "apply_readiness_report_status": (
                read_json(state_dir / APPLY_READINESS_REPORT_JSON).get("apply_status", "not_checked")
                if (state_dir / APPLY_READINESS_REPORT_JSON).is_file()
                else "not_checked"
            ),
            "delivery_readiness_report_status": (
                read_json(state_dir / DELIVERY_READINESS_REPORT_JSON).get("delivery_status", "not_checked")
                if (state_dir / DELIVERY_READINESS_REPORT_JSON).is_file()
                else "not_checked"
            ),
            "workbench_readiness_action_queue_present": (state_dir / WORKBENCH_READINESS_ACTION_QUEUE_JSON).is_file(),
            "workbench_readiness_action_result_present": (state_dir / WORKBENCH_READINESS_ACTION_RESULT_JSON).is_file(),
            "workbench_readiness_action_log_present": (state_dir / WORKBENCH_READINESS_ACTION_LOG_JSONL).is_file(),
            "workflow_execution_status": (
                read_json(state_dir / WORKFLOW_EXECUTION_RESULT_JSON).get("status", "not_checked")
                if (state_dir / WORKFLOW_EXECUTION_RESULT_JSON).is_file()
                else "not_checked"
            ),
            "workflow_remaining_blocker_count": (
                len(read_json(state_dir / WORKFLOW_EXECUTION_RESULT_JSON).get("remaining_blockers", []))
                if (state_dir / WORKFLOW_EXECUTION_RESULT_JSON).is_file()
                else 0
            ),
            "workflow_readiness_status": (
                read_json(state_dir / WORKFLOW_READINESS_SUMMARY_JSON).get("overall_workflow_status", "not_checked")
                if (state_dir / WORKFLOW_READINESS_SUMMARY_JSON).is_file()
                else "not_checked"
            ),
            "workflow_resume_status": (
                read_json(state_dir / WORKFLOW_RESUME_PLAN_JSON).get("resume_status", "not_checked")
                if (state_dir / WORKFLOW_RESUME_PLAN_JSON).is_file()
                else "not_checked"
            ),
            "selective_recompute_status": (
                read_json(state_dir / SELECTIVE_RECOMPUTE_RESULT_JSON).get("status", "not_checked")
                if (state_dir / SELECTIVE_RECOMPUTE_RESULT_JSON).is_file()
                else "not_checked"
            ),
            "workflow_lock_status": (
                read_json(state_dir / WORKFLOW_LOCK_STATE_JSON).get("lock_status", "not_checked")
                if (state_dir / WORKFLOW_LOCK_STATE_JSON).is_file()
                else "not_checked"
            ),
            "workflow_transaction_status": (
                read_json(state_dir / WORKFLOW_TRANSACTION_MANIFEST_JSON).get("status", "not_checked")
                if (state_dir / WORKFLOW_TRANSACTION_MANIFEST_JSON).is_file()
                else "not_checked"
            ),
            "workflow_recovery_status": (
                read_json(state_dir / WORKFLOW_RECOVERY_RESULT_JSON).get("result_status", "not_checked")
                if (state_dir / WORKFLOW_RECOVERY_RESULT_JSON).is_file()
                else "not_checked"
            ),
            "incremental_remaining_blocker_count": (
                len(read_json(state_dir / SELECTIVE_RECOMPUTE_RESULT_JSON).get("remaining_blockers", []))
                if (state_dir / SELECTIVE_RECOMPUTE_RESULT_JSON).is_file()
                else 0
            ),
            "workbench_knowledge_review_queue_present": (state_dir / WORKBENCH_KNOWLEDGE_REVIEW_QUEUE_JSON).is_file(),
            "workbench_action_log_present": (state_dir / WORKBENCH_ACTION_LOG_JSONL).is_file(),
            "workbench_action_result_present": (state_dir / WORKBENCH_ACTION_RESULT_JSON).is_file(),
            "workbench_review_queue_present": (state_dir / WORKBENCH_REVIEW_QUEUE_JSON).is_file(),
            "workbench_claim_queue_present": (state_dir / WORKBENCH_CLAIM_QUEUE_JSON).is_file(),
            "workbench_signoff_summary_present": (state_dir / WORKBENCH_SIGNOFF_SUMMARY_JSON).is_file(),
            "document_evidence_pack_present": bool(document_evidence_manifest),
            "document_evidence_status": document_evidence_manifest.get("status", "not_checked"),
            "document_open_decision_count": document_evidence_manifest.get("summary", {}).get("open_decision_count", 0),
            "document_publicity_risk_count": document_evidence_manifest.get("summary", {}).get("publicity_risk_count", 0),
            "document_claim_metric_blocking_count": document_evidence_manifest.get("summary", {}).get("claim_metric_blocking_count", 0),
            "workbench_document_evidence_queue_present": bool(document_evidence_queue),
            "document_evidence_queue_item_count": document_evidence_queue.get("summary", {}).get("item_count", 0),
            "document_evidence_queue_blocking_count": document_evidence_queue.get("summary", {}).get("blocking_count", 0),
            "document_claim_resolution_status": document_claim_resolution.get("status", "not_checked"),
            "document_unresolved_claim_metric_count": document_claim_resolution.get("summary", {}).get("unresolved_claim_metric_count", 0),
            "document_unresolved_publicity_risk_count": document_claim_resolution.get("summary", {}).get("unresolved_publicity_risk_count", 0),
            "document_signoff_status": document_signoff_summary.get("status", "not_checked"),
            "document_signoff_delivery_authorized": bool(document_signoff_summary.get("delivery_authorized")),
            **(reference_summary or {}),
        },
        "artifacts": artifacts,
        "next_actions": _next_actions(status),
    }
    if android_overlay_plan:
        summary["android_merged_overlay"] = _overlay_report(android_overlay_plan, android_overlay_output)
    return summary


def _write_run_summary(summary: dict[str, Any], run_dir: Path, inspection: dict[str, Any]) -> dict[str, Any]:
    _attach_android_coverage(summary, inspection)
    write_json(run_dir / "run-summary.json", summary)
    record_project_session(
        Path(summary["project"]["root"]),
        run_id=summary["run_id"],
        kind="localize_run",
        status=summary["status"],
        source_locale=summary["project"]["source_locale"],
        target_locale=summary["project"]["target_locale"],
        operating_mode=summary["project"].get("operating_mode"),
        reference_policy=summary["project"].get("reference_policy"),
        selected_source_files=list(summary.get("source_files", [])),
        run_directory=run_dir,
        artifacts=summary.get("artifacts", {}),
        routing=_routing_evidence(inspection, summary.get("source_files", [])),
        summary=summary.get("summary", {}),
        next_actions=summary.get("next_actions", []),
    )
    return summary


def _attach_android_coverage(summary: dict[str, Any], inspection: dict[str, Any]) -> None:
    coverage = inspection.get("android_coverage") or {}
    if not coverage:
        return
    selected = set(summary.get("source_files", []))
    android_sources = set(inspection.get("android_generation_source_files", []))
    selected_android_sources = sorted(selected & android_sources)
    if not selected_android_sources:
        return
    counts = coverage.get("app_source_string_counts", {})
    selected_app_source_strings = sum(int(counts.get(path, 0)) for path in selected_android_sources)
    run_coverage = {
        **coverage,
        "selected_source_files": selected_android_sources,
        "selected_app_source_strings": selected_app_source_strings,
    }
    summary["android_coverage"] = run_coverage
    summary.setdefault("summary", {})["android_coverage"] = {
        "coverage_mode": run_coverage.get("coverage_mode"),
        "selected_app_source_strings": selected_app_source_strings,
        "merged_dependency_strings_detected": run_coverage.get("merged_dependency_strings_detected", 0),
        "merged_dependency_strings_included": run_coverage.get("merged_dependency_strings_included", False),
        "visible_ui_coverage_warning": run_coverage.get("visible_ui_coverage_warning", False),
    }
    warnings = summary.setdefault("warnings", [])
    for warning in run_coverage.get("warnings", []):
        if warning not in warnings:
            warnings.append(warning)
    overlay = summary.get("android_merged_overlay")
    if overlay:
        merged = {
            **run_coverage,
            **overlay,
            "coverage_mode": "source-plus-merged-overlay",
            "merged_dependency_strings_included": overlay.get("merged_dependency_resources_included", 0),
            "visible_ui_coverage_warning": False,
        }
        summary["android_coverage"] = merged
        summary.setdefault("summary", {})["android_coverage"] = {
            "coverage_mode": "source-plus-merged-overlay",
            "selected_app_source_strings": selected_app_source_strings,
            "merged_dependency_strings_detected": overlay.get("merged_dependency_resources_detected", 0),
            "merged_dependency_strings_included": overlay.get("merged_dependency_resources_included", 0),
            "visible_ui_coverage_warning": False,
            "overlay_files_created": overlay.get("overlay_files_created", 0),
        }
        summary["warnings"] = [warning for warning in summary.get("warnings", []) if "source-only localization" not in warning]


def _overlay_report(overlay_plan: dict[str, Any], output: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "coverage_mode": "source-plus-merged-overlay",
        "source_category": ANDROID_MERGED_OVERLAY_CATEGORY,
        "merged_dependency_resources_detected": overlay_plan.get("merged_dependency_resources_detected", 0),
        "merged_dependency_resources_included": overlay_plan.get("merged_dependency_resources_included", 0),
        "merged_dependency_resources_excluded": overlay_plan.get("merged_dependency_resources_excluded", {}),
        "destination": overlay_plan.get("destination"),
        "overlay_files_created": 1 if output else 0,
        "overlay_outputs": [output["destination"]] if output else [],
        "visible_ui_coverage_warning": False,
        "residual_text_categories": overlay_plan.get("residual_text_categories", []),
        "build_variant": overlay_plan.get("build_variant"),
    }


def _routing_evidence(inspection: dict[str, Any], selected_source_files: list[str]) -> dict[str, Any]:
    return {
        "adapter_counts": inspection.get("adapter_counts", {}),
        "selected_source_files": selected_source_files,
        "supported_file_count": len(inspection.get("supported_files", [])),
        "android_generation_source_files": inspection.get("android_generation_source_files", []),
        "android_locale_reference_files": inspection.get("android_locale_reference_files", []),
        "android_coverage": inspection.get("android_coverage", {}),
        "unprocessed_non_text_asset_count": len(inspection.get("unprocessed_non_text_assets", [])),
        "scan_policy": inspection.get("scan_policy", {}),
        "ignored_path_count": inspection.get("ignored_path_count", 0),
        "ignored_paths_sample": inspection.get("ignored_paths", [])[:25],
        "skipped_path_count": inspection.get("skipped_path_count", 0),
        "skipped_paths_sample": inspection.get("skipped_paths", [])[:25],
        "preflight_assessment": inspection.get("preflight_assessment", {}),
    }


def _next_actions(status: str) -> list[str]:
    if status == "generation_strategy_blocked":
        return [
            "Resolve Generation Strategy Gate blockers, especially unresolved term governance conflicts.",
            "Rerun localize-run after the blocking review artifacts are updated.",
        ]
    if status == "handoff_ready":
        return [
            "Send draft_requests/*.json to an LLM workflow and write one generated JSONL file per batch into generated-batches/.",
            "Run localize-run again with --generated-dir or collect-generated/stage-generated when drafts are ready.",
        ]
    if status == "generation_failed":
        return ["Fix generated batch coverage, source integrity, locale, status, or placeholder issues before staging."]
    if status == "provider_generation_failed":
        return ["Fix provider generation and rerun without synthetic fallback output before applying delivery artifacts."]
    return [
        "Review the staged localized files and dashboard.",
        "Run plan-apply, then apply-delivery --confirm-run-id only after the project owner approves overwriting project files.",
    ]
