# ADR 0002: Coding-Agent Localization Workflow And Review Layer

## Status

Accepted — 2026-07-30

Supersedes [ADR 0001](0001-protocol-first-workflow.md) as the product and target-
architecture decision. ADR 0001 remains a historical record of the v0.4
platform-oriented architecture.

Refined by [ADR 0003](0003-localization-surface-boundary.md) for the
surface-aware definition of "Anything", source-code boundaries, and capability
claims.

## Context

Coding Agents can already edit application code, create i18n infrastructure,
run builds and tests, capture screenshots, and prepare Git changes. Rebuilding
those abilities inside Localize Anything creates a parallel platform and shifts
attention away from the actual user problem: applying professional localization
practice and reducing review cost.

The repository accumulated Provider execution governance, workflow
orchestration, Workbench state, enterprise-style authorization, release-claim
artifacts and a large protocol surface. Useful primitives exist inside those
systems, but the systems themselves are not the desired v1 product.

## Decision

Position Localize Anything as:

> **The localization expertise layer for Coding Agents.**

The primary interface is an Agent Skill. A lightweight CLI performs only
deterministic scanning, comparison, structural QA, Glossary normalization and
report generation. The Coding Agent owns code changes, project builds/tests,
screenshots and Git work. Git remains the change-management and collaboration
layer.

The user-facing persistent model is reduced to:

```text
Glossary
Project Memory
```

The workflow supports Standard and Release depths and reviews localization at
string, page/component and product-concept levels. The core outcome is a
complete review of all localized content with a small, risk-ranked set of human
decisions.

## Capability Gate Boundary

Updated 2026-08-02. [ADR 0003](0003-localization-surface-boundary.md) further
defines the localization surface boundary; this ADR remains the product and
target-architecture decision and is not superseded.

- Localization surface is the scope unit, and project-local adapters are a
  constrained extension mechanism selected explicitly by the runtime.
- The Coding Agent must not bypass the runtime capability gate. Unsupported
  surfaces and adapters that have not been explicitly selected must not
  proceed into free-form linguistic inference or hand-built extraction under
  the default path.
- Capability evidence, artifact preconditions, and report-only review limits
  are runtime-owned; the Agent owns engineering, review, and delivery, not
  gate override.

## Consequences

- Existing runtime and protocol code may remain during migration, but it is
  compatibility or implementation inventory rather than the product north star.
- Workbench, Provider management, multi-agent orchestration, enterprise
  authorization/signoff, release-claim governance and productized benchmark
  systems leave the core roadmap.
- Terminology and knowledge structures should be consolidated rather than
  extended as separate user concepts.
- New features should first improve scope discovery, project memory,
  deterministic checks, independent review and Review Report usefulness.
- Documentation must clearly separate target v1, current implementation,
  legacy compatibility and historical release evidence.
