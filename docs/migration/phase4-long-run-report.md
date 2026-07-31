# Phase 4 Runtime Convergence Long-run Report

> Finalized 2026-07-31. No commit or push was created.

## Verdict

**pass** — P4.1 through P4.7 are complete. The broad v0.4 platform Runtime is gone; the five-command Agent-native core is the only public execution path.

## Baseline to final

| Metric | Before P4.1 | After P4.7 | Change |
| --- | ---: | ---: | ---: |
| Runtime Python files | 94 | 24 | -70 |
| Unit tests | 569 | 56 | -513 |
| Protocol schema/example pairs | 192 | 7 | -185 |
| Core imports of LEGACY/DELETE | not isolated | 0 | isolated |

The final CLI surface is:

```text
localize scan
localize glossary bootstrap
localize check
localize review
localize report
```

## Phase summary

| Phase | Result | Files removed | Runtime removed | Tests before → after | Protocol pairs before → after |
| --- | --- | ---: | ---: | ---: | ---: |
| P4.1 | pass | 13 | 6 | 569 → 552 | 192 → 189 |
| P4.2 | pass | 128 | 12 | 552 → 470 | 189 → 131 |
| P4.3 | pass | 14 | 4 | 470 → 407 | 131 → 126 |
| P4.4 | pass | 175 | 19 | 407 → 234 | 126 → 48 |
| P4.5 | pass | 99 | 2 | 234 → 222 | 48 → 7 |
| P4.6 | pass | 1 | 1 | 222 → 227 | 7 → 7 |
| P4.7 | pass | 81 | 31 | 227 → 56 | 7 → 7 |

## P4.1 — CLI-only leaves

Result: **pass**

- Removed files recorded: 13.
- Tests: 569 → 552 (-17).
- Protocol pairs: 192 → 189; removed 3, added 0.
- Runtime removed:

  - `runtime/localize_anything/acceptance.py`
  - `runtime/localize_anything/android_app_test.py`
  - `runtime/localize_anything/deepseek_provider.py`
  - `runtime/localize_anything/inspect_summary.py`
  - `runtime/localize_anything/mo_compiler.py`
  - `runtime/localize_anything/review.py`
- CLI removed:

  - sign-off
  - android-app-test
  - deepseek-generate
  - inspect --output-dir
  - compile-mo
  - review-import
- Extracted or replaced:

  - Finding-linked confirmation remains in the five-command report path.
- Dependencies encountered:

  - The old stress benchmark imported review.py; its obsolete review-import stage was removed with the leaf.
- Blockers: none.
- Removed protocol files: 6; the complete list is in the JSON report and migration map.
- Removed tests, fixtures, docs, benchmark, or entry paths: 1; the complete list is in the JSON report.

## P4.2 — chinese_draft and Provider platform

Result: **pass**

- Removed files recorded: 128.
- Tests: 552 → 470 (-82).
- Protocol pairs: 189 → 131; removed 58, added 0.
- Runtime removed:

  - `runtime/localize_anything/chinese_draft.py`
  - `runtime/localize_anything/provider.py`
  - `runtime/localize_anything/provider_attempt_semantics.py`
  - `runtime/localize_anything/provider_consent.py`
  - `runtime/localize_anything/provider_dry_run.py`
  - `runtime/localize_anything/provider_evidence.py`
  - `runtime/localize_anything/provider_mock.py`
  - `runtime/localize_anything/provider_real_smoke.py`
  - `runtime/localize_anything/provider_result_gate.py`
  - `runtime/localize_anything/provider_safety.py`
  - `runtime/localize_anything/provider_smoke_closure.py`
  - `runtime/localize_anything/provider_staging.py`
- CLI removed:

  - generate-chinese-draft
  - 64 Provider execution, consent, evidence, smoke, result, safety, and staging commands
- Extracted or replaced:

  - No Provider capability justified extraction.
- Dependencies encountered:

  - Benchmark, release-audit, provenance, and artifact-state projections referenced Provider artifacts without importing Provider modules; those projections were removed.
- Blockers: none.
- Removed protocol files: 116; the complete list is in the JSON report and migration map.

## P4.3 — Workbench and Web UI

Result: **pass**

- Removed files recorded: 14.
- Tests: 470 → 407 (-63).
- Protocol pairs: 131 → 126; removed 5, added 0.
- Runtime removed:

  - `runtime/localize_anything/ui.py`
  - `runtime/localize_anything/workbench_action.py`
  - `runtime/localize_anything/workbench_console.py`
  - `runtime/localize_anything/workbench_queue.py`
- CLI removed:

  - 7 Workbench server, console, queue, and action commands
- Extracted or replaced:

  - Human confirmation remains a direct finding-linked core constraint.
- Blockers: none.
- Removed protocol files: 10; the complete list is in the JSON report and migration map.

