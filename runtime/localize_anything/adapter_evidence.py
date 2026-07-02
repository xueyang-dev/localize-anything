from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .adapter_release import (
    ADAPTER_PROMOTION_DECISION_JSON,
    ADAPTER_RELEASE_AUDIT_JSON,
    ADAPTER_SUPPORT_MATRIX_JSON,
    build_adapter_promotion_decision,
    build_adapter_regression_evidence_report,
    build_adapter_release_audit,
    build_adapter_support_matrix,
    read_adapter_promotion_decision,
    read_adapter_support_matrix,
)
from .io_utils import read_json, sha256_file, write_json


ADAPTER_EVIDENCE_PROVENANCE_JSON = "adapter-evidence-provenance.json"
ADAPTER_FIXTURE_MANIFEST_JSON = "adapter-fixture-manifest.json"
ADAPTER_REGRESSION_CHECK_REPORT_JSON = "adapter-regression-check-report.json"
ADAPTER_EVIDENCE_GAP_REPORT_JSON = "adapter-evidence-gap-report.json"
ADAPTER_PROMOTION_READINESS_REPORT_JSON = "adapter-promotion-readiness-report.json"

ADAPTER_EVIDENCE_ASSETS = {
    "adapter_evidence_provenance": ADAPTER_EVIDENCE_PROVENANCE_JSON,
    "adapter_fixture_manifest": ADAPTER_FIXTURE_MANIFEST_JSON,
    "adapter_regression_check_report": ADAPTER_REGRESSION_CHECK_REPORT_JSON,
    "adapter_evidence_gap_report": ADAPTER_EVIDENCE_GAP_REPORT_JSON,
    "adapter_promotion_readiness_report": ADAPTER_PROMOTION_READINESS_REPORT_JSON,
}

LIFECYCLE = ["detect", "inventory", "extract", "validate_source", "rebuild", "validate_output", "plan_apply", "apply_to_copy"]

FIXTURE_REFERENCES: dict[str, dict[str, Any]] = {
    "core.json-locale": {
        "source": "tests/fixtures/json-project/locales/en-US.json",
        "target": "tests/fixtures/json-project/locales/zh-CN.json",
        "stages": ["extract", "rebuild", "validate_output"],
    },
    "core.gettext-po": {
        "source": "tests/fixtures/gettext-wesnoth/messages.pot",
        "stages": ["extract", "rebuild", "validate_output"],
    },
    "core.tabular": {
        "source": "tests/fixtures/common-formats/messages.csv",
        "stages": ["extract", "rebuild", "validate_output"],
    },
    "core.subtitles": {
        "source": "tests/fixtures/common-formats/captions.srt",
        "stages": ["extract", "rebuild", "validate_output"],
    },
    "core.xliff": {
        "source": "tests/fixtures/common-formats/messages.xlf",
        "stages": ["extract", "rebuild", "validate_output"],
    },
    "core.yaml-toml": {
        "source": "tests/fixtures/common-formats/messages.yaml",
        "stages": ["extract", "rebuild", "validate_output"],
    },
    "core.markup": {
        "source": "tests/fixtures/common-formats/guide.md",
        "stages": ["extract", "rebuild", "validate_output"],
    },
    "core.ios-strings": {
        "source": "tests/fixtures/ios-project/App/en.lproj/Localizable.strings",
        "stages": ["extract", "rebuild", "validate_output"],
    },
    "core.xcstrings": {
        "source": "tests/fixtures/xcstrings-project/App/Localizable.xcstrings",
        "stages": ["extract", "rebuild", "validate_output"],
    },
}


