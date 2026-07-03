from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json, write_jsonl


PROVIDER_ATTEMPT_SEMANTICS_REPORT_JSON = "provider-attempt-semantics-report.json"
PROVIDER_ATTEMPT_TYPE_NORMALIZATION_JSON = "provider-attempt-type-normalization.json"
PROVIDER_SMOKE_LEDGER_LINKAGE_REPORT_JSON = "provider-smoke-ledger-linkage-report.json"
PROVIDER_EXECUTION_EVIDENCE_CLASSIFICATION_JSON = "provider-execution-evidence-classification.json"
PROVIDER_LEDGER_SEMANTIC_MIGRATION_REPORT_JSON = "provider-ledger-semantic-migration-report.json"

PROVIDER_ATTEMPT_SEMANTICS_ASSETS = {
    "provider_attempt_semantics_report": PROVIDER_ATTEMPT_SEMANTICS_REPORT_JSON,
    "provider_attempt_type_normalization": PROVIDER_ATTEMPT_TYPE_NORMALIZATION_JSON,
    "provider_smoke_ledger_linkage_report": PROVIDER_SMOKE_LEDGER_LINKAGE_REPORT_JSON,
    "provider_execution_evidence_classification": PROVIDER_EXECUTION_EVIDENCE_CLASSIFICATION_JSON,
    "provider_ledger_semantic_migration_report": PROVIDER_LEDGER_SEMANTIC_MIGRATION_REPORT_JSON,
}

ATTEMPT_TYPES = {
    "blocked_before_execution",
    "dry_run_only",
    "mock_execution",
    "external_result_import",
    "manual_controlled_real_provider_smoke",
    "runtime_real_provider_execution",
    "skipped",
    "failed_policy_check",
}

SMOKE_FORBIDDEN_CLAIMS = {
    "full_product_localization",
    "locale_complete",
    "production_ready",
    "provider_backed_quality",
}


def infer_attempt_type(attempt: dict[str, Any], intake: dict[str, Any] | None = None) -> str:
    intake = intake or {}
    provenance = _provenance(attempt, intake)
    source = str(intake.get("result_source") or provenance.get("result_source") or "")
    current = str(attempt.get("attempt_type") or "")
    status = str(intake.get("provider_status") or intake.get("status") or "")
    if source in {"mock", "synthetic"}:
        return "mock_execution"
    if source == "dry_run":
        return "dry_run_only"
    if source == "skipped":
        return "skipped"
    if status in {"blocked", "rejected_shape", "rejected_provenance", "rejected_stale"}:
        return "failed_policy_check"
    if source == "real_provider":
        if _is_manual_smoke(attempt, intake, provenance):
            return "manual_controlled_real_provider_smoke"
        if _is_runtime_managed(provenance):
            return "runtime_real_provider_execution"
        return "external_result_import"
    if source == "external_provider_result":
        return "external_result_import"
    if current == "future_real_execution_placeholder":
        return "blocked_before_execution"
    return current if current in ATTEMPT_TYPES else "blocked_before_execution"


