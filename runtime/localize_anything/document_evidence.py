from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_json, write_jsonl


DOCUMENT_INTAKE_REPORT_JSON = "document-intake-report.json"
SEMANTIC_ALIGNMENT_JSONL = "semantic-alignment.jsonl"
CLAIM_METRIC_REPORT_JSON = "claim-metric-report.json"
PUBLICITY_RISK_REPORT_JSON = "publicity-risk-report.json"
LEADERSHIP_REVIEW_BRIEF_MD = "leadership-review-brief.md"
OPEN_DECISIONS_MD = "open-decisions.md"
DOCUMENT_EVIDENCE_MANIFEST_JSON = "document-evidence-manifest.json"

DOCUMENT_EVIDENCE_ASSETS = {
    "document_intake_report": DOCUMENT_INTAKE_REPORT_JSON,
    "semantic_alignment": SEMANTIC_ALIGNMENT_JSONL,
    "claim_metric_report": CLAIM_METRIC_REPORT_JSON,
    "publicity_risk_report": PUBLICITY_RISK_REPORT_JSON,
    "leadership_review_brief": LEADERSHIP_REVIEW_BRIEF_MD,
    "open_decisions": OPEN_DECISIONS_MD,
    "document_evidence_manifest": DOCUMENT_EVIDENCE_MANIFEST_JSON,
}

SUPPORTED_SCENARIO = "institutional_publicity_case"

ALIGNMENT_MODES = {
    "direct_rendering",
    "split",
    "merged",
    "localized_rewrite",
    "explanatory_expansion",
    "structural_relocation",
    "english_only_bridge",
    "source_only_omitted",
    "unknown",
}

METRIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("person_times", re.compile(r"\bperson[- ]?times?\b|人次", re.IGNORECASE)),
    ("person_days", re.compile(r"\bperson[- ]?days?\b|人天", re.IGNORECASE)),
    ("course_count", re.compile(r"\bcourses?\b|课程", re.IGNORECASE)),
    ("school_count", re.compile(r"\bschools?\b|学院|学校", re.IGNORECASE)),
    ("student_count", re.compile(r"\bstudents?\b|learners?\b|学员|学生", re.IGNORECASE)),
    ("participant_count", re.compile(r"\bparticipants?\b|参与者|参训", re.IGNORECASE)),
    ("award", re.compile(r"\bawards?\b|奖项|获奖|荣誉", re.IGNORECASE)),
    ("official_recognition", re.compile(r"\bofficial(?:ly)? recognized\b|\brecognitions?\b|官方认定|正式认定", re.IGNORECASE)),
    ("employment_intention", re.compile(r"\bemployment intention\b|就业意向", re.IGNORECASE)),
    ("employment_outcome", re.compile(r"\bemployment outcome\b|\bemployed\b|就业结果|就业人数", re.IGNORECASE)),
    ("trial_use", re.compile(r"\btrial use\b|\bpilot\b|试用|试点", re.IGNORECASE)),
    ("official_adoption", re.compile(r"\bofficial adoption\b|\badopted\b|正式采用|正式推广", re.IGNORECASE)),
    ("partnership_claim", re.compile(r"\bpartners?\b|\bpartnership\b|合作伙伴|合作单位", re.IGNORECASE)),
    ("project_status", re.compile(r"\bcompleted\b|\blaunched\b|\bin progress\b|已完成|上线|建设中", re.IGNORECASE)),
)

NUMBER_RE = re.compile(r"(?<![\w.])\d{1,4}(?:,\d{3})*(?:\.\d+)?(?![\w.])")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
DATE_RE = re.compile(r"\b(?:19|20)\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?\b")

OFFICIAL_OVERSTATEMENT_RE = re.compile(
    r"\bofficial(?:ly)? recognized\b|\bofficial recognition\b|\brecognized by\b|官方认定|正式认定",
    re.IGNORECASE,
)
ACHIEVEMENT_INFLATION_RE = re.compile(
    r"\bleading\b|\bworld[- ]class\b|\bbest\b|\bfirst[- ]class\b|\bpioneering\b|领先|世界一流|最佳|显著成果",
    re.IGNORECASE,
)
TONE_TOO_PROMOTIONAL_RE = re.compile(r"\bunparalleled\b|\bgroundbreaking\b|\boutstanding\b|卓越|辉煌|重大突破", re.IGNORECASE)
SENSITIVE_WORDING_RE = re.compile(r"\bdiplomatic\b|\bpolitically sensitive\b|外交|政治敏感", re.IGNORECASE)


