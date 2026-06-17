from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .acceptance import create_acceptance
from .apply import create_apply_plan
from .contracts import validate_adapter_tree
from .delivery import package_delivery
from .gettext_adapter import extract_segments as extract_po_segments
from .gettext_adapter import rebuild as rebuild_po
from .gettext_adapter import validate_pair as validate_po_pair
from .io_utils import read_json, read_jsonl, write_json, write_jsonl
from .json_adapter import extract_segments, rebuild, validate_pair
from .markup_adapter import extract_segments as extract_markup_segments
from .markup_adapter import rebuild as rebuild_markup
from .markup_adapter import validate_pair as validate_markup_pair
from .mo_compiler import compile_segments_to_mo
from .planning import create_batch_plan
from .project import initialize_project, inspect_project
from .retrieval import build_work_packet
from .review import import_review
from .schema_validation import validate_protocol_tree
from .segments import diff_segments
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
    apply_parser.add_argument("--output", type=Path)
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
            return _emit_json(create_apply_plan(args.delivery_dir, args.project), args.output)
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
