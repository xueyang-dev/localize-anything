# Workbench UI Contract Audit

This audit treats the Workbench as a projection and action surface over runtime artifacts. The UI does not calculate readiness, authorize delivery, execute Apply, or infer provider capability.

## Route map

| Route | Purpose | Runtime, API, or artifact source | Empty state | Error state | Missing or stale state |
| --- | --- | --- | --- | --- | --- |
| `/` | First-run safety explanation and demo entry; compact project overview after selection | `/api/health`, `/api/sessions`, session summary | Explains the safe demo, non-mutation boundary, review flow, and non-claims | Request errors use the typed error notice; progress/success uses the polite status notice | No project is shown as not selected; no run is shown as no run, never as zero results |
| `/generate` | Select or import a project, inspect resources, and prepare staged artifacts | `/api/pick-directory`, `/api/import-files`, `/api/inspect`, `/api/agent-run` | Project, adapter, file, and scan fields say not selected/not inspected | Validation and API errors use field/page error surfaces; progress/success is separate | Inspection and run output remain unavailable until their runtime actions complete |
| `/review` | Completed-run dashboard for scope, readiness, delivery, risks, Apply plan, activity, artifacts, claims, and provider smoke evidence | `/api/sessions`, exact `GET /api/workbench-run?project=...&run_id=...`, session artifact pointers, `/api/read-artifact` | Offers safe demo or local project selection | Invalid URL project/run fails visibly and clears stale client state; card-level corrupt artifacts stay isolated | Exact `run_id` matching is required; `freshness` and newer project state are visible; missing/stale/error status is preserved and raw preview remains available when structured JSON fails |
| `/sessions` | Select a recorded runtime session | `/api/sessions` and the runtime session index | Requests a project first, or reports no recorded sessions | Shared request error banner | Selection preserves project/run URL state and opens the same review projection |
| `/settings` | Navigation language, local version/health, and local safety behavior | `/api/health`, `localStorage`, current URL behavior | Health is checking/offline until the API responds | Offline is explicit | Runtime evidence remains in its source language; no capability is inferred from Workbench health |

Unknown routes return `404` rather than rendering an ambiguous page.

The Review aggregate is the canonical selected-run projection. Historical snapshots never silently upgrade to the project-current projection. When the selected Run is also the current Run, a missing snapshot card may show same-run `current_project_projection` evidence only after an exact `run_id` match and with its current-project scope labelled in the card. After a runtime action, queue data follows the same identity gate and its scope is labelled in the UI.

## Action map

| Action | Mapping | Class | Confirmation | Disabled or fail-closed condition |
| --- | --- | --- | --- | --- |
| Overview / Generate / Review / Sessions / Settings | History API route switch | Read-only | No | Review content stays empty without a selected run |
| English / Chinese | `localStorage` plus `<html lang>` update | Read-only preference | No | Always available |
| Run safe demo | `POST /api/quickstart-demo` -> existing `run_quickstart_demo` | Safe demo | No; the CTA states the boundary before execution | Busy state prevents duplicate action; failure is shown |
| Open local project | `POST /api/pick-directory`, then `/api/inspect` and `/api/sessions` | Read-only local selection | Native directory picker | Cancel leaves the previous state unchanged |
| Read quickstart | Repository quickstart document | Read-only external link | No | Always available |
| Import files | `POST /api/import-files` | Safe temporary copy | Native file picker | No selected files means no action; imported files are copied to a temporary project |
| Inspect project | `POST /api/inspect` | Read-only | No | Disabled by validation when no project is selected |
| Prepare generation handoff | `POST /api/agent-run` with `handoff_only` behavior | Staged, provider-free runtime action | No destructive confirmation required | Requires project and target locale; does not claim generated translations |
| Stage synthetic draft (demo) | `POST /api/agent-run` with `synthetic_draft` | Clearly labeled safe demo | No | Requires project and target locale |
| Import generated responses | `POST /api/agent-run` with responses directory | Staged runtime import | No destructive confirmation required | Requires project, target locale, and responses directory |
| Dashboard card / Preview artifact | Session artifact pointer or projection path -> `POST /api/read-artifact`, then the artifact inspector | Read-only | No | Missing/stale/error state is visible; invalid JSON keeps a raw preview action and does not become an empty success |
| Select session | Session index selection plus History API navigation | Read-only | No | Requires an indexed run |
| Open review | Client route to selected run | Read-only | No | Disabled when there is no current run |
| New run | Client route to `/generate` | Read-only navigation | No | Always available after project selection |
| Directory-path artifact row | Runtime path only | Disabled | Not applicable | Always disabled because it is not a readable artifact |
| Apply plan | Artifact preview only; no Apply endpoint is exposed | Apply-related, read-only | Not applicable | Apply execution is absent; blocked/missing/stale state remains visible |

