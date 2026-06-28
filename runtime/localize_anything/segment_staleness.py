from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, sha256_file, write_json, write_jsonl


STALE_SEGMENTS_JSONL = "stale-segments.jsonl"
REUSE_DECISION_JSON = "reuse-decision.json"

SOURCE_CHANGED = "stale_source_changed"
CONTEXT_CHANGED = "stale_context_changed"
TERM_POLICY_CHANGED = "stale_term_policy_changed"
STRATEGY_CHANGED = "stale_generation_strategy_changed"
PROVIDER_POLICY_CHANGED = "stale_provider_policy_changed"
NEEDS_REGENERATION = "needs_regeneration"
NEEDS_RE_REVIEW = "needs_re_review"
REUSABLE = "reusable"
CURRENT = "current"
BLOCKED = "blocked"

TERM_POLICY_FILES = ("term-registry.csv", "term-decisions.jsonl", "forbidden-translations.csv")
TERM_REVIEW_DECISION_FILE = "term-review-decisions.jsonl"


def build_reuse_decision(
    state_dir: Path,
    current_segments: list[dict[str, Any]],
    *,
    previous_segments: list[dict[str, Any]] | None = None,
    generated_segments: list[dict[str, Any]] | None = None,
    review_result_path: Path | None = None,
    provider_policy: dict[str, Any] | None = None,
    review_policy: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    previous_records = _previous_segment_records(state_dir, previous_segments)
    generated_by_id = _by_segment_id(generated_segments or [], "generated")
    dependency_hashes = _global_dependency_hashes(state_dir, provider_policy, review_policy, review_result_path)
    known_terms = _known_terms(state_dir)

    records = [
        _segment_record(segment, previous_records.get(str(segment.get("segment_id"))), generated_by_id, dependency_hashes, known_terms)
        for segment in current_segments
    ]
    summary = _summary(records)
    decisions = _decisions(summary)
    decision = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-reuse-decision-v1",
        "run_id": run_id,
        "status": _status(summary),
        "stale_segments_path": STALE_SEGMENTS_JSONL,
        "summary": summary,
        "decisions": decisions,
        "quality_claims_forbidden": _forbidden_claims(decisions),
        "source_artifacts": segment_staleness_asset_paths(state_dir),
        "segments": records,
        "next_actions": _next_actions(summary),
    }
    if write:
        state_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(state_dir / STALE_SEGMENTS_JSONL, records)
        write_json(state_dir / REUSE_DECISION_JSON, decision)
    return decision


def read_stale_segments(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / STALE_SEGMENTS_JSONL
    if not path.is_file():
        raise ValueError(f"Missing stale segments artifact: {path}")
    return read_jsonl(path)


def read_reuse_decision(state_dir: Path) -> dict[str, Any]:
    path = state_dir / REUSE_DECISION_JSON
    if not path.is_file():
        raise ValueError(f"Missing reuse decision artifact: {path}")
    return read_json(path)


def segment_staleness_asset_paths(state_dir: Path) -> dict[str, str]:
    names = {
        "stale_segments": STALE_SEGMENTS_JSONL,
        "reuse_decision": REUSE_DECISION_JSON,
    }
    return {key: value for key, value in names.items() if (state_dir / value).is_file()}


def segment_staleness_summary(state_dir: Path) -> dict[str, Any]:
    decision_path = state_dir / REUSE_DECISION_JSON
    if not decision_path.is_file():
        return {
            "status": "not_run",
            "artifact": None,
            "summary": {},
            "decisions": {},
            "stale_segments": [],
            "next_actions": [],
        }
    decision = read_json(decision_path)
    segments = decision.get("segments", [])
    stale_segments = [
        _compact_segment(item)
        for item in segments
        if item.get("state") in {NEEDS_REGENERATION, NEEDS_RE_REVIEW, BLOCKED}
        or any(str(value).startswith("stale_") for value in item.get("classifications", []))
    ]
    return {
        "status": decision.get("status", "not_checked"),
        "artifact": REUSE_DECISION_JSON,
        "stale_segments_artifact": STALE_SEGMENTS_JSONL if (state_dir / STALE_SEGMENTS_JSONL).is_file() else None,
        "summary": decision.get("summary", {}),
        "decisions": decision.get("decisions", {}),
        "quality_claims_forbidden": decision.get("quality_claims_forbidden", []),
        "stale_segments": stale_segments[:50],
        "next_actions": decision.get("next_actions", []),
    }


def _segment_record(
    segment: dict[str, Any],
    previous: dict[str, Any] | None,
    generated_by_id: dict[str, dict[str, Any]],
    dependency_hashes: dict[str, str | None],
    known_terms: set[str],
) -> dict[str, Any]:
    segment_id = str(segment.get("segment_id") or "")
    if not segment_id:
        raise ValueError("current segment lacks segment_id")
    generated = generated_by_id.get(segment_id, {})
    dependencies = _segment_dependencies(segment, generated, dependency_hashes)
    matched_terms = sorted(term for term in known_terms if _term_in_text(term, str(segment.get("source", ""))))
    classifications, reasons, requires_qa, targeted_repair_allowed = _classify_segment(
        segment,
        previous,
        dependencies,
        bool(_target_value(generated) is not None),
        matched_terms,
    )
    state = _primary_state(classifications)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-stale-segments-v1",
        "segment_id": segment_id,
        "resource_key": _resource_key(segment),
        "source_path": segment.get("source_path"),
        "source_text_hash": dependencies["source_text_hash"],
        "source_context_hash": dependencies["source_context_hash"],
        "placeholder_signature_hash": dependencies["placeholder_signature_hash"],
        "dependency_hashes": dependencies,
        "matched_terms": matched_terms,
        "classifications": classifications,
        "state": state,
        "reuse_allowed": state == REUSABLE,
        "action": _action_for_state(state),
        "reason_codes": reasons,
        "targeted_repair_allowed": targeted_repair_allowed,
        "deterministic_qa_required": requires_qa,
        "review_required": state == NEEDS_RE_REVIEW or _is_high_risk(segment),
        "high_risk": _is_high_risk(segment),
        "blocks_generation_handoff": state in {NEEDS_REGENERATION, BLOCKED},
        "blocks_delivery_apply": state in {NEEDS_REGENERATION, BLOCKED},
    }