def normalize_attempt_record(attempt: dict[str, Any], intake: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = dict(attempt)
    previous = str(attempt.get("attempt_type") or "")
    current = infer_attempt_type(attempt, intake)
    normalized["attempt_type"] = current
    normalized["attempt_semantics_version"] = "v2"
    normalized["execution_evidence_class"] = _evidence_class(current)
    if previous and previous != current:
        normalized["legacy_attempt_type"] = previous
    if previous == "future_real_execution_placeholder":
        normalized["result_state"] = "no_execution"
    return normalized


def classify_attempt_record(attempt: dict[str, Any], intake: dict[str, Any] | None = None) -> dict[str, Any]:
    intake = intake or {}
    attempt_type = infer_attempt_type(attempt, intake)
    result_state = str(attempt.get("result_state") or "")
    authorized = attempt.get("authorization_status") == "authorized" and attempt.get("preflight_status") == "authorized"
    has_result = bool(attempt.get("result_id")) and result_state == "success"
    runtime_managed = _is_runtime_managed(_provenance(attempt, intake))
    issues: list[str] = []
    if attempt_type == "external_result_import" and attempt.get("runtime_execution_evidence") is True:
        issues.append("external_result_import_cannot_be_runtime_execution_evidence")
    if attempt_type == "manual_controlled_real_provider_smoke" and attempt.get("provider_backed_quality_supported") is True:
        issues.append("manual_smoke_cannot_support_provider_backed_quality")
    if attempt_type == "runtime_real_provider_execution" and not (authorized and has_result and runtime_managed):
        issues.append("runtime_real_provider_execution_evidence_missing_or_incomplete")
    if attempt_type in {"mock_execution", "dry_run_only"} and attempt.get("provider_backed_quality_supported") is True:
        issues.append(f"{attempt_type}_cannot_support_provider_backed_quality")
    manual_smoke_supported = attempt_type == "manual_controlled_real_provider_smoke" and authorized and has_result
    runtime_execution_supported = attempt_type == "runtime_real_provider_execution" and authorized and has_result and runtime_managed
    return {
        "attempt_id": str(attempt.get("attempt_id") or ""),
        "result_id": str(attempt.get("result_id") or ""),
        "attempt_type": attempt_type,
        "evidence_class": _evidence_class(attempt_type),
        "status": "blocked" if issues else "classified",
        "issues": issues,
        "provider_path_smoke_supported": manual_smoke_supported,
        "runtime_execution_supported": runtime_execution_supported,
        "provider_backed_quality_supported": False,
        "benchmark_expansion_allowed": False,
    }


def build_provider_attempt_type_normalization(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    ledger_path = state_dir / "provider-execution-attempt-ledger.jsonl"
    records = _optional_jsonl(ledger_path)
    intake = _intake_by_result(state_dir)
    normalized = [normalize_attempt_record(item, intake.get(str(item.get("result_id") or ""))) for item in records]
    ledger_changed = normalized != records
    items = [
        {
            "attempt_id": str(after.get("attempt_id") or ""),
            "result_id": str(after.get("result_id") or ""),
            "previous_attempt_type": str(before.get("legacy_attempt_type") or before.get("attempt_type") or "missing"),
            "normalized_attempt_type": str(after.get("attempt_type") or ""),
            "changed": (before.get("legacy_attempt_type") or before.get("attempt_type")) != after.get("attempt_type"),
            "reason": _normalization_reason(before, after),
        }
        for before, after in zip(records, normalized)
    ]
    if write and normalized and ledger_changed:
        write_jsonl(ledger_path, normalized)
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-attempt-type-normalization-v1",
        "artifact": PROVIDER_ATTEMPT_TYPE_NORMALIZATION_JSON,
        "status": "normalized" if any(item["changed"] for item in items) else "current" if items else "no_attempts",
        "normalized_attempt_types": sorted(ATTEMPT_TYPES),
        "items": items,
        "summary": {"attempt_count": len(items), "changed_count": sum(item["changed"] for item in items)},
        "ledger_updated": bool(write and ledger_changed),
        "provider_execution_behavior_changed": False,
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": _existing_names(state_dir, "provider-execution-attempt-ledger.jsonl", "provider-result-intake.jsonl"),
    }
    if write:
        write_json(state_dir / PROVIDER_ATTEMPT_TYPE_NORMALIZATION_JSON, report)
    return report


def build_provider_attempt_semantics_report(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    normalization = build_provider_attempt_type_normalization(state_dir, write=write)
    records = _optional_jsonl(state_dir / "provider-execution-attempt-ledger.jsonl")
    intake = _intake_by_result(state_dir)
    items = [classify_attempt_record(item, intake.get(str(item.get("result_id") or ""))) for item in records]
    blocked = [item for item in items if item["issues"]]
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-attempt-semantics-report-v1",
        "artifact": PROVIDER_ATTEMPT_SEMANTICS_REPORT_JSON,
        "status": "not_run" if not items else "blocked" if blocked else "consistent",
        "items": items,
        "summary": {
            "attempt_count": len(items),
            "blocked_count": len(blocked),
            "attempt_type_counts": _counts(items, "attempt_type"),
            "evidence_class_counts": _counts(items, "evidence_class"),
        },
        "external_import_is_runtime_execution_evidence": False,
        "staging_admission_is_quality_evidence": False,
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": [PROVIDER_ATTEMPT_TYPE_NORMALIZATION_JSON, *_existing_names(state_dir, "provider-execution-attempt-ledger.jsonl", "provider-result-intake.jsonl")],
    }
    if write:
        write_json(state_dir / PROVIDER_ATTEMPT_SEMANTICS_REPORT_JSON, report)
    return report


def build_provider_smoke_ledger_linkage_report(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    semantics = build_provider_attempt_semantics_report(state_dir, write=write)
    evidence = _optional_json(state_dir / "provider-real-smoke-evidence.json")
    fixture_id = str(evidence.get("fixture_id") or "")
    run_id = str(evidence.get("run_id") or "")
    linked = []
    for item in semantics.get("items", []):
        if item.get("attempt_type") != "manual_controlled_real_provider_smoke":
            continue
        linked.append({
            "attempt_id": item.get("attempt_id"),
            "result_id": item.get("result_id"),
            "run_id": run_id,
            "fixture_id": fixture_id,
            "status": "linked" if item.get("provider_path_smoke_supported") else "blocked",
        })
    status = "missing" if not evidence else "linked" if linked and all(item["status"] == "linked" for item in linked) else "mismatch"
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-smoke-ledger-linkage-report-v1",
        "artifact": PROVIDER_SMOKE_LEDGER_LINKAGE_REPORT_JSON,
        "status": status,
        "run_id": run_id,
        "fixture_id": fixture_id,
        "linked_attempts": linked,
        "provider_path_smoke_supported": status == "linked",
        "provider_backed_quality_supported": False,
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": _existing_names(state_dir, "provider-real-smoke-evidence.json", PROVIDER_ATTEMPT_SEMANTICS_REPORT_JSON, "provider-execution-attempt-ledger.jsonl"),
    }
    if write:
        write_json(state_dir / PROVIDER_SMOKE_LEDGER_LINKAGE_REPORT_JSON, report)
    return report


def build_provider_execution_evidence_classification(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    semantics = build_provider_attempt_semantics_report(state_dir, write=write)
    linkage = build_provider_smoke_ledger_linkage_report(state_dir, write=write)
    items = semantics.get("items", [])
    runtime_supported = any(item.get("runtime_execution_supported") for item in items)
    manual_smoke_supported = linkage.get("provider_path_smoke_supported") is True
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-execution-evidence-classification-v1",
        "artifact": PROVIDER_EXECUTION_EVIDENCE_CLASSIFICATION_JSON,
        "status": "blocked" if semantics.get("status") == "blocked" else "classified" if items else "not_run",
        "classifications": items,
        "provider_path_smoke_supported": manual_smoke_supported,
        "runtime_real_provider_execution_available": runtime_supported,
        "external_result_import_supports_runtime_execution": False,
        "provider_backed_quality_supported": False,
        "staging_admission_supports_quality": False,
        "benchmark_expansion_allowed": False,
        "forbidden_claims": sorted(SMOKE_FORBIDDEN_CLAIMS),
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": [PROVIDER_ATTEMPT_SEMANTICS_REPORT_JSON, PROVIDER_SMOKE_LEDGER_LINKAGE_REPORT_JSON, *_existing_names(state_dir, "provider-result-staging-admission.json", "provider-staging-claim-boundary.json")],
    }
    if write:
        write_json(state_dir / PROVIDER_EXECUTION_EVIDENCE_CLASSIFICATION_JSON, report)
    return report


def build_provider_ledger_semantic_migration_report(state_dir: Path, *, write: bool = True) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    normalization = build_provider_attempt_type_normalization(state_dir, write=write)
    changed = [item for item in normalization.get("items", []) if item.get("changed")]
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-provider-ledger-semantic-migration-report-v1",
        "artifact": PROVIDER_LEDGER_SEMANTIC_MIGRATION_REPORT_JSON,
        "status": "migrated" if changed else "current" if normalization.get("items") else "not_required",
        "migrations": changed,
        "historical_attempt_ids_preserved": True,
        "legacy_attempt_type_preserved": True,
        "provider_execution_behavior_changed": False,
        "provider_or_model_called_by_runtime": False,
        "source_artifact_references": [PROVIDER_ATTEMPT_TYPE_NORMALIZATION_JSON, *_existing_names(state_dir, "provider-execution-attempt-ledger.jsonl")],
    }
    if write:
        write_json(state_dir / PROVIDER_LEDGER_SEMANTIC_MIGRATION_REPORT_JSON, report)
    return report


