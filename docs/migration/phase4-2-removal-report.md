# Phase 4.2 Removal Report

Date: 2026-07-31
Status: completed
Git: no commit, no push

## Boundary

Phase 4.2 removed two bounded legacy slices:

1. `chinese_draft.py` and its `generate-chinese-draft` CLI path.
2. The old Provider platform implemented by `provider.py` and
   `provider_*.py`.

The five-command core and Skill default path were not expanded. `core.py` was
not modified. No deprecated shim, empty command, compatibility wrapper,
registry, plugin layer, or state machine was added.

## Pre-delete dependency checks

`chinese_draft.py` had one production caller: the old `cli.py`. It was not
imported by `core.py`, `core_cli.py`, the Skill, five-command tests, or any
non-legacy production path.

The Provider reverse-dependency inventory found 74 import statements across 13
caller files before deletion:

| Provider module | Former callers |
|---|---|
| `provider.py` | `agent.py`, `cli.py`, `tests/test_runtime.py` |
| `provider_attempt_semantics.py` | `artifact_state.py`, `cli.py`, `ui.py`, tests |
| `provider_consent.py` | `artifact_state.py`, `cli.py`, `delivery.py`, `evaluation.py`, `readiness_authorization.py`, `run.py`, `ui.py`, tests |
| `provider_dry_run.py` | `artifact_state.py`, `cli.py`, `delivery.py`, `evaluation.py`, `readiness_authorization.py`, `run.py`, `ui.py`, tests |
| `provider_evidence.py` | `artifact_state.py`, `cli.py`, `delivery.py`, `evaluation.py`, `generation_handoff_policy.py`, `readiness_authorization.py`, `run.py`, `ui.py`, `workflow.py`, tests |
| `provider_mock.py` | `artifact_state.py`, `cli.py`, `delivery.py`, `run.py`, `ui.py`, tests |
| `provider_real_smoke.py` | `artifact_state.py`, `cli.py`, `delivery.py`, `run.py`, `ui.py`, tests |
| `provider_result_gate.py` | `artifact_state.py`, `cli.py`, `delivery.py`, `evaluation.py`, `human_review.py`, `readiness_authorization.py`, `run.py`, `ui.py`, tests |
| `provider_safety.py` | `artifact_state.py`, `cli.py`, `delivery.py`, `evaluation.py`, `readiness_authorization.py`, `run.py`, `ui.py`, tests |
| `provider_smoke_closure.py` | `artifact_state.py`, `cli.py`, `delivery.py`, `ui.py`, tests |
| `provider_staging.py` | `artifact_state.py`, `cli.py`, `delivery.py`, `run.py`, `staging.py`, `ui.py`, tests |

No Provider module was used by the new core or Skill. Inspection found no
independent Provider capability worth extracting into the five-command core.

## Deleted Runtime

The following 12 Runtime files were deleted:

```text
runtime/localize_anything/chinese_draft.py
runtime/localize_anything/provider.py
runtime/localize_anything/provider_attempt_semantics.py
runtime/localize_anything/provider_consent.py
runtime/localize_anything/provider_dry_run.py
runtime/localize_anything/provider_evidence.py
runtime/localize_anything/provider_mock.py
runtime/localize_anything/provider_real_smoke.py
runtime/localize_anything/provider_result_gate.py
runtime/localize_anything/provider_safety.py
runtime/localize_anything/provider_smoke_closure.py
runtime/localize_anything/provider_staging.py
```

Runtime inventory changed from 88 to 76 active files.

## Removed CLI surface

The removal deleted 64 direct commands:

- `generate-chinese-draft`;
- core Provider request, execution, ledger, intake, reconciliation, QA,
  acceptance, and handoff commands;
- Provider mock harness commands;
- Provider safety, credential, network, redaction, dry-run, and consent
  commands;
- Provider result staging, quarantine, attempt-semantics, and claim-boundary
  commands;
- real-smoke planning, evidence-review, closure, release-boundary, and
  next-step commands;
- `workbench-provider-review-queue`.

The exhaustive machine-readable list is in
`phase4-long-run-report.json` under the P4.2 phase's
`removed_cli_surfaces`. At the P4.2 gate, the old CLI help contained none of
these commands.

## Removed protocol and documentation surface

Deleted 58 Provider schema/example pairs:

- policy, handoff, ledger, result intake, reconciliation, QA, review, and
  acceptance;
