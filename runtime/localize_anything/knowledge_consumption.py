from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json
from .modes import OPERATING_MODES


KNOWLEDGE_ROOT = ".localize-anything/knowledge/packs"
PACK_JSON = "pack.json"
KNOWLEDGE_PACK_SELECTION_JSON = "knowledge-pack-selection.json"
KNOWLEDGE_ELIGIBILITY_REPORT_JSON = "knowledge-eligibility-report.json"
WORKING_CONTEXT_PACKET_JSON = "working-context-packet.json"

BAD_STATUSES = {"stale", "rejected", "superseded", "obsolete", "blocked", "fail", "failed", "failed_qa", "unresolved"}
REVIEW_STATUSES = {"raw", "candidate", "deferred", "draft", "suggested", "needs_review", "requires_review"}
APPROVED_STATUSES = {"approved", "locked", "scope_specific", "reviewed", "verified"}
REFERENCE_STATUSES = {"reference", "reference_only"}

PACK_ENTRY_FILES = {
    "term": "term-registry.csv",
    "forbidden_translation": "forbidden-translations.csv",
    "translation_memory": "translation-memory.jsonl",
    "example": "examples.jsonl",
    "style_decision": "style-decisions.jsonl",
    "alignment_example": "alignment-examples.jsonl",
    "claim_pattern": "claim-patterns.jsonl",
    "revision_memory": "revision-memory.jsonl",
}


def select_knowledge_packs(
    state_dir: Path,
    *,
    pack_ids: list[str] | None = None,
    pack_paths: list[Path] | None = None,
    source_locale: str,
    target_locale: str,
    domains: list[str] | None = None,
    scenario: str = "",
    operating_mode: str = "greenfield_localization",
    selection_source: str = "explicit",
    selected_by: str = "localize-anything-runtime",
    allow_experimental: bool = False,
    allowed_domains: list[str] | None = None,
    allowed_scenarios: list[str] | None = None,
    compatible_locales: list[str] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    if not source_locale or not target_locale:
        raise ValueError("source_locale and target_locale are required")
    if operating_mode not in OPERATING_MODES:
        raise ValueError(f"unsupported operating_mode: {operating_mode}")
    domains = sorted({str(value).strip() for value in (domains or []) if str(value).strip()})
    allowed_domains = sorted({str(value).strip() for value in (allowed_domains or []) if str(value).strip()})
    allowed_scenarios = sorted({str(value).strip() for value in (allowed_scenarios or []) if str(value).strip()})
    compatible_locales = sorted({str(value).strip() for value in (compatible_locales or []) if str(value).strip()})
    candidates = _selection_candidates(state_dir, pack_ids or [], pack_paths or [])
    if not candidates:
        raise ValueError("at least one pack_id or pack_path is required")
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for requested_id, path in candidates:
        reasons: list[str] = []
        pack = _read_pack_metadata(path, reasons)
        pack_id = str(pack.get("pack_id") or requested_id or path.name)
        if requested_id and pack_id != requested_id:
            reasons.append("pack_id_mismatch")
        pack_source = str(pack.get("source_locale") or "")
        pack_target = str(pack.get("target_locale") or "")
        if not _locale_matches(pack_source, source_locale, compatible_locales):
            reasons.append("source_locale_mismatch")
        if not _locale_matches(pack_target, target_locale, compatible_locales):
            reasons.append("target_locale_mismatch")
        pack_domains = sorted({str(value) for value in pack.get("domains", []) if str(value)}) if isinstance(pack.get("domains"), list) else []
        if domains and not set(domains).intersection(pack_domains) and not set(domains).intersection(allowed_domains):
            reasons.append("domain_mismatch")
        scenarios = sorted({str(value) for value in pack.get("supported_scenarios", []) if str(value)}) if isinstance(pack.get("supported_scenarios"), list) else []
        if scenario and scenario not in scenarios and scenario not in allowed_scenarios:
            reasons.append("scenario_mismatch")
        privacy_mode = str(pack.get("privacy_mode") or "")
        if privacy_mode == "experimental" and not allow_experimental:
            reasons.append("experimental_pack_not_allowed")
        status = str(pack.get("status") or "")
        freshness = _pack_freshness(pack)
        if status in BAD_STATUSES or freshness != "current":
            reasons.append("pack_not_current")
        record = {
            "pack_id": pack_id,
            "pack_path": path.as_posix(),
            "pack_status": status,
            "pack_freshness": freshness,
            "privacy_mode": privacy_mode,
            "sync_metadata": pack.get("sync_metadata", {}) if isinstance(pack.get("sync_metadata"), dict) else {},
            "source_locale": pack_source,
            "target_locale": pack_target,
            "domains": pack_domains,
            "supported_scenarios": scenarios,
            "reasons": sorted(set(reasons)) if reasons else ["explicit_match"],
            "source_artifact_references": sorted({PACK_JSON, *[str(value) for value in (pack.get("source_artifact_references", []) or [])]}),
        }
        (rejected if reasons else selected).append(record)
    selection = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-pack-selection-v1",
        "artifact": KNOWLEDGE_PACK_SELECTION_JSON,
        "status": "selected" if selected else "none_selected",
        "selection_source": selection_source,
        "source_locale": source_locale,
        "target_locale": target_locale,
        "domains": domains,
        "scenario": scenario,
        "operating_mode": operating_mode,
        "selected_by": selected_by,
        "selected_pack_ids": [item["pack_id"] for item in selected],
        "pack_paths": [item["pack_path"] for item in selected],
        "selected_packs": selected,
        "rejected_packs": rejected,
        "source_artifact_references": sorted({reference for item in selected for reference in item["source_artifact_references"]}),
    }
    if write:
        state_dir.mkdir(parents=True, exist_ok=True)
        write_json(state_dir / KNOWLEDGE_PACK_SELECTION_JSON, selection)
        build_knowledge_eligibility_report(state_dir)
        build_working_context_packet(state_dir)
    return selection


