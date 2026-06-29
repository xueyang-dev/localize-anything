from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .document_decision import DOCUMENT_DECISION_LOG_JSONL, LEADERSHIP_REVIEW_EVIDENCE_JSONL
from .human_review import HUMAN_REVIEW_EVIDENCE_JSONL, summarize_human_review_evidence
from .io_utils import read_json, read_jsonl, write_json, write_jsonl
from .term_governance import FORBIDDEN_TRANSLATION_COLUMNS, TERM_REGISTRY_COLUMNS


KNOWLEDGE_ROOT = ".localize-anything/knowledge/packs"
PACK_JSON = "pack.json"
PACK_TERM_REGISTRY_CSV = "term-registry.csv"
GLOSSARY_CSV = "glossary.csv"
TRANSLATION_MEMORY_JSONL = "translation-memory.jsonl"
EXAMPLES_JSONL = "examples.jsonl"
STYLE_PROFILE_MD = "style-profile.md"
PACK_FORBIDDEN_TRANSLATIONS_CSV = "forbidden-translations.csv"
CLAIM_PATTERNS_JSONL = "claim-patterns.jsonl"
STYLE_DECISIONS_JSONL = "style-decisions.jsonl"
ALIGNMENT_EXAMPLES_JSONL = "alignment-examples.jsonl"
REVISION_MEMORY_JSONL = "revision-memory.jsonl"
PROVENANCE_JSONL = "provenance.jsonl"
QUALITY_REPORT_MD = "quality-report.md"
KNOWLEDGE_REVIEW_QUEUE_JSON = "knowledge-review-queue.json"
KNOWLEDGE_REVIEW_DECISIONS_JSONL = "knowledge-review-decisions.jsonl"

PACK_ARTIFACTS = (
    PACK_JSON,
    PACK_TERM_REGISTRY_CSV,
    GLOSSARY_CSV,
    TRANSLATION_MEMORY_JSONL,
    EXAMPLES_JSONL,
    STYLE_PROFILE_MD,
    PACK_FORBIDDEN_TRANSLATIONS_CSV,
    CLAIM_PATTERNS_JSONL,
    STYLE_DECISIONS_JSONL,
    ALIGNMENT_EXAMPLES_JSONL,
    REVISION_MEMORY_JSONL,
    PROVENANCE_JSONL,
    QUALITY_REPORT_MD,
    KNOWLEDGE_REVIEW_QUEUE_JSON,
    KNOWLEDGE_REVIEW_DECISIONS_JSONL,
)

GLOSSARY_COLUMNS = [
    "source_term",
    "target_term",
    "status",
    "scope",
    "source_locale",
    "target_locale",
    "provenance_id",
    "notes",
]

DECISIONS = {
    "approve",
    "lock",
    "reject",
    "defer",
    "scope_limit",
    "mark_reference_only",
    "mark_obsolete",
    "merge_duplicate",
    "requires_follow_up",
}

PROMOTABLE_DECISIONS = {"approve", "lock", "scope_limit", "mark_reference_only"}
APPROVED_STATUSES = {"approved", "locked", "scope_specific"}
BAD_SOURCE_STATUSES = {"stale", "rejected", "superseded", "blocked", "failed_qa", "unresolved"}


def knowledge_pack_dir(state_dir: Path, pack_id: str) -> Path:
    pack_id = _safe_pack_id(pack_id)
    return state_dir.resolve() / KNOWLEDGE_ROOT / pack_id


def discover_knowledge_pack_artifact_specs(state_dir: Path) -> list[dict[str, str]]:
    root = state_dir.resolve() / KNOWLEDGE_ROOT
    if not root.is_dir():
        return []
    specs: list[dict[str, str]] = []
    for pack_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        pack_id = pack_dir.name
        for artifact in PACK_ARTIFACTS:
            if (pack_dir / artifact).is_file():
                artifact_key = artifact.replace(".", "_").replace("-", "_")
                specs.append(
                    {
                        "artifact_id": f"knowledge_pack_{pack_id}_{artifact_key}",
                        "artifact_type": artifact_key,
                        "path": f"{KNOWLEDGE_ROOT}/{pack_id}/{artifact}",
                        "produced_by": "personal_knowledge_pack_builder",
                    }
                )
    return specs


