from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, sha256_file, write_json
from .segment_repair import (
    REPAIR_HISTORY_JSONL,
    REPAIR_REQUEST_JSON,
    REPAIR_RESULT_JSON,
    SEGMENT_REGENERATION_PLAN_JSON,
    segment_repair_summary,
)
from .segment_staleness import REUSE_DECISION_JSON, STALE_SEGMENTS_JSONL, segment_staleness_summary


ARTIFACT_STATE_JSON = "artifact-state.json"

STATUS_VALUES = {
    "missing",
    "draft",
    "current",
    "stale",
    "superseded",
    "blocked",
    "accepted",
    "rejected",
    "requires_human_review",
}


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_id: str
    artifact_type: str
    path: str
    produced_by: str
    dependencies: tuple[str, ...] = ()
    required_for_handoff: bool = False
    required_for_delivery: bool = False
    location: str = "state"


STATE_ARTIFACTS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec("project_intake_report", "project_intake_report", "project-intake-report.json", "inspect"),
    ArtifactSpec("source_inventory", "source_inventory", "source-inventory.json", "inspect"),
    ArtifactSpec("current_manifest", "source_inventory", "current-manifest.json", "preflight"),
    ArtifactSpec("localization_brief_json", "localization_brief", "localization-brief.json", "preflight", required_for_handoff=True, required_for_delivery=True),
    ArtifactSpec("localization_brief_yaml", "localization_brief", "localization-brief.yaml", "preflight"),
    ArtifactSpec("candidate_terms", "candidate_terms", "candidate-terms.jsonl", "termbase_preflight"),
    ArtifactSpec("term_review_queue", "term_review_queue", "term-review-queue.json", "termbase_preflight", ("candidate_terms",)),
    ArtifactSpec("term_review_decisions", "term_review_decisions", "term-review-decisions.jsonl", "term_review"),
    ArtifactSpec("term_registry", "term_registry", "term-registry.csv", "term_governance"),
    ArtifactSpec("term_decisions", "term_decisions", "term-decisions.jsonl", "term_governance"),
    ArtifactSpec("forbidden_translations", "forbidden_translations", "forbidden-translations.csv", "term_governance"),
    ArtifactSpec(
        "termbase_preflight_report",
        "termbase_preflight_report",
        "termbase-preflight-report.json",
        "termbase_preflight",
        ("candidate_terms", "term_review_queue", "term_review_decisions", "term_registry", "term_decisions", "forbidden_translations"),
        required_for_handoff=True,
        required_for_delivery=True,
    ),
    ArtifactSpec(
        "generation_strategy",
        "generation_strategy",
        "generation-strategy.json",
        "generation_strategy",
        (
            "current_manifest",
            "localization_brief_json",
            "candidate_terms",
            "term_review_queue",
            "term_review_decisions",
            "term_registry",
            "term_decisions",
            "forbidden_translations",
            "termbase_preflight_report",
            "user_resolution_decisions",
        ),
        required_for_handoff=True,
        required_for_delivery=True,
    ),
    ArtifactSpec(
        "blocking_questions",
        "blocking_questions",
        "blocking-questions.json",
        "resolution_gate",
        ("generation_strategy", "termbase_preflight_report", "term_review_queue"),
        required_for_handoff=True,
    ),
    ArtifactSpec("resolution_options", "resolution_options", "resolution-options.json", "resolution_gate", ("blocking_questions",), required_for_handoff=True),
    ArtifactSpec("user_resolution_decisions", "user_resolution_decisions", "user-resolution-decisions.jsonl", "resolution_gate"),
    ArtifactSpec(
        "generation_handoff_decision",
        "generation_handoff_decision",
        "generation-handoff-decision.json",
        "generation_handoff_enforcement",
        (
            "generation_strategy",
            "blocking_questions",
            "resolution_options",
            "user_resolution_decisions",
            "termbase_preflight_report",
            "term_review_queue",
            "term_review_decisions",
            "term_registry",
            "term_decisions",
            "forbidden_translations",
            "localization_brief_json",
        ),
        required_for_handoff=True,
        required_for_delivery=True,
    ),
    ArtifactSpec("stale_segments", "stale_segments", STALE_SEGMENTS_JSONL, "segment_staleness"),
    ArtifactSpec("reuse_decision", "reuse_decision", REUSE_DECISION_JSON, "segment_staleness", ("stale_segments",)),
    ArtifactSpec(
        "segment_regeneration_plan",
        "segment_regeneration_plan",
        SEGMENT_REGENERATION_PLAN_JSON,
        "targeted_repair",
        ("stale_segments", "reuse_decision", "generation_strategy", "generation_handoff_decision", "termbase_preflight_report"),
    ),
    ArtifactSpec("repair_request", "repair_request", REPAIR_REQUEST_JSON, "targeted_repair", ("segment_regeneration_plan",)),
    ArtifactSpec("repair_result", "repair_result", REPAIR_RESULT_JSON, "targeted_repair", ("repair_request",)),
    ArtifactSpec("repair_history", "repair_history", REPAIR_HISTORY_JSONL, "targeted_repair", ("repair_result",)),
    ArtifactSpec(
        "state_delivery_manifest",
        "delivery_manifest",
        "delivery-manifest.json",
        "delivery_packaging",
        required_for_delivery=True,
    ),
)

