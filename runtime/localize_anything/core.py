"""The small, provider-free core used by the v1 ``localize`` commands."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .core_formats import extract_source, extract_target, validate_resource_pair
from .core_glossary import check_locked_concepts, extract_candidate_concepts, normalize_concept
from .core_memory import import_confirmed_knowledge
from .core_preflight import describe_source, detect_adapter, discover_resources, discover_surfaces, relative_path, resolve_project, resolve_project_file, select_resources
from .core_segments import align_review_segments
from .io_utils import write_text_atomic
from .project_adapters import (
    PROJECT_ADAPTER_EXECUTION_MODE,
    ProjectAdapterError,
    adapter_fingerprints,
    adapter_matches_source,
    adapter_summary,
    discover_project_adapters,
    execute_extract_only_check,
    load_project_adapter,
)


STATE_DIRECTORY = ".localize-anything"
PROJECT_MEMORY = "project-memory.json"
SOURCE_SURFACE_INVENTORY = "source-surface-inventory.json"
CAPABILITY_REPORT = "capability-report.json"
INVENTORY = "inventory.json"
GLOSSARY = "glossary.json"
CHECK = "deterministic-check.json"
EXTRACTED_SEGMENTS = "extracted-segments.json"
SOURCE_VALIDATION = "source-validation.json"
REVIEW_PACKET = "review-packet.json"
REVIEW = "independent-review.json"
CONFIRMATIONS = "human-confirmations.json"
REPORT = "report.json"
REPORT_MARKDOWN = "report.md"
SEVERITIES = {"blocking", "actionable", "coverage_limitation", "informational"}
LEGACY_REVIEW_SEVERITIES = {"low": "informational", "medium": "actionable", "high": "actionable", "critical": "blocking"}
COVERAGE_CATEGORIES = {
    "empty_translation",
    "embedded_object_unchecked",
    "source_context",
    "translation_coverage",
    "visual_text_unchecked",
}
INFORMATIONAL_CATEGORIES = {"non_translatable_resource", "translatable_false"}
PATH_TOKEN_RE = re.compile(r"[a-z0-9]+")
PATH_SPLIT_RE = re.compile(r"([/._-])")

def scan(
    project_root: Path,
    *,
    source_locale: str | None = None,
    target_locale: str | None = None,
    source_files: list[str] | None = None,
    adapter_id: str | None = None,
) -> dict[str, Any]:
    """Inventory supported files and optionally establish the Project Memory."""
    project = resolve_project(project_root)
    discovered = discover_resources(project)
    surfaces = discover_surfaces(project)
    adapter_candidates = discover_project_adapters(project)
    result: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-core-scan-v1",
        "project_root": project.as_posix(),
        "supported_files": discovered,
        "supported_file_count": len(discovered),
        "source_surfaces": surfaces,
        "surface_count": len(surfaces),
        "unsupported_surface_count": sum(item["status"] != "supported" for item in surfaces),
        "project_adapter_candidates": adapter_candidates,
        "state_written": False,
    }
    if not source_files:
        if source_locale or target_locale:
            raise ValueError("--source-locale and --target-locale require at least one --source")
        return result
    if not source_locale or not target_locale:
        raise ValueError("--source-locale and --target-locale are required when declaring --source")

    inventory = _surface_inventory(project, source_files, adapter_id)
    capability_report = _capability_report(inventory)
    _write_json(_state_path(project, SOURCE_SURFACE_INVENTORY), inventory)
    _write_json(_state_path(project, CAPABILITY_REPORT), capability_report)
    if capability_report["status"] == "blocked":
        raise ValueError(_capability_gate_message(capability_report))

    selected = _selected_source_records(project, source_files, capability_report, adapter_id)
    memory_path = _state_path(project, PROJECT_MEMORY)
    existing = _read_json_if_exists(memory_path)
    imported = import_confirmed_knowledge(memory_path.parent) if not existing else {}
    if existing and (
        existing.get("source_locale") != source_locale or existing.get("target_locale") != target_locale
    ):
        raise ValueError("Project Memory already declares different source or target locales")
    memory = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-project-memory-v1",
        "source_locale": source_locale,
        "target_locale": target_locale,
        "source_files": selected,
        "product_context": existing.get("product_context", "") if existing else imported.get("product_context", ""),
        "style_rules": existing.get("style_rules", []) if existing else imported.get("style_rules", []),
        "preserve_rules": existing.get("preserve_rules", []) if existing else imported.get("preserve_rules", []),
        "translation_memory": existing.get("translation_memory", []) if existing else imported.get("translation_memory", []),
        "confirmed_decisions": existing.get("confirmed_decisions", []) if existing else imported.get("confirmed_decisions", []),
        "created_at": existing.get("created_at", _now()) if existing else _now(),
        "updated_at": _now(),
    }
    _write_json(memory_path, memory)
    result.update(
        {
            "state_written": True,
            "project_memory": memory_path.as_posix(),
            "source_surface_inventory": _state_path(project, SOURCE_SURFACE_INVENTORY).as_posix(),
            "capability_report": _state_path(project, CAPABILITY_REPORT).as_posix(),
            "selected_source_files": selected,
            "adapter_resolution": capability_report["adapter_resolution"],
            "next": _scan_next(capability_report),
        }
    )
    return result


def bootstrap_glossary(project_root: Path) -> dict[str, Any]:
    project = resolve_project(project_root)
    memory = _read_memory(project)
    segments = _source_segments(project, memory)
    glossary_path = _state_path(project, GLOSSARY)
    existing = _read_json_if_exists(glossary_path) or {}
    existing_concepts = existing.get("concepts", [])
    imported_concepts = import_confirmed_knowledge(glossary_path.parent)["concepts"]
    concepts_by_source = {
        normalize_concept(str(term)): concept
        for concept in [*imported_concepts, *existing_concepts]
        for term in concept.get("source_terms", [])
        if normalize_concept(str(term))
    }
    candidates = extract_candidate_concepts(segments)
    for candidate in candidates:
        concepts_by_source.setdefault(normalize_concept(candidate["source_terms"][0]), candidate)
    concepts = sorted(
        {str(item.get("id", index)): item for index, item in enumerate(concepts_by_source.values())}.values(),
        key=lambda item: normalize_concept(item["source_terms"][0]),
    )
    glossary = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-glossary-v1",
        "source_locale": memory["source_locale"],
        "target_locale": memory["target_locale"],
        "concepts": concepts,
        "updated_at": _now(),
    }
    _write_json(glossary_path, glossary)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-core-glossary-bootstrap-v1",
        "status": "ready_for_confirmation" if candidates else "empty",
        "candidate_count": len(candidates),
        "preserved_concept_count": len(existing_concepts) + len(imported_concepts),
        "glossary": glossary_path.as_posix(),
        "next": "Review candidate concepts in glossary.json. Mark only confirmed concepts as locked before enforcing them in `localize check`.",
    }


def check(project_root: Path, target_files: list[str]) -> dict[str, Any]:
    project = resolve_project(project_root)
    memory = _read_memory(project)
    paired = _pair_resources(project, memory, target_files)
    mapping = _source_target_mapping(paired)
    pairs = []
    extracted_files = []
    inventory_files = []
    source_validation_files = []
    target_text: list[str] = []
    source_text: list[str] = []
    findings: list[dict[str, Any]] = []
    for pair_info in paired:
        source_path = pair_info["source_path"]
        target_path = pair_info["target_path"]
        adapter = str(pair_info["adapter"])
        if not target_path.is_file():
            validation = _normalize_validation({
                "status": "fail",
                "summary": {"blocking_count": 1, "warning_count": 0},
                "items": [{"severity": "blocking", "kind": "missing_target", "message": f"Target file does not exist: {pair_info['target']}"}],
            })
        elif pair_info.get("adapter_kind") == "project_local":
            adapter_result = _run_project_adapter_check(project, pair_info, memory)
            validation = _normalize_validation(adapter_result["source_validation"])
            inventory_files.append(
                {
                    "source": pair_info["source"],
                    "target": pair_info["target"],
                    "adapter": adapter,
                    "adapter_kind": "project_local",
                    "execution_mode": PROJECT_ADAPTER_EXECUTION_MODE,
                    "items": adapter_result.get("inventory", []),
                    "run_artifacts": adapter_result.get("run_artifacts", []),
                }
            )
            source_validation_files.append(
                {
                    "source": pair_info["source"],
                    "target": pair_info["target"],
                    "adapter": adapter,
                    "adapter_kind": "project_local",
                    "execution_mode": PROJECT_ADAPTER_EXECUTION_MODE,
                    "validation": validation,
                    "run_artifacts": adapter_result.get("run_artifacts", []),
                }
            )
        else:
            validation = _normalize_validation(validate_resource_pair(adapter, source_path, target_path, memory["target_locale"]))
        pair = {
            "source": pair_info["source"],
            "target": pair_info["target"],
            "adapter": adapter,
            "adapter_kind": pair_info.get("adapter_kind", "core"),
            "validation": validation,
        }
        if pair_info.get("adapter_provenance"):
            pair["adapter_provenance"] = pair_info["adapter_provenance"]
        pairs.append(pair)
        if validation["status"] != "fail":
            if pair_info.get("adapter_kind") == "project_local":
                source_segments = adapter_result["source_segments"]
                target_segments = adapter_result["target_segments"]
            else:
                source_segments = extract_source(adapter, source_path, memory["source_locale"], pair_info["source"])
                target_segments = extract_target(adapter, target_path, memory["target_locale"], pair_info["target"])
            extracted_file = {
                "source": pair_info["source"],
                "target": pair_info["target"],
                "adapter": adapter,
                "adapter_kind": pair_info.get("adapter_kind", "core"),
                "source_segments": source_segments,
                "target_segments": target_segments,
                "adapter_provenance": pair_info.get("adapter_provenance", {}),
            }
            if pair_info.get("adapter_kind") == "project_local":
                extracted_file["execution_mode"] = PROJECT_ADAPTER_EXECUTION_MODE
            extracted_files.append(extracted_file)
            source_text.extend(
                str(item.get("source", ""))
                for item in source_segments
            )
            target_text.extend(
                str(item.get("source", ""))
                for item in target_segments
            )
        for item in validation.get("items", []):
            findings.append({"source": pair_info["source"], "target": pair_info["target"], **item})

    glossary_findings = check_locked_concepts(_read_json_if_exists(_state_path(project, GLOSSARY)), source_text, target_text)
    findings.extend(_normalize_check_item(item) for item in glossary_findings)
    summary = _severity_summary(findings)
    artifact_hashes = {
        "inventory_sha256": _json_sha256(inventory_files),
        "source_validation_sha256": _json_sha256(source_validation_files),
        "extraction_sha256": _json_sha256(extracted_files),
    }
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-deterministic-check-v1",
        "status": _check_status(summary),
        "source_locale": memory["source_locale"],
        "target_locale": memory["target_locale"],
        "source_target_mapping": mapping,
        "pairs": pairs,
        "summary": summary,
        "findings": findings,
        "file_fingerprints": _file_fingerprints(paired),
        "artifact_hashes": artifact_hashes,
        "checked_at": _now(),
        "limitations": ["Structural checks and exact locked-term checks do not evaluate translation meaning or naturalness."],
    }
    _write_json(_state_path(project, CHECK), result)
    if inventory_files:
        _write_json(
            _state_path(project, INVENTORY),
            {
                "protocol_version": PROTOCOL_VERSION,
                "schema": "localize-anything-inventory-v1",
                "status": result["status"],
                "source_target_mapping": mapping,
                "files": inventory_files,
                "file_fingerprints": result["file_fingerprints"],
                "inventory_sha256": artifact_hashes["inventory_sha256"],
                "inventoried_at": result["checked_at"],
            },
        )
    if source_validation_files:
        _write_json(
            _state_path(project, SOURCE_VALIDATION),
            {
                "protocol_version": PROTOCOL_VERSION,
                "schema": "localize-anything-source-validation-v1",
                "status": result["status"],
                "source_target_mapping": mapping,
                "files": source_validation_files,
                "file_fingerprints": result["file_fingerprints"],
                "source_validation_sha256": artifact_hashes["source_validation_sha256"],
                "validated_at": result["checked_at"],
            },
        )
    _write_json(
        _state_path(project, EXTRACTED_SEGMENTS),
        {
            "protocol_version": PROTOCOL_VERSION,
            "schema": "localize-anything-extracted-segments-v1",
            "status": "ready_for_review" if result["status"] != "fail" else "blocked",
            "source_locale": memory["source_locale"],
            "target_locale": memory["target_locale"],
            "source_target_mapping": mapping,
            "files": extracted_files,
            "file_fingerprints": result["file_fingerprints"],
            "inventory_sha256": artifact_hashes["inventory_sha256"],
            "source_validation_sha256": artifact_hashes["source_validation_sha256"],
            "extraction_sha256": artifact_hashes["extraction_sha256"],
            "extracted_at": result["checked_at"],
        },
    )
    return result


def prepare_review(project_root: Path, target_files: list[str], findings_path: Path | None = None) -> dict[str, Any]:
    project = resolve_project(project_root)
    memory = _read_memory(project)
    paired = _pair_resources(project, memory, target_files)
    mapping = _source_target_mapping(paired)
    for pair_info in paired:
        if not pair_info["target_path"].is_file():
            raise ValueError(f"Target file does not exist: {pair_info['target']}")
    _refresh_project_adapter_fingerprints(project, paired)
    extracted = _require_review_preconditions(project, mapping, paired)
    if findings_path is not None:
        _require_review_packet_current(project, mapping, paired)
        findings = _read_json(findings_path)
        review = _record_review(project, findings)
        return {
            "protocol_version": PROTOCOL_VERSION,
            "schema": "localize-anything-core-review-record-v1",
            "status": review["status"],
            "review": _state_path(project, REVIEW).as_posix(),
            "source_target_mapping": mapping,
            "finding_count": review["summary"]["finding_count"],
            "review_item_count": review["summary"]["review_item_count"],
            "human_confirmation_required": review["summary"]["human_confirmation_required"],
        }

    packet_files = []
    for file_info in extracted["files"]:
        packet_file = {
            "source": file_info["source"],
            "target": file_info["target"],
            "adapter": file_info["adapter"],
            "adapter_kind": file_info.get("adapter_kind", "core"),
            "adapter_provenance": file_info.get("adapter_provenance", {}),
            "segments": align_review_segments(file_info["source_segments"], file_info["target_segments"]),
        }
        if file_info.get("execution_mode"):
            packet_file["execution_mode"] = file_info["execution_mode"]
        packet_files.append(packet_file)
    packet = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-independent-review-packet-v1",
        "status": "ready_for_independent_review",
        "review_mode": "report_only" if any(file.get("adapter_kind") == "project_local" for file in packet_files) else "standard",
        "instruction": "Review in a fresh context. Check meaning, naturalness, tone, product concepts, and the deterministic findings. Do not reuse the generation rationale.",
        "project_memory": _read_memory(project),
        "glossary": _read_json_if_exists(_state_path(project, GLOSSARY)) or {"concepts": []},
        "deterministic_check": _read_json_if_exists(_state_path(project, CHECK)),
        "source_target_mapping": mapping,
        "files": packet_files,
        "file_fingerprints": _file_fingerprints(paired),
        "extraction_sha256": extracted.get("extraction_sha256"),
        "review_result_format": {
            "reviewer": "independent reviewer identity or model",
            "review_items": [{"id": "stable-id", "severity": "informational", "status": "auto_cleared", "note": "concise evidence for a checked item that is not a finding"}],
            "findings": [{"id": "stable-id", "severity": "blocking|actionable|coverage_limitation|informational", "status": "resolved|needs_human_confirmation", "note": "concise evidence"}],
        },
    }
    _write_json(_state_path(project, REVIEW_PACKET), packet)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-core-review-packet-v1",
        "status": packet["status"],
        "review_packet": _state_path(project, REVIEW_PACKET).as_posix(),
        "source_target_mapping": mapping,
        "next": "Give this packet to an independent Agent context, then run `localize review PROJECT --findings REVIEW.json`.",
    }


def report(project_root: Path, confirmations_path: Path | None = None) -> dict[str, Any]:
    project = resolve_project(project_root)
    memory = _read_memory(project)
    if confirmations_path is not None:
        _record_confirmations(project, _read_json(confirmations_path))
    deterministic = _read_json_if_exists(_state_path(project, CHECK))
    review = _read_json_if_exists(_state_path(project, REVIEW))
    confirmations = _read_json_if_exists(_state_path(project, CONFIRMATIONS)) or {"confirmations": []}
    confirmed_ids = {str(item.get("finding_id")) for item in confirmations["confirmations"]}
    needs_confirmation = [
        finding for finding in review.get("findings", []) if finding.get("status") == "needs_human_confirmation"
    ] if review else []
    pending = [item for item in needs_confirmation if str(item["id"]) not in confirmed_ids]
    status = "incomplete"
    if deterministic and deterministic["status"] != "fail" and review and review["status"] == "complete":
        if pending:
            status = "needs_human_confirmation"
        elif deterministic["status"] == "pass_with_warnings":
            status = "needs_attention"
        else:
            status = "ready"
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-report-v1",
        "status": status,
        "source_locale": memory["source_locale"],
        "target_locale": memory["target_locale"],
        "deterministic_check": _summary(deterministic),
        "independent_review": _summary(review),
        "human_confirmation": {"required": len(needs_confirmation), "confirmed": len(confirmed_ids), "pending": pending},
        "artifacts": {
            "project_memory": PROJECT_MEMORY,
            "glossary": GLOSSARY,
            "deterministic_check": CHECK,
            "review_packet": REVIEW_PACKET,
            "independent_review": REVIEW,
            "human_confirmations": CONFIRMATIONS,
            "source_surface_inventory": SOURCE_SURFACE_INVENTORY,
            "capability_report": CAPABILITY_REPORT,
            "inventory": INVENTORY,
            "source_validation": SOURCE_VALIDATION,
            "extracted_segments": EXTRACTED_SEGMENTS,
        },
        "limitations": ["This report does not replace project build/tests, screenshots, Git review, or human release judgment."],
    }
    _write_json(_state_path(project, REPORT), result)
    _write_text(_state_path(project, REPORT_MARKDOWN), _render_report(result))
    return result


def _source_segments(project: Path, memory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        segment
        for source in memory["source_files"]
        for segment in extract_source(
            str(source["adapter"]),
            resolve_project_file(project, str(source["path"])),
            memory["source_locale"],
            str(source["path"]),
        )
    ]


def _pair_resources(project: Path, memory: dict[str, Any], target_files: list[str]) -> list[dict[str, Any]]:
    sources = memory["source_files"]
    if len(target_files) != len(sources):
        raise ValueError(
            f"Expected {len(sources)} --target values, got {len(target_files)}; pass one target for each declared source file"
        )
    pairs = []
    for index, (source, target_name) in enumerate(zip(sources, target_files, strict=True), start=1):
        source_path = resolve_project_file(project, str(source["path"]))
        target_path = resolve_project_file(project, target_name)
        source_rel = str(source["path"])
        target_rel = relative_path(project, target_path)
        adapter = str(source["adapter"])
        adapter_kind = str(source.get("adapter_kind") or "core")
        target_adapter = detect_adapter(project, target_path) if adapter_kind == "core" and target_path.is_file() else None
        if target_adapter and target_adapter != adapter:
            raise ValueError(
                f"Source/target adapter mismatch at pair {index}: {source_rel} ({adapter}) -> {target_rel} ({target_adapter})"
            )
        contradiction = _locale_path_contradiction(
            source_rel,
            target_rel,
            str(memory["source_locale"]),
            str(memory["target_locale"]),
        )
        if contradiction:
            raise ValueError(f"Source/target locale path mismatch at pair {index}: {source_rel} -> {target_rel}: {contradiction}")
        pairs.append(
            {
                "source": source_rel,
                "target": target_rel,
                "adapter": adapter,
                "adapter_kind": adapter_kind,
                "adapter_provenance": source.get("adapter_provenance", {}),
                "adapter_fingerprints": source.get("adapter_fingerprints", []),
                "source_path": source_path,
                "target_path": target_path,
            }
        )
    return pairs


def _source_target_mapping(pairs: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"source": str(item["source"]), "target": str(item["target"]), "adapter": str(item["adapter"])}
        for item in pairs
    ]


def _surface_inventory(project: Path, source_files: list[str], adapter_id: str | None = None) -> dict[str, Any]:
    selected_adapter: dict[str, Any] | None = None
    adapter_error: ProjectAdapterError | None = None
    if adapter_id:
        try:
            selected_adapter = load_project_adapter(project, adapter_id)
        except ProjectAdapterError as exc:
            adapter_error = exc

    candidates = discover_project_adapters(project)
    selected_sources = [
        _describe_selected_source(project, source, selected_adapter, adapter_error, candidates)
        for source in source_files
    ]
    surfaces_by_path = {item["path"]: item for item in discover_surfaces(project)}
    for item in selected_sources:
        surfaces_by_path[item["path"]] = item
    surfaces = sorted(surfaces_by_path.values(), key=lambda item: item["path"])
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-source-surface-inventory-v1",
        "project_root": project.as_posix(),
        "selected_sources": selected_sources,
        "project_adapter_candidates": candidates,
        "surfaces": surfaces,
        "summary": {
            "selected_source_count": len(selected_sources),
            "supported_selected_count": sum(item["status"] == "supported" for item in selected_sources),
            "unsupported_selected_count": sum(item["status"] != "supported" for item in selected_sources),
            "surface_count": len(surfaces),
            "unsupported_surface_count": sum(item["status"] != "supported" for item in surfaces),
        },
        "scanned_at": _now(),
    }


def _capability_report(inventory: dict[str, Any]) -> dict[str, Any]:
    selected = list(inventory["selected_sources"])
    blocked = [item for item in selected if item["status"] != "supported"]
    adapter_resolution = [
        {
            "path": item["path"],
            "adapter": item.get("adapter"),
            "adapter_kind": item.get("adapter_kind"),
            "round_trip_level": item.get("round_trip_level", "unsupported"),
            "allowed_phases": item.get("allowed_phases", []),
            "blocked_phases": item.get("blocked_phases", []),
            "status": item["status"],
            "reason_code": item.get("reason_code"),
            "available_project_adapter_candidates": item.get("available_project_adapter_candidates", []),
        }
        for item in selected
    ]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-capability-report-v1",
        "status": "blocked" if blocked else "ready",
        "phase_order": ["capability_scan", "adapter_selection", "capability_gate", "artifact_preconditions", "allowed_phase_execution"],
        "selected_sources": selected,
        "blocked_sources": blocked,
        "adapter_resolution": adapter_resolution,
        "gate": {
            "status": "fail" if blocked else "pass",
            "required_for_review": ["adapter", "inventory", "extract", "validate", "review_packet"],
        },
        "generated_at": _now(),
    }


def _capability_gate_message(capability_report: dict[str, Any]) -> str:
    blocked_sources = capability_report["blocked_sources"]
    blocked = "; ".join(f"{item['path']}: [{item.get('reason_code', 'blocked')}] {item['reason']}" for item in blocked_sources)
    has_candidate = any(item.get("available_project_adapter_candidates") for item in blocked_sources)
    if has_candidate:
        prefix = "Project-local adapter candidate found. It will not be executed until explicitly selected."
    else:
        prefix = "Localization surface detected, but no safe adapter is selected. Capability: unsupported."
    return f"{prefix} Capability gate failed before Project Memory: {blocked}. See {CAPABILITY_REPORT}."


def _scan_next(capability_report: dict[str, Any]) -> str:
    if any(item.get("adapter_kind") == "project_local" for item in capability_report["adapter_resolution"]):
        return "Run `localize check PROJECT --target ...`, then `localize review PROJECT --target ...` for report-only review. Rebuild and apply remain blocked."
    return "Run `localize glossary bootstrap PROJECT`, then let the Coding Agent localize the declared files."


def _run_project_adapter_check(project: Path, pair_info: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
    try:
        adapter = load_project_adapter(project, str(pair_info["adapter"]))
        pair_info["adapter_provenance"] = adapter_summary(adapter)
        pair_info["adapter_fingerprints"] = adapter_fingerprints(adapter)
    except ProjectAdapterError as exc:
        return {
            "status": "fail",
            "inventory": [],
            "source_segments": [],
            "target_segments": [],
            "source_validation": {"status": "fail", "items": [exc.blocker()]},
            "run_artifacts": list(exc.evidence.get("run_artifacts", [])),
        }
    result = execute_extract_only_check(
        project,
        project / STATE_DIRECTORY,
        adapter,
        source=str(pair_info["source"]),
        target=str(pair_info["target"]),
        source_locale=str(memory["source_locale"]),
        target_locale=str(memory["target_locale"]),
    )
    if result["status"] == "fail":
        return {
            **result,
            "inventory": result.get("inventory", []),
            "source_segments": [],
            "target_segments": [],
            "source_validation": result.get("source_validation") or {"status": "fail", "items": result.get("items", [])},
        }
    return result


def _refresh_project_adapter_fingerprints(project: Path, pairs: list[dict[str, Any]]) -> None:
    for pair in pairs:
        if pair.get("adapter_kind") != "project_local":
            continue
        adapter = load_project_adapter(project, str(pair["adapter"]))
        pair["adapter_provenance"] = adapter_summary(adapter)
        pair["adapter_fingerprints"] = adapter_fingerprints(adapter)


def _describe_selected_source(
    project: Path,
    source: str,
    selected_adapter: dict[str, Any] | None,
    adapter_error: ProjectAdapterError | None,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    if adapter_error:
        base = describe_source(project, source)
        return {
            **base,
            "status": "unsupported",
            "adapter": None,
            "adapter_kind": "project_local",
            "round_trip_level": "unsupported",
            "allowed_phases": ["scan"],
            "blocked_phases": ["glossary", "check", "review", "report"],
            "reason_code": adapter_error.code,
            "reason": str(adapter_error),
            "blocker": adapter_error.blocker(),
        }
    if selected_adapter:
        source_path = resolve_project_file(project, source)
        if selected_adapter["round_trip_level"] != "extract_only":
            return {
                **describe_source(project, source),
                "status": "unsupported",
                "adapter": selected_adapter["id"],
                "adapter_kind": "project_local",
                "round_trip_level": selected_adapter["round_trip_level"],
                "allowed_phases": ["scan"],
                "blocked_phases": ["check", "review", "report", "rebuild", "validate_output", "plan_apply", "apply"],
                "reason_code": "capability_not_allowed",
                "reason": "Selected project-local adapter is inspect_only; check and report-only review require extract_only.",
                "adapter_provenance": adapter_summary(selected_adapter),
                "adapter_fingerprints": adapter_fingerprints(selected_adapter),
            }
        if not adapter_matches_source(project, selected_adapter, relative_path(project, source_path)):
            return {
                **describe_source(project, source),
                "status": "unsupported",
                "adapter": selected_adapter["id"],
                "adapter_kind": "project_local",
                "round_trip_level": "unsupported",
                "allowed_phases": ["scan"],
                "blocked_phases": ["glossary", "check", "review", "report"],
                "reason_code": "capability_not_allowed",
                "reason": "Selected project-local adapter source_scope does not include this source.",
            }
        summary = adapter_summary(selected_adapter)
        return {
            "path": relative_path(project, source_path),
            "surface_type": "code_embedded_catalog",
            "status": "supported",
            "adapter": selected_adapter["id"],
            "adapter_kind": "project_local",
            "capabilities": selected_adapter["capabilities"],
            "missing_capabilities": ["rebuild", "validate_output", "plan_apply", "apply"],
            "round_trip_level": selected_adapter["round_trip_level"],
            "allowed_phases": ["scan", "check", "review", "report"],
            "blocked_phases": ["rebuild", "validate_output", "plan_apply", "apply"],
            "evidence": [f"project_adapter:{selected_adapter['id']}", f"checksum:{selected_adapter['entrypoint_sha256']}"],
            "adapter_provenance": summary,
            "adapter_fingerprints": adapter_fingerprints(selected_adapter),
        }
    base = describe_source(project, source)
    matching_candidates = [
        item
        for item in candidates
        if item.get("status") == "candidate" and _candidate_matches_source(source, item)
    ]
    if base["status"] != "supported" and matching_candidates:
        return {
            **base,
            "reason": "Project-local adapter candidate found. It will not be executed until explicitly selected.",
            "available_project_adapter_candidates": matching_candidates,
            "blocked_phases": ["glossary", "check", "review", "report"],
        }
    return base


def _candidate_matches_source(source: str, candidate: dict[str, Any]) -> bool:
    paths = candidate.get("source_scope", {}).get("paths", [])
    if not paths:
        return True
    return any(source == item or source.startswith(f"{str(item).rstrip('/')}/") for item in paths if isinstance(item, str))


def _selected_source_records(
    project: Path,
    source_files: list[str],
    capability_report: dict[str, Any],
    adapter_id: str | None,
) -> list[dict[str, Any]]:
    if not adapter_id:
        return select_resources(project, source_files)
    selected = []
    for source in capability_report["selected_sources"]:
        selected.append(
            {
                "path": source["path"],
                "adapter": source["adapter"],
                "adapter_kind": "project_local",
                "round_trip_level": source["round_trip_level"],
                "adapter_provenance": source["adapter_provenance"],
                "adapter_fingerprints": source["adapter_fingerprints"],
            }
        )
    return selected


def _require_review_preconditions(project: Path, mapping: list[dict[str, str]], paired: list[dict[str, Any]]) -> dict[str, Any]:
    check_artifact = _read_json_if_exists(_state_path(project, CHECK))
    if not check_artifact:
        raise ValueError("Deterministic check artifact is missing. Run `localize check PROJECT --target ...` before `localize review`.")
    if check_artifact.get("source_target_mapping") != mapping:
        raise ValueError("Deterministic check mapping does not match the requested review targets. Rerun `localize check` with the same targets.")
    if check_artifact.get("status") == "fail":
        raise ValueError("Deterministic check failed. Fix blocking structural findings and rerun `localize check` before review.")
    if check_artifact.get("status") not in {"pass", "pass_with_warnings"}:
        raise ValueError("Deterministic check status is not reviewable. Rerun `localize check` before review.")
    _assert_fingerprints_current(project, check_artifact.get("file_fingerprints"), paired, CHECK)

    extracted = _read_json_if_exists(_state_path(project, EXTRACTED_SEGMENTS))
    if not extracted:
        raise ValueError("Extracted segments artifact is missing. Rerun `localize check` before review.")
    if extracted.get("source_target_mapping") != mapping:
        raise ValueError("Extracted segments mapping does not match the requested review targets. Rerun `localize check` with the same targets.")
    if extracted.get("status") != "ready_for_review":
        raise ValueError("Extracted segments are not reviewable. Fix deterministic-check blockers and rerun `localize check`.")
    if len(extracted.get("files", [])) != len(mapping):
        raise ValueError("Extracted segments do not cover every requested review target. Rerun `localize check`.")
    _assert_fingerprints_current(project, extracted.get("file_fingerprints"), paired, EXTRACTED_SEGMENTS)
    return extracted


def _require_review_packet_current(project: Path, mapping: list[dict[str, str]], paired: list[dict[str, Any]]) -> None:
    packet = _read_json_if_exists(_state_path(project, REVIEW_PACKET))
    if not packet:
        raise ValueError("Independent review packet is missing. Run `localize review PROJECT --target ...` before importing findings.")
    if packet.get("source_target_mapping") != mapping:
        raise ValueError("Independent review packet mapping does not match these targets. Regenerate the review packet before importing findings.")
    _assert_fingerprints_current(project, packet.get("file_fingerprints"), paired, REVIEW_PACKET)
    extracted = _read_json_if_exists(_state_path(project, EXTRACTED_SEGMENTS))
    if not extracted or packet.get("extraction_sha256") != extracted.get("extraction_sha256"):
        raise ValueError("Independent review packet is stale because extracted segments changed. Regenerate the review packet before importing findings.")


def _file_fingerprints(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fingerprints = []
    for pair in pairs:
        for role, path_key in (("source", "source_path"), ("target", "target_path")):
            path = pair[path_key]
            entry: dict[str, Any] = {"role": role, "path": pair[role]}
            if path.is_file():
                stat = path.stat()
                entry.update({"size": stat.st_size, "sha256": _sha256(path)})
            else:
                entry["missing"] = True
            fingerprints.append(entry)
        for item in pair.get("adapter_fingerprints", []):
            if isinstance(item, dict):
                fingerprints.append(dict(item))
    return fingerprints


def _assert_fingerprints_current(project: Path, fingerprints: Any, pairs: list[dict[str, Any]], artifact_name: str) -> None:
    if not isinstance(fingerprints, list) or not fingerprints:
        raise ValueError(f"{artifact_name} lacks file fingerprints. Rerun `localize check` before review.")
    expected = {(role, str(pair[role])) for pair in pairs for role in ("source", "target")}
    for pair in pairs:
        expected.update(
            (str(item.get("role")), str(item.get("path")))
            for item in pair.get("adapter_fingerprints", [])
            if isinstance(item, dict)
        )
    actual = {(str(item.get("role")), str(item.get("path"))) for item in fingerprints if isinstance(item, dict)}
    if actual != expected:
        raise ValueError(f"{artifact_name} file set does not match these targets. Rerun `localize check` before review.")
    for item in fingerprints:
        if not isinstance(item, dict):
            raise ValueError(f"{artifact_name} has invalid file fingerprint data. Rerun `localize check` before review.")
        path = resolve_project_file(project, str(item["path"]))
        if item.get("missing"):
            if path.exists():
                raise ValueError(f"{item['path']} changed since {artifact_name}; rerun `localize check` before review.")
            continue
        if not path.is_file():
            raise ValueError(f"{item['path']} changed since {artifact_name}; rerun `localize check` before review.")
        stat = path.stat()
        if item.get("size") != stat.st_size or item.get("sha256") != _sha256(path):
            raise ValueError(f"{item['path']} changed since {artifact_name}; rerun `localize check` before review.")


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _locale_path_contradiction(source: str, target: str, source_locale: str, target_locale: str) -> str:
    source_tokens = set(PATH_TOKEN_RE.findall(source.casefold()))
    target_tokens = set(PATH_TOKEN_RE.findall(target.casefold()))
    source_locale_tokens = _locale_token_set(source_locale)
    target_locale_tokens = _locale_token_set(target_locale)
    source_has_source = bool(source_tokens & source_locale_tokens)
    source_has_target = bool(source_tokens & target_locale_tokens)
    target_has_source = bool(target_tokens & source_locale_tokens)
    target_has_target = bool(target_tokens & target_locale_tokens)
    if source_has_target and not source_has_source:
        return f"source path contains target-locale token {target_locale!r}"
    if target_has_source and not target_has_target:
        return f"target path contains source-locale token {source_locale!r}"
    if source_has_source and target_has_target:
        source_shape = _locale_path_shape(source, source_locale)
        target_shape = _locale_path_shape(target, target_locale)
        if source_shape != target_shape:
            return f"path shapes differ after locale replacement ({source_shape!r} vs {target_shape!r})"
    return ""


def _locale_token_set(locale: str) -> set[str]:
    parts = [part for part in re.split(r"[-_]", locale.casefold()) if part]
    return set(parts)


def _locale_path_shape(path: str, locale: str) -> str:
    locale_tokens = _locale_token_set(locale)
    parts = [
        "{locale}" if token in locale_tokens else token
        for token in PATH_SPLIT_RE.split(path.casefold())
    ]
    shape = "".join(parts)
    return re.sub(r"\{locale\}(?:[-_]\{locale\})+", "{locale}", shape)


def _normalize_validation(validation: dict[str, Any]) -> dict[str, Any]:
    items = [_normalize_check_item(item) for item in validation.get("items", [])]
    summary = _severity_summary(items)
    return {**validation, "status": _check_status(summary), "summary": summary, "items": items}


def _normalize_check_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    category = str(normalized.get("category") or normalized.get("kind") or "")
    severity = str(normalized.get("severity", "")).strip()
    if severity == "warning":
        if category in INFORMATIONAL_CATEGORIES:
            severity = "informational"
        elif category in COVERAGE_CATEGORIES:
            severity = "coverage_limitation"
        else:
            severity = "actionable"
    elif severity == "info":
        severity = "informational"
    elif severity not in SEVERITIES:
        severity = "informational" if category in INFORMATIONAL_CATEGORIES else "actionable"
    normalized["severity"] = severity
    return normalized


def _severity_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {severity: 0 for severity in sorted(SEVERITIES)}
    for item in items:
        severity = str(item.get("severity", "informational"))
        counts[severity if severity in counts else "informational"] += 1
    return {
        "blocking_count": counts["blocking"],
        "warning_count": counts["actionable"] + counts["coverage_limitation"],
        "actionable_count": counts["actionable"],
        "coverage_limitation_count": counts["coverage_limitation"],
        "informational_count": counts["informational"],
        "severity_counts": counts,
    }


def _check_status(summary: dict[str, Any]) -> str:
    if summary["blocking_count"]:
        return "fail"
    if summary["actionable_count"] or summary["coverage_limitation_count"]:
        return "pass_with_warnings"
    return "pass"


def _record_review(project: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if not _state_path(project, REVIEW_PACKET).is_file():
        raise ValueError("Independent review packet is missing. Run `localize review PROJECT --target ...` before importing findings.")
    reviewer = str(payload.get("reviewer", "")).strip()
    findings = payload.get("findings")
    review_items = payload.get("review_items", [])
    if not reviewer or not isinstance(findings, list):
        raise ValueError("Independent review findings require reviewer and findings")
    if not isinstance(review_items, list):
        raise ValueError("Independent review review_items must be a list")
    normalized_findings = []
    normalized_review_items = []
    for item in review_items:
        normalized_review_items.append(_normalize_review_entry(item, allowed_statuses={"auto_cleared"}, default_status="auto_cleared"))
    for item in findings:
        normalized = _normalize_review_entry(
            item,
            allowed_statuses={"auto_cleared", "resolved", "needs_human_confirmation"},
            default_status="",
        )
        if normalized["status"] == "auto_cleared":
            normalized_review_items.append(normalized)
        else:
            normalized_findings.append(normalized)
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-independent-review-v1",
        "status": "complete",
        "reviewer": reviewer,
        "review_items": normalized_review_items,
        "findings": normalized_findings,
        "summary": {
            "reviewed_count": len(normalized_review_items) + len(normalized_findings),
            "review_item_count": len(normalized_review_items),
            "finding_count": len(normalized_findings),
            "human_confirmation_required": sum(item["status"] == "needs_human_confirmation" for item in normalized_findings),
        },
        "reviewed_at": _now(),
    }
    _write_json(_state_path(project, REVIEW), result)
    return result


def _normalize_review_entry(item: Any, *, allowed_statuses: set[str], default_status: str) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("Each review item or finding must be an object")
    entry_id = str(item.get("id", "")).strip()
    severity = _normalize_review_severity(str(item.get("severity") or "").strip())
    status = str(item.get("status") or default_status).strip()
    if not entry_id or not severity or status not in allowed_statuses:
        raise ValueError("Review items and findings need id, a valid severity, and a valid status")
    return {"id": entry_id, "severity": severity, "status": status, "note": str(item.get("note", "")).strip()}


def _normalize_review_severity(value: str) -> str:
    if value in SEVERITIES:
        return value
    return LEGACY_REVIEW_SEVERITIES.get(value, "")


def _record_confirmations(project: Path, payload: dict[str, Any]) -> None:
    confirmations = payload.get("confirmations")
    if not isinstance(confirmations, list):
        raise ValueError("Human confirmations require a confirmations list")
    review = _read_json_if_exists(_state_path(project, REVIEW))
    if not review:
        raise ValueError("Independent review is missing. Human confirmations cannot be recorded yet.")
    required_ids = {
        str(item.get("id"))
        for item in review.get("findings", [])
        if item.get("status") == "needs_human_confirmation"
    }
    normalized = []
    for item in confirmations:
        if not isinstance(item, dict) or not str(item.get("finding_id", "")).strip() or not str(item.get("decision", "")).strip():
            raise ValueError("Each confirmation needs finding_id and decision")
        finding_id = str(item["finding_id"])
        if finding_id not in required_ids:
            raise ValueError(f"Confirmation does not match an open human-review finding: {finding_id}")
        normalized.append({"finding_id": finding_id, "decision": str(item["decision"]), "note": str(item.get("note", ""))})
    _write_json(_state_path(project, CONFIRMATIONS), {"protocol_version": PROTOCOL_VERSION, "confirmations": normalized, "confirmed_at": _now()})


def _read_memory(project: Path) -> dict[str, Any]:
    memory = _read_json_if_exists(_state_path(project, PROJECT_MEMORY))
    if not memory:
        raise ValueError("Project Memory is missing. Run `localize scan PROJECT --source-locale ... --target-locale ... --source ...` first.")
    return memory


def _summary(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    return {"status": value.get("status"), "summary": value.get("summary", {})}


def _render_report(report: dict[str, Any]) -> str:
    check_summary = report["deterministic_check"] or {"status": "not_run"}
    review_summary = report["independent_review"] or {"status": "not_run"}
    human = report["human_confirmation"]
    return "\n".join(
        [
            "# Localization report",
            "",
            f"Status: **{report['status']}**",
            f"Locales: {report['source_locale']} → {report['target_locale']}",
            "",
            "## Deterministic check",
            "",
            f"Status: {check_summary['status']}",
            "",
            "## Independent review",
            "",
            f"Status: {review_summary['status']}",
            "",
            "## Human confirmation",
            "",
            f"Required: {human['required']}; confirmed: {human['confirmed']}; pending: {len(human['pending'])}",
            "",
            "This report does not replace project build/tests, screenshots, Git review, or human release judgment.",
            "",
        ]
    )


def _state_path(project: Path, name: str) -> Path:
    return project / STATE_DIRECTORY / name


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON file: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    return _read_json(path) if path.is_file() else None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _write_text(path: Path, content: str) -> None:
    write_text_atomic(path, content)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