def _classify_segment(
    segment: dict[str, Any],
    previous: dict[str, Any] | None,
    dependencies: dict[str, str | None],
    has_generated_target: bool,
    matched_terms: list[str],
) -> tuple[list[str], list[str], bool, bool]:
    classifications: list[str] = []
    reasons: list[str] = []
    requires_qa = False
    targeted_repair_allowed = False
    previous_deps = previous.get("dependency_hashes", {}) if previous else {}
    previous_matched_terms = set(previous.get("matched_terms", []) if previous else [])

    if previous and previous_deps.get("source_text_hash") != dependencies.get("source_text_hash"):
        classifications.extend([SOURCE_CHANGED, NEEDS_REGENERATION])
        reasons.append("source_text_changed")
    elif previous and previous_deps.get("placeholder_signature_hash") != dependencies.get("placeholder_signature_hash"):
        classifications.extend([CONTEXT_CHANGED, NEEDS_REGENERATION])
        reasons.append("placeholder_or_markup_signature_changed")
        requires_qa = True
    else:
        if previous and previous_deps.get("source_context_hash") != dependencies.get("source_context_hash"):
            classifications.extend([CONTEXT_CHANGED, NEEDS_RE_REVIEW])
            reasons.append("source_context_changed")
        term_policy_changed = _changed(previous_deps, dependencies, "term_governance_hash") or _changed(
            previous_deps, dependencies, "term_review_decision_hash"
        )
        if term_policy_changed and (matched_terms or previous_matched_terms):
            classifications.extend([TERM_POLICY_CHANGED, NEEDS_REGENERATION])
            reasons.append("term_policy_changed_for_matching_segment")
            targeted_repair_allowed = True
        if _changed(previous_deps, dependencies, "generation_strategy_hash"):
            classifications.extend([STRATEGY_CHANGED, NEEDS_RE_REVIEW])
            reasons.append("generation_strategy_changed")
        if _changed(previous_deps, dependencies, "provider_policy_hash"):
            classifications.extend([PROVIDER_POLICY_CHANGED, NEEDS_RE_REVIEW])
            reasons.append("provider_policy_changed")
        if _changed(previous_deps, dependencies, "review_policy_hash"):
            classifications.append(NEEDS_RE_REVIEW)
            reasons.append("review_policy_changed")

    if not has_generated_target:
        classifications.append(NEEDS_REGENERATION)
        reasons.append("no_previous_generated_target")
    if _is_high_risk(segment) and any(reason.endswith("_changed") or "policy_changed" in reason for reason in reasons):
        classifications.append(NEEDS_RE_REVIEW)
        reasons.append("high_risk_policy_change_requires_review")
    if not classifications:
        classifications.extend([CURRENT, REUSABLE])
        reasons.append("segment_dependencies_current")
    return _dedupe(classifications), _dedupe(reasons), requires_qa or SOURCE_CHANGED in classifications, targeted_repair_allowed


