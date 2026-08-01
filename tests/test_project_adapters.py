from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from runtime.localize_anything.core_cli import main
from runtime.localize_anything.contracts import validate_adapter_manifest
from runtime.localize_anything.project_adapters import MAX_STDOUT_BYTES


REPOSITORY = Path(__file__).resolve().parents[1]
SAMPLE_ADAPTER = REPOSITORY / "tests" / "fixtures" / "project_adapters" / "sample_extract_only"


class ProjectLocalAdapterTests(unittest.TestCase):
    def test_project_local_descriptor_satisfies_manifest_contract(self) -> None:
        self.assertEqual(validate_adapter_manifest(SAMPLE_ADAPTER / "adapter.json"), [])

    def test_candidate_is_reported_but_not_executed_until_selected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = _sample_project(Path(directory))
            _copy_sample_adapter(project)

            exit_code, result = _run("scan", project.as_posix(), "--source-locale", "en", "--target-locale", "fr", "--source", "catalog.samplecat")
            self.assertEqual(exit_code, 2)
            self.assertIn("Project-local adapter candidate found", result["error"])
            state = project / ".localize-anything"
            self.assertFalse((state / "project-memory.json").exists())
            self.assertFalse((state / "adapter-runs").exists())
            capability = _read_state(project, "capability-report.json")
            self.assertEqual(capability["status"], "blocked")
            self.assertEqual(capability["blocked_sources"][0]["available_project_adapter_candidates"][0]["id"], "sample.extract-only")

    def test_explicit_extract_only_adapter_writes_canonical_artifacts_and_review_packet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = _sample_project(Path(directory))
            _copy_sample_adapter(project)

            scan_exit, scan = _run(
                "scan",
                project.as_posix(),
                "--source-locale",
                "en",
                "--target-locale",
                "fr",
                "--source",
                "catalog.samplecat",
                "--adapter",
                "sample.extract-only",
            )
            self.assertEqual(scan_exit, 0, scan)
            resolution = scan["adapter_resolution"][0]
            self.assertEqual(resolution["adapter"], "sample.extract-only")
            self.assertEqual(resolution["round_trip_level"], "extract_only")
            self.assertIn("apply", resolution["blocked_phases"])
            self.assertIn("report-only review", scan["next"])
            self.assertIn("Rebuild and apply remain blocked", scan["next"])
            capability = _read_state(project, "capability-report.json")
            provenance = capability["selected_sources"][0]["adapter_provenance"]
            self.assertEqual(provenance["id"], "sample.extract-only")
            self.assertEqual(len(provenance["checksum"]), 64)

            check_exit, check = _run("check", project.as_posix(), "--target", "catalog.fr.samplecat")
            self.assertEqual(check_exit, 0, check)
            self.assertEqual(check["status"], "pass")
            self.assertEqual(check["pairs"][0]["adapter_kind"], "project_local")
            fingerprint_roles = {item["role"] for item in check["file_fingerprints"]}
            self.assertTrue({"source", "target", "adapter_descriptor", "adapter_entrypoint"}.issubset(fingerprint_roles))
            inventory = _read_state(project, "inventory.json")
            extracted = _read_state(project, "extracted-segments.json")
            source_validation = _read_state(project, "source-validation.json")
            self.assertEqual(inventory["files"][0]["items"][0]["id"], "title")
            self.assertEqual(inventory["files"][0]["execution_mode"], "runtime_project_local_adapter")
            self.assertEqual(source_validation["status"], "pass")
            self.assertEqual(extracted["status"], "ready_for_review")
            self.assertEqual(extracted["files"][0]["execution_mode"], "runtime_project_local_adapter")
            run_dir = project / ".localize-anything" / "adapter-runs"
            self.assertTrue(run_dir.is_dir())
            run_artifacts = sorted(run_dir.glob("*.json"))
            self.assertGreaterEqual(len(run_artifacts), 4)
            run_payload = json.loads(run_artifacts[0].read_text(encoding="utf-8"))
            self.assertEqual(run_payload["schema"], "localize-anything-project-adapter-run-v1")
            self.assertEqual(run_payload["execution_mode"], "runtime_project_local_adapter")
            self.assertTrue((run_dir / run_payload["stderr"]).is_file())

            review_exit, review = _run("review", project.as_posix(), "--target", "catalog.fr.samplecat")
            self.assertEqual(review_exit, 0, review)
            packet = json.loads(Path(review["review_packet"]).read_text(encoding="utf-8"))
            self.assertEqual(packet["review_mode"], "report_only")
            self.assertEqual(packet["files"][0]["execution_mode"], "runtime_project_local_adapter")
            self.assertEqual(packet["files"][0]["segments"][0]["target"], "Bonjour")

    def test_artifact_staleness_blocks_review_for_source_descriptor_checksum_and_extraction_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = _sample_project(Path(directory))
            adapter_root = _copy_sample_adapter(project)
            self.assertEqual(_scan_selected(project)[0], 0)
            self.assertEqual(_run("check", project.as_posix(), "--target", "catalog.fr.samplecat")[0], 0)
            self.assertEqual(_run("review", project.as_posix(), "--target", "catalog.fr.samplecat")[0], 0)

            (project / "catalog.fr.samplecat").write_text('{"messages": [{"id": "title", "text": "Salut"}]}', encoding="utf-8")
            stale_exit, stale = _run("review", project.as_posix(), "--target", "catalog.fr.samplecat")
            self.assertEqual(stale_exit, 2)
            self.assertIn("changed since deterministic-check.json", stale["error"])

            (project / "catalog.fr.samplecat").write_text('{"messages": [{"id": "title", "text": "Bonjour"}]}', encoding="utf-8")
            self.assertEqual(_run("check", project.as_posix(), "--target", "catalog.fr.samplecat")[0], 0)
            self.assertEqual(_run("review", project.as_posix(), "--target", "catalog.fr.samplecat")[0], 0)
            descriptor = json.loads((adapter_root / "adapter.json").read_text(encoding="utf-8"))
            descriptor["version"] = "0.1.1"
            (adapter_root / "adapter.json").write_text(json.dumps(descriptor), encoding="utf-8")
            descriptor_exit, descriptor_stale = _run("review", project.as_posix(), "--target", "catalog.fr.samplecat")
            self.assertEqual(descriptor_exit, 2)
            self.assertIn("changed since deterministic-check.json", descriptor_stale["error"])

            descriptor["version"] = "0.1.0"
            (adapter_root / "adapter.json").write_text(json.dumps(descriptor), encoding="utf-8")
            self.assertEqual(_run("check", project.as_posix(), "--target", "catalog.fr.samplecat")[0], 0)
            self.assertEqual(_run("review", project.as_posix(), "--target", "catalog.fr.samplecat")[0], 0)
            adapter_text = (adapter_root / "adapter.py").read_text(encoding="utf-8")
            (adapter_root / "adapter.py").write_text(adapter_text + "\n# checksum drift\n", encoding="utf-8")
            checksum_exit, checksum_stale = _run("review", project.as_posix(), "--target", "catalog.fr.samplecat")
            self.assertEqual(checksum_exit, 2)
            self.assertIn("checksum mismatch", checksum_stale["error"])

            descriptor["checksum"]["value"] = hashlib.sha256((adapter_root / "adapter.py").read_bytes()).hexdigest()
            (adapter_root / "adapter.json").write_text(json.dumps(descriptor), encoding="utf-8")
            self.assertEqual(_run("check", project.as_posix(), "--target", "catalog.fr.samplecat")[0], 0)
            self.assertEqual(_run("review", project.as_posix(), "--target", "catalog.fr.samplecat")[0], 0)
            findings = project / "findings.json"
            findings.write_text(json.dumps({"reviewer": "independent-agent", "findings": []}), encoding="utf-8")
            (project / ".localize-anything" / "extracted-segments.json").unlink()
            missing_exit, missing = _run("review", project.as_posix(), "--target", "catalog.fr.samplecat", "--findings", findings.as_posix())
            self.assertEqual(missing_exit, 2)
            self.assertIn("Extracted segments artifact is missing", missing["error"])

    def test_descriptor_and_selection_failures_are_blockers(self) -> None:
        cases = [
            ("malformed", "{", "descriptor_invalid"),
            ("bad.checksum", None, "checksum_mismatch", {"checksum": {"type": "sha256", "value": "0" * 64}}),
            ("missing.entrypoint", None, "entrypoint_missing", {"entrypoints": {"detect": ["python3", "missing.py"], "inventory": ["python3", "missing.py"], "extract": ["python3", "missing.py"], "validate_source": ["python3", "missing.py"]}}),
            ("overclaim.rebuild", None, "capability_not_allowed", {"capabilities": ["detect", "inventory", "extract", "validate_source", "rebuild"], "round_trip_level": "full_round_trip"}),
            (
                "inspect.only",
                None,
                "capability_not_allowed",
                {
                    "capabilities": ["detect", "inventory", "validate_source"],
                    "round_trip_level": "inspect_only",
                    "entrypoints": {"detect": ["python3", "adapter.py"], "inventory": ["python3", "adapter.py"], "validate_source": ["python3", "adapter.py"]},
                },
            ),
            ("shell.meta", None, "entrypoint_missing", {"entrypoints": {"detect": ["python3", "adapter.py;rm"], "inventory": ["python3", "adapter.py;rm"], "extract": ["python3", "adapter.py;rm"], "validate_source": ["python3", "adapter.py;rm"]}}),
            ("undeclared.dependency", None, "undeclared_dependency", {"entrypoints": {"detect": ["node", "adapter.py"], "inventory": ["node", "adapter.py"], "extract": ["node", "adapter.py"], "validate_source": ["node", "adapter.py"]}}),
        ]
        for case in cases:
            adapter_id, raw_descriptor, expected = case[:3]
            overrides = case[3] if len(case) == 4 else {}
            with self.subTest(adapter_id=adapter_id):
                with tempfile.TemporaryDirectory() as directory:
                    project = _sample_project(Path(directory))
                    if raw_descriptor is not None:
                        _install_raw_descriptor(project, adapter_id, raw_descriptor)
                    else:
                        _install_scripted_adapter(project, adapter_id, _sample_script(), overrides)
                    exit_code, result = _scan_selected(project, adapter_id)
                    self.assertEqual(exit_code, 2)
                    self.assertIn(expected, result["error"])
                    capability = _read_state(project, "capability-report.json")
                    self.assertEqual(capability["blocked_sources"][0]["reason_code"], expected)

    def test_adapter_runtime_failures_do_not_generate_success_artifacts(self) -> None:
        cases = {
            "timeout.case": ("import time; time.sleep(10)", "adapter_timeout"),
            "nonzero.case": ("import sys; sys.exit(7)", "adapter_nonzero_exit"),
            "invalid.json": ("print('not json')", "adapter_invalid_json"),
            "wrong.schema": ("import json; print(json.dumps({'schema': 'wrong', 'status': 'pass'}))", "adapter_schema_violation"),
            "too.large": (f"import sys; sys.stdout.write('x' * {MAX_STDOUT_BYTES + 1})", "adapter_output_too_large"),
            "writes.source": (
                "import json, sys\n"
                "from pathlib import Path\n"
                "request = json.loads(sys.stdin.read())\n"
                "Path(request['project_root'], request['source']).write_text('{\"messages\": []}', encoding='utf-8')\n"
                "phase = request['phase']\n"
                "schema = f\"localize-anything-project-adapter-{phase.replace('_', '-')}-result-v1\"\n"
                "print(json.dumps({'schema': schema, 'status': 'pass', 'detected': True}))",
                "capability_not_allowed",
            ),
        }
        for adapter_id, (body, expected) in cases.items():
            with self.subTest(adapter_id=adapter_id):
                with tempfile.TemporaryDirectory() as directory:
                    project = _sample_project(Path(directory))
                    script = "from __future__ import annotations\n" + body + "\n"
                    _install_scripted_adapter(project, adapter_id, script)
                    self.assertEqual(_scan_selected(project, adapter_id)[0], 0)
                    check_exit, check = _run("check", project.as_posix(), "--target", "catalog.fr.samplecat")
                    self.assertEqual(check_exit, 1)
                    self.assertEqual(check["status"], "fail")
                    finding = check["findings"][0]
                    self.assertEqual(finding["kind"], expected)
                    if expected == "adapter_output_too_large":
                        self.assertIn(str(MAX_STDOUT_BYTES + 1), finding["message"])
                        self.assertIn(str(MAX_STDOUT_BYTES), finding["message"])
                        self.assertEqual(finding["evidence"]["stdout_bytes"], MAX_STDOUT_BYTES + 1)
                        self.assertEqual(finding["evidence"]["max_stdout_bytes"], MAX_STDOUT_BYTES)
                    run_payloads = [
                        json.loads(path.read_text(encoding="utf-8"))
                        for path in sorted((project / ".localize-anything" / "adapter-runs").glob("*.json"))
                    ]
                    self.assertTrue(run_payloads)
                    self.assertTrue(all(item["execution_mode"] == "runtime_project_local_adapter" for item in run_payloads))
                    extracted = _read_state(project, "extracted-segments.json")
                    self.assertEqual(extracted["status"], "blocked")
                    review_exit, review = _run("review", project.as_posix(), "--target", "catalog.fr.samplecat")
                    self.assertEqual(review_exit, 2)
                    self.assertIn("Deterministic check failed", review["error"])

    def test_path_escape_and_bad_adapter_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = _sample_project(Path(directory))
            exit_code, result = _scan_selected(project, "../sample")
            self.assertEqual(exit_code, 2)
            self.assertIn("descriptor_invalid", result["error"])

        with tempfile.TemporaryDirectory() as directory:
            project = _sample_project(Path(directory))
            adapter_root = project / ".localize-anything" / "adapters" / "escape.case"
            adapter_root.mkdir(parents=True)
            outside = project / "outside.py"
            outside.write_text(_sample_script(), encoding="utf-8")
            (adapter_root / "adapter.py").symlink_to(outside)
            checksum = hashlib.sha256(outside.read_bytes()).hexdigest()
            (adapter_root / "adapter.json").write_text(json.dumps(_manifest("escape.case", checksum)), encoding="utf-8")
            exit_code, result = _scan_selected(project, "escape.case")
            self.assertEqual(exit_code, 2)
            self.assertIn("path_escape", result["error"])