def build_knowledge_eligibility_report(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    selection = read_knowledge_pack_selection(state_dir)
    entries: list[dict[str, Any]] = []
    source_hashes: list[dict[str, str]] = []
    for selected_pack in selection.get("selected_packs", []):
        pack_path = Path(str(selected_pack.get("pack_path") or "")).resolve()
        for artifact_name in sorted({PACK_JSON, "provenance.jsonl", *PACK_ENTRY_FILES.values()}):
            artifact_path = pack_path / artifact_name
            if artifact_path.is_file():
                source_hashes.append({"path": artifact_path.as_posix(), "sha256": _file_hash(artifact_path)})
        provenance = {
            str(item.get("provenance_id")): item
            for item in _read_jsonl(pack_path / "provenance.jsonl")
            if item.get("provenance_id")
        }
        for knowledge_type, artifact_name in PACK_ENTRY_FILES.items():
            for record in _read_records(pack_path / artifact_name):
                entries.append(_classify_entry(selection, selected_pack, knowledge_type, artifact_name, record, provenance))
    entries.sort(key=lambda item: (item["pack_id"], item["knowledge_type"], item["knowledge_id"]))
    counts = {classification: sum(item["classification"] == classification for item in entries) for classification in (
        "hard_constraint", "soft_context", "reference_only", "negative_constraint", "review_required",
        "not_eligible", "stale", "scope_mismatch", "rejected",
    )}
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-eligibility-report-v1",
        "artifact": KNOWLEDGE_ELIGIBILITY_REPORT_JSON,
        "status": "pass" if selection.get("selected_packs") else "not_selected",
        "selection_artifact": KNOWLEDGE_PACK_SELECTION_JSON,
        "source_locale": selection.get("source_locale", ""),
        "target_locale": selection.get("target_locale", ""),
        "domains": selection.get("domains", []),
        "scenario": selection.get("scenario", ""),
        "operating_mode": selection.get("operating_mode", ""),
        "entries": entries,
        "summary": {"entry_count": len(entries), **{f"{key}_count": value for key, value in counts.items()}},
        "source_artifact_references": sorted({item["source_artifact"] for item in entries}),
        "source_artifact_hashes": source_hashes,
    }
    if write:
        write_json(state_dir / KNOWLEDGE_ELIGIBILITY_REPORT_JSON, report)
    return report