RUN_ARTIFACTS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec("segments", "source_segments", "segments.jsonl", "extract", ("current_manifest",), required_for_handoff=True, required_for_delivery=True, location="run"),
    ArtifactSpec("batch_plan", "batch_plan", "batch-plan.json", "plan", ("segments",), required_for_handoff=True, location="run"),
    ArtifactSpec("generation_handoff", "generation_handoff", "generation-handoff.json", "generation_handoff", ("generation_strategy", "generation_handoff_decision", "batch_plan"), location="run"),
    ArtifactSpec(
        "generated_segments",
        "generated_segments",
        "generated.jsonl",
        "generation",
        (
            "segments",
            "localization_brief_json",
            "term_review_decisions",
            "term_registry",
            "term_decisions",
            "forbidden_translations",
            "user_resolution_decisions",
            "generation_strategy",
            "generation_handoff_decision",
            "generation_handoff",
        ),
        required_for_delivery=True,
        location="run",
    ),
    ArtifactSpec("llm_review_result", "review_result", "llm-review-result.json", "review", ("generated_segments",), location="run"),
    ArtifactSpec("review_sheet", "review_result", "review-sheet.json", "review", ("generated_segments",), location="run"),
    ArtifactSpec("run_summary", "run_summary", "run-summary.json", "run_summary", ("generation_handoff_decision", "user_resolution_decisions"), location="run"),
    ArtifactSpec(
        "delivery_decision",
        "delivery_decision",
        "delivery-decision.json",
        "delivery_decision",
        (
            "generated_segments",
            "review_sheet",
            "llm_review_result",
            "generation_strategy",
            "generation_handoff_decision",
            "term_review_decisions",
            "term_registry",
            "term_decisions",
            "forbidden_translations",
            "user_resolution_decisions",
            "state_delivery_manifest",
        ),
        required_for_delivery=True,
        location="run",
    ),
)

DELIVERY_ARTIFACTS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec("delivery_manifest", "delivery_manifest", "delivery-manifest.json", "delivery_packaging", ("generation_handoff_decision", "generated_segments"), required_for_delivery=True, location="delivery"),
)


