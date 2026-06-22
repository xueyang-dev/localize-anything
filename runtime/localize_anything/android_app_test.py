from __future__ import annotations

import fnmatch
import shutil
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .agent import run_agent
from .android_strings_adapter import extract_segments as extract_android_segments
from .android_strings_adapter import target_resource_path, validate_pair as validate_android_strings
from .apply import create_apply_plan, execute_apply
from .chinese_draft import DEFAULT_PROVIDER, DEFAULT_QUALITY_CLAIM, generate_chinese_draft_segments
from .io_utils import read_json, read_jsonl, sha256_file, write_json, write_jsonl
from .json_adapter import extract_placeholders
from .project import IGNORED_DIRECTORY_NAMES, IGNORED_DIRECTORY_PREFIXES, IGNORED_FILE_GLOBS, inspect_project


def run_android_app_test(
    project_root: Path,
    source_file: str | None,
    target_locale: str,
    source_locale: str = "en-US",
    output_root: Path | None = None,
    run_id: str = "android-app-test",
    max_segments: int = 20,
    limit_tokens: int = 4000,
    generated_dir: Path | None = None,
    generated: Path | None = None,
    local_chinese_draft: bool = False,
    require_real_generation: bool = False,
) -> dict[str, Any]:
    """Run an Android source-project localization test against an isolated copy.

    This command intentionally applies to a staged project copy, never to the
    source project. It is the end-to-end Android engineering proof: route,
    generate draft output, package, decide, apply to the copy, and validate the
    copied app resource after apply.
    """

    project_root = project_root.resolve()
    output_root = (output_root or project_root.parent / "localize-anything-output" / "android-app-tests").resolve()
    test_dir = output_root / run_id
    if _is_relative_to(test_dir, project_root):
        raise ValueError("Android app test output must be outside the source project root")
    if sum(1 for value in (generated_dir, generated, local_chinese_draft) if value) > 1:
        raise ValueError("Use only one Android app test generation input: generated_dir, generated, or local_chinese_draft")
    if require_real_generation and not (generated_dir or generated or local_chinese_draft):
        raise ValueError("Android app test requires generated_dir, generated, or local_chinese_draft when require_real_generation is true")
    if test_dir.exists():
        raise ValueError(f"Android app test output already exists: {test_dir}")
    test_dir.mkdir(parents=True)

    source_files = [source_file.replace("\\", "/")] if source_file else _select_android_source_files(project_root)
    original_states = _source_states(project_root, source_files, target_locale)

    app_copy = test_dir / "app-copy"
    shutil.copytree(project_root, app_copy, ignore=_copy_ignore)
    for selected in source_files:
        copy_source = app_copy / selected
        if not copy_source.is_file():
            raise ValueError(f"Copied Android source file is missing: {copy_source}")

    local_draft_artifacts: dict[str, str] = {}
    agent_generated = generated
    if local_chinese_draft:
        local_draft_artifacts = _write_local_chinese_draft(app_copy, source_files, source_locale, target_locale, test_dir)
        agent_generated = Path(local_draft_artifacts["generated_segments"])

    agent_output_root = test_dir / "agent"
    agent_run_id = f"{run_id}-agent"
    agent_result = run_agent(
        app_copy,
        target_locale,
        source_locale,
        source_files,
        agent_output_root,
        agent_run_id,
        max_segments,
        limit_tokens,
        generated_dir=generated_dir,
        generated=agent_generated,
        synthetic_draft=not (generated_dir or agent_generated),
    )
    if agent_result["status"] != "draft_package_created":
        raise ValueError(f"Android app test agent run failed: {agent_result['status']}")

    delivery_dir = Path(agent_result["artifacts"]["delivery_directory"])
    decision = read_json(Path(agent_result["artifacts"]["delivery_decision"]))
    apply_result = execute_apply(delivery_dir, app_copy, agent_run_id)
    apply_result_path = test_dir / "apply-result.json"
    write_json(apply_result_path, apply_result)

    post_apply_qa = _validate_copied_targets(app_copy, source_files, target_locale)
    post_apply_qa_path = test_dir / "post-apply-android-qa.json"
    write_json(post_apply_qa_path, post_apply_qa)

    post_apply_plan = create_apply_plan(delivery_dir, app_copy)
    post_apply_plan_path = test_dir / "post-apply-plan.json"
    write_json(post_apply_plan_path, post_apply_plan)

    original_after_states = _source_states(project_root, source_files, target_locale)
    source_preserved = original_states == original_after_states
    target_files = [
        target_resource_path(app_copy / selected, target_locale, app_copy).as_posix()
        for selected in source_files
    ]
    generated_segments_path = agent_result["artifacts"].get("generated_segments")
    generation = _generation_evidence(agent_result, generated_segments_path)
    real_generation_satisfied = _real_generation_satisfied(generation)
    status = (
        "pass"
        if source_preserved
        and post_apply_qa["status"] in {"pass", "pass_with_warnings"}
        and (not require_real_generation or real_generation_satisfied)
        else "fail"
    )
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime", "agent"],
        "run_id": run_id,
        "status": status,
        "android": {
            "project_root": project_root.as_posix(),
            "app_copy": app_copy.as_posix(),
            "source_file": source_files[0],
            "source_files": source_files,
            "target_locale": target_locale,
            "target_file": target_files[0],
            "target_files": target_files,
            "adapter": "core.android-strings",
        },
        "generation": generation,
        "source_preservation": {
            "source_file_before": original_states[0]["source"],
            "source_file_after": original_after_states[0]["source"],
            "target_file_before": original_states[0]["target"],
            "target_file_after": original_after_states[0]["target"],
            "files": [
                {
                    "source_file": before["source_file"],
                    "target_file": before["target_file"],
                    "before": before,
                    "after": after,
                    "mutated": before != after,
                }
                for before, after in zip(original_states, original_after_states, strict=True)
            ],
            "original_project_mutated": not source_preserved,
        },
        "summary": {
            "segment_count": agent_result["summary"]["segment_count"],
            "batch_count": agent_result["summary"]["batch_count"],
            "output_count": agent_result["summary"]["output_count"],
            "agent_status": agent_result["status"],
            "delivery_decision_status": decision["status"],
            "real_generation_required": require_real_generation,
            "real_generation_satisfied": real_generation_satisfied,
            "apply_created": apply_result["summary"]["created"],
            "apply_replaced": apply_result["summary"]["replaced"],
            "localized_file_count": len(target_files),
            "post_apply_qa_status": post_apply_qa["status"],
            "post_apply_blocking_count": post_apply_qa["summary"]["blocking_count"],
            "post_apply_warning_count": post_apply_qa["summary"]["warning_count"],
        },
        "artifacts": {
            "test_directory": test_dir.as_posix(),
            "app_copy": app_copy.as_posix(),
            "agent_summary": agent_result["artifacts"]["agent_summary"],
            "generated_segments": generated_segments_path,
            "delivery_directory": agent_result["artifacts"]["delivery_directory"],
            "delivery_decision": agent_result["artifacts"]["delivery_decision"],
            "delivery_decision_markdown": agent_result["artifacts"]["delivery_decision_markdown"],
            "apply_result": apply_result_path.as_posix(),
            "post_apply_qa": post_apply_qa_path.as_posix(),
            "post_apply_plan": post_apply_plan_path.as_posix(),
        },
        "next_actions": _next_actions(status, decision, post_apply_qa),
    }
    if local_draft_artifacts:
        report["artifacts"]["local_chinese_draft"] = local_draft_artifacts["generated_segments"]
        report["artifacts"]["local_chinese_draft_report"] = local_draft_artifacts["report"]
    report_path = test_dir / "android-app-test-report.json"
    write_json(report_path, report)
    report["artifacts"]["android_app_test_report"] = report_path.as_posix()
    write_json(report_path, report)
    return report


