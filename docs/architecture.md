# Architecture

## Product North Star

Localize Anything is the localization expertise layer for Coding Agents:

> **An agent-native localization workflow and review layer.**

It helps Codex, Claude Code, and similar agents understand localization scope,
reuse project language decisions, apply terminology and style constraints, and
independently review localized results. It does not replace the Coding Agent or
rebuild the development stack around it.

The canonical product direction is [Product Direction](product-direction.md).
The previous platform-oriented design is preserved only as a
[v0.4 legacy snapshot](architecture-v0.4-legacy.md).

## Target System

```text
User request
    |
    v
Localize Anything Skill
    |-- task depth and declared scope
    |-- project memory, Glossary, style and preserve rules
    |-- localization workflow and completion criteria
    |-- independent review and risk summary
    |
    +------------------------+
    |                        |
    v                        v
Coding Agent            Lightweight CLI
    |                        |
    |-- i18n architecture    |-- scan and source/target comparison
    |-- source edits         |-- placeholder/markup/key checks
    |-- locale resources     |-- declared-scope coverage
    |-- build and tests      |-- Glossary normalization
    |-- screenshots          |-- review report data
    |-- Git diff / PR        |
    +-----------+------------+
                |
                v
       Independent review context
                |
                v
     Small set of human decisions
                |
                v
        Git commit / pull request
```

## Responsibility Boundaries

### Localize Anything Skill

The Skill owns the professional workflow:

- understand the product, audience, target locales and task intent;
- declare pages, components, files, dynamic surfaces and exclusions;
- classify candidate content;
- load or bootstrap project memory;
- define product concepts, terminology, style and preserve rules;
- guide the Coding Agent through implementation;
- start a review context that does not simply repeat the generation context;
- summarize risks, human decisions and completion evidence.

### Coding Agent

The host Coding Agent owns software engineering:

- create or update the project's i18n architecture;
- extract user-visible copy and create locale resources;
- implement locale switching, detection, persistence and fallback;
- edit source code;
- run project-specific build and test commands;
- capture target-locale screenshots;
- prepare clean Git diffs, commits and pull requests.

Localize Anything may require this work and verify its reported result, but it
does not implement a parallel build, test, CI, source-control or project-
management system.

### Lightweight CLI

The CLI owns mechanical work that benefits from deterministic behavior:

- discover localization resources;
- compare source and target structures;
- check keys, placeholders, markup, escapes and preserve rules;
- summarize declared-scope coverage and obvious residual source text;
- import and normalize Glossary data;
- emit machine-readable findings for the final Review Report.

The CLI does not decide whether wording is natural or whether a product concept
has the correct official translation.

### Git

Git is the durable change-management layer: diff, history, rollback, branch,
worktree, commit, pull request and team review. Localize Anything must work with
Git rather than duplicate it.

### User

The user should receive only decisions that genuinely require product
ownership: official terminology, brands, high-risk ambiguity, changes in
product meaning and final release judgment.

## Workflow Depth

### Standard

```text
Preflight
-> Scope and completion criteria
-> Project Memory / Glossary / style
-> Coding Agent implementation
-> Deterministic checks
-> Independent Agent review
-> Human confirmation items
-> Review Report
```

### Release

Release adds target-locale screenshots, page-level review, build/test evidence,
locale-switching and fallback verification, a clean Git diff, commit or pull
request preparation, and promotion of confirmed decisions into project memory.

## Project Memory

The target user-facing model has two concepts:

```text
Glossary
Project Memory
```

Glossary entries model product concepts across locales, including preferred and
forbidden translations, preserve behavior, scope, status and context.

Project Memory holds the Glossary, reviewed Translation Memory, style rules,
preserve rules, product context, confirmed decisions and recurring defects
under `.localize-anything/`. It can be committed with the project when the user
wants shared team memory.

Existing runtime files such as term registries, term decisions, review queues
and Knowledge Pack terms are implementation inputs for migration. They are not
separate product concepts that users should have to maintain.

## Translatability Model

Every candidate item should be classified as one of:

```text
translate
preserve
locale_format
developer_only
dynamic_external
needs_context
```

Coverage means that every candidate in the declared scope has a classification
and every `translate` item has a target result. It does not mean that no source-
language characters may remain anywhere in the project.

## Review Model

Review combines three levels:

1. String-level review checks source/target mapping, placeholders, markup,
   values, obvious omissions and forbidden terms.
2. Page/component-level review checks actual UI meaning, neighboring copy,
   control tone, cross-screen consistency and screenshots.
3. Product-concept review checks whether the same concept remains consistent
   across the product and across target locales.

Quality output remains separated:

- deterministic findings;
- Agent review findings;
- human confirmation items.

No single synthetic score replaces these channels.

## Trust Boundaries

- Structural validation at file and repository boundaries must fail safely.
- Agent judgment must not override keys, placeholders, markup, paths or
  preserve rules.
- Review must distinguish generated opinion from deterministic fact.
- Low-risk findings may be auto-cleared; high-risk ambiguity must remain
  visible to the user.
- Build/test and screenshots must come from the actual project workflow.
- Git changes remain reviewable and reversible.

## Current Repository Versus Target Product

The current repository contains a broad v0.4 reference runtime with provider
execution evidence, workflow orchestration, Workbench, authorization matrices,
enterprise-style signoff, release-claim governance and many protocol artifacts.
Those implementations remain useful as compatibility code and as a source of
reusable primitives, but they no longer define the product.

New work should prefer:

- consolidating terminology structures into one canonical Glossary;
- simplifying persistent state into Project Memory;
- exposing a small deterministic CLI surface;
- strengthening independent review and risk compression;
- integrating with the Coding Agent and Git.

New work should not expand Provider management, a parallel Workbench, a multi-
agent orchestration platform, enterprise approval workflows or protocol surface
area unless a future product decision explicitly changes the direction.

## Status Language

Documentation must distinguish:

- **current implementation**: behavior present in this repository today;
- **target v1**: the accepted product direction being built;
- **legacy compatibility**: existing behavior retained during simplification;
- **non-goal**: behavior that is intentionally outside the product core.

Historical releases and benchmarks remain valid evidence for the code they
tested. They are not the current product positioning.