def _sample_project(root: Path) -> Path:
    project = root / "project"
    project.mkdir()
    (project / "catalog.samplecat").write_text('{"messages": [{"id": "title", "text": "Hello"}]}', encoding="utf-8")
    (project / "catalog.fr.samplecat").write_text('{"messages": [{"id": "title", "text": "Bonjour"}]}', encoding="utf-8")
    return project


def _copy_sample_adapter(project: Path) -> Path:
    destination = project / ".localize-anything" / "adapters" / "sample.extract-only"
    shutil.copytree(SAMPLE_ADAPTER, destination)
    return destination


def _install_raw_descriptor(project: Path, adapter_id: str, raw_descriptor: str) -> Path:
    destination = project / ".localize-anything" / "adapters" / adapter_id
    destination.mkdir(parents=True)
    (destination / "adapter.json").write_text(raw_descriptor, encoding="utf-8")
    return destination


def _install_scripted_adapter(project: Path, adapter_id: str, script: str, overrides: dict[str, object] | None = None) -> Path:
    destination = project / ".localize-anything" / "adapters" / adapter_id
    destination.mkdir(parents=True)
    (destination / "adapter.py").write_text(script, encoding="utf-8")
    checksum = hashlib.sha256((destination / "adapter.py").read_bytes()).hexdigest()
    manifest = _manifest(adapter_id, checksum)
    for key, value in (overrides or {}).items():
        manifest[key] = value
    (destination / "adapter.json").write_text(json.dumps(manifest), encoding="utf-8")
    return destination


