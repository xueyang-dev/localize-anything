# Project-local adapter final review

Status: pass

Generated: `2026-08-01T14:18:53Z`

Integration worktree:
`/Users/xueyang/Dev/localize-anything-vorssaint-e2e`

Branch:
`test/vorssaint-project-adapter-e2e`

Base HEAD:
`76eb1c189b1cb48aa188b10b340b1360f9c28b6c`

Real E2E run:
`/Users/xueyang/Developer/localize-anything-runs/vorssaint-runtime-e2e/20260801-210221/`

## Diff Scope

Allowed scopes:

1. unsupported source capability/fail-closed gate
2. artifact prerequisites and freshness
3. project-local adapter discovery/selection
4. descriptor, checksum, and path validation
5. centralized scripted adapter runner
6. canonical artifact ingestion
7. extract_only runtime policy
8. synthetic fixtures/tests
9. CLI UX
10. security/docs/runbook
11. real E2E regression fixes for stdout limit and execution_mode evidence

## Modified Files

| Path | Purpose | Scope |
| --- | --- | --- |
| `runtime/localize_anything/core_preflight.py` | Adds source surface discovery, fail-closed Swift/code-embedded catalog detection, and ignored transient directories. | 1 |
| `runtime/localize_anything/core.py` | Writes source-surface inventory and capability report, gates scan before Project Memory, resolves explicit project-local adapters, writes canonical inventory/source-validation/extracted artifacts, records file and adapter fingerprints, enforces review freshness/mapping prerequisites, and generates report-only review packets. | 1, 2, 3, 6, 7 |
| `runtime/localize_anything/core_cli.py` | Adds the explicit `scan --adapter` selection path. | 3, 9 |
| `runtime/localize_anything/contracts.py` | Extends adapter manifest validation for scripted/declarative adapter type, checksum, and source scope. | 4 |
| `tests/test_core_cli.py` | Covers unsupported Swift catalog fail-closed scan behavior, capability artifacts, and review artifact freshness. | 1, 2, 9 |
| `tests/test_core_capabilities.py` | Covers source surface discovery and ignored transient directories. | 1 |
| `docs/security.md` | Documents project-local scripted adapter trust boundary, path/checksum validation, bounded stdout/stderr, timeout, environment isolation, and read-only policy. | 10, 11 |
| `skills/localize-anything/SKILL.md` | Updates skill guidance for capability gating, artifact preconditions, and unsupported source boundaries. | 1, 2, 10 |
| `skills/localize-anything/references/workflow.md` | Updates workflow phase order and review prerequisites. | 1, 2, 10 |
| `skills/localize-anything/references/qa-and-delivery.md` | Requires artifact-first review and blocks ad hoc unsupported-source review claims. | 1, 2, 10 |

## New Files

| Path | Purpose | Scope |
| --- | --- | --- |
| `runtime/localize_anything/project_adapters.py` | Single project-local adapter discovery, descriptor validation, checksum/path validation, safe read-only runner, run evidence, output bounds, source mutation detection, and adapter fingerprint helpers. | 3, 4, 5, 7, 11 |
| `tests/test_project_adapters.py` | Synthetic coverage for candidate-not-selected, explicit extract-only selection, canonical artifacts, review packet provenance, stale artifacts, descriptor/path/checksum failures, runtime failure artifacts, oversized output, and read-only source mutation blocking. | 3, 4, 5, 6, 7, 8, 11 |
| `tests/fixtures/project_adapters/sample_extract_only/adapter.py` | Minimal scripted fixture adapter for generic extract-only runtime tests. | 8 |
| `tests/fixtures/project_adapters/sample_extract_only/adapter.json` | Fixture descriptor for the synthetic extract-only adapter. | 8 |
| `docs/runbooks/project-local-extract-only-adapter-smoke.md` | Disposable-worktree smoke runbook for explicit project-local extract-only adapters. | 10, 11 |
| `docs/validation/vorssaint-e2e-change-import-manifest.md` | Clean-room import manifest and hunk ownership record. | 10 |
| `docs/validation/vorssaint-e2e-isolation-audit.md` | Isolation audit confirming no unrelated features, generated files, second registry, second artifact truth, or unselected execution. | 10 |
| `docs/validation/vorssaint-e2e-preflight-results.md` | Phase 0.7 regression and original-worktree unchanged evidence. | 10 |
| `docs/validation/project-local-adapter-final-review.md` | This final packaging and code review record. | 10 |

## Deleted Files

None.

## Unrelated Or Generated Content

- Unrelated changes found in the integration diff: none.
- Generated/cache files found in the integration diff: none.
- `find . -path ./.git -prune -o -type f -size +1M -print`: no results.
- `find . -path ./.git -prune -o \( -name '*.log' -o -name '*.tmp' -o -name '*.bak' -o -name '*.pyc' -o -name '__pycache__' -o -name '.pytest_cache' \) -print`: no results after test cache cleanup.
- Credential scan over `docs`, `runtime`, `tests`, and `skills`: no results.
- E2E run artifacts, adapter snapshot files, Vorssaint source files, third-party source, and large stdout payloads are not present in the repository diff.

## Registry And Artifact Truth

- No second adapter registry was added. Project-local adapter discovery lives in
  `runtime/localize_anything/project_adapters.py`; core imports that module and
  does not maintain a competing registry.
- No second artifact truth was added. Adapter stdout is validated by the runtime
  before canonical ingestion. Review uses `deterministic-check.json` and
  `extracted-segments.json` as prerequisites, not standalone artifacts.
- Standalone/E2E comparison files remain outside the source repository except
  for validation summaries.

## Stdout Limit Review