def build_artifact_state(
    state_dir: Path,
    *,
    run_dir: Path | None = None,
    delivery_dir: Path | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    run_dir = run_dir.resolve() if run_dir else None
    delivery_dir = delivery_dir.resolve() if delivery_dir else None
    previous = _previous_artifacts(state_dir / ARTIFACT_STATE_JSON)
    specs = list(STATE_ARTIFACTS)
    if run_dir:
        specs.extend(RUN_ARTIFACTS)
    if delivery_dir:
        specs.extend(DELIVERY_ARTIFACTS)

    entries: dict[str, dict[str, Any]] = {}
    for spec in specs:
        path = _artifact_path(spec, state_dir, run_dir, delivery_dir)
        entries[spec.artifact_id] = _base_entry(spec, path, state_dir, run_dir, delivery_dir)

    downstream = _downstream_map(specs)
    for spec in specs:
        entry = entries[spec.artifact_id]
        entry["downstream_affected"] = downstream.get(spec.artifact_id, [])
        entry["source_dependency_hashes"] = _dependency_hashes(spec, entries)
        _apply_content_status(entry)
        _apply_previous_state_status(entry, previous.get(spec.artifact_id, {}), entries)

    artifacts = [_public_entry(entries[spec.artifact_id]) for spec in specs]
    stale_artifacts = [item for item in artifacts if item["status"] == "stale"]
    blocked_artifacts = [item for item in artifacts if item["status"] == "blocked"]
    review_artifacts = [item for item in artifacts if item["status"] == "requires_human_review"]
    missing_required = [
        item
        for item in artifacts
        if item["status"] == "missing" and (item.get("required_for_handoff") or item.get("required_for_delivery"))
    ]
    segment_state = segment_staleness_summary(state_dir)
    segment_decisions = segment_state.get("decisions", {})
    segment_summary = segment_state.get("summary", {})
    segment_handoff_policy = str(segment_decisions.get("generation_handoff_policy") or "allowed")
    segment_delivery_policy = str(segment_decisions.get("delivery_apply_policy") or "allowed")
    repair_state = segment_repair_summary(state_dir)
    repair_decisions = repair_state.get("decisions", {})
    repair_summary = repair_state.get("summary", {})
    repair_handoff_policy = str(repair_decisions.get("generation_handoff_policy") or "allowed")
    repair_delivery_policy = str(repair_decisions.get("delivery_apply_policy") or "allowed")
    status = _overall_status(stale_artifacts, blocked_artifacts, review_artifacts, missing_required, artifacts)
    status = _status_with_segment_state(status, segment_state)
    status = _status_with_repair_state(status, repair_state)
    handoff_policy = _merge_policy(
        "blocked" if any(item.get("affects_generation_handoff") for item in stale_artifacts + blocked_artifacts) else "allowed",
        segment_handoff_policy,
        repair_handoff_policy,
    )
    delivery_policy = _merge_policy(
        "blocked" if any(item.get("affects_delivery_or_apply") for item in stale_artifacts + blocked_artifacts) else "allowed",
        segment_delivery_policy,
        repair_delivery_policy,
    )
    state = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-artifact-state-v1",
        "run_id": run_id,
        "status": status,
        "safe_to_continue": status in {"current", "accepted"} and not stale_artifacts and not blocked_artifacts,
        "artifact_state_path": ARTIFACT_STATE_JSON,
        "summary": {
            "artifact_count": len(artifacts),
            "current_count": _count_status(artifacts, "current"),
            "missing_count": _count_status(artifacts, "missing"),
            "stale_count": len(stale_artifacts),
            "blocked_count": len(blocked_artifacts),
            "accepted_count": _count_status(artifacts, "accepted"),
            "rejected_count": _count_status(artifacts, "rejected"),
            "requires_human_review_count": len(review_artifacts),
            "missing_required_count": len(missing_required),
            "stale_segment_count": int(segment_summary.get("stale_segment_count", 0)),
            "segments_requiring_regeneration_count": int(segment_summary.get("needs_regeneration_count", 0)),
            "segments_requiring_review_count": int(segment_summary.get("needs_re_review_count", 0)),
            "reusable_segment_count": int(segment_summary.get("reusable_count", 0)),
            "segment_repair_pending_count": int(repair_summary.get("pending_repair_count", 0)),
            "segments_targeted_repair_count": int(repair_summary.get("targeted_repair_count", 0)),
            "segments_human_confirm_count": int(repair_summary.get("human_confirm_count", 0)),
            "segments_repair_blocked_count": int(repair_summary.get("blocked_count", 0)),
            "segment_repair_applied_count": int(repair_summary.get("applied_count", 0)),
            "segment_repair_pending_provider_count": int(repair_summary.get("pending_provider_count", 0)),
            "segment_repair_pending_human_count": int(repair_summary.get("pending_human_count", 0)),
            "segment_repair_failed_qa_count": int(repair_summary.get("failed_qa_count", 0)),
            "segment_repair_skipped_not_deterministic_count": int(repair_summary.get("skipped_not_deterministic_count", 0)),
            "segment_repair_not_applicable_count": int(repair_summary.get("not_applicable_count", 0)),
        },
        "decisions": {
            "full_quality_generation_handoff_allowed": handoff_policy == "allowed",
            "delivery_apply_allowed": delivery_policy != "blocked",
            "delivery_policy": delivery_policy,
            "apply_policy": delivery_policy,
        },
        "artifacts": artifacts,
        "segment_staleness": segment_state,
        "segment_repair": repair_state,
        "stale_artifacts": [_compact_artifact(item) for item in stale_artifacts],
        "blocked_artifacts": [_compact_artifact(item) for item in blocked_artifacts],
        "missing_required_artifacts": [_compact_artifact(item) for item in missing_required],
        "next_actions": _next_actions(stale_artifacts, blocked_artifacts, missing_required)
        + list(segment_state.get("next_actions", []))
        + list(repair_state.get("next_actions", [])),
    }
    if write:
        state_dir.mkdir(parents=True, exist_ok=True)
        write_json(state_dir / ARTIFACT_STATE_JSON, state)
    return state


