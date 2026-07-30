---
name: localize-anything
description: >-
  Guide a Coding Agent through professional project localization: scope
  discovery, translatability classification, concept-centered Glossary and
  project memory, i18n implementation, deterministic structural checks,
  independent language review, risk-ranked human confirmation, and Standard or
  Release completion. Use when adding or updating locales, reviewing project
  localization, building a glossary or translation memory, finding localization
  gaps, or preparing a multilingual release. Do not trigger for ordinary
  one-sentence translation, vocabulary lookup, language learning, Provider
  management, or general i18n coding without a localization task.
---

# Localize Anything

Act as the localization expertise layer for the host Coding Agent. The Agent
still owns code edits, i18n architecture, project builds/tests, screenshots, and
Git work. Supply the professional workflow, durable language decisions,
mechanical QA, independent review, and a concise set of human decisions.

## Choose The Depth

- Use **Standard** for routine locale additions and copy updates.
- Use **Release** when the user is preparing a formal release and needs
  screenshots, page-level review, build/test evidence, locale behavior checks,
  a clean Git diff, and commit or pull-request preparation.

Recommend a depth from the request and project risk. Use Standard when the user
does not specify and Release evidence is not clearly required.

## Run The Workflow

1. Confirm the product, users, source locale, target locales, task intent, and
   actual project material.
2. Declare scope: pages, components, resource files, dynamic/external surfaces,
   non-text assets, exclusions, and project-specific completion criteria.
3. Classify candidates as `translate`, `preserve`, `locale_format`,
   `developer_only`, `dynamic_external`, or `needs_context`.
4. Load or bootstrap Project Memory. Establish the concept-centered Glossary,
   style guidance, preserve rules, and relevant reviewed Translation Memory.
5. Guide the Coding Agent through the required i18n architecture, resource and
   source-code changes. Reuse the project's existing framework and conventions.
6. Require the Coding Agent to run the real project build/tests appropriate to
   the change. In Release depth, also verify locale switching, persistence,
   system-language detection, fallback, and primary-page screenshots.
7. Run deterministic checks for keys, placeholders, markup, escapes, preserve
   rules, source/target structure, and declared-scope coverage.
8. Start an independent review context that does not merely repeat generation.
   Review at string, page/component, and product-concept levels.
9. Auto-clear low-risk findings with reasons. Send only product terminology,
   brand, high-risk ambiguity, meaning changes, and unresolvable context to the
   user.
10. Produce a Review Report that separates deterministic findings, Agent
    review, and human confirmations. Include totals, auto-cleared items,
    unresolved risks, build/test evidence, screenshots, and Git state as
    applicable.
11. Promote only confirmed terms, reviewed translations, style decisions, and
    recurring defects into Project Memory within the accepted scope.

Read [workflow.md](references/workflow.md) for project work. Read only the
additional reference needed for the active stage:

- [memory-and-context.md](references/memory-and-context.md) for Glossary,
  Translation Memory, project context, or cross-session consistency.
- [qa-and-delivery.md](references/qa-and-delivery.md) for checks, independent
  review, risk routing, reports, screenshots, or release completion.
- [adapters.md](references/adapters.md) for file-format detection and mechanical
  validation limits.

## Preserve Hard Constraints

Never sacrifice keys, placeholders, ICU branches, markup, timestamps, escapes,
encoding, paths, preserve rules, overwrite safety, or source-control safety for
linguistic preference.

Do not treat all source-language text as translatable. Brand names, codes,
currency codes, developer-only text, locale-formatted values, and external
dynamic content may correctly remain unchanged.

## Keep Roles Clear

- The Agent makes semantic and engineering judgments.
- Deterministic tools scan, compare, validate structure, normalize Glossary
  data, and prepare report data.
- Git manages diffs, history, rollback, branches, commits, pull requests, and
  team review.
- The user decides product meaning, official terminology, brands, high-risk
  wording, and final release acceptance.

Do not build a parallel Workbench, Provider manager, multi-agent orchestration
platform, enterprise approval system, CI system, or Git substitute as part of a
localization task.

## Be Honest About Completion

Coverage is complete only within the declared scope: every candidate is
classified and every `translate` item has a target result. Do not redefine it
as zero remaining source-language characters.

Deterministic checks do not prove semantic or professional translation quality.
Agent review is not the same as human confirmation. Never promise perfect
translation or silently decide a high-risk product question.

When runtime support is missing, let the Coding Agent handle the format directly
and record which mechanical checks could not be performed.