def build_adapter_evidence_artifacts(
    state_dir: Path,
    *,
    repo_root: Path | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    root = _repo_root(state_dir, repo_root)
    support_matrix = _support_matrix(state_dir, root, run_id)
    release_regression = build_adapter_regression_evidence_report(state_dir, support_matrix=support_matrix, repo_root=root, run_id=run_id, write=False)
    release_audit = build_adapter_release_audit(state_dir, support_matrix=support_matrix, regression_report=release_regression, run_id=run_id, write=False)
    promotion_decision = build_adapter_promotion_decision(
        state_dir,
        support_matrix=support_matrix,
        release_audit=release_audit,
        regression_report=release_regression,
        run_id=run_id,
        write=False,
    )
    provenance = build_adapter_evidence_provenance(state_dir, repo_root=root, support_matrix=support_matrix, run_id=run_id, write=write)
    fixtures = build_adapter_fixture_manifest(state_dir, provenance=provenance, repo_root=repo_root, run_id=run_id, write=write)
    regression = build_adapter_regression_check_report(state_dir, provenance=provenance, fixture_manifest=fixtures, run_id=run_id, write=write)
    gaps = build_adapter_evidence_gap_report(state_dir, provenance=provenance, regression_report=regression, run_id=run_id, write=write)
    readiness = build_adapter_promotion_readiness_report(
        state_dir,
        provenance=provenance,
        regression_report=regression,
        gap_report=gaps,
        promotion_decision=promotion_decision,
        run_id=run_id,
        write=write,
    )
    return {
        "adapter_evidence_provenance": provenance,
        "adapter_fixture_manifest": fixtures,
        "adapter_regression_check_report": regression,
        "adapter_evidence_gap_report": gaps,
        "adapter_promotion_readiness_report": readiness,
    }


def build_adapter_evidence_provenance(
    state_dir: Path,
    *,
    repo_root: Path | None = None,
    support_matrix: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    root = _repo_root(state_dir, repo_root)
    support_matrix = support_matrix or _support_matrix(state_dir, root, run_id)
    previous = _previous_items(state_dir / ADAPTER_EVIDENCE_PROVENANCE_JSON, "evidence_items", "evidence_id")
    items = []
    for adapter in support_matrix.get("adapters", []):
        items.extend(_evidence_items_for_adapter(adapter, root, previous))
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-adapter-evidence-provenance-v1",
        "artifact": ADAPTER_EVIDENCE_PROVENANCE_JSON,
        "run_id": run_id or support_matrix.get("run_id") or "adapter-evidence",
        "status": _status_from_items(items),
        "evidence_classes": sorted({item["evidence_class"] for item in items}),
        "adapter_count": len(support_matrix.get("adapters", [])),
        "evidence_items": items,
        "summary": _evidence_summary(items),
        "source_artifact_references": [ADAPTER_SUPPORT_MATRIX_JSON],
        "limitations": [
            "adapter evidence provenance explains release support evidence and does not prove translation quality",
            "synthetic, local, benchmark, or fixture evidence does not imply provider-backed or production quality",
        ],
    }
    if write:
        write_json(state_dir / ADAPTER_EVIDENCE_PROVENANCE_JSON, report)
    return report


def read_adapter_evidence_provenance(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / ADAPTER_EVIDENCE_PROVENANCE_JSON)


def build_adapter_fixture_manifest(
    state_dir: Path,
    *,
    provenance: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    root = _repo_root(state_dir, repo_root)
    provenance = provenance or build_adapter_evidence_provenance(state_dir, repo_root=root, run_id=run_id, write=False)
    fixtures = []
    for item in provenance.get("evidence_items", []):
        if item.get("evidence_class") not in {"fixture_round_trip", "fixture_extract_only"}:
            continue
        fixtures.append(
            {
                "fixture_id": item["evidence_id"].replace("adapter-evidence-", "adapter-fixture-"),
                "adapter_id": item["adapter_id"],
                "evidence_class": item["evidence_class"],
                "input_files": item.get("input_files", []),
                "expected_outputs": item.get("expected_outputs", []),
                "lifecycle_stages_tested": item.get("lifecycle_stages_tested", []),
                "source_hashes": item.get("source_hashes", {}),
                "target_hashes": item.get("target_hashes", {}),
                "qa_result": item.get("qa_result", "not_recorded"),
                "freshness": item.get("freshness", "unknown"),
                "known_limitations": item.get("known_limitations", []),
            }
        )
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-adapter-fixture-manifest-v1",
        "artifact": ADAPTER_FIXTURE_MANIFEST_JSON,
        "run_id": run_id or provenance.get("run_id") or "adapter-evidence",
        "status": _status_from_fixture_manifest(fixtures),
        "fixtures": fixtures,
        "summary": {
            "fixture_count": len(fixtures),
            "current_count": sum(1 for item in fixtures if item.get("freshness") == "current"),
            "stale_count": sum(1 for item in fixtures if item.get("freshness") == "stale"),
            "missing_count": sum(1 for item in fixtures if item.get("freshness") == "missing"),
        },
        "source_artifact_references": [ADAPTER_EVIDENCE_PROVENANCE_JSON],
        "repo_root": root.as_posix(),
    }
    if write:
        write_json(state_dir / ADAPTER_FIXTURE_MANIFEST_JSON, manifest)
    return manifest


def read_adapter_fixture_manifest(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / ADAPTER_FIXTURE_MANIFEST_JSON)


def build_adapter_regression_check_report(
    state_dir: Path,
    *,
    provenance: dict[str, Any] | None = None,
    fixture_manifest: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    provenance = provenance or _optional_json(state_dir / ADAPTER_EVIDENCE_PROVENANCE_JSON)
    fixture_manifest = fixture_manifest or _optional_json(state_dir / ADAPTER_FIXTURE_MANIFEST_JSON)
    by_adapter = _items_by_adapter(provenance.get("evidence_items", []))
    checks = [_regression_check(adapter_id, items) for adapter_id, items in sorted(by_adapter.items())]
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-adapter-regression-check-report-v1",
        "artifact": ADAPTER_REGRESSION_CHECK_REPORT_JSON,
        "run_id": run_id or provenance.get("run_id") or "adapter-evidence",
        "status": _status_from_checks(checks),
        "checks": checks,
        "summary": {
            "adapter_count": len(checks),
            "passed_count": sum(1 for item in checks if item.get("status") == "pass"),
            "warning_count": sum(1 for item in checks if item.get("status") == "warning"),
            "failed_count": sum(1 for item in checks if item.get("status") == "fail"),
        },
        "source_artifact_references": _existing_names((ADAPTER_EVIDENCE_PROVENANCE_JSON, provenance), (ADAPTER_FIXTURE_MANIFEST_JSON, fixture_manifest)),
    }
    if write:
        write_json(state_dir / ADAPTER_REGRESSION_CHECK_REPORT_JSON, report)
    return report


def read_adapter_regression_check_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / ADAPTER_REGRESSION_CHECK_REPORT_JSON)


