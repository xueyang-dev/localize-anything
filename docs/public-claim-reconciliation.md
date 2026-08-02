# Public Claim Reconciliation

This note keeps public wording aligned with the accepted
[Product Direction](product-direction.md).

## Canonical Positioning

Chinese:

> **Localize Anything 是面向 Coding Agent 的本地化专业能力层。**

English:

> **An agent-native localization workflow and review layer.**

## Anything Boundary

"Anything" means localization-surface discovery, supported-surface routing,
enablement planning, and explicit unsupported-surface reporting. It does not
mean automatically translating or mutating every file, program, runtime string,
or asset in a project.

## Safe Product Claims

Localize Anything may be described as a product that:

- guides a Coding Agent through professional localization preflight,
  implementation and independent review;
- helps declare localization scope and classify candidate content;
- discovers and explains localization surfaces in the declared project scope;
- routes supported resource catalogs to deterministic handlers;
- records unsupported, dynamic, non-text, or unscanned surfaces as limitations
  instead of hiding them;
- carries project concepts, terminology, style, preserve rules and reviewed
  Translation Memory across sessions;
- uses deterministic tools for structural QA and declared-scope coverage;
- reviews strings, pages/components and product concepts;
- risk-ranks findings and minimizes human confirmation work;
- integrates with the Coding Agent's build/test workflow and Git changes.

These are product-direction claims. Specific format, command or automation
claims must still match current implementation and tests.

## Current Implementation Boundary

The repository implements the five-command `localize` core, canonical Glossary,
Project Memory, deterministic checks, independent review packet, finding-linked
confirmation, and report. The old platform CLI, Workbench, Provider, workflow,
readiness, signoff, Knowledge Pack, generation/delivery orchestration, and broad
protocol inventory have been removed.

Documentation must still distinguish deterministic evidence from Agent review
and human release judgment. Project-native build/test, screenshots, locale
behavior, and Git evidence are not produced by `localize report`.

## Claims To Avoid

- Localize Anything is a translation model or is inherently better at writing
  i18n code than the host Coding Agent.
- Localize Anything automatically mutates every detected surface.
- Programming-language detection implies localization support.
- Structured code catalogs and unstructured inline strings are the same
  capability class.
- Swift, iOS, Android, React, DOCX, or another platform is fully localized
  because one resource format passed deterministic checks.
- Swift source mutation is a stable core capability without an explicit
  adapter, staged patch, syntax validation, build evidence, and apply approval.
- Vorssaint proves generic Swift support.
- Build success proves complete visible localization.
- Extracted-string coverage proves full product coverage.
- Dynamic content and non-text assets are covered by a file-only run.
- Unsupported surfaces can be silently ignored.
- Localize Anything replaces project builds, tests, CI, Git or pull requests.
- Localize Anything is an enterprise TMS, Provider platform, approval system or
  general multi-agent framework.
- Deterministic QA alone proves semantic or professional translation quality.
- Full coverage means no source-language characters remain anywhere.
- Every framework, locale, dynamic surface, asset or document is supported.
- A successful Agent run removes the need for high-risk human decisions.
- The product guarantees perfect translation or automatic release readiness.

## README Safe Path

The primary narrative should be:

```text
Coding Agent can do the engineering
-> Localize Anything supplies professional localization workflow and memory
-> deterministic checks catch mechanical defects
-> independent review checks language and product concepts
-> the user receives only high-risk decisions
-> Git carries the final change
```

Historical platform evidence lives in the legacy architecture snapshot and Git
history, not in current usage instructions.
