from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from runtime.localize_anything.acceptance import create_acceptance
from runtime.localize_anything.apply import create_apply_plan
from runtime.localize_anything.contracts import validate_adapter_tree
from runtime.localize_anything.delivery import package_delivery
from runtime.localize_anything.gettext_adapter import extract_segments as extract_po_segments
from runtime.localize_anything.gettext_adapter import parse_po, rebuild as rebuild_po, validate_pair as validate_po_pair
from runtime.localize_anything.io_utils import read_jsonl, write_json, write_jsonl
from runtime.localize_anything.json_adapter import extract_segments, rebuild, validate_pair
from runtime.localize_anything.markup_adapter import extract_segments as extract_markup_segments
from runtime.localize_anything.markup_adapter import rebuild as rebuild_markup, validate_pair as validate_markup_pair
from runtime.localize_anything.planning import create_batch_plan
from runtime.localize_anything.project import initialize_project, inspect_project
from runtime.localize_anything.retrieval import build_work_packet
from runtime.localize_anything.review import import_review
from runtime.localize_anything.schema_validation import validate_document, validate_protocol_tree
from runtime.localize_anything.segments import diff_segments
from runtime.localize_anything.structured_adapter import extract_segments as extract_structured_segments
from runtime.localize_anything.structured_adapter import rebuild as rebuild_structured, validate_pair as validate_structured_pair
from runtime.localize_anything.subtitle_adapter import extract_segments as extract_subtitle_segments
from runtime.localize_anything.subtitle_adapter import rebuild as rebuild_subtitles, validate_pair as validate_subtitle_pair
from runtime.localize_anything.tabular_adapter import extract_segments as extract_tabular_segments
from runtime.localize_anything.tabular_adapter import rebuild as rebuild_tabular, validate_pair as validate_tabular_pair
from runtime.localize_anything.wesnoth_adapter import enrich_segments, inventory as wesnoth_inventory, validate_source
from runtime.localize_anything.xliff_adapter import extract_segments as extract_xliff_segments
from runtime.localize_anything.xliff_adapter import rebuild as rebuild_xliff, validate_pair as validate_xliff_pair


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "json-project"
GETTEXT_WESNOTH_ROOT = Path(__file__).parent / "fixtures" / "gettext-wesnoth"
COMMON_FORMATS_ROOT = Path(__file__).parent / "fixtures" / "common-formats"
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
            self.assertEqual(json.loads(output.read_text()), json.loads(expected.read_text()))
            result = validate_pair(source, output)
            self.assertEqual(result["status"], "pass")
            assert_protocol_schema(self, "qa-result", result)

    def test_placeholder_mismatch_fails(self) -> None:
        source = FIXTURE_ROOT / "locales" / "en-US.json"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "broken.json"
            target.write_text(source.read_text().replace("{player}", "{username}"), encoding="utf-8")
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


class ProjectTests(unittest.TestCase):
    def test_inspect_and_preflight_initialize_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            locale_dir = project / "locales"
            locale_dir.mkdir()
            (locale_dir / "en-US.json").write_text((FIXTURE_ROOT / "locales" / "en-US.json").read_text(), encoding="utf-8")
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
            (locale_dir / "en-US.json").write_text(source.read_text(), encoding="utf-8")
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

    def test_protocol_examples_validate_against_schemas(self) -> None:
        root = Path(__file__).parents[1]
        result = validate_protocol_tree(root / "protocol")
        self.assertEqual(result["status"], "pass", result["errors"])
        self.assertEqual(result["schemas_checked"], 11)


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
