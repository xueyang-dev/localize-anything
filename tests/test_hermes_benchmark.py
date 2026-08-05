from __future__ import annotations

import sys
import json
import csv
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parents[1] / "benchmarks" / "hermes-agent"))

import common  # noqa: E402
import build_e3_review  # noqa: E402
import run_retention_adjudication  # noqa: E402
import validate_e3_review  # noqa: E402

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

    def test_import_stores_candidate_classification_not_approval(self) -> None:
        extracted = [
            {"segment_id": "x", "source": "Save", "context": {"pointer": "/common/save"}},
            {"segment_id": "y", "source": "Cancel", "context": {"pointer": "/common/cancel"}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "import.jsonl"
            path.write_text(
                '{"segment_id": "x", "target": "Enregistrer"}\n'
                '{"segment_id": "y", "target": "Cancel", "classification": '
                '"technical_term_retained", "classification_note": "candidate"}\n',
                encoding="utf-8",
            )
            merged = common.import_translated_segments(extracted, path)
            by_id = {segment["segment_id"]: segment for segment in merged}
            self.assertEqual(by_id["y"]["candidate_classification"], "technical_term_retained")
            self.assertEqual(by_id["y"]["candidate_classification_note"], "candidate")
            self.assertNotIn("classification", by_id["y"])
            self.assertNotIn("approved_classification", by_id["y"])

    @staticmethod
    def _identity_segment(segment_id: str = "x", pointer: str = "/common/save") -> dict:
        return {
            "segment_id": segment_id,
            "source": "Save",
            "target": "Save",
            "context": {"pointer": pointer},
            "quality_claim": "host_agent_generated",
            "generation_mode": "host_agent_import",
        }

    def test_candidate_classification_alone_does_not_suppress_e1(self) -> None:
        segment = self._identity_segment()
        segment["candidate_classification"] = "technical_term_retained"
        review = common.segment_review_flags([segment])
        self.assertEqual(review["summary"]["untranslated_english"], 1)
        self.assertEqual(review["flags"][0]["category"], "untranslated_english")

    def test_separate_retention_approval_resolves_e1_flag(self) -> None:
        segment = self._identity_segment()
        segment["candidate_classification"] = "technical_term_retained"
        segment.update(
            {
                "approved_classification": "technical_term_retained",
                "classification_note": "glossary term retained",
                "review_status": "approved",
                "reviewer_type": "AI-assisted bilingual review",
            }
        )
        review = common.segment_review_flags([segment])
        self.assertEqual(review["summary"]["untranslated_english"], 0)

    def test_generation_accounting_uniform_host_agent_imports(self) -> None:
        segments = [
            {"segment_id": f"s{i}", "source": f"Source {i}", "target": f"Cible {i}",
             "quality_claim": "host_agent_generated", "generation_mode": "host_agent_import"}
            for i in range(3)
        ]
        accounting = common.generation_accounting(segments)
        self.assertEqual(accounting["total_segments"], 3)
        self.assertEqual(accounting["imported_segments"], 3)
        self.assertEqual(accounting["engineering_fixture_segments"], 0)
        self.assertEqual(accounting["target_identical_to_source_segments"], 0)
        self.assertEqual(accounting["quality_claim"], "host_agent_generated")
        self.assertEqual(common.validate_generation_metadata(segments, "import"), [])

    def test_generation_accounting_mixed_claims_and_fail_closed(self) -> None:
        segments = [
            {"segment_id": "a", "source": "A", "target": "A'",
             "quality_claim": "host_agent_generated", "generation_mode": "host_agent_import"},
            {"segment_id": "b", "source": "B", "target": "B'",
             "quality_claim": "engineering_fixture_only", "generation_mode": "synthetic_identity"},
        ]
        accounting = common.generation_accounting(segments)
        self.assertEqual(accounting["quality_claim"], "mixed")
        self.assertEqual(accounting["engineering_fixture_segments"], 1)
        problems = common.validate_generation_metadata(segments, "import")
        self.assertTrue(any("engineering fixture" in problem for problem in problems))
        self.assertTrue(any("mixed" in problem for problem in problems))

    def test_generation_accounting_missing_metadata_fails_closed(self) -> None:
        segments = [{"segment_id": "a", "source": "A", "target": "A'"}]  # no claim/mode
        problems = common.validate_generation_metadata(segments, "import")
        self.assertTrue(any("missing quality_claim/generation_mode" in problem for problem in problems))

    def test_generation_accounting_identity_counts(self) -> None:
        identity = self._identity_segment()
        identity["candidate_classification"] = "technical_term_retained"
        approved = self._identity_segment("y", "/common/cancel")
        approved["candidate_classification"] = "brand_or_product_name"
        approved.update(
            {
                "approved_classification": "brand_or_product_name",
                "classification_note": "product name",
                "review_status": "approved",
                "reviewer_type": "AI-assisted bilingual review",
            }
        )
        translated = self._identity_segment("z", "/common/ok")
        translated["target"] = "OK"
        accounting = common.generation_accounting([identity, approved, translated])
        self.assertEqual(accounting["target_identical_to_source_segments"], 2)
        self.assertEqual(accounting["classified_retained_segments"], 2)
        self.assertEqual(accounting["approved_retained_segments"], 1)
        self.assertEqual(accounting["unclassified_identity_segments"], 1)
        self.assertEqual(accounting["translated_non_identity_segments"], 1)

    def test_retention_adjudication_validation_rules(self) -> None:
        rows = [
            {"segment_id": "x", "surface": "web", "source": "Save", "target": "Save",
             "candidate_classification": "technical_term_retained"},
        ]
        decisions = {
            "x": {"approved_classification": "not_a_real_class", "classification_note": "n",
                  "review_status": "approved", "reviewer_type": "AI-assisted bilingual review"},
        }
        problems = run_retention_adjudication.validate_decisions(rows, decisions)
        self.assertTrue(any("invalid approved_classification" in problem for problem in problems))

        decisions["x"]["approved_classification"] = "technical_term_retained"
        decisions["x"]["classification_note"] = ""
        problems = run_retention_adjudication.validate_decisions(rows, decisions)
        self.assertTrue(any("non-empty classification_note" in problem for problem in problems))

        decisions["x"]["classification_note"] = "term retained"
        decisions["x"]["review_status"] = "rejected"
        problems = run_retention_adjudication.validate_decisions(rows, decisions)
        self.assertEqual(problems, [])

        decisions["x"]["review_status"] = "approved"
        decisions["x"]["approved_classification"] = ""
        problems = run_retention_adjudication.validate_decisions(rows, decisions)
        self.assertTrue(any("allowed classification" in problem for problem in problems))

    def test_rejected_retention_stays_actionable(self) -> None:
        segment = self._identity_segment()
        segment.update(
            {
                "approved_classification": "",
                "review_status": "rejected",
                "reviewer_type": "AI-assisted bilingual review",
            }
        )
        review = common.segment_review_flags([segment])
        self.assertEqual(review["summary"]["untranslated_english"], 1)

    def test_collect_refuses_to_reset_existing_decisions_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reports_dir = Path(directory) / "reports"
            reports_dir.mkdir()
            (reports_dir / "retained-string-adjudication.json").write_text(
                json.dumps({"rows": [{"segment_id": "x", "review_status": "approved"}]}),
                encoding="utf-8",
            )
            with mock.patch.object(run_retention_adjudication, "REPORTS", reports_dir), mock.patch(
                "sys.argv", ["run_retention_adjudication.py", "--collect"]
            ):
                with self.assertRaises(SystemExit):
                    run_retention_adjudication.main()
            with mock.patch.object(run_retention_adjudication, "REPORTS", reports_dir), mock.patch(
                "sys.argv", ["run_retention_adjudication.py", "--collect", "--force"]
            ):
                # --force proceeds past the guard into collect_rows().
                with mock.patch.object(
                    run_retention_adjudication,
                    "collect_rows",
                    side_effect=SystemExit("collect called"),
                ):
                    with self.assertRaises(SystemExit) as ctx:
                        run_retention_adjudication.main()
                    self.assertIn("collect called", str(ctx.exception))

    def test_committed_import_manifest_verifies(self) -> None:
        import hashlib
        import json

        manifest_path = common.REAL_IMPORTS / "manifest.json"
        self.assertTrue(manifest_path.is_file(), "evidence/real-imports/manifest.json missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_counts = {"yaml": 351, "web": 709, "desktop": 2623}
        for surface, count in expected_counts.items():
            path = common.REAL_IMPORTS / f"{surface}.jsonl"
            self.assertTrue(path.is_file())
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), count)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(manifest["surfaces"][surface]["sha256"], digest)
            ids = [json.loads(line)["segment_id"] for line in lines]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(ids, sorted(ids))

    def test_evidence_reference_checker_flags_stale_and_missing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reports_dir = Path(directory) / "reports"
            evidence_dir = Path(directory) / "evidence"
            reports_dir.mkdir()
            evidence_dir.mkdir()
            (reports_dir / "example.json").write_text(
                '{"evidence": "work/e2-review-sheet.csv", "link": "reports/does-not-exist.json"}',
                encoding="utf-8",
            )
            with mock.patch.object(common, "REPORTS", reports_dir), mock.patch.object(
                common, "EVIDENCE", evidence_dir
            ):
                problems = common.verify_evidence_references()
            self.assertTrue(any("stale durable-evidence reference" in problem for problem in problems))
            self.assertTrue(any("does not exist" in problem for problem in problems))

    def test_visual_smoke_report_separates_runtime_from_visual_qa(self) -> None:
        report_path = common.REPORTS / "visual-smoke-report.json"
        self.assertTrue(report_path.is_file())
        import json

        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertIs(report["runtime_smoke_recorded"], True)
        self.assertIs(report["dom_text_verified"], True)
        self.assertIs(report["screenshots_reviewed"], False)
        self.assertIs(report["visual_layout_review_completed"], False)
        self.assertIn("visual layout quality not reviewed", report["delivery_claim"])

    # ------------------------------------------------------------------
    # E3 review package validation
    # ------------------------------------------------------------------

    def _temp_e3_package(self, mutate, *, fix_hash: bool = True) -> tuple[Path, list[str]]:
        """Copy the real E3 package into a temp dir and apply a CSV mutation."""
        rows = list(
            csv.DictReader(
                (build_e3_review.E3_DIR / "e3-review-sheet.csv").open(encoding="utf-8", newline="")
            )
        )
        mutate(rows)
        fieldnames = list(rows[0].keys())
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            package = tmp / "package"
            shutil.copytree(build_e3_review.E3_DIR, package)
            with (package / "e3-review-sheet.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
            if fix_hash:
                digest = hashlib.sha256((package / "e3-review-sheet.csv").read_bytes()).hexdigest()
                manifest = json.loads((package / "e3-review-manifest.json").read_text(encoding="utf-8"))
                manifest["review_sheet_sha256"] = digest
                (package / "e3-review-manifest.json").write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                summary = json.loads((package / "e3-review-package-summary.json").read_text(encoding="utf-8"))
                summary["rows"] = len(rows)
                (package / "e3-review-package-summary.json").write_text(
                    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            with mock.patch.object(validate_e3_review, "E3_DIR", package):
                problems = validate_e3_review.validate_package()
            return package, problems

    def test_e3_valid_package_passes(self) -> None:
        _, problems = self._temp_e3_package(lambda rows: None)
        self.assertEqual(problems, [])

    def test_e3_missing_mandatory_row_fails(self) -> None:
        def mutate(rows: list[dict]) -> None:
            # drop one e2_sample row
            for index, row in enumerate(rows):
                if "e2_sample" in row["selection_reasons"].split("|"):
                    del rows[index]
                    break

        _, problems = self._temp_e3_package(mutate)
        self.assertTrue(any("mandatory E2 set incomplete" in problem for problem in problems))

    def test_e3_missing_identity_row_fails(self) -> None:
        def mutate(rows: list[dict]) -> None:
            for index, row in enumerate(rows):
                if "identity_retention" in row["selection_reasons"].split("|"):
                    del rows[index]
                    break

        _, problems = self._temp_e3_package(mutate)
        self.assertTrue(any("mandatory identity set incomplete" in problem for problem in problems))

    def test_e3_duplicate_row_fails(self) -> None:
        def mutate(rows: list[dict]) -> None:
            rows.append(dict(rows[0]))

        _, problems = self._temp_e3_package(mutate)
        self.assertTrue(any("duplicate segment ids" in problem for problem in problems))

    def test_e3_altered_target_fails(self) -> None:
        def mutate(rows: list[dict]) -> None:
            rows[0]["current_target_fr"] = "Une modification détectée."

        _, problems = self._temp_e3_package(mutate)
        self.assertTrue(any("target mismatch" in problem for problem in problems))

    def test_e3_unknown_segment_id_fails(self) -> None:
        def mutate(rows: list[dict]) -> None:
            rows[0]["segment_id"] = "unknown:fake#00000000000000000000"

        _, problems = self._temp_e3_package(mutate)
        self.assertTrue(any("unknown segment ids" in problem for problem in problems))

    def test_e3_missing_context_fails(self) -> None:
        def mutate(rows: list[dict]) -> None:
            rows[0]["context"] = ""

        _, problems = self._temp_e3_package(mutate)
        self.assertTrue(any("missing context" in problem for problem in problems))

    def test_e3_prefilled_reviewer_decision_fails(self) -> None:
        def mutate(rows: list[dict]) -> None:
            rows[0]["review_status"] = "approved"

        _, problems = self._temp_e3_package(mutate)
        self.assertTrue(any("prefilled review_status" in problem for problem in problems))

    def test_e3_broken_manifest_hash_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package"
            shutil.copytree(build_e3_review.E3_DIR, package)
            manifest = json.loads((package / "e3-review-manifest.json").read_text(encoding="utf-8"))
            manifest["review_sheet_sha256"] = "0" * 64  # corrupt -> mismatch
            (package / "e3-review-manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            with mock.patch.object(validate_e3_review, "E3_DIR", package):
                problems = validate_e3_review.validate_package()
        self.assertTrue(any("sha256 does not match" in problem for problem in problems))

    def test_e3_malformed_metadata_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metadata = Path(directory) / "reviewer-metadata.json"
            metadata.write_text(json.dumps({"reviewer_id": "fr-native-01"}), encoding="utf-8")
            problems = validate_e3_review.validate_decisions(
                build_e3_review.E3_DIR / "e3-review-sheet.csv", metadata
            )
        self.assertTrue(any("native-language attestation missing" in problem for problem in problems))

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