def build_adapter_evidence_gap_report(
    state_dir: Path,
    *,
    provenance: dict[str, Any] | None = None,
    regression_report: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    provenance = provenance or _optional_json(state_dir / ADAPTER_EVIDENCE_PROVENANCE_JSON)
    regression_report = regression_report or _optional_json(state_dir / ADAPTER_REGRESSION_CHECK_REPORT_JSON)
    gaps = []
    for check in regression_report.get("checks", []):
        adapter_id = check.get("adapter_id", "unknown")
        for missing in check.get("missing_lifecycle_stages", []):
            gaps.append(_gap(adapter_id, "missing_lifecycle_stage", f"missing {missing} evidence", "blocking" if missing in {"rebuild", "validate_output"} else "warning"))
        if check.get("status") == "warning":
            gaps.append(_gap(adapter_id, "promotion_evidence_limited", "evidence supports limited or seed claims only", "warning"))
        if check.get("stale_evidence_count", 0):
            gaps.append(_gap(adapter_id, "stale_evidence", "adapter evidence is stale", "blocking"))
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-adapter-evidence-gap-report-v1",
        "artifact": ADAPTER_EVIDENCE_GAP_REPORT_JSON,
        "run_id": run_id or provenance.get("run_id") or "adapter-evidence",
        "status": "blocked" if any(item["severity"] == "blocking" for item in gaps) else "ready_with_warnings" if gaps else "ready",
        "gaps": gaps,
        "summary": {
            "gap_count": len(gaps),
            "blocking_count": sum(1 for item in gaps if item["severity"] == "blocking"),
            "warning_count": sum(1 for item in gaps if item["severity"] == "warning"),
        },
        "source_artifact_references": _existing_names((ADAPTER_EVIDENCE_PROVENANCE_JSON, provenance), (ADAPTER_REGRESSION_CHECK_REPORT_JSON, regression_report)),
    }
    if write:
        write_json(state_dir / ADAPTER_EVIDENCE_GAP_REPORT_JSON, report)
    return report