def _segment_dependencies(
    segment: dict[str, Any],
    generated: dict[str, Any],
    dependency_hashes: dict[str, str | None],
) -> dict[str, str | None]:
    dependencies = {
        "segment_id": str(segment.get("segment_id") or ""),
        "resource_key": _resource_key(segment),
        "source_text_hash": _hash_text(str(segment.get("source", ""))),
        "source_context_hash": _stable_hash({"source_path": segment.get("source_path"), "context": segment.get("context", {})}),
        "placeholder_signature_hash": _stable_hash(_placeholder_signature(segment)),
        "previous_generated_target_hash": _hash_target(_target_value(generated)),
    }
    dependencies.update(dependency_hashes)
    return dependencies


def _global_dependency_hashes(
    state_dir: Path,
    provider_policy: dict[str, Any] | None,
    review_policy: dict[str, Any] | None,
    review_result_path: Path | None,
) -> dict[str, str | None]:
    return {
        "localization_brief_hash": _combined_file_hash(state_dir, ("localization-brief.json", "localization-brief.yaml")),
        "term_governance_hash": _combined_file_hash(state_dir, TERM_POLICY_FILES),
        "term_review_decision_hash": _file_hash(state_dir / TERM_REVIEW_DECISION_FILE),
        "generation_strategy_hash": _file_hash(state_dir / "generation-strategy.json"),
        "provider_policy_hash": _stable_hash(provider_policy) if provider_policy is not None else None,
        "previous_review_result_hash": _file_hash(review_result_path) if review_result_path else None,
        "review_policy_hash": _stable_hash(review_policy) if review_policy is not None else None,
    }


