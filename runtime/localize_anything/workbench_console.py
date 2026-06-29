from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl
from .workbench_action import read_workbench_action_log, read_workbench_action_result


EVIDENCE_LEVEL_REPORT_MD = "evidence-level-report.md"


CONSOLE_ENDPOINTS = [
    ("Evaluation Scorecard", "/api/evaluation-scorecard", "evaluation_scorecard"),
    ("Evidence Level Report", "/api/evidence-level-report", "evidence_level_report"),
    ("Workbench Review Queue", "/api/workbench-review-queue", "workbench_review_queue"),
    ("Workbench Claim Queue", "/api/workbench-claim-queue", "workbench_claim_queue"),
    ("Workbench Signoff Summary", "/api/workbench-signoff-summary", "workbench_signoff_summary"),
    ("Human Review Evidence", "/api/human-review-evidence", "human_review_evidence"),
    ("Claim Acceptance Decision", "/api/claim-acceptance-decision", "claim_acceptance_decision"),
    ("Signoff Record", "/api/signoff-record", "signoff_record"),
    ("Artifact State", "/api/artifact-state", "artifact_state"),
    ("Repair Request", "/api/repair-request", "repair_request"),
    ("Repair Result", "/api/repair-result", "repair_result"),
    ("Generation Handoff", "/api/generation-handoff-status", "generation_handoff_status"),
    ("Action Log", "/api/workbench-action-log", "workbench_action_log"),
    ("Action Result", "/api/workbench-action-result", "workbench_action_result"),
]


def read_evidence_level_report(state_dir: Path) -> str:
    path = state_dir / EVIDENCE_LEVEL_REPORT_MD
    if not path.is_file():
        raise ValueError(f"Missing evidence level report: {path}")
    return path.read_text(encoding="utf-8")


def build_workbench_console_view(state_dir: Path) -> dict[str, Any]:
    state_dir = state_dir.resolve()
    sections = {
        "evaluation_scorecard": _optional_json(state_dir / "evaluation-scorecard.json"),
        "evidence_level_report": _optional_text(state_dir / EVIDENCE_LEVEL_REPORT_MD),
        "workbench_review_queue": _optional_json(state_dir / "workbench-review-queue.json"),
        "workbench_claim_queue": _optional_json(state_dir / "workbench-claim-queue.json"),
        "workbench_signoff_summary": _optional_json(state_dir / "workbench-signoff-summary.json"),
        "human_review_evidence": _optional_jsonl(state_dir / "human-review-evidence.jsonl"),
        "claim_acceptance_decision": _optional_json(state_dir / "claim-acceptance-decision.json"),
        "signoff_record": _optional_json(state_dir / "signoff-record.json"),
        "artifact_state": _optional_json(state_dir / "artifact-state.json"),
        "repair_request": _optional_json(state_dir / "repair-request.json"),
        "repair_result": _optional_json(state_dir / "repair-result.json"),
        "generation_handoff_status": _optional_json(state_dir / "generation-handoff-decision.json"),
        "workbench_action_log": _optional_action_log(state_dir),
        "workbench_action_result": _optional_action_result(state_dir),
    }
    scorecard = _data(sections["evaluation_scorecard"])
    claim_queue = _data(sections["workbench_claim_queue"])
    review_queue = _data(sections["workbench_review_queue"])
    signoff = _data(sections["workbench_signoff_summary"])
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-console-view-v1",
        "state_dir": state_dir.as_posix(),
        "run_status": {
            "overall_claim": _get(scorecard, "overall_claim"),
            "scorecard_status": _get(scorecard, "status"),
            "review_queue_status": _get(review_queue, "status"),
            "claim_queue_status": _get(claim_queue, "status"),
            "signoff_status": _get(signoff, "current_signoff_status"),
            "source_artifacts": _present_artifacts(sections),
        },
        "forbidden_claims": _forbidden_claims(scorecard, claim_queue),
        "pending_repairs": _pending_repairs(_data(sections["repair_request"]), _data(sections["repair_result"])),
        "stale_artifact_warnings": _stale_artifacts(_data(sections["artifact_state"])),
        "sections": sections,
        "endpoints": [
            {"label": label, "path": path, "key": key}
            for label, path, key in CONSOLE_ENDPOINTS
        ],
    }


