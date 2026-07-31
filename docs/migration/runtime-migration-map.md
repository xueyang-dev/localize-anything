# Runtime Migration Map

> Final Phase 4.7 inventory generated from the filesystem and AST import graph on 2026-07-31.
> Removed paths remain listed so every migration decision is auditable.

## Overall statistics

| Metric | Count |
| --- | ---: |
| Assessed file records | 616 |
| Active files | 105 |
| Removed files | 511 |
| Active Runtime Python files | 24 |
| Unit tests | 56 |
| Protocol schema/example pairs | 7 |
| Adapter manifests | 12 |

Active classification:

| KEEP | EXTRACT | REPLACE | LEGACY | DELETE |
| ---: | ---: | ---: | ---: | ---: |
| 79 | 0 | 0 | 26 | 0 |

All migration records, including removed files:

| KEEP | EXTRACT | REPLACE | LEGACY | DELETE |
| ---: | ---: | ---: | ---: | ---: |
| 79 | 41 | 70 | 39 | 387 |

Lifecycle totals:

| Lifecycle | Files |
| --- | ---: |
| `active` | 105 |
| `removed_in_p4_1` | 13 |
| `removed_in_p4_2` | 128 |
| `removed_in_p4_3` | 14 |
| `removed_in_p4_4` | 175 |
| `removed_in_p4_5` | 99 |
| `removed_in_p4_6` | 1 |
| `removed_in_p4_7` | 81 |

## Final import and call boundary

- Public entrypoint: `localize -> runtime.localize_anything.core_cli:main`.
- The five-command core reaches only focused core modules, seven priority format handlers, `risk_classifier`, `io_utils`, and package metadata.
- `core.py` and `core_cli.py` import zero module classified `LEGACY` or `DELETE`.
- `contracts.py` and `schema_validation.py` are repository validators only; they are not command-execution dependencies.
- No old `localize-anything` console or package `__main__` remains.

Core-reachable modules:

```text
__init__
android_strings_adapter
core
core_cli
core_formats
core_glossary
core_memory
core_preflight
core_segments
gettext_adapter
io_utils
ios_strings_adapter
json_adapter
risk_classifier
structured_adapter
xcstrings_adapter
xliff_adapter
```

Remaining Runtime compatibility modules:

```text
markup_adapter
subtitle_adapter
tabular_adapter
wesnoth_adapter
word_adapter
```

These five handlers remain because their format parsing/rebuild checks have focused tests and bounded practical value. They have no standalone legacy CLI entrypoint and cannot become an automatic fallback.

## First safe deletion candidates

None. Phase 4 removed every currently proven old Runtime island. A future compatibility deletion requires fresh usage evidence; file-name inference is not enough.

## Extraction results

| Order | Capability | Target | Result |
| ---: | --- | --- | --- |
| 1 | Glossary candidates and constraints | `runtime/localize_anything/core_glossary.py` | parity_passed |
| 2 | Project preflight and resource discovery | `runtime/localize_anything/core_preflight.py` | parity_passed |
| 3 | Segment identity, alignment, diff and staleness | `runtime/localize_anything/core_segments.py` | parity_passed |
| 4 | Confirmed terminology, TM, style and decision import | `runtime/localize_anything/core_memory.py` | parity_passed |
| 5 | Android overlay routing and format parsing/validation boundary | `runtime/localize_anything/core_formats.py` | parity_passed |

The old wrappers were removed only after parity coverage passed. No artifact-state, workflow, readiness, evidence, or Knowledge Pack lifecycle was copied into the new modules.

## Dependency blockers

All three original blockers are resolved:

1. The legacy CLI aggregation ended when `cli.py`, `__main__.py`, and the `localize-anything` entrypoint were removed.
2. The monolithic Runtime test suite was reduced to focused core, Skill, format, protocol, and safety tests.
3. The protocol catalog was reduced to seven core contracts; adapter manifests no longer advertise dead CLI entrypoints.

No Phase 4 blocker remains.

## Phase 4 deletion batches

| Phase | Status | Runtime removed | Tests before → after | Protocol pairs before → after |
| --- | --- | ---: | ---: | ---: |
| P4.1 | pass | 6 | 569 → 552 | 192 → 189 |
| P4.2 | pass | 12 | 552 → 470 | 189 → 131 |
| P4.3 | pass | 4 | 470 → 407 | 131 → 126 |
| P4.4 | pass | 19 | 407 → 234 | 126 → 48 |
| P4.5 | pass | 2 | 234 → 222 | 48 → 7 |
| P4.6 | pass | 1 | 222 → 227 | 7 → 7 |
| P4.7 | pass | 31 | 227 → 56 | 7 → 7 |

P4.7 removed 81 tracked paths: 31 Runtime modules, 33 obsolete benchmark runner/fixture paths, and 17 obsolete documentation/script paths. Two Android reliability resources were re-homed under `tests/fixtures/android-reliability/` before the old benchmark tree was removed.

## Classification file lists

### KEEP (79 records; 79 active)

