"""Deterministic Hermes French E3 native-speaker review package generator.

Builds ``evidence/e3-review/`` from:
  - the canonical committed imports (evidence/real-imports/*.jsonl);
  - the deterministic English extraction of the pinned upstream source
    (work/blind) and the official French references (work/source);
  - the committed E2 review sheet, retained-string adjudication, and
    terminology adjudication.

The package always contains four mandatory sources:
   A) all 180 E2 sample rows;
   B) all 203 retained identity strings;
   C) all 20 terminology decisions;
   D) >= 120 additional translated non-identity rows (>= 40 per surface),
      selected deterministically (tier ordering, then segment-id sorted
      stride sampling) — no seeded randomness.
Rows are deduplicated by segment_id and every selection reason is retained.

Note: this script needs the prepared benchmark environment
(`prepare.py source` + `prepare.py blind`), see the benchmark README.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from common import (
    BENCH_ROOT,
    BLIND,
    REPORTS,
    SOURCE,
    EVIDENCE,
    REAL_IMPORTS,
    read_json,
)

sys.path.insert(0, str(BENCH_ROOT))

from runtime.localize_anything.structured_adapter import extract_segments as extract_yaml  # noqa: E402
from runtime.localize_anything.typescript_locale_adapter import extract_segments as extract_ts  # noqa: E402


E3_DIR = EVIDENCE / "e3-review"
SURFACES = [
    ("yaml", "yaml", "locales/en.yaml", "locales/fr.yaml"),
    ("web", "web", "web/src/i18n/en.ts", "web/src/i18n/fr.ts"),
    ("desktop", "desktop", "apps/desktop/src/i18n/en.ts", None),
]

REVIEW_SHEET_COLUMNS = [
    "segment_id",
    "surface",
    "pointer",
    "selection_reasons",
    "risk_level",
    "issue_category",
    "source_en",
    "current_target_fr",
    "existing_official_fr",
    "context",
    "placeholders",
    "template_expressions",
    "current_retention_classification",
    "proposed_action",
    "review_status",
    "native_quality_rating",
    "reviewer_target_fr",
    "reviewer_note",
    "terminology_decision",
    "needs_bilingual_check",
    "user_decision",
    "final_accepted_target",
]

HIGH_RISK_POINTER_MARKERS = (
    "approval",
    "deny",
    "danger",
    "error",
    "fail",
    "warning",
    "delete",
    "clear",
    "reset",
    "overwrite",
    "discard",
    "remove",
    "archive",
    "sudo",
    "secret",
    "empty",
    "tooltip",
    "hint",
    "placeholder",
    "settings",
    "gateway",
    "unavailable",
    "reject",
)

HIGH_RISK_SOURCE_MARKERS = (
    "⚠",
    "❌",
    "✅",
    "⛔",
    "could not",
    "cannot",
    "failed",
    "failure",
    "warning",
    "delete",
    "remove",
    "reset",
    "overwrite",
    "danger",
    "denied",
    "approval",
    "allowed",
)


def risk_level_for(pointer: str, source: str) -> str:
    lower_pointer = pointer.lower()
    lower_source = source.lower()
    if any(marker in lower_pointer for marker in HIGH_RISK_POINTER_MARKERS) or any(
        marker in lower_source for marker in HIGH_RISK_SOURCE_MARKERS
    ):
        return "high"
    if len(source) >= 120 or "${" in source or re.search(r"\{[A-Za-z_][A-Za-z0-9_]*\}", source):
        return "medium"
    return "low"


def issue_category_for(row: dict[str, Any]) -> str:
    if "identity_retention" in row["selection_reasons"]:
        return "retained_english"
    if "terminology" in row["selection_reasons"]:
        return "terminology"
    if row.get("template_expressions") or row.get("placeholders"):
        return "placeholder_template"
    pointer = row["pointer"].lower()
    source = row["source_en"].lower()
    if any(marker in pointer for marker in ("approval", "deny", "danger", "sudo", "secret", "reject")):
        return "action_safety"
    if any(marker in pointer for marker in ("delete", "clear", "reset", "overwrite", "discard", "remove", "archive")):
        return "action_safety"
    if any(marker in pointer for marker in ("error", "fail", "warning", "unavailable", "recovery")):
        return "error_recovery"
    if re.search(r"([!?·…—«»‘’“”]|%|/|→|↻|⏱)", source) and not any(
        marker in pointer for marker in ("approval",)
    ):
        return "punctuation_typography"
    return "naturalness"


def stride_sample(items: list[Any], count: int) -> list[Any]:
    if count <= 0 or not items:
        return []
    if len(items) <= count:
        return list(items)
    step = len(items) / count
    return [items[int(i * step)] for i in range(count)]


def normalized(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: entry.get(key, "") for key in REVIEW_SHEET_COLUMNS}


def main() -> int:

    # ---- canonical imports ------------------------------------------------
    imports: dict[str, dict[str, Any]] = {}
    for surface in ("yaml", "web", "desktop"):
        for line in (REAL_IMPORTS / f"{surface}.jsonl").read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            imports[entry["segment_id"]] = {
                "segment_id": entry["segment_id"],
                "surface": surface,
                "target": entry["target"],
                "classification": entry.get("classification", ""),
                "classification_note": entry.get("classification_note", ""),
            }

    # ---- deterministic extraction index -----------------------------------
    segments_by_surface: dict[str, list[dict[str, Any]]] = {}
    pointer_to_segment: dict[str, dict[str, Any]] = {}
    for surface, surface_dir, source_rel, _ in SURFACES:
        source_path = BLIND / surface_dir / source_rel
        extractor = extract_ts if surface in ("web", "desktop") else extract_yaml
        extracted = extractor(source_path, "en", source_rel)
        segments_by_surface[surface] = extracted
    segment_index: dict[str, dict[str, Any]] = {}
    for surface, extracted in segments_by_surface.items():
        for segment in extracted:
            segment_id = segment["segment_id"]
            context = segment.get("context", {})
            constraints = segment.get("constraints", {})
            segment_index[segment_id] = {
                "segment_id": segment_id,
                "surface": surface,
                "pointer": context.get("pointer", ""),
                "source": str(segment.get("source", "")),
                "placeholders": sorted(constraints.get("placeholders", [])),
                "template_expressions": sorted(
                    list(constraints.get("template_expressions", []))
                    + list(context.get("template_expressions", []))
                ),
                "function_valued": bool(context.get("function_pointer")) or context.get("ts_kind") == "function",
                "ts_kind": context.get("ts_kind", ""),
                "context_blob": json.dumps(context, ensure_ascii=False, sort_keys=True),
            }
            pointer_to_segment.setdefault(context.get("pointer", ""), segment_id)

    # ---- official French references (context only) ------------------------
    official_fr: dict[str, dict[str, str]] = {surface: {} for surface, _, _, _ in SURFACES}
    for surface, _, _, reference_rel in SURFACES:
        if not reference_rel:
            continue
        reference_path = SOURCE / reference_rel
        if not reference_path.is_file():
            continue
        extractor = extract_ts if surface in ("web", "desktop") else extract_yaml
        try:
            for segment in extractor(reference_path, "fr", reference_rel):
                pointer = segment.get("context", {}).get("pointer", "")
                official_fr[surface][pointer] = str(segment.get("source", ""))
        except Exception as exc:  # reference is context-only; never fatal
            print(f"warning: could not extract official fr reference for {surface}: {exc}")

    # ---- committed review artifacts ---------------------------------------
    e2_sheet: list[dict[str, str]] = list(csv.DictReader((REPORTS / "e2-review-sheet.csv").open(encoding="utf-8")))
    retained_rows: list[dict[str, str]] = list(
        csv.DictReader((REPORTS / "retained-string-adjudication.csv").open(encoding="utf-8"))
    )
    terminology_rows: list[dict[str, str]] = list(
        csv.DictReader((REPORTS / "terminology-adjudication.csv").open(encoding="utf-8"))
    )

    previously_corrected = {row["segment_id"] for row in e2_sheet if row.get("verdict") == "needs_revision"}

    # ---- row builders -----------------------------------------------------
    def base_row(segment_id: str, selection_reasons: list[str]) -> dict[str, Any]:
        index = segment_index[segment_id]
        imp = imports[segment_id]
        surface = index["surface"]
        official = official_fr[surface].get(index["pointer"], "")
        return {
            "segment_id": segment_id,
            "surface": surface,
            "pointer": index["pointer"],
            "selection_reasons": selection_reasons,
            "risk_level": risk_level_for(index["pointer"], index["source"]),
            "issue_category": "",
            "source_en": index["source"],
            "current_target_fr": imp["target"],
            "existing_official_fr": official,
            "context": index["context_blob"],
            "placeholders": index["placeholders"],
            "template_expressions": index["template_expressions"],
            "current_retention_classification": imp["classification"],
            "proposed_action": "",
            "review_status": "",
            "native_quality_rating": "",
            "reviewer_target_fr": "",
            "reviewer_note": "",
            "terminology_decision": "",
            "needs_bilingual_check": "",
            "user_decision": "",
            "final_accepted_target": "",
        }

    rows: dict[str, dict[str, Any]] = {}

    # Set A: existing E2 sample (180)
    for row in e2_sheet:
        segment_id = row["segment_id"]
        if segment_id not in segment_index or segment_id not in imports:
            raise SystemExit(f"E2 row missing from extraction/imports: {segment_id}")
        reasons = ["e2_sample"]
        if segment_id in previously_corrected:
            reasons.append("previously_corrected")
        base = base_row(segment_id, reasons)
        base["issue_category"] = issue_category_for(base)
        base["proposed_action"] = "accept_current"
        base["context"] += f"\n# e2_verdict: {row.get('verdict', '')}\n# e2_note: {row.get('note', '')}"
        rows[segment_id] = base

    # Set B: retained identity strings (203)
    for row in retained_rows:
        segment_id = row["segment_id"]
        if segment_id not in segment_index or segment_id not in imports:
            raise SystemExit(f"identity row missing from extraction/imports: {segment_id}")
        base = base_row(segment_id, ["identity_retention"])
        base["issue_category"] = "retained_english"
        base["proposed_action"] = "accept_current"
        base["context"] += (
            f"\n# candidate_classification: {row.get('candidate_classification', '')}\n"
            f"# approved_classification: {row.get('approved_classification', '')}\n"
            f"# classification_note: {row.get('classification_note', '')}"
        )
        existing = rows.get(segment_id)
        if existing:
            existing["selection_reasons"].append("identity_retention")
            existing["issue_category"] = "retained_english"
        else:
            rows[segment_id] = base

    # Set C: terminology decisions (20) — anchored to real segments
    term_to_segment: dict[str, str] = {}
    for term_row in terminology_rows:
        term = term_row["term"]
        candidates = [
            segment_id
            for segment_id, index in segment_index.items()
            if re.search(rf"\b{re.escape(term)}\b", index["source"], re.IGNORECASE)
        ]
        if not candidates:
            raise SystemExit(f"terminology term has no representative segment: {term}")
        candidates.sort()
        segment_id = candidates[0]
        term_to_segment[term] = segment_id
        base = base_row(segment_id, ["terminology"])
        base["issue_category"] = "terminology"
        base["proposed_action"] = "accept_current"
        base["context"] += (
            f"\n# terminology_term: {term}\n"
            f"# e2_decision: {term_row.get('decision', '')}\n"
            f"# yaml_fr: {term_row.get('yaml_fr', '')}\n"
            f"# web_fr: {term_row.get('web_fr', '')}\n"
            f"# desktop_fr: {term_row.get('desktop_fr', '')}\n"
            f"# note: {term_row.get('note', '')}"
        )
        existing = rows.get(segment_id)
        if existing:
            existing["selection_reasons"].append("terminology")
            existing["issue_category"] = "terminology"
        else:
            rows[segment_id] = base

    # Set D: additional translated non-identity naturalness rows (>= 120)
    additional_needed = 120
    per_surface_needed = 40
    additional: dict[str, list[str]] = {surface: [] for surface, _, _, _ in SURFACES}
    for surface, _, _, _ in SURFACES:
        candidates: list[str] = []
        for segment_id, index in segment_index.items():
            if index["surface"] != surface:
                continue
            if segment_id in rows:
                continue
            imp = imports.get(segment_id)
            if not imp:
                continue
            if imp["target"] == index["source"] or not index["source"]:
                continue  # identity rows handled in Set B; empty sources excluded
            candidates.append(segment_id)

        def sort_key(segment_id: str) -> tuple[int, int, str]:
            index = segment_index[segment_id]
            return (
                0 if risk_level_for(index["pointer"], index["source"]) == "high" else 1,
                -len(index["source"]),
                segment_id,
            )

        candidates.sort(key=sort_key)
        selected = stride_sample(candidates, max(per_surface_needed, 0))
        additional[surface] = selected

    for surface, selected in additional.items():
        for segment_id in selected:
            index = segment_index[segment_id]
            base = base_row(segment_id, ["native_naturalness_sample"])
            if risk_level_for(index["pointer"], index["source"]) == "high":
                base["selection_reasons"].append("high_risk")
            if index["pointer"].startswith(("/sessions/", "/config/", "/models/", "/status/", "/app/nav/")):
                base["selection_reasons"].append("runtime_visible")
            base["issue_category"] = issue_category_for(base)
            base["proposed_action"] = "accept_current"
            rows.setdefault(segment_id, base)

    total_selected = sum(len(a) for a in additional.values())
    if total_selected < additional_needed:
        print(f"warning: only {total_selected} additional rows selected (need >= {additional_needed})")

    # ---- tally & write ----------------------------------------------------
    final_rows: list[dict[str, Any]] = []
    for segment_id in sorted(rows):
        row = rows[segment_id]
        row["selection_reasons"] = "|".join(dict.fromkeys(row["selection_reasons"]))
        row["placeholders"] = ",".join(row["placeholders"])
        row["template_expressions"] = ",".join(row["template_expressions"])
        final_rows.append(normalized(row))

    from collections import Counter

    counts_by_surface = Counter(row["surface"] for row in final_rows if row["surface"] != "terminology")
    counts_by_reason: Counter[str] = Counter()
    for row in final_rows:
        for reason in (row["selection_reasons"] or "").split("|"):
            if reason:
                counts_by_reason[reason] += 1
    counts_by_risk = Counter(row["risk_level"] for row in final_rows)

    E3_DIR.mkdir(parents=True, exist_ok=True)
    review_path = E3_DIR / "e3-review-sheet.csv"
    with review_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_SHEET_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in final_rows:
            writer.writerow(row)

    digest = hashlib.sha256(review_path.read_bytes()).hexdigest()

    md_columns = [
        "segment_id",
        "surface",
        "pointer",
        "selection_reasons",
        "risk_level",
        "issue_category",
        "source_en",
        "current_target_fr",
        "existing_official_fr",
        "placeholders",
        "template_expressions",
        "current_retention_classification",
        "proposed_action",
    ]

    def md_cell(value: str) -> str:
        return (value or "").replace("|", "\\|").replace("\n", " ")[:200]

    md_lines = [
        "# Hermes French E3 native-speaker review sheet",
        "",
        f"Total rows: **{len(final_rows)}** (deduplicated by segment_id). See "
        "`e3-review-sheet.csv` for the full schema (context, reviewer and user "
        "columns); this page is a browsable rendering.",
        "",
        "| " + " | ".join(md_columns) + " |",
        "|" + "---|" * len(md_columns),
    ]
    for row in final_rows:
        md_lines.append("| " + " | ".join(md_cell(row[col]) for col in md_columns) + " |")
    (E3_DIR / "e3-review-sheet.md").write_text(
        "\n".join(md_lines) + "\n", encoding="utf-8", newline="\n"
    )

    manifest = {
        "benchmark_id": "hermes-agent",
        "artifact": "e3-review-manifest",
        "target_locale": "fr",
        "upstream": {
            "repository": "https://github.com/NousResearch/hermes-agent",
            "commit": "91937a6dc3ffbbe2f3be91a500f0ecf962c4cf53",
        },
        "review_round": "E3-native-speaker-r1",
        "sample": {
            "e2_sample_rows": len(e2_sheet),
            "identity_retention_rows": len(retained_rows),
            "terminology_rows": len(terminology_rows),
            "additional_naturalness_rows": total_selected,
            "additional_naturalness_needed": additional_needed,
            "rows_before_dedup": len(e2_sheet) + len(retained_rows) + len(terminology_rows) + total_selected,
            "rows_after_dedup": len(final_rows),
            "counts_by_surface": {k: v for k, v in sorted(counts_by_surface.items())},
            "counts_by_reason": {k: v for k, v in sorted(counts_by_reason.items())},
            "counts_by_risk": {k: v for k, v in sorted(counts_by_risk.items())},
        },
        "review_sheet_sha256": digest,
        "selection_method": (
            "Set A: committed E2 sheet (180); Set B: committed retained-string adjudication (203); "
            "Set C: committed terminology adjudication (20, anchored to representative segments); "
            "Set D: >= 40 additional translated non-identity rows per surface, tiered by risk/length "
            "then sorted by segment_id with stride sampling (deterministic, no RNG)"
        ),
        "reviewer_columns_empty_by_design": True,
        "user_columns_empty_by_design": True,
        "notes": [
            "Reviewer/user decision columns are deliberately empty in the shipped package.",
            "All segment_ids are canonical import ids; terminology rows anchor to a representative segment.",
        ],
    }
    (E3_DIR / "e3-review-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    summary = {
        "benchmark_id": "hermes-agent",
        "artifact": "e3-review-package-summary",
        "rows": len(final_rows),
        "counts_by_surface": dict(sorted(counts_by_surface.items())),
        "counts_by_reason": dict(sorted(counts_by_reason.items())),
        "counts_by_risk": dict(sorted(counts_by_risk.items())),
        "review_sheet_sha256": digest,
    }
    (E3_DIR / "e3-review-package-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
