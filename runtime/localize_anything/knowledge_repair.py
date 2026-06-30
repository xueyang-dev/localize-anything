from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json


KNOWLEDGE_REPAIR_PLAN_JSON = "knowledge-repair-plan.json"
KNOWLEDGE_REPAIR_REQUEST_JSON = "knowledge-repair-request.json"
KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON = "knowledge-repair-impact-report.json"

SOURCE_ARTIFACTS = (
    "knowledge-usage-report.json",
    "constraint-application-audit.json",
    "knowledge-conflict-report.json",
    "knowledge-audit-enforcement-decision.json",
    "workbench-knowledge-review-queue.json",
    "knowledge-audit-resolution-log.jsonl",
    "knowledge-constraint-review-evidence.jsonl",
    "knowledge-conflict-resolution.json",
    "knowledge-assurance-summary.json",
    "segment-regeneration-plan.json",
    "repair-request.json",
    "repair-result.json",
    "repair-history.jsonl",
)

BLOCKING_ACTIONS = {"block_until_conflict_resolved", "scope_limit_required"}
HUMAN_ACTIONS = {"human_review_required", "human_rewrite_required"}
MODEL_ACTIONS = {"provider_repair_pending", "model_repair_pending", "regenerate_with_constraints"}
DETERMINISTIC_ACTIONS = {"term_patch", "forbidden_translation_patch", "placeholder_safe_patch", "markup_safe_patch", "escape_safe_patch"}


def build_knowledge_repair_plan(state_dir: Path, *, run_id: str | None = None, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    artifacts = _load_artifacts(state_dir)
    queue = artifacts["workbench-knowledge-review-queue.json"]
    resolved_conflicts = {
        str(item.get("conflict_id") or "")
        for item in artifacts["knowledge-conflict-resolution.json"].get("resolved_conflicts", [])
        if isinstance(item, dict)
    }
    items: list[dict[str, Any]] = []
    for issue in artifacts["knowledge-audit-enforcement-decision.json"].get("issues", []):
        if not isinstance(issue, dict):
            continue
        if issue.get("related_conflict_id") in resolved_conflicts:
            continue
        item = _plan_item(issue, queue, artifacts)
        if item:
            items.append(item)
    items.extend(_review_follow_up_items(artifacts, queue))
    items = _dedupe(items)
    active, cleared = _clear_completed_items(items, artifacts)
    summary = _plan_summary(active, cleared)
    plan = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-repair-plan-v1",
        "artifact": KNOWLEDGE_REPAIR_PLAN_JSON,
        "run_id": run_id,
        "status": _plan_status(active),
        "summary": summary,
        "repair_items": active,
        "cleared_items": cleared,
        "existing_repair_workflow": {
            "segment_regeneration_plan": _presence(artifacts["segment-regeneration-plan.json"]),
            "repair_request": _presence(artifacts["repair-request.json"]),
            "repair_result": _presence(artifacts["repair-result.json"]),
            "repair_history": _presence(artifacts["repair-history.jsonl"]),
            "replacement_policy": "reference_or_enrich_only",
        },
        "forbidden_claims": _forbidden_claims(active),
        "source_artifacts": _source_artifact_map(state_dir),
        "limitations": [
            "planning is deterministic and does not execute provider or model repair",
            "repair planning does not prove repair success",
            "repair results clear items only when target hashes and QA evidence match",
        ],
    }
    request = _build_request(plan, artifacts)
    impact = _build_impact(plan, request)
    if write:
        state_dir.mkdir(parents=True, exist_ok=True)
        write_json(state_dir / KNOWLEDGE_REPAIR_PLAN_JSON, plan)
        write_json(state_dir / KNOWLEDGE_REPAIR_REQUEST_JSON, request)
        write_json(state_dir / KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON, impact)
    return plan


def build_knowledge_repair_request(state_dir: Path, *, run_id: str | None = None, write: bool = True) -> dict[str, Any]:
    build_knowledge_repair_plan(state_dir, run_id=run_id, write=write)
    return read_knowledge_repair_request(state_dir) if write else _build_request(
        build_knowledge_repair_plan(state_dir, run_id=run_id, write=False), _load_artifacts(state_dir)
    )