def build_working_context_packet(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    selection = read_knowledge_pack_selection(state_dir)
    report = read_knowledge_eligibility_report(state_dir)
    included = [item for item in report.get("entries", []) if item.get("classification") in {"hard_constraint", "soft_context", "reference_only", "negative_constraint"}]
    excluded = [item for item in report.get("entries", []) if item not in included]
    hard = [item for item in included if item["classification"] == "hard_constraint" and item["knowledge_type"] == "term"]
    negative = [item for item in included if item["classification"] == "negative_constraint"]
    hard, project_conflicts, shadowed = _apply_project_term_priority(state_dir, hard, selection)
    excluded.extend(shadowed)
    pack_conflicts = _hard_constraint_conflicts(hard)
    conflicts = sorted([*project_conflicts, *pack_conflicts], key=lambda item: (item["source_term"], item["reason"]))
    soft = [item for item in included if item["classification"] == "soft_context"]
    references = [item for item in included if item["classification"] == "reference_only"]
    claim_constraints = [item for item in included if item["knowledge_type"] == "claim_pattern" and item["classification"] in {"hard_constraint", "soft_context"}]
    context = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-working-context-packet-v1",
        "artifact": WORKING_CONTEXT_PACKET_JSON,
        "status": "blocked" if conflicts else "ready" if included else "empty",
        "selection_artifact": KNOWLEDGE_PACK_SELECTION_JSON,
        "eligibility_artifact": KNOWLEDGE_ELIGIBILITY_REPORT_JSON,
        "operating_mode": selection.get("operating_mode", ""),
        "source_locale": selection.get("source_locale", ""),
        "target_locale": selection.get("target_locale", ""),
        "scenario": selection.get("scenario", ""),
        "domains": selection.get("domains", []),
        "hard_constraints": hard,
        "negative_constraints": negative,
        "tm_suggestions": [item for item in soft if item["knowledge_type"] == "translation_memory"],
        "style_guidance": [item for item in soft if item["knowledge_type"] in {"style_decision", "alignment_example"}],
        "retrieved_examples": [item for item in references if item["knowledge_type"] in {"example", "alignment_example", "translation_memory"}],
        "reference_only_context": references,
        "claim_constraints": claim_constraints,
        "revision_hints": [item | {"automatic_rewrite_allowed": False} for item in soft if item["knowledge_type"] == "revision_memory"],
        "risk_notes": ([{"code": "hard_constraint_conflict", "count": len(conflicts)}] if conflicts else [])
        + ([{"code": "excluded_knowledge", "count": len(excluded)}] if excluded else []),
        "scenario_rules": {
            "scope_match_required": True,
            "blind_benchmark_context_firewall": selection.get("operating_mode") == "blind_benchmark",
            "reference_only_is_not_constraint": True,
            "revision_memory_is_hint_only": True,
        },
        "hard_constraint_conflicts": conflicts,
        "excluded_knowledge": sorted(excluded, key=lambda item: (item.get("pack_id", ""), item.get("knowledge_type", ""), item.get("knowledge_id", ""))),
        "provenance": _included_provenance([*hard, *negative, *soft, *references, *claim_constraints]),
        "knowledge_policy": {
            "enabled": bool(included),
            "allowed_classes": sorted({item["classification"] for item in included}),
            "knowledge_augmented_quality_claim_allowed": False,
            "local_first": True,
            "provider_call_performed": False,
            "semantic_retrieval_performed": False,
        },
        "input_hashes": {
            name: _file_hash(state_dir / name)
            for name in (
                KNOWLEDGE_PACK_SELECTION_JSON,
                KNOWLEDGE_ELIGIBILITY_REPORT_JSON,
                "localization-brief.json",
                "term-registry.csv",
                "term-decisions.jsonl",
                "forbidden-translations.csv",
            )
            if (state_dir / name).is_file()
        },
    }
    if write:
        write_json(state_dir / WORKING_CONTEXT_PACKET_JSON, context)
    return context


