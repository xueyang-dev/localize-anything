from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, write_json
from .knowledge_consumption import (
    KNOWLEDGE_ELIGIBILITY_REPORT_JSON,
    KNOWLEDGE_PACK_SELECTION_JSON,
    WORKING_CONTEXT_PACKET_JSON,
)
from .knowledge_usage import (
    CONSTRAINT_APPLICATION_AUDIT_JSON,
    KNOWLEDGE_CONFLICT_REPORT_JSON,
    KNOWLEDGE_USAGE_REPORT_JSON,
)


KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON = "knowledge-audit-enforcement-decision.json"
WORKBENCH_KNOWLEDGE_REVIEW_QUEUE_JSON = "workbench-knowledge-review-queue.json"

FORBIDDEN_KNOWLEDGE_CLAIMS = {
    "knowledge_backed_quality",
    "knowledge_constraints_applied",
    "knowledge_review_complete",
}
DOWNSTREAM_FORBIDDEN_CLAIMS = {"delivery_ready", "apply_ready", "production_ready"}


def build_knowledge_audit_enforcement_decision(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    artifacts = _load_artifacts(state_dir)
    selection = artifacts["selection"]
    if not selection or not selection.get("selected_packs"):
        decision = _base_decision(state_dir, "not_applicable", artifacts)
        decision.update(
            {
                "readiness_impact": {
                    "generation_handoff": "not_applicable",
                    "delivery": "not_applicable",
                    "apply": "not_applicable",
                    "scorecard": "knowledge_pack_not_selected",
                },
                "forbidden_claims": sorted(FORBIDDEN_KNOWLEDGE_CLAIMS),
                "required_next_actions": ["Select a reviewed knowledge pack before requesting knowledge-backed claims."],
            }
        )
        if write:
            write_json(state_dir / KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON, decision)
        return decision

    issues = _collect_issues(artifacts)
    status = _decision_status(issues)
    forbidden = set(FORBIDDEN_KNOWLEDGE_CLAIMS)
    if status == "clear":
        forbidden.discard("knowledge_constraints_applied")
    elif status in {"blocked", "stale", "review_required"}:
        forbidden.update(DOWNSTREAM_FORBIDDEN_CLAIMS)
    elif status == "clear_with_warnings":
        forbidden.add("knowledge_review_complete")
    decision = _base_decision(state_dir, status, artifacts)
    decision.update(
        {
            "reference_only_leakage_status": _issue_status(issues, "reference_only_leakage"),
            "blind_benchmark_firewall_status": _issue_status(issues, "blind_benchmark_firewall_risk"),
            "unresolved_conflicts": _unresolved_conflicts(artifacts["conflicts"]),
            "failed_audits": _failed_audits(artifacts["audit"]),
            "pending_reviews": _pending_reviews(artifacts["audit"], issues),
            "stale_evidence": [issue for issue in issues if issue["issue_type"] in {"working_context_stale", "stale_knowledge_evidence"}],
            "issues": issues,
            "readiness_impact": _readiness_impact(status),
            "forbidden_claims": sorted(forbidden),
            "required_next_actions": _required_next_actions(status, issues),
        }
    )
    if write:
        write_json(state_dir / KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON, decision)
    return decision


def read_knowledge_audit_enforcement_decision(state_dir: Path) -> dict[str, Any]:
    path = state_dir / KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON
    if path.is_file():
        value = read_json(path)
        return value if isinstance(value, dict) else {}
    return build_knowledge_audit_enforcement_decision(state_dir)


def build_workbench_knowledge_review_queue(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    decision = build_knowledge_audit_enforcement_decision(state_dir, write=True)
    resolutions = _load_queue_resolutions(state_dir)
    items = [_queue_item(index, issue, resolutions) for index, issue in enumerate(decision.get("issues", []), 1)]
    queue = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-knowledge-review-queue-v1",
        "artifact": WORKBENCH_KNOWLEDGE_REVIEW_QUEUE_JSON,
        "status": "requires_action" if items else "empty",
        "summary": {
            "item_count": len(items),
            "blocking_count": sum(1 for item in items if item["severity"] == "blocking"),
            "review_required_count": sum(1 for item in items if item["status"] == "requires_review"),
            "stale_count": sum(1 for item in items if item["stale_evidence_involved"]),
        },
        "items": items,
        "source_artifacts": _source_artifacts(state_dir),
    }
    if write:
        write_json(state_dir / WORKBENCH_KNOWLEDGE_REVIEW_QUEUE_JSON, queue)
    return queue


def read_workbench_knowledge_review_queue(state_dir: Path) -> dict[str, Any]:
    path = state_dir / WORKBENCH_KNOWLEDGE_REVIEW_QUEUE_JSON
    if path.is_file():
        value = read_json(path)
        return value if isinstance(value, dict) else {}
    return build_workbench_knowledge_review_queue(state_dir)


def knowledge_audit_enforcement_asset_paths(state_dir: Path) -> dict[str, str]:
    return {
        key: name
        for key, name in (
            ("knowledge_audit_enforcement_decision", KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON),
            ("workbench_knowledge_review_queue", WORKBENCH_KNOWLEDGE_REVIEW_QUEUE_JSON),
        )
        if (state_dir / name).is_file()
    }


def _base_decision(state_dir: Path, status: str, artifacts: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-audit-enforcement-decision-v1",
        "artifact": KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON,
        "status": status,
        "knowledge_pack_selection_status": _artifact_presence(artifacts["selection"]),
        "working_context_freshness": _freshness(artifacts["artifact_state"], "working_context_packet"),
        "usage_report_status": _status_or_missing(artifacts["usage"]),
        "constraint_audit_status": _status_or_missing(artifacts["audit"]),
        "conflict_report_status": _status_or_missing(artifacts["conflicts"]),
        "hard_constraint_application_status": _constraint_status(artifacts["audit"], hard=True),
        "negative_constraint_check_status": _constraint_status(artifacts["audit"], hard=False),
        "reference_only_leakage_status": "clear",
        "blind_benchmark_firewall_status": "clear",
        "source_artifacts": _source_artifacts(state_dir),
    }


def _load_artifacts(state_dir: Path) -> dict[str, Any]:
    return {
        "selection": _read_optional_json(state_dir / KNOWLEDGE_PACK_SELECTION_JSON),
        "eligibility": _read_optional_json(state_dir / KNOWLEDGE_ELIGIBILITY_REPORT_JSON),
        "context": _read_optional_json(state_dir / WORKING_CONTEXT_PACKET_JSON),
        "usage": _read_optional_json(state_dir / KNOWLEDGE_USAGE_REPORT_JSON),
        "audit": _read_optional_json(state_dir / CONSTRAINT_APPLICATION_AUDIT_JSON),
        "conflicts": _read_optional_json(state_dir / KNOWLEDGE_CONFLICT_REPORT_JSON),
        "artifact_state": _read_optional_json(state_dir / "artifact-state.json"),
    }


def _collect_issues(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    context = artifacts["context"]
    usage = artifacts["usage"]
    audit = artifacts["audit"]
    conflicts = artifacts["conflicts"]
    if not usage:
        issues.append(_issue("knowledge_usage_missing", "warning", "requires_review", "knowledge-usage-report.json is missing."))
    if not audit and _constraint_count(context, artifacts["eligibility"]):
        issues.append(_issue("constraint_audit_missing", "warning", "requires_review", "constraint-application-audit.json is missing."))
    if context and _artifact_status(artifacts["artifact_state"], "working_context_packet") in {"stale", "blocked", "superseded"}:
        issues.append(_issue("working_context_stale", "blocking", "stale", "working-context-packet.json is stale or blocked."))
    for artifact_id in ("knowledge_usage_report", "constraint_application_audit", "knowledge_conflict_report", "knowledge_audit_enforcement_decision"):
        if _artifact_status(artifacts["artifact_state"], artifact_id) in {"stale", "blocked", "superseded"}:
            issues.append(_issue("stale_knowledge_evidence", "blocking", "stale", f"{artifact_id} is stale or blocked.", source_artifacts=["artifact-state.json"]))
    for item in audit.get("audited_constraints", []) if isinstance(audit.get("audited_constraints"), list) else []:
        status = str(item.get("status") or "")
        constraint_type = str(item.get("constraint_type") or "")
        if status == "checked_fail" and constraint_type == "forbidden_translation":
            issues.append(_issue("negative_constraint_failed", "blocking", "blocked", str(item.get("reason") or "forbidden translation check failed"), constraint=item))
        elif status in {"checked_fail", "blocked", "conflicted"}:
            issues.append(_issue("hard_constraint_failed", "blocking", "blocked", str(item.get("reason") or "hard constraint check failed"), constraint=item))
        elif status == "pending_generation" or (status == "pending_review" and constraint_type in {"term", "forbidden_translation"}):
            issues.append(_issue("knowledge_review_required", "warning", "requires_review", str(item.get("reason") or "constraint requires generation or review"), constraint=item))
    for conflict in conflicts.get("conflicts", []) if isinstance(conflicts.get("conflicts"), list) else []:
        if conflict.get("blocking") or str(conflict.get("severity") or "") in {"P1", "P2"}:
            item_type = "project_priority_conflict" if str(conflict.get("priority_decision") or "") == "project_local_term_wins" else "knowledge_conflict_unresolved"
            issues.append(_issue(item_type, "blocking", "blocked", str(conflict.get("recommended_resolution") or "Resolve knowledge conflict."), conflict=conflict))
    issues.extend(_context_policy_issues(context, usage))
    return _dedupe_issues(issues)


def _context_policy_issues(context: dict[str, Any], usage: dict[str, Any]) -> list[dict[str, Any]]:
    if not context:
        return []
    issues: list[dict[str, Any]] = []
    hard_groups = [*context.get("hard_constraints", []), *context.get("negative_constraints", [])]
    all_groups = [
        *hard_groups,
        *context.get("tm_suggestions", []),
        *context.get("style_guidance", []),
        *context.get("revision_hints", []),
        *context.get("claim_constraints", []),
        *context.get("retrieved_examples", []),
        *context.get("reference_only_context", []),
    ]
    for item in hard_groups:
        classification = str(item.get("classification") or "")
        status = str(item.get("status") or "")
        if classification == "reference_only" or status == "reference":
            issues.append(_issue("reference_only_leakage", "blocking", "blocked", "reference-only knowledge appeared in enforced constraints.", knowledge_item=item))
        if status in {"raw", "candidate", "rejected", "stale", "superseded"}:
            issues.append(_issue("knowledge_claim_not_supported", "blocking", "blocked", f"{status} knowledge appeared in enforced constraints.", knowledge_item=item))
    if context.get("operating_mode") == "blind_benchmark":
        for item in all_groups:
            if str(item.get("knowledge_type") or "") in {"translation_memory", "alignment_example", "revision_memory"} and item.get("target_value"):
                issues.append(_issue("blind_benchmark_firewall_risk", "blocking", "blocked", "target-language pack knowledge was exposed in blind_benchmark mode.", knowledge_item=item))
    for entry in usage.get("usage_entries", []) if isinstance(usage.get("usage_entries"), list) else []:
        if str(entry.get("usage_state") or "") == "excluded_scope_mismatch" and str(entry.get("classification") or "") in {"hard_constraint", "negative_constraint"}:
            issues.append(_issue("scope_mismatch", "warning", "requires_review", "scope-specific knowledge was excluded from constraints.", knowledge_item=entry))
    return issues


def _issue(
    issue_type: str,
    severity: str,
    status: str,
    reason: str,
    *,
    source_artifacts: list[str] | None = None,
    constraint: dict[str, Any] | None = None,
    conflict: dict[str, Any] | None = None,
    knowledge_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "issue_type": issue_type,
        "severity": severity,
        "status": status,
        "reason": reason,
        "source_artifact_references": source_artifacts or _issue_sources(constraint, conflict, knowledge_item),
        "affected_knowledge_item_ids": _ids_from(constraint, conflict, knowledge_item),
        "affected_segment_ids": [str(item) for item in (constraint or {}).get("affected_segments", [])],
        "related_constraint_id": str((constraint or {}).get("constraint_id") or ""),
        "related_conflict_id": str((conflict or {}).get("conflict_id") or ""),
        "related_forbidden_claim": _related_claim(issue_type),
        "readiness_impact": "blocks_delivery_apply" if severity == "blocking" else "requires_review",
    }


def _queue_item(index: int, issue: dict[str, Any], resolutions: dict[str, Any]) -> dict[str, Any]:
    resolution = _issue_resolution(issue, resolutions)
    return {
        "item_id": f"knowledge-review-{index:04d}",
        "item_type": issue["issue_type"],
        "severity": issue["severity"],
        "status": resolution.get("status") or issue["status"],
        "owner_role": "localization_reviewer" if issue["severity"] == "warning" else "project_owner",
        "source_artifact_references": issue.get("source_artifact_references", []),
        "affected_knowledge_item_ids": issue.get("affected_knowledge_item_ids", []),
        "affected_segment_ids": issue.get("affected_segment_ids", []),
        "affected_scope": {},
        "related_constraint_id": issue.get("related_constraint_id", ""),
        "related_conflict_id": issue.get("related_conflict_id", ""),
        "related_forbidden_claim": issue.get("related_forbidden_claim", ""),
        "readiness_impact": issue.get("readiness_impact", ""),
        "recommended_action": _recommended_action(issue),
        "human_confirmation_required": issue["issue_type"] in {"knowledge_conflict_unresolved", "project_priority_conflict", "knowledge_review_required"},
        "stale_evidence_involved": issue["issue_type"] in {"working_context_stale", "stale_knowledge_evidence"},
        "resolution_status": resolution.get("status") or "unresolved",
        "resolution_artifact_references": resolution.get("artifact_references", []),
        "available_decision_options": _decision_options(issue),
        "action_endpoint_hint": "/api/knowledge-audit-resolution-log" if issue.get("related_conflict_id") or issue.get("related_constraint_id") else "/api/knowledge-constraint-review-evidence",
    }


def _decision_status(issues: list[dict[str, Any]]) -> str:
    if any(item["severity"] == "blocking" and item["issue_type"] not in {"working_context_stale", "stale_knowledge_evidence"} for item in issues):
        return "blocked"
    if any(item["issue_type"] in {"working_context_stale", "stale_knowledge_evidence"} for item in issues):
        return "stale"
    if any(item["status"] == "requires_review" for item in issues):
        return "review_required"
    return "clear"


def _issue_status(issues: list[dict[str, Any]], issue_type: str) -> str:
    matching = [item for item in issues if item["issue_type"] == issue_type]
    if not matching:
        return "clear"
    if any(item["severity"] == "blocking" for item in matching):
        return "blocked"
    if any(item["status"] == "requires_review" for item in matching):
        return "review_required"
    if any(item["status"] == "stale" for item in matching):
        return "stale"
    return "clear_with_warnings"


def _readiness_impact(status: str) -> dict[str, str]:
    if status == "clear":
        return {"generation_handoff": "allowed", "delivery": "allowed", "apply": "allowed", "scorecard": "narrow_constraint_claim_supported"}
    if status == "clear_with_warnings":
        return {"generation_handoff": "allowed_with_warnings", "delivery": "warn", "apply": "warn", "scorecard": "knowledge_claims_limited"}
    if status == "review_required":
        return {"generation_handoff": "knowledge_review_required", "delivery": "downgraded", "apply": "blocked", "scorecard": "knowledge_claims_forbidden"}
    if status == "stale":
        return {"generation_handoff": "blocked", "delivery": "blocked", "apply": "blocked", "scorecard": "stale_knowledge_claims_forbidden"}
    if status == "blocked":
        return {"generation_handoff": "blocked", "delivery": "blocked", "apply": "blocked", "scorecard": "knowledge_claims_forbidden"}
    return {"generation_handoff": "not_applicable", "delivery": "not_applicable", "apply": "not_applicable", "scorecard": "not_applicable"}


def _required_next_actions(status: str, issues: list[dict[str, Any]]) -> list[str]:
    if status == "clear":
        return ["Continue deterministic QA and human review before claiming knowledge-backed quality."]
    actions = []
    if any(item["issue_type"] == "knowledge_usage_missing" for item in issues):
        actions.append("Regenerate knowledge-usage-report.json.")
    if any(item["issue_type"] == "constraint_audit_missing" for item in issues):
        actions.append("Regenerate constraint-application-audit.json before claiming constraints were applied.")
    if any(item["issue_type"] in {"working_context_stale", "stale_knowledge_evidence"} for item in issues):
        actions.append("Refresh stale knowledge context and audit artifacts.")
    if any(item["issue_type"] in {"hard_constraint_failed", "negative_constraint_failed"} for item in issues):
        actions.append("Repair or regenerate affected segments, then rerun deterministic constraint audit.")
    if any(item["issue_type"] in {"knowledge_conflict_unresolved", "project_priority_conflict"} for item in issues):
        actions.append("Resolve knowledge conflicts or record explicit scoped review decisions.")
    if any(item["issue_type"] == "blind_benchmark_firewall_risk" for item in issues):
        actions.append("Remove target-language pack context from blind_benchmark mode artifacts.")
    return actions or ["Review knowledge audit evidence before stronger readiness claims."]


def _failed_audits(audit: dict[str, Any]) -> list[dict[str, Any]]:
    items = audit.get("audited_constraints", []) if isinstance(audit.get("audited_constraints"), list) else []
    return [
        item
        for item in items
        if isinstance(item, dict) and str(item.get("status") or "") in {"checked_fail", "blocked", "conflicted"}
    ]


def _pending_reviews(audit: dict[str, Any], issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = audit.get("audited_constraints", []) if isinstance(audit.get("audited_constraints"), list) else []
    pending = [
        item
        for item in items
        if isinstance(item, dict) and str(item.get("status") or "") in {"pending_generation", "pending_review"}
    ]
    pending.extend(item for item in issues if item["status"] == "requires_review")
    return pending


def _unresolved_conflicts(conflicts: dict[str, Any]) -> list[dict[str, Any]]:
    items = conflicts.get("conflicts", []) if isinstance(conflicts.get("conflicts"), list) else []
    return [
        item
        for item in items
        if isinstance(item, dict) and (item.get("blocking") or str(item.get("severity") or "") in {"P1", "P2"})
    ]


def _constraint_status(audit: dict[str, Any], *, hard: bool) -> str:
    if not audit:
        return "missing"
    items = audit.get("audited_constraints", []) if isinstance(audit.get("audited_constraints"), list) else []
    relevant = [
        item
        for item in items
        if isinstance(item, dict)
        and ((str(item.get("constraint_type") or "") != "forbidden_translation") if hard else (str(item.get("constraint_type") or "") == "forbidden_translation"))
    ]
    if not relevant:
        return "not_applicable"
    statuses = {str(item.get("status") or "") for item in relevant}
    if statuses.intersection({"checked_fail", "blocked", "conflicted"}):
        return "failed"
    if statuses.intersection({"pending_generation", "pending_review"}):
        return "pending"
    if "checked_pass" in statuses:
        return "passed"
    return "not_applicable"


def _constraint_count(context: dict[str, Any], eligibility: dict[str, Any]) -> int:
    if context:
        return len(context.get("hard_constraints", [])) + len(context.get("negative_constraints", []))
    summary = eligibility.get("summary", {}) if isinstance(eligibility.get("summary"), dict) else {}
    return int(summary.get("hard_constraint_count", 0) or 0) + int(summary.get("negative_constraint_count", 0) or 0)


def _artifact_status(artifact_state: dict[str, Any], artifact_id: str) -> str:
    for item in artifact_state.get("artifacts", []) if isinstance(artifact_state, dict) else []:
        if item.get("artifact_id") == artifact_id:
            return str(item.get("status") or "")
    return ""


def _freshness(artifact_state: dict[str, Any], artifact_id: str) -> str:
    status = _artifact_status(artifact_state, artifact_id)
    return status or "unknown"


def _status_or_missing(artifact: dict[str, Any]) -> str:
    return str(artifact.get("status") or "missing") if artifact else "missing"


def _artifact_presence(artifact: dict[str, Any]) -> str:
    if not artifact:
        return "missing"
    if artifact.get("selected_packs"):
        return "selected"
    return "no_valid_pack_selected"


def _issue_sources(constraint: dict[str, Any] | None, conflict: dict[str, Any] | None, knowledge_item: dict[str, Any] | None) -> list[str]:
    if constraint:
        return [item for item in constraint.get("source_artifact_references", []) if item]
    if conflict:
        return [item for item in conflict.get("involved_project_artifacts", []) if item]
    if knowledge_item:
        source = str(knowledge_item.get("source_artifact") or "")
        return [source] if source else [WORKING_CONTEXT_PACKET_JSON]
    return [WORKING_CONTEXT_PACKET_JSON]


def _ids_from(constraint: dict[str, Any] | None, conflict: dict[str, Any] | None, knowledge_item: dict[str, Any] | None) -> list[str]:
    ids: list[str] = []
    if constraint and constraint.get("source_knowledge_item_id"):
        ids.append(str(constraint["source_knowledge_item_id"]))
    if knowledge_item and knowledge_item.get("knowledge_id"):
        ids.append(str(knowledge_item["knowledge_id"]))
    if conflict:
        ids.extend(str(item) for item in conflict.get("involved_knowledge_items", []) if item)
    return sorted(set(ids))


def _related_claim(issue_type: str) -> str:
    if issue_type in {"hard_constraint_failed", "negative_constraint_failed", "constraint_audit_missing"}:
        return "knowledge_constraints_applied"
    if issue_type in {"knowledge_review_required", "knowledge_claim_not_supported"}:
        return "knowledge_review_complete"
    return "knowledge_backed_quality"


def _recommended_action(issue: dict[str, Any]) -> str:
    mapping = {
        "knowledge_usage_missing": "Regenerate knowledge usage evidence from current pack selection and working context.",
        "working_context_stale": "Rebuild the Working Context Packet and rerun usage/audit reports.",
        "constraint_audit_missing": "Run deterministic constraint application audit.",
        "hard_constraint_failed": "Repair or regenerate affected segments and rerun the hard constraint audit.",
        "negative_constraint_failed": "Remove forbidden translations from affected output and rerun deterministic QA.",
        "knowledge_conflict_unresolved": "Resolve conflicting knowledge or scope it before full-quality handoff.",
        "reference_only_leakage": "Remove reference-only entries from hard constraints.",
        "scope_mismatch": "Limit knowledge use to matching scope or request human confirmation.",
        "blind_benchmark_firewall_risk": "Remove target-language pack examples from blind benchmark context.",
        "project_priority_conflict": "Keep project-local decisions authoritative and record conflict resolution.",
        "knowledge_review_required": "Record review evidence for knowledge-affected constraints.",
        "knowledge_claim_not_supported": "Do not request knowledge-backed claims until evidence supports them.",
        "stale_knowledge_evidence": "Refresh stale knowledge audit evidence.",
    }
    return mapping.get(str(issue.get("issue_type") or ""), "Review knowledge audit evidence.")


def _dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for issue in issues:
        key = (issue["issue_type"], ",".join(issue.get("affected_knowledge_item_ids", [])), issue.get("related_constraint_id", "") or issue.get("related_conflict_id", ""))
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result


def _source_artifacts(state_dir: Path) -> dict[str, str]:
    names = (
        KNOWLEDGE_PACK_SELECTION_JSON,
        KNOWLEDGE_ELIGIBILITY_REPORT_JSON,
        WORKING_CONTEXT_PACKET_JSON,
        KNOWLEDGE_USAGE_REPORT_JSON,
        CONSTRAINT_APPLICATION_AUDIT_JSON,
        KNOWLEDGE_CONFLICT_REPORT_JSON,
        "artifact-state.json",
        KNOWLEDGE_AUDIT_ENFORCEMENT_DECISION_JSON,
        WORKBENCH_KNOWLEDGE_REVIEW_QUEUE_JSON,
        "knowledge-audit-resolution-log.jsonl",
        "knowledge-constraint-review-evidence.jsonl",
        "knowledge-conflict-resolution.json",
        "knowledge-assurance-summary.json",
    )
    return {Path(name).stem.replace("-", "_"): name for name in names if (state_dir / name).is_file()}


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _read_optional_jsonl(path: Path) -> list[dict[str, Any]]:
    from .io_utils import read_jsonl

    return read_jsonl(path) if path.is_file() else []


def _load_queue_resolutions(state_dir: Path) -> dict[str, Any]:
    return {
        "resolution_log": _read_optional_jsonl(state_dir / "knowledge-audit-resolution-log.jsonl"),
        "constraint_review": _read_optional_jsonl(state_dir / "knowledge-constraint-review-evidence.jsonl"),
        "conflict_resolution": _read_optional_json(state_dir / "knowledge-conflict-resolution.json"),
    }


def _issue_resolution(issue: dict[str, Any], resolutions: dict[str, Any]) -> dict[str, Any]:
    conflict_id = str(issue.get("related_conflict_id") or "")
    constraint_id = str(issue.get("related_constraint_id") or "")
    for record in reversed(resolutions.get("resolution_log", [])):
        if conflict_id and record.get("related_conflict_id") == conflict_id:
            return {
                "status": _resolved_status(record),
                "artifact_references": ["knowledge-audit-resolution-log.jsonl"],
            }
        if constraint_id and record.get("related_constraint_audit_id") == constraint_id:
            return {
                "status": _resolved_status(record),
                "artifact_references": ["knowledge-audit-resolution-log.jsonl"],
            }
    for record in reversed(resolutions.get("constraint_review", [])):
        reviewed = set(str(item) for item in [*record.get("reviewed_constraints", []), *record.get("reviewed_negative_constraints", [])])
        if constraint_id and constraint_id in reviewed:
            return {
                "status": _resolved_status({"decision_status": record.get("decision")}),
                "artifact_references": ["knowledge-constraint-review-evidence.jsonl"],
            }
    return {"status": "unresolved", "artifact_references": []}


def _resolved_status(record: dict[str, Any]) -> str:
    status = str(record.get("decision_status") or "")
    if status == "accepted":
        return "resolved"
    if status == "accepted_with_limitations":
        return "accepted_with_limitations"
    if status == "rejected":
        return "rejected"
    if status == "requires_follow_up":
        return "requires_follow_up"
    if status in {"blocked", "stale", "superseded"}:
        return status
    return "unresolved"


def _decision_options(issue: dict[str, Any]) -> list[str]:
    issue_type = str(issue.get("issue_type") or "")
    if issue_type in {"hard_constraint_failed", "negative_constraint_failed", "knowledge_review_required"}:
        return ["accept_constraint_application", "reject_constraint_application", "request_generation_repair", "keep_blocked"]
    if issue_type in {"knowledge_conflict_unresolved", "project_priority_conflict"}:
        return ["prefer_project_term", "resolve_knowledge_conflict", "scope_limit_knowledge", "keep_blocked"]
    if issue_type == "reference_only_leakage":
        return ["reject_reference_only_use", "accept_reference_only_use", "keep_blocked"]
    if issue_type == "blind_benchmark_firewall_risk":
        return ["confirm_blind_benchmark_firewall", "reject_blind_benchmark_firewall", "keep_blocked"]
    return ["accept_limited_knowledge_risk", "request_follow_up", "keep_blocked"]
