"""Track 2 (agent-system): style_only reference policy using YAML French style evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from common import BENCH_ROOT, CONFIG, REFERENCE, REPORTS, REPOSITORY_ROOT, RUNS, read_json, read_jsonl, report_markdown, write_json

sys.path.insert(0, str(BENCH_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT))

from runtime.localize_anything.typescript_locale_adapter import extract_segments as extract_ts  # noqa: E402


def main() -> int:
    """Exercise `reference_policy: style_only` with engineering fixture drafts.

    Style evidence comes from the reviewed official YAML French catalog
    (revealed only after Track 1 generation).  The English source remains
    source truth.  ``tm_assisted`` is not exercised in the engineering run.
    """
    terminology = read_json(REPORTS / "terminology-consistency-report.json")
    yaml_rows = [row for row in terminology["rows"] if row["surface"] == "yaml_cli_gateway"]
    style_evidence = {row["term"]: row["official_fr_samples"][0] for row in yaml_rows}
    official_web_path = REFERENCE / "web" / "fr.ts"
    official_web = (
        {s["context"]["pointer"]: s["source"] for s in extract_ts(official_web_path, "fr", "fr.ts")}
        if official_web_path.is_file()
        else {}
    )
    official_web_en_path = REPOSITORY_ROOT / "benchmarks" / "hermes-agent" / "work" / "source" / "web/src/i18n/en.ts"
    official_web_en = (
        {s["context"]["pointer"]: s["source"] for s in extract_ts(official_web_en_path, "en", "en.ts")}
        if official_web_en_path.is_file()
        else {}
    )

    web_generated = read_jsonl(RUNS / "typescript-web/generated.jsonl")
    desktop_generated = read_jsonl(RUNS / "typescript-desktop/generated.jsonl")
    results: dict[str, object] = {}
    for surface, segments in (("web", web_generated), ("desktop", desktop_generated)):
        curated = [s for s in segments if s.get("generation_mode") == "synthetic_curated_draft"]
        checks = []
        for segment in curated:
            source = segment["source"]
            target = segment["target"]
            pointer = segment["context"]["pointer"]
            official_value = official_web.get(pointer)
            official_is_translated = bool(official_value) and official_value != official_web_en.get(pointer)
            checks.append(
                {
                    "pointer": pointer,
                    "english_source": source,
                    "staged_target": target,
                    "official_web_fr": official_value,
                    "official_web_fr_translated": official_is_translated,
                    "consistent_with_official_web_style": official_is_translated and target == official_value,
                }
            )
        results[surface] = {
            "curated_segments": len(curated),
            "cross_surface_checks": len(checks),
            "consistent_with_official_web_style": sum(1 for check in checks if check["consistent_with_official_web_style"]),
            "official_web_fr_translated": sum(1 for check in checks if check["official_web_fr_translated"]),
            "samples": checks[:6],
        }

    report = {
        "protocol_version": CONFIG["protocol_version"],
        "benchmark_id": CONFIG["id"],
        "track": "agent_system",
        "reference_policy": "style_only",
        "tm_assisted": "not_exercised_engineering_run",
        "source_truth": "en",
        "style_evidence_surfaces": {
            "yaml_cli_gateway": "official YAML French term samples (lexicon, see terminology-consistency-report.json)",
            "web_dashboard": "official Web French values used as cross-surface style evidence for the Desktop slice",
        },
        "quality_claim": "engineering_fixture_only",
        "note": "Terminology/style evidence from the official YAML French catalog is applied as a QA constraint to the curated Web/Desktop slice; it is not generation input for Track 1.",
        "surfaces": results,
    }
    REPORTS.mkdir(exist_ok=True)
    write_json(report, REPORTS / "agent-system-benchmark-report.json")
    write_json(report_markdown(report, "agent-system-benchmark-report.md"), REPORTS / "agent-system-benchmark-report.md", raw=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
