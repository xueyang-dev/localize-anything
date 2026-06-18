# QA And Delivery

## Evidence Channels

Keep runtime, agent, and human evidence distinct.

Runtime/adapter QA verifies parsing, schema, key and segment coverage, placeholders, ICU and markup, encoding, escaping, duplicate IDs, hashes, paths, round-trip, and manifest completeness.

Agent QA reviews accuracy, omission, fluency, terminology in context, style, character voice, narrative coherence, cultural adaptation, and provenance. Attach segment evidence, severity, confidence, and a recommended action.

Human review imports edits and grants scoped sign-off. Agent review never substitutes for human acceptance.

## Standard Delivery Package

```text
delivery-manifest.json
localization-context.md
glossary.csv
translation-memory.jsonl
qa-report.md
files/
```

Use smaller packages for inline and lightweight-file work.

## Status

- `draft_package`: Generated but required review or QA remains.
- `review_ready`: Required deterministic checks pass and configured agent review is complete.
- `blocked`: A structural or unresolved critical issue prevents review-ready delivery.
- `applied_draft`: Files were written to the project but not accepted.
- `user_accepted`: The user explicitly accepted a defined scope.

Report a high-signal summary in chat and keep full engineering detail in `qa-report.md`. Store machine-readable status and counts in the manifest.

## Apply-In-Place

Default to bundle-first. Before writing project files, inspect existing changes, create an apply plan, stage outputs, validate them, show a concise diff summary, and obtain explicit confirmation. Do not delete or overwrite uncertain files by default. Revalidate after apply.

## Review Import

Compare reviewed artifacts with the generated draft at segment level. Classify changes as translation, terminology, style, voice, locale convention, format-only, source correction, or unknown. Update TM for reviewed segments. Propose glossary or context promotion only when the change has wider scope.