def _previous_segment_records(state_dir: Path, previous_segments: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    decision_path = state_dir / REUSE_DECISION_JSON
    if decision_path.is_file():
        decision = read_json(decision_path)
        return {
            str(item.get("segment_id")): item
            for item in decision.get("segments", [])
            if isinstance(item, dict) and item.get("segment_id")
        }
    return {
        str(segment.get("segment_id")): {
            "segment_id": segment.get("segment_id"),
            "dependency_hashes": {
                "source_text_hash": _hash_text(str(segment.get("source", ""))),
                "source_context_hash": _stable_hash({"source_path": segment.get("source_path"), "context": segment.get("context", {})}),
                "placeholder_signature_hash": _stable_hash(_placeholder_signature(segment)),
            },
            "matched_terms": [],
        }
        for segment in previous_segments or []
        if segment.get("segment_id")
    }


def _summary(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "segment_count": len(records),
        "current_count": _count_state(records, CURRENT),
        "reusable_count": _count_state(records, REUSABLE),
        "stale_segment_count": sum(any(str(value).startswith("stale_") for value in item["classifications"]) for item in records),
        "needs_regeneration_count": _count_state(records, NEEDS_REGENERATION),
        "needs_re_review_count": _count_state(records, NEEDS_RE_REVIEW),
        "blocked_count": _count_state(records, BLOCKED),
        "deterministic_qa_required_count": sum(bool(item.get("deterministic_qa_required")) for item in records),
        "high_risk_review_required_count": sum(bool(item.get("high_risk") and item.get("review_required")) for item in records),
        "delivery_apply_blocking_count": sum(bool(item.get("blocks_delivery_apply")) for item in records),
        "generation_handoff_blocking_count": sum(bool(item.get("blocks_generation_handoff")) for item in records),
    }


def _decisions(summary: dict[str, int]) -> dict[str, Any]:
    handoff_blocked = summary.get("generation_handoff_blocking_count", 0) > 0
    apply_blocked = summary.get("delivery_apply_blocking_count", 0) > 0
    review_required = summary.get("needs_re_review_count", 0) > 0
    return {
        "reuse_allowed": not handoff_blocked and not apply_blocked and not review_required,
        "generation_handoff_policy": "blocked" if handoff_blocked else "warn" if review_required else "allowed",
        "delivery_apply_policy": "blocked" if apply_blocked else "warn" if review_required else "allowed",
        "requires_deterministic_qa": summary.get("deterministic_qa_required_count", 0) > 0,
        "review_required": review_required,
    }


def _status(summary: dict[str, int]) -> str:
    if summary.get("blocked_count", 0):
        return "blocked"
    if summary.get("needs_regeneration_count", 0):
        return "requires_regeneration"
    if summary.get("needs_re_review_count", 0):
        return "requires_review"
    return "ready"


def _next_actions(summary: dict[str, int]) -> list[str]:
    actions: list[str] = []
    if summary.get("needs_regeneration_count", 0):
        actions.append("Regenerate or targeted-repair stale segments before claiming full-quality generation or applying staged files.")
    if summary.get("needs_re_review_count", 0):
        actions.append("Re-review affected segments before claiming review-complete status.")
    if summary.get("deterministic_qa_required_count", 0):
        actions.append("Run deterministic QA for regenerated segments with changed placeholders or markup.")
    return actions


def _forbidden_claims(decisions: dict[str, Any]) -> list[str]:
    claims: set[str] = set()
    if decisions.get("generation_handoff_policy") in {"blocked", "warn"}:
        claims.add("full_quality_generation")
    if decisions.get("delivery_apply_policy") == "blocked":
        claims.add("safe_apply_readiness")
    if decisions.get("review_required"):
        claims.add("review_complete_status")
    return sorted(claims)


def _known_terms(state_dir: Path) -> set[str]:
    terms: set[str] = set()
    for row in _read_csv_rows(state_dir / "term-registry.csv"):
        _add_term(terms, row.get("source_term"))
    for row in _read_csv_rows(state_dir / "forbidden-translations.csv"):
        _add_term(terms, row.get("source_term"))
    for path in (state_dir / "term-decisions.jsonl", state_dir / TERM_REVIEW_DECISION_FILE):
        for row in _read_jsonl_if_exists(path):
            _add_term(terms, row.get("source_term"))
    return terms


def _add_term(terms: set[str], value: Any) -> None:
    text = str(value or "").strip()
    if text:
        terms.add(text)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [
            {str(key): str(value or "").strip() for key, value in row.items() if key}
            for row in csv.DictReader(handle)
        ]


def _read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.is_file() else []


def _by_segment_id(segments: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for segment in segments:
        segment_id = segment.get("segment_id")
        if not isinstance(segment_id, str) or not segment_id:
            raise ValueError(f"{label} segment lacks segment_id")
        result[segment_id] = segment
    return result


def _primary_state(classifications: list[str]) -> str:
    if BLOCKED in classifications:
        return BLOCKED
    if NEEDS_REGENERATION in classifications:
        return NEEDS_REGENERATION
    if NEEDS_RE_REVIEW in classifications:
        return NEEDS_RE_REVIEW
    return REUSABLE


def _action_for_state(state: str) -> str:
    return {
        NEEDS_REGENERATION: "regenerate_or_targeted_repair",
        NEEDS_RE_REVIEW: "re_review",
        BLOCKED: "blocked",
        REUSABLE: "reuse",
    }.get(state, "reuse")


def _count_state(records: list[dict[str, Any]], state: str) -> int:
    if state == CURRENT:
        return sum(CURRENT in item.get("classifications", []) for item in records)
    return sum(item.get("state") == state or state in item.get("classifications", []) for item in records)


def _changed(previous: dict[str, Any], current: dict[str, Any], key: str) -> bool:
    return bool(previous) and previous.get(key) != current.get(key)


def _placeholder_signature(segment: dict[str, Any]) -> dict[str, Any]:
    constraints = segment.get("constraints", {})
    return {
        "placeholders": constraints.get("placeholders", []),
        "markup": constraints.get("markup", []),
        "markup_signature": constraints.get("markup_signature", []),
        "escape_signature": constraints.get("escape_signature", []),
        "cdata": constraints.get("cdata", False),
    }


def _target_value(segment: dict[str, Any]) -> Any:
    if "target" in segment:
        return segment.get("target")
    if "target_plural" in segment:
        return segment.get("target_plural")
    return None


def _hash_target(value: Any) -> str | None:
    return _stable_hash(value) if value is not None else None


def _resource_key(segment: dict[str, Any]) -> str | None:
    value = segment.get("context", {}).get("resource_key")
    return str(value) if value is not None else None


def _is_high_risk(segment: dict[str, Any]) -> bool:
    risk = segment.get("ui_risk_classification", {})
    return risk.get("risk_level") in {"high", "critical"} or risk.get("review_priority") in {
        "review_recommended",
        "owner_review_required",
    }


def _term_in_text(term: str, text: str) -> bool:
    return term.casefold() in text.casefold()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _file_hash(path: Path | None) -> str | None:
    return sha256_file(path) if path and path.is_file() else None


def _combined_file_hash(state_dir: Path, names: tuple[str, ...]) -> str | None:
    items = [(name, sha256_file(state_dir / name)) for name in names if (state_dir / name).is_file()]
    return _stable_hash(items) if items else None


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _compact_segment(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "segment_id": item.get("segment_id"),
        "resource_key": item.get("resource_key"),
        "state": item.get("state"),
        "classifications": item.get("classifications", []),
        "action": item.get("action"),
        "blocks_generation_handoff": item.get("blocks_generation_handoff"),
        "blocks_delivery_apply": item.get("blocks_delivery_apply"),
    }
