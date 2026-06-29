from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json, write_jsonl
from .knowledge_consumption import imported_term_rows
from .term_governance import (
    FORBIDDEN_TRANSLATION_COLUMNS,
    HARD_TERM_STATUSES,
    TERM_REGISTRY_COLUMNS,
    write_term_governance_seed,
)


CANDIDATE_TERMS_JSONL = "candidate-terms.jsonl"
TERMBASE_PREFLIGHT_REPORT_JSON = "termbase-preflight-report.json"
TERM_REVIEW_QUEUE_JSON = "term-review-queue.json"
TERM_REVIEW_DECISIONS_JSONL = "term-review-decisions.jsonl"

REVIEW_STATUSES = {
    "candidate",
    "needs_review",
    "approved",
    "locked",
    "rejected",
    "forbidden",
    "deferred",
    "scope_specific",
}
HIGH_RISK_LEVELS = {"high", "critical"}
HIGH_RISK_PRIORITIES = {"review_recommended", "owner_review_required"}

ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9&]{1,}(?:-[A-Z0-9]+)?\b")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)?")
DOCUMENT_PATTERN_RULES = (
    (re.compile(r"\b(?:award|honou?r|certification|certified|accredited)\b", re.IGNORECASE), "award"),
    (re.compile(r"\b(?:ministry|government|university|institute|association|foundation)\b", re.IGNORECASE), "institution"),
    (re.compile(r"\b(?:policy|regulation|compliance|standard|license|licence|terms of service)\b", re.IGNORECASE), "policy_term"),
    (re.compile(r"\b(?:\d+(?:\.\d+)?%|\d+(?:,\d{3})+|\d+(?:\.\d+)?\s?(?:kg|km|m|cm|mm|usd|eur|cny))\b", re.IGNORECASE), "metric"),
)
RESOURCE_SUFFIXES = {
    "title",
    "heading",
    "header",
    "label",
    "button",
    "btn",
    "action",
    "cta",
    "message",
    "msg",
    "text",
    "body",
    "description",
    "summary",
    "detail",
    "subtitle",
    "content",
}
STOP_TERMS = {
    "a",
    "an",
    "and",
    "app",
    "button",
    "cancel",
    "content",
    "description",
    "detail",
    "error",
    "for",
    "label",
    "message",
    "new",
    "ok",
    "save",
    "settings",
    "text",
    "the",
    "title",
}


def run_termbase_preflight(
    state_dir: Path,
    segments: list[dict[str, Any]],
    *,
    source_locale: str,
    target_locale: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    write_term_governance_seed(state_dir)
    decisions_path = state_dir / TERM_REVIEW_DECISIONS_JSONL
    if not decisions_path.exists():
        decisions_path.write_text("", encoding="utf-8")

    candidates = extract_candidate_terms(state_dir, segments, source_locale=source_locale, target_locale=target_locale)
    queue = build_term_review_queue(candidates, source_locale=source_locale, target_locale=target_locale, run_id=run_id)
    report = build_termbase_preflight_report(queue, source_locale=source_locale, target_locale=target_locale, run_id=run_id)

    write_jsonl(state_dir / CANDIDATE_TERMS_JSONL, candidates)
    write_json(state_dir / TERM_REVIEW_QUEUE_JSON, queue)
    write_json(state_dir / TERMBASE_PREFLIGHT_REPORT_JSON, report)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": report["status"],
        "terminology_assurance": report["terminology_assurance"],
        "summary": report["summary"],
        "artifacts": termbase_preflight_asset_paths(state_dir),
    }


def termbase_preflight_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "candidate_terms": CANDIDATE_TERMS_JSONL,
        "termbase_preflight_report": TERMBASE_PREFLIGHT_REPORT_JSON,
        "term_review_queue": TERM_REVIEW_QUEUE_JSON,
        "term_review_decisions": TERM_REVIEW_DECISIONS_JSONL,
    }
    return {key: value for key, value in names.items() if (state_dir / value).exists()}


