from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from . import PROTOCOL_VERSION
from .io_utils import read_json, sha256_file, write_json
from .knowledge_repair import KNOWLEDGE_REPAIR_IMPACT_REPORT_JSON, KNOWLEDGE_REPAIR_PLAN_JSON, KNOWLEDGE_REPAIR_REQUEST_JSON
from .knowledge_repair_result import (
    KNOWLEDGE_REPAIR_QA_REPORT_JSON,
    KNOWLEDGE_REPAIR_RECONCILIATION_JSON,
    KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL,
)


KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON = "knowledge-repair-closure-decision.json"
KNOWLEDGE_RECOMPUTE_PLAN_JSON = "knowledge-recompute-plan.json"
KNOWLEDGE_RECOMPUTE_RESULT_JSON = "knowledge-recompute-result.json"
KNOWLEDGE_READINESS_IMPACT_REPORT_JSON = "knowledge-readiness-impact-report.json"

DOWNSTREAM_TARGETS = (
    "constraint-application-audit.json",
    "knowledge-usage-report.json",
    "knowledge-conflict-report.json",
    "knowledge-audit-enforcement-decision.json",
    "knowledge-conflict-resolution.json",
    "knowledge-assurance-summary.json",
    "workbench-knowledge-review-queue.json",
    "evaluation-scorecard.json",
    "artifact-state.json",
    "claim-acceptance-decision.json",
    "signoff-record.json",
    "delivery-decision.json",
    "run-summary.json",
    "delivery-package-metadata",
)

MANUAL_TARGETS = {"claim-acceptance-decision.json", "signoff-record.json", "delivery-decision.json", "run-summary.json", "delivery-package-metadata"}
BLOCKING_CLOSURE_STATUSES = {"partially_closed", "still_blocked", "requires_recompute", "requires_human_review", "stale"}


def build_knowledge_recompute_plan(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    reconciliation = _read_optional_json(state_dir / KNOWLEDGE_REPAIR_RECONCILIATION_JSON)
    qa = _read_optional_json(state_dir / KNOWLEDGE_REPAIR_QA_REPORT_JSON)
    items = []
    blockers = _reconciliation_blockers(reconciliation)
    source_blocker_ids = [str(item.get("blocker_id") or "") for item in blockers] or ["knowledge-repair-reconciliation"]
    for order, target in enumerate(DOWNSTREAM_TARGETS, 1):
        deterministic = target not in MANUAL_TARGETS
        items.append(
            {
                "recompute_item_id": _stable_id("knowledge-recompute", [target, source_blocker_ids, order]),
                "source_blocker_ids": source_blocker_ids,
                "source_repair_result_ids": _matching_result_ids(blockers),
                "source_qa_item_ids": _qa_item_ids(qa),
                "source_reconciliation_id": KNOWLEDGE_REPAIR_RECONCILIATION_JSON if reconciliation else None,
                "target_artifact": target,
                "recompute_reason": _recompute_reason(target, reconciliation),
                "dependency_artifacts": _dependencies_for_target(target),
                "required_order": order,
                "status": "pending" if reconciliation else "blocked",
                "blocking_effect_if_not_recomputed": _blocking_effect(target),
                "deterministic": deterministic,
                "human_review_required": not deterministic,
            }
        )
    plan = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-recompute-plan-v1",
        "artifact": KNOWLEDGE_RECOMPUTE_PLAN_JSON,
        "status": "ready" if reconciliation else "blocked",
        "summary": {
            "recompute_item_count": len(items),
            "deterministic_item_count": sum(bool(item["deterministic"]) for item in items),
            "human_review_required_count": sum(bool(item["human_review_required"]) for item in items),
            "source_blocker_count": len(blockers),
        },
        "recompute_items": items,
        "source_artifacts": _source_artifacts(
            state_dir,
            [
                KNOWLEDGE_REPAIR_PLAN_JSON,
                KNOWLEDGE_REPAIR_REQUEST_JSON,
                KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL,
                KNOWLEDGE_REPAIR_QA_REPORT_JSON,
                KNOWLEDGE_REPAIR_RECONCILIATION_JSON,
            ],
        ),
        "limitations": [
            "recompute planning does not clear repair blockers",
            "manual claim acceptance, signoff, delivery package, and apply authorization are never rewritten automatically",
            "provider/model generation and semantic repair execution are out of scope",
        ],
    }
    if write:
        write_json(state_dir / KNOWLEDGE_RECOMPUTE_PLAN_JSON, plan)
    return plan


