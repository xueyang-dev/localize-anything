from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from runtime.localize_anything.core_cli import main


class CoreCliTests(unittest.TestCase):
    def test_minimal_core_runs_to_a_confirmed_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            locales = project / "locales"
            locales.mkdir()
            (locales / "en.json").write_text(
                json.dumps(
                    {
                        "title": "Open Atlas",
                        "action": "Open Atlas",
                        "welcome": "Welcome, {name}!",
                    }
                ),
                encoding="utf-8",
            )
            (locales / "zh.json").write_text(
                json.dumps(
                    {
                        "title": "打开 Atlas",
                        "action": "打开 Atlas",
                        "welcome": "欢迎，{name}！",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                self._run(
                    "scan",
                    project.as_posix(),
                    "--source-locale",
                    "en-US",
                    "--target-locale",
                    "zh-CN",
                    "--source",
                    "locales/en.json",
                )[0],
                0,
            )
            self.assertEqual(self._run("glossary", "bootstrap", project.as_posix())[0], 0)

            glossary_path = project / ".localize-anything" / "glossary.json"
            glossary = json.loads(glossary_path.read_text(encoding="utf-8"))
            concept = next(item for item in glossary["concepts"] if item["source_terms"] == ["Open Atlas"])
            concept["status"] = "locked"
            concept["target"]["preferred"] = "打开 Atlas"
            glossary_path.write_text(json.dumps(glossary, ensure_ascii=False), encoding="utf-8")

            check_exit, check_result = self._run("check", project.as_posix(), "--target", "locales/zh.json")
            self.assertEqual(check_exit, 0)
            self.assertEqual(check_result["status"], "pass")
            self.assertEqual(
                check_result["source_target_mapping"],
                [{"source": "locales/en.json", "target": "locales/zh.json", "adapter": "json"}],
            )

            packet_exit, packet = self._run("review", project.as_posix(), "--target", "locales/zh.json")
            self.assertEqual(packet_exit, 0)
            self.assertEqual(packet["status"], "ready_for_independent_review")
            self.assertEqual(packet["source_target_mapping"][0]["source"], "locales/en.json")
            findings = project / "findings.json"
            findings.write_text(
                json.dumps(
                    {
                        "reviewer": "independent-agent",
                        "review_items": [
                            {
                                "id": "checked-tone",
                                "severity": "informational",
                                "status": "auto_cleared",
                                "note": "Tone is acceptable for this low-risk label.",
                            }
                        ],
                        "findings": [
                            {
                                "id": "brand-name",
                                "severity": "actionable",
                                "status": "needs_human_confirmation",
                                "note": "Confirm whether Atlas remains untranslated.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                self._run("review", project.as_posix(), "--target", "locales/zh.json", "--findings", findings.as_posix())[0],
                0,
            )
            imported_review = json.loads((project / ".localize-anything" / "independent-review.json").read_text(encoding="utf-8"))
            self.assertEqual(imported_review["summary"]["review_item_count"], 1)
            self.assertEqual(imported_review["summary"]["finding_count"], 1)
            self.assertEqual(len(imported_review["review_items"]), 1)
            self.assertEqual(len(imported_review["findings"]), 1)
            self.assertEqual(self._run("report", project.as_posix())[1]["status"], "needs_human_confirmation")

            confirmations = project / "confirmations.json"
            confirmations.write_text(json.dumps({"confirmations": [{"finding_id": "brand-name", "decision": "preserve"}]}), encoding="utf-8")
            report_exit, report = self._run("report", project.as_posix(), "--confirm", confirmations.as_posix())
            self.assertEqual(report_exit, 0)
            self.assertEqual(report["status"], "ready")
            self.assertTrue((project / ".localize-anything" / "report.md").is_file())

    def test_pairing_rejects_target_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "locales" / "en").mkdir(parents=True)
            (project / "locales" / "ru").mkdir(parents=True)
            (project / "locales" / "en" / "common.json").write_text('{"title": "Title"}', encoding="utf-8")
            (project / "locales" / "en" / "admin.json").write_text('{"save": "Save"}', encoding="utf-8")
            (project / "locales" / "ru" / "common.json").write_text('{"title": "Заголовок"}', encoding="utf-8")
            self._run(
                "scan",
                project.as_posix(),
                "--source-locale",
                "en",
                "--target-locale",
                "ru",
                "--source",
                "locales/en/common.json",
                "--source",
                "locales/en/admin.json",
            )

            exit_code, result = self._run("check", project.as_posix(), "--target", "locales/ru/common.json")
            self.assertEqual(exit_code, 2)
            self.assertIn("Expected 2 --target values, got 1", result["error"])

    def test_pairing_rejects_wrong_target_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "locales" / "en").mkdir(parents=True)
            (project / "locales" / "ru").mkdir(parents=True)
            (project / "locales" / "en" / "common.json").write_text('{"title": "Title"}', encoding="utf-8")
            (project / "locales" / "en" / "admin.json").write_text('{"save": "Save"}', encoding="utf-8")
            (project / "locales" / "ru" / "common.json").write_text('{"title": "Заголовок"}', encoding="utf-8")
            (project / "locales" / "ru" / "admin.json").write_text('{"save": "Сохранить"}', encoding="utf-8")
            self._run(
                "scan",
                project.as_posix(),
                "--source-locale",
                "en",
                "--target-locale",
                "ru",
                "--source",
                "locales/en/common.json",
                "--source",
                "locales/en/admin.json",
            )

            exit_code, result = self._run(
                "review",
                project.as_posix(),
                "--target",
                "locales/ru/admin.json",
                "--target",
                "locales/ru/common.json",
            )
            self.assertEqual(exit_code, 2)
            self.assertIn("Source/target locale path mismatch at pair 1", result["error"])
            self.assertIn("locales/en/common.json -> locales/ru/admin.json", result["error"])

    def test_pairing_rejects_target_path_with_source_locale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "locales").mkdir()
            (project / "locales" / "en.json").write_text('{"title": "Title"}', encoding="utf-8")
            self._run("scan", project.as_posix(), "--source-locale", "en", "--target-locale", "ru", "--source", "locales/en.json")

            exit_code, result = self._run("check", project.as_posix(), "--target", "locales/en.json")
            self.assertEqual(exit_code, 2)
            self.assertIn("target path contains source-locale token", result["error"])

    def test_check_fails_when_a_placeholder_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "en.json").write_text('{"welcome": "Welcome, {name}!"}', encoding="utf-8")
            (project / "zh.json").write_text('{"welcome": "欢迎！"}', encoding="utf-8")
            self._run("scan", project.as_posix(), "--source-locale", "en-US", "--target-locale", "zh-CN", "--source", "en.json")

            exit_code, result = self._run("check", project.as_posix(), "--target", "zh.json")
            self.assertEqual(exit_code, 1)
            self.assertEqual(result["status"], "fail")
            self.assertEqual(result["summary"]["blocking_count"], 1)
            review_exit, review = self._run("review", project.as_posix(), "--target", "zh.json")
            self.assertEqual(review_exit, 2)
            self.assertIn("Deterministic check failed", review["error"])

    def test_scan_blocks_swift_typed_catalog_without_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            catalog = project / "Sources" / "Localization"
            catalog.mkdir(parents=True)
            (catalog / "Strings.swift").write_text(
                "struct Strings {\n  let settingsTitle: String\n}\n\nenum AppLanguage { case english, zhHans }\n",
                encoding="utf-8",
            )
            (catalog / "Strings+zhHans.swift").write_text(
                "extension Strings {\n  static let zhHans = Strings(settingsTitle: \"设置\")\n}\n",
                encoding="utf-8",
            )

            exit_code, result = self._run(
                "scan",
                project.as_posix(),
                "--source-locale",
                "en",
                "--target-locale",
                "zh-Hans",
                "--source",
                "Sources/Localization",
            )
            self.assertEqual(exit_code, 2)
            self.assertIn("Capability gate failed", result["error"])
            state = project / ".localize-anything"
            self.assertFalse((state / "project-memory.json").exists())
            capability = json.loads((state / "capability-report.json").read_text(encoding="utf-8"))
            self.assertEqual(capability["status"], "blocked")
            self.assertEqual(capability["blocked_sources"][0]["surface_type"], "code_embedded_catalog")
            self.assertEqual(capability["blocked_sources"][0]["allowed_phases"], ["scan"])
            inventory = json.loads((state / "source-surface-inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(inventory["summary"]["unsupported_selected_count"], 1)

    def test_review_requires_current_check_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "en.json").write_text('{"title": "Title"}', encoding="utf-8")
            target = project / "zh.json"
            target.write_text('{"title": "标题"}', encoding="utf-8")
            self._run("scan", project.as_posix(), "--source-locale", "en", "--target-locale", "zh-CN", "--source", "en.json")

            missing_exit, missing = self._run("review", project.as_posix(), "--target", "zh.json")
            self.assertEqual(missing_exit, 2)
            self.assertIn("Deterministic check artifact is missing", missing["error"])

            self.assertEqual(self._run("check", project.as_posix(), "--target", "zh.json")[0], 0)
            target.write_text('{"title": "改过的标题"}', encoding="utf-8")
            stale_exit, stale = self._run("review", project.as_posix(), "--target", "zh.json")
            self.assertEqual(stale_exit, 2)
            self.assertIn("changed since deterministic-check.json", stale["error"])

            self.assertEqual(self._run("check", project.as_posix(), "--target", "zh.json")[0], 0)
            review_exit, review = self._run("review", project.as_posix(), "--target", "zh.json")
            self.assertEqual(review_exit, 0)
            packet = json.loads(Path(review["review_packet"]).read_text(encoding="utf-8"))
            self.assertEqual(packet["files"][0]["segments"][0]["target"], "改过的标题")

            findings = project / "findings.json"
            findings.write_text(json.dumps({"reviewer": "independent-agent", "findings": []}), encoding="utf-8")
            target.write_text('{"title": "再次改动"}', encoding="utf-8")
            self.assertEqual(self._run("check", project.as_posix(), "--target", "zh.json")[0], 0)
            stale_packet_exit, stale_packet = self._run(
                "review",
                project.as_posix(),
                "--target",
                "zh.json",
                "--findings",
                findings.as_posix(),
            )
            self.assertEqual(stale_packet_exit, 2)
            self.assertIn("changed since review-packet.json", stale_packet["error"])

    def test_report_is_not_ready_with_untranslated_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "en.po").write_text(
                'msgid "Share"\nmsgstr "Share"\n',
                encoding="utf-8",
            )
            (project / "ru.po").write_text(
                'msgid "Share"\nmsgstr ""\n',
                encoding="utf-8",
            )
            self._run(
                "scan",
                project.as_posix(),
                "--source-locale",
                "en",
                "--target-locale",
                "ru",
                "--source",
                "en.po",
            )

            self.assertEqual(
                self._run("check", project.as_posix(), "--target", "ru.po")[1]["status"],
                "pass_with_warnings",
            )
            self._run("review", project.as_posix(), "--target", "ru.po")
            findings = project / "findings.json"
            findings.write_text(
                json.dumps({"reviewer": "independent-agent", "findings": []}),
                encoding="utf-8",
            )
            self._run(
                "review",
                project.as_posix(),
                "--target",
                "ru.po",
                "--findings",
                findings.as_posix(),
            )

            report = self._run("report", project.as_posix())[1]
            self.assertEqual(report["status"], "needs_attention")
            self.assertIn(
                "Status: **needs_attention**",
                (project / ".localize-anything" / "report.md").read_text(encoding="utf-8"),
            )

    def test_review_reads_xcstrings_target_localizations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            catalog = project / "Localizable.xcstrings"
            catalog.write_text(
                json.dumps(
                    {
                        "sourceLanguage": "en",
                        "strings": {
                            "app.title": {
                                "localizations": {
                                    "en": {"stringUnit": {"value": "Sample App"}},
                                    "zh-Hans": {"stringUnit": {"value": "示例应用"}},
                                }
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self._run("scan", project.as_posix(), "--source-locale", "en-US", "--target-locale", "zh-CN", "--source", "Localizable.xcstrings")

            self.assertEqual(self._run("check", project.as_posix(), "--target", "Localizable.xcstrings")[0], 0)
            _exit_code, result = self._run("review", project.as_posix(), "--target", "Localizable.xcstrings")
            packet = json.loads(Path(result["review_packet"]).read_text(encoding="utf-8"))
            self.assertEqual(packet["files"][0]["segments"][0]["target"], "示例应用")

    def test_review_pairs_gettext_targets_by_message_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "en.po").write_text(
                '#: result.tsx\nmsgid "Document Signed"\nmsgstr ""\n\n'
                '#: result.tsx\nmsgid "Everyone has signed"\nmsgstr ""\n',
                encoding="utf-8",
            )
            (project / "ru.po").write_text(
                '#: result.tsx\nmsgid "Document Signed"\nmsgstr "Документ подписан"\n\n'
                '#: result.tsx\nmsgid "Everyone has signed"\nmsgstr "Все подписали документ"\n',
                encoding="utf-8",
            )
            self._run(
                "scan",
                project.as_posix(),
                "--source-locale",
                "en",
                "--target-locale",
                "ru",
                "--source",
                "en.po",
            )

            self.assertEqual(self._run("check", project.as_posix(), "--target", "ru.po")[0], 0)
            _exit_code, result = self._run("review", project.as_posix(), "--target", "ru.po")
            packet = json.loads(Path(result["review_packet"]).read_text(encoding="utf-8"))
            pairs = {
                segment["source"]: segment["target"]
                for segment in packet["files"][0]["segments"]
            }
            self.assertEqual(pairs["Document Signed"], "Документ подписан")
            self.assertEqual(pairs["Everyone has signed"], "Все подписали документ")

    def _run(self, *argv: str) -> tuple[int, dict[str, object]]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(list(argv))
        if exit_code == 2:
            return exit_code, {"error": stderr.getvalue()}
        return exit_code, json.loads(stdout.getvalue())