def extract_candidate_terms(
    state_dir: Path,
    segments: list[dict[str, Any]],
    *,
    source_locale: str,
    target_locale: str,
) -> list[dict[str, Any]]:
    imported_registry, imported_forbidden = imported_term_rows(state_dir)
    registry_rows = [*_read_csv_rows(state_dir / "term-registry.csv"), *imported_registry]
    forbidden_rows = [*_read_csv_rows(state_dir / "forbidden-translations.csv"), *imported_forbidden]
    decision_rows = _read_jsonl_if_exists(state_dir / "term-decisions.jsonl")
    buckets: dict[str, dict[str, Any]] = {}

    repeated_sources: dict[str, list[dict[str, Any]]] = {}
    for segment in segments:
        source = _clean_term(str(segment.get("source", "")))
        if _is_short_phrase(source):
            repeated_sources.setdefault(source.casefold(), []).append(segment)
    for occurrences in repeated_sources.values():
        if len(occurrences) < 2:
            continue
        source = _clean_term(str(occurrences[0].get("source", "")))
        for segment in occurrences:
            _add_candidate(
                buckets,
                source,
                "domain_term",
                source_locale,
                target_locale,
                segment,
                "repeated_short_phrase",
                status="needs_review",
                risk_level="medium",
            )

    for segment in segments:
        source = str(segment.get("source", ""))
        context = segment.get("context", {}) if isinstance(segment.get("context"), dict) else {}
        risk = segment.get("ui_risk_classification", {}) if isinstance(segment.get("ui_risk_classification"), dict) else {}

        resource_phrase = _resource_key_phrase(context)
        if resource_phrase:
            _add_candidate(
                buckets,
                resource_phrase,
                "ui_term",
                source_locale,
                target_locale,
                segment,
                "resource_key",
                risk_level=_risk_level(risk),
                review_priority=_review_priority(risk),
            )

        for acronym in ACRONYM_RE.findall(source):
            _add_candidate(
                buckets,
                acronym,
                "project",
                source_locale,
                target_locale,
                segment,
                "capitalized_acronym",
                risk_level="medium",
            )

        if _is_high_risk(risk) and _is_short_phrase(source):
            _add_candidate(
                buckets,
                source,
                "ui_term",
                source_locale,
                target_locale,
                segment,
                "android_high_risk_ui_term",
                status="needs_review",
                risk_level=_risk_level(risk),
                review_priority=_review_priority(risk),
            )

        if str(context.get("content_type", "")).startswith("word_document"):
            for rule, term_type in DOCUMENT_PATTERN_RULES:
                if rule.search(source):
                    term = _document_term(source, rule)
                    _add_candidate(
                        buckets,
                        term,
                        term_type,
                        source_locale,
                        target_locale,
                        segment,
                        "document_high_risk_pattern",
                        status="needs_review",
                        risk_level="high",
                        review_priority="review_recommended",
                    )

    source_text = "\n".join(str(segment.get("source", "")) for segment in segments)
    for row in registry_rows:
        source_term = str(row.get("source_term", "")).strip()
        if source_term and _term_in_text(source_term, source_text) and _locale_matches(row.get("target_locale", ""), target_locale):
            _add_existing_candidate(buckets, source_term, row.get("type") or "domain_term", source_locale, target_locale, "term_registry")
    for row in forbidden_rows:
        source_term = str(row.get("source_term", "")).strip()
        if source_term and _term_in_text(source_term, source_text) and _locale_matches(row.get("target_locale", ""), target_locale):
            _add_existing_candidate(buckets, source_term, "domain_term", source_locale, target_locale, "forbidden_translations")
    for row in decision_rows:
        source_term = str(row.get("source_term", "")).strip()
        if source_term and _term_in_text(source_term, source_text) and _locale_matches(row.get("target_locale", ""), target_locale):
            _add_existing_candidate(buckets, source_term, row.get("type") or row.get("term_type") or "domain_term", source_locale, target_locale, "term_decisions")

    candidates = []
    for candidate in buckets.values():
        _attach_existing_matches(candidate, registry_rows, decision_rows, forbidden_rows, target_locale)
        _attach_conflicts(candidate)
        candidates.append(candidate)
    candidates.sort(key=lambda item: _candidate_sort_key(item))
    return candidates