def read_knowledge_recompute_plan(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / KNOWLEDGE_RECOMPUTE_PLAN_JSON)


def build_knowledge_recompute_result(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    plan = build_knowledge_recompute_plan(state_dir, write=write)
    attempted = []
    for item in plan.get("recompute_items", []):
        if not isinstance(item, dict):
            continue
        attempted.append(_run_recompute_item(state_dir, item))
    summary = {
        "attempted_count": len(attempted),
        "completed_count": sum(item["status"] == "completed" for item in attempted),
        "skipped_count": sum(item["status"].startswith("skipped") for item in attempted),
        "failed_count": sum(item["status"] == "failed" for item in attempted),
        "blocked_count": sum(item["status"] == "blocked" for item in attempted),
        "human_review_required_count": sum(item["status"] == "requires_human_review" for item in attempted),
    }
    status = "failed" if summary["failed_count"] else "blocked" if summary["blocked_count"] else "partial" if summary["human_review_required_count"] else "completed"
    result = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-recompute-result-v1",
        "artifact": KNOWLEDGE_RECOMPUTE_RESULT_JSON,
        "status": status,
        "recompute_plan_id": KNOWLEDGE_RECOMPUTE_PLAN_JSON,
        "recompute_items_attempted": attempted,
        "recompute_items_completed": [item for item in attempted if item["status"] == "completed"],
        "recompute_items_skipped": [item for item in attempted if item["status"].startswith("skipped")],
        "recompute_items_failed": [item for item in attempted if item["status"] == "failed"],
        "recompute_items_requiring_human_review": [item for item in attempted if item["status"] == "requires_human_review"],
        "target_artifacts_refreshed": [item["target_artifact"] for item in attempted if item["status"] == "completed"],
        "remaining_stale_artifacts": _remaining_stale_artifacts(state_dir),
        "remaining_blockers": _remaining_repair_blockers(state_dir),
        "readiness_impact": _recompute_readiness_impact(status, summary),
        "source_artifacts": _source_artifacts(state_dir, [KNOWLEDGE_RECOMPUTE_PLAN_JSON, KNOWLEDGE_REPAIR_RECONCILIATION_JSON, KNOWLEDGE_REPAIR_QA_REPORT_JSON]),
        "limitations": [
            "recompute result records deterministic refresh attempts only",
            "recompute does not call providers, apply repairs, or execute semantic rewrites",
            "human-owned claim acceptance, signoff, delivery package metadata, and apply authorization remain explicit follow-up",
        ],
    }
    if write:
        write_json(state_dir / KNOWLEDGE_RECOMPUTE_RESULT_JSON, result)
    return result


def read_knowledge_recompute_result(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / KNOWLEDGE_RECOMPUTE_RESULT_JSON)


def build_knowledge_repair_closure_decision(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    artifacts = _load_closure_artifacts(state_dir)
    status = _closure_status(artifacts)
    cleared = _cleared_blockers(artifacts["reconciliation"])
    still_blocked = _active_blockers(artifacts["reconciliation"])
    decision = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-repair-closure-decision-v1",
        "artifact": KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON,
        "status": status,
        "repair_plan_status": _status(artifacts["plan"], "not_run"),
        "repair_request_status": _status(artifacts["request"], "not_run"),
        "result_intake_status": "provided" if (state_dir / KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL).is_file() else "not_provided",
        "qa_report_status": _status(artifacts["qa"], "not_run"),
        "reconciliation_status": _status(artifacts["reconciliation"], "not_run"),
        "cleared_blockers": cleared,
        "partially_cleared_blockers": _blockers_with_status(artifacts["reconciliation"], {"partially_cleared"}),
        "still_blocked_items": still_blocked,
        "stale_results": _blockers_with_status(artifacts["reconciliation"], {"stale_result"}),
        "unresolved_conflicts": _unresolved_conflicts(artifacts["reconciliation"]),
        "human_review_required_items": _blockers_with_status(artifacts["reconciliation"], {"requires_human_review"}),
        "required_recomputation": _required_recomputation(artifacts["recompute_plan"], artifacts["recompute_result"]),
        "downstream_readiness_impact": _closure_readiness_impact(status),
        "forbidden_claims_remaining": _closure_forbidden_claims(status, artifacts),
        "final_closure_status": status,
        "source_artifacts": _source_artifacts(
            state_dir,
            [
                KNOWLEDGE_REPAIR_PLAN_JSON,
                KNOWLEDGE_REPAIR_REQUEST_JSON,
                KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL,
                KNOWLEDGE_REPAIR_QA_REPORT_JSON,
                KNOWLEDGE_REPAIR_RECONCILIATION_JSON,
                KNOWLEDGE_RECOMPUTE_PLAN_JSON,
                KNOWLEDGE_RECOMPUTE_RESULT_JSON,
            ],
        ),
        "limitations": _closure_limitations(status),
    }
    if write:
        write_json(state_dir / KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON, decision)
    return decision