- The stdout limit is centralized as `MAX_STDOUT_BYTES = 8_000_000` in
  `runtime/localize_anything/project_adapters.py`.
- Stderr has a separate evidence ceiling: `MAX_STDERR_BYTES = 16_000`.
- Adapter stdout/stderr are captured to temporary files first; the runtime
  checks byte size before reading stdout into memory.
- Oversized stdout remains blocked with `adapter_output_too_large`.
- The blocker message and evidence include the actual byte size and configured
  maximum.
- Synthetic tests use `MAX_STDOUT_BYTES + 1` and assert the actual/max evidence.
- This is not a streaming protocol. Future scalability backlog: add thresholded
  streaming/early process termination if adapters need outputs larger than the
  current 8 MB safety ceiling.

## Execution Mode Review

- The execution mode string is centralized as
  `PROJECT_ADAPTER_EXECUTION_MODE = "runtime_project_local_adapter"`.
- Runtime project-local run artifacts record that execution mode for success
  and failure paths through the shared `_run_info()` helper.
- Canonical project-local inventory/source-validation/extracted records and
  report-only review packets carry the same execution mode evidence.
- Standalone adapter artifacts are not read back and rewritten as runtime
  artifacts.
- Candidate-not-selected scans do not create adapter-runs or execution-mode
  evidence because no adapter code ran.

## Contract Compatibility Review

Source:
`/Users/xueyang/Developer/localize-anything-runs/vorssaint-runtime-e2e/20260801-210221/adapter-runtime-compatibility-report.md`

| Difference | Classification | Review |
| --- | --- | --- |
| `round_trip_level = extract_only` | runtime contract requirement | Runtime policy depends on this field to allow check/report-only review and block rebuild/apply/full round trip. |
| phase entrypoints for `detect`, `inventory`, `extract`, `validate_source` | runtime contract requirement | Runtime calls canonical phases through a JSON stdin/stdout envelope. |
| `checksum`, `source_scope`, `adapter_type`, `provenance` | runtime contract requirement | Required for trust-boundary validation, source matching, evidence, and freshness checks. |
| `runtime.type = python` | runtime contract requirement | The v1 safe runner only executes declared Python scripted adapters. |
| `capability_level` | Hermes adapter legacy field | Mapped to `round_trip_level` in the compatibility copy only. |
| `runtime.language` | Hermes adapter legacy field | Mapped to `runtime.type` in the compatibility copy only. |
| `entrypoints.cli` | Hermes adapter legacy field | Replaced by phase-specific runtime entrypoints in the compatibility copy only. |
| `align`, `aligned_validate`, `write_staging` | Hermes adapter legacy field | Removed because the current runtime bridge is extract-only/read-only. |
| `runtime_bridge.py` | temporary bridge shim | Wraps the stable adapter functions without changing parser, extraction rules, or linguistic review rules. |
| `notes`, `limitations` | optional metadata | Preserved as descriptive evidence, not used to grant capability. |
| `maintainer` fallback to provenance | future deprecation candidate | Runtime accepts `maintainer` as fallback now; future descriptors should use explicit `provenance`. |

No runtime code contains a Vorssaint-specific branch or locale-specific special
case. The formal runtime code does not contain `vorssaint`, `zh-Hans`, `zh-TW`,
or `zh-HK`.

## Grep Audit

- `git grep -n '/Users/xueyang' -- .` before staging: existing migration report
  files in `docs/migration/phase4-long-run-report.*`; no formal runtime code
  hit.
- `git grep --cached -n '/Users/xueyang' -- .` after staging: existing
  migration report files plus intentional environment and E2E evidence paths in
  `docs/validation/*.md`; no runtime, tests, fixture adapter, skill, security
  doc, or runbook hit.
- `git grep -n 'vorssaint' -- runtime`: no hits.
- `rg 'vorssaint'` over untracked validation files: hits only in
  `docs/validation/vorssaint-e2e-*.md`, where the real E2E is intentionally
  documented.

## Final Test Results

| Command | Exit code | Result |
| --- | ---: | --- |
| `python3 -m unittest discover -s tests` | 0 | `Ran 70 tests in 6.307s`; `OK`. |
| `python3 -m compileall runtime` | 0 | Runtime modules compiled successfully. |
| `git diff --check` | 0 | No whitespace or patch-format errors. |
| `git status --short` | 0 | Only reviewed source/docs/test changes are present. |
| `find . -name '**pycache**' -o -name '*.pyc'` | 0 | Compileall-created cache files were found immediately after compileall, then removed; rerun produced no output. |
| `git grep -n '/Users/xueyang' -- .` | 0 | No runtime code hits; staged hits are existing migration docs and validation evidence paths. |
| `git grep -n 'vorssaint' -- runtime` | 0 | No runtime hits. |

## Commit Packaging Recommendation

The diff is logically splitable into two commits:

1. `runtime: fail closed on unsupported localization surfaces`
   - `runtime/localize_anything/core_preflight.py`
   - capability/freshness portions of `runtime/localize_anything/core.py`
   - `tests/test_core_capabilities.py`
   - relevant `tests/test_core_cli.py`
   - skill/workflow/QA guidance tied to fail-closed artifact prerequisites

2. `runtime: support explicit project-local extract-only adapters`
   - `runtime/localize_anything/project_adapters.py`
   - adapter resolution, descriptor validation, safe runner, canonical
     ingestion, execution mode evidence, CLI flag, fixture/tests, security
     docs, runbook, and validation reports

If hunk splitting makes either commit non-testable because `core.py` interweaves
the capability report, adapter resolution, canonical artifacts, and review
preconditions, a single commit is acceptable:
`runtime: add fail-closed project-local adapter execution`.