```text
CHANGELOG.md
README.en.md
README.md
adapters/core/android-strings/adapter.json
adapters/core/gettext-po/adapter.json
adapters/core/ios-strings/adapter.json
adapters/core/json-locale/adapter.json
adapters/core/xcstrings/adapter.json
adapters/core/xliff/adapter.json
adapters/core/yaml-toml/adapter.json
docs/adapters.md
docs/architecture-roadmap.md
docs/architecture.md
docs/assets/README.md
docs/assets/logo-localize-anything-transparent.png
docs/decisions/0002-coding-agent-localization-layer.md
docs/product-direction.md
docs/public-claim-reconciliation.md
docs/release-checklist.md
docs/security.md
docs/validation/phase2-live-dry-run.md
protocol/SPEC.md
protocol/examples/deterministic-check.json
protocol/examples/glossary.json
protocol/examples/human-confirmations.json
protocol/examples/independent-review-packet.json
protocol/examples/independent-review.json
protocol/examples/project-memory.json
protocol/examples/report.json
protocol/schemas/deterministic-check.schema.json
protocol/schemas/glossary.schema.json
protocol/schemas/human-confirmations.schema.json
protocol/schemas/independent-review-packet.schema.json
protocol/schemas/independent-review.schema.json
protocol/schemas/project-memory.schema.json
protocol/schemas/report.schema.json
pyproject.toml
runtime/localize_anything/__init__.py
runtime/localize_anything/android_strings_adapter.py
runtime/localize_anything/contracts.py
runtime/localize_anything/core.py
runtime/localize_anything/core_cli.py
runtime/localize_anything/core_formats.py
runtime/localize_anything/core_glossary.py
runtime/localize_anything/core_memory.py
runtime/localize_anything/core_preflight.py
runtime/localize_anything/core_segments.py
runtime/localize_anything/gettext_adapter.py
runtime/localize_anything/io_utils.py
runtime/localize_anything/ios_strings_adapter.py
runtime/localize_anything/json_adapter.py
runtime/localize_anything/risk_classifier.py
runtime/localize_anything/schema_validation.py
runtime/localize_anything/structured_adapter.py
runtime/localize_anything/xcstrings_adapter.py
runtime/localize_anything/xliff_adapter.py
skills/localize-anything/SKILL.md
skills/localize-anything/agents/openai.yaml
skills/localize-anything/references/adapters.md
skills/localize-anything/references/memory-and-context.md
skills/localize-anything/references/qa-and-delivery.md
skills/localize-anything/references/workflow.md
tests/fixtures/android-project/app/src/main/res/values/strings.xml
tests/fixtures/android-reliability/app/src/main/res/values-zh-rCN/strings.xml
tests/fixtures/android-reliability/app/src/main/res/values/strings.xml
tests/fixtures/common-formats/messages-2.xlf
tests/fixtures/common-formats/messages.toml
tests/fixtures/common-formats/messages.xlf
tests/fixtures/common-formats/messages.yaml
tests/fixtures/gettext-wesnoth/messages.pot
tests/fixtures/ios-project/App/en.lproj/Localizable.strings
tests/fixtures/ios-project/App/en.lproj/Localizable.stringsdict
tests/fixtures/json-project/locales/en-US.json
tests/fixtures/json-project/locales/zh-CN.json
tests/fixtures/xcstrings-project/App/Localizable.xcstrings
tests/test_core_capabilities.py
tests/test_core_cli.py
tests/test_runtime.py
tests/test_skill_phase2.py
```

### EXTRACT (41 records; 0 active)

```text
benchmarks/v022-android-resource-reliability/fixture/app/src/main/res/values-zh-rCN/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture/app/src/main/res/values/strings.xml [removed_in_p4_7]
docs/android-coverage-model.md [removed_in_p4_7]
docs/android-merged-resource-overlay.md [removed_in_p4_7]
docs/android-real-project-stress-matrix.md [removed_in_p4_7]
docs/android-v0.2.2-support.md [removed_in_p4_7]
docs/android-v0.2.3-support.md [removed_in_p4_7]
docs/antennapod-smoke-test.md [removed_in_p4_7]
protocol/examples/adapter.json [removed_in_p4_5]
protocol/examples/candidate-term.json [removed_in_p4_5]
protocol/examples/incremental-diff.json [removed_in_p4_5]
protocol/examples/pack.json [removed_in_p4_5]
protocol/examples/reuse-decision.json [removed_in_p4_5]
protocol/examples/segment.json [removed_in_p4_5]
protocol/examples/stale-segments.json [removed_in_p4_5]
protocol/examples/term-decision.json [removed_in_p4_5]
protocol/examples/term-review-decision.json [removed_in_p4_5]
protocol/examples/term-review-queue.json [removed_in_p4_5]
protocol/examples/termbase-preflight-report.json [removed_in_p4_5]
protocol/examples/working-context-packet.json [removed_in_p4_5]
protocol/schemas/adapter.schema.json [removed_in_p4_5]
protocol/schemas/candidate-term.schema.json [removed_in_p4_5]
protocol/schemas/incremental-diff.schema.json [removed_in_p4_5]
protocol/schemas/pack.schema.json [removed_in_p4_5]
protocol/schemas/reuse-decision.schema.json [removed_in_p4_5]
protocol/schemas/segment.schema.json [removed_in_p4_5]
protocol/schemas/stale-segments.schema.json [removed_in_p4_5]
protocol/schemas/term-decision.schema.json [removed_in_p4_5]
protocol/schemas/term-review-decision.schema.json [removed_in_p4_5]
protocol/schemas/term-review-queue.schema.json [removed_in_p4_5]
protocol/schemas/termbase-preflight-report.schema.json [removed_in_p4_5]
protocol/schemas/working-context-packet.schema.json [removed_in_p4_5]
runtime/localize_anything/android_merged_overlay.py [removed_in_p4_7]
runtime/localize_anything/knowledge_consumption.py [removed_in_p4_7]
runtime/localize_anything/knowledge_pack.py [removed_in_p4_7]
runtime/localize_anything/project.py [removed_in_p4_7]
runtime/localize_anything/reference.py [removed_in_p4_7]
runtime/localize_anything/segment_staleness.py [removed_in_p4_7]
runtime/localize_anything/segments.py [removed_in_p4_6]
runtime/localize_anything/term_governance.py [removed_in_p4_7]
runtime/localize_anything/termbase_preflight.py [removed_in_p4_7]
```

### REPLACE (70 records; 0 active)