def _write_local_chinese_draft(
    app_copy: Path,
    source_files: list[str],
    source_locale: str,
    target_locale: str,
    test_dir: Path,
) -> dict[str, str]:
    draft_dir = test_dir / "local-chinese-draft"
    segments: list[dict[str, Any]] = []
    for source_file in source_files:
        source_path = app_copy / source_file
        segments.extend(extract_android_segments(source_path, source_locale, source_file))

    segments_path = draft_dir / "segments.jsonl"
    generated_path = draft_dir / "generated.jsonl"
    report_path = draft_dir / "local-chinese-draft-report.json"
    generated = generate_chinese_draft_segments(segments, target_locale, DEFAULT_PROVIDER, DEFAULT_QUALITY_CLAIM)
    write_jsonl(segments_path, segments)
    write_jsonl(generated_path, generated)

    placeholder_mismatches = [
        segment["segment_id"]
        for segment in generated
        if sorted(str(item) for item in segment.get("constraints", {}).get("placeholders", []))
        != extract_placeholders(str(segment.get("target", "")))
    ]
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "status": "fail" if placeholder_mismatches else "pass",
        "input_segments": segments_path.as_posix(),
        "generated_segments": generated_path.as_posix(),
        "target_locale": target_locale,
        "provider": DEFAULT_PROVIDER,
        "quality_claim": DEFAULT_QUALITY_CLAIM,
        "summary": {
            "source_file_count": len(source_files),
            "segment_count": len(segments),
            "generated_segment_count": len(generated),
            "placeholder_mismatch_count": len(placeholder_mismatches),
        },
        "items": [
            {
                "category": "placeholder_parity",
                "severity": "blocking",
                "message": f"Generated draft target lost placeholders for {segment_id}",
                "segment_id": segment_id,
            }
            for segment_id in placeholder_mismatches
        ],
    }
    write_json(report_path, report)
    if placeholder_mismatches:
        raise ValueError(f"Local Chinese draft generation failed placeholder parity for {len(placeholder_mismatches)} segment(s)")
    return {"segments": segments_path.as_posix(), "generated_segments": generated_path.as_posix(), "report": report_path.as_posix()}


