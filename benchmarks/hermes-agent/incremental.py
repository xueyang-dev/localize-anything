"""Phase 10: incremental classification and regeneration test on a YAML copy."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from common import BENCH_ROOT, CONFIG, REPORTS, WORK, report_markdown, write_json

sys.path.insert(0, str(BENCH_ROOT))

from runtime.localize_anything.core_segments import diff_segments  # noqa: E402
from runtime.localize_anything.structured_adapter import extract_segments, rebuild  # noqa: E402


SOURCE = WORK / "incremental" / "en.yaml"
MUTATED = WORK / "incremental" / "en-mutated.yaml"
REBUILT = WORK / "incremental" / "fr-mutated.yaml"
LOGICAL_PATH = "locales/en.yaml"


def main() -> int:
    source_checkout = WORK / "source" / "locales/en.yaml"
    if not source_checkout.is_file():
        raise ValueError("source checkout missing; run `python prepare.py source` first")
    incremental_root = WORK / "incremental"
    if incremental_root.exists():
        shutil.rmtree(incremental_root)
    incremental_root.mkdir(parents=True)
    shutil.copy2(source_checkout, SOURCE)

    previous = extract_segments(SOURCE, "en", LOGICAL_PATH)
    # Simulate a reviewed previous run: translate a few stable keys.
    reviewed = {s["context"]["pointer"]: f"[REVIEWED:{s['source']}]" for s in previous if s["context"]["pointer"] in {
        "/approval/denied", "/gateway/draining", "/gateway/model/switched", "/usage/header_session",
    }}
    for segment in previous:
        if segment["context"]["pointer"] in reviewed:
            segment["target"] = reviewed[segment["context"]["pointer"]]
            segment["target_locale"] = "fr"
            segment["status"] = "generated"

    mutated = _mutate(SOURCE.read_text(encoding="utf-8"))
    MUTATED.write_text(mutated, encoding="utf-8", newline="")
    current = extract_segments(MUTATED, "en", LOGICAL_PATH)

    diff = diff_segments(previous, current)
    classification = diff["summary"]
    affected = {item["segment_id"] for item in diff["segments"] if item["status"] != "unchanged"}

    # Regenerate only affected segments; preserve reviewed translations.
    regenerated = []
    preserved = 0
    for segment in current:
        if segment["segment_id"] in affected:
            segment["target"] = segment["source"]
            segment["target_locale"] = "fr"
            segment["status"] = "generated"
            segment["quality_claim"] = "engineering_fixture_only"
            segment["generation_mode"] = "incremental_regenerated"
            regenerated.append(segment)
        else:
            previous_by_id = {s["segment_id"]: s for s in previous}
            old = previous_by_id[segment["segment_id"]]
            if "target" in old:
                segment["target"] = old["target"]
                segment["target_locale"] = old["target_locale"]
                segment["status"] = "kept"
                preserved += 1
            regenerated.append(segment)

    rebuild(MUTATED, regenerated, REBUILT)
    rebuilt_text = REBUILT.read_text(encoding="utf-8")
    kept_targets = [segment["target"] for segment in regenerated if segment.get("status") == "kept"]
    preserved_ok = bool(kept_targets) and all(target in rebuilt_text for target in kept_targets)
    regenerated_count = sum(1 for s in regenerated if s.get("status") == "generated")

    report = {
        "protocol_version": CONFIG["protocol_version"],
        "benchmark_id": CONFIG["id"],
        "phase": "incremental",
        "classification": classification,
        "expected": {
            "new": 1,
            "changed": 2,
            "moved": 1,
            "deleted": 1,
        },
        "regenerated_segments": regenerated_count,
        "preserved_reviewed_segments": preserved,
        "preserved_translations_intact": preserved_ok,
        "staged_output": REBUILT.as_posix(),
    }
    REPORTS.mkdir(exist_ok=True)
    write_json(report, REPORTS / "incremental-report.json")
    write_json(report_markdown(report, "incremental-report.md"), REPORTS / "incremental-report.md", raw=True)
    print(_markdown(report))
    return 0 if (preserved_ok and all(classification.get(k) == v for k, v in report["expected"].items())) else 1


def _mutate(text: str) -> str:
    mutations = {
        # add one key
        'warn_passthrough:            "⚠️ {error}"\n': (
            'warn_passthrough:            "⚠️ {error}"\n'
            "  incremental:\n    new_key:                     \"New incremental string.\"\n"
        ),
        # change one string
        'goal_cleared:     "✓ Goal cleared."': 'goal_cleared:     "✓ Goal cleared (changed)."',
        # move one semantically equivalent string to a new key
        'no_active_goal:   "No active goal."': 'no_active_goal_moved: "No active goal."',
        # remove one key
        'choose_smart_deny: "      [o]nce  |  [d]eny"\n': "",
        # change one placeholder-bearing string
        'draining:         "⏳ Draining {count} active agent(s) before restart..."': (
            'draining:         "⏳ Draining {count} active agent(s) before restart... (changed)"'
        ),
    }
    for before, after in mutations.items():
        if before not in text:
            raise ValueError(f"mutation anchor not found: {before[:60]!r}")
        text = text.replace(before, after, 1)
    return text


def _markdown(report: dict[str, object]) -> str:
    lines = ["# Incremental report", ""]
    for key, value in report.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
