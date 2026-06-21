from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from . import PROTOCOL_VERSION
from .android_strings_adapter import extract_segments as extract_android_strings
from .android_strings_adapter import validate_pair as validate_android_strings
from .apply import create_apply_plan, render_apply_plan_markdown
from .dashboard import build_delivery_dashboard, render_dashboard_markdown
from .delivery import package_delivery
from .delivery_decision import create_delivery_decision_report, render_delivery_decision_markdown
from .generation import (
    collect_generated_handoff,
    create_draft_request,
    create_generation_handoff,
    render_generation_instructions,
    write_handoff_prompts,
)
from .gettext_adapter import extract_segments as extract_po_segments
from .gettext_adapter import validate_pair as validate_po_pair
from .io_utils import read_json, read_jsonl, write_json, write_jsonl
from .ios_strings_adapter import extract_segments as extract_ios_strings
from .ios_strings_adapter import validate_pair as validate_ios_strings
from .json_adapter import extract_segments as extract_json_segments
from .json_adapter import validate_pair as validate_json_pair
from .markup_adapter import extract_segments as extract_markup_segments
from .markup_adapter import validate_pair as validate_markup_pair
from .modes import DEFAULT_OPERATING_MODE, DEFAULT_REFERENCE_POLICY_BY_MODE, mode_contract, resolve_mode_policy
from .planning import create_batch_plan
from .project import initialize_project, inspect_project, record_project_session, session_index_path
from .reference import create_reference_plan
from .retrieval import build_work_packet
from .reflection import create_llm_review_request, render_llm_review_prompt
from .review_sheet import write_review_sheet
from .staging import stage_generated
from .structured_adapter import extract_segments as extract_structured_segments
from .structured_adapter import validate_pair as validate_structured_pair
from .subtitle_adapter import extract_segments as extract_subtitle_segments
from .subtitle_adapter import validate_pair as validate_subtitle_pair
from .tabular_adapter import extract_segments as extract_tabular_segments
from .tabular_adapter import validate_pair as validate_tabular_pair
from .xcstrings_adapter import extract_segments as extract_xcstrings
from .xcstrings_adapter import validate_pair as validate_xcstrings
from .xliff_adapter import extract_segments as extract_xliff_segments
from .xliff_adapter import validate_pair as validate_xliff_pair


Extractor = Callable[[Path, str, str | None], list[dict[str, Any]]]


EXTRACTORS: dict[str, Extractor] = {
    "core.android-strings": extract_android_strings,
    "core.gettext-po": extract_po_segments,
    "core.ios-strings": extract_ios_strings,
    "core.json-locale": extract_json_segments,
    "core.markup": extract_markup_segments,
    "core.subtitles": extract_subtitle_segments,
    "core.tabular": extract_tabular_segments,
    "core.yaml-toml": lambda path, source_locale, source_path: extract_structured_segments(
        path, source_locale, source_path, _structured_format(path)
    ),
    "core.xcstrings": extract_xcstrings,
    "core.xliff": extract_xliff_segments,
}