def build_term_review_queue(
    candidates: list[dict[str, Any]],
    *,
    source_locale: str,
    target_locale: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    unreviewed = [item for item in candidates if item["status"] in {"candidate", "needs_review"}]
    high_risk = [item for item in unreviewed if item.get("risk_level") in HIGH_RISK_LEVELS]
    conflicts = [conflict for item in candidates for conflict in item.get("conflicts", [])]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-term-review-queue-v1",
        "run_id": run_id,
        "source_locale": source_locale,
        "target_locale": target_locale,
        "status": "blocked_by_conflict" if conflicts else ("review_required" if unreviewed else "reviewed"),
        "decision_artifact": TERM_REVIEW_DECISIONS_JSONL,
        "summary": {
            "candidate_count": len(candidates),
            "review_required_count": len(unreviewed),
            "high_risk_unreviewed_count": len(high_risk),
            "conflict_count": len(conflicts),
        },
        "terms": candidates,
    }


def build_termbase_preflight_report(
    queue: dict[str, Any],
    *,
    source_locale: str,
    target_locale: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    summary = dict(queue.get("summary", {}))
    high_risk = [
        _queue_term_summary(item)
        for item in queue.get("terms", [])
        if item.get("status") in {"candidate", "needs_review"} and item.get("risk_level") in HIGH_RISK_LEVELS
    ]
    conflicts = [conflict for item in queue.get("terms", []) for conflict in item.get("conflicts", [])]
    assurance = "reviewed" if not summary.get("review_required_count") else "incomplete_review_required"
    if conflicts:
        assurance = "blocked_by_conflict"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-termbase-preflight-report-v1",
        "run_id": run_id,
        "source_locale": source_locale,
        "target_locale": target_locale,
        "status": "blocked" if conflicts else ("review_required" if summary.get("review_required_count") else "pass"),
        "terminology_assurance": assurance,
        "summary": summary,
        "unreviewed_high_risk_terms": high_risk,
        "conflicts": conflicts,
        "artifacts": {
            "candidate_terms": CANDIDATE_TERMS_JSONL,
            "term_review_queue": TERM_REVIEW_QUEUE_JSON,
            "term_review_decisions": TERM_REVIEW_DECISIONS_JSONL,
        },
        "limitations": [
            "candidate extraction is deterministic and conservative",
            "incomplete term review must not be treated as full terminology assurance",
        ],
    }


def read_term_review_queue(state_dir: Path) -> dict[str, Any]:
    path = state_dir / TERM_REVIEW_QUEUE_JSON
    if not path.is_file():
        raise ValueError(f"Missing term review queue: {path}")
    return read_json(path)


def record_term_review_decision(state_dir: Path, decision: dict[str, Any]) -> dict[str, Any]:
    write_term_governance_seed(state_dir)
    queue = read_term_review_queue(state_dir)
    normalized = _normalize_review_decision(decision, queue)
    _append_jsonl(state_dir / TERM_REVIEW_DECISIONS_JSONL, normalized)
    _append_term_decision(state_dir, normalized)
    _update_governance_assets(state_dir, normalized)
    _apply_decision_to_queue(queue, normalized)
    report = build_termbase_preflight_report(
        queue,
        source_locale=str(queue.get("source_locale") or normalized.get("source_locale") or ""),
        target_locale=str(queue.get("target_locale") or normalized.get("target_locale") or ""),
        run_id=queue.get("run_id"),
    )
    write_json(state_dir / TERM_REVIEW_QUEUE_JSON, queue)
    write_json(state_dir / TERMBASE_PREFLIGHT_REPORT_JSON, report)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": "pass",
        "decision": normalized,
        "queue": queue,
        "report": report,
        "artifacts": termbase_preflight_asset_paths(state_dir),
    }


