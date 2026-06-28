# Memory And Context

## Canonical Memory

Maintain artifact-backed project memory for standard projects. The exact set
depends on the delivery level, but current canonical memory may include:

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
generation-strategy.json
blocking-questions.json
resolution-options.json
user-resolution-decisions.jsonl
generation-handoff-decision.json
artifact-state.json
stale-segments.jsonl
reuse-decision.json
segment-regeneration-plan.json
repair-request.json
repair-result.json
repair-history.jsonl
evaluation-scorecard.json
evidence-level-report.md
human-review-evidence.jsonl
claim-acceptance-decision.json
signoff-record.json
delivery-manifest.json
delivery-decision.json
apply-plan.json
```

Keep long-lived state in `.localize-anything/`. Copy relevant immutable snapshots into each delivery package.
Do not turn rebuildable indexes, embeddings, browser state, or chat summaries
into a source of truth.

## Context Priorities

Always load P0: project contract, source of truth, target audience/locales, content strategy, hard constraints, approved decisions, QA contract, and blockers.

Retrieve P1 by relevance: characters, entities, relationships, world/domain notes, narrative state, locale notes, adapter constraints, and recent relevant batch facts.

Keep P2 archived: rejected alternatives, old logs, long summaries, and resolved low-risk review notes.

Do not store complete source text, complete translations, private reasoning, duplicated adapter rules, or unverified guesses as facts.

## Working Context Packet

Build the packet ephemerally from canonical context, relevant glossary rows, relevant TM segments, and adapter constraints. Do not save it by default. In debug or benchmark mode, save it outside the standard delivery package and record its references and budget.

Allocate context approximately as follows when runtime limits are known:

- working context: 20%
- current source batch: 40%
- expected output: 20%
- QA and repair: 10%
- safety reserve: 10%

Use conservative limits when the runtime cannot report a context window. Shrink the batch before dropping P0 or hard constraints.

## Retrieval

Prefer accepted decisions, exact glossary matches, exact segment IDs, exact source matches, and only then high-confidence fuzzy TM matches within compatible scope and content type. Do not cross target locales. Treat generated memory as reference, not authority.

Use canonical files as source of truth. Permit a rebuildable SQLite index for lookup; do not require embeddings in v0.1.

Knowledge-pack and Document Evidence Pack assets are roadmap features unless the
current runtime writes their protocol artifacts. Treat imported glossaries,
translation memories, examples, and style notes as reference material until
their provenance, scope, and review status are explicit.

## Promotion

After each batch, route information by function:

- strategy, character, narrative, or cross-file decisions -> context
- reusable approved or locked terms -> term governance
- reviewed segment targets -> translation memory within accepted scope
- defects, unresolved questions, stale evidence, and repair outcomes -> QA,
  scorecard, repair, or delivery-decision artifacts

Promote only within accepted locale, content, file, and batch scope.
