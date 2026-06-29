from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json
from .knowledge_consumption import (
    KNOWLEDGE_ELIGIBILITY_REPORT_JSON,
    KNOWLEDGE_PACK_SELECTION_JSON,
    WORKING_CONTEXT_PACKET_JSON,
)


KNOWLEDGE_USAGE_REPORT_JSON = "knowledge-usage-report.json"
CONSTRAINT_APPLICATION_AUDIT_JSON = "constraint-application-audit.json"
KNOWLEDGE_CONFLICT_REPORT_JSON = "knowledge-conflict-report.json"


def build_knowledge_usage_report(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    selection = _read_optional_json(state_dir / KNOWLEDGE_PACK_SELECTION_JSON)
    eligibility = _read_optional_json(state_dir / KNOWLEDGE_ELIGIBILITY_REPORT_JSON)
    context = _read_optional_json(state_dir / WORKING_CONTEXT_PACKET_JSON)
    entries = eligibility.get("entries", []) if isinstance(eligibility.get("entries"), list) else []
    context_ids = _context_usage_ids(context)
    usage_entries = [_usage_entry(item, context_ids) for item in entries if isinstance(item, dict)]
    counts = _count_by(usage_entries, "usage_state")
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-usage-report-v1",
        "artifact": KNOWLEDGE_USAGE_REPORT_JSON,
        "status": _usage_status(selection, eligibility, context, usage_entries),
        "selected_pack_ids": selection.get("selected_pack_ids", []) if selection else [],
        "selected_packs": selection.get("selected_packs", []) if selection else [],
        "eligible_entry_count": sum(1 for item in usage_entries if not str(item.get("usage_state", "")).startswith("excluded_")),
        "usage_entries": usage_entries,
        "summary": {
            "entry_count": len(usage_entries),
            "applied_hard_constraint_count": counts.get("applied_hard_constraint", 0),
            "applied_negative_constraint_count": counts.get("applied_negative_constraint", 0),
            "used_soft_context_count": counts.get("used_soft_context", 0),
            "shown_reference_only_count": counts.get("shown_reference_only", 0),
            "excluded_count": sum(value for key, value in counts.items() if key.startswith("excluded_")),
            "conflicted_count": counts.get("conflicted", 0),
            "not_used_count": counts.get("not_used", 0),
        },
        "affected_artifacts": _existing_artifacts(state_dir, [KNOWLEDGE_PACK_SELECTION_JSON, KNOWLEDGE_ELIGIBILITY_REPORT_JSON, WORKING_CONTEXT_PACKET_JSON, "generation-strategy.json"]),
        "quality_claim_support": {
            "knowledge_backed_quality": False,
            "knowledge_constraints_applied": bool(counts.get("applied_hard_constraint", 0) or counts.get("applied_negative_constraint", 0)),
            "limitations": [
                "pack selection does not prove generation quality",
                "reference-only knowledge is not enforced",
                "constraint application still requires deterministic audit and downstream QA",
            ],
        },
    }
    if write:
        write_json(state_dir / KNOWLEDGE_USAGE_REPORT_JSON, report)
    return report


def build_constraint_application_audit(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    context = _read_optional_json(state_dir / WORKING_CONTEXT_PACKET_JSON)
    generated = _read_optional_jsonl(state_dir / "generated-segments.jsonl")
    constraints = [
        *context.get("hard_constraints", []),
        *context.get("negative_constraints", []),
        *context.get("claim_constraints", []),
        *context.get("style_guidance", []),
        *context.get("revision_hints", []),
        *context.get("reference_only_context", []),
    ] if context else []
    items = [_audit_constraint(item, generated) for item in constraints if isinstance(item, dict)]
    summary = _audit_summary(items)
    audit = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-constraint-application-audit-v1",
        "artifact": CONSTRAINT_APPLICATION_AUDIT_JSON,
        "status": "blocked" if summary["checked_fail_count"] else "pending_generation" if summary["pending_generation_count"] else "pass",
        "working_context_artifact": WORKING_CONTEXT_PACKET_JSON if context else None,
        "generated_segments_artifact": "generated-segments.jsonl" if generated else None,
        "audited_constraints": items,
        "summary": summary,
        "limitations": [
            "audit is deterministic and does not verify semantic translation quality",
            "pending_generation means constraints are eligible but no generated targets were available to check",
            "reference-only knowledge is listed for traceability and is not enforced",
        ],
    }
    if write:
        write_json(state_dir / CONSTRAINT_APPLICATION_AUDIT_JSON, audit)
    return audit


