from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY))

from runtime.localize_anything import android_strings_adapter as android  # noqa: E402
from runtime.localize_anything.generation import validate_generated_segments  # noqa: E402
from runtime.localize_anything.io_utils import read_json, read_jsonl, write_json, write_jsonl  # noqa: E402
from runtime.localize_anything.planning import is_generation_eligible  # noqa: E402
from runtime.localize_anything.run import run_localize  # noqa: E402


SOURCE_LOCALE = "en-US"
TARGET_LOCALE = "zh-CN"
SOURCE_FILE = "app/src/main/res/values/strings.xml"
TARGET_FILE = "app/src/main/res/values-zh-rCN/strings.xml"
LEGACY_KEY = "legacy_removed_key"
LEGACY_RESOURCE_KEY = f"string:{LEGACY_KEY}"
LEGACY_TEXT = "旧版专属译文_不得自动删除"
COMPLEX_MARKUP_KEYS = {
    "string:nested_markup",
    "string:font_markup",
    "string:styled_bold",
    "string:complex_link",
}
SUPPORTED_ARRAY_MARKUP_KEYS = {
    "string-array:rich_sort_options[0]",
    "string-array:rich_sort_options[1]",
    "string-array:rich_sort_options[2]",
}
SUPPORTED_PLURAL_MARKUP_KEYS = {
    "plurals:rich_episode_count#one",
    "plurals:rich_episode_count#other",
}
UNSUPPORTED_ARRAY_MARKUP_KEYS = {
    "string-array:complex_sort_options[0]",
    "string-array:complex_sort_options[1]",
}
UNSUPPORTED_PLURAL_MARKUP_KEYS = {
    "plurals:complex_episode_count#one",
    "plurals:complex_episode_count#other",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.2.2 Android resource reliability benchmark")
    parser.add_argument("--work-root", type=Path, default=ROOT / "work")
    parser.add_argument("--report-dir", type=Path, default=ROOT)
    parser.add_argument("--keep-work", action="store_true")
    args = parser.parse_args()
    report = run_benchmark(args.work_root, args.report_dir, args.keep_work)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report["status"] in {"pass", "partial"} else 1


def run_benchmark(work_root: Path = ROOT / "work", report_dir: Path = ROOT, keep_work: bool = False) -> dict[str, Any]:
    work_root = work_root.resolve()
    report_dir = report_dir.resolve()
    if work_root.exists() and not keep_work:
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    project_root = work_root / "direct-adapter" / "project"
    _copy_fixture(project_root, include_target=True)
    source_path = project_root / SOURCE_FILE
    target_path = project_root / TARGET_FILE

    extraction = _extraction_check(source_path)
    generated_segments = _generated_segments(extraction["segments"])
    generated_path = work_root / "direct-adapter" / "generated.jsonl"
    write_jsonl(generated_path, generated_segments)
    staging = _staging_check(project_root, source_path, generated_segments, work_root / "direct-adapter" / "staging")
    qa = _qa_check(source_path, Path(staging["staged_target"]))
    escape_signature = _escape_signature_check(extraction["segments"], generated_segments)
    inline_markup = _inline_markup_check(extraction["segments"], generated_segments, staging)
    cdata = _cdata_check(extraction["segments"], generated_segments, source_path, Path(staging["staged_target"]))
    comments = _comment_round_trip_check(source_path, Path(staging["staged_target"]))

    blind = _run_mode(work_root, "blind_benchmark", "blind")
    blind_leakage = _blind_leakage_check(blind["result"], target_path)
    maintenance = _run_mode(work_root, "existing_locale_maintenance", "preserve_existing")
    maintenance_preservation = _maintenance_preservation_check(maintenance["result"])
    complex_markup_policy = _complex_markup_policy_check(
        extraction["segments"],
        generated_segments,
        staging,
        blind["result"],
        maintenance["result"],
        target_path,
    )
    array_plural_markup_policy = _array_plural_markup_policy_check(
        extraction["segments"],
        generated_segments,
        staging,
        blind["result"],
        maintenance["result"],
        target_path,
    )

    checks = {
        "extraction": _strip_segments(extraction),
        "staging": staging,
        "qa": qa,
        "escape_signature": escape_signature,
        "inline_markup": inline_markup,
        "cdata": cdata,
        "comments": comments,
        "blind_leakage": blind_leakage,
        "maintenance_preservation": maintenance_preservation,
        "complex_markup_policy": complex_markup_policy,
        "array_plural_markup_policy": array_plural_markup_policy,
    }
    failed_checks = _failed_checks(checks)
    known_limitations = _known_limitations(extraction, staging, qa)
    core_pass = not failed_checks
    status = "pass" if core_pass else "fail"

    report = {
        "schema": "localize-anything-v022-android-array-plural-markup-boundary-policy",
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": status,
        "verdict": _verdict(status),
        "fixture_path": (ROOT / "fixture").as_posix(),
        "work_root": work_root.as_posix(),
        "source_locale": SOURCE_LOCALE,
        "target_locale": TARGET_LOCALE,
        "source_file": SOURCE_FILE,
        "target_file": TARGET_FILE,
        "commands_executed": [
            "python -m unittest discover -s tests -v",
            "python -m runtime.localize_anything validate-protocol",
            "python -m runtime.localize_anything validate-contracts",
            "python -m compileall -q runtime benchmarks",
            "python benchmarks/v022-android-resource-reliability/run.py",
            "python benchmarks/v021-mode-system/run.py",
        ],
        "source_segment_count": extraction["source_segment_count"],
        "extracted_segment_count": extraction["extracted_segment_count"],
        "generated_segment_count": len(generated_segments),
        "skipped_translatable_false_count": extraction["skipped_translatable_false_count"],
        "placeholder_check_result": extraction["placeholder_check"],
        "escape_signature_check": escape_signature,
        "inline_markup_check": inline_markup,
        "cdata_check": cdata,
        "comment_round_trip_check": comments,
        "escape_check_result": staging["escape_check"],
        "xml_entity_check_result": staging["xml_entity_check"],
        "inline_html_check_result": staging["inline_html_check"],
        "cdata_check_result": staging["cdata_check"],
        "string_array_check_result": staging["string_array_check"],
        "plurals_check_result": staging["plurals_check"],
        "target_only_preservation_check_result": staging["target_only_preservation_check"],
        "blind_leakage_check_result": blind_leakage,
        "maintenance_preservation_check_result": maintenance_preservation,
        "complex_markup_policy_check": complex_markup_policy,
        "array_plural_markup_policy_check": array_plural_markup_policy,
        "qa_check_result": qa,
        "known_limitations": known_limitations,
        "checks": checks,
        "artifacts": {
            "generated_jsonl": generated_path.as_posix(),
            "staged_target": staging["staged_target"],
            "blind_run_directory": blind["result"]["artifacts"]["run_directory"],
            "maintenance_run_directory": maintenance["result"]["artifacts"]["run_directory"],
            "maintenance_staging_result": maintenance["result"]["artifacts"]["staging_result"],
        },
        "failed_checks": failed_checks,
    }
    write_json(report_dir / "report.json", report)
    (report_dir / "report.md").write_text(render_report_markdown(report), encoding="utf-8", newline="\n")
    return report


def _copy_fixture(project_root: Path, include_target: bool) -> None:
    if project_root.exists():
        shutil.rmtree(project_root)
    shutil.copytree(ROOT / "fixture", project_root)
    if not include_target:
        target = project_root / TARGET_FILE
        if target.exists():
            target.unlink()


def _extraction_check(source_path: Path) -> dict[str, Any]:
    segments = android.extract_segments(source_path, SOURCE_LOCALE, SOURCE_FILE)
    document = android._read_document(source_path)  # noqa: SLF001 - benchmark probes adapter-observed structure.
    by_key = {segment["context"]["resource_key"]: segment for segment in segments}
    resource_types = sorted({segment["context"]["resource_type"] for segment in segments})
    skipped = document["skipped"]
    placeholder_expected = {
        "string:literal_percent": [],
        "string:welcome_user": ["%1$s"],
        "string:delete_files": ["%1$d", "%2$d"],
        "plurals:episode_count#one": ["%1$d"],
        "plurals:episode_count#other": ["%1$d"],
        "plurals:rich_episode_count#one": ["%1$d"],
        "plurals:rich_episode_count#other": ["%1$d"],
    }
    placeholder_checks = {
        key: by_key.get(key, {}).get("constraints", {}).get("placeholders") == expected
        for key, expected in placeholder_expected.items()
    }
    escape_expected = {
        "string:cant_sync": ["\\'", '"'],
        "string:multiline_help": ["\\n", "\\t"],
        "string:delete_files": ["%%"],
    }
    escape_checks = {
        key: by_key.get(key, {}).get("constraints", {}).get("escape_signature") == expected
        for key, expected in escape_expected.items()
    }
    markup_expected = {
        "string:learn_more": ["b"],
        "string:formatting_example": ["i", "u"],
        "string:unsupported_link": ["a"],
        "string:privacy_link": ["a"],
        "string-array:rich_sort_options[0]": ["b"],
        "string-array:rich_sort_options[1]": ["i"],
        "string-array:rich_sort_options[2]": ["a"],
        "plurals:rich_episode_count#one": ["b"],
        "plurals:rich_episode_count#other": ["b"],
    }
    markup_checks = {
        key: [item.get("tag") for item in by_key.get(key, {}).get("constraints", {}).get("markup_signature", [])] == expected
        for key, expected in markup_expected.items()
    }
    cdata_expected = {
        "string:html_cdata": True,
        "string:plain_cdata": True,
    }
    cdata_checks = {
        key: by_key.get(key, {}).get("constraints", {}).get("cdata") is expected
        for key, expected in cdata_expected.items()
    }
    comment_expected = {
        "string:settings_title": "Settings screen",
        "string-array:sort_options[0]": "Sort options shown in the queue screen",
        "plurals:episode_count#one": "Number of downloaded episodes",
    }
    comment_checks = {
        key: by_key.get(key, {}).get("context", {}).get("resource_comment") == expected
        for key, expected in comment_expected.items()
    }
    review_only = [segment for segment in segments if not is_generation_eligible(segment)]
    review_by_key = {segment["context"]["resource_key"]: segment for segment in review_only}
    complex_markup_checks = {
        "nested": "complex_nested_markup" in review_by_key.get("string:nested_markup", {}).get("review_required_reasons", []),
        "unsupported_tag": "unsupported_markup_tag" in review_by_key.get("string:font_markup", {}).get("review_required_reasons", []),
        "styled_attribute": "unsupported_markup_attribute" in review_by_key.get("string:styled_bold", {}).get("review_required_reasons", []),
        "link_attribute": "unsupported_markup_attribute" in review_by_key.get("string:complex_link", {}).get("review_required_reasons", []),
        "owner_review_required": all(segment.get("owner_review_required") for segment in review_only),
        "generation_excluded": all(segment.get("generation_eligible") is False for segment in review_only),
    }
    translatable_false = [item for item in skipped if item["reason"] == "translatable_false"]
    return {
        "pass": (
            "string:build_flavor" not in by_key
            and {"string", "string-array", "plurals"}.issubset(set(resource_types))
            and all(placeholder_checks.values())
            and all(escape_checks.values())
            and all(markup_checks.values())
            and all(cdata_checks.values())
            and all(comment_checks.values())
            and COMPLEX_MARKUP_KEYS.issubset(set(review_by_key))
            and all(complex_markup_checks.values())
            and bool(translatable_false)
        ),
        "segments": segments,
        "source_segment_count": len(segments),
        "extracted_segment_count": len(segments),
        "skipped_translatable_false_count": len(translatable_false),
        "owner_review_required_count": len(review_only),
        "resource_types": resource_types,
        "placeholder_check": {"pass": all(placeholder_checks.values()), "items": placeholder_checks},
        "escape_signature_extraction_check": {"pass": all(escape_checks.values()), "items": escape_checks},
        "markup_signature_extraction_check": {"pass": all(markup_checks.values()), "items": markup_checks},
        "cdata_signature_extraction_check": {"pass": all(cdata_checks.values()), "items": cdata_checks},
        "resource_comment_extraction_check": {"pass": all(comment_checks.values()), "items": comment_checks},
        "complex_markup_detection_check": {"pass": all(complex_markup_checks.values()), "items": complex_markup_checks},
        "unsupported_high_risk": {
            "unsupported_inline_markup": [item for item in skipped if item.get("owner_review_required")],
            "cdata_present_in_source": "<![CDATA[" in source_path.read_text(encoding="utf-8"),
        },
        "skipped": skipped,
    }


def _generated_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    generated = []
    for segment in segments:
        if not is_generation_eligible(segment):
            continue
        item = dict(segment)
        key = str(item["context"]["resource_key"])
        item["target_locale"] = TARGET_LOCALE
        item["target"] = _target_for_key(key, str(item["source"]))
        item["status"] = "generated"
        item["generation"] = {"provider": "synthetic", "purpose": "v0.2.2 baseline"}
        generated.append(item)
    return generated


def _target_for_key(key: str, source: str) -> str:
    mapping = {
        "string:app_name": "示例应用",
        "string:literal_percent": "电量为 100%",
        "string:welcome_user": "欢迎，%1$s！",
        "string:delete_files": "这将永久删除 %1$d 个文件（已完成 %2$d%%）。",
        "string:cant_sync": "Can\\'t sync \"Favorites\" right now.",
        "string:multiline_help": "Line one\\nLine two\\tIndented",
        "string:terms": "Read & accept the terms.",
        "string:learn_more": "Tap <b>Learn more</b> to continue.",
        "string:formatting_example": "Use <i>italic</i> or <u>underline</u> formatting.",
        "string:html_cdata": "Tap <b>Learn more</b> to continue.",
        "string:plain_cdata": "Use < and > safely in this message.",
        "string-array:sort_options[0]": "最新优先",
        "string-array:sort_options[1]": "最旧优先",
        "string-array:sort_options[2]": "播放最多",
        "string-array:rich_sort_options[0]": "<b>最新</b>优先",
        "string-array:rich_sort_options[1]": "最旧<i>优先</i>",
        "string-array:rich_sort_options[2]": "阅读<a href=\"https://example.com/sort\">排序帮助</a>",
        "plurals:episode_count#one": "%1$d 集",
        "plurals:episode_count#other": "%1$d 集",
        "plurals:rich_episode_count#one": "<b>%1$d</b> 集",
        "plurals:rich_episode_count#other": "<b>%1$d</b> 集",
        "string:settings_title": "设置",
    }
    return mapping.get(key, source)


def _staging_check(project_root: Path, source_path: Path, generated_segments: list[dict[str, Any]], staging_dir: Path) -> dict[str, Any]:
    result = android.stage_rebuild(source_path, generated_segments, staging_dir, TARGET_LOCALE, project_root, preserve_target_only=True)
    staged_target = Path(result["output"])
    parse_ok = _xml_parse_ok(staged_target)
    staged_text = staged_target.read_text(encoding="utf-8")
    tree = ElementTree.parse(staged_target)
    root = tree.getroot()
    names = [element.attrib.get("name") for element in list(root) if element.attrib.get("name")]
    extracted = android.extract_segments(staged_target, TARGET_LOCALE, TARGET_FILE)
    by_key = {segment["context"]["resource_key"]: segment for segment in extracted}
    placeholder_checks = {
        "welcome_user": by_key.get("string:welcome_user", {}).get("constraints", {}).get("placeholders") == ["%1$s"],
        "delete_files": by_key.get("string:delete_files", {}).get("constraints", {}).get("placeholders") == ["%1$d", "%2$d"],
        "plural_one": by_key.get("plurals:episode_count#one", {}).get("constraints", {}).get("placeholders") == ["%1$d"],
        "plural_other": by_key.get("plurals:episode_count#other", {}).get("constraints", {}).get("placeholders") == ["%1$d"],
    }
    array_items = _array_items(root, "sort_options")
    plurals = _plural_items(root, "episode_count")
    translatable_false_element = _find_named(root, "build_flavor")
    learn_more_element = _find_named(root, "learn_more")
    formatting_element = _find_named(root, "formatting_example")
    inline_markup_preserved = _child_tags(learn_more_element) == ["b"] and _child_tags(formatting_element) == ["i", "u"]
    cdata_sections = _cdata_sections(staged_text)
    cdata_raw_preserved = {"html_cdata", "plain_cdata"}.issubset(set(cdata_sections))
    cdata_semantic_preserved = (
        by_key.get("string:html_cdata", {}).get("source") == "Tap <b>Learn more</b> to continue."
        and by_key.get("string:plain_cdata", {}).get("source") == "Use < and > safely in this message."
    )
    source_comments = android._read_document(source_path)["comments"]  # noqa: SLF001 - benchmark probes adapter-observed comments.
    staged_comments = android._read_document(staged_target)["comments"]  # noqa: SLF001 - benchmark probes adapter-observed comments.
    string_comment_preserved = staged_comments.get("string:settings_title", {}).get("comment") == "Settings screen"
    array_comment_preserved = staged_comments.get("string-array:sort_options", {}).get("comment") == "Sort options shown in the queue screen"
    plurals_comment_preserved = staged_comments.get("plurals:episode_count", {}).get("comment") == "Number of downloaded episodes"
    target_only_comment_preserved = staged_comments.get(LEGACY_RESOURCE_KEY, {}).get("comment") == "Legacy removed key preserved for owner review"
    comments_preserved = string_comment_preserved and array_comment_preserved and plurals_comment_preserved and target_only_comment_preserved
    expected_complex = _resources_by_key(project_root / TARGET_FILE)
    staged_complex = _resources_by_key(staged_target)
    complex_markup_preserved = all(
        staged_complex.get(key, {}).get("value") == expected_complex.get(key, {}).get("value")
        and staged_complex.get(key, {}).get("markup_structure_signature") == expected_complex.get(key, {}).get("markup_structure_signature")
        for key in COMPLEX_MARKUP_KEYS
    )
    return {
        "pass": (
            parse_ok
            and "app_name" in names
            and translatable_false_element is not None
            and translatable_false_element.attrib.get("translatable") == "false"
            and 'formatted="false"' in staged_text
            and all(placeholder_checks.values())
            and "%2$d%%" in staged_text
            and "\\n" in staged_text
            and "\\t" in staged_text
            and array_items == ["最新优先", "最旧优先", "播放最多"]
            and list(plurals) == ["one", "other"]
            and plurals.get("one") == "%1$d 集"
            and plurals.get("other") == "%1$d 集"
            and inline_markup_preserved
            and cdata_raw_preserved
            and cdata_semantic_preserved
            and comments_preserved
            and complex_markup_preserved
            and LEGACY_TEXT in staged_text
            and f'name="{LEGACY_KEY}"' in staged_text
        ),
        "staged_target": staged_target.as_posix(),
        "staging_result": result,
        "xml_parse_check": {"pass": parse_ok},
        "resource_name_check": {"pass": "app_name" in names and "settings_title" in names, "names": names},
        "translatable_false_check": {
            "pass": translatable_false_element is not None and translatable_false_element.attrib.get("translatable") == "false",
            "policy": "preserved_from_existing_target_only_reference",
        },
        "formatted_false_check": {"pass": 'formatted="false"' in staged_text and "100%" in staged_text},
        "placeholder_check": {"pass": all(placeholder_checks.values()), "items": placeholder_checks},
        "escape_check": {"pass": "Can\\'t sync \"Favorites\" right now." in staged_text and "\\n" in staged_text and "\\t" in staged_text},
        "xml_entity_check": {"pass": "Read &amp; accept the terms." in staged_text and by_key.get("string:terms", {}).get("source") == "Read & accept the terms."},
        "inline_html_check": {
            "pass": inline_markup_preserved,
            "status": "pass" if inline_markup_preserved else "fail",
            "message": "simple Android inline markup child nodes are preserved as XML child tags",
            "supported_tags": ["b", "i", "u"],
            "learn_more_child_tags": _child_tags(learn_more_element),
            "formatting_example_child_tags": _child_tags(formatting_element),
        },
        "cdata_check": {
            "pass": cdata_semantic_preserved and cdata_raw_preserved,
            "status": "pass" if cdata_semantic_preserved and cdata_raw_preserved else "fail",
            "message": "CDATA text and section boundaries are preserved for source CDATA resources",
            "raw_cdata_preserved": cdata_raw_preserved,
            "semantic_text_preserved": cdata_semantic_preserved,
            "cdata_sections": cdata_sections,
        },
        "comment_check": {
            "pass": comments_preserved,
            "status": "pass" if comments_preserved else "fail",
            "message": "resource comments are preserved before corresponding staged resources",
            "source_comment_count": len(source_comments),
            "staged_comment_count": len(staged_comments),
            "string_comment_preserved": string_comment_preserved,
            "array_comment_preserved": array_comment_preserved,
            "plurals_comment_preserved": plurals_comment_preserved,
            "target_only_comment_preserved": target_only_comment_preserved,
        },
        "complex_markup_preservation_check": {
            "pass": complex_markup_preserved,
            "preserved_keys": sorted(key for key in COMPLEX_MARKUP_KEYS if staged_complex.get(key, {}).get("value") == expected_complex.get(key, {}).get("value")),
            "staged_xml_parse": parse_ok,
        },
        "string_array_check": {"pass": array_items == ["最新优先", "最旧优先", "播放最多"], "items": array_items},
        "plurals_check": {"pass": list(plurals) == ["one", "other"] and all("%1$d" in value for value in plurals.values()), "items": plurals},
        "target_only_preservation_check": {
            "pass": result.get("preserved_target_only_count", 0) > 0 and LEGACY_RESOURCE_KEY in result.get("preserved_target_only_keys", []),
            "preserved_target_only_count": result.get("preserved_target_only_count", 0),
            "preserved_target_only_keys": result.get("preserved_target_only_keys", []),
        },
    }


def _qa_check(source_path: Path, staged_target: Path) -> dict[str, Any]:
    qa = android.validate_pair(source_path, staged_target)
    drift_target = staged_target.parent / "strings-drift.xml"
    drift_text = staged_target.read_text(encoding="utf-8").replace("%2$d%%", "complete", 1)
    drift_text = drift_text.replace('        <item quantity="other">%1$d 集</item>\n', "", 1)
    drift_target.write_text(drift_text, encoding="utf-8", newline="\n")
    drift_qa = android.validate_pair(source_path, drift_target)
    drift_categories = {item.get("category") for item in drift_qa.get("items", [])}
    escape_drift_target = staged_target.parent / "strings-escape-drift.xml"
    escape_drift_text = staged_target.read_text(encoding="utf-8").replace("Can\\'t", "Cant", 1)
    escape_drift_text = escape_drift_text.replace("\\n", " ", 1).replace("\\t", " ", 1)
    escape_drift_target.write_text(escape_drift_text, encoding="utf-8", newline="\n")
    escape_drift_qa = android.validate_pair(source_path, escape_drift_target)
    escape_drift_categories = {item.get("category") for item in escape_drift_qa.get("items", [])}
    escape_drift_detected = bool({"escape_missing", "escape_drift", "malformed_escape", "percent_literal_drift"} & escape_drift_categories)
    known_unsupported_items = []
    if any(item.get("segment_id") == "string:unsupported_link" for item in qa.get("items", [])):
        known_unsupported_items.append(
            {
                "category": "unsupported_inline_markup",
                "severity": "warning",
                "status": "known_unsupported",
                "message": "inline markup with attributes is reported as unsupported_or_skipped_resource",
            }
        )
    return {
        "pass": (
            qa["summary"]["blocking_count"] == 0
            and "placeholder_parity" in drift_categories
            and "translation_coverage" in drift_categories
            and escape_drift_detected
        ),
        "status": "known_unsupported" if known_unsupported_items else qa["status"],
        "adapter_qa_status": qa["status"],
        "adapter_qa": qa,
        "drift_qa_status": drift_qa["status"],
        "drift_qa": drift_qa,
        "escape_drift_qa_status": escape_drift_qa["status"],
        "escape_drift_qa": escape_drift_qa,
        "escape_drift_detected": escape_drift_detected,
        "known_unsupported_items": known_unsupported_items,
        "qa_status_taxonomy": ["pass", "pass_with_warnings", "fail", "known_unsupported"],
    }


def _escape_signature_check(source_segments: list[dict[str, Any]], generated_segments: list[dict[str, Any]]) -> dict[str, Any]:
    normal_segments = _normal_generation_segments(source_segments)
    work_packet = {"target_locale": TARGET_LOCALE, "segments": normal_segments}
    valid_qa = validate_generated_segments(work_packet, generated_segments)
    protected = _protected_escapes_detected(source_segments)
    negative_missing = _negative_generated_case(
        work_packet,
        generated_segments,
        "string:multiline_help",
        "Line one Line two Indented",
        {"escape_missing", "escape_drift"},
    )
    negative_percent = _negative_generated_case(
        work_packet,
        generated_segments,
        "string:delete_files",
        "这将永久删除 %1$d 个文件（已完成 %2$d%）。",
        {"percent_literal_drift", "malformed_escape", "placeholder_parity"},
    )
    negative_malformed = _negative_generated_case(
        work_packet,
        generated_segments,
        "string:cant_sync",
        "Dangling backslash \\",
        {"malformed_escape"},
    )
    valid_categories = _qa_categories(valid_qa)
    return {
        "pass": (
            valid_qa["status"] == "pass"
            and {"\\'", '"', "\\n", "\\t", "%%"}.issubset(set(protected))
            and negative_missing["pass"]
            and negative_percent["pass"]
            and negative_malformed["pass"]
        ),
        "checked_segments": sum(1 for segment in normal_segments if segment.get("constraints", {}).get("escape_signature")),
        "protected_escapes_detected": protected,
        "valid_generated_qa_status": valid_qa["status"],
        "valid_generated_categories": sorted(valid_categories),
        "missing_escape_issues": _count_categories([negative_missing["qa"]], {"escape_missing", "escape_drift"}),
        "malformed_escape_issues": _count_categories([negative_malformed["qa"], negative_percent["qa"]], {"malformed_escape"}),
        "percent_literal_issues": _count_categories([negative_percent["qa"]], {"percent_literal_drift"}),
        "negative_checks": [negative_missing, negative_percent, negative_malformed],
        "known_limitations": [],
    }


def _inline_markup_check(
    source_segments: list[dict[str, Any]],
    generated_segments: list[dict[str, Any]],
    staging: dict[str, Any],
) -> dict[str, Any]:
    normal_segments = _normal_generation_segments(source_segments)
    work_packet = {"target_locale": TARGET_LOCALE, "segments": normal_segments}
    valid_qa = validate_generated_segments(work_packet, generated_segments)
    markup_segments = [
        segment
        for segment in normal_segments
        if segment.get("constraints", {}).get("markup_signature")
    ]
    protected_tags = _protected_markup_tags(normal_segments)
    negative_missing = _negative_generated_case(
        work_packet,
        generated_segments,
        "string:learn_more",
        "Tap Learn more to continue.",
        {"markup_missing", "markup_mismatch"},
    )
    negative_broken_pair = _negative_generated_case(
        work_packet,
        generated_segments,
        "string:learn_more",
        "Tap <b>Learn more</i> to continue.",
        {"malformed_markup", "markup_mismatch"},
    )
    negative_unsupported = _negative_generated_case(
        work_packet,
        generated_segments,
        "string:learn_more",
        "Tap <strong>Learn more</strong> to continue.",
        {"unsupported_markup", "markup_missing", "markup_mismatch"},
    )
    # Inline attribute markup negative checks
    neg_href_missing = _negative_generated_case(
        work_packet,
        generated_segments,
        "string:privacy_link",
        'Read our <a>privacy policy</a>.',
        {"markup_attribute_missing", "markup_missing"},
    )
    neg_href_drift = _negative_generated_case(
        work_packet,
        generated_segments,
        "string:privacy_link",
        'Read our <a href="https://evil.example.com">privacy policy</a>.',
        {"markup_url_drift", "markup_attribute_drift"},
    )
    neg_unsupported_attr = _negative_generated_case(
        work_packet,
        generated_segments,
        "string:privacy_link",
        'Read our <a href="https://example.com/privacy" onclick="alert(1)">privacy policy</a>.',
        {"unsupported_markup"},
    )
    supported_tags = ["b", "i", "u", "a"]
    return {
        "pass": (
            valid_qa["status"] == "pass"
            and {"b", "i", "u"}.issubset(set(protected_tags))
            and len(markup_segments) >= 2
            and bool(staging["inline_html_check"]["pass"])
            and negative_missing["pass"]
            and negative_broken_pair["pass"]
            and negative_unsupported["pass"]
            and neg_href_missing["pass"]
            and neg_href_drift["pass"]
            and neg_unsupported_attr["pass"]
        ),
        "supported_tags": supported_tags,
        "checked_segments": len(markup_segments),
        "markup_signature_segments": len(markup_segments),
        "protected_tags_detected": protected_tags,
        "valid_generated_qa_status": valid_qa["status"],
        "missing_markup_issues": _count_categories([negative_missing["qa"], negative_unsupported["qa"]], {"markup_missing", "markup_mismatch"}),
        "malformed_markup_issues": _count_categories([negative_broken_pair["qa"]], {"malformed_markup"}),
        "unsupported_markup_issues": _count_categories([negative_unsupported["qa"], neg_unsupported_attr["qa"]], {"unsupported_markup", "unsupported_markup"}),
        "href_preserved": valid_qa["status"] == "pass",
        "missing_attribute_issues": _count_categories([neg_href_missing["qa"]], {"markup_attribute_missing"}),
        "attribute_drift_issues": 0,
        "url_drift_issues": _count_categories([neg_href_drift["qa"]], {"markup_url_drift"}),
        "unsupported_attribute_issues": _count_categories([neg_unsupported_attr["qa"]], {"unsupported_markup"}),
        "malformed_markup_count": _count_categories([negative_broken_pair["qa"]], {"malformed_markup"}),
        "supported_inline_markup_staged": bool(staging["inline_html_check"]["pass"]),
        "negative_checks": [negative_missing, negative_broken_pair, negative_unsupported, neg_href_missing, neg_href_drift, neg_unsupported_attr],
        "known_limitations": ["complex nested markup unsupported"],
    }


def _cdata_check(
    source_segments: list[dict[str, Any]],
    generated_segments: list[dict[str, Any]],
    source_path: Path,
    staged_target: Path,
) -> dict[str, Any]:
    normal_segments = _normal_generation_segments(source_segments)
    work_packet = {"target_locale": TARGET_LOCALE, "segments": normal_segments}
    cdata_segments = [
        segment
        for segment in normal_segments
        if segment.get("constraints", {}).get("cdata")
    ]
    staged_text = staged_target.read_text(encoding="utf-8")
    cdata_sections = _cdata_sections(staged_text)
    boundary_preserved = {"html_cdata", "plain_cdata"}.issubset(set(cdata_sections))
    boundary_loss_target = staged_target.parent / "strings-cdata-boundary-loss.xml"
    boundary_loss_target.write_text(_drop_cdata_boundaries(staged_text), encoding="utf-8", newline="\n")
    boundary_loss_qa = android.validate_pair(source_path, boundary_loss_target)
    unsafe_generated = [dict(segment) for segment in generated_segments]
    for segment in unsafe_generated:
        if segment.get("context", {}).get("resource_key") == "string:plain_cdata":
            segment["target"] = "Unsafe ]]> terminator"
            break
    unsafe_qa = validate_generated_segments(work_packet, unsafe_generated)
    try:
        android.stage_rebuild(source_path, unsafe_generated, staged_target.parent / "unsafe-cdata-staging", TARGET_LOCALE, source_path.parents[5], preserve_target_only=True)
        unsafe_stage_blocked = False
    except ValueError as exc:
        unsafe_stage_blocked = "]]>" in str(exc)
    return {
        "pass": (
            len(cdata_segments) == 2
            and boundary_preserved
            and _xml_parse_ok(staged_target)
            and "cdata_boundary_missing" in _qa_categories(boundary_loss_qa)
            and "cdata_terminator_unsafe" in _qa_categories(unsafe_qa)
            and unsafe_stage_blocked
        ),
        "cdata_segments": len(cdata_segments),
        "cdata_boundary_preserved": boundary_preserved,
        "unsafe_terminator_issues": _count_categories([unsafe_qa], {"cdata_terminator_unsafe"}),
        "boundary_missing_issues": _count_categories([boundary_loss_qa], {"cdata_boundary_missing"}),
        "staged_xml_parse": _xml_parse_ok(staged_target),
        "cdata_sections": cdata_sections,
        "unsafe_staging_blocked": unsafe_stage_blocked,
        "negative_checks": [
            {
                "name": "cdata_boundary_dropped",
                "pass": "cdata_boundary_missing" in _qa_categories(boundary_loss_qa),
                "status": boundary_loss_qa["status"],
                "categories": sorted(_qa_categories(boundary_loss_qa)),
                "qa": boundary_loss_qa,
            },
            {
                "name": "cdata_unsafe_terminator",
                "pass": "cdata_terminator_unsafe" in _qa_categories(unsafe_qa) and unsafe_stage_blocked,
                "status": unsafe_qa["status"],
                "categories": sorted(_qa_categories(unsafe_qa)),
                "staging_blocked": unsafe_stage_blocked,
                "qa": unsafe_qa,
            },
        ],
        "known_limitations": [],
    }


def _comment_round_trip_check(source_path: Path, staged_target: Path) -> dict[str, Any]:
    source_doc = android._read_document(source_path)  # noqa: SLF001 - benchmark probes adapter-observed comments.
    staged_doc = android._read_document(staged_target)  # noqa: SLF001 - benchmark probes adapter-observed comments.
    source_comments = source_doc["comments"]
    staged_comments = staged_doc["comments"]
    string_comment = staged_comments.get("string:settings_title", {}).get("comment") == "Settings screen"
    array_comment = staged_comments.get("string-array:sort_options", {}).get("comment") == "Sort options shown in the queue screen"
    plurals_comment = staged_comments.get("plurals:episode_count", {}).get("comment") == "Number of downloaded episodes"
    target_only_comment = staged_comments.get(LEGACY_RESOURCE_KEY, {}).get("comment") == "Legacy removed key preserved for owner review"
    staged_text = staged_target.read_text(encoding="utf-8")

    missing_target = staged_target.parent / "strings-comment-missing.xml"
    missing_target.write_text(_drop_comment(staged_text, "Settings screen"), encoding="utf-8", newline="\n")
    missing_qa = android.validate_pair(source_path, missing_target)

    misattached_target = staged_target.parent / "strings-comment-misattached.xml"
    misattached_target.write_text(_misattach_comment(staged_text, "Settings screen"), encoding="utf-8", newline="\n")
    misattached_qa = android.validate_pair(source_path, misattached_target)

    duplicate_target = staged_target.parent / "strings-comment-duplicate.xml"
    duplicate_target.write_text(_duplicate_comment(staged_text, "Settings screen"), encoding="utf-8", newline="\n")
    duplicate_qa = android.validate_pair(source_path, duplicate_target)

    return {
        "pass": (
            len(source_comments) >= 3
            and len(staged_comments) >= len(source_comments)
            and string_comment
            and array_comment
            and plurals_comment
            and target_only_comment
            and "comment_missing" in _qa_categories(missing_qa)
            and "comment_misattached" in _qa_categories(misattached_qa)
            and "comment_duplicate" in _qa_categories(duplicate_qa)
            and _xml_parse_ok(staged_target)
        ),
        "source_comment_count": len(source_comments),
        "staged_comment_count": len(staged_comments),
        "resource_comments_preserved": string_comment and array_comment and plurals_comment,
        "string_comment_preserved": string_comment,
        "array_comment_preserved": array_comment,
        "plurals_comment_preserved": plurals_comment,
        "target_only_comment_preserved": target_only_comment,
        "missing_comment_issues": _count_categories([missing_qa], {"comment_missing"}),
        "misattached_comment_issues": _count_categories([misattached_qa], {"comment_misattached"}),
        "duplicate_comment_issues": _count_categories([duplicate_qa], {"comment_duplicate"}),
        "staged_xml_parse": _xml_parse_ok(staged_target),
        "negative_checks": [
            {
                "name": "comment_dropped",
                "pass": "comment_missing" in _qa_categories(missing_qa),
                "status": missing_qa["status"],
                "categories": sorted(_qa_categories(missing_qa)),
                "qa": missing_qa,
            },
            {
                "name": "comment_misattached",
                "pass": "comment_misattached" in _qa_categories(misattached_qa),
                "status": misattached_qa["status"],
                "categories": sorted(_qa_categories(misattached_qa)),
                "qa": misattached_qa,
            },
            {
                "name": "comment_duplicate",
                "pass": "comment_duplicate" in _qa_categories(duplicate_qa),
                "status": duplicate_qa["status"],
                "categories": sorted(_qa_categories(duplicate_qa)),
                "qa": duplicate_qa,
            },
        ],
        "known_limitations": [],
    }


def _negative_generated_case(
    work_packet: dict[str, Any],
    generated_segments: list[dict[str, Any]],
    resource_key: str,
    target: str,
    expected_categories: set[str],
) -> dict[str, Any]:
    candidate = [dict(segment) for segment in generated_segments]
    for segment in candidate:
        if segment.get("context", {}).get("resource_key") == resource_key:
            segment["target"] = target
            break
    qa = validate_generated_segments(work_packet, candidate)
    categories = _qa_categories(qa)
    return {
        "name": f"negative_{resource_key}",
        "pass": qa["status"] != "pass" and bool(categories & expected_categories),
        "status": qa["status"],
        "categories": sorted(categories),
        "expected_categories": sorted(expected_categories),
        "qa": qa,
    }


def _protected_escapes_detected(segments: list[dict[str, Any]]) -> list[str]:
    found: set[str] = set()
    for segment in segments:
        found.update(str(item) for item in segment.get("constraints", {}).get("escape_signature", []))
    order = ["\\'", '"', "\\n", "\\t", "%%"]
    return [item for item in order if item in found]


def _protected_markup_tags(segments: list[dict[str, Any]]) -> list[str]:
    found: set[str] = set()
    for segment in segments:
        for item in segment.get("constraints", {}).get("markup_signature", []):
            if isinstance(item, dict) and item.get("tag"):
                found.add(str(item["tag"]))
    return [item for item in ["b", "i", "u", "a"] if item in found]


def _qa_categories(qa: dict[str, Any]) -> set[str]:
    return {str(item.get("category")) for item in qa.get("items", [])}


def _count_categories(qa_results: list[dict[str, Any]], categories: set[str]) -> int:
    return sum(1 for qa in qa_results for item in qa.get("items", []) if item.get("category") in categories)


def _run_mode(work_root: Path, operating_mode: str, reference_policy: str) -> dict[str, Any]:
    project_root = work_root / operating_mode / "project"
    output_root = work_root / operating_mode / "runs"
    _copy_fixture(project_root, include_target=True)
    result = run_localize(
        project_root,
        SOURCE_LOCALE,
        [TARGET_LOCALE],
        source_files=[SOURCE_FILE],
        output_root=output_root,
        run_id=f"{operating_mode}-001",
        max_segments=100,
        synthetic_draft=True,
        operating_mode=operating_mode,
        reference_policy=reference_policy,
    )
    return {"project_root": project_root.as_posix(), "result": result}


def _blind_leakage_check(result: dict[str, Any], target_path: Path) -> dict[str, Any]:
    forbidden = _target_texts(target_path)
    forbidden.extend([LEGACY_KEY, LEGACY_RESOURCE_KEY, LEGACY_TEXT])
    leakage = validate_no_leakage(_generation_facing_artifacts(result["artifacts"]), forbidden)
    return {
        "pass": leakage["pass"],
        "forbidden_count": len(forbidden),
        "matches": leakage["matches"],
        "message": "blind generation-facing artifacts do not contain existing zh-CN target text" if leakage["pass"] else "blind generation leaked existing zh-CN target text",
    }


def _maintenance_preservation_check(result: dict[str, Any]) -> dict[str, Any]:
    staging = read_json(Path(result["artifacts"]["staging_result"]))
    output = staging["outputs"][0]
    staged_target = Path(output["output"])
    staged_text = staged_target.read_text(encoding="utf-8")
    generated_records = read_jsonl(Path(result["artifacts"]["generated_segments"]))
    generated_keys = {record.get("context", {}).get("resource_key") for record in generated_records}
    keys = output.get("preserved_target_only_keys", [])
    return {
        "pass": (
            LEGACY_TEXT in staged_text
            and LEGACY_RESOURCE_KEY not in generated_keys
            and int(output.get("preserved_target_only_count", 0)) > 0
            and LEGACY_RESOURCE_KEY in keys
        ),
        "staged_target": staged_target.as_posix(),
        "legacy_present_in_staged_output": LEGACY_TEXT in staged_text,
        "legacy_counted_as_generated": LEGACY_RESOURCE_KEY in generated_keys,
        "preserved_target_only_count": output.get("preserved_target_only_count", 0),
        "preserved_target_only_keys": keys,
    }


def _complex_markup_policy_check(
    source_segments: list[dict[str, Any]],
    generated_segments: list[dict[str, Any]],
    direct_staging: dict[str, Any],
    blind_result: dict[str, Any],
    maintenance_result: dict[str, Any],
    existing_target_path: Path,
) -> dict[str, Any]:
    policy = _validate_complex_markup_segments(source_segments)
    generated_keys = {segment.get("context", {}).get("resource_key") for segment in generated_segments}
    packet_keys = _work_packet_resource_keys(Path(blind_result["artifacts"]["work_packets"]))
    sent_keys = sorted(COMPLEX_MARKUP_KEYS & (generated_keys | packet_keys))

    maintenance_staging = read_json(Path(maintenance_result["artifacts"]["staging_result"]))
    maintenance_target = Path(maintenance_staging["outputs"][0]["output"])
    existing = _resources_by_key(existing_target_path)
    maintained = _resources_by_key(maintenance_target)
    preserved_keys = sorted(
        key
        for key in COMPLEX_MARKUP_KEYS
        if maintained.get(key, {}).get("value") == existing.get(key, {}).get("value")
        and maintained.get(key, {}).get("markup_structure_signature") == existing.get(key, {}).get("markup_structure_signature")
    )
    direct_target = Path(direct_staging["staged_target"])
    preserved_without_corruption = set(preserved_keys) == COMPLEX_MARKUP_KEYS
    negative_checks = _complex_markup_negative_checks(source_segments)
    passed = (
        policy["pass"]
        and not sent_keys
        and preserved_without_corruption
        and _xml_parse_ok(direct_target)
        and _xml_parse_ok(maintenance_target)
        and all(item["pass"] for item in negative_checks)
    )
    return {
        "pass": passed,
        "unsupported_markup_detected": policy["unsupported_markup_detected"],
        "complex_nested_detected": policy["complex_nested_detected"],
        "unsupported_attribute_detected": policy["unsupported_attribute_detected"],
        "unsupported_tag_detected": policy["unsupported_tag_detected"],
        "owner_review_required_count": policy["owner_review_required_count"],
        "sent_to_normal_generation_count": len(sent_keys),
        "sent_to_normal_generation_keys": sent_keys,
        "preserved_without_corruption": preserved_without_corruption,
        "preserved_existing_target_keys": preserved_keys,
        "staged_xml_parse": _xml_parse_ok(direct_target) and _xml_parse_ok(maintenance_target),
        "negative_checks": negative_checks,
        "known_limitations": ["complex nested markup not automatically localized"],
    }


def _array_plural_markup_policy_check(
    source_segments: list[dict[str, Any]],
    generated_segments: list[dict[str, Any]],
    direct_staging: dict[str, Any],
    blind_result: dict[str, Any],
    maintenance_result: dict[str, Any],
    existing_target_path: Path,
) -> dict[str, Any]:
    by_key = {segment.get("context", {}).get("resource_key"): segment for segment in source_segments}
    supported_array = [by_key[key] for key in sorted(SUPPORTED_ARRAY_MARKUP_KEYS) if key in by_key]
    supported_plural = [by_key[key] for key in sorted(SUPPORTED_PLURAL_MARKUP_KEYS) if key in by_key]
    policy = _validate_array_plural_segments(source_segments)

    normal_segments = _normal_generation_segments(source_segments)
    valid_qa = validate_generated_segments(
        {"target_locale": TARGET_LOCALE, "segments": normal_segments},
        generated_segments,
    )
    plural_markup_loss = _negative_generated_case(
        {"target_locale": TARGET_LOCALE, "segments": normal_segments},
        generated_segments,
        "plurals:rich_episode_count#one",
        "%1$d 集",
        {"markup_missing", "markup_mismatch"},
    )

    generated_keys = {segment.get("context", {}).get("resource_key") for segment in generated_segments}
    packet_keys = _work_packet_resource_keys(Path(blind_result["artifacts"]["work_packets"]))
    unsupported_keys = UNSUPPORTED_ARRAY_MARKUP_KEYS | UNSUPPORTED_PLURAL_MARKUP_KEYS
    sent_keys = sorted(unsupported_keys & (generated_keys | packet_keys))

    direct_target = Path(direct_staging["staged_target"])
    staged_document = android._read_document(direct_target)  # noqa: SLF001 - benchmark checks item order and structure.
    staged = {resource["key"]: resource for resource in staged_document["resources"]}
    expected = _resources_by_key(existing_target_path)
    supported_keys = SUPPORTED_ARRAY_MARKUP_KEYS | SUPPORTED_PLURAL_MARKUP_KEYS
    supported_markup_preserved = all(
        staged.get(key, {}).get("value") == expected.get(key, {}).get("value")
        and staged.get(key, {}).get("markup_structure_signature") == expected.get(key, {}).get("markup_structure_signature")
        for key in supported_keys
    )
    rich_array_order = [
        resource["key"]
        for resource in staged_document["resources"]
        if resource.get("name") == "rich_sort_options"
    ]
    rich_plural_quantities = [
        resource.get("quantity")
        for resource in staged_document["resources"]
        if resource.get("name") == "rich_episode_count"
    ]

    maintenance_staging = read_json(Path(maintenance_result["artifacts"]["staging_result"]))
    maintenance_target = Path(maintenance_staging["outputs"][0]["output"])
    maintained = _resources_by_key(maintenance_target)
    preserved_keys = sorted(
        key
        for key in unsupported_keys
        if maintained.get(key, {}).get("value") == expected.get(key, {}).get("value")
        and maintained.get(key, {}).get("markup_structure_signature") == expected.get(key, {}).get("markup_structure_signature")
    )
    existing_preserved = set(preserved_keys) == unsupported_keys

    blind_staging = read_json(Path(blind_result["artifacts"]["staging_result"]))
    blind_target = Path(blind_staging["outputs"][0]["output"])
    blind_resources = _resources_by_key(blind_target)
    source_resources = _resources_by_key(ROOT / "fixture" / SOURCE_FILE)
    source_fallback_preserved = all(
        blind_resources.get(key, {}).get("value") == source_resources.get(key, {}).get("value")
        and blind_resources.get(key, {}).get("markup_structure_signature") == source_resources.get(key, {}).get("markup_structure_signature")
        for key in unsupported_keys
    )

    negative_policy_checks = _array_plural_negative_policy_checks(source_segments)
    negative_checks = [*negative_policy_checks, plural_markup_loss]
    passed = (
        len(supported_array) == len(SUPPORTED_ARRAY_MARKUP_KEYS)
        and len(supported_plural) == len(SUPPORTED_PLURAL_MARKUP_KEYS)
        and all(is_generation_eligible(segment) and segment.get("markup_signature") for segment in supported_array + supported_plural)
        and all(segment.get("constraints", {}).get("placeholders") == ["%1$d"] for segment in supported_plural)
        and policy["pass"]
        and not sent_keys
        and valid_qa["status"] == "pass"
        and supported_markup_preserved
        and rich_array_order == [
            "string-array:rich_sort_options[0]",
            "string-array:rich_sort_options[1]",
            "string-array:rich_sort_options[2]",
        ]
        and rich_plural_quantities == ["one", "other"]
        and existing_preserved
        and source_fallback_preserved
        and _xml_parse_ok(direct_target)
        and _xml_parse_ok(maintenance_target)
        and all(check["pass"] for check in negative_checks)
    )
    return {
        "pass": passed,
        "supported_array_markup_segments": len(supported_array),
        "supported_plural_markup_segments": len(supported_plural),
        "unsupported_array_items_detected": policy["unsupported_array_items_detected"],
        "unsupported_plural_items_detected": policy["unsupported_plural_items_detected"],
        "owner_review_required_count": policy["owner_review_required_count"],
        "sent_to_normal_generation_count": len(sent_keys),
        "sent_to_normal_generation_keys": sent_keys,
        "existing_target_preserved_in_maintenance": existing_preserved,
        "source_fallback_preserved_without_target_use": source_fallback_preserved,
        "preserved_existing_target_keys": preserved_keys,
        "supported_markup_preserved": supported_markup_preserved,
        "placeholder_qa_preserved": all(segment.get("constraints", {}).get("placeholders") == ["%1$d"] for segment in supported_plural),
        "array_item_order_preserved": len(rich_array_order) == 3,
        "plural_quantity_branches_preserved": rich_plural_quantities == ["one", "other"],
        "staged_xml_parse": _xml_parse_ok(direct_target) and _xml_parse_ok(maintenance_target),
        "valid_generated_qa_status": valid_qa["status"],
        "negative_checks": negative_checks,
        "known_limitations": [],
    }


def _validate_array_plural_segments(segments: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {segment.get("context", {}).get("resource_key"): segment for segment in segments}
    array_items = [by_key[key] for key in sorted(UNSUPPORTED_ARRAY_MARKUP_KEYS) if key in by_key]
    plural_items = [by_key[key] for key in sorted(UNSUPPORTED_PLURAL_MARKUP_KEYS) if key in by_key]
    scoped = [*array_items, *plural_items]
    sent = [segment for segment in scoped if is_generation_eligible(segment)]
    owner_count = sum(bool(segment.get("owner_review_required")) for segment in scoped)
    result = {
        "unsupported_array_items_detected": len(array_items),
        "unsupported_plural_items_detected": len(plural_items),
        "owner_review_required_count": owner_count,
        "sent_to_normal_generation_count": len(sent),
    }
    result["pass"] = (
        len(array_items) == len(UNSUPPORTED_ARRAY_MARKUP_KEYS)
        and len(plural_items) == len(UNSUPPORTED_PLURAL_MARKUP_KEYS)
        and all(segment.get("review_required_reasons") for segment in scoped)
        and owner_count == len(scoped)
        and not sent
    )
    return result


def _array_plural_negative_policy_checks(source_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = [
        ("unsupported_array_item_sent_to_normal_generation", "string-array:complex_sort_options[0]"),
        ("unsupported_plural_item_sent_to_normal_generation", "plurals:complex_episode_count#one"),
    ]
    checks: list[dict[str, Any]] = []
    for name, resource_key in cases:
        tampered = json.loads(json.dumps(source_segments))
        for segment in tampered:
            if segment.get("context", {}).get("resource_key") != resource_key:
                continue
            segment["generation_eligible"] = True
            segment["owner_review_required"] = False
            segment["workflow_status"] = "generation_candidate"
            break
        result = _validate_array_plural_segments(tampered)
        checks.append(
            {
                "name": name,
                "pass": not result["pass"] and result["sent_to_normal_generation_count"] > 0,
                "policy_validation": result,
            }
        )
    return checks


def _validate_complex_markup_segments(segments: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {segment.get("context", {}).get("resource_key"): segment for segment in segments}
    scoped = [by_key[key] for key in sorted(COMPLEX_MARKUP_KEYS) if key in by_key]
    reasons = {key: set(by_key.get(key, {}).get("review_required_reasons", [])) for key in COMPLEX_MARKUP_KEYS}
    sent = [segment for segment in scoped if is_generation_eligible(segment)]
    owner_count = sum(bool(segment.get("owner_review_required")) for segment in scoped)
    result = {
        "unsupported_markup_detected": len(scoped) == len(COMPLEX_MARKUP_KEYS),
        "complex_nested_detected": "complex_nested_markup" in reasons["string:nested_markup"],
        "unsupported_attribute_detected": all(
            "unsupported_markup_attribute" in reasons[key]
            for key in ("string:styled_bold", "string:complex_link")
        ),
        "unsupported_tag_detected": "unsupported_markup_tag" in reasons["string:font_markup"],
        "owner_review_required_count": owner_count,
        "sent_to_normal_generation_count": len(sent),
    }
    result["pass"] = (
        all(value for key, value in result.items() if key.endswith("_detected"))
        and owner_count == len(COMPLEX_MARKUP_KEYS)
        and not sent
    )
    return result


def _complex_markup_negative_checks(source_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = [
        ("complex_nested_markup_treated_as_normal", "string:nested_markup", None),
        ("unsupported_tag_sent_without_owner_review", "string:font_markup", None),
        ("unsupported_attribute_silently_accepted", "string:styled_bold", []),
    ]
    checks: list[dict[str, Any]] = []
    for name, resource_key, replacement_reasons in cases:
        tampered = json.loads(json.dumps(source_segments))
        for segment in tampered:
            if segment.get("context", {}).get("resource_key") != resource_key:
                continue
            segment["generation_eligible"] = True
            segment["owner_review_required"] = False
            segment["status"] = "new"
            if replacement_reasons is not None:
                segment["review_required_reasons"] = replacement_reasons
            break
        result = _validate_complex_markup_segments(tampered)
        checks.append(
            {
                "name": name,
                "pass": not result["pass"] and result["sent_to_normal_generation_count"] > 0,
                "policy_validation": result,
            }
        )
    return checks


def _work_packet_resource_keys(packet_dir: Path) -> set[str]:
    keys: set[str] = set()
    for path in sorted(packet_dir.glob("*.json")):
        packet = read_json(path)
        keys.update(
            str(segment.get("context", {}).get("resource_key"))
            for segment in packet.get("segments", [])
            if segment.get("context", {}).get("resource_key")
        )
    return keys


def _normal_generation_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [segment for segment in segments if is_generation_eligible(segment)]


def _resources_by_key(path: Path) -> dict[str, dict[str, Any]]:
    document = android._read_document(path)  # noqa: SLF001 - benchmark compares adapter-observed preservation.
    return {resource["key"]: resource for resource in document["resources"]}


def validate_no_leakage(paths: list[str], forbidden_strings: list[str]) -> dict[str, Any]:
    matches: list[dict[str, str]] = []
    for value in paths:
        path = Path(value)
        candidates = [item for item in path.rglob("*") if item.is_file()] if path.is_dir() else [path] if path.is_file() else []
        for candidate in candidates:
            try:
                text = candidate.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for forbidden in sorted({item for item in forbidden_strings if item}, key=len, reverse=True):
                if forbidden in text:
                    matches.append({"path": candidate.as_posix(), "text": forbidden})
    return {"pass": not matches, "matches": matches, "scanned_path_count": len(paths)}


def _generation_facing_artifacts(artifacts: dict[str, Any]) -> list[str]:
    keys = [
        "work_packets",
        "draft_requests",
        "prompts",
        "prompt_manifest",
        "generation_handoff",
        "generation_readme",
        "generated_segments",
    ]
    return [str(artifacts[key]) for key in keys if key in artifacts]


def _target_texts(target_path: Path) -> list[str]:
    tree = ElementTree.parse(target_path)
    texts: list[str] = []
    for resource in list(tree.getroot()):
        if _local_tag(resource.tag) == "string":
            text = "".join(resource.itertext()).strip()
            if text:
                texts.append(text)
            continue
        for item in list(resource):
            if _local_tag(item.tag) != "item":
                continue
            text = "".join(item.itertext()).strip()
            if text:
                texts.append(text)
    return texts


def _local_tag(tag: Any) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _strip_segments(extraction: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in extraction.items() if key != "segments"}


def _failed_checks(checks: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not checks["extraction"]["pass"]:
        failures.append("extraction check failed")
    if not checks["staging"]["pass"]:
        failures.append("staging check failed")
    if not checks["qa"]["pass"]:
        failures.append("qa check failed")
    if not checks["escape_signature"]["pass"]:
        failures.append("escape signature check failed")
    if not checks["inline_markup"]["pass"]:
        failures.append("inline markup check failed")
    if not checks["cdata"]["pass"]:
        failures.append("cdata check failed")
    if not checks["comments"]["pass"]:
        failures.append("comment round-trip check failed")
    if not checks["blind_leakage"]["pass"]:
        failures.append("blind leakage check failed")
    if not checks["maintenance_preservation"]["pass"]:
        failures.append("maintenance preservation check failed")
    if not checks["complex_markup_policy"]["pass"]:
        failures.append("complex markup boundary policy check failed")
    if not checks["array_plural_markup_policy"]["pass"]:
        failures.append("array/plural markup boundary policy check failed")
    return failures


def _known_limitations(extraction: dict[str, Any], staging: dict[str, Any], qa: dict[str, Any]) -> list[dict[str, str]]:
    limitations: list[dict[str, str]] = []
    if extraction["unsupported_high_risk"]["unsupported_inline_markup"]:
        limitations.append(
            {
                "id": "android_complex_markup_not_automatically_localized",
                "severity": "known_unsupported",
                "message": "Complex, unsupported-tag, and unsupported-attribute markup is preserved and requires owner review; it is not automatically localized.",
            }
        )
    if qa["known_unsupported_items"]:
        limitations.append(
            {
                "id": "android_known_unsupported_qa_items",
                "severity": "known_unsupported",
                "message": "Benchmark-level QA records unsupported inline markup attributes.",
            }
        )
    return limitations


def _verdict(status: str) -> str:
    if status == "pass":
        return "V0.2.2-H ANDROID ARRAY/PLURAL MARKUP BOUNDARY POLICY: PASS"
    if status == "partial":
        return "V0.2.2-H ANDROID ARRAY/PLURAL MARKUP BOUNDARY POLICY: PARTIAL"
    return "V0.2.2-H ANDROID ARRAY/PLURAL MARKUP BOUNDARY POLICY: FAIL"


def _xml_parse_ok(path: Path) -> bool:
    try:
        ElementTree.parse(path)
        return True
    except ElementTree.ParseError:
        return False


def _find_named(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    for element in list(root):
        if element.attrib.get("name") == name:
            return element
    return None


def _array_items(root: ElementTree.Element, name: str) -> list[str]:
    element = _find_named(root, name)
    if element is None:
        return []
    return [child.text or "" for child in list(element) if child.tag.endswith("item")]


def _plural_items(root: ElementTree.Element, name: str) -> dict[str, str]:
    element = _find_named(root, name)
    if element is None:
        return {}
    return {child.attrib.get("quantity", ""): child.text or "" for child in list(element) if child.tag.endswith("item")}


def _child_tags(element: ElementTree.Element | None) -> list[str]:
    if element is None:
        return []
    return [str(child.tag).rsplit("}", 1)[-1] for child in list(element)]


def _cdata_sections(text: str) -> list[str]:
    sections: list[str] = []
    pattern = re.compile(r"<string\b(?P<attrs>[^>]*)>\s*<!\[CDATA\[.*?\]\]>\s*</string>", re.DOTALL)
    name_pattern = re.compile(r'\bname="(?P<name>[^"]+)"')
    for match in pattern.finditer(text):
        name_match = name_pattern.search(match.group("attrs"))
        if name_match:
            sections.append(name_match.group("name"))
    return sections


def _drop_cdata_boundaries(text: str) -> str:
    pattern = re.compile(
        r"(?P<open><string\b(?P<attrs>[^>]*)>)\s*<!\[CDATA\[(?P<value>.*?)\]\]>\s*(?P<close></string>)",
        re.DOTALL,
    )

    def replace(match: re.Match[str]) -> str:
        return f"{match.group('open')}{escape(match.group('value'))}{match.group('close')}"

    return pattern.sub(replace, text)


def _drop_comment(text: str, comment: str) -> str:
    return text.replace(f"    <!-- {comment} -->\n", "", 1)


def _misattach_comment(text: str, comment: str) -> str:
    without_comment = _drop_comment(text, comment)
    return without_comment.replace('    <string name="app_name"', f"    <!-- {comment} -->\n    <string name=\"app_name\"", 1)


def _duplicate_comment(text: str, comment: str) -> str:
    marker = f"    <!-- {comment} -->\n"
    return text.replace(marker, marker + marker, 1)


def render_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# v0.2.2-H Android Array/Plural Markup Boundary Policy",
        "",
        f"- Status: `{report['status']}`",
        f"- Verdict: **{report['verdict']}**",
        f"- Fixture: `{report['fixture_path']}`",
        f"- Source locale: `{report['source_locale']}`",
        f"- Target locale: `{report['target_locale']}`",
        f"- Source segments: {report['source_segment_count']}",
        f"- Extracted segments: {report['extracted_segment_count']}",
        f"- Generated segments: {report['generated_segment_count']}",
        f"- Skipped `translatable=false`: {report['skipped_translatable_false_count']}",
        "",
        "## Checks",
        "",
        f"- Placeholders: `{report['placeholder_check_result']['pass']}`",
        f"- Escape signatures: `{report['escape_signature_check']['pass']}`",
        f"- Inline markup: `{report['inline_markup_check']['pass']}`",
        f"- CDATA boundary: `{report['cdata_check']['pass']}`",
        f"- Resource comments: `{report['comment_round_trip_check']['pass']}`",
        f"- Escapes: `{report['escape_check_result']['pass']}`",
        f"- XML entity: `{report['xml_entity_check_result']['pass']}`",
        f"- Inline HTML: `{report['inline_html_check_result']['status']}`",
        f"- CDATA: `{report['cdata_check_result']['status']}`",
        f"- String array: `{report['string_array_check_result']['pass']}`",
        f"- Plurals: `{report['plurals_check_result']['pass']}`",
        f"- Target-only preservation: `{report['target_only_preservation_check_result']['pass']}`",
        f"- Blind leakage: `{report['blind_leakage_check_result']['pass']}`",
        f"- Maintenance preservation: `{report['maintenance_preservation_check_result']['pass']}`",
        f"- Complex markup boundary policy: `{report['complex_markup_policy_check']['pass']}`",
        f"- Array/plural markup boundary policy: `{report['array_plural_markup_policy_check']['pass']}`",
        f"- QA status: `{report['qa_check_result']['status']}`",
        "",
        "## Escape Signature QA",
        "",
    ]
    escape = report["escape_signature_check"]
    lines.extend(
        [
            f"- Pass: `{escape['pass']}`",
            f"- Checked segments: {escape['checked_segments']}",
            f"- Protected escapes detected: `{', '.join(escape['protected_escapes_detected'])}`",
            f"- Missing escape issues: {escape['missing_escape_issues']}",
            f"- Malformed escape issues: {escape['malformed_escape_issues']}",
            f"- Percent literal issues: {escape['percent_literal_issues']}",
            f"- Known limitations: `{len(escape['known_limitations'])}`",
            "",
        ]
    )
    inline = report["inline_markup_check"]
    lines.extend(
        [
            "## Inline Markup QA",
            "",
            f"- Pass: `{inline['pass']}`",
            f"- Supported tags: `{', '.join(inline['supported_tags'])}`",
            f"- Checked segments: {inline['checked_segments']}",
            f"- Markup signature segments: {inline['markup_signature_segments']}",
            f"- Missing markup issues: {inline['missing_markup_issues']}",
            f"- Malformed markup issues: {inline['malformed_markup_issues']}",
            f"- Unsupported markup issues: {inline['unsupported_markup_issues']}",
            f"- Supported inline markup staged: `{inline['supported_inline_markup_staged']}`",
            f"- Known limitations: `{', '.join(inline['known_limitations'])}`",
            "",
        ]
    )
    cdata = report["cdata_check"]
    lines.extend(
        [
            "## CDATA Boundary QA",
            "",
            f"- Pass: `{cdata['pass']}`",
            f"- CDATA segments: {cdata['cdata_segments']}",
            f"- Boundary preserved: `{cdata['cdata_boundary_preserved']}`",
            f"- Unsafe terminator issues: {cdata['unsafe_terminator_issues']}",
            f"- Boundary missing issues: {cdata['boundary_missing_issues']}",
            f"- Staged XML parses: `{cdata['staged_xml_parse']}`",
            f"- Known limitations: `{len(cdata['known_limitations'])}`",
            "",
        ]
    )
    comments = report["comment_round_trip_check"]
    lines.extend(
        [
            "## Resource Comment QA",
            "",
            f"- Pass: `{comments['pass']}`",
            f"- Source comment count: {comments['source_comment_count']}",
            f"- Staged comment count: {comments['staged_comment_count']}",
            f"- Resource comments preserved: `{comments['resource_comments_preserved']}`",
            f"- String comment preserved: `{comments['string_comment_preserved']}`",
            f"- Array comment preserved: `{comments['array_comment_preserved']}`",
            f"- Plurals comment preserved: `{comments['plurals_comment_preserved']}`",
            f"- Target-only comment preserved: `{comments['target_only_comment_preserved']}`",
            f"- Missing comment issues: {comments['missing_comment_issues']}",
            f"- Misattached comment issues: {comments['misattached_comment_issues']}",
            f"- Duplicate comment issues: {comments['duplicate_comment_issues']}",
            f"- Known limitations: `{len(comments['known_limitations'])}`",
            "",
        ]
    )
    complex_markup = report["complex_markup_policy_check"]
    lines.extend(
        [
            "## Complex Markup Boundary Policy",
            "",
            f"- Pass: `{complex_markup['pass']}`",
            f"- Unsupported markup detected: `{complex_markup['unsupported_markup_detected']}`",
            f"- Complex nested detected: `{complex_markup['complex_nested_detected']}`",
            f"- Unsupported attribute detected: `{complex_markup['unsupported_attribute_detected']}`",
            f"- Unsupported tag detected: `{complex_markup['unsupported_tag_detected']}`",
            f"- Owner review required: {complex_markup['owner_review_required_count']}",
            f"- Sent to normal generation: {complex_markup['sent_to_normal_generation_count']}",
            f"- Preserved without corruption: `{complex_markup['preserved_without_corruption']}`",
            f"- Staged XML parses: `{complex_markup['staged_xml_parse']}`",
            f"- Known limitations: `{', '.join(complex_markup['known_limitations'])}`",
            "",
        ]
    )
    item_markup = report["array_plural_markup_policy_check"]
    lines.extend(
        [
            "## Array/Plural Markup Boundary Policy",
            "",
            f"- Pass: `{item_markup['pass']}`",
            f"- Supported array markup segments: {item_markup['supported_array_markup_segments']}",
            f"- Supported plural markup segments: {item_markup['supported_plural_markup_segments']}",
            f"- Unsupported array items detected: {item_markup['unsupported_array_items_detected']}",
            f"- Unsupported plural items detected: {item_markup['unsupported_plural_items_detected']}",
            f"- Owner review required: {item_markup['owner_review_required_count']}",
            f"- Sent to normal generation: {item_markup['sent_to_normal_generation_count']}",
            f"- Existing target preserved: `{item_markup['existing_target_preserved_in_maintenance']}`",
            f"- Source fallback preserved: `{item_markup['source_fallback_preserved_without_target_use']}`",
            f"- Placeholder QA preserved: `{item_markup['placeholder_qa_preserved']}`",
            f"- Staged XML parses: `{item_markup['staged_xml_parse']}`",
            f"- Known limitations: `{len(item_markup['known_limitations'])}`",
            "",
        ]
    )
    lines.extend(
        [
        "## Known Limitations",
        "",
        ]
    )
    if report["known_limitations"]:
        lines.extend(f"- `{item['id']}`: {item['message']}" for item in report["known_limitations"])
    else:
        lines.append("None.")
    lines.extend(["", "## Artifacts", ""])
    for key, value in report["artifacts"].items():
        lines.append(f"- `{key}`: `{value}`")
    if report["failed_checks"]:
        lines.extend(["", "## Failed Checks", ""])
        lines.extend(f"- {item}" for item in report["failed_checks"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
