# Architecture Roadmap

This roadmap implements the accepted [Product Direction](product-direction.md)
and [target architecture](architecture.md). It is a deletion-first migration
roadmap, not a plan to keep expanding the v0.4 platform.

## Product Goal

```text
Skill guides professional localization workflow
CLI performs mechanical checks
Coding Agent performs engineering
Git manages changes and collaboration
User resolves high-risk product decisions
```

The main product metric is lower human review cost without hiding localization
defects or structural risk.

## Ordering Rule

Work proceeds in this order:

```text
consolidate
-> replace
-> deprecate
-> remove
-> simplify
-> complete only the missing target-v1 experience
```

Do not add a new artifact, report, queue, matrix, service, or UI surface when an
existing capability can be consolidated or removed. New work must improve a
Standard or Release workflow that a real Coding Agent can complete in a real
repository.

Trust-boundary validation, data-loss prevention, source safety, and benchmark
evidence are not removed merely because their original subsystem is legacy.

## P0 — Align And Freeze

Goal: make every entry point tell the same product story and stop expanding the
old one.

- Align README, Product Direction, Architecture, public claims, Skill,
  contribution guidance, and repository metadata.
- Make the Agent Skill the primary interface.
- Mark the broad protocol as Compatibility and classify Core, Legacy, and
  Experimental contracts explicitly.
- Archive the v0.4 platform architecture as historical reference.
- Freeze new Provider governance, Workbench, multi-agent orchestration,
  workflow-state, authorization-matrix, enterprise-signoff, release-claim, and
  adapter-promotion features.

Exit criteria:

- a contributor can explain the product in one sentence;
- active guidance does not route through a legacy subsystem by default;
- target capabilities are not described as already shipped;
- no legacy subsystem receives new scope without a new accepted product
  decision.

## P1 — Consolidate And Replace Project Memory

Goal: replace competing terminology and knowledge structures with one user-
facing model.

- Inventory current Glossary, term registry, term decisions, review decisions,
  Knowledge Pack terms, Translation Memory, style, preserve, and history data.
- Define the target concept-centered canonical Glossary.
- Define Project Memory as the home for reviewed TM, style, preserve rules,
  confirmed decisions, product context, and recurring defects.
- Build migration readers before changing or deleting stored user data.
- Consolidate duplicate sources of truth behind the new model.
- Replace Skill references to old memory artifacts with Glossary and Project
  Memory.
- Deprecate direct user maintenance of term registry, term-decision, term-review,
  and Knowledge Pack term files.
- Remove obsolete representations only after migration tests prove no approved
  terms or reviewed translations are lost.

Target Glossary discovery may later support:

```text
Discover -> Import -> Normalize -> Rank -> Confirm -> Use
```

Automatic discovery, ranking, and a final canonical file format remain planned
until implemented and tested.

Exit criteria:

- users maintain one Glossary and one Project Memory;
- existing approved terminology and reviewed translations migrate losslessly;
- changing Coding Agent or session does not change confirmed product language;
- old memory artifacts are no longer required by the default Skill path.

## P2 — Simplify The CLI And Replace Default Paths

Goal: replace the broad platform command surface with the smallest deterministic
toolset the Skill needs.

Target capability groups:

```text
scan
glossary bootstrap
check
review
report
```

- Map existing parsing, comparison, QA, coverage, TM, and report primitives to
  these target capability groups.
- Keep existing commands available only where compatibility callers require
  them.
- Replace the Skill's default path with the smaller capabilities.
- Deprecate commands whose purpose is Provider governance, Workbench state,
  orchestration, readiness matrices, claim acceptance, signoff, or release-
  evidence management.
- Remove deprecated commands and protocol wiring after callers and tests have
  migrated.
- Simplify generated output so the user sees deterministic findings, Agent
  review, human confirmations, and Git state—not an internal artifact graph.

The exact target command spelling is planned and may change before it is
implemented.

Exit criteria:

- Standard workflow mechanical checks use a small documented surface;
- no default command requires Workbench, Provider management, workflow state,
  enterprise approval, or release-claim machinery;
- compatibility commands are visibly deprecated and have a removal path;
- fewer public commands and outputs remain than before the migration.

## P3 — Deprecate And Remove Legacy Product Surfaces

Goal: shrink the repository after replacement paths exist.

Legacy candidates:

- Provider execution, consent, ledger and smoke evidence;
- multi-agent orchestration and workflow state-machine surfaces;
- concurrency, recovery and idempotency product layers;
- Readiness Authorization Matrix, Claim Acceptance and enterprise signoff;
- release-claim and adapter-promotion governance;
- Workbench Web UI;
- Document Evidence leadership workflows;
- productized runtime Benchmark Lab;
- large user-facing protocol schema inventories.

For each candidate:

1. identify real callers, data, tests, and safety checks;
2. extract any primitive required by target v1;
3. replace the default user/Skill path;
4. mark the old surface deprecated;
5. preserve a documented compatibility window when needed;
6. remove code, schemas, examples, docs, and tests that no longer protect a
   supported path;
7. verify that source safety and migration behavior remain covered.

Protocol cleanup must reduce the number of Compatibility and Legacy contracts.
Creating a replacement matrix, queue, or report with a new name is not
simplification.

Exit criteria:

- Workbench and Provider governance are not required for Standard or Release;
- legacy endpoints and commands have been removed or have explicit remaining
  callers and removal criteria;
- protocol validation reports a materially smaller long-term surface;
- repository concepts match what users see in the Skill.

## P4 — Complete Independent Review And Release Experience

Goal: fill only the user-facing gaps that remain after consolidation and
removal.

Planned review work:

- separate review context from generation;
- combine string, page/component, and product-concept review;
- classify content as `translate`, `preserve`, `locale_format`,
  `developer_only`, `dynamic_external`, or `needs_context`;
- clear low-risk findings with visible reasons;
- route product terminology, brand, high-risk ambiguity, and meaning changes to
  human confirmation;
- report total, reviewed, auto-cleared, confirmation-required, and human-edited
  counts.

Planned Release work:

- target-locale screenshots for primary pages;
- page semantic and visible-result review;
- locale switch, persistence, system/browser detection, and fallback checks;
- actual project build/test results;
- a clear Git diff and optional commit or pull request;
- confirmed decisions promoted into Project Memory.

These are target capabilities, not current runtime claims. Prefer host Coding
Agent capabilities over new Localize Anything infrastructure.

Exit criteria:

- every in-scope localized item is reviewed;
- human confirmation items are risk-ranked and explain why a decision is
  needed;
- a Release run links scope, checks, review, screenshots, build/test results,
  Git change, and unresolved risks;
- Localize Anything does not duplicate the project build system, CI, or Git.

## Format Priorities

The first simplified CLI tier plans to prioritize:

- JSON and YAML;
- Android XML;
- Apple `.strings` and `.xcstrings`;
- PO/POT;
- XLIFF.

Existing TOML, tabular, Word OpenXML, subtitle, and markup handlers may remain
available as Compatibility capabilities. Broader format count is secondary to
consolidation, review quality, and lower human review cost.

## Persistent Non-Goals

The roadmap does not turn Localize Anything into:

- a translation model or Provider marketplace;
- an enterprise TMS;
- a general multi-agent framework;
- a replacement for Git, CI, or project build systems;
- a universal i18n architecture generator;
- an automatic professional-quality certification system;
- a guarantee of perfect translation or zero source-language characters.
