# Public Launch Checklist

## GitHub Repository Settings

Recommended About description:

> Localization workflow and review layer for Coding Agents.

Recommended topics:

- `localization`
- `l10n`
- `i18n`
- `coding-agents`
- `agent-skills`
- `translation-memory`
- `glossary`
- `quality-assurance`
- `developer-tools`

## README First Screen

The first screen must answer:

- What is it? The localization expertise layer for Coding Agents.
- Who is it for? Individuals, indie developers, small teams and open-source
  maintainers using Coding Agents.
- What does it solve? Scope, durable project language, independent review and
  review-cost reduction.
- What does the Coding Agent still do? i18n engineering, code, build/test,
  screenshots and Git.
- What does the user do? Only high-risk product and release decisions.

## Direction Consistency

- [ ] Chinese positioning says “面向 Coding Agent 的本地化专业能力层”.
- [ ] English positioning says “An agent-native localization workflow and
      review layer.”
- [ ] Agent Skill is presented as the primary interface.
- [ ] CLI is presented as a small deterministic helper.
- [ ] Git is presented as the state and collaboration layer.
- [ ] Standard and Release are the two workflow depths.
- [ ] Review covers string, page/component and product-concept levels.
- [ ] Glossary and Project Memory are the only user-facing memory concepts.
- [ ] The main metric is lower human Review cost.

## Current Versus Target

- [ ] Target v1 behavior is not described as already shipped unless verified.
- [ ] The existing v0.4 runtime is described as current/legacy implementation.
- [ ] Workbench is not presented as the future primary interface.
- [ ] Provider governance and multi-agent orchestration are not presented as
      core roadmap items.
- [ ] Historical benchmark and release evidence remains scoped to what it
      actually tested.

## Claims To Avoid

- [ ] No promise of perfect or fully automatic professional translation.
- [ ] No implication that Localize Anything replaces Coding Agent engineering.
- [ ] No enterprise TMS, Provider marketplace or general orchestration claim.
- [ ] No definition of coverage as zero source-language characters.
- [ ] No semantic quality claim based only on structural QA.
- [ ] No universal framework, locale or content-surface support claim.
- [ ] No release-readiness claim without real build/test, review and Git
      evidence.

## Pre-Posting Checks

- [ ] README and documentation links work.
- [ ] CI status is green.
- [ ] Current release and implementation status are accurate.
- [ ] Skill metadata and workflow references match the accepted direction.
- [ ] Product Direction, Architecture, Roadmap and ADR 0002 agree.
- [ ] Examples use Coding Agent language rather than platform-orchestrator
      language.
- [ ] No private user data, credentials or local paths are included.
