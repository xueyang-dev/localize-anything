# Public Claim Reconciliation

This note keeps public wording aligned with the accepted
[Product Direction](product-direction.md).

## Canonical Positioning

Chinese:

> **Localize Anything 是面向 Coding Agent 的本地化专业能力层。**

English:

> **An agent-native localization workflow and review layer.**

## Safe Product Claims

Localize Anything may be described as a product that:

- guides a Coding Agent through professional localization preflight,
  implementation and independent review;
- helps declare localization scope and classify candidate content;
- carries project concepts, terminology, style, preserve rules and reviewed
  Translation Memory across sessions;
- uses deterministic tools for structural QA and declared-scope coverage;
- reviews strings, pages/components and product concepts;
- risk-ranks findings and minimizes human confirmation work;
- integrates with the Coding Agent's build/test workflow and Git changes.

These are product-direction claims. Specific format, command or automation
claims must still match current implementation and tests.

## Current Implementation Boundary

The repository still contains the broad v0.4 reference runtime, protocol,
Workbench, Provider evidence, workflow orchestration and release-governance
systems. They may be described as current or legacy implementation, but not as
the active product north star.

The target v1 Skill and small CLI surface are being consolidated from existing
capabilities. Documentation must not imply that every target command or
simplified memory format already exists.

## Claims To Avoid

- Localize Anything is a translation model or is inherently better at writing
  i18n code than the host Coding Agent.
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

Historical releases and benchmarks can remain linked as implementation
evidence, but they should not dominate the first-screen product story.
