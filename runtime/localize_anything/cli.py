from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .acceptance import create_acceptance
from .agent import run_agent
from .android_app_test import run_android_app_test
from .artifact_state import build_artifact_state
from .android_strings_adapter import extract_segments as extract_android_strings
from .android_strings_adapter import rebuild as rebuild_android_strings
from .android_strings_adapter import stage_rebuild as stage_android_strings
from .android_strings_adapter import validate_pair as validate_android_strings
from .apply import create_apply_plan, execute_apply, render_apply_plan_markdown
from .contracts import validate_adapter_tree
from .chinese_draft import generate_chinese_draft_file
from .dashboard import build_delivery_dashboard, render_dashboard_markdown
from .delivery import package_delivery
from .delivery_decision import create_delivery_decision_report, render_delivery_decision_markdown
from .document_evidence import build_document_evidence_pack
from .document_evidence_queue import build_workbench_document_evidence_queue
from .document_decision import (
    build_document_claim_resolution,
    build_document_signoff_summary,
    read_document_decision_log,
    read_leadership_review_evidence,
    record_document_decision,
    record_leadership_review_evidence,
)
from .evaluation import build_evaluation_scorecard, read_evaluation_scorecard
from .generation import (
    collect_generated_handoff,
    create_draft_request,
    create_generation_handoff,
    create_retry_handoff,
    import_generated_handoff,
    import_generated_response,
    render_draft_prompt,
    render_generation_instructions,
    validate_generated_segments,
    write_handoff_prompts,
)
from .generation_handoff_policy import build_generation_handoff_decision
from .generation_strategy import build_generation_strategy, write_generation_strategy
from .human_review import (
    build_claim_acceptance_decision,
    create_signoff_record,
    read_human_review_evidence,
    read_signoff_record,
    record_human_review_evidence,
)
from .gettext_adapter import extract_segments as extract_po_segments
from .gettext_adapter import rebuild as rebuild_po
from .gettext_adapter import validate_pair as validate_po_pair
from .io_utils import read_json, read_jsonl, write_json, write_jsonl
from .knowledge_pack import (
    export_knowledge_pack,
    init_knowledge_pack,
    read_knowledge_pack,
    read_knowledge_quality_report,
    read_knowledge_review_queue,
    record_knowledge_review_decision,
)
from .knowledge_consumption import (
    build_knowledge_eligibility_report,
    build_working_context_packet,
    select_knowledge_packs,
)
from .knowledge_usage import (
    build_constraint_application_audit,
    build_knowledge_conflict_report,
    build_knowledge_usage_report,
)
from .knowledge_audit_enforcement import (
    build_knowledge_audit_enforcement_decision,
    build_workbench_knowledge_review_queue,
)
from .knowledge_review_confirmation import (
    build_knowledge_assurance_summary,
    build_knowledge_conflict_resolution,
    read_knowledge_audit_resolution_log,
    read_knowledge_constraint_review_evidence,
    record_knowledge_audit_resolution,
    record_knowledge_constraint_review_evidence,
)
from .knowledge_repair import (
    build_knowledge_repair_impact_report,
    build_knowledge_repair_plan,
    build_knowledge_repair_request,
)
from .knowledge_repair_result import (
    build_knowledge_repair_qa_report,
    build_knowledge_repair_reconciliation,
    read_knowledge_repair_result_intake,
    record_knowledge_repair_result,
)
from .knowledge_repair_closure import (
    build_knowledge_readiness_impact_report,
    build_knowledge_recompute_plan,
    build_knowledge_recompute_result,
    build_knowledge_repair_closure_decision,
)
from .readiness_authorization import (
    build_apply_readiness_report,
    build_delivery_readiness_report,
    build_manual_followup_gap_report,
    build_readiness_authorization_matrix,
    build_readiness_reports,
)
from .readiness_action import (
    build_workbench_readiness_action_queue,
    perform_workbench_readiness_action,
    read_workbench_readiness_action_log,
    read_workbench_readiness_action_result,
)
from .workflow import (
    WORKFLOW_MODES,
    build_workflow_dependency_graph,
    build_workflow_readiness_summary,
    build_workflow_run_plan,
    build_workflow_stage_status,
    read_workflow_execution_result,
    run_workflow,
)
from .workflow_incremental import (
    RECOMPUTE_STRATEGIES,
    RESUME_SOURCES,
    build_artifact_invalidation_report,
    build_incremental_workflow_summary,
    build_selective_recompute_plan,
    build_workflow_resume_plan,
    read_selective_recompute_result,
    resume_workflow,
    run_selective_recompute,
)
from .workflow_hardening import (
    build_workflow_recovery_plan,
    read_workflow_checkpoint_log,
    read_workflow_idempotency_report,
    read_workflow_lock_state,
    read_workflow_recovery_result,
    read_workflow_transaction_manifest,
    run_workflow_recovery,
)
from .provider_evidence import (
    append_provider_execution_ledger_entry,
    build_provider_evidence_reconciliation,
    build_provider_execution_policy,
    build_provider_handoff_request,
    read_provider_evidence_reconciliation,
    read_provider_execution_ledger,
    read_provider_execution_policy,
    read_provider_handoff_request,
    read_provider_result_intake,
    record_provider_result_intake,
)
from .inspect_summary import build_inspect_summary, validate_inspect_output_directory, write_inspect_summary
from .ios_strings_adapter import extract_segments as extract_ios_strings
from .ios_strings_adapter import rebuild as rebuild_ios_strings
from .ios_strings_adapter import stage_rebuild as stage_ios_strings
from .ios_strings_adapter import validate_pair as validate_ios_strings
from .json_adapter import extract_segments, rebuild, validate_pair
from .markup_adapter import extract_segments as extract_markup_segments
from .markup_adapter import rebuild as rebuild_markup
from .markup_adapter import validate_pair as validate_markup_pair
from .modes import OPERATING_MODES, REFERENCE_POLICIES
from .mo_compiler import compile_segments_to_mo
from .planning import create_batch_plan
from .project import initialize_project, inspect_project, load_session_index
from .provider import generate_handoff_with_http_provider
from .reflection import create_llm_review_request, import_llm_review_response, render_llm_review_prompt
from .resolution_gate import build_resolution_gate, record_user_resolution_decision
from .retrieval import build_work_packet
from .review import import_review
from .review_sheet import write_review_sheet
from .run import run_localize
from .schema_validation import validate_protocol_tree
from .segments import diff_segments
from .segment_repair import (
    apply_repair_plan,
    build_segment_regeneration_plan,
    read_repair_history,
    read_repair_request,
    read_repair_result,
    read_segment_regeneration_plan,
)
from .segment_staleness import build_reuse_decision, read_reuse_decision, read_stale_segments
from .staging import stage_generated
from .structured_adapter import extract_segments as extract_structured_segments
from .structured_adapter import rebuild as rebuild_structured
from .structured_adapter import validate_pair as validate_structured_pair
from .subtitle_adapter import extract_segments as extract_subtitle_segments
from .subtitle_adapter import rebuild as rebuild_subtitles
from .subtitle_adapter import validate_pair as validate_subtitle_pair
from .tabular_adapter import extract_segments as extract_tabular_segments
from .tabular_adapter import rebuild as rebuild_tabular
from .tabular_adapter import validate_pair as validate_tabular_pair
from .termbase_preflight import record_term_review_decision, run_termbase_preflight
from .word_adapter import extract_segments as extract_word_segments
from .word_adapter import rebuild as rebuild_word
from .word_adapter import validate_pair as validate_word_pair
from .workbench_action import perform_workbench_action, read_workbench_action_log
from .workbench_console import render_workbench_console_html
from .workbench_queue import (
    build_workbench_claim_queue,
    build_workbench_review_queue,
    build_workbench_signoff_summary,
)
from .wesnoth_adapter import extract_segments as extract_wesnoth_segments
from .wesnoth_adapter import enrich_segments as enrich_wesnoth_segments
from .wesnoth_adapter import inventory as inventory_wesnoth
from .wesnoth_adapter import validate_source as validate_wesnoth_source
from .xcstrings_adapter import extract_segments as extract_xcstrings
from .xcstrings_adapter import rebuild as rebuild_xcstrings
from .xcstrings_adapter import stage_rebuild as stage_xcstrings
from .xcstrings_adapter import validate_pair as validate_xcstrings
from .xliff_adapter import extract_segments as extract_xliff_segments
from .xliff_adapter import rebuild as rebuild_xliff
from .xliff_adapter import validate_pair as validate_xliff_pair


