from __future__ import annotations

import ast
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime.localize_anything.core_cli import main as localize


REPOSITORY = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY / "skills" / "localize-anything"


class SkillDefaultPathTests(unittest.TestCase):
    def test_default_path_uses_only_the_five_core_commands(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        default = _section(skill, "## Default Path", "## Explicit Compatibility").lower()
        expected = [
            "localize scan",
            "localize glossary bootstrap",
            "localize check",
            "localize review",
            "localize report",
        ]
        positions = [default.index(command) for command in expected]
        self.assertEqual(positions, sorted(positions))
        for forbidden in ("provider", "readiness", "workbench", "workflow-run", "knowledge-pack-select", "build-work-packet", "signoff"):
            self.assertNotIn(forbidden, default)

        for reference in ("workflow.md", "qa-and-delivery.md", "memory-and-context.md", "adapters.md"):
            text = (SKILL_ROOT / "references" / reference).read_text(encoding="utf-8").lower()
            for forbidden in ("provider", "readiness", "workbench", "workflow-run", "knowledge-pack-select", "build-work-packet", "signoff"):
                self.assertNotIn(forbidden, text, f"{reference} routes the default path through {forbidden}")

        compatibility = _section(skill, "## Explicit Compatibility", "## Preserve Hard Constraints").lower()
        self.assertIn("only when the", compatibility)
        self.assertIn("must not invoke old", compatibility)

        default_prompt = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8").lower()
        for command in expected:
            self.assertIn(command, default_prompt)

        for runtime_file in ("core.py", "core_cli.py"):
            tree = ast.parse((REPOSITORY / "runtime" / "localize_anything" / runtime_file).read_text(encoding="utf-8"))
            modules = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            for forbidden in ("provider", "readiness", "workbench", "workflow", "knowledge", "run"):
                self.assertFalse(
                    any(forbidden in module for module in modules),
                    f"{runtime_file} imports a legacy {forbidden} module",
                )

    def test_skill_dry_run_uses_core_commands_and_keeps_human_gate_open(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "quickstart-json"
            shutil.copytree(REPOSITORY / "examples" / "quickstart-json", project)
            target = project / "locales" / "ru-RU.json"

            self.assertEqual(
                _run(
                    "scan",
                    project.as_posix(),
                    "--source-locale",
                    "en-US",
                    "--target-locale",
                    "ru-RU",
                    "--source",
                    "locales/en-US.json",
                )[0],
                0,
            )
            self.assertEqual(_run("glossary", "bootstrap", project.as_posix())[0], 0)

            # This is the Coding Agent's project-native resource edit.
            target.write_text(
                json.dumps(
                    {
                        "menu": {"start": "Начать игру", "welcome": "Добро пожаловать, {player}!"},
                        "inventory": {"coins": "У вас {{count}} монет.", "weight": "Вес: %s кг"},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            subprocess.run([sys.executable, "-m", "json.tool", target.as_posix()], check=True, capture_output=True, text=True)

            check_exit, check = _run("check", project.as_posix(), "--target", "locales/ru-RU.json")
            self.assertEqual(check_exit, 0)
            self.assertEqual(check["status"], "pass")

            review_exit, review = _run("review", project.as_posix(), "--target", "locales/ru-RU.json")
            self.assertEqual(review_exit, 0)
            packet = json.loads(Path(review["review_packet"]).read_text(encoding="utf-8"))
            self.assertEqual(packet["status"], "ready_for_independent_review")
            self.assertEqual(len(packet["files"][0]["segments"]), 4)
            self.assertIn("У вас {{count}} монет.", {item["target"] for item in packet["files"][0]["segments"]})

            findings = project / "independent-review.json"
            findings.write_text(
                json.dumps(
                    {
                        "reviewer": "fresh-review-context",
                        "findings": [
                            {
                                "id": "game-tone",
                                "severity": "actionable",
                                "status": "needs_human_confirmation",
                                "note": "Confirm the preferred Russian imperative for the primary action.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                _run("review", project.as_posix(), "--target", "locales/ru-RU.json", "--findings", findings.as_posix())[0],
                0,
            )
            self.assertEqual(_run("report", project.as_posix())[1]["status"], "needs_human_confirmation")

            wrong_confirmation = project / "wrong-confirmation.json"
            wrong_confirmation.write_text(json.dumps({"confirmations": [{"finding_id": "unknown", "decision": "approved"}]}), encoding="utf-8")
            self.assertEqual(_run("report", project.as_posix(), "--confirm", wrong_confirmation.as_posix())[0], 2)

            confirmation = project / "confirmation.json"
            confirmation.write_text(json.dumps({"confirmations": [{"finding_id": "game-tone", "decision": "approved"}]}), encoding="utf-8")
            report_exit, report = _run("report", project.as_posix(), "--confirm", confirmation.as_posix())
            self.assertEqual(report_exit, 0)
            self.assertEqual(report["status"], "ready")
            self.assertIn("Status: **ready**", (project / ".localize-anything" / "report.md").read_text(encoding="utf-8"))


def _section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def _run(*argv: str) -> tuple[int, dict[str, object]]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = localize(list(argv))
    if exit_code == 2:
        return exit_code, {"error": stderr.getvalue()}
    return exit_code, json.loads(stdout.getvalue())
