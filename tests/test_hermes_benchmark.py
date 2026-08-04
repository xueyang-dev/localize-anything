from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "benchmarks" / "hermes-agent"))

import common  # noqa: E402

from runtime.localize_anything.core_segments import diff_segments  # noqa: E402
from runtime.localize_anything.structured_adapter import extract_segments as extract_yaml  # noqa: E402


class HermesBenchmarkHelpersTests(unittest.TestCase):

    def test_engineering_draft_labels_and_preserves_placeholders(self) -> None:
        segments = [
            {
                "segment_id": "a",
                "source": "Hello {name}",
                "context": {"pointer": "/common/welcome"},
                "constraints": {"placeholders": ["{name}"]},
            },
            {
                "segment_id": "b",
                "source": "Try ${term}",
                "context": {"pointer": "/common/try#fn0"},
                "constraints": {"placeholders": [], "template_expressions": ["${term}"]},
            },
        ]
        drafted = common.apply_engineering_draft(segments, {"/common/welcome": "Bonjour {name}"})
        by_id = {segment["segment_id"]: segment for segment in drafted}
        self.assertEqual(by_id["a"]["target"], "Bonjour {name}")
        self.assertEqual(by_id["a"]["quality_claim"], "engineering_fixture_only")
        self.assertEqual(by_id["b"]["target"], "Try ${term}")
        self.assertEqual(by_id["b"]["generation_mode"], "synthetic_identity")
        self.assertEqual(by_id["a"]["generation_mode"], "synthetic_curated_draft")

    def test_import_rejects_unknown_and_missing_ids(self) -> None:
        extracted = [
            {"segment_id": "x", "source": "Save", "context": {"pointer": "/common/save"}},
            {"segment_id": "y", "source": "Cancel", "context": {"pointer": "/common/cancel"}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "import.jsonl"
            path.write_text('{"segment_id": "x", "target": "Enregistrer"}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                common.import_translated_segments(extracted, path)
            path.write_text(
                '{"segment_id": "x", "target": "Enregistrer"}\n{"segment_id": "z", "target": "X"}\n',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                common.import_translated_segments(extracted, path)
            path.write_text(
                '{"segment_id": "x", "target": "Enregistrer"}\n{"segment_id": "y", "target": "Annuler"}\n',
                encoding="utf-8",
            )
            merged = common.import_translated_segments(extracted, path)
            self.assertEqual(merged[0]["target"], "Enregistrer")
            self.assertEqual(merged[0]["status"], "generated")

    def test_batch_assignment_is_semantic(self) -> None:
        segments = [
            {"segment_id": "a", "context": {"pointer": "/common/save"}},
            {"segment_id": "b", "context": {"pointer": "/approval/denied"}},
            {"segment_id": "c", "context": {"pointer": "/gateway/draining"}},
            {"segment_id": "d", "context": {"pointer": "/misc/thing"}},
        ]
        common.assign_batches(segments)
        batches = [segment["context"]["batch"] for segment in segments]
        self.assertEqual(batches, ["common", "approval", "gateway", "misc"])

    def test_incremental_diff_classifies_yaml_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "en.yaml"
            source.write_text(
                "a:\n  one: \"One\"\n  two: \"Two {n}\"\n  three: \"Three\"\n  extra: \"Extra\"\n",
                encoding="utf-8",
            )
            mutated = root / "en-mutated.yaml"
            mutated.write_text(
                "a:\n  one: \"One (changed)\"\n  two: \"Two {n}\"\n  three_moved: \"Three\"\n  four: \"Four\"\n",
                encoding="utf-8",
            )
            previous = extract_yaml(source, "en", "locales/en.yaml")
            current = extract_yaml(mutated, "en", "locales/en.yaml")
            diff = diff_segments(previous, current)
            self.assertEqual(diff["summary"]["changed"], 1)
            self.assertEqual(diff["summary"]["moved"], 1)
            self.assertEqual(diff["summary"]["new"], 1)
            self.assertEqual(diff["summary"]["deleted"], 1)
            self.assertEqual(diff["summary"]["unchanged"], 1)

    @staticmethod
    def _build_report(steps: list[dict]) -> dict:
        return {
            "status": "pass",
            "summary": {"total": len(steps), "passed": len(steps), "failed": 0, "skipped": 0},
            "steps": steps,
        }

    def test_build_gate_all_required_steps_pass(self) -> None:
        steps = [
            {"check": "a", "status": "passed", "passed": True, "required": True},
            {"check": "b", "status": "passed", "passed": True, "required": True},
        ]
        ok, problems = common.evaluate_build_gate(self._build_report(steps))
        self.assertTrue(ok)
        self.assertEqual(problems, [])

    def test_build_gate_required_step_fails(self) -> None:
        steps = [
            {"check": "a", "status": "passed", "passed": True, "required": True},
            {"check": "b", "status": "failed", "passed": False, "required": True},
        ]
        report = self._build_report(steps)
        report["status"] = "fail"
        ok, problems = common.evaluate_build_gate(report)
        self.assertFalse(ok)
        self.assertTrue(any("required build step 'b'" in problem for problem in problems))

    def test_build_gate_missing_report_fails(self) -> None:
        ok, problems = common.evaluate_build_gate(None)
        self.assertFalse(ok)
        self.assertTrue(any("missing" in problem for problem in problems))

    def test_build_gate_required_step_absent_fails(self) -> None:
        steps = [
            {"check": "a", "status": "passed", "passed": True, "required": True},
            {"check": "b", "required": True},  # absent status/passed fields
        ]
        ok, problems = common.evaluate_build_gate(self._build_report(steps))
        self.assertFalse(ok)
        self.assertTrue(any("required build step 'b'" in problem for problem in problems))

    def test_build_gate_optional_step_skipped_passes(self) -> None:
        steps = [
            {"check": "a", "status": "passed", "passed": True, "required": True},
            {"check": "optional", "status": "skipped", "passed": False, "required": False},
        ]
        ok, problems = common.evaluate_build_gate(self._build_report(steps))
        self.assertTrue(ok)
        self.assertEqual(problems, [])

    def test_sanitize_text_replaces_machine_paths(self) -> None:
        home = str(Path.home())
        sample = (
            f"{common.COPY / 'hermes' / '.venv/bin/python'} "
            "-m pytest /var/folders/70/m56f428103j8mb2ssqj6zr4c0000gn/T/tmp.abc123/x.yaml "
            f"{home}/.hermes/config.yaml"
        )
        cleaned = common.sanitize_text(sample)
        self.assertNotIn(home, cleaned)
        self.assertNotIn("/var/folders/", cleaned)
        self.assertIn("<hermes-copy>/.venv/bin/python", cleaned)
        self.assertIn("<temporary-directory>/x.yaml", cleaned)
        self.assertIn("<home>/.hermes/config.yaml", cleaned)

    def test_sanitize_report_is_recursive_and_deterministic(self) -> None:
        report = {
            "command": f"python {common.BENCH_ROOT / 'prepare.py'} source",
            "items": [
                {"tail": str(common.SOURCE)},
            ],
            "count": 3,
        }
        first = common.sanitize_report(report)
        second = common.sanitize_report(report)
        self.assertEqual(first, second)
        self.assertEqual(first["command"], "python <benchmark>/prepare.py source")
        self.assertEqual(first["items"][0]["tail"], "<hermes-source>")
        self.assertEqual(first["count"], 3)

    def test_sanitize_text_leaves_plain_text_unchanged(self) -> None:
        text = "python prepare.py source && npm run typecheck"
        self.assertEqual(common.sanitize_text(text), text)


if __name__ == "__main__":
    unittest.main()
