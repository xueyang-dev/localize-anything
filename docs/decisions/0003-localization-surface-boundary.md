# ADR 0003: Localization Surface Boundary

## Status

Accepted - 2026-08-01
Updated - 2026-08-02 (surface inventory and capability report contracts are
now generated and validated by the merged project-local adapter runtime)

## Context

The name "Localize Anything" can be misread as a promise to automatically
translate and mutate every file, program, runtime string, and asset in a
project. That claim is neither safe nor consistent with the accepted
agent-native product direction.

Projects expose user-visible content through different localization surfaces:
standard resource catalogs, structured catalogs embedded in source code,
unstructured inline source strings, templates, runtime services, visual or
audio assets, and binary resources. These surfaces require different evidence,
tooling, review, and safety rules.

## Decision

Define "Anything" as surface-aware localization coverage:

> Localize Anything discovers, classifies, and explains project localization
> surfaces; routes supported surfaces to reliable adapters; produces enablement
> plans for surfaces that require project-structure changes; and explicitly
> reports unsupported, unscanned, dynamically generated, and non-text content.

Localization Surface is a first-class architecture model. Adapter resolution
must use surface evidence, not only file extension or programming language.
Capability claims must combine the round-trip level with orthogonal dimensions
such as detection, extraction, staged rebuild, source mutation, syntax
validation, build verification, launch verification, runtime-surface
verification, and visual verification.

Structured code-embedded catalogs and unstructured inline code strings are
different capability classes. A project-local Swift catalog slice such as
Vorssaint may be experimental evidence for a specific `code_embedded_catalog`
structure, but it is not generic Swift localization support.

## Consequences

- README, Product Direction, Architecture, adapter docs, roadmap, benchmark
  docs, Skill guidance, and public claims must avoid universal mutation or
  programming-language support claims.
- Unsupported, unscanned, dynamic, and non-text surfaces must remain visible as
  coverage limitations or enablement work, not disappear from delivery wording.
- Existing protocol-first, deterministic-runtime versus semantic-Agent,
  staged-output, review, Git, backup/rollback, and evidence-separation
  principles remain intact.
- The current protocol keeps its seven stable contracts. Source surface
  inventory and capability report artifacts are now generated and validated
  by the runtime (implemented by the merged project-local adapter runtime);
  enablement plan artifacts remain planned contracts.
