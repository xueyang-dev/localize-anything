from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY))

from runtime.localize_anything.android_strings_adapter import android_resource_routing, extract_segments, target_resource_path  # noqa: E402
from runtime.localize_anything.io_utils import read_json, read_jsonl, write_json, write_jsonl  # noqa: E402
from runtime.localize_anything.project import file_sha256, initialize_project, inspect_project  # noqa: E402
from runtime.localize_anything.reference import segment_identity  # noqa: E402
from runtime.localize_anything.run import run_localize  # noqa: E402


SOURCE_LOCALE = "en-US"
TARGET_LOCALE = "zh-CN"
FIXTURE = ROOT / "fixture-source-sets"
GENERATION_SOURCE_FILES = sorted([
    "app/src/debug/res/values/strings.xml",
    "app/src/free/res/values/strings.xml",
    "app/src/main/res/values-land/strings.xml",
    "app/src/main/res/values-mcc310-mnc004-land/strings.xml",
    "app/src/main/res/values-mcc310-mnc004/strings.xml",
    "app/src/main/res/values-mcc310-night/strings.xml",
    "app/src/main/res/values-mcc310/strings.xml",
    "app/src/main/res/values-night/strings.xml",
    "app/src/main/res/values-sw600dp/strings.xml",
    "app/src/main/res/values/strings.xml",
])
LOCALE_REFERENCE_FILES = [
    "app/src/main/res/values-es/strings.xml",
    "app/src/main/res/values-fr/strings.xml",
    "app/src/main/res/values-zh-rCN/strings.xml",
]
TARGET_PATHS = {
    "app/src/debug/res/values/strings.xml": "app/src/debug/res/values-zh-rCN/strings.xml",
    "app/src/free/res/values/strings.xml": "app/src/free/res/values-zh-rCN/strings.xml",
    "app/src/main/res/values-land/strings.xml": "app/src/main/res/values-zh-rCN-land/strings.xml",
    "app/src/main/res/values-mcc310-mnc004-land/strings.xml": "app/src/main/res/values-mcc310-mnc004-zh-rCN-land/strings.xml",
    "app/src/main/res/values-mcc310-mnc004/strings.xml": "app/src/main/res/values-mcc310-mnc004-zh-rCN/strings.xml",
    "app/src/main/res/values-mcc310-night/strings.xml": "app/src/main/res/values-mcc310-zh-rCN-night/strings.xml",
    "app/src/main/res/values-mcc310/strings.xml": "app/src/main/res/values-mcc310-zh-rCN/strings.xml",
    "app/src/main/res/values-night/strings.xml": "app/src/main/res/values-zh-rCN-night/strings.xml",
    "app/src/main/res/values-sw600dp/strings.xml": "app/src/main/res/values-zh-rCN-sw600dp/strings.xml",
    "app/src/main/res/values/strings.xml": "app/src/main/res/values-zh-rCN/strings.xml",
}
REFERENCE_SENTINELS = ["已有主标题", "旧版目标专属文本", "Título existente ES", "Titre existant FR"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Android source-set and qualifier routing benchmark")
    parser.add_argument("--work-root", type=Path, default=ROOT / "work-source-sets")
    parser.add_argument("--report-dir", type=Path, default=ROOT)
    parser.add_argument("--keep-work", action="store_true")
    args = parser.parse_args()
    report = run_benchmark(args.work_root, args.report_dir, args.keep_work)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report["status"] == "pass" else 1


def run_benchmark(work_root: Path = ROOT / "work-source-sets", report_dir: Path = ROOT, keep_work: bool = False) -> dict[str, Any]:
    work_root = work_root.resolve()
    report_dir = report_dir.resolve()
    if work_root.exists() and not keep_work:
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    scan_project = work_root / "scan-project"
    _copy_fixture(scan_project)
    inspection = inspect_project(scan_project)
    routing = _routing_check(scan_project, inspection)

    blind_project = work_root / "blind-project"
    _copy_fixture(blind_project)
    source_hashes_before = _source_hashes(blind_project)
    blind = run_localize(
        blind_project,
        SOURCE_LOCALE,
        [TARGET_LOCALE],
        output_root=work_root / "blind-runs",
        run_id="source-sets-blind-001",
        synthetic_draft=True,
        operating_mode="blind_benchmark",
        reference_policy="blind",
        max_segments=100,
    )
    blind_check = _blind_check(blind, blind_project, source_hashes_before)

    maintenance_project = work_root / "maintenance-project"
    _copy_fixture(maintenance_project)
    _seed_reviewed_main_translation(maintenance_project)
    maintenance = run_localize(
        maintenance_project,
        SOURCE_LOCALE,
        [TARGET_LOCALE],
        output_root=work_root / "maintenance-runs",
        run_id="source-sets-maintenance-001",
        synthetic_draft=True,
        operating_mode="existing_locale_maintenance",
        reference_policy="preserve_existing",
        max_segments=100,
    )
    maintenance_check = _maintenance_check(maintenance)

    negative_checks = _negative_checks()
    warnings = sorted(
        warning
        for item in inspection["supported_files"]
        if item.get("adapter") == "core.android-strings"
        for warning in item.get("warnings", [])
    )
    check = {
        "pass": (
            routing["pass"]
            and blind_check["pass"]
            and maintenance_check["pass"]
            and all(item["pass"] for item in negative_checks)
            and not warnings
        ),
        "source_files_detected": len(routing["generation_source_files"]),
        "locale_reference_files_detected": len(routing["excluded_locale_reference_files"]),
        "generation_source_files": routing["generation_source_files"],
        "excluded_locale_reference_files": routing["excluded_locale_reference_files"],
        "staged_target_paths": blind_check["staged_target_paths"],
        "source_set_metadata_present": routing["source_set_metadata_present"],
        "qualifier_metadata_present": routing["qualifier_metadata_present"],
        "target_path_mapping_pass": routing["target_path_mapping_pass"],
        "blind_reference_leakage_pass": blind_check["blind_reference_leakage_pass"],
        "maintenance_existing_target_behavior_pass": maintenance_check["pass"],
        "source_files_unchanged": blind_check["source_files_unchanged"],
        "negative_checks": negative_checks,
        "warnings": warnings,
    }
    status = "pass" if check["pass"] else "fail"
    report = {
        "schema": "localize-anything-v022-android-source-set-qualifier-policy",
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": status,
        "verdict": f"V0.2.2-I ANDROID SOURCE-SET / QUALIFIER DETECTION POLICY: {status.upper()}",
        "fixture_path": FIXTURE.as_posix(),
        "work_root": work_root.as_posix(),
        "source_set_qualifier_check": check,
        "routing_check": routing,
        "blind_check": blind_check,
        "maintenance_check": maintenance_check,
        "failed_checks": _failed_checks(routing, blind_check, maintenance_check, negative_checks, warnings),
    }
    write_json(report_dir / "source-set-report.json", report)
    (report_dir / "source-set-report.md").write_text(_render_markdown(report), encoding="utf-8", newline="\n")
    return report


def _routing_check(project: Path, inspection: dict[str, Any]) -> dict[str, Any]:
    generation = inspection.get("android_generation_source_files", [])
    references = inspection.get("android_locale_reference_files", [])
    android_files = [item for item in inspection["supported_files"] if item["adapter"] == "core.android-strings"]
    by_path = {item["path"]: item for item in android_files}
    mappings = {
        source: target_resource_path(project / source, TARGET_LOCALE, project).as_posix()
        for source in generation
    }
    metadata_present = all(item.get("android_source_set") in {"main", "debug", "free"} for item in android_files)
    qualifier_metadata = all(
        isinstance(item.get("android_qualifiers", {}).get("non_locale"), list)
        and "locale" in item.get("android_qualifiers", {})
        for item in android_files
    )
    return {
        "pass": (
            generation == GENERATION_SOURCE_FILES
            and references == LOCALE_REFERENCE_FILES
            and mappings == TARGET_PATHS
            and metadata_present
            and qualifier_metadata
        ),
        "generation_source_files": generation,
        "excluded_locale_reference_files": references,
        "target_path_mappings": mappings,
        "source_set_metadata_present": metadata_present,
        "qualifier_metadata_present": qualifier_metadata,
        "target_path_mapping_pass": mappings == TARGET_PATHS,
        "metadata": {
            path: {
                "android_source_set": by_path[path]["android_source_set"],
                "android_res_dir": by_path[path]["android_res_dir"],
                "android_qualifiers": by_path[path]["android_qualifiers"],
                "android_role": by_path[path]["android_role"],
            }
            for path in sorted(by_path)
        },
    }


def _blind_check(result: dict[str, Any], project: Path, before: dict[str, str]) -> dict[str, Any]:
    artifacts = result["artifacts"]
    leakage = _scan_forbidden(_generation_facing_artifacts(artifacts), REFERENCE_SENTINELS)
    staging = read_json(Path(artifacts["staging_result"]))
    staged_paths = sorted(output["destination"] for output in staging["outputs"])
    selected = sorted(result["source_files"])
    unchanged = before == _source_hashes(project)
    return {
        "pass": selected == GENERATION_SOURCE_FILES and staged_paths == sorted(TARGET_PATHS.values()) and leakage["pass"] and unchanged,
        "generation_source_files": selected,
        "staged_target_paths": staged_paths,
        "blind_reference_leakage_pass": leakage["pass"],
        "leakage_matches": leakage["matches"],
        "source_files_unchanged": unchanged,
    }


def _maintenance_check(result: dict[str, Any]) -> dict[str, Any]:
    artifacts = result["artifacts"]
    staging = read_json(Path(artifacts["staging_result"]))
    outputs = {output["destination"]: output for output in staging["outputs"]}
    main_target = Path(outputs[TARGET_PATHS["app/src/main/res/values/strings.xml"]]["output"])
    main_text = main_target.read_text(encoding="utf-8")
    generated_keys = {
        item.get("context", {}).get("resource_key")
        for item in read_jsonl(Path(artifacts["generated_segments"]))
    }
    reference_plan = read_json(Path(artifacts["reference_plan"]))
    return {
        "pass": (
            "已有主标题" in main_text
            and "旧版目标专属文本" in main_text
            and "string:main_title" not in generated_keys
            and reference_plan["summary"].get("preserved_segment_count") == 1
            and sorted(outputs) == sorted(TARGET_PATHS.values())
        ),
        "existing_main_translation_preserved": "已有主标题" in main_text,
        "target_only_resource_preserved": "旧版目标专属文本" in main_text,
        "main_title_sent_to_generation": "string:main_title" in generated_keys,
        "preserved_segment_count": reference_plan["summary"].get("preserved_segment_count"),
        "staged_target_paths": sorted(outputs),
    }


def _seed_reviewed_main_translation(project: Path) -> None:
    inspection = inspect_project(project)
    initialize_project(
        project,
        SOURCE_LOCALE,
        inspection["android_generation_source_files"],
        [TARGET_LOCALE],
        "existing_locale_maintenance",
        "preserve_existing",
    )
    source_file = "app/src/main/res/values/strings.xml"
    segment = extract_segments(project / source_file, SOURCE_LOCALE, source_file)[0]
    write_jsonl(
        project / ".localize-anything" / "translation-memory.jsonl",
        [
            {
                "id": "tm-main-title",
                "identity": segment_identity(segment),
                "segment_id": segment["segment_id"],
                "source": segment["source"],
                "source_hash": segment["source_hash"],
                "target": "已有主标题",
                "target_locale": TARGET_LOCALE,
                "status": "reviewed",
                "content_type": "android_string",
            }
        ],
    )


def _negative_checks() -> list[dict[str, Any]]:
    cases = []
    locale_selected = _validate_policy([*GENERATION_SOURCE_FILES, LOCALE_REFERENCE_FILES[-1]], TARGET_PATHS)
    cases.append({"name": "existing_locale_selected_as_source", "pass": not locale_selected["pass"], "validation": locale_selected})

    collapsed_qualifier = dict(TARGET_PATHS)
    collapsed_qualifier["app/src/main/res/values-night/strings.xml"] = "app/src/main/res/values-zh-rCN/strings.xml"
    qualifier = _validate_policy(GENERATION_SOURCE_FILES, collapsed_qualifier)
    cases.append({"name": "qualifier_target_path_collapsed", "pass": not qualifier["pass"], "validation": qualifier})

    collapsed_source_set = dict(TARGET_PATHS)
    collapsed_source_set["app/src/debug/res/values/strings.xml"] = "app/src/main/res/values-zh-rCN/strings.xml"
    collapsed_source_set["app/src/free/res/values/strings.xml"] = "app/src/main/res/values-zh-rCN/strings.xml"
    source_set = _validate_policy(GENERATION_SOURCE_FILES, collapsed_source_set)
    cases.append({"name": "source_set_target_path_collapsed", "pass": not source_set["pass"], "validation": source_set})

    wrong_mcc = dict(TARGET_PATHS)
    wrong_mcc["app/src/main/res/values-mcc310/strings.xml"] = "app/src/main/res/values-zh-rCN-mcc310/strings.xml"
    mcc = _validate_policy(GENERATION_SOURCE_FILES, wrong_mcc)
    cases.append({"name": "mcc_staged_after_locale", "pass": not mcc["pass"], "validation": mcc})

    wrong_mcc_mnc_land = dict(TARGET_PATHS)
    wrong_mcc_mnc_land["app/src/main/res/values-mcc310-mnc004-land/strings.xml"] = (
        "app/src/main/res/values-zh-rCN-mcc310-mnc004-land/strings.xml"
    )
    mcc_mnc_land = _validate_policy(GENERATION_SOURCE_FILES, wrong_mcc_mnc_land)
    cases.append({"name": "mcc_mnc_land_staged_after_locale", "pass": not mcc_mnc_land["pass"], "validation": mcc_mnc_land})

    invalid_path = Path("app/src/main/res/values-zh-rCN-mcc310/strings.xml")
    invalid_routing = android_resource_routing(invalid_path, target_locale=TARGET_LOCALE)
    invalid_rejected = False
    try:
        target_resource_path(invalid_path, TARGET_LOCALE)
    except ValueError:
        invalid_rejected = True
    cases.append({
        "name": "invalid_locale_order_selected_as_source",
        "pass": (
            invalid_routing["android_role"] != "source_candidate"
            and bool(invalid_routing["warnings"])
            and invalid_rejected
        ),
        "validation": {
            "android_role": invalid_routing["android_role"],
            "warnings": invalid_routing["warnings"],
            "target_path_rejected": invalid_rejected,
        },
    })
    return cases


def _validate_policy(generation_sources: list[str], mappings: dict[str, str]) -> dict[str, Any]:
    selected_locale_references = sorted(set(generation_sources) & set(LOCALE_REFERENCE_FILES))
    wrong_mappings = {
        source: mappings.get(source)
        for source, expected in TARGET_PATHS.items()
        if mappings.get(source) != expected
    }
    return {
        "pass": not selected_locale_references and not wrong_mappings and sorted(generation_sources) == GENERATION_SOURCE_FILES,
        "selected_locale_references": selected_locale_references,
        "wrong_mappings": wrong_mappings,
    }


def _source_hashes(project: Path) -> dict[str, str]:
    return {path: file_sha256(project / path) for path in GENERATION_SOURCE_FILES}


def _generation_facing_artifacts(artifacts: dict[str, Any]) -> list[Path]:
    keys = ("work_packets", "draft_requests", "prompts", "prompt_manifest", "generation_handoff", "generation_readme", "generated_segments")
    return [Path(str(artifacts[key])) for key in keys if key in artifacts]


def _scan_forbidden(paths: list[Path], forbidden: list[str]) -> dict[str, Any]:
    matches: list[dict[str, str]] = []
    for path in paths:
        candidates = [item for item in path.rglob("*") if item.is_file()] if path.is_dir() else [path] if path.is_file() else []
        for candidate in candidates:
            try:
                text = candidate.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for sentinel in forbidden:
                if sentinel in text:
                    matches.append({"path": candidate.as_posix(), "text": sentinel})
    return {"pass": not matches, "matches": matches}


def _copy_fixture(project: Path) -> None:
    if project.exists():
        shutil.rmtree(project)
    shutil.copytree(FIXTURE, project)


def _failed_checks(
    routing: dict[str, Any],
    blind: dict[str, Any],
    maintenance: dict[str, Any],
    negatives: list[dict[str, Any]],
    warnings: list[str],
) -> list[str]:
    failures = []
    if not routing["pass"]:
        failures.append("source-set routing check failed")
    if not blind["pass"]:
        failures.append("blind source-set check failed")
    if not maintenance["pass"]:
        failures.append("maintenance source-set check failed")
    if not all(item["pass"] for item in negatives):
        failures.append("source-set negative checks failed")
    if warnings:
        failures.append("routing warnings require owner review")
    return failures


def _render_markdown(report: dict[str, Any]) -> str:
    check = report["source_set_qualifier_check"]
    lines = [
        "# v0.2.2-I Android Source-Set / Qualifier Detection Policy",
        "",
        f"- Status: `{report['status']}`",
        f"- Verdict: **{report['verdict']}**",
        f"- Source files detected: {check['source_files_detected']}",
        f"- Locale reference files detected: {check['locale_reference_files_detected']}",
        f"- Target path mapping: `{check['target_path_mapping_pass']}`",
        f"- Blind leakage: `{check['blind_reference_leakage_pass']}`",
        f"- Maintenance behavior: `{check['maintenance_existing_target_behavior_pass']}`",
        f"- Source files unchanged: `{check['source_files_unchanged']}`",
        "",
        "## Staged Target Paths",
        "",
        *[f"- `{path}`" for path in check["staged_target_paths"]],
        "",
        "## Negative Checks",
        "",
        *[f"- `{item['name']}`: `{item['pass']}`" for item in check["negative_checks"]],
    ]
    if check["warnings"]:
        lines.extend(["", "## Warnings", "", *[f"- {warning}" for warning in check["warnings"]]])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