def init_knowledge_pack(
    state_dir: Path,
    *,
    pack_id: str,
    name: str | None = None,
    source_locale: str | None = None,
    target_locale: str | None = None,
    domains: list[str] | None = None,
    privacy_mode: str = "local_only",
    created_by: str = "localize-anything-runtime",
    quality_level: str = "raw",
    supported_scenarios: list[str] | None = None,
    review_policy: dict[str, Any] | None = None,
    source_artifact_references: list[str] | None = None,
    status: str = "draft",
    write: bool = True,
) -> dict[str, Any]:
    pack_dir = knowledge_pack_dir(state_dir, pack_id)
    pack = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-pack-v1",
        "artifact": PACK_JSON,
        "pack_id": _safe_pack_id(pack_id),
        "name": name or _safe_pack_id(pack_id),
        "source_locale": source_locale or "",
        "target_locale": target_locale or "",
        "domains": sorted({str(value) for value in (domains or []) if str(value)}),
        "privacy_mode": privacy_mode,
        "created_by": created_by,
        "created_at": _now(),
        "quality_level": quality_level,
        "source_artifact_references": sorted({str(value) for value in (source_artifact_references or []) if str(value)}),
        "review_policy": review_policy or {"promotion_requires_review": True, "raw_generated_segments_are_reference_only": True},
        "supported_scenarios": sorted({str(value) for value in (supported_scenarios or []) if str(value)}),
        "status": status,
    }
    if write:
        pack_dir.mkdir(parents=True, exist_ok=True)
        write_json(pack_dir / PACK_JSON, pack)
        _write_csv(pack_dir / PACK_TERM_REGISTRY_CSV, TERM_REGISTRY_COLUMNS, [])
        _write_csv(pack_dir / GLOSSARY_CSV, GLOSSARY_COLUMNS, [])
        _write_csv(pack_dir / PACK_FORBIDDEN_TRANSLATIONS_CSV, FORBIDDEN_TRANSLATION_COLUMNS, [])
        for artifact in (
            TRANSLATION_MEMORY_JSONL,
            EXAMPLES_JSONL,
            CLAIM_PATTERNS_JSONL,
            STYLE_DECISIONS_JSONL,
            ALIGNMENT_EXAMPLES_JSONL,
            REVISION_MEMORY_JSONL,
            PROVENANCE_JSONL,
            KNOWLEDGE_REVIEW_DECISIONS_JSONL,
        ):
            path = pack_dir / artifact
            if not path.exists():
                path.write_text("", encoding="utf-8")
        write_json(pack_dir / KNOWLEDGE_REVIEW_QUEUE_JSON, _empty_queue(pack))
        (pack_dir / STYLE_PROFILE_MD).write_text("# Style Profile\n\nNo reviewed style knowledge has been exported yet.\n", encoding="utf-8")
        (pack_dir / QUALITY_REPORT_MD).write_text(_render_quality_report(pack, [], [], []), encoding="utf-8")
    return pack


def read_knowledge_pack(state_dir: Path, pack_id: str) -> dict[str, Any]:
    return read_json(knowledge_pack_dir(state_dir, pack_id) / PACK_JSON)


def export_knowledge_pack(state_dir: Path, pack_id: str, *, write: bool = True) -> dict[str, Any]:
    pack_dir = knowledge_pack_dir(state_dir, pack_id)
    pack = _read_pack_or_init(state_dir, pack_id, write=write)
    candidates = _collect_candidates(state_dir, pack)
    decisions = read_knowledge_review_decisions(state_dir, pack_id)
    candidates = [_apply_review_decision(candidate, decisions) for candidate in candidates]
    queue = _queue(pack, candidates)
    artifacts = _pack_artifacts(pack, candidates)
    provenance = _provenance_records(candidates)
    report = _render_quality_report(pack, candidates, decisions, artifacts["skipped"])
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-pack-export-result-v1",
        "pack_id": pack["pack_id"],
        "pack_dir": pack_dir.as_posix(),
        "status": "pass",
        "artifacts": {name: f"{KNOWLEDGE_ROOT}/{pack['pack_id']}/{name}" for name in PACK_ARTIFACTS},
        "summary": queue["summary"] | artifacts["summary"],
    }
    if write:
        pack_dir.mkdir(parents=True, exist_ok=True)
        write_json(pack_dir / PACK_JSON, pack)
        write_json(pack_dir / KNOWLEDGE_REVIEW_QUEUE_JSON, queue)
        _write_csv(pack_dir / PACK_TERM_REGISTRY_CSV, TERM_REGISTRY_COLUMNS, artifacts["term_registry"])
        _write_csv(pack_dir / GLOSSARY_CSV, GLOSSARY_COLUMNS, artifacts["glossary"])
        _write_csv(pack_dir / PACK_FORBIDDEN_TRANSLATIONS_CSV, FORBIDDEN_TRANSLATION_COLUMNS, artifacts["forbidden_translations"])
        write_jsonl(pack_dir / TRANSLATION_MEMORY_JSONL, artifacts["translation_memory"])
        write_jsonl(pack_dir / EXAMPLES_JSONL, artifacts["examples"])
        write_jsonl(pack_dir / CLAIM_PATTERNS_JSONL, artifacts["claim_patterns"])
        write_jsonl(pack_dir / STYLE_DECISIONS_JSONL, artifacts["style_decisions"])
        write_jsonl(pack_dir / ALIGNMENT_EXAMPLES_JSONL, artifacts["alignment_examples"])
        write_jsonl(pack_dir / REVISION_MEMORY_JSONL, artifacts["revision_memory"])
        write_jsonl(pack_dir / PROVENANCE_JSONL, provenance)
        (pack_dir / STYLE_PROFILE_MD).write_text(_render_style_profile(artifacts["style_decisions"], artifacts["alignment_examples"]), encoding="utf-8")
        (pack_dir / QUALITY_REPORT_MD).write_text(report, encoding="utf-8")
    return result