def _file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "sha256": None}
    if not path.is_file():
        return {"exists": True, "sha256": None, "kind": "non_file"}
    return {"exists": True, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def _select_android_source_files(project_root: Path) -> list[str]:
    inspection = inspect_project(project_root)
    candidates = sorted(
        item["path"]
        for item in inspection.get("supported_files", [])
        if item.get("adapter") == "core.android-strings" and "/res/values/strings.xml" in f"/{item.get('path', '')}"
    )
    if not candidates:
        raise ValueError("No Android source strings.xml file was found under res/values")
    return candidates


def _source_states(project_root: Path, source_files: list[str], target_locale: str) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for source_file in source_files:
        source = project_root / source_file
        if not source.is_file():
            raise ValueError(f"Android source file does not exist: {source}")
        target = project_root / target_resource_path(source, target_locale, project_root)
        states.append(
            {
                "source_file": source_file,
                "target_file": target.relative_to(project_root).as_posix(),
                "source": _file_state(source),
                "target": _file_state(target),
            }
        )
    return states


def _validate_copied_targets(app_copy: Path, source_files: list[str], target_locale: str) -> dict[str, Any]:
    per_file: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for source_file in source_files:
        source = app_copy / source_file
        target = app_copy / target_resource_path(source, target_locale, app_copy)
        qa = validate_android_strings(source, target)
        per_file.append(
            {
                "source_file": source_file,
                "target_file": target.relative_to(app_copy).as_posix(),
                "status": qa["status"],
                "summary": qa["summary"],
            }
        )
        items.extend(qa.get("items", []))
    blocking = sum(int(item["summary"]["blocking_count"]) for item in per_file)
    warnings = sum(int(item["summary"]["warning_count"]) for item in per_file)
    status = "fail" if blocking else "pass_with_warnings" if warnings else "pass"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["adapter"],
        "status": status,
        "summary": {
            "file_count": len(source_files),
            "blocking_count": blocking,
            "warning_count": warnings,
        },
        "files": per_file,
        "items": items,
    }


def _generation_evidence(agent_result: dict[str, Any], generated_segments_path: str | None) -> dict[str, Any]:
    mode = agent_result.get("artifacts", {}).get("provider_generation") and "direct_provider"
    mode = agent_result.get("generation", {}).get("mode") or mode or "unknown"
    evidence: dict[str, Any] = {
        "mode": mode,
        "quality_claim": "none",
        "purpose": "full_android_app_engineering_test",
    }
    if not generated_segments_path:
        return evidence
    records = read_jsonl(Path(generated_segments_path))
    providers = sorted(
        {
            str(record.get("generation", {}).get("provider") or record.get("generation", {}).get("kind") or "unknown")
            for record in records
        }
    )
    quality_claims = sorted({str(record.get("generation", {}).get("quality_claim") or "none") for record in records})
    evidence.update(
        {
            "provider": providers[0] if len(providers) == 1 else "mixed",
            "providers": providers,
            "quality_claim": quality_claims[0] if len(quality_claims) == 1 else "mixed",
            "quality_claims": quality_claims,
            "generated_segment_count": len(records),
        }
    )
    if evidence["mode"] == "unknown":
        evidence["mode"] = "synthetic_draft" if providers == ["synthetic"] else "generated_segments"
    return evidence


def _real_generation_satisfied(generation: dict[str, Any]) -> bool:
    return generation.get("mode") != "synthetic_draft" and generation.get("quality_claim") not in {None, "", "none"}


def _copy_ignore(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        normalized = name.lower()
        if normalized in IGNORED_DIRECTORY_NAMES:
            ignored.add(name)
            continue
        if any(normalized.startswith(prefix) for prefix in IGNORED_DIRECTORY_PREFIXES):
            ignored.add(name)
            continue
        if any(fnmatch.fnmatch(normalized, pattern) for pattern in IGNORED_FILE_GLOBS):
            ignored.add(name)
    return ignored


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _next_actions(status: str, decision: dict[str, Any], qa: dict[str, Any]) -> list[str]:
    if status != "pass":
        actions = ["Inspect android-app-test-report.json and fix failed source-preservation or post-apply QA evidence."]
        if qa.get("status") == "fail":
            actions.append("Resolve Android resource QA blockers before treating the localized app copy as valid.")
        return actions
    if decision.get("status") == "owner_review_required":
        return [
            "Inspect the localized app copy and delivery decision report.",
            "Use a real LLM/provider generated output before making translation quality claims.",
        ]
    return ["Inspect the localized app copy before reusing the generated language resource."]