def build_provider_attempt_semantics_artifacts(state_dir: Path) -> dict[str, Any]:
    normalization = build_provider_attempt_type_normalization(state_dir)
    semantics = build_provider_attempt_semantics_report(state_dir)
    linkage = build_provider_smoke_ledger_linkage_report(state_dir)
    classification = build_provider_execution_evidence_classification(state_dir)
    migration = build_provider_ledger_semantic_migration_report(state_dir)
    return {
        "provider_attempt_type_normalization": normalization,
        "provider_attempt_semantics_report": semantics,
        "provider_smoke_ledger_linkage_report": linkage,
        "provider_execution_evidence_classification": classification,
        "provider_ledger_semantic_migration_report": migration,
        "provider_or_model_called_by_runtime": False,
    }


def read_provider_attempt_semantics_artifact(state_dir: Path, name: str) -> dict[str, Any]:
    filename = PROVIDER_ATTEMPT_SEMANTICS_ASSETS.get(name)
    if not filename:
        raise ValueError(f"unknown provider attempt semantics artifact: {name}")
    return _required_json(state_dir / filename)


def provider_attempt_semantics_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in PROVIDER_ATTEMPT_SEMANTICS_ASSETS.items() if (state_dir / name).is_file()}


def _is_manual_smoke(attempt: dict[str, Any], intake: dict[str, Any], provenance: dict[str, Any]) -> bool:
    scope = intake.get("scope") if isinstance(intake.get("scope"), dict) else attempt.get("scope") if isinstance(attempt.get("scope"), dict) else {}
    run_id = str(intake.get("run_id") or provenance.get("run_id") or provenance.get("external_reference") or "")
    return bool(scope.get("fixture_id") == "quickstart-json-provider-smoke-v1" and run_id.startswith("provider-smoke-"))


