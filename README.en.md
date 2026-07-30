# Localize Anything

<p align="center">
  <img src="docs/assets/logo-localize-anything-transparent.png" alt="Localize Anything logo" width="220" />
</p>

<p align="center">
  <strong>The localization expertise layer for Coding Agents.</strong>
</p>

<p align="center">
  Target: give agents a professional workflow, durable project language, complete review, and a much smaller set of human decisions.
</p>

<p align="center">
  English · <a href="README.md">简体中文</a>
</p>

<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue" />
  <img alt="CI" src="https://github.com/xueyang-dev/localize-anything/actions/workflows/ci.yml/badge.svg" />
  <img alt="Current release: v0.4.1" src="https://img.shields.io/badge/release-v0.4.1-blue" />
  <img alt="Primary interface: Agent Skill" src="https://img.shields.io/badge/interface-Agent%20Skill-blueviolet" />
</p>

---

The current repository already provides an Agent Skill, structural QA,
Translation Memory, and handlers for multiple resource formats. The revised
Skill now requires Codex, Claude Code, and similar Coding Agents to declare
scope and language constraints before localization and to review drafts from a
separate context. A concept-centered canonical Glossary, unified Project
Memory, page-level review, and automatic risk compression are still being
consolidated for target v1.

Coding Agents can already edit code, build i18n infrastructure, run builds and
tests, capture screenshots, and prepare pull requests. Localize Anything does
not rebuild those capabilities. It adds professional localization workflow and
low-cost review.

> **An agent-native localization workflow and review layer.**

## Who It Is For

The core users are:

- individual and indie developers;
- small product teams;
- open-source maintainers;

who build products with Coding Agents.

A typical request is:

> Use Localize Anything to add Russian support to this project.

Large enterprise localization teams, language-service providers, and
professional translation agencies are not the initial core audience. Localize
Anything does not compete with enterprise TMS products.

## What It Solves

### A complete localization workflow for the Agent

A general Coding Agent can easily patch one screen at a time, extract every
string indiscriminately, stop after a successful build, or skip terminology and
language review. The target workflow starts with scope, project memory, and
completion criteria, then ends with independent review and a risk summary. The
current Skill now specifies that method; the smaller CLI and unified report
remain migration work.

### Durable project language

Target v1 Project Memory will preserve and share through Git under
`.localize-anything/`:

- product concepts and confirmed translations per locale;
- forbidden translations and preserve rules;
- style guidance;
- reviewed Translation Memory;
- human corrections and recurring defects.

The current runtime already stores configuration, Translation Memory, and
multiple terminology/review artifacts. Consolidating them into one Project
Memory and concept-centered Glossary is still the migration direction. Once
consolidated, confirmed product language should remain stable when the Agent,
model, or session changes.

### Lower human review cost

The target experience has the Agent review every item, clear low-risk content
with visible reasons, and route only official product terminology, brands, and
high-risk ambiguity to the user. The current Skill requires independent review
and risk routing; automatic clearing, metrics, and the complete report are
still being consolidated. An ideal result looks like:

```text
Translated items: 412
Agent-reviewed: 412
Auto-cleared: 397
Human confirmation required: 15
Human-edited after review: 6
```

## Target Responsibility Boundaries

| Role | Responsibility |
| --- | --- |
| Localize Anything Skill | Scope, Glossary, style, project memory, workflow, independent review, final report |
| Coding Agent | i18n architecture, code changes, locale resources, build/test, screenshots, Git diff, commits, pull requests |
| Lightweight CLI | Scanning, source/target comparison, placeholder/markup/key checks, coverage summaries, report data |
| Git | Diff, history, rollback, branches, worktrees, commits, pull requests, team review |
| User | Product meaning, brands, high-risk wording, final release judgment |

## Skill Depth And Target v1 Workflow

The current Skill defines Standard and Release depths. They are Agent workflow
methods, not two fully integrated v0.4.1 runtime modes. Supporting commands,
unified Project Memory, page review, and automatic reporting are still being
consolidated.

### Standard

For everyday locale additions and copy updates:

```text
Project and scope preflight
-> Glossary, style, and preserve rules
-> Coding Agent implementation
-> Deterministic structural checks
-> Independent Agent review
-> High-risk human confirmations
-> Review Report
```

### Release

For a formal release, add:

- target-locale screenshots of primary pages;
- page-level semantic and visual review;
- build/test result confirmation;
- locale switching, persistence, system-language detection, and fallback
  verification;
- a clean Git diff;
- a commit or pull request;
- promotion of confirmed decisions into project memory.

Not every task needs Release depth.

## Target Review Model

Target v1 reviews more than isolated strings:

1. **String level:** source/target mapping, placeholders, markup, values,
   omissions, and forbidden terms.
2. **Page or component level:** actual meaning, neighboring copy, control tone,
   cross-screen consistency, and screenshots.
3. **Product-concept level:** consistent expression of the same concepts across
   the product and target locales.

The current runtime already provides string-level structural QA. Page/component
and product-concept review are now required by the Skill but are not yet
delivered as a complete standalone automation engine. Target quality output
remains separated into:

- deterministic checks;
- Agent review;
- human confirmation.

One vague aggregate score does not replace these channels.

## Glossary And Project Memory

The target canonical Glossary is centered on product concepts, not isolated
language pairs. One concept may include multiple source terms, preferred and
forbidden translations per locale, preserve behavior, scope, status, context,
and product meaning.

Users should understand only two durable concepts:

```text
Glossary
Project Memory
```

The current runtime's separate term registry, term decisions, review queues,
and Knowledge Pack terms will be consolidated behind those concepts instead of
becoming additional user-maintained sources of truth.

Translation Memory is a project capability, not an enterprise TM server. It
reuses confirmed sentences, detects stale source changes, preserves human
corrections, and reduces duplicate translation.

## Translatability And Coverage

Candidate content is classified as:

```text
translate
preserve
locale_format
developer_only
dynamic_external
needs_context
```

Complete coverage means every candidate in the declared scope has a
classification and every `translate` item has a target result. It does not mean
that no source-language characters may remain anywhere in the project.

## Current Status

**Current public release:**
[v0.4.1 — Workbench UI Wiring](https://github.com/xueyang-dev/localize-anything/releases/tag/v0.4.1)

On 2026-07-30, the project reset its product direction: the Agent Skill is the
primary interface, the lightweight CLI performs mechanical checks, Git manages
state, and independent review plus lower human review cost define the core
experience.

The repository still contains the broad v0.4.1 reference runtime, including
Workbench, Provider evidence, workflow orchestration, authorization, release
audit, and many protocol artifacts. That code remains temporarily for
compatibility and reusable implementation primitives, but it no longer defines
the product or core roadmap.

The target v1 command surface, canonical Glossary, and Project Memory are being
consolidated from existing capabilities. This README does not present that
migration as already shipped.

## How To Use It

### Through A Coding Agent

When the Localize Anything Skill is available to the Agent, describe a project-
level task:

```text
Use Localize Anything to add Chinese and Russian support to this project.
Use Release depth, including primary-page screenshots, build/test, and PR preparation.
```

The current Skill guides the Agent through scope and existing-memory preflight,
project changes, available mechanical checks, and review from a separate
context. The canonical Glossary, automatic low-risk clearing, and unified risk
report are being connected incrementally for target v1.

The Skill source is
[skills/localize-anything/SKILL.md](skills/localize-anything/SKILL.md).

### Current CLI Developer Preview

Python 3.11+ is required:

```bash
git clone https://github.com/xueyang-dev/localize-anything.git
cd localize-anything
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[yaml]"
python -m unittest discover -s tests -v
```

The current runtime can inspect a real project without writing to it:

```bash
localize-anything inspect /path/to/project
```

Target v1 will converge common Agent mechanics into small `scan`, `glossary
bootstrap`, `check`, `review`, and `report` capability groups. Those names are
directional and are not all shipped in the current release.

## Reusable Deterministic Capabilities

The repository already contains implementation that can support the smaller v1:

- segments and stable IDs;
- candidate-term extraction, forbidden terms, and term review;
- exact/fuzzy Translation Memory;
- working-context construction;
- placeholder, markup, key, escape, and resource-structure QA;
- source/target coverage;
- staging and Git-diff integration;
- existing handlers for JSON, YAML/TOML, Android XML, Apple `.strings`,
  `.xcstrings`, PO/POT, XLIFF, subtitles, tables, markup, and Word OpenXML.

See [Adapters](docs/adapters.md) for exact format boundaries. Historical
benchmarks and releases remain implementation evidence, but no longer define
the product positioning.

## What It Is Not

Localize Anything is not:

- a standalone translation model;
- a model Provider management platform;
- a general multi-agent orchestration framework;
- an enterprise TMS, approval, or permissions system;
- a replacement for Git, CI/CD, or project build systems;
- a general development Workbench;
- an independent i18n framework generator;
- an automatic professional-quality certification system;
- a promise of perfect translation or zero source-language characters.

It may require the Coding Agent to run builds/tests, capture screenshots, and
prepare a PR, but it does not reimplement those systems.

## Product Documents

- [Product Direction](docs/product-direction.md)
- [Target Architecture](docs/architecture.md)
- [Roadmap](docs/architecture-roadmap.md)
- [Public Claim Boundary](docs/public-claim-reconciliation.md)
- [ADR 0002: Coding-Agent Localization Workflow And Review Layer](docs/decisions/0002-coding-agent-localization-layer.md)
- [v0.4 Legacy Architecture Snapshot](docs/architecture-v0.4-legacy.md)
- [Changelog](CHANGELOG.md)

## Repository Layout

```text
skills/            Agent Skill: the primary product interface
runtime/           Current Python reference runtime and migration source
adapters/          Existing format-handler manifests
protocol/          v0.4 compatibility protocol, not product positioning
benchmarks/        Historical and regression validation
tests/             Unit and integration tests
docs/              Product direction, architecture, boundaries, implementation docs
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
