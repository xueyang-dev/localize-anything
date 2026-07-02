from __future__ import annotations

from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .contracts import validate_adapter_tree
from .io_utils import read_json, write_json


ADAPTER_SUPPORT_MATRIX_JSON = "adapter-support-matrix.json"
ADAPTER_RELEASE_AUDIT_JSON = "adapter-release-audit.json"
ADAPTER_PROMOTION_DECISION_JSON = "adapter-promotion-decision.json"
ADAPTER_REGRESSION_EVIDENCE_REPORT_JSON = "adapter-regression-evidence-report.json"
ADAPTER_PUBLIC_CLAIMS_REPORT_MD = "adapter-public-claims-report.md"

ADAPTER_RELEASE_ASSETS = {
    "adapter_support_matrix": ADAPTER_SUPPORT_MATRIX_JSON,
    "adapter_release_audit": ADAPTER_RELEASE_AUDIT_JSON,
    "adapter_promotion_decision": ADAPTER_PROMOTION_DECISION_JSON,
    "adapter_regression_evidence_report": ADAPTER_REGRESSION_EVIDENCE_REPORT_JSON,
    "adapter_public_claims_report": ADAPTER_PUBLIC_CLAIMS_REPORT_MD,
}

FULL_ROUND_TRIP_REQUIREMENTS = {"extract", "rebuild", "validate_output"}
CORE_STABLE_ADAPTERS = {"core.json-locale", "core.gettext-po", "core.tabular", "core.subtitles", "core.xliff"}
SEED_ADAPTERS = {"core.yaml-toml", "core.markup"}
EXPERIMENTAL_ADAPTERS = {"core.android-strings", "core.ios-strings", "core.xcstrings", "core.word-document"}

EVIDENCE_OVERRIDES: dict[str, dict[str, Any]] = {
    "core.json-locale": {"fixture_tests": True, "regression_evidence": True, "release_audit_support": True},
    "core.gettext-po": {"fixture_tests": True, "regression_evidence": True, "release_audit_support": True},
    "core.tabular": {"fixture_tests": True, "regression_evidence": True, "release_audit_support": True},
    "core.subtitles": {"fixture_tests": True, "regression_evidence": True, "release_audit_support": True},
    "core.xliff": {"fixture_tests": True, "regression_evidence": True, "release_audit_support": True},
    "core.yaml-toml": {"fixture_tests": True, "regression_evidence": True, "release_audit_support": False},
    "core.markup": {"fixture_tests": True, "regression_evidence": True, "release_audit_support": False},
    "core.android-strings": {
        "fixture_tests": True,
        "benchmark_evidence": True,
        "real_project_smoke_evidence": True,
        "apply_to_copy_evidence": True,
        "release_audit_support": False,
    },
    "core.ios-strings": {"fixture_tests": True, "release_audit_support": False},
    "core.xcstrings": {"fixture_tests": True, "benchmark_evidence": True, "release_audit_support": False},
    "core.word-document": {"fixture_tests": True, "release_audit_support": False},
    "scenario.wesnoth": {"fixture_tests": True, "release_audit_support": False},
}

KNOWN_LIMITATIONS = {
    "core.android-strings": [
        "experimental platform slice",
        "does not cover APK decompilation, signing, layouts, drawables, or build-system changes",
    ],
    "core.ios-strings": [
        "experimental platform slice",
        "does not edit Xcode project files, storyboards, assets, or build settings",
    ],
    "core.xcstrings": [
        "experimental platform slice",
        "does not edit Xcode project files or application code",
    ],
    "core.word-document": [
        "experimental document slice",
        "does not verify DOCX rendered layout or image text",
    ],
    "core.markup": ["does not localize HTML attributes or image alt text"],
    "core.yaml-toml": ["complex YAML/TOML constructs remain bounded by parser support"],
    "scenario.wesnoth": ["scenario overlay is extract-only and not a full rebuild adapter"],
}


