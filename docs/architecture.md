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
 -> Generation Strategy Gate
 -> Resolution Gate
 -> Generation Handoff Enforcement
 -> Artifact State Check
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
generation-strategy.json
blocking-questions.json
resolution-options.json
user-resolution-decisions.jsonl
resolution-summary.md
generation-handoff-decision.json
artifact-state.json
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

## Generation Strategy Gate

Generation strategy runs after deterministic preflight inputs exist and before
generation handoff. The seed gate writes `generation-strategy.json` from the
localization brief, termbase preflight report, operating mode, reference policy,
and batch plan.

The strategy does not translate and does not call providers. It decides whether
generation is `ready`, `review_required`, or `blocked`, and records the intended
route:

- `standard_handoff` for deterministic handoff with no blocking review signals;
- `high_assurance_handoff` when generation may proceed but high-risk review
  signals remain visible;
- `blocked` when unresolved governance conflicts would make generation unsafe.

Work packets include a compact `memory.generation_strategy` summary. Draft
requests repeat blocked or review-required strategy state so host-agent
workflows cannot silently claim full assurance. The gate consumes Termbase
Preflight and Term Governance output; it does not replace the UI-first term
review queue or invent terminology decisions.

## Resolution Gate

Resolution Gate runs after Generation Strategy Gate. It turns blocked or
review-required strategy states into structured owner decisions instead of
hiding them inside prompt instructions.

The seed gate writes:

- `blocking-questions.json`: stable question ids, source artifact references,
  severity, owner type, affected terms or segments, recommended defaults,
  available options, and whether human confirmation is required.
- `resolution-options.json`: conservative actions such as keeping generation
  blocked, approving or deferring a term, requiring a localization brief,
  allowing partial coverage with an explicit warning, or blocking unsafe
  provider policy.
- `user-resolution-decisions.jsonl`: append-only user decisions.
- `resolution-summary.md`: human-readable debug and delivery evidence.

Term approval decisions reuse the Termbase Preflight review path so approved or
locked terms can still flow into Term Governance and later hard constraints.
Coverage decisions update generation strategy state without claiming full
visible coverage. Provider fallback or unsafe provider policy must remain an
explicit provider-backed generation blocker until provider policy is safe.

The current Workbench/API surface is artifact-backed only: clients can read
blocking questions and resolution options and post user decisions. A full visual
review panel belongs to a later UI loop.

## Generation Handoff Enforcement

Generation Handoff Enforcement runs after Generation Strategy Gate and
Resolution Gate and before work packets are treated as executable generation
handoff. It writes `generation-handoff-decision.json`, a deterministic artifact
that answers two separate questions:

- whether any full-quality generation handoff is allowed;
- whether a downgraded handoff may proceed, and under which apply/delivery
  policy.

The gate reads `generation-strategy.json`, `blocking-questions.json`,
`resolution-options.json`, `user-resolution-decisions.jsonl`, termbase preflight
status, terminology assurance, provider policy, and coverage policy. It blocks
full-quality handoff when strategy is blocked, `allow_generation` is false,
blocking questions or term conflicts remain unresolved, unsafe provider fallback
is requested in real provider mode, provider policy is missing or unsafe for
provider-controlled generation, high-risk terms still need confirmation,
partial coverage lacks explicit allowance, required brief information is
missing, or a resolution decision tries to override a non-overridable safety
blocker.

Downgraded modes are explicit: `draft_only`, `review_required`,
`allowed_with_warnings`, and `source_only_with_partial_coverage_warning`. A
downgraded handoff records why it is downgraded, which questions remain
unresolved, which user decisions allowed continuation, which quality claims are
forbidden, and whether delivery/apply should be blocked, warned, or allowed.

Provider fallback is fail-closed. Synthetic fallback is allowed only for
explicit synthetic/test output and cannot be silently presented as
provider-backed quality. Unsafe provider fallback and unsafe provider policy are
non-overridable through ordinary resolution decisions.

Run summaries and delivery packages consume the same artifact so they cannot
claim full terminology assurance, full source coverage, provider-backed quality
after provider failure, review-complete status with unresolved high-risk terms,
or safe apply readiness when generation readiness is blocked or review-required.
Workbench exposes the artifact through a minimal API endpoint; full visual UI
comes later because policy enforcement must exist before presentation.

## Artifact State Machine

Artifact State Machine runs after linked pre-generation artifacts exist and
whenever handoff, delivery, or apply readiness is checked. It writes
`artifact-state.json`, a machine-readable index of important state and run
artifacts, their content hashes, source dependency hashes, status, producing
stage, blocking reason, and downstream artifacts affected by staleness.

Supported statuses are `missing`, `draft`, `current`, `stale`, `superseded`,
`blocked`, `accepted`, `rejected`, and `requires_human_review`. The seed engine
is conservative: source inventory or segment changes make generated output,
review results, strategy, handoff decision, and delivery decisions stale; brief,
term governance, term review, resolution, generation strategy, handoff decision,
generated segment, and review-result changes make their downstream evidence
stale until the affected artifacts are regenerated or reviewed.

Generation Strategy Gate, Resolution Gate, and Generation Handoff Enforcement
remain the sources of their own policy decisions. Artifact State Machine does not
invent user decisions or provider policy; it records whether those decisions are
still current enough to be used as evidence. Generation handoff must not use
stale strategy, brief, term, or resolution artifacts to justify full-quality
readiness. Delivery decision and apply planning must surface stale evidence and
block apply when it affects generated files or safety policy.

Run summaries and delivery packages include artifact state so reviewers can see
which artifacts are current, which are stale, which decision is affected, and
what needs to be regenerated. Workbench exposes this through an artifact-backed
API endpoint; the visual UI should display `artifact-state.json`, not infer
freshness from filenames or timestamps in the browser.

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
