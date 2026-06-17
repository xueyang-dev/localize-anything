---
name: localize-anything
description: Localize projects, files, games, websites, documents, subtitles, structured language resources, and mixed artifact bundles into review-ready target-locale deliverables while preserving format, placeholders, context, terminology, provenance, and QA state. Use for localization, i18n, multilingual delivery, locale-file generation, culturally adapted copy, glossary or translation-memory workflows, incremental localization, and project localization enablement. Do not trigger for ordinary one-sentence translation, vocabulary lookup, or language-learning questions unless the user explicitly asks for localization or market adaptation.
---

# Localize Anything

Treat localization as a delivery workflow, not direct translation. Produce artifacts that users can review and apply without silently damaging source structure.

## Classify The Request

Choose the smallest suitable delivery level:

- Use `inline` for short copy that needs localization or cultural adaptation.
- Use `lightweight_file` for one independent file with limited project context.
- Use `standard_project` for multiple files, multiple locales, incremental work, reusable memory, or apply-in-place delivery.

Choose the project mode:

- Use Delivery Mode when a localization entrypoint already exists.
- Offer Enablement Mode when the project lacks a localization entrypoint. Explain the proposed structural changes before editing.

## Run The Workflow

1. Confirm the actual source material and source locale.
2. Honor explicit target locales. If missing, ask and recommend likely choices without selecting silently.
3. Scan runtime capabilities and adapter support.
4. Select full, layered, light, or skipped deep preflight according to context dependence and scale.
5. Recommend a workflow depth and let the user choose.
6. Create or update project memory for standard projects.
7. Split work by semantic content unit and adapter constraints.
8. Build an ephemeral working context packet for each batch.
9. Localize from the original source, preserving unit-level source provenance for mixed-language names and concepts.
10. Run deterministic QA, agent linguistic review, and targeted repair as required.
11. Package a draft or review-ready delivery. Never declare final acceptance for the user.
12. Import reviewer changes and promote memory only within explicitly accepted scope.

Read [workflow.md](references/workflow.md) before standard project work. Read only the additional reference needed for the active stage:

- [memory-and-context.md](references/memory-and-context.md) for preflight, memory, context budgets, or incremental work.
- [qa-and-delivery.md](references/qa-and-delivery.md) for QA, packaging, apply-in-place, review import, or sign-off.
- [adapters.md](references/adapters.md) for format detection, capability degradation, or adapter selection.

## Preserve Hard Constraints

Treat parsing, keys, placeholders, ICU branches, markup, timestamps, escaping, encoding, paths, and overwrite safety as hard constraints. Do not let linguistic preferences override them.

Preserve globally understandable dates, currencies, times, and units by default. Detect ambiguity, keep the original value, and ask the user whether to adapt it.

## Handle Risk Honestly

Identify legal, medical, financial, regulatory, religious, and other specialist content. Produce a review draft and risk notes; do not claim specialist certification.

List unprocessed images, audio, visual text, and other non-text assets in QA. Do not imply that text completion means the full experience is localized.

## Use The Runtime When Available

Prefer the companion runtime for deterministic extraction, stable IDs, hashes, schema validation, staging, structural QA, packaging, and apply planning. If unavailable, degrade capability explicitly. Do not label a standard project `review_ready` without required deterministic checks.