def _is_runtime_managed(provenance: dict[str, Any]) -> bool:
    return provenance.get("runtime_managed_execution") is True or provenance.get("execution_mode") == "runtime_real_provider_execution"


def _provenance(attempt: dict[str, Any], intake: dict[str, Any]) -> dict[str, Any]:
    result = {}
    if isinstance(attempt.get("provenance"), dict):
        result.update(attempt["provenance"])
    if isinstance(intake.get("provenance"), dict):
        result.update(intake["provenance"])
    return result


def _evidence_class(attempt_type: str) -> str:
    return {
        "blocked_before_execution": "no_execution",
        "dry_run_only": "planning_only",
        "mock_execution": "mock_only",
        "external_result_import": "external_result_only",
        "manual_controlled_real_provider_smoke": "provider_path_smoke_only",
        "runtime_real_provider_execution": "runtime_execution",
        "skipped": "no_execution",
        "failed_policy_check": "blocked",
    }.get(attempt_type, "unknown")


def _normalization_reason(before: dict[str, Any], after: dict[str, Any]) -> str:
    previous = before.get("legacy_attempt_type") or before.get("attempt_type")
    if previous == after.get("attempt_type"):
        return "attempt type already uses normalized semantics"
    if after.get("attempt_type") == "manual_controlled_real_provider_smoke":
        return "real provider result is bound to the controlled quickstart smoke scope"
    if previous == "future_real_execution_placeholder":
        return "placeholder did not execute and is normalized to blocked-before-execution"
    return "attempt type normalized from result source and provenance"


def _intake_by_result(state_dir: Path) -> dict[str, dict[str, Any]]:
    return {str(item.get("result_id") or ""): item for item in _optional_jsonl(state_dir / "provider-result-intake.jsonl")}


def _counts(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _existing_names(state_dir: Path, *names: str) -> list[str]:
    return [name for name in names if (state_dir / name).is_file()]


def _optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _optional_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.is_file() else []


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"artifact not found: {path.name}")
    return read_json(path)