def read_knowledge_review_queue(state_dir: Path, pack_id: str) -> dict[str, Any]:
    return read_json(knowledge_pack_dir(state_dir, pack_id) / KNOWLEDGE_REVIEW_QUEUE_JSON)


def read_knowledge_review_decisions(state_dir: Path, pack_id: str) -> list[dict[str, Any]]:
    path = knowledge_pack_dir(state_dir, pack_id) / KNOWLEDGE_REVIEW_DECISIONS_JSONL
    return read_jsonl(path) if path.is_file() else []


def record_knowledge_review_decision(
    state_dir: Path,
    pack_id: str,
    decision: dict[str, Any],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    normalized = _normalize_review_decision(pack_id, decision, run_id=run_id)
    pack_dir = knowledge_pack_dir(state_dir, pack_id)
    decisions = read_knowledge_review_decisions(state_dir, pack_id)
    decisions.append(normalized)
    write_jsonl(pack_dir / KNOWLEDGE_REVIEW_DECISIONS_JSONL, decisions)
    export_result = export_knowledge_pack(state_dir, pack_id)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-review-decision-record-result-v1",
        "artifact": KNOWLEDGE_REVIEW_DECISIONS_JSONL,
        "record": normalized,
        "export_result": export_result,
    }


def read_knowledge_quality_report(state_dir: Path, pack_id: str) -> str:
    return (knowledge_pack_dir(state_dir, pack_id) / QUALITY_REPORT_MD).read_text(encoding="utf-8")


def _read_pack_or_init(state_dir: Path, pack_id: str, *, write: bool) -> dict[str, Any]:
    path = knowledge_pack_dir(state_dir, pack_id) / PACK_JSON
    if path.is_file():
        return read_json(path)
    return init_knowledge_pack(state_dir, pack_id=pack_id, write=write)


