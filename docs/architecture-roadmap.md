# Architecture Roadmap

This roadmap follows the accepted [Product Direction](product-direction.md)
and [current architecture](architecture.md).

## Convergence Status

The deletion-first migration is complete through Phase 4.7:

- Phase 1 established the provider-free five-command core.
- Phase 2 moved the Skill default path to those commands and validated it on
  Documenso.
- Phase 3 classified the old Runtime from actual imports and callers.
- Phase 4.1 removed the first six CLI-only leaves.
- Phase 4.2 removed `chinese_draft` and the Provider platform.
- Phase 4.3 removed Workbench and Web UI.
- Phase 4.4 removed readiness, workflow, signoff, release/document governance,
  Benchmark Lab, adapter promotion, and knowledge repair/audit systems.
- Phase 4.5 removed the old CLI and reduced the protocol to seven core
  contracts.
- Phase 4.6 extracted glossary, preflight, segment, confirmed-memory-import,
  and format-boundary capabilities into focused modules.
- Phase 4.7 removed the remaining generation/delivery/retrieval/repair island,
  dead benchmark runners, tests, fixtures, entrypoints, and active claims.

The active product surface is now:

```text
localize scan
localize glossary bootstrap
localize check
localize review
localize report
```

## Stabilization and Release Preparation

Phase 5 clean-install and multi-format evidence, followed by the Phase 6
Documenso Russian release acceptance and Phase 6.1 blocker attribution, now
support the first agent-native core release candidate. The remaining target
application Google Vertex type error is pre-existing in Documenso; it is not a
Localize Anything core dependency. Phase 7 is release preparation only:
versioning, packaging, documentation, migration guidance, and clean wheel
verification.

## Next Product Work

Further work must improve a real Agent localization task, not recreate the
removed platform. The dependency order is:

### Phase A: Canonical Definition Alignment

Status: completed for this alignment pass through ADR 0003 and the current
documentation sync.

Exit criteria:

- "Anything" is defined as surface-aware discovery, routing, enablement
  planning, and unsupported-surface reporting.
- Localization Surface is a first-class architecture concept.
- Structured code catalogs and inline code strings are distinct boundaries.
- Public claims, README, Skill guidance, adapter docs, benchmarking, and this
  roadmap no longer imply universal mutation or programming-language support.

### Phase B: State Truth And Evidence Integrity

Status: completed for the old platform risk.

Phase 4.3 removed Workbench and Web UI. Phase 4.4 removed readiness, workflow,
signoff, claim acceptance, and release governance. Phase 4.5 reduced the
protocol to seven current contracts. The current five-command core has no
historical-run projection path, no Workbench fallback, and no UI-derived
business status.

Exit criteria for future changes:

- missing artifact, parse error, network error, and not-run states remain
  distinct;
- readiness/report state comes from same-run current artifacts;
- no UI or helper infers business status outside protocol evidence.

### Phase C: Universal Surface Discovery

Status: partially completed - scan now produces
`source-surface-inventory.json` and `capability-report.json`; discovery of the
remaining surface classes (templates, inline strings, dynamic content,
non-text assets, binary resources) is still planned.

Extend project inspection as read-only first. It must identify standard
resource catalogs, structured source-code catalog candidates, inline string
candidates, templates, dynamic content entry points, non-text assets, binary or
unknown resources, and unsupported surfaces.

Exit criteria:

- produce `source-surface-inventory.json` - completed;
- produce `capability-report.json` - completed;
- include unhandled surfaces in coverage impact - completed;
- do not mutate source code - completed;
- discover and classify template, inline-string, dynamic-content, non-text and
  binary surfaces - planned.

### Phase C.5: Project-Local Adapter Runtime Boundary

Status: completed for the generic extract-only boundary.

Completed:

- source surface inventory during scan;
- capability report with selected adapter and blocked phases;
- explicit project-local adapter selection (`scan --adapter`);
- extract-only adapter execution through a centralized runner;
- canonical artifact ingestion (inventory, source validation, extracted
  segments, deterministic check);
- adapter freshness gate covering descriptor, entrypoint, and the full payload
  fingerprint;
- fail-closed unsupported surfaces before Project Memory and review.

Still planned / backlog:

- built-in Swift typed catalog support;
- editable round trip;
- apply / rebuild phases;
- OS-level sandbox;
- streaming output cap (current stdout limit is post-process);
- whole-process-tree timeout cleanup;
- generalized adapter dependency contract.

### Phase D: Vorssaint Inspect-Only Vertical Slice

Status: validated as an extract-only project-local adapter runtime slice;
inspect-only scope and generic Swift support remain planned.

Use Vorssaint only to validate `code_embedded_catalog` and project-local adapter
contracts for a typed Swift constructor catalog. It is not generic Swift
support.

Exit criteria:

- detect the language enum, supported languages, `Strings` definition, locale
  implementations, feature-specific string files, and `Info.plist`
  localization declarations;
- compute per-locale field coverage and missing/duplicate/extra fields;
- generate stable segment IDs with source file, type name, parameter labels,
  and context;
- perform no source mutation.

### Phase E: Safe Code-Catalog Rebuild

Status: planned after inspect evidence.

Add staged source patching only with AST/parser support, syntax validation,
build validation, exact diff scope, apply plan, backup/rollback evidence, and
no-unrelated-code-change verification.

Exit criteria:

- rebuild only to staging by default;
- validate interpolation and escape preservation;
- run syntax/build commands declared by the adapter or project;
- require explicit apply confirmation and rollback evidence.

### Phase F: Generic Extraction

Status: deferred.

Only after multiple independent Swift projects prove a shared structure should
the project evaluate a generic `format.swift-static-catalog` adapter. Do not
name a project-local vertical slice `core.swift`.

### Later Surface Ecosystem

Future coverage should be organized by surface and platform, not by a flat list
of file extensions:

- Web framework localization;
- Flutter and React Native;
- `.resx` / XAML;
- Qt;
- Java ResourceBundle;
- Unity, Godot, Unreal, and Ren'Py;
- iOS storyboard/xib;
- documents and publishing;
- image text;
- subtitle, audio, and video;
- runtime CMS/API content;
- visual QA;
- build, launch, and runtime-surface verification;
- connector-based dynamic content localization.

None of these are current stable support claims.

## Non-Goals

Do not reintroduce:

- Provider execution or a model marketplace;
- Workbench or queue UI;
- workflow orchestration, resume/recovery, locks, or idempotency products;
- readiness matrices, signoff, claim acceptance, or release governance;
- Knowledge Pack as a user-facing product concept;
- adapter registries, plugin layers, or broad protocol catalogs detached from
  current surface evidence;
- project build/test, CI, Git, or pull-request substitutes.

## Change Gate

Before adding Runtime code, answer:

1. Does a real five-command task require it?
2. Can the Coding Agent or project-native tooling handle it?
3. Can an existing focused module handle it without a new abstraction?
4. Is there a runnable regression test for the observed failure?

If the answer does not justify new Runtime, record the limitation and keep the
core small.