def terminology_review_summary(state_dir: Path, segments: list[dict[str, Any]]) -> dict[str, Any]:
    report_path = state_dir / TERMBASE_PREFLIGHT_REPORT_JSON
    queue_path = state_dir / TERM_REVIEW_QUEUE_JSON
    if not report_path.is_file() or not queue_path.is_file():
        return {
            "status": "not_run",
            "terminology_assurance": "not_checked",
            "queue": None,
            "unreviewed_high_risk_terms": [],
        }
    report = read_json(report_path)
    queue = read_json(queue_path)
    source_text = "\n".join(str(segment.get("source", "")) for segment in segments)
    high_risk = [
        _queue_term_summary(item)
        for item in queue.get("terms", [])
        if item.get("status") in {"candidate", "needs_review"}
        and item.get("risk_level") in HIGH_RISK_LEVELS
        and _term_in_text(str(item.get("source_term", "")), source_text)
    ]
    return {
        "status": report.get("status", "not_checked"),
        "terminology_assurance": report.get("terminology_assurance", "not_checked"),
        "queue": TERM_REVIEW_QUEUE_JSON,
        "review_required_count": report.get("summary", {}).get("review_required_count", 0),
        "high_risk_unreviewed_count": report.get("summary", {}).get("high_risk_unreviewed_count", 0),
        "unreviewed_high_risk_terms": high_risk[:20],
    }


def _add_candidate(
    buckets: dict[str, dict[str, Any]],
    source_term: str,
    term_type: str,
    source_locale: str,
    target_locale: str,
    segment: dict[str, Any],
    evidence_type: str,
    *,
    status: str = "candidate",
    risk_level: str = "low",
    review_priority: str = "normal",
) -> None:
    source_term = _clean_term(source_term)
    if not _is_reviewable_term(source_term):
        return
    key = source_term.casefold()
    candidate = buckets.setdefault(
        key,
        {
            "protocol_version": PROTOCOL_VERSION,
            "schema": "localize-anything-candidate-term-v1",
            "candidate_id": _candidate_id(source_term, target_locale),
            "source_term": source_term,
            "target_term": "",
            "term_type": term_type,
            "status": status,
            "risk_level": risk_level,
            "review_priority": review_priority,
            "source_locale": source_locale,
            "target_locale": target_locale,
            "occurrence_count": 0,
            "occurrences": [],
            "evidence": [],
            "matches": {
                "term_registry": [],
                "term_decisions": [],
                "forbidden_translations": [],
            },
            "conflicts": [],
            "suggested_action": "review_in_workbench",
        },
    )
    candidate["term_type"] = _stronger_term_type(str(candidate.get("term_type", "")), term_type)
    candidate["risk_level"] = _stronger_risk(str(candidate.get("risk_level", "")), risk_level)
    candidate["review_priority"] = _stronger_priority(str(candidate.get("review_priority", "")), review_priority)
    if candidate["status"] == "candidate" and (candidate["risk_level"] in HIGH_RISK_LEVELS or candidate["review_priority"] in HIGH_RISK_PRIORITIES):
        candidate["status"] = "needs_review"
    if status == "needs_review" and candidate["status"] == "candidate":
        candidate["status"] = "needs_review"
    _append_unique(candidate["occurrences"], _occurrence(segment))
    _append_unique(candidate["evidence"], _evidence(evidence_type, segment))
    candidate["occurrence_count"] = len(candidate["occurrences"])


def _add_existing_candidate(
    buckets: dict[str, dict[str, Any]],
    source_term: str,
    term_type: str,
    source_locale: str,
    target_locale: str,
    evidence_type: str,
) -> None:
    source_term = _clean_term(source_term)
    if not _is_reviewable_term(source_term):
        return
    key = source_term.casefold()
    candidate = buckets.setdefault(
        key,
        {
            "protocol_version": PROTOCOL_VERSION,
            "schema": "localize-anything-candidate-term-v1",
            "candidate_id": _candidate_id(source_term, target_locale),
            "source_term": source_term,
            "target_term": "",
            "term_type": term_type,
            "status": "candidate",
            "risk_level": "medium",
            "review_priority": "review_recommended",
            "source_locale": source_locale,
            "target_locale": target_locale,
            "occurrence_count": 0,
            "occurrences": [],
            "evidence": [],
            "matches": {
                "term_registry": [],
                "term_decisions": [],
                "forbidden_translations": [],
            },
            "conflicts": [],
            "suggested_action": "review_existing_termbase_match",
        },
    )
    _append_unique(candidate["evidence"], {"type": evidence_type})