## P4.4 — Enterprise governance and old workflow platform

Result: **pass**

- Removed files recorded: 175.
- Tests: 407 → 234 (-173).
- Protocol pairs: 126 → 48; removed 78, added 0.
- Runtime removed:

  - `runtime/localize_anything/adapter_evidence.py`
  - `runtime/localize_anything/adapter_release.py`
  - `runtime/localize_anything/benchmark_lab.py`
  - `runtime/localize_anything/document_decision.py`
  - `runtime/localize_anything/document_evidence.py`
  - `runtime/localize_anything/document_evidence_queue.py`
  - `runtime/localize_anything/human_review.py`
  - `runtime/localize_anything/knowledge_audit_enforcement.py`
  - `runtime/localize_anything/knowledge_repair.py`
  - `runtime/localize_anything/knowledge_repair_closure.py`
  - `runtime/localize_anything/knowledge_repair_result.py`
  - `runtime/localize_anything/knowledge_review_confirmation.py`
  - `runtime/localize_anything/knowledge_usage.py`
  - `runtime/localize_anything/readiness_action.py`
  - `runtime/localize_anything/readiness_authorization.py`
  - `runtime/localize_anything/release_audit.py`
  - `runtime/localize_anything/workflow.py`
  - `runtime/localize_anything/workflow_hardening.py`
  - `runtime/localize_anything/workflow_incremental.py`
- CLI removed:

  - readiness and authorization
  - workflow, resume, recovery, idempotency, and lock
  - signoff and human-review evidence
  - release audit and public claims
  - document evidence and leadership review
  - Benchmark Lab
  - adapter promotion and release governance
  - knowledge repair, audit enforcement, and readiness integration
- Extracted or replaced:

  - No platform state, queue, matrix, evidence lifecycle, or governance abstraction was retained.
- Dependencies encountered:

  - Old aggregation modules shared projections across slices; each caller was removed only with its owning vertical slice.
- Blockers: none.
- Removed protocol files: 156; the complete list is in the JSON report and migration map.

## P4.5 — Legacy CLI and protocol contraction

Result: **pass**

- Removed files recorded: 99.
- Tests: 234 → 222 (-12).
- Protocol pairs: 48 → 7; removed 48, added 7.
- Runtime removed:

  - `runtime/localize_anything/__main__.py`
  - `runtime/localize_anything/cli.py`
- CLI removed:

  - The remaining legacy command surface; cli.py and package __main__.py were removed completely.
- Extracted or replaced:

  - Added seven durable contracts for Project Memory, Glossary, deterministic check, review packet/result, human confirmations, and report.
- Dependencies encountered:

  - The old validator assumed catalog parity; it was kept as a dependency-free tree validator over the seven current pairs rather than preserving dead contracts.
- Blockers: none.
- Removed protocol files: 96; the complete list is in the JSON report and migration map.
- Removed tests, fixtures, docs, benchmark, or entry paths: 1; the complete list is in the JSON report.

## P4.6 — Five focused capability extractions

Result: **pass**

- Removed files recorded: 1.
- Tests: 222 → 227 (+5).
- Protocol pairs: 7 → 7; removed 0, added 0.
- Runtime removed:

  - `runtime/localize_anything/segments.py`
- CLI removed: none; the old CLI had already been removed.
- Extracted or replaced:

  - core_glossary.py
  - core_preflight.py
  - core_segments.py
  - core_memory.py
  - core_formats.py
- Dependencies encountered:

  - A remaining Android overlay helper called target_resource_path directly; the full gate caught it and the call was routed through the extracted format boundary before the wrapper was later removed.
- Blockers: none.

## P4.7 — Final old-island cleanup and architecture review

Result: **pass**

- Removed files recorded: 81.
- Tests: 227 → 56 (-171).
- Protocol pairs: 7 → 7; removed 0, added 0.
- Runtime removed:

  - `runtime/localize_anything/agent.py`
  - `runtime/localize_anything/android_merged_overlay.py`
  - `runtime/localize_anything/apply.py`
  - `runtime/localize_anything/artifact_state.py`
  - `runtime/localize_anything/dashboard.py`
  - `runtime/localize_anything/delivery.py`
  - `runtime/localize_anything/delivery_decision.py`
  - `runtime/localize_anything/evaluation.py`
  - `runtime/localize_anything/generation.py`
  - `runtime/localize_anything/generation_handoff_policy.py`
  - `runtime/localize_anything/generation_strategy.py`
  - `runtime/localize_anything/knowledge_consumption.py`
  - `runtime/localize_anything/knowledge_pack.py`
  - `runtime/localize_anything/locale_capability.py`
  - `runtime/localize_anything/localization_brief.py`
  - `runtime/localize_anything/modes.py`
  - `runtime/localize_anything/planning.py`
  - `runtime/localize_anything/project.py`
  - `runtime/localize_anything/quickstart_demo.py`
  - `runtime/localize_anything/reference.py`
  - `runtime/localize_anything/reflection.py`
  - `runtime/localize_anything/resolution_gate.py`
  - `runtime/localize_anything/retrieval.py`
  - `runtime/localize_anything/review_sheet.py`
  - `runtime/localize_anything/run.py`
  - `runtime/localize_anything/segment_repair.py`
  - `runtime/localize_anything/segment_staleness.py`
  - `runtime/localize_anything/staging.py`
  - `runtime/localize_anything/term_governance.py`
  - `runtime/localize_anything/termbase_preflight.py`
  - `runtime/localize_anything/translation_provenance.py`