def build_knowledge_repair_impact_report(state_dir: Path, *, run_id: str | None = None, write: bool = True) -> dict[str, Any]:
    plan = build_knowledge_repair_plan(state_dir, run_id=run_id, write=write)
    if write:
        return read_knowledge_repair_impact_report(state_dir)
    request = _build_request(plan, _load_artifacts(state_dir))
    return _build_impact(plan, request)


def read_knowledge_repair_plan(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / KNOWLEDGE_REPAIR_PLAN_JSON)


def read_knowledge_repair_request(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / KNOWLEDGE_REPAIR_REQUEST_JSON)


def read_knowledge_repair_impact_report(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON)


def knowledge_repair_asset_paths(state_dir: Path) -> dict[str, str]:
    return {
        key: name
        for key, name in (
            ("knowledge_repair_plan", KNOWLEDGE_REPAIR_PLAN_JSON),
            ("knowledge_repair_request", KNOWLEDGE_REPAIR_REQUEST_JSON),
            ("knowledge_repair_impact_report", KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON),
        )
        if (state_dir / name).is_file()
    }


def knowledge_repair_summary(state_dir: Path) -> dict[str, Any]:
    path = state_dir / KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON
    if not path.is_file():
        return {"status": "not_run", "pending_required_count": 0, "blocked_count": 0, "forbidden_claims": []}
    report = read_json(path)
    return {
        "status": report.get("status", "unknown"),
        "pending_required_count": int(report.get("summary", {}).get("repair_item_count", 0)),
        "blocked_count": int(report.get("summary", {}).get("blocked_count", 0)),
        "forbidden_claims": report.get("affected_claims", []),
        "delivery_apply_readiness_impact": report.get("delivery_apply_readiness_impact", "unknown"),
    }


def _load_artifacts(state_dir: Path) -> dict[str, Any]:
    artifacts = {name: _read_optional(state_dir / name) for name in SOURCE_ARTIFACTS}
    artifacts["working-context-packet.json"] = _read_optional(state_dir / "working-context-packet.json")
    artifacts["artifact-state.json"] = _read_optional(state_dir / "artifact-state.json")
    artifacts["generated-segments.jsonl"] = _read_jsonl_optional(state_dir / "generated-segments.jsonl")
    if not artifacts["generated-segments.jsonl"]:
        artifacts["generated-segments.jsonl"] = _read_jsonl_optional(state_dir / "generated.jsonl")
    return artifacts


def _plan_item(issue: dict[str, Any], queue: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any] | None:
    issue_type = _supported_issue_type(issue)
    if not issue_type:
        return None
    knowledge_ids = _strings(issue.get("affected_knowledge_item_ids"))
    segment_ids = _strings(issue.get("affected_segment_ids"))
    constraint_id = str(issue.get("related_constraint_id") or "")
    conflict_id = str(issue.get("related_conflict_id") or "")
    queue_item = _matching_queue_item(queue, issue)
    knowledge = _knowledge_entry(knowledge_ids, artifacts["working-context-packet.json"])
    action, deterministic, replacement = _repair_policy(issue_type, issue, knowledge, artifacts)
    item_id = _stable_id("knowledge-repair", [issue_type, constraint_id, conflict_id, knowledge_ids, segment_ids])
    source_refs = list(dict.fromkeys(_strings(issue.get("source_artifact_references")) + ["knowledge-audit-enforcement-decision.json"]))
    return {
        "repair_item_id": item_id,
        "affected_segment_ids": segment_ids,
        "affected_scope": queue_item.get("affected_scope", {}) if queue_item else {},
        "source_knowledge_item_ids": knowledge_ids,
        "related_constraint_id": constraint_id,
        "related_conflict_id": conflict_id,
        "related_audit_item_id": constraint_id,
        "related_queue_item_id": str((queue_item or {}).get("item_id") or ""),
        "issue_type": issue_type,
        "severity": str(issue.get("severity") or "warning"),
        "repair_action": action,
        "deterministic_eligibility": deterministic,
        "preferred_replacement": replacement,
        "forbidden_target_pattern": str(knowledge.get("target_value") or "") if issue_type == "forbidden_translation_detected" else None,
        "required_human_confirmation": (
            action in HUMAN_ACTIONS or action in BLOCKING_ACTIONS or issue_type == "blind_benchmark_firewall_violation"
        ),
        "required_provider_model_repair_status": (
            "pending"
            if action in MODEL_ACTIONS
            else "blocked"
            if action in BLOCKING_ACTIONS or issue_type == "blind_benchmark_firewall_violation"
            else "not_required"
        ),
        "expected_downstream_artifacts_to_refresh": _downstream_refresh(segment_ids),
        "forbidden_claims_affected": _item_forbidden_claims(issue_type),
        "readiness_impact": "blocked" if action in BLOCKING_ACTIONS else "requires_repair" if action != "no_repair_applicable" else "requires_review",
        "source_artifact_references": source_refs,
        "reason": str(issue.get("reason") or ""),
    }


