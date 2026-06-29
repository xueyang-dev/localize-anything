from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .document_evidence import (
    CLAIM_METRIC_REPORT_JSON,
    DOCUMENT_EVIDENCE_MANIFEST_JSON,
    DOCUMENT_INTAKE_REPORT_JSON,
    LEADERSHIP_REVIEW_BRIEF_MD,
    OPEN_DECISIONS_MD,
    PUBLICITY_RISK_REPORT_JSON,
    SEMANTIC_ALIGNMENT_JSONL,
)
from .io_utils import read_json, read_jsonl, write_json


WORKBENCH_DOCUMENT_EVIDENCE_QUEUE_JSON = "workbench-document-evidence-queue.json"

DOCUMENT_FORBIDDEN_CLAIMS = ["review_complete", "delivery_ready", "apply_ready", "production_ready", "layout_verified"]


def build_workbench_document_evidence_queue(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    artifacts = _load_artifacts(state_dir)
    items: list[dict[str, Any]] = []
    items.extend(_intake_items(artifacts))
    items.extend(_alignment_items(artifacts))
    items.extend(_claim_metric_items(artifacts))
    items.extend(_publicity_risk_items(artifacts))
    items.extend(_open_decision_items(artifacts))
    items.extend(_stale_items(artifacts))
    items.extend(_leadership_items(artifacts))
    items = _dedupe_items(items)
    queue = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-document-evidence-queue-v1",
        "artifact": WORKBENCH_DOCUMENT_EVIDENCE_QUEUE_JSON,
        "status": "requires_action" if items else "empty",
        "summary": {
            "item_count": len(items),
            "blocking_count": sum(item["severity"] == "blocking" for item in items),
            "stale_item_count": sum(bool(item.get("stale_evidence_involved")) for item in items),
            "claim_metric_risk_count": sum(item["item_type"] == "claim_metric_review_required" for item in items),
            "publicity_risk_count": sum(item["item_type"] == "publicity_risk_review_required" for item in items),
            "open_decision_count": sum(item["item_type"] == "open_decision_required" for item in items),
            "human_confirmation_required_count": sum(bool(item.get("human_confirmation_required")) for item in items),
        },
        "items": items,
        "source_artifacts": _source_artifacts(state_dir),
    }
    if write:
        write_json(state_dir / WORKBENCH_DOCUMENT_EVIDENCE_QUEUE_JSON, queue)
    return queue


def read_workbench_document_evidence_queue(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / WORKBENCH_DOCUMENT_EVIDENCE_QUEUE_JSON)


def workbench_document_evidence_queue_asset_paths(state_dir: Path) -> dict[str, str]:
    if (state_dir / WORKBENCH_DOCUMENT_EVIDENCE_QUEUE_JSON).is_file():
        return {"workbench_document_evidence_queue": WORKBENCH_DOCUMENT_EVIDENCE_QUEUE_JSON}
    return {}