- mock harness;
- safety, credential, network, redaction, dry-run, and consent;
- attempt semantics and result staging;
- real-smoke and smoke-closure;
- Workbench Provider review queue.

Protocol counts changed:

| Item | Before | After | Change |
|---|---:|---:|---:|
| schemas | 189 | 131 | -58 |
| examples | 189 | 131 | -58 |
| schema/example files | 378 | 262 | -116 |
| protocol files including `SPEC.md` | 379 | 263 | -116 |

Current Provider contract sections were removed from `protocol/SPEC.md`.
README status text now states that the Provider platform was removed. Active
Android documentation delegates semantic translation to the Coding Agent and
project-native validation. Historical Provider material remains only in
explicitly historical architecture/release/changelog records and the migration
audit trail.

## Shared caller cleanup

Former callers were reduced rather than replaced:

- `cli.py`: removed imports, parsers, dispatch, and direct generation flags.
- `agent.py`: removed direct HTTP Provider execution.
- `ui.py`: removed Provider routes, actions, and handlers.
- `artifact_state.py`: removed Provider artifact specs and dependency
  propagation.
- `delivery.py`, `run.py`, `staging.py`, `workflow.py`: removed Provider assets,
  stages, blockers, and output fields tied to the deleted platform.
- `evaluation.py`, `readiness_authorization.py`, `human_review.py`: removed
  Provider artifact intake and reconciliation.
- `benchmark_lab.py`, `release_audit.py`, `translation_provenance.py`: removed
  hidden reads of deleted Provider artifacts.

These edits did not introduce a replacement orchestration layer.

## Retained generation modules

Three generation modules remain because they have non-Provider callers:

| Module | Non-Provider callers |
|---|---|
| `generation.py` | `agent.py`, `cli.py`, `run.py` |
| `generation_strategy.py` | `cli.py`, `delivery.py`, `generation_handoff_policy.py`, `resolution_gate.py`, `retrieval.py`, `run.py`, `segment_repair.py`, `ui.py` |
| `generation_handoff_policy.py` | `cli.py`, `delivery.py`, `retrieval.py`, `run.py`, `ui.py` |

Their direct imports of Provider modules, deleted artifact reads, and
`provider-generate` instructions were removed. Remaining generic Agent/model
generation behavior belongs to later legacy vertical decisions and was not
deleted in P4.2.

## Tests

The monolithic suite changed from 552 to 470 tests, a reduction of 82
Provider/chinese_draft-only methods. No test file was deleted.

The `chinese_draft` gate was run before Provider deletion:

```text
tests.test_core_cli + tests.test_skill_phase2: 7 passed
```

Final validation:

| Validation | Result |
|---|---|
| five-command end-to-end + `test_skill_phase2.py` | pass, 7 tests |
| full unit suite | pass, 470 tests |
| `compileall` | pass |
| protocol validator | pass, 131 schemas and 131 examples |
| adapter validator | pass, 12 manifests |
| deleted module import audit | pass, 0 active imports |
| deleted CLI/artifact reference audit | pass |
| Markdown link audit | pass after correcting one pre-existing benchmark link |

## Unexpected dependencies and blockers

Two unexpected dependency shapes were found:

1. `benchmark_lab.py`, `release_audit.py`, and `translation_provenance.py`
   consumed Provider artifacts without importing Provider modules. Those reads
   were removed.
2. `artifact_state.py` placed Provider and general locale/provenance JSON status
   handling in the same branch. The first mechanical removal also removed the
   general behavior; locale/provenance handling was restored and its existing
   tests pass.

There were no EXTRACT blockers. There are no remaining imports of
`provider.py`, `provider_*.py`, or `chinese_draft.py`.

## Inventory result

Phase 4.2 removed 128 files:

- 12 Runtime files;
- 58 schemas;
- 58 examples.

Active migration-map classification counts at the P4.2 gate were:

| KEEP | EXTRACT | REPLACE | LEGACY | DELETE | Total |
|---:|---:|---:|---:|---:|---:|
| 40 | 63 | 67 | 20 | 223 | 413 |

## Phase 4.3 recommendation

Phase 4.3 can begin, but should remain sliced:

1. generate a new reverse-dependency list for `ui.py` and `workbench*.py`;
2. remove the Workbench/UI vertical if no new-core dependency appears;
3. handle readiness/signoff/document, then release/benchmark/provenance as
   separate batches;
4. do not combine these with Knowledge/workflow extraction.

The five-command core, Skill default path, and project-native engineering
validation remain the deletion gate.