def read_knowledge_repair_closure_decision(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON)


def build_knowledge_readiness_impact_report(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    closure = build_knowledge_repair_closure_decision(state_dir, write=write)
    scorecard = _read_optional_json(state_dir / "evaluation-scorecard.json")
    claim = _read_optional_json(state_dir / "claim-acceptance-decision.json")
    signoff = _read_optional_json(state_dir / "signoff-record.json")
    before_forbidden = _strings(_read_optional_json(state_dir / KNOWLEDGE_REPAIR_RECONCILIATION_JSON).get("forbidden_claims_remaining"))
    after_forbidden = _strings(scorecard.get("forbidden_claims")) or closure.get("forbidden_claims_remaining", [])
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-readiness-impact-report-v1",
        "artifact": KNOWLEDGE_READINESS_IMPACT_REPORT_JSON,
        "status": "blocked" if closure.get("status") in BLOCKING_CLOSURE_STATUSES else "clear_with_warnings" if closure.get("status") == "closed_with_warnings" else "clear" if closure.get("status") == "closed" else "not_applicable",
        "before": {
            "blocker_count": len(_remaining_repair_blockers(state_dir)),
            "forbidden_claims": before_forbidden,
            "scorecard_overall_claim": "unknown",
        },
        "after": {
            "blocker_count": len(closure.get("still_blocked_items", [])),
            "forbidden_claims": after_forbidden,
            "scorecard_overall_claim": scorecard.get("overall_claim", "not_checked"),
        },
        "delivery_apply_readiness_impact": closure.get("downstream_readiness_impact", {}),
        "signoff_staleness_impact": _manual_artifact_impact(signoff, closure, "signoff"),
        "claim_acceptance_staleness_impact": _manual_artifact_impact(claim, closure, "claim_acceptance"),
        "remaining_review_requirements": closure.get("human_review_required_items", []),
        "remaining_repair_requirements": closure.get("still_blocked_items", []),
        "remaining_knowledge_conflicts": closure.get("unresolved_conflicts", []),
        "limitations": closure.get("limitations", []),
        "recommended_next_actions": _impact_next_actions(closure),
        "source_artifacts": _source_artifacts(
            state_dir,
            [KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON, KNOWLEDGE_RECOMPUTE_RESULT_JSON, "evaluation-scorecard.json", "claim-acceptance-decision.json", "signoff-record.json"],
        ),
    }
    if write:
        write_json(state_dir / KNOWLEDGE_READINESS_IMPACT_REPORT_JSON, report)
    return report


def read_knowledge_readiness_impact_report(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / KNOWLEDGE_READINESS_IMPACT_REPORT_JSON)


def knowledge_repair_closure_asset_paths(state_dir: Path) -> dict[str, str]:
    return {
        key: name
        for key, name in (
            ("knowledge_repair_closure_decision", KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON),
            ("knowledge_recompute_plan", KNOWLEDGE_RECOMPUTE_PLAN_JSON),
            ("knowledge_recompute_result", KNOWLEDGE_RECOMPUTE_RESULT_JSON),
            ("knowledge_readiness_impact_report", KNOWLEDGE_READINESS_IMPACT_REPORT_JSON),
        )
        if (state_dir / name).is_file()
    }


def knowledge_repair_closure_summary(state_dir: Path) -> dict[str, Any]:
    path = state_dir / KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON
    if not path.is_file():
        return {"status": "not_run", "forbidden_claims_remaining": [], "required_recompute_count": 0}
    value = read_json(path)
    return {
        "status": value.get("status", "unknown"),
        "forbidden_claims_remaining": value.get("forbidden_claims_remaining", []),
        "required_recompute_count": len(value.get("required_recomputation", [])),
    }


