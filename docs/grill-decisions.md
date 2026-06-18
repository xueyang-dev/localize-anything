# Grill Decision Record

## Status

Accepted product and architecture decisions. This document is the canonical,
process-free result of the design grill. It supersedes the conversational
question-and-answer trail; implementation details must remain consistent with
the protocol, schemas, and accepted ADRs.

## Product Definition

- The project is named **Localize Anything**.
- It is an agent-native localization framework, not only a prompt or a single
  platform skill.
- Its architecture is **protocol-first, workflow-driven, skill-integrated, and
  adapter-extensible**.
- Its core promise is to turn source artifacts into review-ready target-locale
  deliverables while preserving usable structure, context, terminology,
  provenance, QA evidence, and delivery state.
- Translation is one stage of localization. The framework must support direct
  return to the original content structure, such as generating usable language
  files inside a game project.
- The runtime and protocol are provider- and model-agnostic. The host agent is
  the semantic executor; v0.1 does not add a separate translation-provider
  abstraction.
- The project uses the MIT license.

## Architecture

The framework has four replaceable layers:

1. A portable localization protocol for artifacts and lifecycle rules.
2. A reference workflow runtime and CLI for deterministic operations.
3. Thin integrations for Codex, Claude Code, and other agent hosts.
4. An adapter ecosystem for repeatable format, scenario, and platform SOPs.

The canonical core stays independent from agent hosts. Integrations translate
host capabilities into protocol operations without forking core behavior.

## Intake And Operating Modes

- Confirm which material is the actual source before localization begins.
- Honor target locales explicitly provided by the user. When targets are
  missing, ask and suggest common or market-relevant locales.
- Use **Delivery Mode** when the project already has a localization entrypoint.
- Offer **Enablement Mode** when no entrypoint exists, and explain the proposed
  project restructuring before changing files.
- Choose localization depth automatically by content type, declare that choice
  during intake, and allow the user to change it.
- During preflight, assess whether the work needs a fast, standard, or
  high-assurance multi-stage workflow. Recommend one and let the user choose.

Delivery levels are:

- `inline` for short, independent localization returned in chat.
- `lightweight_file` for a localized file with compact manifest and QA data.
- `standard_project` for reusable memory, multiple files or locales,
  incremental work, or apply-in-place delivery.

Standard projects default to **bundle-first** delivery. Apply-in-place remains
available after an explicit plan and confirmation.

## Standard Project Assets

Long-lived project state lives under `.localize-anything/`. Every standard
delivery is an immutable snapshot containing:

```text
delivery-manifest.json
localization-context.md
glossary.csv
translation-memory.jsonl
qa-report.md
files/
```

`delivery-manifest.json` is mandatory machine-readable delivery metadata.
Questions and unresolved issues belong in `qa-report.md`; a separate
`open-questions.md` is not mandatory.

## Four-Layer Memory

- `localization-context.md` is the semantic project memory: source truth,
  audience, strategy, story or domain summary, entities, relationships, voice,
  cultural notes, and approved decisions.
- `glossary.csv` stores term-level constraints, approved forms, scope, and
  provenance.
- `translation-memory.jsonl` stores reusable source-target segments and review
  state. TMX is a later interchange export, not the canonical v0.1 store.
- `delivery-manifest.json` stores machine state, files, versions, adapter facts,
  hashes, QA status, and delivery scope.

The ephemeral working context packet is not a fifth memory layer. It is built
for a batch, may be recorded for debugging or benchmarks, and never becomes a
new source of truth.

Agents read the relevant memory before every stage and update canonical memory
after each completed batch. Promotion rules are:

- strategy, narrative, entities, and accepted project facts go to context;
- terms and naming constraints go to the glossary;
- reusable reviewed segments go to translation memory;
- defects, risks, questions, and unprocessed assets go to QA.

Scoped acceptance promotes knowledge only within the accepted locale, content,
file, batch, and review scope. Human review import compares edits, updates
reviewed TM, and proposes wider context or glossary changes without blindly
learning them globally.

## Context Loading And Preflight

Batch is the main context-loading axis, adjusted by task type. Batches are split
by semantic content units and adapter constraints rather than token count alone:
screens or namespaces for UI, scenes or conversations for dialogue, timed
scenes for subtitles, sections for documents, and sheets or features for tabular
content.

