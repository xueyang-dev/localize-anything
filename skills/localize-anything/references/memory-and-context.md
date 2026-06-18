# Memory And Context

## Canonical Memory

Maintain four assets for standard projects:

- `localization-context.md`: semantic project memory and approved decisions.
- `glossary.csv`: term-level constraints and provenance.
- `translation-memory.jsonl`: segment-level reuse by target locale.
- `delivery-manifest.json`: machine facts, file mapping, run state, and sign-off scope.

Keep long-lived state in `.localize-anything/`. Copy relevant immutable snapshots into each delivery package.

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

## Promotion

After each batch, route information by function:

- strategy, character, narrative, or cross-file decisions -> context
- reusable terms and names -> glossary
- processed segments -> TM
- defects and unresolved questions -> QA report

Promote only within accepted locale, content, file, and batch scope.
