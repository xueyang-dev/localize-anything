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

            packet_exit, packet = self._run("review", project.as_posix(), "--target", "locales/zh.json")
            self.assertEqual(packet_exit, 0)
            self.assertEqual(packet["status"], "ready_for_independent_review")
            findings = project / "findings.json"
            findings.write_text(
                json.dumps(
                    {
                        "reviewer": "independent-agent",
                        "findings": [
                            {
                                "id": "brand-name",
                                "severity": "high",
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
            self.assertEqual(self._run("report", project.as_posix())[1]["status"], "needs_human_confirmation")

            confirmations = project / "confirmations.json"
            confirmations.write_text(json.dumps({"confirmations": [{"finding_id": "brand-name", "decision": "preserve"}]}), encoding="utf-8")
            report_exit, report = self._run("report", project.as_posix(), "--confirm", confirmations.as_posix())
            self.assertEqual(report_exit, 0)
            self.assertEqual(report["status"], "ready")
            self.assertTrue((project / ".localize-anything" / "report.md").is_file())

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
        with contextlib.redirect_stdout(stdout):
            exit_code = main(list(argv))
        return exit_code, json.loads(stdout.getvalue())
