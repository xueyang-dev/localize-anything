# Vorssaint runtime E2E isolation audit

Status: pass

Generated: `2026-08-01T14:18:53Z`

Integration worktree:
`/Users/xueyang/Dev/localize-anything-vorssaint-e2e`

Original worktree, read-only:
`/Users/xueyang/Dev/localize-anything`

Localize Anything base HEAD:
`76eb1c189b1cb48aa188b10b340b1360f9c28b6c`

Runtime E2E run:
`/Users/xueyang/Developer/localize-anything-runs/vorssaint-runtime-e2e/20260801-210221`

## Scope Audit

| Check | Result | Evidence |
| --- | --- | --- |
| All modifications are in the import manifest | pass | `docs/validation/vorssaint-e2e-change-import-manifest.md` lists owned new files, owned modified files, excluded unrelated files, and the two integration-only E2E regression hunks. |
| No unrelated feature changes imported | pass | The manifest excludes README, architecture, product, protocol, unrelated runtime adapters, `tests/test_runtime.py`, and mixed adapter docs. Current integration status contains only the listed gate/bridge paths plus validation reports. |
| No generated files, caches, or credentials imported | pass | `git status --porcelain=v1 --untracked-files=all` shows no `__pycache__`, `.pyc`, cache, build output, or credential file. Credential scan over `docs`, `runtime`, `tests`, and `skills` returned no matches. Compile-time `__pycache__` output was removed after verification. |
| No second adapter registry | pass | Project-local discovery is contained in `runtime/localize_anything/project_adapters.py`; core calls `discover_project_adapters()` and `load_project_adapter()` from that module. No duplicate registry or parallel adapter index was added. |
| No second artifact truth | pass | Adapter output is admitted only through runtime-generated canonical artifacts: `source-surface-inventory.json`, `capability-report.json`, `inventory.json`, `source-validation.json`, `deterministic-check.json`, and `extracted-segments.json`. Standalone artifacts were used only for comparison. |
| Capability policy remains centralized | pass | `runtime/localize_anything/core.py` builds the capability report and blocked phases; `runtime/localize_anything/project_adapters.py` enforces read-only phases and descriptor constraints. Adapter internals do not decide delivery capability. |
| Unselected adapter does not execute | pass | Phase 3 scan exited `2`; stderr says the candidate will not be executed until explicit selection. Phase 3 state contains only `capability-report.json` and `source-surface-inventory.json`; no `adapter-runs`, stdout artifact, Project Memory, or extraction artifact exists. |
| `extract_only` is not elevated by rebuild-like adapter code | pass | The snapshot adapter contained standalone/full workflow concepts, but the runtime compatibility copy exposes only `detect`, `inventory`, `extract`, and `validate_source` with `round_trip_level = extract_only`. Runtime blocked `rebuild`, `validate_output`, `plan_apply`, and `apply`. |
| Review depends on current, valid, mapping-consistent canonical artifacts | pass | `runtime/localize_anything/core.py` checks deterministic mapping and extracted mapping before review. Phase 9 verified source drift, descriptor drift, entrypoint checksum drift, deleted extraction, and mapping mismatch all block review. |

## Code Boundary Evidence

- `runtime/localize_anything/project_adapters.py` declares the only project-local adapter directory, allowed permissions, allowed read-only phases, descriptor validation, safe command execution, stdout/stderr limits, and source mutation detection.
- `runtime/localize_anything/core.py` performs adapter resolution, capability report generation, canonical artifact writing, deterministic fingerprinting, and review precondition checks.
- `runtime/localize_anything/core_cli.py` exposes the single explicit selection path: `scan --adapter`.
- `runtime/localize_anything/contracts.py` validates adapter manifest fields without creating a separate runtime contract source.

## Runtime Evidence

- Candidate not selected:
  `phase3-scan-no-adapter.exitcode = 2`; no adapter execution record exists under `phase3-state`.
- Explicit selection:
  `phase4-scan-selected.exitcode = 0`; `adapter-selection-evidence.json` records selected adapter `vorssaint-swift-typed`, version `0.1.2`, descriptor checksum `b341cfd979945d9770c93a410f14f289c5fe707929b8afd4764f6e74abebbfd0`, and entrypoint checksum `b7c1013fea062a8d0781db345d4f09fdddad8dd81715a60b2b0eac61676fba86`.
- Formal check:
  `phase5-check.exitcode = 0`; canonical artifacts are listed in `canonical-artifact-manifest.json` and checksummed in `canonical-artifact-checksums.sha256`.
- Review:
  `phase7-review.exitcode = 0`; `review-gate-report.json` records `review_mode = report_only`, `adapter_kind = project_local`, and `segments = 1641`.
- Extract-only blocks:
  `extract-only-block-report.json` records blocked delivery/apply/full-round-trip claims with machine-readable `capability_not_allowed` results.
- Staleness:
  `staleness-test-report.json` records all stale/failure injection cases as blocked and confirms restored review succeeds.
- Source mutation:
  `source-mutation-audit.json` records empty tracked status and empty tracked diff for the Vorssaint source worktree.

## Artifact Truth Boundary

Standalone run artifacts were not imported as canonical runtime truth. The
runtime used the project-local adapter through the official CLI and wrote its
own canonical artifacts. `standalone-runtime-comparison.json` and
`standalone-runtime-comparison.md` classify differences with the required
machine categories:

- `schema_only`
- `expected_runtime_normalization`
- `contract_mapping_issue`
- `runtime_ingestion_bug`
- `adapter_output_loss`
- `source_mismatch`
- `unexplained`

No resource or segment count decreased. Runtime extraction matched the
standalone baseline for resources, total extracted segments, locale counts,
family counts, hardcoded UI occurrences, and placeholder candidate items.

## Isolation Verdict

The integration worktree contains only the imported fail-closed/capability gate
and project-local adapter bridge changes, plus two E2E-discovered bridge
regression hunks documented in the import manifest. No original worktree file
was staged, committed, reset, cleaned, or modified. The runtime claims only
`extract_only` plus report-only review capability for this adapter path.
