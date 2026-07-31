# Phase 4.1 Legacy Runtime Leaf Removal Report

Date: 2026-07-31

Result: **pass**

## Boundary confirmation

Before deletion, AST import and text-reference checks confirmed that none of the
six Runtime modules was imported by `core.py`, `core_cli.py`, the Skill default
path, `tests/test_core_cli.py`, or `tests/test_skill_phase2.py`. The five-command
core remained:

```text
scan
glossary bootstrap
check
review
report
```

No capability needed by the new core was found, so there was no EXTRACT
blocker. No compatibility shim, registry, plugin layer, wrapper, or state
machine was added.

## Deleted files

Thirteen files were deleted.

Runtime modules:

```text
runtime/localize_anything/acceptance.py
runtime/localize_anything/android_app_test.py
runtime/localize_anything/deepseek_provider.py
runtime/localize_anything/inspect_summary.py
runtime/localize_anything/mo_compiler.py
runtime/localize_anything/review.py
```

Protocol schemas and examples:

```text
protocol/schemas/acceptance.schema.json
protocol/examples/acceptance.json
protocol/schemas/android-app-test-report.schema.json
protocol/examples/android-app-test-report.json
protocol/schemas/review-import.schema.json
protocol/examples/review-import.json
```

Documentation:

```text
docs/inspect-summary.md
```

## Removed CLI surfaces

The old `cli.py` imports, argparse definitions, and dispatch branches were
removed for:

```text
sign-off
android-app-test
deepseek-generate
inspect --output-dir
compile-mo
review-import
```

The commands do not appear in the old CLI help, and no empty or deprecated
placeholder command remains.

## Supporting cleanup

- Removed 17 test methods dedicated to the deleted chains from
  `tests/test_runtime.py`; no test file contained only one of these chains, so
  no test file was deleted.
- Updated the protocol catalog assertion from 192 to 189 schema/example pairs.
- Removed active capability claims from `protocol/SPEC.md`, AntennaPod smoke
  instructions, the Android benchmark description, and related public change
  notes.
- Marked v0.3.0/v0.3.1 inspect-summary evidence as historical rather than
  rewriting history.
- Changed two internal legacy artifact labels from `inspect-summary` to
  `project-inspection`; this did not add or extend behavior.
- Removed the review-import/TM-after-review stage from
  `benchmarks/stress-v01/run.py`.

## Unexpected dependency

One unexpected old-only dependency was found:

```text
benchmarks/stress-v01/run.py
  -> runtime.localize_anything.review.import_review
```

It was not a production or new-core dependency. The dependent benchmark stage
and its option/summary fields were removed while the remaining stress benchmark
was preserved. This was not a deletion blocker.

## Count changes

| Inventory | Before | After | Change |
|---|---:|---:|---:|
| Runtime Python files | 94 | 88 | -6 |
| Protocol schemas | 192 | 189 | -3 |
| Protocol examples | 192 | 189 | -3 |
| Discovered unit tests | 569 | 552 | -17 |
| Test files in migration-map scope | 21 | 21 | 0 |
| Total files deleted in Phase 4.1 | 0 | 13 | +13 removed |

The active migration-map classification at the P4.1 gate was:

| Class | Active files |
|---|---:|
| KEEP | 40 |
| EXTRACT | 63 |
| REPLACE | 67 |
| LEGACY | 20 |
| DELETE | 351 |
| **Total** | **541** |

At that checkpoint, the JSON map retained all 554 originally assessed records.
The consolidated map now records those 13 deleted entries with
`lifecycle: removed_in_p4_1`.

## Validation

| Validation | Result |
|---|---|
| Five-command core and Skill behavior tests | PASS — 7 tests |
| Full unit suite | PASS — 552 tests in 40.859s |
| Protocol validator | PASS — 189 schemas and 189 examples |
| Adapter contract validator | PASS — 12 manifests |
| `compileall` for Runtime, tests, benchmarks, and scripts | PASS |
| Old CLI help audit | PASS — all six removed surfaces absent |
| Deleted-module import audit | PASS — no live imports |
| Active command/artifact reference audit | PASS — no dangling current claims |
| Markdown relative-link audit | PASS for changed/current Phase 4.1 docs |

The repository-wide Markdown audit checked 44 relative links and found one
pre-existing, unrelated broken link in
`benchmarks/v022-android-resource-reliability/v022-final-report.md`. It is
outside this six-chain deletion boundary and was not changed. Remaining
inspect-summary references are limited to CHANGELOG history and historical
reports that now carry an explicit historical-evidence notice.

The first full-suite run correctly exposed one stale hard-coded protocol count
(`192`). After updating it to the new catalog count (`189`), the complete suite
passed.

## Blockers

No Phase 4.1 blocker remains. The old CLI is still a major aggregation point
with 78 Runtime imports, so later batches must continue to remove complete
vertical slices rather than deleting arbitrary shared modules.

## Recommended Phase 4.2 boundary

Start with `runtime/localize_anything/chinese_draft.py`, which became a true
CLI-only DELETE leaf after `android_app_test.py` was removed. Then treat the
Provider platform as one bounded vertical:

```text
provider.py
provider_attempt_semantics.py
provider_consent.py
provider_dry_run.py
provider_evidence.py
provider_mock.py
provider_real_smoke.py
provider_result_gate.py
provider_safety.py
provider_smoke_closure.py
provider_staging.py
```

Remove its CLI/parser/dispatch, protocol pairs, focused tests, and references
from old aggregators in the same batch. Do not include Workbench, readiness,
workflow, Knowledge Pack, or broad protocol cleanup. Keep
`generation.py`, `generation_strategy.py`, and
`generation_handoff_policy.py` out of the first Phase 4.2 cut until their
remaining non-Provider legacy callers are explicitly detached.