```text
docs/inspect-summary.md [removed_in_p4_1]
protocol/examples/acceptance.json [removed_in_p4_1]
protocol/examples/agent-summary.json [removed_in_p4_5]
protocol/examples/apply-plan.json [removed_in_p4_5]
protocol/examples/batch-plan.json [removed_in_p4_5]
protocol/examples/blocking-questions.json [removed_in_p4_5]
protocol/examples/delivery-decision.json [removed_in_p4_5]
protocol/examples/delivery-manifest.json [removed_in_p4_5]
protocol/examples/draft-request.json [removed_in_p4_5]
protocol/examples/generation-handoff-decision.json [removed_in_p4_5]
protocol/examples/generation-handoff.json [removed_in_p4_5]
protocol/examples/generation-strategy.json [removed_in_p4_5]
protocol/examples/human-review-evidence.json [removed_in_p4_4]
protocol/examples/llm-review-request.json [removed_in_p4_5]
protocol/examples/llm-review-result.json [removed_in_p4_5]
protocol/examples/localization-brief.json [removed_in_p4_5]
protocol/examples/project-config.json [removed_in_p4_5]
protocol/examples/project-session.json [removed_in_p4_5]
protocol/examples/qa-result.json [removed_in_p4_5]
protocol/examples/resolution-options.json [removed_in_p4_5]
protocol/examples/review-import.json [removed_in_p4_1]
protocol/examples/signoff-record.json [removed_in_p4_4]
protocol/examples/user-resolution-decision.json [removed_in_p4_5]
protocol/examples/work-packet.json [removed_in_p4_5]
protocol/schemas/acceptance.schema.json [removed_in_p4_1]
protocol/schemas/agent-summary.schema.json [removed_in_p4_5]
protocol/schemas/apply-plan.schema.json [removed_in_p4_5]
protocol/schemas/batch-plan.schema.json [removed_in_p4_5]
protocol/schemas/blocking-questions.schema.json [removed_in_p4_5]
protocol/schemas/delivery-decision.schema.json [removed_in_p4_5]
protocol/schemas/delivery-manifest.schema.json [removed_in_p4_5]
protocol/schemas/draft-request.schema.json [removed_in_p4_5]
protocol/schemas/generation-handoff-decision.schema.json [removed_in_p4_5]
protocol/schemas/generation-handoff.schema.json [removed_in_p4_5]
protocol/schemas/generation-strategy.schema.json [removed_in_p4_5]
protocol/schemas/human-review-evidence.schema.json [removed_in_p4_4]
protocol/schemas/llm-review-request.schema.json [removed_in_p4_5]
protocol/schemas/llm-review-result.schema.json [removed_in_p4_5]
protocol/schemas/localization-brief.schema.json [removed_in_p4_5]
protocol/schemas/project-config.schema.json [removed_in_p4_5]
protocol/schemas/project-session.schema.json [removed_in_p4_5]
protocol/schemas/qa-result.schema.json [removed_in_p4_5]
protocol/schemas/resolution-options.schema.json [removed_in_p4_5]
protocol/schemas/review-import.schema.json [removed_in_p4_1]
protocol/schemas/signoff-record.schema.json [removed_in_p4_4]
protocol/schemas/user-resolution-decision.schema.json [removed_in_p4_5]
protocol/schemas/work-packet.schema.json [removed_in_p4_5]
runtime/localize_anything/agent.py [removed_in_p4_7]
runtime/localize_anything/android_app_test.py [removed_in_p4_1]
runtime/localize_anything/apply.py [removed_in_p4_7]
runtime/localize_anything/artifact_state.py [removed_in_p4_7]
runtime/localize_anything/dashboard.py [removed_in_p4_7]
runtime/localize_anything/delivery.py [removed_in_p4_7]
runtime/localize_anything/delivery_decision.py [removed_in_p4_7]
runtime/localize_anything/evaluation.py [removed_in_p4_7]
runtime/localize_anything/generation.py [removed_in_p4_7]
runtime/localize_anything/generation_strategy.py [removed_in_p4_7]
runtime/localize_anything/human_review.py [removed_in_p4_4]
runtime/localize_anything/inspect_summary.py [removed_in_p4_1]
runtime/localize_anything/localization_brief.py [removed_in_p4_7]
runtime/localize_anything/modes.py [removed_in_p4_7]
runtime/localize_anything/planning.py [removed_in_p4_7]
runtime/localize_anything/reflection.py [removed_in_p4_7]
runtime/localize_anything/resolution_gate.py [removed_in_p4_7]
runtime/localize_anything/retrieval.py [removed_in_p4_7]
runtime/localize_anything/review.py [removed_in_p4_1]
runtime/localize_anything/review_sheet.py [removed_in_p4_7]
runtime/localize_anything/segment_repair.py [removed_in_p4_7]
runtime/localize_anything/staging.py [removed_in_p4_7]
scripts/smoke-antennapod.sh [removed_in_p4_7]
```

### LEGACY (39 records; 26 active)

```text
adapters/core/markup/adapter.json
adapters/core/subtitles/adapter.json
adapters/core/tabular/adapter.json
adapters/core/word-document/adapter.json
adapters/scenarios/wesnoth/adapter.json
benchmarks/wesnoth-south-guard/README.md
benchmarks/wesnoth-south-guard/benchmark.json
benchmarks/wesnoth-south-guard/metrics.md
benchmarks/wesnoth-south-guard/prepare.py
benchmarks/wesnoth-south-guard/run-metadata.template.json
benchmarks/wesnoth-south-guard/verify.py
docs/antennapod-smoke-test-results-v0.3.0.md [removed_in_p4_7]
docs/antennapod-smoke-test-results.md [removed_in_p4_7]
docs/architecture-v0.4-legacy.md
docs/assets/architecture-layers.svg [removed_in_p4_7]
docs/assets/benchmark-antennapod.svg [removed_in_p4_7]
docs/assets/delivery-package.svg [removed_in_p4_7]
docs/assets/workflow-dark.svg [removed_in_p4_7]
docs/benchmarking.md
docs/decisions/0001-protocol-first-workflow.md
docs/quickstart-demo.md [removed_in_p4_5]
docs/v0.3.0-real-project-workflow-plan.md [removed_in_p4_7]
docs/v0.3.1-release-audit.md [removed_in_p4_7]
runtime/localize_anything/__main__.py [removed_in_p4_5]
runtime/localize_anything/cli.py [removed_in_p4_5]
runtime/localize_anything/markup_adapter.py
runtime/localize_anything/quickstart_demo.py [removed_in_p4_7]
runtime/localize_anything/run.py [removed_in_p4_7]
runtime/localize_anything/subtitle_adapter.py
runtime/localize_anything/tabular_adapter.py
runtime/localize_anything/wesnoth_adapter.py
runtime/localize_anything/word_adapter.py
tests/fixtures/common-formats/captions.srt
tests/fixtures/common-formats/captions.vtt
tests/fixtures/common-formats/guide.md
tests/fixtures/common-formats/messages.csv
tests/fixtures/common-formats/messages.tsv
tests/fixtures/common-formats/page.html
tests/fixtures/gettext-wesnoth/data/campaigns/The_South_Guard/scenarios/01_Born_to_the_Banner.cfg
```

