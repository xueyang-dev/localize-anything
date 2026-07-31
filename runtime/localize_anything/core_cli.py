from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import bootstrap_glossary, check, prepare_review, report, scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="localize", description="Minimal deterministic core for Localize Anything", allow_abbrev=False)
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    scan_parser = commands.add_parser("scan", help="Inventory files and establish Project Memory")
    scan_parser.add_argument("project", type=Path)
    scan_parser.add_argument("--source-locale")
    scan_parser.add_argument("--target-locale")
    scan_parser.add_argument("--source", action="append", dest="source_files")

    glossary_parser = commands.add_parser("glossary", help="Manage the canonical Glossary")
    glossary_commands = glossary_parser.add_subparsers(dest="glossary_command", required=True)
    bootstrap_parser = glossary_commands.add_parser("bootstrap", help="Create conservative candidate concepts from declared sources")
    bootstrap_parser.add_argument("project", type=Path)

    check_parser = commands.add_parser("check", help="Run deterministic structure and locked-glossary checks")
    check_parser.add_argument("project", type=Path)
    check_parser.add_argument("--target", action="append", required=True, dest="target_files")

    review_parser = commands.add_parser("review", help="Prepare or record an independent review")
    review_parser.add_argument("project", type=Path)
    review_parser.add_argument("--target", action="append", required=True, dest="target_files")
    review_parser.add_argument("--findings", type=Path)

    report_parser = commands.add_parser("report", help="Summarize deterministic checks, review, and human confirmations")
    report_parser.add_argument("project", type=Path)
    report_parser.add_argument("--confirm", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "scan":
            result = scan(args.project, source_locale=args.source_locale, target_locale=args.target_locale, source_files=args.source_files)
        elif args.command == "glossary":
            result = bootstrap_glossary(args.project)
        elif args.command == "check":
            result = check(args.project, args.target_files)
        elif args.command == "review":
            result = prepare_review(args.project, args.target_files, args.findings)
        else:
            result = report(args.project, args.confirm)
    except (OSError, SyntaxError, ValueError) as exc:
        print(f"localize: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if args.command == "check" and result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
