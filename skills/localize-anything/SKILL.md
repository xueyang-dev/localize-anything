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
  one-sentence translation, vocabulary lookup, language learning, or general
  i18n coding without a localization task.
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

## Make The Skill Available

- **Codex:** expose this `skills/localize-anything/` directory as an available
  Skill, or copy it into the configured Codex skills directory.
- **Claude Code:** place this directory under the project's
  `.claude/skills/localize-anything/` and keep `SKILL.md` plus `references/`.

The Skill is guidance for the host Coding Agent. It does not install a second
CLI, replace project-native commands, or restore removed platform workflows.

## Default Path

The default path uses only these five `localize` capability groups:

```text
localize scan
-> localize glossary bootstrap
-> Coding Agent localization with project-native tools
-> localize check
-> localize review
-> human confirmation
-> localize report
```

1. Confirm the product, users, source locale, target locale, task intent, and
   project material. Declare in-scope files, surfaces, exclusions, and
   completion criteria.
2. Run `localize scan PROJECT --source-locale SOURCE --target-locale TARGET
   --source PATH` for every source file in scope. It establishes Project Memory.
3. Run `localize glossary bootstrap PROJECT`. Review only high-impact candidate
   concepts; lock a term only after it is confirmed.
4. Guide the Coding Agent to make i18n and resource changes using the project's
   conventions. The Coding Agent runs its own build and test commands, such as
   `npm test`, `npm run build`, `./gradlew test`, or `xcodebuild`, plus `git
   diff` when relevant.
5. Run `localize check PROJECT --target PATH` once per declared source, in the
   same order as `scan`. Fix blocking structural findings before review.
6. Run `localize review PROJECT --target PATH` to create the review packet.
   Give that packet to a fresh review context that did not generate the draft.
   Import its findings with the same command and `--findings REVIEW.json`.
7. Send only high-risk, meaning-changing, terminology, or brand findings to the
   user. Do not record a human confirmation while an open finding lacks a user
   decision.
8. Run `localize report PROJECT`. If the user has decided every open item, pass
   those decisions with `--confirm CONFIRMATIONS.json`; otherwise report the
   remaining confirmation-required risks.

When a supported mechanical check is unavailable, let the Coding Agent make a
scoped project-native edit and record the limitation. Continue the default path;
do not substitute another platform workflow.

## Explicit Compatibility

Never select a compatibility path automatically. It is allowed only when the
user explicitly requests a legacy command or asks to maintain existing legacy
state. In that case, explain that the path is compatibility-only and keep its
scope separate from the default workflow.

Do not use compatibility mechanisms as a fallback for a missing adapter or an
ordinary localization task. In particular, the default path must not invoke old
run orchestration, work-packet construction, provider handoff, readiness
reports, workbench queues, signoff records, or knowledge eligibility pipelines.

Read [workflow.md](references/workflow.md) for the default command sequence. Read only the
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

Do not build a parallel orchestration, approval, CI, or Git substitute as part
of a localization task.

## Be Honest About Completion

Coverage is complete only within the declared scope: every candidate is
classified and every `translate` item has a target result. Do not redefine it
as zero remaining source-language characters.

Deterministic checks do not prove semantic or professional translation quality.
Agent review is not the same as human confirmation. Never promise perfect
translation or silently decide a high-risk product question.

When the five-command core lacks format support, let the Coding Agent handle the
format directly and record which mechanical checks could not be performed.