def _supported_issue_type(issue: dict[str, Any]) -> str:
    raw = str(issue.get("issue_type") or "")
    mapping = {
        "hard_constraint_failed": "hard_term_constraint_failed",
        "negative_constraint_failed": "forbidden_translation_detected",
        "knowledge_conflict_unresolved": "knowledge_conflict_unresolved",
        "project_priority_conflict": "project_priority_violation",
        "scope_mismatch": "scope_mismatch",
        "reference_only_leakage": "reference_only_leakage",
        "blind_benchmark_firewall_risk": "blind_benchmark_firewall_violation",
        "knowledge_review_required": "knowledge_review_required",
    }
    if raw == "knowledge_claim_not_supported":
        reason = str(issue.get("reason") or "").lower()
        return "stale_knowledge_used" if "stale" in reason or "superseded" in reason else "raw_candidate_knowledge_used"
    return mapping.get(raw, "")


def _repair_policy(
    issue_type: str,
    issue: dict[str, Any],
    knowledge: dict[str, Any],
    artifacts: dict[str, Any],
) -> tuple[str, bool, str | None]:
    if issue_type == "hard_term_constraint_failed":
        replacement = str(knowledge.get("target_value") or "")
        if replacement and issue.get("affected_segment_ids") and not issue.get("related_conflict_id"):
            return "term_patch", True, replacement
        return "human_rewrite_required", False, None
    if issue_type in {"forbidden_translation_detected", "negative_constraint_failed"}:
        replacement = _approved_replacement(knowledge, artifacts["working-context-packet.json"])
        if replacement and issue.get("affected_segment_ids"):
            return "forbidden_translation_patch", True, replacement
        return "human_rewrite_required", False, None
    if issue_type in {"knowledge_conflict_unresolved", "project_priority_violation"}:
        return "block_until_conflict_resolved", False, None
    if issue_type == "scope_mismatch":
        return "scope_limit_required", False, None
    if issue_type in {"reference_only_leakage", "stale_knowledge_used", "raw_candidate_knowledge_used"}:
        return "human_review_required", False, None
    if issue_type == "blind_benchmark_firewall_violation":
        return "no_repair_applicable", False, None
    if issue_type in {"knowledge_review_required", "constraint_review_follow_up_required"}:
        return "human_review_required", False, None
    return "no_repair_applicable", False, None


