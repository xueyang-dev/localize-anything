# Localize Anything Phase 5 Stabilization Report

Date: 2026-07-31
Decision: **release_candidate_with_limitations**
Commits: five local semantic commits; not pushed or published

## Scope and safety checkpoint

Phase 5 did not delete Runtime code or extend `core.py`. The existing Phase 4
work was split into these local commits:

1. `63b83f3` — five-command core, contracts, adapters, and focused tests.
2. `7f4cfbe` — legacy Runtime and protocol platform removal.
3. `e69e3cb` — obsolete benchmark and platform-artifact cleanup.
4. `8b5d169` — README, Skill, architecture, and public-surface alignment.
5. `0ffae69` — Phase 4 migration and validation records.

The source worktree is clean apart from the three Phase 5 validation documents
being added by this report commit. No project output, temporary run directory,
or target-application content was added to the repository.

## Clean installation

A fresh clone was created outside the repository at
`/tmp/localize-anything-phase5-CFcNFW/repo` with a new virtual environment.
The package was installed as a wheel with `pip install --no-deps .`; the
developer environment and uncommitted files were not used.

| Gate | Result |
| --- | --- |
| package metadata | pass — `localize-anything 0.4.1` |
| package runtime data | pass — core and all bounded handler modules present; repository-only catalogs remain validation assets |
| console entrypoint | pass — only `localize = runtime.localize_anything.core_cli:main` |
| `localize --help` | pass — only `scan`, `glossary`, `check`, `review`, `report` |
| deleted module import audit | pass — `provider`, `chinese_draft`, and old `cli` resolve to no module |
| clean-clone unit suite | pass — 56 tests |
| minimal five-command flow | pass — scan → glossary → check → review → report |

The clean-install JSON flow also verified that a report stays
`needs_human_confirmation` before an open finding is confirmed and becomes
`ready` only after the exact finding is confirmed.

## Capability coverage

The full matrix is in
[core-capability-matrix.md](core-capability-matrix.md) and
[core-capability-matrix.json](core-capability-matrix.json).

| Status | Count |
| --- | ---: |
| covered | 19 |
| partially_covered | 4 |
| uncovered | 0 |
| intentionally_unsupported | 0 |

Partial coverage is deliberate and bounded: conservative Glossary candidate
heuristics, product-concept Glossary quality, optional full YAML syntax, and
the extract-only Wesnoth compatibility handler.

## Fixed-slice project validation

These are fixed resource slices copied into the clean-clone temporary area,
not claims of complete localization for the upstream applications.

| Slice | Resource scope and native validation | Scan / locale | Glossary | Check findings | Review / confirmation | Final report |
| --- | --- | --- | --- | --- | --- | --- |
| Web/JSON (`examples/quickstart-json`) | `locales/en-US.json` → `locales/ru-RU.json`; `python -m json.tool` pass | pass; `en-US → ru-RU` | candidate 0; canonical file written | blocking 0; actionable warning 0; coverage limitation: structural checks do not judge meaning; known warning 0 | 1 human finding; pending gate then exact confirmation | `ready`; no false-ready |
| Android (`tests/fixtures/android-project`) | `values/strings.xml` → `values-ru/strings.xml`; `xmllint --noout` pass | pass; `en → ru` | candidate 0; canonical file written | blocking 0; actionable warning 0; coverage limitation: semantic review; known/expected info 1 (`translatable=false`) | 1 auto-cleared finding; no confirmation required | `needs_attention`; no false-ready |
| Apple (`tests/fixtures/ios-project`) | `en.lproj/Localizable.strings` → `ru.lproj/Localizable.strings`; `plutil -lint` pass | pass; `en → ru` | candidate 0; canonical file written | blocking 0; actionable warning 0; coverage limitation: structural checks do not judge meaning; known warning 0 | 1 human finding; pending gate then exact confirmation | `ready`; no false-ready |

Each slice followed:

```text
scan → glossary bootstrap → Coding Agent resource edit
     → project-native validation → check → review → report
```

No old CLI, Provider, Workbench, readiness, workflow, Knowledge Pack, or
signoff path was called. No product code was changed for these validations.

## Compatibility Adapter audit

The five retained Python compatibility handlers have no public CLI entrypoint,
no automatic fallback from the core, and are imported directly only when
explicitly requested. Their independent checks passed:

| Adapter | Test state | Boundary |
| --- | --- | --- |
| `markup_adapter` | pass — Markdown/HTML parse/round-trip | explicit handler; no automatic fallback |
| `subtitle_adapter` | pass — SRT/WebVTT parse/round-trip | explicit handler; playback review remains external |
| `tabular_adapter` | pass — CSV/TSV/XLSX round-trip | explicit locale-table convention |
| `wesnoth_adapter` | pass — WML context validation | extract-only compatibility boundary |
| `word_adapter` | pass — DOCX/DOTX/DOCM/DOTM round-trip tests | explicit handler; rendered layout remains external |

The core import graph contains none of these five compatibility modules.
Adapter manifests contain no removed Python CLI entrypoints.

## Release assessment

There is no P0 defect, false-ready result, or deletion regression in this
validation. The open limitations are product-boundary items, not hidden old
Runtime dependencies.

### Before a production release

- Run the same flow against at least one real application with a native build,
  test, locale switch, and fallback path; the Phase 5 slices intentionally do
  not contain Gradle, Xcode, or Node build projects.
- Exercise Glossary bootstrap on a project with repeated product concepts and
  manually inspect candidate precision.
- Decide whether release CI should install the optional `yaml` extra when
  claiming full YAML syntax validation.

### Safe for later iteration

- Broaden real-project coverage and screenshot/UX review.
- Improve candidate-term ranking only when real projects demonstrate a review
  cost problem.
- Revisit the five compatibility handlers only with evidence of actual use.

## Phase 5 decision

**release_candidate_with_limitations**. The clean package is installable, the
five-command path is stable, the finding/confirmation gate is real, and all
current capability claims have tests or explicit boundaries. The next step is
new-core product capability iteration plus real application build/test
validation; no further broad Runtime deletion is recommended.