No decorative button remains. There is no Workbench action that mutates target project files or authorizes Apply.

## Copy boundary audit

The UI now says what the runtime action actually does:

- The primary generation action is **Prepare generation handoff**, not translation generation.
- Synthetic output is labeled demo-only.
- `ready_with_warnings` is rendered as **Review package ready with warnings**, not delivery or production authorization.
- Apply is described as a dry-run plan that still requires explicit authorization.
- Provider smoke is limited to `provider_path_smoke_only`, its exact public fixture and segment count, and the manifest's runtime-call field.
- Missing provider artifacts keep provider execution, quality, reliability, and production claims unsupported.

The UI does not claim one-click translation, provider-backed quality, production readiness, locale completeness, full-product coverage, benchmark reliability, runtime-managed real-provider execution, or automatic Apply.

## Artifact mapping audit

| Surface | Source of truth | Missing, stale, or demo behavior |
| --- | --- | --- |
| Project/source status | `/api/inspect` routing projection | Says not selected/not inspected; never shows a zero-result run before inspection |
| Locale status | Session locales or current form fields | Says not selected without a project |
| File and segment counts | Session `summary` and inspection routing | Missing values are unavailable, not zero |
| QA status | Session `summary.qa_status` | Not checked remains explicit |
| Readiness status | `readiness-authorization-matrix.json`, delivery/apply readiness reports | Exact run match required; blocked, review-required, stale, and missing states are preserved |
| Artifact state | `artifact-state.json` | Shows overall status and stale, required-missing, and human-review counts without interpreting policy decisions |
| Delivery state | `delivery-readiness-report.json` plus delivery artifact pointer | `ready_with_warnings` means a scoped review package, not authorized delivery |
| Apply plan | Apply plan artifact plus `apply-readiness-report.json` | Operation counts are read from the plan artifact; demo remains blocked and preview does not execute Apply |
| Claim boundary | Runtime `forbidden_claims`, limitations, and observed session summary | Artifact wording is retained; absent matrix fails closed |
| Provider smoke | Both provider smoke closure report and evidence manifest for the selected run | Both must exist and match the run; otherwise provider claims remain unsupported |
| Run identity/freshness | Aggregate `run_id`, `freshness`, `newer_project_state_available`, and `current_project_projection` | Historical/current scope is shown beside the exact Run; current projection is not substituted for a historical snapshot |
| Run summary artifact | `summary_artifact` projection plus indexed session summary fallback | A corrupt `run-summary.json` keeps the Review page usable, marks the card error, and exposes the raw artifact |

## Removed or collapsed noise

- Removed the context-bar inspection action because it had no visible result outside the Generate surface.
- Replaced `APP / SRC / LOC / SEG / CHK` debug labels with a readable project context strip.
- Removed the neutral persistent `Ready` banner; only progress, success, and error feedback is announced.
- Collapsed source overrides, output path, run ID, segment limit, and response import under Advanced run options.
- Kept raw runtime artifact names in the completed-run activity, recent-artifact, and secondary All runtime artifacts surfaces instead of leading with them on first run.
- Replaced the terminal-like artifact preview with a readable, bordered document surface.
- Reorganized the selected run into an artifact-backed completed-run dashboard; no score, percentage, file size, duration, or event timestamp is invented when the runtime does not provide it.