def build_adapter_release_artifacts(
    state_dir: Path,
    *,
    repo_root: Path | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    matrix = build_adapter_support_matrix(state_dir, repo_root=repo_root, run_id=run_id, write=write)
    regression = build_adapter_regression_evidence_report(state_dir, support_matrix=matrix, repo_root=repo_root, run_id=run_id, write=write)
    audit = build_adapter_release_audit(state_dir, support_matrix=matrix, regression_report=regression, run_id=run_id, write=write)
    decision = build_adapter_promotion_decision(state_dir, support_matrix=matrix, release_audit=audit, regression_report=regression, run_id=run_id, write=write)
    markdown = build_adapter_public_claims_report(state_dir, promotion_decision=decision, support_matrix=matrix, run_id=run_id, write=write)
    return {
        "adapter_support_matrix": matrix,
        "adapter_regression_evidence_report": regression,
        "adapter_release_audit": audit,
        "adapter_promotion_decision": decision,
        "adapter_public_claims_report": markdown,
    }


def build_adapter_support_matrix(
    state_dir: Path,
    *,
    repo_root: Path | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    root = _repo_root(state_dir, repo_root)
    contract = validate_adapter_tree(root / "adapters")
    rows = [_adapter_row(path, root) for path in sorted((root / "adapters").rglob("adapter.json"))]
    matrix = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-adapter-support-matrix-v1",
        "artifact": ADAPTER_SUPPORT_MATRIX_JSON,
        "run_id": run_id or "adapter-release-audit",
        "status": "blocked" if contract.get("status") != "pass" else "ready_with_warnings",
        "adapter_count": len(rows),
        "adapters": rows,
        "summary": _matrix_summary(rows),
        "contract_validation": contract,
        "claim_boundaries": {
            "adapter_existence_implies_stable_support": False,
            "unit_tests_alone_promote_adapter": False,
            "full_round_trip_requires_fixture_qa_and_regression_evidence": True,
        },
    }
    if write:
        write_json(state_dir / ADAPTER_SUPPORT_MATRIX_JSON, matrix)
    return matrix


def read_adapter_support_matrix(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / ADAPTER_SUPPORT_MATRIX_JSON)


def build_adapter_regression_evidence_report(
    state_dir: Path,
    *,
    support_matrix: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    support_matrix = support_matrix or build_adapter_support_matrix(state_dir, repo_root=repo_root, run_id=run_id, write=False)
    rows = []
    for adapter in support_matrix.get("adapters", []):
        evidence = adapter.get("evidence", {})
        rows.append(
            {
                "adapter_id": adapter.get("adapter_id"),
                "capability_classification": adapter.get("capability_classification"),
                "contract_tests": evidence.get("contract_tests", "missing"),
                "fixture_tests": evidence.get("fixture_tests", "missing"),
                "benchmark_evidence": evidence.get("benchmark_evidence", "missing"),
                "real_project_smoke_evidence": evidence.get("real_project_smoke_evidence", "missing"),
                "apply_to_copy_evidence": evidence.get("apply_to_copy_evidence", "missing"),
                "release_audit_support": evidence.get("release_audit_support", "missing"),
                "full_round_trip_supported": adapter.get("full_round_trip_supported", False),
                "known_limitations": adapter.get("known_limitations", []),
            }
        )
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-adapter-regression-evidence-report-v1",
        "artifact": ADAPTER_REGRESSION_EVIDENCE_REPORT_JSON,
        "run_id": run_id or support_matrix.get("run_id") or "adapter-release-audit",
        "status": "ready_with_warnings",
        "evidence": rows,
        "summary": {
            "adapter_count": len(rows),
            "full_round_trip_supported_count": sum(1 for row in rows if row["full_round_trip_supported"]),
            "benchmark_evidence_count": sum(1 for row in rows if row["benchmark_evidence"] == "present"),
            "missing_release_audit_support_count": sum(1 for row in rows if row["release_audit_support"] != "present"),
        },
        "limitations": ["regression evidence is structural and does not prove semantic translation quality"],
        "source_artifact_references": [ADAPTER_SUPPORT_MATRIX_JSON],
    }
    if write:
        write_json(state_dir / ADAPTER_REGRESSION_EVIDENCE_REPORT_JSON, report)
    return report


def read_adapter_regression_evidence_report(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / ADAPTER_REGRESSION_EVIDENCE_REPORT_JSON)


def build_adapter_release_audit(
    state_dir: Path,
    *,
    support_matrix: dict[str, Any] | None = None,
    regression_report: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    support_matrix = support_matrix or _optional_json(state_dir / ADAPTER_SUPPORT_MATRIX_JSON)
    regression_report = regression_report or _optional_json(state_dir / ADAPTER_REGRESSION_EVIDENCE_REPORT_JSON)
    rows = support_matrix.get("adapters", [])
    blockers = []
    for adapter in rows:
        if adapter.get("declared_round_trip_level") == "full_round_trip" and not adapter.get("full_round_trip_supported"):
            blockers.append(_blocker(adapter["adapter_id"], "overbroad_full_round_trip_claim", "full_round_trip lacks required evidence"))
        if adapter.get("evidence", {}).get("contract_tests") != "present":
            blockers.append(_blocker(adapter["adapter_id"], "missing_contract_evidence", "adapter contract validation is missing"))
    audit = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-adapter-release-audit-v1",
        "artifact": ADAPTER_RELEASE_AUDIT_JSON,
        "run_id": run_id or support_matrix.get("run_id") or "adapter-release-audit",
        "status": "blocked" if blockers else "ready_with_warnings",
        "stable_baseline_adapters": [row["adapter_id"] for row in rows if row.get("capability_classification") == "stable_baseline"],
        "seed_adapters": [row["adapter_id"] for row in rows if row.get("capability_classification") == "implemented_seed"],
        "experimental_adapters": [row["adapter_id"] for row in rows if row.get("capability_classification") == "experimental"],
        "partial_adapters": [row["adapter_id"] for row in rows if row.get("capability_classification") == "partial"],
        "unsupported_adapters": [row["adapter_id"] for row in rows if row.get("capability_classification") == "unsupported"],
        "blockers": blockers,
        "forbidden_claims": _forbidden_claims(rows, blockers),
        "source_artifact_references": [ADAPTER_SUPPORT_MATRIX_JSON, ADAPTER_REGRESSION_EVIDENCE_REPORT_JSON] if regression_report else [ADAPTER_SUPPORT_MATRIX_JSON],
    }
    if write:
        write_json(state_dir / ADAPTER_RELEASE_AUDIT_JSON, audit)
    return audit


def read_adapter_release_audit(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / ADAPTER_RELEASE_AUDIT_JSON)


def build_adapter_promotion_decision(
    state_dir: Path,
    *,
    support_matrix: dict[str, Any] | None = None,
    release_audit: dict[str, Any] | None = None,
    regression_report: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    support_matrix = support_matrix or _optional_json(state_dir / ADAPTER_SUPPORT_MATRIX_JSON)
    release_audit = release_audit or _optional_json(state_dir / ADAPTER_RELEASE_AUDIT_JSON)
    regression_report = regression_report or _optional_json(state_dir / ADAPTER_REGRESSION_EVIDENCE_REPORT_JSON)
    decisions = [_promotion(row) for row in support_matrix.get("adapters", [])]
    decision = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-adapter-promotion-decision-v1",
        "artifact": ADAPTER_PROMOTION_DECISION_JSON,
        "run_id": run_id or support_matrix.get("run_id") or "adapter-release-audit",
        "status": "ready_with_warnings" if decisions else "missing",
        "decisions": decisions,
        "forbidden_claims": release_audit.get("forbidden_claims", []),
        "source_artifact_references": _existing_names(
            (ADAPTER_SUPPORT_MATRIX_JSON, support_matrix),
            (ADAPTER_RELEASE_AUDIT_JSON, release_audit),
            (ADAPTER_REGRESSION_EVIDENCE_REPORT_JSON, regression_report),
        ),
    }
    if write:
        write_json(state_dir / ADAPTER_PROMOTION_DECISION_JSON, decision)
    return decision


def read_adapter_promotion_decision(state_dir: Path) -> dict[str, Any]:
    return _required_json(state_dir / ADAPTER_PROMOTION_DECISION_JSON)


def build_adapter_public_claims_report(
    state_dir: Path,
    *,
    promotion_decision: dict[str, Any] | None = None,
    support_matrix: dict[str, Any] | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> str:
    state_dir = state_dir.resolve()
    promotion_decision = promotion_decision or _optional_json(state_dir / ADAPTER_PROMOTION_DECISION_JSON)
    support_matrix = support_matrix or _optional_json(state_dir / ADAPTER_SUPPORT_MATRIX_JSON)
    lines = [
        "# Adapter Public Claims Report",
        "",
        "Adapter existence does not imply stable support. Public claims must follow the promotion decision and documented limitations.",
        "",
        "## Stable Baseline",
    ]
    for item in promotion_decision.get("decisions", []):
        if item.get("promotion_status") == "stable_baseline":
            lines.append(f"- `{item['adapter_id']}`: {item.get('public_claim', 'stable baseline within documented boundaries')}")
    lines.extend(["", "## Seed / Experimental / Partial", ""])
    for item in promotion_decision.get("decisions", []):
        if item.get("promotion_status") != "stable_baseline":
            lines.append(f"- `{item['adapter_id']}`: {item['promotion_status']} - {item.get('public_claim', 'limited claim only')}")
    lines.extend(["", "## Non-Claims", ""])
    for claim in promotion_decision.get("forbidden_claims", []):
        lines.append(f"- `{claim}`")
    lines.extend(["", f"Source: `{ADAPTER_SUPPORT_MATRIX_JSON}` ({support_matrix.get('adapter_count', 0)} adapters)."])
    markdown = "\n".join(lines) + "\n"
    if write:
        (state_dir / ADAPTER_PUBLIC_CLAIMS_REPORT_MD).write_text(markdown, encoding="utf-8")
    return markdown


def read_adapter_public_claims_report(state_dir: Path) -> str:
    path = state_dir / ADAPTER_PUBLIC_CLAIMS_REPORT_MD
    if not path.is_file():
        raise FileNotFoundError(f"Missing adapter artifact: {path}")
    return path.read_text(encoding="utf-8")


def adapter_release_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: name for key, name in ADAPTER_RELEASE_ASSETS.items() if (state_dir / name).is_file()}


def _adapter_row(path: Path, repo_root: Path) -> dict[str, Any]:
    manifest = read_json(path)
    adapter_id = str(manifest.get("id") or path.parent.name)
    capabilities = set(manifest.get("capabilities", []))
    round_trip = str(manifest.get("round_trip_level") or "unsupported")
    evidence = _evidence(adapter_id)
    full_supported = (
        round_trip == "full_round_trip"
        and FULL_ROUND_TRIP_REQUIREMENTS.issubset(capabilities)
        and evidence["contract_tests"] == "present"
        and evidence["fixture_tests"] == "present"
        and evidence["regression_evidence"] == "present"
    )
    classification = _classification(adapter_id, manifest, full_supported)
    return {
        "adapter_id": adapter_id,
        "name": manifest.get("name", adapter_id),
        "manifest_path": path.relative_to(repo_root).as_posix(),
        "formats": manifest.get("formats", []),
        "extensions": manifest.get("extensions", []),
        "implementation_status": manifest.get("implementation_status", "planned"),
        "declared_round_trip_level": round_trip,
        "capabilities": sorted(capabilities),
        "capability_classification": classification,
        "full_round_trip_supported": full_supported,
        "evidence": evidence,
        "known_limitations": KNOWN_LIMITATIONS.get(adapter_id, []),
        "forbidden_claims": _adapter_forbidden_claims(adapter_id, classification, full_supported),
    }


def _classification(adapter_id: str, manifest: dict[str, Any], full_supported: bool) -> str:
    status = str(manifest.get("implementation_status") or "planned")
    round_trip = str(manifest.get("round_trip_level") or "unsupported")
    if round_trip == "unsupported" or status == "planned":
        return "unsupported"
    if round_trip == "inspect_only":
        return "inspect_only"
    if adapter_id in EXPERIMENTAL_ADAPTERS or status == "experimental":
        return "experimental"
    if round_trip == "extract_only":
        return "partial"
    if adapter_id in CORE_STABLE_ADAPTERS and full_supported:
        return "stable_baseline"
    if adapter_id in SEED_ADAPTERS or status == "implemented":
        return "implemented_seed"
    return "partial"


def _evidence(adapter_id: str) -> dict[str, str]:
    overrides = EVIDENCE_OVERRIDES.get(adapter_id, {})
    return {
        "contract_tests": "present",
        "fixture_tests": "present" if overrides.get("fixture_tests") else "missing",
        "benchmark_evidence": "present" if overrides.get("benchmark_evidence") else "missing",
        "real_project_smoke_evidence": "present" if overrides.get("real_project_smoke_evidence") else "missing",
        "apply_to_copy_evidence": "present" if overrides.get("apply_to_copy_evidence") else "missing",
        "release_audit_support": "present" if overrides.get("release_audit_support") else "missing",
        "regression_evidence": "present" if overrides.get("regression_evidence") or overrides.get("benchmark_evidence") else "missing",
    }


def _promotion(row: dict[str, Any]) -> dict[str, Any]:
    classification = str(row.get("capability_classification") or "unsupported")
    if classification == "stable_baseline":
        status = "stable_baseline"
        claim = "stable baseline within documented format boundaries"
    elif classification == "implemented_seed":
        status = "implemented_seed"
        claim = "implemented seed; do not claim stable full adapter support"
    elif classification == "experimental":
        status = "experimental"
        claim = "experimental platform/document slice; preserve non-goals"
    elif classification == "inspect_only":
        status = "inspect_only"
        claim = "inspect-only support"
    else:
        status = "partial" if classification == "partial" else "unsupported"
        claim = "partial support only"
    return {
        "adapter_id": row.get("adapter_id"),
        "promotion_status": status,
        "public_claim": claim,
        "limitations": row.get("known_limitations", []),
        "forbidden_claims": row.get("forbidden_claims", []),
    }


def _adapter_forbidden_claims(adapter_id: str, classification: str, full_supported: bool) -> list[str]:
    claims = {"adapter_production_ready", "full_product_localization"}
    if not full_supported:
        claims.add("full_round_trip")
    if classification != "stable_baseline":
        claims.add(f"{adapter_id}_stable_support")
    if adapter_id in {"core.android-strings", "core.ios-strings", "core.xcstrings"}:
        claims.update({"full_platform_localization", "app_store_ready_localization"})
    if adapter_id == "core.word-document":
        claims.update({"docx_layout_verified", "document_render_verified"})
    return sorted(claims)


def _forbidden_claims(rows: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> list[str]:
    claims = {"adapter_production_ready", "full_product_localization"}
    for row in rows:
        claims.update(row.get("forbidden_claims", []))
    if blockers:
        claims.add("adapter_release_promotion_ready")
    return sorted(claims)


def _blocker(adapter_id: str, blocker_type: str, message: str) -> dict[str, str]:
    return {"adapter_id": adapter_id, "blocker_type": blocker_type, "severity": "blocking", "message": message}


def _matrix_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = {key: 0 for key in ["stable_baseline", "implemented_seed", "experimental", "partial", "inspect_only", "unsupported"]}
    for row in rows:
        classification = str(row.get("capability_classification") or "unsupported")
        summary[classification] = summary.get(classification, 0) + 1
    return summary


def _repo_root(state_dir: Path, repo_root: Path | None) -> Path:
    if repo_root is not None:
        return repo_root.resolve()
    current = state_dir.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "adapters").is_dir():
            return candidate
    return Path.cwd().resolve()


def _existing_names(*items: tuple[str, Any]) -> list[str]:
    return [name for name, value in items if bool(value)]


def _optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing adapter artifact: {path}")
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError(f"Invalid adapter artifact: {path}")
    return value
