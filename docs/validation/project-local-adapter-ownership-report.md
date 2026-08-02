# Project-local adapter ownership report

Generated during the project-local extract-only adapter infrastructure pass.

## Repository state at Phase 0

- Branch: `main`
- HEAD: `76eb1c189b1cb48aa188b10b340b1360f9c28b6c`
- Untracked before this report: `docs/decisions/0003-localization-surface-boundary.md`
- Checkpoint commit: not created

## Reason checkpoint commit was skipped

The worktree contains hunk-level mixed ownership. The previous capability/gate
fix changed files that already had unrelated documentation and runtime edits.
A local commit containing only the previous fix would require manual partial
staging across mixed files and risks capturing unrelated user work.

## A. Previous capability/gate fix ownership

Files with previous gate/freshness changes to preserve:

- `runtime/localize_anything/core.py`
- `runtime/localize_anything/core_preflight.py`
- `tests/test_core_cli.py`
- `tests/test_core_capabilities.py`
- `skills/localize-anything/SKILL.md`
- `skills/localize-anything/references/workflow.md`
- `skills/localize-anything/references/qa-and-delivery.md`

These changes introduced source surface inventory, capability report,
unsupported source fail-closed behavior, scan gating, extracted segment
artifacts, file fingerprints, and review/import freshness checks.

## B. Pre-existing unrelated or mixed changes

Do not stage, rewrite, delete, or normalize these as part of the adapter
infrastructure work unless directly required by the new implementation:

- `README.en.md`
- `README.md`
- `docs/adapters.md`
- `docs/architecture-roadmap.md`
- `docs/architecture.md`
- `docs/benchmarking.md`
- `docs/decisions/0002-coding-agent-localization-layer.md`
- `docs/product-direction.md`
- `docs/public-claim-reconciliation.md`
- `docs/release-checklist.md`
- `docs/validation/core-capability-matrix.json`
- `docs/validation/core-capability-matrix.md`
- `protocol/SPEC.md`
- `runtime/localize_anything/android_strings_adapter.py`
- `runtime/localize_anything/core_segments.py`
- `runtime/localize_anything/io_utils.py`
- `runtime/localize_anything/risk_classifier.py`
- `runtime/localize_anything/tabular_adapter.py`
- `runtime/localize_anything/xcstrings_adapter.py`
- `skills/localize-anything/references/adapters.md`
- `tests/test_runtime.py`
- `docs/decisions/0003-localization-surface-boundary.md`

Some Skill/reference files also contain mixed previous edits and should be
treated carefully at hunk level.

## C. Current pass ownership

This report and subsequent project-local extract-only adapter infrastructure,
fixtures, tests, and runbook updates are owned by the current pass.

## Status update (2026-08-02)

- The project-local extract-only adapter infrastructure was merged to `main`
  as PR #78 (rebase merge). `main` is now
  `f09291f2740670fe5ce107e4c3998cb357175065`; the Phase 0 HEAD above
  (`76eb1c1...`) is the historical base before that merge.
- Section A (capability/gate fix) and Section C (adapter infrastructure,
  fixtures, tests, runbook) are now **merged** via PR #78.
- Section B files remain **pending** in the original mixed worktree; they are
  preserved outside the repository in the dirty-worktree audit backup and are
  not touched by this pass.
- This report and ADR 0003 are the two documents migrated to the
  `reconcile/project-local-adapter-docs` branch and committed here; they were
  the only ownership/decision documents that existed only in the local
  worktree.