def build_knowledge_conflict_report(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    context = _read_optional_json(state_dir / WORKING_CONTEXT_PACKET_JSON)
    conflicts = []
    if context:
        for index, item in enumerate(context.get("hard_constraint_conflicts", []), 1):
            conflicts.append({
                "conflict_id": f"knowledge-conflict-{index:04d}",
                "severity": "P1" if item.get("blocking") else "P2",
                "type": str(item.get("reason") or "knowledge_constraint_conflict"),
                "involved_knowledge_items": item.get("pack_ids", [item.get("pack_id")]) if item.get("pack_ids") or item.get("pack_id") else [],
                "involved_project_artifacts": [WORKING_CONTEXT_PACKET_JSON],
                "source_term": str(item.get("source_term") or ""),
                "targets": item.get("targets", []),
                "priority_decision": "project_local_term_wins" if item.get("reason") == "project_local_term_conflicts_with_pack" else "requires_human_resolution",
                "blocking": bool(item.get("blocking")),
                "recommended_resolution": "Resolve or explicitly scope the conflicting locked knowledge before full-quality generation.",
                "handoff_impact": "blocked" if item.get("blocking") else "review_required",
            })
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-conflict-report-v1",
        "artifact": KNOWLEDGE_CONFLICT_REPORT_JSON,
        "status": "blocked" if any(item["blocking"] for item in conflicts) else "review_required" if conflicts else "pass",
        "conflicts": conflicts,
        "summary": {
            "conflict_count": len(conflicts),
            "blocking_conflict_count": sum(1 for item in conflicts if item["blocking"]),
        },
        "source_artifacts": _existing_artifacts(state_dir, [WORKING_CONTEXT_PACKET_JSON, KNOWLEDGE_ELIGIBILITY_REPORT_JSON, KNOWLEDGE_PACK_SELECTION_JSON]),
    }
    if write:
        write_json(state_dir / KNOWLEDGE_CONFLICT_REPORT_JSON, report)
    return report


