# Changelog

## Unreleased

### Added

- Add term-governance groundwork with seeded `term-registry.csv`,
  `term-decisions.jsonl`, `forbidden-translations.csv`,
  `term-conflicts.jsonl`, and `term-provenance.jsonl` project artifacts.
- Add a `term-decision` protocol schema and feed approved/locked term-registry
  entries plus forbidden translations into work-packet hard constraints.
- Add localization-brief groundwork with machine-readable
  `localization-brief.json` and human-readable `localization-brief.yaml`
  artifacts seeded during project initialization.
- Add a `localization-brief` protocol schema and delivery packaging support so
  task intent, source surface, constraints, and required human confirmations are
  recorded before generation.
- Align brief fields with the optimized architecture structure:
  `document_type`, `source_genre`, `target_mode`, `target_audience`, `style`,
  `constraints`, `allowed_transformations`, and `forbidden_behaviors`.
- Add a UI-first termbase preflight seed that writes `candidate-terms.jsonl`,
  `termbase-preflight-report.json`, `term-review-queue.json`, and
  `term-review-decisions.jsonl`, with CLI and Workbench API paths for queue
  review decisions.
- Add a Generation Strategy Gate seed that writes `generation-strategy.json`,
  routes review-required handoffs, blocks unresolved term conflicts, and
  propagates strategy state into work packets and draft requests.
- Add a Resolution Gate seed that writes `blocking-questions.json`,
  `resolution-options.json`, `user-resolution-decisions.jsonl`, and
  `resolution-summary.md` so blocked or review-required generation strategy
  states become explicit human decisions.
- Add Generation Handoff Enforcement with `generation-handoff-decision.json`,
  CLI/API status access, provider fallback fail-closed checks, and run/delivery
  metadata that prevents downgraded handoffs from claiming full assurance.
- Add Artifact State Machine seed with `artifact-state.json`, CLI/API status
  access, stale-evidence handoff enforcement, and delivery/apply blockers for
  stale upstream artifacts.
- Add Segment-Level Staleness / Reuse Decision seed with
  `stale-segments.jsonl`, `reuse-decision.json`, CLI/API read paths,
  artifact-state summary integration, and handoff/delivery/apply enforcement
  for stale generated segments.
- Add Targeted Repair / Segment Regeneration Plan seed with
  `segment-regeneration-plan.json`, `repair-request.json`,
  `repair-result.json`, `repair-history.jsonl`, CLI/API read paths, and
  handoff/delivery/apply enforcement for pending segment repairs.
- Add Patch-Based Repair Execution seed with provider-free deterministic
  `apply-repair-plan`, `GET /api/repair-result`,
  `POST /api/apply-repair-plan`, repair execution statuses, QA/provenance
  history, and run/delivery summaries for applied, pending, blocked, and failed
  repairs.

## v0.4.1 - Workbench UI Wiring

### Changed

- Refine the Workbench WebUI into a practical app shell without copied macOS
  window controls.
- Wire the Workbench localization mode selector to the agent
  `operating_mode` and `reference_policy` backend parameters.
- Add a sessions panel backed by `/api/sessions` so prior agent runs can be
  loaded from the WebUI.
- Add inline WebUI validation for missing project paths, missing target
  locales, and missing response directories before backend calls are made.

### Fixed

- Pass Workbench `operating_mode` and `reference_policy` values through
  `/api/agent-run` into the runtime agent.
- Skip the bash-only AntennaPod helper syntax test when Windows exposes a WSL
  `bash.exe` launcher but no runnable Linux distribution is installed.

### Notes

- `PROTOCOL_VERSION` remains `0.1`.

## v0.4.0 - Word Document Localization

### Added

- Add the `core.word-document` adapter for `.docx`, `.dotx`, `.docm`, and
  `.dotm` OpenXML packages.
- Extract, rebuild, and validate visible WordprocessingML and DrawingML text in
  body content, tables, headers, footers, notes, comments, text boxes, charts,
  and safely editable diagram/drawing XML.
- Add `extract-word`, `rebuild-word`, and `validate-word` CLI commands.
- Add Workbench file/folder import and drag-and-drop upload into a temporary
  project so Word documents can reuse the existing agent-run, staging,
  delivery, and apply flow.
- Add explicit opt-in Android merged dependency resource overlay generation for
  projects that need to localize dependency-provided Android resources.

