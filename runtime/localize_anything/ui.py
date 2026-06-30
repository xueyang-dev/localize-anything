from __future__ import annotations

import base64
import binascii
import json
import uuid
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path, PurePosixPath
from tempfile import gettempdir
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .agent import run_agent
from .artifact_state import read_artifact_state
from .document_evidence import (
    read_claim_metric_report,
    read_document_evidence_manifest,
    read_document_intake_report,
    read_leadership_review_brief,
    read_open_decisions,
    read_publicity_risk_report,
    read_semantic_alignment,
)
from .document_evidence_queue import read_workbench_document_evidence_queue
from .document_decision import (
    build_document_claim_resolution,
    build_document_signoff_summary,
    read_document_claim_resolution,
    read_document_decision_log,
    read_document_signoff_summary,
    read_leadership_review_evidence,
    record_document_decision,
    record_leadership_review_evidence,
)
from .evaluation import read_evaluation_scorecard
from .generation_handoff_policy import read_generation_handoff_decision
from .generation_strategy import read_generation_strategy
from .human_review import (
    build_claim_acceptance_decision,
    create_signoff_record,
    read_claim_acceptance_decision,
    read_human_review_evidence,
    read_signoff_record,
    record_human_review_evidence,
)
from .knowledge_pack import (
    export_knowledge_pack,
    init_knowledge_pack,
    read_knowledge_pack,
    read_knowledge_quality_report,
    read_knowledge_review_queue,
    record_knowledge_review_decision,
)
from .knowledge_consumption import (
    read_knowledge_eligibility_report,
    read_knowledge_pack_selection,
    read_working_context_packet,
    select_knowledge_packs,
)
from .knowledge_usage import (
    read_constraint_application_audit,
    read_knowledge_conflict_report,
    read_knowledge_usage_report,
)
from .knowledge_audit_enforcement import (
    read_knowledge_audit_enforcement_decision,
    read_workbench_knowledge_review_queue,
)
from .knowledge_review_confirmation import (
    build_knowledge_assurance_summary,
    build_knowledge_conflict_resolution,
    read_knowledge_audit_resolution_log,
    read_knowledge_constraint_review_evidence,
    record_knowledge_audit_resolution,
    record_knowledge_constraint_review_evidence,
)
from .knowledge_repair import (
    read_knowledge_repair_impact_report,
    read_knowledge_repair_plan,
    read_knowledge_repair_request,
)
from .project import inspect_project, load_session_index
from .resolution_gate import read_blocking_questions, read_resolution_options, record_user_resolution_decision
from .segment_repair import (
    apply_repair_plan,
    read_repair_history,
    read_repair_request,
    read_repair_result,
    read_segment_regeneration_plan,
)
from .segment_staleness import read_reuse_decision, read_stale_segments
from .termbase_preflight import read_term_review_queue, record_term_review_decision
from .workbench_action import perform_workbench_action, read_workbench_action_log, read_workbench_action_result
from .workbench_console import build_workbench_console_view, read_evidence_level_report, render_workbench_console_html
from .workbench_queue import read_workbench_claim_queue, read_workbench_review_queue, read_workbench_signoff_summary


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_ARTIFACT_BYTES = 1_000_000
MAX_IMPORT_FILE_BYTES = 25_000_000
MAX_IMPORT_TOTAL_BYTES = 100_000_000
MAX_IMPORT_FILES = 500


@dataclass
class WorkbenchState:
    allowed_roots: set[Path] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.add_allowed_root(Path.cwd())
        self.add_allowed_root(Path(gettempdir()))

    def add_allowed_root(self, path: Path | str | None) -> None:
        if not path:
            return
        root = Path(path).expanduser().resolve()
        if root.is_file():
            root = root.parent
        self.allowed_roots.add(root)

    def allow_agent_result(self, result: dict[str, Any]) -> None:
        for value in result.get("artifacts", {}).values():
            if isinstance(value, str):
                self.add_allowed_root(Path(value))
        for pointer in result.get("runs", {}).values():
            if isinstance(pointer, dict) and pointer.get("run_directory"):
                self.add_allowed_root(Path(str(pointer["run_directory"])))

    def is_allowed(self, path: Path) -> bool:
        resolved = path.expanduser().resolve()
        return any(resolved == root or resolved.is_relative_to(root) for root in self.allowed_roots)


def create_ui_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, state: WorkbenchState | None = None) -> ThreadingHTTPServer:
    state = state or WorkbenchState()
    handler = _handler_factory(state)
    errors: list[OSError] = []
    candidates = [port] if port == 0 else list(range(port, port + 20))
    for candidate in candidates:
        try:
            return ThreadingHTTPServer((host, candidate), handler)
        except OSError as exc:
            errors.append(exc)
            if port == 0:
                break
    raise errors[-1]