def run_localize(
    project_root: Path,
    source_locale: str,
    target_locales: list[str],
    source_files: list[str] | None = None,
    output_root: Path | None = None,
    run_id: str | None = None,
    max_segments: int = 80,
    limit_tokens: int = 4000,
    handoff_only: bool = False,
    generated_dir: Path | None = None,
    generated: Path | None = None,
    synthetic_draft: bool = False,
    workflow_depth: str = "ask",
    preflight_mode: str = "auto",
    privacy_mode: str = "standard",
    data_classification: str = "internal",
    delivery_status: str = "draft_package",
    operating_mode: str | None = None,
    reference_policy: str | None = None,
) -> dict[str, Any]:
    if len(target_locales) != 1:
        raise ValueError("localize-run currently accepts exactly one target locale per run")
    if sum(1 for value in (generated_dir, generated, synthetic_draft) if value) > 1:
        raise ValueError("Use only one generation input: --generated-dir, --generated, or --synthetic-draft")
    if not handoff_only and not (generated_dir or generated or synthetic_draft):
        raise ValueError("No generated translation input was provided. Use --handoff-only or provide --generated-dir/--generated.")

    project_root = project_root.resolve()
    target_locale = target_locales[0]
    operating_mode, reference_policy = resolve_mode_policy(operating_mode, reference_policy)
    output_root = (output_root or project_root / "localize-anything-output").resolve()
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / run_id
    if run_dir.exists():
        raise ValueError(f"Run output already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    inspection = inspect_project(project_root)
    selected_files = _select_source_files(inspection, source_locale, source_files)
    initialized = initialize_project(
        project_root,
        source_locale,
        selected_files,
        target_locales,
        operating_mode,
        reference_policy,
        workflow_depth,
        preflight_mode,
        privacy_mode,
        data_classification,
    )
    state_dir = Path(initialized["state_directory"])

    segments = _extract_all(project_root, inspection, selected_files, source_locale)
    if not segments:
        raise ValueError("Selected source files did not produce any translatable segments")
    segments_path = run_dir / "segments.jsonl"
    write_jsonl(segments_path, segments)

    inventory_by_path = {item["path"]: item for item in inspection["supported_files"]}
    candidate_segments, preserved_segments, reference_plan = create_reference_plan(
        project_root,
        inventory_by_path,
        selected_files,
        source_locale,
        target_locale,
        segments,
        state_dir,
        operating_mode,
        reference_policy,
    )
    reference_plan_path = run_dir / "reference-plan.json"
    write_json(reference_plan_path, reference_plan)

    plan = create_batch_plan(candidate_segments, source_locale, target_locales, max_segments, operating_mode, reference_policy)
    plan_path = run_dir / "batch-plan.json"
    write_json(plan_path, plan)

    packet_dir = run_dir / "work-packets"
    request_dir = run_dir / "draft-requests"
    for batch in plan["batches"]:
        packet = build_work_packet(plan, batch["batch_id"], candidate_segments, state_dir, target_locale, limit_tokens, operating_mode=operating_mode, reference_policy=reference_policy)
        write_json(packet_dir / f"{batch['batch_id']}.json", packet)
        write_json(request_dir / f"{batch['batch_id']}.json", create_draft_request(packet))

    generated_batches_dir = (generated_dir or run_dir / "generated-batches").resolve()
    handoff = create_generation_handoff(packet_dir, request_dir, generated_batches_dir, target_locale)
    handoff_path = run_dir / "generation-handoff.json"
    write_json(handoff_path, handoff)
    prompt_dir = run_dir / "prompts"
    response_dir = run_dir / "responses"
    response_dir.mkdir(parents=True, exist_ok=True)
    prompt_manifest = write_handoff_prompts(handoff, prompt_dir)
    prompt_manifest_path = run_dir / "prompt-manifest.json"
    write_json(prompt_manifest_path, prompt_manifest)
    generation_readme_path = run_dir / "generation-README.md"
    generation_readme_path.write_text(
        render_generation_instructions(handoff, prompt_dir, response_dir, run_dir / "generated.jsonl"),
        encoding="utf-8",
        newline="\n",
    )

    if handoff_only:
        summary = _summary(
            run_id,
            "handoff_ready",
            project_root,
            source_locale,
            target_locale,
            selected_files,
            run_dir,
            segments_path,
            plan_path,
            handoff_path,
            len(segments),
            len(plan["batches"]),
            generation_mode="handoff_only",
            reference_plan_path=reference_plan_path,
            operating_mode=operating_mode,
            reference_policy=reference_policy,
            reference_summary=reference_plan["summary"],
            prompt_manifest_path=prompt_manifest_path,
            generation_readme_path=generation_readme_path,
        )
        return _write_run_summary(summary, run_dir, inspection)

    if synthetic_draft:
        _write_synthetic_batches(handoff, target_locale)
        generation_mode = "synthetic_draft"
    elif generated:
        _write_batches_from_combined(generated, handoff)
        generation_mode = "combined_generated"
    else:
        generation_mode = "generated_dir"

    generated_path = run_dir / "generated.jsonl"
    collect_result = collect_generated_handoff(handoff, generated_path)
    collect_path = run_dir / "generation-collect.json"
    write_json(collect_path, collect_result)
    if collect_result["status"] == "fail":
        summary = _summary(
            run_id,
            "generation_failed",
            project_root,
            source_locale,
            target_locale,
            selected_files,
            run_dir,
            segments_path,
            plan_path,
            handoff_path,
            len(segments),
            len(plan["batches"]),
            generation_mode=generation_mode,
            reference_plan_path=reference_plan_path,
            operating_mode=operating_mode,
            reference_policy=reference_policy,
            reference_summary=reference_plan["summary"],
            prompt_manifest_path=prompt_manifest_path,
            generation_readme_path=generation_readme_path,
            collect_path=collect_path,
            generated_path=generated_path,
            generation_status=collect_result["status"],
        )
        return _write_run_summary(summary, run_dir, inspection)

    generated_segments = read_jsonl(generated_path)
    delivery_segments = [*generated_segments, *preserved_segments]
    review_markdown_path = run_dir / "review-sheet.md"
    review_csv_path = run_dir / "review-sheet.csv"
    review_sheet_path = run_dir / "review-sheet.json"
    review_sheet = write_review_sheet(delivery_segments, review_markdown_path, review_csv_path)
    write_json(review_sheet_path, review_sheet)
    llm_review_request = create_llm_review_request(
        delivery_segments,
        source_locale,
        target_locale,
        collect_result.get("items", []),
        run_id,
    )
    llm_review_request_path = run_dir / "llm-review-request.json"
    llm_review_prompt_path = run_dir / "llm-review-prompt.md"
    write_json(llm_review_request_path, llm_review_request)
    llm_review_prompt_path.write_text(render_llm_review_prompt(llm_review_request), encoding="utf-8", newline="\n")

    staging_dir = run_dir / "staging"
    preserve_target_only = operating_mode in {"existing_locale_maintenance", "rewrite_or_harmonization"}
    staging_result = stage_generated(
        project_root,
        delivery_segments,
        staging_dir,
        source_locale,
        target_locale,
        selected_files,
        preserve_target_only=preserve_target_only,
    )
    staging_path = run_dir / "staging-result.json"
    write_json(staging_path, staging_result)
    qa_paths = _validate_staged_outputs(project_root, staging_result, target_locale, run_dir / "qa")
    packaged = package_delivery(state_dir, staging_dir, run_dir / "deliveries", qa_paths, delivery_status, run_id)
    delivery_dir = Path(packaged["delivery_directory"])
    apply_plan = create_apply_plan(delivery_dir, project_root)
    apply_plan_path = run_dir / "apply-plan.json"
    apply_plan_markdown_path = run_dir / "apply-plan.md"
    write_json(apply_plan_path, apply_plan)
    apply_plan_markdown_path.write_text(render_apply_plan_markdown(apply_plan), encoding="utf-8", newline="\n")
    dashboard = build_delivery_dashboard(delivery_dir)
    dashboard_path = run_dir / "delivery-dashboard.json"
    dashboard_md_path = run_dir / "delivery-dashboard.md"
    write_json(dashboard_path, dashboard)
    dashboard_md_path.write_text(render_dashboard_markdown(dashboard), encoding="utf-8", newline="\n")
    delivery_decision = create_delivery_decision_report(delivery_dir, project_root)
    delivery_decision_path = run_dir / "delivery-decision.json"
    delivery_decision_md_path = run_dir / "delivery-decision.md"
    write_json(delivery_decision_path, delivery_decision)
    delivery_decision_md_path.write_text(
        render_delivery_decision_markdown(delivery_decision),
        encoding="utf-8",
        newline="\n",
    )

    summary = _summary(
        run_id,
        "draft_package_created",
        project_root,
        source_locale,
        target_locale,
        selected_files,
        run_dir,
        segments_path,
        plan_path,
        handoff_path,
        len(segments),
        len(plan["batches"]),
        generation_mode=generation_mode,
        reference_plan_path=reference_plan_path,
        operating_mode=operating_mode,
        reference_policy=reference_policy,
        reference_summary=reference_plan["summary"],
        prompt_manifest_path=prompt_manifest_path,
        generation_readme_path=generation_readme_path,
        collect_path=collect_path,
        generated_path=generated_path,
        generation_status=collect_result["status"],
        review_sheet_path=review_sheet_path,
        review_markdown_path=review_markdown_path,
        review_csv_path=review_csv_path,
        llm_review_request_path=llm_review_request_path,
        llm_review_prompt_path=llm_review_prompt_path,
        staging_path=staging_path,
        delivery_dir=delivery_dir,
        apply_plan_path=apply_plan_path,
        apply_plan_markdown_path=apply_plan_markdown_path,
        dashboard_path=dashboard_path,
        dashboard_markdown=dashboard_md_path,
        delivery_decision_path=delivery_decision_path,
        delivery_decision_markdown=delivery_decision_md_path,
        output_count=staging_result["summary"]["output_count"],
        qa_status=dashboard["summary"]["qa_status"],
        blocking_count=dashboard["summary"]["blocking_count"],
        warning_count=dashboard["summary"]["warning_count"],
    )
    return _write_run_summary(summary, run_dir, inspection)


def _select_source_files(inspection: dict[str, Any], source_locale: str, source_files: list[str] | None) -> list[str]:
    inventory = {item["path"]: item for item in inspection["supported_files"]}
    if source_files:
        normalized = [path.replace("\\", "/") for path in source_files]
        unsupported = sorted(path for path in normalized if path not in inventory)
        if unsupported:
            raise ValueError(f"Requested source files were not found or are unsupported: {', '.join(unsupported)}")
        unsupported_adapters = sorted({inventory[path]["adapter"] for path in normalized if inventory[path]["adapter"] not in EXTRACTORS})
        if unsupported_adapters:
            raise ValueError(f"localize-run cannot extract adapters yet: {', '.join(unsupported_adapters)}")
        excluded_android = sorted(
            path
            for path in normalized
            if inventory[path]["adapter"] == "core.android-strings"
            and inventory[path].get("android_role") != "source_candidate"
        )
        if excluded_android:
            raise ValueError(
                "Android locale references or uncertain qualifier paths cannot be source truth: "
                + ", ".join(excluded_android)
            )
        return normalized

    candidates = [
        item
        for item in inspection["supported_files"]
        if item["adapter"] in EXTRACTORS
        and not (
            item["adapter"] == "core.android-strings"
            and item.get("android_role") != "source_candidate"
        )
    ]
    if not candidates:
        raise ValueError("No source files supported by localize-run were found")
    locale_matches = [item["path"] for item in candidates if _matches_source_locale(item, source_locale)]
    return sorted(locale_matches or [item["path"] for item in candidates])


def _matches_source_locale(item: dict[str, Any], source_locale: str) -> bool:
    path = str(item["path"]).replace("\\", "/")
    lower_path = path.lower().replace("_", "-")
    tokens = _locale_tokens(source_locale)
    adapter = item["adapter"]
    if adapter == "core.android-strings":
        return item.get("android_role") == "source_candidate"
    if adapter == "core.ios-strings":
        return any(f"/{token}.lproj/" in f"/{lower_path}/" for token in tokens)
    if adapter == "core.xcstrings":
        return True
    return any(token in lower_path for token in tokens)


def _locale_tokens(locale: str) -> set[str]:
    normalized = locale.lower().replace("_", "-")
    language = normalized.split("-", 1)[0]
    return {normalized, normalized.replace("-", "_"), language}


def _extract_all(project_root: Path, inspection: dict[str, Any], source_files: list[str], source_locale: str) -> list[dict[str, Any]]:
    inventory = {item["path"]: item for item in inspection["supported_files"]}
    segments: list[dict[str, Any]] = []
    for source_file in source_files:
        adapter = inventory[source_file]["adapter"]
        extractor = EXTRACTORS.get(adapter)
        if not extractor:
            raise ValueError(f"localize-run cannot extract adapter: {adapter}")
        path = project_root / source_file
        if adapter == "core.yaml-toml":
            records = extract_structured_segments(path, source_locale, source_file, _structured_format(path))
        else:
            records = extractor(path, source_locale, source_file)
        segments.extend(records)
    return segments


def _write_synthetic_batches(handoff: dict[str, Any], target_locale: str) -> None:
    for batch in handoff.get("batches", []):
        packet = read_json(Path(batch["work_packet"]))
        generated = [_synthetic_segment(segment, target_locale) for segment in packet.get("segments", [])]
        write_jsonl(Path(batch["generated"]), generated)


def _synthetic_segment(segment: dict[str, Any], target_locale: str) -> dict[str, Any]:
    generated = dict(segment)
    source = str(segment.get("source", ""))
    placeholders = [str(item) for item in segment.get("constraints", {}).get("placeholders", [])]
    plural_source = str(segment.get("context", {}).get("source_plural") or "")
    if placeholders and plural_source and any(placeholder not in source for placeholder in placeholders):
        source = plural_source
    generated["target_locale"] = target_locale
    generated["target"] = f"[{target_locale}] {source}"
    generated["status"] = "generated"
    generated["generation"] = {
        "provider": "synthetic",
        "quality_claim": "none",
        "purpose": "test_or_benchmark_only",
    }
    return generated


def _write_batches_from_combined(generated: Path, handoff: dict[str, Any]) -> None:
    records = read_jsonl(generated)
    expected_ids: set[str] = set()
    for batch in handoff.get("batches", []):
        packet = read_json(Path(batch["work_packet"]))
        expected_ids.update(str(segment["segment_id"]) for segment in packet.get("segments", []))
    unexpected = sorted({str(record.get("segment_id")) for record in records if str(record.get("segment_id")) not in expected_ids})
    if unexpected:
        raise ValueError(f"Generated file contains unexpected segment ids: {', '.join(unexpected)}")

    for batch in handoff.get("batches", []):
        packet = read_json(Path(batch["work_packet"]))
        batch_ids = {str(segment["segment_id"]) for segment in packet.get("segments", [])}
        write_jsonl(Path(batch["generated"]), [record for record in records if str(record.get("segment_id")) in batch_ids])


def _validate_staged_outputs(project_root: Path, staging_result: dict[str, Any], target_locale: str, qa_dir: Path) -> list[Path]:
    qa_paths: list[Path] = []
    for index, output in enumerate(staging_result.get("outputs", []), 1):
        adapter = output["adapter"]
        source = project_root / output["source"]
        target = Path(output["output"])
        if not target.is_absolute():
            target = Path(staging_result["staging_dir"]) / output["destination"]
        if adapter == "core.android-strings":
            qa = validate_android_strings(source, target)
        elif adapter == "core.gettext-po":
            qa = validate_po_pair(source, target)
        elif adapter == "core.ios-strings":
            qa = validate_ios_strings(source, target)
        elif adapter == "core.json-locale":
            qa = validate_json_pair(source, target)
        elif adapter == "core.markup":
            qa = validate_markup_pair(source, target)
        elif adapter == "core.subtitles":
            qa = validate_subtitle_pair(source, target)
        elif adapter == "core.tabular":
            qa = validate_tabular_pair(source, target)
        elif adapter == "core.xcstrings":
            qa = validate_xcstrings(source, target, target_locale)
        elif adapter == "core.xliff":
            qa = validate_xliff_pair(source, target)
        elif adapter == "core.yaml-toml":
            qa = validate_structured_pair(source, target, _structured_format(source))
        else:
            raise ValueError(f"localize-run cannot validate adapter: {adapter}")
        qa_path = qa_dir / f"{index:03d}-{adapter.replace('.', '-').replace('_', '-')}.json"
        write_json(qa_path, qa)
        qa_paths.append(qa_path)
    return qa_paths


def _structured_format(path: Path) -> str:
    return "toml" if path.suffix.lower() == ".toml" else "yaml"


def _summary(
    run_id: str,
    status: str,
    project_root: Path,
    source_locale: str,
    target_locale: str,
    source_files: list[str],
    run_dir: Path,
    segments_path: Path,
    plan_path: Path,
    handoff_path: Path,
    segment_count: int,
    batch_count: int,
    generation_mode: str,
    prompt_manifest_path: Path | None = None,
    generation_readme_path: Path | None = None,
    collect_path: Path | None = None,
    generated_path: Path | None = None,
    generation_status: str | None = None,
    review_sheet_path: Path | None = None,
    review_markdown_path: Path | None = None,
    review_csv_path: Path | None = None,
    llm_review_request_path: Path | None = None,
    llm_review_prompt_path: Path | None = None,
    staging_path: Path | None = None,
    delivery_dir: Path | None = None,
    apply_plan_path: Path | None = None,
    apply_plan_markdown_path: Path | None = None,
    dashboard_path: Path | None = None,
    dashboard_markdown: Path | None = None,
    delivery_decision_path: Path | None = None,
    delivery_decision_markdown: Path | None = None,
    output_count: int = 0,
    qa_status: str | None = None,
    blocking_count: int = 0,
    warning_count: int = 0,
    reference_plan_path: Path | None = None,
    operating_mode: str = DEFAULT_OPERATING_MODE,
    reference_policy: str = DEFAULT_REFERENCE_POLICY_BY_MODE[DEFAULT_OPERATING_MODE],
    reference_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifacts: dict[str, str] = {
        "run_directory": run_dir.as_posix(),
        "session_index": session_index_path(project_root).as_posix(),
        "segments": segments_path.as_posix(),
        "batch_plan": plan_path.as_posix(),
        "work_packets": (run_dir / "work-packets").as_posix(),
        "draft_requests": (run_dir / "draft-requests").as_posix(),
        "prompts": (run_dir / "prompts").as_posix(),
        "responses": (run_dir / "responses").as_posix(),
        "generation_handoff": handoff_path.as_posix(),
    }
    optional = {
        "prompt_manifest": prompt_manifest_path,
        "generation_readme": generation_readme_path,
        "generation_collect": collect_path,
        "generated_segments": generated_path,
        "review_sheet": review_sheet_path,
        "review_sheet_markdown": review_markdown_path,
        "review_sheet_csv": review_csv_path,
        "llm_review_request": llm_review_request_path,
        "llm_review_prompt": llm_review_prompt_path,
        "staging_result": staging_path,
        "delivery_directory": delivery_dir,
        "apply_plan": apply_plan_path,
        "apply_plan_markdown": apply_plan_markdown_path,
        "delivery_dashboard": dashboard_path,
        "delivery_dashboard_markdown": dashboard_markdown,
        "delivery_decision": delivery_decision_path,
        "delivery_decision_markdown": delivery_decision_markdown,
        "reference_plan": reference_plan_path,
    }
    for key, value in optional.items():
        if value is not None:
            artifacts[key] = value.as_posix()

    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "run_id": run_id,
        "status": status,
        "project": {
            "root": project_root.as_posix(),
            "source_locale": source_locale,
            "target_locale": target_locale,
            "mode": "standard_project",
            "operating_mode": operating_mode,
            "reference_policy": reference_policy,
        },
        "source_files": source_files,
        "reference": {
            "operating_mode": operating_mode,
            "reference_policy": reference_policy,
            "mode_contract": mode_contract(operating_mode, reference_policy),
            "summary": reference_summary or {},
        },
        "generation": {
            "mode": generation_mode,
            "status": generation_status or "pending",
            "provider_agnostic": True,
        },
        "summary": {
            "source_file_count": len(source_files),
            "segment_count": segment_count,
            "batch_count": batch_count,
            "output_count": output_count,
            "qa_status": qa_status or "not_checked",
            "blocking_count": blocking_count,
            "warning_count": warning_count,
            **(reference_summary or {}),
        },
        "artifacts": artifacts,
        "next_actions": _next_actions(status),
    }


def _write_run_summary(summary: dict[str, Any], run_dir: Path, inspection: dict[str, Any]) -> dict[str, Any]:
    write_json(run_dir / "run-summary.json", summary)
    record_project_session(
        Path(summary["project"]["root"]),
        run_id=summary["run_id"],
        kind="localize_run",
        status=summary["status"],
        source_locale=summary["project"]["source_locale"],
        target_locale=summary["project"]["target_locale"],
        operating_mode=summary["project"].get("operating_mode"),
        reference_policy=summary["project"].get("reference_policy"),
        selected_source_files=list(summary.get("source_files", [])),
        run_directory=run_dir,
        artifacts=summary.get("artifacts", {}),
        routing=_routing_evidence(inspection, summary.get("source_files", [])),
        summary=summary.get("summary", {}),
        next_actions=summary.get("next_actions", []),
    )
    return summary


def _routing_evidence(inspection: dict[str, Any], selected_source_files: list[str]) -> dict[str, Any]:
    return {
        "adapter_counts": inspection.get("adapter_counts", {}),
        "selected_source_files": selected_source_files,
        "supported_file_count": len(inspection.get("supported_files", [])),
        "android_generation_source_files": inspection.get("android_generation_source_files", []),
        "android_locale_reference_files": inspection.get("android_locale_reference_files", []),
        "unprocessed_non_text_asset_count": len(inspection.get("unprocessed_non_text_assets", [])),
        "scan_policy": inspection.get("scan_policy", {}),
        "ignored_path_count": inspection.get("ignored_path_count", 0),
        "ignored_paths_sample": inspection.get("ignored_paths", [])[:25],
        "skipped_path_count": inspection.get("skipped_path_count", 0),
        "skipped_paths_sample": inspection.get("skipped_paths", [])[:25],
        "preflight_assessment": inspection.get("preflight_assessment", {}),
    }


def _next_actions(status: str) -> list[str]:
    if status == "handoff_ready":
        return [
            "Send draft_requests/*.json to an LLM workflow and write one generated JSONL file per batch into generated-batches/.",
            "Run localize-run again with --generated-dir or collect-generated/stage-generated when drafts are ready.",
        ]
    if status == "generation_failed":
        return ["Fix generated batch coverage, source integrity, locale, status, or placeholder issues before staging."]
    return [
        "Review the staged localized files and dashboard.",
        "Run plan-apply, then apply-delivery --confirm-run-id only after the project owner approves overwriting project files.",
    ]
