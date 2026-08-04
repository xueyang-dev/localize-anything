"""Retention-string adjudication for identity targets.

Imported entries may carry a *candidate* classification, but that is not an
approval.  This script collects every identity target (target == source) into
a review sheet, then applies separately recorded decisions (reviewer type:
AI-assisted bilingual review) that can approve, reject, or request revision.
Only ``approved`` rows suppress the E1 untranslated-English finding.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

from common import (
    BENCH_ROOT,
    CONFIG,
    REPORTS,
    RUNS,
    RETENTION_CLASSIFICATIONS,
    REVIEW_STATUSES,
    read_jsonl,
    write_json,
)

sys.path.insert(0, str(BENCH_ROOT))

SURFACES = [
    ("yaml", "yaml"),
    ("web", "typescript-web"),
    ("desktop", "typescript-desktop"),
]

CSV_HEADER = [
    "segment_id",
    "surface",
    "source",
    "target",
    "candidate_classification",
    "candidate_classification_note",
    "approved_classification",
    "classification_note",
    "review_status",
    "reviewer_type",
]


def collect_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for surface, run in SURFACES:
        for segment in read_jsonl(RUNS / run / "generated.jsonl"):
            source = str(segment.get("source", ""))
            target = str(segment.get("target", ""))
            if source and target == source:
                rows.append(
                    {
                        "segment_id": segment["segment_id"],
                        "surface": surface,
                        "source": source,
                        "target": target,
                        "candidate_classification": segment.get("candidate_classification", ""),
                        "candidate_classification_note": segment.get("candidate_classification_note", ""),
                        "approved_classification": "",
                        "classification_note": "",
                        "review_status": "",
                        "reviewer_type": "",
                    }
                )
    rows.sort(key=lambda row: (row["surface"], row["segment_id"]))
    return rows


def write_review_sheet(rows: list[dict[str, Any]]) -> None:
    csv_path = REPORTS / "retained-string-adjudication.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_decisions(path: Path) -> dict[str, dict[str, str]]:
    decisions: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            decisions[row["segment_id"]] = {
                key: (row.get(key) or "").strip()
                for key in ("approved_classification", "classification_note", "review_status", "reviewer_type")
            }
    return decisions


def validate_decisions(rows: list[dict[str, Any]], decisions: dict[str, dict[str, str]]) -> list[str]:
    problems: list[str] = []
    row_ids = {row["segment_id"] for row in rows}
    for segment_id, decision in decisions.items():
        if segment_id not in row_ids:
            problems.append(f"unknown segment_id in decisions: {segment_id}")
            continue
        status = decision["review_status"]
        if status not in REVIEW_STATUSES:
            problems.append(f"{segment_id}: invalid review_status {status!r}")
            continue
        classification = decision["approved_classification"]
        if classification and classification not in RETENTION_CLASSIFICATIONS:
            problems.append(f"{segment_id}: invalid approved_classification {classification!r}")
        if not decision["reviewer_type"]:
            problems.append(f"{segment_id}: reviewer_type is required")
        if status == "approved":
            if classification not in RETENTION_CLASSIFICATIONS:
                problems.append(f"{segment_id}: approved retention requires an allowed classification")
            if not decision["classification_note"]:
                problems.append(f"{segment_id}: approved retention requires a non-empty classification_note")
    for row in rows:
        if row["segment_id"] not in decisions:
            problems.append(f"missing decision for {row['segment_id']}")
    return problems


def merge_decisions(rows: list[dict[str, Any]], decisions: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    for row in rows:
        decision = decisions.get(row["segment_id"])
        if decision:
            row.update(decision)
    return rows


def write_adjudication(rows: list[dict[str, Any]]) -> None:
    summary = {
        "protocol_version": CONFIG["protocol_version"],
        "benchmark_id": CONFIG["id"],
        "artifact": "retained-string-adjudication",
        "reviewer_type": "AI-assisted bilingual review",
        "human_review": False,
        "identity_segments": len(rows),
        "by_surface": {},
        "by_status": {},
        "rows": rows,
    }
    for row in rows:
        summary["by_surface"][row["surface"]] = summary["by_surface"].get(row["surface"], 0) + 1
        status = row["review_status"] or "unreviewed"
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
    write_json(summary, REPORTS / "retained-string-adjudication.json")
    write_review_sheet(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect or apply retained-string adjudication")
    parser.add_argument("--collect", action="store_true", help="collect identity targets into the review sheet")
    parser.add_argument("--decisions", type=Path, help="CSV with filled decision columns to validate and apply")
    args = parser.parse_args()

    if args.collect:
        rows = collect_rows()
        write_review_sheet(rows)
        write_adjudication(rows)
        print(f"collected {len(rows)} identity targets across {len(SURFACES)} surfaces")
        return 0

    if args.decisions:
        rows = collect_rows()
        decisions = read_decisions(args.decisions)
        problems = validate_decisions(rows, decisions)
        if problems:
            for problem in problems[:50]:
                print("PROBLEM:", problem)
            raise SystemExit(f"adjudication validation failed with {len(problems)} problem(s)")
        rows = merge_decisions(rows, decisions)
        write_adjudication(rows)
        print(f"applied {len(rows)} adjudication rows")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