def build_document_evidence_pack(
    state_dir: Path,
    *,
    run_dir: Path | None = None,
    scenario: str | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    run_dir = run_dir.resolve() if run_dir else None
    artifacts = _load_artifacts(state_dir, run_dir)
    source_segments = _source_segments(artifacts)
    target_segments = _target_segments(artifacts)
    intake = build_document_intake_report(state_dir, artifacts=artifacts, scenario=scenario, run_id=run_id, write=False)
    alignment = build_semantic_alignment(source_segments, target_segments)
    claim_report = build_claim_metric_report(source_segments, target_segments)
    publicity_report = build_publicity_risk_report(source_segments, target_segments, claim_report)
    open_decisions = _open_decision_items(artifacts, intake, alignment, claim_report, publicity_report)
    leadership_brief = render_leadership_review_brief(artifacts, intake, claim_report, publicity_report, open_decisions)
    open_decisions_md = render_open_decisions(open_decisions)
    manifest = build_document_evidence_manifest(
        state_dir,
        intake,
        alignment,
        claim_report,
        publicity_report,
        open_decisions,
        artifacts,
        run_id=run_id,
    )
    if write:
        state_dir.mkdir(parents=True, exist_ok=True)
        write_json(state_dir / DOCUMENT_INTAKE_REPORT_JSON, intake)
        write_jsonl(state_dir / SEMANTIC_ALIGNMENT_JSONL, alignment)
        write_json(state_dir / CLAIM_METRIC_REPORT_JSON, claim_report)
        write_json(state_dir / PUBLICITY_RISK_REPORT_JSON, publicity_report)
        (state_dir / LEADERSHIP_REVIEW_BRIEF_MD).write_text(leadership_brief, encoding="utf-8", newline="\n")
        (state_dir / OPEN_DECISIONS_MD).write_text(open_decisions_md, encoding="utf-8", newline="\n")
        write_json(state_dir / DOCUMENT_EVIDENCE_MANIFEST_JSON, manifest)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-document-evidence-pack-result-v1",
        "state_dir": state_dir.as_posix(),
        "document_intake_report": intake,
        "semantic_alignment": alignment,
        "claim_metric_report": claim_report,
        "publicity_risk_report": publicity_report,
        "leadership_review_brief": leadership_brief,
        "open_decisions": open_decisions_md,
        "document_evidence_manifest": manifest,
    }


def build_document_intake_report(
    state_dir: Path,
    *,
    artifacts: dict[str, Any] | None = None,
    scenario: str | None = None,
    run_id: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    artifacts = artifacts or _load_artifacts(state_dir, None)
    brief = artifacts.get("localization_brief", {})
    detected_scenario = scenario or _detect_document_scenario(brief)
    supported = detected_scenario == SUPPORTED_SCENARIO
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-document-intake-report-v1",
        "artifact": DOCUMENT_INTAKE_REPORT_JSON,
        "run_id": run_id,
        "status": "ready" if supported else "unsupported",
        "document_type": _brief_value(brief, "document_type", "unknown_document"),
        "source_genre": _brief_value(brief, "source_genre", "unknown_source_genre"),
        "target_delivery_mode": _brief_value(brief, "target_mode", "reviewable_delivery_bundle"),
        "target_audience": _list_value(brief.get("target_audience") if isinstance(brief, dict) else None),
        "detected_scenario_adapter": detected_scenario,
        "source_locale": _task_intent_value(brief, "source_locale", "unknown"),
        "target_locale": _first_target_locale(brief),
        "risk_profile": {
            "risk_level": "high" if supported else "unknown",
            "scenario": detected_scenario,
            "requires_claim_metric_review": supported,
            "requires_publicity_review": supported,
            "requires_leadership_review": supported,
        },
        "required_human_confirmations": _list_value(brief.get("required_human_confirmations") if isinstance(brief, dict) else None),
        "known_limitations": _known_limitations(supported),
        "source_artifacts": _source_artifacts(artifacts),
        "evidence_dependencies": _evidence_dependencies(),
    }
    if write:
        write_json(state_dir / DOCUMENT_INTAKE_REPORT_JSON, report)
    return report


