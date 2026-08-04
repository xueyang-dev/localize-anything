"""Track 1 (controlled): YAML CLI/gateway catalog benchmark for fr."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from common import (
    report_markdown,
    BENCH_ROOT,
    BLIND,
    CONFIG,
    REFERENCE,
    REPORTS,
    RUNS,
    STAGING,
    assign_batches,
    apply_engineering_draft,
    batch_plan_for,
    flatten_yaml,
    import_translated_segments,
    load_curated,
    read_jsonl,
    segment_review_flags,
    write_json,
    write_jsonl,
    write_prompts,
)

sys.path.insert(0, str(BENCH_ROOT))

from runtime.localize_anything.structured_adapter import (  # noqa: E402
    extract_segments,
    rebuild,
    validate_pair,
)


SURFACE = "yaml"
SOURCE_FILE = "locales/en.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Hermes YAML catalog benchmark")
    parser.add_argument("--mode", choices=["engineering", "import"], default="engineering")
    parser.add_argument("--import-segments", type=Path)
    args = parser.parse_args()

    run_dir = RUNS / SURFACE
    run_dir.mkdir(parents=True, exist_ok=True)
    blind_source = BLIND / SURFACE / SOURCE_FILE
    if not blind_source.is_file():
        raise ValueError("blind workspace missing; run `python prepare.py blind` first")

    # Phase 3: deterministic extraction.
    segments = extract_segments(blind_source, "en", SOURCE_FILE)
    repeated = extract_segments(blind_source, "en", SOURCE_FILE)
    extraction = {
        "segments": len(segments),
        "deterministic": [s["segment_id"] for s in segments] == [s["segment_id"] for s in repeated],
        "duplicate_ids": len({s["segment_id"] for s in segments}) != len(segments),
        "source_hash": _sha256(blind_source),
    }
    assign_batches(segments)
    write_jsonl(segments, run_dir / "segments.jsonl")
    plan = batch_plan_for(SURFACE)
    write_json(plan, run_dir / "batch-plan.json")
    write_prompts(segments, run_dir, SURFACE, plan)

    # Phase 5: generation (engineering draft or provider import).
    if args.mode == "import":
        if not args.import_segments or not args.import_segments.is_file():
            raise ValueError("--import-segments FILE is required with --mode import")
        generated = import_translated_segments(segments, args.import_segments)
        generation_mode = "imported"
    else:
        generated = apply_engineering_draft(segments, load_curated(SURFACE))
        generation_mode = "engineering_fixture_only"
    curated = sum(1 for s in generated if s.get("generation_mode") == "synthetic_curated_draft")
    write_jsonl(generated, run_dir / "generated.jsonl")

    # Phase 6: staging (rebuild only).
    staging_dir = STAGING / SURFACE
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged_path = staging_dir / "fr.yaml"
    rebuild(blind_source, generated, staged_path)

    # Phase 7: deterministic QA.
    qa = validate_pair(blind_source, staged_path)
    source_unchanged = _sha256(blind_source) == extraction["source_hash"]
    write_json(qa, run_dir / "qa.json")

    # Phase 8: automated semantic review (E1 only).
    review = segment_review_flags(generated)
    write_json(review, run_dir / "semantic-review.json")

    # Reference comparison (only after `prepare.py reference` reveals them).
    reference_comparison: dict[str, object] | None = None
    official = REFERENCE / SURFACE / "fr.yaml"
    if official.is_file():
        reference_comparison = _compare_reference(blind_source, staged_path, official)
        write_json(reference_comparison, run_dir / "reference-comparison.json")

    report = {
        "protocol_version": CONFIG["protocol_version"],
        "benchmark_id": CONFIG["id"],
        "surface": "yaml_cli_gateway",
        "track": "controlled",
        "commit": CONFIG["upstream"]["commit"],
        "target_locale": CONFIG["target_locale"],
        "generation": {
            "mode": generation_mode,
            "quality_claim": "engineering_fixture_only",
            "provider": CONFIG["generation"]["provider"],
            "curated_slice_segments": curated,
            "identity_segments": len(generated) - curated,
        },
        "extraction": extraction,
        "batch_plan": plan,
        "qa": {"status": qa["status"], "summary": qa["summary"]},
        "semantic_review": review["summary"],
        "staging": {"path": staged_path.as_posix(), "source_unchanged": source_unchanged},
        "reference_comparison": reference_comparison,
    }
    REPORTS.mkdir(exist_ok=True)
    write_json(report, REPORTS / "yaml-benchmark-report.json")
    write_json(report_markdown(report, "yaml-benchmark-report.md"), REPORTS / "yaml-benchmark-report.md", raw=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _compare_reference(blind_source: Path, staged: Path, official: Path) -> dict[str, object]:
    staged_flat = flatten_yaml(staged)
    official_flat = flatten_yaml(official)
    source_flat = flatten_yaml(blind_source)
    official_missing = sorted(set(staged_flat) - set(official_flat))
    staged_missing = sorted(set(official_flat) - set(staged_flat))
    official_english_stragglers = sorted(
        key for key, value in official_flat.items() if value == source_flat.get(key)
    )
    staged_english_stragglers = sorted(
        key for key, value in staged_flat.items() if value == source_flat.get(key)
    )
    overlap = sorted(
        key
        for key in staged_flat.keys() & official_flat.keys()
        if staged_flat[key] != source_flat.get(key) and staged_flat[key] == official_flat[key]
    )
    return {
        "official_is_reference_not_ground_truth": True,
        "official_key_missing_vs_staged": official_missing,
        "staged_key_missing_vs_official": staged_missing,
        "official_untranslated_english_stragglers": len(official_english_stragglers),
        "staged_untranslated_english_segments": len(staged_english_stragglers),
        "identical_translated_values": len(overlap),
        "identical_translated_sample": overlap[:10],
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
