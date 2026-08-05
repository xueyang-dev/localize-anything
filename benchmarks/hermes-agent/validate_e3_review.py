"""Validate the Hermes French E3 review package (and optionally a completed review).

Default mode validates the shipped handoff package (Mode A invariants):
manifest hash, canonical-id coverage, mandatory sets, source/target fidelity,
placeholder/expression fidelity, empty reviewer and user columns, deterministic
line endings/encoding, and absence of machine paths or personal data.

``--decisions FILE`` additionally validates a completed reviewer CSV and a
``--metadata FILE`` JSON attestation before Mode B import.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

from build_e3_review import (
    E3_DIR,
    REAL_IMPORTS,
    REPORTS,
    REVIEW_SHEET_COLUMNS,
    SURFACES,
    extract_yaml,
    extract_ts,
)
from common import BENCH_ROOT, BLIND


REVIEWER_COLUMNS = [
    "review_status",
    "native_quality_rating",
    "reviewer_target_fr",
    "reviewer_note",
    "terminology_decision",
    "needs_bilingual_check",
]
USER_COLUMNS = ["user_decision", "final_accepted_target"]
VALID_STATUSES = {"", "approved", "approved_with_note", "needs_revision", "needs_bilingual_check", "reject", "defer"}
MACHINE_PATH_PATTERNS = [re.compile(r"/Users(/|\\|$)|/private/(var|tmp)|C:\\Users\\\\"), re.compile(r"/tmp/[A-Za-z0-9._-]+")]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_imports() -> dict[str, dict[str, str]]:
    imports: dict[str, dict[str, str]] = {}
    for surface in ("yaml", "web", "desktop"):
        path = REAL_IMPORTS / f"{surface}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            imports[entry["segment_id"]] = {
                "surface": surface,
                "target": entry["target"],
                "classification": entry.get("classification", ""),
            }
    return imports


def load_extraction_index() -> dict[str, dict[str, object]]:
    index: dict[str, dict[str, object]] = {}
    for surface, surface_dir, source_rel, _ in SURFACES:
        extractor = extract_ts if surface in ("web", "desktop") else extract_yaml
        for segment in extractor(BLIND / surface_dir / source_rel, "en", source_rel):
            context = segment.get("context", {})
            constraints = segment.get("constraints", {})
            index[segment["segment_id"]] = {
                "surface": surface,
                "pointer": context.get("pointer", ""),
                "source": str(segment.get("source", "")),
                "placeholders": sorted(constraints.get("placeholders", [])),
                "template_expressions": sorted(
                    list(constraints.get("template_expressions", []))
                    + list(context.get("template_expressions", []))
                ),
                "context": json.dumps(context, ensure_ascii=False, sort_keys=True),
            }
    return index


def validate_package(require_decision_gate_silent: bool = False) -> list[str]:
    problems: list[str] = []

    required_files = [
        E3_DIR / "e3-review-sheet.csv",
        E3_DIR / "e3-review-sheet.md",
        E3_DIR / "e3-review-schema.json",
        E3_DIR / "e3-review-manifest.json",
        E3_DIR / "e3-review-package-summary.json",
        E3_DIR / "REVIEWER-INSTRUCTIONS-FR.md",
        E3_DIR / "COORDINATOR-INSTRUCTIONS.md",
        E3_DIR / "reviewer-metadata-template.json",
    ]
    for path in required_files:
        if not path.is_file():
            problems.append(f"missing package file: {path.name}")
    if problems:
        return problems

    manifest = json.loads((E3_DIR / "e3-review-manifest.json").read_text(encoding="utf-8"))
    if sha256(E3_DIR / "e3-review-sheet.csv") != manifest.get("review_sheet_sha256"):
        problems.append("review sheet sha256 does not match the manifest")

    imports = load_imports()
    index = load_extraction_index()

    with (E3_DIR / "e3-review-sheet.csv").open(encoding="utf-8", newline="") as handle:
        reader = list(csv.DictReader(handle))
    if not reader:
        problems.append("review sheet is empty")
        return problems
    if list(reader[0].keys()) != REVIEW_SHEET_COLUMNS:
        problems.append(f"review sheet header mismatch: {list(reader[0].keys())}")

    rows = list(reader)
    ids = [row["segment_id"] for row in rows]
    if len(ids) != len(set(ids)):
        problems.append(f"duplicate segment ids: {len(ids) - len(set(ids))}")

    known_ids = set(imports)
    unknown = sorted(set(ids) - known_ids)
    if unknown:
        problems.append(f"unknown segment ids: {unknown[:5]}")

    reasons = {name: 0 for name in ("e2_sample", "identity_retention", "terminology", "native_naturalness_sample")}
    surfaces_present = set()
    for row in rows:
        surfaces_present.add(row["surface"])
        for key in reasons:
            if key in (row.get("selection_reasons") or "").split("|"):
                reasons[key] += 1
        segment_id = row["segment_id"]
        if segment_id not in index:
            problems.append(f"row for {segment_id} has no extraction entry")
            continue
        index_row = index[segment_id]
        if row["source_en"] != index_row["source"]:
            problems.append(f"source mismatch for {segment_id}")
        if segment_id not in imports:
            continue
        if row["current_target_fr"] != imports[segment_id]["target"]:
            problems.append(f"target mismatch for {segment_id}")
        if not row["context"]:
            problems.append(f"missing context for {segment_id}")
        expected_placeholders = ",".join(index_row["placeholders"])
        if row["placeholders"] != expected_placeholders:
            problems.append(f"placeholder mismatch for {segment_id}: {row['placeholders']!r} != {expected_placeholders!r}")
        expected_exprs = ",".join(index_row["template_expressions"])
        if row["template_expressions"] != expected_exprs:
            problems.append(f"template expression mismatch for {segment_id}")

    if reasons["e2_sample"] < 180:
        problems.append(f"mandatory E2 set incomplete: {reasons['e2_sample']}/180")
    if reasons["identity_retention"] < 203:
        problems.append(f"mandatory identity set incomplete: {reasons['identity_retention']}/203")
    if reasons["terminology"] < 20:
        problems.append(f"mandatory terminology set incomplete: {reasons['terminology']}/20")
    if reasons["native_naturalness_sample"] < 120:
        problems.append(f"additional naturalness set incomplete: {reasons['native_naturalness_sample']}/120")
    if surfaces_present != {"yaml", "web", "desktop"}:
        problems.append(f"surfaces not all represented: {sorted(surfaces_present)}")

    # reviewer and user columns must be empty in the shipped package
    for row in rows:
        for column in REVIEWER_COLUMNS + USER_COLUMNS:
            if (row.get(column) or "").strip():
                problems.append(f"shipped package has prefilled {column} on {row['segment_id']}")

    # deterministic line endings / encoding
    raw = (E3_DIR / "e3-review-sheet.csv").read_bytes()
    if b"\r" in raw or b"\x00" in raw:
        problems.append("review sheet has non-LF line endings or NUL bytes")

    # machine paths and personal data
    blob = " ".join(" ".join(row.values()) for row in rows)
    for pattern in MACHINE_PATH_PATTERNS:
        if pattern.search(blob):
            problems.append(f"machine-specific path pattern found: {pattern.pattern}")
    emails = EMAIL_RE.findall(blob)
    if emails:
        problems.append(f"email-like personal data found: {emails[:3]}")

    # summary consistency
    summary = json.loads((E3_DIR / "e3-review-package-summary.json").read_text(encoding="utf-8"))
    if summary.get("rows") != len(rows):
        problems.append(f"package summary rows ({summary.get('rows')}) != sheet rows ({len(rows)})")
    return problems


def validate_decisions(csv_path: Path, metadata_path: Path) -> list[str]:
    problems: list[str] = validate_package()
    if not metadata_path.is_file():
        problems.append("reviewer metadata file is required for a completed review")
        return problems
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not metadata.get("native_language_attestation") or "native" not in str(
        metadata.get("native_language_attestation", "")
    ).lower():
        problems.append("reviewer native-language attestation missing")
    if not metadata.get("french_locale_or_region"):
        problems.append("french locale/region missing")
    if metadata.get("ai_assistance_used") is not True and metadata.get("ai_assistance_used") is not False:
        problems.append("ai_assistance_used must be boolean true/false")

    index = load_extraction_index()
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if list(rows[0].keys()) != REVIEW_SHEET_COLUMNS:
        problems.append("decisions header mismatch")
        return problems
    reviewed = 0
    for row in rows:
        status = row.get("review_status", "")
        if status not in VALID_STATUSES:
            problems.append(f"{row['segment_id']}: invalid review_status {status!r}")
        if status and status != "defer":
            reviewed += 1
        if status == "needs_revision" and not (row.get("reviewer_target_fr") or "").strip():
            problems.append(f"{row['segment_id']}: needs_revision without reviewer_target_fr")
        if row.get("user_decision") or row.get("final_accepted_target"):
            problems.append(f"{row['segment_id']}: user columns must remain empty")
        segment_id = row["segment_id"]
        if segment_id not in index:
            continue
        source = index[segment_id]["source"]
        candidate = row.get("reviewer_target_fr") or row.get("current_target_fr") or ""
        source_tokens = set(re.findall(r"\{[A-Za-z_][A-Za-z0-9_]*\}", source))
        candidate_tokens = set(re.findall(r"\{[A-Za-z_][A-Za-z0-9_]*\}", candidate))
        if source_tokens != candidate_tokens:
            problems.append(f"{segment_id}: reviewer edit damages placeholders")
        source_exprs = re.findall(r"\$\{[^}]*\}", source)
        candidate_exprs = re.findall(r"\$\{[^}]*\}", candidate)
        if source_exprs != candidate_exprs:
            problems.append(f"{segment_id}: reviewer edit damages template expressions")
    if reviewed < 180 + 203 + 20:
        problems.append(f"mandatory rows not all reviewed: {reviewed} reviewed")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the E3 review package")
    parser.add_argument("--decisions", type=Path, help="validate a completed review CSV")
    parser.add_argument("--metadata", type=Path, help="reviewer metadata JSON (with --decisions)")
    args = parser.parse_args()

    if args.decisions:
        problems = validate_decisions(args.decisions, args.metadata or Path())
    else:
        problems = validate_package()
    if problems:
        for problem in problems[:80]:
            print("PROBLEM:", problem)
        raise SystemExit(f"e3 review validation failed with {len(problems)} problem(s)")
    print("e3 review validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
