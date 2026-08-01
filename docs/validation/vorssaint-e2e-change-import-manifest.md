# Vorssaint runtime E2E change import manifest

Generated in the clean-room integration worktree:
`/Users/xueyang/Dev/localize-anything-vorssaint-e2e`.

Source worktree, read-only:
`/Users/xueyang/Dev/localize-anything`.

Source and integration base HEAD:
`76eb1c189b1cb48aa188b10b340b1360f9c28b6c`.

## Import Rule

Only changes explicitly owned by these two passes were imported:

1. unsupported source capability/fail-closed gate;
2. project-local extract-only adapter runtime bridge.

No original-worktree file was modified, staged, committed, stashed, reset, or
cleaned during import.

## Entirely Owned New Files

Copied byte-for-byte from the source worktree.

| Path | Source SHA-256 | Imported SHA-256 | Purpose |
| --- | --- | --- | --- |
| `runtime/localize_anything/project_adapters.py` | `963c139c75321d13ca0e2844afb13af95a44c0c6273466fe6f6d6b9ff525a67e` | `963c139c75321d13ca0e2844afb13af95a44c0c6273466fe6f6d6b9ff525a67e` | Project-local adapter discovery, validation, centralized runner, run evidence, read-only mutation detection. |
| `tests/test_project_adapters.py` | `fe864cf680e3fb402fa00f67eaf7acb19c1fa98570daf8e0e1f0097826680f08` | `fe864cf680e3fb402fa00f67eaf7acb19c1fa98570daf8e0e1f0097826680f08` | Synthetic bridge regression coverage. |
| `tests/fixtures/project_adapters/sample_extract_only/adapter.py` | `582b1dd9a2027beb49ff791cc0315a3ca4e2bc773235893d33a44bc4d26ecfe6` | `582b1dd9a2027beb49ff791cc0315a3ca4e2bc773235893d33a44bc4d26ecfe6` | Stable synthetic extract-only fixture adapter. |
| `tests/fixtures/project_adapters/sample_extract_only/adapter.json` | `7ec74f6ad1776ca3218203208da664fefc4de9fb6a639f17ca25fb92ccc8ae0b` | `7ec74f6ad1776ca3218203208da664fefc4de9fb6a639f17ca25fb92ccc8ae0b` | Stable synthetic fixture descriptor. |
| `docs/runbooks/project-local-extract-only-adapter-smoke.md` | `8d99640935aa66d9e1cf3c7a5728dd0cf380476486b2e930b4de0b8ac2718d42` | `8d99640935aa66d9e1cf3c7a5728dd0cf380476486b2e930b4de0b8ac2718d42` | Smoke procedure for stable project-local extract-only adapters. |
| `docs/validation/vorssaint-e2e-change-import-manifest.md` | n/a | generated in integration worktree | This clean-room import manifest. |

## Entirely Owned Modified Files

Imported by path-scoped patch after reviewing that each diff belongs to the
capability gate or project-local bridge.

| Path | Imported hunks |
| --- | --- |
| `runtime/localize_anything/core.py` | Capability scan/report, project-local adapter resolution, canonical inventory/source-validation/extracted artifacts, artifact hashes, review preconditions, report-only review packet, adapter fingerprint freshness. |
| `runtime/localize_anything/core_preflight.py` | Surface discovery, Swift typed catalog candidate detection as unsupported without explicit adapter, ignored transient directories. |
| `runtime/localize_anything/core_cli.py` | Single explicit selection mechanism: `scan --adapter`. |
| `runtime/localize_anything/contracts.py` | Adapter manifest validation for `adapter_type`, checksum, and `source_scope`. |
| `tests/test_core_cli.py` | Regression coverage for unsupported Swift catalog fail-closed behavior and review artifact freshness. |
| `tests/test_core_capabilities.py` | Regression coverage for surface discovery and ignored transient directories. |
| `docs/security.md` | Project-local scripted adapter trust, checksum, path, and runner security boundary. |
| `skills/localize-anything/SKILL.md` | Skill gate language for surface-aware coverage and artifact preconditions. |
| `skills/localize-anything/references/workflow.md` | Workflow gate language: scan writes capability artifacts, review requires current check/extracted artifacts. |
| `skills/localize-anything/references/qa-and-delivery.md` | Artifact-first phase gate and prohibition on ad hoc review for unsupported sources. |