def build_knowledge_usage_evidence(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    usage = build_knowledge_usage_report(state_dir, write=write)
    audit = build_constraint_application_audit(state_dir, write=write)
    conflicts = build_knowledge_conflict_report(state_dir, write=write)
    return {
        "knowledge_usage_report": usage,
        "constraint_application_audit": audit,
        "knowledge_conflict_report": conflicts,
    }


def read_knowledge_usage_report(state_dir: Path) -> dict[str, Any]:
    return _read_required_json(state_dir / KNOWLEDGE_USAGE_REPORT_JSON)


def read_constraint_application_audit(state_dir: Path) -> dict[str, Any]:
    return _read_required_json(state_dir / CONSTRAINT_APPLICATION_AUDIT_JSON)


def read_knowledge_conflict_report(state_dir: Path) -> dict[str, Any]:
    return _read_required_json(state_dir / KNOWLEDGE_CONFLICT_REPORT_JSON)


def knowledge_usage_asset_paths(state_dir: Path) -> dict[str, str]:
    return {
        key: name
        for key, name in {
            "knowledge_usage_report": KNOWLEDGE_USAGE_REPORT_JSON,
            "constraint_application_audit": CONSTRAINT_APPLICATION_AUDIT_JSON,
            "knowledge_conflict_report": KNOWLEDGE_CONFLICT_REPORT_JSON,
        }.items()
        if (state_dir / name).is_file()
    }


def _usage_entry(item: dict[str, Any], context_ids: dict[str, set[str]]) -> dict[str, Any]:
    classification = str(item.get("classification") or "")
    reasons = [str(reason) for reason in item.get("reasons", [])]
    knowledge_id = str(item.get("knowledge_id") or "")
    state = "not_used"
    if knowledge_id in context_ids["conflicted"]:
        state = "conflicted"
    elif classification == "hard_constraint":
        state = "applied_hard_constraint" if knowledge_id in context_ids["hard"] else "not_used"
    elif classification == "negative_constraint":
        state = "applied_negative_constraint" if knowledge_id in context_ids["negative"] else "not_used"
    elif classification == "soft_context":
        state = "used_soft_context" if knowledge_id in context_ids["soft"] else "not_used"
    elif classification == "reference_only":
        state = "shown_reference_only" if knowledge_id in context_ids["reference"] else "not_used"
    elif classification == "scope_mismatch":
        state = "excluded_scope_mismatch"
    elif classification == "stale":
        state = "excluded_stale"
    elif classification == "rejected":
        state = "excluded_rejected" if "entry_rejected" in reasons else "excluded_superseded" if "entry_superseded" in reasons else "excluded_rejected"
    elif "blind_benchmark_target_context_hidden" in reasons:
        state = "excluded_blind_benchmark"
    elif "status_requires_review" in reasons:
        state = "excluded_raw_or_candidate"
    return {
        "knowledge_id": knowledge_id,
        "pack_id": str(item.get("pack_id") or ""),
        "knowledge_type": str(item.get("knowledge_type") or ""),
        "source_artifact": str(item.get("source_artifact") or ""),
        "source_value": str(item.get("source_value") or ""),
        "target_value_present": bool(item.get("target_value")),
        "classification": classification,
        "usage_state": state,
        "scope": str(item.get("scope") or ""),
        "reasons": reasons,
        "provenance_id": str(item.get("provenance_id") or ""),
    }


def _context_usage_ids(context: dict[str, Any]) -> dict[str, set[str]]:
    groups = {
        "hard": _ids(context.get("hard_constraints", [])),
        "negative": _ids(context.get("negative_constraints", [])),
        "soft": _ids([*context.get("tm_suggestions", []), *context.get("style_guidance", []), *context.get("revision_hints", []), *context.get("claim_constraints", [])]),
        "reference": _ids([*context.get("retrieved_examples", []), *context.get("reference_only_context", [])]),
        "conflicted": set(),
    }
    conflict_sources = {str(item.get("source_term") or "").casefold() for item in context.get("hard_constraint_conflicts", []) if isinstance(item, dict)}
    for item in context.get("hard_constraints", []):
        if str(item.get("source_value") or "").casefold() in conflict_sources:
            groups["conflicted"].add(str(item.get("knowledge_id") or ""))
    return groups


def _audit_constraint(item: dict[str, Any], generated: list[dict[str, Any]]) -> dict[str, Any]:
    knowledge_type = str(item.get("knowledge_type") or "")
    classification = str(item.get("classification") or "")
    constraint_type = "forbidden_translation" if classification == "negative_constraint" else knowledge_type
    affected = _affected_segments(item, generated)
    status = "pending_review"
    result = "not_applicable"
    check = "trace_only"
    reason = "knowledge is not a deterministic hard constraint"
    if classification == "reference_only":
        status, reason = "reference_only_not_enforced", "reference-only entries cannot become hard constraints"
    elif classification == "soft_context":
        status, reason = "pending_review", "soft context requires downstream review evidence"
    elif classification == "hard_constraint" and knowledge_type == "term":
        check = "target_contains_approved_term_for_matching_source_segments"
        status, result, reason = _term_check(item, affected, generated)
    elif classification == "negative_constraint":
        check = "target_excludes_forbidden_translation_for_matching_source_segments"
        status, result, reason = _forbidden_check(item, affected, generated)
    elif classification == "hard_constraint":
        status, result, reason = "pending_review", "not_applicable", "claim or policy constraint requires review evidence"
    return {
        "constraint_id": f"constraint-{str(item.get('knowledge_id') or '')}",
        "source_knowledge_item_id": str(item.get("knowledge_id") or ""),
        "constraint_type": constraint_type,
        "source_artifact_references": [str(item.get("source_artifact") or "")],
        "target_artifact_references": ["generated-segments.jsonl"] if generated else [],
        "scope": str(item.get("scope") or ""),
        "status": status,
        "deterministic_check_performed": check,
        "affected_segments": affected,
        "result": result,
        "reason": reason,
        "limitations": ["semantic quality is not verified"],
    }


def _term_check(item: dict[str, Any], affected: list[str], generated: list[dict[str, Any]]) -> tuple[str, str, str]:
    if not generated:
        return "pending_generation", "not_applicable", "no generated targets available"
    if not affected:
        return "not_applicable", "not_applicable", "source term did not appear in generated segments"
    target = str(item.get("target_value") or "")
    missing = [segment_id for segment_id in affected if target not in _target_by_id(generated).get(segment_id, "")]
    if missing:
        return "checked_fail", "fail", "approved or locked term was missing from affected target segments"
    return "checked_pass", "pass", "approved or locked term appeared in affected target segments"


def _forbidden_check(item: dict[str, Any], affected: list[str], generated: list[dict[str, Any]]) -> tuple[str, str, str]:
    if not generated:
        return "pending_generation", "not_applicable", "no generated targets available"
    if not affected:
        return "not_applicable", "not_applicable", "source term did not appear in generated segments"
    forbidden = str(item.get("target_value") or "")
    violations = [segment_id for segment_id in affected if forbidden and forbidden in _target_by_id(generated).get(segment_id, "")]
    if violations:
        return "checked_fail", "fail", "forbidden translation appeared in affected target segments"
    return "checked_pass", "pass", "forbidden translation was absent from affected target segments"


def _affected_segments(item: dict[str, Any], generated: list[dict[str, Any]]) -> list[str]:
    source = str(item.get("source_value") or "").casefold()
    if not source:
        return []
    return [
        str(record.get("segment_id") or record.get("id") or "")
        for record in generated
        if source in str(record.get("source") or "").casefold()
    ]


def _target_by_id(generated: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(record.get("segment_id") or record.get("id") or ""): str(record.get("target") or record.get("target_text") or "")
        for record in generated
    }


def _audit_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "constraint_count": len(items),
        "applied_count": sum(1 for item in items if item.get("status") in {"applied", "checked_pass"}),
        "checked_pass_count": sum(1 for item in items if item.get("status") == "checked_pass"),
        "checked_fail_count": sum(1 for item in items if item.get("status") == "checked_fail"),
        "pending_generation_count": sum(1 for item in items if item.get("status") == "pending_generation"),
        "pending_review_count": sum(1 for item in items if item.get("status") == "pending_review"),
        "reference_only_not_enforced_count": sum(1 for item in items if item.get("status") == "reference_only_not_enforced"),
    }


def _usage_status(selection: dict[str, Any], eligibility: dict[str, Any], context: dict[str, Any], entries: list[dict[str, Any]]) -> str:
    if not selection:
        return "not_selected"
    if not eligibility or not context:
        return "blocked"
    if context.get("status") == "blocked" or any(item.get("usage_state") == "conflicted" for item in entries):
        return "blocked"
    return "pass"


def _ids(items: list[Any]) -> set[str]:
    return {str(item.get("knowledge_id") or "") for item in items if isinstance(item, dict)}


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _existing_artifacts(state_dir: Path, names: list[str]) -> dict[str, str]:
    return {name.removesuffix(".json").replace("-", "_"): name for name in names if (state_dir / name).is_file()}


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _read_required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing knowledge usage artifact: {path}")
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Knowledge usage artifact must be an object: {path}")
    return value


def _read_optional_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.is_file() else []