def read_artifact_state(state_dir: Path) -> dict[str, Any]:
    path = state_dir / ARTIFACT_STATE_JSON
    if not path.is_file():
        raise ValueError(f"Missing artifact state: {path}")
    return read_json(path)


def artifact_state_summary(state_dir: Path) -> dict[str, Any]:
    path = state_dir / ARTIFACT_STATE_JSON
    if not path.is_file():
        return {
            "status": "not_run",
            "safe_to_continue": True,
            "artifact": None,
            "summary": {},
            "stale_artifacts": [],
            "blocked_artifacts": [],
            "decisions": {},
        }
    state = read_json(path)
    return {
        "status": state.get("status", "not_checked"),
        "safe_to_continue": bool(state.get("safe_to_continue", False)),
        "artifact": ARTIFACT_STATE_JSON,
        "summary": state.get("summary", {}),
        "stale_artifacts": state.get("stale_artifacts", []),
        "blocked_artifacts": state.get("blocked_artifacts", []),
        "segment_staleness": state.get("segment_staleness", {}),
        "segment_repair": state.get("segment_repair", {}),
        "decisions": state.get("decisions", {}),
        "next_actions": state.get("next_actions", []),
    }


def artifact_state_asset_paths(state_dir: Path) -> dict[str, str]:
    return {"artifact_state": ARTIFACT_STATE_JSON} if (state_dir / ARTIFACT_STATE_JSON).is_file() else {}


def artifact_state_from_delivery(delivery_dir: Path) -> dict[str, Any] | None:
    path = delivery_dir / ARTIFACT_STATE_JSON
    return read_json(path) if path.is_file() else None


def artifact_state_summary_from_document(state: dict[str, Any] | None) -> dict[str, Any]:
    if not state:
        return {
            "status": "not_available",
            "safe_to_continue": True,
            "summary": {},
        "stale_artifacts": [],
        "blocked_artifacts": [],
        "segment_staleness": {},
        "segment_repair": {},
        "decisions": {},
    }
    return {
        "status": state.get("status", "not_checked"),
        "safe_to_continue": bool(state.get("safe_to_continue", False)),
        "summary": state.get("summary", {}),
        "stale_artifacts": state.get("stale_artifacts", []),
        "blocked_artifacts": state.get("blocked_artifacts", []),
        "segment_staleness": state.get("segment_staleness", {}),
        "segment_repair": state.get("segment_repair", {}),
        "decisions": state.get("decisions", {}),
        "next_actions": state.get("next_actions", []),
    }