def _attach_existing_matches(
    candidate: dict[str, Any],
    registry_rows: list[dict[str, str]],
    decision_rows: list[dict[str, Any]],
    forbidden_rows: list[dict[str, str]],
    target_locale: str,
) -> None:
    source_term = str(candidate["source_term"])
    registry_matches = [
        _registry_match(row)
        for row in registry_rows
        if _same_term(row.get("source_term", ""), source_term) and _locale_matches(row.get("target_locale", ""), target_locale)
    ]
    decision_matches = [
        _decision_match(row)
        for row in decision_rows
        if _same_term(row.get("source_term", ""), source_term) and _locale_matches(row.get("target_locale", ""), target_locale)
    ]
    forbidden_matches = [
        _forbidden_match(row)
        for row in forbidden_rows
        if _same_term(row.get("source_term", ""), source_term) and _locale_matches(row.get("target_locale", ""), target_locale)
    ]
    candidate["matches"] = {
        "term_registry": registry_matches,
        "term_decisions": decision_matches,
        "forbidden_translations": forbidden_matches,
    }
    hard_registry = [item for item in registry_matches if item.get("status") in HARD_TERM_STATUSES and item.get("target_term")]
    hard_decisions = [item for item in decision_matches if item.get("status") in HARD_TERM_STATUSES and item.get("target_term")]
    if hard_registry:
        candidate["status"] = str(hard_registry[0]["status"])
        candidate["target_term"] = str(hard_registry[0]["target_term"])
        candidate["suggested_action"] = "already_available_for_hard_constraints"
    elif hard_decisions:
        candidate["status"] = str(hard_decisions[0]["status"])
        candidate["target_term"] = str(hard_decisions[0]["target_term"])
        candidate["suggested_action"] = "sync_decision_to_term_registry"
    elif forbidden_matches:
        candidate["status"] = "forbidden"
        candidate["suggested_action"] = "avoid_forbidden_translation"


def _attach_conflicts(candidate: dict[str, Any]) -> None:
    matches = candidate.get("matches", {})
    registry = [item for item in matches.get("term_registry", []) if item.get("status") in HARD_TERM_STATUSES]
    targets = sorted({str(item.get("target_term", "")).strip() for item in registry if item.get("target_term")})
    if len(targets) > 1:
        candidate["conflicts"].append(
            {
                "type": "multiple_approved_targets",
                "source_term": candidate["source_term"],
                "target_terms": targets,
                "severity": "blocking",
            }
        )
        candidate["status"] = "needs_review"
        candidate["suggested_action"] = "resolve_term_conflict"
    forbidden_targets = {
        str(item.get("forbidden_target", "")).strip()
        for item in matches.get("forbidden_translations", [])
        if item.get("forbidden_target")
    }
    for target in targets:
        if target in forbidden_targets:
            candidate["conflicts"].append(
                {
                    "type": "approved_target_is_forbidden",
                    "source_term": candidate["source_term"],
                    "target_term": target,
                    "severity": "blocking",
                }
            )
            candidate["status"] = "needs_review"
            candidate["suggested_action"] = "resolve_term_conflict"


def _normalize_review_decision(decision: dict[str, Any], queue: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(decision.get("candidate_id") or "").strip()
    by_id = {str(item.get("candidate_id")): item for item in queue.get("terms", [])}
    candidate = by_id.get(candidate_id, {}) if candidate_id else {}
    source_term = str(decision.get("source_term") or candidate.get("source_term") or "").strip()
    status = str(decision.get("status") or "").strip()
    if status not in REVIEW_STATUSES - {"candidate", "needs_review"}:
        raise ValueError(f"Unsupported term review decision status: {status}")
    target_term = str(decision.get("target_term") or "").strip()
    if status in {"approved", "locked", "scope_specific"} and not target_term:
        raise ValueError(f"{status} term decisions require target_term")
    if not source_term:
        raise ValueError("source_term is required")
    target_locale = str(decision.get("target_locale") or queue.get("target_locale") or candidate.get("target_locale") or "").strip()
    if not target_locale:
        raise ValueError("target_locale is required")
    now = datetime.now(UTC).isoformat()
    forbidden_targets = [str(item).strip() for item in decision.get("forbidden_targets", []) if str(item).strip()]
    normalized = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-term-review-decision-v1",
        "candidate_id": candidate_id or _candidate_id(source_term, target_locale),
        "source_term": source_term,
        "target_term": target_term,
        "term_type": str(decision.get("term_type") or candidate.get("term_type") or "other"),
        "status": status,
        "source_locale": str(decision.get("source_locale") or queue.get("source_locale") or candidate.get("source_locale") or ""),
        "target_locale": target_locale,
        "scope": str(decision.get("scope") or candidate.get("scope") or ""),
        "notes": str(decision.get("notes") or ""),
        "forbidden_targets": forbidden_targets,
        "decided_by": str(decision.get("decided_by") or "workbench-user"),
        "decided_at": str(decision.get("decided_at") or now),
        "provenance": [
            {
                "type": "term_review_queue",
                "candidate_id": candidate_id or _candidate_id(source_term, target_locale),
            }
        ],
    }
    return normalized


