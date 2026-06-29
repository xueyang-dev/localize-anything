from __future__ import annotations

import base64
import csv
import json
import gettext
import http.client
import importlib.util
import io
import contextlib
import os
import re
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest import mock
from xml.etree import ElementTree

from runtime.localize_anything.acceptance import create_acceptance
from runtime.localize_anything.agent import run_agent
from runtime.localize_anything.android_app_test import run_android_app_test
from runtime.localize_anything.artifact_state import build_artifact_state, read_artifact_state
from runtime.localize_anything.android_strings_adapter import android_resource_routing
from runtime.localize_anything.android_strings_adapter import extract_segments as extract_android_segments
from runtime.localize_anything.android_strings_adapter import rebuild as rebuild_android_strings
from runtime.localize_anything.android_strings_adapter import stage_rebuild as stage_android_strings
from runtime.localize_anything.android_strings_adapter import target_resource_path, validate_pair as validate_android_strings
from runtime.localize_anything.apply import create_apply_plan, execute_apply, render_apply_plan_markdown
from runtime.localize_anything.cli import main as cli_main
from runtime.localize_anything.contracts import validate_adapter_tree
from runtime.localize_anything.dashboard import build_delivery_dashboard, render_dashboard_markdown
from runtime.localize_anything.delivery import package_delivery
from runtime.localize_anything.delivery_decision import create_delivery_decision_report, render_delivery_decision_markdown
from runtime.localize_anything.deepseek_provider import _get_api_key, generate_deepseek_batch_file
from runtime.localize_anything.evaluation import build_evaluation_scorecard
from runtime.localize_anything.generation import (
    collect_generated_handoff,
    create_draft_request,
    create_generation_handoff,
    create_retry_handoff,
    import_generated_handoff,
    import_generated_response,
    render_draft_prompt,
    validate_generated_segments,
    write_handoff_prompts,
)
from runtime.localize_anything.generation_handoff_policy import (
    build_generation_handoff_decision,
    read_generation_handoff_decision,
)
from runtime.localize_anything.generation_strategy import (
    build_generation_strategy,
    read_generation_strategy,
    write_generation_strategy,
)
from runtime.localize_anything.human_review import (
    build_claim_acceptance_decision,
    create_signoff_record,
    read_human_review_evidence,
    record_human_review_evidence,
)
from runtime.localize_anything.gettext_adapter import extract_segments as extract_po_segments
from runtime.localize_anything.gettext_adapter import parse_po, rebuild as rebuild_po, validate_pair as validate_po_pair
from runtime.localize_anything.io_utils import read_json, read_jsonl, sha256_file, write_json, write_jsonl
from runtime.localize_anything.ios_strings_adapter import extract_segments as extract_ios_segments
from runtime.localize_anything.ios_strings_adapter import rebuild as rebuild_ios_strings
from runtime.localize_anything.ios_strings_adapter import stage_rebuild as stage_ios_strings
from runtime.localize_anything.ios_strings_adapter import target_resource_path as target_ios_resource_path
from runtime.localize_anything.ios_strings_adapter import validate_pair as validate_ios_strings
from runtime.localize_anything.json_adapter import extract_segments, rebuild, validate_pair
from runtime.localize_anything.markup_adapter import extract_segments as extract_markup_segments
from runtime.localize_anything.markup_adapter import rebuild as rebuild_markup, validate_pair as validate_markup_pair
from runtime.localize_anything.mo_compiler import compile_segments_to_mo
from runtime.localize_anything.workbench_action import (
    perform_workbench_action,
    read_workbench_action_log,
)
from runtime.localize_anything.workbench_console import render_workbench_console_html
from runtime.localize_anything.workbench_queue import (
    build_workbench_claim_queue,
    build_workbench_review_queue,
    build_workbench_signoff_summary,
)
from runtime.localize_anything.planning import create_batch_plan, is_generation_eligible
from runtime.localize_anything.project import initialize_project, inspect_project, load_session_index
from runtime.localize_anything.provider import generate_handoff_with_http_provider
from runtime.localize_anything.reflection import create_llm_review_request, import_llm_review_response, render_llm_review_prompt
from runtime.localize_anything.resolution_gate import (
    build_resolution_gate,
    read_blocking_questions,
    record_user_resolution_decision,
)
from runtime.localize_anything.retrieval import build_work_packet
from runtime.localize_anything.review import import_review
from runtime.localize_anything.review_sheet import write_review_sheet
from runtime.localize_anything.run import run_localize
from runtime.localize_anything.schema_validation import validate_document, validate_protocol_tree
from runtime.localize_anything.segments import diff_segments
from runtime.localize_anything.segment_repair import (
    apply_repair_plan,
    build_segment_regeneration_plan,
    read_repair_history,
    read_repair_request,
    read_repair_result,
    read_segment_regeneration_plan,
)
from runtime.localize_anything.segment_staleness import build_reuse_decision, read_reuse_decision, read_stale_segments
from runtime.localize_anything.staging import stage_generated
from runtime.localize_anything.structured_adapter import extract_segments as extract_structured_segments
from runtime.localize_anything.structured_adapter import rebuild as rebuild_structured, validate_pair as validate_structured_pair
from runtime.localize_anything.subtitle_adapter import extract_segments as extract_subtitle_segments
from runtime.localize_anything.subtitle_adapter import rebuild as rebuild_subtitles, validate_pair as validate_subtitle_pair
from runtime.localize_anything.tabular_adapter import extract_segments as extract_tabular_segments
from runtime.localize_anything.tabular_adapter import rebuild as rebuild_tabular, validate_pair as validate_tabular_pair
from runtime.localize_anything.term_governance import select_term_constraints
from runtime.localize_anything.termbase_preflight import (
    record_term_review_decision,
    run_termbase_preflight,
)
from runtime.localize_anything.ui import create_ui_server
from runtime.localize_anything.word_adapter import extract_segments as extract_word_segments
from runtime.localize_anything.word_adapter import rebuild as rebuild_word, validate_pair as validate_word_pair
from runtime.localize_anything.wesnoth_adapter import extract_segments as extract_wesnoth_segments
from runtime.localize_anything.wesnoth_adapter import enrich_segments, inventory as wesnoth_inventory, validate_source
from runtime.localize_anything.xcstrings_adapter import extract_segments as extract_xcstrings_segments
from runtime.localize_anything.xcstrings_adapter import rebuild as rebuild_xcstrings
from runtime.localize_anything.xcstrings_adapter import stage_rebuild as stage_xcstrings
from runtime.localize_anything.xcstrings_adapter import validate_pair as validate_xcstrings
from runtime.localize_anything.xliff_adapter import extract_segments as extract_xliff_segments
from runtime.localize_anything.xliff_adapter import rebuild as rebuild_xliff, validate_pair as validate_xliff_pair


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "json-project"
GETTEXT_WESNOTH_ROOT = Path(__file__).parent / "fixtures" / "gettext-wesnoth"
COMMON_FORMATS_ROOT = Path(__file__).parent / "fixtures" / "common-formats"
ANDROID_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "android-project"
IOS_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ios-project"
XCSTRINGS_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "xcstrings-project"
REPOSITORY_ROOT = Path(__file__).parents[1]
SCHEMA_ROOT = REPOSITORY_ROOT / "protocol" / "schemas"


def assert_protocol_schema(testcase: unittest.TestCase, name: str, value: object) -> None:
    schema = json.loads((SCHEMA_ROOT / f"{name}.schema.json").read_text(encoding="utf-8"))
    errors = validate_document(value, schema, SCHEMA_ROOT)
    testcase.assertEqual(errors, [], f"{name} schema errors: {errors}")


class JsonAdapterTests(unittest.TestCase):
    def test_extract_rebuild_and_validate(self) -> None:
        source = FIXTURE_ROOT / "locales" / "en-US.json"
        expected = FIXTURE_ROOT / "locales" / "zh-CN.json"
        segments = extract_segments(source, "en-US", "locales/en-US.json")
        for segment in segments:
            assert_protocol_schema(self, "segment", segment)
        targets = {
            "/menu/start": "开始游戏",
            "/menu/welcome": "欢迎你，{player}！",
            "/inventory/coins": "你有 {{count}} 枚硬币。",
            "/inventory/weight": "重量：%s kg",
        }
        for segment in segments:
            segment["target_locale"] = "zh-CN"
            segment["target"] = targets[segment["context"]["json_pointer"]]
            segment["status"] = "generated"

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "zh-CN.json"
            rebuild(source, segments, output)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                json.loads(expected.read_text(encoding="utf-8")),
            )
            result = validate_pair(source, output)
            self.assertEqual(result["status"], "pass")
            assert_protocol_schema(self, "qa-result", result)

    def test_placeholder_mismatch_fails(self) -> None:
        source = FIXTURE_ROOT / "locales" / "en-US.json"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "broken.json"
            target.write_text(source.read_text(encoding="utf-8").replace("{player}", "{username}"), encoding="utf-8")
            result = validate_pair(source, target)
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any(item["category"] == "placeholder_parity" for item in result["items"]))


class GettextAdapterTests(unittest.TestCase):
    def test_extract_rebuild_plural_and_validate(self) -> None:
        source = GETTEXT_WESNOTH_ROOT / "messages.pot"
        logical_path = "po/The_South_Guard.pot"
        segments = extract_po_segments(source, "en-US", logical_path)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["context"]["msgctxt"], "campaign-dialogue")
        self.assertEqual(segments[0]["constraints"]["placeholders"], ["%s"])
        self.assertEqual(segments[1]["context"]["source_plural"], "%d turns")

        segments[0]["target"] = "欢迎你，%s！"
        segments[0]["target_locale"] = "zh-CN"
        segments[1]["target_plural"] = {"0": "%d 回合"}
        segments[1]["target_locale"] = "zh-CN"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "zh-CN.po"
            rebuild_po(source, segments, output, "zh-CN")
            target_document = parse_po(output)
            header = target_document.entries[0].msgstr_fields()[0].value
            self.assertIn("Language: zh_CN", header)
            self.assertIn("nplurals=1", header)
            plural = target_document.entries[2]
            self.assertEqual([(field.plural_index, field.value) for field in plural.msgstr_fields()], [(0, "%d 回合")])
            result = validate_po_pair(source, output)
            self.assertEqual(result["status"], "pass", result["items"])

    def test_placeholder_mismatch_fails(self) -> None:
        source = GETTEXT_WESNOTH_ROOT / "messages.pot"
        segments = extract_po_segments(source, "en-US", "messages.pot")
        segments[0]["target"] = "欢迎你！"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "broken.po"
            rebuild_po(source, segments, output, "zh-CN")
            result = validate_po_pair(source, output)
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any(item["category"] == "placeholder_parity" for item in result["items"]))


class WesnothAdapterTests(unittest.TestCase):
    def test_inventory_enrichment_and_context_validation(self) -> None:
        source = GETTEXT_WESNOTH_ROOT / "messages.pot"
        segments = extract_po_segments(source, "en-US", "messages.pot")
        result = wesnoth_inventory(GETTEXT_WESNOTH_ROOT)
        self.assertEqual(len(result["scenario_files"]), 1)
        self.assertEqual(result["pot_files"], ["messages.pot"])

        enriched = enrich_segments(segments, GETTEXT_WESNOTH_ROOT)
        opening = enriched[0]["context"]
        self.assertEqual(opening["campaign"], "The_South_Guard")
        self.assertEqual(opening["scenario"], "01_Born_to_the_Banner")
        self.assertEqual(opening["speaker"], "Deoran")
        self.assertEqual(opening["content_type"], "dialogue")
        self.assertEqual(validate_source(GETTEXT_WESNOTH_ROOT, segments)["status"], "pass")

    def test_wml_extract_and_compile_mo(self) -> None:
        segments = extract_wesnoth_segments(GETTEXT_WESNOTH_ROOT)
        self.assertEqual({item["source"] for item in segments}, {"Born to the Banner", "Welcome, %s!", "%d turns"})
        dialogue = next(item for item in segments if item["source"] == "Welcome, %s!")
        self.assertEqual(dialogue["context"]["speaker"], "Deoran")
        self.assertEqual(dialogue["context"]["content_type"], "dialogue")
        for segment in segments:
            segment["target"] = {
                "Born to the Banner": "生于旌旗下",
                "Welcome, %s!": "欢迎你，%s！",
                "%d turns": "%d 回合",
            }[segment["source"]]

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "wesnoth-tsg.mo"
            compile_segments_to_mo(segments, output)
            translations = gettext.GNUTranslations(io.BytesIO(output.read_bytes()))
            self.assertEqual(translations.gettext("Born to the Banner"), "生于旌旗下")
            self.assertEqual(translations.gettext("Welcome, %s!"), "欢迎你，%s！")


class StructuredAdapterTests(unittest.TestCase):
    def test_yaml_round_trip_and_placeholder_validation(self) -> None:
        source = COMMON_FORMATS_ROOT / "messages.yaml"
        segments = extract_structured_segments(source, "en-US", "locales/messages.yaml")
        self.assertEqual(len(segments), 5)
        self.assertNotIn("12", [item["source"] for item in segments])
        targets = {
            "Start game": "开始游戏",
            "Welcome, {player}!": "欢迎你，{player}！",
            "Try again": "再试一次",
            "Sword": "剑",
            "Shield": "盾牌",
        }
        for segment in segments:
            segment["target"] = targets[segment["source"]]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "messages.yaml"
            rebuild_structured(source, segments, output)
            self.assertIn("max_items: 12", output.read_text(encoding="utf-8"))
            self.assertIn("# Keep the player token.", output.read_text(encoding="utf-8"))
            self.assertEqual(validate_structured_pair(source, output)["status"], "pass")

    def test_toml_round_trip_and_parse(self) -> None:
        source = COMMON_FORMATS_ROOT / "messages.toml"
        segments = extract_structured_segments(source, "en-US", "locales/messages.toml")
        self.assertEqual(len(segments), 5)
        for segment in segments:
            segment["target"] = f"译文：{segment['source']}"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "messages.toml"
            rebuild_structured(source, segments, output)
            self.assertIn("max_items = 12", output.read_text(encoding="utf-8"))
            self.assertEqual(validate_structured_pair(source, output)["status"], "pass")


class TabularAdapterTests(unittest.TestCase):
    def test_csv_and_tsv_round_trip(self) -> None:
        for name in ("messages.csv", "messages.tsv"):
            with self.subTest(name=name):
                source = COMMON_FORMATS_ROOT / name
                segments = extract_tabular_segments(source, "en-US", f"locales/{name}")
                self.assertTrue(segments)
                self.assertTrue(all(item["context"]["column"] > 0 for item in segments))
                for segment in segments:
                    segment["target"] = segment["source"].replace("Start game", "开始游戏").replace(
                        "Welcome, {player}!", "欢迎你，{player}！"
                    )
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / name
                    rebuild_tabular(source, segments, output)
                    self.assertEqual(validate_tabular_pair(source, output)["status"], "pass")
                    text = output.read_text(encoding="utf-8")
                    output.write_text(text.replace("menu.start", "menu.changed", 1), encoding="utf-8")
                    self.assertEqual(validate_tabular_pair(source, output)["status"], "fail")

    def test_xlsx_shared_and_inline_strings_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "messages.xlsx"
            _write_minimal_xlsx(source)
            segments = extract_tabular_segments(source, "en-US", "locales/messages.xlsx")
            self.assertEqual({item["source"] for item in segments}, {"Start game", "Welcome, {player}!"})
            for segment in segments:
                segment["target"] = {
                    "Start game": "开始游戏",
                    "Welcome, {player}!": "欢迎你，{player}！",
                }[segment["source"]]
            output = root / "zh-CN.xlsx"
            rebuild_tabular(source, segments, output)
            self.assertEqual(validate_tabular_pair(source, output)["status"], "pass")
            rebuilt = extract_tabular_segments(output, "zh-CN", "locales/messages.xlsx")
            self.assertEqual({item["source"] for item in rebuilt}, {"开始游戏", "欢迎你，{player}！"})


class MarkupAdapterTests(unittest.TestCase):
    def test_markdown_preserves_code_links_and_structure(self) -> None:
        source = COMMON_FORMATS_ROOT / "guide.md"
        segments = extract_markup_segments(source, "en-US", "docs/guide.md")
        self.assertFalse(any("Do not translate this code" in item["source"] for item in segments))
        for segment in segments:
            segment["target"] = (
                segment["source"]
                .replace("Getting Started", "入门")
                .replace("Welcome", "欢迎")
                .replace("player guide", "玩家指南")
                .replace("Choose", "选择")
                .replace("Keep", "保持")
            )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "guide.md"
            rebuild_markup(source, segments, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn('print("Do not translate this code")', text)
            self.assertIn("https://example.com/guide", text)
            self.assertEqual(validate_markup_pair(source, output)["status"], "pass")

    def test_html_preserves_tags_attributes_and_script(self) -> None:
        source = COMMON_FORMATS_ROOT / "page.html"
        segments = extract_markup_segments(source, "en-US", "docs/page.html")
        self.assertFalse(any("Do not translate" in item["source"] for item in segments))
        for segment in segments:
            segment["target"] = segment["source"].replace("Game Guide", "游戏指南").replace(
                "Welcome", "欢迎"
            ).replace("Choose a", "选择").replace("difficulty", "难度").replace("level", "级别").replace("begin", "开始")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "page.html"
            rebuild_markup(source, segments, output)
            self.assertIn('const message = "Do not translate"', output.read_text(encoding="utf-8"))
            self.assertEqual(validate_markup_pair(source, output)["status"], "pass")


class WordDocumentAdapterTests(unittest.TestCase):
    def test_docx_extract_rebuild_and_validate_visible_parts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "report.docx"
            _write_minimal_docx(source)

            segments = extract_word_segments(source, "en-US", "docs/report.docx")
            for segment in segments:
                assert_protocol_schema(self, "segment", segment)
            self.assertTrue(
                {
                    "Hello, {name}!",
                    "Table total: {total}",
                    "Header title",
                    "Footer note",
                    "Footnote body",
                    "Reviewer comment",
                    "Box text",
                    "Chart title",
                }.issubset({segment["source"] for segment in segments})
            )
            for segment in segments:
                segment["target_locale"] = "zh-CN"
                segment["target"] = f"[zh-CN] {segment['source']}"
                segment["status"] = "generated"

            output = root / "report.zh-CN.docx"
            rebuild_word(source, segments, output)
            self.assertEqual(validate_word_pair(source, output)["status"], "pass")
            rebuilt = extract_word_segments(output, "zh-CN", "docs/report.docx")
            self.assertIn("[zh-CN] Hello, {name}!", {segment["source"] for segment in rebuilt})
            with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
                self.assertEqual(before.read("word/styles.xml"), after.read("word/styles.xml"))
                self.assertEqual(before.read("word/_rels/document.xml.rels"), after.read("word/_rels/document.xml.rels"))
                document = ElementTree.fromstring(after.read("word/document.xml"))
                w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                fonts = document.findall(f".//{{{w_ns}}}rFonts")
                self.assertTrue(fonts)
                self.assertTrue(
                    all(
                        font.get(f"{{{w_ns}}}{name}") == "Microsoft YaHei"
                        for font in fonts
                        for name in ("ascii", "hAnsi", "eastAsia", "cs")
                    )
                )

    def test_rebuild_applies_english_font_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "report.docx"
            _write_minimal_docx(source)
            segments = extract_word_segments(source, "zh-CN", "docs/report.docx")
            for segment in segments:
                segment["target_locale"] = "en-US"
                segment["target"] = f"[en-US] {segment['source']}"
                segment["status"] = "generated"
            output = root / "report.en-US.docx"
            rebuild_word(source, segments, output)
            self.assertEqual(validate_word_pair(source, output)["status"], "pass")
            with zipfile.ZipFile(output) as archive:
                document = ElementTree.fromstring(archive.read("word/document.xml"))
                w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                fonts = document.findall(f".//{{{w_ns}}}rFonts")
                self.assertTrue(fonts)
                self.assertTrue(
                    all(
                        font.get(f"{{{w_ns}}}{name}") == "Arial"
                        for font in fonts
                        for name in ("ascii", "hAnsi", "eastAsia", "cs")
                    )
                )
                chart = ElementTree.fromstring(archive.read("word/charts/chart1.xml"))
                a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
                typefaces = {node.get("typeface") for node in chart.findall(f".//{{{a_ns}}}latin")}
                self.assertEqual(typefaces, {"Arial"})

    def test_mixed_style_runs_are_split_and_styles_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "mixed.docx"
            _write_minimal_docx(source, mixed_styles=True)
            segments = extract_word_segments(source, "en-US", "docs/mixed.docx")
            by_source = {segment["source"]: segment for segment in segments}
            self.assertIn("Bold text", by_source)
            self.assertIn("Italic text", by_source)
            for segment in segments:
                segment["target_locale"] = "zh-CN"
                segment["target"] = f"[zh-CN] {segment['source']}"
                segment["status"] = "generated"
            output = root / "mixed.zh-CN.docx"
            rebuild_word(source, segments, output)
            self.assertEqual(validate_word_pair(source, output)["status"], "pass")

    def test_docm_macro_bytes_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "macro.docm"
            _write_minimal_docx(source, include_macro=True)
            segments = extract_word_segments(source, "en-US", "docs/macro.docm")
            for segment in segments:
                segment["target_locale"] = "zh-CN"
                segment["target"] = f"[zh-CN] {segment['source']}"
                segment["status"] = "generated"
            output = root / "macro.zh-CN.docm"
            rebuild_word(source, segments, output)
            with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
                self.assertEqual(before.read("word/vbaProject.bin"), after.read("word/vbaProject.bin"))
            self.assertEqual(validate_word_pair(source, output)["status"], "pass")

    def test_legacy_doc_and_malformed_docx_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            (project / "legacy.doc").write_bytes(b"legacy")
            inspection = inspect_project(project)
            self.assertEqual(inspection["unprocessed_non_text_assets"][0]["status"], "unsupported")
            self.assertEqual(inspection["unprocessed_non_text_assets"][0]["required_action"], "convert_to_openxml_docx_before_localization")

            broken = root / "broken.docx"
            broken.write_bytes(b"not a zip")
            result = validate_word_pair(broken, broken)
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any(item["category"] == "parse" for item in result["items"]))

    def test_stage_and_localize_run_route_word_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            source = project / "docs" / "report.docx"
            source.parent.mkdir(parents=True)
            _write_minimal_docx(source)
            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                ["docs/report.docx"],
                root / "out",
                "word-run-001",
                synthetic_draft=True,
            )
            self.assertEqual(result["status"], "draft_package_created")
            self.assertEqual(result["summary"]["qa_status"], "pass")
            staging = read_json(Path(result["artifacts"]["staging_result"]))
            self.assertEqual(staging["outputs"][0]["adapter"], "core.word-document")
            self.assertEqual(staging["outputs"][0]["destination"], "docs/report.zh-CN.docx")
            self.assertTrue((Path(staging["staging_dir"]) / "docs" / "report.zh-CN.docx").is_file())


class SubtitleAdapterTests(unittest.TestCase):
    def test_srt_and_vtt_preserve_timing_and_markup(self) -> None:
        for name in ("captions.srt", "captions.vtt"):
            with self.subTest(name=name):
                source = COMMON_FORMATS_ROOT / name
                segments = extract_subtitle_segments(source, "en-US", f"subtitles/{name}")
                self.assertEqual(len(segments), 2)
                segments[0]["target"] = "欢迎，<i>{player}</i>！"
                segments[1]["target"] = "旅程开始了。"
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / name
                    rebuild_subtitles(source, segments, output)
                    self.assertEqual(validate_subtitle_pair(source, output)["status"], "pass")
                    self.assertIn(segments[0]["context"]["timing"], output.read_text(encoding="utf-8"))


class XliffAdapterTests(unittest.TestCase):
    def test_xliff_12_and_20_round_trip(self) -> None:
        for name in ("messages.xlf", "messages-2.xlf"):
            with self.subTest(name=name):
                source = COMMON_FORMATS_ROOT / name
                segments = extract_xliff_segments(source, "en-US", f"locales/{name}")
                self.assertEqual(len(segments), 2)
                for segment in segments:
                    segment["target"] = segment["source"].replace("Welcome", "欢迎").replace(
                        "Start game", "开始游戏"
                    ).replace("Quit game", "退出游戏")
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / name
                    rebuild_xliff(source, segments, output, "zh-CN")
                    self.assertEqual(validate_xliff_pair(source, output)["status"], "pass")
                    rebuilt = extract_xliff_segments(output, "en-US", f"locales/{name}")
                    self.assertTrue(all(item.get("existing_target") for item in rebuilt))


class AndroidStringsAdapterTests(unittest.TestCase):
    def test_extract_rebuild_stage_and_validate_android_strings(self) -> None:
        source = ANDROID_FIXTURE_ROOT / "app" / "src" / "main" / "res" / "values" / "strings.xml"
        logical_path = "app/src/main/res/values/strings.xml"
        segments = extract_android_segments(source, "en-US", logical_path)
        self.assertEqual(
            {item["source"] for item in segments},
            {"Sample App", "Welcome, %1$s!", "You have %d coins.", "Battery at 100%", "Home", "Settings", "%d message", "%d messages"},
        )
        self.assertEqual(len(segments), 8)
        self.assertEqual(next(item for item in segments if item["source"] == "Home")["context"]["resource_type"], "string-array")
        self.assertEqual(next(item for item in segments if item["source"] == "%d message")["context"]["resource_type"], "plurals")
        self.assertEqual(next(item for item in segments if item["source"] == "Welcome, %1$s!")["constraints"]["placeholders"], ["%1$s"])
        self.assertEqual(next(item for item in segments if item["source"] == "Battery at 100%")["constraints"]["placeholders"], [])
        for segment in segments:
            assert_protocol_schema(self, "segment", segment)
            segment["target_locale"] = "zh-CN"
            segment["target"] = {
                "Sample App": "示例应用",
                "Welcome, %1$s!": "欢迎，%1$s！",
                "You have %d coins.": "你有 %d 枚金币。",
                "Battery at 100%": "电量 100%",
                "Home": "首页",
                "Settings": "设置",
                "%d message": "%d 条消息",
                "%d messages": "%d 条消息",
            }[segment["source"]]
            segment["status"] = "generated"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "strings.xml"
            rebuild_android_strings(source, segments, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn('name="app_name"', text)
            self.assertIn("示例应用", text)
            self.assertIn("<string-array", text)
            self.assertIn("<plurals", text)
            self.assertNotIn("debug_token", text)
            result = validate_android_strings(source, output)
            self.assertEqual(result["status"], "pass", result["items"])
            self.assertTrue(any(item["category"] == "unsupported_or_skipped_resource" for item in result["items"]))
            assert_protocol_schema(self, "qa-result", result)

            self.assertEqual(
                target_resource_path(source, "zh-CN", ANDROID_FIXTURE_ROOT).as_posix(),
                "app/src/main/res/values-zh-rCN/strings.xml",
            )
            staged = stage_android_strings(source, segments, root / "staging", "zh-CN", ANDROID_FIXTURE_ROOT)
            staged_path = root / "staging" / "app" / "src" / "main" / "res" / "values-zh-rCN" / "strings.xml"
            self.assertEqual(staged["destination"], "app/src/main/res/values-zh-rCN/strings.xml")
            self.assertTrue(staged_path.is_file())
            self.assertEqual(validate_android_strings(source, staged_path)["status"], "pass")

    def test_android_qualifier_target_path_mapping(self) -> None:
        project = REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture-source-sets"
        expected = {
            "app/src/main/res/values/strings.xml": "app/src/main/res/values-zh-rCN/strings.xml",
            "app/src/main/res/values-night/strings.xml": "app/src/main/res/values-zh-rCN-night/strings.xml",
            "app/src/main/res/values-land/strings.xml": "app/src/main/res/values-zh-rCN-land/strings.xml",
            "app/src/main/res/values-sw600dp/strings.xml": "app/src/main/res/values-zh-rCN-sw600dp/strings.xml",
            "app/src/main/res/values-mcc310/strings.xml": "app/src/main/res/values-mcc310-zh-rCN/strings.xml",
            "app/src/main/res/values-mcc310-mnc004/strings.xml": "app/src/main/res/values-mcc310-mnc004-zh-rCN/strings.xml",
            "app/src/main/res/values-mcc310-night/strings.xml": "app/src/main/res/values-mcc310-zh-rCN-night/strings.xml",
            "app/src/main/res/values-mcc310-mnc004-land/strings.xml": "app/src/main/res/values-mcc310-mnc004-zh-rCN-land/strings.xml",
            "app/src/debug/res/values/strings.xml": "app/src/debug/res/values-zh-rCN/strings.xml",
            "app/src/free/res/values/strings.xml": "app/src/free/res/values-zh-rCN/strings.xml",
        }
        for source_file, target_file in expected.items():
            with self.subTest(source_file=source_file):
                source = project / source_file
                routing = android_resource_routing(source, project, "zh-CN")
                self.assertEqual(target_resource_path(source, "zh-CN", project).as_posix(), target_file)
                self.assertEqual(routing["target_resource_path"], target_file)
                self.assertEqual(routing["warnings"], [])
                segments = extract_android_segments(source, "en-US", source_file)
                self.assertTrue(all(segment["context"]["android_source_set"] in {"main", "debug", "free"} for segment in segments))

        locale_reference = project / "app/src/main/res/values-zh-rCN/strings.xml"
        self.assertEqual(android_resource_routing(locale_reference, project)["android_role"], "locale_reference")
        with self.assertRaises(ValueError):
            target_resource_path(locale_reference, "zh-CN", project)

        invalid_order = Path("app/src/main/res/values-zh-rCN-mcc310/strings.xml")
        invalid_routing = android_resource_routing(invalid_order, target_locale="zh-CN")
        self.assertEqual(invalid_routing["android_role"], "locale_reference")
        self.assertTrue(invalid_routing["warnings"])
        self.assertIsNone(invalid_routing["target_resource_path"])
        with self.assertRaises(ValueError):
            target_resource_path(invalid_order, "zh-CN")

        unknown_order = Path("app/src/main/res/values-night-land/strings.xml")
        unknown_routing = android_resource_routing(unknown_order, target_locale="zh-CN")
        self.assertEqual(unknown_routing["android_role"], "owner_review_required")
        self.assertTrue(unknown_routing["warnings"])
        with self.assertRaises(ValueError):
            target_resource_path(unknown_order, "zh-CN")

    def test_android_staging_preserves_target_only_resources_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            source = project / "app" / "src" / "main" / "res" / "values" / "strings.xml"
            target = project / "app" / "src" / "main" / "res" / "values-zh-rCN" / "strings.xml"
            target.parent.mkdir(parents=True)
            target.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="legacy_removed_key">旧版专属译文_不得自动删除</string>
</resources>
""",
                encoding="utf-8",
            )
            segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
            for segment in segments:
                segment["target_locale"] = "zh-CN"
                segment["target"] = segment["source"]
                segment["status"] = "generated"

            stage_android_strings(source, segments, root / "staging", "zh-CN", project, preserve_target_only=True)
            staged = root / "staging" / "app" / "src" / "main" / "res" / "values-zh-rCN" / "strings.xml"
            text = staged.read_text(encoding="utf-8")
            self.assertIn('name="legacy_removed_key"', text)
            self.assertIn("旧版专属译文_不得自动删除", text)
            self.assertEqual(validate_android_strings(source, staged)["status"], "pass_with_warnings")

    def test_android_escape_signature_extraction(self) -> None:
        source = (
            REPOSITORY_ROOT
            / "benchmarks"
            / "v022-android-resource-reliability"
            / "fixture"
            / "app"
            / "src"
            / "main"
            / "res"
            / "values"
            / "strings.xml"
        )
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        by_key = {segment["context"]["resource_key"]: segment for segment in segments}

        self.assertEqual(by_key["string:cant_sync"]["constraints"]["escape_signature"], ["\\'", '"'])
        self.assertEqual(by_key["string:multiline_help"]["constraints"]["escape_signature"], ["\\n", "\\t"])
        self.assertEqual(by_key["string:delete_files"]["constraints"]["placeholders"], ["%1$d", "%2$d"])
        self.assertEqual(by_key["string:delete_files"]["constraints"]["escape_signature"], ["%%"])
        self.assertNotIn("%%", by_key["string:delete_files"]["constraints"]["placeholders"])

    def test_android_escape_drift_validation(self) -> None:
        source = (
            REPOSITORY_ROOT
            / "benchmarks"
            / "v022-android-resource-reliability"
            / "fixture"
            / "app"
            / "src"
            / "main"
            / "res"
            / "values"
            / "strings.xml"
        )
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        normal_segments = [segment for segment in segments if is_generation_eligible(segment)]
        generated = []
        for segment in normal_segments:
            item = dict(segment)
            item["target_locale"] = "zh-CN"
            item["target"] = item["source"]
            item["status"] = "generated"
            item["generation"] = {"provider": "synthetic"}
            generated.append(item)
        work_packet = {"target_locale": "zh-CN", "segments": normal_segments}

        valid = validate_generated_segments(work_packet, generated)
        self.assertEqual(valid["status"], "pass", valid["items"])

        missing_newline = [dict(segment) for segment in generated]
        for segment in missing_newline:
            if segment["context"]["resource_key"] == "string:multiline_help":
                segment["target"] = "Line one Line two Indented"
        newline_result = validate_generated_segments(work_packet, missing_newline)
        self.assertNotEqual(newline_result["status"], "pass")
        self.assertIn("escape_missing", {item["category"] for item in newline_result["items"]})

        broken_percent = [dict(segment) for segment in generated]
        for segment in broken_percent:
            if segment["context"]["resource_key"] == "string:delete_files":
                segment["target"] = "This will permanently delete %1$d files (%2$d% complete)."
        percent_result = validate_generated_segments(work_packet, broken_percent)
        self.assertNotEqual(percent_result["status"], "pass")
        categories = {item["category"] for item in percent_result["items"]}
        self.assertTrue({"percent_literal_drift", "malformed_escape"} & categories)

    def test_android_inline_markup_signature_extraction(self) -> None:
        source = (
            REPOSITORY_ROOT
            / "benchmarks"
            / "v022-android-resource-reliability"
            / "fixture"
            / "app"
            / "src"
            / "main"
            / "res"
            / "values"
            / "strings.xml"
        )
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        by_key = {segment["context"]["resource_key"]: segment for segment in segments}

        self.assertEqual(by_key["string:learn_more"]["source"], "Tap <b>Learn more</b> to continue.")
        self.assertEqual(
            [item["tag"] for item in by_key["string:learn_more"]["constraints"]["markup_signature"]],
            ["b"],
        )
        self.assertEqual(
            [item["tag"] for item in by_key["string:formatting_example"]["constraints"]["markup_signature"]],
            ["i", "u"],
        )
        self.assertIn("string:unsupported_link", by_key)

    def test_android_complex_markup_detected_as_owner_review_required(self) -> None:
        source = REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture" / "app" / "src" / "main" / "res" / "values" / "strings.xml"
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        by_key = {segment["context"]["resource_key"]: segment for segment in segments}
        expected = {
            "string:nested_markup": "complex_nested_markup",
            "string:font_markup": "unsupported_markup_tag",
            "string:styled_bold": "unsupported_markup_attribute",
            "string:complex_link": "unsupported_markup_attribute",
        }
        for key, category in expected.items():
            with self.subTest(key=key):
                segment = by_key[key]
                assert_protocol_schema(self, "segment", segment)
                self.assertTrue(segment["owner_review_required"])
                self.assertFalse(segment["generation_eligible"])
                self.assertEqual(segment["status"], "new")
                self.assertEqual(segment["workflow_status"], "owner_review_required")
                self.assertIn(category, segment["review_required_reasons"])
                self.assertEqual(segment["constraints"]["markup_signature"], [])

    def test_android_unsupported_markup_not_sent_to_normal_generation(self) -> None:
        source = REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture" / "app" / "src" / "main" / "res" / "values" / "strings.xml"
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        blocked = [segment for segment in segments if not is_generation_eligible(segment)]
        plan = create_batch_plan(segments, "en-US", ["zh-CN"], max_segments=100)
        planned_ids = {segment_id for batch in plan["batches"] for segment_id in batch["segment_ids"]}

        self.assertEqual(len(blocked), 8)
        self.assertTrue(all(segment["segment_id"] not in planned_ids for segment in blocked))
        forbidden = dict(blocked[0])
        forbidden.update({"target_locale": "zh-CN", "target": forbidden["source"], "status": "generated", "generation": {"provider": "synthetic"}})
        qa = validate_generated_segments({"target_locale": "zh-CN", "segments": segments}, [forbidden])
        self.assertEqual(qa["status"], "fail")
        self.assertIn("owner_review_required_generation_forbidden", {item["category"] for item in qa["items"]})

    def test_android_array_item_markup_policy(self) -> None:
        project = REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture"
        source = project / "app" / "src" / "main" / "res" / "values" / "strings.xml"
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        by_key = {segment["context"]["resource_key"]: segment for segment in segments}
        supported = {
            "string-array:rich_sort_options[0]": "b",
            "string-array:rich_sort_options[1]": "i",
            "string-array:rich_sort_options[2]": "a",
        }
        for index, (key, tag) in enumerate(supported.items()):
            segment = by_key[key]
            self.assertTrue(segment["generation_eligible"])
            self.assertEqual(segment["context"]["resource_type"], "string-array")
            self.assertEqual(segment["context"]["item_index"], index)
            self.assertEqual([item["tag"] for item in segment["markup_signature"]], [tag])

        self.assertIn("complex_nested_markup", by_key["string-array:complex_sort_options[0]"]["review_required_reasons"])
        self.assertIn("unsupported_markup_tag", by_key["string-array:complex_sort_options[1]"]["review_required_reasons"])
        self.assertTrue(all(by_key[key]["owner_review_required"] for key in (
            "string-array:complex_sort_options[0]",
            "string-array:complex_sort_options[1]",
        )))

        generated = []
        for segment in segments:
            if not is_generation_eligible(segment):
                continue
            item = dict(segment)
            item.update({"target_locale": "zh-CN", "target": item["source"], "status": "generated", "generation": {"provider": "synthetic"}})
            generated.append(item)
        with tempfile.TemporaryDirectory() as directory:
            staged = stage_android_strings(source, generated, Path(directory), "zh-CN", project, preserve_target_only=True)
            self.assertTrue(ElementTree.parse(staged["output"]).getroot() is not None)
            self.assertIn("string-array:complex_sort_options[0]", staged["preserved_review_required_keys"])
            self.assertIn("string-array:complex_sort_options[1]", staged["preserved_review_required_keys"])

    def test_android_plural_item_markup_policy(self) -> None:
        source = REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture" / "app" / "src" / "main" / "res" / "values" / "strings.xml"
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        by_key = {segment["context"]["resource_key"]: segment for segment in segments}
        for key, quantity in (
            ("plurals:rich_episode_count#one", "one"),
            ("plurals:rich_episode_count#other", "other"),
        ):
            segment = by_key[key]
            self.assertTrue(segment["generation_eligible"])
            self.assertEqual(segment["context"]["resource_type"], "plurals")
            self.assertEqual(segment["context"]["quantity"], quantity)
            self.assertEqual(segment["constraints"]["placeholders"], ["%1$d"])
            self.assertEqual([item["tag"] for item in segment["markup_signature"]], ["b"])

        self.assertIn("unsupported_markup_tag", by_key["plurals:complex_episode_count#one"]["review_required_reasons"])
        self.assertIn("unsupported_markup_attribute", by_key["plurals:complex_episode_count#other"]["review_required_reasons"])
        normal = [segment for segment in segments if is_generation_eligible(segment)]
        generated = []
        for segment in normal:
            item = dict(segment)
            item.update({"target_locale": "zh-CN", "target": item["source"], "status": "generated", "generation": {"provider": "synthetic"}})
            if item["context"]["resource_key"] == "plurals:rich_episode_count#one":
                item["target"] = "%1$d episode"
            generated.append(item)
        qa = validate_generated_segments({"target_locale": "zh-CN", "segments": normal}, generated)
        self.assertIn("markup_missing", {item["category"] for item in qa["items"]})

    def test_android_inline_markup_drift_validation(self) -> None:
        source = (
            REPOSITORY_ROOT
            / "benchmarks"
            / "v022-android-resource-reliability"
            / "fixture"
            / "app"
            / "src"
            / "main"
            / "res"
            / "values"
            / "strings.xml"
        )
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        normal_segments = [segment for segment in segments if is_generation_eligible(segment)]
        generated = []
        for segment in normal_segments:
            item = dict(segment)
            item["target_locale"] = "zh-CN"
            item["target"] = item["source"]
            item["status"] = "generated"
            item["generation"] = {"provider": "synthetic"}
            generated.append(item)
        work_packet = {"target_locale": "zh-CN", "segments": normal_segments}

        valid = validate_generated_segments(work_packet, generated)
        self.assertEqual(valid["status"], "pass", valid["items"])

        missing_tag = [dict(segment) for segment in generated]
        for segment in missing_tag:
            if segment["context"]["resource_key"] == "string:learn_more":
                segment["target"] = "Tap Learn more to continue."
        missing_result = validate_generated_segments(work_packet, missing_tag)
        self.assertNotEqual(missing_result["status"], "pass")
        self.assertIn("markup_missing", {item["category"] for item in missing_result["items"]})

        broken_pair = [dict(segment) for segment in generated]
        for segment in broken_pair:
            if segment["context"]["resource_key"] == "string:learn_more":
                segment["target"] = "Tap <b>Learn more</i> to continue."
        broken_result = validate_generated_segments(work_packet, broken_pair)
        self.assertEqual(broken_result["status"], "fail")
        self.assertIn("malformed_markup", {item["category"] for item in broken_result["items"]})

        unsupported_tag = [dict(segment) for segment in generated]
        for segment in unsupported_tag:
            if segment["context"]["resource_key"] == "string:learn_more":
                segment["target"] = "Tap <strong>Learn more</strong> to continue."
        unsupported_result = validate_generated_segments(work_packet, unsupported_tag)
        self.assertNotEqual(unsupported_result["status"], "pass")
        categories = {item["category"] for item in unsupported_result["items"]}
        self.assertTrue({"unsupported_markup", "markup_missing"} <= categories)

    def test_generic_markup_list_does_not_enter_android_markup_validator(self) -> None:
        segment = {
            "segment_id": "generic-markup-001",
            "source": "Read **more**",
            "source_hash": "hash-generic-markup",
            "source_locale": "en-US",
            "source_path": "docs/example.md",
            "context": {},
            "constraints": {"placeholders": [], "markup": ["strong"]},
        }
        generated = {
            **segment,
            "target_locale": "zh-CN",
            "target": "Read **more**",
            "status": "generated",
            "generation": {"provider": "synthetic"},
        }

        result = validate_generated_segments({"target_locale": "zh-CN", "segments": [segment]}, [generated])

        self.assertEqual(result["status"], "pass", result["items"])

    def test_android_cdata_signature_extraction(self) -> None:
        source = (
            REPOSITORY_ROOT
            / "benchmarks"
            / "v022-android-resource-reliability"
            / "fixture"
            / "app"
            / "src"
            / "main"
            / "res"
            / "values"
            / "strings.xml"
        )
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        by_key = {segment["context"]["resource_key"]: segment for segment in segments}

        self.assertTrue(by_key["string:html_cdata"]["constraints"]["cdata"])
        self.assertTrue(by_key["string:plain_cdata"]["constraints"]["cdata"])
        self.assertTrue(by_key["string:html_cdata"]["cdata"])
        self.assertEqual(by_key["string:html_cdata"]["markup_signature"], [])
        self.assertEqual(by_key["string:plain_cdata"]["source"], "Use < and > safely in this message.")
        self.assertEqual(
            by_key["string:html_cdata"]["cdata_signature"],
            {"boundary": "cdata", "original_had_cdata": True},
        )

    def test_android_cdata_boundary_preserved_in_staging(self) -> None:
        project = REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture"
        source = project / "app" / "src" / "main" / "res" / "values" / "strings.xml"
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        for segment in segments:
            segment["target_locale"] = "zh-CN"
            segment["target"] = segment["source"]
            segment["status"] = "generated"

        with tempfile.TemporaryDirectory() as directory:
            staged = stage_android_strings(source, segments, Path(directory), "zh-CN", project)
            staged_path = Path(staged["output"])
            text = staged_path.read_text(encoding="utf-8")
            self.assertIn('<string name="html_cdata"><![CDATA[Tap <b>Learn more</b> to continue.]]></string>', text)
            self.assertIn('<string name="plain_cdata"><![CDATA[Use < and > safely in this message.]]></string>', text)
            result = validate_android_strings(source, staged_path)
            self.assertNotIn("cdata_boundary_missing", {item["category"] for item in result["items"]})

    def test_android_cdata_terminator_rejected(self) -> None:
        project = REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture"
        source = project / "app" / "src" / "main" / "res" / "values" / "strings.xml"
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        normal_segments = [segment for segment in segments if is_generation_eligible(segment)]
        generated = []
        for segment in normal_segments:
            item = dict(segment)
            item["target_locale"] = "zh-CN"
            item["target"] = "Unsafe ]]>" if item["context"]["resource_key"] == "string:plain_cdata" else item["source"]
            item["status"] = "generated"
            item["generation"] = {"provider": "synthetic"}
            generated.append(item)
        work_packet = {"target_locale": "zh-CN", "segments": normal_segments}

        result = validate_generated_segments(work_packet, generated)
        self.assertEqual(result["status"], "fail")
        self.assertIn("cdata_terminator_unsafe", {item["category"] for item in result["items"]})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                stage_android_strings(source, generated, Path(directory), "zh-CN", project)

    def test_android_resource_comment_metadata_extraction(self) -> None:
        source = (
            REPOSITORY_ROOT
            / "benchmarks"
            / "v022-android-resource-reliability"
            / "fixture"
            / "app"
            / "src"
            / "main"
            / "res"
            / "values"
            / "strings.xml"
        )
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        by_key = {segment["context"]["resource_key"]: segment for segment in segments}

        self.assertEqual(by_key["string:settings_title"]["context"]["resource_comment"], "Settings screen")
        self.assertEqual(
            by_key["string-array:sort_options[0]"]["context"]["resource_comment"],
            "Sort options shown in the queue screen",
        )
        self.assertEqual(
            by_key["plurals:episode_count#one"]["context"]["resource_comment"],
            "Number of downloaded episodes",
        )
        self.assertFalse(any(segment["source"] == "Settings screen" for segment in segments))

    def test_android_resource_comments_round_trip_in_staging(self) -> None:
        project = REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture"
        source = project / "app" / "src" / "main" / "res" / "values" / "strings.xml"
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        for segment in segments:
            segment["target_locale"] = "zh-CN"
            segment["target"] = segment["source"]
            segment["status"] = "generated"

        with tempfile.TemporaryDirectory() as directory:
            staged = stage_android_strings(source, segments, Path(directory), "zh-CN", project, preserve_target_only=True)
            staged_path = Path(staged["output"])
            text = staged_path.read_text(encoding="utf-8")
            self.assertLess(text.index("<!-- Settings screen -->"), text.index('name="settings_title"'))
            self.assertLess(text.index("<!-- Sort options shown in the queue screen -->"), text.index('name="sort_options"'))
            self.assertLess(text.index("<!-- Number of downloaded episodes -->"), text.index('name="episode_count"'))
            self.assertLess(text.index("<!-- Legacy removed key preserved for owner review -->"), text.index('name="legacy_removed_key"'))
            result = validate_android_strings(source, staged_path)
            categories = {item["category"] for item in result["items"]}
            self.assertNotIn("comment_missing", categories)
            self.assertNotIn("comment_misattached", categories)

    def test_android_comment_drift_validation(self) -> None:
        project = REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture"
        source = project / "app" / "src" / "main" / "res" / "values" / "strings.xml"
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        for segment in segments:
            segment["target_locale"] = "zh-CN"
            segment["target"] = segment["source"]
            segment["status"] = "generated"

        with tempfile.TemporaryDirectory() as directory:
            staged = stage_android_strings(source, segments, Path(directory), "zh-CN", project)
            staged_path = Path(staged["output"])
            text = staged_path.read_text(encoding="utf-8")

            missing = Path(directory) / "missing-comment.xml"
            missing.write_text(text.replace("    <!-- Settings screen -->\n", "", 1), encoding="utf-8")
            missing_result = validate_android_strings(source, missing)
            self.assertIn("comment_missing", {item["category"] for item in missing_result["items"]})

            misattached = Path(directory) / "misattached-comment.xml"
            moved = text.replace("    <!-- Settings screen -->\n", "", 1)
            moved = moved.replace('    <string name="app_name"', '    <!-- Settings screen -->\n    <string name="app_name"', 1)
            misattached.write_text(moved, encoding="utf-8")
            misattached_result = validate_android_strings(source, misattached)
            self.assertIn("comment_misattached", {item["category"] for item in misattached_result["items"]})

    def test_placeholder_mismatch_fails_android_strings(self) -> None:
        source = ANDROID_FIXTURE_ROOT / "app" / "src" / "main" / "res" / "values" / "strings.xml"
        segments = extract_android_segments(source, "en-US", "app/src/main/res/values/strings.xml")
        for segment in segments:
            segment["target"] = "缺少占位符" if segment["source"] == "Welcome, %1$s!" else segment["source"]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "strings.xml"
            rebuild_android_strings(source, segments, output)
            result = validate_android_strings(source, output)
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any(item["category"] == "placeholder_parity" for item in result["items"]))


class AndroidAppE2ETests(unittest.TestCase):
    def test_android_app_test_applies_to_copy_and_preserves_source_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            source_file = "app/src/main/res/values/strings.xml"
            original_source = (project / source_file).read_text(encoding="utf-8")
            original_target = project / "app/src/main/res/values-zh-rCN/strings.xml"
            self.assertFalse(original_target.exists())

            report = run_android_app_test(
                project,
                None,
                "zh-CN",
                output_root=root / "out",
                run_id="android-e2e-001",
                max_segments=3,
            )

            assert_protocol_schema(self, "android-app-test-report", report)
            self.assertEqual(report["status"], "pass")
            self.assertFalse(report["source_preservation"]["original_project_mutated"])
            self.assertEqual(report["android"]["source_files"], [source_file])
            self.assertEqual(report["summary"]["localized_file_count"], 1)
            self.assertFalse(report["summary"]["real_generation_required"])
            self.assertFalse(report["summary"]["real_generation_satisfied"])
            self.assertEqual((project / source_file).read_text(encoding="utf-8"), original_source)
            self.assertFalse(original_target.exists())
            app_copy = Path(report["artifacts"]["app_copy"])
            copied_target = app_copy / report["android"]["target_file"]
            self.assertTrue(copied_target.is_file())
            self.assertEqual(report["summary"]["post_apply_qa_status"], "pass")
            self.assertEqual(report["summary"]["delivery_decision_status"], "owner_review_required")
            self.assertEqual(read_json(Path(report["artifacts"]["post_apply_plan"]))["summary"]["unchanged"], 1)
            self.assertTrue(Path(report["artifacts"]["android_app_test_report"]).is_file())

    def test_android_app_test_rejects_output_inside_source_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)

            with self.assertRaisesRegex(ValueError, "outside the source project root"):
                run_android_app_test(
                    project,
                    "app/src/main/res/values/strings.xml",
                    "zh-CN",
                    output_root=project / "localize-anything-output",
                    run_id="unsafe",
                )

    def test_android_app_test_rejects_multiple_generation_inputs_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            output_root = root / "out"

            with self.assertRaisesRegex(ValueError, "Use only one Android app test generation input"):
                run_android_app_test(
                    project,
                    None,
                    "zh-CN",
                    output_root=output_root,
                    run_id="invalid-generation-inputs",
                    generated_dir=root / "generated-batches",
                    generated=root / "generated.jsonl",
                )
            self.assertFalse((output_root / "invalid-generation-inputs").exists())

    def test_android_app_test_requires_real_generation_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            output_root = root / "out"

            with self.assertRaisesRegex(ValueError, "requires generated_dir, generated, or local_chinese_draft"):
                run_android_app_test(
                    project,
                    None,
                    "zh-CN",
                    output_root=output_root,
                    run_id="requires-real-generation",
                    require_real_generation=True,
                )
            self.assertFalse((output_root / "requires-real-generation").exists())

    def test_android_app_test_accepts_real_generated_chinese_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            source_file = "app/src/main/res/values/strings.xml"
            source = project / source_file
            generated = extract_android_segments(source, "en-US", source_file)
            translations = {
                "Sample App": "示例应用",
                "Welcome, %1$s!": "欢迎，%1$s！",
                "You have %d coins.": "你有 %d 枚金币。",
                "Battery at 100%": "电量 100%",
                "Home": "首页",
                "Settings": "设置",
                "%d message": "%d 条消息",
                "%d messages": "%d 条消息",
            }
            for segment in generated:
                segment["target_locale"] = "zh-CN"
                segment["target"] = translations[segment["source"]]
                segment["status"] = "generated"
                segment["generation"] = {
                    "provider": "codex",
                    "quality_claim": "fixture_human_readable_chinese_draft",
                    "purpose": "android_app_e2e_test",
                }
            generated_path = root / "codex-generated.jsonl"
            write_jsonl(generated_path, generated)

            report = run_android_app_test(
                project,
                None,
                "zh-CN",
                output_root=root / "out",
                run_id="android-e2e-codex-001",
                max_segments=3,
                generated=generated_path,
                require_real_generation=True,
            )

            assert_protocol_schema(self, "android-app-test-report", report)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["generation"]["provider"], "codex")
            self.assertEqual(report["generation"]["quality_claim"], "fixture_human_readable_chinese_draft")
            self.assertTrue(report["summary"]["real_generation_required"])
            self.assertTrue(report["summary"]["real_generation_satisfied"])
            app_copy = Path(report["artifacts"]["app_copy"])
            target_text = (app_copy / report["android"]["target_file"]).read_text(encoding="utf-8")
            self.assertIn("示例应用", target_text)
            self.assertIn("欢迎，%1$s！", target_text)
            self.assertNotIn("[zh-CN]", target_text)

    def test_android_app_test_cli_accepts_generated_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            source_file = "app/src/main/res/values/strings.xml"
            generated = extract_android_segments(project / source_file, "en-US", source_file)
            for segment in generated:
                segment["target_locale"] = "zh-CN"
                segment["target"] = {
                    "Sample App": "示例应用",
                    "Welcome, %1$s!": "欢迎，%1$s！",
                    "You have %d coins.": "你有 %d 枚金币。",
                    "Battery at 100%": "电量 100%",
                    "Home": "首页",
                    "Settings": "设置",
                    "%d message": "%d 条消息",
                    "%d messages": "%d 条消息",
                }[segment["source"]]
                segment["status"] = "generated"
                segment["generation"] = {"provider": "codex", "quality_claim": "cli_fixture_chinese_draft"}
            generated_path = root / "generated.jsonl"
            report_path = root / "report.json"
            write_jsonl(generated_path, generated)

            exit_code = cli_main(
                [
                    "android-app-test",
                    project.as_posix(),
                    "--target-locale",
                    "zh-CN",
                    "--generated",
                    generated_path.as_posix(),
                    "--require-real-generation",
                    "--output-root",
                    (root / "out").as_posix(),
                    "--run-id",
                    "android-e2e-cli-001",
                    "--max-segments",
                    "3",
                    "--output",
                    report_path.as_posix(),
                ]
            )

            self.assertEqual(exit_code, 0)
            report = read_json(report_path)
            assert_protocol_schema(self, "android-app-test-report", report)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["generation"]["provider"], "codex")
            self.assertTrue(report["summary"]["real_generation_satisfied"])
            target_text = (Path(report["artifacts"]["app_copy"]) / report["android"]["target_file"]).read_text(encoding="utf-8")
            self.assertIn("设置", target_text)

    def test_generate_chinese_draft_cli_feeds_android_app_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            source_file = "app/src/main/res/values/strings.xml"
            segments = extract_android_segments(project / source_file, "en-US", source_file)
            segments_path = root / "segments.jsonl"
            generated_path = root / "generated.jsonl"
            draft_report_path = root / "draft-report.json"
            write_jsonl(segments_path, segments)

            exit_code = cli_main(
                [
                    "generate-chinese-draft",
                    segments_path.as_posix(),
                    "--target-locale",
                    "zh-CN",
                    "--generated-output",
                    generated_path.as_posix(),
                    "--output",
                    draft_report_path.as_posix(),
                ]
            )

            self.assertEqual(exit_code, 0)
            draft_report = read_json(draft_report_path)
            self.assertEqual(draft_report["status"], "pass")
            self.assertEqual(draft_report["provider"], "codex-local")
            generated = read_jsonl(generated_path)
            generated_by_source = {segment["source"]: segment for segment in generated}
            self.assertEqual(generated_by_source["Sample App"]["target"], "\u793a\u4f8b\u5e94\u7528")
            self.assertEqual(generated_by_source["Welcome, %1$s!"]["target"], "\u6b22\u8fce\uff0c%1$s\uff01")
            self.assertEqual(generated_by_source["Welcome, %1$s!"]["generation"]["quality_claim"], "local_chinese_draft_for_e2e")

            report = run_android_app_test(
                project,
                None,
                "zh-CN",
                output_root=root / "out",
                run_id="android-e2e-local-draft-001",
                max_segments=3,
                generated=generated_path,
                require_real_generation=True,
            )

            assert_protocol_schema(self, "android-app-test-report", report)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["generation"]["provider"], "codex-local")
            self.assertEqual(report["generation"]["quality_claim"], "local_chinese_draft_for_e2e")
            self.assertTrue(report["summary"]["real_generation_satisfied"])
            target_text = (Path(report["artifacts"]["app_copy"]) / report["android"]["target_file"]).read_text(encoding="utf-8")
            self.assertIn("\u793a\u4f8b\u5e94\u7528", target_text)
            self.assertNotIn("[zh-CN]", target_text)

    def test_android_app_test_cli_generates_local_chinese_draft(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            report_path = root / "report.json"

            exit_code = cli_main(
                [
                    "android-app-test",
                    project.as_posix(),
                    "--target-locale",
                    "zh-CN",
                    "--local-chinese-draft",
                    "--require-real-generation",
                    "--output-root",
                    (root / "out").as_posix(),
                    "--run-id",
                    "android-e2e-local-auto-001",
                    "--max-segments",
                    "3",
                    "--output",
                    report_path.as_posix(),
                ]
            )

            self.assertEqual(exit_code, 0)
            report = read_json(report_path)
            assert_protocol_schema(self, "android-app-test-report", report)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["generation"]["provider"], "codex-local")
            self.assertEqual(report["generation"]["quality_claim"], "local_chinese_draft_for_e2e")
            self.assertTrue(report["summary"]["real_generation_required"])
            self.assertTrue(report["summary"]["real_generation_satisfied"])
            self.assertTrue(Path(report["artifacts"]["local_chinese_draft"]).is_file())
            self.assertTrue(Path(report["artifacts"]["local_chinese_draft_report"]).is_file())
            target_text = (Path(report["artifacts"]["app_copy"]) / report["android"]["target_file"]).read_text(encoding="utf-8")
            self.assertIn("\u793a\u4f8b\u5e94\u7528", target_text)
            self.assertNotIn("[zh-CN]", target_text)


class IOSStringsAdapterTests(unittest.TestCase):
    def test_extract_rebuild_stage_and_validate_strings(self) -> None:
        source = IOS_FIXTURE_ROOT / "App" / "en.lproj" / "Localizable.strings"
        logical_path = "App/en.lproj/Localizable.strings"
        segments = extract_ios_segments(source, "en-US", logical_path)
        self.assertEqual(
            {item["source"] for item in segments},
            {"Sample App", "Welcome, %@!", "You have %d coins.", 'Tap "Continue"', "Battery at 100%"},
        )
        self.assertEqual(len(segments), 5)
        self.assertEqual(next(item for item in segments if item["source"] == "Welcome, %@!")["constraints"]["placeholders"], ["%@"])
        self.assertEqual(next(item for item in segments if item["source"] == "Battery at 100%")["constraints"]["placeholders"], [])
        for segment in segments:
            assert_protocol_schema(self, "segment", segment)
            segment["target_locale"] = "zh-CN"
            segment["target"] = {
                "Sample App": "示例应用",
                "Welcome, %@!": "欢迎，%@！",
                "You have %d coins.": "你有 %d 枚金币。",
                'Tap "Continue"': "点按\"继续\"",
                "Battery at 100%": "电量 100%",
            }[segment["source"]]
            segment["status"] = "generated"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "Localizable.strings"
            rebuild_ios_strings(source, segments, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("/* Main screen */", text)
            self.assertIn('"welcome.message" = "欢迎，%@！";', text)
            result = validate_ios_strings(source, output)
            self.assertEqual(result["status"], "pass", result["items"])
            assert_protocol_schema(self, "qa-result", result)

            staged = stage_ios_strings(source, segments, root / "staging", "zh-CN", IOS_FIXTURE_ROOT)
            staged_path = root / "staging" / "App" / "zh-Hans.lproj" / "Localizable.strings"
            self.assertEqual(staged["destination"], "App/zh-Hans.lproj/Localizable.strings")
            self.assertTrue(staged_path.is_file())
            self.assertEqual(validate_ios_strings(source, staged_path)["status"], "pass")
            self.assertEqual(target_ios_resource_path(source, "zh-TW", IOS_FIXTURE_ROOT).as_posix(), "App/zh-Hant.lproj/Localizable.strings")

    def test_stringsdict_plural_round_trip(self) -> None:
        source = IOS_FIXTURE_ROOT / "App" / "en.lproj" / "Localizable.stringsdict"
        logical_path = "App/en.lproj/Localizable.stringsdict"
        segments = extract_ios_segments(source, "en-US", logical_path)
        self.assertEqual({item["source"] for item in segments}, {"%d file", "%d files"})
        self.assertEqual(len(segments), 2)
        self.assertTrue(all(item["context"]["file_format"] == "stringsdict" for item in segments))
        for segment in segments:
            assert_protocol_schema(self, "segment", segment)
            segment["target_locale"] = "zh-CN"
            segment["target"] = "%d 个文件"
            segment["status"] = "generated"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "Localizable.stringsdict"
            rebuild_ios_strings(source, segments, output)
            result = validate_ios_strings(source, output)
            self.assertEqual(result["status"], "pass", result["items"])

    def test_placeholder_mismatch_fails_ios_strings(self) -> None:
        source = IOS_FIXTURE_ROOT / "App" / "en.lproj" / "Localizable.strings"
        segments = extract_ios_segments(source, "en-US", "App/en.lproj/Localizable.strings")
        for segment in segments:
            segment["target"] = "缺少占位符" if segment["source"] == "Welcome, %@!" else segment["source"]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "Localizable.strings"
            rebuild_ios_strings(source, segments, output)
            result = validate_ios_strings(source, output)
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any(item["category"] == "placeholder_parity" for item in result["items"]))


class XCStringsAdapterTests(unittest.TestCase):
    def test_extract_rebuild_stage_and_validate_catalog(self) -> None:
        source = XCSTRINGS_FIXTURE_ROOT / "App" / "Localizable.xcstrings"
        logical_path = "App/Localizable.xcstrings"
        segments = extract_xcstrings_segments(source, "en-US", logical_path)
        self.assertEqual(
            {item["source"] for item in segments},
            {"Sample App", "Settings", "Welcome, %@!", "%lld file", "%lld files"},
        )
        self.assertEqual(len(segments), 5)
        self.assertEqual(next(item for item in segments if item["source"] == "Settings")["context"]["resource_type"], "stringUnit")
        self.assertEqual(next(item for item in segments if item["source"] == "%lld file")["context"]["resource_type"], "variation")
        self.assertEqual(next(item for item in segments if item["source"] == "%lld file")["constraints"]["placeholders"], ["%lld"])
        for segment in segments:
            assert_protocol_schema(self, "segment", segment)
            segment["target_locale"] = "zh-CN"
            segment["target"] = {
                "Sample App": "示例应用",
                "Settings": "设置",
                "Welcome, %@!": "欢迎，%@！",
                "%lld file": "%lld 个文件",
                "%lld files": "%lld 个文件",
            }[segment["source"]]
            segment["status"] = "generated"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "Localizable.xcstrings"
            rebuild_xcstrings(source, segments, output, "zh-CN")
            text = output.read_text(encoding="utf-8")
            self.assertIn('"zh-Hans"', text)
            self.assertIn('"value": "欢迎，%@！"', text)
            result = validate_xcstrings(source, output, "zh-CN")
            self.assertEqual(result["status"], "pass", result["items"])
            assert_protocol_schema(self, "qa-result", result)

            staged = stage_xcstrings(source, segments, root / "staging", "zh-CN", XCSTRINGS_FIXTURE_ROOT)
            staged_path = root / "staging" / "App" / "Localizable.xcstrings"
            self.assertEqual(staged["destination"], "App/Localizable.xcstrings")
            self.assertTrue(staged_path.is_file())
            self.assertEqual(validate_xcstrings(source, staged_path, "zh-CN")["status"], "pass")

    def test_placeholder_mismatch_fails_xcstrings(self) -> None:
        source = XCSTRINGS_FIXTURE_ROOT / "App" / "Localizable.xcstrings"
        segments = extract_xcstrings_segments(source, "en-US", "App/Localizable.xcstrings")
        for segment in segments:
            segment["target_locale"] = "zh-CN"
            segment["target"] = "缺少占位符" if segment["source"] == "Welcome, %@!" else segment["source"]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "Localizable.xcstrings"
            rebuild_xcstrings(source, segments, output, "zh-CN")
            result = validate_xcstrings(source, output, "zh-CN")
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any(item["category"] == "placeholder_parity" for item in result["items"]))


class ProjectTests(unittest.TestCase):
    def test_inspect_and_preflight_initialize_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            locale_dir = project / "locales"
            locale_dir.mkdir()
            (locale_dir / "en-US.json").write_text(
                (FIXTURE_ROOT / "locales" / "en-US.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (project / "cover.png").write_bytes(b"not-a-real-image")

            inspection = inspect_project(project)
            self.assertEqual(inspection["adapter_counts"], {"core.json-locale": 1})
            self.assertEqual(inspection["unprocessed_non_text_assets"][0]["path"], "cover.png")
            self.assertEqual(inspection["preflight_assessment"]["recommended_workflow_depth"], "fast")

            result = initialize_project(project, "en-US", ["locales/en-US.json"], ["zh-CN"])
            state = Path(result["state_directory"])
            self.assertTrue((state / "config.json").exists())
            self.assertTrue((state / "localization-context.md").exists())
            self.assertTrue((state / "localization-brief.json").exists())
            self.assertTrue((state / "localization-brief.yaml").exists())
            self.assertTrue((state / "glossary.csv").exists())
            self.assertTrue((state / "translation-memory.jsonl").exists())
            self.assertTrue((state / "term-registry.csv").exists())
            self.assertTrue((state / "forbidden-translations.csv").exists())
            self.assertTrue((state / "term-decisions.jsonl").exists())
            self.assertTrue((state / "term-conflicts.jsonl").exists())
            self.assertTrue((state / "term-provenance.jsonl").exists())
            self.assertTrue((state / "delivery-manifest.json").exists())
            manifest = json.loads((state / "delivery-manifest.json").read_text(encoding="utf-8"))
            config = json.loads((state / "config.json").read_text(encoding="utf-8"))
            brief = json.loads((state / "localization-brief.json").read_text(encoding="utf-8"))
            assert_protocol_schema(self, "project-config", config)
            assert_protocol_schema(self, "delivery-manifest", manifest)
            assert_protocol_schema(self, "localization-brief", brief)
            self.assertEqual(config["operating_mode"], "greenfield_localization")
            self.assertEqual(config["reference_policy"], "style_only")
            self.assertEqual(manifest["project"]["operating_mode"], "greenfield_localization")
            self.assertEqual(manifest["project"]["reference_policy"], "style_only")
            self.assertEqual(manifest["source_material"][0]["role"], "source_of_truth")
            self.assertEqual([item["path"] for item in manifest["source_material"]], ["locales/en-US.json"])
            self.assertEqual(manifest["unprocessed_non_text_assets"][0]["asset_type"], "image")
            self.assertEqual(manifest["assets"]["localization_brief"], "localization-brief.json")
            self.assertEqual(manifest["assets"]["term_registry"], "term-registry.csv")
            self.assertEqual(manifest["assets"]["term_decisions"], "term-decisions.jsonl")
            self.assertEqual(brief["document_type"], "generic_localization_project")
            self.assertEqual(brief["source_genre"], "project_locale_assets")
            self.assertEqual(brief["target_mode"], "greenfield_localization_delivery")
            self.assertEqual(brief["target_audience"], ["unknown_requires_user_confirmation"])
            self.assertEqual(brief["task_intent"]["scenario"], "project_localization")
            self.assertEqual(brief["source_surface"]["selected_source_files"], ["locales/en-US.json"])
            self.assertIn("localized_rewrite", brief["allowed_transformations"])
            self.assertIn("unsupported_official_recognition", brief["forbidden_behaviors"])
            self.assertTrue(brief["constraints"]["do_not_invent_facts"])
            self.assertIn("target_audience", {item["item"] for item in brief["required_human_confirmations"]})
            brief_yaml = (state / "localization-brief.yaml").read_text(encoding="utf-8")
            self.assertIn("document_type: generic_localization_project", brief_yaml)
            self.assertIn("task_intent:", brief_yaml)

    def test_inspect_ignores_generated_outputs_and_records_routing_evidence(self) -> None:
        source_file = "app/src/main/res/values/strings.xml"
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "android-project"
            copied = project / source_file
            copied.parent.mkdir(parents=True)
            copied.write_text((ANDROID_FIXTURE_ROOT / source_file).read_text(encoding="utf-8"), encoding="utf-8")
            (project / "localize-run-002" / "reports").mkdir(parents=True)
            (project / "localize-run-002" / "reports" / "pm-analysis-report.md").write_text("# Old report\n", encoding="utf-8")
            (project / "localize-anything-output" / "old").mkdir(parents=True)
            (project / "localize-anything-output" / "old" / "run-summary.json").write_text("{}", encoding="utf-8")
            (project / ".localize-anything" / "backups").mkdir(parents=True)
            (project / ".localize-anything" / "backups" / "old.json").write_text("{}", encoding="utf-8")
            (project / "build" / "generated").mkdir(parents=True)
            (project / "build" / "generated" / "strings.json").write_text("{}", encoding="utf-8")

            inspection = inspect_project(project)

            self.assertEqual([item["path"] for item in inspection["supported_files"]], [source_file])
            self.assertEqual(inspection["adapter_counts"], {"core.android-strings": 1})
            ignored = {item["path"]: item["reason"] for item in inspection["ignored_paths"]}
            self.assertEqual(ignored["localize-run-002"], "localize_anything_run_output")
            self.assertEqual(ignored["localize-anything-output"], "ignored_directory")
            self.assertEqual(ignored[".localize-anything"], "ignored_directory")
            self.assertEqual(ignored["build"], "ignored_directory")
            self.assertIn("localize-run-", inspection["scan_policy"]["ignored_directory_prefixes"])

    def test_android_strings_are_detected_as_platform_resources(self) -> None:
        source_file = "app/src/main/res/values/strings.xml"
        source = ANDROID_FIXTURE_ROOT / source_file
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "android-project"
            copied = project / source_file
            copied.parent.mkdir(parents=True)
            copied.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

            inspection = inspect_project(project)
            self.assertEqual(inspection["adapter_counts"], {"core.android-strings": 1})
            self.assertEqual(inspection["supported_files"][0]["path"], source_file)

            result = initialize_project(project, "en-US", [source_file], ["zh-CN"])
            self.assertEqual(result["manifest"]["source_material"][0]["adapter"], "core.android-strings")

    def test_android_coverage_counts_source_and_merged_dependency_resources_separately(self) -> None:
        source_file = "app/src/main/res/values/strings.xml"
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "android-project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            merged = project / "app" / "build" / "intermediates" / "incremental" / "debug" / "mergeDebugResources" / "merged.dir" / "values" / "values.xml"
            merged.parent.mkdir(parents=True)
            merged.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Sample App</string>
    <string name="sort_by">Sort by</string>
    <string name="storage">Storage</string>
    <string name="internal_debug" translatable="false">Do not translate</string>
</resources>
""",
                encoding="utf-8",
            )

            inspection = inspect_project(project)
            coverage = inspection["android_coverage"]

            self.assertEqual(coverage["coverage_mode"], "source-only")
            self.assertEqual(coverage["app_source_strings"], 8)
            self.assertEqual(coverage["app_source_string_counts"][source_file], 8)
            self.assertEqual(coverage["merged_dependency_strings_detected"], 2)
            self.assertFalse(coverage["merged_dependency_strings_included"])
            self.assertTrue(coverage["visible_ui_coverage_warning"])
            self.assertEqual(coverage["categories"]["app_source_resources"]["string_count"], 8)
            self.assertEqual(coverage["categories"]["merged_dependency_resources"]["string_count"], 2)
            self.assertEqual(coverage["categories"]["non_resource_runtime_text"]["included"], False)

            initialized = initialize_project(project, "en-US", [source_file], ["zh-CN"])
            brief = read_json(Path(initialized["state_directory"]) / "localization-brief.json")
            assert_protocol_schema(self, "localization-brief", brief)
            self.assertEqual(brief["document_type"], "android_resource_project")
            self.assertEqual(brief["task_intent"]["scenario"], "software_resource_localization")
            self.assertIn(
                "android_visible_ui_coverage",
                {item["item"] for item in brief["required_human_confirmations"]},
            )

    def test_android_source_set_detection_excludes_locale_dirs(self) -> None:
        project = REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture-source-sets"
        inspection = inspect_project(project)
        self.assertEqual(
            inspection["android_generation_source_files"],
            [
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
            ],
        )
        self.assertEqual(
            inspection["android_locale_reference_files"],
            [
                "app/src/main/res/values-es/strings.xml",
                "app/src/main/res/values-fr/strings.xml",
                "app/src/main/res/values-zh-rCN/strings.xml",
            ],
        )
        by_path = {item["path"]: item for item in inspection["supported_files"]}
        self.assertEqual(by_path["app/src/main/res/values-night/strings.xml"]["android_qualifiers"]["non_locale"], ["night"])
        self.assertEqual(by_path["app/src/debug/res/values/strings.xml"]["android_source_set"], "debug")
        self.assertEqual(by_path["app/src/main/res/values-zh-rCN/strings.xml"]["android_role"], "locale_reference")
        with self.assertRaises(ValueError):
            initialize_project(
                project,
                "en-US",
                ["app/src/main/res/values-zh-rCN/strings.xml"],
                ["zh-CN"],
            )

    def test_inspect_summary_cli_writes_json_markdown_and_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture", project)
            output_dir = root / "inspect-output"
            emitted = root / "emitted-summary.json"
            before = {
                path.relative_to(project).as_posix(): path.read_bytes()
                for path in project.rglob("*")
                if path.is_file()
            }

            exit_code = cli_main(
                [
                    "inspect",
                    "--project",
                    project.as_posix(),
                    "--output-dir",
                    output_dir.as_posix(),
                    "--output",
                    emitted.as_posix(),
                ]
            )

            self.assertEqual(exit_code, 0)
            after = {
                path.relative_to(project).as_posix(): path.read_bytes()
                for path in project.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertFalse((project / ".localize-anything").exists())
            summary = read_json(output_dir / "inspect-summary.json")
            emitted_summary = read_json(emitted)
            markdown = (output_dir / "inspect-summary.md").read_text(encoding="utf-8")
            self.assertEqual(summary, emitted_summary)
            self.assertTrue(summary["read_only"])
            self.assertEqual(summary["detected_project_type"], "android")
            self.assertEqual(summary["primary_adapter"], "core.android-strings")
            self.assertEqual(summary["android"]["resource_types"]["string"], 35)
            self.assertEqual(summary["android"]["resource_types"]["string-array"], 6)
            self.assertEqual(summary["android"]["resource_types"]["plurals"], 6)
            self.assertIn("app/src/main/res/values/strings.xml", summary["android"]["generation_source_files"])
            self.assertIn("zh-rCN", summary["android"]["existing_target_locales"])
            self.assertFalse(summary["risk_review_metadata"]["available"])
            self.assertIn("Inspect is read-only", markdown)

    def test_inspect_summary_warns_when_merged_dependency_resources_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            merged = project / "app" / "build" / "intermediates" / "incremental" / "debug" / "mergeDebugResources" / "merged.dir" / "values" / "values.xml"
            merged.parent.mkdir(parents=True)
            merged.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Sample App</string>
    <string name="files_tab">Files</string>
</resources>
""",
                encoding="utf-8",
            )
            output_dir = root / "inspect-output"

            exit_code = cli_main(["inspect", project.as_posix(), "--output-dir", output_dir.as_posix()])

            self.assertEqual(exit_code, 0)
            summary = read_json(output_dir / "inspect-summary.json")
            markdown = (output_dir / "inspect-summary.md").read_text(encoding="utf-8")
            self.assertEqual(summary["android"]["coverage"]["merged_dependency_strings_detected"], 1)
            self.assertTrue(summary["android"]["coverage"]["visible_ui_coverage_warning"])
            self.assertTrue(any("source-only localization may not cover" in warning for warning in summary["warnings"]))
            self.assertIn("merged dependency strings detected: 1", markdown)

    def test_inspect_summary_reports_android_source_sets_and_qualifiers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "source-set-project"
            shutil.copytree(REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture-source-sets", project)
            output_dir = root / "summary"
            emitted = root / "emitted-summary.json"

            exit_code = cli_main(
                [
                    "inspect",
                    project.as_posix(),
                    "--output-dir",
                    output_dir.as_posix(),
                    "--output",
                    emitted.as_posix(),
                ]
            )

            self.assertEqual(exit_code, 0)
            summary = read_json(output_dir / "inspect-summary.json")
            self.assertEqual(summary["android"]["source_sets"], ["debug", "free", "main"])
            self.assertIn("night", summary["android"]["qualifiers"])
            self.assertIn("mcc310", summary["android"]["qualifiers"])
            self.assertEqual(
                summary["android"]["target_locale_files"],
                [
                    "app/src/main/res/values-es/strings.xml",
                    "app/src/main/res/values-fr/strings.xml",
                    "app/src/main/res/values-zh-rCN/strings.xml",
                ],
            )
            self.assertIsNotNone(summary["output_directory"])

    def test_inspect_summary_rejects_output_dir_inside_source_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "fixture", project)
            output_dir = project / "inspect-output"

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = cli_main(
                    [
                        "inspect",
                        "--project",
                        project.as_posix(),
                        "--output-dir",
                        output_dir.as_posix(),
                    ]
                )

            self.assertEqual(exit_code, 2)
            self.assertFalse(output_dir.exists())
            self.assertIn("must be outside the source project", stderr.getvalue())

    def test_cli_help_describes_inspect_read_only_and_localize_run_no_apply(self) -> None:
        inspect_stdout = io.StringIO()
        with contextlib.redirect_stdout(inspect_stdout), self.assertRaises(SystemExit) as inspect_exit:
            cli_main(["inspect", "--help"])
        self.assertEqual(inspect_exit.exception.code, 0)
        self.assertIn("Read-only project inspection", inspect_stdout.getvalue())

        run_stdout = io.StringIO()
        with contextlib.redirect_stdout(run_stdout), self.assertRaises(SystemExit) as run_exit:
            cli_main(["localize-run", "--help"])
        self.assertEqual(run_exit.exception.code, 0)
        self.assertIn("does not call apply-delivery", run_stdout.getvalue())
        self.assertIn("--include-android-merged-resources", run_stdout.getvalue())
        self.assertIn("--android-merged-resources", run_stdout.getvalue())
        self.assertNotIn("--apply-to-project", run_stdout.getvalue())
        self.assertNotIn("--apply-confirm-run-id", run_stdout.getvalue())

    def test_android_coverage_model_doc_records_runtime_text_boundary(self) -> None:
        doc = (REPOSITORY_ROOT / "docs" / "android-coverage-model.md").read_text(encoding="utf-8")
        self.assertIn("Gradle merged resources", doc)
        self.assertIn("Alarms", doc)
        self.assertIn("Apply/write-back is out of scope", doc)

    def test_android_merged_resource_overlay_doc_records_explicit_boundaries(self) -> None:
        doc = (REPOSITORY_ROOT / "docs" / "android-merged-resource-overlay.md").read_text(encoding="utf-8")
        self.assertIn("defaults to source-only Android localization", doc)
        self.assertIn("--include-android-merged-resources", doc)
        self.assertIn("does not modify the source project during `localize-run`", doc)
        self.assertIn("not a claim of full Android app localization", doc)

    def test_smoke_antennapod_helper_has_valid_bash_syntax(self) -> None:
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash is not available")
        probe = subprocess.run(
            [bash, "-lc", "true"],
            capture_output=True,
            check=False,
        )
        if probe.returncode != 0:
            self.skipTest("bash is present but not runnable")
        result = subprocess.run(
            [bash, "-n", "scripts/smoke-antennapod.sh"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ios_strings_are_detected_as_platform_resources(self) -> None:
        source_files = ["App/en.lproj/Localizable.strings", "App/en.lproj/Localizable.stringsdict"]
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "ios-project"
            for source_file in source_files:
                copied = project / source_file
                copied.parent.mkdir(parents=True, exist_ok=True)
                copied.write_text((IOS_FIXTURE_ROOT / source_file).read_text(encoding="utf-8"), encoding="utf-8")

            inspection = inspect_project(project)
            self.assertEqual(inspection["adapter_counts"], {"core.ios-strings": 2})
            self.assertEqual([item["path"] for item in inspection["supported_files"]], source_files)

            result = initialize_project(project, "en-US", source_files, ["zh-CN"])
            self.assertEqual([item["adapter"] for item in result["manifest"]["source_material"]], ["core.ios-strings", "core.ios-strings"])

    def test_xcstrings_are_detected_as_platform_resources(self) -> None:
        source_file = "App/Localizable.xcstrings"
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "xcstrings-project"
            copied = project / source_file
            copied.parent.mkdir(parents=True)
            copied.write_text((XCSTRINGS_FIXTURE_ROOT / source_file).read_text(encoding="utf-8"), encoding="utf-8")

            inspection = inspect_project(project)
            self.assertEqual(inspection["adapter_counts"], {"core.xcstrings": 1})
            self.assertEqual(inspection["supported_files"][0]["path"], source_file)

            result = initialize_project(project, "en-US", [source_file], ["zh-CN"])
            self.assertEqual(result["manifest"]["source_material"][0]["adapter"], "core.xcstrings")

    def test_plan_and_retrieve_context_packet(self) -> None:
        source = FIXTURE_ROOT / "locales" / "en-US.json"
        segments = extract_segments(source, "en-US", "locales/en-US.json")
        plan = create_batch_plan(segments, "en-US", ["zh-CN"], operating_mode="rewrite_or_harmonization")
        assert_protocol_schema(self, "batch-plan", plan)
        self.assertEqual(plan["operating_mode"], "rewrite_or_harmonization")
        self.assertEqual(plan["reference_policy"], "tm_assisted")
        self.assertEqual([batch["content_unit"] for batch in plan["batches"]], ["json:inventory", "json:menu"])

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            locale_dir = project / "locales"
            locale_dir.mkdir()
            (locale_dir / "en-US.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            result = initialize_project(project, "en-US", ["locales/en-US.json"], ["zh-CN"])
            state = Path(result["state_directory"])
            with (state / "glossary.csv").open("a", encoding="utf-8") as handle:
                handle.write("Weight,en-US,zh-CN,重量,approved,ui,noun,Displayed item weight,inventory,false,project,\n")
            write_jsonl(
                state / "translation-memory.jsonl",
                [
                    {
                        "id": "tm-weight",
                        "segment_id": "old-weight",
                        "source": "Weight: %s kg",
                        "target": "重量：%s kg",
                        "source_locale": "en-US",
                        "target_locale": "zh-CN",
                        "content_type": "locale_string",
                        "status": "approved",
                    }
                ],
            )
            packet = build_work_packet(plan, "batch-0001", segments, state, "zh-CN", limit_tokens=4000)
            assert_protocol_schema(self, "work-packet", packet)
            self.assertEqual(packet["batch_id"], "batch-0001")
            self.assertEqual(packet["operating_mode"], "rewrite_or_harmonization")
            self.assertEqual(packet["reference_policy"], "tm_assisted")
            self.assertEqual(packet["memory"]["glossary"][0]["approved_translation"], "重量")
            self.assertEqual(packet["memory"]["translation_memory"][0]["match_kind"], "exact_source")
            self.assertLessEqual(packet["budget"]["estimated_tokens"], packet["budget"]["limit_tokens"])

            draft_request = create_draft_request(packet)
            assert_protocol_schema(self, "draft-request", draft_request)
            prompt = render_draft_prompt(draft_request)
            self.assertIn("Return only generated segment JSONL", prompt)
            self.assertIn(packet["batch_id"], prompt)
            self.assertIn('"segments"', prompt)
            generated = []
            for segment in packet["segments"]:
                candidate = dict(segment)
                candidate["target_locale"] = "zh-CN"
                candidate["target"] = segment["source"].replace("Start game", "开始游戏").replace(
                    "Welcome, {player}!", "欢迎你，{player}！"
                ).replace("coins", "硬币").replace("Weight", "重量")
                candidate["status"] = "generated"
                candidate["generation"] = {"kind": "unit_test", "quality_claim": "none"}
                generated.append(candidate)
            generated_result = validate_generated_segments(packet, generated)
            self.assertEqual(generated_result["status"], "pass", generated_result["items"])
            assert_protocol_schema(self, "qa-result", generated_result)

            broken = json.loads(json.dumps(generated, ensure_ascii=False))
            broken[0]["target"] = "缺少占位符"
            if broken[0]["constraints"]["placeholders"]:
                self.assertEqual(validate_generated_segments(packet, broken)["status"], "fail")

            handoff_root = Path(directory) / "handoff"
            packet_dir = handoff_root / "work-packets"
            request_dir = handoff_root / "draft-requests"
            generated_dir = handoff_root / "generated-batches"
            write_json(packet_dir / "batch-0001.json", packet)
            write_json(request_dir / "batch-0001.json", draft_request)
            write_jsonl(generated_dir / "batch-0001.jsonl", generated)
            handoff = create_generation_handoff(packet_dir, request_dir, generated_dir, "zh-CN")
            self.assertEqual(handoff["request_count"], 1)
            assert_protocol_schema(self, "generation-handoff", handoff)
            prompt_manifest = write_handoff_prompts(handoff, handoff_root / "prompts")
            self.assertEqual(prompt_manifest["summary"]["prompt_count"], 1)
            self.assertTrue((handoff_root / "prompts" / "batch-0001.md").is_file())
            self.assertIn("batch-0001-response.md", prompt_manifest["prompts"][0]["suggested_response_file"])
            collected = collect_generated_handoff(handoff, handoff_root / "generated.jsonl")
            self.assertEqual(collected["status"], "pass", collected["items"])
            self.assertEqual(collected["summary"]["generated_segment_count"], len(generated))
            self.assertEqual(read_jsonl(handoff_root / "generated.jsonl"), generated)
            review_sheet = write_review_sheet(
                generated,
                handoff_root / "review-sheet.md",
                handoff_root / "review-sheet.csv",
            )
            self.assertEqual(review_sheet["summary"]["segment_count"], len(generated))
            self.assertTrue((handoff_root / "review-sheet.md").read_text(encoding="utf-8").startswith("# Translation Review Sheet"))
            self.assertIn("segment_id,source_path", (handoff_root / "review-sheet.csv").read_text(encoding="utf-8"))

            minimal_response = json.dumps(
                [
                    {
                        "segment_id": segment["segment_id"],
                        "source": "model-mutated-source",
                        "translation": f"[zh-CN] {segment['source']}",
                    }
                    for segment in packet["segments"]
                ],
                ensure_ascii=False,
            )
            imported_path = handoff_root / "imported-array.jsonl"
            imported = import_generated_response(packet, minimal_response, imported_path)
            self.assertEqual(imported["status"], "pass", imported["items"])
            self.assertEqual(imported["summary"]["parsed_record_count"], len(packet["segments"]))
            imported_records = read_jsonl(imported_path)
            self.assertEqual(imported_records[0]["source"], packet["segments"][0]["source"])
            self.assertEqual(imported_records[0]["target"], f"[zh-CN] {packet['segments'][0]['source']}")
            self.assertEqual(imported_records[0]["generation"]["imported_from"], "llm_response")

            mapped = {segment["segment_id"]: f"[zh-CN] {segment['source']}" for segment in packet["segments"]}
            fenced_response = "```json\n" + json.dumps(mapped, ensure_ascii=False) + "\n```"
            fenced_import = import_generated_response(packet, fenced_response, handoff_root / "imported-map.jsonl")
            self.assertEqual(fenced_import["status"], "pass", fenced_import["items"])
            self.assertTrue(fenced_import["response_format"].startswith("fenced-1:"))

            bom_import = import_generated_response(packet, "\ufeff" + json.dumps(mapped, ensure_ascii=False), handoff_root / "imported-bom.jsonl")
            self.assertEqual(bom_import["status"], "pass", bom_import["items"])

            response_dir = handoff_root / "responses"
            response_dir.mkdir()
            response_path = response_dir / "batch-0001-response.md"
            response_path.write_text(fenced_response, encoding="utf-8")
            imported_handoff = import_generated_handoff(
                handoff,
                response_dir,
                handoff_root / "imported-generated.jsonl",
            )
            self.assertEqual(imported_handoff["status"], "pass", imported_handoff["items"])
            self.assertEqual(imported_handoff["summary"]["imported_batch_count"], 1)
            self.assertEqual(imported_handoff["summary"]["generated_segment_count"], len(packet["segments"]))
            self.assertEqual(len(read_jsonl(handoff_root / "imported-generated.jsonl")), len(packet["segments"]))

            missing_handoff = import_generated_handoff(handoff, handoff_root / "missing-responses")
            self.assertEqual(missing_handoff["status"], "fail")
            self.assertEqual(missing_handoff["summary"]["blocking_count"], 1)
            retry = create_retry_handoff(handoff, missing_handoff, handoff_root / "retry-generated")
            assert_protocol_schema(self, "generation-handoff", retry)
            self.assertEqual(retry["parent_handoff_id"], handoff["handoff_id"])
            self.assertEqual(retry["request_count"], 1)
            self.assertEqual(retry["retry"]["failed_batch_ids"], ["batch-0001"])
            self.assertEqual(retry["batches"][0]["generated"], (handoff_root / "retry-generated" / "batch-0001.jsonl").as_posix())

    def test_term_governance_hard_constraints_feed_work_packets(self) -> None:
        source = FIXTURE_ROOT / "locales" / "en-US.json"
        segments = extract_segments(source, "en-US", "locales/en-US.json")
        plan = create_batch_plan(segments, "en-US", ["zh-CN"])

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            locale_dir = project / "locales"
            locale_dir.mkdir(parents=True)
            (locale_dir / "en-US.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            result = initialize_project(project, "en-US", ["locales/en-US.json"], ["zh-CN"])
            state = Path(result["state_directory"])

            with (state / "term-registry.csv").open("a", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "source_term",
                        "target_term",
                        "type",
                        "status",
                        "priority",
                        "scope",
                        "notes",
                        "source_locale",
                        "target_locale",
                        "forbidden_targets",
                        "provenance",
                    ],
                )
                writer.writerow(
                    {
                        "source_term": "Weight",
                        "target_term": "重量",
                        "type": "ui_term",
                        "status": "locked",
                        "priority": "user_confirmed",
                        "scope": "inventory",
                        "notes": "Use the short UI term.",
                        "source_locale": "en-US",
                        "target_locale": "zh-CN",
                        "forbidden_targets": "体重|砝码",
                        "provenance": "user_decision",
                    }
                )
                writer.writerow(
                    {
                        "source_term": "coins",
                        "target_term": "金币",
                        "type": "ui_term",
                        "status": "suggested",
                        "priority": "model_suggestion",
                        "scope": "inventory",
                        "target_locale": "zh-CN",
                    }
                )
            with (state / "forbidden-translations.csv").open("a", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "source_term",
                        "forbidden_target",
                        "target_locale",
                        "scope",
                        "reason",
                        "status",
                        "provenance",
                    ],
                )
                writer.writerow(
                    {
                        "source_term": "coins",
                        "forbidden_target": "硬币们",
                        "target_locale": "zh-CN",
                        "scope": "inventory",
                        "reason": "unnatural_plural",
                        "status": "rejected",
                        "provenance": "user_decision",
                    }
                )

            packet = build_work_packet(plan, "batch-0001", segments, state, "zh-CN")
            assert_protocol_schema(self, "work-packet", packet)
            hard_constraints = packet["memory"]["hard_constraints"]
            self.assertEqual(hard_constraints["visibility"], "approved_locked_terms_only")
            self.assertEqual([item["source_term"] for item in hard_constraints["term_registry"]], ["Weight"])
            self.assertEqual(hard_constraints["term_registry"][0]["target_term"], "重量")
            self.assertEqual(
                {(item["source_term"], item["forbidden_target"]) for item in hard_constraints["forbidden_translations"]},
                {("Weight", "体重"), ("Weight", "砝码"), ("coins", "硬币们")},
            )

            blind_plan = create_batch_plan(segments, "en-US", ["zh-CN"], operating_mode="blind_benchmark")
            blind_packet = build_work_packet(blind_plan, "batch-0001", segments, state, "zh-CN")
            self.assertEqual(blind_packet["memory"]["hard_constraints"]["term_registry"], [])
            self.assertEqual(blind_packet["memory"]["hard_constraints"]["forbidden_translations"], [])
            self.assertEqual(blind_packet["memory"]["hard_constraints"]["visibility"], "hidden_by_reference_policy")


class LocalizeRunTests(unittest.TestCase):
    def test_handoff_only_infers_source_locale_files_and_writes_requests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            locales = project / "locales"
            locales.mkdir(parents=True)
            (locales / "en-US.json").write_text((FIXTURE_ROOT / "locales" / "en-US.json").read_text(encoding="utf-8"), encoding="utf-8")
            (locales / "zh-CN.json").write_text((FIXTURE_ROOT / "locales" / "zh-CN.json").read_text(encoding="utf-8"), encoding="utf-8")

            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                output_root=root / "out",
                run_id="handoff-001",
                max_segments=2,
                handoff_only=True,
            )

            self.assertEqual(result["status"], "handoff_ready")
            self.assertEqual(result["source_files"], ["locales/en-US.json"])
            run_dir = Path(result["artifacts"]["run_directory"])
            self.assertTrue((run_dir / "segments.jsonl").is_file())
            self.assertTrue((run_dir / "batch-plan.json").is_file())
            self.assertTrue((run_dir / "generation-handoff.json").is_file())
            self.assertTrue((run_dir / "prompt-manifest.json").is_file())
            self.assertTrue((run_dir / "generation-README.md").is_file())
            self.assertTrue((run_dir / "responses").is_dir())
            self.assertEqual(len(list((run_dir / "draft-requests").glob("*.json"))), result["summary"]["batch_count"])
            self.assertEqual(len(list((run_dir / "prompts").glob("*.md"))), result["summary"]["batch_count"])
            self.assertIn("generation_readme", result["artifacts"])
            self.assertFalse((run_dir / "staging").exists())

    def test_synthetic_draft_runs_to_staged_delivery_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            locales = project / "locales"
            locales.mkdir(parents=True)
            source = FIXTURE_ROOT / "locales" / "en-US.json"
            (locales / "en-US.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                source_files=["locales/en-US.json"],
                output_root=root / "out",
                run_id="draft-001",
                max_segments=2,
                synthetic_draft=True,
            )

            self.assertEqual(result["status"], "draft_package_created")
            self.assertEqual(result["generation"]["mode"], "synthetic_draft")
            self.assertEqual(result["summary"]["output_count"], 1)
            self.assertEqual(result["summary"]["qa_status"], "pass")
            delivery = Path(result["artifacts"]["delivery_directory"])
            manifest = read_json(delivery / "delivery-manifest.json")
            self.assertEqual(manifest["generation"]["provider_actual"], "synthetic")
            self.assertEqual(manifest["generation"]["provider_status"], "synthetic_test")
            self.assertTrue(manifest["generation"]["apply_allowed"])
            self.assertFalse(read_json(Path(result["artifacts"]["apply_plan"]))["blocked_by_provider_status"])
            packaged_target = delivery / "files" / "locales" / "zh-CN.json"
            self.assertTrue(packaged_target.is_file())
            self.assertEqual(validate_pair(source, packaged_target)["status"], "pass")
            self.assertTrue(Path(result["artifacts"]["delivery_dashboard"]).is_file())
            self.assertTrue(Path(result["artifacts"]["delivery_dashboard_markdown"]).is_file())
            self.assertTrue(Path(result["artifacts"]["review_sheet_markdown"]).is_file())
            self.assertTrue(Path(result["artifacts"]["review_sheet_csv"]).is_file())
            self.assertTrue(Path(result["artifacts"]["apply_plan"]).is_file())
            self.assertTrue(Path(result["artifacts"]["apply_plan_markdown"]).is_file())
            self.assertTrue(Path(result["artifacts"]["delivery_decision"]).is_file())
            self.assertTrue(Path(result["artifacts"]["delivery_decision_markdown"]).is_file())
            delivery_decision = read_json(Path(result["artifacts"]["delivery_decision"]))
            assert_protocol_schema(self, "delivery-decision", delivery_decision)
            self.assertEqual(delivery_decision["status"], "owner_review_required")
            self.assertIn("Apply Plan", Path(result["artifacts"]["apply_plan_markdown"]).read_text(encoding="utf-8"))
            self.assertIn(
                "Delivery Decision Report",
                Path(result["artifacts"]["delivery_decision_markdown"]).read_text(encoding="utf-8"),
            )
            self.assertIn("Translation Review Sheet", Path(result["artifacts"]["review_sheet_markdown"]).read_text(encoding="utf-8"))

    def test_android_localize_run_reports_merged_dependency_warning_without_overlay_or_source_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            merged = project / "app" / "build" / "intermediates" / "incremental" / "debug" / "mergeDebugResources" / "merged.dir" / "values" / "values.xml"
            merged.parent.mkdir(parents=True)
            merged.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Sample App</string>
    <string name="sort_by">Sort by</string>
    <string name="storage">Storage</string>
</resources>
""",
                encoding="utf-8",
            )
            before_app_sources = {
                path.relative_to(project).as_posix(): path.read_bytes()
                for path in (project / "app" / "src").rglob("*")
                if path.is_file()
            }

            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                output_root=root / "out",
                run_id="android-coverage-diagnosis-001",
                max_segments=20,
                synthetic_draft=True,
            )

            after_app_sources = {
                path.relative_to(project).as_posix(): path.read_bytes()
                for path in (project / "app" / "src").rglob("*")
                if path.is_file()
            }
            self.assertEqual(result["status"], "draft_package_created")
            self.assertEqual(before_app_sources, after_app_sources)
            self.assertFalse(list((project / "app" / "src").rglob("localize_anything_overlay*.xml")))
            self.assertEqual(result["summary"]["android_coverage"]["coverage_mode"], "source-only")
            self.assertEqual(result["summary"]["android_coverage"]["merged_dependency_strings_detected"], 2)
            self.assertTrue(result["summary"]["android_coverage"]["visible_ui_coverage_warning"])
            self.assertTrue(any("source-only localization may not cover" in warning for warning in result["warnings"]))

    def test_provider_failed_fallback_delivery_is_not_apply_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            _copy_json_fixture_project(project, include_existing_target=False)
            source = project / "locales" / "en-US.json"
            generated_path = root / "deepseek-fallback.jsonl"
            generated = []
            for segment in extract_segments(source, "en-US", "locales/en-US.json"):
                record = dict(segment)
                record["target_locale"] = "zh-CN"
                record["target"] = f"[zh-CN] {segment['source']}"
                record["status"] = "generated"
                record["generation"] = {
                    "provider": "deepseek-fallback",
                    "provider_error_kind": "ssl_certificate_error",
                    "quality_claim": "none",
                    "purpose": "fallback",
                }
                generated.append(record)
            write_jsonl(generated_path, generated)

            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                source_files=["locales/en-US.json"],
                output_root=root / "out",
                run_id="provider-fallback-001",
                max_segments=10,
                generated=generated_path,
            )

            self.assertEqual(result["status"], "provider_generation_failed")
            self.assertEqual(result["generation"]["provider_requested"], "deepseek")
            self.assertEqual(result["generation"]["provider_actual"], "synthetic_fallback")
            self.assertEqual(result["generation"]["provider_status"], "failed")
            self.assertEqual(result["generation"]["provider_generated_segments"], 0)
            self.assertEqual(result["generation"]["synthetic_fallback_segments"], len(generated))
            self.assertFalse(result["generation"]["apply_allowed"])
            delivery = Path(result["artifacts"]["delivery_directory"])
            manifest = read_json(delivery / "delivery-manifest.json")
            self.assertEqual(manifest["delivery_status"], "blocked")
            self.assertFalse(manifest["generation"]["apply_allowed"])
            plan = create_apply_plan(delivery, project)
            self.assertTrue(plan["blocked_by_provider_status"])
            with self.assertRaisesRegex(ValueError, "provider generation status"):
                execute_apply(delivery, project, "provider-fallback-001")

    def test_android_merged_resources_overlay_is_explicit_and_app_owned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "android-project"
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            debug_source = project / "app" / "src" / "debug" / "res" / "values" / "strings.xml"
            debug_source.parent.mkdir(parents=True)
            debug_source.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="debug_label">Debug</string>
</resources>
""",
                encoding="utf-8",
            )
            target_existing = project / "app" / "src" / "main" / "res" / "values-th" / "strings.xml"
            target_existing.parent.mkdir(parents=True)
            target_existing.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="already_translated">Existing target</string>
</resources>
""",
                encoding="utf-8",
            )
            merged = project / "merged" / "values.xml"
            merged.parent.mkdir(parents=True)
            merged.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">App duplicate</string>
    <string name="already_translated">Existing target duplicate</string>
    <string name="files_tab">Files</string>
    <string name="skip_dependency" translatable="false">Do not translate</string>
    <string-array name="sort_options">
        <item>Name</item>
        <item>Date</item>
    </string-array>
    <plurals name="item_count">
        <item quantity="one">%d item</item>
        <item quantity="other">%d items</item>
    </plurals>
    <color name="brand_color">#ffffff</color>
</resources>
""",
                encoding="utf-8",
            )
            before_app_sources = {
                path.relative_to(project).as_posix(): path.read_bytes()
                for path in (project / "app" / "src").rglob("*")
                if path.is_file()
            }

            result = run_localize(
                project,
                "en-US",
                ["th"],
                source_files=[
                    "app/src/debug/res/values/strings.xml",
                    "app/src/main/res/values/strings.xml",
                ],
                output_root=root / "out",
                run_id="android-overlay-001",
                max_segments=40,
                synthetic_draft=True,
                include_android_merged_resources=True,
                android_merged_resources=merged,
                android_build_variant="debug",
            )

            after_app_sources = {
                path.relative_to(project).as_posix(): path.read_bytes()
                for path in (project / "app" / "src").rglob("*")
                if path.is_file()
            }
            self.assertEqual(result["status"], "draft_package_created")
            self.assertEqual(before_app_sources, after_app_sources)
            self.assertFalse((project / "app" / "src" / "main" / "res" / "values-th" / "localize_anything_overlay.xml").exists())
            coverage = result["summary"]["android_coverage"]
            self.assertEqual(coverage["coverage_mode"], "source-plus-merged-overlay")
            self.assertFalse(coverage["visible_ui_coverage_warning"])
            self.assertEqual(coverage["merged_dependency_strings_included"], 5)
            overlay = result["android_merged_overlay"]
            self.assertEqual(overlay["destination"], "app/src/main/res/values-th/localize_anything_overlay.xml")
            self.assertEqual(overlay["merged_dependency_resources_excluded"]["app_owned_duplicate"], 1)
            self.assertEqual(overlay["merged_dependency_resources_excluded"]["target_locale_existing"], 1)
            self.assertEqual(overlay["merged_dependency_resources_excluded"]["translatable_false"], 1)
            self.assertEqual(overlay["merged_dependency_resources_excluded"]["unsupported_type"], 1)

            delivery = Path(result["artifacts"]["delivery_directory"])
            packaged_overlay = delivery / "files" / "app" / "src" / "main" / "res" / "values-th" / "localize_anything_overlay.xml"
            self.assertTrue(packaged_overlay.is_file())
            overlay_text = packaged_overlay.read_text(encoding="utf-8")
            self.assertIn('name="files_tab"', overlay_text)
            self.assertIn('name="sort_options"', overlay_text)
            self.assertIn('name="item_count"', overlay_text)
            self.assertNotIn("app_name", overlay_text)
            self.assertNotIn("already_translated", overlay_text)
            self.assertNotIn("skip_dependency", overlay_text)
            self.assertNotIn("brand_color", overlay_text)
            manifest = read_json(delivery / "delivery-manifest.json")
            overlay_outputs = [
                output
                for output in manifest["outputs"]
                if output.get("source_category") == "merged_dependency_overlay"
            ]
            self.assertEqual(len(overlay_outputs), 1)
            self.assertEqual(overlay_outputs[0]["destination"], "app/src/main/res/values-th/localize_anything_overlay.xml")
            self.assertEqual(overlay_outputs[0]["apply_safety"]["requires_explicit_run_id"], True)
            self.assertEqual(overlay_outputs[0]["apply_safety"]["requires_clean_git_tree"], True)
            self.assertNotIn(str(root), json.dumps(overlay_outputs[0]))

    def test_blind_benchmark_hides_target_references_from_generation_packets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            _copy_json_fixture_project(project, include_existing_target=True)
            segments = extract_segments(project / "locales" / "en-US.json", "en-US", "locales/en-US.json")
            start = next(segment for segment in segments if segment["context"]["json_pointer"] == "/menu/start")
            state = project / ".localize-anything"
            state.mkdir(parents=True)
            (state / "glossary.csv").write_text(
                "term,source_locale,target_locale,approved_translation,status,scope,part_of_speech,definition,context,do_not_translate,source_provenance,notes\n"
                "Start,en-US,zh-CN,LEAK_GLOSSARY_TARGET,approved,ui,noun,Test leak,menu,false,test,\n",
                encoding="utf-8",
            )
            write_jsonl(
                state / "translation-memory.jsonl",
                [
                    {
                        "id": "tm-leak-start",
                        "identity": "json_pointer:/menu/start",
                        "segment_id": start["segment_id"],
                        "source": start["source"],
                        "source_hash": start["source_hash"],
                        "target": "LEAK_TM_TARGET",
                        "source_locale": "en-US",
                        "target_locale": "zh-CN",
                        "content_type": "locale_string",
                        "status": "approved",
                    }
                ],
            )

            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                source_files=["locales/en-US.json"],
                output_root=root / "out",
                run_id="blind-001",
                max_segments=10,
                handoff_only=True,
                operating_mode="blind_benchmark",
            )

            self.assertEqual(result["project"]["operating_mode"], "blind_benchmark")
            self.assertEqual(result["project"]["reference_policy"], "blind")
            reference_plan = read_json(Path(result["artifacts"]["reference_plan"]))
            self.assertTrue(reference_plan["summary"]["blind_reference_hidden"])
            self.assertGreaterEqual(reference_plan["summary"]["existing_reference_file_count"], 1)

            packet_paths = sorted(Path(result["artifacts"]["work_packets"]).glob("*.json"))
            self.assertTrue(packet_paths)
            for packet_path in packet_paths:
                packet = read_json(packet_path)
                self.assertEqual(packet["operating_mode"], "blind_benchmark")
                self.assertEqual(packet["reference_policy"], "blind")
                self.assertEqual(packet["memory"]["glossary"], [])
                self.assertEqual(packet["memory"]["translation_memory"], [])
                packet_text = json.dumps(packet, ensure_ascii=False)
                self.assertNotIn("LEAK_GLOSSARY_TARGET", packet_text)
                self.assertNotIn("LEAK_TM_TARGET", packet_text)

                draft_request = read_json(Path(result["artifacts"]["draft_requests"]) / packet_path.name)
                request_text = json.dumps(draft_request, ensure_ascii=False)
                self.assertIn("Blind benchmark mode", "\n".join(draft_request["instructions"]))
                self.assertNotIn("LEAK_GLOSSARY_TARGET", request_text)
                self.assertNotIn("LEAK_TM_TARGET", request_text)

    def test_existing_locale_maintenance_preserves_reviewed_unchanged_segments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            _copy_json_fixture_project(project, include_existing_target=True)
            segments = extract_segments(project / "locales" / "en-US.json", "en-US", "locales/en-US.json")
            start = next(segment for segment in segments if segment["context"]["json_pointer"] == "/menu/start")
            state = project / ".localize-anything"
            state.mkdir(parents=True)
            write_jsonl(
                state / "translation-memory.jsonl",
                [
                    {
                        "id": "tm-reviewed-start",
                        "identity": "json_pointer:/menu/start",
                        "segment_id": start["segment_id"],
                        "source": start["source"],
                        "source_hash": start["source_hash"],
                        "target": "REVIEWED START TARGET",
                        "source_locale": "en-US",
                        "target_locale": "zh-CN",
                        "content_type": "locale_string",
                        "status": "reviewed",
                    }
                ],
            )

            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                source_files=["locales/en-US.json"],
                output_root=root / "out",
                run_id="maintenance-001",
                max_segments=10,
                synthetic_draft=True,
                operating_mode="existing_locale_maintenance",
            )

            self.assertEqual(result["project"]["operating_mode"], "existing_locale_maintenance")
            self.assertEqual(result["project"]["reference_policy"], "preserve_existing")
            reference_plan = read_json(Path(result["artifacts"]["reference_plan"]))
            self.assertEqual(reference_plan["summary"]["source_segment_count"], len(segments))
            self.assertEqual(reference_plan["summary"]["preserved_segment_count"], 1)
            self.assertEqual(reference_plan["summary"]["candidate_segment_count"], len(segments) - 1)

            batch_plan = read_json(Path(result["artifacts"]["batch_plan"]))
            planned_segment_ids = {
                segment_id
                for batch in batch_plan["batches"]
                for segment_id in batch["segment_ids"]
            }
            self.assertNotIn(start["segment_id"], planned_segment_ids)

            for packet_path in sorted(Path(result["artifacts"]["work_packets"]).glob("*.json")):
                packet = read_json(packet_path)
                self.assertNotIn(start["segment_id"], [segment["segment_id"] for segment in packet["segments"]])
                self.assertEqual(packet["reference_policy"], "preserve_existing")

            delivery = Path(result["artifacts"]["delivery_directory"])
            packaged_target = delivery / "files" / "locales" / "zh-CN.json"
            target_payload = json.loads(packaged_target.read_text(encoding="utf-8"))
            self.assertEqual(target_payload["menu"]["start"], "REVIEWED START TARGET")
            self.assertTrue(target_payload["menu"]["welcome"].startswith("[zh-CN] "))

    def test_existing_locale_maintenance_can_package_when_all_segments_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            _copy_json_fixture_project(project, include_existing_target=True)
            segments = extract_segments(project / "locales" / "en-US.json", "en-US", "locales/en-US.json")
            state = project / ".localize-anything"
            state.mkdir(parents=True)
            write_jsonl(
                state / "translation-memory.jsonl",
                [
                    {
                        "id": f"tm-reviewed-{index}",
                        "identity": f"json_pointer:{segment['context']['json_pointer']}",
                        "segment_id": segment["segment_id"],
                        "source": segment["source"],
                        "source_hash": segment["source_hash"],
                        "target": f"REVIEWED {segment['source']}",
                        "source_locale": "en-US",
                        "target_locale": "zh-CN",
                        "content_type": "locale_string",
                        "status": "reviewed",
                    }
                    for index, segment in enumerate(segments)
                ],
            )

            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                source_files=["locales/en-US.json"],
                output_root=root / "out",
                run_id="maintenance-all-preserved-001",
                max_segments=10,
                synthetic_draft=True,
                operating_mode="existing_locale_maintenance",
            )

            self.assertEqual(result["status"], "draft_package_created")
            self.assertEqual(result["summary"]["candidate_segment_count"], 0)
            self.assertEqual(result["summary"]["preserved_segment_count"], len(segments))
            self.assertEqual(result["summary"]["batch_count"], 0)
            self.assertEqual(list(Path(result["artifacts"]["work_packets"]).glob("*.json")), [])
            self.assertEqual(read_json(Path(result["artifacts"]["generation_handoff"]))["request_count"], 0)
            self.assertEqual(read_jsonl(Path(result["artifacts"]["generated_segments"])), [])

            delivery = Path(result["artifacts"]["delivery_directory"])
            packaged_target = delivery / "files" / "locales" / "zh-CN.json"
            target_payload = json.loads(packaged_target.read_text(encoding="utf-8"))
            self.assertEqual(target_payload["menu"]["start"], "REVIEWED Start Game")
            self.assertEqual(target_payload["menu"]["welcome"], "REVIEWED Welcome, {player}!")
            self.assertEqual(target_payload["inventory"]["coins"], "REVIEWED You have {{count}} coins.")
            self.assertEqual(target_payload["inventory"]["weight"], "REVIEWED Weight: %s kg")


class AgentRunTests(unittest.TestCase):
    def test_agent_run_routes_project_and_writes_handoff_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            _copy_json_fixture_project(project)

            result = run_agent(
                project,
                "zh-CN",
                output_root=root / "out",
                run_id="agent-001",
                max_segments=2,
            )

            self.assertEqual(result["status"], "awaiting_llm_responses")
            self.assertEqual(result["agent"]["architecture"], "routing_parallelization_reflection")
            self.assertEqual(result["routing"]["adapter_counts"], {"core.json-locale": 2})
            self.assertEqual(result["routing"]["selected_source_files"], ["locales/en-US.json"])
            self.assertEqual(result["parallelization"]["batch_count"], result["summary"]["batch_count"])
            self.assertEqual(result["reflection"]["status"], "pending_llm_output")
            self.assertIn("scan_policy", result["routing"])
            self.assertIn("session_index", result["artifacts"])
            assert_protocol_schema(self, "agent-summary", result)
            run_dir = Path(result["artifacts"]["run_directory"])
            self.assertTrue((run_dir / "agent-summary.json").is_file())
            self.assertTrue((run_dir / "generation-README.md").is_file())
            self.assertIn("--responses-dir", "\n".join(result["next_actions"]))
            session_index = load_session_index(project)
            assert_protocol_schema(self, "project-session", session_index)
            self.assertEqual(session_index["latest_session_id"], "agent-001")
            self.assertEqual(session_index["sessions"][-1]["kind"], "agent_run")
            self.assertEqual(session_index["sessions"][-1]["selected_source_files"], ["locales/en-US.json"])

    def test_agent_run_synthetic_draft_creates_reviewable_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            _copy_json_fixture_project(project, include_existing_target=False)

            result = run_agent(
                project,
                "zh-CN",
                source_files=["locales/en-US.json"],
                output_root=root / "out",
                run_id="agent-draft-001",
                max_segments=2,
                synthetic_draft=True,
            )

            self.assertEqual(result["status"], "draft_package_created")
            self.assertEqual(result["reflection"]["status"], "review_artifacts_ready")
            self.assertEqual(result["reflection"]["qa_status"], "pass")
            self.assertEqual(result["reflection"]["delivery_decision_status"], "owner_review_required")
            self.assertEqual(result["delivery"]["status"], "decision_ready")
            self.assertEqual(result["delivery"]["decision_status"], "owner_review_required")
            self.assertTrue(result["reflection"]["requires_user_confirmation_before_apply"])
            self.assertTrue(Path(result["artifacts"]["agent_summary"]).is_file())
            self.assertTrue(Path(result["artifacts"]["review_sheet_markdown"]).is_file())
            self.assertTrue(Path(result["artifacts"]["llm_review_request"]).is_file())
            self.assertTrue(Path(result["artifacts"]["llm_review_prompt"]).is_file())
            self.assertEqual(result["reflection"]["llm_review_status"], "request_ready")
            self.assertTrue(Path(result["artifacts"]["apply_plan_markdown"]).is_file())
            self.assertTrue(Path(result["artifacts"]["delivery_decision_markdown"]).is_file())
            delivery = Path(result["artifacts"]["delivery_directory"])
            self.assertTrue((delivery / "files" / "locales" / "zh-CN.json").is_file())

    def test_agent_run_synthetic_gettext_plural_preserves_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            (project / "messages.pot").write_text((GETTEXT_WESNOTH_ROOT / "messages.pot").read_text(encoding="utf-8"), encoding="utf-8")

            result = run_agent(
                project,
                "zh-CN",
                source_files=["messages.pot"],
                output_root=root / "out",
                run_id="agent-gettext-001",
                max_segments=2,
                synthetic_draft=True,
            )

            self.assertEqual(result["status"], "draft_package_created", result.get("reflection"))
            self.assertEqual(result["routing"]["adapter_counts"], {"core.gettext-po": 1})
            self.assertEqual(result["summary"]["segment_count"], 2)
            self.assertEqual(result["reflection"]["qa_status"], "pass")
            delivery = Path(result["artifacts"]["delivery_directory"])
            packaged_target = delivery / "files" / "messages.zh_CN.pot"
            self.assertTrue(packaged_target.is_file())
            self.assertIn("%d", packaged_target.read_text(encoding="utf-8"))

    def test_agent_run_imports_llm_responses_and_packages_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            _copy_json_fixture_project(project, include_existing_target=False)

            seed = run_agent(
                project,
                "zh-CN",
                output_root=root / "out",
                run_id="seed-handoff",
                max_segments=2,
            )
            responses_dir = root / "responses"
            responses_dir.mkdir()
            for packet_path in sorted(Path(seed["artifacts"]["work_packets"]).glob("*.json")):
                packet = read_json(packet_path)
                mapped = {segment["segment_id"]: f"[zh-CN] {segment['source']}" for segment in packet["segments"]}
                (responses_dir / f"{packet['batch_id']}-response.md").write_text(
                    "```json\n" + json.dumps(mapped, ensure_ascii=False) + "\n```",
                    encoding="utf-8",
                )

            result = run_agent(
                project,
                "zh-CN",
                output_root=root / "out",
                run_id="agent-response-001",
                max_segments=2,
                responses_dir=responses_dir,
            )

            self.assertEqual(result["status"], "draft_package_created", result.get("reflection"))
            self.assertEqual(result["reflection"]["response_import_status"], "pass")
            self.assertEqual(result["reflection"]["qa_status"], "pass")
            self.assertEqual(result["runs"]["handoff"]["run_id"], "agent-response-001-handoff")
            self.assertEqual(result["runs"]["delivery"]["run_id"], "agent-response-001-delivery")
            self.assertTrue(Path(result["artifacts"]["response_import"]).is_file())
            self.assertTrue(Path(result["artifacts"]["delivery_directory"]).is_dir())

    def test_agent_run_direct_http_provider_packages_delivery(self) -> None:
        class ProviderHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                mapped = {
                    segment["segment_id"]: f"[{payload['draft_request']['target_locale']}] {segment['source']}"
                    for segment in payload["draft_request"]["segments"]
                }
                body = json.dumps(mapped, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            _copy_json_fixture_project(project, include_existing_target=False)
            server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                result = run_agent(
                    project,
                    "zh-CN",
                    source_files=["locales/en-US.json"],
                    output_root=root / "out",
                    run_id="agent-provider-001",
                    max_segments=2,
                    provider_url=f"http://{host}:{port}/generate",
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

            self.assertEqual(result["status"], "draft_package_created", result.get("reflection"))
            self.assertEqual(result["agent"]["provider_mode"], "direct_http_provider")
            self.assertTrue(result["agent"]["direct_model_api"])
            self.assertEqual(result["reflection"]["provider_generation_status"], "pass")
            self.assertEqual(result["reflection"]["qa_status"], "pass")
            self.assertEqual(result["delivery"]["decision_status"], "owner_review_required")
            self.assertTrue(Path(result["artifacts"]["provider_generation"]).is_file())
            self.assertTrue(Path(result["artifacts"]["delivery_decision"]).is_file())
            self.assertTrue(Path(result["artifacts"]["delivery_directory"]).is_dir())


class ReviewAgentTests(unittest.TestCase):
    def test_llm_review_request_and_import_are_segment_level(self) -> None:
        segments = extract_segments(FIXTURE_ROOT / "locales" / "en-US.json", "en-US", "locales/en-US.json")
        for segment in segments:
            segment["target_locale"] = "zh-CN"
            segment["target"] = f"[zh-CN] {segment['source']}"
            segment["status"] = "generated"
        request = create_llm_review_request(
            segments,
            "en-US",
            "zh-CN",
            [{"segment_id": segments[0]["segment_id"], "severity": "warning", "message": "deterministic note"}],
            "review-run-001",
            max_segments=2,
        )
        assert_protocol_schema(self, "llm-review-request", request)
        prompt = render_llm_review_prompt(request)
        self.assertIn("issues", prompt)
        response = {
            "issues": [
                {
                    "segment_id": request["segments"][0]["segment_id"],
                    "severity": "blocking",
                    "category": "meaning",
                    "message": "Target mistranslates the command.",
                    "confidence": "medium",
                    "suggested_target": "开始游戏",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "llm-review-result.json"
            result = import_llm_review_response(request, "```json\n" + json.dumps(response, ensure_ascii=False) + "\n```", output)
            assert_protocol_schema(self, "llm-review-result", result)
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["summary"]["issue_count"], 1)
            self.assertEqual(result["issues"][0]["segment_id"], request["segments"][0]["segment_id"])
            self.assertTrue(output.is_file())


class ProviderGenerationTests(unittest.TestCase):
    def test_http_provider_generation_uses_generated_segment_contract(self) -> None:
        class ProviderHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                mapped = {
                    segment["segment_id"]: f"[{payload['draft_request']['target_locale']}] {segment['source']}"
                    for segment in payload["draft_request"]["segments"]
                }
                body = json.dumps(mapped, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            _copy_json_fixture_project(project, include_existing_target=False)
            source = project / "locales" / "en-US.json"
            source_path = "locales/en-US.json"
            initialized = initialize_project(project, "en-US", [source_path], ["zh-CN"])
            state = Path(initialized["state_directory"])
            segments = extract_segments(source, "en-US", source_path)
            plan = create_batch_plan(segments, "en-US", ["zh-CN"], max_segments=10)
            packet_dir = root / "work-packets"
            request_dir = root / "draft-requests"
            generated_dir = root / "generated-batches"
            for batch in plan["batches"]:
                packet = build_work_packet(plan, batch["batch_id"], segments, state, "zh-CN", limit_tokens=4000)
                write_json(packet_dir / f"{batch['batch_id']}.json", packet)
                write_json(request_dir / f"{batch['batch_id']}.json", create_draft_request(packet))
            handoff = create_generation_handoff(packet_dir, request_dir, generated_dir, "zh-CN")
            server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                result = generate_handoff_with_http_provider(
                    handoff,
                    f"http://{host}:{port}/generate",
                    root / "generated.jsonl",
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

            self.assertEqual(result["status"], "pass", result["items"])
            self.assertEqual(result["summary"]["generated_segment_count"], len(segments))
            generated = read_jsonl(root / "generated.jsonl")
            self.assertEqual(len(generated), len(segments))
            self.assertEqual(generated[0]["generation"]["imported_from"], "llm_response")


class ProviderPathHygieneTests(unittest.TestCase):
    def test_runtime_code_does_not_contain_private_local_paths(self) -> None:
        patterns = [
            "/mnt/c/Users/",
            "C:\\Users\\",
            "/Users/",
            ".env.reasonix",
        ]
        home_documents = re.compile(r"/home/[^/]+/Documents/")
        violations: list[tuple[str, str]] = []
        for path in (REPOSITORY_ROOT / "runtime").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for pattern in patterns:
                if pattern in text:
                    violations.append((path.relative_to(REPOSITORY_ROOT).as_posix(), pattern))
            if home_documents.search(text):
                violations.append((path.relative_to(REPOSITORY_ROOT).as_posix(), "/home/<name>/Documents/"))
        self.assertEqual(violations, [])

    def test_deepseek_provider_does_not_default_to_local_env_file(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DEEPSEEK_API_KEY not found"):
                _get_api_key()

    def test_deepseek_missing_credentials_error_has_no_private_path(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            try:
                _get_api_key()
            except RuntimeError as exc:
                message = str(exc)
            else:  # pragma: no cover - defensive guard
                self.fail("_get_api_key unexpectedly found credentials")
        self.assertNotIn("/mnt/c/Users", message)
        self.assertNotIn("C:\\Users", message)
        self.assertNotIn("/Users/", message)
        self.assertNotIn(".env.reasonix", message)

    def test_deepseek_explicit_env_file_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "deepseek.env"
            env_file.write_text("DEEPSEEK_API_KEY='test-key'\n", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {"LOCALIZE_ANYTHING_DEEPSEEK_ENV_FILE": str(env_file)},
                clear=True,
            ):
                self.assertEqual(_get_api_key(), "test-key")

    def test_deepseek_ssl_failure_does_not_write_synthetic_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            segments_path = root / "segments.jsonl"
            generated_path = root / "generated.jsonl"
            write_jsonl(
                segments_path,
                [
                    {
                        "segment_id": "s1",
                        "source": "Search",
                        "source_locale": "en-US",
                        "constraints": {},
                    }
                ],
            )
            with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=True), mock.patch(
                "runtime.localize_anything.deepseek_provider.urllib.request.urlopen",
                side_effect=ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED"),
            ):
                result = generate_deepseek_batch_file(segments_path, generated_path, "th")

            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["provider_status"], "failed")
            self.assertEqual(result["provider_error_kind"], "ssl_certificate_error")
            self.assertEqual(result["provider_generated_segments"], 0)
            self.assertEqual(result["synthetic_fallback_segments"], 0)
            self.assertEqual(result["quality_claim"], "none")
            self.assertFalse(result["apply_allowed"])
            self.assertFalse(generated_path.exists())


class WorkbenchUITests(unittest.TestCase):
    def test_ui_server_inspects_runs_agent_and_reads_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            _copy_json_fixture_project(project, include_existing_target=False)

            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                home_status, home = _http_get(host, port, "/")
                self.assertEqual(home_status, 200)
                self.assertIn("Localize Anything Workbench", home)

                inspect_status, inspected = _http_post_json(host, port, "/api/inspect", {"project": project.as_posix()})
                self.assertEqual(inspect_status, 200)
                self.assertEqual(inspected["status"], "pass")
                self.assertEqual(inspected["routing"]["adapter_counts"], {"core.json-locale": 1})

                run_status, run_payload = _http_post_json(
                    host,
                    port,
                    "/api/agent-run",
                    {
                        "project": project.as_posix(),
                        "source_locale": "en-US",
                        "target_locale": "zh-CN",
                        "source_files": ["locales/en-US.json"],
                        "output_root": (root / "out").as_posix(),
                        "run_id": "ui-agent-001",
                        "max_segments": 2,
                        "synthetic_draft": True,
                        "operating_mode": "blind_benchmark",
                        "reference_policy": "blind",
                    },
                )
                self.assertEqual(run_status, 200)
                result = run_payload["agent_result"]
                self.assertEqual(result["status"], "draft_package_created")
                self.assertEqual(result["project"]["operating_mode"], "blind_benchmark")
                self.assertEqual(result["project"]["reference_policy"], "blind")
                self.assertEqual(result["reflection"]["qa_status"], "pass")

                sessions_status, sessions_payload = _http_post_json(host, port, "/api/sessions", {"project": project.as_posix()})
                self.assertEqual(sessions_status, 200)
                self.assertEqual(sessions_payload["session_index"]["latest_session_id"], "ui-agent-001")

                read_status, artifact = _http_post_json(
                    host,
                    port,
                    "/api/read-artifact",
                    {"path": result["artifacts"]["review_sheet_markdown"]},
                )
                self.assertEqual(read_status, 200)
                self.assertIn("Translation Review Sheet", artifact["content"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_ui_import_files_creates_temp_project_and_rejects_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "upload.docx"
            _write_minimal_docx(source)
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                status, payload = _http_post_json(
                    host,
                    port,
                    "/api/import-files",
                    {
                        "files": [
                            {
                                "relative_path": "docs/upload.docx",
                                "content_base64": base64.b64encode(source.read_bytes()).decode("ascii"),
                            },
                            {
                                "relative_path": "locales/en-US.json",
                                "content_base64": base64.b64encode(b'{"hello": "Hello"}\n').decode("ascii"),
                            },
                        ]
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(payload["status"], "pass")
                imported_project = Path(payload["project"])
                self.assertTrue((imported_project / "docs" / "upload.docx").is_file())
                self.assertTrue((imported_project / "locales" / "en-US.json").is_file())
                self.assertEqual(
                    payload["routing"]["adapter_counts"],
                    {"core.json-locale": 1, "core.word-document": 1},
                )
                self.assertEqual(payload["source_files"], ["docs/upload.docx", "locales/en-US.json"])
                home_status, home = _http_get(host, port, "/")
                self.assertEqual(home_status, 200)
                self.assertIn("dropzone", home)
                self.assertNotIn("folderPicker", home)
                self.assertNotIn('accept=".docx', home)
                self.assertIn('onclick="pickProjectDirectory()"', home)
                self.assertIn('postJson("/api/pick-directory", {})', home)
                self.assertNotIn("traverseEntry", home)
                self.assertIn('id="targetLocale" value="zh-CN" list="localeOptions"', home)
                self.assertIn('id="sourceLocale" value="en-US" list="localeOptions"', home)
                self.assertIn('value="th-TH" label="🇹🇭 泰语 · ไทย（泰国）"', home)

                unsafe_status, unsafe = _http_post_json(
                    host,
                    port,
                    "/api/import-files",
                    {"files": [{"relative_path": "../escape.docx", "content_base64": ""}]},
                )
                self.assertEqual(unsafe_status, 400)
                self.assertEqual(unsafe["status"], "fail")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_ui_pick_directory_reads_local_project_without_upload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            _copy_json_fixture_project(project, include_existing_target=False)
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                with mock.patch("runtime.localize_anything.ui._pick_directory", return_value=project.resolve()):
                    status, payload = _http_post_json(host, port, "/api/pick-directory", {})
                self.assertEqual(status, 200)
                self.assertEqual(payload["status"], "pass")
                self.assertEqual(Path(payload["project"]), project.resolve())
                self.assertEqual(payload["routing"]["adapter_counts"], {"core.json-locale": 1})
                self.assertEqual(payload["source_files"], ["locales/en-US.json"])

                with mock.patch("runtime.localize_anything.ui._pick_directory", return_value=None):
                    cancelled_status, cancelled = _http_post_json(host, port, "/api/pick-directory", {})
                self.assertEqual(cancelled_status, 200)
                self.assertEqual(cancelled["status"], "cancelled")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class UnifiedStagingTests(unittest.TestCase):
    def test_stage_generated_routes_multiple_adapters_to_staging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            source_files = [
                "locales/en-US.json",
                "media/captions.en.srt",
                "app/src/main/res/values/strings.xml",
                "ios/App/en.lproj/Localizable.strings",
                "ios/App/Localizable.xcstrings",
            ]
            sources = {
                "locales/en-US.json": FIXTURE_ROOT / "locales" / "en-US.json",
                "media/captions.en.srt": COMMON_FORMATS_ROOT / "captions.srt",
                "app/src/main/res/values/strings.xml": ANDROID_FIXTURE_ROOT / "app" / "src" / "main" / "res" / "values" / "strings.xml",
                "ios/App/en.lproj/Localizable.strings": IOS_FIXTURE_ROOT / "App" / "en.lproj" / "Localizable.strings",
                "ios/App/Localizable.xcstrings": XCSTRINGS_FIXTURE_ROOT / "App" / "Localizable.xcstrings",
            }
            for logical_path, source in sources.items():
                destination = project / logical_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

            generated: list[dict[str, object]] = []
            generated.extend(extract_segments(project / "locales" / "en-US.json", "en-US", "locales/en-US.json"))
            generated.extend(extract_subtitle_segments(project / "media" / "captions.en.srt", "en-US", "media/captions.en.srt"))
            generated.extend(extract_android_segments(project / "app" / "src" / "main" / "res" / "values" / "strings.xml", "en-US", "app/src/main/res/values/strings.xml"))
            generated.extend(extract_ios_segments(project / "ios" / "App" / "en.lproj" / "Localizable.strings", "en-US", "ios/App/en.lproj/Localizable.strings"))
            generated.extend(extract_xcstrings_segments(project / "ios" / "App" / "Localizable.xcstrings", "en-US", "ios/App/Localizable.xcstrings"))
            for segment in generated:
                segment["target_locale"] = "zh-CN"
                segment["target"] = f"[zh-CN] {segment['source']}"
                segment["status"] = "generated"

            result = stage_generated(project, generated, root / "staging", "en-US", "zh-CN", source_files)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["summary"], {"output_count": 5, "source_file_count": 5})
            self.assertEqual(
                [item["destination"] for item in result["outputs"]],
                [
                    "locales/zh-CN.json",
                    "media/captions.zh-CN.srt",
                    "app/src/main/res/values-zh-rCN/strings.xml",
                    "ios/App/zh-Hans.lproj/Localizable.strings",
                    "ios/App/Localizable.xcstrings",
                ],
            )
            self.assertEqual(validate_pair(project / "locales" / "en-US.json", root / "staging" / "locales" / "zh-CN.json")["status"], "pass")
            self.assertEqual(
                validate_subtitle_pair(
                    project / "media" / "captions.en.srt",
                    root / "staging" / "media" / "captions.zh-CN.srt",
                )["status"],
                "pass",
            )
            self.assertEqual(
                validate_android_strings(
                    project / "app" / "src" / "main" / "res" / "values" / "strings.xml",
                    root / "staging" / "app" / "src" / "main" / "res" / "values-zh-rCN" / "strings.xml",
                )["status"],
                "pass",
            )
            self.assertEqual(
                validate_ios_strings(
                    project / "ios" / "App" / "en.lproj" / "Localizable.strings",
                    root / "staging" / "ios" / "App" / "zh-Hans.lproj" / "Localizable.strings",
                )["status"],
                "pass",
            )
            self.assertEqual(
                validate_xcstrings(
                    project / "ios" / "App" / "Localizable.xcstrings",
                    root / "staging" / "ios" / "App" / "Localizable.xcstrings",
                    "zh-CN",
                )["status"],
                "pass",
            )


class IncrementalTests(unittest.TestCase):
    def test_diff_classifies_changed_moved_new_and_deleted(self) -> None:
        previous = [
            {"segment_id": "a", "source_hash": "1"},
            {"segment_id": "b", "source_hash": "2"},
            {"segment_id": "e", "source_hash": "5"},
        ]
        current = [
            {"segment_id": "a", "source_hash": "3"},
            {"segment_id": "c", "source_hash": "2"},
            {"segment_id": "d", "source_hash": "4"},
        ]
        result = diff_segments(previous, current)
        assert_protocol_schema(self, "incremental-diff", result)
        self.assertEqual(result["summary"], {"new": 1, "unchanged": 0, "changed": 1, "moved": 1, "deleted": 1})
        moved = next(item for item in result["segments"] if item["status"] == "moved")
        self.assertEqual(moved["previous_segment_id"], "b")


class DeliveryLifecycleTests(unittest.TestCase):
    def test_package_review_signoff_and_apply_dry_run(self) -> None:
        source = FIXTURE_ROOT / "locales" / "en-US.json"
        expected = FIXTURE_ROOT / "locales" / "zh-CN.json"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            locales = project / "locales"
            locales.mkdir(parents=True)
            (locales / "en-US.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            (locales / "zh-CN.json").write_text("{}\n", encoding="utf-8")
            (project / "voice.ogg").write_bytes(b"audio-placeholder")
            initialized = initialize_project(project, "en-US", ["locales/en-US.json"], ["zh-CN"])
            state = Path(initialized["state_directory"])
            segments = extract_segments(project / "locales" / "en-US.json", "en-US", "locales/en-US.json")
            plan = create_batch_plan(segments, "en-US", ["zh-CN"], 10)
            write_generation_strategy(
                state,
                build_generation_strategy(state, plan, source_locale="en-US", target_locale="zh-CN", run_id="test-run-001"),
            )

            staging = root / "staging"
            staged_target = staging / "locales" / "zh-CN.json"
            staged_target.parent.mkdir(parents=True)
            staged_target.write_text(expected.read_text(encoding="utf-8"), encoding="utf-8")
            qa_path = root / "qa.json"
            agent_qa_path = root / "agent-qa.json"
            write_json(
                qa_path,
                {"protocol_version": "0.1", "status": "pass", "evidence_channels": ["adapter"], "items": []},
            )
            write_json(
                agent_qa_path,
                {"protocol_version": "0.1", "status": "pass", "evidence_channels": ["agent"], "items": []},
            )
            with self.assertRaisesRegex(ValueError, "agent linguistic QA"):
                package_delivery(
                    state,
                    staging,
                    root / "deliveries",
                    [qa_path],
                    "review_ready",
                    "missing-agent-qa",
                )

            packaged = package_delivery(
                state,
                staging,
                root / "deliveries",
                [qa_path, agent_qa_path],
                "review_ready",
                "test-run-001",
            )
            delivery = Path(packaged["delivery_directory"])
            for name in (
                "delivery-manifest.json",
                "localization-context.md",
                "localization-brief.json",
                "localization-brief.yaml",
                "glossary.csv",
                "translation-memory.jsonl",
                "term-registry.csv",
                "forbidden-translations.csv",
                "term-decisions.jsonl",
                "term-conflicts.jsonl",
                "term-provenance.jsonl",
                "generation-strategy.json",
                "qa-report.md",
                "files/locales/zh-CN.json",
            ):
                self.assertTrue((delivery / name).exists(), name)
            self.assertEqual(packaged["manifest"]["delivery_status"], "review_ready")
            self.assertEqual(packaged["manifest"]["assets"]["generation_strategy"], "generation-strategy.json")
            assert_protocol_schema(self, "delivery-manifest", packaged["manifest"])
            self.assertEqual(packaged["manifest"]["unprocessed_non_text_assets"][0]["path"], "voice.ogg")
            self.assertIn("voice.ogg", (delivery / "qa-report.md").read_text(encoding="utf-8"))
            dashboard = build_delivery_dashboard(delivery)
            self.assertEqual(dashboard["summary"]["output_count"], 1)
            self.assertEqual(dashboard["summary"]["qa_status"], "pass")
            self.assertEqual(dashboard["unprocessed_non_text_assets"][0]["path"], "voice.ogg")
            self.assertIn("plan-apply", "\n".join(dashboard["next_actions"]))
            self.assertIn("voice.ogg", render_dashboard_markdown(dashboard))
            with self.assertRaises(ValueError):
                package_delivery(
                    state,
                    staging,
                    root / "deliveries",
                    [qa_path, agent_qa_path],
                    "review_ready",
                    "test-run-001",
                )

            apply_plan = create_apply_plan(delivery, project)
            assert_protocol_schema(self, "apply-plan", apply_plan)
            self.assertEqual(apply_plan["summary"]["replace"], 1)
            self.assertTrue(apply_plan["requires_confirmation"])
            apply_plan_markdown = render_apply_plan_markdown(apply_plan)
            self.assertIn("# Apply Plan", apply_plan_markdown)
            self.assertIn("apply-delivery --confirm-run-id test-run-001", apply_plan_markdown)
            decision = create_delivery_decision_report(delivery, project)
            assert_protocol_schema(self, "delivery-decision", decision)
            self.assertEqual(decision["status"], "owner_review_required")
            self.assertEqual(decision["summary"]["requires_confirmation_count"], 1)
            self.assertEqual(decision["summary"]["requires_review_count"], 1)
            decision_markdown = render_delivery_decision_markdown(decision)
            self.assertIn("Delivery Decision Report", decision_markdown)
            self.assertIn("apply-delivery --confirm-run-id test-run-001", decision_markdown)
            (locales / "zh-CN.json").write_text('{"changed": true}\n', encoding="utf-8")
            conflicted_plan = create_apply_plan(delivery, project)
            self.assertEqual(conflicted_plan["summary"]["conflict"], 1)
            self.assertTrue(conflicted_plan["blocked_by_conflicts"])
            conflicted_decision = create_delivery_decision_report(delivery, project)
            self.assertEqual(conflicted_decision["status"], "blocked")

            acceptance_path = state / "acceptances" / "test-run-001.json"
            acceptance = create_acceptance(
                delivery / "delivery-manifest.json",
                "project-owner",
                {"locales": ["zh-CN"], "files": ["locales/zh-CN.json"]},
                acceptance_path,
            )
            self.assertEqual(acceptance["delivery_status"], "user_accepted")
            assert_protocol_schema(self, "acceptance", acceptance)
            self.assertEqual(len(acceptance["manifest_sha256"]), 64)
            with self.assertRaises(ValueError):
                create_acceptance(
                    delivery / "delivery-manifest.json",
                    "project-owner",
                    {"locales": ["zh-CN"]},
                    acceptance_path,
                )

            generated = extract_segments(source, "en-US", "locales/en-US.json")
            for segment in generated:
                segment["target_locale"] = "zh-CN"
                segment["target"] = "初稿"
                segment["status"] = "generated"
            reviewed = json.loads(json.dumps(generated, ensure_ascii=False))
            reviewed[0]["target"] = "人工审校稿"
            for segment in reviewed:
                segment["status"] = "reviewed"
            generated_path = root / "generated.jsonl"
            reviewed_path = root / "reviewed.jsonl"
            write_jsonl(generated_path, generated)
            write_jsonl(reviewed_path, reviewed)
            review_result = import_review(generated_path, reviewed_path, state, "test-run-001", "zh-CN")
            assert_protocol_schema(self, "review-import", review_result)
            self.assertEqual(len(review_result["changes"]), 1)
            self.assertEqual(review_result["tm_updates"], len(reviewed))
            tm = read_jsonl(state / "translation-memory.jsonl")
            self.assertEqual(len(tm), len(reviewed))
            self.assertTrue(all(item["status"] == "reviewed" for item in tm))

    def test_confirmed_apply_writes_files_and_backups_replacements(self) -> None:
        source = FIXTURE_ROOT / "locales" / "en-US.json"
        expected = FIXTURE_ROOT / "locales" / "zh-CN.json"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            locales = project / "locales"
            locales.mkdir(parents=True)
            (locales / "en-US.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            (locales / "zh-CN.json").write_text('{"old": true}\n', encoding="utf-8")
            initialized = initialize_project(project, "en-US", ["locales/en-US.json"], ["zh-CN"])
            state = Path(initialized["state_directory"])

            staging = root / "staging"
            staged_target = staging / "locales" / "zh-CN.json"
            staged_target.parent.mkdir(parents=True)
            staged_target.write_text(expected.read_text(encoding="utf-8"), encoding="utf-8")
            packaged = package_delivery(state, staging, root / "deliveries", [], "draft_package", "apply-run-001")
            delivery = Path(packaged["delivery_directory"])
            with self.assertRaisesRegex(ValueError, "confirm_run_id"):
                execute_apply(delivery, project, "wrong-run")

            result = execute_apply(delivery, project, "apply-run-001")
            self.assertEqual(result["summary"]["replaced"], 1)
            self.assertEqual(json.loads((locales / "zh-CN.json").read_text(encoding="utf-8")), json.loads(expected.read_text(encoding="utf-8")))
            backup = project / ".localize-anything" / "backups" / "apply-run-001" / "locales" / "zh-CN.json"
            self.assertEqual(backup.read_text(encoding="utf-8"), '{"old": true}\n')

    def test_android_overlay_apply_requires_clean_git_tree_and_locale_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True, text=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=project, check=True)
            source_file = project / "app" / "src" / "main" / "res" / "values" / "strings.xml"
            source_file.parent.mkdir(parents=True)
            source_file.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">Sample</string>
</resources>
""",
                encoding="utf-8",
            )
            initialized = initialize_project(project, "en-US", ["app/src/main/res/values/strings.xml"], ["th"])
            state = Path(initialized["state_directory"])
            subprocess.run(["git", "add", "."], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=project, check=True, capture_output=True, text=True)

            staging = root / "staging"
            overlay = staging / "app" / "src" / "main" / "res" / "values-th" / "localize_anything_overlay.xml"
            overlay.parent.mkdir(parents=True)
            overlay.write_text(
                """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="files_tab">ไฟล์</string>
</resources>
""",
                encoding="utf-8",
            )
            packaged = package_delivery(
                state,
                staging,
                root / "deliveries",
                [],
                "draft_package",
                "overlay-apply-001",
                {
                    "app/src/main/res/values-th/localize_anything_overlay.xml": {
                        "source_category": "merged_dependency_overlay",
                        "apply_safety": {
                            "requires_explicit_run_id": True,
                            "requires_clean_git_tree": True,
                            "destination_policy": "android_target_locale_resource_file",
                        },
                    }
                },
            )
            delivery = Path(packaged["delivery_directory"])
            subprocess.run(["git", "add", "."], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "package overlay"], cwd=project, check=True, capture_output=True, text=True)
            dirty_file = project / "README.md"
            dirty_file.write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "clean git tree"):
                execute_apply(delivery, project, "overlay-apply-001")
            dirty_file.unlink()

            result = execute_apply(delivery, project, "overlay-apply-001")
            self.assertEqual(result["summary"]["created"], 1)
            written = project / "app" / "src" / "main" / "res" / "values-th" / "localize_anything_overlay.xml"
            self.assertTrue(written.is_file())
            self.assertIn("values-th/localize_anything_overlay.xml", result["post_apply_git_diff"])

            unsafe_staging = root / "unsafe-staging"
            unsafe = unsafe_staging / "app" / "src" / "main" / "res" / "values" / "localize_anything_overlay.xml"
            unsafe.parent.mkdir(parents=True)
            unsafe.write_text(overlay.read_text(encoding="utf-8"), encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "apply overlay"], cwd=project, check=True, capture_output=True, text=True)
            unsafe_packaged = package_delivery(
                state,
                unsafe_staging,
                root / "unsafe-deliveries",
                [],
                "draft_package",
                "unsafe-overlay-apply-001",
                {
                    "app/src/main/res/values/localize_anything_overlay.xml": {
                        "source_category": "merged_dependency_overlay",
                        "apply_safety": {"requires_explicit_run_id": True},
                    }
                },
            )
            subprocess.run(["git", "add", "."], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "package unsafe overlay"], cwd=project, check=True, capture_output=True, text=True)
            with self.assertRaisesRegex(ValueError, "locale values directory"):
                execute_apply(Path(unsafe_packaged["delivery_directory"]), project, "unsafe-overlay-apply-001")


class TermbasePreflightTests(unittest.TestCase):
    def test_candidate_term_extraction_and_queue_report(self) -> None:
        segments = _termbase_segments()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            result = run_termbase_preflight(state, segments, source_locale="en-US", target_locale="zh-CN", run_id="terms-001")

            self.assertEqual(result["status"], "review_required")
            self.assertEqual(result["terminology_assurance"], "incomplete_review_required")
            candidates = read_jsonl(state / "candidate-terms.jsonl")
            queue = read_json(state / "term-review-queue.json")
            report = read_json(state / "termbase-preflight-report.json")
            self.assertTrue((state / "term-review-decisions.jsonl").is_file())
            assert_protocol_schema(self, "candidate-term", candidates[0])
            assert_protocol_schema(self, "term-review-queue", queue)
            assert_protocol_schema(self, "termbase-preflight-report", report)

            by_term = {item["source_term"]: item for item in candidates}
            self.assertIn("Delete account", by_term)
            self.assertEqual(by_term["Delete account"]["status"], "needs_review")
            self.assertEqual(by_term["Delete account"]["term_type"], "ui_term")
            self.assertGreaterEqual(by_term["Delete account"]["occurrence_count"], 2)
            self.assertIn("SSO", by_term)
            self.assertIn("NASA", by_term)
            self.assertIn("National award certification improves trust", by_term)
            self.assertGreaterEqual(queue["summary"]["high_risk_unreviewed_count"], 1)
            self.assertEqual(report["terminology_assurance"], "incomplete_review_required")
            self.assertIn("Delete account", {item["source_term"] for item in report["unreviewed_high_risk_terms"]})

    def test_existing_term_registry_match_marks_approved(self) -> None:
        segments = [_segment("s1", "Enable SSO for sign in")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            state.mkdir()
            _write_term_registry(
                state,
                [
                    {
                        "source_term": "SSO",
                        "target_term": "单点登录",
                        "type": "domain_term",
                        "status": "approved",
                        "priority": "user_confirmed",
                        "target_locale": "zh-CN",
                    }
                ],
            )

            run_termbase_preflight(state, segments, source_locale="en-US", target_locale="zh-CN")
            candidates = {item["source_term"]: item for item in read_jsonl(state / "candidate-terms.jsonl")}

            self.assertEqual(candidates["SSO"]["status"], "approved")
            self.assertEqual(candidates["SSO"]["target_term"], "单点登录")
            self.assertEqual(candidates["SSO"]["matches"]["term_registry"][0]["status"], "approved")

    def test_forbidden_translation_match_is_visible(self) -> None:
        segments = [_segment("s1", "Delete account")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            state.mkdir()
            _write_forbidden_translations(
                state,
                [
                    {
                        "source_term": "Delete account",
                        "forbidden_target": "删除账号",
                        "target_locale": "zh-CN",
                        "reason": "too blunt for product policy",
                        "status": "approved",
                    }
                ],
            )

            run_termbase_preflight(state, segments, source_locale="en-US", target_locale="zh-CN")
            candidates = {item["source_term"]: item for item in read_jsonl(state / "candidate-terms.jsonl")}

            self.assertEqual(candidates["Delete account"]["status"], "forbidden")
            self.assertEqual(candidates["Delete account"]["matches"]["forbidden_translations"][0]["forbidden_target"], "删除账号")

    def test_simple_conflict_detection_blocks_assurance(self) -> None:
        segments = [_segment("s1", "API access")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            state.mkdir()
            _write_term_registry(
                state,
                [
                    {
                        "source_term": "API",
                        "target_term": "接口",
                        "type": "domain_term",
                        "status": "approved",
                        "priority": "user_confirmed",
                        "target_locale": "zh-CN",
                    },
                    {
                        "source_term": "API",
                        "target_term": "应用程序接口",
                        "type": "domain_term",
                        "status": "locked",
                        "priority": "user_confirmed",
                        "target_locale": "zh-CN",
                    },
                ],
            )
            _write_forbidden_translations(
                state,
                [
                    {
                        "source_term": "API",
                        "forbidden_target": "接口",
                        "target_locale": "zh-CN",
                        "reason": "ambiguous",
                        "status": "approved",
                    }
                ],
            )

            run_termbase_preflight(state, segments, source_locale="en-US", target_locale="zh-CN")
            queue = read_json(state / "term-review-queue.json")
            report = read_json(state / "termbase-preflight-report.json")

            self.assertEqual(queue["status"], "blocked_by_conflict")
            self.assertEqual(report["terminology_assurance"], "blocked_by_conflict")
            conflict_types = {item["type"] for item in report["conflicts"]}
            self.assertIn("multiple_approved_targets", conflict_types)
            self.assertIn("approved_target_is_forbidden", conflict_types)

    def test_user_decision_updates_governance_and_work_packet_constraints(self) -> None:
        segments = [_segment("s1", "Enable SSO login")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / ".localize-anything"
            run_termbase_preflight(state, segments, source_locale="en-US", target_locale="zh-CN")
            queue = read_json(state / "term-review-queue.json")
            candidate_id = next(item["candidate_id"] for item in queue["terms"] if item["source_term"] == "SSO")

            result = record_term_review_decision(
                state,
                {
                    "candidate_id": candidate_id,
                    "target_term": "单点登录",
                    "status": "locked",
                    "notes": "Use the established product term.",
                    "forbidden_targets": ["SSO"],
                    "decided_by": "tester",
                },
            )

            self.assertEqual(result["queue"]["terms"][0]["status"], "locked")
            review_decisions = read_jsonl(state / "term-review-decisions.jsonl")
            assert_protocol_schema(self, "term-review-decision", review_decisions[0])
            term_constraints = select_term_constraints(state, segments, "zh-CN", "style_only")
            self.assertEqual(term_constraints["term_registry"][0]["source_term"], "SSO")
            self.assertEqual(term_constraints["term_registry"][0]["target_term"], "单点登录")
            self.assertEqual(term_constraints["forbidden_translations"][0]["forbidden_target"], "SSO")

            plan = create_batch_plan(segments, "en-US", ["zh-CN"], 10)
            packet = build_work_packet(plan, "batch-0001", segments, state, "zh-CN")
            self.assertEqual(packet["memory"]["hard_constraints"]["term_registry"][0]["source_term"], "SSO")
            self.assertEqual(packet["memory"]["terminology_review"]["terminology_assurance"], "reviewed")

    def test_unreviewed_terms_downgrade_work_packet_terminology_assurance(self) -> None:
        segments = [_segment("s1", "Delete account", high_risk=True)]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            run_termbase_preflight(state, segments, source_locale="en-US", target_locale="zh-CN")

            plan = create_batch_plan(segments, "en-US", ["zh-CN"], 10)
            packet = build_work_packet(plan, "batch-0001", segments, state, "zh-CN")

            self.assertEqual(packet["memory"]["terminology_review"]["terminology_assurance"], "incomplete_review_required")
            self.assertEqual(packet["memory"]["terminology_review"]["unreviewed_high_risk_terms"][0]["source_term"], "Delete account")

    def test_workbench_api_reads_queue_and_records_decision(self) -> None:
        segments = [_segment("s1", "Enable SSO login")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            run_termbase_preflight(state, segments, source_locale="en-US", target_locale="zh-CN")
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                queue_status, queue_payload = _http_post_json(
                    host,
                    port,
                    "/api/term-review-queue",
                    {"state_dir": state.as_posix()},
                )
                self.assertEqual(queue_status, 200)
                queue = queue_payload["term_review_queue"]
                candidate_id = next(item["candidate_id"] for item in queue["terms"] if item["source_term"] == "SSO")

                decision_status, decision_payload = _http_post_json(
                    host,
                    port,
                    "/api/term-review-decision",
                    {
                        "state_dir": state.as_posix(),
                        "decision": {
                            "candidate_id": candidate_id,
                            "target_term": "单点登录",
                            "status": "approved",
                            "decided_by": "tester",
                        },
                    },
                )
                self.assertEqual(decision_status, 200)
                self.assertEqual(decision_payload["result"]["report"]["terminology_assurance"], "reviewed")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class GenerationStrategyGateTests(unittest.TestCase):
    def test_generation_strategy_blocks_conflicted_terms_and_marks_draft_request(self) -> None:
        segments = [_segment("s1", "API access")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            state.mkdir()
            _write_term_registry(
                state,
                [
                    {
                        "source_term": "API",
                        "target_term": "接口",
                        "type": "domain_term",
                        "status": "approved",
                        "priority": "user_confirmed",
                        "target_locale": "zh-CN",
                    },
                    {
                        "source_term": "API",
                        "target_term": "应用程序接口",
                        "type": "domain_term",
                        "status": "locked",
                        "priority": "user_confirmed",
                        "target_locale": "zh-CN",
                    },
                ],
            )
            run_termbase_preflight(state, segments, source_locale="en-US", target_locale="zh-CN", run_id="strategy-001")
            plan = create_batch_plan(segments, "en-US", ["zh-CN"], 10)

            strategy = write_generation_strategy(
                state,
                build_generation_strategy(state, plan, source_locale="en-US", target_locale="zh-CN", run_id="strategy-001"),
            )

            assert_protocol_schema(self, "generation-strategy", strategy)
            self.assertEqual(strategy["status"], "blocked")
            self.assertFalse(strategy["work_packet_policy"]["allow_generation"])
            self.assertEqual(strategy["route"]["mode"], "blocked")
            self.assertIn("term_conflict", strategy["work_packet_policy"]["blocked_reason_codes"])

            packet = build_work_packet(plan, "batch-0001", segments, state, "zh-CN")
            self.assertFalse(packet["memory"]["generation_strategy"]["allow_generation"])
            draft_request = create_draft_request(packet)
            self.assertIn("Generation Strategy Gate is blocked", "\n".join(draft_request["instructions"]))

    def test_generation_strategy_review_required_routes_high_assurance_handoff(self) -> None:
        segments = [_segment("s1", "Delete account", high_risk=True)]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            run_termbase_preflight(state, segments, source_locale="en-US", target_locale="zh-CN", run_id="strategy-002")
            plan = create_batch_plan(segments, "en-US", ["zh-CN"], 10)

            strategy = write_generation_strategy(
                state,
                build_generation_strategy(state, plan, source_locale="en-US", target_locale="zh-CN", run_id="strategy-002"),
            )

            self.assertEqual(strategy["status"], "review_required")
            self.assertTrue(strategy["work_packet_policy"]["allow_generation"])
            self.assertEqual(strategy["route"]["mode"], "high_assurance_handoff")
            self.assertIn("unreviewed_high_risk_terms", strategy["work_packet_policy"]["warning_codes"])

            packet = build_work_packet(plan, "batch-0001", segments, state, "zh-CN")
            draft_request = create_draft_request(packet)
            self.assertIn("Generation Strategy Gate requires review", "\n".join(draft_request["instructions"]))

    def test_workbench_api_reads_generation_strategy(self) -> None:
        segments = [_segment("s1", "Delete account", high_risk=True)]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            run_termbase_preflight(state, segments, source_locale="en-US", target_locale="zh-CN")
            plan = create_batch_plan(segments, "en-US", ["zh-CN"], 10)
            write_generation_strategy(
                state,
                build_generation_strategy(state, plan, source_locale="en-US", target_locale="zh-CN"),
            )
            self.assertEqual(read_generation_strategy(state)["status"], "review_required")
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                status, payload = _http_post_json(
                    host,
                    port,
                    "/api/generation-strategy",
                    {"state_dir": state.as_posix()},
                )
                self.assertEqual(status, 200)
                self.assertEqual(payload["generation_strategy"]["status"], "review_required")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_cli_generation_strategy_writes_artifact(self) -> None:
        segments = [_segment("s1", "Delete account", high_risk=True)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / ".localize-anything"
            run_termbase_preflight(state, segments, source_locale="en-US", target_locale="zh-CN")
            plan = create_batch_plan(segments, "en-US", ["zh-CN"], 10)
            plan_path = root / "batch-plan.json"
            output = root / "strategy-output.json"
            write_json(plan_path, plan)

            exit_code = cli_main(
                [
                    "generation-strategy",
                    plan_path.as_posix(),
                    state.as_posix(),
                    "--target-locale",
                    "zh-CN",
                    "--output",
                    output.as_posix(),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(read_json(output)["status"], "review_required")
            self.assertEqual(read_json(state / "generation-strategy.json")["status"], "review_required")

    def test_localize_run_blocks_handoff_on_generation_strategy_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            locale_dir = project / "locales"
            locale_dir.mkdir(parents=True)
            (locale_dir / "en-US.json").write_text(json.dumps({"api": "API access"}), encoding="utf-8")
            state = project / ".localize-anything"
            _write_term_registry(
                state,
                [
                    {
                        "source_term": "API",
                        "target_term": "接口",
                        "type": "domain_term",
                        "status": "approved",
                        "priority": "user_confirmed",
                        "target_locale": "zh-CN",
                    },
                    {
                        "source_term": "API",
                        "target_term": "应用程序接口",
                        "type": "domain_term",
                        "status": "locked",
                        "priority": "user_confirmed",
                        "target_locale": "zh-CN",
                    },
                ],
            )

            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                source_files=["locales/en-US.json"],
                output_root=root / "runs",
                run_id="blocked-strategy-001",
                handoff_only=True,
            )

            self.assertEqual(result["status"], "generation_strategy_blocked")
            self.assertEqual(result["generation"]["status"], "blocked")
            self.assertEqual(result["generation"]["strategy"]["status"], "blocked")
            self.assertEqual(result["generation"]["strategy"]["route"]["mode"], "blocked")
            self.assertTrue((state / "generation-strategy.json").is_file())
            self.assertEqual(read_json(Path(result["artifacts"]["generation_handoff"]))["request_count"], 0)
            self.assertEqual(list(Path(result["artifacts"]["work_packets"]).glob("*.json")), [])


class ResolutionGateTests(unittest.TestCase):
    def test_unresolved_term_conflicts_create_blocking_questions(self) -> None:
        segments = [_segment("s1", "API access")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            state.mkdir()
            _write_term_registry(
                state,
                [
                    {"source_term": "API", "target_term": "接口", "type": "domain_term", "status": "approved", "target_locale": "zh-CN"},
                    {"source_term": "API", "target_term": "应用程序接口", "type": "domain_term", "status": "locked", "target_locale": "zh-CN"},
                ],
            )
            strategy = _write_strategy_for_segments(state, segments)

            questions = build_resolution_gate(state, strategy)

            assert_protocol_schema(self, "blocking-questions", questions)
            self.assertEqual(questions["status"], "blocked")
            question = questions["questions"][0]
            self.assertEqual(question["reason_code"], "term_conflict")
            self.assertEqual(question["severity"], "blocking")
            self.assertIn("keep_blocked", question["available_options"])
            self.assertTrue((state / "resolution-options.json").is_file())
            self.assertTrue((state / "user-resolution-decisions.jsonl").is_file())

    def test_high_risk_unreviewed_terms_create_review_questions(self) -> None:
        segments = [_segment("s1", "Delete account", high_risk=True)]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)

            questions = build_resolution_gate(state, strategy)

            self.assertEqual(questions["status"], "review_required")
            question = next(item for item in questions["questions"] if item["reason_code"] == "unreviewed_high_risk_terms")
            self.assertEqual(question["severity"], "review_required")
            self.assertEqual(question["responsible_owner_type"], "terminology_owner")
            self.assertEqual(question["affected_terms"][0]["source_term"], "Delete account")

    def test_incomplete_terminology_assurance_stays_downgraded(self) -> None:
        segments = [_segment("s1", "Start game"), _segment("s2", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)

            questions = build_resolution_gate(state, strategy)
            packet = build_work_packet(create_batch_plan(segments, "en-US", ["zh-CN"], 10), "batch-0001", segments, state, "zh-CN")
            draft_request = create_draft_request(packet)

            self.assertEqual(strategy["generation_readiness"], "review_required")
            self.assertIn("term_review_incomplete", {item["reason_code"] for item in questions["questions"]})
            self.assertEqual(packet["memory"]["resolution_gate"]["status"], "review_required")
            self.assertIn("Resolution Gate has unresolved questions", "\n".join(draft_request["instructions"]))

    def test_partial_coverage_without_allowance_creates_warning_question(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)

            questions = build_resolution_gate(
                state,
                strategy,
                context={"android_coverage": {"visible_ui_coverage_warning": True, "merged_dependency_strings_detected": 8}},
            )

            question = next(item for item in questions["questions"] if item["reason_code"] == "partial_source_coverage")
            self.assertEqual(question["severity"], "warning")
            self.assertIn("allow_partial_coverage", question["available_options"])

    def test_unsafe_provider_fallback_creates_blocker(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)

            questions = build_resolution_gate(
                state,
                strategy,
                context={"provider_policy": {"mode": "real_provider", "fallback_requested": True}},
            )

            question = next(item for item in questions["questions"] if item["reason_code"] == "provider_fallback_requested")
            self.assertEqual(question["severity"], "blocking")
            self.assertEqual(question["recommended_default"], "block_provider_until_safe")
            self.assertEqual(question["available_options"], ["block_provider_until_safe"])
            with self.assertRaisesRegex(ValueError, "not available"):
                record_user_resolution_decision(
                    state,
                    {
                        "question_id": question["question_id"],
                        "option_id": "continue_only_draft_review",
                        "decided_by": "tester",
                    },
                )
            questions["questions"][0]["available_options"].append("continue_only_draft_review")
            write_json(state / "blocking-questions.json", questions)
            with self.assertRaisesRegex(ValueError, "Unsafe provider fallback"):
                record_user_resolution_decision(
                    state,
                    {
                        "question_id": question["question_id"],
                        "option_id": "continue_only_draft_review",
                        "decided_by": "tester",
                    },
                )
            decision = record_user_resolution_decision(
                state,
                {
                    "question_id": question["question_id"],
                    "option_id": "block_provider_until_safe",
                    "decided_by": "tester",
                },
            )["decision"]
            updated_strategy = read_json(state / "generation-strategy.json")
            self.assertEqual(decision["reason_code"], "provider_fallback_requested")
            self.assertFalse(updated_strategy["resolution_state"]["provider_policy"]["provider_backed_generation_allowed"])
            self.assertFalse(updated_strategy["resolution_state"]["provider_policy"]["unsafe_provider_fallback_allowed"])
            self.assertFalse(updated_strategy["work_packet_policy"]["allow_generation"])
            self.assertEqual(updated_strategy["generation_readiness"], "blocked")

    def test_unknown_mode_and_scenario_create_resolution_questions(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)

            questions = build_resolution_gate(state, strategy, context={"operating_mode": "mystery_mode", "scenario": "unknown"})

            reason_codes = {item["reason_code"] for item in questions["questions"]}
            self.assertIn("unknown_operating_mode", reason_codes)
            self.assertIn("unknown_scenario", reason_codes)

    def test_recording_term_approval_feeds_governance(self) -> None:
        segments = [_segment("s1", "Enable SSO login")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            questions = build_resolution_gate(state, strategy)
            question = next(item for item in questions["questions"] if item["reason_code"] == "term_review_incomplete")
            # Use a concrete term question from the queue to exercise term governance updates.
            queue = read_json(state / "term-review-queue.json")
            candidate_id = next(item["candidate_id"] for item in queue["terms"] if item["source_term"] == "SSO")
            term_question = {
                **question,
                "question_id": "bq-term-approval-test",
                "reason_code": "unreviewed_high_risk_terms",
                "affected_terms": [{"candidate_id": candidate_id, "source_term": "SSO", "target_locale": "zh-CN", "term_type": "project"}],
                "available_options": ["approve_term"],
                "recommended_default": "approve_term",
            }
            questions["questions"].append(term_question)
            write_json(state / "blocking-questions.json", questions)

            result = record_user_resolution_decision(
                state,
                {
                    "question_id": "bq-term-approval-test",
                    "option_id": "approve_term",
                    "target_term": "单点登录",
                    "decided_by": "tester",
                },
            )

            assert_protocol_schema(self, "user-resolution-decision", result["decision"])
            constraints = select_term_constraints(state, segments, "zh-CN", "style_only")
            self.assertEqual(constraints["term_registry"][0]["source_term"], "SSO")
            self.assertEqual(constraints["term_registry"][0]["target_term"], "单点登录")

    def test_allowing_partial_coverage_updates_decision_state_without_full_coverage_claim(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            questions = build_resolution_gate(
                state,
                strategy,
                context={"android_coverage": {"visible_ui_coverage_warning": True}},
            )
            question_id = next(item["question_id"] for item in questions["questions"] if item["reason_code"] == "partial_source_coverage")

            record_user_resolution_decision(
                state,
                {"question_id": question_id, "option_id": "allow_partial_coverage", "decided_by": "tester"},
            )

            updated_strategy = read_json(state / "generation-strategy.json")
            coverage = updated_strategy["resolution_state"]["coverage_policy"]
            self.assertTrue(coverage["partial_coverage_allowed"])
            self.assertFalse(coverage["full_coverage_claim"])
            self.assertNotEqual(updated_strategy["generation_readiness"], "ready")

    def test_run_summary_surfaces_unresolved_blocking_questions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            locale_dir = project / "locales"
            locale_dir.mkdir(parents=True)
            (locale_dir / "en-US.json").write_text(json.dumps({"api": "API access"}), encoding="utf-8")
            _write_term_registry(
                project / ".localize-anything",
                [
                    {"source_term": "API", "target_term": "接口", "type": "domain_term", "status": "approved", "target_locale": "zh-CN"},
                    {"source_term": "API", "target_term": "应用程序接口", "type": "domain_term", "status": "locked", "target_locale": "zh-CN"},
                ],
            )

            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                source_files=["locales/en-US.json"],
                output_root=root / "runs",
                run_id="resolution-blocked-001",
                handoff_only=True,
            )

            self.assertEqual(result["status"], "generation_strategy_blocked")
            self.assertEqual(result["resolution"]["status"], "blocked")
            self.assertGreater(result["summary"]["unresolved_blocking_questions"], 0)
            self.assertEqual(read_json(Path(result["artifacts"]["generation_handoff"]))["request_count"], 0)

    def test_resolved_questions_are_included_in_delivery_package(self) -> None:
        source = FIXTURE_ROOT / "locales" / "en-US.json"
        expected = FIXTURE_ROOT / "locales" / "zh-CN.json"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            locale_dir = project / "locales"
            locale_dir.mkdir(parents=True)
            (locale_dir / "en-US.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            initialized = initialize_project(project, "en-US", ["locales/en-US.json"], ["zh-CN"])
            state = Path(initialized["state_directory"])
            segments = extract_segments(project / "locales" / "en-US.json", "en-US", "locales/en-US.json")
            strategy = _write_strategy_for_segments(state, segments)
            questions = build_resolution_gate(state, strategy, context={"android_coverage": {"visible_ui_coverage_warning": True}})
            question_id = next(item["question_id"] for item in questions["questions"] if item["reason_code"] == "partial_source_coverage")
            record_user_resolution_decision(state, {"question_id": question_id, "option_id": "allow_partial_coverage"})

            staging = root / "staging"
            target = staging / "locales" / "zh-CN.json"
            target.parent.mkdir(parents=True)
            target.write_text(expected.read_text(encoding="utf-8"), encoding="utf-8")
            qa_path = root / "qa.json"
            agent_qa_path = root / "agent-qa.json"
            write_json(qa_path, {"protocol_version": "0.1", "status": "pass", "evidence_channels": ["adapter"], "items": []})
            write_json(agent_qa_path, {"protocol_version": "0.1", "status": "pass", "evidence_channels": ["agent"], "items": []})

            packaged = package_delivery(state, staging, root / "deliveries", [qa_path, agent_qa_path], "review_ready", "resolution-delivery-001")
            delivery = Path(packaged["delivery_directory"])

            self.assertTrue((delivery / "blocking-questions.json").is_file())
            self.assertTrue((delivery / "user-resolution-decisions.jsonl").is_file())
            self.assertEqual(packaged["manifest"]["assets"]["blocking_questions"], "blocking-questions.json")

    def test_workbench_api_reads_and_writes_resolution_artifacts(self) -> None:
        segments = [_segment("s1", "Delete account", high_risk=True)]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            questions = build_resolution_gate(state, strategy)
            question_id = next(item["question_id"] for item in questions["questions"] if item["reason_code"] == "unreviewed_high_risk_terms")
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                status, body = _http_get(host, port, f"/api/blocking-questions?state_dir={state.as_posix()}")
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["blocking_questions"]["status"], "review_required")
                status, body = _http_get(host, port, f"/api/resolution-options?state_dir={state.as_posix()}")
                self.assertEqual(status, 200)
                self.assertTrue(json.loads(body)["resolution_options"]["options"])
                decision_status, payload = _http_post_json(
                    host,
                    port,
                    "/api/user-resolution-decision",
                    {
                        "state_dir": state.as_posix(),
                        "decision": {
                            "question_id": question_id,
                            "option_id": "defer_term_continue_downgraded",
                            "decided_by": "tester",
                        },
                    },
                )
                self.assertEqual(decision_status, 200)
                self.assertEqual(payload["result"]["decision"]["option_id"], "defer_term_continue_downgraded")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_cli_blocking_questions_and_resolve_question(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / ".localize-anything"
            _write_strategy_for_segments(state, segments)
            questions_output = root / "questions.json"
            decision_output = root / "decision.json"

            exit_code = cli_main(
                [
                    "blocking-questions",
                    state.as_posix(),
                    "--coverage-warning",
                    "--output",
                    questions_output.as_posix(),
                ]
            )
            self.assertEqual(exit_code, 0)
            question_id = next(
                item["question_id"]
                for item in read_json(questions_output)["questions"]
                if item["reason_code"] == "partial_source_coverage"
            )

            exit_code = cli_main(
                [
                    "resolve-question",
                    state.as_posix(),
                    "--question-id",
                    question_id,
                    "--option-id",
                    "allow_partial_coverage",
                    "--output",
                    decision_output.as_posix(),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(read_json(decision_output)["decision"]["option_id"], "allow_partial_coverage")


class GenerationHandoffEnforcementTests(unittest.TestCase):
    def test_blocked_strategy_prevents_full_quality_handoff(self) -> None:
        segments = [_segment("s1", "API access")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_term_registry(
                state,
                [
                    {"source_term": "API", "target_term": "接口", "type": "domain_term", "status": "approved", "target_locale": "zh-CN"},
                    {"source_term": "API", "target_term": "应用程序接口", "type": "domain_term", "status": "locked", "target_locale": "zh-CN"},
                ],
            )
            strategy = _write_strategy_for_segments(state, segments)
            build_resolution_gate(state, strategy)

            decision = build_generation_handoff_decision(state)

            assert_protocol_schema(self, "generation-handoff-decision", decision)
            self.assertEqual(decision["status"], "blocked")
            self.assertFalse(decision["full_quality_handoff_allowed"])
            self.assertFalse(decision["handoff_allowed"])
            self.assertIn("generation_strategy_blocked", {item["code"] for item in decision["blockers"]})

    def test_allow_generation_false_prevents_handoff(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            strategy["work_packet_policy"]["allow_generation"] = False
            write_json(state / "generation-strategy.json", strategy)
            build_resolution_gate(state, strategy)

            decision = build_generation_handoff_decision(state)

            self.assertEqual(decision["status"], "blocked")
            self.assertIn("allow_generation_false", {item["code"] for item in decision["blockers"]})

    def test_unresolved_blocking_questions_prevent_full_quality_handoff(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            build_resolution_gate(state, strategy, context={"provider_policy": {"mode": "real_provider", "fallback_requested": True}})

            decision = build_generation_handoff_decision(
                state,
                provider_policy={"mode": "real_provider", "provider_controlled": True, "status": "safe", "fallback_requested": True},
            )

            self.assertEqual(decision["status"], "blocked")
            self.assertFalse(decision["handoff_allowed"])
            self.assertIn("provider_fallback_requested", {item["reason_code"] for item in decision["unresolved_questions"]})

    def test_resolved_questions_allow_only_decision_effects(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            questions = build_resolution_gate(
                state,
                strategy,
                context={"android_coverage": {"visible_ui_coverage_warning": True}},
            )
            question_id = next(item["question_id"] for item in questions["questions"] if item["reason_code"] == "partial_source_coverage")
            record_user_resolution_decision(state, {"question_id": question_id, "option_id": "allow_partial_coverage", "decided_by": "tester"})

            decision = build_generation_handoff_decision(state, coverage_policy={"visible_ui_coverage_warning": True})

            self.assertTrue(decision["handoff_allowed"])
            self.assertFalse(decision["full_quality_handoff_allowed"])
            self.assertEqual(decision["handoff_mode"], "source_only_with_partial_coverage_warning")
            self.assertEqual(decision["continuation_decisions"][0]["option_id"], "allow_partial_coverage")
            self.assertIn("full_source_coverage", decision["forbidden_quality_claims"])

    def test_high_risk_unreviewed_terms_force_review_required_handoff(self) -> None:
        segments = [_segment("s1", "Delete account", high_risk=True)]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            build_resolution_gate(state, strategy)

            decision = build_generation_handoff_decision(state)

            self.assertTrue(decision["handoff_allowed"])
            self.assertFalse(decision["full_quality_handoff_allowed"])
            self.assertEqual(decision["handoff_mode"], "review_required")
            self.assertIn("high_risk_unreviewed_terms", {item["code"] for item in decision["warnings"]})
            self.assertIn("full_terminology_assurance", decision["forbidden_quality_claims"])

    def test_partial_coverage_without_allowance_downgrades_handoff(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            build_resolution_gate(state, strategy, context={"android_coverage": {"visible_ui_coverage_warning": True}})

            decision = build_generation_handoff_decision(state, coverage_policy={"visible_ui_coverage_warning": True})

            self.assertTrue(decision["handoff_allowed"])
            self.assertFalse(decision["full_quality_handoff_allowed"])
            self.assertEqual(decision["handoff_mode"], "source_only_with_partial_coverage_warning")
            self.assertIn("partial_source_coverage_unaccepted", {item["code"] for item in decision["warnings"]})
            self.assertIn("full_source_coverage", decision["forbidden_quality_claims"])

    def test_partial_coverage_with_allowance_warns_without_full_coverage_claim(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            questions = build_resolution_gate(state, strategy, context={"android_coverage": {"visible_ui_coverage_warning": True}})
            question_id = next(item["question_id"] for item in questions["questions"] if item["reason_code"] == "partial_source_coverage")
            record_user_resolution_decision(state, {"question_id": question_id, "option_id": "allow_partial_coverage", "decided_by": "tester"})

            decision = build_generation_handoff_decision(state, coverage_policy={"visible_ui_coverage_warning": True})

            self.assertTrue(decision["handoff_allowed"])
            self.assertEqual(decision["delivery_policy"], "warn")
            self.assertIn("partial_source_coverage_allowed", {item["code"] for item in decision["warnings"]})
            self.assertIn("full_source_coverage", decision["forbidden_quality_claims"])

    def test_unsafe_provider_fallback_blocks_real_provider_handoff(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            build_resolution_gate(state, strategy)

            decision = build_generation_handoff_decision(
                state,
                provider_policy={"mode": "real_provider", "provider_controlled": True, "status": "safe", "fallback_requested": True},
            )
            blocked = generate_handoff_with_http_provider({}, "http://127.0.0.1:9/generate", handoff_decision=decision)

            self.assertEqual(decision["status"], "blocked")
            self.assertIn("provider_fallback_requested", {item["code"] for item in decision["blockers"]})
            self.assertEqual(blocked["status"], "fail")
            self.assertEqual(blocked["items"][0]["category"], "generation_handoff_blocked")

    def test_provider_controlled_handoff_requires_safe_provider_policy(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            build_resolution_gate(state, strategy)

            missing = build_generation_handoff_decision(
                state,
                provider_policy={"mode": "real_provider", "provider_controlled": True},
            )

            self.assertEqual(missing["status"], "blocked")
            self.assertIn("provider_policy_missing", {item["code"] for item in missing["blockers"]})

    def test_unsafe_provider_fallback_cannot_be_overridden_by_ordinary_decision(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            build_resolution_gate(state, strategy)
            write_jsonl(
                state / "user-resolution-decisions.jsonl",
                [
                    {
                        "decision_id": "bad-provider-override",
                        "question_id": "bq-provider",
                        "option_id": "continue_only_draft_review",
                        "status": "accepted",
                        "reason_code": "provider_fallback_requested",
                    }
                ],
            )

            decision = build_generation_handoff_decision(state, provider_policy={"mode": "real_provider", "provider_controlled": True, "status": "safe"})

            self.assertEqual(decision["status"], "blocked")
            self.assertIn("non_overridable_safety_override", {item["code"] for item in decision["blockers"]})

    def test_synthetic_fallback_is_allowed_only_in_explicit_synthetic_test_mode(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            build_resolution_gate(state, strategy)

            real_provider = build_generation_handoff_decision(
                state,
                provider_policy={"mode": "real_provider", "provider_controlled": True, "status": "safe", "fallback_requested": True},
            )
            synthetic = build_generation_handoff_decision(
                state,
                requested_mode="synthetic_test",
                provider_policy={"mode": "synthetic_test", "fallback_requested": True},
            )

            self.assertEqual(real_provider["status"], "blocked")
            self.assertTrue(synthetic["handoff_allowed"])
            self.assertEqual(synthetic["handoff_mode"], "synthetic_test")
            self.assertFalse(synthetic["provider_backed_generation_allowed"])
            self.assertIn("provider_backed_quality", synthetic["forbidden_quality_claims"])

    def test_downgraded_handoff_appears_in_run_summary_and_delivery_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            locales = project / "locales"
            locales.mkdir(parents=True)
            (locales / "en-US.json").write_text(json.dumps({"delete": "Delete account"}), encoding="utf-8")

            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                source_files=["locales/en-US.json"],
                output_root=root / "out",
                run_id="handoff-decision-delivery-001",
                max_segments=10,
                synthetic_draft=True,
            )

            self.assertIn("generation_handoff_decision", result["artifacts"])
            self.assertIn("full_quality_generation", result["generation"]["handoff_decision"]["forbidden_quality_claims"])
            delivery = Path(result["artifacts"]["delivery_directory"])
            manifest = read_json(delivery / "delivery-manifest.json")
            self.assertEqual(manifest["assets"]["generation_handoff_decision"], "generation-handoff-decision.json")
            self.assertIn("full_quality_generation", manifest["generation"]["handoff_decision"]["forbidden_quality_claims"])

    def test_workbench_api_exposes_artifact_backed_handoff_readiness(self) -> None:
        segments = [_segment("s1", "Delete account", high_risk=True)]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            build_resolution_gate(state, strategy)
            build_generation_handoff_decision(state)
            self.assertEqual(read_generation_handoff_decision(state)["handoff_mode"], "review_required")
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                status, body = _http_get(host, port, f"/api/generation-handoff-status?state_dir={state.as_posix()}")
                self.assertEqual(status, 200)
                payload = json.loads(body)
                self.assertEqual(payload["generation_handoff_status"]["handoff_mode"], "review_required")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_cli_generation_handoff_status_writes_artifact(self) -> None:
        segments = [_segment("s1", "Start game")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / ".localize-anything"
            strategy = _write_strategy_for_segments(state, segments)
            build_resolution_gate(state, strategy)
            output = root / "handoff-decision.json"

            exit_code = cli_main(
                [
                    "generation-handoff-status",
                    state.as_posix(),
                    "--provider-mode",
                    "real_provider",
                    "--provider-policy",
                    "missing",
                    "--output",
                    output.as_posix(),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(read_json(output)["status"], "blocked")
            self.assertTrue((state / "generation-handoff-decision.json").is_file())


class ArtifactStateMachineTests(unittest.TestCase):
    def test_artifact_state_created_for_normal_run_and_delivery_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            _copy_json_fixture_project(project, include_existing_target=False)

            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                source_files=["locales/en-US.json"],
                output_root=root / "out",
                run_id="artifact-state-run-001",
                max_segments=2,
                synthetic_draft=True,
            )

            self.assertIn("artifact_state", result["artifacts"])
            artifact_state = read_artifact_state(project / ".localize-anything")
            assert_protocol_schema(self, "artifact-state", artifact_state)
            self.assertIn("artifact_state", result)
            self.assertEqual(result["artifact_state"]["artifact"], "artifact-state.json")
            self.assertIn("stale_segments", result["artifacts"])
            self.assertIn("reuse_decision", result["artifacts"])
            self.assertEqual(result["summary"]["stale_segment_count"], 0)
            delivery = Path(result["artifacts"]["delivery_directory"])
            self.assertTrue((delivery / "artifact-state.json").is_file())
            self.assertTrue((delivery / "stale-segments.jsonl").is_file())
            manifest_assets = read_json(delivery / "delivery-manifest.json")["assets"]
            self.assertEqual(manifest_assets["artifact_state"], "artifact-state.json")
            self.assertEqual(manifest_assets["reuse_decision"], "reuse-decision.json")

    def test_missing_required_artifacts_are_marked_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"

            artifact_state = build_artifact_state(state)

            brief = _artifact_by_id(artifact_state, "localization_brief_json")
            self.assertEqual(brief["status"], "missing")
            self.assertGreater(artifact_state["summary"]["missing_required_count"], 0)

    def test_localization_brief_change_makes_generation_strategy_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _seed_strategy_handoff_state(state)
            build_artifact_state(state)

            _write_artifact_brief(state, "updated-brief")
            artifact_state = build_artifact_state(state)

            self.assertEqual(_artifact_by_id(artifact_state, "generation_strategy")["status"], "stale")
            self.assertIn("generation_strategy", {item["artifact_id"] for item in artifact_state["stale_artifacts"]})

    def test_dependency_hash_change_marks_stale_even_when_mtime_is_not_newer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _seed_strategy_handoff_state(state)
            build_artifact_state(state)

            strategy = state / "generation-strategy.json"
            strategy_mtime_ns = strategy.stat().st_mtime_ns
            _write_artifact_brief(state, "updated-brief-with-preserved-time")
            os.utime(state / "localization-brief.json", ns=(strategy_mtime_ns - 1, strategy_mtime_ns - 1))
            artifact_state = build_artifact_state(state)

            strategy_state = _artifact_by_id(artifact_state, "generation_strategy")
            self.assertEqual(strategy_state["status"], "stale")
            self.assertIn("localization_brief_json", strategy_state["stale_dependency_ids"])

    def test_term_decision_change_makes_strategy_and_handoff_decision_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _seed_strategy_handoff_state(state)
            build_artifact_state(state)

            write_jsonl(
                state / "term-decisions.jsonl",
                [
                    {
                        "protocol_version": "0.1",
                        "schema": "localize-anything-term-decision-v1",
                        "decision_id": "term-decision-stale-test",
                        "source_term": "Start",
                        "target_term": "开始",
                        "status": "approved",
                    }
                ],
            )
            artifact_state = build_artifact_state(state)

            self.assertEqual(_artifact_by_id(artifact_state, "generation_strategy")["status"], "stale")
            self.assertEqual(_artifact_by_id(artifact_state, "generation_handoff_decision")["status"], "stale")

    def test_resolution_decision_change_makes_handoff_decision_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _seed_strategy_handoff_state(state)
            build_artifact_state(state)

            write_jsonl(
                state / "user-resolution-decisions.jsonl",
                [
                    {
                        "decision_id": "resolution-stale-test",
                        "question_id": "bq-test",
                        "option_id": "continue_only_draft_review",
                        "status": "accepted",
                    }
                ],
            )
            artifact_state = build_artifact_state(state)

            self.assertEqual(_artifact_by_id(artifact_state, "generation_handoff_decision")["status"], "stale")

    def test_generation_strategy_change_makes_generated_segments_and_delivery_decision_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / ".localize-anything"
            run_dir = root / "run"
            run_dir.mkdir()
            segments = [_segment("s1", "Start game")]
            _seed_strategy_handoff_state(state, segments)
            write_jsonl(run_dir / "segments.jsonl", segments)
            write_jsonl(run_dir / "generated.jsonl", [{**segments[0], "target": "开始游戏", "status": "generated"}])
            write_json(run_dir / "review-sheet.json", {"protocol_version": "0.1", "status": "owner_review_required"})
            write_json(run_dir / "delivery-decision.json", {"protocol_version": "0.1", "status": "owner_review_required"})
            write_json(state / "delivery-manifest.json", {"protocol_version": "0.1", "delivery_status": "draft_package"})
            build_artifact_state(state, run_dir=run_dir)

            strategy = read_json(state / "generation-strategy.json")
            strategy["scope"]["segment_count"] = 99
            write_json(state / "generation-strategy.json", strategy)
            artifact_state = build_artifact_state(state, run_dir=run_dir)

            self.assertEqual(_artifact_by_id(artifact_state, "generated_segments")["status"], "stale")
            self.assertEqual(_artifact_by_id(artifact_state, "delivery_decision")["status"], "stale")

    def test_stale_upstream_artifact_prevents_full_quality_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _seed_strategy_handoff_state(state)
            build_artifact_state(state)
            _write_artifact_brief(state, "changed-after-strategy")
            build_artifact_state(state)

            decision = build_generation_handoff_decision(state)

            self.assertEqual(decision["status"], "blocked")
            self.assertFalse(decision["full_quality_handoff_allowed"])
            self.assertIn("stale_artifacts_block_handoff", {item["code"] for item in decision["blockers"]})

    def test_stale_evidence_blocks_delivery_decision_and_apply_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            output = root / "delivery" / "files" / "locales" / "zh-CN.json"
            output.parent.mkdir(parents=True)
            output.write_text('{"start": "开始"}\n', encoding="utf-8")
            (project / "locales").mkdir(parents=True)
            (project / "locales" / "zh-CN.json").write_text("{}\n", encoding="utf-8")
            delivery = root / "delivery"
            write_json(
                delivery / "delivery-manifest.json",
                {
                    "protocol_version": "0.1",
                    "run_id": "stale-delivery-001",
                    "outputs": [
                        {
                            "package_path": "files/locales/zh-CN.json",
                            "destination": "locales/zh-CN.json",
                            "sha256": _sha256(output),
                            "destination_base_sha256": _sha256(project / "locales" / "zh-CN.json"),
                        }
                    ],
                    "generation": {"provider_status": "synthetic_test", "apply_allowed": True},
                    "qa": {"status": "pass", "blocking_count": 0, "warning_count": 0, "items": []},
                    "unprocessed_non_text_assets": [],
                },
            )
            write_json(delivery / "artifact-state.json", _stale_artifact_state_document())

            apply_plan = create_apply_plan(delivery, project)
            delivery_decision = create_delivery_decision_report(delivery, project)

            self.assertTrue(apply_plan["blocked_by_stale_artifacts"])
            self.assertEqual(delivery_decision["status"], "blocked")
            self.assertIn("artifact_state", {item["type"] for item in delivery_decision["decisions"]})

    def test_workbench_api_exposes_artifact_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _seed_strategy_handoff_state(state)
            build_artifact_state(state)
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                status, body = _http_get(host, port, f"/api/artifact-state?state_dir={state.as_posix()}")
                self.assertEqual(status, 200)
                payload = json.loads(body)
                self.assertEqual(payload["artifact_state"]["schema"], "localize-anything-artifact-state-v1")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_cli_artifact_state_reports_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / ".localize-anything"
            output = root / "artifact-state-output.json"
            _seed_strategy_handoff_state(state)

            exit_code = cli_main(["artifact-state", state.as_posix(), "--run-id", "cli-artifact-state-001", "--output", output.as_posix()])

            self.assertEqual(exit_code, 0)
            self.assertTrue((state / "artifact-state.json").is_file())
            result = read_json(output)
            assert_protocol_schema(self, "artifact-state", result)
            self.assertEqual(result["run_id"], "cli-artifact-state-001")


class SegmentStalenessReuseTests(unittest.TestCase):
    def test_unchanged_segments_are_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            segment = _segment("s1", "Start game")
            _seed_strategy_handoff_state(state, [segment])

            decision = build_reuse_decision(state, [segment], generated_segments=[_generated_segment(segment)])

            assert_protocol_schema(self, "reuse-decision", decision)
            assert_protocol_schema(self, "stale-segments", decision["segments"][0])
            self.assertEqual(decision["status"], "ready")
            self.assertEqual(decision["summary"]["reusable_count"], 1)
            self.assertEqual(read_stale_segments(state)[0]["state"], "reusable")

    def test_source_text_change_marks_affected_segment_for_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            old = _segment("s1", "Start game")
            new = _segment("s1", "Start game now")
            _seed_strategy_handoff_state(state, [old])
            build_reuse_decision(state, [old], generated_segments=[_generated_segment(old)])

            decision = build_reuse_decision(state, [new], generated_segments=[_generated_segment(old)])
            record = decision["segments"][0]

            self.assertEqual(record["state"], "needs_regeneration")
            self.assertIn("stale_source_changed", record["classifications"])
            self.assertTrue(record["deterministic_qa_required"])

    def test_placeholder_signature_change_marks_regeneration_and_qa(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            old = _segment("s1", "Delete %s files")
            old["constraints"]["placeholders"] = ["%s"]
            new = _segment("s1", "Delete %s files")
            new["constraints"]["placeholders"] = ["%d"]
            _seed_strategy_handoff_state(state, [old])
            build_reuse_decision(state, [old], generated_segments=[_generated_segment(old)])

            decision = build_reuse_decision(state, [new], generated_segments=[_generated_segment(old)])
            record = decision["segments"][0]

            self.assertEqual(record["state"], "needs_regeneration")
            self.assertIn("stale_context_changed", record["classifications"])
            self.assertTrue(record["deterministic_qa_required"])

    def test_term_policy_change_marks_term_containing_segments_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            segment = _segment("s1", "Weight limit", resource_name="weight_limit", high_risk=True)
            _write_term_registry(
                state,
                [
                    {
                        "source_term": "Weight",
                        "target_term": "重量",
                        "type": "domain_term",
                        "status": "approved",
                        "target_locale": "zh-CN",
                    }
                ],
            )
            _seed_strategy_handoff_state(state, [segment])
            build_reuse_decision(state, [segment], generated_segments=[_generated_segment(segment)])
            _write_term_registry(
                state,
                [
                    {
                        "source_term": "Weight",
                        "target_term": "体重",
                        "type": "domain_term",
                        "status": "approved",
                        "target_locale": "zh-CN",
                    }
                ],
            )

            decision = build_reuse_decision(state, [segment], generated_segments=[_generated_segment(segment)])
            record = decision["segments"][0]

            self.assertIn("stale_term_policy_changed", record["classifications"])
            self.assertEqual(record["state"], "needs_regeneration")
            self.assertTrue(record["targeted_repair_allowed"])
            self.assertTrue(record["review_required"])

    def test_generation_strategy_change_marks_segments_review_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            segment = _segment("s1", "Start game")
            _seed_strategy_handoff_state(state, [segment])
            build_reuse_decision(state, [segment], generated_segments=[_generated_segment(segment)])
            strategy = read_json(state / "generation-strategy.json")
            strategy["route"]["mode"] = "high_assurance_handoff"
            write_json(state / "generation-strategy.json", strategy)

            decision = build_reuse_decision(state, [segment], generated_segments=[_generated_segment(segment)])
            record = decision["segments"][0]

            self.assertEqual(record["state"], "needs_re_review")
            self.assertIn("stale_generation_strategy_changed", record["classifications"])
            self.assertEqual(decision["decisions"]["generation_handoff_policy"], "warn")

    def test_review_policy_change_marks_segments_for_re_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            segment = _segment("s1", "Start game")
            _seed_strategy_handoff_state(state, [segment])
            build_reuse_decision(
                state,
                [segment],
                generated_segments=[_generated_segment(segment)],
                review_policy={"deterministic_review": "standard"},
            )

            decision = build_reuse_decision(
                state,
                [segment],
                generated_segments=[_generated_segment(segment)],
                review_policy={"deterministic_review": "strict"},
            )

            self.assertEqual(decision["segments"][0]["state"], "needs_re_review")
            self.assertIn("review_policy_changed", decision["segments"][0]["reason_codes"])

    def test_stale_segment_summary_appears_in_artifact_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            old = _segment("s1", "Start game")
            new = _segment("s1", "Start game now")
            _seed_strategy_handoff_state(state, [old])
            build_reuse_decision(state, [old], generated_segments=[_generated_segment(old)])
            build_reuse_decision(state, [new], generated_segments=[_generated_segment(old)])

            artifact_state = build_artifact_state(state)

            self.assertEqual(artifact_state["summary"]["stale_segment_count"], 1)
            self.assertEqual(artifact_state["segment_staleness"]["summary"]["needs_regeneration_count"], 1)
            self.assertFalse(artifact_state["decisions"]["full_quality_generation_handoff_allowed"])

    def test_handoff_is_blocked_when_required_stale_segments_remain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            old = _segment("s1", "Start game")
            new = _segment("s1", "Start game now")
            _seed_strategy_handoff_state(state, [old])
            build_reuse_decision(state, [old], generated_segments=[_generated_segment(old)])
            build_reuse_decision(state, [new], generated_segments=[_generated_segment(old)])
            build_artifact_state(state)

            decision = build_generation_handoff_decision(state)

            self.assertEqual(decision["status"], "blocked")
            self.assertIn("stale_segments_block_handoff", {item["code"] for item in decision["blockers"]})

    def test_delivery_apply_blocks_when_stale_generated_segments_affect_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            delivery = root / "delivery"
            output = delivery / "files" / "locales" / "zh-CN.json"
            output.parent.mkdir(parents=True)
            output.write_text('{"start": "开始"}\n', encoding="utf-8")
            (project / "locales").mkdir(parents=True)
            (project / "locales" / "zh-CN.json").write_text("{}\n", encoding="utf-8")
            state = root / ".localize-anything"
            old = _segment("s1", "Start game")
            new = _segment("s1", "Start game now")
            _seed_strategy_handoff_state(state, [old])
            build_reuse_decision(state, [old], generated_segments=[_generated_segment(old)])
            build_reuse_decision(state, [new], generated_segments=[_generated_segment(old)])
            artifact_state = build_artifact_state(state)
            write_json(
                delivery / "delivery-manifest.json",
                {
                    "protocol_version": "0.1",
                    "run_id": "segment-stale-delivery-001",
                    "outputs": [
                        {
                            "package_path": "files/locales/zh-CN.json",
                            "destination": "locales/zh-CN.json",
                            "sha256": _sha256(output),
                            "destination_base_sha256": _sha256(project / "locales" / "zh-CN.json"),
                        }
                    ],
                    "generation": {"provider_status": "synthetic_test", "apply_allowed": True},
                    "qa": {"status": "pass", "blocking_count": 0, "warning_count": 0, "items": []},
                    "unprocessed_non_text_assets": [],
                },
            )
            write_json(delivery / "artifact-state.json", artifact_state)

            apply_plan = create_apply_plan(delivery, project)
            delivery_decision = create_delivery_decision_report(delivery, project)

            self.assertTrue(apply_plan["blocked_by_stale_artifacts"])
            self.assertIn("s1", apply_plan["artifact_state_apply_block_reason"])
            self.assertEqual(delivery_decision["status"], "blocked")

    def test_cli_reports_stale_segments_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / ".localize-anything"
            segment = _segment("s1", "Start game")
            _seed_strategy_handoff_state(state, [segment])
            segments_path = root / "segments.jsonl"
            generated_path = root / "generated.jsonl"
            decision_output = root / "reuse-decision-output.json"
            stale_output = root / "stale-segments-output.json"
            write_jsonl(segments_path, [segment])
            write_jsonl(generated_path, [_generated_segment(segment)])

            exit_code = cli_main(
                [
                    "reuse-decision",
                    state.as_posix(),
                    segments_path.as_posix(),
                    "--generated",
                    generated_path.as_posix(),
                    "--run-id",
                    "cli-reuse-001",
                    "--output",
                    decision_output.as_posix(),
                ]
            )
            stale_exit = cli_main(["stale-segments", state.as_posix(), "--output", stale_output.as_posix()])

            self.assertEqual(exit_code, 0)
            self.assertEqual(stale_exit, 0)
            self.assertEqual(read_json(decision_output)["run_id"], "cli-reuse-001")
            self.assertEqual(read_json(stale_output)["segments"][0]["state"], "reusable")

    def test_workbench_api_exposes_stale_segments_and_reuse_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            segment = _segment("s1", "Start game")
            _seed_strategy_handoff_state(state, [segment])
            build_reuse_decision(state, [segment], generated_segments=[_generated_segment(segment)])
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                stale_status, stale_body = _http_get(host, port, f"/api/stale-segments?state_dir={state.as_posix()}")
                reuse_status, reuse_body = _http_get(host, port, f"/api/reuse-decision?state_dir={state.as_posix()}")
                self.assertEqual(stale_status, 200)
                self.assertEqual(reuse_status, 200)
                self.assertEqual(json.loads(stale_body)["stale_segments"][0]["state"], "reusable")
                self.assertEqual(json.loads(reuse_body)["reuse_decision"]["status"], "ready")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class TargetedRepairRegenerationPlanTests(unittest.TestCase):
    def test_unchanged_low_risk_segment_action_is_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            segment = _segment("s1", "Start game")
            _seed_strategy_handoff_state(state, [segment])
            build_reuse_decision(state, [segment], generated_segments=[_generated_segment(segment)])

            plan = build_segment_regeneration_plan(state)

            assert_protocol_schema(self, "segment-regeneration-plan", plan)
            self.assertEqual(plan["status"], "ready")
            self.assertEqual(plan["segments"][0]["action"], "reuse")
            self.assertEqual(read_repair_request(state)["summary"]["request_count"], 0)

    def test_source_changed_segment_action_is_regenerate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            old = _segment("s1", "Start game")
            new = _segment("s1", "Start game now")
            _seed_strategy_handoff_state(state, [old])
            build_reuse_decision(state, [old], generated_segments=[_generated_segment(old)])
            build_reuse_decision(state, [new], generated_segments=[_generated_segment(old)])

            plan = build_segment_regeneration_plan(state)

            self.assertEqual(plan["segments"][0]["action"], "regenerate")
            self.assertEqual(plan["segments"][0]["repair_type"], "regenerate_segment")
            self.assertEqual(plan["decisions"]["generation_handoff_policy"], "blocked")

    def test_placeholder_changed_segment_requires_regenerate_and_qa(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            old = _segment("s1", "Delete %s files")
            old["constraints"]["placeholders"] = ["%s"]
            new = _segment("s1", "Delete %s files")
            new["constraints"]["placeholders"] = ["%d"]
            _seed_strategy_handoff_state(state, [old])
            build_reuse_decision(state, [old], generated_segments=[_generated_segment(old)])
            build_reuse_decision(state, [new], generated_segments=[_generated_segment(old)])

            plan = build_segment_regeneration_plan(state)
            segment = plan["segments"][0]

            self.assertEqual(segment["action"], "regenerate")
            self.assertTrue(segment["deterministic_qa_required"])
            self.assertTrue(plan["decisions"]["requires_deterministic_qa"])

    def test_term_policy_change_creates_targeted_repair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            segment = _segment("s1", "Weight limit")
            _write_term_registry(
                state,
                [{"source_term": "Weight", "target_term": "重量", "type": "domain_term", "status": "approved", "target_locale": "zh-CN"}],
            )
            _seed_strategy_handoff_state(state, [segment])
            build_reuse_decision(state, [segment], generated_segments=[_generated_segment(segment)])
            _write_term_registry(
                state,
                [{"source_term": "Weight", "target_term": "体重", "type": "domain_term", "status": "approved", "target_locale": "zh-CN"}],
            )
            build_reuse_decision(state, [segment], generated_segments=[_generated_segment(segment)])

            plan = build_segment_regeneration_plan(state)

            self.assertEqual(plan["segments"][0]["action"], "targeted_repair")
            self.assertEqual(plan["segments"][0]["repair_type"], "term_patch")

    def test_review_policy_changed_segment_creates_re_review_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            segment = _segment("s1", "Start game")
            _seed_strategy_handoff_state(state, [segment])
            build_reuse_decision(
                state,
                [segment],
                generated_segments=[_generated_segment(segment)],
                review_policy={"deterministic_review": "standard"},
            )
            build_reuse_decision(
                state,
                [segment],
                generated_segments=[_generated_segment(segment)],
                review_policy={"deterministic_review": "strict"},
            )

            plan = build_segment_regeneration_plan(state)

            self.assertEqual(plan["segments"][0]["action"], "re_review")
            self.assertEqual(plan["segments"][0]["repair_type"], "review_only")
            self.assertEqual(plan["decisions"]["generation_handoff_policy"], "warn")

    def test_high_risk_unresolved_segment_requires_human_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            segment = _segment("s1", "Delete account", high_risk=True)
            _seed_strategy_handoff_state(state, [segment])
            build_reuse_decision(
                state,
                [segment],
                generated_segments=[_generated_segment(segment)],
                review_policy={"deterministic_review": "standard"},
            )
            build_reuse_decision(
                state,
                [segment],
                generated_segments=[_generated_segment(segment)],
                review_policy={"deterministic_review": "strict"},
            )

            plan = build_segment_regeneration_plan(state)

            self.assertEqual(plan["segments"][0]["action"], "human_confirm")
            self.assertTrue(plan["segments"][0]["human_confirmation_required"])

    def test_repair_request_is_created_for_targeted_repair_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _seed_term_targeted_repair(state)

            build_segment_regeneration_plan(state)
            request = read_repair_request(state)

            assert_protocol_schema(self, "repair-request", request)
            self.assertEqual(request["summary"]["request_count"], 1)
            self.assertEqual(request["requests"][0]["repair_type"], "term_patch")
            self.assertTrue(request["requests"][0]["provider_or_model_required"])

    def test_repair_result_does_not_fabricate_provider_model_repairs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _seed_term_targeted_repair(state)

            build_segment_regeneration_plan(state)
            result = read_repair_result(state)

            assert_protocol_schema(self, "repair-result", result)
            self.assertEqual(result["results"][0]["repair_status"], "pending_provider_or_model_repair")
            self.assertIsNone(result["results"][0]["new_target"])
            self.assertIsNone(result["results"][0]["new_target_hash"])

    def test_repair_history_appends_repair_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _seed_term_targeted_repair(state)

            build_segment_regeneration_plan(state)
            first = read_repair_history(state)
            build_segment_regeneration_plan(state)
            second = read_repair_history(state)

            assert_protocol_schema(self, "repair-history", first[0])
            self.assertEqual(len(first), 1)
            self.assertEqual(len(second), 2)
            self.assertEqual(first[0]["repair_id"], second[0]["repair_id"])

    def test_pending_repairs_block_handoff_delivery_and_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            delivery = root / "delivery"
            output = delivery / "files" / "locales" / "zh-CN.json"
            output.parent.mkdir(parents=True)
            output.write_text('{"weight": "重量限制"}\n', encoding="utf-8")
            (project / "locales").mkdir(parents=True)
            (project / "locales" / "zh-CN.json").write_text("{}\n", encoding="utf-8")
            state = root / ".localize-anything"
            _seed_term_targeted_repair(state)
            build_segment_regeneration_plan(state)
            artifact_state = build_artifact_state(state)
            write_json(
                delivery / "delivery-manifest.json",
                {
                    "protocol_version": "0.1",
                    "run_id": "pending-repair-delivery-001",
                    "outputs": [
                        {
                            "package_path": "files/locales/zh-CN.json",
                            "destination": "locales/zh-CN.json",
                            "sha256": _sha256(output),
                            "destination_base_sha256": _sha256(project / "locales" / "zh-CN.json"),
                        }
                    ],
                    "generation": {"provider_status": "synthetic_test", "apply_allowed": True},
                    "qa": {"status": "pass", "blocking_count": 0, "warning_count": 0, "items": []},
                    "unprocessed_non_text_assets": [],
                },
            )
            write_json(delivery / "artifact-state.json", artifact_state)

            handoff = build_generation_handoff_decision(state)
            apply_plan = create_apply_plan(delivery, project)
            delivery_decision = create_delivery_decision_report(delivery, project)

            self.assertEqual(handoff["status"], "blocked")
            self.assertIn("pending_segment_repairs_block_handoff", {item["code"] for item in handoff["blockers"]})
            self.assertTrue(apply_plan["blocked_by_stale_artifacts"])
            self.assertIn("s1", apply_plan["artifact_state_apply_block_reason"])
            self.assertEqual(delivery_decision["status"], "blocked")
            self.assertEqual(delivery_decision["summary"]["pending_segment_repair_count"], 1)

    def test_run_summary_surfaces_repair_regeneration_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = _make_json_project(Path(directory))

            result = run_localize(project, "en-US", ["zh-CN"], synthetic_draft=True, run_id="repair-summary-001")

            self.assertIn("segment_regeneration_plan", result["artifacts"])
            self.assertIn("repair_request", result["artifacts"])
            self.assertIn("repair_result", result["artifacts"])
            self.assertIn("repair_history", result["artifacts"])
            self.assertEqual(result["summary"]["pending_segment_repairs"], 0)
            self.assertEqual(result["summary"]["segments_targeted_repair"], 0)

    def test_cli_commands_produce_deterministic_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / ".localize-anything"
            output = root / "plan-output.json"
            request_output = root / "request-output.json"
            history_output = root / "history-output.json"
            _seed_term_targeted_repair(state)

            plan_exit = cli_main(["segment-regeneration-plan", state.as_posix(), "--run-id", "cli-repair-001", "--output", output.as_posix()])
            request_exit = cli_main(["repair-request", state.as_posix(), "--output", request_output.as_posix()])
            history_exit = cli_main(["repair-history", state.as_posix(), "--output", history_output.as_posix()])

            self.assertEqual(plan_exit, 0)
            self.assertEqual(request_exit, 0)
            self.assertEqual(history_exit, 0)
            self.assertEqual(read_json(output)["run_id"], "cli-repair-001")
            self.assertEqual(read_json(request_output)["repair_request"]["summary"]["request_count"], 1)
            self.assertEqual(read_json(history_output)["repair_history"][0]["segment_id"], "s1")

    def test_workbench_api_exposes_regeneration_and_repair_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _seed_term_targeted_repair(state)
            build_segment_regeneration_plan(state)
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                plan_status, plan_body = _http_get(host, port, f"/api/segment-regeneration-plan?state_dir={state.as_posix()}")
                request_status, request_body = _http_get(host, port, f"/api/repair-request?state_dir={state.as_posix()}")
                result_status, result_body = _http_get(host, port, f"/api/repair-result?state_dir={state.as_posix()}")
                history_status, history_body = _http_get(host, port, f"/api/repair-history?state_dir={state.as_posix()}")
                self.assertEqual(plan_status, 200)
                self.assertEqual(request_status, 200)
                self.assertEqual(result_status, 200)
                self.assertEqual(history_status, 200)
                self.assertEqual(json.loads(plan_body)["segment_regeneration_plan"]["segments"][0]["action"], "targeted_repair")
                self.assertEqual(json.loads(request_body)["repair_request"]["summary"]["request_count"], 1)
                self.assertEqual(json.loads(result_body)["repair_result"]["summary"]["result_count"], 1)
                self.assertEqual(json.loads(history_body)["repair_history"][0]["segment_id"], "s1")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class PatchBasedRepairExecutionTests(unittest.TestCase):
    def test_placeholder_patch_applies_only_when_mechanically_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            generated = [_generated_segment(_segment("s1", "Delete %s files"), "Delete % S files")]
            _write_repair_execution_state(
                state,
                [
                    _manual_repair_request(
                        "s1",
                        "placeholder_patch",
                        old_target="Delete % S files",
                        required_constraints={"placeholders": ["%s"]},
                        deterministic_qa_required=True,
                    )
                ],
                generated,
            )

            result = apply_repair_plan(state, generated_segments_path=state / "generated-segments.jsonl")

            self.assertEqual(result["results"][0]["repair_status"], "applied")
            self.assertEqual(result["results"][0]["new_target"], "Delete %s files")
            self.assertEqual(read_jsonl(state / "generated-segments.jsonl")[0]["target"], "Delete %s files")

    def test_markup_patch_applies_only_when_structurally_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_repair_execution_state(
                state,
                [_manual_repair_request("s1", "markup_patch", old_target="Save", required_constraints={"markup": ["b"]})],
            )

            result = apply_repair_plan(state)

            self.assertEqual(result["results"][0]["repair_status"], "applied")
            self.assertEqual(result["results"][0]["new_target"], "<b>Save</b>")

    def test_escape_patch_fixes_format_escaping_and_reruns_qa(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_repair_execution_state(state, [_manual_repair_request("s1", "escape_patch", old_target="Tom & Jerry")])

            result = apply_repair_plan(state)

            repair = result["results"][0]
            self.assertEqual(repair["repair_status"], "applied")
            self.assertEqual(repair["new_target"], "Tom &amp; Jerry")
            self.assertEqual(repair["qa_result"]["status"], "pass")

    def test_term_patch_applies_only_for_locked_unambiguous_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_term_registry(
                state,
                [
                    {
                        "source_term": "Weight",
                        "target_term": "体重",
                        "type": "domain_term",
                        "status": "locked",
                        "target_locale": "zh-CN",
                        "forbidden_targets": "重量",
                    }
                ],
            )
            _write_repair_execution_state(
                state,
                [
                    _manual_repair_request(
                        "s1",
                        "term_patch",
                        old_target="重量限制",
                        required_constraints={"matched_terms": ["Weight"]},
                    )
                ],
            )

            result = apply_repair_plan(state)

            self.assertEqual(result["results"][0]["repair_status"], "applied")
            self.assertEqual(result["results"][0]["new_target"], "体重限制")
            self.assertEqual(result["results"][0]["deterministic_rule_used"], "locked_term_exact_replacement")

    def test_term_patch_refuses_ambiguous_or_missing_old_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "missing" / ".localize-anything"
            _write_term_registry(
                state,
                [{"source_term": "Weight", "target_term": "体重", "status": "approved", "forbidden_targets": "重量"}],
            )
            _write_repair_execution_state(
                state,
                [_manual_repair_request("s1", "term_patch", required_constraints={"matched_terms": ["Weight"]})],
            )

            missing = apply_repair_plan(state)

            ambiguous_state = Path(directory) / "ambiguous" / ".localize-anything"
            _write_term_registry(
                ambiguous_state,
                [
                    {"source_term": "Weight", "target_term": "体重", "status": "approved", "forbidden_targets": "重量"},
                    {"source_term": "Weight", "target_term": "砝码", "status": "approved", "forbidden_targets": "重量"},
                ],
            )
            _write_repair_execution_state(
                ambiguous_state,
                [
                    _manual_repair_request(
                        "s1",
                        "term_patch",
                        old_target="重量限制",
                        required_constraints={"matched_terms": ["Weight"]},
                    )
                ],
            )
            ambiguous = apply_repair_plan(ambiguous_state)

            self.assertEqual(missing["results"][0]["repair_status"], "pending_provider")
            self.assertEqual(missing["results"][0]["no_patch_reason"], "missing_old_target_text")
            self.assertEqual(ambiguous["results"][0]["repair_status"], "blocked")

    def test_risk_wording_patch_remains_pending_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_repair_execution_state(state, [_manual_repair_request("s1", "risk_wording_patch", old_target="Delete account")])

            result = apply_repair_plan(state)

            self.assertEqual(result["results"][0]["repair_status"], "pending_provider")

    def test_regenerate_segment_remains_pending_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_repair_execution_state(state, [_manual_repair_request("s1", "regenerate_segment", old_target="Start game")])

            result = apply_repair_plan(state)

            self.assertEqual(result["results"][0]["repair_status"], "pending_provider")

    def test_high_risk_repair_without_human_confirmation_is_pending_human(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_repair_execution_state(
                state,
                [
                    _manual_repair_request(
                        "s1",
                        "escape_patch",
                        old_target="Delete account",
                        risk_level="high",
                    )
                ],
            )

            result = apply_repair_plan(state)

            self.assertEqual(result["results"][0]["repair_status"], "pending_human")

    def test_stale_old_target_mismatch_blocks_generated_artifact_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            generated = [_generated_segment(_segment("s1", "Brand"), "Tom and Jerry")]
            _write_repair_execution_state(
                state,
                [_manual_repair_request("s1", "escape_patch", old_target="Tom & Jerry")],
                generated,
            )

            result = apply_repair_plan(state, generated_segments_path=state / "generated-segments.jsonl")

            self.assertEqual(result["results"][0]["repair_status"], "blocked")
            self.assertEqual(result["results"][0]["no_patch_reason"], "generated_target_does_not_match_repair_request_old_target")
            self.assertEqual(read_jsonl(state / "generated-segments.jsonl")[0]["target"], "Tom and Jerry")

    def test_failed_deterministic_qa_blocks_delivery_apply_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_repair_execution_state(
                state,
                [
                    _manual_repair_request(
                        "s1",
                        "placeholder_patch",
                        old_target="Delete % S files",
                        required_constraints={"placeholders": ["%s", "%d"]},
                        deterministic_qa_required=True,
                    )
                ],
            )

            result = apply_repair_plan(state)
            artifact_state = build_artifact_state(state)

            self.assertEqual(result["results"][0]["repair_status"], "failed_qa")
            self.assertEqual(artifact_state["decisions"]["apply_policy"], "blocked")
            self.assertEqual(artifact_state["summary"]["segment_repair_failed_qa_count"], 1)

    def test_repair_history_records_applied_and_pending_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_repair_execution_state(
                state,
                [
                    _manual_repair_request("s1", "escape_patch", old_target="Tom & Jerry"),
                    _manual_repair_request("s2", "regenerate_segment", old_target="Start game"),
                ],
            )

            apply_repair_plan(state)
            history = read_repair_history(state)

            self.assertEqual([item["repair_status"] for item in history], ["applied", "pending_provider"])
            self.assertEqual(history[0]["deterministic_rule_used"], "xml_ampersand_escape")
            self.assertEqual(history[1]["no_patch_reason"], "provider_or_model_repair_required")

    def test_run_summary_surfaces_patch_repair_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = _make_json_project(Path(directory))

            result = run_localize(project, "en-US", ["zh-CN"], synthetic_draft=True, run_id="patch-repair-summary-001")

            self.assertIn("segment_repairs_applied", result["summary"])
            self.assertIn("segment_repairs_pending_provider", result["summary"])
            self.assertIn("segment_repairs_failed_qa", result["summary"])
            manifest = read_json(Path(result["artifacts"]["delivery_directory"]) / "delivery-manifest.json")
            self.assertEqual(manifest["assets"]["repair_result"], "repair-result.json")
            self.assertEqual(manifest["assets"]["repair_history"], "repair-history.jsonl")

    def test_cli_repair_command_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            output = Path(directory) / "repair-result-output.json"
            _write_repair_execution_state(state, [_manual_repair_request("s1", "escape_patch", old_target="Tom & Jerry")])

            exit_code = cli_main(["apply-repair-plan", state.as_posix(), "--output", output.as_posix()])
            read_exit = cli_main(["repair-result", state.as_posix(), "--output", (Path(directory) / "repair-read.json").as_posix()])

            self.assertEqual(exit_code, 0)
            self.assertEqual(read_exit, 0)
            self.assertEqual(read_json(output)["results"][0]["new_target"], "Tom &amp; Jerry")

    def test_workbench_api_repair_endpoint_does_not_call_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_repair_execution_state(state, [_manual_repair_request("s1", "escape_patch", old_target="Tom & Jerry")])
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                with mock.patch("runtime.localize_anything.provider.generate_handoff_with_http_provider", side_effect=AssertionError):
                    post_status, post_payload = _http_post_json(
                        host,
                        port,
                        "/api/apply-repair-plan",
                        {"state_dir": state.as_posix()},
                    )
                get_status, get_body = _http_get(host, port, f"/api/repair-result?state_dir={state.as_posix()}")
                self.assertEqual(post_status, 200)
                self.assertEqual(get_status, 200)
                self.assertEqual(post_payload["repair_result"]["results"][0]["repair_status"], "applied")
                self.assertEqual(json.loads(get_body)["repair_result"]["summary"]["applied_count"], 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class EvaluationScorecardTests(unittest.TestCase):
    def test_scorecard_blocks_provider_backed_claim_when_provider_failed_or_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            failed_state = Path(directory) / "failed" / ".localize-anything"
            failed = _build_scorecard_state(
                failed_state,
                provider_status="failed",
                provider_actual="synthetic_fallback",
            )
            not_run_state = Path(directory) / "not-run" / ".localize-anything"
            not_run = _build_scorecard_state(
                not_run_state,
                provider_status="not_run",
                provider_actual="none",
            )

            self.assertEqual(failed["provider_status"]["status"], "blocked")
            self.assertIn("provider_backed_quality", failed["forbidden_claims"])
            self.assertIn("provider_backed_quality", not_run["forbidden_claims"])

    def test_scorecard_blocks_full_coverage_claim_when_coverage_is_partial_or_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            partial = _build_scorecard_state(
                Path(directory) / "partial" / ".localize-anything",
                coverage={"coverage_mode": "source-only", "visible_ui_coverage_warning": True},
            )
            unknown = _build_scorecard_state(Path(directory) / "unknown" / ".localize-anything", coverage={})

            self.assertIn("full_coverage", partial["forbidden_claims"])
            self.assertIn("full_coverage", unknown["forbidden_claims"])
            self.assertEqual(partial["coverage_assurance"]["status"], "warning")

    def test_incomplete_term_review_downgrades_terminology_assurance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scorecard = _build_scorecard_state(
                Path(directory) / ".localize-anything",
                term_assurance="incomplete_review_required",
                high_risk_unreviewed_count=1,
            )

            self.assertEqual(scorecard["terminology_assurance"]["status"], "warning")
            self.assertIn("full_terminology_assurance", scorecard["forbidden_claims"])

    def test_stale_artifacts_block_or_downgrade_overall_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scorecard = _build_scorecard_state(
                Path(directory) / ".localize-anything",
                artifact_status="stale",
                stale_count=1,
            )

            self.assertEqual(scorecard["artifact_freshness"]["status"], "blocked")
            self.assertEqual(scorecard["overall_claim"], "blocked")
            self.assertIn("full_coverage", scorecard["forbidden_claims"])
            self.assertIn("full_terminology_assurance", scorecard["forbidden_claims"])

    def test_pending_required_repairs_block_delivery_and_apply_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scorecard = _build_scorecard_state(
                Path(directory) / ".localize-anything",
                pending_required_repairs=1,
            )

            self.assertEqual(scorecard["repair_readiness"]["status"], "blocked")
            self.assertIn("delivery_ready", scorecard["forbidden_claims"])
            self.assertIn("apply_ready", scorecard["forbidden_claims"])

    def test_successful_deterministic_qa_supports_e0(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scorecard = _build_scorecard_state(Path(directory) / ".localize-anything")

            assert_protocol_schema(self, "evaluation-scorecard", scorecard)
            self.assertEqual(scorecard["structural_qa"]["status"], "pass")
            self.assertEqual(scorecard["evidence_level"]["levels"]["E0_deterministic_structural_qa"]["status"], "provided")

    def test_automated_policy_artifacts_support_e1_but_not_e2_to_e4(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scorecard = _build_scorecard_state(Path(directory) / ".localize-anything")
            levels = scorecard["evidence_level"]["levels"]

            self.assertEqual(levels["E1_automated_semantic_or_policy_review"]["status"], "provided")
            self.assertEqual(levels["E2_bilingual_human_spot_check"]["status"], "not_provided")
            self.assertEqual(levels["E3_native_language_review"]["status"], "not_provided")
            self.assertEqual(levels["E4_professional_localization_review"]["status"], "not_provided")

    def test_human_native_professional_review_evidence_is_required_for_e2_to_e4(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            without_human = _build_scorecard_state(Path(directory) / "without" / ".localize-anything")
            with_native = _build_scorecard_state(
                Path(directory) / "with-native" / ".localize-anything",
                review_evidence="E3_native_language_review",
            )

            self.assertEqual(without_human["evidence_level"]["levels"]["E2_bilingual_human_spot_check"]["status"], "not_provided")
            self.assertEqual(with_native["evidence_level"]["highest_supported"], "E3_native_language_review")
            self.assertEqual(with_native["evidence_level"]["levels"]["E2_bilingual_human_spot_check"]["status"], "not_provided")
            self.assertEqual(with_native["evidence_level"]["levels"]["E3_native_language_review"]["status"], "provided")
            self.assertEqual(with_native["evidence_level"]["levels"]["E4_professional_localization_review"]["status"], "not_provided")

    def test_overall_claim_becomes_review_ready_only_when_blockers_are_clear(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clear = _build_scorecard_state(
                Path(directory) / "clear" / ".localize-anything",
                delivery_status="owner_review_required",
            )
            blocked = _build_scorecard_state(
                Path(directory) / "blocked" / ".localize-anything",
                delivery_status="owner_review_required",
                unresolved_question_count=1,
            )

            self.assertEqual(clear["overall_claim"], "review_ready")
            self.assertEqual(blocked["overall_claim"], "blocked")

    def test_delivery_ready_with_warnings_requires_explicit_non_blocking_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scorecard = _build_scorecard_state(
                Path(directory) / ".localize-anything",
                coverage={"coverage_mode": "source-only", "visible_ui_coverage_warning": True},
            )

            self.assertEqual(scorecard["delivery_readiness"]["status"], "pass")
            self.assertEqual(scorecard["overall_claim"], "delivery_ready_with_warnings")
            self.assertIn("full_coverage", scorecard["forbidden_claims"])

    def test_apply_ready_is_blocked_when_apply_evidence_is_blocked_or_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scorecard = _build_scorecard_state(
                Path(directory) / ".localize-anything",
                apply_blocked_by_stale=True,
            )

            self.assertEqual(scorecard["apply_readiness"]["status"], "blocked")
            self.assertEqual(scorecard["overall_claim"], "blocked")
            self.assertIn("apply_ready", scorecard["forbidden_claims"])

    def test_forbidden_claims_are_emitted_for_unsupported_quality_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scorecard = _build_scorecard_state(
                Path(directory) / ".localize-anything",
                provider_status="synthetic_test",
                provider_actual="synthetic",
                term_assurance="incomplete_review_required",
                high_risk_unreviewed_count=1,
                coverage={},
                delivery_status="draft_package",
                apply_operations=[{"action": "replace", "destination": "locales/zh-CN.json"}],
            )

            self.assertTrue(
                {
                    "full_coverage",
                    "provider_backed_quality",
                    "full_terminology_assurance",
                    "review_complete",
                    "delivery_ready",
                    "apply_ready",
                    "production_ready",
                }.issubset(set(scorecard["forbidden_claims"]))
            )

    def test_run_summary_and_delivery_package_reference_scorecard_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = _make_json_project(Path(directory))

            result = run_localize(project, "en-US", ["zh-CN"], synthetic_draft=True, run_id="scorecard-run-001")

            self.assertIn("evaluation_scorecard", result["artifacts"])
            self.assertIn("evidence_level_report", result["artifacts"])
            self.assertIn("evaluation_status", result["summary"])
            self.assertIn("overall_claim", result["summary"])
            scorecard = read_json(Path(result["artifacts"]["evaluation_scorecard"]))
            assert_protocol_schema(self, "evaluation-scorecard", scorecard)
            delivery = Path(result["artifacts"]["delivery_directory"])
            manifest = read_json(delivery / "delivery-manifest.json")
            self.assertEqual(manifest["assets"]["evaluation_scorecard"], "evaluation-scorecard.json")
            self.assertEqual(manifest["assets"]["evidence_level_report"], "evidence-level-report.md")
            self.assertTrue((delivery / "evaluation-scorecard.json").is_file())
            self.assertTrue((delivery / "evidence-level-report.md").is_file())
            packaged_scorecard = read_json(delivery / "evaluation-scorecard.json")
            self.assertEqual(packaged_scorecard["overall_claim"], scorecard["overall_claim"])

    def test_cli_output_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            output = Path(directory) / "scorecard-output.json"
            _write_scorecard_state(state)

            exit_code = cli_main(
                [
                    "evaluation-scorecard",
                    state.as_posix(),
                    "--run-id",
                    "cli-scorecard-001",
                    "--output",
                    output.as_posix(),
                ]
            )

            self.assertEqual(exit_code, 0)
            emitted = read_json(output)
            self.assertEqual(emitted["overall_claim"], emitted["evaluation_scorecard"]["overall_claim"])
            self.assertEqual(emitted["evaluation_scorecard"]["run_id"], "cli-scorecard-001")
            self.assertTrue((state / "evidence-level-report.md").is_file())

    def test_workbench_api_exposes_scorecard_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                status, body = _http_get(host, port, f"/api/evaluation-scorecard?state_dir={state.as_posix()}")
                self.assertEqual(status, 200)
                payload = json.loads(body)
                self.assertEqual(payload["evaluation_scorecard"]["schema"], "localize-anything-evaluation-scorecard-v1")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class HumanReviewClaimAcceptanceTests(unittest.TestCase):
    def test_record_bilingual_human_review_supports_e2(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_scorecard_state(state)
            record_human_review_evidence(state, _human_review_record("bilingual_reviewer", "E2_bilingual_human_spot_check", "full_run"))
            scorecard = build_evaluation_scorecard(state, coverage_diagnostics={"coverage_mode": "source-plus-merged-overlay"})

            assert_protocol_schema(self, "human-review-evidence", read_human_review_evidence(state)[0])
            self.assertEqual(scorecard["evidence_level"]["levels"]["E2_bilingual_human_spot_check"]["status"], "provided")
            self.assertEqual(scorecard["review_readiness"]["status"], "pass")

    def test_project_owner_signoff_does_not_create_e2(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_scorecard_state(state)
            record_human_review_evidence(state, _human_review_record("project_owner", "E2_bilingual_human_spot_check", "full_run"))
            scorecard = build_evaluation_scorecard(state, coverage_diagnostics={"coverage_mode": "source-plus-merged-overlay"})

            self.assertEqual(scorecard["human_review_evidence"]["global_supported_levels"], [])
            self.assertEqual(scorecard["evidence_level"]["levels"]["E2_bilingual_human_spot_check"]["status"], "not_provided")
            self.assertIn("review_complete", scorecard["forbidden_claims"])

    def test_limited_scope_human_review_is_reported_as_limited(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_scorecard_state(state)
            record_human_review_evidence(state, _human_review_record("bilingual_reviewer", "E2_bilingual_human_spot_check", "segment"))
            scorecard = build_evaluation_scorecard(state, coverage_diagnostics={"coverage_mode": "source-plus-merged-overlay"})

            self.assertEqual(scorecard["human_review_evidence"]["status"], "limited_scope")
            self.assertEqual(scorecard["review_readiness"]["status"], "warning")
            self.assertIn("review_complete", scorecard["forbidden_claims"])

    def test_rejected_or_stale_review_does_not_support_e_levels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_scorecard_state(state)
            record_human_review_evidence(
                state,
                {**_human_review_record("native_language_reviewer", "E3_native_language_review", "full_run"), "status": "rejected"},
            )
            scorecard = build_evaluation_scorecard(state, coverage_diagnostics={"coverage_mode": "source-plus-merged-overlay"})

            self.assertEqual(scorecard["evidence_level"]["levels"]["E3_native_language_review"]["status"], "not_provided")
            self.assertEqual(scorecard["human_review_evidence"]["status"], "requires_follow_up")

    def test_claim_acceptance_blocks_forbidden_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, provider_status="not_run", provider_actual="none")

            decision = build_claim_acceptance_decision(state, requested_claims=["provider_backed_quality"])

            assert_protocol_schema(self, "claim-acceptance-decision", decision)
            self.assertEqual(decision["status"], "blocked")
            self.assertIn("provider_backed_quality", decision["rejected_claims"])

    def test_claim_acceptance_accepts_review_ready_when_scorecard_supports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, delivery_status="owner_review_required")

            decision = build_claim_acceptance_decision(state, requested_claims=["review_ready"])

            self.assertEqual(decision["status"], "accepted")
            self.assertEqual(decision["accepted_claims"], ["review_ready"])

    def test_limited_delivery_claim_requires_explicit_risk_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, coverage={"coverage_mode": "source-only", "visible_ui_coverage_warning": True})

            blocked = build_claim_acceptance_decision(state, requested_claims=["limited_scope_delivery_ready"])
            limited = build_claim_acceptance_decision(
                state,
                requested_claims=["limited_scope_delivery_ready"],
                accepted_risk={"accepts_limitations": True},
            )

            self.assertEqual(blocked["status"], "blocked")
            self.assertEqual(limited["status"], "accepted_with_limitations")

    def test_signoff_cannot_authorize_apply_when_scorecard_forbids_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            build_claim_acceptance_decision(state, requested_claims=["apply_ready"])

            signoff = create_signoff_record(state, _signoff_request(apply=True))

            assert_protocol_schema(self, "signoff-record", signoff)
            self.assertFalse(signoff["apply_authorized"])
            self.assertEqual(signoff["status"], "requires_follow_up")

    def test_signoff_authorizes_apply_only_when_scorecard_is_apply_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, review_evidence="E2_bilingual_human_spot_check")
            build_claim_acceptance_decision(state, requested_claims=["apply_ready"])

            signoff = create_signoff_record(state, _signoff_request(apply=True, limitations=False))

            self.assertTrue(signoff["apply_authorized"])
            self.assertEqual(signoff["status"], "accepted")

    def test_artifact_state_tracks_human_review_claim_and_signoff_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, review_evidence="E2_bilingual_human_spot_check")
            build_claim_acceptance_decision(state, requested_claims=["review_complete"])
            create_signoff_record(state, _signoff_request(delivery=True))

            artifact_state = build_artifact_state(state)
            artifact_ids = {item["artifact_id"] for item in artifact_state["artifacts"]}

            self.assertTrue({"human_review_evidence", "claim_acceptance_decision", "signoff_record"}.issubset(artifact_ids))
            self.assertEqual(artifact_state["summary"]["human_review_global_count"], 1)

    def test_human_review_change_stales_claim_acceptance_and_signoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, review_evidence="E2_bilingual_human_spot_check")
            build_claim_acceptance_decision(state, requested_claims=["review_complete"])
            create_signoff_record(state, _signoff_request(delivery=True))
            build_artifact_state(state)
            record_human_review_evidence(state, _human_review_record("bilingual_reviewer", "E2_bilingual_human_spot_check", "segment"))

            artifact_state = build_artifact_state(state)

            self.assertEqual(_artifact_by_id(artifact_state, "claim_acceptance_decision")["status"], "stale")
            self.assertEqual(_artifact_by_id(artifact_state, "signoff_record")["status"], "stale")

    def test_scorecard_ignores_unstructured_review_result_for_e2_to_e4(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_scorecard_state(state)
            write_json(state / "review-result.json", {"notes": "E4_professional_localization_review"})
            scorecard = build_evaluation_scorecard(state, coverage_diagnostics={"coverage_mode": "source-plus-merged-overlay"})

            self.assertEqual(scorecard["evidence_level"]["levels"]["E4_professional_localization_review"]["status"], "not_provided")

    def test_evidence_report_mentions_claim_and_signoff_states(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            build_claim_acceptance_decision(state, requested_claims=["review_ready"])
            create_signoff_record(state, _signoff_request(delivery=True))
            build_evaluation_scorecard(state, coverage_diagnostics={"coverage_mode": "source-plus-merged-overlay"})

            report = (state / "evidence-level-report.md").read_text(encoding="utf-8")

            self.assertIn("## Claim Acceptance", report)
            self.assertIn("## Human Review And Signoff", report)

    def test_apply_plan_blocks_scorecard_forbidden_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, delivery = _write_apply_delivery(
                Path(directory),
                scorecard={
                    "status": "blocked",
                    "overall_claim": "blocked",
                    "forbidden_claims": ["apply_ready"],
                    "structural_qa": {"status": "blocked"},
                },
            )

            plan = create_apply_plan(delivery, project)

            self.assertTrue(plan["blocked_by_evaluation_scorecard"])

    def test_apply_plan_blocks_missing_apply_signoff_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, delivery = _write_apply_delivery(
                Path(directory),
                scorecard={"overall_claim": "apply_ready", "forbidden_claims": []},
                signoff={"status": "requires_follow_up", "apply_authorized": False},
            )

            plan = create_apply_plan(delivery, project)

            self.assertTrue(plan["blocked_by_signoff"])

    def test_delivery_decision_surfaces_scorecard_and_signoff_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, delivery = _write_apply_delivery(
                Path(directory),
                scorecard={
                    "status": "blocked",
                    "overall_claim": "blocked",
                    "forbidden_claims": ["apply_ready"],
                    "structural_qa": {"status": "blocked"},
                },
                signoff={"status": "requires_follow_up", "apply_authorized": False},
            )

            decision = create_delivery_decision_report(delivery, project)

            self.assertIn("evaluation_scorecard", {item["type"] for item in decision["decisions"]})
            self.assertIn("signoff", {item["type"] for item in decision["decisions"]})

    def test_delivery_package_includes_human_review_claim_and_signoff_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = _make_json_project(root)
            initialized = initialize_project(project, "en-US", ["locales/en-US.json"], ["zh-CN"])
            state = Path(initialized["state_directory"])
            _build_scorecard_state(state, review_evidence="E2_bilingual_human_spot_check")
            build_claim_acceptance_decision(state, requested_claims=["review_complete"])
            create_signoff_record(state, _signoff_request(delivery=True))
            staging = root / "staging"
            staged = staging / "locales" / "zh-CN.json"
            staged.parent.mkdir(parents=True)
            staged.write_text('{"start": "开始游戏"}\n', encoding="utf-8")

            packaged = package_delivery(state, staging, root / "deliveries", [], "draft_package", "human-review-delivery-001")
            delivery = Path(packaged["delivery_directory"])

            self.assertEqual(packaged["manifest"]["assets"]["human_review_evidence"], "human-review-evidence.jsonl")
            self.assertEqual(packaged["manifest"]["assets"]["claim_acceptance_decision"], "claim-acceptance-decision.json")
            self.assertEqual(packaged["manifest"]["assets"]["signoff_record"], "signoff-record.json")
            self.assertTrue((delivery / "human-review-evidence.jsonl").is_file())

    def test_cli_and_api_are_artifact_backed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            input_path = Path(directory) / "review.json"
            output_path = Path(directory) / "review-output.json"
            _build_scorecard_state(state)
            write_json(input_path, _human_review_record("bilingual_reviewer", "E2_bilingual_human_spot_check", "full_run"))

            self.assertEqual(cli_main(["record-human-review", state.as_posix(), "--input", input_path.as_posix(), "--output", output_path.as_posix()]), 0)
            self.assertTrue((state / "human-review-evidence.jsonl").is_file())

            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                claim_status, claim_payload = _http_post_json(
                    host,
                    port,
                    "/api/claim-acceptance-decision",
                    {"state_dir": state.as_posix(), "claims": ["review_ready"]},
                )
                signoff_status, signoff_payload = _http_post_json(
                    host,
                    port,
                    "/api/signoff-record",
                    {"state_dir": state.as_posix(), "signoff": _signoff_request(delivery=True)},
                )
                get_status, body = _http_get(host, port, f"/api/human-review-evidence?state_dir={state.as_posix()}")
                self.assertEqual(claim_status, 200)
                self.assertEqual(signoff_status, 200)
                self.assertEqual(get_status, 200)
                self.assertEqual(claim_payload["claim_acceptance_decision"]["schema"], "localize-anything-claim-acceptance-decision-v1")
                self.assertEqual(signoff_payload["signoff_record"]["schema"], "localize-anything-signoff-record-v1")
                self.assertEqual(len(json.loads(body)["human_review_evidence"]), 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class WorkbenchReviewClaimQueueTests(unittest.TestCase):
    def test_review_queue_includes_human_review_required_when_e2_to_e4_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)

            queue = build_workbench_review_queue(state)

            assert_protocol_schema(self, "workbench-review-queue", queue)
            item_types = {item["item_type"] for item in queue["items"]}
            self.assertIn("human_review_required", item_types)
            self.assertIn("native_review_required", item_types)
            self.assertIn("professional_review_required", item_types)

    def test_review_queue_includes_stale_review_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, review_evidence="E2_bilingual_human_spot_check")
            _write_artifact_state_with_status(state, "human_review_evidence", "stale")

            queue = build_workbench_review_queue(state)

            stale_items = [item for item in queue["items"] if item["item_type"] == "stale_review_evidence"]
            self.assertTrue(stale_items)
            self.assertTrue(stale_items[0]["stale_evidence_involved"])

    def test_claim_queue_preserves_forbidden_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, provider_status="not_run", provider_actual="none")

            queue = build_workbench_claim_queue(state)

            assert_protocol_schema(self, "workbench-claim-queue", queue)
            claims = {item["claim"]: item for item in queue["claims"]}
            self.assertEqual(claims["provider_backed_quality"]["current_status"], "blocked")
            self.assertFalse(claims["provider_backed_quality"]["can_be_accepted"])

    def test_claim_queue_marks_full_coverage_not_acceptable_when_forbidden(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, coverage={"coverage_mode": "source-only", "visible_ui_coverage_warning": True})

            queue = build_workbench_claim_queue(state)
            full_coverage = next(item for item in queue["claims"] if item["claim"] == "full_coverage")

            self.assertEqual(full_coverage["related_forbidden_claim"], "full_coverage")
            self.assertFalse(full_coverage["can_be_accepted"])

    def test_claim_queue_limited_scope_delivery_only_when_scorecard_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, coverage={"coverage_mode": "source-only", "visible_ui_coverage_warning": True})

            queue = build_workbench_claim_queue(state)
            limited = next(item for item in queue["claims"] if item["claim"] == "limited_scope_delivery_ready")

            self.assertTrue(limited["limited_scope_acceptance_possible"])
            self.assertTrue(limited["can_be_accepted"])

    def test_signoff_summary_does_not_authorize_apply_when_signoff_rejects_apply(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, review_evidence="E2_bilingual_human_spot_check")
            build_claim_acceptance_decision(state, requested_claims=["apply_ready"])
            _write_signoff_record(state, status="requires_follow_up", apply_authorized=False)

            summary = build_workbench_signoff_summary(state)

            assert_protocol_schema(self, "workbench-signoff-summary", summary)
            self.assertFalse(summary["apply_authorized"])

    def test_signoff_summary_warns_when_signoff_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, review_evidence="E2_bilingual_human_spot_check")
            build_claim_acceptance_decision(state, requested_claims=["apply_ready"])
            _write_signoff_record(state, status="accepted", apply_authorized=True)
            _write_artifact_state_with_status(state, "signoff_record", "stale")

            summary = build_workbench_signoff_summary(state)

            self.assertFalse(summary["apply_authorized"])
            self.assertTrue(summary["stale_or_superseded_signoff_warnings"])

    def test_queues_do_not_infer_e2_to_e4_from_project_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _write_scorecard_state(state)
            record_human_review_evidence(state, _human_review_record("project_owner", "E2_bilingual_human_spot_check", "full_run"))
            build_evaluation_scorecard(state, coverage_diagnostics={"coverage_mode": "source-plus-merged-overlay"})

            queue = build_workbench_review_queue(state)

            self.assertIn("human_review_required", {item["item_type"] for item in queue["items"]})

    def test_pending_required_repairs_appear_in_review_queue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, pending_required_repairs=1)
            write_json(
                state / "repair-request.json",
                {
                    "protocol_version": "0.1",
                    "schema": "localize-anything-repair-request-v1",
                    "summary": {"request_count": 1, "human_confirmation_required_count": 0, "provider_or_model_required_count": 1},
                    "requests": [{"repair_id": "repair-s1", "segment_id": "s1", "human_confirmation_required": False}],
                },
            )

            queue = build_workbench_review_queue(state)

            item = next(item for item in queue["items"] if item["item_type"] == "pending_repair")
            self.assertIn("s1", item["affected_segment_ids"])

    def test_blocked_handoff_appears_in_review_queue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, unresolved_question_count=1)

            queue = build_workbench_review_queue(state)

            self.assertIn("blocked_handoff", {item["item_type"] for item in queue["items"]})

    def test_delivery_package_references_workbench_queue_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = _make_json_project(root)
            initialized = initialize_project(project, "en-US", ["locales/en-US.json"], ["zh-CN"])
            state = Path(initialized["state_directory"])
            _build_scorecard_state(state)
            build_workbench_review_queue(state)
            build_workbench_claim_queue(state)
            build_workbench_signoff_summary(state)
            staging = root / "staging"
            staged = staging / "locales" / "zh-CN.json"
            staged.parent.mkdir(parents=True)
            staged.write_text('{"start": "开始游戏"}\n', encoding="utf-8")

            packaged = package_delivery(state, staging, root / "deliveries", [], "draft_package", "workbench-queue-delivery-001")

            assets = packaged["manifest"]["assets"]
            self.assertEqual(assets["workbench_review_queue"], "workbench-review-queue.json")
            self.assertEqual(assets["workbench_claim_queue"], "workbench-claim-queue.json")
            self.assertEqual(assets["workbench_signoff_summary"], "workbench-signoff-summary.json")

    def test_run_summary_references_workbench_queue_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = _make_json_project(root)
            initialized = initialize_project(project, "en-US", ["locales/en-US.json"], ["zh-CN"])
            state = Path(initialized["state_directory"])
            _build_scorecard_state(state)
            build_workbench_review_queue(state)
            build_workbench_claim_queue(state)
            build_workbench_signoff_summary(state)

            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                ["locales/en-US.json"],
                output_root=root / "runs",
                run_id="workbench-queue-summary-001",
                synthetic_draft=True,
            )

            self.assertTrue(result["summary"]["workbench_review_queue_present"])
            self.assertIn("workbench_review_queue", result["artifacts"])

    def test_cli_commands_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            review_output = Path(directory) / "review-queue.json"
            claim_output = Path(directory) / "claim-queue.json"
            signoff_output = Path(directory) / "signoff-summary.json"

            self.assertEqual(cli_main(["workbench-review-queue", state.as_posix(), "--output", review_output.as_posix()]), 0)
            self.assertEqual(cli_main(["workbench-claim-queue", state.as_posix(), "--output", claim_output.as_posix()]), 0)
            self.assertEqual(cli_main(["workbench-signoff-summary", state.as_posix(), "--output", signoff_output.as_posix()]), 0)

            self.assertEqual(read_json(review_output)["schema"], "localize-anything-workbench-review-queue-v1")
            self.assertEqual(read_json(claim_output)["schema"], "localize-anything-workbench-claim-queue-v1")
            self.assertEqual(read_json(signoff_output)["schema"], "localize-anything-workbench-signoff-summary-v1")

    def test_api_exposes_workbench_queue_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            build_workbench_review_queue(state)
            build_workbench_claim_queue(state)
            build_workbench_signoff_summary(state)
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                review_status, review_body = _http_get(host, port, f"/api/workbench-review-queue?state_dir={state.as_posix()}")
                claim_status, claim_body = _http_get(host, port, f"/api/workbench-claim-queue?state_dir={state.as_posix()}")
                signoff_status, signoff_body = _http_get(host, port, f"/api/workbench-signoff-summary?state_dir={state.as_posix()}")
                self.assertEqual(review_status, 200)
                self.assertEqual(claim_status, 200)
                self.assertEqual(signoff_status, 200)
                self.assertEqual(json.loads(review_body)["workbench_review_queue"]["schema"], "localize-anything-workbench-review-queue-v1")
                self.assertEqual(json.loads(claim_body)["workbench_claim_queue"]["schema"], "localize-anything-workbench-claim-queue-v1")
                self.assertEqual(json.loads(signoff_body)["workbench_signoff_summary"]["schema"], "localize-anything-workbench-signoff-summary-v1")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


class WorkbenchActionSurfaceTests(unittest.TestCase):
    def test_action_records_human_review_evidence_through_runtime_writer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)

            result = perform_workbench_action(
                state,
                {
                    "action_id": "action-review-e2",
                    "action_type": "record_human_review_evidence",
                    "actor_role": "bilingual_reviewer",
                    "actor_reference": "reviewer@example.com",
                    "created_at": "2026-06-28T00:00:00Z",
                    "payload": {"evidence": _human_review_record("bilingual_reviewer", "E2_bilingual_human_spot_check", "full_run")},
                },
            )

            assert_protocol_schema(self, "workbench-action-result", result)
            self.assertEqual(result["outcome"], "accepted")
            self.assertEqual(read_human_review_evidence(state)[0]["effective_evidence_levels"], ["E2_bilingual_human_spot_check"])

    def test_action_accepts_claim_only_when_runtime_allows_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, review_evidence="E2_bilingual_human_spot_check")

            result = perform_workbench_action(
                state,
                {
                    "action_type": "accept_claim",
                    "actor_role": "project_owner",
                    "payload": {"claim": "review_ready"},
                },
            )

            self.assertEqual(result["outcome"], "accepted")
            self.assertIn("review_ready", read_json(state / "claim-acceptance-decision.json")["accepted_claims"])

    def test_action_rejects_provider_backed_claim_when_provider_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, provider_status="not_run", provider_actual="none")

            result = perform_workbench_action(
                state,
                {
                    "action_type": "accept_claim",
                    "actor_role": "project_owner",
                    "payload": {"claim": "provider_backed_quality"},
                },
            )

            decision = read_json(state / "claim-acceptance-decision.json")
            self.assertEqual(result["outcome"], "blocked")
            self.assertIn("provider_backed_quality", decision["forbidden_claims_remaining"])

    def test_action_rejects_full_coverage_claim_when_coverage_is_source_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, coverage={"coverage_mode": "source-only", "visible_ui_coverage_warning": True})

            result = perform_workbench_action(
                state,
                {
                    "action_type": "accept_claim",
                    "actor_role": "project_owner",
                    "payload": {"claim": "full_coverage"},
                },
            )

            self.assertEqual(result["outcome"], "blocked")
            self.assertIn("full_coverage", read_json(state / "claim-acceptance-decision.json")["forbidden_claims_remaining"])

    def test_acknowledging_forbidden_claim_does_not_remove_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, provider_status="not_run", provider_actual="none")

            result = perform_workbench_action(
                state,
                {
                    "action_type": "acknowledge_forbidden_claim",
                    "actor_role": "project_owner",
                    "payload": {"claim": "provider_backed_quality"},
                },
            )

            self.assertEqual(result["outcome"], "accepted")
            self.assertIn("provider_backed_quality", read_json(state / "evaluation-scorecard.json")["forbidden_claims"])

    def test_workbench_signoff_cannot_authorize_apply_when_scorecard_forbids_apply_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            perform_workbench_action(state, {"action_type": "accept_claim", "actor_role": "project_owner", "payload": {"claim": "review_ready"}})

            result = perform_workbench_action(
                state,
                {
                    "action_type": "create_signoff",
                    "actor_role": "project_owner",
                    "payload": {"signoff": _signoff_request(apply=True)},
                },
            )

            signoff = read_json(state / "signoff-record.json")
            self.assertEqual(result["outcome"], "requires_follow_up")
            self.assertFalse(signoff["apply_authorized"])

    def test_project_owner_signoff_action_does_not_create_e2_to_e4(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)

            perform_workbench_action(
                state,
                {
                    "action_type": "create_signoff",
                    "actor_role": "project_owner",
                    "payload": {"signoff": _signoff_request(delivery=True)},
                },
            )

            scorecard = read_json(state / "evaluation-scorecard.json")
            self.assertEqual(scorecard["evidence_level"]["levels"]["E2_bilingual_human_spot_check"]["status"], "not_provided")
            self.assertFalse((state / "human-review-evidence.jsonl").is_file())

    def test_rejected_signoff_blocks_delivery_and_apply_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, review_evidence="E2_bilingual_human_spot_check")
            build_claim_acceptance_decision(state, requested_claims=["review_ready"])

            result = perform_workbench_action(
                state,
                {
                    "action_type": "reject_signoff",
                    "actor_role": "project_owner",
                    "payload": {"signoff": _signoff_request(delivery=True, apply=True)},
                },
            )

            signoff = read_json(state / "signoff-record.json")
            self.assertEqual(result["outcome"], "rejected")
            self.assertEqual(signoff["status"], "rejected")
            self.assertFalse(signoff["delivery_authorized"])
            self.assertFalse(signoff["apply_authorized"])

    def test_action_log_records_accepted_rejected_and_blocked_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, provider_status="not_run", provider_actual="none")
            perform_workbench_action(state, {"action_type": "acknowledge_limitation", "actor_role": "project_owner", "payload": {"claim": "draft_only"}})
            perform_workbench_action(state, {"action_type": "accept_claim", "actor_role": "project_owner", "payload": {"claim": "provider_backed_quality"}})
            perform_workbench_action(state, {"action_type": "reject_signoff", "actor_role": "project_owner", "payload": {"signoff": _signoff_request(delivery=True)}})

            log = read_workbench_action_log(state)

            assert_protocol_schema(self, "workbench-action-log", log[0])
            self.assertEqual([item["outcome"] for item in log], ["accepted", "blocked", "rejected"])

    def test_action_triggers_regeneration_of_queue_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)

            result = perform_workbench_action(
                state,
                {
                    "action_type": "record_human_review_evidence",
                    "actor_role": "bilingual_reviewer",
                    "payload": {"evidence": _human_review_record("bilingual_reviewer", "E2_bilingual_human_spot_check", "full_run")},
                },
            )

            self.assertIn("workbench-review-queue.json", result["refreshed_artifacts"])
            self.assertTrue((state / "workbench-review-queue.json").is_file())
            self.assertTrue((state / "workbench-claim-queue.json").is_file())
            self.assertTrue((state / "workbench-signoff-summary.json").is_file())

    def test_queue_items_cannot_be_marked_addressed_while_underlying_artifacts_still_require_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            queue = build_workbench_review_queue(state)
            item_id = next(item["item_id"] for item in queue["items"] if item["item_type"] == "human_review_required")

            result = perform_workbench_action(
                state,
                {
                    "action_type": "mark_queue_item_addressed",
                    "actor_role": "project_owner",
                    "payload": {"queue_item_id": item_id},
                },
            )

            self.assertEqual(result["outcome"], "blocked")
            refreshed = read_json(state / "workbench-review-queue.json")
            self.assertIn(item_id, {item["item_id"] for item in refreshed["items"]})

    def test_api_workbench_action_post_does_not_call_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                with mock.patch("runtime.localize_anything.provider.generate_handoff_with_http_provider") as provider_call:
                    status, payload = _http_post_json(
                        host,
                        port,
                        "/api/workbench-action",
                        {
                            "state_dir": state.as_posix(),
                            "action": {
                                "action_type": "accept_claim",
                                "actor_role": "project_owner",
                                "payload": {"claim": "review_ready"},
                            },
                        },
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(payload["workbench_action_result"]["schema"], "localize-anything-workbench-action-result-v1")
                    provider_call.assert_not_called()
                log_status, log_body = _http_get(host, port, f"/api/workbench-action-log?state_dir={state.as_posix()}")
                self.assertEqual(log_status, 200)
                self.assertEqual(len(json.loads(log_body)["workbench_action_log"]), 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_cli_action_command_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            action_path = Path(directory) / "action.json"
            output_path = Path(directory) / "action-output.json"
            log_output = Path(directory) / "action-log.json"
            write_json(
                action_path,
                {
                    "action_id": "fixed-action-id",
                    "action_type": "acknowledge_limitation",
                    "actor_role": "project_owner",
                    "created_at": "2026-06-28T00:00:00Z",
                    "payload": {"claim": "draft_only"},
                },
            )

            self.assertEqual(cli_main(["workbench-action", state.as_posix(), "--input", action_path.as_posix(), "--output", output_path.as_posix()]), 0)
            self.assertEqual(cli_main(["workbench-action-log", state.as_posix(), "--output", log_output.as_posix()]), 0)

            self.assertEqual(read_json(output_path)["action_id"], "fixed-action-id")
            self.assertEqual(read_json(log_output)["records"][0]["created_at"], "2026-06-28T00:00:00Z")

    def test_delivery_package_and_run_summary_reference_workbench_action_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = _make_json_project(root)
            initialized = initialize_project(project, "en-US", ["locales/en-US.json"], ["zh-CN"])
            state = Path(initialized["state_directory"])
            _build_scorecard_state(state)
            perform_workbench_action(state, {"action_type": "acknowledge_limitation", "actor_role": "project_owner", "payload": {"claim": "draft_only"}})
            staging = root / "staging"
            staged = staging / "locales" / "zh-CN.json"
            staged.parent.mkdir(parents=True)
            staged.write_text('{"start": "开始游戏"}\n', encoding="utf-8")

            packaged = package_delivery(state, staging, root / "deliveries", [], "draft_package", "workbench-action-delivery-001")
            result = run_localize(
                project,
                "en-US",
                ["zh-CN"],
                ["locales/en-US.json"],
                output_root=root / "runs",
                run_id="workbench-action-summary-001",
                synthetic_draft=True,
            )

            self.assertEqual(packaged["manifest"]["assets"]["workbench_action_log"], "workbench-action-log.jsonl")
            self.assertEqual(packaged["manifest"]["assets"]["workbench_action_result"], "workbench-action-result.json")
            self.assertTrue(result["summary"]["workbench_action_log_present"])
            self.assertIn("workbench_action_result", result["artifacts"])


class WorkbenchReviewConsoleTests(unittest.TestCase):
    def test_console_page_renders_evaluation_scorecard_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, review_evidence="E2_bilingual_human_spot_check")
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                status, body = _http_get(host, port, f"/workbench-review-console?state_dir={state.as_posix()}")
                self.assertEqual(status, 200)
                self.assertIn("Evaluation Scorecard", body)
                self.assertIn("overall_claim", body)
                self.assertIn("apply_ready", body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_console_renders_review_queue_items(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            build_workbench_review_queue(state)

            html = render_workbench_console_html(state)

            self.assertIn("Workbench Review Queue", html)
            self.assertIn("human_review_required", html)

    def test_console_renders_claim_queue_and_forbidden_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, provider_status="not_run", provider_actual="none")
            build_workbench_claim_queue(state)

            html = render_workbench_console_html(state)

            self.assertIn("Workbench Claim Queue", html)
            self.assertIn("Forbidden Claims", html)
            self.assertIn("provider_backed_quality", html)

    def test_console_renders_signoff_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, review_evidence="E2_bilingual_human_spot_check")
            build_claim_acceptance_decision(state, requested_claims=["review_ready"])
            create_signoff_record(state, _signoff_request(delivery=True))
            build_workbench_signoff_summary(state)

            html = render_workbench_console_html(state)

            self.assertIn("Workbench Signoff Summary", html)
            self.assertIn("delivery_authorized", html)

    def test_console_renders_action_log_and_action_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            perform_workbench_action(
                state,
                {
                    "action_id": "console-action-001",
                    "action_type": "acknowledge_limitation",
                    "actor_role": "project_owner",
                    "payload": {"claim": "draft_only"},
                },
            )

            html = render_workbench_console_html(state)

            self.assertIn("Action Log", html)
            self.assertIn("Action Result", html)
            self.assertIn("console-action-001", html)

    def test_console_action_form_delegates_to_workbench_action_endpoint(self) -> None:
        html = render_workbench_console_html()

        self.assertIn('fetch("/api/workbench-action"', html)
        self.assertIn("workbench-action-result-data", html)
        self.assertIn("Submit Runtime Action", html)
        self.assertIn("Action JSON", html)

    def test_console_does_not_mark_queue_item_resolved_without_runtime_artifact_update(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            queue = build_workbench_review_queue(state)
            item_id = next(item["item_id"] for item in queue["items"] if item["item_type"] == "human_review_required")
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                status, payload = _http_post_json(
                    host,
                    port,
                    "/api/workbench-action",
                    {
                        "state_dir": state.as_posix(),
                        "action": {
                            "action_type": "mark_queue_item_addressed",
                            "actor_role": "project_owner",
                            "payload": {"queue_item_id": item_id},
                        },
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(payload["workbench_action_result"]["outcome"], "blocked")
                page_status, body = _http_get(host, port, f"/workbench-review-console?state_dir={state.as_posix()}")
                self.assertEqual(page_status, 200)
                self.assertIn(item_id, body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_forbidden_claims_remain_visible_after_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, provider_status="not_run", provider_actual="none")
            build_workbench_claim_queue(state)
            perform_workbench_action(
                state,
                {
                    "action_type": "acknowledge_forbidden_claim",
                    "actor_role": "project_owner",
                    "payload": {"claim": "provider_backed_quality"},
                },
            )

            html = render_workbench_console_html(state)

            self.assertIn("Forbidden Claims", html)
            self.assertIn("provider_backed_quality", html)

    def test_limited_scope_acceptance_does_not_display_global_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, coverage={"coverage_mode": "source-only", "visible_ui_coverage_warning": True})
            build_claim_acceptance_decision(
                state,
                requested_claims=["limited_scope_delivery_ready"],
                accepted_risk={"accepts_limitations": True},
            )
            build_workbench_claim_queue(state)

            html = render_workbench_console_html(state)

            self.assertIn("limited_scope_delivery_ready", html)
            self.assertIn("full_coverage", html)
            self.assertNotIn('"overall_claim": "delivery_ready"', html)

    def test_owner_signoff_does_not_display_e2_to_e4_review_level(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            create_signoff_record(state, _signoff_request(delivery=True))
            build_workbench_signoff_summary(state)

            html = render_workbench_console_html(state)

            self.assertIn("E2_bilingual_human_spot_check", html)
            self.assertIn("not_provided", html)

    def test_stale_evidence_warnings_are_visible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, artifact_status="stale", stale_count=1)
            write_json(
                state / "artifact-state.json",
                {
                    "protocol_version": "0.1",
                    "schema": "localize-anything-artifact-state-v1",
                    "status": "stale",
                    "safe_to_continue": False,
                    "summary": {"stale_count": 1, "blocked_count": 0},
                    "artifacts": [
                        {
                            "artifact_path": "localization-brief.json",
                            "artifact_type": "localization_brief",
                            "status": "stale",
                            "blocking_reason": "localization_brief_changed",
                        }
                    ],
                },
            )

            html = render_workbench_console_html(state)

            self.assertIn("Stale Artifact Warnings", html)
            self.assertIn("localization-brief.json", html)

    def test_pending_repairs_and_blocked_handoff_are_visible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, pending_required_repairs=1, unresolved_question_count=1)
            write_json(
                state / "repair-request.json",
                {
                    "protocol_version": "0.1",
                    "schema": "localize-anything-repair-request-v1",
                    "summary": {"request_count": 1, "human_confirmation_required_count": 0, "provider_or_model_required_count": 1},
                    "requests": [{"repair_id": "repair-s1", "segment_id": "s1", "human_confirmation_required": False}],
                },
            )

            html = render_workbench_console_html(state)

            self.assertIn("Pending Repairs", html)
            self.assertIn("repair-s1", html)
            self.assertIn("Generation Handoff", html)
            self.assertIn("handoff_allowed", html)
            self.assertIn("false", html)

    def test_console_api_does_not_call_providers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                with mock.patch("runtime.localize_anything.provider.generate_handoff_with_http_provider") as provider_call:
                    status, body = _http_get(host, port, f"/workbench-review-console?state_dir={state.as_posix()}")
                    self.assertEqual(status, 200)
                    api_status, api_body = _http_get(host, port, f"/api/workbench-console?state_dir={state.as_posix()}")
                    self.assertEqual(api_status, 200)
                    self.assertEqual(json.loads(api_body)["workbench_console"]["schema"], "localize-anything-workbench-console-view-v1")
                    provider_call.assert_not_called()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_action_result_endpoint_returns_artifact_backed_runtime_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state)
            perform_workbench_action(
                state,
                {
                    "action_id": "console-result-001",
                    "action_type": "acknowledge_limitation",
                    "actor_role": "project_owner",
                    "payload": {"claim": "draft_only"},
                },
            )
            server = create_ui_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address[:2]
            try:
                status, body = _http_get(host, port, f"/api/workbench-action-result?state_dir={state.as_posix()}")
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["workbench_action_result"]["action_id"], "console-result-001")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_cli_console_command_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / ".localize-anything"
            _build_scorecard_state(state, review_evidence="E2_bilingual_human_spot_check")
            first = Path(directory) / "console-1.html"
            second = Path(directory) / "console-2.html"

            self.assertEqual(cli_main(["workbench-console", state.as_posix(), "--output", first.as_posix()]), 0)
            self.assertEqual(cli_main(["workbench-console", state.as_posix(), "--output", second.as_posix()]), 0)

            self.assertEqual(first.read_text(encoding="utf-8"), second.read_text(encoding="utf-8"))
            self.assertIn("Workbench Review Console", first.read_text(encoding="utf-8"))


def _build_scorecard_state(
    state: Path,
    *,
    coverage: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    _write_scorecard_state(state, **kwargs)
    coverage = {"coverage_mode": "source-plus-merged-overlay"} if coverage is None else coverage
    return build_evaluation_scorecard(
        state,
        run_id="scorecard-test-001",
        coverage_diagnostics=coverage,
    )


def _write_scorecard_state(
    state: Path,
    *,
    provider_status: str = "passed",
    provider_actual: str = "deepseek",
    term_assurance: str = "reviewed",
    high_risk_unreviewed_count: int = 0,
    artifact_status: str = "current",
    stale_count: int = 0,
    blocked_count: int = 0,
    pending_required_repairs: int = 0,
    failed_repair_qa_count: int = 0,
    delivery_status: str = "ready_no_changes",
    apply_blocked_by_stale: bool = False,
    apply_operations: list[dict[str, Any]] | None = None,
    unresolved_question_count: int = 0,
    review_evidence: str | None = None,
) -> None:
    state.mkdir(parents=True, exist_ok=True)
    write_json(
        state / "termbase-preflight-report.json",
        {
            "protocol_version": "0.1",
            "schema": "localize-anything-termbase-preflight-report-v1",
            "status": "ready",
            "terminology_assurance": term_assurance,
            "summary": {
                "conflict_count": 0,
                "high_risk_unreviewed_count": high_risk_unreviewed_count,
            },
        },
    )
    unresolved_questions = [
        {"question_id": f"bq-{index}", "status": "unresolved"}
        for index in range(unresolved_question_count)
    ]
    write_json(
        state / "blocking-questions.json",
        {
            "protocol_version": "0.1",
            "schema": "localize-anything-blocking-questions-v1",
            "summary": {"unresolved_blocking_count": unresolved_question_count},
            "questions": unresolved_questions,
        },
    )
    write_json(
        state / "resolution-options.json",
        {
            "protocol_version": "0.1",
            "schema": "localize-anything-resolution-options-v1",
            "options": [],
        },
    )
    write_json(
        state / "generation-strategy.json",
        {
            "protocol_version": "0.1",
            "schema": "localize-anything-generation-strategy-v1",
            "status": "ready",
            "generation_readiness": "ready",
        },
    )
    write_json(
        state / "generation-handoff-decision.json",
        {
            "protocol_version": "0.1",
            "schema": "localize-anything-generation-handoff-decision-v1",
            "status": "ready",
            "handoff_allowed": unresolved_question_count == 0,
            "full_quality_handoff_allowed": unresolved_question_count == 0,
            "unresolved_questions": unresolved_questions,
            "forbidden_quality_claims": [],
        },
    )
    write_json(
        state / "artifact-state.json",
        {
            "protocol_version": "0.1",
            "schema": "localize-anything-artifact-state-v1",
            "status": artifact_status,
            "safe_to_continue": artifact_status == "current" and blocked_count == 0 and stale_count == 0,
            "summary": {
                "stale_count": stale_count,
                "blocked_count": blocked_count,
            },
            "decisions": {
                "delivery_policy": "blocked" if stale_count or blocked_count else "allowed",
                "apply_policy": "blocked" if stale_count or blocked_count else "allowed",
            },
            "next_actions": [],
        },
    )
    write_json(
        state / "reuse-decision.json",
        {
            "protocol_version": "0.1",
            "schema": "localize-anything-reuse-decision-v1",
            "status": "ready",
            "decisions": {
                "generation_handoff_policy": "allowed",
                "delivery_apply_policy": "allowed",
                "review_required": False,
            },
        },
    )
    write_json(
        state / "repair-result.json",
        {
            "protocol_version": "0.1",
            "schema": "localize-anything-repair-result-v1",
            "status": "ready" if not pending_required_repairs and not failed_repair_qa_count else "blocked",
            "summary": {
                "pending_required_repair_count": pending_required_repairs,
                "pending_provider_or_model_repair_count": 0,
                "failed_qa_count": failed_repair_qa_count,
                "blocked_count": 0,
                "skipped_not_deterministic_count": 0,
            },
            "results": [],
        },
    )
    write_json(
        state / "delivery-manifest.json",
        {
            "protocol_version": "0.1",
            "run_id": "scorecard-test-001",
            "delivery_status": delivery_status,
            "outputs": [],
            "generation": {
                "provider_status": provider_status,
                "provider_actual": provider_actual,
                "apply_allowed": True,
            },
            "qa": {
                "status": "pass",
                "blocking_count": 0,
                "warning_count": 0,
                "evidence_channels": ["runtime"],
            },
            "assets": {},
        },
    )
    write_json(
        state / "delivery-decision.json",
        {
            "protocol_version": "0.1",
            "status": delivery_status,
            "summary": {"blocking_count": 0},
        },
    )
    write_json(
        state / "apply-plan.json",
        {
            "protocol_version": "0.1",
            "blocked_by_provider_status": False,
            "blocked_by_stale_artifacts": apply_blocked_by_stale,
            "operations": apply_operations or [],
        },
    )
    if review_evidence:
        role = {
            "E2_bilingual_human_spot_check": "bilingual_reviewer",
            "E3_native_language_review": "native_language_reviewer",
            "E4_professional_localization_review": "professional_localization_reviewer",
        }[review_evidence]
        write_jsonl(
            state / "human-review-evidence.jsonl",
            [
                {
                    "protocol_version": "0.1",
                    "schema": "localize-anything-human-review-evidence-v1",
                    "run_id": "scorecard-test-001",
                    "evidence_id": f"review-{review_evidence}",
                    "reviewer_role": role,
                    "status": "accepted",
                    "review_scope": {"scope_type": "full_run"},
                    "supports_evidence_levels": [review_evidence],
                    "effective_evidence_levels": [review_evidence],
                }
            ],
        )


def _human_review_record(role: str, level: str, scope_type: str) -> dict[str, Any]:
    return {
        "evidence_id": f"review-{role}-{scope_type}-{level}",
        "reviewer_role": role,
        "status": "accepted",
        "review_scope": {
            "scope_type": scope_type,
            "segments": ["s1"] if scope_type == "segment" else [],
        },
        "supports_evidence_levels": [level],
        "review_notes": "test review evidence",
    }


def _signoff_request(*, delivery: bool = False, apply: bool = False, limitations: bool = True) -> dict[str, Any]:
    return {
        "signed_by": "owner@example.com",
        "signed_role": "project_owner",
        "signoff_scope": {"scope_type": "limited", "locales": ["zh-CN"]},
        "authorizations": {"delivery": delivery, "apply": apply},
        "limitations_accepted": limitations,
    }


def _write_artifact_state_with_status(state: Path, artifact_id: str, status: str) -> None:
    artifact_state = read_json(state / "artifact-state.json") if (state / "artifact-state.json").is_file() else {}
    artifact_state.setdefault("protocol_version", "0.1")
    artifact_state.setdefault("schema", "localize-anything-artifact-state-v1")
    artifacts = [item for item in artifact_state.get("artifacts", []) if item.get("artifact_id") != artifact_id]
    artifacts.append(
        {
            "artifact_id": artifact_id,
            "artifact_path": artifact_id.replace("_", "-"),
            "artifact_type": artifact_id,
            "status": status,
            "produced_by": "test",
            "downstream_affected": [],
        }
    )
    artifact_state["artifacts"] = artifacts
    artifact_state["status"] = "blocked" if status == "blocked" else "stale" if status in {"stale", "superseded"} else artifact_state.get("status", "current")
    artifact_state["safe_to_continue"] = status not in {"stale", "superseded", "blocked"}
    write_json(state / "artifact-state.json", artifact_state)


def _write_signoff_record(
    state: Path,
    *,
    status: str = "accepted",
    delivery_authorized: bool = False,
    apply_authorized: bool = False,
) -> None:
    write_json(
        state / "signoff-record.json",
        {
            "protocol_version": "0.1",
            "schema": "localize-anything-signoff-record-v1",
            "run_id": "scorecard-test-001",
            "artifact": "signoff-record.json",
            "status": status,
            "signed_by": "owner@example.com",
            "signed_role": "project_owner",
            "signoff_scope": {"scope_type": "limited", "locales": ["zh-CN"]},
            "delivery_authorized": delivery_authorized,
            "apply_authorized": apply_authorized,
            "limitations_accepted": True,
            "forbidden_claims_remaining": [],
            "blocked_authorizations": [],
        },
    )


def _write_apply_delivery(
    root: Path,
    *,
    scorecard: dict[str, Any] | None = None,
    signoff: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    project = root / "project"
    delivery = root / "delivery"
    output = delivery / "files" / "locales" / "zh-CN.json"
    project_file = project / "locales" / "zh-CN.json"
    output.parent.mkdir(parents=True)
    project_file.parent.mkdir(parents=True)
    output.write_text('{"start": "开始"}\n', encoding="utf-8")
    project_file.write_text('{"start": "Start"}\n', encoding="utf-8")
    write_json(
        delivery / "delivery-manifest.json",
        {
            "protocol_version": "0.1",
            "run_id": "apply-gate-test-001",
            "delivery_status": "review_ready",
            "outputs": [
                {
                    "package_path": "files/locales/zh-CN.json",
                    "destination": "locales/zh-CN.json",
                    "sha256": sha256_file(output),
                    "destination_base_sha256": sha256_file(project_file),
                }
            ],
            "generation": {
                "provider_requested": "none",
                "provider_actual": "none",
                "provider_status": "not_applicable",
                "quality_claim": "not_applicable",
                "apply_allowed": True,
            },
            "qa": {"status": "pass", "blocking_count": 0, "warning_count": 0, "evidence_channels": ["runtime"]},
            "assets": {},
        },
    )
    if scorecard is not None:
        write_json(
            delivery / "evaluation-scorecard.json",
            {
                "protocol_version": "0.1",
                "schema": "localize-anything-evaluation-scorecard-v1",
                "status": scorecard.get("status", "pass_with_warnings"),
                "overall_claim": scorecard.get("overall_claim", "delivery_ready"),
                "evidence_level": {"highest_supported": "E1_automated_semantic_or_policy_review", "levels": {}},
                "structural_qa": scorecard.get("structural_qa", {}),
                "provider_status": scorecard.get("provider_status", {}),
                "handoff_readiness": scorecard.get("handoff_readiness", {}),
                "repair_readiness": scorecard.get("repair_readiness", {}),
                "forbidden_claims": scorecard.get("forbidden_claims", []),
                "recommended_next_actions": [],
                "source_artifacts": {},
            },
        )
    if signoff is not None:
        write_json(
            delivery / "signoff-record.json",
            {
                "protocol_version": "0.1",
                "schema": "localize-anything-signoff-record-v1",
                "signoff_id": "signoff-apply-gate-test",
                "status": signoff.get("status", "requires_follow_up"),
                "signed_by": "owner@example.com",
                "signed_role": "project_owner",
                "signoff_scope": {"scope_type": "limited"},
                "requested_authorizations": {"delivery": False, "apply": True},
                "delivery_authorized": False,
                "apply_authorized": signoff.get("apply_authorized", False),
                "forbidden_claims_remaining": [],
            },
        )
    return project, delivery


def _write_repair_execution_state(
    state: Path,
    requests: list[dict[str, Any]],
    generated_segments: list[dict[str, Any]] | None = None,
) -> None:
    state.mkdir(parents=True, exist_ok=True)
    write_json(
        state / "segment-regeneration-plan.json",
        {
            "protocol_version": "0.1",
            "schema": "localize-anything-segment-regeneration-plan-v1",
            "run_id": "patch-repair-test-001",
            "status": "requires_repair" if requests else "ready",
            "summary": {
                "segment_count": len(requests),
                "reuse_count": 0,
                "regenerate_count": 0,
                "re_review_count": 0,
                "targeted_repair_count": len(requests),
                "human_confirm_count": sum(bool(item.get("human_confirmation_required")) for item in requests),
                "blocked_count": 0,
                "deterministic_qa_required_count": sum(bool(item.get("deterministic_qa_required")) for item in requests),
                "pending_repair_count": len(requests),
                "generation_handoff_blocking_count": len(requests),
                "delivery_apply_blocking_count": len(requests),
            },
            "decisions": {
                "generation_handoff_policy": "blocked" if requests else "allowed",
                "delivery_apply_policy": "blocked" if requests else "allowed",
                "apply_policy": "blocked" if requests else "allowed",
                "full_quality_generation_handoff_allowed": not requests,
                "requires_deterministic_qa": any(bool(item.get("deterministic_qa_required")) for item in requests),
                "review_required": any(bool(item.get("human_confirmation_required")) for item in requests),
                "pending_required_repair_count": len(requests),
            },
            "segments": [
                {
                    "segment_id": item["segment_id"],
                    "action": "targeted_repair",
                    "repair_type": item["repair_type"],
                    "repair_id": item["repair_id"],
                    "human_confirmation_required": item.get("human_confirmation_required", False),
                    "blocks_generation_handoff": True,
                    "blocks_delivery_apply": True,
                }
                for item in requests
            ],
            "next_actions": ["Complete deterministic repair execution."],
        },
    )
    write_json(
        state / "repair-request.json",
        {
            "protocol_version": "0.1",
            "schema": "localize-anything-repair-request-v1",
            "run_id": "patch-repair-test-001",
            "status": "pending_repairs" if requests else "ready",
            "segment_regeneration_plan_path": "segment-regeneration-plan.json",
            "summary": {
                "request_count": len(requests),
                "human_confirmation_required_count": sum(bool(item.get("human_confirmation_required")) for item in requests),
                "provider_or_model_required_count": sum(bool(item.get("provider_or_model_required")) for item in requests),
            },
            "requests": requests,
        },
    )
    if generated_segments is not None:
        write_jsonl(state / "generated-segments.jsonl", generated_segments)


def _manual_repair_request(
    segment_id: str,
    repair_type: str,
    *,
    old_target: str | None = None,
    required_constraints: dict[str, Any] | None = None,
    risk_level: str = "low",
    human_confirmation_required: bool = False,
    deterministic_qa_required: bool = False,
) -> dict[str, Any]:
    request = {
        "repair_id": f"repair-{segment_id}-{repair_type}",
        "segment_id": segment_id,
        "source_artifact_refs": {"segment_regeneration_plan": "localize-anything-segment-regeneration-plan-v1"},
        "repair_type": repair_type,
        "reason": f"test_{repair_type}",
        "old_target": old_target,
        "previous_target_hash": "b" * 64 if old_target is not None else None,
        "source_hash": "a" * 64,
        "required_constraints": required_constraints or {},
        "risk_level": risk_level,
        "human_confirmation_required": human_confirmation_required,
        "deterministic_qa_required": deterministic_qa_required,
        "provider_or_model_required": repair_type in {"risk_wording_patch", "style_patch", "coverage_patch", "regenerate_segment"},
        "status": "pending_provider_or_model_repair"
        if repair_type in {"risk_wording_patch", "style_patch", "coverage_patch", "regenerate_segment"}
        else "pending_human_confirmation"
        if human_confirmation_required
        else "pending_review",
        "plan_status": "requires_repair",
    }
    return request


def _write_strategy_for_segments(state: Path, segments: list[dict[str, Any]]) -> dict[str, Any]:
    run_termbase_preflight(state, segments, source_locale="en-US", target_locale="zh-CN")
    plan = create_batch_plan(segments, "en-US", ["zh-CN"], 10)
    return write_generation_strategy(
        state,
        build_generation_strategy(state, plan, source_locale="en-US", target_locale="zh-CN"),
    )


def _seed_strategy_handoff_state(state: Path, segments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    _write_artifact_brief(state, "initial-brief")
    strategy = _write_strategy_for_segments(state, segments or [_segment("s1", "Start game")])
    build_resolution_gate(state, strategy)
    build_generation_handoff_decision(state)
    return strategy


def _seed_term_targeted_repair(state: Path) -> None:
    segment = _segment("s1", "Weight limit")
    _write_term_registry(
        state,
        [{"source_term": "Weight", "target_term": "重量", "type": "domain_term", "status": "approved", "target_locale": "zh-CN"}],
    )
    _seed_strategy_handoff_state(state, [segment])
    build_reuse_decision(state, [segment], generated_segments=[_generated_segment(segment)])
    _write_term_registry(
        state,
        [{"source_term": "Weight", "target_term": "体重", "type": "domain_term", "status": "approved", "target_locale": "zh-CN"}],
    )
    build_reuse_decision(state, [segment], generated_segments=[_generated_segment(segment)])


def _make_json_project(root: Path) -> Path:
    project = root / "project"
    locales = project / "locales"
    locales.mkdir(parents=True)
    (locales / "en-US.json").write_text(
        json.dumps({"start": "Start game", "weight": "Weight limit"}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return project


def _write_artifact_brief(state: Path, marker: str) -> None:
    state.mkdir(parents=True, exist_ok=True)
    write_json(
        state / "localization-brief.json",
        {
            "protocol_version": "0.1",
            "status": "ready",
            "document_type": marker,
            "required_human_confirmations": [],
        },
    )


def _artifact_by_id(artifact_state: dict[str, Any], artifact_id: str) -> dict[str, Any]:
    return next(item for item in artifact_state["artifacts"] if item["artifact_id"] == artifact_id)


def _sha256(path: Path) -> str:
    return sha256_file(path)


def _stale_artifact_state_document() -> dict[str, Any]:
    return {
        "protocol_version": "0.1",
        "schema": "localize-anything-artifact-state-v1",
        "run_id": "stale-delivery-001",
        "status": "stale",
        "safe_to_continue": False,
        "artifact_state_path": "artifact-state.json",
        "summary": {
            "artifact_count": 1,
            "current_count": 0,
            "missing_count": 0,
            "stale_count": 1,
            "blocked_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "requires_human_review_count": 0,
            "missing_required_count": 0,
        },
        "decisions": {
            "full_quality_generation_handoff_allowed": False,
            "delivery_apply_allowed": False,
            "delivery_policy": "blocked",
            "apply_policy": "blocked",
        },
        "artifacts": [
            {
                "artifact_id": "generation_strategy",
                "artifact_type": "generation_strategy",
                "path": "generation-strategy.json",
                "status": "stale",
                "content_hash": "a" * 64,
                "source_dependency_hashes": {},
                "produced_by": "generation_strategy",
                "produced_at": "2026-06-27T00:00:00Z",
                "supersedes": [],
                "superseded_by": [],
                "blocking_reason": "upstream_dependency_changed",
                "downstream_affected": ["generation_handoff_decision", "generated_segments", "delivery_decision"],
            }
        ],
        "stale_artifacts": [
            {
                "artifact_id": "generation_strategy",
                "artifact_type": "generation_strategy",
                "path": "generation-strategy.json",
                "status": "stale",
                "blocking_reason": "upstream_dependency_changed",
                "stale_dependency_ids": ["localization_brief_json"],
                "downstream_affected": ["generation_handoff_decision", "generated_segments", "delivery_decision"],
            }
        ],
        "blocked_artifacts": [],
        "missing_required_artifacts": [],
        "next_actions": ["Regenerate stale upstream artifacts."],
    }


def _termbase_segments() -> list[dict[str, Any]]:
    return [
        _segment("s1", "Delete account", resource_name="delete_account_button", high_risk=True),
        _segment("s2", "Delete account", resource_name="delete_account_title", high_risk=True),
        _segment("s3", "Enable SSO for NASA login"),
        _segment("s4", "National award certification improves trust", content_type="word_document_text"),
    ]


def _segment(
    segment_id: str,
    source: str,
    *,
    resource_name: str | None = None,
    content_type: str = "locale_string",
    high_risk: bool = False,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "content_type": content_type,
        "content_unit": "test:terms",
    }
    if resource_name:
        context.update(
            {
                "resource_key": f"string:{resource_name}",
                "resource_name": resource_name,
                "resource_type": "string",
            }
        )
    segment: dict[str, Any] = {
        "protocol_version": "0.1",
        "segment_id": segment_id,
        "source": source,
        "source_locale": "en-US",
        "source_path": "locales/en-US.json",
        "source_hash": "a" * 64,
        "context": context,
        "constraints": {"placeholders": [], "markup": []},
        "status": "new",
    }
    if high_risk:
        segment["ui_risk_classification"] = {
            "ui_role": ["destructive_action"],
            "risk_level": "critical",
            "review_priority": "owner_review_required",
            "classification_evidence": ["source_text_pattern"],
        }
    return segment


def _generated_segment(segment: dict[str, Any], target: str = "开始") -> dict[str, Any]:
    generated = dict(segment)
    generated["target_locale"] = "zh-CN"
    generated["target"] = target
    generated["status"] = "generated"
    generated["generation"] = {"provider": "synthetic"}
    return generated


def _write_term_registry(state: Path, rows: list[dict[str, str]]) -> None:
    state.mkdir(parents=True, exist_ok=True)
    columns = [
        "source_term",
        "target_term",
        "type",
        "status",
        "priority",
        "scope",
        "notes",
        "source_locale",
        "target_locale",
        "forbidden_targets",
        "provenance",
    ]
    with (state / "term-registry.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _write_forbidden_translations(state: Path, rows: list[dict[str, str]]) -> None:
    state.mkdir(parents=True, exist_ok=True)
    columns = [
        "source_term",
        "forbidden_target",
        "target_locale",
        "scope",
        "reason",
        "status",
        "provenance",
    ]
    with (state / "forbidden-translations.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


class ProtocolFilesTests(unittest.TestCase):
    def test_protocol_json_files_parse(self) -> None:
        root = Path(__file__).parents[1]
        paths = list((root / "protocol" / "schemas").glob("*.json"))
        paths.extend((root / "protocol" / "examples").glob("*.json"))
        paths.extend((root / "adapters").rglob("adapter.json"))
        self.assertGreater(len(paths), 5)
        for path in paths:
            with self.subTest(path=path):
                json.loads(path.read_text(encoding="utf-8"))
        schema_names = {path.name.removesuffix(".schema.json") for path in (root / "protocol" / "schemas").glob("*.json")}
        example_names = {path.stem for path in (root / "protocol" / "examples").glob("*.json")}
        self.assertEqual(schema_names, example_names)

    def test_adapter_manifests_satisfy_builtin_contract(self) -> None:
        root = Path(__file__).parents[1]
        result = validate_adapter_tree(root / "adapters")
        self.assertEqual(result["status"], "pass", result["errors"])
        self.assertGreaterEqual(result["manifests_checked"], 5)
        adapter_schema = json.loads((SCHEMA_ROOT / "adapter.schema.json").read_text(encoding="utf-8"))
        for manifest_path in (root / "adapters").rglob("adapter.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            errors = validate_document(manifest, adapter_schema, SCHEMA_ROOT)
            self.assertEqual(errors, [], f"{manifest_path}: {errors}")

    def test_public_benchmark_definition_is_pinned_and_blind(self) -> None:
        root = Path(__file__).parents[1]
        benchmark = json.loads((root / "benchmarks" / "wesnoth-south-guard" / "benchmark.json").read_text(encoding="utf-8"))
        self.assertEqual(len(benchmark["upstream"]["commit"]), 40)
        self.assertEqual(len(benchmark["upstream"]["source_template_sha256"]), 64)
        self.assertTrue(benchmark["generation_policy"]["blind"])
        self.assertIn("po/wesnoth-tsg/zh_CN.po", benchmark["generation_policy"]["forbidden_during_generation"])

    def test_android_oss_benchmark_definition_is_pinned(self) -> None:
        root = Path(__file__).parents[1]
        benchmark = json.loads((root / "benchmarks" / "android-antennapod" / "benchmark.json").read_text(encoding="utf-8"))
        self.assertEqual(benchmark["id"], "antennapod-android-strings-en-us-zh-cn")
        self.assertEqual(len(benchmark["upstream"]["commit"]), 40)
        self.assertEqual(len(benchmark["upstream"]["source_file_sha256"]), 64)
        self.assertEqual(benchmark["upstream"]["source_file"], "ui/i18n/src/main/res/values/strings.xml")
        self.assertEqual(
            benchmark["generation_policy"]["expected_target_destination"],
            "ui/i18n/src/main/res/values-zh-rCN/strings.xml",
        )
        self.assertEqual(benchmark["expected_results"]["segments"], 869)
        self.assertEqual(benchmark["expected_results"]["batches"], 44)
        self.assertEqual(benchmark["expected_results"]["qa_status"], "pass")
        self.assertEqual(benchmark["expected_results"]["qa_warnings"], 0)
        self.assertIn("core.android-strings", benchmark["adapters"])

    def test_ios_oss_benchmark_definition_is_pinned(self) -> None:
        root = Path(__file__).parents[1]
        benchmark = json.loads((root / "benchmarks" / "ios-signal" / "benchmark.json").read_text(encoding="utf-8"))
        self.assertEqual(benchmark["id"], "signal-ios-localizable-en-us-zh-cn")
        self.assertEqual(len(benchmark["upstream"]["commit"]), 40)
        self.assertEqual(len(benchmark["upstream"]["source_file_sha256"]), 64)
        self.assertEqual(benchmark["upstream"]["source_file"], "Signal/translations/en.lproj/Localizable.strings")
        self.assertEqual(
            benchmark["generation_policy"]["expected_target_destination"],
            "Signal/translations/zh-Hans.lproj/Localizable.strings",
        )
        self.assertEqual(benchmark["expected_results"]["segments"], 3486)
        self.assertEqual(benchmark["expected_results"]["batches"], 175)
        self.assertEqual(benchmark["expected_results"]["qa_status"], "pass")
        self.assertEqual(benchmark["expected_results"]["qa_warnings"], 0)
        self.assertIn("core.ios-strings", benchmark["adapters"])

    def test_xcstrings_oss_benchmark_definition_is_pinned(self) -> None:
        root = Path(__file__).parents[1]
        benchmark = json.loads((root / "benchmarks" / "ios-icecubes-xcstrings" / "benchmark.json").read_text(encoding="utf-8"))
        self.assertEqual(benchmark["id"], "icecubes-ios-xcstrings-en-us-zh-cn")
        self.assertEqual(len(benchmark["upstream"]["commit"]), 40)
        self.assertEqual(len(benchmark["upstream"]["source_file_sha256"]), 64)
        self.assertEqual(benchmark["upstream"]["source_file"], "IceCubesApp/Resources/Localization/Localizable.xcstrings")
        self.assertEqual(
            benchmark["generation_policy"]["expected_target_destination"],
            "IceCubesApp/Resources/Localization/Localizable.xcstrings",
        )
        self.assertEqual(benchmark["expected_results"]["segments"], 747)
        self.assertEqual(benchmark["expected_results"]["batches"], 38)
        self.assertEqual(benchmark["expected_results"]["qa_status"], "pass")
        self.assertEqual(benchmark["expected_results"]["qa_warnings"], 0)
        self.assertIn("core.xcstrings", benchmark["adapters"])

    def test_protocol_examples_validate_against_schemas(self) -> None:
        root = Path(__file__).parents[1]
        result = validate_protocol_tree(root / "protocol")
        self.assertEqual(result["status"], "pass", result["errors"])
        self.assertEqual(result["schemas_checked"], 46)


class V021ModeSystemBenchmarkTests(unittest.TestCase):
    def test_v021_mode_system_benchmark_passes_with_executable_assertions(self) -> None:
        benchmark = _load_v021_mode_system_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = benchmark.run_benchmark(root / "work", root / "report")

            self.assertEqual(report["status"], "pass", report["failed_checks"])
            self.assertEqual(report["verdict"], "PASS: v0.2.1 obsolete preservation verified")
            self.assertTrue((root / "report" / "report.json").is_file())
            self.assertTrue((root / "report" / "report.md").is_file())

            blind = report["modes"]["blind_benchmark"]
            maintenance = report["modes"]["existing_locale_maintenance"]
            greenfield = report["modes"]["greenfield_localization"]
            rewrite = report["modes"]["rewrite_or_harmonization"]

            self.assertEqual(blind["generated_segment_count"], blind["source_segment_count"])
            self.assertTrue(blind["leakage_check"]["pass"], blind["leakage_check"])
            self.assertEqual(maintenance["preserved_segment_count"], 10)
            self.assertEqual(maintenance["generated_segment_count"], 2)
            self.assertEqual(maintenance["stale_segment_count"], 1)
            self.assertEqual(maintenance["missing_segment_count"], 1)
            self.assertEqual(maintenance["obsolete_segment_count"], 2)
            obsolete = maintenance["obsolete_preservation_check"]
            self.assertTrue(obsolete["pass"], obsolete)
            self.assertTrue(obsolete["detected_as_obsolete"])
            self.assertTrue(obsolete["present_in_original_target"])
            self.assertTrue(obsolete["present_in_staged_target"])
            self.assertTrue(obsolete["present_after_apply_to_copy"])
            self.assertFalse(obsolete["deleted_by_apply_plan"])
            self.assertFalse(obsolete["generation_facing_leakage"])
            self.assertTrue(obsolete["requires_owner_review"])
            self.assertTrue(obsolete["not_counted_as_generated"])
            self.assertEqual(report["obsolete_preservation_check"]["obsolete_key"], "legacy_removed_key")
            self.assertLess(maintenance["generated_segment_count"], blind["generated_segment_count"])
            self.assertFalse(greenfield["existing_target_detected"])
            self.assertEqual(rewrite["explicit_rewrite_count"], rewrite["source_segment_count"])
            self.assertTrue(rewrite["obsolete_preservation_check"]["present_after_apply_to_copy"])
            self.assertTrue(report["same_project_behavior_difference"]["pass"])
            self.assertTrue(all(check["pass"] for check in report["negative_checks"]))

    def test_v021_mode_system_negative_validators_fail_closed(self) -> None:
        benchmark = _load_v021_mode_system_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            leaky = root / "leaky-work-packet.json"
            leaky.write_text(json.dumps({"target": benchmark.SENTINEL}, ensure_ascii=False), encoding="utf-8")

            leakage = benchmark.validate_no_leakage([leaky.as_posix()], [benchmark.SENTINEL])
            self.assertFalse(leakage["pass"])
            self.assertEqual(leakage["matches"][0]["text"], benchmark.SENTINEL)

            mass_rewrite = benchmark.validate_maintenance_not_mass_rewrite(
                {"summary": {"source_segment_count": 12, "candidate_segment_count": 12, "preserved_segment_count": 0}}
            )
            self.assertFalse(mass_rewrite["pass"])
            self.assertIn("mass rewrite", mass_rewrite["message"])

            original = root / "original.xml"
            staged = root / "staged.xml"
            applied = root / "applied.xml"
            original.write_text(
                f'<resources><string name="{benchmark.OBSOLETE_KEY}">{benchmark.OBSOLETE_TEXT}</string></resources>\n',
                encoding="utf-8",
            )
            staged.write_text("<resources></resources>\n", encoding="utf-8")
            applied.write_text("<resources></resources>\n", encoding="utf-8")
            reference_plan = {
                "obsolete_references": [
                    {
                        "identity": benchmark.OBSOLETE_IDENTITY,
                        "resource_key": benchmark.OBSOLETE_RESOURCE_KEY,
                    }
                ]
            }
            delivery_decision = {
                "decisions": [
                    {
                        "type": "obsolete_target_reference",
                        "status": "requires_review",
                        "evidence": {"obsolete_references": reference_plan["obsolete_references"]},
                    }
                ]
            }
            obsolete = benchmark.validate_obsolete_target_preservation(
                reference_plan,
                delivery_decision,
                {"operations": [{"action": "replace", "destination": benchmark.TARGET_FILE}]},
                original,
                staged,
                applied,
            )
            self.assertFalse(obsolete["pass"])
            self.assertIn("dropped obsolete target-only key legacy_removed_key", obsolete["message"])

    def test_multi_mode_staging_exposes_android_target_only_metadata(self) -> None:
        benchmark = _load_v021_mode_system_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = benchmark.run_benchmark(root / "work", root / "report")

            for mode_name in ("existing_locale_maintenance", "rewrite_or_harmonization", "greenfield_localization", "blind_benchmark"):
                mode = report["modes"][mode_name]
                staging_path = Path(mode["artifacts"]["staging_result"])
                self.assertTrue(staging_path.is_file(), f"missing staging result for {mode_name}")
                staging = json.loads(staging_path.read_text(encoding="utf-8"))

                for output in staging.get("outputs", []):
                    self.assertIn("preserved_target_only_count", output, f"{mode_name} output missing preserved_target_only_count")
                    self.assertIn("preserved_target_only_keys", output, f"{mode_name} output missing preserved_target_only_keys")
                    self.assertIsInstance(output["preserved_target_only_count"], int)
                    self.assertIsInstance(output["preserved_target_only_keys"], list)
                    self.assertEqual(len(output["preserved_target_only_keys"]), output["preserved_target_only_count"])

                if mode_name == "existing_locale_maintenance":
                    out = staging["outputs"][0]
                    self.assertGreater(out["preserved_target_only_count"], 0)
                    self.assertIn("string:legacy_removed_key", out["preserved_target_only_keys"])
                elif mode_name == "rewrite_or_harmonization":
                    out = staging["outputs"][0]
                    self.assertGreater(out["preserved_target_only_count"], 0)
                elif mode_name in ("blind_benchmark", "greenfield_localization"):
                    out = staging["outputs"][0]
                    self.assertEqual(out["preserved_target_only_count"], 0)


class V022AndroidResourceReliabilityTests(unittest.TestCase):
    def test_v022_android_resource_reliability_source_sets(self) -> None:
        benchmark = _load_v022_android_source_set_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = benchmark.run_benchmark(root / "work", root / "report")

            self.assertEqual(report["status"], "pass", report["failed_checks"])
            self.assertEqual(report["verdict"], "V0.2.2-I ANDROID SOURCE-SET / QUALIFIER DETECTION POLICY: PASS")
            check = report["source_set_qualifier_check"]
            self.assertEqual(check["source_files_detected"], 10)
            self.assertEqual(check["locale_reference_files_detected"], 3)
            self.assertTrue(check["source_set_metadata_present"])
            self.assertTrue(check["qualifier_metadata_present"])
            self.assertTrue(check["target_path_mapping_pass"])
            self.assertTrue(check["blind_reference_leakage_pass"])
            self.assertTrue(check["maintenance_existing_target_behavior_pass"])
            self.assertTrue(check["source_files_unchanged"])
            self.assertEqual(check["warnings"], [])
            self.assertTrue(all(item["pass"] for item in check["negative_checks"]))

    def test_v022_android_resource_reliability_fixture_runs(self) -> None:
        benchmark = _load_v022_android_resource_reliability_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = benchmark.run_benchmark(root / "work", root / "report")

            self.assertEqual(report["status"], "pass", report["failed_checks"])
            self.assertEqual(report["verdict"], "V0.2.2-H ANDROID ARRAY/PLURAL MARKUP BOUNDARY POLICY: PASS")
            self.assertTrue((root / "report" / "report.json").is_file())
            self.assertTrue((root / "report" / "report.md").is_file())
            self.assertEqual(report["source_segment_count"], 32)
            self.assertEqual(report["extracted_segment_count"], 32)
            self.assertEqual(report["generated_segment_count"], 24)
            self.assertEqual(report["skipped_translatable_false_count"], 1)
            self.assertTrue(report["blind_leakage_check_result"]["pass"])
            self.assertTrue(report["maintenance_preservation_check_result"]["pass"])
            limitation_ids = {item["id"] for item in report["known_limitations"]}
            self.assertNotIn("android_inline_markup_attributes_unsupported", limitation_ids)
            self.assertNotIn("android_cdata_section_normalized", limitation_ids)
            self.assertNotIn("android_resource_comments_not_preserved", limitation_ids)
            self.assertNotIn("android_escape_drift_qa_not_supported", limitation_ids)
            self.assertNotIn("android_inline_markup_skipped", limitation_ids)

    def test_v022_android_resource_reliability_preserves_placeholders_and_target_only_keys(self) -> None:
        benchmark = _load_v022_android_resource_reliability_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = benchmark.run_benchmark(root / "work", root / "report")

            self.assertTrue(report["placeholder_check_result"]["pass"])
            escape = report["escape_signature_check"]
            self.assertTrue(escape["pass"], escape)
            self.assertEqual(escape["known_limitations"], [])
            self.assertIn("\\n", escape["protected_escapes_detected"])
            self.assertIn("\\t", escape["protected_escapes_detected"])
            self.assertIn("%%", escape["protected_escapes_detected"])
            self.assertGreaterEqual(escape["missing_escape_issues"], 1)
            self.assertGreaterEqual(escape["percent_literal_issues"], 1)
            self.assertTrue(report["escape_check_result"]["pass"])
            self.assertTrue(report["xml_entity_check_result"]["pass"])
            self.assertTrue(report["string_array_check_result"]["pass"])
            self.assertTrue(report["plurals_check_result"]["pass"])
            target_only = report["target_only_preservation_check_result"]
            self.assertTrue(target_only["pass"])
            self.assertGreater(target_only["preserved_target_only_count"], 0)
            self.assertIn("string:legacy_removed_key", target_only["preserved_target_only_keys"])
            maintenance = report["maintenance_preservation_check_result"]
            self.assertFalse(maintenance["legacy_counted_as_generated"])
            self.assertIn("string:legacy_removed_key", maintenance["preserved_target_only_keys"])

    def test_v022_android_resource_reliability_inline_markup(self) -> None:
        benchmark = _load_v022_android_resource_reliability_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = benchmark.run_benchmark(root / "work", root / "report")

            inline = report["inline_markup_check"]
            self.assertTrue(inline["pass"], inline)
            self.assertIn("a", inline["supported_tags"])
            self.assertIn("b", inline["supported_tags"])
            self.assertGreaterEqual(inline["checked_segments"], 3)
            self.assertGreaterEqual(inline["markup_signature_segments"], 3)
            self.assertTrue(inline["supported_inline_markup_staged"])
            self.assertIn("b", inline["protected_tags_detected"])
            self.assertIn("a", inline["protected_tags_detected"])
            self.assertTrue(inline["href_preserved"])
            self.assertGreaterEqual(inline["missing_markup_issues"], 1)
            self.assertGreaterEqual(inline["malformed_markup_issues"], 1)
            self.assertGreaterEqual(inline["unsupported_markup_issues"], 1)
            self.assertGreaterEqual(inline["missing_attribute_issues"], 1)
            self.assertGreaterEqual(inline["url_drift_issues"], 1)
            self.assertGreaterEqual(inline["unsupported_attribute_issues"], 1)
            self.assertEqual(report["inline_html_check_result"]["status"], "pass")

    def test_v022_android_resource_reliability_complex_markup_policy(self) -> None:
        benchmark = _load_v022_android_resource_reliability_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = benchmark.run_benchmark(root / "work", root / "report")

            policy = report["complex_markup_policy_check"]
            self.assertTrue(policy["pass"], policy)
            self.assertTrue(policy["unsupported_markup_detected"])
            self.assertTrue(policy["complex_nested_detected"])
            self.assertTrue(policy["unsupported_attribute_detected"])
            self.assertTrue(policy["unsupported_tag_detected"])
            self.assertGreater(policy["owner_review_required_count"], 0)
            self.assertEqual(policy["sent_to_normal_generation_count"], 0)
            self.assertTrue(policy["preserved_without_corruption"])
            self.assertTrue(policy["staged_xml_parse"])
            self.assertTrue(all(item["pass"] for item in policy["negative_checks"]))

    def test_v022_android_resource_reliability_array_plural_markup_policy(self) -> None:
        benchmark = _load_v022_android_resource_reliability_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = benchmark.run_benchmark(root / "work", root / "report")

            policy = report["array_plural_markup_policy_check"]
            self.assertTrue(policy["pass"], policy)
            self.assertEqual(policy["supported_array_markup_segments"], 3)
            self.assertEqual(policy["supported_plural_markup_segments"], 2)
            self.assertEqual(policy["unsupported_array_items_detected"], 2)
            self.assertEqual(policy["unsupported_plural_items_detected"], 2)
            self.assertEqual(policy["owner_review_required_count"], 4)
            self.assertEqual(policy["sent_to_normal_generation_count"], 0)
            self.assertTrue(policy["existing_target_preserved_in_maintenance"])
            self.assertTrue(policy["source_fallback_preserved_without_target_use"])
            self.assertTrue(policy["supported_markup_preserved"])
            self.assertTrue(policy["placeholder_qa_preserved"])
            self.assertTrue(policy["array_item_order_preserved"])
            self.assertTrue(policy["plural_quantity_branches_preserved"])
            self.assertTrue(policy["staged_xml_parse"])
            self.assertEqual(policy["known_limitations"], [])
            self.assertTrue(all(item["pass"] for item in policy["negative_checks"]))

    def test_v022_android_resource_reliability_cdata(self) -> None:
        benchmark = _load_v022_android_resource_reliability_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = benchmark.run_benchmark(root / "work", root / "report")

            cdata = report["cdata_check"]
            self.assertTrue(cdata["pass"], cdata)
            self.assertEqual(cdata["cdata_segments"], 2)
            self.assertTrue(cdata["cdata_boundary_preserved"])
            self.assertTrue(cdata["staged_xml_parse"])
            self.assertGreaterEqual(cdata["unsafe_terminator_issues"], 1)
            self.assertGreaterEqual(cdata["boundary_missing_issues"], 1)
            self.assertTrue(cdata["unsafe_staging_blocked"])
            self.assertEqual(cdata["known_limitations"], [])
            self.assertTrue(report["cdata_check_result"]["pass"])
            self.assertEqual(report["cdata_check_result"]["status"], "pass")

    def test_v022_android_resource_reliability_comments(self) -> None:
        benchmark = _load_v022_android_resource_reliability_benchmark()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = benchmark.run_benchmark(root / "work", root / "report")

            comments = report["comment_round_trip_check"]
            self.assertTrue(comments["pass"], comments)
            self.assertGreaterEqual(comments["source_comment_count"], 3)
            self.assertGreaterEqual(comments["staged_comment_count"], comments["source_comment_count"])
            self.assertTrue(comments["resource_comments_preserved"])
            self.assertTrue(comments["string_comment_preserved"])
            self.assertTrue(comments["array_comment_preserved"])
            self.assertTrue(comments["plurals_comment_preserved"])
            self.assertTrue(comments["target_only_comment_preserved"])
            self.assertGreaterEqual(comments["missing_comment_issues"], 1)
            self.assertGreaterEqual(comments["misattached_comment_issues"], 1)
            self.assertGreaterEqual(comments["duplicate_comment_issues"], 1)
            self.assertEqual(comments["known_limitations"], [])


class SkillFilesTests(unittest.TestCase):
    def test_skill_metadata_and_progressive_disclosure_contract(self) -> None:
        skill_root = REPOSITORY_ROOT / "skills" / "localize-anything"
        text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        frontmatter = text.split("---", 2)[1]
        self.assertIn("name: localize-anything", frontmatter)
        self.assertIn("description:", frontmatter)
        self.assertLess(len(text.splitlines()), 500)
        metadata = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "Localize Anything"', metadata)
        self.assertIn("$localize-anything", metadata)
        for reference in ("workflow.md", "memory-and-context.md", "qa-and-delivery.md", "adapters.md"):
            self.assertTrue((skill_root / "references" / reference).is_file())


def _copy_json_fixture_project(project: Path, include_existing_target: bool = True) -> None:
    locales = project / "locales"
    locales.mkdir(parents=True)
    (locales / "en-US.json").write_text((FIXTURE_ROOT / "locales" / "en-US.json").read_text(encoding="utf-8"), encoding="utf-8")
    if include_existing_target:
        (locales / "zh-CN.json").write_text((FIXTURE_ROOT / "locales" / "zh-CN.json").read_text(encoding="utf-8"), encoding="utf-8")


def _http_get(host: str, port: int, path: str) -> tuple[int, str]:
    connection = http.client.HTTPConnection(host, port, timeout=10)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        return response.status, body
    finally:
        connection.close()


def _http_post_json(host: str, port: int, path: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
    connection = http.client.HTTPConnection(host, port, timeout=30)
    try:
        body = json.dumps(payload).encode("utf-8")
        connection.request("POST", path, body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        return response.status, data
    finally:
        connection.close()


def _load_v021_mode_system_benchmark():
    path = REPOSITORY_ROOT / "benchmarks" / "v021-mode-system" / "run.py"
    spec = importlib.util.spec_from_file_location("v021_mode_system_benchmark", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load benchmark module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_v022_android_resource_reliability_benchmark():
    path = REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "run.py"
    spec = importlib.util.spec_from_file_location("v022_android_resource_reliability_benchmark", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load benchmark module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_v022_android_source_set_benchmark():
    path = REPOSITORY_ROOT / "benchmarks" / "v022-android-resource-reliability" / "source_sets.py"
    spec = importlib.util.spec_from_file_location("v022_android_source_set_benchmark", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load benchmark module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_minimal_docx(path: Path, include_macro: bool = False, mixed_styles: bool = False) -> None:
    mixed = """
    <w:p>
      <w:r><w:rPr><w:b/></w:rPr><w:t>Bold text</w:t></w:r>
      <w:r><w:rPr><w:i/></w:rPr><w:t>Italic text</w:t></w:r>
    </w:p>
""" if mixed_styles else ""
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:r><w:t>Hello, {{name}}!</w:t></w:r></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table total: {{total}}</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
    <w:p><w:r><w:drawing><w:txbxContent><w:p><w:r><w:t>Box text</w:t></w:r></w:p></w:txbxContent></w:drawing></w:r></w:p>
    {mixed}
  </w:body>
</w:document>
"""
    header = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p><w:r><w:t>Header title</w:t></w:r></w:p>
</w:hdr>
"""
    footer = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p><w:r><w:t>Footer note</w:t></w:r></w:p>
</w:ftr>
"""
    footnotes = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="1"><w:p><w:r><w:t>Footnote body</w:t></w:r></w:p></w:footnote>
</w:footnotes>
"""
    comments = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:comment w:id="0"><w:p><w:r><w:t>Reviewer comment</w:t></w:r></w:p></w:comment>
</w:comments>
"""
    chart = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <c:chart><c:title><c:tx><c:rich><a:p><a:r><a:t>Chart title</a:t></a:r></a:p></c:rich></c:tx></c:title></c:chart>
</c:chartSpace>
"""
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
</w:styles>
"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    document_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdHeader" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>
  <Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
</Relationships>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/>
</Types>
"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/_rels/document.xml.rels", document_rels)
        archive.writestr("word/header1.xml", header)
        archive.writestr("word/footer1.xml", footer)
        archive.writestr("word/footnotes.xml", footnotes)
        archive.writestr("word/comments.xml", comments)
        archive.writestr("word/charts/chart1.xml", chart)
        archive.writestr("word/styles.xml", styles)
        if include_macro:
            archive.writestr("word/vbaProject.bin", b"fake-vba-project")


def _write_minimal_xlsx(path: Path) -> None:
    shared = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="6" uniqueCount="5">
  <si><t>key</t></si>
  <si><t>text</t></si>
  <si><t>menu.start</t></si>
  <si><t>Start game</t></si>
  <si><t>menu.welcome</t></si>
</sst>
"""
    sheet = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>3</v></c></row>
    <row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="s"><v>3</v></c></row>
    <row r="3"><c r="A3" t="s"><v>4</v></c><c r="B3" t="inlineStr"><is><t>Welcome, {player}!</t></is></c></row>
  </sheetData>
</worksheet>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
</Types>
"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("xl/sharedStrings.xml", shared)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


class TestV022AndroidRiskClassification(unittest.TestCase):
    """V0.2.2-J Android UI role / high-risk context classification baseline."""

    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def _write_fixture(self, content: str) -> Path:
        res_dir = self.temp / "res" / "values"
        res_dir.mkdir(parents=True)
        path = res_dir / "strings.xml"
        path.write_text(content, encoding="utf-8")
        return path

    def _extract(self, path: Path) -> list[dict[str, Any]]:
        from runtime.localize_anything.android_strings_adapter import extract_segments
        return extract_segments(path, "en-US", "res/values/strings.xml")

    def test_android_ui_risk_classification_destructive_action(self) -> None:
        content = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- Destructive account action -->
    <string name="delete_account_button">Delete account</string>
    <string name="delete_account_warning">This action cannot be undone.</string>
    <string name="confirm_remove_device">Remove this device</string>
</resources>"""
        path = self._write_fixture(content)
        segments = self._extract(path)
        by_key = {s["context"]["resource_key"]: s for s in segments}

        # Delete account button: both name and text contain "delete" → critical
        seg = by_key["string:delete_account_button"]
        self.assertIn("destructive_action", seg["ui_risk_classification"]["ui_role"])
        self.assertEqual(seg["ui_risk_classification"]["risk_level"], "critical")
        self.assertEqual(seg["ui_risk_classification"]["review_priority"], "owner_review_required")
        self.assertTrue(len(seg["ui_risk_classification"]["classification_evidence"]) > 0)
        self.assertIn("resource_name_pattern", seg["ui_risk_classification"]["classification_evidence"])
        self.assertIn("source_text_pattern", seg["ui_risk_classification"]["classification_evidence"])
        self.assertNotIn("placeholder_or_markup_protected", seg["ui_risk_classification"]["classification_evidence"])

        # Delete account warning: text matches destructive but name doesn't → high
        seg2 = by_key["string:delete_account_warning"]
        self.assertIn("destructive_action", seg2["ui_risk_classification"]["ui_role"])
        self.assertEqual(seg2["ui_risk_classification"]["risk_level"], "high")

        # Confirm remove device: name "remove" matches, text "Remove this device" also matches → critical
        seg3 = by_key["string:confirm_remove_device"]
        self.assertIn("destructive_action", seg3["ui_risk_classification"]["ui_role"])
        self.assertIn(seg3["ui_risk_classification"]["risk_level"], ("high", "critical"))
        review = seg3["ui_risk_classification"]["review_priority"]
        self.assertIn(review, ("review_recommended", "owner_review_required"))

    def test_android_ui_risk_classification_legal_and_payment(self) -> None:
        content = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="accept_terms_checkbox">I agree to the Terms of Service.</string>
    <string name="onboarding_consent">I consent to data processing.</string>
    <string name="purchase_subscription_button">Subscribe for %1$s/month</string>
    <string name="privacy_policy_link">Read our <a href="https://example.com/privacy">privacy policy</a>.</string>
    <string name="billing_error">Payment failed. Please update your billing method.</string>
</resources>"""
        path = self._write_fixture(content)
        segments = self._extract(path)
        by_key = {s["context"]["resource_key"]: s for s in segments}

        # accept_terms_checkbox: legal, high, at least review_recommended
        seg = by_key["string:accept_terms_checkbox"]
        self.assertIn("legal", seg["ui_risk_classification"]["ui_role"])
        self.assertEqual(seg["ui_risk_classification"]["risk_level"], "high")
        self.assertIn(seg["ui_risk_classification"]["review_priority"],
                      ("review_recommended", "owner_review_required"))

        # onboarding_consent: legal, high, at least owner_review_required
        seg2 = by_key["string:onboarding_consent"]
        self.assertIn("legal", seg2["ui_risk_classification"]["ui_role"])
        self.assertEqual(seg2["ui_risk_classification"]["risk_level"], "high")
        self.assertEqual(seg2["ui_risk_classification"]["review_priority"], "owner_review_required")

        # purchase_subscription_button: payment, high
        seg3 = by_key["string:purchase_subscription_button"]
        self.assertIn("payment", seg3["ui_risk_classification"]["ui_role"])
        self.assertEqual(seg3["ui_risk_classification"]["risk_level"], "high")
        self.assertIn(seg3["ui_risk_classification"]["review_priority"],
                      ("review_recommended", "owner_review_required"))
        self.assertIn("placeholder_or_markup_protected", seg3["ui_risk_classification"]["classification_evidence"])

        # privacy_policy_link: privacy, high
        seg4 = by_key["string:privacy_policy_link"]
        self.assertIn("privacy", seg4["ui_risk_classification"]["ui_role"])
        self.assertEqual(seg4["ui_risk_classification"]["risk_level"], "high")
        self.assertIn("placeholder_or_markup_protected", seg4["ui_risk_classification"]["classification_evidence"])

        # billing_error: error+payment, high
        seg5 = by_key["string:billing_error"]
        roles = seg5["ui_risk_classification"]["ui_role"]
        self.assertTrue({"error", "payment"} & set(roles))
        self.assertEqual(seg5["ui_risk_classification"]["risk_level"], "high")

    def test_android_ui_risk_classification_avoids_generic_false_positive(self) -> None:
        content = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="generic_title">Library</string>
    <string name="playlist_name">My playlist</string>
    <string name="settings_title">Settings</string>
</resources>"""
        path = self._write_fixture(content)
        segments = self._extract(path)
        by_key = {s["context"]["resource_key"]: s for s in segments}

        risky_roles = {"destructive_action", "legal", "payment", "auth", "privacy", "permission"}
        for key, safe_levels in [
            ("string:generic_title", {"low", "medium"}),
            ("string:playlist_name", {"low", "medium"}),
            ("string:settings_title", {"low", "medium"}),
        ]:
            seg = by_key[key]
            cls = seg["ui_risk_classification"]
            overlap = set(cls.get("ui_role", [])) & risky_roles
            self.assertEqual(len(overlap), 0,
                             f"{key} should not have risky roles, got {overlap}")
            self.assertIn(cls["risk_level"], safe_levels,
                          f"{key} risk_level={cls['risk_level']}, expected {safe_levels}")
            self.assertNotIn("placeholder_or_markup_protected", cls["classification_evidence"])

    def test_v022_android_resource_reliability_risk_classification(self) -> None:
        """Full benchmark fixture smoke test: high-risk classified, generics not."""
        content = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- Destructive account action -->
    <string name="delete_account_button">Delete account</string>
    <string name="delete_account_warning">This action cannot be undone.</string>
    <string name="reset_password_title">Reset password</string>
    <string name="two_factor_code_message">Enter your verification code.</string>
    <string name="allow_location_permission">Allow location access</string>
    <string name="privacy_policy_link">Read our <a href="https://example.com/privacy">privacy policy</a>.</string>
    <string name="accept_terms_checkbox">I agree to the Terms of Service.</string>
    <string name="purchase_subscription_button">Subscribe for %1$s/month</string>
    <string name="billing_error">Payment failed. Please update your billing method.</string>
    <string name="generic_title">Library</string>
    <string name="playlist_name">My playlist</string>
    <!-- Destructive account action -->
    <string name="confirm_remove_device">Remove this device</string>
    <!-- Legal consent shown during onboarding -->
    <string name="onboarding_consent">I consent to data processing.</string>
</resources>"""
        path = self._write_fixture(content)
        segments = self._extract(path)
        by_key = {s["context"]["resource_key"]: s for s in segments}

        # Negative check 1: destructive action not high risk → fail closed
        seg = by_key["string:delete_account_button"]
        self.assertIn(seg["ui_risk_classification"]["risk_level"], ("high", "critical"),
                      "destructive_account_button MUST be high or critical")
        self.assertNotEqual(seg["ui_risk_classification"]["review_priority"], "normal",
                            "destructive_account_button MUST NOT be normal priority")

        # Negative check 2: legal consent missing review priority → fail closed
        seg = by_key["string:accept_terms_checkbox"]
        self.assertIn(seg["ui_risk_classification"]["review_priority"],
                      ("review_recommended", "owner_review_required"),
                      "accept_terms_checkbox MUST be review_recommended or higher")

        seg2 = by_key["string:onboarding_consent"]
        self.assertIn(seg2["ui_risk_classification"]["review_priority"],
                      ("review_recommended", "owner_review_required"),
                      "onboarding_consent MUST be review_recommended or higher")

        # Negative check 3: generic title overclassified → fail closed
        for key in ("string:generic_title", "string:playlist_name"):
            seg = by_key[key]
            self.assertNotIn(seg["ui_risk_classification"]["risk_level"], ("high", "critical"),
                             f"{key} MUST NOT be high/critical")

        # Negative check 4: payment placeholder not review recommended → fail closed
        seg = by_key["string:purchase_subscription_button"]
        self.assertIn(seg["ui_risk_classification"]["review_priority"],
                      ("review_recommended", "owner_review_required"),
                      "purchase_subscription_button MUST be review_recommended or higher")

        # Verify all non-low-risk classified segments have evidence
        for seg in segments:
            cls = seg["ui_risk_classification"]
            if cls["risk_level"] != "low":
                self.assertTrue(len(cls["classification_evidence"]) > 0,
                                f"{seg['context']['resource_key']} risk={cls['risk_level']} missing classification_evidence")


if __name__ == "__main__":
    unittest.main()