def _collect_candidates(state_dir: Path, pack: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    candidates.extend(_term_candidates(state_dir, pack))
    candidates.extend(_forbidden_candidates(state_dir, pack))
    candidates.extend(_document_decision_candidates(state_dir, pack))
    candidates.extend(_repair_candidates(state_dir, pack))
    candidates.extend(_generated_segment_candidates(state_dir, pack))
    return _dedupe_candidates(candidates)


def _term_candidates(state_dir: Path, pack: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in _read_csv_rows(state_dir / "term-registry.csv"):
        source = row.get("source_term", "")
        target = row.get("target_term", "")
        if not source or not target:
            continue
        status = row.get("status", "reference")
        promotable = status in APPROVED_STATUSES
        items.append(
            _candidate(
                "term",
                source,
                target,
                status if promotable else "reference",
                ["term-registry.csv"],
                row.get("scope") or "global",
                confidence="high" if promotable else "medium",
                risk_level="low" if promotable else "medium",
                recommended_decision="lock" if status == "locked" else "approve" if promotable else "defer",
                human_confirmation_required=not promotable,
                metadata=row,
            )
        )
    for record in _read_jsonl_if_exists(state_dir / "term-decisions.jsonl") + _read_jsonl_if_exists(state_dir / "term-review-decisions.jsonl"):
        source = str(record.get("source_term") or record.get("term") or record.get("source_value") or "")
        target = str(record.get("target_term") or record.get("target_value") or record.get("approved_translation") or "")
        status = str(record.get("status") or record.get("decision") or "candidate")
        if source and target:
            items.append(
                _candidate(
                    "term",
                    source,
                    target,
                    "locked" if status == "locked" else "approved" if status in {"approved", "accept", "accepted"} else "reference",
                    ["term-decisions.jsonl"],
                    _scope_text(record.get("scope") or record.get("effective_scope")),
                    confidence="high" if status in {"approved", "locked", "accepted"} else "low",
                    risk_level="low" if status in {"approved", "locked", "accepted"} else "medium",
                    recommended_decision="lock" if status == "locked" else "approve" if status in {"approved", "accepted"} else "defer",
                    human_confirmation_required=status not in {"approved", "locked", "accepted"},
                    metadata=record,
                )
            )
    return items


def _forbidden_candidates(state_dir: Path, pack: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in _read_csv_rows(state_dir / "forbidden-translations.csv"):
        source = row.get("source_term", "")
        target = row.get("forbidden_target", "")
        if not source or not target:
            continue
        has_provenance = bool(row.get("provenance"))
        status = row.get("status") or "reference"
        items.append(
            _candidate(
                "forbidden_translation",
                source,
                target,
                "locked" if status in {"locked", "approved", "verified"} and has_provenance else "reference",
                ["forbidden-translations.csv"],
                row.get("scope") or "global",
                confidence="high" if has_provenance else "medium",
                risk_level="high",
                recommended_decision="lock" if has_provenance else "mark_reference_only",
                blocking_reason=None if has_provenance else "missing_explicit_provenance",
                human_confirmation_required=not has_provenance,
                metadata=row,
            )
        )
    return items


def _document_decision_candidates(state_dir: Path, pack: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in _read_jsonl_if_exists(state_dir / DOCUMENT_DECISION_LOG_JSONL):
        status = str(record.get("decision_status") or "")
        decision_type = str(record.get("decision_type") or "")
        source_value = decision_type
        target_value = str(record.get("decision_rationale") or record.get("accepted_limitation") or decision_type)
        candidate_type = _document_candidate_type(decision_type)
        items.append(
            _candidate(
                candidate_type,
                source_value,
                target_value,
                "scope_specific" if status in {"accepted", "accepted_with_limitations"} else "reference",
                [DOCUMENT_DECISION_LOG_JSONL],
                _scope_text(record.get("effective_scope")),
                confidence="high" if status in {"accepted", "accepted_with_limitations"} else "low",
                risk_level="high" if "publicity" in decision_type or "metric" in decision_type else "medium",
                recommended_decision="approve" if status in {"accepted", "accepted_with_limitations"} else "defer",
                blocking_reason=None if status in {"accepted", "accepted_with_limitations"} else f"decision_status_{status or 'missing'}",
                human_confirmation_required=status not in {"accepted", "accepted_with_limitations"},
                metadata=record,
            )
        )
    for record in _read_jsonl_if_exists(state_dir / LEADERSHIP_REVIEW_EVIDENCE_JSONL):
        decision = str(record.get("decision") or "")
        if decision not in {"accepted", "accepted_with_limitations"}:
            continue
        for claim in record.get("reviewed_claims", []) or ["leadership_confirmation"]:
            items.append(
                _candidate(
                    "claim_pattern",
                    str(claim),
                    "; ".join(str(value) for value in record.get("limitations", [])),
                    "scope_specific",
                    [LEADERSHIP_REVIEW_EVIDENCE_JSONL],
                    _scope_text(record.get("review_scope")),
                    confidence="medium",
                    risk_level="high",
                    recommended_decision="approve",
                    human_confirmation_required=False,
                    metadata=record,
                )
            )
    return items


def _repair_candidates(state_dir: Path, pack: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in _read_jsonl_if_exists(state_dir / "repair-history.jsonl"):
        status = str(record.get("repair_status") or record.get("status") or "")
        qa_passed = _qa_passed(record)
        items.append(
            _candidate(
                "revision_memory",
                str(record.get("segment_id") or record.get("repair_id") or "repair"),
                str(record.get("repair_reason") or record.get("reason") or record.get("repair_type") or ""),
                "approved" if status in {"applied", "accepted"} and qa_passed else "candidate",
                ["repair-history.jsonl"],
                _scope_text(record.get("scope")),
                confidence="high" if qa_passed else "low",
                risk_level="medium",
                recommended_decision="approve" if status in {"applied", "accepted"} and qa_passed else "defer",
                blocking_reason=None if status in {"applied", "accepted"} and qa_passed else "repair_not_applied_or_qa_not_passed",
                human_confirmation_required=not qa_passed,
                metadata=record,
            )
        )
    return items


def _generated_segment_candidates(state_dir: Path, pack: dict[str, Any]) -> list[dict[str, Any]]:
    records = _read_jsonl_if_exists(state_dir / "generated-segments.jsonl")
    if not records:
        records = _read_jsonl_if_exists(state_dir / "generated.jsonl")
    if not records:
        return []
    review = summarize_human_review_evidence(_read_jsonl_if_exists(state_dir / HUMAN_REVIEW_EVIDENCE_JSONL))
    signoff = _read_optional_json(state_dir / "signoff-record.json")
    reviewed = bool(review.get("global_supported_levels"))
    signed = bool(signoff.get("delivery_authorized"))
    items: list[dict[str, Any]] = []
    for record in records:
        source = str(record.get("source") or record.get("source_text") or "")
        target = str(record.get("target") or record.get("target_text") or record.get("translation") or "")
        if not source or not target:
            continue
        status = "approved" if reviewed else "reference" if signed else "candidate"
        items.append(
            _candidate(
                "tm_entry",
                source,
                target,
                status,
                ["generated-segments.jsonl"],
                "full_run" if reviewed else "limited",
                confidence="medium" if reviewed or signed else "low",
                risk_level="high" if not reviewed else "medium",
                recommended_decision="approve" if reviewed else "mark_reference_only",
                blocking_reason=None if reviewed or signed else "raw_generated_segment_without_review_evidence",
                human_confirmation_required=not reviewed,
                metadata={"segment_id": record.get("segment_id"), "reviewed": reviewed, "signed": signed},
            )
        )
    return items


def _pack_artifacts(pack: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    term_registry: list[dict[str, str]] = []
    glossary: list[dict[str, str]] = []
    forbidden: list[dict[str, str]] = []
    tm: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    claim_patterns: list[dict[str, Any]] = []
    style_decisions: list[dict[str, Any]] = []
    alignment: list[dict[str, Any]] = []
    revision: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for item in candidates:
        if not _is_promoted(item):
            skipped.append({"candidate_id": item["candidate_id"], "reason": item.get("blocking_reason") or "not_approved_or_locked"})
            continue
        if item["candidate_type"] == "term":
            row = _term_row(pack, item)
            term_registry.append(row)
            glossary.append(_glossary_row(pack, item))
        elif item["candidate_type"] == "forbidden_translation":
            forbidden.append(_forbidden_row(pack, item))
        elif item["candidate_type"] == "tm_entry":
            tm.append(_jsonl_item(pack, item, "translation_memory_entry"))
        elif item["candidate_type"] == "claim_pattern":
            claim_patterns.append(_jsonl_item(pack, item, "claim_pattern"))
        elif item["candidate_type"] == "style_rule":
            style_decisions.append(_jsonl_item(pack, item, "style_decision"))
        elif item["candidate_type"] == "alignment_example":
            alignment.append(_jsonl_item(pack, item, "alignment_example"))
            examples.append(_jsonl_item(pack, item, "example"))
        elif item["candidate_type"] == "revision_memory":
            revision.append(_jsonl_item(pack, item, "revision_memory"))
    return {
        "term_registry": term_registry,
        "glossary": glossary,
        "forbidden_translations": forbidden,
        "translation_memory": tm,
        "examples": examples,
        "claim_patterns": claim_patterns,
        "style_decisions": style_decisions,
        "alignment_examples": alignment,
        "revision_memory": revision,
        "skipped": skipped,
        "summary": {
            "approved_or_locked_entry_count": len(term_registry) + len(forbidden) + len(tm) + len(claim_patterns) + len(style_decisions) + len(alignment) + len(revision),
            "reference_or_candidate_skipped_count": len(skipped),
            "safe_for_hard_constraints": bool(term_registry or forbidden) and not any(item.get("risk_level") == "high" and item.get("human_confirmation_required") for item in candidates),
        },
    }


def _apply_review_decision(candidate: dict[str, Any], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    matching = [item for item in decisions if item.get("candidate_id") == candidate["candidate_id"]]
    if not matching:
        return candidate
    decision = matching[-1]
    value = str(decision.get("decision") or "")
    updated = dict(candidate)
    updated["review_decision"] = value
    updated["review_decision_id"] = decision.get("decision_id")
    if value == "approve":
        updated["proposed_status"] = "approved"
        updated["blocking_reason"] = None
        updated["human_confirmation_required"] = False
    elif value == "lock":
        updated["proposed_status"] = "locked"
        updated["blocking_reason"] = None
        updated["human_confirmation_required"] = False
    elif value == "scope_limit":
        updated["proposed_status"] = "scope_specific"
        updated["scope"] = _scope_text(decision.get("effective_scope") or decision.get("scope") or updated.get("scope"))
        updated["blocking_reason"] = None
        updated["human_confirmation_required"] = False
    elif value == "mark_reference_only":
        updated["proposed_status"] = "reference"
        updated["blocking_reason"] = "reference_only_not_hard_constraint"
    elif value in {"reject", "mark_obsolete"}:
        updated["proposed_status"] = "rejected" if value == "reject" else "obsolete"
        updated["blocking_reason"] = value
    elif value in {"defer", "requires_follow_up", "merge_duplicate"}:
        updated["blocking_reason"] = value
    return updated


def _normalize_review_decision(pack_id: str, decision: dict[str, Any], *, run_id: str | None) -> dict[str, Any]:
    value = str(decision.get("decision") or "").strip()
    candidate_id = str(decision.get("candidate_id") or "").strip()
    if value not in DECISIONS:
        raise ValueError(f"decision must be one of: {', '.join(sorted(DECISIONS))}")
    if not candidate_id:
        raise ValueError("candidate_id is required")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-review-decision-v1",
        "run_id": run_id or decision.get("run_id"),
        "pack_id": _safe_pack_id(pack_id),
        "decision_id": str(decision.get("decision_id") or _stable_id("knowledge-review-decision", decision)[:32]),
        "candidate_id": candidate_id,
        "decision": value,
        "reviewer_role": str(decision.get("reviewer_role") or "knowledge_reviewer"),
        "reviewer_reference": str(decision.get("reviewer_reference") or ""),
        "rationale": str(decision.get("rationale") or ""),
        "effective_scope": decision.get("effective_scope") if isinstance(decision.get("effective_scope"), dict) else {"scope_type": "limited"},
        "source_artifact_references": [str(item) for item in decision.get("source_artifact_references", [])],
        "created_at": str(decision.get("created_at") or _now()),
        "supersedes": decision.get("supersedes", []) if isinstance(decision.get("supersedes"), list) else [],
        "superseded_by": decision.get("superseded_by", []) if isinstance(decision.get("superseded_by"), list) else [],
    }


def _candidate(
    candidate_type: str,
    source_value: str,
    target_value: str,
    proposed_status: str,
    source_artifacts: list[str],
    scope: str,
    *,
    confidence: str,
    risk_level: str,
    recommended_decision: str,
    blocking_reason: str | None = None,
    human_confirmation_required: bool,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "candidate_type": candidate_type,
        "source_value": source_value,
        "target_value": target_value,
        "source_artifact_references": sorted(source_artifacts),
        "scope": scope or "limited",
        "metadata": metadata,
    }
    return {
        "candidate_id": _stable_id("knowledge-candidate", payload)[:32],
        "candidate_type": candidate_type,
        "source_value": source_value,
        "target_value": target_value,
        "proposed_status": proposed_status,
        "confidence": confidence,
        "source_artifact_references": sorted(source_artifacts),
        "provenance_summary": _provenance_summary(source_artifacts, metadata),
        "scope": scope or "limited",
        "risk_level": risk_level,
        "recommended_decision": recommended_decision,
        "blocking_reason": blocking_reason,
        "human_confirmation_required": human_confirmation_required,
        "metadata": metadata,
    }


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        existing = by_id.get(candidate["candidate_id"])
        if not existing or _status_rank(candidate.get("proposed_status")) < _status_rank(existing.get("proposed_status")):
            by_id[candidate["candidate_id"]] = candidate
    return [by_id[key] for key in sorted(by_id)]


def _queue(pack: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    items = [
        {key: value for key, value in candidate.items() if key != "metadata"}
        for candidate in candidates
    ]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-review-queue-v1",
        "artifact": KNOWLEDGE_REVIEW_QUEUE_JSON,
        "pack_id": pack["pack_id"],
        "status": "requires_review" if any(item.get("human_confirmation_required") for item in items) else "ready",
        "items": items,
        "summary": {
            "candidate_count": len(items),
            "human_confirmation_required_count": sum(1 for item in items if item.get("human_confirmation_required")),
            "approved_or_locked_candidate_count": sum(1 for item in items if item.get("proposed_status") in {"approved", "locked", "scope_specific"}),
            "reference_only_candidate_count": sum(1 for item in items if item.get("proposed_status") == "reference"),
            "blocked_candidate_count": sum(1 for item in items if item.get("blocking_reason")),
        },
        "source_artifacts": sorted({artifact for item in items for artifact in item.get("source_artifact_references", [])}),
    }


def _empty_queue(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-review-queue-v1",
        "artifact": KNOWLEDGE_REVIEW_QUEUE_JSON,
        "pack_id": pack["pack_id"],
        "status": "empty",
        "items": [],
        "summary": {
            "candidate_count": 0,
            "human_confirmation_required_count": 0,
            "approved_or_locked_candidate_count": 0,
            "reference_only_candidate_count": 0,
            "blocked_candidate_count": 0,
        },
        "source_artifacts": [],
    }


def _is_promoted(candidate: dict[str, Any]) -> bool:
    return candidate.get("proposed_status") in APPROVED_STATUSES and not candidate.get("blocking_reason")


def _term_row(pack: dict[str, Any], item: dict[str, Any]) -> dict[str, str]:
    metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
    return {
        "source_term": item["source_value"],
        "target_term": item["target_value"],
        "type": str(metadata.get("type") or "term"),
        "status": "scope_specific" if item["proposed_status"] == "scope_specific" else item["proposed_status"],
        "priority": str(metadata.get("priority") or "reviewed"),
        "scope": item["scope"],
        "notes": str(metadata.get("notes") or "exported_from_personal_knowledge_pack_builder"),
        "source_locale": str(metadata.get("source_locale") or pack.get("source_locale") or ""),
        "target_locale": str(metadata.get("target_locale") or pack.get("target_locale") or ""),
        "forbidden_targets": str(metadata.get("forbidden_targets") or ""),
        "provenance": item["candidate_id"],
    }


def _glossary_row(pack: dict[str, Any], item: dict[str, Any]) -> dict[str, str]:
    return {
        "source_term": item["source_value"],
        "target_term": item["target_value"],
        "status": item["proposed_status"],
        "scope": item["scope"],
        "source_locale": str(pack.get("source_locale") or ""),
        "target_locale": str(pack.get("target_locale") or ""),
        "provenance_id": item["candidate_id"],
        "notes": "approved knowledge" if item["proposed_status"] in {"approved", "locked"} else "scope-specific knowledge",
    }


def _forbidden_row(pack: dict[str, Any], item: dict[str, Any]) -> dict[str, str]:
    metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
    return {
        "source_term": item["source_value"],
        "forbidden_target": item["target_value"],
        "target_locale": str(metadata.get("target_locale") or pack.get("target_locale") or ""),
        "scope": item["scope"],
        "reason": str(metadata.get("reason") or "reviewed_forbidden_translation"),
        "status": item["proposed_status"],
        "provenance": item["candidate_id"],
    }


def _jsonl_item(pack: dict[str, Any], item: dict[str, Any], schema: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": f"localize-anything-{schema}-v1",
        "pack_id": pack["pack_id"],
        "knowledge_id": item["candidate_id"],
        "source_value": item["source_value"],
        "target_value": item["target_value"],
        "status": item["proposed_status"],
        "scope": item["scope"],
        "risk_level": item["risk_level"],
        "provenance_id": item["candidate_id"],
        "source_artifact_references": item["source_artifact_references"],
    }


def _provenance_records(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "protocol_version": PROTOCOL_VERSION,
            "schema": "localize-anything-knowledge-provenance-record-v1",
            "provenance_id": candidate["candidate_id"],
            "candidate_type": candidate["candidate_type"],
            "source_artifact_references": candidate["source_artifact_references"],
            "scope": candidate["scope"],
            "status": candidate["proposed_status"],
            "review_decision_id": candidate.get("review_decision_id"),
            "provenance_summary": candidate.get("provenance_summary", ""),
        }
        for candidate in candidates
    ]


def _render_quality_report(pack: dict[str, Any], candidates: list[dict[str, Any]], decisions: list[dict[str, Any]], skipped: list[dict[str, str]]) -> str:
    approved = sum(1 for item in candidates if item.get("proposed_status") in {"approved", "locked", "scope_specific"})
    reference = sum(1 for item in candidates if item.get("proposed_status") == "reference")
    rejected = sum(1 for item in candidates if item.get("proposed_status") in {"rejected", "obsolete"})
    unresolved = sum(1 for item in candidates if item.get("blocking_reason"))
    safe = approved > 0 and unresolved == 0
    sources = sorted({artifact for item in candidates for artifact in item.get("source_artifact_references", [])})
    return "\n".join(
        [
            "# Knowledge Pack Quality Report",
            "",
            f"Pack: `{pack.get('pack_id')}`",
            f"Quality level: `{pack.get('quality_level', 'raw')}`",
            f"Status: `{'safe_for_scoped_hard_constraints' if safe else 'review_required'}`",
            "",
            "## Source Artifacts Used",
            *(f"- `{source}`" for source in sources),
            "- none" if not sources else "",
            "",
            "## Counts",
            f"- approved/locked/scope-specific: {approved}",
            f"- reference-only: {reference}",
            f"- rejected/obsolete: {rejected}",
            f"- skipped or unresolved: {len(skipped) or unresolved}",
            f"- review decisions: {len(decisions)}",
            "",
            "## Risks And Limitations",
            "- Raw generated translations are not promoted to reviewed TM without explicit review evidence.",
            "- Limited-scope decisions remain scope-specific and do not create global readiness.",
            "- Stale, rejected, superseded, blocked, failed-QA, and unresolved records are not approved knowledge.",
            "",
            "## Recommended Next Review Actions",
            "- Review `knowledge-review-queue.json` and record explicit approve/lock/reject/defer decisions.",
        ]
    ).replace("\n- none\n\n", "\n- none\n\n")


def _render_style_profile(style_decisions: list[dict[str, Any]], alignment_examples: list[dict[str, Any]]) -> str:
    lines = ["# Style Profile", ""]
    if not style_decisions and not alignment_examples:
        lines.append("No reviewed style or alignment knowledge has been exported yet.")
        return "\n".join(lines) + "\n"
    for item in style_decisions:
        lines.append(f"- {item.get('source_value')}: {item.get('target_value')} (`{item.get('scope')}`)")
    for item in alignment_examples:
        lines.append(f"- Alignment example: {item.get('source_value')} -> {item.get('target_value')} (`{item.get('scope')}`)")
    return "\n".join(lines) + "\n"


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{str(key): str(value or "").strip() for key, value in row.items() if key} for row in csv.DictReader(handle)]


def _read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.is_file() else []


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _safe_pack_id(pack_id: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(pack_id).strip())
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("pack_id must contain at least one safe character")
    return cleaned


def _stable_id(prefix: str, value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _scope_text(value: Any) -> str:
    if isinstance(value, dict):
        if value.get("scope_type"):
            return str(value["scope_type"])
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    text = str(value or "").strip()
    return text or "limited"


def _provenance_summary(source_artifacts: list[str], metadata: dict[str, Any]) -> str:
    ids = [
        str(metadata.get(key))
        for key in ("decision_id", "leadership_review_evidence_id", "evidence_id", "repair_id", "segment_id")
        if metadata.get(key)
    ]
    return ", ".join([*source_artifacts, *ids])


def _document_candidate_type(decision_type: str) -> str:
    if decision_type in {"confirm_alignment_mode", "accept_explanatory_expansion", "reject_explanatory_expansion", "accept_source_omission", "reject_source_omission"}:
        return "alignment_example"
    if decision_type in {"accept_claim_wording", "reject_claim_wording", "confirm_metric_boundary", "accept_publicity_risk", "reject_publicity_risk"}:
        return "claim_pattern"
    return "style_rule"


def _qa_passed(record: dict[str, Any]) -> bool:
    qa = record.get("qa_result") or record.get("qa") or {}
    if isinstance(qa, dict):
        return str(qa.get("status") or "").lower() in {"pass", "passed", "ok"}
    return bool(record.get("qa_passed"))


def _status_rank(status: Any) -> int:
    order = {"locked": 0, "approved": 1, "scope_specific": 2, "reference": 3, "candidate": 4, "rejected": 5, "obsolete": 6}
    return order.get(str(status), 9)
