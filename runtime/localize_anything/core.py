"""The small, provider-free core used by the v1 ``localize`` commands."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .core_formats import extract_source, extract_target, validate_resource_pair
from .core_glossary import check_locked_concepts, extract_candidate_concepts, normalize_concept
from .core_memory import import_confirmed_knowledge
from .core_preflight import detect_adapter, discover_resources, relative_path, resolve_project, resolve_project_file, select_resources
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
    paired = _pair_resources(project, memory, target_files)
    mapping = _source_target_mapping(paired)
    pairs = []
    target_text: list[str] = []
    source_text: list[str] = []
    findings: list[dict[str, Any]] = []
    for pair_info in paired:
        source_path = pair_info["source_path"]
        target_path = pair_info["target_path"]
        adapter = str(pair_info["adapter"])
        if target_path.is_file():
            validation = _normalize_validation(validate_resource_pair(adapter, source_path, target_path, memory["target_locale"]))
        else:
            validation = _normalize_validation({
                "status": "fail",
                "summary": {"blocking_count": 1, "warning_count": 0},
                "items": [{"severity": "blocking", "kind": "missing_target", "message": f"Target file does not exist: {pair_info['target']}"}],
            })
        pair = {
            "source": pair_info["source"],
            "target": pair_info["target"],
            "adapter": adapter,
            "validation": validation,
        }
        pairs.append(pair)
        if validation["status"] != "fail":
            source_text.extend(
                str(item.get("source", ""))
                for item in extract_source(adapter, source_path, memory["source_locale"], pair_info["source"])
            )
            target_text.extend(
                str(item.get("source", ""))
                for item in extract_target(adapter, target_path, memory["target_locale"], pair_info["target"])
            )
        for item in validation.get("items", []):
            findings.append({"source": pair_info["source"], "target": pair_info["target"], **item})

    glossary_findings = check_locked_concepts(_read_json_if_exists(_state_path(project, GLOSSARY)), source_text, target_text)
    findings.extend(_normalize_check_item(item) for item in glossary_findings)
    summary = _severity_summary(findings)
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
        "checked_at": _now(),
        "limitations": ["Structural checks and exact locked-term checks do not evaluate translation meaning or naturalness."],
    }
    _write_json(_state_path(project, CHECK), result)
    return result


def prepare_review(project_root: Path, target_files: list[str], findings_path: Path | None = None) -> dict[str, Any]:
    project = resolve_project(project_root)
    memory = _read_memory(project)
    paired = _pair_resources(project, memory, target_files)
    mapping = _source_target_mapping(paired)
    for pair_info in paired:
        if not pair_info["target_path"].is_file():
            raise ValueError(f"Target file does not exist: {pair_info['target']}")
    if findings_path is not None:
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
    for pair_info in paired:
        source_path = pair_info["source_path"]
        target_path = pair_info["target_path"]
        adapter = str(pair_info["adapter"])
        source_segments = extract_source(adapter, source_path, memory["source_locale"], pair_info["source"])
        target_segments = extract_target(adapter, target_path, memory["target_locale"], pair_info["target"])
        packet_files.append(
            {
                "source": pair_info["source"],
                "target": pair_info["target"],
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
        "source_target_mapping": mapping,
        "files": packet_files,
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
        target_adapter = detect_adapter(project, target_path) if target_path.is_file() else None
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