def _intake_items(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    intake = artifacts["document_intake_report"]
    manifest = artifacts["document_evidence_manifest"]
    if not intake and not manifest:
        return []
    scenario = str(intake.get("detected_scenario_adapter") or manifest.get("document_scenario") or "")
    if str(intake.get("status") or manifest.get("status") or "") == "unsupported" or scenario == "unsupported_document_scenario":
        return [
            _item(
                "unsupported_document_scenario",
                "blocking",
                "open",
                "project_owner",
                [DOCUMENT_INTAKE_REPORT_JSON, DOCUMENT_EVIDENCE_MANIFEST_JSON],
                affected_scope={"scenario": scenario or "unknown"},
                forbidden_claims_affected=DOCUMENT_FORBIDDEN_CLAIMS,
                recommended_action="Confirm a supported document evidence scenario or keep document delivery claims blocked.",
                human_confirmation_required=True,
            )
        ]
    if not intake:
        return [
            _item(
                "document_intake_incomplete",
                "blocking",
                "open",
                "project_owner",
                [DOCUMENT_INTAKE_REPORT_JSON],
                forbidden_claims_affected=DOCUMENT_FORBIDDEN_CLAIMS,
                recommended_action="Generate document-intake-report.json before using document evidence for readiness.",
                human_confirmation_required=True,
            )
        ]
    return []


def _alignment_items(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in artifacts["semantic_alignment"]:
        mode = str(record.get("alignment_mode") or "unknown")
        if not record.get("human_confirmation_required") and not record.get("risk_flags"):
            continue
        item_type = "semantic_alignment_risk"
        if mode == "english_only_bridge":
            item_type = "english_only_bridge_review_required"
        elif mode == "source_only_omitted":
            item_type = "source_only_omitted_review_required"
        items.append(
            _item(
                item_type,
                "warning",
                "open",
                "document_reviewer",
                [SEMANTIC_ALIGNMENT_JSONL],
                affected_segment_ids=[str(record.get("segment_id"))] if record.get("segment_id") else [],
                evidence_level_impact=["E2_bilingual_human_spot_check"],
                forbidden_claims_affected=["review_complete", "delivery_ready", "production_ready"],
                recommended_action=f"Confirm semantic alignment mode `{mode}` before strong document readiness claims.",
                human_confirmation_required=bool(record.get("human_confirmation_required")),
            )
        )
    return items


def _claim_metric_items(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for check in artifacts["claim_metric_report"].get("checks", []):
        status = str(check.get("status") or "")
        if status not in {"blocked", "warning", "pending"}:
            continue
        items.append(
            _item(
                "claim_metric_review_required",
                "blocking" if status == "blocked" else "warning",
                "open",
                "document_owner",
                [CLAIM_METRIC_REPORT_JSON],
                affected_segment_ids=[str(check.get("segment_id"))] if check.get("segment_id") else [],
                related_claim_metric_risk={
                    "check_id": check.get("check_id"),
                    "claim_type": check.get("claim_type"),
                    "risk_class": check.get("risk_class"),
                    "status": status,
                    "reason": check.get("reason"),
                },
                evidence_level_impact=["E1_automated_semantic_or_policy_review", "E2_bilingual_human_spot_check"],
                forbidden_claims_affected=["review_complete", "delivery_ready", "production_ready"],
                recommended_action="Resolve or explicitly confirm claim/metric boundary risks before document delivery.",
                human_confirmation_required=bool(check.get("human_confirmation_required")),
            )
        )
    return items


def _publicity_risk_items(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for risk in artifacts["publicity_risk_report"].get("risks", []):
        severity = "blocking" if risk.get("severity") == "blocking" else "warning"
        items.append(
            _item(
                "publicity_risk_review_required",
                severity,
                "open",
                "leadership_reviewer",
                [PUBLICITY_RISK_REPORT_JSON],
                affected_segment_ids=[str(risk.get("segment_id"))] if risk.get("segment_id") else [],
                related_publicity_risk={
                    "risk_id": risk.get("risk_id"),
                    "risk_class": risk.get("risk_class"),
                    "severity": risk.get("severity"),
                    "reason": risk.get("reason"),
                },
                evidence_level_impact=["E2_bilingual_human_spot_check"],
                forbidden_claims_affected=["review_complete", "delivery_ready", "production_ready"],
                recommended_action=str(risk.get("recommended_action") or "Review external-facing publicity risk before delivery."),
                human_confirmation_required=bool(risk.get("human_confirmation_required", True)),
            )
        )
    return items


def _open_decision_items(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = artifacts["document_evidence_manifest"]
    open_count = int(manifest.get("summary", {}).get("open_decision_count", 0) or 0) if isinstance(manifest, dict) else 0
    if not open_count:
        return []
    return [
        _item(
            "open_decision_required",
            "blocking" if int(manifest.get("summary", {}).get("blocking_decision_count", 0) or 0) else "warning",
            "open",
            "project_owner",
            [OPEN_DECISIONS_MD, DOCUMENT_EVIDENCE_MANIFEST_JSON],
            related_open_decision={"open_decision_count": open_count},
            evidence_level_impact=["E2_bilingual_human_spot_check"],
            forbidden_claims_affected=["review_complete", "delivery_ready", "production_ready"],
            recommended_action="Close document evidence open decisions or keep delivery/apply downgraded.",
            human_confirmation_required=True,
        )
    ]


def _stale_items(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    state = artifacts["artifact_state"]
    items: list[dict[str, Any]] = []
    document_ids = {
        "document_intake_report",
        "semantic_alignment",
        "claim_metric_report",
        "publicity_risk_report",
        "leadership_review_brief",
        "open_decisions",
        "document_evidence_manifest",
        "signoff_record",
    }
    for artifact in state.get("artifacts", []) if isinstance(state, dict) else []:
        if artifact.get("artifact_id") not in document_ids:
            continue
        if artifact.get("status") not in {"stale", "superseded", "blocked", "requires_human_review"}:
            continue
        items.append(
            _item(
                "document_evidence_stale",
                "blocking",
                "open",
                "developer",
                ["artifact-state.json", str(artifact.get("path") or artifact.get("artifact_id"))],
                affected_scope={"artifact_id": artifact.get("artifact_id"), "status": artifact.get("status")},
                forbidden_claims_affected=DOCUMENT_FORBIDDEN_CLAIMS,
                recommended_action="Regenerate or review stale document evidence before delivery/apply readiness.",
                human_confirmation_required=True,
                stale_evidence_involved=True,
            )
        )
    return items


def _leadership_items(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = artifacts["document_evidence_manifest"]
    if not manifest:
        return []
    signoff = artifacts["signoff_record"]
    if signoff and signoff.get("status") in {"accepted", "final"}:
        return []
    return [
        _item(
            "leadership_review_required",
            "warning",
            "open",
            "project_owner",
            [LEADERSHIP_REVIEW_BRIEF_MD, "signoff-record.json"],
            evidence_level_impact=["E2_bilingual_human_spot_check"],
            forbidden_claims_affected=["review_complete", "delivery_ready", "production_ready"],
            recommended_action="Record explicit document review/signoff with limitations preserved.",
            human_confirmation_required=True,
        ),
        _item(
            "document_signoff_required",
            "warning",
            "open",
            "project_owner",
            [DOCUMENT_EVIDENCE_MANIFEST_JSON, "signoff-record.json"],
            forbidden_claims_affected=["delivery_ready", "apply_ready", "production_ready"],
            recommended_action="Create final signoff only after document evidence blockers are resolved.",
            human_confirmation_required=True,
        ),
    ]


def _load_artifacts(state_dir: Path) -> dict[str, Any]:
    return {
        "document_intake_report": _read_json_object(state_dir / DOCUMENT_INTAKE_REPORT_JSON),
        "semantic_alignment": _read_jsonl(state_dir / SEMANTIC_ALIGNMENT_JSONL),
        "claim_metric_report": _read_json_object(state_dir / CLAIM_METRIC_REPORT_JSON),
        "publicity_risk_report": _read_json_object(state_dir / PUBLICITY_RISK_REPORT_JSON),
        "document_evidence_manifest": _read_json_object(state_dir / DOCUMENT_EVIDENCE_MANIFEST_JSON),
        "artifact_state": _read_json_object(state_dir / "artifact-state.json"),
        "evaluation_scorecard": _read_json_object(state_dir / "evaluation-scorecard.json"),
        "signoff_record": _read_json_object(state_dir / "signoff-record.json"),
    }


def _source_artifacts(state_dir: Path) -> dict[str, str]:
    names = (
        DOCUMENT_INTAKE_REPORT_JSON,
        SEMANTIC_ALIGNMENT_JSONL,
        CLAIM_METRIC_REPORT_JSON,
        PUBLICITY_RISK_REPORT_JSON,
        LEADERSHIP_REVIEW_BRIEF_MD,
        OPEN_DECISIONS_MD,
        DOCUMENT_EVIDENCE_MANIFEST_JSON,
        "artifact-state.json",
        "evaluation-scorecard.json",
        "signoff-record.json",
    )
    return {Path(name).stem.replace("-", "_"): name for name in names if (state_dir / name).is_file()}


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = read_json(path)
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [item for item in read_jsonl(path) if isinstance(item, dict)]


def _item(
    item_type: str,
    severity: str,
    status: str,
    owner_role: str,
    source_artifact_references: list[str],
    *,
    affected_segment_ids: list[str] | None = None,
    affected_scope: dict[str, Any] | None = None,
    related_claim_metric_risk: dict[str, Any] | None = None,
    related_publicity_risk: dict[str, Any] | None = None,
    related_open_decision: dict[str, Any] | None = None,
    evidence_level_impact: list[str] | None = None,
    forbidden_claims_affected: list[str] | None = None,
    recommended_action: str,
    human_confirmation_required: bool,
    stale_evidence_involved: bool = False,
) -> dict[str, Any]:
    payload = {
        "item_type": item_type,
        "source_artifact_references": sorted(source_artifact_references),
        "affected_segment_ids": sorted(affected_segment_ids or []),
        "affected_scope": affected_scope or {},
        "related_claim_metric_risk": related_claim_metric_risk or {},
        "related_publicity_risk": related_publicity_risk or {},
        "related_open_decision": related_open_decision or {},
        "forbidden_claims_affected": sorted(set(forbidden_claims_affected or [])),
    }
    return {
        "item_id": _stable_id("workbench-document-evidence", payload),
        "item_type": item_type,
        "severity": severity,
        "status": status,
        "owner_role": owner_role,
        "source_artifact_references": payload["source_artifact_references"],
        "affected_segment_ids": payload["affected_segment_ids"],
        "affected_scope": payload["affected_scope"],
        "related_claim_metric_risk": payload["related_claim_metric_risk"],
        "related_publicity_risk": payload["related_publicity_risk"],
        "related_open_decision": payload["related_open_decision"],
        "evidence_level_impact": evidence_level_impact or [],
        "forbidden_claims_affected": payload["forbidden_claims_affected"],
        "recommended_action": recommended_action,
        "human_confirmation_required": human_confirmation_required,
        "stale_evidence_involved": stale_evidence_involved,
    }


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        item_id = str(item.get("item_id"))
        if item_id in seen:
            continue
        seen.add(item_id)
        deduped.append(item)
    severity_order = {"blocking": 0, "warning": 1, "info": 2}
    return sorted(deduped, key=lambda item: (severity_order.get(str(item.get("severity")), 9), str(item.get("item_type")), str(item.get("item_id"))))


def _stable_id(prefix: str, value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:24]}"
