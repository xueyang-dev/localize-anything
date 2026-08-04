"""Regenerate the real-evidence verification report from current state.

Every gate is derived from committed artifacts (evidence/real-imports,
reports/*) plus the current runs; the report fails closed when imports are
absent, hashes mismatch, engineering fixtures are present, unapproved
identity strings remain, evidence paths are broken, or build validation
fails.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from common import (
    BENCH_ROOT,
    CONFIG,
    EVIDENCE,
    REAL_IMPORTS,
    REPORTS,
    RUNS,
    report_markdown,
    read_json,
    read_jsonl,
    verify_evidence_references,
    write_json,
)

sys.path.insert(0, str(BENCH_ROOT))

SURFACES = [
    ("yaml", "yaml", "yaml-benchmark-report.json"),
    ("web", "typescript-web", "typescript-web-benchmark-report.json"),
    ("desktop", "typescript-desktop", "typescript-desktop-benchmark-report.json"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest_path = REAL_IMPORTS / "manifest.json"
    gates: dict[str, Any] = {}
    problems: list[str] = []

    # --- committed import artifacts ---
    artifacts_present = manifest_path.is_file() and all(
        (REAL_IMPORTS / f"{surface}.jsonl").is_file() for surface, _, _ in SURFACES
    )
    gates["committed_import_artifacts_present"] = artifacts_present
    if not artifacts_present:
        problems.append("committed import artifacts missing (evidence/real-imports/)")

    hashes_match = False
    expected_counts_match = False
    if artifacts_present:
        manifest = read_json(manifest_path)
        manifest_surfaces = manifest["surfaces"]
        hashes_match = all(
            manifest_surfaces[surface]["sha256"] == sha256(REAL_IMPORTS / f"{surface}.jsonl")
            for surface, _, _ in SURFACES
        )
        expected_counts_match = all(
            manifest_surfaces[surface]["segment_count"] == sum(
                1 for _ in open(REAL_IMPORTS / f"{surface}.jsonl", encoding="utf-8")
            )
            for surface, _, _ in SURFACES
        )
        if not hashes_match:
            problems.append("committed import hashes do not match the manifest")
        if not expected_counts_match:
            problems.append("committed import segment counts do not match the manifest")
    gates["committed_import_hashes_match"] = hashes_match
    gates["expected_segment_counts_match"] = expected_counts_match

    # --- id coverage and accounting from current runs ---
    no_unknown_ids = True
    no_missing_ids = True
    engineering_zero = True
    claims: set[str] = set()
    unapproved_identity = 0
    identity_total = 0
    for surface, run, report_name in SURFACES:
        import_ids = {row["segment_id"] for row in read_jsonl(REAL_IMPORTS / f"{surface}.jsonl")}
        extraction_ids = {row["segment_id"] for row in read_jsonl(RUNS / run / "segments.jsonl")}
        if not extraction_ids <= import_ids:
            no_unknown_ids = False
            problems.append(f"{surface}: imports contain unknown segment ids")
        if not import_ids <= extraction_ids:
            no_missing_ids = False
            problems.append(f"{surface}: imports miss extracted segment ids")
        generated = read_jsonl(RUNS / run / "generated.jsonl")
        identity = [row for row in generated if str(row.get("source", "")) and row["target"] == row["source"]]
        identity_total += len(identity)
        unapproved_identity += sum(1 for row in identity if row.get("review_status") != "approved")
        if any(row.get("quality_claim") == "engineering_fixture_only" for row in generated):
            engineering_zero = False
            problems.append(f"{surface}: engineering fixture segments present")
        claims.update(str(row.get("quality_claim")) for row in generated)
        report = read_json(REPORTS / report_name)
        accounting = report["generation"]["accounting"]
        if accounting["engineering_fixture_segments"] != 0:
            engineering_zero = False
    gates["no_unknown_segment_ids"] = no_unknown_ids
    gates["no_missing_segment_ids"] = no_missing_ids
    gates["engineering_fixture_segments_zero"] = engineering_zero
    gates["quality_claim_uniform"] = claims == {"host_agent_generated"}
    if claims != {"host_agent_generated"}:
        problems.append(f"quality claims are not uniform host_agent_generated: {sorted(claims)}")

    # --- generation metadata completeness ---
    metadata = read_json(REPORTS / "real-generation-metadata.json")
    producer_ok = (
        metadata.get("producer_type") == "host_agent"
        and metadata.get("producer_model") in (None, "unknown")
        and metadata.get("retry_count") in (None, "unknown")
        and metadata.get("retry_count_tracked") is False
    )
    gates["generation_metadata_complete_or_explicitly_unknown"] = producer_ok
    if not producer_ok:
        problems.append("real-generation-metadata.json contains speculative or incomplete producer fields")

    # --- retention adjudication ---
    adjudication = read_json(REPORTS / "retained-string-adjudication.json")
    adjudicated_ids = {
        row["segment_id"]
        for row in adjudication.get("rows", [])
        if row.get("review_status") == "approved"
    }
    unclassified_identity_segments_zero = unapproved_identity == 0
    retained_identity_segments_adjudicated = (
        unapproved_identity == 0
        and identity_total == len(adjudicated_ids)
        and identity_total == len(adjudication.get("rows", []))
        and adjudication.get("human_review") is False
        and adjudication.get("reviewer_type") == "AI-assisted bilingual review"
    )
    gates["unclassified_identity_segments_zero"] = unclassified_identity_segments_zero
    gates["retained_identity_segments_adjudicated"] = retained_identity_segments_adjudicated
    if unclassified_identity_segments_zero is False:
        problems.append(f"{unapproved_identity} identity segments lack approved adjudication")
    if retained_identity_segments_adjudicated is False:
        problems.append("retained identity adjudication is incomplete or mislabeled")

    # --- QA / build / E2 ---
    qa_pass = all(read_json(REPORTS / name)["qa"]["status"] == "pass" for _, _, name in SURFACES)
    gates["post_edit_QA_pass"] = qa_pass
    if not qa_pass:
        problems.append("post-edit deterministic QA did not pass on all surfaces")

    build = read_json(REPORTS / "build-validation.json")
    build_pass = build.get("status") == "pass" and build.get("summary", {}).get("failed", 1) == 0
    gates["build_validation_pass"] = build_pass
    if not build_pass:
        problems.append("build validation did not pass")

    e2 = read_json(REPORTS / "e2-review-summary.json")
    e2_ai = e2.get("reviewer_type") == "AI-assisted bilingual review" and e2.get("human_review") is False
    e2_zero = e2.get("blocking", -1) == 0
    gates["E2_AI_review_recorded"] = e2_ai
    gates["E2_blocking_zero"] = e2_zero
    if not (e2_ai and e2_zero):
        problems.append("E2 review record missing, mislabeled, or has blocking findings")

    visual = read_json(REPORTS / "visual-smoke-report.json")
    gates["runtime_DOM_smoke_recorded"] = visual.get("runtime_smoke_recorded") is True and visual.get(
        "dom_text_verified"
    ) is True
    gates["visual_layout_review_completed"] = visual.get("visual_layout_review_completed") is True
    gates["human_review"] = False
    if visual.get("visual_layout_review_completed") is not False:
        problems.append("visual layout review must be false (not completed)")

    gates["overall_pass"] = not problems
    report = {
        "protocol_version": CONFIG["protocol_version"],
        "benchmark_id": CONFIG["id"],
        "artifact": "real-evidence-verification",
        "gates": gates,
        "identity_segments_total": identity_total,
        "problems": problems,
    }
    # Write first so the freshly regenerated report is what gets scanned.
    write_json(report, REPORTS / "real-evidence-verification.json")
    write_json(
        report_markdown(report, "real-evidence-verification.md"),
        REPORTS / "real-evidence-verification.md",
        raw=True,
    )
    # --- evidence path integrity (after regeneration) ---
    path_problems = verify_evidence_references()
    gates["evidence_paths_resolve"] = not path_problems
    if path_problems:
        report["gates"]["evidence_paths_resolve"] = False
        report["problems"].extend(path_problems)
        report["gates"]["overall_pass"] = False
        write_json(report, REPORTS / "real-evidence-verification.json")
        write_json(
            report_markdown(report, "real-evidence-verification.md"),
            REPORTS / "real-evidence-verification.md",
            raw=True,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