def build_semantic_alignment(source_segments: list[dict[str, Any]], target_segments: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, segment in enumerate(source_segments, 1):
        segment_id = str(segment.get("segment_id") or f"segment-{index:04d}")
        source = str(segment.get("source") or "")
        target = target_segments.get(segment_id, {})
        target_text = str(target.get("target") or "") if target else ""
        explicit_mode = str(target.get("alignment_mode") or target.get("document_alignment_mode") or segment.get("alignment_mode") or "")
        mode = _alignment_mode(source, target_text, explicit_mode, target)
        risk_flags = _alignment_risk_flags(mode, source, target_text)
        records.append(
            {
                "protocol_version": PROTOCOL_VERSION,
                "schema": "localize-anything-semantic-alignment-record-v1",
                "alignment_id": f"align-{_stable_id(segment_id, source)[:16]}",
                "segment_id": segment_id,
                "source_text": source,
                "source_hash": str(segment.get("source_hash") or _hash_text(source)),
                "target_text_hash": _hash_text(target_text) if target_text else None,
                "alignment_mode": mode,
                "information_function": _information_function(source),
                "risk_flags": risk_flags,
                "source_artifact_references": ["segments.jsonl"],
                "target_artifact_references": ["generated-segments.jsonl"] if target else [],
                "review_status": "pending" if mode in {"unknown", "english_only_bridge", "source_only_omitted", "explanatory_expansion"} else "not_reviewed",
                "human_confirmation_required": mode in {"english_only_bridge", "source_only_omitted", "explanatory_expansion"},
                "limitations": _alignment_limitations(mode),
            }
        )
    return records


def build_claim_metric_report(source_segments: list[dict[str, Any]], target_segments: dict[str, dict[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for index, segment in enumerate(source_segments, 1):
        segment_id = str(segment.get("segment_id") or f"segment-{index:04d}")
        source = str(segment.get("source") or "")
        target = target_segments.get(segment_id, {})
        target_text = str(target.get("target") or "") if target else ""
        claim_types = _claim_types(source, target_text)
        if not claim_types and not _numbers(source) and not _numbers(target_text):
            continue
        for claim_type in claim_types or ["number"]:
            checks.append(_claim_check(segment_id, claim_type, source, target_text, bool(target)))
    report = {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-claim-metric-report-v1",
        "artifact": CLAIM_METRIC_REPORT_JSON,
        "status": _report_status(checks),
        "summary": _check_summary(checks),
        "checks": checks,
        "limitations": [
            "claim metric checks compare source and target boundaries; they do not verify real-world truth",
            "missing target text is marked pending/not_evaluable instead of inferred",
        ],
    }
    return report


def build_publicity_risk_report(
    source_segments: list[dict[str, Any]],
    target_segments: dict[str, dict[str, Any]],
    claim_report: dict[str, Any],
) -> dict[str, Any]:
    risks: list[dict[str, Any]] = []
    for index, segment in enumerate(source_segments, 1):
        segment_id = str(segment.get("segment_id") or f"segment-{index:04d}")
        source = str(segment.get("source") or "")
        target = target_segments.get(segment_id, {})
        target_text = str(target.get("target") or "") if target else ""
        risks.extend(_publicity_risks_for_segment(segment_id, source, target_text, bool(target)))
    for check in claim_report.get("checks", []):
        if check.get("risk_class") == "metric_boundary_change" and check.get("status") in {"warning", "blocked"}:
            risks.append(
                _risk(
                    str(check.get("segment_id") or "unknown"),
                    "metric_boundary_change",
                    "blocking" if check.get("status") == "blocked" else "warning",
                    str(check.get("reason") or "claim metric boundary changed"),
                    affected_claim=check.get("claim_type"),
                )
            )
    risks = _dedupe_risks(risks)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-publicity-risk-report-v1",
        "artifact": PUBLICITY_RISK_REPORT_JSON,
        "status": "blocked" if any(item["severity"] == "blocking" for item in risks) else "requires_review" if risks else "ready",
        "summary": {
            "risk_count": len(risks),
            "blocking_count": sum(item["severity"] == "blocking" for item in risks),
            "human_confirmation_required_count": sum(bool(item.get("human_confirmation_required")) for item in risks),
        },
        "risks": risks,
    }


def render_leadership_review_brief(
    artifacts: dict[str, Any],
    intake: dict[str, Any],
    claim_report: dict[str, Any],
    publicity_report: dict[str, Any],
    open_decisions: list[dict[str, Any]],
) -> str:
    scorecard = artifacts.get("evaluation_scorecard", {})
    signoff = artifacts.get("signoff_record", {})
    terms = _highest_risk_terms(artifacts)
    lines = [
        "# Leadership Review Brief",
        "",
        f"- Document purpose: `{intake.get('source_genre')}` to `{intake.get('target_delivery_mode')}`",
        f"- Target audience: {', '.join(intake.get('target_audience') or ['unknown'])}",
        f"- Scenario adapter: `{intake.get('detected_scenario_adapter')}`",
        f"- Evidence scorecard: `{scorecard.get('overall_claim', 'not_provided')}`",
        f"- Signoff status: `{signoff.get('status', 'not_provided')}`",
        "",
        "## Highest-Risk Terms",
        "",
    ]
    lines.extend([f"- `{term}`" for term in terms] or ["- No high-risk terms were found in current artifacts."])
    lines.extend(["", "## Claim And Metric Risks", ""])
    claim_risks = [item for item in claim_report.get("checks", []) if item.get("status") in {"warning", "blocked", "pending"}]
    lines.extend([f"- `{item.get('segment_id')}` / `{item.get('claim_type')}`: {item.get('reason')}" for item in claim_risks[:10]] or ["- No claim/metric risk was detected."])
    lines.extend(["", "## Publicity Risks", ""])
    lines.extend([f"- `{item.get('risk_class')}` / `{item.get('segment_id')}`: {item.get('reason')}" for item in publicity_report.get("risks", [])[:10]] or ["- No publicity risk was detected."])
    lines.extend(["", "## Open Decisions", ""])
    lines.extend([f"- `{item.get('decision_id')}`: {item.get('required_decision')}" for item in open_decisions[:12]] or ["- No open decision was found."])
    lines.extend(["", "## Forbidden Claims", ""])
    lines.extend([f"- `{claim}`" for claim in scorecard.get("forbidden_claims", [])] or ["- None recorded."])
    lines.extend(["", "## Recommended Review Actions", ""])
    lines.extend(_recommended_review_actions(claim_report, publicity_report, open_decisions))
    return "\n".join(lines) + "\n"


def render_open_decisions(open_decisions: list[dict[str, Any]]) -> str:
    lines = ["# Open Decisions", ""]
    if not open_decisions:
        lines.append("No unresolved document evidence decisions were found.")
        return "\n".join(lines) + "\n"
    for item in open_decisions:
        lines.extend(
            [
                f"## {item['decision_id']}",
                "",
                f"- Owner role: `{item['owner_role']}`",
                f"- Severity: `{item['severity']}`",
                f"- Required decision: {item['required_decision']}",
                f"- Source artifacts: `{', '.join(item['source_artifact_references'])}`",
                f"- Recommended default: {item['recommended_default']}",
                "",
            ]
        )
    return "\n".join(lines)


def build_document_evidence_manifest(
    state_dir: Path,
    intake: dict[str, Any],
    alignment: list[dict[str, Any]],
    claim_report: dict[str, Any],
    publicity_report: dict[str, Any],
    open_decisions: list[dict[str, Any]],
    artifacts: dict[str, Any],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    blocking_count = (
        int(claim_report.get("summary", {}).get("blocking_count", 0) or 0)
        + int(publicity_report.get("summary", {}).get("blocking_count", 0) or 0)
        + sum(item.get("severity") == "blocking" for item in open_decisions)
    )
    if intake.get("status") == "unsupported":
        status = "unsupported"
    elif blocking_count:
        status = "blocked"
    elif open_decisions:
        status = "requires_review"
    else:
        status = "ready"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-document-evidence-manifest-v1",
        "artifact": DOCUMENT_EVIDENCE_MANIFEST_JSON,
        "run_id": run_id,
        "status": status,
        "document_scenario": intake.get("detected_scenario_adapter"),
        "summary": {
            "alignment_record_count": len(alignment),
            "pending_alignment_count": sum(item.get("review_status") == "pending" for item in alignment),
            "claim_metric_check_count": len(claim_report.get("checks", [])),
            "claim_metric_blocking_count": claim_report.get("summary", {}).get("blocking_count", 0),
            "publicity_risk_count": publicity_report.get("summary", {}).get("risk_count", 0),
            "open_decision_count": len(open_decisions),
            "blocking_decision_count": sum(item.get("severity") == "blocking" for item in open_decisions),
        },
        "artifacts": {
            key: {
                "path": value,
                "status": "present"
                if (state_dir / value).exists()
                or key
                in {
                    "document_intake_report",
                    "semantic_alignment",
                    "claim_metric_report",
                    "publicity_risk_report",
                    "leadership_review_brief",
                    "open_decisions",
                    "document_evidence_manifest",
                }
                else "planned",
            }
            for key, value in DOCUMENT_EVIDENCE_ASSETS.items()
        },
        "referenced_evidence": _manifest_evidence_refs(artifacts),
        "delivery_readiness_note": "Document Evidence Pack is evidence only; delivery/apply readiness remains controlled by scorecard, signoff, artifact-state, repair, QA, and handoff gates.",
        "limitations": [
            "does not render DOCX or prove real-world factual truth",
            "does not make spreadsheet exports a source of truth",
            "does not upgrade delivery/apply readiness merely by existing",
        ],
    }


def read_document_evidence_manifest(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / DOCUMENT_EVIDENCE_MANIFEST_JSON)


def read_document_intake_report(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / DOCUMENT_INTAKE_REPORT_JSON)


def read_semantic_alignment(state_dir: Path) -> list[dict[str, Any]]:
    return read_jsonl(state_dir / SEMANTIC_ALIGNMENT_JSONL)


def read_claim_metric_report(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / CLAIM_METRIC_REPORT_JSON)


def read_publicity_risk_report(state_dir: Path) -> dict[str, Any]:
    return read_json(state_dir / PUBLICITY_RISK_REPORT_JSON)


def read_leadership_review_brief(state_dir: Path) -> str:
    path = state_dir / LEADERSHIP_REVIEW_BRIEF_MD
    if not path.is_file():
        raise ValueError(f"Missing leadership review brief: {path}")
    return path.read_text(encoding="utf-8")


def read_open_decisions(state_dir: Path) -> str:
    path = state_dir / OPEN_DECISIONS_MD
    if not path.is_file():
        raise ValueError(f"Missing open decisions: {path}")
    return path.read_text(encoding="utf-8")


def document_evidence_asset_paths(state_dir: Path) -> dict[str, str]:
    return {key: value for key, value in DOCUMENT_EVIDENCE_ASSETS.items() if (state_dir / value).is_file()}


def _load_artifacts(state_dir: Path, run_dir: Path | None) -> dict[str, Any]:
    return {
        "localization_brief": _optional_json(state_dir / "localization-brief.json"),
        "termbase_preflight_report": _optional_json(state_dir / "termbase-preflight-report.json"),
        "term_review_queue": _optional_json(state_dir / "term-review-queue.json"),
        "blocking_questions": _optional_json(state_dir / "blocking-questions.json"),
        "evaluation_scorecard": _optional_json(state_dir / "evaluation-scorecard.json"),
        "human_review_evidence": _optional_jsonl(state_dir / "human-review-evidence.jsonl"),
        "claim_acceptance_decision": _optional_json(state_dir / "claim-acceptance-decision.json"),
        "signoff_record": _optional_json(state_dir / "signoff-record.json"),
        "artifact_state": _optional_json(state_dir / "artifact-state.json"),
        "repair_request": _optional_json(state_dir / "repair-request.json"),
        "repair_result": _optional_json(state_dir / "repair-result.json"),
        "delivery_decision": _optional_json(state_dir / "delivery-decision.json"),
        "source_segments": _first_jsonl(
            [
                state_dir / "segments.jsonl",
                (run_dir / "segments.jsonl") if run_dir else state_dir / "missing-run-segments.jsonl",
            ]
        ),
        "generated_segments": _first_jsonl(
            [
                state_dir / "generated-segments.jsonl",
                state_dir / "generated.jsonl",
                (run_dir / "generated.jsonl") if run_dir else state_dir / "missing-run-generated.jsonl",
            ]
        ),
    }


def _source_segments(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in artifacts.get("source_segments", []) if isinstance(item, dict)]


def _target_segments(artifacts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in artifacts.get("generated_segments", []):
        if isinstance(item, dict) and item.get("segment_id"):
            result[str(item["segment_id"])] = item
    return result


def _detect_document_scenario(brief: dict[str, Any]) -> str:
    values = [
        str(brief.get("document_type") or ""),
        str(brief.get("source_genre") or ""),
        str(brief.get("target_mode") or ""),
        str((brief.get("task_intent") or {}).get("scenario") if isinstance(brief.get("task_intent"), dict) else ""),
    ]
    haystack = " ".join(values).lower()
    if "institutional" in haystack and ("publicity" in haystack or "case" in haystack):
        return SUPPORTED_SCENARIO
    if "application_summary" in haystack or "external_publicity" in haystack:
        return SUPPORTED_SCENARIO
    return "unsupported_document_scenario"


def _brief_value(brief: dict[str, Any], key: str, default: str) -> str:
    return str(brief.get(key) or default) if isinstance(brief, dict) else default


def _task_intent_value(brief: dict[str, Any], key: str, default: str) -> str:
    task_intent = brief.get("task_intent") if isinstance(brief, dict) else None
    return str(task_intent.get(key) or default) if isinstance(task_intent, dict) else default


def _first_target_locale(brief: dict[str, Any]) -> str:
    task_intent = brief.get("task_intent") if isinstance(brief, dict) else None
    target_locales = task_intent.get("target_locales") if isinstance(task_intent, dict) else None
    if isinstance(target_locales, list) and target_locales:
        return str(target_locales[0])
    return "unknown"


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _known_limitations(supported: bool) -> list[str]:
    limitations = [
        "document evidence pack does not render DOCX or inspect layout fidelity in this seed",
        "claim and publicity checks are deterministic boundary checks, not real-world fact verification",
        "target text is never fabricated when generated segments are missing",
    ]
    if not supported:
        limitations.append("document scenario is unsupported in this seed")
    return limitations


def _evidence_dependencies() -> list[str]:
    return [
        "localization-brief.json",
        "segments.jsonl",
        "generated-segments.jsonl",
        "evaluation-scorecard.json",
        "artifact-state.json",
        "human-review-evidence.jsonl",
        "claim-acceptance-decision.json",
        "signoff-record.json",
    ]


def _alignment_mode(source: str, target: str, explicit_mode: str, target_segment: dict[str, Any]) -> str:
    if explicit_mode in ALIGNMENT_MODES:
        return explicit_mode
    status = str(target_segment.get("status") or "")
    if not target_segment:
        return "unknown"
    if not target.strip() or status in {"omitted", "source_only_omitted"}:
        return "source_only_omitted"
    if _looks_english_only_bridge(source, target):
        return "english_only_bridge"
    if len(target) > max(80, int(len(source) * 1.65)):
        return "explanatory_expansion"
    return "direct_rendering"


def _alignment_risk_flags(mode: str, source: str, target: str) -> list[str]:
    flags: list[str] = []
    if mode == "english_only_bridge":
        flags.append("english_only_bridge")
    if mode == "source_only_omitted":
        flags.append("source_only_omitted")
    if mode == "explanatory_expansion":
        flags.append("requires_traceable_source_intent_or_human_confirmation")
    if _numbers(target) - _numbers(source):
        flags.append("target_adds_metric_or_number")
    return sorted(flags)


def _alignment_limitations(mode: str) -> list[str]:
    if mode == "unknown":
        return ["target text is missing or alignment mode could not be determined"]
    if mode == "explanatory_expansion":
        return ["expansion requires traceable source intent or human confirmation"]
    if mode == "english_only_bridge":
        return ["English-only bridge text must be confirmed for final delivery"]
    if mode == "source_only_omitted":
        return ["source-only omission must be confirmed before delivery"]
    return []


def _looks_english_only_bridge(source: str, target: str) -> bool:
    return "english_only_bridge" in target.lower() or "english-only bridge" in target.lower()


def _information_function(text: str) -> str:
    claim_types = _claim_types(text, "")
    if "official_recognition" in claim_types or "award" in claim_types:
        return "recognition_or_award_claim"
    if "partnership_claim" in claim_types:
        return "partner_or_institution_claim"
    if claim_types or _numbers(text):
        return "claim_or_metric"
    if re.search(r"\b(university|college|institute|school)\b|大学|学院|学校", text, re.IGNORECASE):
        return "institution_name"
    return "general_publicity_copy"


def _claim_check(segment_id: str, claim_type: str, source: str, target: str, has_target: bool) -> dict[str, Any]:
    source_numbers = sorted(_numbers(source))
    target_numbers = sorted(_numbers(target))
    source_units = _number_units(source)
    target_units = _number_units(target)
    if not has_target:
        status = "pending"
        severity = "warning"
        reason = "target text is unavailable; claim/metric boundary is not evaluable"
        risk_class = "not_evaluable"
    else:
        extra_numbers = sorted(set(target_numbers) - set(source_numbers))
        missing_numbers = sorted(set(source_numbers) - set(target_numbers))
        changed_units = sorted(
            number
            for number in set(source_units) & set(target_units)
            if source_units[number] and target_units[number] and source_units[number] != target_units[number]
        )
        extra_claim = claim_type not in _claim_types(source, "") and claim_type in _claim_types("", target)
        if extra_numbers or changed_units or extra_claim:
            status = "blocked"
            severity = "blocking"
            risk_class = "metric_boundary_change" if extra_numbers or changed_units else "unsupported_external_facing_claim"
            reason = "target adds or changes a claim/metric boundary"
        elif missing_numbers:
            status = "warning"
            severity = "warning"
            risk_class = "metric_boundary_change"
            reason = "target omits a source claim/metric value"
        else:
            status = "pass"
            severity = "info"
            risk_class = "none"
            reason = "source and target claim/metric boundaries match deterministically"
    return {
        "check_id": f"claim-metric-{_stable_id(segment_id, claim_type)[:16]}",
        "segment_id": segment_id,
        "claim_type": claim_type,
        "status": status,
        "severity": severity,
        "risk_class": risk_class,
        "source_values": source_numbers,
        "target_values": target_numbers,
        "source_units": {key: sorted(value) for key, value in source_units.items()},
        "target_units": {key: sorted(value) for key, value in target_units.items()},
        "reason": reason,
        "source_artifact_references": ["segments.jsonl"],
        "target_artifact_references": ["generated-segments.jsonl"] if has_target else [],
        "human_confirmation_required": status in {"warning", "blocked", "pending"},
    }


def _claim_types(source: str, target: str) -> list[str]:
    text = f"{source}\n{target}"
    found = {name for name, pattern in METRIC_PATTERNS if pattern.search(text)}
    if YEAR_RE.search(text):
        found.add("year")
    if DATE_RE.search(text):
        found.add("date")
    if NUMBER_RE.search(text):
        found.add("number")
    return sorted(found)


def _numbers(text: str) -> set[str]:
    return {match.group(0).replace(",", "") for match in NUMBER_RE.finditer(text)}


def _number_units(text: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for match in NUMBER_RE.finditer(text):
        window = text[max(0, match.start() - 28) : min(len(text), match.end() + 32)]
        units = {name for name, pattern in METRIC_PATTERNS if pattern.search(window)}
        result.setdefault(match.group(0).replace(",", ""), set()).update(units)
    return result


def _publicity_risks_for_segment(segment_id: str, source: str, target: str, has_target: bool) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    if not has_target and _claim_types(source, ""):
        risks.append(_risk(segment_id, "unsupported_external_facing_claim", "warning", "target is missing for a source claim that needs review"))
        return risks
    if OFFICIAL_OVERSTATEMENT_RE.search(target) and not OFFICIAL_OVERSTATEMENT_RE.search(source):
        risks.append(_risk(segment_id, "official-recognition overstatement", "blocking", "target states or implies official recognition beyond the source"))
    if ACHIEVEMENT_INFLATION_RE.search(target) and not ACHIEVEMENT_INFLATION_RE.search(source):
        risks.append(_risk(segment_id, "achievement inflation", "blocking", "target uses stronger achievement language than the source"))
    if re.search(r"\b(university|college|institute|school)\b|大学|学院|学校", source, re.IGNORECASE):
        risks.append(_risk(segment_id, "institution name uncertainty", "warning", "institution name should be confirmed for external-facing use"))
    if re.search(r"\bpartner|partnership\b|合作伙伴|合作单位", source, re.IGNORECASE):
        risks.append(_risk(segment_id, "partner name uncertainty", "warning", "partner name should be confirmed"))
    if re.search(r"\baward\b|奖项|获奖", source, re.IGNORECASE):
        risks.append(_risk(segment_id, "award name uncertainty", "warning", "award name should be confirmed"))
    if re.search(r"\bslogan\b|口号", source, re.IGNORECASE):
        risks.append(_risk(segment_id, "policy slogan literalism", "warning", "policy slogan wording should be reviewed"))
    if re.search(r"\btrial\b|\bpilot\b|试点|试用", source, re.IGNORECASE) and re.search(r"\badopted\b|\blaunched\b|正式采用|正式推广", target, re.IGNORECASE):
        risks.append(_risk(segment_id, "unconfirmed project status", "blocking", "target may turn trial/pilot status into official adoption"))
    if SENSITIVE_WORDING_RE.search(source) or SENSITIVE_WORDING_RE.search(target):
        risks.append(_risk(segment_id, "politically or diplomatically sensitive wording", "warning", "sensitive wording requires human confirmation"))
    if TONE_TOO_PROMOTIONAL_RE.search(target) and not TONE_TOO_PROMOTIONAL_RE.search(source):
        risks.append(_risk(segment_id, "tone too promotional", "warning", "target tone is more promotional than source"))
    if target and _looks_english_only_bridge(source, target):
        risks.append(_risk(segment_id, "audience mismatch", "warning", "English-only bridge text may not match final target audience"))
    return risks


def _risk(segment_id: str, risk_class: str, severity: str, reason: str, *, affected_claim: Any = None) -> dict[str, Any]:
    return {
        "risk_id": f"doc-risk-{_stable_id(segment_id, risk_class, reason)[:16]}",
        "segment_id": segment_id,
        "scope": {"scope_type": "segment", "segment_ids": [segment_id]},
        "risk_class": risk_class,
        "severity": severity,
        "reason": reason,
        "supporting_source_artifact": "segments.jsonl",
        "affected_claim": affected_claim,
        "recommended_action": "Confirm wording and claim boundary with the document owner before delivery.",
        "human_confirmation_required": True,
    }


def _dedupe_risks(risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for risk in risks:
        key = str(risk.get("risk_id"))
        if key in seen:
            continue
        seen.add(key)
        result.append(risk)
    return result


def _open_decision_items(
    artifacts: dict[str, Any],
    intake: dict[str, Any],
    alignment: list[dict[str, Any]],
    claim_report: dict[str, Any],
    publicity_report: dict[str, Any],
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    if intake.get("status") == "unsupported":
        decisions.append(_decision("unsupported-scenario", "project_owner", "blocking", "Confirm a supported document evidence scenario or defer this pack.", [DOCUMENT_INTAKE_REPORT_JSON], "defer_until_supported"))
    for question in _items(artifacts.get("blocking_questions"), "questions"):
        if str(question.get("status") or "unresolved") not in {"resolved", "accepted"}:
            decisions.append(_decision(str(question.get("question_id") or "blocking-question"), "project_owner", "blocking", "Resolve blocking question before claiming document readiness.", ["blocking-questions.json"], "keep_blocked"))
    for item in _items(artifacts.get("term_review_queue"), "items") + _items(artifacts.get("term_review_queue"), "terms"):
        if str(item.get("status") or "needs_review") in {"candidate", "needs_review", "deferred"}:
            decisions.append(_decision(str(item.get("term_id") or item.get("candidate_id") or item.get("term") or "term-review"), "terminology_owner", "warning", "Review unresolved document terminology.", ["term-review-queue.json"], "needs_review"))
    scorecard = artifacts.get("evaluation_scorecard", {})
    if "review_complete" in set(scorecard.get("forbidden_claims", [])):
        decisions.append(_decision("human-review-evidence", "bilingual_reviewer", "warning", "Record explicit human review evidence before claiming review completion.", ["evaluation-scorecard.json", "human-review-evidence.jsonl"], "record_e2_or_keep_review_required"))
    claim_decision = artifacts.get("claim_acceptance_decision", {})
    if claim_decision and str(claim_decision.get("status")) not in {"accepted", "accepted_with_limitations"}:
        decisions.append(_decision("claim-acceptance", "project_owner", "warning", "Accept only scorecard-supported claims or leave forbidden claims visible.", ["claim-acceptance-decision.json"], "do_not_accept_forbidden_claims"))
    signoff = artifacts.get("signoff_record", {})
    if not signoff or str(signoff.get("status")) not in {"accepted", "final"}:
        decisions.append(_decision("signoff", "project_owner", "warning", "Create final signoff only after evidence and claim limits are accepted.", ["signoff-record.json"], "keep_delivery_review_required"))
    for record in alignment:
        if record.get("human_confirmation_required"):
            decisions.append(_decision(str(record.get("alignment_id")), "document_reviewer", "warning", f"Confirm `{record.get('alignment_mode')}` alignment for segment `{record.get('segment_id')}`.", [SEMANTIC_ALIGNMENT_JSONL], "human_confirm"))
    for check in claim_report.get("checks", []):
        if check.get("human_confirmation_required"):
            decisions.append(_decision(str(check.get("check_id")), "document_owner", "blocking" if check.get("severity") == "blocking" else "warning", str(check.get("reason")), [CLAIM_METRIC_REPORT_JSON], "confirm_or_repair_claim"))
    for risk in publicity_report.get("risks", []):
        decisions.append(_decision(str(risk.get("risk_id")), "leadership_reviewer", "blocking" if risk.get("severity") == "blocking" else "warning", str(risk.get("recommended_action")), [PUBLICITY_RISK_REPORT_JSON], "confirm_or_reword"))
    for artifact in _items(artifacts.get("artifact_state"), "artifacts"):
        if artifact.get("status") in {"stale", "superseded", "blocked", "requires_human_review"}:
            decisions.append(_decision(str(artifact.get("artifact_id") or "artifact-state"), "developer", "blocking", "Refresh stale or blocked artifact evidence before delivery/apply.", ["artifact-state.json"], "regenerate_or_review"))
    repair_request = artifacts.get("repair_request", {})
    repair_result = artifacts.get("repair_result", {})
    if _pending_repair_count(repair_request, repair_result):
        decisions.append(_decision("pending-repairs", "developer", "blocking", "Complete required repairs before delivery/apply readiness.", ["repair-request.json", "repair-result.json"], "complete_repairs"))
    return _dedupe_decisions(decisions)


def _decision(decision_id: str, owner_role: str, severity: str, required_decision: str, refs: list[str], recommended_default: str) -> dict[str, Any]:
    return {
        "decision_id": f"doc-decision-{_stable_id(decision_id)[:16]}",
        "owner_role": owner_role,
        "severity": severity,
        "required_decision": required_decision,
        "source_artifact_references": refs,
        "recommended_default": recommended_default,
    }


def _dedupe_decisions(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in decisions:
        key = str(item["decision_id"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _pending_repair_count(repair_request: dict[str, Any], repair_result: dict[str, Any]) -> int:
    request_count = len(repair_request.get("requests", [])) if isinstance(repair_request, dict) else 0
    summary = repair_result.get("summary", {}) if isinstance(repair_result, dict) else {}
    return request_count + int(summary.get("pending_required_repair_count", 0) or 0) + int(summary.get("pending_provider_or_model_repair_count", 0) or 0)


def _highest_risk_terms(artifacts: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    queue = artifacts.get("term_review_queue", {})
    for item in _items(queue, "items") + _items(queue, "terms"):
        if item.get("risk_level") in {"high", "critical"} or item.get("status") in {"needs_review", "candidate"}:
            value = item.get("term") or item.get("source_term") or item.get("candidate")
            if value:
                terms.append(str(value))
    return sorted(dict.fromkeys(terms))[:10]


def _recommended_review_actions(
    claim_report: dict[str, Any],
    publicity_report: dict[str, Any],
    open_decisions: list[dict[str, Any]],
) -> list[str]:
    actions: list[str] = []
    if claim_report.get("summary", {}).get("blocking_count"):
        actions.append("Resolve claim/metric boundary blockers before external delivery.")
    if publicity_report.get("summary", {}).get("blocking_count"):
        actions.append("Review and confirm high-risk publicity wording with leadership.")
    if open_decisions:
        actions.append("Close open decisions or keep delivery/apply downgraded.")
    if not actions:
        actions.append("Proceed to human review/signoff without upgrading claims beyond existing scorecard evidence.")
    return [f"- {action}" for action in actions]


def _report_status(checks: list[dict[str, Any]]) -> str:
    if any(item["status"] == "blocked" for item in checks):
        return "blocked"
    if any(item["status"] in {"warning", "pending"} for item in checks):
        return "requires_review"
    return "ready"


def _check_summary(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "check_count": len(checks),
        "passing_count": sum(item["status"] == "pass" for item in checks),
        "pending_count": sum(item["status"] == "pending" for item in checks),
        "warning_count": sum(item["status"] == "warning" for item in checks),
        "blocking_count": sum(item["status"] == "blocked" for item in checks),
        "human_confirmation_required_count": sum(bool(item.get("human_confirmation_required")) for item in checks),
    }


def _manifest_evidence_refs(artifacts: dict[str, Any]) -> dict[str, str]:
    names = {
        "evaluation_scorecard": "evaluation-scorecard.json",
        "evidence_level_report": "evidence-level-report.md",
        "human_review_evidence": "human-review-evidence.jsonl",
        "claim_acceptance_decision": "claim-acceptance-decision.json",
        "signoff_record": "signoff-record.json",
        "delivery_decision": "delivery-decision.json",
        "artifact_state": "artifact-state.json",
    }
    return {key: value for key, value in names.items() if artifacts.get(key)}


def _source_artifacts(artifacts: dict[str, Any]) -> dict[str, str]:
    names = {
        "localization_brief": "localization-brief.json",
        "termbase_preflight_report": "termbase-preflight-report.json",
        "term_review_queue": "term-review-queue.json",
        "blocking_questions": "blocking-questions.json",
        "evaluation_scorecard": "evaluation-scorecard.json",
        "artifact_state": "artifact-state.json",
        "repair_request": "repair-request.json",
        "repair_result": "repair-result.json",
    }
    return {key: value for key, value in names.items() if artifacts.get(key)}


def _items(value: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    items = value.get(key, [])
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.is_file() else {}


def _optional_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.is_file() else []


def _first_jsonl(paths: list[Path]) -> list[dict[str, Any]]:
    for path in paths:
        if path.is_file():
            return read_jsonl(path)
    return []


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_id(*parts: Any) -> str:
    return _hash_text("|".join(str(part) for part in parts))
