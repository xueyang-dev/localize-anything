from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json, write_jsonl


KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL = "knowledge-repair-result-intake.jsonl"
KNOWLEDGE_REPAIR_QA_REPORT_JSON = "knowledge-repair-qa-report.json"
KNOWLEDGE_REPAIR_RECONCILIATION_JSON = "knowledge-repair-reconciliation.json"

RESULT_SOURCES = {
    "manual_repair",
    "deterministic_local_patch",
    "external_provider_result",
    "external_model_result",
    "reviewer_edit",
    "imported_patch",
    "unknown",
}
REPAIR_MODES = {
    "term_patch",
    "forbidden_translation_patch",
    "human_rewrite",
    "provider_repair",
    "model_repair",
    "regenerate_with_constraints",
    "scope_limit",
    "no_change_accepted",
    "not_applicable",
}
INTAKE_STATUSES = {
    "received",
    "accepted_for_qa",
    "rejected_shape",
    "rejected_stale",
    "rejected_provenance",
    "requires_follow_up",
}
SEMANTIC_MODES = {"human_rewrite", "provider_repair", "model_repair", "regenerate_with_constraints", "no_change_accepted"}
QA_BLOCKING = {"failed", "stale", "blocked"}

_PLACEHOLDER = re.compile(r"(?:\{[A-Za-z_][A-Za-z0-9_.-]*\}|%\d*\$?[A-Za-z]|\$\{[^}]+\})")
_MARKUP = re.compile(r"</?([A-Za-z][A-Za-z0-9:_-]*)\b[^>]*>")
_ESCAPE = re.compile(r"(?:\\[nrt'\"]|%%|&(?:amp|lt|gt|quot|apos);)")