def read_knowledge_pack_selection(state_dir: Path) -> dict[str, Any]:
    return _read_required_json(state_dir / KNOWLEDGE_PACK_SELECTION_JSON)


def read_knowledge_eligibility_report(state_dir: Path) -> dict[str, Any]:
    return _read_required_json(state_dir / KNOWLEDGE_ELIGIBILITY_REPORT_JSON)


def read_working_context_packet(state_dir: Path) -> dict[str, Any]:
    return _read_required_json(state_dir / WORKING_CONTEXT_PACKET_JSON)


def knowledge_consumption_asset_paths(state_dir: Path) -> dict[str, str]:
    return {
        key: name
        for key, name in {
            "knowledge_pack_selection": KNOWLEDGE_PACK_SELECTION_JSON,
            "knowledge_eligibility_report": KNOWLEDGE_ELIGIBILITY_REPORT_JSON,
            "working_context_packet": WORKING_CONTEXT_PACKET_JSON,
        }.items()
        if (state_dir / name).is_file()
    }


def imported_term_rows(state_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    path = state_dir / WORKING_CONTEXT_PACKET_JSON
    if not path.is_file():
        return [], []
    context = read_json(path)
    if context.get("status") == "blocked":
        return [], []
    terms = [_term_row(item) for item in context.get("hard_constraints", []) if item.get("knowledge_type") == "term"]
    forbidden = [_forbidden_row(item) for item in context.get("negative_constraints", [])]
    return terms, forbidden


def _selection_candidates(state_dir: Path, pack_ids: list[str], pack_paths: list[Path]) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    for pack_id in pack_ids:
        if not pack_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in pack_id):
            raise ValueError(f"Invalid pack_id: {pack_id!r}")
        candidates.append((pack_id, (state_dir / KNOWLEDGE_ROOT / pack_id).resolve()))
    candidates.extend(("", Path(path).expanduser().resolve()) for path in pack_paths)
    deduped: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for pack_id, path in candidates:
        key = path.as_posix().casefold()
        if key not in seen:
            deduped.append((pack_id, path))
            seen.add(key)
    return deduped


def _read_pack_metadata(path: Path, reasons: list[str]) -> dict[str, Any]:
    pack_path = path / PACK_JSON
    if not path.is_dir() or not pack_path.is_file():
        reasons.append("missing_pack_metadata")
        return {}
    try:
        pack = read_json(pack_path)
    except (OSError, ValueError, json.JSONDecodeError):
        reasons.append("invalid_pack_metadata")
        return {}
    required = ("pack_id", "source_locale", "target_locale", "privacy_mode", "status")
    if (
        not all(str(pack.get(key) or "").strip() for key in required)
        or pack.get("schema") != "localize-anything-knowledge-pack-v1"
        or pack.get("privacy_mode") not in {"local_only", "team_shared", "experimental"}
        or not isinstance(pack.get("domains", []), list)
        or not isinstance(pack.get("supported_scenarios", []), list)
    ):
        reasons.append("invalid_pack_metadata")
    return pack


def _pack_freshness(pack: dict[str, Any]) -> str:
    freshness = str(pack.get("freshness") or "current").strip().lower()
    status = str(pack.get("status") or "").strip().lower()
    return "stale" if status in BAD_STATUSES or freshness in {"stale", "expired", "invalid"} else "current"


def _locale_matches(pack_locale: str, requested_locale: str, compatible: list[str]) -> bool:
    if pack_locale == requested_locale:
        return True
    return f"{pack_locale}->{requested_locale}" in compatible or f"{requested_locale}->{pack_locale}" in compatible