Context priority is:

- **P0, always load:** source truth, audience, strategy, hard constraints,
  accepted decisions, active QA blockers, and current delivery contract.
- **P1, retrieve as relevant:** entities, characters, world or domain facts,
  locale guidance, adapter constraints, glossary matches, reviewed TM, and
  recent batches.
- **P2, archive:** rejected alternatives, historical detail, long summaries,
  and low-value background.

Do not store full source files, full translations, private reasoning, duplicated
adapter rules, or unverified guesses as project facts.

Use an adaptive context budget. The initial target is approximately 20% durable
working context, 40% current source batch, 20% expected output, 10% QA and
repair, and 10% safety reserve. When constrained, shrink the batch before
dropping P0 material or hard constraints.

Preflight should scan all source material when it fits. Otherwise scan in
bounded layers, updating a compressed initial context that captures names,
titles, background, relationships, recurring concepts, running jokes, and other
cross-batch dependencies. Deep semantic preflight may be skipped for extremely
long, weakly connected practical text, but source confirmation, format checks,
hard constraints, manifest setup, and QA setup remain mandatory.

Canonical files are primary storage. A rebuildable SQLite index may accelerate
retrieval; a vector database is not required in v0.1.

## Source Truth And Multi-Locale Work

- Every target locale is grounded in the user-confirmed original source.
- Locales may share source analysis, but localization, QA, review, and sign-off
  remain independent per locale.
- Pivot translation is forbidden unless the user explicitly approves it.
- For mixed-language names, items, quotations, or cultural references, record
  unit-level detected origin, canonical native form when known, confidence, and
  status. Do not silently reverse-transliterate uncertain forms.
- Resolve provenance from project data first, then existing locale files or
  documentation, user glossary, authoritative external sources, and finally
  clearly marked inference.

## Localization Policy

Default depth depends on content:

- UI copy should be natural and spatially practical.
- Errors should remain actionable.
- Dialogue should preserve character voice and adapt cultural meaning.
- Marketing may require market rewriting.
- Slogans may require transcreation.
- Documentation prioritizes precision.
- Legal and regulatory content receives conservative review-draft treatment
  with explicit risk notes.

Globally understandable dates, currencies, times, and units keep their original
format by default. Detect ambiguous or market-sensitive cases and ask before
adapting them; do not silently convert values.

Images and audio are inventoried but deferred from the initial text workflow.
Every unprocessed non-text asset must appear in QA so text completion cannot be
mistaken for complete product localization.

Questions are batched at stage boundaries. Ask blocking questions before the
affected batch; continue independent work when possible. Preserve uncertain
content conservatively and record non-blocking issues in QA.

## Adapter Contract

Adapters exist to make format handling repeatable and verifiable, not because
agents cannot read common formats. They implement:

```text
detect -> inventory -> extract -> validate-source
       -> rebuild -> validate-output -> plan-apply
```

- Adapters communicate through language-neutral JSON or JSONL.
- Adapters never translate. The runtime owns scheduling, permissions,
  manifests, staging, apply operations, and rollback metadata.
- Compose adapters as format adapter plus scenario adapter plus optional
  platform overlay.
- Capability levels are `full_round_trip`, `extract_and_rebuild`,
  `extract_only`, `inspect_only`, and `unsupported`.
- Prefer native core adapters. Users may explicitly select or fork a custom
  adapter.
- Core adapters are open source and editable. A project fork uses copy-on-write
  under `.localize-anything/adapters/<custom-id>` so upstream updates cannot
  overwrite it.
- Private adapters may stay local or be shared by their author. Sensitive
  projects may use reference-only or vendored snapshots according to policy.
- Dependencies must be declared, isolated, version-locked, and installed only
  with consent. Do not pollute global or source-project environments.
- Multiple matches resolve by explicit user selection, project lock, core,
  verified community, then generic fallback.
- Pseudo-localization is optional and must not pollute glossary, TM, or context.

The initial repository keeps core and scenario adapters together. Automatic
community discovery and installation follow later with checksums, trust tiers,
permissions, fixtures, contract tests, and explicit installation.

## QA, Delivery, And Acceptance

QA keeps three evidence channels separate:

1. Runtime and adapter QA for parsing, schema, keys, coverage, placeholders,
   ICU branches, markup, encoding, escaping, IDs, paths, hashes, round-trip, and
   manifest integrity.
2. Agent linguistic and cultural QA for accuracy, omissions, fluency,
   terminology, style, voice, coherence, adaptation, and provenance. Findings
   include evidence, severity, confidence, and action.
3. Human review and scoped sign-off.

Use multidimensional statuses rather than one composite quality score:
`pass`, `pass_with_warnings`, `review_required`, `fail`, `not_applicable`, or
`not_checked`.

Delivery states are `draft_package`, `review_ready`, `blocked`,
`applied_draft`, and `user_accepted`. The agent may produce a final draft or
`review_ready` package, but only the user can decide that work is complete.
Sign-off records the accepted locale, files, content, batches, and immutable
manifest hash.

Chat reports high-signal blockers and warnings. `qa-report.md` remains the full
engineering record, and the manifest remains the machine-readable state.

Layout-dependent artifacts require visual QA when applicable. If it cannot run,
record `visual_qa_not_run` and downgrade the claim. High-risk specialist content
remains review-required.

Apply-in-place requires staged writes, a dry-run diff, explicit confirmation,
backup or rollback metadata, and post-apply validation. Never silently
overwrite or delete source material.

## Incremental Localization

Use stable segment IDs and source hashes to classify `new`, `unchanged`,
`changed`, `moved`, `deleted`, and `conflicted` units. Do not retranslate
unchanged content. Mark changed targets stale. Never delete removed source units
from a destination without an explicit apply decision.

The normal multi-stage loop is generation, structural QA, linguistic review,
targeted repair, revalidation, then memory promotion. Repair affected units
instead of rewriting an entire batch without cause.

## Privacy And Capability Disclosure

- Offer optional data classes: public, internal, confidential, and restricted.
- Offer standard, minimal-disclosure, and local-only handling.
- Minimize external disclosure and never place credentials in memory or
  delivery bundles.
- Declare locale capability as `direct_supported`, `supported_with_review`,
  `specialist_review_required`, or `insufficient_capability`.
- Do not claim native-level quality without a qualified human reviewer.

## Benchmarking

The public end-to-end benchmark uses **Battle for Wesnoth: The South Guard**,
`en-US` to `zh-CN`.

- Pin the source commit and hide the existing target translation during blind
  generation.
- Existing translations may be separate evaluation references, never source
  truth or the sole quality standard.
- Record effective variables: agent/runtime, model and version, context window,
  settings, tools, adapter versions, source commit, target locale, workflow
  depth, privacy policy, preflight mode, glossary and TM availability, network,
  human intervention, and local hardware when relevant.
- Evaluate round-trip correctness, localization quality, cross-batch
  consistency, context efficiency, token use, incremental behavior, and human
  review outcomes.
- Separate controlled model benchmarks from real-world agent-system benchmarks.
- Label evidence levels from E0 structural through automated linguistic checks,
  bilingual review, native review, and professional localization review. Lack
  of human review limits claims but does not block the v0.1 engineering slice.

Disco Elysium may be used only as a private, user-owned stress test. Do not
commit copyrighted source text, translations, TM, or context; publish aggregate
metrics only. The core project does not unpack or bypass protections on
commercial games.

## Release Scope

### v0.1 Alpha

- Protocol schemas and examples.
- Lightweight deterministic runtime and CLI.
- Four-layer project memory initialization.
- Source confirmation, preflight inventory, workflow recommendation, batch
  planning, and working packet contracts.
- Stable segment IDs, hashes, and incremental diff.
- Generic JSON, GNU gettext PO/POT, and Wesnoth scenario adapters.
- Staged rebuild, deterministic QA, immutable packaging, review import, scoped
  sign-off, and apply dry-run.
- Reproducible blind Wesnoth benchmark definition and fixtures.

### v0.1 Beta

Add YAML/TOML, CSV/TSV/XLSX, Markdown/HTML, SRT/VTT, and XLIFF with round-trip
coverage.

### v0.2 And Later

Add Android/iOS resources, generic game and web enablement, visual QA,
Unity/Godot/Unreal/Ren'Py, document formats, image and audio localization, MCP,
and the governed community adapter ecosystem.