def _review_follow_up_items(artifacts: dict[str, Any], queue: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for evidence in artifacts["knowledge-constraint-review-evidence.jsonl"].get("items", []):
        follow_up = _strings(evidence.get("required_follow_up"))
        if not follow_up:
            continue
        issue = {
            "issue_type": "constraint_review_follow_up_required",
            "severity": "warning",
            "status": "requires_review",
            "reason": "; ".join(follow_up),
            "affected_knowledge_item_ids": _strings(evidence.get("reviewed_knowledge_usage_entries")),
            "affected_segment_ids": _strings(evidence.get("reviewed_generated_or_staged_segments")),
            "related_constraint_id": (_strings(evidence.get("reviewed_constraints")) or [""])[0],
            "source_artifact_references": ["knowledge-constraint-review-evidence.jsonl"],
        }
        item = _plan_item(issue, queue, artifacts)
        if item:
            items.append(item)
    return items


def _build_request(plan: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    existing = artifacts["repair-request.json"].get("requests", [])
    requests = []
    for item in plan.get("repair_items", []):
        action = str(item.get("repair_action") or "")
        if action == "no_repair_applicable":
            continue
        segment_ids = item.get("affected_segment_ids", [])
        request_id = _stable_id("knowledge-repair-request", item.get("repair_item_id"))
        requests.append(
            {
                "request_id": request_id,
                "knowledge_repair_item_id": item.get("repair_item_id"),
                "request_type": action,
                "affected_segment_ids": segment_ids,
                "affected_scope": item.get("affected_scope", {}),
                "current_target_hashes": _current_target_hashes(segment_ids, artifacts["generated-segments.jsonl"]),
                "required_constraint": item.get("related_constraint_id") or None,
                "forbidden_target_pattern": item.get("forbidden_target_pattern"),
                "preferred_replacement": item.get("preferred_replacement") if item.get("deterministic_eligibility") else None,
                "source_knowledge_provenance": {
                    "knowledge_item_ids": item.get("source_knowledge_item_ids", []),
                    "source_artifact_references": item.get("source_artifact_references", []),
                },
                "required_reviewer_role": "project_owner" if item.get("severity") == "blocking" else "localization_reviewer",
                "allowed_repair_modes": _allowed_modes(item),
                "blocked_repair_modes": _blocked_modes(item),
                "expected_validation_checks": ["target_hash_match", "constraint_application_audit", "deterministic_qa", "knowledge_usage_recompute"],
                "related_existing_repair_ids": [
                    str(request.get("repair_id"))
                    for request in existing
                    if isinstance(request, dict) and str(request.get("segment_id") or "") in segment_ids
                ],
                "status": "blocked" if action in BLOCKING_ACTIONS else "pending",
                "limitations": ["request creation does not execute repair or prove success"],
            }
        )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-repair-request-v1",
        "artifact": KNOWLEDGE_REPAIR_REQUEST_JSON,
        "run_id": plan.get("run_id"),
        "status": "blocked" if any(item["status"] == "blocked" for item in requests) else "pending" if requests else "ready",
        "knowledge_repair_plan_path": KNOWLEDGE_REPAIR_PLAN_JSON,
        "existing_repair_request_path": "repair-request.json" if artifacts["repair-request.json"] else None,
        "summary": {
            "request_count": len(requests),
            "deterministic_request_count": sum(item["request_type"] in DETERMINISTIC_ACTIONS for item in requests),
            "blocked_request_count": sum(item["status"] == "blocked" for item in requests),
        },
        "requests": requests,
        "provider_or_model_execution_performed": False,
    }


def _build_impact(plan: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    items = plan.get("repair_items", [])
    affected_segments = sorted({segment for item in items for segment in item.get("affected_segment_ids", [])})
    affected_claims = sorted({claim for item in items for claim in item.get("forbidden_claims_affected", [])})
    refresh = sorted({artifact for item in items for artifact in item.get("expected_downstream_artifacts_to_refresh", [])})
    summary = {
        "repair_item_count": len(items),
        "deterministic_repair_candidate_count": sum(bool(item.get("deterministic_eligibility")) for item in items),
        "human_review_required_count": sum(item.get("repair_action") in HUMAN_ACTIONS for item in items),
        "provider_model_pending_count": sum(item.get("repair_action") in MODEL_ACTIONS for item in items),
        "blocked_count": sum(item.get("repair_action") in BLOCKING_ACTIONS or item.get("issue_type") == "blind_benchmark_firewall_violation" for item in items),
        "cleared_item_count": len(plan.get("cleared_items", [])),
        "request_count": int(request.get("summary", {}).get("request_count", 0)),
    }
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-repair-impact-report-v1",
        "artifact": KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON,
        "run_id": plan.get("run_id"),
        "status": "blocked" if summary["blocked_count"] else "repair_required" if items else "clear",
        "summary": summary,
        "affected_segments": affected_segments,
        "affected_claims": affected_claims,
        "affected_scorecard_dimensions": ["knowledge_assurance", "terminology_assurance", "review_readiness", "delivery_readiness", "apply_readiness"] if items else [],
        "artifacts_to_regenerate_after_repair": refresh,
        "delivery_apply_readiness_impact": "blocked" if items else "clear",
        "open_decisions_or_confirmations_required": [item["repair_item_id"] for item in items if item.get("required_human_confirmation")],
        "knowledge_repair_plan_path": KNOWLEDGE_REPAIR_PLAN_JSON,
        "knowledge_repair_request_path": KNOWLEDGE_REPAIR_REQUEST_JSON,
        "limitations": ["pending candidates are not repaired until matching repair result and QA evidence exist"],
    }


def _clear_completed_items(items: list[dict[str, Any]], artifacts: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results = artifacts["repair-result.json"].get("results", [])
    current_hashes = _current_target_hashes(
        sorted({segment for item in items for segment in item.get("affected_segment_ids", [])}), artifacts["generated-segments.jsonl"]
    )
    active, cleared = [], []
    for item in items:
        match = next((result for result in results if _result_matches(item, result, current_hashes)), None)
        if match:
            cleared.append({**item, "cleared_by_repair_result": str(match.get("repair_id") or match.get("request_id") or "")})
        else:
            active.append(item)
    return active, cleared


def _result_matches(item: dict[str, Any], result: dict[str, Any], current_hashes: dict[str, str]) -> bool:
    if not isinstance(result, dict) or str(result.get("repair_status") or result.get("status") or "") not in {"applied", "completed", "pass"}:
        return False
    segment_ids = item.get("affected_segment_ids", [])
    if not segment_ids or str(result.get("segment_id") or "") not in segment_ids:
        return False
    current_hash = current_hashes.get(str(result.get("segment_id") or ""))
    if not current_hash or str(result.get("new_target_hash") or "") != current_hash:
        return False
    qa = result.get("qa") if isinstance(result.get("qa"), dict) else result.get("qa_result") if isinstance(result.get("qa_result"), dict) else {}
    return str(qa.get("status") or "") in {"pass", "pass_with_warnings"} and bool(
        result.get("knowledge_repair_item_id") == item.get("repair_item_id")
        or set(_strings(result.get("source_knowledge_item_ids"))).intersection(item.get("source_knowledge_item_ids", []))
    )


def _matching_queue_item(queue: dict[str, Any], issue: dict[str, Any]) -> dict[str, Any] | None:
    for item in queue.get("items", []):
        if not isinstance(item, dict):
            continue
        if issue.get("related_constraint_id") and item.get("related_constraint_id") == issue.get("related_constraint_id"):
            return item
        if issue.get("related_conflict_id") and item.get("related_conflict_id") == issue.get("related_conflict_id"):
            return item
        if item.get("item_type") == issue.get("issue_type"):
            return item
    return None


def _knowledge_entry(ids: list[str], context: dict[str, Any]) -> dict[str, Any]:
    for group in ("hard_constraints", "negative_constraints", "tm_suggestions", "retrieved_examples", "excluded_knowledge"):
        for item in context.get(group, []):
            if isinstance(item, dict) and str(item.get("knowledge_id") or item.get("source_knowledge_item_id") or "") in ids:
                return item
    return {}


def _approved_replacement(knowledge: dict[str, Any], context: dict[str, Any]) -> str | None:
    source = str(knowledge.get("source_value") or "")
    forbidden = str(knowledge.get("target_value") or "")
    matches = {
        str(item.get("target_value") or "")
        for item in context.get("hard_constraints", [])
        if isinstance(item, dict)
        and str(item.get("source_value") or "") == source
        and str(item.get("target_value") or "")
        and str(item.get("target_value") or "") != forbidden
    }
    return next(iter(matches)) if len(matches) == 1 else None


def _current_target_hashes(segment_ids: list[str], generated: list[dict[str, Any]]) -> dict[str, str]:
    requested = set(segment_ids)
    return {
        str(item.get("segment_id")): hashlib.sha256(str(item.get("target") or "").encode("utf-8")).hexdigest()
        for item in generated
        if isinstance(item, dict) and str(item.get("segment_id") or "") in requested and item.get("target") is not None
    }


def _allowed_modes(item: dict[str, Any]) -> list[str]:
    if item.get("deterministic_eligibility"):
        return ["deterministic_local_patch", "human_review"]
    if item.get("repair_action") in HUMAN_ACTIONS:
        return ["human_review"]
    if item.get("repair_action") in MODEL_ACTIONS:
        return ["human_review", "provider_or_model_pending"]
    return []


def _blocked_modes(item: dict[str, Any]) -> list[str]:
    blocked = ["automatic_semantic_rewrite"]
    if item.get("repair_action") in BLOCKING_ACTIONS or item.get("issue_type") == "blind_benchmark_firewall_violation":
        blocked.extend(["provider_repair", "model_repair"])
    if item.get("issue_type") == "reference_only_leakage":
        blocked.append("automatic_hard_constraint_repair")
    return blocked


def _downstream_refresh(segment_ids: list[str]) -> list[str]:
    base = [
        "constraint-application-audit.json",
        "knowledge-usage-report.json",
        "knowledge-audit-enforcement-decision.json",
        "knowledge-assurance-summary.json",
        "evaluation-scorecard.json",
        "signoff-record.json",
        "delivery-decision.json",
        "artifact-state.json",
    ]
    return ["generated-segments.jsonl", *base] if segment_ids else base


def _item_forbidden_claims(issue_type: str) -> list[str]:
    claims = {"knowledge_constraints_applied", "knowledge_review_complete", "review_complete", "delivery_ready", "apply_ready", "production_ready"}
    if issue_type in {"reference_only_leakage", "stale_knowledge_used", "raw_candidate_knowledge_used"}:
        claims.add("knowledge_backed_quality")
    return sorted(claims)


def _forbidden_claims(items: list[dict[str, Any]]) -> list[str]:
    return sorted({claim for item in items for claim in item.get("forbidden_claims_affected", [])})


def _plan_summary(items: list[dict[str, Any]], cleared: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "repair_item_count": len(items),
        "deterministic_candidate_count": sum(bool(item.get("deterministic_eligibility")) for item in items),
        "human_required_count": sum(item.get("repair_action") in HUMAN_ACTIONS for item in items),
        "provider_model_pending_count": sum(item.get("repair_action") in MODEL_ACTIONS for item in items),
        "blocked_count": sum(item.get("repair_action") in BLOCKING_ACTIONS for item in items),
        "cleared_count": len(cleared),
    }


def _plan_status(items: list[dict[str, Any]]) -> str:
    if any(item.get("repair_action") in BLOCKING_ACTIONS or item.get("issue_type") == "blind_benchmark_firewall_violation" for item in items):
        return "blocked"
    return "repair_required" if items else "clear"


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return list({str(item["repair_item_id"]): item for item in items}.values())


def _presence(value: Any) -> str:
    return "available" if value else "missing"


def _source_artifact_map(state_dir: Path) -> dict[str, str]:
    return {Path(name).stem.replace("-", "_"): name for name in SOURCE_ARTIFACTS if (state_dir / name).is_file()}


def _read_optional(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    if path.suffix == ".jsonl":
        return {"items": read_jsonl(path)}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _read_jsonl_optional(path: Path) -> list[dict[str, Any]]:
    return [item for item in read_jsonl(path) if isinstance(item, dict)] if path.is_file() else []


def _read_required(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing knowledge repair artifact: {path}")
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Knowledge repair artifact must be a JSON object: {path}")
    return value


def _stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in {None, ""}]
    return [str(value)] if value not in {None, ""} else []
