# QA And Delivery

## Evidence Channels

Keep runtime, agent, and human evidence distinct.

Runtime/adapter QA verifies parsing, schema, key and segment coverage, placeholders, ICU and markup, encoding, escaping, duplicate IDs, hashes, paths, round-trip, and manifest completeness.

Agent or automated policy review can flag accuracy, omission, fluency, terminology in context, style, character voice, narrative coherence, cultural adaptation, and provenance. Attach segment evidence, severity, confidence, and a recommended action. This supports automated review evidence, not final human acceptance.

Human review evidence is explicit and role-scoped. Bilingual review can support E2, native-language review can support E3, and professional localization review can support E4. Project-owner signoff can authorize a workflow decision, but it does not create E2/E3/E4 review evidence.

Evaluation scorecards and claim acceptance decide which claims are currently
allowed. Do not claim provider-backed quality, full coverage, full terminology
assurance, review-complete status, delivery readiness, apply readiness, or
production readiness when upstream evidence forbids the claim.

## Standard Delivery Package

```text
delivery-manifest.json
delivery-decision.json
qa-result.json
evaluation-scorecard.json
evidence-level-report.md
artifact-state.json
repair-result.json
repair-history.jsonl
human-review-evidence.jsonl
claim-acceptance-decision.json
signoff-record.json
apply-plan.json
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

When a scorecard exists, align delivery language with its `overall_claim` and
`forbidden_claims`. A delivery package with warnings is not the same thing as a
production-ready package.

## Apply-In-Place

Default to bundle-first. Before writing project files, inspect existing changes, create an apply plan, stage outputs, validate them, show a concise diff summary, and obtain explicit confirmation. Do not delete or overwrite uncertain files by default. Revalidate after apply.

Block or downgrade apply when artifact state is stale, required repairs are
pending or failed, unsafe provider policy remains, the handoff decision is
blocked, or claim acceptance/signoff does not support apply readiness.

## Review Import

Compare reviewed artifacts with the generated draft at segment level. Classify changes as translation, terminology, style, voice, locale convention, format-only, source correction, or unknown. Update TM for reviewed segments. Propose glossary or context promotion only when the change has wider scope.