def _run_recompute_item(state_dir: Path, item: dict[str, Any]) -> dict[str, Any]:
    target = str(item.get("target_artifact") or "")
    before = _artifact_hash(state_dir / target)
    result = {
        "recompute_item_id": item.get("recompute_item_id"),
        "target_artifact": target,
        "dependency_artifacts": item.get("dependency_artifacts", []),
        "blocking_effect_if_not_recomputed": item.get("blocking_effect_if_not_recomputed", "unknown"),
        "target_hash_before": before,
        "target_hash_after": before,
        "status": "not_applicable",
        "reason": "",
        "provider_or_model_called": False,
        "repair_applied": False,
    }
    if target in MANUAL_TARGETS:
        result.update({"status": "requires_human_review", "reason": "target is human-owned or delivery-context-specific and is not rewritten by deterministic recompute"})
        return result
    builder = _deterministic_builders().get(target)
    if builder is None:
        result.update({"status": "skipped_not_needed", "reason": "no deterministic builder is registered for this target"})
        return result
    try:
        builder(state_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.update({"status": "failed", "reason": str(exc)})
        return result
    result.update({"status": "completed", "reason": "deterministic artifact refreshed", "target_hash_after": _artifact_hash(state_dir / target)})
    return result


def _deterministic_builders() -> dict[str, Callable[[Path], Any]]:
    from .artifact_state import build_artifact_state
    from .evaluation import build_evaluation_scorecard
    from .knowledge_audit_enforcement import build_knowledge_audit_enforcement_decision, build_workbench_knowledge_review_queue
    from .knowledge_review_confirmation import build_knowledge_assurance_summary, build_knowledge_conflict_resolution
    from .knowledge_usage import build_constraint_application_audit, build_knowledge_conflict_report, build_knowledge_usage_report

    return {
        "constraint-application-audit.json": build_constraint_application_audit,
        "knowledge-usage-report.json": build_knowledge_usage_report,
        "knowledge-conflict-report.json": build_knowledge_conflict_report,
        "knowledge-audit-enforcement-decision.json": build_knowledge_audit_enforcement_decision,
        "knowledge-conflict-resolution.json": build_knowledge_conflict_resolution,
        "knowledge-assurance-summary.json": build_knowledge_assurance_summary,
        "workbench-knowledge-review-queue.json": build_workbench_knowledge_review_queue,
        "evaluation-scorecard.json": build_evaluation_scorecard,
        "artifact-state.json": build_artifact_state,
    }


def _closure_status(artifacts: dict[str, Any]) -> str:
    reconciliation = artifacts["reconciliation"]
    qa = artifacts["qa"]
    recompute = artifacts["recompute_result"]
    if not artifacts["plan"] and not reconciliation:
        return "not_applicable"
    if _artifact_state_status(artifacts["artifact_state"], "knowledge_repair_reconciliation") == "stale":
        return "stale"
    if str(reconciliation.get("status") or "") == "stale" or _summary_int(reconciliation, "stale_result_count"):
        return "stale"
    if str(qa.get("status") or "") in {"blocked", "failed"} or _summary_int(reconciliation, "failed_qa_count"):
        return "still_blocked"
    if _summary_int(reconciliation, "human_review_required_count"):
        return "requires_human_review"
    if str(reconciliation.get("status") or "") == "partial":
        return "partially_closed"
    if str(reconciliation.get("status") or "") == "blocked":
        return "still_blocked"
    if str(reconciliation.get("status") or "") != "clear":
        return "requires_recompute"
    if not recompute:
        return "requires_recompute"
    if str(recompute.get("status") or "") in {"failed", "blocked"}:
        return "partially_closed"
    if str(recompute.get("status") or "") == "completed":
        return "closed"
    if str(recompute.get("status") or "") == "partial":
        return "closed_with_warnings"
    return "requires_recompute"


def _load_closure_artifacts(state_dir: Path) -> dict[str, Any]:
    return {
        "plan": _read_optional_json(state_dir / KNOWLEDGE_REPAIR_PLAN_JSON),
        "request": _read_optional_json(state_dir / KNOWLEDGE_REPAIR_REQUEST_JSON),
        "qa": _read_optional_json(state_dir / KNOWLEDGE_REPAIR_QA_REPORT_JSON),
        "reconciliation": _read_optional_json(state_dir / KNOWLEDGE_REPAIR_RECONCILIATION_JSON),
        "recompute_plan": _read_optional_json(state_dir / KNOWLEDGE_RECOMPUTE_PLAN_JSON),
        "recompute_result": _read_optional_json(state_dir / KNOWLEDGE_RECOMPUTE_RESULT_JSON),
        "artifact_state": _read_optional_json(state_dir / "artifact-state.json"),
    }


def _read_required(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing knowledge repair closure artifact: {path}")
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Knowledge repair closure artifact is not a JSON object: {path}")
    return value


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _artifact_hash(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() and path.name != "delivery-package-metadata" else None


def _source_artifacts(state_dir: Path, names: list[str]) -> dict[str, dict[str, str]]:
    refs = {}
    for name in names:
        path = state_dir / name
        if path.is_file():
            refs[name.replace("-", "_").replace(".", "_")] = {"path": name, "sha256": sha256_file(path)}
    return refs


def _status(value: dict[str, Any], missing: str) -> str:
    return str(value.get("status") or missing) if value else missing


def _summary_int(value: dict[str, Any], key: str) -> int:
    return int(value.get("summary", {}).get(key, 0) or 0) if isinstance(value, dict) else 0


def _reconciliation_blockers(reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in reconciliation.get("blockers", []) if isinstance(item, dict)]


def _blockers_with_status(reconciliation: dict[str, Any], statuses: set[str]) -> list[dict[str, Any]]:
    return [item for item in _reconciliation_blockers(reconciliation) if str(item.get("reconciliation_status") or "") in statuses]


def _cleared_blockers(reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    return _blockers_with_status(reconciliation, {"cleared"})


def _active_blockers(reconciliation: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _reconciliation_blockers(reconciliation) if str(item.get("reconciliation_status") or "") != "cleared"]


def _unresolved_conflicts(reconciliation: dict[str, Any]) -> list[str]:
    conflicts = []
    for item in _active_blockers(reconciliation):
        conflicts.extend(_strings(item.get("remaining_conflicts")))
    return sorted(set(conflicts))


def _matching_result_ids(blockers: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for item in blockers:
        ids.extend(_strings(item.get("matching_result_ids")))
    return sorted(set(ids))


def _qa_item_ids(qa: dict[str, Any]) -> list[str]:
    return sorted({str(item.get("qa_item_id")) for item in qa.get("qa_items", []) if isinstance(item, dict) and item.get("qa_item_id")})


def _dependencies_for_target(target: str) -> list[str]:
    base = [KNOWLEDGE_REPAIR_RECONCILIATION_JSON, KNOWLEDGE_REPAIR_QA_REPORT_JSON]
    mapping = {
        "constraint-application-audit.json": ["generated-segments.jsonl", "working-context-packet.json"],
        "knowledge-audit-enforcement-decision.json": ["constraint-application-audit.json", "knowledge-conflict-report.json", "knowledge-usage-report.json"],
        "knowledge-assurance-summary.json": ["knowledge-audit-enforcement-decision.json", "knowledge-constraint-review-evidence.jsonl"],
        "evaluation-scorecard.json": ["knowledge-assurance-summary.json", KNOWLEDGE_REPAIR_CLOSURE_DECISION_JSON],
        "claim-acceptance-decision.json": ["evaluation-scorecard.json"],
        "signoff-record.json": ["evaluation-scorecard.json", "claim-acceptance-decision.json"],
        "delivery-decision.json": ["evaluation-scorecard.json", "signoff-record.json"],
    }
    return list(dict.fromkeys(base + mapping.get(target, [])))


def _recompute_reason(target: str, reconciliation: dict[str, Any]) -> str:
    if not reconciliation:
        return "repair reconciliation is missing"
    return f"{target} must be refreshed after knowledge repair reconciliation status {reconciliation.get('status', 'unknown')}"


def _blocking_effect(target: str) -> str:
    if target in {"claim-acceptance-decision.json", "signoff-record.json", "delivery-decision.json"}:
        return "manual authorization remains stale or blocked"
    if target == "evaluation-scorecard.json":
        return "scorecard cannot narrow repair blockers"
    if target == "artifact-state.json":
        return "stale evidence cannot be surfaced reliably"
    return "knowledge repair closure cannot support downstream readiness"


def _required_recomputation(plan: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    if not plan:
        return [
            {
                "target_artifact": target,
                "current_status": "pending",
                "deterministic": target not in MANUAL_TARGETS,
                "human_review_required": target in MANUAL_TARGETS,
                "blocking_effect_if_not_recomputed": _blocking_effect(target),
            }
            for target in DOWNSTREAM_TARGETS
        ]
    result_status = {str(item.get("target_artifact") or ""): str(item.get("status") or "") for item in result.get("recompute_items_attempted", []) if isinstance(item, dict)}
    required = []
    for item in plan.get("recompute_items", []):
        if not isinstance(item, dict):
            continue
        status = result_status.get(str(item.get("target_artifact") or ""), item.get("status", "pending"))
        if status not in {"completed", "skipped_not_needed"}:
            required.append({**item, "current_status": status})
    return required


def _remaining_repair_blockers(state_dir: Path) -> list[dict[str, Any]]:
    reconciliation = _read_optional_json(state_dir / KNOWLEDGE_REPAIR_RECONCILIATION_JSON)
    return _active_blockers(reconciliation)


def _remaining_stale_artifacts(state_dir: Path) -> list[str]:
    artifact_state = _read_optional_json(state_dir / "artifact-state.json")
    return sorted(
        str(item.get("artifact_id"))
        for item in artifact_state.get("artifacts", [])
        if isinstance(item, dict) and item.get("status") == "stale" and item.get("artifact_id")
    )


def _artifact_state_status(artifact_state: dict[str, Any], artifact_id: str) -> str:
    for item in artifact_state.get("artifacts", []):
        if isinstance(item, dict) and item.get("artifact_id") == artifact_id:
            return str(item.get("status") or "")
    return ""


def _recompute_readiness_impact(status: str, summary: dict[str, int]) -> dict[str, str]:
    if status == "completed":
        return {"scorecard": "may_recompute", "delivery": "manual_authorization_still_required", "apply": "manual_authorization_still_required"}
    if summary.get("failed_count") or summary.get("blocked_count"):
        return {"scorecard": "blocked", "delivery": "blocked", "apply": "blocked"}
    return {"scorecard": "limited", "delivery": "review_required", "apply": "review_required"}


def _closure_readiness_impact(status: str) -> dict[str, str]:
    if status == "closed":
        return {"generation_handoff": "may_continue_if_other_gates_clear", "delivery": "may_recompute_if_other_gates_clear", "apply": "may_recompute_if_other_gates_clear"}
    if status == "closed_with_warnings":
        return {"generation_handoff": "allowed_with_warnings", "delivery": "review_required", "apply": "review_required"}
    if status == "not_applicable":
        return {"generation_handoff": "not_applicable", "delivery": "not_applicable", "apply": "not_applicable"}
    return {"generation_handoff": "blocked_or_downgraded", "delivery": "blocked", "apply": "blocked"}


def _closure_forbidden_claims(status: str, artifacts: dict[str, Any]) -> list[str]:
    claims = set(_strings(artifacts["reconciliation"].get("forbidden_claims_remaining")))
    if status in BLOCKING_CLOSURE_STATUSES:
        claims.update({"knowledge_constraints_applied", "knowledge_review_complete", "delivery_ready", "apply_ready", "production_ready"})
    if status != "closed":
        claims.add("knowledge_backed_quality")
    if status in {"requires_human_review", "partially_closed", "still_blocked"}:
        claims.add("review_complete")
    return sorted(claims)


def _closure_limitations(status: str) -> list[str]:
    limitations = [
        "closure is computed from artifact evidence and does not apply repairs",
        "QA-passed repair evidence does not by itself authorize delivery or apply",
        "claim acceptance and signoff remain explicit human-owned artifacts",
    ]
    if status != "closed":
        limitations.append("strong readiness claims remain forbidden until recomputation and required review are complete")
    return limitations


def _manual_artifact_impact(value: dict[str, Any], closure: dict[str, Any], label: str) -> str:
    if not value:
        return f"{label}_missing"
    if closure.get("status") in {"closed", "closed_with_warnings"}:
        return f"{label}_requires_reconfirmation_if_claim_basis_changed"
    return f"{label}_cannot_support_closure"


def _impact_next_actions(closure: dict[str, Any]) -> list[str]:
    status = str(closure.get("status") or "")
    if status == "requires_recompute":
        return ["Run knowledge-repair-recompute, then refresh scorecard and authorization artifacts."]
    if status == "requires_human_review":
        return ["Record scoped human review evidence for semantic or high-risk knowledge repair items."]
    if status in {"still_blocked", "partially_closed", "stale"}:
        return ["Resolve remaining repair blockers or stale reconciliation evidence before delivery/apply authorization."]
    if status == "closed_with_warnings":
        return ["Renew claim acceptance and signoff with limitations preserved before delivery/apply."]
    if status == "closed":
        return ["Refresh or renew claim acceptance, signoff, delivery, and apply decisions as required by current scorecard."]
    return ["No knowledge repair closure action is required."]


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    return [str(value)]


def _stable_id(prefix: str, parts: list[Any]) -> str:
    import hashlib
    import json

    payload = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return f"{prefix}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"