def read_adapter_evidence_gap_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / ADAPTER_EVIDENCE_GAP_REPORT_JSON)


def build_adapter_promotion_readiness_report(
    state_dir: Path,
    *,
    provenance: dict[str, Any] | None = None,
    regression_report: dict[str, Any] | None = None,
    gap_report: dict[str, Any] | None = None,
    promotion_decision: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    provenance = provenance or _optional_json(state_dir / ADAPTER_EVIDENCE_PROVENANCE_JSON)
    regression_report = regression_report or _optional_json(state_dir / ADAPTER_REGRESSION_CHECK_REPORT_JSON)
    gap_report = gap_report or _optional_json(state_dir / ADAPTER_EVIDENCE_GAP_REPORT_JSON)
    promotion_decision = promotion_decision or _promotion_decision(state_dir, repo_root=repo_root, run_id=run_id)
    gaps_by_adapter = _gaps_by_adapter(gap_report.get("gaps", []))
    checks = {item.get("adapter_id"): item for item in regression_report.get("checks", [])}
    rows = []
    for decision in promotion_decision.get("decisions", []):
        adapter_id = decision.get("adapter_id")
        check = checks.get(adapter_id, {})
        gaps = gaps_by_adapter.get(adapter_id, [])
        readiness = _readiness_status(decision, check, gaps)
        rows.append(
            {
                "adapter_id": adapter_id,
                "promotion_status": decision.get("promotion_status"),
                "readiness_status": readiness,
                "supported_public_claim": decision.get("public_claim"),
                "unsupported_claims": decision.get("forbidden_claims", []),
                "evidence_classes": check.get("evidence_classes", []),
                "gaps": gaps,
                "known_limitations": decision.get("limitations", []),
            }
        )
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-adapter-promotion-readiness-report-v1",
        "artifact": ADAPTER_PROMOTION_READINESS_REPORT_JSON,
        "run_id": run_id or provenance.get("run_id") or "adapter-evidence",
        "status": _status_from_readiness(rows),
        "adapters": rows,
        "summary": {
            "adapter_count": len(rows),
            "ready_count": sum(1 for item in rows if item["readiness_status"] == "ready"),
            "warning_count": sum(1 for item in rows if item["readiness_status"] == "ready_with_warnings"),
            "blocked_count": sum(1 for item in rows if item["readiness_status"] == "blocked"),
        },
        "forbidden_claims": sorted({claim for item in rows for claim in item.get("unsupported_claims", [])}),
        "source_artifact_references": _existing_names(
            (ADAPTER_EVIDENCE_PROVENANCE_JSON, provenance),
            (ADAPTER_REGRESSION_CHECK_REPORT_JSON, regression_report),
            (ADAPTER_EVIDENCE_GAP_REPORT_JSON, gap_report),
            (ADAPTER_PROMOTION_DECISION_JSON, promotion_decision),
        ),
    }
    if write:
        write_json(state_dir / ADAPTER_PROMOTION_READINESS_REPORT_JSON, report)
    return report


