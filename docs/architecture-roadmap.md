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
removed platform.

Priority order:

1. exercise the five-command path on more real repositories and locales;
2. improve resource discovery only when a real project proves a gap;
3. improve semantic review prompts and risk compression from observed misses;
4. promote confirmed human decisions into Project Memory without adding a
   second terminology source of truth;
5. improve report clarity around declared scope, project-native build/test,
   screenshots, limitations, and release judgment;
6. add focused format checks only where they protect a demonstrated
   trust-boundary failure.

## Non-Goals

Do not reintroduce:

- Provider execution or a model marketplace;
- Workbench or queue UI;
- workflow orchestration, resume/recovery, locks, or idempotency products;
- readiness matrices, signoff, claim acceptance, or release governance;
- Knowledge Pack as a user-facing product concept;
- adapter registries, plugin layers, or broad protocol catalogs;
- project build/test, CI, Git, or pull-request substitutes.

## Change Gate

Before adding Runtime code, answer:

1. Does a real five-command task require it?
2. Can the Coding Agent or project-native tooling handle it?
3. Can an existing focused module handle it without a new abstraction?
4. Is there a runnable regression test for the observed failure?

If the answer does not justify new Runtime, record the limitation and keep the
core small.