def _classify_entry(
    selection: dict[str, Any],
    selected_pack: dict[str, Any],
    knowledge_type: str,
    artifact_name: str,
    record: dict[str, Any],
    provenance: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    status = str(record.get("status") or "reference").strip().lower()
    scope = str(record.get("scope") or "limited").strip()
    provenance_id = str(record.get("provenance_id") or record.get("provenance") or "").strip()
    provenance_record = provenance.get(provenance_id, {})
    source_value = str(record.get("source_term") or record.get("source_value") or record.get("source") or "")
    target_value = str(record.get("target_term") or record.get("forbidden_target") or record.get("target_value") or record.get("target") or "")
    knowledge_id = str(record.get("knowledge_id") or provenance_id or _stable_id(selected_pack.get("pack_id"), artifact_name, record))
    classification = "not_eligible"
    reasons: list[str] = []
    if status == "stale":
        classification, reasons = "stale", ["entry_stale"]
    elif status in {"rejected", "superseded", "obsolete"}:
        classification, reasons = "rejected", [f"entry_{status}"]
    elif status in BAD_STATUSES:
        classification, reasons = "not_eligible", [f"entry_{status}"]
    elif not _scope_matches(scope, str(selection.get("scenario") or ""), selection.get("domains", [])):
        classification, reasons = "scope_mismatch", ["scope_mismatch"]
    elif status in REVIEW_STATUSES:
        classification, reasons = "review_required", ["status_requires_review"]
    elif selection.get("operating_mode") == "blind_benchmark" and target_value:
        classification, reasons = "not_eligible", ["blind_benchmark_target_context_hidden"]
    elif not _valid_provenance(provenance_id, provenance_record):
        classification, reasons = "not_eligible", ["missing_valid_provenance"]
    elif knowledge_type == "term" and status in APPROVED_STATUSES:
        classification, reasons = "hard_constraint", ["approved_scoped_term"]
    elif knowledge_type == "forbidden_translation" and status in APPROVED_STATUSES:
        classification, reasons = "negative_constraint", ["approved_forbidden_translation"]
    elif knowledge_type == "translation_memory" and status in APPROVED_STATUSES:
        classification, reasons = "soft_context", ["reviewed_tm_suggestion"]
    elif knowledge_type == "style_decision" and status in APPROVED_STATUSES:
        classification, reasons = "soft_context", ["approved_style_guidance"]
    elif knowledge_type == "claim_pattern" and status in APPROVED_STATUSES:
        classification, reasons = "hard_constraint", ["approved_claim_review_constraint"]
    elif knowledge_type == "revision_memory" and status in APPROVED_STATUSES:
        classification, reasons = "soft_context", ["review_or_repair_hint_only"]
    elif knowledge_type in {"example", "alignment_example", "translation_memory"} or status in REFERENCE_STATUSES:
        classification, reasons = "reference_only", ["reference_only_not_constraint"]
    return {
        "knowledge_id": knowledge_id,
        "pack_id": str(selected_pack.get("pack_id") or ""),
        "pack_path": str(selected_pack.get("pack_path") or ""),
        "knowledge_type": knowledge_type,
        "source_artifact": artifact_name,
        "source_value": source_value,
        "target_value": target_value,
        "status": status,
        "scope": scope,
        "classification": classification,
        "reasons": reasons,
        "provenance_id": provenance_id,
        "provenance": provenance_record,
        "priority": str(record.get("priority") or "pack_generic"),
        "source_locale": str(record.get("source_locale") or selected_pack.get("source_locale") or ""),
        "target_locale": str(record.get("target_locale") or selected_pack.get("target_locale") or ""),
    }


def _scope_matches(scope: str, scenario: str, domains: list[str]) -> bool:
    if scope in {"global", "full_run", "all", "*"}:
        return True
    if scope == scenario or scope in domains:
        return True
    try:
        value = json.loads(scope)
    except (json.JSONDecodeError, TypeError):
        value = None
    if isinstance(value, dict):
        values = {str(child) for child in value.values() if not isinstance(child, (dict, list))}
        return bool(({scenario, *domains} - {""}) & values)
    return False


def _valid_provenance(provenance_id: str, record: dict[str, Any]) -> bool:
    return bool(provenance_id and record and record.get("source_artifact_references"))


def _apply_project_term_priority(
    state_dir: Path,
    hard: list[dict[str, Any]],
    selection: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    local_rows = _read_csv(state_dir / "term-registry.csv")
    kept: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    shadowed: list[dict[str, Any]] = []
    for item in hard:
        local = next(
            (
                row
                for row in local_rows
                if row.get("source_term", "").casefold() == item.get("source_value", "").casefold()
                and row.get("status") in {"approved", "locked"}
                and row.get("target_locale", "") in {"", item.get("target_locale", "")}
                and (
                    row.get("scope", "") in {"", "global", "full_run", "all", "*"}
                    or _scope_matches(str(row.get("scope") or ""), str(selection.get("scenario") or ""), selection.get("domains", []))
                )
            ),
            None,
        )
        if not local:
            kept.append(item)
            continue
        excluded = item | {"classification": "not_eligible", "reasons": ["project_local_term_outranks_pack"]}
        shadowed.append(excluded)
        if str(local.get("target_term") or "") != str(item.get("target_value") or ""):
            conflicts.append({
                "source_term": item.get("source_value", ""),
                "targets": sorted({str(local.get("target_term") or ""), str(item.get("target_value") or "")}),
                "reason": "project_local_term_conflicts_with_pack",
                "blocking": item.get("status") == "locked" or local.get("status") == "locked",
                "pack_id": item.get("pack_id"),
                "provenance_id": item.get("provenance_id"),
            })
    return kept, conflicts, shadowed


def _hard_constraint_conflicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_source: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        by_source.setdefault(str(item.get("source_value") or "").casefold(), []).append(item)
    conflicts: list[dict[str, Any]] = []
    for grouped in by_source.values():
        targets = sorted({str(item.get("target_value") or "") for item in grouped})
        if len(targets) > 1:
            conflicts.append({
                "source_term": grouped[0].get("source_value", ""),
                "targets": targets,
                "reason": "conflicting_pack_hard_constraints",
                "blocking": any(item.get("status") == "locked" for item in grouped),
                "pack_ids": sorted({str(item.get("pack_id") or "") for item in grouped}),
            })
    return conflicts


def _included_provenance(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        provenance_id = str(item.get("provenance_id") or "")
        if provenance_id and provenance_id not in seen:
            result.append({"provenance_id": provenance_id, "pack_id": item.get("pack_id"), "source_artifact": item.get("source_artifact"), "record": item.get("provenance", {})})
            seen.add(provenance_id)
    return result


def _term_row(item: dict[str, Any]) -> dict[str, str]:
    return {
        "source_term": str(item.get("source_value") or ""),
        "target_term": str(item.get("target_value") or ""),
        "type": "imported_pack_term",
        "status": str(item.get("status") or "approved"),
        "priority": "pack_generic",
        "scope": str(item.get("scope") or "limited"),
        "notes": f"imported from knowledge pack {item.get('pack_id')}",
        "source_locale": str(item.get("source_locale") or ""),
        "target_locale": str(item.get("target_locale") or ""),
        "forbidden_targets": "",
        "provenance": str(item.get("provenance_id") or ""),
    }


def _forbidden_row(item: dict[str, Any]) -> dict[str, str]:
    return {
        "source_term": str(item.get("source_value") or ""),
        "forbidden_target": str(item.get("target_value") or ""),
        "target_locale": str(item.get("target_locale") or ""),
        "scope": str(item.get("scope") or "limited"),
        "reason": "imported_pack_negative_constraint",
        "status": "approved",
        "provenance": str(item.get("provenance_id") or ""),
    }


def _read_records(path: Path) -> list[dict[str, Any]]:
    return _read_csv(path) if path.suffix == ".csv" else _read_jsonl(path)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{str(key): str(value or "").strip() for key, value in row.items() if key} for row in csv.DictReader(handle)]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.is_file() else []


def _read_required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing knowledge consumption artifact: {path}")
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Knowledge consumption artifact must be an object: {path}")
    return value


def _stable_id(pack_id: Any, artifact: str, record: dict[str, Any]) -> str:
    payload = json.dumps({"pack_id": pack_id, "artifact": artifact, "record": record}, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return f"knowledge-{hashlib.sha256(payload).hexdigest()[:24]}"


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