def read_adapter_promotion_readiness_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / ADAPTER_PROMOTION_READINESS_REPORT_JSON)


def adapter_evidence_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in ADAPTER_EVIDENCE_ASSETS.items() if (state_dir / name).is_file()}


def _support_matrix(state_dir: Path, repo_root: Path, run_id: str | None) -> dict[str, Any]:
    return read_adapter_support_matrix(state_dir) if (state_dir / ADAPTER_SUPPORT_MATRIX_JSON).is_file() else build_adapter_support_matrix(state_dir, repo_root=repo_root, run_id=run_id, write=False)


def _promotion_decision(state_dir: Path, *, repo_root: Path | None = None, run_id: str | None = None) -> dict[str, Any]:
    if (state_dir / ADAPTER_PROMOTION_DECISION_JSON).is_file():
        return read_adapter_promotion_decision(state_dir)
    root = _repo_root(state_dir, repo_root)
    matrix = _optional_json(state_dir / ADAPTER_SUPPORT_MATRIX_JSON) or build_adapter_support_matrix(state_dir, repo_root=root, run_id=run_id, write=False)
    audit = _optional_json(state_dir / ADAPTER_RELEASE_AUDIT_JSON)
    if not audit:
        regression = build_adapter_regression_evidence_report(state_dir, support_matrix=matrix, repo_root=root, run_id=run_id, write=False)
        audit = build_adapter_release_audit(state_dir, support_matrix=matrix, regression_report=regression, run_id=run_id, write=False)
    else:
        regression = _optional_json(state_dir / ADAPTER_REGRESSION_EVIDENCE_REPORT_JSON)
    return build_adapter_promotion_decision(state_dir, support_matrix=matrix, release_audit=audit, regression_report=regression, run_id=run_id, write=False)


