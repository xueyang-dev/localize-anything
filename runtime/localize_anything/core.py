"""The small, provider-free core used by the v1 ``localize`` commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .core_formats import extract_source, extract_target, validate_resource_pair
from .core_glossary import check_locked_concepts, extract_candidate_concepts, normalize_concept
from .core_memory import import_confirmed_knowledge
from .core_preflight import discover_resources, relative_path, resolve_project, resolve_project_file, select_resources
from .core_segments import align_review_segments
from .io_utils import write_text_atomic


STATE_DIRECTORY = ".localize-anything"
PROJECT_MEMORY = "project-memory.json"
GLOSSARY = "glossary.json"
CHECK = "deterministic-check.json"
REVIEW_PACKET = "review-packet.json"
REVIEW = "independent-review.json"
CONFIRMATIONS = "human-confirmations.json"
REPORT = "report.json"
REPORT_MARKDOWN = "report.md"

def scan(
    project_root: Path,
    *,
    source_locale: str | None = None,
    target_locale: str | None = None,
    source_files: list[str] | None = None,
) -> dict[str, Any]:
    """Inventory supported files and optionally establish the Project Memory."""
    project = resolve_project(project_root)
    discovered = discover_resources(project)
    result: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-core-scan-v1",
        "project_root": project.as_posix(),
        "supported_files": discovered,
        "supported_file_count": len(discovered),
        "state_written": False,
    }
    if not source_files:
        if source_locale or target_locale:
            raise ValueError("--source-locale and --target-locale require at least one --source")
        return result
    if not source_locale or not target_locale:
        raise ValueError("--source-locale and --target-locale are required when declaring --source")

    selected = select_resources(project, source_files)
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
            "selected_source_files": selected,
            "next": "Run `localize glossary bootstrap PROJECT`, then let the Coding Agent localize the declared files.",
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
    sources = memory["source_files"]
    if len(target_files) != len(sources):
        raise ValueError(f"Expected {len(sources)} --target values, one for each declared source file")
    pairs = []
    target_text: list[str] = []
    source_text: list[str] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for source, target_name in zip(sources, target_files, strict=True):
        source_path = resolve_project_file(project, str(source["path"]))
        target_path = resolve_project_file(project, target_name)
        adapter = str(source["adapter"])
        if target_path.is_file():
            validation = validate_resource_pair(adapter, source_path, target_path, memory["target_locale"])
        else:
            validation = {
                "status": "fail",
                "summary": {"blocking_count": 1, "warning_count": 0},
                "items": [{"severity": "blocking", "kind": "missing_target", "message": f"Target file does not exist: {target_name}"}],
            }
        pair = {
            "source": source["path"],
            "target": relative_path(project, target_path),
            "adapter": adapter,
            "validation": validation,
        }
        pairs.append(pair)
        if validation["status"] != "fail":
            source_text.extend(
                str(item.get("source", ""))
                for item in extract_source(adapter, source_path, memory["source_locale"], source["path"])
            )
            target_text.extend(
                str(item.get("source", ""))
                for item in extract_target(adapter, target_path, memory["target_locale"], relative_path(project, target_path))
            )
        for item in validation.get("items", []):
            issue = {"source": source["path"], "target": relative_path(project, target_path), **item}
            (errors if item.get("severity") == "blocking" else warnings).append(issue)

    glossary_findings = check_locked_concepts(_read_json_if_exists(_state_path(project, GLOSSARY)), source_text, target_text)
    errors.extend(item for item in glossary_findings if item["severity"] == "blocking")
    warnings.extend(item for item in glossary_findings if item["severity"] != "blocking")
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-deterministic-check-v1",
        "status": "fail" if errors else ("pass_with_warnings" if warnings else "pass"),
        "source_locale": memory["source_locale"],
        "target_locale": memory["target_locale"],
        "pairs": pairs,
        "summary": {"blocking_count": len(errors), "warning_count": len(warnings)},
        "findings": [*errors, *warnings],
        "checked_at": _now(),
        "limitations": ["Structural checks and exact locked-term checks do not evaluate translation meaning or naturalness."],
    }
    _write_json(_state_path(project, CHECK), result)
    return result


def prepare_review(project_root: Path, target_files: list[str], findings_path: Path | None = None) -> dict[str, Any]:
    project = resolve_project(project_root)
    memory = _read_memory(project)
    sources = memory["source_files"]
    if len(target_files) != len(sources):
        raise ValueError(f"Expected {len(sources)} --target values, one for each declared source file")
    target_paths = [resolve_project_file(project, value) for value in target_files]
    for path in target_paths:
        if not path.is_file():
            raise ValueError(f"Target file does not exist: {relative_path(project, path)}")
    if findings_path is not None:
        findings = _read_json(findings_path)
        review = _record_review(project, findings)
        return {
            "protocol_version": PROTOCOL_VERSION,
            "schema": "localize-anything-core-review-record-v1",
            "status": review["status"],
            "review": _state_path(project, REVIEW).as_posix(),
            "human_confirmation_required": review["summary"]["human_confirmation_required"],
        }

    packet_files = []
    for source, target_path in zip(sources, target_paths, strict=True):
        source_path = resolve_project_file(project, str(source["path"]))
        adapter = str(source["adapter"])
        source_segments = extract_source(adapter, source_path, memory["source_locale"], source["path"])
        target_segments = extract_target(adapter, target_path, memory["target_locale"], relative_path(project, target_path))
        packet_files.append(
            {
                "source": source["path"],
                "target": relative_path(project, target_path),
                "adapter": adapter,
                "segments": align_review_segments(source_segments, target_segments),
            }
        )
    packet = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-independent-review-packet-v1",
        "status": "ready_for_independent_review",
        "instruction": "Review in a fresh context. Check meaning, naturalness, tone, product concepts, and the deterministic findings. Do not reuse the generation rationale.",
        "project_memory": _read_memory(project),
        "glossary": _read_json_if_exists(_state_path(project, GLOSSARY)) or {"concepts": []},
        "deterministic_check": _read_json_if_exists(_state_path(project, CHECK)),
        "files": packet_files,
        "review_result_format": {
            "reviewer": "independent reviewer identity or model",
            "findings": [{"id": "stable-id", "severity": "low|medium|high|critical", "status": "auto_cleared|resolved|needs_human_confirmation", "note": "concise evidence"}],
        },
    }
    _write_json(_state_path(project, REVIEW_PACKET), packet)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-core-review-packet-v1",
        "status": packet["status"],
        "review_packet": _state_path(project, REVIEW_PACKET).as_posix(),
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


def _record_review(project: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if not _state_path(project, REVIEW_PACKET).is_file():
        raise ValueError("Independent review packet is missing. Run `localize review PROJECT --target ...` before importing findings.")
    reviewer = str(payload.get("reviewer", "")).strip()
    findings = payload.get("findings")
    if not reviewer or not isinstance(findings, list):
        raise ValueError("Independent review findings require reviewer and findings")
    normalized = []
    for item in findings:
        if not isinstance(item, dict):
            raise ValueError("Each review finding must be an object")
        finding_id = str(item.get("id", "")).strip()
        severity = str(item.get("severity", "")).strip()
        status = str(item.get("status", "")).strip()
        if not finding_id or severity not in {"low", "medium", "high", "critical"} or status not in {"auto_cleared", "resolved", "needs_human_confirmation"}:
            raise ValueError("Review findings need id, a valid severity, and a valid status")
        normalized.append({"id": finding_id, "severity": severity, "status": status, "note": str(item.get("note", "")).strip()})
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-independent-review-v1",
        "status": "complete",
        "reviewer": reviewer,
        "findings": normalized,
        "summary": {
            "reviewed_count": len(normalized),
            "auto_cleared": sum(item["status"] == "auto_cleared" for item in normalized),
            "human_confirmation_required": sum(item["status"] == "needs_human_confirmation" for item in normalized),
        },
        "reviewed_at": _now(),
    }
    _write_json(_state_path(project, REVIEW), result)
    return result


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