## Integration E2E Regression Hunks

The first real Vorssaint runtime E2E exposed two bridge/runtime issues after the
clean import. These changes were made only in the integration worktree, are
owned by the project-local adapter bridge, and are included in the current
Definition-of-Done scope.

| Path | Current integration SHA-256 | Imported hunks |
| --- | --- | --- |
| `runtime/localize_anything/project_adapters.py` | `56e9337e50286b956a71fe8fc34b9662423eb07f773faf5a9d52805e5d1dfed2` | Raised `MAX_STDOUT_BYTES` from `1_000_000` to `8_000_000` so a validated read-only extract payload of 3,829,242 bytes can pass through the centralized runner; preserved the `adapter_output_too_large` guard. Adapter stdout/stderr now go through temporary files before bounded reads, oversized blockers include actual/max byte evidence, and `runtime_project_local_adapter` is a centralized execution-mode constant. |
| `tests/test_project_adapters.py` | `8c38870d99187e3a26dc8deedd6957970637a36e2499461b4c4ee50e4a2e1ef6` | Imported `MAX_STDOUT_BYTES` for the oversized-output regression case, made that case exceed the runtime limit by one byte, asserted actual/max byte evidence, and asserted run, canonical, review, and failure artifacts declare `execution_mode = runtime_project_local_adapter` when project-local adapter execution actually occurred. |

## Mixed Ownership Files

These were reviewed but not copied wholesale.

| Path | Decision |
| --- | --- |
| `docs/adapters.md` | Mixed documentation ownership. Not imported into the integration worktree; runtime E2E does not require it, and `docs/security.md` plus the runbook carry the bridge-specific evidence needed here. |
| `skills/localize-anything/references/adapters.md` | Mixed reference ownership. Not imported to avoid carrying unrelated source-surface documentation. |
| `docs/validation/core-capability-matrix.json` | Mixed/generated validation material. Not required for this runtime E2E. |
| `docs/validation/core-capability-matrix.md` | Mixed/generated validation material. Not required for this runtime E2E. |
| `docs/release-checklist.md` | Mixed release documentation. Not required for this runtime E2E. |

## Excluded Unrelated Files

Excluded because the ownership report marked them unrelated or mixed, and the
runtime E2E can run without them.

- `README.en.md`
- `README.md`
- `docs/architecture-roadmap.md`
- `docs/architecture.md`
- `docs/benchmarking.md`
- `docs/decisions/0002-coding-agent-localization-layer.md`
- `docs/decisions/0003-localization-surface-boundary.md`
- `docs/product-direction.md`
- `docs/public-claim-reconciliation.md`
- `protocol/SPEC.md`
- `runtime/localize_anything/android_strings_adapter.py`
- `runtime/localize_anything/core_segments.py`
- `runtime/localize_anything/io_utils.py`
- `runtime/localize_anything/risk_classifier.py`
- `runtime/localize_anything/tabular_adapter.py`
- `runtime/localize_anything/xcstrings_adapter.py`
- `tests/test_runtime.py`

## Uncertain

None imported. Any file whose ownership was not clear enough was left behind.

## Import Commands

- Path-scoped patch from source worktree for owned modified files.
- Exact file copy for owned new files, followed by SHA-256 comparison.
- No staging, commit, push, PR, reset, stash, or cleanup.

## Original Worktree Status Check

The source worktree status after import matched the pre-import dirty file set;
no files in `/Users/xueyang/Dev/localize-anything` were changed by this import.