def _manifest(adapter_id: str, checksum: str) -> dict[str, object]:
    return {
        "protocol_version": "0.1",
        "id": adapter_id,
        "name": "Fault fixture",
        "version": "0.1.0",
        "implementation_status": "experimental",
        "trust": "project",
        "adapter_type": "scripted",
        "formats": ["sample-catalog"],
        "extensions": [".samplecat"],
        "capabilities": ["detect", "inventory", "extract", "validate_source"],
        "round_trip_level": "extract_only",
        "permissions": ["read_project", "execute"],
        "runtime": {"type": "python", "version": ">=3.11", "dependencies": []},
        "entrypoints": {
            "detect": ["python3", "adapter.py"],
            "inventory": ["python3", "adapter.py"],
            "extract": ["python3", "adapter.py"],
            "validate_source": ["python3", "adapter.py"],
        },
        "checksum": {"type": "sha256", "value": checksum},
        "source_scope": {"paths": ["catalog.samplecat"]},
        "provenance": "Synthetic fault fixture",
        "notes": [],
        "limitations": ["No write phases."],
    }


def _sample_script() -> str:
    return textwrap.dedent(
        """
        from __future__ import annotations
        import json
        import sys

        request = json.loads(sys.stdin.read())
        phase = request["phase"]
        schema = f"localize-anything-project-adapter-{phase.replace('_', '-')}-result-v1"
        if phase == "detect":
            payload = {"detected": True}
        elif phase == "inventory":
            payload = {"items": [{"id": "title"}]}
        elif phase == "extract":
            payload = {
                "source_segments": [{"segment_id": "sample:title", "source": "Hello", "context": {"resource_key": "title"}}],
                "target_segments": [{"segment_id": "sample:title", "source": "Bonjour", "context": {"resource_key": "title"}}],
            }
        else:
            payload = {"validation": {"status": "pass", "items": []}}
        print(json.dumps({"schema": schema, "status": "pass", **payload}))
        """
    ).lstrip()


def _scan_selected(project: Path, adapter_id: str = "sample.extract-only") -> tuple[int, dict[str, object]]:
    return _run(
        "scan",
        project.as_posix(),
        "--source-locale",
        "en",
        "--target-locale",
        "fr",
        "--source",
        "catalog.samplecat",
        "--adapter",
        adapter_id,
    )


def _read_state(project: Path, name: str) -> dict[str, object]:
    return json.loads((project / ".localize-anything" / name).read_text(encoding="utf-8"))


def _run(*argv: str) -> tuple[int, dict[str, object]]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(list(argv))
    if exit_code == 2:
        return exit_code, {"error": stderr.getvalue()}
    return exit_code, json.loads(stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
