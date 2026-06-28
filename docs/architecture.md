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
 -> Patch-Based Repair Execution
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

## Segment-Level Staleness / Reuse Decision

Segment-Level Staleness extends Artifact State Machine from whole artifacts to
individual source segments. It writes `stale-segments.jsonl` and
`reuse-decision.json` so the runtime can distinguish segments that can be
reused, segments that need re-review, and segments that must be regenerated or
targeted-repaired.

The seed engine is deterministic. It compares source text hashes, source
context hashes, placeholder/markup signatures, localization brief hash, term
governance hash, term-review decision hash, generation strategy hash,
provider-policy hash when supplied, previous target hash, and review-policy or
review-result hash when supplied. It does not call an LLM and it is not a full
Translation Memory implementation.

Reuse policy is conservative: source text or placeholder/markup signature
changes require regeneration; term-policy changes affect only segments
containing known terms; strategy, provider, or review-policy changes require
re-review when reuse may still be acceptable; unrelated artifact changes allow
reuse. High-risk segments affected by policy changes remain review-required
even when the target text can be reused.

Artifact State Machine summarizes stale segment counts and applies those counts
to handoff, delivery, and apply readiness. Generation handoff cannot claim
full-quality readiness while required stale segments remain unresolved. Delivery
and apply block when stale generated segments affect staged files. Run summaries
and delivery packages include both segment-level artifacts so reviewers can see
the concrete affected segment ids.

This seed comes before Document Evidence Pack because document-level evidence
cannot safely reuse prior review or source coverage unless segment reuse
boundaries are already explicit. It also prepares the future Targeted Repair
Loop: segments marked `needs_regeneration` may later be routed to full
regeneration or targeted repair, while `needs_re_review` can stay on a cheaper
human-review path.

Workbench exposes artifact-backed API endpoints for stale segments and reuse
decisions. A full visual panel should render those artifacts rather than infer
freshness in browser state.

## Targeted Repair / Segment Regeneration Plan

Targeted Repair consumes `stale-segments.jsonl` and `reuse-decision.json` and
writes `segment-regeneration-plan.json`, `repair-request.json`,
`repair-result.json`, and `repair-history.jsonl`. It is a deterministic
planning gate, not a Translation Memory system and not an LLM repair executor.

The planner assigns one action per segment: `reuse`, `regenerate`,
`re_review`, `targeted_repair`, `human_confirm`, or `blocked`. Source text
changes and placeholder or markup signature changes require regeneration;
placeholder/markup changes also require deterministic QA. Term-policy changes
for segments containing affected known terms become targeted repair when that
is allowed, otherwise regeneration. Generation strategy, provider policy, or
review policy changes can route a segment to re-review. High-risk unresolved
segments require human confirmation or are blocked.

`repair-request.json` is the actionable queue for repair work. Each item has a
stable repair id, source artifact references, repair type, reason, previous
target hash when available, required constraints, risk level, and whether human
confirmation is required. `repair-result.json` records only deterministic
runtime outcomes. If a repair would require provider or model generation, the
result stays pending instead of inventing target text. `repair-history.jsonl`
appends every repair decision so repeated runs remain auditable.

Generation Handoff Enforcement reads the regeneration plan before allowing a
full-quality handoff. Pending regeneration, targeted repair, human
confirmation, or blocked segments block full-quality readiness and safe apply
claims; re-review-only segments downgrade readiness. Delivery decisions and
apply planning surface pending repairs and block apply when required repairs
affect staged files.

This loop comes before a Patch-Based Repair Loop because repair execution needs
a stable, reviewable plan first. Workbench exposes artifact-backed read
endpoints for the plan, repair request, and repair history; the visual UI should
display these artifacts rather than reimplementing planner rules in browser
state.

## Patch-Based Repair Execution

Patch-Based Repair Execution is the deterministic execution layer after the
segment regeneration plan. It reads `segment-regeneration-plan.json`,
`repair-request.json`, generated segment artifacts when provided, term
governance artifacts, generation strategy/handoff context, and artifact state.
It updates `repair-result.json` and appends `repair-history.jsonl`.

The seed intentionally supports only narrow, mechanically verifiable patches:
placeholder normalization, recoverable markup tag restoration, XML/Android
escape fixes, locked/approved term replacements with exact old-term matches,
and review-only decisions. Every applied repair records old/new target hashes,
the deterministic rule used, QA result, source artifact references, and whether
the generated segment artifact was updated.

Anything requiring semantic judgment remains pending. That includes risk
wording, style changes, coverage repair, segment regeneration, missing old
target text, ambiguous term replacement, provider/model repair, and high-risk
segments without human confirmation. The execution layer must not invent target
text; if the old target is not available, it records why no patch was applied.

Deterministic QA runs after each applied patch. Failed QA is recorded as
`failed_qa` and continues to block or downgrade handoff, delivery, and apply
readiness. Pending, blocked, skipped, or failed repairs remain visible in
artifact-state, run summary, delivery decision reports, and delivery packages.

Workbench exposes artifact-backed `GET /api/repair-result` and a minimal
`POST /api/apply-repair-plan`. The POST endpoint executes only deterministic
rules and does not call providers. A richer visual UI should come after this
enforcement layer so the UI displays runtime decisions instead of duplicating
repair policy.

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