def _append_term_decision(state_dir: Path, decision: dict[str, Any]) -> None:
    if decision["status"] == "forbidden":
        return
    target_term = decision.get("target_term", "")
    if not target_term:
        return
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "source_term": decision["source_term"],
        "target_term": target_term or "",
        "type": decision["term_type"],
        "status": decision["status"],
        "priority": "user_confirmed",
        "scope": decision.get("scope", ""),
        "forbidden_targets": decision.get("forbidden_targets", []),
        "notes": decision.get("notes", ""),
        "source_locale": decision.get("source_locale", ""),
        "target_locale": decision.get("target_locale", ""),
        "provenance": decision.get("provenance", []),
    }
    _append_jsonl(state_dir / "term-decisions.jsonl", record)


def _update_governance_assets(state_dir: Path, decision: dict[str, Any]) -> None:
    if decision["status"] in {"approved", "locked", "scope_specific"}:
        _upsert_term_registry_row(state_dir / "term-registry.csv", decision)
    if decision["status"] == "forbidden":
        targets = decision.get("forbidden_targets") or ([decision["target_term"]] if decision.get("target_term") else [])
        for target in targets:
            _append_forbidden_row(state_dir / "forbidden-translations.csv", decision, str(target))
    for target in decision.get("forbidden_targets", []):
        _append_forbidden_row(state_dir / "forbidden-translations.csv", decision, str(target))


def _apply_decision_to_queue(queue: dict[str, Any], decision: dict[str, Any]) -> None:
    for item in queue.get("terms", []):
        if item.get("candidate_id") != decision["candidate_id"] and not _same_term(item.get("source_term", ""), decision["source_term"]):
            continue
        item["status"] = decision["status"]
        item["target_term"] = decision.get("target_term", "")
        item["scope"] = decision.get("scope", "")
        item["review_decision"] = {
            "decided_by": decision.get("decided_by", ""),
            "decided_at": decision.get("decided_at", ""),
            "notes": decision.get("notes", ""),
        }
    terms = queue.get("terms", [])
    unreviewed = [item for item in terms if item.get("status") in {"candidate", "needs_review"}]
    high_risk = [item for item in unreviewed if item.get("risk_level") in HIGH_RISK_LEVELS]
    conflicts = [conflict for item in terms for conflict in item.get("conflicts", [])]
    queue["status"] = "blocked_by_conflict" if conflicts else ("review_required" if unreviewed else "reviewed")
    queue["summary"] = {
        "candidate_count": len(terms),
        "review_required_count": len(unreviewed),
        "high_risk_unreviewed_count": len(high_risk),
        "conflict_count": len(conflicts),
    }


def _upsert_term_registry_row(path: Path, decision: dict[str, Any]) -> None:
    rows = _read_csv_rows(path)
    key = (decision["source_term"].casefold(), decision["target_locale"], decision.get("scope", ""))
    updated = False
    for row in rows:
        row_key = (row.get("source_term", "").casefold(), row.get("target_locale", ""), row.get("scope", ""))
        if row_key != key:
            continue
        row.update(_registry_row_from_decision(decision))
        updated = True
        break
    if not updated:
        rows.append(_registry_row_from_decision(decision))
    _write_csv_rows(path, TERM_REGISTRY_COLUMNS, rows)