def serve_ui(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = False) -> None:
    server = create_ui_server(host, port)
    actual_host, actual_port = server.server_address[:2]
    url = f"http://{actual_host}:{actual_port}/"
    print(f"Localize Anything Workbench: {url}", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _handler_factory(state: WorkbenchState) -> type[BaseHTTPRequestHandler]:
    class LocalizeAnythingUIHandler(BaseHTTPRequestHandler):
        server_version = "LocalizeAnythingWorkbench/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    self._send_text(WORKBENCH_HTML, "text/html; charset=utf-8")
                    return
                if parsed.path == "/workbench-review-console":
                    self._handle_workbench_review_console(parsed.query)
                    return
                if parsed.path == "/api/health":
                    self._send_json({"status": "pass", "app": "localize-anything-workbench", "version": __version__})
                    return
                if parsed.path == "/api/blocking-questions":
                    self._handle_blocking_questions_query(parsed.query)
                    return
                if parsed.path == "/api/resolution-options":
                    self._handle_resolution_options_query(parsed.query)
                    return
                if parsed.path == "/api/generation-handoff-status":
                    self._handle_generation_handoff_status_query(parsed.query)
                    return
                if parsed.path == "/api/artifact-state":
                    self._handle_artifact_state_query(parsed.query)
                    return
                if parsed.path == "/api/stale-segments":
                    self._handle_stale_segments_query(parsed.query)
                    return
                if parsed.path == "/api/reuse-decision":
                    self._handle_reuse_decision_query(parsed.query)
                    return
                if parsed.path == "/api/segment-regeneration-plan":
                    self._handle_segment_regeneration_plan_query(parsed.query)
                    return
                if parsed.path == "/api/repair-request":
                    self._handle_repair_request_query(parsed.query)
                    return
                if parsed.path == "/api/repair-result":
                    self._handle_repair_result_query(parsed.query)
                    return
                if parsed.path == "/api/repair-history":
                    self._handle_repair_history_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-repair-plan":
                    self._handle_knowledge_repair_query(parsed.query, "plan")
                    return
                if parsed.path == "/api/knowledge-repair-request":
                    self._handle_knowledge_repair_query(parsed.query, "request")
                    return
                if parsed.path == "/api/knowledge-repair-impact-report":
                    self._handle_knowledge_repair_query(parsed.query, "impact")
                    return
                if parsed.path == "/api/evaluation-scorecard":
                    self._handle_evaluation_scorecard_query(parsed.query)
                    return
                if parsed.path == "/api/evidence-level-report":
                    self._handle_evidence_level_report_query(parsed.query)
                    return
                if parsed.path == "/api/human-review-evidence":
                    self._handle_human_review_evidence_query(parsed.query)
                    return
                if parsed.path == "/api/claim-acceptance-decision":
                    self._handle_claim_acceptance_decision_query(parsed.query)
                    return
                if parsed.path == "/api/signoff-record":
                    self._handle_signoff_record_query(parsed.query)
                    return
                if parsed.path == "/api/workbench-review-queue":
                    self._handle_workbench_review_queue_query(parsed.query)
                    return
                if parsed.path == "/api/workbench-claim-queue":
                    self._handle_workbench_claim_queue_query(parsed.query)
                    return
                if parsed.path == "/api/workbench-signoff-summary":
                    self._handle_workbench_signoff_summary_query(parsed.query)
                    return
                if parsed.path == "/api/workbench-document-evidence-queue":
                    self._handle_workbench_document_evidence_queue_query(parsed.query)
                    return
                if parsed.path == "/api/workbench-action-log":
                    self._handle_workbench_action_log_query(parsed.query)
                    return
                if parsed.path == "/api/workbench-action-result":
                    self._handle_workbench_action_result_query(parsed.query)
                    return
                if parsed.path == "/api/workbench-console":
                    self._handle_workbench_console_query(parsed.query)
                    return
                if parsed.path == "/api/document-evidence-manifest":
                    self._handle_document_evidence_manifest_query(parsed.query)
                    return
                if parsed.path == "/api/document-intake-report":
                    self._handle_document_intake_report_query(parsed.query)
                    return
                if parsed.path == "/api/semantic-alignment":
                    self._handle_semantic_alignment_query(parsed.query)
                    return
                if parsed.path == "/api/claim-metric-report":
                    self._handle_claim_metric_report_query(parsed.query)
                    return
                if parsed.path == "/api/publicity-risk-report":
                    self._handle_publicity_risk_report_query(parsed.query)
                    return
                if parsed.path == "/api/leadership-review-brief":
                    self._handle_leadership_review_brief_query(parsed.query)
                    return
                if parsed.path == "/api/open-decisions":
                    self._handle_open_decisions_query(parsed.query)
                    return
                if parsed.path == "/api/document-decision-log":
                    self._handle_document_decision_log_query(parsed.query)
                    return
                if parsed.path == "/api/leadership-review-evidence":
                    self._handle_leadership_review_evidence_query(parsed.query)
                    return
                if parsed.path == "/api/document-claim-resolution":
                    self._handle_document_claim_resolution_query(parsed.query)
                    return
                if parsed.path == "/api/document-signoff-summary":
                    self._handle_document_signoff_summary_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-pack":
                    self._handle_knowledge_pack_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-review-queue":
                    self._handle_knowledge_review_queue_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-quality-report":
                    self._handle_knowledge_quality_report_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-pack-selection":
                    self._handle_knowledge_pack_selection_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-eligibility-report":
                    self._handle_knowledge_eligibility_query(parsed.query)
                    return
                if parsed.path == "/api/working-context-packet":
                    self._handle_working_context_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-usage-report":
                    self._handle_knowledge_usage_query(parsed.query)
                    return
                if parsed.path == "/api/constraint-application-audit":
                    self._handle_constraint_audit_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-conflict-report":
                    self._handle_knowledge_conflict_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-audit-enforcement-decision":
                    self._handle_knowledge_audit_enforcement_query(parsed.query)
                    return
                if parsed.path == "/api/workbench-knowledge-review-queue":
                    self._handle_workbench_knowledge_review_queue_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-audit-resolution-log":
                    self._handle_knowledge_audit_resolution_log_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-constraint-review-evidence":
                    self._handle_knowledge_constraint_review_evidence_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-conflict-resolution":
                    self._handle_knowledge_conflict_resolution_query(parsed.query)
                    return
                if parsed.path == "/api/knowledge-assurance-summary":
                    self._handle_knowledge_assurance_summary_query(parsed.query)
                    return
                self._send_json({"status": "fail", "error": "Not found"}, HTTPStatus.NOT_FOUND)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self._send_json({"status": "fail", "error": str(exc)}, HTTPStatus.BAD_REQUEST)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                payload = self._read_json_body()
                if parsed.path == "/api/inspect":
                    self._handle_inspect(payload)
                    return
                if parsed.path == "/api/sessions":
                    self._handle_sessions(payload)
                    return
                if parsed.path == "/api/import-files":
                    self._handle_import_files(payload)
                    return
                if parsed.path == "/api/pick-directory":
                    self._handle_pick_directory()
                    return
                if parsed.path == "/api/agent-run":
                    self._handle_agent_run(payload)
                    return
                if parsed.path == "/api/read-artifact":
                    self._handle_read_artifact(payload)
                    return
                if parsed.path == "/api/term-review-queue":
                    self._handle_term_review_queue(payload)
                    return
                if parsed.path == "/api/term-review-decision":
                    self._handle_term_review_decision(payload)
                    return
                if parsed.path == "/api/generation-strategy":
                    self._handle_generation_strategy(payload)
                    return
                if parsed.path == "/api/user-resolution-decision":
                    self._handle_user_resolution_decision(payload)
                    return
                if parsed.path == "/api/apply-repair-plan":
                    self._handle_apply_repair_plan(payload)
                    return
                if parsed.path == "/api/human-review-evidence":
                    self._handle_record_human_review_evidence(payload)
                    return
                if parsed.path == "/api/claim-acceptance-decision":
                    self._handle_claim_acceptance_decision(payload)
                    return
                if parsed.path == "/api/signoff-record":
                    self._handle_signoff_record(payload)
                    return
                if parsed.path == "/api/workbench-action":
                    self._handle_workbench_action(payload)
                    return
                if parsed.path == "/api/document-decision-log":
                    self._handle_record_document_decision(payload)
                    return
                if parsed.path == "/api/leadership-review-evidence":
                    self._handle_record_leadership_review_evidence(payload)
                    return
                if parsed.path == "/api/knowledge-pack/init":
                    self._handle_knowledge_pack_init(payload)
                    return
                if parsed.path == "/api/knowledge-pack/export":
                    self._handle_knowledge_pack_export(payload)
                    return
                if parsed.path == "/api/knowledge-review-decision":
                    self._handle_knowledge_review_decision(payload)
                    return
                if parsed.path == "/api/knowledge-pack-selection":
                    self._handle_knowledge_pack_selection(payload)
                    return
                if parsed.path == "/api/knowledge-audit-resolution-log":
                    self._handle_record_knowledge_audit_resolution(payload)
                    return
                if parsed.path == "/api/knowledge-constraint-review-evidence":
                    self._handle_record_knowledge_constraint_review(payload)
                    return
                self._send_json({"status": "fail", "error": "Not found"}, HTTPStatus.NOT_FOUND)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self._send_json({"status": "fail", "error": str(exc)}, HTTPStatus.BAD_REQUEST)

        def _handle_inspect(self, payload: dict[str, Any]) -> None:
            project = _required_path(payload, "project")
            state.add_allowed_root(project)
            inspection = inspect_project(project)
            self._send_json({"status": "pass", "routing": _routing_view(inspection), "inspection": inspection})

        def _handle_sessions(self, payload: dict[str, Any]) -> None:
            project = _required_path(payload, "project")
            state.add_allowed_root(project)
            self._send_json({"status": "pass", "session_index": load_session_index(project)})

        def _handle_import_files(self, payload: dict[str, Any]) -> None:
            project = _write_imported_files(payload.get("files"))
            state.add_allowed_root(project)
            inspection = inspect_project(project)
            source_files = [
                item["path"]
                for item in inspection.get("supported_files", [])
            ]
            self._send_json(
                {
                    "status": "pass",
                    "project": project.as_posix(),
                    "routing": _routing_view(inspection),
                    "inspection": inspection,
                    "source_files": source_files,
                }
            )

        def _handle_pick_directory(self) -> None:
            if not ip_address(self.client_address[0].split("%", 1)[0]).is_loopback:
                raise ValueError("Local directory selection is only available from this computer")
            project = _pick_directory()
            if project is None:
                self._send_json({"status": "cancelled"})
                return
            state.add_allowed_root(project)
            inspection = inspect_project(project)
            self._send_json(
                {
                    "status": "pass",
                    "project": project.as_posix(),
                    "routing": _routing_view(inspection),
                    "inspection": inspection,
                    "source_files": [item["path"] for item in inspection.get("supported_files", [])],
                }
            )

        def _handle_agent_run(self, payload: dict[str, Any]) -> None:
            project = _required_path(payload, "project")
            target_locale = str(payload.get("target_locale") or "").strip()
            if not target_locale:
                raise ValueError("target_locale is required")
            output_root = _optional_path(payload, "output_root")
            responses_dir = _optional_path(payload, "responses_dir")
            generated_dir = _optional_path(payload, "generated_dir")
            generated = _optional_path(payload, "generated")
            provider_url = _optional_string(payload.get("provider_url"))
            for root in (project, output_root, responses_dir, generated_dir, generated):
                state.add_allowed_root(root)
            result = run_agent(
                project,
                target_locale,
                str(payload.get("source_locale") or "en-US").strip() or "en-US",
                _source_files(payload.get("source_files")),
                output_root,
                _optional_string(payload.get("run_id")),
                _optional_int(payload.get("max_segments"), 80),
                _optional_int(payload.get("limit_tokens"), 4000),
                responses_dir,
                generated_dir,
                generated,
                bool(payload.get("synthetic_draft")),
                provider_url,
                {},
                _optional_int(payload.get("provider_timeout_seconds"), 60),
                _optional_string(payload.get("delivery_run_id")),
                str(payload.get("workflow_depth") or "ask"),
                str(payload.get("preflight_mode") or "auto"),
                str(payload.get("privacy_mode") or "standard"),
                str(payload.get("data_classification") or "internal"),
                str(payload.get("status") or "draft_package"),
                _optional_string(payload.get("operating_mode")),
                _optional_string(payload.get("reference_policy")),
            )
            state.allow_agent_result(result)
            self._send_json({"status": "pass", "agent_result": result})

        def _handle_read_artifact(self, payload: dict[str, Any]) -> None:
            path = _required_path(payload, "path")
            if not state.is_allowed(path):
                raise ValueError(f"Artifact is outside allowed workbench roots: {path}")
            if not path.is_file():
                raise ValueError(f"Artifact is not a file: {path}")
            max_bytes = min(_optional_int(payload.get("max_bytes"), MAX_ARTIFACT_BYTES), MAX_ARTIFACT_BYTES)
            data = path.read_bytes()
            truncated = len(data) > max_bytes
            content = data[:max_bytes].decode("utf-8-sig", errors="replace")
            self._send_json({"status": "pass", "path": path.as_posix(), "truncated": truncated, "content": content})

        def _handle_term_review_queue(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Term review queue is outside allowed workbench roots: {state_dir}")
            queue = read_term_review_queue(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "term_review_queue": queue})

        def _handle_term_review_decision(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Term review queue is outside allowed workbench roots: {state_dir}")
            decision = payload.get("decision")
            if not isinstance(decision, dict):
                raise ValueError("decision must be a JSON object")
            result = record_term_review_decision(state_dir, decision)
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "result": result})

        def _handle_generation_strategy(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Generation strategy is outside allowed workbench roots: {state_dir}")
            strategy = read_generation_strategy(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "generation_strategy": strategy})

        def _handle_workbench_review_console(self, query: str) -> None:
            state_dir = _optional_state_dir_from_query(query)
            if state_dir is None:
                self._send_text(render_workbench_console_html(), "text/html; charset=utf-8")
                return
            if not state.is_allowed(state_dir):
                raise ValueError(f"Workbench review console is outside allowed workbench roots: {state_dir}")
            self._send_text(render_workbench_console_html(state_dir), "text/html; charset=utf-8")

        def _handle_workbench_console_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Workbench review console is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "workbench_console": build_workbench_console_view(state_dir)})

        def _handle_document_evidence_manifest_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Document evidence manifest is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "document_evidence_manifest": read_document_evidence_manifest(state_dir)})

        def _handle_document_intake_report_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Document intake report is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "document_intake_report": read_document_intake_report(state_dir)})

        def _handle_semantic_alignment_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Semantic alignment is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "semantic_alignment": read_semantic_alignment(state_dir)})

        def _handle_claim_metric_report_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Claim metric report is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "claim_metric_report": read_claim_metric_report(state_dir)})

        def _handle_publicity_risk_report_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Publicity risk report is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "publicity_risk_report": read_publicity_risk_report(state_dir)})

        def _handle_leadership_review_brief_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Leadership review brief is outside allowed workbench roots: {state_dir}")
            self._send_text(read_leadership_review_brief(state_dir), "text/markdown; charset=utf-8")

        def _handle_open_decisions_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Open decisions are outside allowed workbench roots: {state_dir}")
            self._send_text(read_open_decisions(state_dir), "text/markdown; charset=utf-8")

        def _handle_workbench_document_evidence_queue_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Workbench document evidence queue is outside allowed workbench roots: {state_dir}")
            self._send_json(
                {
                    "status": "pass",
                    "state_dir": state_dir.as_posix(),
                    "workbench_document_evidence_queue": read_workbench_document_evidence_queue(state_dir),
                }
            )

        def _handle_document_decision_log_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Document decision log is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "document_decision_log": read_document_decision_log(state_dir)})

        def _handle_leadership_review_evidence_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Leadership review evidence is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "leadership_review_evidence": read_leadership_review_evidence(state_dir)})

        def _handle_document_claim_resolution_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Document claim resolution is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "document_claim_resolution": read_document_claim_resolution(state_dir)})

        def _handle_document_signoff_summary_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Document signoff summary is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "document_signoff_summary": read_document_signoff_summary(state_dir)})

        def _handle_knowledge_pack_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            pack_id = _pack_id_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge pack is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_pack": read_knowledge_pack(state_dir, pack_id)})

        def _handle_knowledge_review_queue_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            pack_id = _pack_id_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge review queue is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_review_queue": read_knowledge_review_queue(state_dir, pack_id)})

        def _handle_knowledge_quality_report_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            pack_id = _pack_id_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge quality report is outside allowed workbench roots: {state_dir}")
            self._send_text(read_knowledge_quality_report(state_dir, pack_id), "text/markdown; charset=utf-8")

        def _handle_knowledge_pack_selection_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge pack selection is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_pack_selection": read_knowledge_pack_selection(state_dir)})

        def _handle_knowledge_eligibility_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge eligibility report is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_eligibility_report": read_knowledge_eligibility_report(state_dir)})

        def _handle_working_context_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Working Context Packet is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "working_context_packet": read_working_context_packet(state_dir)})

        def _handle_knowledge_usage_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge usage report is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_usage_report": read_knowledge_usage_report(state_dir)})

        def _handle_constraint_audit_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Constraint application audit is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "constraint_application_audit": read_constraint_application_audit(state_dir)})

        def _handle_knowledge_conflict_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge conflict report is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_conflict_report": read_knowledge_conflict_report(state_dir)})

        def _handle_knowledge_audit_enforcement_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge audit enforcement decision is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_audit_enforcement_decision": read_knowledge_audit_enforcement_decision(state_dir)})

        def _handle_workbench_knowledge_review_queue_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Workbench knowledge review queue is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "workbench_knowledge_review_queue": read_workbench_knowledge_review_queue(state_dir)})

        def _handle_knowledge_audit_resolution_log_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge audit resolution log is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_audit_resolution_log": read_knowledge_audit_resolution_log(state_dir)})

        def _handle_knowledge_constraint_review_evidence_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge constraint review evidence is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_constraint_review_evidence": read_knowledge_constraint_review_evidence(state_dir)})

        def _handle_knowledge_conflict_resolution_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge conflict resolution is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_conflict_resolution": build_knowledge_conflict_resolution(state_dir)})

        def _handle_knowledge_assurance_summary_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge assurance summary is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_assurance_summary": build_knowledge_assurance_summary(state_dir)})

        def _handle_blocking_questions_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Blocking questions are outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "blocking_questions": read_blocking_questions(state_dir)})

        def _handle_resolution_options_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Resolution options are outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "resolution_options": read_resolution_options(state_dir)})

        def _handle_generation_handoff_status_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Generation handoff status is outside allowed workbench roots: {state_dir}")
            self._send_json(
                {
                    "status": "pass",
                    "state_dir": state_dir.as_posix(),
                    "generation_handoff_status": read_generation_handoff_decision(state_dir),
                }
            )

        def _handle_artifact_state_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Artifact state is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "artifact_state": read_artifact_state(state_dir)})

        def _handle_stale_segments_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Stale segments are outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "stale_segments": read_stale_segments(state_dir)})

        def _handle_reuse_decision_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Reuse decision is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "reuse_decision": read_reuse_decision(state_dir)})

        def _handle_segment_regeneration_plan_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Segment regeneration plan is outside allowed workbench roots: {state_dir}")
            self._send_json(
                {
                    "status": "pass",
                    "state_dir": state_dir.as_posix(),
                    "segment_regeneration_plan": read_segment_regeneration_plan(state_dir),
                }
            )

        def _handle_repair_request_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Repair request is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "repair_request": read_repair_request(state_dir)})

        def _handle_repair_result_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Repair result is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "repair_result": read_repair_result(state_dir)})

        def _handle_repair_history_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Repair history is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "repair_history": read_repair_history(state_dir)})

        def _handle_knowledge_repair_query(self, query: str, artifact: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge repair artifact is outside allowed workbench roots: {state_dir}")
            readers = {
                "plan": ("knowledge_repair_plan", read_knowledge_repair_plan),
                "request": ("knowledge_repair_request", read_knowledge_repair_request),
                "impact": ("knowledge_repair_impact_report", read_knowledge_repair_impact_report),
            }
            key, reader = readers[artifact]
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), key: reader(state_dir)})

        def _handle_evaluation_scorecard_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Evaluation scorecard is outside allowed workbench roots: {state_dir}")
            self._send_json(
                {
                    "status": "pass",
                    "state_dir": state_dir.as_posix(),
                    "evaluation_scorecard": read_evaluation_scorecard(state_dir),
                }
            )

        def _handle_evidence_level_report_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Evidence level report is outside allowed workbench roots: {state_dir}")
            self._send_text(read_evidence_level_report(state_dir), "text/markdown; charset=utf-8")

        def _handle_human_review_evidence_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Human review evidence is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "human_review_evidence": read_human_review_evidence(state_dir)})

        def _handle_claim_acceptance_decision_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Claim acceptance decision is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "claim_acceptance_decision": read_claim_acceptance_decision(state_dir)})

        def _handle_signoff_record_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Signoff record is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "signoff_record": read_signoff_record(state_dir)})

        def _handle_workbench_review_queue_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Workbench review queue is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "workbench_review_queue": read_workbench_review_queue(state_dir)})

        def _handle_workbench_claim_queue_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Workbench claim queue is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "workbench_claim_queue": read_workbench_claim_queue(state_dir)})

        def _handle_workbench_signoff_summary_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Workbench signoff summary is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "workbench_signoff_summary": read_workbench_signoff_summary(state_dir)})

        def _handle_workbench_action_log_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Workbench action log is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "workbench_action_log": read_workbench_action_log(state_dir)})

        def _handle_workbench_action_result_query(self, query: str) -> None:
            state_dir = _state_dir_from_query(query)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Workbench action result is outside allowed workbench roots: {state_dir}")
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "workbench_action_result": read_workbench_action_result(state_dir)})

        def _handle_apply_repair_plan(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Repair plan is outside allowed workbench roots: {state_dir}")
            generated_segments = _optional_path(payload, "generated_segments")
            if generated_segments is not None and not state.is_allowed(generated_segments):
                raise ValueError(f"Generated segments are outside allowed workbench roots: {generated_segments}")
            result = apply_repair_plan(
                state_dir,
                generated_segments_path=generated_segments,
                run_id=_optional_string(payload.get("run_id")),
            )
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "repair_result": result})

        def _handle_user_resolution_decision(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Resolution decision is outside allowed workbench roots: {state_dir}")
            decision = payload.get("decision")
            if not isinstance(decision, dict):
                raise ValueError("decision must be a JSON object")
            result = record_user_resolution_decision(state_dir, decision)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "result": result})

        def _handle_record_human_review_evidence(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Human review evidence is outside allowed workbench roots: {state_dir}")
            evidence = payload.get("evidence")
            if not isinstance(evidence, dict):
                raise ValueError("evidence must be a JSON object")
            result = record_human_review_evidence(state_dir, evidence, run_id=_optional_string(payload.get("run_id")))
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "result": result})

        def _handle_claim_acceptance_decision(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Claim acceptance decision is outside allowed workbench roots: {state_dir}")
            claims = payload.get("claims")
            if claims is not None and not isinstance(claims, list):
                raise ValueError("claims must be a list when provided")
            accepted_risk = payload.get("accepted_risk")
            if accepted_risk is not None and not isinstance(accepted_risk, dict):
                raise ValueError("accepted_risk must be a JSON object when provided")
            result = build_claim_acceptance_decision(
                state_dir,
                requested_claims=[str(item) for item in claims] if claims is not None else None,
                accepted_risk=accepted_risk or {},
                run_id=_optional_string(payload.get("run_id")),
            )
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "claim_acceptance_decision": result})

        def _handle_signoff_record(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Signoff record is outside allowed workbench roots: {state_dir}")
            signoff = payload.get("signoff")
            if not isinstance(signoff, dict):
                raise ValueError("signoff must be a JSON object")
            result = create_signoff_record(state_dir, signoff, run_id=_optional_string(payload.get("run_id")))
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "signoff_record": result})

        def _handle_workbench_action(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Workbench action is outside allowed workbench roots: {state_dir}")
            action = payload.get("action")
            if not isinstance(action, dict):
                raise ValueError("action must be a JSON object")
            result = perform_workbench_action(state_dir, action, run_id=_optional_string(payload.get("run_id")))
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "workbench_action_result": result})

        def _handle_record_document_decision(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Document decision log is outside allowed workbench roots: {state_dir}")
            decision = payload.get("decision")
            if not isinstance(decision, dict):
                raise ValueError("decision must be a JSON object")
            result = record_document_decision(state_dir, decision, run_id=_optional_string(payload.get("run_id")))
            build_document_claim_resolution(state_dir, run_id=_optional_string(payload.get("run_id")))
            build_document_signoff_summary(state_dir, run_id=_optional_string(payload.get("run_id")))
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "result": result})

        def _handle_record_leadership_review_evidence(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Leadership review evidence is outside allowed workbench roots: {state_dir}")
            evidence = payload.get("evidence")
            if not isinstance(evidence, dict):
                raise ValueError("evidence must be a JSON object")
            result = record_leadership_review_evidence(state_dir, evidence, run_id=_optional_string(payload.get("run_id")))
            build_document_claim_resolution(state_dir, run_id=_optional_string(payload.get("run_id")))
            build_document_signoff_summary(state_dir, run_id=_optional_string(payload.get("run_id")))
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "result": result})

        def _handle_knowledge_pack_init(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge pack is outside allowed workbench roots: {state_dir}")
            result = init_knowledge_pack(
                state_dir,
                pack_id=_pack_id_from_payload(payload),
                name=_optional_string(payload.get("name")),
                source_locale=_optional_string(payload.get("source_locale")),
                target_locale=_optional_string(payload.get("target_locale")),
                domains=[str(item) for item in payload.get("domains", [])] if isinstance(payload.get("domains"), list) else [],
                privacy_mode=_optional_string(payload.get("privacy_mode")) or "local_only",
                created_by=_optional_string(payload.get("created_by")) or "localize-anything-runtime",
                quality_level=_optional_string(payload.get("quality_level")) or "raw",
                supported_scenarios=[str(item) for item in payload.get("supported_scenarios", [])] if isinstance(payload.get("supported_scenarios"), list) else [],
            )
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_pack": result})

        def _handle_knowledge_pack_export(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge pack export is outside allowed workbench roots: {state_dir}")
            result = export_knowledge_pack(state_dir, _pack_id_from_payload(payload))
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_pack_export": result})

        def _handle_knowledge_review_decision(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge review decision is outside allowed workbench roots: {state_dir}")
            decision = payload.get("decision")
            if not isinstance(decision, dict):
                raise ValueError("decision must be a JSON object")
            result = record_knowledge_review_decision(state_dir, _pack_id_from_payload(payload), decision, run_id=_optional_string(payload.get("run_id")))
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "result": result})

        def _handle_knowledge_pack_selection(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge pack selection is outside allowed workbench roots: {state_dir}")
            pack_ids = payload.get("pack_ids") if isinstance(payload.get("pack_ids"), list) else [payload["pack_id"]] if payload.get("pack_id") else []
            pack_paths = payload.get("pack_paths") if isinstance(payload.get("pack_paths"), list) else [payload["pack_path"]] if payload.get("pack_path") else []
            resolved_pack_paths = [Path(str(item)).expanduser().resolve() for item in pack_paths]
            if any(not state.is_allowed(path) for path in resolved_pack_paths):
                raise ValueError("Knowledge pack path is outside allowed workbench roots")
            result = select_knowledge_packs(
                state_dir,
                pack_ids=[str(item) for item in pack_ids],
                pack_paths=resolved_pack_paths,
                source_locale=str(payload.get("source_locale") or ""),
                target_locale=str(payload.get("target_locale") or ""),
                domains=[str(item) for item in payload.get("domains", [])] if isinstance(payload.get("domains"), list) else [],
                scenario=str(payload.get("scenario") or ""),
                operating_mode=str(payload.get("operating_mode") or "greenfield_localization"),
                selection_source=str(payload.get("selection_source") or "workbench_api"),
                selected_by=str(payload.get("selected_by") or "workbench_api"),
                allow_experimental=bool(payload.get("allow_experimental")),
                allowed_domains=[str(item) for item in payload.get("allowed_domains", [])] if isinstance(payload.get("allowed_domains"), list) else [],
                allowed_scenarios=[str(item) for item in payload.get("allowed_scenarios", [])] if isinstance(payload.get("allowed_scenarios"), list) else [],
                compatible_locales=[str(item) for item in payload.get("compatible_locales", [])] if isinstance(payload.get("compatible_locales"), list) else [],
            )
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "knowledge_pack_selection": result})

        def _handle_record_knowledge_audit_resolution(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge audit resolution is outside allowed workbench roots: {state_dir}")
            decision = payload.get("decision")
            if not isinstance(decision, dict):
                raise ValueError("decision must be a JSON object")
            result = record_knowledge_audit_resolution(state_dir, decision, run_id=_optional_string(payload.get("run_id")))
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "result": result})

        def _handle_record_knowledge_constraint_review(self, payload: dict[str, Any]) -> None:
            state_dir = _state_dir_from_payload(payload)
            if not state.is_allowed(state_dir):
                raise ValueError(f"Knowledge constraint review evidence is outside allowed workbench roots: {state_dir}")
            evidence = payload.get("evidence")
            if not isinstance(evidence, dict):
                raise ValueError("evidence must be a JSON object")
            result = record_knowledge_constraint_review_evidence(state_dir, evidence, run_id=_optional_string(payload.get("run_id")))
            state.add_allowed_root(state_dir)
            self._send_json({"status": "pass", "state_dir": state_dir.as_posix(), "result": result})

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            value = json.loads(self.rfile.read(length).decode("utf-8-sig"))
            if not isinstance(value, dict):
                raise ValueError("Request body must be a JSON object")
            return value

        def _send_json(self, value: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, value: str, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = value.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return LocalizeAnythingUIHandler


def _required_path(payload: dict[str, Any], key: str) -> Path:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return Path(value).expanduser().resolve()


def _optional_path(payload: dict[str, Any], key: str) -> Path | None:
    value = str(payload.get(key) or "").strip()
    return Path(value).expanduser().resolve() if value else None


def _state_dir_from_payload(payload: dict[str, Any]) -> Path:
    if payload.get("state_dir"):
        return _required_path(payload, "state_dir")
    project = _required_path(payload, "project")
    return project / ".localize-anything"


def _state_dir_from_query(query: str) -> Path:
    params = parse_qs(query)
    state_dir = (params.get("state_dir") or [""])[0]
    if state_dir:
        return Path(state_dir).expanduser().resolve()
    project = (params.get("project") or [""])[0]
    if not project:
        raise ValueError("state_dir or project query parameter is required")
    return Path(project).expanduser().resolve() / ".localize-anything"


def _pack_id_from_query(query: str) -> str:
    value = (parse_qs(query).get("pack_id") or [""])[0].strip()
    if not value:
        raise ValueError("pack_id query parameter is required")
    return value


def _pack_id_from_payload(payload: dict[str, Any]) -> str:
    value = str(payload.get("pack_id") or "").strip()
    if not value:
        raise ValueError("pack_id is required")
    return value


def _optional_state_dir_from_query(query: str) -> Path | None:
    params = parse_qs(query)
    state_dir = (params.get("state_dir") or [""])[0]
    if state_dir:
        return Path(state_dir).expanduser().resolve()
    project = (params.get("project") or [""])[0]
    return Path(project).expanduser().resolve() / ".localize-anything" if project else None


def _source_files(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        items = [line.strip() for line in value.replace(",", "\n").splitlines()]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        raise ValueError("source_files must be a string or list")
    cleaned = [item.replace("\\", "/") for item in items if item]
    return cleaned or None


def _write_imported_files(value: Any) -> Path:
    if not isinstance(value, list) or not value:
        raise ValueError("files must be a non-empty list")
    if len(value) > MAX_IMPORT_FILES:
        raise ValueError(f"Too many imported files; limit is {MAX_IMPORT_FILES}")
    root = Path(gettempdir()) / "localize-anything-imports" / f"import-{uuid.uuid4().hex[:12]}"
    root.mkdir(parents=True, exist_ok=False)
    total = 0
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each imported file must be an object")
        relative = _safe_import_relative_path(str(item.get("relative_path") or item.get("name") or ""))
        encoded = str(item.get("content_base64") or "")
        try:
            data = base64.b64decode(encoded, validate=True)
        except binascii.Error as exc:
            raise ValueError(f"Invalid base64 content for {relative.as_posix()}") from exc
        if len(data) > MAX_IMPORT_FILE_BYTES:
            raise ValueError(f"Imported file is too large: {relative.as_posix()}")
        total += len(data)
        if total > MAX_IMPORT_TOTAL_BYTES:
            raise ValueError("Imported files exceed the total size limit")
        destination = root / Path(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    return root


def _pick_directory() -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise ValueError("This Python installation does not provide a native directory picker") from exc

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(parent=root, title="选择本地项目目录", mustexist=True)
    except tk.TclError as exc:
        raise ValueError(f"Could not open the native directory picker: {exc}") from exc
    finally:
        if root is not None:
            root.destroy()
    return Path(selected).expanduser().resolve() if selected else None


def _safe_import_relative_path(value: str) -> PurePosixPath:
    normalized = value.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe imported file path: {value!r}")
    parts = tuple(part for part in path.parts if part not in {"", "."})
    if not parts:
        raise ValueError(f"Unsafe imported file path: {value!r}")
    return PurePosixPath(*parts)


def _optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_int(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("Numeric options must be positive")
    return parsed


def _routing_view(inspection: dict[str, Any]) -> dict[str, Any]:
    supported = inspection.get("supported_files", [])
    assessment = inspection.get("preflight_assessment", {})
    return {
        "supported_file_count": len(supported),
        "adapter_counts": inspection.get("adapter_counts", {}),
        "unprocessed_non_text_asset_count": len(inspection.get("unprocessed_non_text_assets", [])),
        "recommended_preflight_mode": assessment.get("recommended_preflight_mode"),
        "recommended_workflow_depth": assessment.get("recommended_workflow_depth"),
        "reason": assessment.get("reason"),
        "supported_files": supported[:500],
    }


WORKBENCH_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Localize Anything Workbench</title>
  <link rel="icon" href="data:,">
  <style>
    :root {
      --bg: #f6f8fa;
      --panel: #ffffff;
      --panel-muted: #f6f8fa;
      --line: #d0d7de;
      --text: #24292f;
      --muted: #57606a;
      --accent: #0969da;
      --accent-hover: #0550ae;
      --accent-soft: #ddf4ff;
      --success: #1a7f37;
      --success-soft: #dafbe1;
      --bad: #cf222e;
      --bad-soft: #ffebe9;
      --code: #0d1117;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      letter-spacing: 0;
      line-height: 1.45;
    }
    header {
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 0 24px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1 { font-size: 18px; margin: 0; font-weight: 760; }
    label {
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin: 12px 0 6px;
      font-weight: 650;
    }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      font: inherit;
      font-size: 13px;
      padding: 9px 10px;
      min-height: 40px;
      outline: 0;
      transition: border-color 160ms ease, box-shadow 160ms ease;
    }
    input::placeholder, textarea::placeholder { color: var(--muted); }
    input:focus, textarea:focus, select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-soft);
    }
    textarea {
      min-height: 86px;
      resize: vertical;
      font-family: Consolas, "Courier New", monospace;
    }
    .file-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 8px;
    }
    .file-input {
      position: absolute;
      width: 1px;
      height: 1px;
      opacity: 0;
      overflow: hidden;
    }
    .dropzone {
      border: 1px dashed #9aa8b5;
      border-radius: 6px;
      background: var(--panel-muted);
      color: var(--muted);
      padding: 14px;
      min-height: 76px;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      font-size: 13px;
      cursor: pointer;
      transition: background 160ms ease, border-color 160ms ease, color 160ms ease;
    }
    .dropzone.dragging {
      border-color: var(--accent);
      color: var(--accent);
      background: var(--accent-soft);
    }
    button, .file-button {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      min-height: 36px;
      font: inherit;
      font-size: 13px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0 12px;
      text-decoration: none;
      transition: background 160ms ease, border-color 160ms ease, color 160ms ease, box-shadow 160ms ease, transform 120ms ease;
    }
    .file-button {
      margin: 0;
      font-weight: 650;
    }
    button:hover:not(:disabled), .file-button:hover {
      border-color: var(--accent);
      color: var(--accent);
      background: var(--accent-soft);
    }
    button:focus-visible, .file-button:focus-visible, .dropzone:focus-visible {
      outline: 0;
      box-shadow: 0 0 0 3px var(--accent-soft);
      border-color: var(--accent);
    }
    button:active:not(:disabled), .file-button:active, .dropzone:active {
      transform: translateY(1px);
    }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 700;
    }
    button.primary:hover:not(:disabled) {
      background: var(--accent-hover);
      border-color: var(--accent-hover);
      color: #fff;
    }
    button:disabled {
      opacity: 0.55;
      cursor: wait;
    }
    body.is-busy .dropzone,
    body.is-busy .file-button {
      opacity: 0.55;
      cursor: wait;
      pointer-events: none;
    }
    .status {
      min-height: 44px;
      border: 1px solid var(--line);
      border-left: 4px solid var(--accent);
      background: #fff;
      border-radius: 6px;
      padding: 11px 13px;
      margin-bottom: 16px;
      font-size: 13px;
    }
    .status.fail { border-left-color: var(--bad); background: var(--bad-soft); }
    .status.pass { border-left-color: var(--success); background: var(--success-soft); }
    .band {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 6px;
      overflow: hidden;
    }
    .band h2 {
      font-size: 14px;
      margin: 0;
      padding: 11px 13px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-muted);
    }
    .band-body { padding: 13px; }
    .table-wrap {
      width: 100%;
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      min-width: 520px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 7px 8px;
      text-align: left;
      vertical-align: top;
      word-break: break-word;
    }
    th { color: var(--muted); font-weight: 700; background: var(--panel-muted); }
    code, pre {
      font-family: Consolas, "Courier New", monospace;
      letter-spacing: 0;
    }
    pre {
      margin: 0;
      padding: 12px;
      overflow: auto;
      max-height: 50vh;
      background: var(--code);
      color: #f8fafc;
      font-size: 12px;
      white-space: pre-wrap;
    }
    .path {
      font-family: Consolas, "Courier New", monospace;
      color: var(--muted);
      font-size: 12px;
    }
    .artifact-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 86px;
      gap: 8px;
      align-items: center;
      border-bottom: 1px solid var(--line);
      padding: 9px 0;
    }
    .artifact-row:last-child { border-bottom: 0; }
    .pill {
      display: inline-block;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      color: var(--muted);
      background: #fff;
      margin: 0 5px 5px 0;
    }
    .app-window {
      min-height: 100vh;
      background: linear-gradient(180deg, #ffffff 0%, #f6f8fa 100%);
    }
    .titlebar {
      height: 64px;
      display: grid;
      grid-template-columns: minmax(270px, 1fr) auto minmax(270px, 1fr);
      align-items: center;
      padding: 0 28px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.92);
    }
    .window-brand {
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
    }
    .app-mark {
      width: 32px;
      height: 32px;
      border-radius: 9px;
      background: linear-gradient(180deg, #2f81f7, #0969da);
      color: #fff;
      display: grid;
      place-items: center;
      font-weight: 800;
      font-size: 13px;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.3);
    }
    .app-title {
      font-size: 18px;
      font-weight: 760;
      white-space: nowrap;
    }
    .tabs {
      display: flex;
      align-items: stretch;
      height: 64px;
      gap: 18px;
    }
    .tab {
      min-width: 76px;
      border: 0;
      border-radius: 0;
      background: transparent;
      color: var(--text);
      font-size: 15px;
      font-weight: 700;
      position: relative;
    }
    .tab:hover:not(:disabled) {
      background: transparent;
      color: var(--accent);
    }
    .tab.active {
      color: var(--accent);
    }
    .tab.active::after {
      content: "";
      position: absolute;
      left: 10px;
      right: 10px;
      bottom: 0;
      height: 3px;
      border-radius: 999px 999px 0 0;
      background: var(--accent);
    }
    .health {
      justify-self: end;
      font-size: 12px;
    }
    .contextbar {
      min-height: 56px;
      display: flex;
      align-items: center;
      gap: 0;
      padding: 0 34px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.88);
      overflow-x: auto;
    }
    .context-item,
    .context-action {
      display: inline-flex;
      align-items: center;
      gap: 9px;
      padding: 0 18px;
      min-height: 28px;
      color: var(--text);
      font-size: 14px;
      white-space: nowrap;
      border-left: 1px solid transparent;
    }
    .context-item + .context-item,
    .context-action {
      border-left-color: var(--line);
    }
    .context-icon {
      color: var(--muted);
      font-size: 12px;
      font-weight: 760;
      letter-spacing: 0;
      min-width: 22px;
      text-align: center;
    }
    .context-action {
      border-top: 0;
      border-right: 0;
      border-bottom: 0;
      border-radius: 0;
      background: transparent;
      color: var(--accent);
      font-weight: 700;
    }
    .workspace {
      display: block;
      height: auto;
      min-height: calc(100vh - 121px);
      padding: 34px 42px 40px;
      overflow: visible;
    }
    .page-intro {
      margin: 0 0 22px;
    }
    .page-intro h2 {
      margin: 0;
      font-size: 32px;
      line-height: 1.14;
      letter-spacing: 0;
    }
    .page-intro p {
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 15px;
    }
    .generate-layout {
      display: grid;
      grid-template-columns: minmax(0, 1.08fr) minmax(360px, 0.92fr);
      gap: 18px;
      align-items: stretch;
    }
    .work-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.96);
      box-shadow: 0 8px 28px rgba(31, 35, 40, 0.08);
      padding: 22px;
    }
    .work-card h3 {
      margin: 0 0 18px;
      font-size: 18px;
      line-height: 1.2;
    }
    .dropzone.hero-drop {
      min-height: 176px;
      border-radius: 8px;
      border-color: #9ec5fe;
      background: #f6fbff;
      flex-direction: column;
      gap: 10px;
      margin-bottom: 12px;
    }
    .drop-icon {
      width: 54px;
      height: 42px;
      border-radius: 8px;
      background: linear-gradient(180deg, #79b8ff, #2f81f7);
      box-shadow: inset 0 -5px 0 rgba(9, 105, 218, 0.35);
    }
    .drop-title {
      color: var(--text);
      font-size: 20px;
      font-weight: 760;
    }
    .form-grid {
      display: grid;
      grid-template-columns: 160px minmax(0, 1fr);
      gap: 12px 18px;
      align-items: center;
      margin-top: 18px;
    }
    .form-grid label {
      margin: 0;
      color: var(--text);
      font-size: 14px;
    }
    .mode-options {
      display: grid;
      gap: 8px;
    }
    .mode-options label {
      display: flex;
      align-items: center;
      gap: 9px;
      color: var(--text);
      font-weight: 500;
    }
    .mode-options input {
      width: 18px;
      min-height: 18px;
    }
    .recommended {
      display: inline-flex;
      align-items: center;
      margin-left: 8px;
      padding: 2px 9px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 760;
    }
    .primary.wide {
      width: 100%;
      min-height: 44px;
      margin-top: 18px;
      font-size: 15px;
    }
    .secondary-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 10px;
    }
    .preview-list {
      margin-top: 2px;
      border-top: 1px solid var(--line);
    }
    .preview-row {
      display: grid;
      grid-template-columns: 150px minmax(0, 1fr);
      gap: 18px;
      align-items: center;
      min-height: 50px;
      border-bottom: 1px solid var(--line);
      font-size: 14px;
    }
    .preview-row .key {
      color: var(--muted);
    }
    .preview-row .value {
      color: var(--text);
      font-weight: 650;
      min-width: 0;
      word-break: break-word;
    }
    .info-note {
      margin-top: 22px;
      border: 1px solid #9ec5fe;
      border-radius: 8px;
      background: #eef6ff;
      color: var(--accent);
      padding: 14px 16px;
      font-weight: 650;
      font-size: 14px;
    }
    .notice-bar {
      margin: 18px 0;
    }
    .delivery-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(320px, 0.72fr);
      gap: 18px;
      align-items: start;
    }
    .sessions-panel {
      margin-top: 18px;
    }
    .detail-stack {
      display: grid;
      gap: 18px;
    }
    .band.work-band {
      box-shadow: 0 6px 22px rgba(31, 35, 40, 0.06);
      border-radius: 8px;
    }
    .band.work-band h2 {
      background: #f6f8fa;
      padding: 13px 16px;
    }
    @media (max-width: 1180px) {
      .generate-layout,
      .delivery-grid {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 900px) {
      header { padding: 0 16px; }
      main {
        grid-template-columns: 1fr;
        height: auto;
        min-height: 0;
      }
      .titlebar {
        height: auto;
        grid-template-columns: 1fr;
        gap: 12px;
        padding: 14px 18px 0;
      }
      .tabs {
        justify-content: stretch;
        width: 100%;
        overflow-x: auto;
      }
      .health { justify-self: start; }
      .contextbar {
        padding: 0 16px;
      }
      .workspace {
        padding: 26px 16px 30px;
      }
      .page-intro h2 {
        font-size: 28px;
      }
      .form-grid {
        grid-template-columns: 1fr;
      }
      .secondary-actions {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 520px) {
      header { align-items: flex-start; flex-direction: column; height: auto; padding: 12px 16px; }
      .file-actions { grid-template-columns: 1fr; }
      table { min-width: 460px; }
    }
    @media (prefers-reduced-motion: reduce) {
      * {
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
      }
      button:active:not(:disabled), .file-button:active, .dropzone:active {
        transform: none;
      }
    }
  </style>
</head>
<body>
  <div class="app-window">
    <header class="titlebar">
      <div class="window-brand">
        <div class="app-mark" aria-hidden="true">LA</div>
        <div class="app-title">Localize Anything</div>
      </div>
      <nav class="tabs" aria-label="Workbench sections">
        <button class="tab active" type="button" data-tab="generate" onclick="setTab('generate')">生成</button>
        <button class="tab" type="button" data-tab="review" onclick="setTab('review')">审查</button>
        <button class="tab" type="button" data-tab="sessions" onclick="setTab('sessions')">会话</button>
        <button class="tab" type="button" data-tab="settings" onclick="setTab('settings')">设置</button>
      </nav>
      <div class="health path" id="health">checking</div>
    </header>

    <div class="contextbar" aria-label="Project context">
      <div class="context-item"><span class="context-icon">APP</span><span id="contextProject">未选择项目</span></div>
      <div class="context-item"><span class="context-icon">SRC</span><span id="contextType">源码项目</span></div>
      <div class="context-item"><span class="context-icon">LOC</span><span id="contextLocale">en-US -> zh-CN</span></div>
      <div class="context-item"><span class="context-icon">SEG</span><span id="contextSegments">0 片段</span></div>
      <div class="context-item"><span class="context-icon">CHK</span><span id="contextScope">检查范围：自动</span></div>
      <button class="context-action" type="button" onclick="inspectProject()">查看资源清单</button>
      <button class="context-action" type="button" onclick="focusProject()">切换项目</button>
    </div>

    <main class="workspace">
      <section class="page-intro" id="generateTop">
        <h2>生成本地化交付物</h2>
        <p>选择一个项目文件夹，系统将识别本地化资源并生成语言文件。</p>
      </section>

      <section class="generate-layout">
        <div class="work-card" id="settingsPanel">
          <h3>本地化设置</h3>
          <label for="project">项目路径</label>
          <input id="project" placeholder="C:\path\to\project">

          <label for="dropzone">打开本地项目或导入文件</label>
          <div class="dropzone hero-drop" id="dropzone" role="button" tabindex="0">
            <div class="drop-icon" aria-hidden="true"></div>
            <div class="drop-title">打开本地项目目录</div>
            <div>直接读取本机路径，不上传目录内容</div>
          </div>
          <div class="file-actions">
            <button class="file-button" type="button" onclick="pickProjectDirectory()">选择本地目录</button>
            <label class="file-button" for="filePicker">导入文件</label>
            <input class="file-input" id="filePicker" type="file" multiple>
          </div>

          <div class="form-grid">
            <label for="targetLocale">目标语言</label>
            <input id="targetLocale" value="zh-CN" list="localeOptions" autocomplete="off" spellcheck="false">
            <datalist id="localeOptions">
              <option value="ar-SA" label="🇸🇦 阿拉伯语 · العربية（沙特阿拉伯）"></option>
              <option value="bn-BD" label="🇧🇩 孟加拉语 · বাংলা（孟加拉国）"></option>
              <option value="cs-CZ" label="🇨🇿 捷克语 · Čeština（捷克）"></option>
              <option value="da-DK" label="🇩🇰 丹麦语 · Dansk（丹麦）"></option>
              <option value="de-DE" label="🇩🇪 德语 · Deutsch（德国）"></option>
              <option value="el-GR" label="🇬🇷 希腊语 · Ελληνικά（希腊）"></option>
              <option value="en-GB" label="🇬🇧 英语 · English（英国）"></option>
              <option value="en-US" label="🇺🇸 英语 · English（美国）"></option>
              <option value="es-ES" label="🇪🇸 西班牙语 · Español（西班牙）"></option>
              <option value="es-MX" label="🇲🇽 西班牙语 · Español（墨西哥）"></option>
              <option value="fi-FI" label="🇫🇮 芬兰语 · Suomi（芬兰）"></option>
              <option value="fr-CA" label="🇨🇦 法语 · Français（加拿大）"></option>
              <option value="fr-FR" label="🇫🇷 法语 · Français（法国）"></option>
              <option value="he-IL" label="🇮🇱 希伯来语 · עברית（以色列）"></option>
              <option value="hi-IN" label="🇮🇳 印地语 · हिन्दी（印度）"></option>
              <option value="hu-HU" label="🇭🇺 匈牙利语 · Magyar（匈牙利）"></option>
              <option value="id-ID" label="🇮🇩 印度尼西亚语 · Bahasa Indonesia（印度尼西亚）"></option>
              <option value="it-IT" label="🇮🇹 意大利语 · Italiano（意大利）"></option>
              <option value="ja-JP" label="🇯🇵 日语 · 日本語（日本）"></option>
              <option value="ko-KR" label="🇰🇷 韩语 · 한국어（韩国）"></option>
              <option value="ms-MY" label="🇲🇾 马来语 · Bahasa Melayu（马来西亚）"></option>
              <option value="nl-NL" label="🇳🇱 荷兰语 · Nederlands（荷兰）"></option>
              <option value="no-NO" label="🇳🇴 挪威语 · Norsk（挪威）"></option>
              <option value="pl-PL" label="🇵🇱 波兰语 · Polski（波兰）"></option>
              <option value="pt-BR" label="🇧🇷 葡萄牙语 · Português（巴西）"></option>
              <option value="pt-PT" label="🇵🇹 葡萄牙语 · Português（葡萄牙）"></option>
              <option value="ro-RO" label="🇷🇴 罗马尼亚语 · Română（罗马尼亚）"></option>
              <option value="ru-RU" label="🇷🇺 俄语 · Русский（俄罗斯）"></option>
              <option value="sv-SE" label="🇸🇪 瑞典语 · Svenska（瑞典）"></option>
              <option value="th-TH" label="🇹🇭 泰语 · ไทย（泰国）"></option>
              <option value="tr-TR" label="🇹🇷 土耳其语 · Türkçe（土耳其）"></option>
              <option value="uk-UA" label="🇺🇦 乌克兰语 · Українська（乌克兰）"></option>
              <option value="vi-VN" label="🇻🇳 越南语 · Tiếng Việt（越南）"></option>
              <option value="zh-CN" label="🇨🇳 简体中文 · 中文（中国大陆）"></option>
              <option value="zh-HK" label="🇭🇰 繁体中文 · 中文（香港）"></option>
              <option value="zh-TW" label="🇹🇼 繁体中文 · 中文（台湾）"></option>
            </datalist>

            <label>本地化模式</label>
            <div class="mode-options">
              <label><input type="radio" name="mode" value="greenfield_localization" checked> 新建本地化 <span class="recommended">推荐</span></label>
              <label><input type="radio" name="mode" value="existing_locale_maintenance"> 维护现有语言</label>
              <label><input type="radio" name="mode" value="rewrite_or_harmonization"> 重写 / 统一风格</label>
              <label><input type="radio" name="mode" value="blind_benchmark"> 盲测基准</label>
            </div>

            <label for="sourceLocale">源语言</label>
            <input id="sourceLocale" value="en-US" list="localeOptions" autocomplete="off" spellcheck="false">

            <label for="sourceFiles">源文件</label>
            <textarea id="sourceFiles" placeholder="可选。每行一个相对路径。"></textarea>

            <label for="outputRoot">输出目录</label>
            <input id="outputRoot" placeholder="可选。默认写入项目输出目录。">

            <label for="runId">Run ID</label>
            <input id="runId" placeholder="可选">

            <label for="maxSegments">片段上限</label>
            <input id="maxSegments" type="number" min="1" value="80">
          </div>

          <button type="button" class="primary wide" onclick="runAgent('handoff')">生成 zh-CN 本地化</button>
          <div class="secondary-actions">
            <button type="button" onclick="inspectProject()">识别项目</button>
            <button type="button" onclick="runAgent('synthetic')">Synthetic Draft</button>
          </div>
        </div>

        <div class="work-card">
          <h3>运行预览</h3>
          <div class="preview-list">
            <div class="preview-row"><div class="key">将处理</div><div class="value"><span id="metricFiles">0</span> 个源文件</div></div>
            <div class="preview-row"><div class="key">片段数</div><div class="value"><span id="metricSegments">0</span></div></div>
            <div class="preview-row"><div class="key">将生成</div><div class="value" id="plannedOutput">等待识别项目</div></div>
            <div class="preview-row"><div class="key">运行模式</div><div class="value" id="previewMode">新建本地化</div></div>
            <div class="preview-row"><div class="key">输出模式</div><div class="value">暂存交付包</div></div>
            <div class="preview-row"><div class="key">质量检查</div><div class="value">结构、占位符、标记</div></div>
            <div class="preview-row"><div class="key">源项目修改</div><div class="value">不会覆盖任何源文件</div></div>
            <div class="preview-row"><div class="key">输出数</div><div class="value"><span id="metricOutputs">0</span></div></div>
          </div>
          <div class="info-note">将生成新的语言资源包，你的源项目保持不变。</div>

          <label for="responsesDir">Responses Directory</label>
          <input id="responsesDir" placeholder="包含 batch response 文件的路径">
          <div class="secondary-actions">
            <button type="button" onclick="runAgent('responses')">导入响应</button>
            <button type="button" onclick="setTab('review')">进入审查</button>
          </div>
        </div>
      </section>

      <div id="status" class="status notice-bar" aria-live="polite">Ready.</div>

      <section class="delivery-grid" id="reviewPanel">
        <div class="detail-stack">
          <div class="band work-band">
            <h2>资源清单</h2>
            <div class="band-body" id="routing">尚未识别项目。</div>
          </div>
          <div class="band work-band">
            <h2>交付结果</h2>
            <div class="band-body" id="agentResult">尚未运行。</div>
          </div>
        </div>
        <div class="detail-stack">
          <div class="band work-band">
            <h2>交付物</h2>
            <div class="band-body" id="artifacts">暂无交付物。</div>
          </div>
          <div class="band work-band">
            <h2>预览</h2>
            <pre id="preview">选择一个交付物进行预览。</pre>
          </div>
        </div>
      </section>

      <section class="sessions-panel" id="sessionsPanel">
        <div class="band work-band">
          <h2>会话</h2>
          <div class="band-body" id="sessions">选择项目后查看历史运行。</div>
        </div>
      </section>
    </main>
  </div>
  <script>
    const $ = (id) => document.getElementById(id);
    const MODE_CONFIG = {
      greenfield_localization: {
        label: "新建本地化",
        reference_policy: "style_only",
        workflow_depth: "ask",
        preflight_mode: "auto"
      },
      existing_locale_maintenance: {
        label: "维护现有语言",
        reference_policy: "preserve_existing",
        workflow_depth: "standard",
        preflight_mode: "auto"
      },
      rewrite_or_harmonization: {
        label: "重写 / 统一风格",
        reference_policy: "tm_assisted",
        workflow_depth: "standard",
        preflight_mode: "auto"
      },
      blind_benchmark: {
        label: "盲测基准",
        reference_policy: "blind",
        workflow_depth: "high_assurance",
        preflight_mode: "full"
      }
    };
    let busy = false;

    function setTab(tab) {
      document.querySelectorAll(".tab").forEach((button) => {
        button.classList.toggle("active", button.dataset.tab === tab);
      });
      const target = {
        generate: "generateTop",
        review: "reviewPanel",
        sessions: "sessionsPanel",
        settings: "settingsPanel"
      }[tab];
      if (target && $(target)) {
        $(target).scrollIntoView({behavior: "smooth", block: "start"});
      }
      if (tab === "sessions") {
        loadSessions();
      }
    }

    async function postJson(path, payload) {
      const response = await fetch(path, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok || data.status === "fail") {
        throw new Error(data.error || "Request failed");
      }
      return data;
    }

    function payloadBase() {
      const mode = selectedModeConfig();
      return {
        project: $("project").value.trim(),
        source_locale: $("sourceLocale").value.trim() || "en-US",
        target_locale: $("targetLocale").value.trim(),
        source_files: $("sourceFiles").value,
        output_root: $("outputRoot").value.trim(),
        run_id: $("runId").value.trim(),
        max_segments: Number($("maxSegments").value || 80),
        operating_mode: mode.operating_mode,
        reference_policy: mode.reference_policy,
        workflow_depth: mode.workflow_depth,
        preflight_mode: mode.preflight_mode,
        privacy_mode: "standard",
        data_classification: "internal",
        status: "draft_package"
      };
    }

    function selectedModeConfig() {
      const selected = document.querySelector("input[name='mode']:checked");
      const key = selected ? selected.value : "greenfield_localization";
      return {operating_mode: key, ...(MODE_CONFIG[key] || MODE_CONFIG.greenfield_localization)};
    }

    function updateContext(routing) {
      const mode = selectedModeConfig();
      const projectPath = $("project").value.trim();
      const normalized = projectPath.replace(/\\/g, "/").replace(/\/$/, "");
      $("contextProject").textContent = normalized ? normalized.split("/").pop() : "未选择项目";
      $("contextLocale").textContent = `${$("sourceLocale").value.trim() || "en-US"} -> ${$("targetLocale").value.trim() || "zh-CN"}`;
      $("contextScope").textContent = "检查范围：" + ({auto: "自动", full: "完整"}[mode.preflight_mode] || mode.preflight_mode);
      $("previewMode").textContent = mode.label;
      if (routing) {
        const counts = routing.adapter_counts || {};
        const adapter = Object.keys(counts).sort()[0] || "源码项目";
        const files = routing.selected_source_files ? routing.selected_source_files.length : routing.supported_file_count || 0;
        $("contextType").textContent = adapter;
        $("contextSegments").textContent = `${files} 文件`;
        $("plannedOutput").textContent = routing.selected_source_files && routing.selected_source_files.length
          ? "选定源文件"
          : "按资源清单生成";
      }
    }

    function fileToBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || "").split(",", 2)[1] || "");
        reader.onerror = () => reject(reader.error || new Error("Could not read file"));
        reader.readAsDataURL(file);
      });
    }

    async function importSelectedFiles(fileList) {
      return importFileItems(Array.from(fileList || []).map((file) => ({
        file,
        relative_path: file.webkitRelativePath || file.name
      })));
    }

    async function importFileItems(items) {
      if (!items.length) return;
      await runBusy(async () => {
        const payloadFiles = [];
        for (const item of items) {
          payloadFiles.push({
            relative_path: item.relative_path,
            content_base64: await fileToBase64(item.file)
          });
        }
        const data = await postJson("/api/import-files", {files: payloadFiles});
        $("project").value = data.project;
        $("sourceFiles").value = (data.source_files || []).join("\n");
        renderRouting(data.routing);
        updateContext(data.routing);
        setStatus(`已导入 ${payloadFiles.length} 个文件。`, "pass");
      });
    }

    function requireProject() {
      if (!$("project").value.trim()) {
        $("project").focus();
        throw new Error("请先选择项目路径。");
      }
    }

    function requireTargetLocale() {
      if (!$("targetLocale").value.trim()) {
        $("targetLocale").focus();
        throw new Error("目标语言是必填项。");
      }
    }

    function focusProject() {
      setTab("settings");
      $("project").focus();
    }

    async function pickProjectDirectory() {
      await runBusy(async () => {
        const data = await postJson("/api/pick-directory", {});
        if (data.status === "cancelled") {
          setStatus("未选择项目。", "");
          return;
        }
        $("project").value = data.project;
        $("sourceFiles").value = (data.source_files || []).join("\n");
        renderRouting(data.routing);
        updateContext(data.routing);
        setStatus("已打开本地项目，目录内容未上传。", "pass");
      });
    }

    function setBusy(value) {
      busy = value;
      document.querySelectorAll("button").forEach((button) => button.disabled = value);
      document.querySelectorAll("input[type='file']").forEach((input) => input.disabled = value);
      document.body.classList.toggle("is-busy", value);
      document.body.setAttribute("aria-busy", String(value));
    }

    function setStatus(text, kind) {
      $("status").textContent = text;
      $("status").className = "status " + (kind || "");
    }

    async function inspectProject() {
      await runBusy(async () => {
        requireProject();
        const data = await postJson("/api/inspect", {project: $("project").value.trim()});
        renderRouting(data.routing);
        setStatus("项目识别完成。", "pass");
        updateContext(data.routing);
      });
    }

    async function loadSessions() {
      await runBusy(async () => {
        requireProject();
        const data = await postJson("/api/sessions", {project: $("project").value.trim()});
        renderSessions(data.session_index);
        setStatus("会话已加载。", "pass");
      });
    }

    async function runAgent(mode) {
      await runBusy(async () => {
        const payload = payloadBase();
        requireProject();
        requireTargetLocale();
        if (mode === "synthetic") payload.synthetic_draft = true;
        if (mode === "responses") {
          payload.responses_dir = $("responsesDir").value.trim();
          if (!payload.responses_dir) {
            $("responsesDir").focus();
            throw new Error("Responses Directory 是导入响应的必填项。");
          }
        }
        const data = await postJson("/api/agent-run", payload);
        const result = data.agent_result;
        renderAgent(result);
        renderRouting(result.routing);
        renderArtifacts(result.artifacts || {});
        updateContext(result.routing);
        setStatus("运行状态：" + result.status, result.status.includes("failed") ? "fail" : "pass");
        setTab("review");
      });
    }

    async function runBusy(fn) {
      if (busy) return;
      setBusy(true);
      setStatus("处理中。", "");
      try {
        await fn();
      } catch (error) {
        setStatus(error.message, "fail");
      } finally {
        setBusy(false);
      }
    }

    function renderRouting(routing) {
      if (!routing) {
        $("routing").textContent = "暂无资源清单。";
        return;
      }
      $("metricFiles").textContent = routing.selected_source_files ? routing.selected_source_files.length : routing.supported_file_count || 0;
      const counts = routing.adapter_counts || {};
      const pills = Object.keys(counts).sort().map((key) => `<span class="pill">${escapeHtml(key)}: ${counts[key]}</span>`).join("");
      const files = routing.supported_files || [];
      const selected = routing.selected_source_files || [];
      const rows = (selected.length ? selected.map((path) => ({path, adapter: "selected"})) : files.slice(0, 40))
        .map((item) => `<tr><td>${escapeHtml(item.path || item)}</td><td>${escapeHtml(item.adapter || "")}</td></tr>`)
        .join("");
      $("routing").innerHTML = `
        <div>${pills || "<span class='pill'>未识别适配器</span>"}</div>
        <p class="path">${escapeHtml(routing.reason || "")}</p>
        <div class="table-wrap"><table><thead><tr><th>路径</th><th>适配器</th></tr></thead><tbody>${rows}</tbody></table></div>
      `;
    }

    function renderAgent(result) {
      const summary = result.summary || {};
      $("metricSegments").textContent = summary.segment_count || 0;
      $("metricOutputs").textContent = summary.output_count || 0;
      const reflection = result.reflection || {};
      $("agentResult").innerHTML = `
        <div class="table-wrap"><table>
          <tbody>
            <tr><th>Status</th><td>${escapeHtml(result.status || "")}</td></tr>
            <tr><th>Run ID</th><td>${escapeHtml(result.run_id || "")}</td></tr>
            <tr><th>Generation</th><td>${escapeHtml(reflection.generation_status || "pending")}</td></tr>
            <tr><th>QA</th><td>${escapeHtml(reflection.qa_status || "not_checked")}</td></tr>
            <tr><th>Blocking</th><td>${reflection.blocking_count || 0}</td></tr>
            <tr><th>Warnings</th><td>${reflection.warning_count || 0}</td></tr>
          </tbody>
        </table></div>
      `;
    }

    function renderSessions(index) {
      const sessions = Array.isArray(index && index.sessions) ? index.sessions.slice().reverse() : [];
      if (!sessions.length) {
        $("sessions").textContent = "暂无会话。";
        return;
      }
      const rows = sessions.slice(0, 20).map((item) => `
        <tr>
          <td>${escapeHtml(item.run_id || item.session_id || "")}</td>
          <td>${escapeHtml(item.status || "")}</td>
          <td>${escapeHtml(item.target_locale || "")}</td>
          <td>${escapeHtml(item.operating_mode || "")}</td>
          <td>${escapeHtml(item.run_directory || "")}</td>
        </tr>
      `).join("");
      $("sessions").innerHTML = `
        <p class="path">Latest: ${escapeHtml(index.latest_session_id || "none")}</p>
        <div class="table-wrap"><table>
          <thead><tr><th>Run ID</th><th>Status</th><th>Target</th><th>Mode</th><th>Directory</th></tr></thead>
          <tbody>${rows}</tbody>
        </table></div>
      `;
    }

    function renderArtifacts(artifacts) {
      const preferred = [
        "generation_readme",
        "prompt_manifest",
        "agent_summary",
        "review_sheet_markdown",
        "review_sheet_csv",
        "delivery_decision_markdown",
        "delivery_dashboard_markdown",
        "apply_plan_markdown",
        "generation_collect",
        "staging_result"
      ];
      const keys = preferred.filter((key) => artifacts[key]).concat(Object.keys(artifacts).filter((key) => !preferred.includes(key)).sort());
      if (!keys.length) {
        $("artifacts").textContent = "暂无交付物。";
        return;
      }
      $("artifacts").innerHTML = keys.map((key) => `
        <div class="artifact-row">
          <div><strong>${escapeHtml(key)}</strong><div class="path">${escapeHtml(artifacts[key])}</div></div>
          <button onclick="previewArtifact('${escapeJs(artifacts[key])}')">预览</button>
        </div>
      `).join("");
    }

    async function previewArtifact(path) {
      await runBusy(async () => {
        const data = await postJson("/api/read-artifact", {path});
        $("preview").textContent = data.content + (data.truncated ? "\n\n[truncated]" : "");
        setStatus("预览已载入。", "pass");
      });
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      })[char]);
    }

    function escapeJs(value) {
      return String(value ?? "").replace(/\\/g, "\\\\").replace(/'/g, "\\'");
    }

    fetch("/api/health")
      .then((response) => response.json())
      .then((data) => $("health").textContent = data.status + " / " + data.version)
      .catch(() => $("health").textContent = "offline");

    ["project", "sourceLocale", "targetLocale"].forEach((id) => {
      $(id).addEventListener("input", () => updateContext());
    });
    document.querySelectorAll("input[name='mode']").forEach((input) => {
      input.addEventListener("change", () => updateContext());
    });
    updateContext();

    $("filePicker").addEventListener("change", (event) => importSelectedFiles(event.target.files));
    $("dropzone").addEventListener("click", () => {
      if (!busy) pickProjectDirectory();
    });
    $("dropzone").addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        if (!busy) pickProjectDirectory();
      }
    });
    $("dropzone").addEventListener("dragover", (event) => {
      event.preventDefault();
      $("dropzone").classList.add("dragging");
    });
    $("dropzone").addEventListener("dragleave", () => $("dropzone").classList.remove("dragging"));
    $("dropzone").addEventListener("drop", async (event) => {
      event.preventDefault();
      $("dropzone").classList.remove("dragging");
      const entries = Array.from(event.dataTransfer.items || []).map((item) => item.webkitGetAsEntry && item.webkitGetAsEntry());
      if (entries.some((entry) => entry && entry.isDirectory)) {
        setStatus("文件夹请使用“选择本地目录”，服务会直接读取路径。", "");
        return;
      }
      importSelectedFiles(event.dataTransfer.files);
    });
  </script>
</body>
</html>
"""
