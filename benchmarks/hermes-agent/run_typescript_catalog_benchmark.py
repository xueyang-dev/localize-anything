"""Track 1 (controlled): Web + Desktop TypeScript catalog benchmark for fr."""

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
    COPY,
    REFERENCE,
    REPORTS,
    RUNS,
    STAGING,
    assign_batches,
    apply_engineering_draft,
    batch_plan_for,
    import_translated_segments,
    load_curated,
    segment_review_flags,
    write_json,
    write_jsonl,
    write_prompts,
)

sys.path.insert(0, str(BENCH_ROOT))

from runtime.localize_anything.typescript_locale_adapter import (  # noqa: E402
    extract_segments,
    rebuild,
    validate_pair,
)


SURFACES = {
    "web": {"source": "web/src/i18n/en.ts", "output": "fr.ts", "reference": "web/src/i18n/fr.ts"},
    "desktop": {"source": "apps/desktop/src/i18n/en.ts", "output": "fr.ts", "reference": None},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Hermes TypeScript catalog benchmark")
    parser.add_argument("--surface", choices=["web", "desktop"], required=True)
    parser.add_argument("--mode", choices=["engineering", "import"], default="engineering")
    parser.add_argument("--import-segments", type=Path)
    args = parser.parse_args()

    spec = SURFACES[args.surface]
    run_dir = RUNS / f"typescript-{args.surface}"
    run_dir.mkdir(parents=True, exist_ok=True)
    blind_source = BLIND / args.surface / spec["source"]
    if not blind_source.is_file():
        raise ValueError("blind workspace missing; run `python prepare.py blind` first")

    segments = extract_segments(blind_source, "en", spec["source"])
    repeated = extract_segments(blind_source, "en", spec["source"])
    extraction = {
        "segments": len(segments),
        "deterministic": [s["segment_id"] for s in segments] == [s["segment_id"] for s in repeated],
        "duplicate_ids": len({s["segment_id"] for s in segments}) != len(segments),
        "source_hash": _sha256(blind_source),
        "function_valued": sum(bool(s["context"].get("function_pointer")) for s in segments),
        "template_expression_bearing": sum(bool(s["constraints"]["template_expressions"]) for s in segments),
    }
    assign_batches(segments)
    write_jsonl(segments, run_dir / "segments.jsonl")
    plan = batch_plan_for(args.surface)
    write_json(plan, run_dir / "batch-plan.json")
    write_prompts(segments, run_dir, args.surface, plan)

    if args.mode == "import":
        if not args.import_segments or not args.import_segments.is_file():
            raise ValueError("--import-segments FILE is required with --mode import")
        generated = import_translated_segments(segments, args.import_segments)
        generation_mode = "imported"
    else:
        generated = apply_engineering_draft(segments, load_curated(args.surface))
        generation_mode = "engineering_fixture_only"
    curated = sum(1 for s in generated if s.get("generation_mode") == "synthetic_curated_draft")
    quality_claims = sorted({str(s.get("quality_claim", "unknown")) for s in generated})
    preferred_claims = [c for c in quality_claims if c != "engineering_fixture_only"]
    write_jsonl(generated, run_dir / "generated.jsonl")

    staging_dir = STAGING / args.surface
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged_path = staging_dir / spec["output"]
    rebuild(blind_source, generated, staged_path, export_name=CONFIG["target_locale"])

    qa = validate_pair(blind_source, staged_path)
    source_unchanged = _sha256(blind_source) == extraction["source_hash"]
    write_json(qa, run_dir / "qa.json")
    review = segment_review_flags(generated)
    write_json(review, run_dir / "semantic-review.json")

    reference_comparison: dict[str, object] | None = None
    if spec["reference"]:
        official = REFERENCE / args.surface / Path(spec["reference"]).name
        if official.is_file():
            reference_comparison = _compare_reference(blind_source, staged_path, official)
            write_json(reference_comparison, run_dir / "reference-comparison.json")
    else:
        reference_comparison = {"official_reference_exists": False}

    apply_plan = None
    if args.surface == "desktop":
        apply_plan = desktop_apply_plan(staged_path)
        write_json(apply_plan, run_dir / "desktop-apply-plan.json")

    report = {
        "protocol_version": CONFIG["protocol_version"],
        "benchmark_id": CONFIG["id"],
        "surface": "desktop" if args.surface == "desktop" else "web_dashboard",
        "track": "controlled",
        "commit": CONFIG["upstream"]["commit"],
        "target_locale": CONFIG["target_locale"],
        "generation": {
            "mode": generation_mode,
            "quality_claim": preferred_claims[0] if preferred_claims else quality_claims[0],
            "quality_claims": quality_claims,
            "provider": CONFIG["generation"]["provider"],
            "curated_slice_segments": curated,
            "identity_segments": len(generated) - curated if generation_mode == "engineering_fixture_only" else 0,
            "imported_segments": len(generated) if generation_mode == "imported" else 0,
        },
        "extraction": extraction,
        "batch_plan": plan,
        "qa": {"status": qa["status"], "summary": qa["summary"]},
        "semantic_review": review["summary"],
        "staging": {"path": staged_path.as_posix(), "source_unchanged": source_unchanged},
        "reference_comparison": reference_comparison,
        "apply_plan": apply_plan,
    }
    REPORTS.mkdir(exist_ok=True)
    write_json(report, REPORTS / f"typescript-{args.surface}-benchmark-report.json")
    write_json(
        report_markdown(report, f"typescript-{args.surface}-benchmark-report.md"),
        REPORTS / f"typescript-{args.surface}-benchmark-report.md",
        raw=True,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def desktop_apply_plan(staged_fr: Path) -> dict[str, object]:
    """Explicit apply plan for enabling fr in the Desktop locale registration."""
    return {
        "description": "Desktop fr enablement requires registering the staged catalog in the locale contract.",
        "files": [
            {
                "path": "apps/desktop/src/i18n/fr.ts",
                "action": "copy_staged",
                "source": staged_fr.as_posix(),
            },
            {
                "path": "apps/desktop/src/i18n/types.ts",
                "action": "edit_locale_union",
                "edit": "add 'fr' to the `export type Locale` union",
            },
            {
                "path": "apps/desktop/src/i18n/catalog.ts",
                "action": "edit_translations_record",
                "edit": "import fr and register it in TRANSLATIONS",
            },
            {
                "path": "apps/desktop/src/i18n/languages.ts",
                "action": "edit_locale_options",
                "edit": "add the Français LOCALE_OPTIONS entry and fr aliases",
            },
        ],
        "staged_only": True,
        "original_checkout_mutation": False,
    }


def _compare_reference(blind_source: Path, staged: Path, official: Path) -> dict[str, object]:
    def leaves(path: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        for segment in extract_segments(path, "en", path.name):
            result[segment["context"]["pointer"]] = segment["source"]
        return result

    staged_flat = leaves(staged)
    official_flat = leaves(official)
    source_flat = leaves(blind_source)
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