### Changed

- Localized Word runs now normalize the font family by target locale. English
  output uses Arial; Simplified Chinese uses Microsoft YaHei; Japanese and
  Korean use common platform fonts.
- Word QA preserves package entries, relationships, styles, non-text resources,
  paragraph properties, non-font run properties, placeholder parity, and macro
  bytes while allowing the target-locale font-family normalization.

### Notes

- Legacy binary `.doc` remains unsupported and must be converted to OpenXML
  before localization.
- Macro documents are supported only as OpenXML packages; `vbaProject.bin` bytes
  are copied and validated but never executed.
- Images, embedded objects, and scanned/image text are preserved but not
  localized.
- `PROTOCOL_VERSION` remains `0.1`.

## v0.3.2 - Android Coverage Diagnostics

### Added

- Add Android coverage diagnostics that distinguish editable app source
  resources from Gradle merged dependency resources.
- Add inspect and run-summary warnings when source-only Android localization may
  leave visible dependency-provided UI strings in the source language.
- Document the Android coverage model, including runtime text that is outside
  Android resource-file localization.

### Notes

- This release does not add merged dependency overlay generation.
- This release does not add apply-to-project write-back.
- This release does not run provider-backed translation.
- `PROTOCOL_VERSION` remains `0.1`.

## v0.3.1 - Provider Path Hygiene Fix

### Fixed

- Removed a hardcoded private env-file path from the DeepSeek provider.
- Require DeepSeek provider credentials through explicit environment
  configuration instead of default user-specific filesystem locations.
- Added runtime-code hygiene coverage to guard against private local path
  leakage.

### Notes

- This release does not change localization behavior.
- This release does not change Android adapter behavior.
- `PROTOCOL_VERSION` remains `0.1`.

## v0.3.0 - Real-Project Workflow Hardening

### Added

- Add read-only inspect summaries with JSON and Markdown outputs.
- Document the inspect-summary workflow for real-project source detection.
- Add refreshed AntennaPod disposable-clone smoke-test evidence for the
  v0.3.0 pre-release workflow.

### Changed

- Improve CLI help so `inspect` is clearly read-only and `localize-run` is
  clearly non-apply.
- Refuse `inspect --output-dir` paths inside the inspected source project.
- Improve the AntennaPod smoke-test helper output by reporting raw inspection
  and compact inspect-summary artifact paths.
- Normalize shell helper line endings for Bash compatibility.
- Bump package/runtime version metadata to `0.3.0`.

### Fixed

- Harden generated-segment markup validation so generic markup constraint lists
  do not enter the Android inline-markup validator.

### Notes

- `PROTOCOL_VERSION` remains `0.1`.
- This release does not validate provider-backed AntennaPod translation.
- This release does not validate destructive apply against AntennaPod.
- Known limitations remain: no full HTML parser, no layout/drawable/asset
  localization, no Gradle editing, and no APK decompilation.

## v0.2.5 — Public Readiness and Smoke Test Evidence

### Changed

- Improve release hygiene, README clarity, and CI benchmark coverage.
- Synchronize package/runtime version metadata with the public release line.
- Complete public readiness cleanup for the repository presentation.
- Polish the bilingual README and public launch documentation.
- Add contributor guidance, issue templates, a pull request template, and a
  SECURITY entry point.
- Document the AntennaPod disposable-clone smoke-test guide and smoke-test
  results.
- Bump package/runtime version metadata to `0.2.5`.

### Notes

- This release does not change runtime localization behavior.
- This release does not add adapter support.

## v0.2.3 — Android Resource Reliability Fixes

### Fixed

- Corrected Android resource qualifier ordering for target locale paths.
  - `values-mcc310` now maps to `values-mcc310-zh-rCN`.
  - `values-mcc310-mnc004-land` now maps to `values-mcc310-mnc004-zh-rCN-land`.
- Fixed risk classification evidence truthfulness.
  - Protected-structure evidence is emitted only when placeholders, escapes,
    markup, CDATA, or structural review markers actually exist.

### Added

- Android support boundary documentation in `docs/android-v0.2.3-support.md`.
- MCC/MNC source-set regression fixtures and fail-closed routing checks.
- Clean release validation flow for v0.2.3.

### Notes

- v0.2.3 supersedes the unpublished v0.2.2 tag.
- v0.2.2 remains in history but should not be used as a public release.
