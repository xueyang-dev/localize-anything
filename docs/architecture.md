# Architecture

## North Star

Localize Anything is an agent-native localization framework, not a translation prompt. Its core promise is to produce a review-ready, traceable delivery package that can be applied to the source project without silently damaging structure.

## Layers

### Localization Protocol

Define machine-readable contracts for project configuration, adapters, segments, QA results, manifests, memory assets, and scoped sign-off. Keep the protocol independent from a model vendor and implementation language.

### Reference Runtime

Perform deterministic work: adapter discovery, extraction, stable IDs, hashes, schema validation, structural QA, incremental diffing, packaging, apply planning, and rollback metadata. Do not translate content.

### Agent Integration

Perform semantic work: intake, source confirmation, preflight interpretation, workflow recommendation, context selection, localization, linguistic review, ambiguity resolution, and user communication.

### Adapter Ecosystem

Implement format, scenario, and platform SOPs through a language-neutral JSON/JSONL contract. Prefer core adapters, permit project-local forks, and reserve a community registry for later releases.

## Workflow

```text
Intake
 -> Capability Scan
 -> Source-of-Truth Confirmation
 -> Target Locale Confirmation
 -> Localization Brief
 -> Adapter Detection
 -> Preflight Policy Selection
 -> Preflight Scan
 -> Initial Memory Assets
 -> Termbase Preflight Gate
 -> Batch Plan
 -> Working Context Packet
 -> Localization
 -> Deterministic QA
 -> Agent Linguistic Review
 -> Targeted Repair
 -> Delivery Package
 -> Review Import
 -> Scoped Sign-off
 -> Optional Apply-in-Place
```

## Delivery Modes

- `inline`: Return short localized content in chat. Do not create project state.
- `lightweight_file`: Return the requested file plus a compact manifest and QA report.
- `standard_project`: Maintain four-layer memory, immutable delivery snapshots, incremental state, and sign-off.

Standard project delivery defaults to bundle-first. Apply-in-place requires a dry run, explicit confirmation, staged writes, and post-apply validation.

## Memory

Canonical project memory consists of:

```text
localization-context.md
localization-brief.json
localization-brief.yaml
glossary.csv
translation-memory.jsonl
term-registry.csv
term-decisions.jsonl
forbidden-translations.csv
term-conflicts.jsonl
term-provenance.jsonl
candidate-terms.jsonl
termbase-preflight-report.json
term-review-queue.json
term-review-decisions.jsonl
delivery-manifest.json
```

The working context packet is ephemeral. A rebuildable SQLite cache may index canonical memory, but never becomes a source of truth.

## Term Governance

Glossaries are advisory memory. The term governance files represent reviewable
decisions:

- `term-registry.csv` stores approved or locked source-to-target term choices,
  scope, priority, and rejected alternatives.
- `term-decisions.jsonl` stores provenance-bearing term decision records.
- `forbidden-translations.csv` stores target renderings that must not be used.
- `term-conflicts.jsonl` and `term-provenance.jsonl` keep unresolved conflicts
  and evidence history separate from approved decisions.

Generation-facing work packets expose approved and locked term-registry entries
through `memory.hard_constraints`. Blind benchmark mode hides target-language
term and translation-memory content to preserve reference isolation.

## Termbase Preflight Gate

Termbase preflight runs after source segment extraction and before generation
handoff. It scans source segments for conservative terminology signals:
repeated short phrases, resource-key-derived UI labels, capitalized acronyms,
Android high-risk UI strings, document high-risk term patterns, and matches
against existing term governance files.

The gate writes four UI-first artifacts:

- `candidate-terms.jsonl`: one deterministic candidate term per line with
  source occurrences, evidence, term type, risk, existing matches, and
  conflicts.
- `termbase-preflight-report.json`: summary status, terminology assurance, high
  risk unreviewed terms, conflicts, and artifact links.
- `term-review-queue.json`: the Workbench-ready review queue.
- `term-review-decisions.jsonl`: decisions recorded from the queue.

The queue is the primary review surface. Workbench/API clients can read the
queue and record decisions without exporting a spreadsheet. Sheet or CSV export
may be added later for convenience, but it is not the source of truth because
spreadsheet review loses artifact identity, segment evidence, queue status,
and safe API write semantics.

Review decisions feed Term Governance. Approved and locked terms sync into
`term-registry.csv`; forbidden targets sync into
`forbidden-translations.csv`; provenance-bearing decisions append to
`term-decisions.jsonl` when they include a target term. Work packets can then
select those approved or locked registry entries as hard constraints.

This gate is intentionally not the full Generation Strategy Gate. It provides
terminology assurance status and visible blockers. Later generation strategy can
use the same report to decide whether to block, route for higher assurance, or
request more user decisions. Until review is complete, run summaries and work
packets carry `terminology_assurance: incomplete_review_required` or
`blocked_by_conflict`; generation must not claim full terminology assurance.

## Localization Brief

`localization-brief.json` is the machine-readable draft of task intent before
generation. `localization-brief.yaml` is the same draft rendered for human
review. The runtime can infer a conservative brief from inspection, confirmed
source files, selected mode, and privacy/workflow settings, but it cannot accept
task intent for the user.

The brief records:

- `document_type`, `source_genre`, `target_mode`, and `target_audience`;
- top-level `style`, `constraints`, `allowed_transformations`, and
  `forbidden_behaviors` for review-facing compatibility with the optimized
  architecture structure;
- scenario and target delivery form;
- selected source surface and adapter counts;
- workflow/privacy/data-classification strategy;
- hard constraints such as fact preservation, placeholder preservation, and
  markup preservation;
- required human confirmations for task intent, audience, claims/metrics, or
  coverage gaps.

Passing deterministic QA does not replace brief confirmation. The brief is the
first artifact boundary between "files were processed" and "the localization
task intent is understood."

## Source and Provenance

Keep the user-confirmed original artifact as project source of truth. Record unit-level linguistic or cultural provenance for names, quotations, transliterations, and imported concepts. Never promote uncertain reverse transliteration into project fact without evidence or user confirmation.

## QA Evidence

Keep three evidence channels distinct:

- Runtime/adapter QA proves deterministic structure and round-trip properties.
- Agent QA records linguistic and cultural findings with evidence and confidence.
- Human review and scoped sign-off determine acceptance.

The agent may produce `review_ready`; only explicit user action produces `user_accepted`.