def _append_forbidden_row(path: Path, decision: dict[str, Any], forbidden_target: str) -> None:
    rows = _read_csv_rows(path)
    row = {
        "source_term": decision["source_term"],
        "forbidden_target": forbidden_target,
        "target_locale": decision["target_locale"],
        "scope": decision.get("scope", ""),
        "reason": decision.get("notes", "") or "term_review_decision",
        "status": "rejected" if decision["status"] != "forbidden" else "approved",
        "provenance": json.dumps(decision.get("provenance", []), ensure_ascii=False),
    }
    duplicate_key = (row["source_term"].casefold(), row["forbidden_target"].casefold(), row["target_locale"], row["scope"])
    if not any(
        (item.get("source_term", "").casefold(), item.get("forbidden_target", "").casefold(), item.get("target_locale", ""), item.get("scope", ""))
        == duplicate_key
        for item in rows
    ):
        rows.append(row)
    _write_csv_rows(path, FORBIDDEN_TRANSLATION_COLUMNS, rows)


def _registry_row_from_decision(decision: dict[str, Any]) -> dict[str, str]:
    return {
        "source_term": decision["source_term"],
        "target_term": decision["target_term"],
        "type": decision["term_type"],
        "status": decision["status"],
        "priority": "user_confirmed",
        "scope": decision.get("scope", ""),
        "notes": decision.get("notes", ""),
        "source_locale": decision.get("source_locale", ""),
        "target_locale": decision.get("target_locale", ""),
        "forbidden_targets": "|".join(decision.get("forbidden_targets", [])),
        "provenance": json.dumps(decision.get("provenance", []), ensure_ascii=False),
    }


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [
            {str(key): str(value or "").strip() for key, value in row.items() if key}
            for row in csv.DictReader(handle)
        ]