def render_workbench_console_html(state_dir: Path | None = None) -> str:
    view = build_workbench_console_view(state_dir) if state_dir is not None else _empty_view()
    state_dir_value = view.get("state_dir", "")
    initial_json = json.dumps(view, ensure_ascii=False, indent=2)
    sections = [
        _section("Run Status", "run-status", view["run_status"]),
        _section("Evaluation Scorecard", "evaluation-scorecard", _data(view["sections"]["evaluation_scorecard"])),
        _section("Evidence Level Report", "evidence-level-report", _data(view["sections"]["evidence_level_report"])),
        _section("Workbench Review Queue", "workbench-review-queue", _data(view["sections"]["workbench_review_queue"])),
        _section("Workbench Claim Queue", "workbench-claim-queue", _data(view["sections"]["workbench_claim_queue"])),
        _section("Workbench Signoff Summary", "workbench-signoff-summary", _data(view["sections"]["workbench_signoff_summary"])),
        _section("Forbidden Claims", "forbidden-claims", view["forbidden_claims"]),
        _section("Pending Repairs", "pending-repairs", view["pending_repairs"]),
        _section("Stale Artifact Warnings", "stale-artifact-warnings", view["stale_artifact_warnings"]),
        _section("Generation Handoff", "generation-handoff-status", _data(view["sections"]["generation_handoff_status"])),
        _section("Action Log", "workbench-action-log", _data(view["sections"]["workbench_action_log"])),
        _section("Action Result", "workbench-action-result", _data(view["sections"]["workbench_action_result"])),
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Localize Anything Workbench Review Console</title>
  <style>
    :root {{
      color-scheme: light dark;
      --surface: #ffffff;
      --surface-subtle: #f6f8fa;
      --text: #17202a;
      --muted: #59636e;
      --line: #d0d7de;
      --accent: #0969da;
      --danger: #b42318;
      --warning: #9a6700;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --surface: #0d1117;
        --surface-subtle: #161b22;
        --text: #e6edf3;
        --muted: #9da7b3;
        --line: #30363d;
        --accent: #58a6ff;
        --danger: #ff7b72;
        --warning: #d29922;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--surface);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 16px;
      line-height: 1.5;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      padding: 24px;
    }}
    main {{
      display: grid;
      gap: 16px;
      grid-template-columns: minmax(0, 1fr);
      padding: 16px;
    }}
    @media (min-width: 980px) {{
      main {{ grid-template-columns: minmax(0, 1fr) minmax(340px, 420px); }}
      .primary {{ grid-column: 1; }}
      .side {{ grid-column: 2; grid-row: 1 / span 8; align-self: start; position: sticky; top: 12px; }}
    }}
    h1 {{ font-size: 28px; margin: 0 0 8px; }}
    h2 {{ font-size: 18px; margin: 0 0 12px; }}
    p {{ margin: 0; color: var(--muted); }}
    section {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: var(--surface);
    }}
    pre, textarea, input {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface-subtle);
      color: var(--text);
      font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }}
    pre {{
      min-height: 44px;
      max-height: 360px;
      margin: 0;
      overflow: auto;
      padding: 12px;
      white-space: pre-wrap;
    }}
    textarea {{ min-height: 180px; padding: 12px; resize: vertical; }}
    input {{ min-height: 44px; padding: 8px 10px; }}
    label {{ display: block; font-weight: 600; margin: 12px 0 6px; }}
    button {{
      min-height: 44px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      cursor: pointer;
      font-weight: 600;
      padding: 8px 14px;
    }}
    button:focus-visible, textarea:focus-visible, input:focus-visible {{
      outline: 3px solid color-mix(in srgb, var(--accent) 35%, transparent);
      outline-offset: 2px;
    }}
    .badge-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
    .badge {{
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      padding: 4px 10px;
    }}
    .danger {{ color: var(--danger); font-weight: 700; }}
    .warning {{ color: var(--warning); font-weight: 700; }}
    .actions {{ display: grid; gap: 12px; }}
  </style>
</head>
<body>
  <header>
    <h1>Workbench Review Console</h1>
    <p>Artifact-backed review state and action submission. Runtime gates remain the source of truth.</p>
    <div class="badge-row" aria-label="Console safeguards">
      <span class="badge">No UI-local readiness logic</span>
      <span class="badge">Forbidden claims stay visible</span>
      <span class="badge">Actions POST to /api/workbench-action</span>
    </div>
  </header>
  <main>
    <div class="primary">
      {''.join(sections[:9])}
    </div>
    <aside class="side">
      <section aria-labelledby="action-submission-heading">
        <h2 id="action-submission-heading">Action Submission</h2>
        <form class="actions" onsubmit="submitWorkbenchAction(event)">
          <label for="stateDirInput">State directory</label>
          <input id="stateDirInput" name="state_dir" value="{html.escape(str(state_dir_value), quote=True)}">
          <label for="actionInput">Action JSON</label>
          <textarea id="actionInput" name="action">{html.escape(_sample_action(), quote=False)}</textarea>
          <button type="submit">Submit Runtime Action</button>
        </form>
        <p id="actionMessage" role="status" aria-live="polite"></p>
      </section>
      {''.join(sections[9:])}
    </aside>
  </main>
  <script type="application/json" id="workbench-console-data">{html.escape(initial_json, quote=False)}</script>
  <script>
    const endpointSpecs = {json.dumps(view["endpoints"], ensure_ascii=False)};

    async function submitWorkbenchAction(event) {{
      event.preventDefault();
      const stateDir = document.getElementById("stateDirInput").value.trim();
      const actionText = document.getElementById("actionInput").value;
      const message = document.getElementById("actionMessage");
      try {{
        const action = JSON.parse(actionText);
        const response = await fetch("/api/workbench-action", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ state_dir: stateDir, action }})
        }});
        const payload = await response.json();
        document.getElementById("workbench-action-result-data").textContent = JSON.stringify(payload, null, 2);
        message.textContent = response.ok ? "Runtime action completed. Refreshing artifact views." : "Runtime action returned an error.";
        await refreshConsoleArtifacts(stateDir);
      }} catch (error) {{
        message.textContent = "Action JSON could not be submitted: " + error.message;
      }}
    }}

    async function refreshConsoleArtifacts(stateDir) {{
      if (!stateDir) return;
      for (const spec of endpointSpecs) {{
        const element = document.getElementById(spec.key.replaceAll("_", "-") + "-data");
        if (!element) continue;
        try {{
          const response = await fetch(spec.path + "?state_dir=" + encodeURIComponent(stateDir));
          const contentType = response.headers.get("content-type") || "";
          const payload = contentType.includes("application/json") ? await response.json() : await response.text();
          element.textContent = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
        }} catch (error) {{
          element.textContent = "Unavailable: " + error.message;
        }}
      }}
    }}
  </script>
