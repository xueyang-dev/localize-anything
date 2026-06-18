from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .acceptance import create_acceptance
from .android_strings_adapter import extract_segments as extract_android_strings
from .android_strings_adapter import rebuild as rebuild_android_strings
from .android_strings_adapter import stage_rebuild as stage_android_strings
from .android_strings_adapter import validate_pair as validate_android_strings
from .apply import create_apply_plan, execute_apply, render_apply_plan_markdown
from .contracts import validate_adapter_tree
from .dashboard import build_delivery_dashboard, render_dashboard_markdown
from .delivery import package_delivery
from .generation import (
    collect_generated_handoff,
    create_draft_request,
    create_generation_handoff,
    import_generated_handoff,
    import_generated_response,
    render_draft_prompt,
    render_generation_instructions,
    validate_generated_segments,
    write_handoff_prompts,
)
from .gettext_adapter import extract_segments as extract_po_segments
from .gettext_adapter import rebuild as rebuild_po
from .gettext_adapter import validate_pair as validate_po_pair
from .io_utils import read_json, read_jsonl, write_json, write_jsonl
from .ios_strings_adapter import extract_segments as extract_ios_strings
from .ios_strings_adapter import rebuild as rebuild_ios_strings
from .ios_strings_adapter import stage_rebuild as stage_ios_strings
from .ios_strings_adapter import validate_pair as validate_ios_strings
from .json_adapter import extract_segments, rebuild, validate_pair
from .markup_adapter import extract_segments as extract_markup_segments
from .markup_adapter import rebuild as rebuild_markup
from .markup_adapter import validate_pair as validate_markup_pair
from .mo_compiler import compile_segments_to_mo
from .planning import create_batch_plan
from .project import initialize_project, inspect_project
from .retrieval import build_work_packet
from .review import import_review
from .review_sheet import write_review_sheet
from .run import run_localize
from .schema_validation import validate_protocol_tree
from .segments import diff_segments
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="localize-anything", description="Reference runtime for the Localize Anything protocol")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Discover files supported by alpha adapters")
    inspect_parser.add_argument("project", type=Path)
    inspect_parser.add_argument("--output", type=Path)

    preflight_parser = subparsers.add_parser("preflight", help="Initialize deterministic project state and inventory")
    preflight_parser.add_argument("project", type=Path)
    preflight_parser.add_argument("--source-locale", required=True)
    preflight_parser.add_argument("--source-file", action="append", required=True, dest="source_files")
    preflight_parser.add_argument("--target-locale", action="append", required=True, dest="target_locales")
    preflight_parser.add_argument("--workflow-depth", choices=["ask", "fast", "standard", "high_assurance"], default="ask")
    preflight_parser.add_argument("--preflight-mode", choices=["auto", "full", "layered", "light", "skip_deep"], default="auto")
    preflight_parser.add_argument("--privacy-mode", choices=["standard", "minimal_disclosure", "local_only"], default="standard")
    preflight_parser.add_argument("--data-classification", choices=["public", "internal", "confidential", "restricted"], default="internal")
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
    plan_parser.add_argument("--output", type=Path)

    retrieve_parser = subparsers.add_parser("retrieve", help="Build an ephemeral working context packet")
    retrieve_parser.add_argument("plan", type=Path)
    retrieve_parser.add_argument("segments", type=Path)
    retrieve_parser.add_argument("state_dir", type=Path)
    retrieve_parser.add_argument("--batch-id", required=True)
    retrieve_parser.add_argument("--target-locale", required=True)
    retrieve_parser.add_argument("--limit-tokens", type=int, default=4000)
    retrieve_parser.add_argument("--output", type=Path)

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
    localize_run_parser.add_argument("--workflow-depth", default="ask", choices=["ask", "fast", "standard", "high_assurance"])
    localize_run_parser.add_argument("--preflight-mode", default="auto", choices=["auto", "light", "full", "layered", "skip_deep"])
    localize_run_parser.add_argument("--privacy-mode", default="standard")
    localize_run_parser.add_argument("--data-classification", default="internal")
    localize_run_parser.add_argument("--status", choices=["draft_package", "review_ready", "blocked"], default="draft_package")
    localize_run_parser.add_argument("--output", type=Path)

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

    execute_apply_parser = subparsers.add_parser("apply-delivery", help="Apply a delivery after explicit run-id confirmation")
    execute_apply_parser.add_argument("delivery_dir", type=Path)
    execute_apply_parser.add_argument("project", type=Path)
    execute_apply_parser.add_argument("--confirm-run-id", required=True)
    execute_apply_parser.add_argument("--backup-root", type=Path)
    execute_apply_parser.add_argument("--output", type=Path)

    dashboard_parser = subparsers.add_parser("delivery-dashboard", help="Summarize a delivery for developers and translators")
    dashboard_parser.add_argument("delivery_dir", type=Path)
    dashboard_parser.add_argument("--markdown-output", type=Path)
    dashboard_parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_project(args.project)
            return _emit_json(result, args.output)
        if args.command == "preflight":
            result = initialize_project(
                args.project,
                args.source_locale,
                args.source_files,
                args.target_locales,
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
            result = create_batch_plan(read_jsonl(args.segments), args.source_locale, args.target_locales, args.max_segments)
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
            )
            _emit_json(result, args.output)
            return 1 if result["status"] == "generation_failed" else 0
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