def _write_csv_rows(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.exists() and path.read_text(encoding="utf-8").strip() else []


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _clean_term(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip(" \t\r\n:;,.!?()[]{}\"'")).strip()


def _is_reviewable_term(value: str) -> bool:
    folded = value.casefold()
    if not value or folded in STOP_TERMS:
        return False
    if len(value) < 2 or len(value) > 96:
        return False
    if value.isdigit():
        return False
    if "{" in value or "}" in value:
        return False
    words = WORD_RE.findall(value)
    return bool(words) and len(words) <= 8


def _is_short_phrase(value: str) -> bool:
    words = WORD_RE.findall(value)
    return 1 <= len(words) <= 5 and len(value) <= 72


def _term_in_text(term: str, text: str) -> bool:
    if not term:
        return False
    return term.casefold() in text.casefold()


def _resource_key_phrase(context: dict[str, Any]) -> str:
    raw = str(context.get("resource_name") or context.get("resource_key") or "").strip()
    if not raw:
        return ""
    raw = raw.rsplit("#", 1)[0].replace(".", "_").replace("-", "_")
    parts = [part for part in re.split(r"_+", _split_camel(raw)) if part]
    while parts and parts[-1].casefold() in RESOURCE_SUFFIXES:
        parts.pop()
    words = [part for part in parts if part.casefold() not in STOP_TERMS]
    if not words:
        return ""
    return " ".join(word.capitalize() if word.islower() else word for word in words[:5])


def _split_camel(value: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)


def _document_term(source: str, rule: re.Pattern[str]) -> str:
    match = rule.search(source)
    if not match:
        return _clean_term(source)
    words = WORD_RE.findall(source)
    if len(words) <= 6:
        return _clean_term(source)
    matched = match.group(0)
    for index, word in enumerate(words):
        if word.casefold() == matched.casefold():
            start = max(0, index - 2)
            end = min(len(words), index + 4)
            return _clean_term(" ".join(words[start:end]))
    return _clean_term(matched)


def _risk_level(risk: dict[str, Any]) -> str:
    value = str(risk.get("risk_level") or "low")
    return value if value in {"low", "medium", "high", "critical"} else "low"


def _review_priority(risk: dict[str, Any]) -> str:
    value = str(risk.get("review_priority") or "normal")
    return value if value in {"normal", "review_recommended", "owner_review_required"} else "normal"


def _is_high_risk(risk: dict[str, Any]) -> bool:
    return _risk_level(risk) in HIGH_RISK_LEVELS or _review_priority(risk) in HIGH_RISK_PRIORITIES


def _occurrence(segment: dict[str, Any]) -> dict[str, Any]:
    context = segment.get("context", {}) if isinstance(segment.get("context"), dict) else {}
    item = {
        "segment_id": str(segment.get("segment_id", "")),
        "source_path": str(segment.get("source_path", "")),
        "source": str(segment.get("source", ""))[:240],
    }
    for key in ("resource_key", "resource_name", "content_type", "json_pointer"):
        if context.get(key) is not None:
            item[key] = str(context[key])
    return item


def _evidence(evidence_type: str, segment: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": evidence_type,
        "segment_id": str(segment.get("segment_id", "")),
        "source_path": str(segment.get("source_path", "")),
    }


def _append_unique(items: list[dict[str, Any]], item: dict[str, Any]) -> None:
    encoded = json.dumps(item, sort_keys=True, ensure_ascii=False)
    if all(json.dumps(existing, sort_keys=True, ensure_ascii=False) != encoded for existing in items):
        items.append(item)


def _candidate_id(source_term: str, target_locale: str) -> str:
    digest = hashlib.sha256(f"{source_term.casefold()}\0{target_locale}".encode("utf-8")).hexdigest()[:16]
    return f"termcand-{digest}"


def _candidate_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    status_rank = {"needs_review": 0, "candidate": 1, "forbidden": 2, "locked": 3, "approved": 4}.get(str(item.get("status", "")), 9)
    risk_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(str(item.get("risk_level", "")), 9)
    return (status_rank, risk_rank, str(item.get("source_term", "")).casefold())


def _stronger_risk(current: str, new: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    return new if order.get(new, 0) > order.get(current, 0) else current


def _stronger_priority(current: str, new: str) -> str:
    order = {"normal": 0, "review_recommended": 1, "owner_review_required": 2}
    return new if order.get(new, 0) > order.get(current, 0) else current


def _stronger_term_type(current: str, new: str) -> str:
    order = ["other", "domain_term", "style_term", "project", "mechanism", "metric", "institution", "award", "policy_term", "ui_term"]
    if current not in order:
        return new
    if new not in order:
        return current
    return new if order.index(new) > order.index(current) else current


def _registry_match(row: dict[str, str]) -> dict[str, str]:
    return {
        "source_term": row.get("source_term", ""),
        "target_term": row.get("target_term", ""),
        "type": row.get("type", ""),
        "status": row.get("status", ""),
        "priority": row.get("priority", ""),
        "scope": row.get("scope", ""),
        "target_locale": row.get("target_locale", ""),
    }


def _decision_match(row: dict[str, Any]) -> dict[str, str]:
    return {
        "source_term": str(row.get("source_term", "")),
        "target_term": str(row.get("target_term", "")),
        "type": str(row.get("type") or row.get("term_type") or ""),
        "status": str(row.get("status", "")),
        "scope": str(row.get("scope", "")),
        "target_locale": str(row.get("target_locale", "")),
    }


def _forbidden_match(row: dict[str, str]) -> dict[str, str]:
    return {
        "source_term": row.get("source_term", ""),
        "forbidden_target": row.get("forbidden_target", ""),
        "target_locale": row.get("target_locale", ""),
        "scope": row.get("scope", ""),
        "reason": row.get("reason", ""),
        "status": row.get("status", ""),
    }


def _same_term(left: Any, right: Any) -> bool:
    return str(left or "").casefold() == str(right or "").casefold()


def _locale_matches(value: Any, target_locale: str) -> bool:
    locale = str(value or "").strip()
    return locale in {"", target_locale}


def _queue_term_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": item.get("candidate_id"),
        "source_term": item.get("source_term"),
        "term_type": item.get("term_type"),
        "risk_level": item.get("risk_level"),
        "review_priority": item.get("review_priority"),
        "occurrence_count": item.get("occurrence_count", 0),
        "status": item.get("status"),
    }
