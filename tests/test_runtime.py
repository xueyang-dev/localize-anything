from __future__ import annotations

import json
import gettext
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from runtime.localize_anything.acceptance import create_acceptance
from runtime.localize_anything.android_strings_adapter import extract_segments as extract_android_segments
from runtime.localize_anything.android_strings_adapter import rebuild as rebuild_android_strings
from runtime.localize_anything.android_strings_adapter import stage_rebuild as stage_android_strings
from runtime.localize_anything.android_strings_adapter import target_resource_path, validate_pair as validate_android_strings
from runtime.localize_anything.apply import create_apply_plan, execute_apply, render_apply_plan_markdown
from runtime.localize_anything.contracts import validate_adapter_tree
from runtime.localize_anything.dashboard import build_delivery_dashboard, render_dashboard_markdown
from runtime.localize_anything.delivery import package_delivery
from runtime.localize_anything.generation import (
    collect_generated_handoff,
    create_draft_request,
    create_generation_handoff,
    import_generated_handoff,
    import_generated_response,
    render_draft_prompt,
    validate_generated_segments,
    write_handoff_prompts,
)
from runtime.localize_anything.gettext_adapter import extract_segments as extract_po_segments
from runtime.localize_anything.gettext_adapter import parse_po, rebuild as rebuild_po, validate_pair as validate_po_pair
from runtime.localize_anything.io_utils import read_jsonl, write_json, write_jsonl
from runtime.localize_anything.ios_strings_adapter import extract_segments as extract_ios_segments
from runtime.localize_anything.ios_strings_adapter import rebuild as rebuild_ios_strings
from runtime.localize_anything.ios_strings_adapter import stage_rebuild as stage_ios_strings
from runtime.localize_anything.ios_strings_adapter import target_resource_path as target_ios_resource_path
from runtime.localize_anything.ios_strings_adapter import validate_pair as validate_ios_strings
from runtime.localize_anything.json_adapter import extract_segments, rebuild, validate_pair
from runtime.localize_anything.markup_adapter import extract_segments as extract_markup_segments
from runtime.localize_anything.markup_adapter import rebuild as rebuild_markup, validate_pair as validate_markup_pair
from runtime.localize_anything.mo_compiler import compile_segments_to_mo
from runtime.localize_anything.planning import create_batch_plan
from runtime.localize_anything.project import initialize_project, inspect_project
from runtime.localize_anything.retrieval import build_work_packet
from runtime.localize_anything.review import import_review
from runtime.localize_anything.review_sheet import write_review_sheet
from runtime.localize_anything.run import run_localize
from runtime.localize_anything.schema_validation import validate_document, validate_protocol_tree
from runtime.localize_anything.segments import diff_segments
from runtime.localize_anything.staging import stage_generated
from runtime.localize_anything.structured_adapter import extract_segments as extract_structured_segments
from runtime.localize_anything.structured_adapter import rebuild as rebuild_structured, validate_pair as validate_structured_pair
from runtime.localize_anything.subtitle_adapter import extract_segments as extract_subtitle_segments
from runtime.localize_anything.subtitle_adapter import rebuild as rebuild_subtitles, validate_pair as validate_subtitle_pair
from runtime.localize_anything.tabular_adapter import extract_segments as extract_tabular_segments
from runtime.localize_anything.tabular_adapter import rebuild as rebuild_tabular, validate_pair as validate_tabular_pair
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
            self.assertTrue((state / "glossary.csv").exists())
            self.assertTrue((state / "translation-memory.jsonl").exists())
            self.assertTrue((state / "delivery-manifest.json").exists())
            manifest = json.loads((state / "delivery-manifest.json").read_text(encoding="utf-8"))
            config = json.loads((state / "config.json").read_text(encoding="utf-8"))
            assert_protocol_schema(self, "project-config", config)
            assert_protocol_schema(self, "delivery-manifest", manifest)
            self.assertEqual(manifest["source_material"][0]["role"], "source_of_truth")
            self.assertEqual([item["path"] for item in manifest["source_material"]], ["locales/en-US.json"])
            self.assertEqual(manifest["unprocessed_non_text_assets"][0]["asset_type"], "image")

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
        plan = create_batch_plan(segments, "en-US", ["zh-CN"])
        assert_protocol_schema(self, "batch-plan", plan)
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
            packaged_target = delivery / "files" / "locales" / "zh-CN.json"
            self.assertTrue(packaged_target.is_file())
            self.assertEqual(validate_pair(source, packaged_target)["status"], "pass")
            self.assertTrue(Path(result["artifacts"]["delivery_dashboard"]).is_file())
            self.assertTrue(Path(result["artifacts"]["delivery_dashboard_markdown"]).is_file())
            self.assertTrue(Path(result["artifacts"]["review_sheet_markdown"]).is_file())
            self.assertTrue(Path(result["artifacts"]["review_sheet_csv"]).is_file())
            self.assertTrue(Path(result["artifacts"]["apply_plan"]).is_file())
            self.assertTrue(Path(result["artifacts"]["apply_plan_markdown"]).is_file())
            self.assertIn("Apply Plan", Path(result["artifacts"]["apply_plan_markdown"]).read_text(encoding="utf-8"))
            self.assertIn("Translation Review Sheet", Path(result["artifacts"]["review_sheet_markdown"]).read_text(encoding="utf-8"))


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
                "glossary.csv",
                "translation-memory.jsonl",
                "qa-report.md",
                "files/locales/zh-CN.json",
            ):
                self.assertTrue((delivery / name).exists(), name)
            self.assertEqual(packaged["manifest"]["delivery_status"], "review_ready")
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
            (locales / "zh-CN.json").write_text('{"changed": true}\n', encoding="utf-8")
            conflicted_plan = create_apply_plan(delivery, project)
            self.assertEqual(conflicted_plan["summary"]["conflict"], 1)
            self.assertTrue(conflicted_plan["blocked_by_conflicts"])

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
        self.assertEqual(result["schemas_checked"], 13)


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


if __name__ == "__main__":
    unittest.main()
