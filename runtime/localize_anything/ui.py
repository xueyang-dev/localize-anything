from __future__ import annotations

import base64
import binascii
import json
import uuid
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from tempfile import gettempdir
from typing import Any
from urllib.parse import urlparse

from . import __version__
from .agent import run_agent
from .project import inspect_project, load_session_index


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
            if parsed.path == "/":
                self._send_text(WORKBENCH_HTML, "text/html; charset=utf-8")
                return
            if parsed.path == "/api/health":
                self._send_json({"status": "pass", "app": "localize-anything-workbench", "version": __version__})
                return
            self._send_json({"status": "fail", "error": "Not found"}, HTTPStatus.NOT_FOUND)

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
                if parsed.path == "/api/agent-run":
                    self._handle_agent_run(payload)
                    return
                if parsed.path == "/api/read-artifact":
                    self._handle_read_artifact(payload)
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
                if item.get("adapter") == "core.word-document"
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
  <style>
    :root {
      --bg: #f6f7f8;
      --panel: #ffffff;
      --line: #d8dee4;
      --text: #1f2328;
      --muted: #667085;
      --accent: #0b6bcb;
      --accent-2: #16794c;
      --warn: #9a6700;
      --bad: #b42318;
      --code: #101828;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--text);
      letter-spacing: 0;
    }
    header {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 18px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1 { font-size: 18px; margin: 0; font-weight: 700; }
    main {
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      min-height: calc(100vh - 56px);
    }
    aside {
      border-right: 1px solid var(--line);
      background: var(--panel);
      padding: 16px;
      overflow: auto;
    }
    section {
      padding: 16px 20px;
      overflow: auto;
    }
    label {
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin: 12px 0 6px;
    }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      font: inherit;
      font-size: 13px;
      padding: 8px 9px;
    }
    textarea {
      min-height: 76px;
      resize: vertical;
      font-family: Consolas, "Courier New", monospace;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .buttons {
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
      margin-top: 16px;
    }
    .file-actions {
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
    }
    .dropzone {
      border: 1px dashed #9aa8b5;
      border-radius: 8px;
      background: #fbfbfc;
      color: var(--muted);
      padding: 12px;
      min-height: 62px;
      display: flex;
      align-items: center;
      font-size: 13px;
    }
    .dropzone.dragging {
      border-color: var(--accent);
      color: var(--accent);
      background: #eef6ff;
    }
    button {
      border: 1px solid #a9b7c6;
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      min-height: 36px;
      font: inherit;
      font-size: 13px;
      cursor: pointer;
    }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 700;
    }
    button:disabled {
      opacity: 0.55;
      cursor: wait;
    }
    .status {
      min-height: 40px;
      border: 1px solid var(--line);
      border-left: 4px solid var(--accent);
      background: #fff;
      padding: 10px 12px;
      margin-bottom: 14px;
      font-size: 13px;
    }
    .status.fail { border-left-color: var(--bad); }
    .status.pass { border-left-color: var(--accent-2); }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }
    .metric {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 12px;
      min-height: 76px;
    }
    .metric .value { font-size: 22px; font-weight: 700; margin-bottom: 5px; }
    .metric .label { color: var(--muted); font-size: 12px; }
    .band {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      margin-bottom: 14px;
      overflow: hidden;
    }
    .band h2 {
      font-size: 14px;
      margin: 0;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      background: #fbfbfc;
    }
    .band-body { padding: 12px; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 7px 8px;
      text-align: left;
      vertical-align: top;
      word-break: break-word;
    }
    th { color: var(--muted); font-weight: 700; background: #fbfbfc; }
    code, pre {
      font-family: Consolas, "Courier New", monospace;
      letter-spacing: 0;
    }
    pre {
      margin: 0;
      padding: 12px;
      overflow: auto;
      max-height: 48vh;
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
      grid-template-columns: minmax(0, 1fr) 92px;
      gap: 8px;
      align-items: center;
      border-bottom: 1px solid var(--line);
      padding: 8px 0;
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
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Localize Anything Workbench</h1>
    <div class="path" id="health">checking</div>
  </header>
  <main>
    <aside>
      <label for="project">Project Path</label>
      <input id="project" placeholder="C:\path\to\project">
      <label>Import Word Files</label>
      <div class="dropzone" id="dropzone">Drop Word files or a folder here.</div>
      <div class="file-actions">
        <input id="filePicker" type="file" multiple accept=".docx,.dotx,.docm,.dotm,.doc">
        <input id="folderPicker" type="file" multiple webkitdirectory directory>
      </div>
      <div class="row">
        <div>
          <label for="sourceLocale">Source Locale</label>
          <input id="sourceLocale" value="en-US">
        </div>
        <div>
          <label for="targetLocale">Target Locale</label>
          <input id="targetLocale" value="zh-CN">
        </div>
      </div>
      <label for="sourceFiles">Source Files</label>
      <textarea id="sourceFiles" placeholder="Optional. One relative path per line."></textarea>
      <label for="outputRoot">Output Root</label>
      <input id="outputRoot" placeholder="Optional. Defaults inside project.">
      <div class="row">
        <div>
          <label for="runId">Run ID</label>
          <input id="runId" placeholder="Optional">
        </div>
        <div>
          <label for="maxSegments">Max Segments</label>
          <input id="maxSegments" type="number" min="1" value="80">
        </div>
      </div>
      <label for="responsesDir">Responses Directory</label>
      <input id="responsesDir" placeholder="Path containing batch response files">
      <div class="buttons">
        <button onclick="inspectProject()">Inspect</button>
        <button class="primary" onclick="runAgent('handoff')">Create Handoff</button>
        <button onclick="runAgent('responses')">Import Responses</button>
        <button onclick="runAgent('synthetic')">Synthetic Draft</button>
      </div>
    </aside>
    <section>
      <div id="status" class="status">Ready.</div>
      <div class="grid">
        <div class="metric"><div class="value" id="metricFiles">0</div><div class="label">Source files</div></div>
        <div class="metric"><div class="value" id="metricSegments">0</div><div class="label">Segments</div></div>
        <div class="metric"><div class="value" id="metricOutputs">0</div><div class="label">Outputs</div></div>
      </div>
      <div class="band">
        <h2>Routing</h2>
        <div class="band-body" id="routing">No project inspected.</div>
      </div>
      <div class="band">
        <h2>Agent Result</h2>
        <div class="band-body" id="agentResult">No run yet.</div>
      </div>
      <div class="band">
        <h2>Artifacts</h2>
        <div class="band-body" id="artifacts">No artifacts yet.</div>
      </div>
      <div class="band">
        <h2>Preview</h2>
        <pre id="preview">Select an artifact to preview.</pre>
      </div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    let busy = false;

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
      return {
        project: $("project").value.trim(),
        source_locale: $("sourceLocale").value.trim() || "en-US",
        target_locale: $("targetLocale").value.trim(),
        source_files: $("sourceFiles").value,
        output_root: $("outputRoot").value.trim(),
        run_id: $("runId").value.trim(),
        max_segments: Number($("maxSegments").value || 80)
      };
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
        setStatus(`Imported ${payloadFiles.length} file(s).`, "pass");
      });
    }

    async function droppedFileItems(dataTransfer) {
      const transferItems = Array.from(dataTransfer.items || []);
      if (!transferItems.length || !transferItems[0].webkitGetAsEntry) {
        return Array.from(dataTransfer.files || []).map((file) => ({file, relative_path: file.name}));
      }
      const collected = [];
      for (const item of transferItems) {
        const entry = item.webkitGetAsEntry();
        if (entry) collected.push(...await traverseEntry(entry, ""));
      }
      return collected;
    }

    async function traverseEntry(entry, prefix) {
      if (entry.isFile) {
        return await new Promise((resolve, reject) => {
          entry.file(
            (file) => resolve([{file, relative_path: prefix + file.name}]),
            reject
          );
        });
      }
      if (!entry.isDirectory) return [];
      const reader = entry.createReader();
      const result = [];
      while (true) {
        const entries = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
        if (!entries.length) break;
        for (const child of entries) {
          result.push(...await traverseEntry(child, prefix + entry.name + "/"));
        }
      }
      return result;
    }

    function setBusy(value) {
      busy = value;
      document.querySelectorAll("button").forEach((button) => button.disabled = value);
    }

    function setStatus(text, kind) {
      $("status").textContent = text;
      $("status").className = "status " + (kind || "");
    }

    async function inspectProject() {
      await runBusy(async () => {
        const data = await postJson("/api/inspect", {project: $("project").value.trim()});
        renderRouting(data.routing);
        setStatus("Inspection complete.", "pass");
      });
    }

    async function runAgent(mode) {
      await runBusy(async () => {
        const payload = payloadBase();
        if (mode === "synthetic") payload.synthetic_draft = true;
        if (mode === "responses") payload.responses_dir = $("responsesDir").value.trim();
        const data = await postJson("/api/agent-run", payload);
        const result = data.agent_result;
        renderAgent(result);
        renderRouting(result.routing);
        renderArtifacts(result.artifacts || {});
        setStatus("Agent status: " + result.status, result.status.includes("failed") ? "fail" : "pass");
      });
    }

    async function runBusy(fn) {
      if (busy) return;
      setBusy(true);
      setStatus("Working.", "");
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
        $("routing").textContent = "No routing data.";
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
        <div>${pills || "<span class='pill'>no adapters</span>"}</div>
        <p class="path">${escapeHtml(routing.reason || "")}</p>
        <table><thead><tr><th>Path</th><th>Adapter</th></tr></thead><tbody>${rows}</tbody></table>
      `;
    }

    function renderAgent(result) {
      const summary = result.summary || {};
      $("metricSegments").textContent = summary.segment_count || 0;
      $("metricOutputs").textContent = summary.output_count || 0;
      const reflection = result.reflection || {};
      $("agentResult").innerHTML = `
        <table>
          <tbody>
            <tr><th>Status</th><td>${escapeHtml(result.status || "")}</td></tr>
            <tr><th>Run ID</th><td>${escapeHtml(result.run_id || "")}</td></tr>
            <tr><th>Generation</th><td>${escapeHtml(reflection.generation_status || "pending")}</td></tr>
            <tr><th>QA</th><td>${escapeHtml(reflection.qa_status || "not_checked")}</td></tr>
            <tr><th>Blocking</th><td>${reflection.blocking_count || 0}</td></tr>
            <tr><th>Warnings</th><td>${reflection.warning_count || 0}</td></tr>
          </tbody>
        </table>
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
        $("artifacts").textContent = "No artifacts yet.";
        return;
      }
      $("artifacts").innerHTML = keys.map((key) => `
        <div class="artifact-row">
          <div><strong>${escapeHtml(key)}</strong><div class="path">${escapeHtml(artifacts[key])}</div></div>
          <button onclick="previewArtifact('${escapeJs(artifacts[key])}')">Preview</button>
        </div>
      `).join("");
    }

    async function previewArtifact(path) {
      await runBusy(async () => {
        const data = await postJson("/api/read-artifact", {path});
        $("preview").textContent = data.content + (data.truncated ? "\n\n[truncated]" : "");
        setStatus("Preview loaded.", "pass");
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

    $("filePicker").addEventListener("change", (event) => importSelectedFiles(event.target.files));
    $("folderPicker").addEventListener("change", (event) => importSelectedFiles(event.target.files));
    $("dropzone").addEventListener("dragover", (event) => {
      event.preventDefault();
      $("dropzone").classList.add("dragging");
    });
    $("dropzone").addEventListener("dragleave", () => $("dropzone").classList.remove("dragging"));
    $("dropzone").addEventListener("drop", async (event) => {
      event.preventDefault();
      $("dropzone").classList.remove("dragging");
      importFileItems(await droppedFileItems(event.dataTransfer));
    });
  </script>
</body>
</html>
"""