def _previous_artifacts(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    try:
        value = read_json(path)
    except (OSError, ValueError):
        return {}
    return {
        str(item.get("artifact_id")): item
        for item in value.get("artifacts", [])
        if isinstance(item, dict) and item.get("artifact_id")
    }


def _artifact_path(spec: ArtifactSpec, state_dir: Path, run_dir: Path | None, delivery_dir: Path | None) -> Path:
    if spec.location == "run":
        return (run_dir / spec.path) if run_dir else state_dir / spec.path
    if spec.location == "delivery":
        return (delivery_dir / spec.path) if delivery_dir else state_dir / spec.path
    return state_dir / spec.path


def _base_entry(
    spec: ArtifactSpec,
    path: Path,
    state_dir: Path,
    run_dir: Path | None,
    delivery_dir: Path | None,
) -> dict[str, Any]:
    exists = path.is_file()
    return {
        "artifact_id": spec.artifact_id,
        "artifact_type": spec.artifact_type,
        "path": _display_path(path, state_dir, run_dir, delivery_dir),
        "status": "current" if exists else "missing",
        "content_hash": sha256_file(path) if exists else None,
        "source_dependency_hashes": {},
        "produced_by": spec.produced_by,
        "produced_at": _file_timestamp(path) if exists else None,
        "supersedes": [],
        "superseded_by": [],
        "blocking_reason": None,
        "downstream_affected": [],
        "required_for_handoff": spec.required_for_handoff,
        "required_for_delivery": spec.required_for_delivery,
        "affects_generation_handoff": spec.required_for_handoff,
        "affects_delivery_or_apply": spec.required_for_delivery,
        "_absolute_path": path.as_posix(),
        "_mtime_ns": path.stat().st_mtime_ns if exists else None,
    }


def _display_path(path: Path, state_dir: Path, run_dir: Path | None, delivery_dir: Path | None) -> str:
    for root in (state_dir, run_dir, delivery_dir):
        if root and path == root / path.name:
            return path.name
        if root and _is_relative_to(path, root):
            return path.relative_to(root).as_posix()
    return path.as_posix()


def _dependency_hashes(spec: ArtifactSpec, entries: dict[str, dict[str, Any]]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for dependency_id in spec.dependencies:
        dependency = entries.get(dependency_id)
        if dependency and dependency.get("content_hash"):
            hashes[dependency_id] = str(dependency["content_hash"])
    return hashes


def _apply_content_status(entry: dict[str, Any]) -> None:
    if entry["status"] == "missing":
        return
    path = Path(str(entry["path"]))
    name = path.name
    if name.endswith(".json") and name != "artifact-state.json":
        try:
            content = read_json(_absolute_existing_path(entry))
        except (OSError, ValueError):
            return
        status = str(content.get("status") or content.get("delivery_status") or "")
        readiness = str(content.get("generation_readiness") or "")
        if status in STATUS_VALUES and status not in {"current", ""}:
            entry["status"] = "requires_human_review" if status in {"review_required", "owner_review_required"} else status
        if status == "draft_package":
            entry["status"] = "draft"
        if status == "review_ready":
            entry["status"] = "accepted"
        if status == "blocked" or readiness == "blocked":
            entry["status"] = "blocked"
            entry["blocking_reason"] = "artifact_declares_blocked"
        elif status in {"review_required", "owner_review_required"} or readiness == "review_required":
            entry["status"] = "requires_human_review"


def _absolute_existing_path(entry: dict[str, Any]) -> Path:
    return Path(str(entry.get("_absolute_path") or entry["path"]))


def _apply_previous_state_status(
    entry: dict[str, Any],
    previous: dict[str, Any],
    entries: dict[str, dict[str, Any]],
) -> None:
    if entry["status"] == "missing" or not previous:
        return
    if previous.get("status") == "stale" and previous.get("content_hash") == entry.get("content_hash"):
        entry["status"] = "stale"
        entry["blocking_reason"] = previous.get("blocking_reason") or "upstream_dependency_changed"
        if previous.get("stale_dependency_ids"):
            entry["stale_dependency_ids"] = previous.get("stale_dependency_ids")
        return
    current_dependencies = entry.get("source_dependency_hashes", {})
    previous_dependencies = previous.get("source_dependency_hashes", {})
    if current_dependencies == previous_dependencies:
        return
    changed_dependencies = sorted(
        dependency_id
        for dependency_id, dependency_hash in current_dependencies.items()
        if previous_dependencies.get(dependency_id) != dependency_hash
    )
    if not changed_dependencies:
        return
    if previous.get("content_hash") != entry.get("content_hash"):
        dependency_newer = any(
            (entries.get(dependency_id, {}).get("_mtime_ns") or 0) > (entry.get("_mtime_ns") or 0)
            for dependency_id in changed_dependencies
        )
        if not dependency_newer:
            return
    entry["status"] = "stale"
    entry["blocking_reason"] = "upstream_dependency_changed"
    entry["stale_dependency_ids"] = changed_dependencies


def _downstream_map(specs: list[ArtifactSpec]) -> dict[str, list[str]]:
    downstream: dict[str, set[str]] = {spec.artifact_id: set() for spec in specs}
    for spec in specs:
        for dependency in spec.dependencies:
            downstream.setdefault(dependency, set()).add(spec.artifact_id)
    return {key: sorted(value) for key, value in downstream.items()}


def _overall_status(
    stale_artifacts: list[dict[str, Any]],
    blocked_artifacts: list[dict[str, Any]],
    review_artifacts: list[dict[str, Any]],
    missing_required: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> str:
    if blocked_artifacts:
        return "blocked"
    if stale_artifacts:
        return "stale"
    if review_artifacts:
        return "requires_human_review"
    if missing_required and not any(item["status"] == "current" for item in artifacts):
        return "missing"
    return "current"


def _status_with_segment_state(status: str, segment_state: dict[str, Any]) -> str:
    segment_status = str(segment_state.get("status") or "not_run")
    if segment_status == "blocked":
        return "blocked"
    if segment_status == "requires_regeneration" and status == "current":
        return "stale"
    if segment_status == "requires_review" and status == "current":
        return "requires_human_review"
    return status


def _status_with_repair_state(status: str, repair_state: dict[str, Any]) -> str:
    repair_status = str(repair_state.get("status") or "not_run")
    if repair_status == "blocked":
        return "blocked"
    if repair_status in {"requires_regeneration", "requires_repair"} and status == "current":
        return "stale"
    if repair_status in {"requires_review", "requires_human_confirmation"} and status == "current":
        return "requires_human_review"
    return status


def _merge_policy(*policies: str) -> str:
    if "blocked" in policies:
        return "blocked"
    if "warn" in policies:
        return "warn"
    return "allowed"


def _compact_artifact(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": item.get("artifact_id"),
        "artifact_type": item.get("artifact_type"),
        "path": item.get("path"),
        "status": item.get("status"),
        "blocking_reason": item.get("blocking_reason"),
        "stale_dependency_ids": item.get("stale_dependency_ids", []),
        "downstream_affected": item.get("downstream_affected", []),
    }


def _public_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if not key.startswith("_")}


def _next_actions(
    stale_artifacts: list[dict[str, Any]],
    blocked_artifacts: list[dict[str, Any]],
    missing_required: list[dict[str, Any]],
) -> list[str]:
    actions: list[str] = []
    if stale_artifacts:
        actions.append("Regenerate or review stale artifacts before claiming full-quality generation, delivery, or apply readiness.")
    if blocked_artifacts:
        actions.append("Resolve blocked artifacts before continuing downstream execution.")
    if missing_required:
        actions.append("Create missing required artifacts before using them as generation, delivery, or apply evidence.")
    return actions


def _count_status(artifacts: list[dict[str, Any]], status: str) -> int:
    return sum(item["status"] == status for item in artifacts)


def _file_timestamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat().replace("+00:00", "Z")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