from .deepseek_provider import translate_batch_deepseek


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="localize-anything", description="Reference runtime for the Localize Anything protocol")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Read-only discovery of files supported by alpha adapters",
        description="Read-only project inspection. Does not generate, stage, or apply translations.",
    )
    inspect_parser.add_argument("project", type=Path, nargs="?")
    inspect_parser.add_argument("--project", dest="project_option", type=Path, help="Project path to inspect")
    inspect_parser.add_argument("--output", type=Path, help="Write JSON output to this file instead of stdout")
    inspect_parser.add_argument("--output-dir", type=Path, help="Write read-only inspect-summary.json and inspect-summary.md")

    sessions_parser = subparsers.add_parser("sessions", help="List resumable Localize Anything sessions for a project")
    sessions_parser.add_argument("project", type=Path)
    sessions_parser.add_argument("--output", type=Path)

    preflight_parser = subparsers.add_parser("preflight", help="Initialize deterministic project state and inventory")
    preflight_parser.add_argument("project", type=Path)
    preflight_parser.add_argument("--source-locale", required=True)
    preflight_parser.add_argument("--source-file", action="append", required=True, dest="source_files")
    preflight_parser.add_argument("--target-locale", action="append", required=True, dest="target_locales")
    preflight_parser.add_argument("--workflow-depth", choices=["ask", "fast", "standard", "high_assurance"], default="ask")
    preflight_parser.add_argument("--preflight-mode", choices=["auto", "full", "layered", "light", "skip_deep"], default="auto")
    preflight_parser.add_argument("--privacy-mode", choices=["standard", "minimal_disclosure", "local_only"], default="standard")
    preflight_parser.add_argument("--data-classification", choices=["public", "internal", "confidential", "restricted"], default="internal")
    preflight_parser.add_argument("--operating-mode", choices=OPERATING_MODES)
    preflight_parser.add_argument("--reference-policy", choices=REFERENCE_POLICIES)
    preflight_parser.add_argument("--output", type=Path)

    extract_parser = subparsers.add_parser("extract-json", help="Extract string leaves from a JSON locale file")
    extract_parser.add_argument("source", type=Path)
    extract_parser.add_argument("--source-locale", required=True)
    extract_parser.add_argument("--source-path")
    extract_parser.add_argument("--output", type=Path)

    rebuild_parser = subparsers.add_parser("rebuild-json", help="Rebuild a JSON locale file from translated segment JSONL")
    rebuild_parser.add_argument("source", type=Path)
    rebuild_parser.add_argument("translations", type=Path)
    rebuild_parser.add_argument("--output", type=Path, required=True)

    validate_parser = subparsers.add_parser("validate-json", help="Validate JSON key and placeholder parity")
    validate_parser.add_argument("source", type=Path)
    validate_parser.add_argument("target", type=Path)
    validate_parser.add_argument("--output", type=Path)

    extract_po_parser = subparsers.add_parser("extract-po", help="Extract gettext PO/POT entries")
    extract_po_parser.add_argument("source", type=Path)
    extract_po_parser.add_argument("--source-locale", required=True)
    extract_po_parser.add_argument("--source-path")
    extract_po_parser.add_argument("--output", type=Path)

    rebuild_po_parser = subparsers.add_parser("rebuild-po", help="Rebuild a gettext catalog from translated segments")
    rebuild_po_parser.add_argument("source", type=Path)
    rebuild_po_parser.add_argument("translations", type=Path)
    rebuild_po_parser.add_argument("--target-locale")
    rebuild_po_parser.add_argument("--output", type=Path, required=True)

    validate_po_parser = subparsers.add_parser("validate-po", help="Validate gettext entry, plural, and placeholder parity")
    validate_po_parser.add_argument("source", type=Path)
    validate_po_parser.add_argument("target", type=Path)
    validate_po_parser.add_argument("--output", type=Path)

    extract_structured_parser = subparsers.add_parser("extract-structured", help="Extract YAML or TOML string values")
    extract_structured_parser.add_argument("source", type=Path)
    extract_structured_parser.add_argument("--source-locale", required=True)
    extract_structured_parser.add_argument("--source-path")
    extract_structured_parser.add_argument("--format", choices=["yaml", "toml"])
    extract_structured_parser.add_argument("--output", type=Path)

    rebuild_structured_parser = subparsers.add_parser("rebuild-structured", help="Rebuild YAML or TOML from translated segments")
    rebuild_structured_parser.add_argument("source", type=Path)
    rebuild_structured_parser.add_argument("translations", type=Path)
    rebuild_structured_parser.add_argument("--format", choices=["yaml", "toml"])
    rebuild_structured_parser.add_argument("--output", type=Path, required=True)

    validate_structured_parser = subparsers.add_parser("validate-structured", help="Validate YAML or TOML keys and placeholders")
    validate_structured_parser.add_argument("source", type=Path)
    validate_structured_parser.add_argument("target", type=Path)
    validate_structured_parser.add_argument("--format", choices=["yaml", "toml"])
    validate_structured_parser.add_argument("--output", type=Path)

    extract_tabular_parser = subparsers.add_parser("extract-tabular", help="Extract CSV, TSV, or XLSX string cells")
    extract_tabular_parser.add_argument("source", type=Path)
    extract_tabular_parser.add_argument("--source-locale", required=True)
    extract_tabular_parser.add_argument("--source-path")
    extract_tabular_parser.add_argument("--output", type=Path)

    rebuild_tabular_parser = subparsers.add_parser("rebuild-tabular", help="Rebuild CSV, TSV, or XLSX from translated segments")
    rebuild_tabular_parser.add_argument("source", type=Path)
    rebuild_tabular_parser.add_argument("translations", type=Path)
    rebuild_tabular_parser.add_argument("--output", type=Path, required=True)

    validate_tabular_parser = subparsers.add_parser("validate-tabular", help="Validate tabular cell and placeholder parity")
    validate_tabular_parser.add_argument("source", type=Path)
    validate_tabular_parser.add_argument("target", type=Path)
    validate_tabular_parser.add_argument("--output", type=Path)

    extract_word_parser = subparsers.add_parser("extract-word", help="Extract visible Word OpenXML text")
    extract_word_parser.add_argument("source", type=Path)
    extract_word_parser.add_argument("--source-locale", required=True)
    extract_word_parser.add_argument("--source-path")
    extract_word_parser.add_argument("--output", type=Path)

    rebuild_word_parser = subparsers.add_parser("rebuild-word", help="Rebuild Word OpenXML from translated segments")
    rebuild_word_parser.add_argument("source", type=Path)
    rebuild_word_parser.add_argument("translations", type=Path)
    rebuild_word_parser.add_argument("--output", type=Path, required=True)

    validate_word_parser = subparsers.add_parser("validate-word", help="Validate Word OpenXML structure, styles, and placeholders")
    validate_word_parser.add_argument("source", type=Path)
    validate_word_parser.add_argument("target", type=Path)
    validate_word_parser.add_argument("--output", type=Path)

    extract_markup_parser = subparsers.add_parser("extract-markup", help="Extract visible Markdown or HTML text")
    extract_markup_parser.add_argument("source", type=Path)
    extract_markup_parser.add_argument("--source-locale", required=True)
    extract_markup_parser.add_argument("--source-path")
    extract_markup_parser.add_argument("--output", type=Path)

    rebuild_markup_parser = subparsers.add_parser("rebuild-markup", help="Rebuild Markdown or HTML from translated segments")
    rebuild_markup_parser.add_argument("source", type=Path)
    rebuild_markup_parser.add_argument("translations", type=Path)
    rebuild_markup_parser.add_argument("--output", type=Path, required=True)

    validate_markup_parser = subparsers.add_parser("validate-markup", help="Validate Markdown or HTML structure and placeholders")
    validate_markup_parser.add_argument("source", type=Path)
    validate_markup_parser.add_argument("target", type=Path)
    validate_markup_parser.add_argument("--output", type=Path)

    extract_subtitle_parser = subparsers.add_parser("extract-subtitles", help="Extract SRT or WebVTT cues")
    extract_subtitle_parser.add_argument("source", type=Path)
    extract_subtitle_parser.add_argument("--source-locale", required=True)
    extract_subtitle_parser.add_argument("--source-path")
    extract_subtitle_parser.add_argument("--output", type=Path)

    rebuild_subtitle_parser = subparsers.add_parser("rebuild-subtitles", help="Rebuild SRT or WebVTT from translated cues")
    rebuild_subtitle_parser.add_argument("source", type=Path)
    rebuild_subtitle_parser.add_argument("translations", type=Path)
    rebuild_subtitle_parser.add_argument("--output", type=Path, required=True)

    validate_subtitle_parser = subparsers.add_parser("validate-subtitles", help="Validate subtitle timing and cue structure")
    validate_subtitle_parser.add_argument("source", type=Path)
    validate_subtitle_parser.add_argument("target", type=Path)
    validate_subtitle_parser.add_argument("--output", type=Path)

    extract_xliff_parser = subparsers.add_parser("extract-xliff", help="Extract XLIFF 1.2 or 2.x units")
    extract_xliff_parser.add_argument("source", type=Path)
    extract_xliff_parser.add_argument("--source-locale", required=True)
    extract_xliff_parser.add_argument("--source-path")
    extract_xliff_parser.add_argument("--output", type=Path)

    rebuild_xliff_parser = subparsers.add_parser("rebuild-xliff", help="Rebuild XLIFF from translated units")
    rebuild_xliff_parser.add_argument("source", type=Path)
    rebuild_xliff_parser.add_argument("translations", type=Path)
    rebuild_xliff_parser.add_argument("--target-locale")
    rebuild_xliff_parser.add_argument("--output", type=Path, required=True)

    validate_xliff_parser = subparsers.add_parser("validate-xliff", help="Validate XLIFF units, source integrity, and inline tags")
    validate_xliff_parser.add_argument("source", type=Path)
    validate_xliff_parser.add_argument("target", type=Path)
    validate_xliff_parser.add_argument("--output", type=Path)

    extract_android_parser = subparsers.add_parser("extract-android-strings", help="Extract Android res/values string resources")
    extract_android_parser.add_argument("source", type=Path)
    extract_android_parser.add_argument("--source-locale", required=True)
    extract_android_parser.add_argument("--source-path")
    extract_android_parser.add_argument("--output", type=Path)

    rebuild_android_parser = subparsers.add_parser("rebuild-android-strings", help="Rebuild an Android strings.xml language resource")
    rebuild_android_parser.add_argument("source", type=Path)
    rebuild_android_parser.add_argument("translations", type=Path)
    rebuild_android_parser.add_argument("--output", type=Path, required=True)

    stage_android_parser = subparsers.add_parser("stage-android-strings", help="Write Android strings.xml to the target locale staging path")
    stage_android_parser.add_argument("source", type=Path)
    stage_android_parser.add_argument("translations", type=Path)
    stage_android_parser.add_argument("--target-locale", required=True)
    stage_android_parser.add_argument("--staging-dir", type=Path, required=True)
    stage_android_parser.add_argument("--project-root", type=Path, required=True)
    stage_android_parser.add_argument("--output", type=Path)

    validate_android_parser = subparsers.add_parser("validate-android-strings", help="Validate Android strings.xml coverage and placeholders")
    validate_android_parser.add_argument("source", type=Path)
    validate_android_parser.add_argument("target", type=Path)
    validate_android_parser.add_argument("--output", type=Path)

    extract_ios_parser = subparsers.add_parser("extract-ios-strings", help="Extract iOS .strings or .stringsdict resources")
    extract_ios_parser.add_argument("source", type=Path)
    extract_ios_parser.add_argument("--source-locale", required=True)
    extract_ios_parser.add_argument("--source-path")
    extract_ios_parser.add_argument("--output", type=Path)

    rebuild_ios_parser = subparsers.add_parser("rebuild-ios-strings", help="Rebuild an iOS .strings or .stringsdict resource")
    rebuild_ios_parser.add_argument("source", type=Path)
    rebuild_ios_parser.add_argument("translations", type=Path)
    rebuild_ios_parser.add_argument("--output", type=Path, required=True)

    stage_ios_parser = subparsers.add_parser("stage-ios-strings", help="Write an iOS resource to the target .lproj staging path")
    stage_ios_parser.add_argument("source", type=Path)
    stage_ios_parser.add_argument("translations", type=Path)
    stage_ios_parser.add_argument("--target-locale", required=True)
    stage_ios_parser.add_argument("--staging-dir", type=Path, required=True)
    stage_ios_parser.add_argument("--project-root", type=Path, required=True)
    stage_ios_parser.add_argument("--output", type=Path)

    validate_ios_parser = subparsers.add_parser("validate-ios-strings", help="Validate iOS string resource coverage and placeholders")
    validate_ios_parser.add_argument("source", type=Path)
    validate_ios_parser.add_argument("target", type=Path)
    validate_ios_parser.add_argument("--output", type=Path)

    extract_xcstrings_parser = subparsers.add_parser("extract-xcstrings", help="Extract Xcode String Catalog resources")
    extract_xcstrings_parser.add_argument("source", type=Path)
    extract_xcstrings_parser.add_argument("--source-locale", required=True)
    extract_xcstrings_parser.add_argument("--source-path")
    extract_xcstrings_parser.add_argument("--output", type=Path)

    rebuild_xcstrings_parser = subparsers.add_parser("rebuild-xcstrings", help="Rebuild an Xcode String Catalog with generated target localizations")
    rebuild_xcstrings_parser.add_argument("source", type=Path)
    rebuild_xcstrings_parser.add_argument("translations", type=Path)
    rebuild_xcstrings_parser.add_argument("--target-locale")
    rebuild_xcstrings_parser.add_argument("--output", type=Path, required=True)

    stage_xcstrings_parser = subparsers.add_parser("stage-xcstrings", help="Write an Xcode String Catalog to staging")
    stage_xcstrings_parser.add_argument("source", type=Path)
    stage_xcstrings_parser.add_argument("translations", type=Path)
    stage_xcstrings_parser.add_argument("--target-locale", required=True)
    stage_xcstrings_parser.add_argument("--staging-dir", type=Path, required=True)
    stage_xcstrings_parser.add_argument("--project-root", type=Path, required=True)
    stage_xcstrings_parser.add_argument("--output", type=Path)

    validate_xcstrings_parser = subparsers.add_parser("validate-xcstrings", help="Validate String Catalog target locale coverage and placeholders")
    validate_xcstrings_parser.add_argument("source", type=Path)
    validate_xcstrings_parser.add_argument("target", type=Path)
    validate_xcstrings_parser.add_argument("--target-locale", required=True)
    validate_xcstrings_parser.add_argument("--output", type=Path)

    wesnoth_parser = subparsers.add_parser("wesnoth-inventory", help="Inventory a Wesnoth campaign or checkout")
    wesnoth_parser.add_argument("project", type=Path)
    wesnoth_parser.add_argument("--output", type=Path)

    extract_wesnoth_parser = subparsers.add_parser("extract-wesnoth", help="Extract translatable WML strings")
    extract_wesnoth_parser.add_argument("project", type=Path)
    extract_wesnoth_parser.add_argument("--source-locale", default="en-US")
    extract_wesnoth_parser.add_argument("--output", type=Path)

    enrich_wesnoth_parser = subparsers.add_parser("enrich-wesnoth", help="Add WML scenario context to PO segments")
    enrich_wesnoth_parser.add_argument("segments", type=Path)
    enrich_wesnoth_parser.add_argument("project", type=Path)
    enrich_wesnoth_parser.add_argument("--output", type=Path)

    validate_wesnoth_parser = subparsers.add_parser("validate-wesnoth", help="Validate WML occurrence context coverage")
    validate_wesnoth_parser.add_argument("segments", type=Path)
    validate_wesnoth_parser.add_argument("project", type=Path)
    validate_wesnoth_parser.add_argument("--output", type=Path)

    contracts_parser = subparsers.add_parser("validate-contracts", help="Validate adapter manifests without external dependencies")
    contracts_parser.add_argument("root", type=Path, nargs="?", default=Path("adapters"))
    contracts_parser.add_argument("--output", type=Path)

    protocol_parser = subparsers.add_parser("validate-protocol", help="Validate protocol schemas and canonical examples")
    protocol_parser.add_argument("root", type=Path, nargs="?", default=Path("protocol"))
    protocol_parser.add_argument("--output", type=Path)

    plan_parser = subparsers.add_parser("plan", help="Create a content-unit batch plan from segment JSONL")
    plan_parser.add_argument("segments", type=Path)
    plan_parser.add_argument("--source-locale", required=True)
    plan_parser.add_argument("--target-locale", action="append", required=True, dest="target_locales")
    plan_parser.add_argument("--max-segments", type=int, default=80)
    plan_parser.add_argument("--operating-mode", choices=OPERATING_MODES)
    plan_parser.add_argument("--reference-policy", choices=REFERENCE_POLICIES)
    plan_parser.add_argument("--output", type=Path)

    retrieve_parser = subparsers.add_parser("retrieve", help="Build an ephemeral working context packet")
    retrieve_parser.add_argument("plan", type=Path)
    retrieve_parser.add_argument("segments", type=Path)
    retrieve_parser.add_argument("state_dir", type=Path)
    retrieve_parser.add_argument("--batch-id", required=True)
    retrieve_parser.add_argument("--target-locale", required=True)
    retrieve_parser.add_argument("--limit-tokens", type=int, default=4000)
    retrieve_parser.add_argument("--output", type=Path)

    termbase_preflight_parser = subparsers.add_parser(
        "termbase-preflight",
        help="Create UI-ready term candidate, report, and review queue artifacts before generation",
    )
    termbase_preflight_parser.add_argument("segments", type=Path)
    termbase_preflight_parser.add_argument("state_dir", type=Path)
    termbase_preflight_parser.add_argument("--source-locale", required=True)
    termbase_preflight_parser.add_argument("--target-locale", required=True)
    termbase_preflight_parser.add_argument("--run-id")
    termbase_preflight_parser.add_argument("--output", type=Path)

    term_review_decision_parser = subparsers.add_parser(
        "term-review-decision",
        help="Record a term review queue decision and sync applicable term governance assets",
    )
    term_review_decision_parser.add_argument("state_dir", type=Path)
    term_review_decision_parser.add_argument("--candidate-id")
    term_review_decision_parser.add_argument("--source-term")
    term_review_decision_parser.add_argument("--target-term", default="")
    term_review_decision_parser.add_argument("--term-type", default="other")
    term_review_decision_parser.add_argument(
        "--status",
        required=True,
        choices=["approved", "locked", "rejected", "forbidden", "deferred", "scope_specific"],
    )
    term_review_decision_parser.add_argument("--target-locale")
    term_review_decision_parser.add_argument("--scope", default="")
    term_review_decision_parser.add_argument("--notes", default="")
    term_review_decision_parser.add_argument("--forbidden-target", action="append", default=[], dest="forbidden_targets")
    term_review_decision_parser.add_argument("--decided-by", default="cli-user")
    term_review_decision_parser.add_argument("--output", type=Path)

    generation_strategy_parser = subparsers.add_parser(
        "generation-strategy",
        help="Create a deterministic Generation Strategy Gate artifact from batch and review state",
    )
    generation_strategy_parser.add_argument("plan", type=Path)
    generation_strategy_parser.add_argument("state_dir", type=Path)
    generation_strategy_parser.add_argument("--source-locale")
    generation_strategy_parser.add_argument("--target-locale")
    generation_strategy_parser.add_argument("--run-id")
    generation_strategy_parser.add_argument("--output", type=Path)

    blocking_questions_parser = subparsers.add_parser(
        "blocking-questions",
        help="Create Resolution Gate blocking-question artifacts from generation strategy state",
    )
    blocking_questions_parser.add_argument("state_dir", type=Path)
    blocking_questions_parser.add_argument("--coverage-warning", action="store_true")
    blocking_questions_parser.add_argument("--provider-policy", choices=["safe", "unsafe", "fallback_requested"], default="safe")
    blocking_questions_parser.add_argument("--operating-mode")
    blocking_questions_parser.add_argument("--scenario")
    blocking_questions_parser.add_argument("--run-id")
    blocking_questions_parser.add_argument("--output", type=Path)

    resolve_question_parser = subparsers.add_parser(
        "resolve-question",
        help="Record a user Resolution Gate decision",
    )
    resolve_question_parser.add_argument("state_dir", type=Path)
    resolve_question_parser.add_argument("--question-id", required=True)
    resolve_question_parser.add_argument("--option-id", required=True)
    resolve_question_parser.add_argument("--target-term")
    resolve_question_parser.add_argument("--target-locale")
    resolve_question_parser.add_argument("--term-status", choices=["approved", "locked"], default="approved")
    resolve_question_parser.add_argument("--notes", default="")
    resolve_question_parser.add_argument("--decided-by", default="cli-user")
    resolve_question_parser.add_argument("--output", type=Path)

    handoff_status_parser = subparsers.add_parser(
        "generation-handoff-status",
        help="Create or refresh the deterministic Generation Handoff Enforcement decision artifact",
    )
    handoff_status_parser.add_argument("state_dir", type=Path)
    handoff_status_parser.add_argument(
        "--requested-mode",
        choices=["full_quality", "draft_only", "review_required", "allowed_with_warnings", "source_only_with_partial_coverage_warning", "synthetic_test"],
        default="full_quality",
    )
    handoff_status_parser.add_argument(
        "--provider-mode",
        choices=["host_agent", "real_provider", "synthetic_test"],
        default="host_agent",
    )
    handoff_status_parser.add_argument("--provider-policy", choices=["missing", "safe", "unsafe", "fallback_requested"], default="missing")
    handoff_status_parser.add_argument("--coverage-warning", action="store_true")
    handoff_status_parser.add_argument("--run-id")
    handoff_status_parser.add_argument("--output", type=Path)

    artifact_state_parser = subparsers.add_parser(
        "artifact-state",
        help="Create or refresh artifact-state.json and report stale upstream evidence",
    )
    artifact_state_parser.add_argument("state_dir", type=Path)
    artifact_state_parser.add_argument("--run-dir", type=Path)
    artifact_state_parser.add_argument("--delivery-dir", type=Path)
    artifact_state_parser.add_argument("--run-id")
    artifact_state_parser.add_argument("--output", type=Path)

    reuse_decision_parser = subparsers.add_parser("reuse-decision", help="Create stale-segments.jsonl and reuse-decision.json")
    reuse_decision_parser.add_argument("state_dir", type=Path)
    reuse_decision_parser.add_argument("segments", type=Path)
    reuse_decision_parser.add_argument("--previous-segments", type=Path)
    reuse_decision_parser.add_argument("--generated", type=Path)
    reuse_decision_parser.add_argument("--review-result", type=Path)
    reuse_decision_parser.add_argument("--provider-policy-json")
    reuse_decision_parser.add_argument("--review-policy-json")
    reuse_decision_parser.add_argument("--run-id")
    reuse_decision_parser.add_argument("--output", type=Path)

    stale_segments_parser = subparsers.add_parser("stale-segments", help="Read stale-segments.jsonl as deterministic JSON")
    stale_segments_parser.add_argument("state_dir", type=Path)
    stale_segments_parser.add_argument("--output", type=Path)

    segment_regeneration_parser = subparsers.add_parser(
        "segment-regeneration-plan",
        help="Create segment-regeneration-plan.json and repair artifacts from reuse decisions",
    )
    segment_regeneration_parser.add_argument("state_dir", type=Path)
    segment_regeneration_parser.add_argument("--run-id")
    segment_regeneration_parser.add_argument("--output", type=Path)

    repair_request_parser = subparsers.add_parser("repair-request", help="Read repair-request.json as deterministic JSON")
    repair_request_parser.add_argument("state_dir", type=Path)
    repair_request_parser.add_argument("--output", type=Path)

    apply_repair_parser = subparsers.add_parser("apply-repair-plan", help="Apply deterministic provider-free repair patches")
    apply_repair_parser.add_argument("state_dir", type=Path)
    apply_repair_parser.add_argument("--generated-segments", type=Path)
    apply_repair_parser.add_argument("--run-id")
    apply_repair_parser.add_argument("--output", type=Path)

    repair_result_parser = subparsers.add_parser("repair-result", help="Read repair-result.json as deterministic JSON")
    repair_result_parser.add_argument("state_dir", type=Path)
    repair_result_parser.add_argument("--output", type=Path)

    repair_history_parser = subparsers.add_parser("repair-history", help="Read repair-history.jsonl as deterministic JSON")
    repair_history_parser.add_argument("state_dir", type=Path)
    repair_history_parser.add_argument("--output", type=Path)

    knowledge_repair_plan_parser = subparsers.add_parser(
        "knowledge-repair-plan", help="Create deterministic knowledge-repair-plan.json and handoff artifacts"
    )
    knowledge_repair_plan_parser.add_argument("state_dir", type=Path)
    knowledge_repair_plan_parser.add_argument("--run-id")
    knowledge_repair_plan_parser.add_argument("--output", type=Path)

    knowledge_repair_request_parser = subparsers.add_parser(
        "knowledge-repair-request", help="Create deterministic knowledge-repair-request.json"
    )
    knowledge_repair_request_parser.add_argument("state_dir", type=Path)
    knowledge_repair_request_parser.add_argument("--run-id")
    knowledge_repair_request_parser.add_argument("--output", type=Path)

    knowledge_repair_impact_parser = subparsers.add_parser(
        "knowledge-repair-impact-report", help="Create deterministic knowledge-repair-impact-report.json"
    )
    knowledge_repair_impact_parser.add_argument("state_dir", type=Path)
    knowledge_repair_impact_parser.add_argument("--run-id")
    knowledge_repair_impact_parser.add_argument("--output", type=Path)

    record_knowledge_repair_result_parser = subparsers.add_parser(
        "record-knowledge-repair-result", help="Append a repair result intake record and refresh deterministic QA/reconciliation"
    )
    record_knowledge_repair_result_parser.add_argument("state_dir", type=Path)
    record_knowledge_repair_result_parser.add_argument("--input", type=Path, required=True)
    record_knowledge_repair_result_parser.add_argument("--run-id")
    record_knowledge_repair_result_parser.add_argument("--output", type=Path)

    knowledge_repair_intake_parser = subparsers.add_parser(
        "knowledge-repair-result-intake", help="Read knowledge-repair-result-intake.jsonl"
    )
    knowledge_repair_intake_parser.add_argument("state_dir", type=Path)
    knowledge_repair_intake_parser.add_argument("--output", type=Path)

    knowledge_repair_qa_parser = subparsers.add_parser(
        "knowledge-repair-qa-report", help="Create deterministic knowledge-repair-qa-report.json"
    )
    knowledge_repair_qa_parser.add_argument("state_dir", type=Path)
    knowledge_repair_qa_parser.add_argument("--output", type=Path)

    knowledge_repair_reconciliation_parser = subparsers.add_parser(
        "knowledge-repair-reconciliation", help="Create deterministic knowledge-repair-reconciliation.json"
    )
    knowledge_repair_reconciliation_parser.add_argument("state_dir", type=Path)
    knowledge_repair_reconciliation_parser.add_argument("--output", type=Path)

    knowledge_recompute_plan_parser = subparsers.add_parser(
        "knowledge-recompute-plan", help="Create deterministic knowledge-recompute-plan.json"
    )
    knowledge_recompute_plan_parser.add_argument("state_dir", type=Path)
    knowledge_recompute_plan_parser.add_argument("--output", type=Path)

    knowledge_recompute_result_parser = subparsers.add_parser(
        "knowledge-recompute-result", help="Create deterministic knowledge-recompute-result.json"
    )
    knowledge_recompute_result_parser.add_argument("state_dir", type=Path)
    knowledge_recompute_result_parser.add_argument("--output", type=Path)

    knowledge_repair_closure_parser = subparsers.add_parser(
        "knowledge-repair-closure-decision", help="Create deterministic knowledge-repair-closure-decision.json"
    )
    knowledge_repair_closure_parser.add_argument("state_dir", type=Path)
    knowledge_repair_closure_parser.add_argument("--output", type=Path)

    knowledge_readiness_impact_parser = subparsers.add_parser(
        "knowledge-readiness-impact-report", help="Create deterministic knowledge-readiness-impact-report.json"
    )
    knowledge_readiness_impact_parser.add_argument("state_dir", type=Path)
    knowledge_readiness_impact_parser.add_argument("--output", type=Path)

    knowledge_repair_recompute_parser = subparsers.add_parser(
        "knowledge-repair-recompute", help="Run provider-free deterministic knowledge repair recompute orchestration"
    )
    knowledge_repair_recompute_parser.add_argument("state_dir", type=Path)
    knowledge_repair_recompute_parser.add_argument("--output", type=Path)

    readiness_matrix_parser = subparsers.add_parser(
        "readiness-authorization-matrix", help="Create readiness-authorization-matrix.json from current evidence"
    )
    readiness_matrix_parser.add_argument("state_dir", type=Path)
    readiness_matrix_parser.add_argument("--delivery-dir", type=Path)
    readiness_matrix_parser.add_argument("--run-id")
    readiness_matrix_parser.add_argument("--output", type=Path)

    manual_followup_parser = subparsers.add_parser(
        "manual-followup-gap-report", help="Create manual-followup-gap-report.json from unresolved follow-up evidence"
    )
    manual_followup_parser.add_argument("state_dir", type=Path)
    manual_followup_parser.add_argument("--delivery-dir", type=Path)
    manual_followup_parser.add_argument("--run-id")
    manual_followup_parser.add_argument("--output", type=Path)

    apply_readiness_parser = subparsers.add_parser(
        "apply-readiness-report", help="Create apply-readiness-report.json without mutating target files"
    )
    apply_readiness_parser.add_argument("state_dir", type=Path)
    apply_readiness_parser.add_argument("--delivery-dir", type=Path)
    apply_readiness_parser.add_argument("--run-id")
    apply_readiness_parser.add_argument("--output", type=Path)

    delivery_readiness_parser = subparsers.add_parser(
        "delivery-readiness-report", help="Create delivery-readiness-report.json from current evidence"
    )
    delivery_readiness_parser.add_argument("state_dir", type=Path)
    delivery_readiness_parser.add_argument("--delivery-dir", type=Path)
    delivery_readiness_parser.add_argument("--run-id")
    delivery_readiness_parser.add_argument("--output", type=Path)

    readiness_check_parser = subparsers.add_parser(
        "readiness-check", help="Refresh readiness matrix, manual gaps, apply report, and delivery report"
    )
    readiness_check_parser.add_argument("state_dir", type=Path)
    readiness_check_parser.add_argument("--delivery-dir", type=Path)
    readiness_check_parser.add_argument("--run-id")
    readiness_check_parser.add_argument("--output", type=Path)

    evaluation_parser = subparsers.add_parser("evaluation-scorecard", help="Create evaluation-scorecard.json and evidence-level-report.md")
    evaluation_parser.add_argument("state_dir", type=Path)
    evaluation_parser.add_argument("--run-dir", type=Path)
    evaluation_parser.add_argument("--delivery-dir", type=Path)
    evaluation_parser.add_argument("--run-id")
    evaluation_parser.add_argument("--output", type=Path)

    provider_policy_parser = subparsers.add_parser("provider-execution-policy", help="Create or read provider-execution-policy.json without calling providers")
    provider_policy_parser.add_argument("state_dir", type=Path)
    provider_policy_parser.add_argument("--input", type=Path)
    provider_policy_parser.add_argument("--run-id")
    provider_policy_parser.add_argument("--output", type=Path)

    provider_handoff_parser = subparsers.add_parser("provider-handoff-request", help="Create or read provider-handoff-request.json without calling providers")
    provider_handoff_parser.add_argument("state_dir", type=Path)
    provider_handoff_parser.add_argument("--input", type=Path)
    provider_handoff_parser.add_argument("--run-id")
    provider_handoff_parser.add_argument("--output", type=Path)

    provider_ledger_parser = subparsers.add_parser("provider-execution-ledger", help="Read or append provider-execution-ledger.jsonl without calling providers")
    provider_ledger_parser.add_argument("state_dir", type=Path)
    provider_ledger_parser.add_argument("--input", type=Path)
    provider_ledger_parser.add_argument("--run-id")
    provider_ledger_parser.add_argument("--output", type=Path)

    provider_result_parser = subparsers.add_parser("provider-result-intake", help="Read or append provider-result-intake.jsonl as evidence only")
    provider_result_parser.add_argument("state_dir", type=Path)
    provider_result_parser.add_argument("--input", type=Path)
    provider_result_parser.add_argument("--run-id")
    provider_result_parser.add_argument("--output", type=Path)

    provider_reconciliation_parser = subparsers.add_parser("provider-evidence-reconciliation", help="Create or read provider-evidence-reconciliation.json")
    provider_reconciliation_parser.add_argument("state_dir", type=Path)
    provider_reconciliation_parser.add_argument("--run-id")
    provider_reconciliation_parser.add_argument("--output", type=Path)

    record_human_review_parser = subparsers.add_parser("record-human-review", help="Append structured human review evidence")
    record_human_review_parser.add_argument("state_dir", type=Path)
    record_human_review_parser.add_argument("--input", type=Path, required=True)
    record_human_review_parser.add_argument("--run-id")
    record_human_review_parser.add_argument("--output", type=Path)

    human_review_parser = subparsers.add_parser("human-review-evidence", help="Read human-review-evidence.jsonl as deterministic JSON")
    human_review_parser.add_argument("state_dir", type=Path)
    human_review_parser.add_argument("--output", type=Path)

    claim_acceptance_parser = subparsers.add_parser("claim-acceptance", help="Create claim-acceptance-decision.json from current scorecard evidence")
    claim_acceptance_parser.add_argument("state_dir", type=Path)
    claim_acceptance_parser.add_argument("--claim", action="append", default=[], dest="claims")
    claim_acceptance_parser.add_argument("--accepted-risk-json")
    claim_acceptance_parser.add_argument("--run-id")
    claim_acceptance_parser.add_argument("--output", type=Path)

    signoff_record_parser = subparsers.add_parser("signoff-record", help="Create or read signoff-record.json")
    signoff_record_parser.add_argument("state_dir", type=Path)
    signoff_record_parser.add_argument("--input", type=Path)
    signoff_record_parser.add_argument("--run-id")
    signoff_record_parser.add_argument("--output", type=Path)

    workbench_review_queue_parser = subparsers.add_parser("workbench-review-queue", help="Create workbench-review-queue.json from artifact-backed evidence")
    workbench_review_queue_parser.add_argument("state_dir", type=Path)
    workbench_review_queue_parser.add_argument("--output", type=Path)

    workbench_claim_queue_parser = subparsers.add_parser("workbench-claim-queue", help="Create workbench-claim-queue.json from scorecard and claim evidence")
    workbench_claim_queue_parser.add_argument("state_dir", type=Path)
    workbench_claim_queue_parser.add_argument("--output", type=Path)

    workbench_signoff_summary_parser = subparsers.add_parser("workbench-signoff-summary", help="Create workbench-signoff-summary.json from signoff evidence")
    workbench_signoff_summary_parser.add_argument("state_dir", type=Path)
    workbench_signoff_summary_parser.add_argument("--output", type=Path)

    workbench_action_parser = subparsers.add_parser("workbench-action", help="Execute one artifact-backed Workbench action from JSON")
    workbench_action_parser.add_argument("state_dir", type=Path)
    workbench_action_parser.add_argument("--input", type=Path, required=True)
    workbench_action_parser.add_argument("--run-id")
    workbench_action_parser.add_argument("--output", type=Path)

    workbench_action_log_parser = subparsers.add_parser("workbench-action-log", help="Read workbench-action-log.jsonl")
    workbench_action_log_parser.add_argument("state_dir", type=Path)
    workbench_action_log_parser.add_argument("--output", type=Path)

    workbench_readiness_action_queue_parser = subparsers.add_parser(
        "workbench-readiness-action-queue",
        help="Create workbench-readiness-action-queue.json from readiness gaps",
    )
    workbench_readiness_action_queue_parser.add_argument("state_dir", type=Path)
    workbench_readiness_action_queue_parser.add_argument("--run-id")
    workbench_readiness_action_queue_parser.add_argument("--output", type=Path)

    workbench_readiness_action_parser = subparsers.add_parser(
        "workbench-readiness-action",
        help="Execute one readiness action request from JSON",
    )
    workbench_readiness_action_parser.add_argument("state_dir", type=Path)
    workbench_readiness_action_parser.add_argument("--input", type=Path, required=True)
    workbench_readiness_action_parser.add_argument("--run-id")
    workbench_readiness_action_parser.add_argument("--output", type=Path)

    workbench_readiness_action_log_parser = subparsers.add_parser(
        "workbench-readiness-action-log",
        help="Read workbench-readiness-action-log.jsonl",
    )
    workbench_readiness_action_log_parser.add_argument("state_dir", type=Path)
    workbench_readiness_action_log_parser.add_argument("--output", type=Path)

    workbench_readiness_action_result_parser = subparsers.add_parser(
        "workbench-readiness-action-result",
        help="Read workbench-readiness-action-result.json",
    )
    workbench_readiness_action_result_parser.add_argument("state_dir", type=Path)
    workbench_readiness_action_result_parser.add_argument("--output", type=Path)

    for command, help_text in (
        ("workflow-plan", "Create a deterministic workflow-run-plan.json"),
        ("workflow-stage-status", "Create workflow-stage-status.json from current artifact evidence"),
        ("workflow-dependency-graph", "Create the workflow dependency graph"),
        ("workflow-run", "Run safe deterministic artifact builders only"),
        ("workflow-execution-result", "Read workflow-execution-result.json"),
        ("workflow-readiness-summary", "Create workflow-readiness-summary.json without upgrading readiness"),
    ):
        workflow_parser = subparsers.add_parser(command, help=help_text)
        workflow_parser.add_argument("state_dir", type=Path)
        workflow_parser.add_argument("--workflow-mode", choices=sorted(WORKFLOW_MODES), default="diagnose_only")
        workflow_parser.add_argument("--stage", action="append", default=[], dest="selected_stages")
        workflow_parser.add_argument("--scenario")
        workflow_parser.add_argument("--source-locale")
        workflow_parser.add_argument("--target-locale")
        workflow_parser.add_argument("--target-delivery-mode")
        workflow_parser.add_argument("--run-id")
        workflow_parser.add_argument("--idempotency-key")
        workflow_parser.add_argument("--force-release-stale-lock", action="store_true")
        workflow_parser.add_argument("--output", type=Path)

    for command, help_text in (
        ("workflow-resume-plan", "Create workflow-resume-plan.json from prior lifecycle evidence"),
        ("artifact-invalidation-report", "Create artifact-invalidation-report.json from dependency hashes"),
        ("selective-recompute-plan", "Create a deterministic selective recompute plan"),
        ("selective-recompute-result", "Read selective-recompute-result.json"),
        ("incremental-workflow-summary", "Create incremental-workflow-summary.json"),
        ("workflow-resume", "Resume safe deterministic workflow stages"),
        ("selective-recompute", "Run selected deterministic recompute stages only"),
    ):
        incremental_parser = subparsers.add_parser(command, help=help_text)
        incremental_parser.add_argument("state_dir", type=Path)
        incremental_parser.add_argument("--workflow-mode", choices=sorted(WORKFLOW_MODES), default="diagnose_only")
        incremental_parser.add_argument("--resume-source", choices=sorted(RESUME_SOURCES))
        incremental_parser.add_argument("--recompute-strategy", choices=sorted(RECOMPUTE_STRATEGIES), default="minimal_safe")
        incremental_parser.add_argument("--trigger-source", default="manual-request")
        incremental_parser.add_argument("--stage", action="append", default=[], dest="selected_stages")
        incremental_parser.add_argument("--run-id")
        incremental_parser.add_argument("--idempotency-key")
        incremental_parser.add_argument("--force-release-stale-lock", action="store_true")
        incremental_parser.add_argument("--output", type=Path)

    for command, help_text in (
        ("workflow-lock-state", "Read workflow-lock-state.json"),
        ("workflow-checkpoint-log", "Read workflow-checkpoint-log.jsonl"),
        ("workflow-transaction-manifest", "Read workflow-transaction-manifest.json"),
        ("workflow-idempotency-report", "Read workflow-idempotency-report.json"),
        ("workflow-recovery-plan", "Create workflow-recovery-plan.json"),
        ("workflow-recovery-result", "Read workflow-recovery-result.json"),
        ("workflow-recover", "Run deterministic workflow recovery without providers, repairs, or target mutation"),
    ):
        hardening_parser = subparsers.add_parser(command, help=help_text)
        hardening_parser.add_argument("state_dir", type=Path)
        hardening_parser.add_argument("--recovery-action", default="recompute_stale_artifacts")
        hardening_parser.add_argument("--run-id")
        hardening_parser.add_argument("--output", type=Path)

    workbench_console_parser = subparsers.add_parser("workbench-console", help="Render the artifact-backed Workbench Review Console HTML")
    workbench_console_parser.add_argument("state_dir", type=Path)
    workbench_console_parser.add_argument("--output", type=Path)

    document_evidence_parser = subparsers.add_parser("document-evidence-pack", help="Create the artifact-backed Document Evidence Pack")
    document_evidence_parser.add_argument("state_dir", type=Path)
    document_evidence_parser.add_argument("--run-dir", type=Path)
    document_evidence_parser.add_argument("--scenario")
    document_evidence_parser.add_argument("--run-id")
    document_evidence_parser.add_argument("--output", type=Path)

    workbench_document_evidence_queue_parser = subparsers.add_parser(
        "workbench-document-evidence-queue",
        help="Create workbench-document-evidence-queue.json from document evidence artifacts",
    )
    workbench_document_evidence_queue_parser.add_argument("state_dir", type=Path)
    workbench_document_evidence_queue_parser.add_argument("--output", type=Path)

    record_document_decision_parser = subparsers.add_parser("record-document-decision", help="Append a structured document evidence decision")
    record_document_decision_parser.add_argument("state_dir", type=Path)
    record_document_decision_parser.add_argument("--input", type=Path, required=True)
    record_document_decision_parser.add_argument("--run-id")
    record_document_decision_parser.add_argument("--output", type=Path)

    document_decision_log_parser = subparsers.add_parser("document-decision-log", help="Read document-decision-log.jsonl as deterministic JSON")
    document_decision_log_parser.add_argument("state_dir", type=Path)
    document_decision_log_parser.add_argument("--output", type=Path)

    record_leadership_review_parser = subparsers.add_parser("record-leadership-review", help="Append structured leadership review evidence")
    record_leadership_review_parser.add_argument("state_dir", type=Path)
    record_leadership_review_parser.add_argument("--input", type=Path, required=True)
    record_leadership_review_parser.add_argument("--run-id")
    record_leadership_review_parser.add_argument("--output", type=Path)

    leadership_review_parser = subparsers.add_parser("leadership-review-evidence", help="Read leadership-review-evidence.jsonl as deterministic JSON")
    leadership_review_parser.add_argument("state_dir", type=Path)
    leadership_review_parser.add_argument("--output", type=Path)

    document_claim_resolution_parser = subparsers.add_parser("document-claim-resolution", help="Create document-claim-resolution.json from document decisions")
    document_claim_resolution_parser.add_argument("state_dir", type=Path)
    document_claim_resolution_parser.add_argument("--run-id")
    document_claim_resolution_parser.add_argument("--output", type=Path)

    document_signoff_summary_parser = subparsers.add_parser("document-signoff-summary", help="Create document-signoff-summary.json from document decisions and signoff")
    document_signoff_summary_parser.add_argument("state_dir", type=Path)
    document_signoff_summary_parser.add_argument("--run-id")
    document_signoff_summary_parser.add_argument("--output", type=Path)

    knowledge_pack_init_parser = subparsers.add_parser("knowledge-pack-init", help="Initialize a local-first Personal Knowledge Pack")
    knowledge_pack_init_parser.add_argument("state_dir", type=Path)
    knowledge_pack_init_parser.add_argument("--pack-id", required=True)
    knowledge_pack_init_parser.add_argument("--name")
    knowledge_pack_init_parser.add_argument("--source-locale")
    knowledge_pack_init_parser.add_argument("--target-locale")
    knowledge_pack_init_parser.add_argument("--domain", action="append", default=[], dest="domains")
    knowledge_pack_init_parser.add_argument("--privacy-mode", default="local_only")
    knowledge_pack_init_parser.add_argument("--created-by", default="localize-anything-runtime")
    knowledge_pack_init_parser.add_argument("--quality-level", default="raw")
    knowledge_pack_init_parser.add_argument("--scenario", action="append", default=[], dest="supported_scenarios")
    knowledge_pack_init_parser.add_argument("--output", type=Path)

    knowledge_pack_export_parser = subparsers.add_parser("knowledge-pack-export", help="Export reviewed candidate knowledge into a Personal Knowledge Pack")
    knowledge_pack_export_parser.add_argument("state_dir", type=Path)
    knowledge_pack_export_parser.add_argument("--pack-id", required=True)
    knowledge_pack_export_parser.add_argument("--output", type=Path)

    knowledge_pack_parser = subparsers.add_parser("knowledge-pack", help="Read pack.json for a Personal Knowledge Pack")
    knowledge_pack_parser.add_argument("state_dir", type=Path)
    knowledge_pack_parser.add_argument("--pack-id", required=True)
    knowledge_pack_parser.add_argument("--output", type=Path)

    knowledge_review_queue_parser = subparsers.add_parser("knowledge-review-queue", help="Read knowledge-review-queue.json")
    knowledge_review_queue_parser.add_argument("state_dir", type=Path)
    knowledge_review_queue_parser.add_argument("--pack-id", required=True)
    knowledge_review_queue_parser.add_argument("--output", type=Path)

    knowledge_review_decision_parser = subparsers.add_parser("knowledge-review-decision", help="Append a structured knowledge review decision")
    knowledge_review_decision_parser.add_argument("state_dir", type=Path)
    knowledge_review_decision_parser.add_argument("--pack-id", required=True)
    knowledge_review_decision_parser.add_argument("--input", type=Path, required=True)
    knowledge_review_decision_parser.add_argument("--run-id")
    knowledge_review_decision_parser.add_argument("--output", type=Path)

    knowledge_quality_report_parser = subparsers.add_parser("knowledge-quality-report", help="Read quality-report.md for a Personal Knowledge Pack")
    knowledge_quality_report_parser.add_argument("state_dir", type=Path)
    knowledge_quality_report_parser.add_argument("--pack-id", required=True)
    knowledge_quality_report_parser.add_argument("--output", type=Path)

    knowledge_pack_select_parser = subparsers.add_parser("knowledge-pack-select", help="Select local knowledge packs and build deterministic eligibility/context artifacts")
    knowledge_pack_select_parser.add_argument("state_dir", type=Path)
    knowledge_pack_select_parser.add_argument("--pack-id", action="append", default=[], dest="pack_ids")
    knowledge_pack_select_parser.add_argument("--pack-path", action="append", type=Path, default=[], dest="pack_paths")
    knowledge_pack_select_parser.add_argument("--source-locale", required=True)
    knowledge_pack_select_parser.add_argument("--target-locale", required=True)
    knowledge_pack_select_parser.add_argument("--domain", action="append", default=[], dest="domains")
    knowledge_pack_select_parser.add_argument("--scenario", default="")
    knowledge_pack_select_parser.add_argument("--operating-mode", choices=OPERATING_MODES, default="greenfield_localization")
    knowledge_pack_select_parser.add_argument("--selection-source", default="explicit")
    knowledge_pack_select_parser.add_argument("--selected-by", default="localize-anything-runtime")
    knowledge_pack_select_parser.add_argument("--allow-experimental", action="store_true")
    knowledge_pack_select_parser.add_argument("--allowed-domain", action="append", default=[], dest="allowed_domains")
    knowledge_pack_select_parser.add_argument("--allowed-scenario", action="append", default=[], dest="allowed_scenarios")
    knowledge_pack_select_parser.add_argument("--compatible-locale", action="append", default=[], dest="compatible_locales")
    knowledge_pack_select_parser.add_argument("--output", type=Path)

    knowledge_eligibility_parser = subparsers.add_parser("knowledge-eligibility-report", help="Rebuild knowledge-eligibility-report.json deterministically")
    knowledge_eligibility_parser.add_argument("state_dir", type=Path)
    knowledge_eligibility_parser.add_argument("--output", type=Path)

    working_context_parser = subparsers.add_parser("working-context-packet", help="Rebuild working-context-packet.json deterministically")
    working_context_parser.add_argument("state_dir", type=Path)
    working_context_parser.add_argument("--output", type=Path)

    knowledge_usage_parser = subparsers.add_parser("knowledge-usage-report", help="Rebuild knowledge-usage-report.json deterministically")
    knowledge_usage_parser.add_argument("state_dir", type=Path)
    knowledge_usage_parser.add_argument("--output", type=Path)

    constraint_audit_parser = subparsers.add_parser("constraint-application-audit", help="Rebuild constraint-application-audit.json deterministically")
    constraint_audit_parser.add_argument("state_dir", type=Path)
    constraint_audit_parser.add_argument("--output", type=Path)

    knowledge_conflict_parser = subparsers.add_parser("knowledge-conflict-report", help="Rebuild knowledge-conflict-report.json deterministically")
    knowledge_conflict_parser.add_argument("state_dir", type=Path)
    knowledge_conflict_parser.add_argument("--output", type=Path)

    knowledge_enforcement_parser = subparsers.add_parser("knowledge-audit-enforcement-decision", help="Rebuild knowledge-audit-enforcement-decision.json deterministically")
    knowledge_enforcement_parser.add_argument("state_dir", type=Path)
    knowledge_enforcement_parser.add_argument("--output", type=Path)

    workbench_knowledge_queue_parser = subparsers.add_parser("workbench-knowledge-review-queue", help="Create workbench-knowledge-review-queue.json from knowledge audit evidence")
    workbench_knowledge_queue_parser.add_argument("state_dir", type=Path)
    workbench_knowledge_queue_parser.add_argument("--output", type=Path)

    record_knowledge_resolution_parser = subparsers.add_parser("record-knowledge-audit-resolution", help="Append a structured knowledge audit resolution decision")
    record_knowledge_resolution_parser.add_argument("state_dir", type=Path)
    record_knowledge_resolution_parser.add_argument("--input", type=Path, required=True)
    record_knowledge_resolution_parser.add_argument("--run-id")
    record_knowledge_resolution_parser.add_argument("--output", type=Path)

    knowledge_resolution_log_parser = subparsers.add_parser("knowledge-audit-resolution-log", help="Read knowledge-audit-resolution-log.jsonl")
    knowledge_resolution_log_parser.add_argument("state_dir", type=Path)
    knowledge_resolution_log_parser.add_argument("--output", type=Path)

    record_constraint_review_parser = subparsers.add_parser("record-knowledge-constraint-review", help="Append knowledge constraint review evidence")
    record_constraint_review_parser.add_argument("state_dir", type=Path)
    record_constraint_review_parser.add_argument("--input", type=Path, required=True)
    record_constraint_review_parser.add_argument("--run-id")
    record_constraint_review_parser.add_argument("--output", type=Path)

    constraint_review_parser = subparsers.add_parser("knowledge-constraint-review-evidence", help="Read knowledge-constraint-review-evidence.jsonl")
    constraint_review_parser.add_argument("state_dir", type=Path)
    constraint_review_parser.add_argument("--output", type=Path)

    conflict_resolution_parser = subparsers.add_parser("knowledge-conflict-resolution", help="Rebuild knowledge-conflict-resolution.json deterministically")
    conflict_resolution_parser.add_argument("state_dir", type=Path)
    conflict_resolution_parser.add_argument("--output", type=Path)

    assurance_summary_parser = subparsers.add_parser("knowledge-assurance-summary", help="Rebuild knowledge-assurance-summary.json deterministically")
    assurance_summary_parser.add_argument("state_dir", type=Path)
    assurance_summary_parser.add_argument("--output", type=Path)

    draft_request_parser = subparsers.add_parser("draft-request", help="Create a provider-agnostic LLM draft request from a work packet")
    draft_request_parser.add_argument("work_packet", type=Path)
    draft_request_parser.add_argument("--output", type=Path)

    draft_prompt_parser = subparsers.add_parser("render-draft-prompt", help="Render a draft request as a paste-ready Markdown prompt")
    draft_prompt_parser.add_argument("draft_request", type=Path)
    draft_prompt_parser.add_argument("--output", type=Path, required=True)

    validate_generated_parser = subparsers.add_parser("validate-generated", help="Validate generated segment JSONL against a work packet")
    validate_generated_parser.add_argument("work_packet", type=Path)
    validate_generated_parser.add_argument("generated", type=Path)
    validate_generated_parser.add_argument("--output", type=Path)

    import_generated_parser = subparsers.add_parser(
        "import-generated-response",
        help="Normalize an LLM response into generated segment JSONL and validate it against a work packet",
    )
    import_generated_parser.add_argument("work_packet", type=Path)
    import_generated_parser.add_argument("response", type=Path)
    import_generated_parser.add_argument("--generated-output", type=Path, required=True)
    import_generated_parser.add_argument("--output", type=Path)

    import_handoff_parser = subparsers.add_parser(
        "import-generated-handoff",
        help="Normalize a directory of LLM responses into generated JSONL batches for a handoff",
    )
    import_handoff_parser.add_argument("handoff", type=Path)
    import_handoff_parser.add_argument("response_dir", type=Path)
    import_handoff_parser.add_argument("--generated-output", type=Path)
    import_handoff_parser.add_argument("--output", type=Path)

    handoff_prompts_parser = subparsers.add_parser("render-handoff-prompts", help="Render every draft request in a handoff as Markdown prompts")
    handoff_prompts_parser.add_argument("handoff", type=Path)
    handoff_prompts_parser.add_argument("--prompt-dir", type=Path, required=True)
    handoff_prompts_parser.add_argument("--response-dir", type=Path)
    handoff_prompts_parser.add_argument("--readme-output", type=Path)
    handoff_prompts_parser.add_argument("--generated-output", type=Path)
    handoff_prompts_parser.add_argument("--output", type=Path)

    handoff_parser = subparsers.add_parser("generation-handoff", help="Create a host-agent generation handoff manifest")
    handoff_parser.add_argument("work_packet_dir", type=Path)
    handoff_parser.add_argument("draft_request_dir", type=Path)
    handoff_parser.add_argument("--generated-dir", type=Path, required=True)
    handoff_parser.add_argument("--target-locale")
    handoff_parser.add_argument("--output", type=Path)

    collect_parser = subparsers.add_parser("collect-generated", help="Validate and combine generated batches from a handoff manifest")
    collect_parser.add_argument("handoff", type=Path)
    collect_parser.add_argument("--generated-output", type=Path)
    collect_parser.add_argument("--output", type=Path)

    retry_handoff_parser = subparsers.add_parser("retry-handoff", help="Create a handoff manifest for failed or missing generation batches")
    retry_handoff_parser.add_argument("handoff", type=Path)
    retry_handoff_parser.add_argument("generation_report", type=Path)
    retry_handoff_parser.add_argument("--generated-dir", type=Path)
    retry_handoff_parser.add_argument("--output", type=Path)

    provider_generate_parser = subparsers.add_parser("provider-generate", help="Generate batches through a direct HTTP JSON provider")
    provider_generate_parser.add_argument("handoff", type=Path)
    provider_generate_parser.add_argument("--provider-url", required=True)
    provider_generate_parser.add_argument("--api-key-env")
    provider_generate_parser.add_argument("--state-dir", type=Path)
    provider_generate_parser.add_argument("--generated-output", type=Path)
    provider_generate_parser.add_argument("--timeout-seconds", type=int, default=60)
    provider_generate_parser.add_argument("--output", type=Path)

    chinese_draft_parser = subparsers.add_parser(
        "generate-chinese-draft",
        help="Create local Chinese draft generated-segment JSONL for E2E testing",
    )
    chinese_draft_parser.add_argument("segments", type=Path)
    chinese_draft_parser.add_argument("--target-locale", default="zh-CN")
    chinese_draft_parser.add_argument("--generated-output", type=Path, required=True)
    chinese_draft_parser.add_argument("--provider", default="codex-local")
    chinese_draft_parser.add_argument("--quality-claim", default="local_chinese_draft_for_e2e")
    chinese_draft_parser.add_argument("--output", type=Path)

    deepseek_parser = subparsers.add_parser(
        "deepseek-generate",
        help="Translate segments via DeepSeek API and write generated JSONL",
    )
    deepseek_parser.add_argument("segments", type=Path, help="JSONL file of extracted segments")
    deepseek_parser.add_argument("--target-locale", required=True, help="e.g. ja, ko, zh-CN")
    deepseek_parser.add_argument("--source-locale", default="en-US")
    deepseek_parser.add_argument("--model", default="deepseek-chat")
    deepseek_parser.add_argument("--generated-output", type=Path, required=True)
    deepseek_parser.add_argument("--output", type=Path)

    stage_generated_parser = subparsers.add_parser("stage-generated", help="Route generated segment JSONL to adapter-specific staged output files")
    stage_generated_parser.add_argument("project", type=Path)
    stage_generated_parser.add_argument("generated", type=Path)
    stage_generated_parser.add_argument("--source-locale", required=True)
    stage_generated_parser.add_argument("--target-locale", required=True)
    stage_generated_parser.add_argument("--source-file", action="append", dest="source_files")
    stage_generated_parser.add_argument("--staging-dir", type=Path, required=True)
    stage_generated_parser.add_argument("--output", type=Path)

    localize_run_parser = subparsers.add_parser(
        "localize-run",
        help="Run preflight, extract, plan, generation handoff, staging, package, and dashboard",
        description=(
            "Run the non-apply localization workflow: preflight, extraction, planning, generation handoff "
            "or provided drafts, staging, packaging, and dashboard creation. This command does not call "
            "apply-delivery or overwrite source files."
        ),
    )
    localize_run_parser.add_argument("project", type=Path)
    localize_run_parser.add_argument("--source-locale", required=True)
    localize_run_parser.add_argument("--target-locale", action="append", required=True, dest="target_locales")
    localize_run_parser.add_argument("--source-file", action="append", dest="source_files")
    localize_run_parser.add_argument("--output-root", type=Path)
    localize_run_parser.add_argument("--run-id")
    localize_run_parser.add_argument("--max-segments", type=int, default=80)
    localize_run_parser.add_argument("--limit-tokens", type=int, default=4000)
    localize_run_parser.add_argument("--handoff-only", action="store_true")
    localize_run_parser.add_argument("--generated-dir", type=Path)
    localize_run_parser.add_argument("--generated", type=Path)
    localize_run_parser.add_argument("--synthetic-draft", action="store_true")
    localize_run_parser.add_argument(
        "--include-android-merged-resources",
        action="store_true",
        help="Explicitly include Gradle merged Android resources as an app-owned dependency overlay",
    )
    localize_run_parser.add_argument(
        "--android-merged-resources",
        type=Path,
        help="Merged Android values.xml file or directory to use with --include-android-merged-resources",
    )
    localize_run_parser.add_argument(
        "--android-build-variant",
        help="Build variant whose Gradle merged resources should be discovered, such as fossDebug",
    )
    localize_run_parser.add_argument(
        "--android-overlay-output-name",
        default="localize_anything_overlay.xml",
        help="App-owned overlay XML file name for merged dependency resources",
    )
    localize_run_parser.add_argument("--workflow-depth", default="ask", choices=["ask", "fast", "standard", "high_assurance"])
    localize_run_parser.add_argument("--preflight-mode", default="auto", choices=["auto", "light", "full", "layered", "skip_deep"])
    localize_run_parser.add_argument("--privacy-mode", default="standard")
    localize_run_parser.add_argument("--data-classification", default="internal")
    localize_run_parser.add_argument("--operating-mode", choices=OPERATING_MODES)
    localize_run_parser.add_argument("--reference-policy", choices=REFERENCE_POLICIES)
    localize_run_parser.add_argument("--status", choices=["draft_package", "review_ready", "blocked"], default="draft_package")
    localize_run_parser.add_argument("--output", type=Path)

    agent_run_parser = subparsers.add_parser(
        "agent-run",
        help="Run the provider-agnostic routing, parallelization, and reflection localization agent",
    )
    agent_run_parser.add_argument("project", type=Path)
    agent_run_parser.add_argument("--source-locale", default="en-US")
    agent_run_parser.add_argument("--target-locale", required=True)
    agent_run_parser.add_argument("--source-file", action="append", dest="source_files")
    agent_run_parser.add_argument("--output-root", type=Path)
    agent_run_parser.add_argument("--run-id")
    agent_run_parser.add_argument("--max-segments", type=int, default=80)
    agent_run_parser.add_argument("--limit-tokens", type=int, default=4000)
    agent_run_parser.add_argument("--responses-dir", type=Path)
    agent_run_parser.add_argument("--generated-dir", type=Path)
    agent_run_parser.add_argument("--generated", type=Path)
    agent_run_parser.add_argument("--synthetic-draft", action="store_true")
    agent_run_parser.add_argument("--provider-url")
    agent_run_parser.add_argument("--api-key-env")
    agent_run_parser.add_argument("--provider-timeout-seconds", type=int, default=60)
    agent_run_parser.add_argument("--delivery-run-id")
    agent_run_parser.add_argument("--workflow-depth", default="ask", choices=["ask", "fast", "standard", "high_assurance"])
    agent_run_parser.add_argument("--preflight-mode", default="auto", choices=["auto", "light", "full", "layered", "skip_deep"])
    agent_run_parser.add_argument("--privacy-mode", default="standard")
    agent_run_parser.add_argument("--data-classification", default="internal")
    agent_run_parser.add_argument("--operating-mode", choices=OPERATING_MODES)
    agent_run_parser.add_argument("--reference-policy", choices=REFERENCE_POLICIES)
    agent_run_parser.add_argument("--status", choices=["draft_package", "review_ready", "blocked"], default="draft_package")
    agent_run_parser.add_argument("--output", type=Path)

    android_app_test_parser = subparsers.add_parser(
        "android-app-test",
        help="Run a full Android source-project localization test against an isolated app copy",
    )
    android_app_test_parser.add_argument("project", type=Path)
    android_app_test_parser.add_argument("--source-locale", default="en-US")
    android_app_test_parser.add_argument("--target-locale", required=True)
    android_app_test_parser.add_argument("--source-file")
    android_app_test_parser.add_argument("--output-root", type=Path)
    android_app_test_parser.add_argument("--run-id", default="android-app-test")
    android_app_test_parser.add_argument("--max-segments", type=int, default=20)
    android_app_test_parser.add_argument("--limit-tokens", type=int, default=4000)
    android_app_test_parser.add_argument("--generated-dir", type=Path)
    android_app_test_parser.add_argument("--generated", type=Path)
    android_app_test_parser.add_argument("--local-chinese-draft", action="store_true")
    android_app_test_parser.add_argument("--require-real-generation", action="store_true")
    android_app_test_parser.add_argument("--output", type=Path)

    ui_parser = subparsers.add_parser("ui", help="Start the local web workbench")
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", type=int, default=8765)
    ui_parser.add_argument("--open", action="store_true")

    diff_parser = subparsers.add_parser("diff-segments", help="Classify incremental segment changes")
    diff_parser.add_argument("previous", type=Path)
    diff_parser.add_argument("current", type=Path)
    diff_parser.add_argument("--output", type=Path)

    package_parser = subparsers.add_parser("package", help="Create an immutable standard-project delivery snapshot")
    package_parser.add_argument("state_dir", type=Path)
    package_parser.add_argument("staging_dir", type=Path)
    package_parser.add_argument("--output-root", type=Path, required=True)
    package_parser.add_argument("--qa-result", action="append", type=Path, default=[], dest="qa_results")
    package_parser.add_argument("--status", choices=["draft_package", "review_ready", "blocked"], default="draft_package")
    package_parser.add_argument("--run-id")
    package_parser.add_argument("--output", type=Path)

    compile_mo_parser = subparsers.add_parser("compile-mo", help="Compile translated segments into a GNU gettext MO file")
    compile_mo_parser.add_argument("translations", type=Path)
    compile_mo_parser.add_argument("--output", type=Path, required=True)

    review_parser = subparsers.add_parser("review-import", help="Import scoped human-reviewed segments into project TM")
    review_parser.add_argument("generated", type=Path)
    review_parser.add_argument("reviewed", type=Path)
    review_parser.add_argument("state_dir", type=Path)
    review_parser.add_argument("--run-id", required=True)
    review_parser.add_argument("--target-locale", required=True)
    review_parser.add_argument("--output", type=Path)

    review_sheet_parser = subparsers.add_parser("review-sheet", help="Export generated segment JSONL as Markdown and CSV for human review")
    review_sheet_parser.add_argument("generated", type=Path)
    review_sheet_parser.add_argument("--markdown-output", type=Path)
    review_sheet_parser.add_argument("--csv-output", type=Path)
    review_sheet_parser.add_argument("--output", type=Path)

    llm_review_request_parser = subparsers.add_parser("llm-review-request", help="Create an LLM reflection request from generated segment JSONL")
    llm_review_request_parser.add_argument("generated", type=Path)
    llm_review_request_parser.add_argument("--source-locale", required=True)
    llm_review_request_parser.add_argument("--target-locale", required=True)
    llm_review_request_parser.add_argument("--run-id")
    llm_review_request_parser.add_argument("--max-segments", type=int, default=80)
    llm_review_request_parser.add_argument("--deterministic-report", type=Path)
    llm_review_request_parser.add_argument("--prompt-output", type=Path)
    llm_review_request_parser.add_argument("--output", type=Path)

    import_llm_review_parser = subparsers.add_parser("import-llm-review", help="Import an LLM reflection response into segment-level issues")
    import_llm_review_parser.add_argument("request", type=Path)
    import_llm_review_parser.add_argument("response", type=Path)
    import_llm_review_parser.add_argument("--review-output", type=Path)
    import_llm_review_parser.add_argument("--output", type=Path)

    signoff_parser = subparsers.add_parser("sign-off", help="Create user-owned scoped acceptance for a delivery manifest")
    signoff_parser.add_argument("manifest", type=Path)
    signoff_parser.add_argument("--accepted-by", required=True)
    signoff_parser.add_argument("--locale", action="append", default=[], dest="locales")
    signoff_parser.add_argument("--content-type", action="append", default=[], dest="content_types")
    signoff_parser.add_argument("--file", action="append", default=[], dest="files")
    signoff_parser.add_argument("--batch-id", action="append", default=[], dest="batch_ids")
    signoff_parser.add_argument("--allow-draft", action="store_true")
    signoff_parser.add_argument("--output", type=Path, required=True)

    apply_parser = subparsers.add_parser("plan-apply", help="Create a non-mutating apply-in-place dry run")
    apply_parser.add_argument("delivery_dir", type=Path)
    apply_parser.add_argument("project", type=Path)
    apply_parser.add_argument("--markdown-output", type=Path)
    apply_parser.add_argument("--output", type=Path)

    execute_apply_parser = subparsers.add_parser(
        "apply-delivery",
        help="Apply a delivery after explicit run-id confirmation and clean-git safety checks",
    )
    execute_apply_parser.add_argument("delivery_dir", type=Path)
    execute_apply_parser.add_argument("project", type=Path)
    execute_apply_parser.add_argument("--confirm-run-id", required=True)
    execute_apply_parser.add_argument("--backup-root", type=Path)
    execute_apply_parser.add_argument("--output", type=Path)

    dashboard_parser = subparsers.add_parser("delivery-dashboard", help="Summarize a delivery for developers and translators")
    dashboard_parser.add_argument("delivery_dir", type=Path)
    dashboard_parser.add_argument("--markdown-output", type=Path)
    dashboard_parser.add_argument("--output", type=Path)

    delivery_decision_parser = subparsers.add_parser("delivery-decision", help="Create a Delivery Agent decision report for staged output")
    delivery_decision_parser.add_argument("delivery_dir", type=Path)
    delivery_decision_parser.add_argument("project", type=Path)
    delivery_decision_parser.add_argument("--markdown-output", type=Path)
    delivery_decision_parser.add_argument("--output", type=Path)
    return parser


