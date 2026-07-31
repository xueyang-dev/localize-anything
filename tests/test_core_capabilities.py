from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from runtime.localize_anything.core_glossary import check_locked_concepts, extract_candidate_concepts
from runtime.localize_anything.core_preflight import discover_resources, select_resources
from runtime.localize_anything.core_segments import align_review_segments, diff_segments
from runtime.localize_anything.core import bootstrap_glossary, scan
from runtime.localize_anything.core_formats import (
    android_overlay_destination,
    discover_android_merged_resources,
    extract_source,
    validate_resource_pair,
)


class CoreGlossaryParityTests(unittest.TestCase):
    def test_candidates_are_stable_and_locked_constraints_block(self) -> None:
        segments = [
            {"segment_id": "one", "source_path": "en.json", "source": "Document"},
            {"segment_id": "two", "source_path": "en.json", "source": "Document"},
            {"segment_id": "three", "source_path": "en.json", "source": "API"},
        ]
        candidates = extract_candidate_concepts(segments)
        self.assertEqual([item["source_terms"][0] for item in candidates], ["API", "Document"])
        self.assertEqual(candidates, extract_candidate_concepts(segments))

        glossary = {
            "concepts": [
                {
                    "id": "document",
                    "source_terms": ["Document"],
                    "behavior": "translate",
                    "status": "locked",
                    "target": {"preferred": "Документ", "forbidden": ["Док"]},
                }
            ]
        }
        findings = check_locked_concepts(glossary, ["Document"], ["Док"])
        self.assertEqual({item["kind"] for item in findings}, {"locked_glossary", "forbidden_glossary"})


class CorePreflightParityTests(unittest.TestCase):
    def test_discovery_is_scoped_and_selection_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "locales").mkdir()
            (project / "locales" / "en.json").write_text('{"title": "Document"}', encoding="utf-8")
            (project / "build").mkdir()
            (project / "build" / "generated.json").write_text("{}", encoding="utf-8")

            self.assertEqual(discover_resources(project), [{"path": "locales/en.json", "adapter": "json"}])
            self.assertEqual(select_resources(project, ["locales/en.json"]), [{"path": "locales/en.json", "adapter": "json"}])
            with self.assertRaisesRegex(ValueError, "inside the project root"):
                select_resources(project, ["../outside.json"])


class CoreSegmentParityTests(unittest.TestCase):
    def test_identity_alignment_and_staleness_diff_are_deterministic(self) -> None:
        source = [{"segment_id": "old", "source_hash": "same", "source": "Share", "context": {"key": "share"}}]
        target = [{"segment_id": "target", "source": "Поделиться", "context": {"key": "share"}}]
        self.assertEqual(align_review_segments(source, target)[0]["target"], "Поделиться")

        result = diff_segments(source, [{"segment_id": "new", "source_hash": "same", "source": "Share", "context": {"key": "share"}}])
        self.assertEqual(result["summary"]["moved"], 1)
        self.assertEqual(result["segments"][0]["previous_segment_id"], "old")


class CoreMemoryImportTests(unittest.TestCase):
    def test_only_confirmed_legacy_knowledge_enters_memory_and_glossary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "locales").mkdir()
            (project / "locales" / "en.json").write_text('{"title": "Document"}', encoding="utf-8")
            state = project / ".localize-anything"
            state.mkdir()
            (state / "glossary.csv").write_text(
                "source,target,status,notes\nDocument,Документ,approved,\nDraft,Черновик,suggested,\n",
                encoding="utf-8",
            )
            (state / "translation-memory.jsonl").write_text(
                json.dumps({"source": "Share", "target": "Поделиться", "status": "confirmed"}) + "\n"
                + json.dumps({"source": "Cancel", "target": "Отмена", "status": "reference"}) + "\n",
                encoding="utf-8",
            )
            (state / "localization-context.md").write_text("# Style\n\n- Use concise labels.\n", encoding="utf-8")

            scan(project, source_locale="en", target_locale="ru", source_files=["locales/en.json"])
            memory = json.loads((state / "project-memory.json").read_text(encoding="utf-8"))
            self.assertEqual(len(memory["translation_memory"]), 1)
            self.assertEqual(memory["style_rules"], ["Use concise labels."])

            bootstrap_glossary(project)
            glossary = json.loads((state / "glossary.json").read_text(encoding="utf-8"))
            by_source = {item["source_terms"][0]: item for item in glossary["concepts"]}
            self.assertEqual(by_source["Document"]["status"], "locked")
            self.assertNotIn("Draft", by_source)


class CoreFormatBoundaryTests(unittest.TestCase):
    def test_json_boundary_and_android_overlay_routing_match_existing_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / "en.json"
            target = project / "ru.json"
            source.write_text('{"title": "Document"}', encoding="utf-8")
            target.write_text('{"title": "Документ"}', encoding="utf-8")
            self.assertEqual(extract_source("json", source, "en", "en.json")[0]["source"], "Document")
            self.assertEqual(validate_resource_pair("json", source, target, "ru")["status"], "pass")

            merged = project / "app" / "build" / "intermediates" / "incremental" / "x" / "mergeDebugResources" / "merged.dir" / "values" / "values.xml"
            merged.parent.mkdir(parents=True)
            merged.write_text("<resources />", encoding="utf-8")
            self.assertEqual(discover_android_merged_resources(project, build_variant="debug"), [merged.resolve()])
            destination = android_overlay_destination(
                project,
                "app/src/main/res/values/strings.xml",
                "ru",
                "localize_anything_overlay.xml",
            )
            self.assertEqual(destination.as_posix(), "app/src/main/res/values-ru/localize_anything_overlay.xml")


if __name__ == "__main__":
    unittest.main()