### DELETE (387 records; 0 active)

```text
benchmarks/android-antennapod/README.md [removed_in_p4_7]
benchmarks/android-antennapod/benchmark.json [removed_in_p4_7]
benchmarks/android-antennapod/run.py [removed_in_p4_7]
benchmarks/ios-icecubes-xcstrings/README.md [removed_in_p4_7]
benchmarks/ios-icecubes-xcstrings/benchmark.json [removed_in_p4_7]
benchmarks/ios-icecubes-xcstrings/run.py [removed_in_p4_7]
benchmarks/ios-signal/README.md [removed_in_p4_7]
benchmarks/ios-signal/benchmark.json [removed_in_p4_7]
benchmarks/ios-signal/run.py [removed_in_p4_7]
benchmarks/stress-v01/README.md [removed_in_p4_7]
benchmarks/stress-v01/run.py [removed_in_p4_7]
benchmarks/v021-mode-system/fixture/app/src/main/res/values-zh-rCN/strings.xml [removed_in_p4_7]
benchmarks/v021-mode-system/fixture/app/src/main/res/values/strings.xml [removed_in_p4_7]
benchmarks/v021-mode-system/run.py [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-risk/app/src/main/res/values/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/debug/res/values/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/free/res/values/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/main/res/values-es/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/main/res/values-fr/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/main/res/values-land/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/main/res/values-mcc310-mnc004-land/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/main/res/values-mcc310-mnc004/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/main/res/values-mcc310-night/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/main/res/values-mcc310/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/main/res/values-night/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/main/res/values-sw600dp/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/main/res/values-zh-rCN/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/fixture-source-sets/app/src/main/res/values/strings.xml [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/risk_classification.py [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/run.py [removed_in_p4_7]
benchmarks/v022-android-resource-reliability/source_sets.py [removed_in_p4_7]
docs/public-introduction-draft.md [removed_in_p4_7]
docs/public-launch-checklist.md [removed_in_p4_7]
protocol/examples/adapter-evidence-gap-report.json [removed_in_p4_4]
protocol/examples/adapter-evidence-provenance.json [removed_in_p4_4]
protocol/examples/adapter-fixture-manifest.json [removed_in_p4_4]
protocol/examples/adapter-promotion-decision.json [removed_in_p4_4]
protocol/examples/adapter-promotion-readiness-report.json [removed_in_p4_4]
protocol/examples/adapter-regression-check-report.json [removed_in_p4_4]
protocol/examples/adapter-regression-evidence-report.json [removed_in_p4_4]
protocol/examples/adapter-release-audit.json [removed_in_p4_4]
protocol/examples/adapter-support-matrix.json [removed_in_p4_4]
protocol/examples/android-app-test-report.json [removed_in_p4_1]
protocol/examples/apply-readiness-report.json [removed_in_p4_4]
protocol/examples/artifact-invalidation-report.json [removed_in_p4_4]
protocol/examples/artifact-state.json [removed_in_p4_5]
protocol/examples/benchmark-baseline-report.json [removed_in_p4_4]
protocol/examples/benchmark-candidate-report.json [removed_in_p4_4]
protocol/examples/benchmark-claim-boundary-report.json [removed_in_p4_4]
protocol/examples/benchmark-comparison-report.json [removed_in_p4_4]
protocol/examples/benchmark-dataset-manifest.json [removed_in_p4_4]
protocol/examples/benchmark-evidence-matrix.json [removed_in_p4_4]
protocol/examples/benchmark-fixture-policy.json [removed_in_p4_4]
protocol/examples/benchmark-reference-boundary-report.json [removed_in_p4_4]
protocol/examples/benchmark-reproducibility-report.json [removed_in_p4_4]
protocol/examples/benchmark-run-manifest.json [removed_in_p4_4]
protocol/examples/claim-acceptance-decision.json [removed_in_p4_4]
protocol/examples/claim-metric-report.json [removed_in_p4_4]
protocol/examples/constraint-application-audit.json [removed_in_p4_4]
protocol/examples/delivery-readiness-report.json [removed_in_p4_4]
protocol/examples/document-claim-resolution.json [removed_in_p4_4]
protocol/examples/document-decision-log.json [removed_in_p4_4]
protocol/examples/document-evidence-manifest.json [removed_in_p4_4]
protocol/examples/document-intake-report.json [removed_in_p4_4]
protocol/examples/document-signoff-summary.json [removed_in_p4_4]
protocol/examples/evaluation-scorecard.json [removed_in_p4_5]
protocol/examples/incremental-workflow-summary.json [removed_in_p4_4]
protocol/examples/knowledge-assurance-summary.json [removed_in_p4_4]
protocol/examples/knowledge-audit-enforcement-decision.json [removed_in_p4_4]
protocol/examples/knowledge-audit-resolution-log.json [removed_in_p4_4]
protocol/examples/knowledge-conflict-report.json [removed_in_p4_5]
protocol/examples/knowledge-conflict-resolution.json [removed_in_p4_4]
protocol/examples/knowledge-constraint-review-evidence.json [removed_in_p4_4]
protocol/examples/knowledge-eligibility-report.json [removed_in_p4_5]
protocol/examples/knowledge-pack-selection.json [removed_in_p4_5]
protocol/examples/knowledge-readiness-impact-report.json [removed_in_p4_4]
protocol/examples/knowledge-recompute-plan.json [removed_in_p4_4]
protocol/examples/knowledge-recompute-result.json [removed_in_p4_4]
protocol/examples/knowledge-repair-closure-decision.json [removed_in_p4_4]
protocol/examples/knowledge-repair-impact-report.json [removed_in_p4_4]
protocol/examples/knowledge-repair-plan.json [removed_in_p4_4]
protocol/examples/knowledge-repair-qa-report.json [removed_in_p4_4]
protocol/examples/knowledge-repair-reconciliation.json [removed_in_p4_4]
protocol/examples/knowledge-repair-request.json [removed_in_p4_4]
protocol/examples/knowledge-repair-result-intake.json [removed_in_p4_4]
protocol/examples/knowledge-review-decision.json [removed_in_p4_4]
protocol/examples/knowledge-review-queue.json [removed_in_p4_4]
protocol/examples/knowledge-usage-report.json [removed_in_p4_4]
protocol/examples/leadership-review-evidence.json [removed_in_p4_4]
protocol/examples/locale-capability-report.json [removed_in_p4_5]
protocol/examples/locale-readiness-impact.json [removed_in_p4_5]
protocol/examples/locale-risk-report.json [removed_in_p4_5]
protocol/examples/manual-followup-gap-report.json [removed_in_p4_4]
protocol/examples/provenance-coverage-report.json [removed_in_p4_5]
protocol/examples/provider-attempt-semantics-report.json [removed_in_p4_2]
protocol/examples/provider-attempt-type-normalization.json [removed_in_p4_2]
protocol/examples/provider-claim-support-report.json [removed_in_p4_2]
protocol/examples/provider-consent-action.json [removed_in_p4_2]
protocol/examples/provider-consent-audit-record.json [removed_in_p4_2]
protocol/examples/provider-consent-resolution-report.json [removed_in_p4_2]
protocol/examples/provider-consent-scope-diff.json [removed_in_p4_2]
protocol/examples/provider-credential-policy-report.json [removed_in_p4_2]
protocol/examples/provider-data-disclosure-report.json [removed_in_p4_2]
protocol/examples/provider-dry-run-plan.json [removed_in_p4_2]
protocol/examples/provider-evidence-reconciliation.json [removed_in_p4_2]
protocol/examples/provider-execution-attempt-ledger.json [removed_in_p4_2]
protocol/examples/provider-execution-attempt-summary.json [removed_in_p4_2]
protocol/examples/provider-execution-authorization-decision.json [removed_in_p4_2]
protocol/examples/provider-execution-consent-state.json [removed_in_p4_2]
protocol/examples/provider-execution-evidence-classification.json [removed_in_p4_2]
protocol/examples/provider-execution-ledger.json [removed_in_p4_2]
protocol/examples/provider-execution-policy.json [removed_in_p4_2]
protocol/examples/provider-execution-preflight-gate.json [removed_in_p4_2]
protocol/examples/provider-execution-readiness-report.json [removed_in_p4_2]
protocol/examples/provider-execution-safety-decision.json [removed_in_p4_2]
protocol/examples/provider-failure-taxonomy.json [removed_in_p4_2]
protocol/examples/provider-handoff-request.json [removed_in_p4_2]
protocol/examples/provider-ledger-semantic-migration-report.json [removed_in_p4_2]
protocol/examples/provider-mock-claim-boundary.json [removed_in_p4_2]
protocol/examples/provider-mock-evidence-report.json [removed_in_p4_2]
protocol/examples/provider-mock-failure-report.json [removed_in_p4_2]
protocol/examples/provider-mock-response.json [removed_in_p4_2]
protocol/examples/provider-mock-run-manifest.json [removed_in_p4_2]
protocol/examples/provider-network-boundary-report.json [removed_in_p4_2]
protocol/examples/provider-real-execution-blockers.json [removed_in_p4_2]
protocol/examples/provider-real-smoke-acceptance-criteria.json [removed_in_p4_2]
protocol/examples/provider-real-smoke-admission-audit.json [removed_in_p4_2]
protocol/examples/provider-real-smoke-claim-review.json [removed_in_p4_2]
protocol/examples/provider-real-smoke-evidence-review.json [removed_in_p4_2]
protocol/examples/provider-real-smoke-evidence-template.json [removed_in_p4_2]
protocol/examples/provider-real-smoke-expansion-decision.json [removed_in_p4_2]
protocol/examples/provider-real-smoke-fixture-manifest.json [removed_in_p4_2]
protocol/examples/provider-real-smoke-ledger-audit.json [removed_in_p4_2]
protocol/examples/provider-real-smoke-plan.json [removed_in_p4_2]
protocol/examples/provider-real-smoke-safety-checklist.json [removed_in_p4_2]
protocol/examples/provider-redaction-audit.json [removed_in_p4_2]
protocol/examples/provider-result-acceptance-decision.json [removed_in_p4_2]
protocol/examples/provider-result-acceptance-policy.json [removed_in_p4_2]
protocol/examples/provider-result-intake.json [removed_in_p4_2]
protocol/examples/provider-result-qa-report.json [removed_in_p4_2]
protocol/examples/provider-result-quarantine-report.json [removed_in_p4_2]
protocol/examples/provider-result-review-evidence.json [removed_in_p4_2]
protocol/examples/provider-result-staging-admission.json [removed_in_p4_2]
protocol/examples/provider-result-staging-manifest.json [removed_in_p4_2]
protocol/examples/provider-smoke-closure-report.json [removed_in_p4_2]
protocol/examples/provider-smoke-evidence-manifest.json [removed_in_p4_2]
protocol/examples/provider-smoke-ledger-linkage-report.json [removed_in_p4_2]
protocol/examples/provider-smoke-next-step-decision.json [removed_in_p4_2]
protocol/examples/provider-smoke-release-boundary-audit.json [removed_in_p4_2]
protocol/examples/provider-smoke-remaining-blockers.json [removed_in_p4_2]
protocol/examples/provider-staging-claim-boundary.json [removed_in_p4_2]
protocol/examples/public-claims-report.json [removed_in_p4_4]
protocol/examples/publicity-risk-report.json [removed_in_p4_4]
protocol/examples/readiness-authorization-matrix.json [removed_in_p4_4]
protocol/examples/release-blockers.json [removed_in_p4_4]
protocol/examples/release-evidence-manifest.json [removed_in_p4_4]
protocol/examples/release-readiness-audit.json [removed_in_p4_4]
protocol/examples/repair-history.json [removed_in_p4_5]
protocol/examples/repair-request.json [removed_in_p4_5]
protocol/examples/repair-result.json [removed_in_p4_5]
protocol/examples/segment-evidence-view.json [removed_in_p4_5]
protocol/examples/segment-regeneration-plan.json [removed_in_p4_5]
protocol/examples/selective-recompute-plan.json [removed_in_p4_4]
protocol/examples/selective-recompute-result.json [removed_in_p4_4]
protocol/examples/semantic-alignment.json [removed_in_p4_5]
protocol/examples/translation-claim-provenance-report.json [removed_in_p4_5]
protocol/examples/translation-provenance.json [removed_in_p4_5]
protocol/examples/workbench-action-log.json [removed_in_p4_3]
protocol/examples/workbench-action-result.json [removed_in_p4_3]
protocol/examples/workbench-claim-queue.json [removed_in_p4_3]
protocol/examples/workbench-document-evidence-queue.json [removed_in_p4_4]
protocol/examples/workbench-knowledge-review-queue.json [removed_in_p4_4]
protocol/examples/workbench-provider-review-queue.json [removed_in_p4_2]
protocol/examples/workbench-readiness-action-log.json [removed_in_p4_4]
protocol/examples/workbench-readiness-action-queue.json [removed_in_p4_4]
protocol/examples/workbench-readiness-action-result.json [removed_in_p4_4]
protocol/examples/workbench-review-queue.json [removed_in_p4_3]
protocol/examples/workbench-signoff-summary.json [removed_in_p4_3]
protocol/examples/workflow-checkpoint-log.json [removed_in_p4_4]
protocol/examples/workflow-dependency-graph.json [removed_in_p4_4]
protocol/examples/workflow-execution-result.json [removed_in_p4_4]
protocol/examples/workflow-idempotency-report.json [removed_in_p4_4]
protocol/examples/workflow-lock-state.json [removed_in_p4_4]
protocol/examples/workflow-readiness-summary.json [removed_in_p4_4]
protocol/examples/workflow-recovery-plan.json [removed_in_p4_4]
protocol/examples/workflow-recovery-result.json [removed_in_p4_4]
protocol/examples/workflow-resume-plan.json [removed_in_p4_4]
protocol/examples/workflow-run-plan.json [removed_in_p4_4]
protocol/examples/workflow-stage-status.json [removed_in_p4_4]
protocol/examples/workflow-transaction-manifest.json [removed_in_p4_4]
protocol/schemas/adapter-evidence-gap-report.schema.json [removed_in_p4_4]
protocol/schemas/adapter-evidence-provenance.schema.json [removed_in_p4_4]
protocol/schemas/adapter-fixture-manifest.schema.json [removed_in_p4_4]
protocol/schemas/adapter-promotion-decision.schema.json [removed_in_p4_4]
protocol/schemas/adapter-promotion-readiness-report.schema.json [removed_in_p4_4]
protocol/schemas/adapter-regression-check-report.schema.json [removed_in_p4_4]
protocol/schemas/adapter-regression-evidence-report.schema.json [removed_in_p4_4]
protocol/schemas/adapter-release-audit.schema.json [removed_in_p4_4]
protocol/schemas/adapter-support-matrix.schema.json [removed_in_p4_4]
protocol/schemas/android-app-test-report.schema.json [removed_in_p4_1]
protocol/schemas/apply-readiness-report.schema.json [removed_in_p4_4]
protocol/schemas/artifact-invalidation-report.schema.json [removed_in_p4_4]
protocol/schemas/artifact-state.schema.json [removed_in_p4_5]
protocol/schemas/benchmark-baseline-report.schema.json [removed_in_p4_4]
protocol/schemas/benchmark-candidate-report.schema.json [removed_in_p4_4]
protocol/schemas/benchmark-claim-boundary-report.schema.json [removed_in_p4_4]
protocol/schemas/benchmark-comparison-report.schema.json [removed_in_p4_4]
protocol/schemas/benchmark-dataset-manifest.schema.json [removed_in_p4_4]
protocol/schemas/benchmark-evidence-matrix.schema.json [removed_in_p4_4]
protocol/schemas/benchmark-fixture-policy.schema.json [removed_in_p4_4]
protocol/schemas/benchmark-reference-boundary-report.schema.json [removed_in_p4_4]
protocol/schemas/benchmark-reproducibility-report.schema.json [removed_in_p4_4]
protocol/schemas/benchmark-run-manifest.schema.json [removed_in_p4_4]
protocol/schemas/claim-acceptance-decision.schema.json [removed_in_p4_4]
protocol/schemas/claim-metric-report.schema.json [removed_in_p4_4]
protocol/schemas/constraint-application-audit.schema.json [removed_in_p4_4]
protocol/schemas/delivery-readiness-report.schema.json [removed_in_p4_4]
protocol/schemas/document-claim-resolution.schema.json [removed_in_p4_4]
protocol/schemas/document-decision-log.schema.json [removed_in_p4_4]
protocol/schemas/document-evidence-manifest.schema.json [removed_in_p4_4]
protocol/schemas/document-intake-report.schema.json [removed_in_p4_4]
protocol/schemas/document-signoff-summary.schema.json [removed_in_p4_4]
protocol/schemas/evaluation-scorecard.schema.json [removed_in_p4_5]
protocol/schemas/incremental-workflow-summary.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-assurance-summary.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-audit-enforcement-decision.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-audit-resolution-log.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-conflict-report.schema.json [removed_in_p4_5]
protocol/schemas/knowledge-conflict-resolution.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-constraint-review-evidence.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-eligibility-report.schema.json [removed_in_p4_5]
protocol/schemas/knowledge-pack-selection.schema.json [removed_in_p4_5]
protocol/schemas/knowledge-readiness-impact-report.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-recompute-plan.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-recompute-result.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-repair-closure-decision.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-repair-impact-report.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-repair-plan.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-repair-qa-report.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-repair-reconciliation.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-repair-request.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-repair-result-intake.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-review-decision.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-review-queue.schema.json [removed_in_p4_4]
protocol/schemas/knowledge-usage-report.schema.json [removed_in_p4_4]
protocol/schemas/leadership-review-evidence.schema.json [removed_in_p4_4]
protocol/schemas/locale-capability-report.schema.json [removed_in_p4_5]
protocol/schemas/locale-readiness-impact.schema.json [removed_in_p4_5]
protocol/schemas/locale-risk-report.schema.json [removed_in_p4_5]
protocol/schemas/manual-followup-gap-report.schema.json [removed_in_p4_4]
protocol/schemas/provenance-coverage-report.schema.json [removed_in_p4_5]
protocol/schemas/provider-attempt-semantics-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-attempt-type-normalization.schema.json [removed_in_p4_2]
protocol/schemas/provider-claim-support-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-consent-action.schema.json [removed_in_p4_2]
protocol/schemas/provider-consent-audit-record.schema.json [removed_in_p4_2]
protocol/schemas/provider-consent-resolution-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-consent-scope-diff.schema.json [removed_in_p4_2]
protocol/schemas/provider-credential-policy-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-data-disclosure-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-dry-run-plan.schema.json [removed_in_p4_2]
protocol/schemas/provider-evidence-reconciliation.schema.json [removed_in_p4_2]
protocol/schemas/provider-execution-attempt-ledger.schema.json [removed_in_p4_2]
protocol/schemas/provider-execution-attempt-summary.schema.json [removed_in_p4_2]
protocol/schemas/provider-execution-authorization-decision.schema.json [removed_in_p4_2]
protocol/schemas/provider-execution-consent-state.schema.json [removed_in_p4_2]
protocol/schemas/provider-execution-evidence-classification.schema.json [removed_in_p4_2]
protocol/schemas/provider-execution-ledger.schema.json [removed_in_p4_2]
protocol/schemas/provider-execution-policy.schema.json [removed_in_p4_2]
protocol/schemas/provider-execution-preflight-gate.schema.json [removed_in_p4_2]
protocol/schemas/provider-execution-readiness-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-execution-safety-decision.schema.json [removed_in_p4_2]
protocol/schemas/provider-failure-taxonomy.schema.json [removed_in_p4_2]
protocol/schemas/provider-handoff-request.schema.json [removed_in_p4_2]
protocol/schemas/provider-ledger-semantic-migration-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-mock-claim-boundary.schema.json [removed_in_p4_2]
protocol/schemas/provider-mock-evidence-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-mock-failure-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-mock-response.schema.json [removed_in_p4_2]
protocol/schemas/provider-mock-run-manifest.schema.json [removed_in_p4_2]
protocol/schemas/provider-network-boundary-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-real-execution-blockers.schema.json [removed_in_p4_2]
protocol/schemas/provider-real-smoke-acceptance-criteria.schema.json [removed_in_p4_2]
protocol/schemas/provider-real-smoke-admission-audit.schema.json [removed_in_p4_2]
protocol/schemas/provider-real-smoke-claim-review.schema.json [removed_in_p4_2]
protocol/schemas/provider-real-smoke-evidence-review.schema.json [removed_in_p4_2]
protocol/schemas/provider-real-smoke-evidence-template.schema.json [removed_in_p4_2]
protocol/schemas/provider-real-smoke-expansion-decision.schema.json [removed_in_p4_2]
protocol/schemas/provider-real-smoke-fixture-manifest.schema.json [removed_in_p4_2]
protocol/schemas/provider-real-smoke-ledger-audit.schema.json [removed_in_p4_2]
protocol/schemas/provider-real-smoke-plan.schema.json [removed_in_p4_2]
protocol/schemas/provider-real-smoke-safety-checklist.schema.json [removed_in_p4_2]
protocol/schemas/provider-redaction-audit.schema.json [removed_in_p4_2]
protocol/schemas/provider-result-acceptance-decision.schema.json [removed_in_p4_2]
protocol/schemas/provider-result-acceptance-policy.schema.json [removed_in_p4_2]
protocol/schemas/provider-result-intake.schema.json [removed_in_p4_2]
protocol/schemas/provider-result-qa-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-result-quarantine-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-result-review-evidence.schema.json [removed_in_p4_2]
protocol/schemas/provider-result-staging-admission.schema.json [removed_in_p4_2]
protocol/schemas/provider-result-staging-manifest.schema.json [removed_in_p4_2]
protocol/schemas/provider-smoke-closure-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-smoke-evidence-manifest.schema.json [removed_in_p4_2]
protocol/schemas/provider-smoke-ledger-linkage-report.schema.json [removed_in_p4_2]
protocol/schemas/provider-smoke-next-step-decision.schema.json [removed_in_p4_2]
protocol/schemas/provider-smoke-release-boundary-audit.schema.json [removed_in_p4_2]
protocol/schemas/provider-smoke-remaining-blockers.schema.json [removed_in_p4_2]
protocol/schemas/provider-staging-claim-boundary.schema.json [removed_in_p4_2]
protocol/schemas/public-claims-report.schema.json [removed_in_p4_4]
protocol/schemas/publicity-risk-report.schema.json [removed_in_p4_4]
protocol/schemas/readiness-authorization-matrix.schema.json [removed_in_p4_4]
protocol/schemas/release-blockers.schema.json [removed_in_p4_4]
protocol/schemas/release-evidence-manifest.schema.json [removed_in_p4_4]
protocol/schemas/release-readiness-audit.schema.json [removed_in_p4_4]
protocol/schemas/repair-history.schema.json [removed_in_p4_5]
protocol/schemas/repair-request.schema.json [removed_in_p4_5]
protocol/schemas/repair-result.schema.json [removed_in_p4_5]
protocol/schemas/segment-evidence-view.schema.json [removed_in_p4_5]
protocol/schemas/segment-regeneration-plan.schema.json [removed_in_p4_5]
protocol/schemas/selective-recompute-plan.schema.json [removed_in_p4_4]
protocol/schemas/selective-recompute-result.schema.json [removed_in_p4_4]
protocol/schemas/semantic-alignment.schema.json [removed_in_p4_5]
protocol/schemas/translation-claim-provenance-report.schema.json [removed_in_p4_5]
protocol/schemas/translation-provenance.schema.json [removed_in_p4_5]
protocol/schemas/workbench-action-log.schema.json [removed_in_p4_3]
protocol/schemas/workbench-action-result.schema.json [removed_in_p4_3]
protocol/schemas/workbench-claim-queue.schema.json [removed_in_p4_3]
protocol/schemas/workbench-document-evidence-queue.schema.json [removed_in_p4_4]
protocol/schemas/workbench-knowledge-review-queue.schema.json [removed_in_p4_4]
protocol/schemas/workbench-provider-review-queue.schema.json [removed_in_p4_2]
protocol/schemas/workbench-readiness-action-log.schema.json [removed_in_p4_4]
protocol/schemas/workbench-readiness-action-queue.schema.json [removed_in_p4_4]
protocol/schemas/workbench-readiness-action-result.schema.json [removed_in_p4_4]
protocol/schemas/workbench-review-queue.schema.json [removed_in_p4_3]
protocol/schemas/workbench-signoff-summary.schema.json [removed_in_p4_3]
protocol/schemas/workflow-checkpoint-log.schema.json [removed_in_p4_4]
protocol/schemas/workflow-dependency-graph.schema.json [removed_in_p4_4]
protocol/schemas/workflow-execution-result.schema.json [removed_in_p4_4]
protocol/schemas/workflow-idempotency-report.schema.json [removed_in_p4_4]
protocol/schemas/workflow-lock-state.schema.json [removed_in_p4_4]
protocol/schemas/workflow-readiness-summary.schema.json [removed_in_p4_4]
protocol/schemas/workflow-recovery-plan.schema.json [removed_in_p4_4]
protocol/schemas/workflow-recovery-result.schema.json [removed_in_p4_4]
protocol/schemas/workflow-resume-plan.schema.json [removed_in_p4_4]
protocol/schemas/workflow-run-plan.schema.json [removed_in_p4_4]
protocol/schemas/workflow-stage-status.schema.json [removed_in_p4_4]
protocol/schemas/workflow-transaction-manifest.schema.json [removed_in_p4_4]
runtime/localize_anything/acceptance.py [removed_in_p4_1]
runtime/localize_anything/adapter_evidence.py [removed_in_p4_4]
runtime/localize_anything/adapter_release.py [removed_in_p4_4]
runtime/localize_anything/benchmark_lab.py [removed_in_p4_4]
runtime/localize_anything/chinese_draft.py [removed_in_p4_2]
runtime/localize_anything/deepseek_provider.py [removed_in_p4_1]
runtime/localize_anything/document_decision.py [removed_in_p4_4]
runtime/localize_anything/document_evidence.py [removed_in_p4_4]
runtime/localize_anything/document_evidence_queue.py [removed_in_p4_4]
runtime/localize_anything/generation_handoff_policy.py [removed_in_p4_7]
runtime/localize_anything/knowledge_audit_enforcement.py [removed_in_p4_4]
runtime/localize_anything/knowledge_repair.py [removed_in_p4_4]
runtime/localize_anything/knowledge_repair_closure.py [removed_in_p4_4]
runtime/localize_anything/knowledge_repair_result.py [removed_in_p4_4]
runtime/localize_anything/knowledge_review_confirmation.py [removed_in_p4_4]
runtime/localize_anything/knowledge_usage.py [removed_in_p4_4]
runtime/localize_anything/locale_capability.py [removed_in_p4_7]
runtime/localize_anything/mo_compiler.py [removed_in_p4_1]
runtime/localize_anything/provider.py [removed_in_p4_2]
runtime/localize_anything/provider_attempt_semantics.py [removed_in_p4_2]
runtime/localize_anything/provider_consent.py [removed_in_p4_2]
runtime/localize_anything/provider_dry_run.py [removed_in_p4_2]
runtime/localize_anything/provider_evidence.py [removed_in_p4_2]
runtime/localize_anything/provider_mock.py [removed_in_p4_2]
runtime/localize_anything/provider_real_smoke.py [removed_in_p4_2]
runtime/localize_anything/provider_result_gate.py [removed_in_p4_2]
runtime/localize_anything/provider_safety.py [removed_in_p4_2]
runtime/localize_anything/provider_smoke_closure.py [removed_in_p4_2]
runtime/localize_anything/provider_staging.py [removed_in_p4_2]
runtime/localize_anything/readiness_action.py [removed_in_p4_4]
runtime/localize_anything/readiness_authorization.py [removed_in_p4_4]
runtime/localize_anything/release_audit.py [removed_in_p4_4]
runtime/localize_anything/translation_provenance.py [removed_in_p4_7]
runtime/localize_anything/ui.py [removed_in_p4_3]
runtime/localize_anything/workbench_action.py [removed_in_p4_3]
runtime/localize_anything/workbench_console.py [removed_in_p4_3]
runtime/localize_anything/workbench_queue.py [removed_in_p4_3]
runtime/localize_anything/workflow.py [removed_in_p4_4]
runtime/localize_anything/workflow_hardening.py [removed_in_p4_4]
runtime/localize_anything/workflow_incremental.py [removed_in_p4_4]
```

## Phase 4 completion

Phase 4 is complete. The repository now contains the five-command Agent-native core, seven core protocol pairs, focused deterministic format QA, confirmed-memory import, and five explicitly bounded compatibility handlers.

The next step is real-project product validation and focused fixes for demonstrated gaps—not another broad deletion or a replacement platform.

The machine-readable per-file record is [runtime-migration-map.json](runtime-migration-map.json).