- CLI removed: none; the old CLI had already been removed.
- Extracted or replaced:

  - Moved two Android reliability resources to tests/fixtures/android-reliability before deleting obsolete benchmark trees.
- Dependencies encountered:

  - Legacy benchmark runners were the only callers outside the old Runtime island and were removed with their obsolete artifacts.
  - One qualifier-routing test depended on the deleted benchmark fixture tree; it now creates the minimal resource tree in a temporary directory.
- Blockers: none.
- Removed tests, fixtures, docs, benchmark, or entry paths: 50; the complete list is in the JSON report.

## P4.6 extraction outcome

| Capability | Focused home | Result |
| --- | --- | --- |
| Glossary candidates and constraints | `runtime/localize_anything/core_glossary.py` | parity_passed |
| Project preflight and resource discovery | `runtime/localize_anything/core_preflight.py` | parity_passed |
| Segment identity, alignment, diff and staleness | `runtime/localize_anything/core_segments.py` | parity_passed |
| Confirmed terminology, TM, style and decision import | `runtime/localize_anything/core_memory.py` | parity_passed |
| Android overlay routing and format parsing/validation boundary | `runtime/localize_anything/core_formats.py` | parity_passed |

The extraction did not copy old artifact-state, workflow, readiness, evidence, queue, or Knowledge Pack lifecycle code. `core.py` delegates to the focused modules instead of becoming a larger orchestrator.

## P4.7 import graph review

- `core.py` / `core_cli.py` import zero module classified LEGACY or DELETE.
- The generation modules had no surviving new-core caller. Their only remaining callers were the old Agent/run/delivery/retrieval/repair island, so the entire island was removed.
- The old benchmark runners were callers of that same island, not independent product consumers; they were deleted with their generated artifacts.
- Adapter manifests no longer expose `python -m runtime.localize_anything` commands after package `__main__.py` removal.
- Two Android reliability resources were moved into `tests/fixtures/android-reliability/`; qualifier routing now uses a minimal temporary fixture.

## Remaining LEGACY Runtime

- `runtime/localize_anything/markup_adapter.py`
- `runtime/localize_anything/subtitle_adapter.py`
- `runtime/localize_anything/tabular_adapter.py`
- `runtime/localize_anything/wesnoth_adapter.py`
- `runtime/localize_anything/word_adapter.py`

Five focused format handlers retain bounded, tested Python compatibility value. They have no public legacy CLI and no automatic fallback path.

Repository validators `contracts.py` and `schema_validation.py` are KEEP, not legacy execution paths. They validate the finite 12-manifest and seven-contract repository surface.

## Final validation

| Gate | Result |
| --- | --- |
| focused core and skill tests | pass (12) |
| full unit tests | pass (56) |
| compileall | pass |
| protocol validator | pass (7 schema/example pairs) |
| adapter validator | pass (12 manifests) |
| markdown links | pass (35 Markdown files) |
| skill frontmatter | pass |
| public claim audit | pass |
| dangling imports | pass (0) |
| core legacy imports | pass (0) |

The Markdown audit includes current documents and the explicitly labeled v0.4 historical snapshot. Active public usage documents contain no removed command examples.

Ignored historical benchmark outputs and validation bytecode caches were moved
out of the workspace to recoverable Trash locations:
`/Users/xueyang/.Trash/localize-anything-p47-old-benchmarks-20260731` and
`/Users/xueyang/.Trash/localize-anything-phase4-pycache-20260731-final`.
No temporary run artifact remains in the source tree.

## Current migration-map statistics

| Scope | KEEP | EXTRACT | REPLACE | LEGACY | DELETE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Active files | 79 | 0 | 0 | 26 | 0 |
| All 616 migration records | 79 | 41 | 70 | 39 | 387 |

## Next recommendation

Return to real-project validation and make only focused fixes for demonstrated five-command gaps. Do not start a new platform or broad deletion batch.

Phase 4 is complete; there is no Phase 4.8 deletion recommendation. A later compatibility sunset should start only from fresh real usage and import evidence.

Machine-readable details:

- [phase4-long-run-report.json](phase4-long-run-report.json)
- [runtime-migration-map.json](runtime-migration-map.json)
