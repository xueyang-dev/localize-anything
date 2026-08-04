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


if __name__ == "__main__":
    unittest.main()