def _resolve_inspect_project(project: Path | None, project_option: Path | None) -> Path:
    if project is not None and project_option is not None and project != project_option:
        raise ValueError("inspect accepts either positional PROJECT or --project, not both")
    resolved = project_option or project
    if resolved is None:
        raise ValueError("inspect requires a project path; pass PROJECT or --project PROJECT")
    return resolved


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            project = _resolve_inspect_project(args.project, args.project_option)
            result = inspect_project(project)
            if args.output_dir:
                validate_inspect_output_directory(project, args.output_dir)
                summary = build_inspect_summary(result, output_directory=args.output_dir)
                summary["artifacts"] = write_inspect_summary(args.output_dir, summary)
                return _emit_json(summary, args.output)
            return _emit_json(result, args.output)
        if args.command == "sessions":
            return _emit_json(load_session_index(args.project), args.output)
        if args.command == "preflight":
            result = initialize_project(
                args.project,
                args.source_locale,
                args.source_files,
                args.target_locales,
                args.operating_mode,
                args.reference_policy,
                args.workflow_depth,
                args.preflight_mode,
                args.privacy_mode,
                args.data_classification,
            )
            return _emit_json(result, args.output)
        if args.command == "extract-json":
            records = extract_segments(args.source, args.source_locale, args.source_path)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "rebuild-json":
            rebuild(args.source, read_jsonl(args.translations), args.output)
            return 0
        if args.command == "validate-json":
            result = validate_pair(args.source, args.target)
            _emit_json(result, args.output)
            return 0 if result["status"] == "pass" else 1
        if args.command == "extract-po":
            records = extract_po_segments(args.source, args.source_locale, args.source_path)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "rebuild-po":
            rebuild_po(args.source, read_jsonl(args.translations), args.output, args.target_locale)
            return 0
        if args.command == "validate-po":
            result = validate_po_pair(args.source, args.target)
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "extract-structured":
            records = extract_structured_segments(args.source, args.source_locale, args.source_path, args.format)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "rebuild-structured":
            rebuild_structured(args.source, read_jsonl(args.translations), args.output, args.format)
            return 0
        if args.command == "validate-structured":
            result = validate_structured_pair(args.source, args.target, args.format)
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "extract-tabular":
            records = extract_tabular_segments(args.source, args.source_locale, args.source_path)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "rebuild-tabular":
            rebuild_tabular(args.source, read_jsonl(args.translations), args.output)
            return 0
        if args.command == "validate-tabular":
            result = validate_tabular_pair(args.source, args.target)
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "extract-word":
            records = extract_word_segments(args.source, args.source_locale, args.source_path)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "rebuild-word":
            rebuild_word(args.source, read_jsonl(args.translations), args.output)
            return 0
        if args.command == "validate-word":
            result = validate_word_pair(args.source, args.target)
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "extract-markup":
            records = extract_markup_segments(args.source, args.source_locale, args.source_path)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "rebuild-markup":
            rebuild_markup(args.source, read_jsonl(args.translations), args.output)
            return 0
        if args.command == "validate-markup":
            result = validate_markup_pair(args.source, args.target)
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "extract-subtitles":
            records = extract_subtitle_segments(args.source, args.source_locale, args.source_path)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "rebuild-subtitles":
            rebuild_subtitles(args.source, read_jsonl(args.translations), args.output)
            return 0
        if args.command == "validate-subtitles":
            result = validate_subtitle_pair(args.source, args.target)
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "extract-xliff":
            records = extract_xliff_segments(args.source, args.source_locale, args.source_path)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "rebuild-xliff":
            rebuild_xliff(args.source, read_jsonl(args.translations), args.output, args.target_locale)
            return 0
        if args.command == "validate-xliff":
            result = validate_xliff_pair(args.source, args.target)
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "extract-android-strings":
            records = extract_android_strings(args.source, args.source_locale, args.source_path)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "rebuild-android-strings":
            rebuild_android_strings(args.source, read_jsonl(args.translations), args.output)
            return 0
        if args.command == "stage-android-strings":
            result = stage_android_strings(
                args.source,
                read_jsonl(args.translations),
                args.staging_dir,
                args.target_locale,
                args.project_root,
            )
            return _emit_json(result, args.output)
        if args.command == "validate-android-strings":
            result = validate_android_strings(args.source, args.target)
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "extract-ios-strings":
            records = extract_ios_strings(args.source, args.source_locale, args.source_path)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "rebuild-ios-strings":
            rebuild_ios_strings(args.source, read_jsonl(args.translations), args.output)
            return 0
        if args.command == "stage-ios-strings":
            result = stage_ios_strings(
                args.source,
                read_jsonl(args.translations),
                args.staging_dir,
                args.target_locale,
                args.project_root,
            )
            return _emit_json(result, args.output)
        if args.command == "validate-ios-strings":
            result = validate_ios_strings(args.source, args.target)
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "extract-xcstrings":
            records = extract_xcstrings(args.source, args.source_locale, args.source_path)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "rebuild-xcstrings":
            rebuild_xcstrings(args.source, read_jsonl(args.translations), args.output, args.target_locale)
            return 0
        if args.command == "stage-xcstrings":
            result = stage_xcstrings(
                args.source,
                read_jsonl(args.translations),
                args.staging_dir,
                args.target_locale,
                args.project_root,
            )
            return _emit_json(result, args.output)
        if args.command == "validate-xcstrings":
            result = validate_xcstrings(args.source, args.target, args.target_locale)
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "wesnoth-inventory":
            return _emit_json(inventory_wesnoth(args.project), args.output)
        if args.command == "extract-wesnoth":
            records = extract_wesnoth_segments(args.project, args.source_locale)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "enrich-wesnoth":
            records = enrich_wesnoth_segments(read_jsonl(args.segments), args.project)
            if args.output:
                write_jsonl(args.output, records)
            else:
                sys.stdout.write("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
            return 0
        if args.command == "validate-wesnoth":
            result = validate_wesnoth_source(args.project, read_jsonl(args.segments))
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "validate-contracts":
            result = validate_adapter_tree(args.root)
            _emit_json(result, args.output)
            return 0 if result["status"] == "pass" else 1
        if args.command == "validate-protocol":
            result = validate_protocol_tree(args.root)
            _emit_json(result, args.output)
            return 0 if result["status"] == "pass" else 1
        if args.command == "plan":
            result = create_batch_plan(
                read_jsonl(args.segments),
                args.source_locale,
                args.target_locales,
                args.max_segments,
                args.operating_mode,
                args.reference_policy,
            )
            return _emit_json(result, args.output)
        if args.command == "retrieve":
            result = build_work_packet(
                read_json(args.plan),
                args.batch_id,
                read_jsonl(args.segments),
                args.state_dir,
                args.target_locale,
                args.limit_tokens,
            )
            return _emit_json(result, args.output)
        if args.command == "termbase-preflight":
            result = run_termbase_preflight(
                args.state_dir,
                read_jsonl(args.segments),
                source_locale=args.source_locale,
                target_locale=args.target_locale,
                run_id=args.run_id,
            )
            return _emit_json(result, args.output)
        if args.command == "term-review-decision":
            result = record_term_review_decision(
                args.state_dir,
                {
                    "candidate_id": args.candidate_id,
                    "source_term": args.source_term,
                    "target_term": args.target_term,
                    "term_type": args.term_type,
                    "status": args.status,
                    "target_locale": args.target_locale,
                    "scope": args.scope,
                    "notes": args.notes,
                    "forbidden_targets": args.forbidden_targets,
                    "decided_by": args.decided_by,
                },
            )
            return _emit_json(result, args.output)
        if args.command == "generation-strategy":
            result = write_generation_strategy(
                args.state_dir,
                build_generation_strategy(
                    args.state_dir,
                    read_json(args.plan),
                    source_locale=args.source_locale,
                    target_locale=args.target_locale,
                    run_id=args.run_id,
                ),
            )
            return _emit_json(result, args.output)
        if args.command == "blocking-questions":
            provider_policy = {"status": args.provider_policy}
            if args.provider_policy == "fallback_requested":
                provider_policy = {"mode": "real_provider", "fallback_requested": True}
            context = {
                "android_coverage": {"visible_ui_coverage_warning": bool(args.coverage_warning)},
                "provider_policy": provider_policy,
                "operating_mode": args.operating_mode,
                "scenario": args.scenario,
            }
            return _emit_json(build_resolution_gate(args.state_dir, context=context, run_id=args.run_id), args.output)
        if args.command == "resolve-question":
            decision = {
                "question_id": args.question_id,
                "option_id": args.option_id,
                "target_term": args.target_term,
                "target_locale": args.target_locale,
                "term_status": args.term_status,
                "notes": args.notes,
                "decided_by": args.decided_by,
            }
            return _emit_json(record_user_resolution_decision(args.state_dir, decision), args.output)
        if args.command == "generation-handoff-status":
            provider_policy: dict[str, Any] = {
                "mode": args.provider_mode,
                "provider_controlled": args.provider_mode == "real_provider",
            }
            if args.provider_policy == "safe":
                provider_policy["status"] = "safe"
            elif args.provider_policy == "unsafe":
                provider_policy["status"] = "unsafe"
            elif args.provider_policy == "fallback_requested":
                provider_policy["status"] = "unsafe"
                provider_policy["fallback_requested"] = True
            if args.provider_mode == "synthetic_test":
                provider_policy["status"] = "safe"
            build_artifact_state(args.state_dir, run_id=args.run_id)
            result = build_generation_handoff_decision(
                args.state_dir,
                requested_mode=args.requested_mode,
                provider_policy=provider_policy,
                coverage_policy={"visible_ui_coverage_warning": bool(args.coverage_warning)},
                run_id=args.run_id,
            )
            build_artifact_state(args.state_dir, run_id=args.run_id)
            return _emit_json(result, args.output)
        if args.command == "artifact-state":
            result = build_artifact_state(
                args.state_dir,
                run_dir=args.run_dir,
                delivery_dir=args.delivery_dir,
                run_id=args.run_id,
            )
            return _emit_json(result, args.output)
        if args.command == "reuse-decision":
            result = build_reuse_decision(
                args.state_dir,
                read_jsonl(args.segments),
                previous_segments=read_jsonl(args.previous_segments) if args.previous_segments else None,
                generated_segments=read_jsonl(args.generated) if args.generated else None,
                review_result_path=args.review_result,
                provider_policy=_json_argument(args.provider_policy_json, "provider-policy-json"),
                review_policy=_json_argument(args.review_policy_json, "review-policy-json"),
                run_id=args.run_id,
            )
            return _emit_json(result, args.output)
        if args.command == "stale-segments":
            result = {
                "protocol_version": "0.1",
                "schema": "localize-anything-stale-segments-list-v1",
                "state_dir": args.state_dir.as_posix(),
                "reuse_decision": read_reuse_decision(args.state_dir),
                "segments": read_stale_segments(args.state_dir),
            }
            return _emit_json(result, args.output)
        if args.command == "segment-regeneration-plan":
            result = build_segment_regeneration_plan(args.state_dir, run_id=args.run_id)
            return _emit_json(result, args.output)
        if args.command == "repair-request":
            result = {
                "protocol_version": "0.1",
                "schema": "localize-anything-repair-request-read-v1",
                "state_dir": args.state_dir.as_posix(),
                "segment_regeneration_plan": read_segment_regeneration_plan(args.state_dir),
                "repair_request": read_repair_request(args.state_dir),
            }
            return _emit_json(result, args.output)
        if args.command == "apply-repair-plan":
            result = apply_repair_plan(
                args.state_dir,
                generated_segments_path=args.generated_segments,
                run_id=args.run_id,
            )
            return _emit_json(result, args.output)
        if args.command == "repair-result":
            result = {
                "protocol_version": "0.1",
                "schema": "localize-anything-repair-result-read-v1",
                "state_dir": args.state_dir.as_posix(),
                "repair_result": read_repair_result(args.state_dir),
            }
            return _emit_json(result, args.output)
        if args.command == "repair-history":
            result = {
                "protocol_version": "0.1",
                "schema": "localize-anything-repair-history-list-v1",
                "state_dir": args.state_dir.as_posix(),
                "repair_history": read_repair_history(args.state_dir),
            }
            return _emit_json(result, args.output)
        if args.command == "knowledge-repair-plan":
            return _emit_json(build_knowledge_repair_plan(args.state_dir, run_id=args.run_id), args.output)
        if args.command == "knowledge-repair-request":
            return _emit_json(build_knowledge_repair_request(args.state_dir, run_id=args.run_id), args.output)
        if args.command == "knowledge-repair-impact-report":
            return _emit_json(build_knowledge_repair_impact_report(args.state_dir, run_id=args.run_id), args.output)
        if args.command == "record-knowledge-repair-result":
            return _emit_json(
                record_knowledge_repair_result(args.state_dir, read_json(args.input), run_id=args.run_id),
                args.output,
            )
        if args.command == "knowledge-repair-result-intake":
            return _emit_json(
                {
                    "protocol_version": "0.1",
                    "schema": "localize-anything-knowledge-repair-result-intake-list-v1",
                    "state_dir": args.state_dir.as_posix(),
                    "results": read_knowledge_repair_result_intake(args.state_dir),
                },
                args.output,
            )
        if args.command == "knowledge-repair-qa-report":
            return _emit_json(build_knowledge_repair_qa_report(args.state_dir), args.output)
        if args.command == "knowledge-repair-reconciliation":
            return _emit_json(build_knowledge_repair_reconciliation(args.state_dir), args.output)
        if args.command == "knowledge-recompute-plan":
            return _emit_json(build_knowledge_recompute_plan(args.state_dir), args.output)
        if args.command == "knowledge-recompute-result":
            return _emit_json(build_knowledge_recompute_result(args.state_dir), args.output)
        if args.command == "knowledge-repair-closure-decision":
            return _emit_json(build_knowledge_repair_closure_decision(args.state_dir), args.output)
        if args.command == "knowledge-readiness-impact-report":
            return _emit_json(build_knowledge_readiness_impact_report(args.state_dir), args.output)
        if args.command == "knowledge-repair-recompute":
            result = {
                "protocol_version": "0.1",
                "schema": "localize-anything-knowledge-repair-recompute-command-v1",
                "state_dir": args.state_dir.as_posix(),
                "recompute_plan": build_knowledge_recompute_plan(args.state_dir),
                "recompute_result": build_knowledge_recompute_result(args.state_dir),
                "closure_decision": build_knowledge_repair_closure_decision(args.state_dir),
                "readiness_impact_report": build_knowledge_readiness_impact_report(args.state_dir),
                "provider_or_model_called": False,
                "repair_applied": False,
            }
            return _emit_json(result, args.output)
        if args.command == "readiness-authorization-matrix":
            return _emit_json(
                build_readiness_authorization_matrix(args.state_dir, delivery_dir=args.delivery_dir, run_id=args.run_id),
                args.output,
            )
        if args.command == "manual-followup-gap-report":
            return _emit_json(
                build_manual_followup_gap_report(args.state_dir, delivery_dir=args.delivery_dir, run_id=args.run_id),
                args.output,
            )
        if args.command == "apply-readiness-report":
            return _emit_json(
                build_apply_readiness_report(args.state_dir, delivery_dir=args.delivery_dir, run_id=args.run_id),
                args.output,
            )
        if args.command == "delivery-readiness-report":
            return _emit_json(
                build_delivery_readiness_report(args.state_dir, delivery_dir=args.delivery_dir, run_id=args.run_id),
                args.output,
            )
        if args.command == "readiness-check":
            result = {
                "protocol_version": "0.1",
                "schema": "localize-anything-readiness-check-command-v1",
                "state_dir": args.state_dir.as_posix(),
                **build_readiness_reports(args.state_dir, delivery_dir=args.delivery_dir, run_id=args.run_id),
                "provider_or_model_called": False,
                "repair_applied": False,
                "target_files_mutated": False,
            }
            return _emit_json(result, args.output)
        if args.command == "evaluation-scorecard":
            scorecard = build_evaluation_scorecard(
                args.state_dir,
                run_dir=args.run_dir,
                delivery_dir=args.delivery_dir,
                run_id=args.run_id,
            )
            result = {
                "protocol_version": "0.1",
                "schema": "localize-anything-evaluation-scorecard-read-v1",
                "state_dir": args.state_dir.as_posix(),
                "evaluation_scorecard": read_evaluation_scorecard(args.state_dir),
                "overall_claim": scorecard.get("overall_claim"),
            }
            return _emit_json(result, args.output)
        if args.command == "provider-execution-policy":
            result = build_provider_execution_policy(args.state_dir, read_json(args.input) if args.input else None, run_id=args.run_id) if args.input else read_provider_execution_policy(args.state_dir)
            return _emit_json({"protocol_version": "0.1", "schema": "localize-anything-provider-execution-policy-read-v1", "provider_execution_policy": result}, args.output)
        if args.command == "provider-handoff-request":
            result = build_provider_handoff_request(args.state_dir, read_json(args.input) if args.input else None, run_id=args.run_id) if args.input else read_provider_handoff_request(args.state_dir)
            return _emit_json({"protocol_version": "0.1", "schema": "localize-anything-provider-handoff-request-read-v1", "provider_handoff_request": result}, args.output)
        if args.command == "provider-execution-ledger":
            if args.input:
                append_provider_execution_ledger_entry(args.state_dir, read_json(args.input), run_id=args.run_id)
            return _emit_json({"protocol_version": "0.1", "schema": "localize-anything-provider-execution-ledger-read-v1", "records": read_provider_execution_ledger(args.state_dir)}, args.output)
        if args.command == "provider-result-intake":
            if args.input:
                record_provider_result_intake(args.state_dir, read_json(args.input), run_id=args.run_id)
            return _emit_json({"protocol_version": "0.1", "schema": "localize-anything-provider-result-intake-read-v1", "records": read_provider_result_intake(args.state_dir)}, args.output)
        if args.command == "provider-evidence-reconciliation":
            result = build_provider_evidence_reconciliation(args.state_dir, run_id=args.run_id)
            return _emit_json({"protocol_version": "0.1", "schema": "localize-anything-provider-evidence-reconciliation-read-v1", "provider_evidence_reconciliation": result}, args.output)
        if args.command == "record-human-review":
            result = record_human_review_evidence(args.state_dir, read_json(args.input), run_id=args.run_id)
            return _emit_json(result, args.output)
        if args.command == "human-review-evidence":
            result = {
                "protocol_version": "0.1",
                "schema": "localize-anything-human-review-evidence-list-v1",
                "state_dir": args.state_dir.as_posix(),
                "records": read_human_review_evidence(args.state_dir),
            }
            return _emit_json(result, args.output)
        if args.command == "claim-acceptance":
            result = build_claim_acceptance_decision(
                args.state_dir,
                requested_claims=args.claims or None,
                accepted_risk=_json_argument(args.accepted_risk_json, "accepted-risk-json") or {},
                run_id=args.run_id,
            )
            return _emit_json(result, args.output)
        if args.command == "signoff-record":
            if args.input:
                result = create_signoff_record(args.state_dir, read_json(args.input), run_id=args.run_id)
            else:
                result = read_signoff_record(args.state_dir)
            return _emit_json(result, args.output)
        if args.command == "workbench-review-queue":
            return _emit_json(build_workbench_review_queue(args.state_dir), args.output)
        if args.command == "workbench-claim-queue":
            return _emit_json(build_workbench_claim_queue(args.state_dir), args.output)
        if args.command == "workbench-signoff-summary":
            return _emit_json(build_workbench_signoff_summary(args.state_dir), args.output)
        if args.command == "workbench-action":
            return _emit_json(perform_workbench_action(args.state_dir, read_json(args.input), run_id=args.run_id), args.output)
        if args.command == "workbench-action-log":
            result = {
                "protocol_version": "0.1",
                "schema": "localize-anything-workbench-action-log-list-v1",
                "state_dir": args.state_dir.as_posix(),
                "records": read_workbench_action_log(args.state_dir),
            }
            return _emit_json(result, args.output)
        if args.command == "workbench-readiness-action-queue":
            return _emit_json(build_workbench_readiness_action_queue(args.state_dir, run_id=args.run_id), args.output)
        if args.command == "workbench-readiness-action":
            return _emit_json(perform_workbench_readiness_action(args.state_dir, read_json(args.input), run_id=args.run_id), args.output)
        if args.command == "workbench-readiness-action-log":
            result = {
                "protocol_version": "0.1",
                "schema": "localize-anything-workbench-readiness-action-log-list-v1",
                "state_dir": args.state_dir.as_posix(),
                "records": read_workbench_readiness_action_log(args.state_dir),
            }
            return _emit_json(result, args.output)
        if args.command == "workbench-readiness-action-result":
            return _emit_json(read_workbench_readiness_action_result(args.state_dir), args.output)
        if args.command == "workflow-plan":
            return _emit_json(
                build_workflow_run_plan(
                    args.state_dir,
                    workflow_mode=args.workflow_mode,
                    selected_stages=args.selected_stages or None,
                    scenario=args.scenario,
                    source_locale=args.source_locale,
                    target_locale=args.target_locale,
                    target_delivery_mode=args.target_delivery_mode,
                    run_id=args.run_id,
                ),
                args.output,
            )
        if args.command == "workflow-stage-status":
            return _emit_json(
                build_workflow_stage_status(
                    args.state_dir,
                    workflow_mode=args.workflow_mode,
                    selected_stages=args.selected_stages or None,
                ),
                args.output,
            )
        if args.command == "workflow-dependency-graph":
            return _emit_json(build_workflow_dependency_graph(args.state_dir), args.output)
        if args.command == "workflow-run":
            return _emit_json(
                run_workflow(
                    args.state_dir,
                    workflow_mode=args.workflow_mode,
                    selected_stages=args.selected_stages or None,
                    scenario=args.scenario,
                    source_locale=args.source_locale,
                    target_locale=args.target_locale,
                    target_delivery_mode=args.target_delivery_mode,
                    run_id=args.run_id,
                    idempotency_key=args.idempotency_key,
                    force_release_stale_lock=args.force_release_stale_lock,
                ),
                args.output,
            )
        if args.command == "workflow-execution-result":
            return _emit_json(read_workflow_execution_result(args.state_dir), args.output)
        if args.command == "workflow-readiness-summary":
            return _emit_json(build_workflow_readiness_summary(args.state_dir), args.output)
        if args.command == "workflow-lock-state":
            return _emit_json(read_workflow_lock_state(args.state_dir), args.output)
        if args.command == "workflow-checkpoint-log":
            return _emit_json(
                {
                    "protocol_version": "0.1",
                    "schema": "localize-anything-workflow-checkpoint-log-list-v1",
                    "records": read_workflow_checkpoint_log(args.state_dir),
                },
                args.output,
            )
        if args.command == "workflow-transaction-manifest":
            return _emit_json(read_workflow_transaction_manifest(args.state_dir), args.output)
        if args.command == "workflow-idempotency-report":
            return _emit_json(read_workflow_idempotency_report(args.state_dir), args.output)
        if args.command == "workflow-recovery-plan":
            return _emit_json(build_workflow_recovery_plan(args.state_dir), args.output)
        if args.command == "workflow-recovery-result":
            return _emit_json(read_workflow_recovery_result(args.state_dir), args.output)
        if args.command == "workflow-recover":
            return _emit_json(run_workflow_recovery(args.state_dir, recovery_action=args.recovery_action, run_id=args.run_id), args.output)
        if args.command == "workflow-resume-plan":
            return _emit_json(
                build_workflow_resume_plan(
                    args.state_dir,
                    requested_workflow_mode=args.workflow_mode,
                    resume_source=args.resume_source,
                    selected_stages=args.selected_stages or None,
                    run_id=args.run_id,
                ),
                args.output,
            )
        if args.command == "artifact-invalidation-report":
            return _emit_json(build_artifact_invalidation_report(args.state_dir), args.output)
        if args.command == "selective-recompute-plan":
            return _emit_json(
                build_selective_recompute_plan(
                    args.state_dir,
                    recompute_strategy=args.recompute_strategy,
                    target_workflow_mode=args.workflow_mode,
                    selected_stages=args.selected_stages or None,
                    trigger_source=args.trigger_source,
                    run_id=args.run_id,
                ),
                args.output,
            )
        if args.command == "selective-recompute-result":
            return _emit_json(read_selective_recompute_result(args.state_dir), args.output)
        if args.command == "incremental-workflow-summary":
            return _emit_json(build_incremental_workflow_summary(args.state_dir), args.output)
        if args.command == "workflow-resume":
            return _emit_json(
                resume_workflow(
                    args.state_dir,
                    requested_workflow_mode=args.workflow_mode,
                    resume_source=args.resume_source,
                    recompute_strategy=args.recompute_strategy,
                    selected_stages=args.selected_stages or None,
                    run_id=args.run_id,
                    idempotency_key=args.idempotency_key,
                    force_release_stale_lock=args.force_release_stale_lock,
                ),
                args.output,
            )
        if args.command == "selective-recompute":
            return _emit_json(
                run_selective_recompute(
                    args.state_dir,
                    recompute_strategy=args.recompute_strategy,
                    target_workflow_mode=args.workflow_mode,
                    selected_stages=args.selected_stages or None,
                    trigger_source=args.trigger_source,
                    run_id=args.run_id,
                    idempotency_key=args.idempotency_key,
                    force_release_stale_lock=args.force_release_stale_lock,
                ),
                args.output,
            )
        if args.command == "workbench-console":
            return _emit_text(render_workbench_console_html(args.state_dir), args.output)
        if args.command == "document-evidence-pack":
            return _emit_json(
                build_document_evidence_pack(
                    args.state_dir,
                    run_dir=args.run_dir,
                    scenario=args.scenario,
                    run_id=args.run_id,
                ),
                args.output,
            )
        if args.command == "workbench-document-evidence-queue":
            return _emit_json(build_workbench_document_evidence_queue(args.state_dir), args.output)
        if args.command == "record-document-decision":
            return _emit_json(record_document_decision(args.state_dir, read_json(args.input), run_id=args.run_id), args.output)
        if args.command == "document-decision-log":
            return _emit_json({"document_decision_log": read_document_decision_log(args.state_dir)}, args.output)
        if args.command == "record-leadership-review":
            return _emit_json(record_leadership_review_evidence(args.state_dir, read_json(args.input), run_id=args.run_id), args.output)
        if args.command == "leadership-review-evidence":
            return _emit_json({"leadership_review_evidence": read_leadership_review_evidence(args.state_dir)}, args.output)
        if args.command == "document-claim-resolution":
            return _emit_json(build_document_claim_resolution(args.state_dir, run_id=args.run_id), args.output)
        if args.command == "document-signoff-summary":
            return _emit_json(build_document_signoff_summary(args.state_dir, run_id=args.run_id), args.output)
        if args.command == "knowledge-pack-init":
            return _emit_json(
                init_knowledge_pack(
                    args.state_dir,
                    pack_id=args.pack_id,
                    name=args.name,
                    source_locale=args.source_locale,
                    target_locale=args.target_locale,
                    domains=args.domains,
                    privacy_mode=args.privacy_mode,
                    created_by=args.created_by,
                    quality_level=args.quality_level,
                    supported_scenarios=args.supported_scenarios,
                ),
                args.output,
            )
        if args.command == "knowledge-pack-export":
            return _emit_json(export_knowledge_pack(args.state_dir, args.pack_id), args.output)
        if args.command == "knowledge-pack":
            return _emit_json(read_knowledge_pack(args.state_dir, args.pack_id), args.output)
        if args.command == "knowledge-review-queue":
            return _emit_json(read_knowledge_review_queue(args.state_dir, args.pack_id), args.output)
        if args.command == "knowledge-review-decision":
            return _emit_json(record_knowledge_review_decision(args.state_dir, args.pack_id, read_json(args.input), run_id=args.run_id), args.output)
        if args.command == "knowledge-quality-report":
            return _emit_text(read_knowledge_quality_report(args.state_dir, args.pack_id), args.output)
        if args.command == "knowledge-pack-select":
            return _emit_json(
                select_knowledge_packs(
                    args.state_dir,
                    pack_ids=args.pack_ids,
                    pack_paths=args.pack_paths,
                    source_locale=args.source_locale,
                    target_locale=args.target_locale,
                    domains=args.domains,
                    scenario=args.scenario,
                    operating_mode=args.operating_mode,
                    selection_source=args.selection_source,
                    selected_by=args.selected_by,
                    allow_experimental=args.allow_experimental,
                    allowed_domains=args.allowed_domains,
                    allowed_scenarios=args.allowed_scenarios,
                    compatible_locales=args.compatible_locales,
                ),
                args.output,
            )
        if args.command == "knowledge-eligibility-report":
            return _emit_json(build_knowledge_eligibility_report(args.state_dir), args.output)
        if args.command == "working-context-packet":
            return _emit_json(build_working_context_packet(args.state_dir), args.output)
        if args.command == "knowledge-usage-report":
            return _emit_json(build_knowledge_usage_report(args.state_dir), args.output)
        if args.command == "constraint-application-audit":
            return _emit_json(build_constraint_application_audit(args.state_dir), args.output)
        if args.command == "knowledge-conflict-report":
            return _emit_json(build_knowledge_conflict_report(args.state_dir), args.output)
        if args.command == "knowledge-audit-enforcement-decision":
            return _emit_json(build_knowledge_audit_enforcement_decision(args.state_dir), args.output)
        if args.command == "workbench-knowledge-review-queue":
            return _emit_json(build_workbench_knowledge_review_queue(args.state_dir), args.output)
        if args.command == "record-knowledge-audit-resolution":
            return _emit_json(record_knowledge_audit_resolution(args.state_dir, read_json(args.input), run_id=args.run_id), args.output)
        if args.command == "knowledge-audit-resolution-log":
            return _emit_json(read_knowledge_audit_resolution_log(args.state_dir), args.output)
        if args.command == "record-knowledge-constraint-review":
            return _emit_json(record_knowledge_constraint_review_evidence(args.state_dir, read_json(args.input), run_id=args.run_id), args.output)
        if args.command == "knowledge-constraint-review-evidence":
            return _emit_json(read_knowledge_constraint_review_evidence(args.state_dir), args.output)
        if args.command == "knowledge-conflict-resolution":
            return _emit_json(build_knowledge_conflict_resolution(args.state_dir), args.output)
        if args.command == "knowledge-assurance-summary":
            return _emit_json(build_knowledge_assurance_summary(args.state_dir), args.output)
        if args.command == "draft-request":
            return _emit_json(create_draft_request(read_json(args.work_packet)), args.output)
        if args.command == "render-draft-prompt":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(render_draft_prompt(read_json(args.draft_request)), encoding="utf-8", newline="\n")
            return 0
        if args.command == "validate-generated":
            result = validate_generated_segments(read_json(args.work_packet), read_jsonl(args.generated))
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "import-generated-response":
            result = import_generated_response(
                read_json(args.work_packet),
                args.response.read_text(encoding="utf-8"),
                args.generated_output,
            )
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "import-generated-handoff":
            result = import_generated_handoff(read_json(args.handoff), args.response_dir, args.generated_output)
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "render-handoff-prompts":
            handoff = read_json(args.handoff)
            result = write_handoff_prompts(handoff, args.prompt_dir)
            if args.readme_output:
                response_dir = args.response_dir or args.prompt_dir.parent / "responses"
                args.readme_output.parent.mkdir(parents=True, exist_ok=True)
                args.readme_output.write_text(
                    render_generation_instructions(handoff, args.prompt_dir, response_dir, args.generated_output),
                    encoding="utf-8",
                    newline="\n",
                )
            return _emit_json(result, args.output)
        if args.command == "generation-handoff":
            result = create_generation_handoff(args.work_packet_dir, args.draft_request_dir, args.generated_dir, args.target_locale)
            return _emit_json(result, args.output)
        if args.command == "collect-generated":
            result = collect_generated_handoff(read_json(args.handoff), args.generated_output)
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "retry-handoff":
            return _emit_json(create_retry_handoff(read_json(args.handoff), read_json(args.generation_report), args.generated_dir), args.output)
        if args.command == "provider-generate":
            headers = {}
            if args.api_key_env:
                api_key = os.environ.get(args.api_key_env)
                if not api_key:
                    raise ValueError(f"Environment variable is not set: {args.api_key_env}")
                headers["Authorization"] = f"Bearer {api_key}"
            handoff_decision = None
            if args.state_dir:
                build_artifact_state(args.state_dir)
                handoff_decision = build_generation_handoff_decision(
                    args.state_dir,
                    provider_policy={"mode": "real_provider", "provider_controlled": True, "status": "safe"},
                )
            result = generate_handoff_with_http_provider(
                read_json(args.handoff),
                args.provider_url,
                args.generated_output,
                headers,
                args.timeout_seconds,
                handoff_decision,
            )
            _emit_json(result, args.output)
            return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1
        if args.command == "generate-chinese-draft":
            result = generate_chinese_draft_file(
                args.segments,
                args.generated_output,
                args.target_locale,
                args.provider,
                args.quality_claim,
            )
            _emit_json(result, args.output)
            return 0 if result["status"] == "pass" else 1
        if args.command == "deepseek-generate":
            from .deepseek_provider import generate_deepseek_batch_file

            result = generate_deepseek_batch_file(
                args.segments,
                args.generated_output,
                args.target_locale,
                args.source_locale,
                args.model,
            )
            _emit_json(result, args.output)
            return 0 if result["status"] == "pass" else 1
        if args.command == "stage-generated":
            return _emit_json(
                stage_generated(
                    args.project,
                    read_jsonl(args.generated),
                    args.staging_dir,
                    args.source_locale,
                    args.target_locale,
                    args.source_files,
                ),
                args.output,
            )
        if args.command == "localize-run":
            result = run_localize(
                args.project,
                args.source_locale,
                args.target_locales,
                args.source_files,
                args.output_root,
                args.run_id,
                args.max_segments,
                args.limit_tokens,
                args.handoff_only,
                args.generated_dir,
                args.generated,
                args.synthetic_draft,
                args.workflow_depth,
                args.preflight_mode,
                args.privacy_mode,
                args.data_classification,
                args.status,
                args.operating_mode,
                args.reference_policy,
                args.include_android_merged_resources,
                args.android_merged_resources,
                args.android_build_variant,
                args.android_overlay_output_name,
            )
            _emit_json(result, args.output)
            return 1 if result["status"] in {"generation_failed", "provider_generation_failed"} else 0
        if args.command == "agent-run":
            provider_headers = {}
            if args.api_key_env:
                api_key = os.environ.get(args.api_key_env)
                if not api_key:
                    raise ValueError(f"Environment variable is not set: {args.api_key_env}")
                provider_headers["Authorization"] = f"Bearer {api_key}"
            result = run_agent(
                args.project,
                args.target_locale,
                args.source_locale,
                args.source_files,
                args.output_root,
                args.run_id,
                args.max_segments,
                args.limit_tokens,
                args.responses_dir,
                args.generated_dir,
                args.generated,
                args.synthetic_draft,
                args.provider_url,
                provider_headers,
                args.provider_timeout_seconds,
                args.delivery_run_id,
                args.workflow_depth,
                args.preflight_mode,
                args.privacy_mode,
                args.data_classification,
                args.status,
                args.operating_mode,
                args.reference_policy,
            )
            _emit_json(result, args.output)
            return 1 if result["status"] in {"response_import_failed", "generation_failed"} else 0
        if args.command == "android-app-test":
            result = run_android_app_test(
                args.project,
                args.source_file,
                args.target_locale,
                args.source_locale,
                args.output_root,
                args.run_id,
                args.max_segments,
                args.limit_tokens,
                args.generated_dir,
                args.generated,
                args.local_chinese_draft,
                args.require_real_generation,
            )
            _emit_json(result, args.output)
            return 0 if result["status"] == "pass" else 1
        if args.command == "ui":
            from .ui import serve_ui

            serve_ui(args.host, args.port, args.open)
            return 0
        if args.command == "diff-segments":
            result = diff_segments(read_jsonl(args.previous), read_jsonl(args.current))
            return _emit_json(result, args.output)
        if args.command == "package":
            result = package_delivery(
                args.state_dir,
                args.staging_dir,
                args.output_root,
                args.qa_results,
                args.status,
                args.run_id,
            )
            return _emit_json(result, args.output)
        if args.command == "compile-mo":
            compile_segments_to_mo(read_jsonl(args.translations), args.output)
            return 0
        if args.command == "review-import":
            result = import_review(args.generated, args.reviewed, args.state_dir, args.run_id, args.target_locale)
            return _emit_json(result, args.output)
        if args.command == "review-sheet":
            return _emit_json(write_review_sheet(read_jsonl(args.generated), args.markdown_output, args.csv_output), args.output)
        if args.command == "llm-review-request":
            deterministic_findings = read_json(args.deterministic_report).get("items", []) if args.deterministic_report else []
            result = create_llm_review_request(
                read_jsonl(args.generated),
                args.source_locale,
                args.target_locale,
                deterministic_findings,
                args.run_id,
                args.max_segments,
            )
            if args.prompt_output:
                args.prompt_output.parent.mkdir(parents=True, exist_ok=True)
                args.prompt_output.write_text(render_llm_review_prompt(result), encoding="utf-8", newline="\n")
            return _emit_json(result, args.output)
        if args.command == "import-llm-review":
            result = import_llm_review_response(
                read_json(args.request),
                args.response.read_text(encoding="utf-8"),
                args.review_output,
            )
            return _emit_json(result, args.output)
        if args.command == "sign-off":
            scope = {
                "locales": args.locales,
                "content_types": args.content_types,
                "files": args.files,
                "batch_ids": args.batch_ids,
            }
            result = create_acceptance(args.manifest, args.accepted_by, scope, args.output, args.allow_draft)
            if not args.output:
                json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
                sys.stdout.write("\n")
            return 0
        if args.command == "plan-apply":
            result = create_apply_plan(args.delivery_dir, args.project)
            if args.markdown_output:
                args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
                args.markdown_output.write_text(render_apply_plan_markdown(result), encoding="utf-8", newline="\n")
            return _emit_json(result, args.output)
        if args.command == "apply-delivery":
            return _emit_json(execute_apply(args.delivery_dir, args.project, args.confirm_run_id, args.backup_root), args.output)
        if args.command == "delivery-dashboard":
            result = build_delivery_dashboard(args.delivery_dir)
            if args.markdown_output:
                args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
                args.markdown_output.write_text(render_dashboard_markdown(result), encoding="utf-8", newline="\n")
            return _emit_json(result, args.output)
        if args.command == "delivery-decision":
            result = create_delivery_decision_report(args.delivery_dir, args.project)
            if args.markdown_output:
                args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
                args.markdown_output.write_text(render_delivery_decision_markdown(result), encoding="utf-8", newline="\n")
            return _emit_json(result, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


def _emit_json(value: Any, output: Path | None) -> int:
    if output:
        write_json(output, value)
    else:
        json.dump(value, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    return 0


def _emit_text(value: str, output: Path | None) -> int:
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(value, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(value)
        if not value.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def _json_argument(value: str | None, label: str) -> dict[str, Any] | None:
    if not value:
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    return parsed