</body>
</html>
"""


def _section(title: str, section_id: str, value: Any) -> str:
    state_class = ""
    if title == "Forbidden Claims" and value:
        state_class = " danger"
    if title == "Stale Artifact Warnings" and value:
        state_class = " warning"
    return (
        f'<section aria-labelledby="{section_id}-heading">'
        f'<h2 id="{section_id}-heading" class="{state_class.strip()}">{html.escape(title)}</h2>'
        f'<pre id="{section_id}-data">{html.escape(_format_value(value))}</pre>'
        "</section>"
    )


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "missing", "artifact": path.name}
    return {"status": "present", "artifact": path.name, "data": read_json(path)}


def _optional_jsonl(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "missing", "artifact": path.name}
    return {"status": "present", "artifact": path.name, "data": read_jsonl(path)}


def _optional_text(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "missing", "artifact": path.name}
    return {"status": "present", "artifact": path.name, "data": path.read_text(encoding="utf-8")}


def _optional_action_log(state_dir: Path) -> dict[str, Any]:
    records = read_workbench_action_log(state_dir)
    return {"status": "present" if records else "missing", "artifact": "workbench-action-log.jsonl", "data": records}


def _optional_action_result(state_dir: Path) -> dict[str, Any]:
    path = state_dir / "workbench-action-result.json"
    if not path.is_file():
        return {"status": "missing", "artifact": path.name}
    return {"status": "present", "artifact": path.name, "data": read_workbench_action_result(state_dir)}


def _empty_view() -> dict[str, Any]:
    sections = {
        key: {"status": "missing", "artifact": None}
        for _, _, key in CONSOLE_ENDPOINTS
    }
    return {
        "protocol_version": PROTOCOL_VERSION,
        "schema": "localize-anything-workbench-console-view-v1",
        "state_dir": "",
        "run_status": {"overall_claim": None, "source_artifacts": []},
        "forbidden_claims": [],
        "pending_repairs": [],
        "stale_artifact_warnings": [],
        "sections": sections,
        "endpoints": [
            {"label": label, "path": path, "key": key}
            for label, path, key in CONSOLE_ENDPOINTS
        ],
    }


def _data(section: dict[str, Any]) -> Any:
    return section.get("data") if isinstance(section, dict) and "data" in section else section


def _get(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, dict) else None


def _present_artifacts(sections: dict[str, dict[str, Any]]) -> list[str]:
    return [
        str(section.get("artifact"))
        for section in sections.values()
        if section.get("status") == "present" and section.get("artifact")
    ]


def _forbidden_claims(scorecard: Any, claim_queue: Any) -> list[str]:
    claims: set[str] = set()
    if isinstance(scorecard, dict):
        claims.update(str(item) for item in scorecard.get("forbidden_claims", []))
    if isinstance(claim_queue, dict):
        for item in claim_queue.get("items", []):
            related = item.get("related_forbidden_claim") if isinstance(item, dict) else None
            if related:
                claims.add(str(related))
    return sorted(claims)


def _pending_repairs(repair_request: Any, repair_result: Any) -> dict[str, Any]:
    return {
        "repair_request_summary": repair_request.get("summary") if isinstance(repair_request, dict) else None,
        "repair_result_summary": repair_result.get("summary") if isinstance(repair_result, dict) else None,
        "requests": repair_request.get("requests", []) if isinstance(repair_request, dict) else [],
    }


def _stale_artifacts(artifact_state: Any) -> list[dict[str, Any]]:
    if not isinstance(artifact_state, dict):
        return []
    artifacts = artifact_state.get("artifacts")
    if not isinstance(artifacts, list):
        return []
    return [
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("status") in {"stale", "superseded", "blocked", "requires_human_review"}
    ]


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _sample_action() -> str:
    return json.dumps(
        {
            "action_type": "acknowledge_limitation",
            "actor_role": "project_owner",
            "payload": {"claim": "draft_only"},
        },
        ensure_ascii=False,
        indent=2,
    )
