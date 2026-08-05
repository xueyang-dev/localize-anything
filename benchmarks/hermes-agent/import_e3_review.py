"""Import a completed Hermes French E3 native-speaker review (Mode B).

This script only runs when a genuine completed human review exists:
  --decisions  completed e3-review-sheet.csv (as returned by the reviewer)
  --metadata   reviewer-metadata.json (attestation)

It validates everything, preserves the original submission as immutable
evidence, applies approved ``needs_revision`` targets to the canonical imports
(updating the manifest with an E3 revision section), and writes E3 evidence
reports. It never fabricates decisions and it never fills user columns.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from common import EVIDENCE, REAL_IMPORTS, REPORTS, write_json
from validate_e3_review import REVIEW_SHEET_COLUMNS, validate_decisions


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def classify_retention_outcome(row: dict[str, str], identity_import_ids: set[str]) -> str:
    """Classify an identity-retention row after native review."""
    segment_id = row["segment_id"]
    status = row.get("review_status", "")
    if segment_id not in identity_import_ids:
        return "not_an_identity_target"
    if status in ("reject",):
        return "rejected_retention"
    if row.get("needs_bilingual_check", "") == "true":
        return "needs_bilingual_check"
    if status == "needs_revision" and (row.get("reviewer_target_fr") or "").strip():
        return "translate_now"
    if status in ("approved", "approved_with_note", ""):
        return "confirmed_retention"
    return "context_dependent"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a completed French E3 review")
    parser.add_argument("--decisions", type=Path, required=True, help="completed review CSV")
    parser.add_argument("--metadata", type=Path, required=True, help="reviewer metadata JSON")
    parser.add_argument("--import-dir", type=Path, default=EVIDENCE / "e3-imported", help="immutable evidence dir")
    args = parser.parse_args()

    problems = validate_decisions(args.decisions, args.metadata)
    if problems:
        raise SystemExit(f"e3 import refused: {len(problems)} problem(s): " + "; ".join(problems[:10]))

    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    reviewer_id = metadata.get("reviewer_id", "unknown")

    # Preserve the original submission as immutable evidence.
    import_dir = args.import_dir
    import_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.decisions, import_dir / "completed-e3-review.csv")
    shutil.copy2(args.metadata, import_dir / "reviewer-metadata.json")

    rows = _load_csv(args.decisions)
    by_id = {row["segment_id"]: row for row in rows}

    # Load canonical imports and identity ids.
    imports: dict[str, dict[str, Any]] = {}
    identity_ids: set[str] = set()
    for surface in ("yaml", "web", "desktop"):
        for line in (REAL_IMPORTS / f"{surface}.jsonl").read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            imports[entry["segment_id"]] = entry
    source_map: dict[str, str] = {}
    from common import BLIND
    from build_e3_review import SURFACES, extract_ts, extract_yaml

    for surface, surface_dir, source_rel, _ in SURFACES:
        extractor = extract_ts if surface in ("web", "desktop") else extract_yaml
        for segment in extractor(BLIND / surface_dir / source_rel, "en", source_rel):
            source_map[segment["segment_id"]] = str(segment.get("source", ""))
    for segment_id, entry in imports.items():
        if source_map.get(segment_id) and entry["target"] == source_map[segment_id]:
            identity_ids.add(segment_id)

    revisions_applied: list[dict[str, Any]] = []
    identity_outcomes: Counter[str] = Counter()
    for row in rows:
        segment_id = row["segment_id"]
        target_new = (row.get("reviewer_target_fr") or "").strip()
        current = imports.get(segment_id)
        if current and row.get("review_status") == "needs_revision" and target_new:
            if current["target"] != target_new:
                revisions_applied.append(
                    {
                        "segment_id": segment_id,
                        "surface": current.get("surface", row.get("surface", "")),
                        "pointer": row.get("pointer", ""),
                        "old_target": current["target"],
                        "new_target": target_new,
                        "reviewer_note": row.get("reviewer_note", ""),
                    }
                )
        identity_outcomes[classify_retention_outcome(row, identity_ids)] += 1

    # Apply corrections to canonical imports and refresh the manifest hashes.
    changed: dict[str, list[str]] = {"yaml": [], "web": [], "desktop": []}
    for revision in revisions_applied:
        segment_id = revision["segment_id"]
        entry = imports.get(segment_id)
        if entry is None:
            continue
        surface = entry.get("surface")
        if surface not in changed:
            continue
        entry["target"] = revision["new_target"]
        changed[surface].append(segment_id)

    manifest_path = REAL_IMPORTS / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for surface, segment_ids in changed.items():
        if not segment_ids:
            continue
        path = REAL_IMPORTS / f"{surface}.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for entry_id in sorted(imports):
                if imports[entry_id].get("surface") == surface:
                    handle.write(json.dumps(imports[entry_id], ensure_ascii=False) + "\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["surfaces"][surface]["sha256"] = digest
        manifest["surfaces"][surface]["segment_count"] = sum(
            1 for entry_id in imports if imports[entry_id].get("surface") == surface
        )
    manifest["e3_revision"] = {
        "round": "E3-native-speaker-r1",
        "reviewer_id": reviewer_id,
        "revisions_applied": len(revisions_applied),
        "changed_surface_ids": {surface: len(ids) for surface, ids in changed.items() if ids},
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    counts_by_status = Counter(row.get("review_status", "") or "unreviewed" for row in rows)
    counts_by_rating = Counter((row.get("native_quality_rating", "") or "").strip() for row in rows)
    summary = {
        "benchmark_id": "hermes-agent",
        "artifact": "e3-review-summary",
        "reviewer_type": "native-language reviewer",
        "human_review": True,
        "professional_localization_review": False,
        "reviewer_id": reviewer_id,
        "sample_size": len(rows),
        "counts_by_surface": dict(Counter((row.get("surface", "") or "") for row in rows)),
        "counts_by_status": dict(counts_by_status),
        "counts_by_rating": dict(counts_by_rating),
        "revisions_proposed": sum(1 for row in rows if row.get("review_status") == "needs_revision"),
        "revisions_applied": len(revisions_applied),
        "needs_bilingual_check": sum(1 for row in rows if row.get("needs_bilingual_check") == "true"),
        "rejected": counts_by_status.get("reject", 0),
        "deferred": counts_by_status.get("defer", 0),
        "identity_retention_changes": identity_outcomes.get("translate_now", 0),
        "glossary_changes": 0,
        "forbidden_term_changes": 0,
        "user_accepted": False,
    }
    write_json(summary, REPORTS / "e3-review-summary.json")
    csv_path = REPORTS / "e3-review-result.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=REVIEW_SHEET_COLUMNS
            + ["old_target", "applied_revision", "retention_outcome"],
            lineterminator="\n",
        )
        writer.writeheader()
        applied = {revision["segment_id"]: revision for revision in revisions_applied}
        for row in rows:
            segment_id = row["segment_id"]
            extra = {
                "old_target": applied.get(segment_id, {}).get("old_target", row.get("current_target_fr", "")),
                "applied_revision": "1" if segment_id in applied else "0",
                "retention_outcome": classify_retention_outcome(row, identity_ids),
            }
            writer.writerow({**row, **extra})
    write_json(revisions_applied, REPORTS / "e3-applied-changes.json")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