def record_knowledge_repair_result(
    state_dir: Path,
    result: dict[str, Any],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    record = _normalize_intake(state_dir, result, run_id=run_id)
    records = read_knowledge_repair_result_intake(state_dir)
    records.append(record)
    write_jsonl(state_dir / KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL, records)
    build_knowledge_repair_reconciliation(state_dir)
    return record


def read_knowledge_repair_result_intake(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL
    return read_jsonl(path) if path.is_file() else []


def build_knowledge_repair_qa_report(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    artifacts = _load_artifacts(state_dir)
    requests = _requests_by_id(artifacts["knowledge-repair-request.json"])
    plan_items = _plan_items_by_id(artifacts["knowledge-repair-plan.json"])
    generated = _generated_by_id(artifacts["generated-segments.jsonl"])
    qa_items: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for record in artifacts[KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL]:
        request = requests.get(str(record.get("source_repair_request_id") or ""), {})
        plan_item = plan_items.get(str(record.get("source_repair_plan_item_id") or request.get("knowledge_repair_item_id") or ""), {})
        checks = _qa_checks(record, request, plan_item, generated, artifacts)
        qa_items.extend(checks)
        status = _qa_result_status(checks)
        results.append(
            {
                "result_id": record.get("result_id"),
                "repair_request_id": record.get("source_repair_request_id"),
                "status": status,
                "blocking_check_count": sum(bool(item.get("blocking")) and item.get("status") not in {"passed", "not_applicable"} for item in checks),
                "failed_check_types": [item["check_type"] for item in checks if item.get("status") in QA_BLOCKING],
                "requires_human_review": any(item.get("status") == "requires_human_review" for item in checks),
            }
        )
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-repair-qa-report-v1",
        "artifact": KNOWLEDGE_REPAIR_QA_REPORT_JSON,
        "status": _qa_report_status(results),
        "summary": {
            "result_count": len(results),
            "qa_item_count": len(qa_items),
            "passed_result_count": sum(item["status"] == "passed" for item in results),
            "failed_result_count": sum(item["status"] in QA_BLOCKING for item in results),
            "human_review_required_count": sum(bool(item["requires_human_review"]) for item in results),
        },
        "results": results,
        "qa_items": qa_items,
        "source_artifacts": _source_artifacts(state_dir),
        "limitations": [
            "QA is deterministic and does not execute repair",
            "provider/model submissions remain external evidence",
            "passing QA does not by itself prove semantic quality or authorize delivery",
        ],
    }
    if write:
        write_json(state_dir / KNOWLEDGE_REPAIR_QA_REPORT_JSON, report)
    return report


def read_knowledge_repair_qa_report(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / KNOWLEDGE_REPAIR_QA_REPORT_JSON)


def build_knowledge_repair_reconciliation(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    artifacts = _load_artifacts(state_dir)
    qa = build_knowledge_repair_qa_report(state_dir, write=write)
    qa_by_result = {str(item.get("result_id") or ""): item for item in qa.get("results", []) if isinstance(item, dict)}
    intake_by_request: dict[str, list[dict[str, Any]]] = {}
    for record in artifacts[KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL]:
        intake_by_request.setdefault(str(record.get("source_repair_request_id") or ""), []).append(record)
    requests = _requests_by_id(artifacts["knowledge-repair-request.json"])
    reconciled: list[dict[str, Any]] = []
    for item in artifacts["knowledge-repair-plan.json"].get("repair_items", []):
        if not isinstance(item, dict):
            continue
        request = next(
            (request for request in requests.values() if request.get("knowledge_repair_item_id") == item.get("repair_item_id")),
            {},
        )
        matches = intake_by_request.get(str(request.get("request_id") or ""), [])
        reconciliation_status, result_ids, qa_status = _reconcile_item(item, request, matches, qa_by_result)
        cleared = reconciliation_status == "cleared"
        reconciled.append(
            {
                "blocker_id": item.get("repair_item_id"),
                "issue_type": item.get("issue_type"),
                "source_repair_request_id": request.get("request_id"),
                "matching_result_ids": result_ids,
                "qa_status": qa_status,
                "reconciliation_status": reconciliation_status,
                "cleared_constraints": [item.get("related_constraint_id")] if cleared and item.get("related_constraint_id") else [],
                "remaining_constraints": [] if cleared else [item.get("related_constraint_id")] if item.get("related_constraint_id") else [],
                "remaining_conflicts": [] if cleared else [item.get("related_conflict_id")] if item.get("related_conflict_id") else [],
                "stale_evidence": reconciliation_status == "stale_result",
                "required_follow_up": _reconciliation_follow_up(reconciliation_status),
                "readiness_impact": "clear" if cleared else "blocked",
                "affected_forbidden_claims": [] if cleared else item.get("forbidden_claims_affected", []),
                "source_artifact_references": list(
                    dict.fromkeys(
                        [
                            "knowledge-repair-plan.json",
                            "knowledge-repair-request.json",
                            KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL,
                            KNOWLEDGE_REPAIR_QA_REPORT_JSON,
                            *item.get("source_artifact_references", []),
                        ]
                    )
                ),
            }
        )
    summary = {
        "blocker_count": len(reconciled),
        "cleared_count": sum(item["reconciliation_status"] == "cleared" for item in reconciled),
        "partially_cleared_count": sum(item["reconciliation_status"] == "partially_cleared" for item in reconciled),
        "remaining_blocker_count": sum(item["reconciliation_status"] != "cleared" for item in reconciled),
        "failed_qa_count": sum(item["reconciliation_status"] == "failed_qa" for item in reconciled),
        "stale_result_count": sum(item["reconciliation_status"] == "stale_result" for item in reconciled),
        "human_review_required_count": sum(item["reconciliation_status"] == "requires_human_review" for item in reconciled),
    }
    status = "clear" if not summary["remaining_blocker_count"] else "partial" if summary["cleared_count"] else "blocked"
    reconciliation = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-repair-reconciliation-v1",
        "artifact": KNOWLEDGE_REPAIR_RECONCILIATION_JSON,
        "status": status,
        "summary": summary,
        "blockers": reconciled,
        "forbidden_claims_remaining": sorted(
            {claim for item in reconciled if item["reconciliation_status"] != "cleared" for claim in item.get("affected_forbidden_claims", [])}
        ),
        "recompute_required": [
            "knowledge-audit-enforcement-decision.json",
            "knowledge-assurance-summary.json",
            "evaluation-scorecard.json",
            "claim-acceptance-decision.json",
            "signoff-record.json",
            "delivery-decision.json",
            "artifact-state.json",
        ],
        "generic_repair_evidence": {
            "repair_result": "repair-result.json" if artifacts["repair-result.json"] else None,
            "repair_history": "repair-history.jsonl" if artifacts["repair-history.jsonl"] else None,
        },
        "source_artifacts": _source_artifacts(state_dir),
        "limitations": [
            "reconciliation does not apply patches or execute provider/model repair",
            "cleared deterministic blockers still require audit and readiness recomputation",
            "knowledge_backed_quality is not granted by repair QA",
        ],
    }
    if write:
        write_json(state_dir / KNOWLEDGE_REPAIR_RECONCILIATION_JSON, reconciliation)
    return reconciliation


def read_knowledge_repair_reconciliation(state_dir: Path) -> dict[str, Any]:
    return _read_required(state_dir / KNOWLEDGE_REPAIR_RECONCILIATION_JSON)


def knowledge_repair_result_asset_paths(state_dir: Path) -> dict[str, str]:
    return {
        key: name
        for key, name in (
            ("knowledge_repair_result_intake", KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL),
            ("knowledge_repair_qa_report", KNOWLEDGE_REPAIR_QA_REPORT_JSON),
            ("knowledge_repair_reconciliation", KNOWLEDGE_REPAIR_RECONCILIATION_JSON),
        )
        if (state_dir / name).is_file()
    }


def knowledge_repair_reconciliation_summary(state_dir: Path) -> dict[str, Any]:
    path = state_dir / KNOWLEDGE_REPAIR_RECONCILIATION_JSON
    if not path.is_file():
        return {"status": "not_run", "remaining_blocker_count": 0, "forbidden_claims_remaining": []}
    value = read_json(path)
    return {
        "status": value.get("status", "unknown"),
        "remaining_blocker_count": int(value.get("summary", {}).get("remaining_blocker_count", 0) or 0),
        "forbidden_claims_remaining": value.get("forbidden_claims_remaining", []),
    }


def _normalize_intake(state_dir: Path, result: dict[str, Any], *, run_id: str | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("knowledge repair result must be a JSON object")
    source = _enum(result, "result_source", RESULT_SOURCES, "unknown")
    mode = _enum(result, "repair_mode", REPAIR_MODES, "not_applicable")
    requests = _requests_by_id(_read_optional_json(state_dir / "knowledge-repair-request.json"))
    request_id = str(result.get("source_repair_request_id") or result.get("repair_request_id") or "")
    request = requests.get(request_id, {})
    plan_item_id = str(result.get("source_repair_plan_item_id") or request.get("knowledge_repair_item_id") or "")
    segment_ids = _strings(result.get("affected_segment_ids")) or _strings(request.get("affected_segment_ids"))
    scope = result.get("affected_scope") if isinstance(result.get("affected_scope"), dict) else request.get("affected_scope", {})
    text = result.get("repaired_target_text")
    text_valid = text is None or isinstance(text, str) and "\x00" not in text and len(text.encode("utf-8")) <= 1_000_000
    repaired_hash = str(result.get("repaired_target_hash") or "")
    if isinstance(text, str) and text_valid:
        calculated = _hash_text(text)
        if repaired_hash and repaired_hash != calculated:
            text_valid = False
        repaired_hash = calculated
    expected_hashes = request.get("current_target_hashes", {}) if isinstance(request.get("current_target_hashes"), dict) else {}
    submitted_hash = str(result.get("submitted_target_hash") or result.get("previous_target_hash") or "")
    expected = {str(value) for segment_id, value in expected_hashes.items() if not segment_ids or segment_id in segment_ids}
    provenance = _strings(result.get("provenance_references"))
    knowledge_ids = _strings(result.get("source_knowledge_item_ids"))
    expected_knowledge = set(request.get("source_knowledge_provenance", {}).get("knowledge_item_ids", []))
    status = "accepted_for_qa"
    limitations = _strings(result.get("limitations"))
    if not request or not segment_ids or not text_valid or not repaired_hash:
        status = "rejected_shape"
    elif expected and submitted_hash not in expected:
        status = "rejected_stale"
    elif not provenance or not knowledge_ids or not expected_knowledge.issubset(set(knowledge_ids)):
        status = "rejected_provenance"
    elif mode in SEMANTIC_MODES and not _human_review_exists(state_dir, segment_ids) and not bool(result.get("draft_or_review_only")):
        status = "requires_follow_up"
        limitations.append("semantic or high-risk repair requires scoped qualified human review evidence")
    identity = {key: value for key, value in result.items() if key not in {"result_id", "submitted_at", "status"}}
    record = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-knowledge-repair-result-intake-v1",
        "result_id": str(result.get("result_id") or _stable_id("knowledge-repair-result", identity)),
        "run_id": run_id or result.get("run_id"),
        "source_repair_request_id": request_id,
        "source_repair_plan_item_id": plan_item_id,
        "affected_segment_ids": segment_ids,
        "affected_scope": scope if isinstance(scope, dict) else {},
        "result_source": source,
        "actor_role": str(result.get("actor_role") or "unknown"),
        "actor_reference": str(result.get("actor_reference") or "unspecified"),
        "repair_mode": mode,
        "submitted_target_hash": submitted_hash,
        "previous_target_hash": str(result.get("previous_target_hash") or submitted_hash),
        "repaired_target_hash": repaired_hash,
        "source_knowledge_item_ids": knowledge_ids,
        "source_constraint_ids": _strings(result.get("source_constraint_ids")),
        "source_conflict_ids": _strings(result.get("source_conflict_ids")),
        "provenance_references": provenance,
        "claimed_fix_types": _strings(result.get("claimed_fix_types")) or [mode],
        "limitations": list(dict.fromkeys(limitations)),
        "submitted_at": str(result.get("submitted_at") or _now()),
        "status": status,
        "draft_or_review_only": bool(result.get("draft_or_review_only")),
        "system_provider_or_model_execution_performed": False,
    }
    if isinstance(text, str) and text_valid:
        record["repaired_target_text"] = text
    return record


def _qa_checks(
    record: dict[str, Any],
    request: dict[str, Any],
    plan_item: dict[str, Any],
    generated: dict[str, dict[str, Any]],
    artifacts: dict[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    add = lambda check_type, status, reason, blocking=True, limitations=None: checks.append(
        _qa_item(record, check_type, status, reason, blocking=blocking, limitations=limitations)
    )
    if record.get("status") == "rejected_shape":
        add("request_id_match", "blocked", "intake shape or request reference is invalid")
        return checks
    request_matches = bool(request) and str(record.get("source_repair_plan_item_id") or "") == str(request.get("knowledge_repair_item_id") or "")
    add("request_id_match", "passed" if request_matches else "blocked", "repair request and plan item matched" if request_matches else "repair request or plan item did not match")
    segment_ids = _strings(record.get("affected_segment_ids"))
    expected_hashes = request.get("current_target_hashes", {}) if isinstance(request.get("current_target_hashes"), dict) else {}
    submitted = str(record.get("submitted_target_hash") or "")
    base_matches = bool(expected_hashes) and all(str(expected_hashes.get(segment_id) or "") == submitted for segment_id in segment_ids)
    add("request_base_hash_match", "passed" if base_matches else "stale", "submitted base hash matches request" if base_matches else "submitted base hash is stale")
    repaired_hash = str(record.get("repaired_target_hash") or "")
    current_hashes = {segment_id: _hash_text(str(generated.get(segment_id, {}).get("target") or "")) for segment_id in segment_ids if generated.get(segment_id, {}).get("target") is not None}
    current_matches = bool(current_hashes) and all(value == repaired_hash for value in current_hashes.values())
    add("current_target_hash_match", "passed" if current_matches else "failed", "current target contains the repaired result" if current_matches else "repaired result does not match current target artifact")
    expected_knowledge = set(request.get("source_knowledge_provenance", {}).get("knowledge_item_ids", []))
    expected_constraint = str(request.get("required_constraint") or "")
    provenance_matches = (
        bool(record.get("provenance_references"))
        and expected_knowledge.issubset(set(record.get("source_knowledge_item_ids", [])))
        and (not expected_constraint or expected_constraint in set(record.get("source_constraint_ids", [])))
    )
    add("provenance_match", "passed" if provenance_matches else "failed", "knowledge provenance matched" if provenance_matches else "knowledge provenance is missing or mismatched")
    request_segments = set(_strings(request.get("affected_segment_ids")))
    scope_matches = bool(segment_ids) and set(segment_ids).issubset(request_segments)
    add("scope_match", "passed" if scope_matches else "failed", "result scope matches request" if scope_matches else "result scope exceeds request")
    text = str(record.get("repaired_target_text") or "\n".join(str(generated.get(segment_id, {}).get("target") or "") for segment_id in segment_ids))
    preferred = str(request.get("preferred_replacement") or "")
    add("required_term_present", "passed" if preferred and preferred in text else "not_applicable" if not preferred else "failed", "required term is present" if preferred and preferred in text else "no required term" if not preferred else "required term is absent")
    forbidden = str(request.get("forbidden_target_pattern") or "")
    forbidden_absent = not forbidden or forbidden not in text
    add("forbidden_translation_absent", "passed" if forbidden and forbidden_absent else "not_applicable" if not forbidden else "failed", "forbidden translation is absent" if forbidden and forbidden_absent else "no forbidden pattern" if not forbidden else "forbidden translation remains")
    add("negative_constraint_satisfied", "passed" if forbidden_absent else "failed", "negative constraints are satisfied" if forbidden_absent else "negative constraint failed")
    sources = [str(generated.get(segment_id, {}).get("source") or "") for segment_id in segment_ids]
    source_text = "\n".join(sources)
    active_failures = _active_constraint_failures(artifacts["working-context-packet.json"], source_text, text)
    add(
        "active_constraints_preserved",
        "failed" if active_failures else "passed",
        "; ".join(active_failures) if active_failures else "other active constraints are preserved",
    )
    add("placeholder_preservation", *_signature_check(_PLACEHOLDER, source_text, text, "placeholder"))
    add("markup_preservation", *_signature_check(_MARKUP, source_text, text, "markup"))
    add("escape_preservation", *_signature_check(_ESCAPE, source_text, text, "escape"))
    issue_type = str(plan_item.get("issue_type") or "")
    add("blind_benchmark_firewall_preserved", "blocked" if issue_type == "blind_benchmark_firewall_violation" else "passed", "blind benchmark leakage remains unresolved" if issue_type == "blind_benchmark_firewall_violation" else "blind benchmark firewall is preserved")
    conflict_ids = set(_strings(record.get("source_conflict_ids")) + _strings(plan_item.get("related_conflict_id")))
    resolved_conflicts = {
        str(item.get("conflict_id") or "")
        for item in artifacts["knowledge-conflict-resolution.json"].get("resolved_conflicts", [])
        if isinstance(item, dict)
    }
    conflicts_ok = not conflict_ids or conflict_ids.issubset(resolved_conflicts)
    add("conflict_resolution_exists", "passed" if conflicts_ok else "blocked", "required conflicts are resolved" if conflicts_ok else "required conflict resolution is missing")
    add("project_local_priority_preserved", "blocked" if issue_type == "project_priority_violation" and not conflicts_ok else "passed", "project-local priority requires conflict resolution" if issue_type == "project_priority_violation" and not conflicts_ok else "project-local priority is preserved")
    classifications = _knowledge_classifications(artifacts["working-context-packet.json"], record.get("source_knowledge_item_ids", []))
    add("no_reference_only_promotion", "blocked" if "reference_only" in classifications else "passed", "reference-only knowledge cannot support repair acceptance" if "reference_only" in classifications else "no reference-only promotion")
    disallowed = classifications.intersection({"raw", "candidate", "rejected", "stale", "superseded"})
    add("no_raw_candidate_promotion", "blocked" if disallowed else "passed", f"ineligible knowledge classifications: {', '.join(sorted(disallowed))}" if disallowed else "no raw/candidate knowledge promotion")
    semantic_or_high_risk = str(record.get("repair_mode") or "") in SEMANTIC_MODES or bool(plan_item.get("required_human_confirmation"))
    draft_only = bool(record.get("draft_or_review_only"))
    human_required = semantic_or_high_risk and not draft_only
    human_exists = _human_review_exists_from_records(artifacts["human-review-evidence.jsonl"], segment_ids)
    add("human_review_evidence", "passed" if human_required and human_exists else "requires_human_review" if human_required else "not_applicable", "scoped qualified human review exists" if human_exists else "semantic or high-risk repair requires scoped qualified human review" if human_required else "human review is not required", blocking=human_required)
    if semantic_or_high_risk and draft_only:
        add("draft_review_scope_limit", "warning", "semantic repair is limited to draft/review mode", blocking=False)
    return checks


def _qa_item(
    record: dict[str, Any],
    check_type: str,
    status: str,
    reason: str,
    *,
    blocking: bool = True,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "qa_item_id": _stable_id("knowledge-repair-qa", [record.get("result_id"), check_type]),
        "result_id": record.get("result_id"),
        "repair_request_id": record.get("source_repair_request_id"),
        "affected_segment_ids": record.get("affected_segment_ids", []),
        "affected_scope": record.get("affected_scope", {}),
        "check_type": check_type,
        "status": status,
        "reason": reason,
        "source_artifact_references": [KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL, "knowledge-repair-request.json"],
        "target_artifact_references": ["generated-segments.jsonl"],
        "blocking": bool(blocking and status not in {"passed", "not_applicable"}),
        "limitations": limitations or [],
    }


def _signature_check(pattern: re.Pattern[str], source: str, target: str, label: str) -> tuple[str, str, bool]:
    source_values = pattern.findall(source)
    target_values = pattern.findall(target)
    if not source_values:
        return "not_applicable", f"no source {label} signature", False
    matches = sorted(source_values) == sorted(target_values)
    return ("passed" if matches else "failed", f"{label} signature is preserved" if matches else f"{label} signature changed", True)


def _qa_result_status(items: list[dict[str, Any]]) -> str:
    if any(item["status"] == "stale" for item in items):
        return "stale"
    if any(item["status"] == "blocked" for item in items):
        return "blocked"
    if any(item["status"] == "failed" for item in items):
        return "failed"
    if any(item["status"] == "requires_human_review" for item in items):
        return "requires_human_review"
    if items and all(item["status"] == "not_applicable" for item in items):
        return "not_applicable"
    if any(item["status"] == "warning" for item in items):
        return "warning"
    return "passed"


def _qa_report_status(results: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "") for item in results}
    if statuses.intersection(QA_BLOCKING):
        return "blocked"
    if "requires_human_review" in statuses:
        return "requires_human_review"
    if "warning" in statuses:
        return "warning"
    return "passed" if results else "not_applicable"


def _reconcile_item(
    item: dict[str, Any],
    request: dict[str, Any],
    matches: list[dict[str, Any]],
    qa_by_result: dict[str, dict[str, Any]],
) -> tuple[str, list[str], str]:
    if not request:
        return "not_applicable", [], "not_applicable"
    if not matches:
        return "still_blocked", [], "not_applicable"
    latest = matches[-1]
    result_id = str(latest.get("result_id") or "")
    intake_status = str(latest.get("status") or "")
    qa_status = str(qa_by_result.get(result_id, {}).get("status") or "not_applicable")
    if intake_status == "rejected_stale" or qa_status == "stale":
        return "stale_result", [result_id], qa_status
    if intake_status == "rejected_provenance":
        return "provenance_mismatch", [result_id], qa_status
    if intake_status == "rejected_shape":
        return "requires_follow_up", [result_id], qa_status
    if qa_status == "requires_human_review":
        return "requires_human_review", [result_id], qa_status
    if qa_status in {"failed", "blocked"}:
        failed = set(qa_by_result.get(result_id, {}).get("failed_check_types", []))
        if "current_target_hash_match" in failed or "request_base_hash_match" in failed:
            return "hash_mismatch", [result_id], qa_status
        if "provenance_match" in failed:
            return "provenance_mismatch", [result_id], qa_status
        return "failed_qa", [result_id], qa_status
    if qa_status == "passed":
        return "cleared", [result_id], qa_status
    return "partially_cleared" if qa_status == "warning" else "still_blocked", [result_id], qa_status


def _reconciliation_follow_up(status: str) -> list[str]:
    messages = {
        "still_blocked": "Submit a matching repair result and rerun QA.",
        "failed_qa": "Correct the repaired target and rerun deterministic QA.",
        "stale_result": "Refresh the repair request and submit a result for the current target state.",
        "provenance_mismatch": "Provide provenance matching the repair request knowledge items.",
        "hash_mismatch": "Apply the repaired target to the current segment artifact or reconcile hashes explicitly.",
        "requires_human_review": "Record scoped qualified human review evidence.",
        "requires_follow_up": "Correct the intake record and resubmit.",
    }
    return [messages[status]] if status in messages else []


def _human_review_exists(state_dir: Path, segment_ids: list[str]) -> bool:
    return _human_review_exists_from_records(_read_jsonl_optional(state_dir / "human-review-evidence.jsonl"), segment_ids)


def _human_review_exists_from_records(records: list[dict[str, Any]], segment_ids: list[str]) -> bool:
    requested = set(segment_ids)
    for record in records:
        if record.get("status") not in {"accepted", "accepted_with_limitations"} or not record.get("effective_evidence_levels"):
            continue
        scope = record.get("review_scope", {}) if isinstance(record.get("review_scope"), dict) else {}
        if scope.get("scope_type") == "full_run" or requested.issubset(set(_strings(scope.get("segment_ids")))):
            return True
    return False


def _knowledge_classifications(context: dict[str, Any], ids: Any) -> set[str]:
    requested = set(_strings(ids))
    classifications: set[str] = set()
    for group in (
        "hard_constraints",
        "negative_constraints",
        "tm_suggestions",
        "retrieved_examples",
        "reference_only_context",
        "excluded_knowledge",
    ):
        for item in context.get(group, []):
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("knowledge_id") or item.get("source_knowledge_item_id") or "")
            if item_id in requested:
                classifications.add(str(item.get("classification") or item.get("status") or ""))
    return classifications


def _active_constraint_failures(context: dict[str, Any], source: str, target: str) -> list[str]:
    failures: list[str] = []
    for item in context.get("hard_constraints", []):
        if not isinstance(item, dict):
            continue
        source_value = str(item.get("source_value") or "")
        target_value = str(item.get("target_value") or "")
        if source_value and target_value and source_value in source and target_value not in target:
            failures.append(f"required term missing: {source_value}")
    for item in context.get("negative_constraints", []):
        if not isinstance(item, dict):
            continue
        source_value = str(item.get("source_value") or "")
        forbidden = str(item.get("target_value") or "")
        if forbidden and (not source_value or source_value in source) and forbidden in target:
            failures.append(f"forbidden target remains: {forbidden}")
    return failures


def _load_artifacts(state_dir: Path) -> dict[str, Any]:
    json_names = (
        "knowledge-repair-plan.json",
        "knowledge-repair-request.json",
        "knowledge-repair-impact-report.json",
        "knowledge-repair-qa-report.json",
        "knowledge-repair-reconciliation.json",
        "repair-request.json",
        "repair-result.json",
        "knowledge-conflict-resolution.json",
        "knowledge-assurance-summary.json",
        "knowledge-audit-enforcement-decision.json",
        "constraint-application-audit.json",
        "knowledge-conflict-report.json",
        "working-context-packet.json",
        "artifact-state.json",
    )
    artifacts: dict[str, Any] = {name: _read_optional_json(state_dir / name) for name in json_names}
    artifacts[KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL] = read_knowledge_repair_result_intake(state_dir)
    artifacts["repair-history.jsonl"] = _read_jsonl_optional(state_dir / "repair-history.jsonl")
    artifacts["knowledge-audit-resolution-log.jsonl"] = _read_jsonl_optional(state_dir / "knowledge-audit-resolution-log.jsonl")
    artifacts["knowledge-constraint-review-evidence.jsonl"] = _read_jsonl_optional(state_dir / "knowledge-constraint-review-evidence.jsonl")
    artifacts["human-review-evidence.jsonl"] = _read_jsonl_optional(state_dir / "human-review-evidence.jsonl")
    artifacts["generated-segments.jsonl"] = _read_jsonl_optional(state_dir / "generated-segments.jsonl")
    if not artifacts["generated-segments.jsonl"]:
        artifacts["generated-segments.jsonl"] = _read_jsonl_optional(state_dir / "generated.jsonl")
    return artifacts


def _source_artifacts(state_dir: Path) -> dict[str, str]:
    names = (
        "knowledge-repair-plan.json",
        "knowledge-repair-request.json",
        "knowledge-repair-impact-report.json",
        KNOWLEDGE_REPAIR_RESULT_INTAKE_JSONL,
        "repair-request.json",
        "repair-result.json",
        "repair-history.jsonl",
        "knowledge-audit-resolution-log.jsonl",
        "knowledge-constraint-review-evidence.jsonl",
        "knowledge-conflict-resolution.json",
        "knowledge-assurance-summary.json",
        "knowledge-audit-enforcement-decision.json",
        "constraint-application-audit.json",
        "knowledge-conflict-report.json",
        "generated-segments.jsonl",
        "human-review-evidence.jsonl",
    )
    return {Path(name).stem.replace("-", "_"): name for name in names if (state_dir / name).is_file()}


def _requests_by_id(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("request_id") or ""): item for item in document.get("requests", []) if isinstance(item, dict) and item.get("request_id")}


def _plan_items_by_id(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("repair_item_id") or ""): item for item in document.get("repair_items", []) if isinstance(item, dict) and item.get("repair_item_id")}


def _generated_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("segment_id") or ""): item for item in items if isinstance(item, dict) and item.get("segment_id")}


def _enum(value: dict[str, Any], key: str, allowed: set[str], default: str) -> str:
    item = str(value.get(key) or default)
    if item not in allowed:
        raise ValueError(f"{key} must be one of: {', '.join(sorted(allowed))}")
    return item


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _read_jsonl_optional(path: Path) -> list[dict[str, Any]]:
    return [item for item in read_jsonl(path) if isinstance(item, dict)] if path.is_file() else []


def _read_required(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing knowledge repair result artifact: {path}")
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Knowledge repair result artifact must be a JSON object: {path}")
    return value


def _stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in {None, ""}]
    return [str(value)] if value not in {None, ""} else []


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