def _evidence_items_for_adapter(adapter: dict[str, Any], repo_root: Path, previous: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    adapter_id = str(adapter.get("adapter_id") or "unknown")
    evidence = adapter.get("evidence", {})
    limitations = adapter.get("known_limitations", [])
    items = [
        _item(adapter, "unit_test", "current", [], limitations, qa_result="not_quality_proof"),
        _item(adapter, "contract_test", "current" if evidence.get("contract_tests") == "present" else "missing", ["detect"], limitations),
    ]
    fixture = _fixture_item(adapter, repo_root, previous)
    if fixture:
        items.append(fixture)
    if evidence.get("benchmark_evidence") == "present":
        items.append(_item(adapter, "benchmark_controlled", "current", ["extract", "validate_output"], limitations, source_refs=["benchmark reports"]))
    if evidence.get("real_project_smoke_evidence") == "present":
        items.append(_item(adapter, "real_project_smoke", "current", ["extract", "rebuild", "validate_output"], limitations, source_refs=["adapter release evidence override"]))
    if evidence.get("apply_to_copy_evidence") == "present":
        items.append(_item(adapter, "apply_to_copy", "current", ["plan_apply", "apply_to_copy"], limitations, source_refs=["adapter release evidence override"]))
    return items


def _fixture_item(adapter: dict[str, Any], repo_root: Path, previous: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    adapter_id = str(adapter.get("adapter_id") or "unknown")
    if adapter.get("evidence", {}).get("fixture_tests") != "present":
        return None
    ref = FIXTURE_REFERENCES.get(adapter_id, {})
    evidence_class = "fixture_extract_only" if adapter.get("declared_round_trip_level") == "extract_only" else "fixture_round_trip"
    source_paths = [ref["source"]] if ref.get("source") else []
    target_paths = [ref["target"]] if ref.get("target") else []
    source_hashes = _hashes(repo_root, source_paths)
    target_hashes = _hashes(repo_root, target_paths)
    freshness = _freshness(source_paths, target_paths, source_hashes, target_hashes, previous.get(_evidence_id(adapter_id, evidence_class)))
    return _item(
        adapter,
        evidence_class,
        freshness,
        ref.get("stages", ["extract"]),
        adapter.get("known_limitations", []),
        input_files=source_paths,
        expected_outputs=target_paths,
        source_hashes=source_hashes,
        target_hashes=target_hashes,
        qa_result="pass" if freshness in {"current", "stale"} else "not_recorded",
    )


def _item(
    adapter: dict[str, Any] | str,
    evidence_class: str,
    freshness: str,
    stages: list[str],
    limitations: list[str],
    *,
    input_files: list[str] | None = None,
    expected_outputs: list[str] | None = None,
    source_hashes: dict[str, str] | None = None,
    target_hashes: dict[str, str] | None = None,
    qa_result: str = "not_recorded",
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    if isinstance(adapter, dict):
        adapter_id = str(adapter.get("adapter_id") or "unknown")
        declared_round_trip = adapter.get("declared_round_trip_level", "unknown")
        capability_classification = adapter.get("capability_classification", "unknown")
    else:
        adapter_id = adapter
        declared_round_trip = "unknown"
        capability_classification = "unknown"
    return {
        "evidence_id": _evidence_id(adapter_id, evidence_class),
        "adapter_id": adapter_id,
        "evidence_class": evidence_class,
        "declared_round_trip_level": declared_round_trip,
        "capability_classification": capability_classification,
        "freshness": freshness,
        "lifecycle_stages_tested": sorted(set(stages), key=lambda item: LIFECYCLE.index(item) if item in LIFECYCLE else 99),
        "input_files": input_files or [],
        "expected_outputs": expected_outputs or [],
        "source_hashes": source_hashes or {},
        "target_hashes": target_hashes or {},
        "qa_result": qa_result,
        "source_artifact_references": source_refs or [ADAPTER_SUPPORT_MATRIX_JSON],
        "known_limitations": limitations,
    }


def _regression_check(adapter_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    classes = sorted({item["evidence_class"] for item in items})
    stages = sorted({stage for item in items for stage in item.get("lifecycle_stages_tested", [])}, key=lambda item: LIFECYCLE.index(item) if item in LIFECYCLE else 99)
    stale_count = sum(1 for item in items if item.get("freshness") == "stale")
    missing_count = sum(1 for item in items if item.get("freshness") == "missing")
    declared_levels = {item.get("declared_round_trip_level") for item in items}
    requires_round_trip = "full_round_trip" in declared_levels or any(item.get("evidence_class") == "fixture_round_trip" for item in items)
    required = ["extract", "rebuild", "validate_output"] if requires_round_trip else ["extract"]
    missing_stages = [stage for stage in required if stage not in stages]
    unit_only = classes == ["contract_test", "unit_test"]
    status = "fail" if stale_count or any(stage in {"rebuild", "validate_output"} for stage in missing_stages) else "warning" if missing_count or missing_stages or unit_only else "pass"
    return {
        "adapter_id": adapter_id,
        "status": status,
        "evidence_classes": classes,
        "lifecycle_stages_checked": stages,
        "missing_lifecycle_stages": missing_stages,
        "stale_evidence_count": stale_count,
        "missing_evidence_count": missing_count,
        "benchmark_evidence_separated": "benchmark_controlled" in classes or "benchmark_agent_system" in classes,
        "unit_tests_alone": unit_only,
    }


def _gap(adapter_id: str, gap_type: str, message: str, severity: str) -> dict[str, Any]:
    return {
        "gap_id": f"adapter-gap-{_short_hash(adapter_id + gap_type + message)}",
        "adapter_id": adapter_id,
        "gap_type": gap_type,
        "severity": severity,
        "message": message,
        "recommended_action": "add current scoped fixture/regression evidence before promotion",
    }


def _readiness_status(decision: dict[str, Any], check: dict[str, Any], gaps: list[dict[str, Any]]) -> str:
    if any(item.get("severity") == "blocking" for item in gaps) or check.get("status") == "fail":
        return "blocked"
    if decision.get("promotion_status") == "stable_baseline" and check.get("status") == "pass":
        return "ready"
    return "ready_with_warnings"


def _freshness(
    source_paths: list[str],
    target_paths: list[str],
    source_hashes: dict[str, str],
    target_hashes: dict[str, str],
    previous: dict[str, Any] | None,
) -> str:
    expected_paths = source_paths + target_paths
    observed_hashes = {**source_hashes, **target_hashes}
    if expected_paths and len(observed_hashes) != len(expected_paths):
        return "missing"
    if previous:
        previous_hashes = {**previous.get("source_hashes", {}), **previous.get("target_hashes", {})}
        if previous_hashes and previous_hashes != observed_hashes:
            return "stale"
    return "current" if observed_hashes or not expected_paths else "unknown"


def _hashes(root: Path, paths: list[str]) -> dict[str, str]:
    hashes = {}
    for value in paths:
        path = root / value
        if path.is_file():
            hashes[value] = sha256_file(path)
    return hashes


def _repo_root(state_dir: Path, repo_root: Path | None) -> Path:
    if repo_root is not None:
        return repo_root.resolve()
    current = state_dir.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "adapters").is_dir():
            return candidate
    return Path.cwd().resolve()


def _previous_items(path: Path, list_key: str, id_key: str) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    try:
        value = read_json(path)
    except (OSError, ValueError):
        return {}
    return {str(item.get(id_key)): item for item in value.get(list_key, []) if isinstance(item, dict) and item.get(id_key)}


def _items_by_adapter(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        result.setdefault(str(item.get("adapter_id") or "unknown"), []).append(item)
    return result


def _gaps_by_adapter(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        result.setdefault(str(item.get("adapter_id") or "unknown"), []).append(item)
    return result


def _status_from_items(items: list[dict[str, Any]]) -> str:
    if any(item.get("freshness") == "stale" for item in items):
        return "stale"
    if any(item.get("freshness") == "missing" for item in items):
        return "partial"
    return "ready_with_warnings"


def _status_from_fixture_manifest(fixtures: list[dict[str, Any]]) -> str:
    if any(item.get("freshness") == "stale" for item in fixtures):
        return "stale"
    if any(item.get("freshness") == "missing" for item in fixtures):
        return "partial"
    return "ready_with_warnings" if fixtures else "missing"


def _status_from_checks(checks: list[dict[str, Any]]) -> str:
    if any(item.get("status") == "fail" for item in checks):
        return "blocked"
    if any(item.get("status") == "warning" for item in checks):
        return "ready_with_warnings"
    return "ready"


def _status_from_readiness(rows: list[dict[str, Any]]) -> str:
    if any(item.get("readiness_status") == "blocked" for item in rows):
        return "blocked"
    if any(item.get("readiness_status") == "ready_with_warnings" for item in rows):
        return "ready_with_warnings"
    return "ready" if rows else "missing"


def _evidence_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "item_count": len(items),
        "current_count": sum(1 for item in items if item.get("freshness") == "current"),
        "stale_count": sum(1 for item in items if item.get("freshness") == "stale"),
        "missing_count": sum(1 for item in items if item.get("freshness") == "missing"),
        "benchmark_item_count": sum(1 for item in items if str(item.get("evidence_class", "")).startswith("benchmark_")),
        "real_project_smoke_count": sum(1 for item in items if item.get("evidence_class") == "real_project_smoke"),
    }


def _evidence_id(adapter_id: str, evidence_class: str) -> str:
    return f"adapter-evidence-{_short_hash(adapter_id + ':' + evidence_class)}"


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _existing_names(*items: tuple[str, Any]) -> list[str]:
    return [name for name, value in items if bool(value)]


def _optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing adapter evidence artifact: {path}")
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Invalid adapter evidence artifact: {path}")
    return value
