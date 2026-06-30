# Architecture

## North Star

Localize Anything is an agent-native localization framework, not a translation prompt. Its core promise is to produce a review-ready, traceable delivery package that can be applied to the source project without silently damaging structure.

This file describes the current repository-facing architecture and keeps stable
claims, seed claims, and experimental/non-claim areas separate. Future-facing
vision lives in [Architecture Roadmap](architecture-roadmap.md).

## Product Thesis

Localize Anything is a localization engineering harness:

```text
Model     -> semantic generation and semantic judgment
Runtime   -> deterministic validation, state, boundaries, and delivery
Artifacts -> evidence, traceability, reproducibility, and review state
Human     -> high-risk decisions and final authorization
```

The optimized target combines:

```text
source project or document
+ project/file structure
+ task intent and scenario constraints
+ user-approved translation knowledge
+ model generation
+ deterministic QA
+ semantic and human review
-> review-ready, traceable, safely applicable delivery artifacts
```

The runtime must not treat processed files, generated text, or structural QA as
task completion. A localization run needs evidence for task intent, source
surface coverage, terminology, provider state, review state, repair state, and
delivery/apply readiness.

The target architecture also defines scoped Project, Knowledge Curator,
Generation, Review, Delivery, and Evolution subagent responsibilities. Those
are roadmap boundaries, not a claim that a production subagent runtime exists.

## Scope Boundaries

Current v0.x focus is Android application resources plus institutional Word
document localization. The architecture is designed for broader "any project"
coverage, but unsupported platforms remain non-claims until adapters, runtime
contracts, and benchmark evidence exist.

Current conservative scope:

- Android source resources are supported; merged dependency overlays are
  experimental and opt-in.
- Word OpenXML documents are supported; legacy binary `.doc`, image text, and
  embedded object localization are non-claims.
- iOS/macOS, Web framework i18n, XLIFF/PO hardening, subtitles, and advanced
  tabular formats are roadmap areas unless implemented by a specific adapter.
- Desktop apps, game engines, non-text asset localization, runtime dynamic
  content, server-returned copy, push notification text, OS strings, and
  hardcoded inline code strings are outside current stable scope.
- Locale engineering features such as plural rules, grammatical gender, RTL/
  bidi layout, date/time/number/currency formatting, Unicode normalization, and
  fallback-locale chains are recognized gaps until implemented and surfaced in
  runtime evidence.

## Status Model

- Stable baseline: released, tested, documented, and backed by regression or
  real-project evidence.
- Architecture seed: functional code exists on main or an active PR, but the
  capability should not be described as complete or production-stable until a
  release audit and evidence pass.
- Experimental: implemented behind opt-in or investigation paths and not a
  default product claim.
- Non-claim: recognized by the architecture but not implemented.

## Progress Snapshot After PR #57

Repository presence, release stability, and public support claims are separate
states. A merged architecture seed is implemented and tested, but it is not a
stable production capability until a release audit, real-project regression
evidence, benchmark evidence, documentation audit, and public-claim review all
support promotion.

| Status | Current scope |
| --- | --- |
| Stable public baseline | Released v0.4.1 behavior: protocol/runtime contracts, staged delivery, explicit apply confirmation, deterministic structural QA, Workbench UI wiring, and released adapter capabilities within their documented format boundaries. |
| Implemented architecture seeds | Evidence Spine gates through provider result QA/review acceptance: document evidence, personal knowledge, knowledge consumption/audit/repair, readiness authorization, workflow lifecycle/resume/hardening, provider handoff evidence, and provider result QA/acceptance. |
| Active draft / under review | Locale Capability Report seed. It adds conservative locale-engineering evidence and claim downgrades, not full CLDR or full-product localization support. |
| Experimental | Explicit opt-in Android merged dependency overlays, synthetic/mock provider paths, and other opt-in adapter or benchmark surfaces identified as experimental in their own docs. |
| Explicit non-claims | Complete product or Android-app localization, locale-complete support, automatic semantic quality, provider- or knowledge-backed quality without scoped evidence, DOCX render fidelity, factual truth verification, and automatic destructive apply. |

Architecture progress by PR range:

| PR range | Architecture area | Current classification |
| --- | --- | --- |
| #25–#36 | Evidence Spine foundations | Implemented seeds; selected released foundations are stable only where release evidence says so. |
| #37–#39 | Workbench review, action, and console | Implemented seeds. |
| #40–#42 | Document Evidence enforcement and decisions | Implemented seeds. |
| #43–#47 | Personal Knowledge, Knowledge Audit, and Knowledge Assurance | Implemented seeds. |
| #48–#50 | Knowledge Repair, closure, and recompute | Implemented seeds. |
| #51–#52 | Readiness Matrix and Workbench readiness actions | Implemented seeds. |
| #53–#55 | Workflow orchestration, incremental resume, and hardening | Implemented seeds. |
| #56–#57 | Provider handoff evidence and provider result QA/review acceptance | Implemented seeds; no provider-backed quality claim follows from intake or QA alone. |
| #58 | Architecture and roadmap progress synchronization | Documentation and public claim boundaries synced with implemented seed state. |
| Current | Locale Capability Report | Active seed; locale-complete, RTL-safe, plural-complete, formatting-complete, and full-product claims remain forbidden unless evidence supports them. |

## Public Claim Boundary

Public wording may claim the released engineering baseline and may describe
merged work explicitly as an architecture seed. It must not convert a seed,
experimental path, or narrow evidence result into a stable or global claim.

Localize Anything does not currently claim:

- complete Android app localization or zero residual English;
- production-ready provider translation quality, or provider-backed quality
  from result intake, reconciliation, or deterministic QA alone;
- full knowledge-backed quality without matching scope, qualified review, and
  compatible signoff;
- locale-complete support across plural, gender, RTL/bidi, formatting, Unicode,
  and fallback behavior;
- DOCX layout or rendered-page fidelity;
- real-world factual truth verification for translated claims;
- full product localization when image, audio/video, layout, dynamic, server,
  OS, or other runtime surfaces are outside the selected source scope;
- automatic destructive apply or an apply operation without a staged plan and
  explicit confirmation.

## Layers

### Localization Protocol

Define machine-readable contracts for project configuration, adapters, segments, QA results, manifests, memory assets, and scoped sign-off. Keep the protocol independent from a model vendor and implementation language.

### Reference Runtime

Perform deterministic work: adapter discovery, extraction, stable IDs, hashes, schema validation, structural QA, incremental diffing, packaging, apply planning, and rollback metadata. Do not translate content.

### Agent Integration

Perform semantic work: intake, source confirmation, preflight interpretation, workflow recommendation, context selection, localization, linguistic review, ambiguity resolution, and user communication.

### Adapter Ecosystem

Implement format, scenario, and platform SOPs through a language-neutral JSON/JSONL contract. Prefer core adapters, permit project-local forks, and reserve a community registry for later releases.

## System Rules

```text
Model may suggest.
Runtime must verify.
Artifacts must preserve evidence.
Human must authorize high-risk and final acceptance.
```

No major decision should live only in a prompt, UI state, or chat transcript.
Every gate that affects generation, delivery, or apply readiness should produce
or consume durable artifacts.

The system must never silently report success when a required layer failed. For
example:

- real provider requested but provider failed -> do not claim provider-backed
  quality through synthetic fallback;
- Android source-only resources pass -> report visible UI coverage risk when
  merged dependency resources or runtime strings are out of scope;
- Word document text is translated -> report whether audience, genre, claims,
  terminology, and review evidence support the requested delivery claim.

## Workflow

```text
Intake
 -> Capability Scan
 -> Source-of-Truth Confirmation
 -> Target Locale Confirmation
 -> Locale Capability Report
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
 -> Evaluation Scorecard
 -> Human Review Evidence Intake
 -> Claim Acceptance Gate
 -> Delivery Package
 -> Review Import
 -> Signoff Record
 -> Optional Apply-in-Place
```

## Evidence Spine

The Evidence Spine is the current architectural backbone. It connects each
pre-generation, generation, review, repair, delivery, and signoff decision into
a traceable artifact chain.

```text
Localization Brief
 -> Term Governance
 -> Termbase Preflight
 -> Generation Strategy
 -> Resolution Gate
 -> Generation Handoff Enforcement
 -> Working Context / Knowledge Constraints
 -> Provider Handoff Evidence
 -> Generation Result Intake
 -> Deterministic QA
 -> Knowledge Usage / Conflict / Constraint Audit
 -> Document Evidence / Decision / Leadership Review
 -> Knowledge and Provider Repair / Reconciliation / Closure
 -> Provider Result QA / Scoped Review / Acceptance / Claim Support
 -> Evaluation Scorecard
 -> Human Review Evidence
 -> Claim Acceptance
 -> Signoff
 -> Readiness Authorization Matrix
 -> Workbench Readiness Actions
 -> Delivery / Apply Decision
```

Artifact State and workflow lifecycle controls surround the chain rather than
forming a single linear gate. They track staleness, orchestrate deterministic
builders, resume interrupted work, selectively recompute affected projections,
and record checkpoint/lock/idempotency evidence. None of those controls can
fabricate provider execution, human review, repair success, or readiness.

Each link has a specific contract:

| Gate | Artifact(s) | Enforces |
| --- | --- | --- |
| Localization Brief | `localization-brief.json`, `localization-brief.yaml` | Task intent and human confirmations are visible before generation. |
| Term Governance | `term-registry.csv`, `term-decisions.jsonl`, `forbidden-translations.csv` | Terminology decisions are explicit and reusable. |
| Termbase Preflight | `candidate-terms.jsonl`, `termbase-preflight-report.json`, `term-review-queue.json` | High-risk terminology is visible before drafting. |
| Generation Strategy | `generation-strategy.json` | Provider, mode, coverage, and fallback strategy are explicit. |
| Resolution Gate | `blocking-questions.json`, `resolution-options.json`, `user-resolution-decisions.jsonl` | Blocking questions become traceable owner decisions. |
| Handoff Enforcement | `generation-handoff-decision.json` | Full-quality and downgraded handoffs are enforced before execution. |
| Artifact State | `artifact-state.json` | Stale or missing evidence cannot justify readiness. |
| Segment Staleness | `stale-segments.jsonl`, `reuse-decision.json` | Changed segments are regenerated, reviewed, or reused conservatively. |
| Targeted Repair | `segment-regeneration-plan.json`, `repair-request.json` | Repair scope is segment-level and deterministic before execution. |
| Patch Repair | `repair-result.json`, `repair-history.jsonl` | Only mechanically safe repairs are applied without providers. |
| Evaluation | `evaluation-scorecard.json`, `evidence-level-report.md` | Unsupported quality/readiness claims are forbidden. |
| Document Evidence Pack | `document-intake-report.json`, `semantic-alignment.jsonl`, `claim-metric-report.json`, `publicity-risk-report.json`, `leadership-review-brief.md`, `open-decisions.md`, `document-evidence-manifest.json` | High-context document evidence, claim risk, publicity risk, and leadership review needs are explicit. |
| Document Evidence Decision | Document enforcement, queue, decision, leadership review, claim-resolution, and signoff-summary artifacts | Document review blockers stay visible and scoped; leadership evidence does not become factual truth verification. |
| Personal Knowledge | Pack manifest, provenance, review queue/decisions, TM, term, style, claim-pattern, and revision-memory artifacts | Only reviewed, scoped, provenance-backed knowledge is eligible for promotion. |
| Knowledge Consumption | Selection, eligibility, and Working Context Packet artifacts | Hard constraints, soft context, examples, and excluded knowledge remain separate. |
| Knowledge Audit And Assurance | Usage, constraint audit, conflict, enforcement, resolution, and assurance artifacts | Knowledge use must match status, provenance, scope, freshness, and operating mode. |
| Knowledge Repair Lifecycle | Plan, request, impact, result intake, QA, reconciliation, closure, and recompute artifacts | Repair planning/intake cannot clear blockers without matching result and QA evidence. |
| Provider Evidence | Execution policy, handoff request, ledger, result intake, and reconciliation artifacts | External provider/model evidence is recorded without claiming runtime execution or semantic quality. |
| Provider Result Acceptance | QA report, scoped review evidence, acceptance decision, claim support report, and Workbench provider queue | QA pass is not semantic quality; limited acceptance remains limited and unsupported provider claims stay forbidden. |
| Locale Capability | `locale-capability-report.json`, `locale-risk-report.json`, `locale-readiness-impact.json` | Seed-level locale engineering evidence downgrades unsupported locale, RTL, plural, formatting, and full-product claims. |
| Human Review | `human-review-evidence.jsonl` | E2/E3/E4 evidence requires explicit qualified review. |
| Claim Acceptance | `claim-acceptance-decision.json` | User decisions cannot accept scorecard-forbidden claims. |
| Signoff | `signoff-record.json` | Owner authorization is separate from review evidence and claim truth. |
| Readiness Authorization | `readiness-authorization-matrix.json`, `manual-followup-gap-report.json`, `apply-readiness-report.json`, `delivery-readiness-report.json` | Delivery/apply readiness is explicit, scoped, and evidence-backed across the full pipeline. |
| Workflow Lifecycle Controls | Run plan/status/result/readiness, dependency graph, resume/recompute, invalidation, checkpoint, lock, transaction, recovery, and idempotency artifacts | Deterministic refresh and recovery preserve blockers; workflow completion does not imply success. |
| Delivery / Apply | `delivery-manifest.json`, `delivery-decision.json`, `apply-plan.json` | Delivery and source writes remain staged, reviewable, and blocked when evidence is insufficient. |

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
stale-segments.jsonl
reuse-decision.json
segment-regeneration-plan.json
repair-request.json
repair-result.json
repair-history.jsonl
evaluation-scorecard.json
evidence-level-report.md
document-intake-report.json
semantic-alignment.jsonl
claim-metric-report.json
publicity-risk-report.json
leadership-review-brief.md
open-decisions.md
document-evidence-manifest.json
human-review-evidence.jsonl
claim-acceptance-decision.json
signoff-record.json
readiness-authorization-matrix.json
manual-followup-gap-report.json
apply-readiness-report.json
delivery-readiness-report.json
workbench-action-log.jsonl
workbench-action-result.json
workbench-review-queue.json
workbench-claim-queue.json
workbench-signoff-summary.json
delivery-manifest.json
```

The working context packet is ephemeral. A rebuildable SQLite cache may index canonical memory, but never becomes a source of truth.

## Adapter And Scenario Model

Localize Anything separates three adapter layers:

- Format adapters preserve file structure and deterministic round-trip rules
  such as Android XML, Word OpenXML, PO, XLIFF, CSV, Markdown, or subtitles.
- Platform overlays describe platform-specific source surfaces such as Android
  merged dependency resources.
- Scenario adapters describe task intent, audience, risk, and delivery shape
  such as software UI localization, institutional publicity documents, or
  subtitle adaptation.

This separation keeps file parsing out of scenario policy and keeps future
platform support additive. A future adapter registry should require manifest
metadata, capability declarations, trust tier, and adapter contract tests before
an adapter can be treated as stable.

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

## Evaluation Scorecard

Evaluation Scorecard runs after deterministic QA, handoff enforcement,
artifact-state checks, segment reuse planning, and patch-based repair state are
available. It produces `evaluation-scorecard.json` plus the concise
human-readable `evidence-level-report.md`.

The scorecard is deliberately conservative. It summarizes what the current run
has actually proven across structural QA, provider status, terminology
assurance, coverage, resolution state, handoff readiness, artifact freshness,
segment reuse, repair readiness, review readiness, delivery readiness, and
apply readiness. Missing evidence does not become a positive claim.

Evidence levels are explicit:

- `E0_deterministic_structural_qa`: deterministic runtime or adapter checks.
- `E1_automated_semantic_or_policy_review`: automated policy, handoff,
  artifact-state, repair, delivery, or review artifacts.
- `E2_bilingual_human_spot_check`: explicit bilingual human spot-check
  evidence.
- `E3_native_language_review`: explicit native-language review evidence.
- `E4_professional_localization_review`: explicit professional localization
  review evidence.

The seed mostly computes E0/E1 readiness from existing artifacts. It must not
fabricate E2-E4; those levels remain `not_provided` unless explicit review
artifacts exist.

The scorecard emits `forbidden_claims` such as `full_coverage`,
`provider_backed_quality`, `full_terminology_assurance`, `review_complete`,
`delivery_ready`, `apply_ready`, and `production_ready` when the evidence chain
does not support those statements. Overall claim is derived from the weakest
required evidence, not from the happiest path.

Run summaries and delivery packages reference the scorecard and report so
Workbench and downstream reviewers read artifact-backed readiness instead of
inferring quality from UI state. The minimal Workbench path is
`GET /api/evaluation-scorecard`; a richer visual panel should come after this
runtime enforcement layer.

## Document Evidence Pack

Document Evidence Pack is the seed evidence layer for high-context document
localization. It is not a second translation system. It reads existing
segments, generated segments when present, Localization Brief, term governance,
termbase preflight, Evaluation Scorecard, human review, claim acceptance,
signoff, repair, delivery, and artifact-state evidence, then produces a
review-ready package for document owners and leadership reviewers.

The initial supported scenario is `institutional_publicity_case`. Other
document scenarios are marked unsupported or pending rather than forced through
generic publicity rules. `document-intake-report.json` records document type,
source genre, target delivery mode, target audience, locales, risk profile,
required confirmations, limitations, source artifacts, and evidence
dependencies.

`semantic-alignment.jsonl` records segment-level alignment modes:
`direct_rendering`, `split`, `merged`, `localized_rewrite`,
`explanatory_expansion`, `structural_relocation`, `english_only_bridge`,
`source_only_omitted`, and `unknown`. English-only bridge and source-only
omission are always flagged. Explanatory expansion requires traceable source
intent or human confirmation. Missing target text remains pending; the pack
must not invent target text.

`claim-metric-report.json` checks numbers, years, dates, course counts, school
counts, student/participant counts, person-times, person-days, awards,
recognitions, employment intention/outcome, trial use versus official adoption,
partnership claims, and project status. It does not prove real-world truth; it
only checks that available target text does not exceed or distort source claim
boundaries. Missing targets are `pending`/not evaluable.

`publicity-risk-report.json` surfaces external-facing risks such as
official-recognition overstatement, unsupported claims, achievement inflation,
metric boundary changes, name uncertainty, policy slogan literalism,
unconfirmed project status, sensitive wording, promotional tone, and audience
mismatch. `leadership-review-brief.md` summarizes purpose, audience,
high-risk terms, claim and publicity risks, open decisions, forbidden claims,
scorecard status, signoff status, and recommended review actions.

`open-decisions.md` aggregates unresolved blocking questions, term review
items, human-review gaps, claim-acceptance gaps, signoff gaps, publicity risks,
claim/metric risks, stale artifacts, and pending repairs. The final
`document-evidence-manifest.json` references every pack artifact plus existing
scorecard, human review, claim acceptance, signoff, and delivery evidence when
present.

Excel or spreadsheet exports are optional future convenience outputs, not the
primary review workflow and not the source of truth. JSON, JSONL, and Markdown
artifacts remain the protocol contract. Delivery packages may include the pack,
but the pack's existence never upgrades delivery/apply readiness. Evaluation
Scorecard, Human Review Evidence, Claim Acceptance, Signoff, Artifact State,
Repair, QA, and Handoff gates remain responsible for enforcement. Workbench
can display the pack later as an artifact-backed review surface.

### Document Evidence Enforcement And Queue

Document Evidence Pack artifacts now participate in the same enforcement chain
as generation, repair, scorecard, and signoff artifacts. `artifact-state.json`
tracks `document-intake-report.json`, `semantic-alignment.jsonl`,
`claim-metric-report.json`, `publicity-risk-report.json`,
`leadership-review-brief.md`, `open-decisions.md`, and
`document-evidence-manifest.json`. Source, generated segment, Localization
Brief, term governance, claim/signoff, and delivery evidence changes can mark
document evidence and downstream decisions stale. Staleness is content-hash
driven; filesystem timestamp is not the source of truth.

The Evaluation Scorecard consumes document evidence conservatively. Open
claim/metric blockers, publicity blockers, unresolved open decisions,
unsupported scenarios, stale document evidence, or missing document signoff can
block or downgrade `review_readiness`, `delivery_readiness`,
`apply_readiness`, and `overall_claim`. Unsupported document evidence forbids
strong claims instead of pretending that a generic adapter reviewed the
document. Because this seed does not perform DOCX layout/render verification
or real-world factual truth verification, `layout_verified`,
`review_complete`, `delivery_ready`, `apply_ready`, and `production_ready`
remain forbidden when current evidence does not support them.

`workbench-document-evidence-queue.json` is a Workbench-facing projection over
the evidence artifacts. It surfaces unsupported scenarios, semantic alignment
risks, English-only bridge review, source-only omissions, claim/metric risks,
publicity risks, leadership review requirements, open decisions, stale
document evidence, and document signoff requirements. The queue is not a second
source of truth. It is regenerated from runtime artifacts and exposed through
`workbench-document-evidence-queue` and
`GET /api/workbench-document-evidence-queue`. UI code should render this queue
instead of inferring document readiness locally.

### Document Evidence Decision Resolution

Document evidence risks are resolved only by explicit artifacts. The seed adds
`document-decision-log.jsonl`, `leadership-review-evidence.jsonl`,
`document-claim-resolution.json`, and `document-signoff-summary.json`.
Decision records can confirm or reject institution names, project names,
metric boundaries, claim wording, publicity risks, alignment modes,
explanatory expansion, source omission, limited-scope delivery, follow-up
requests, and leadership confirmation. Each record keeps reviewer role,
source artifact references, related risk ids, rationale, limitations, scope,
and supersession metadata where available.

Leadership review evidence can accept institutional, project, claim, or
publicity risk within an explicit scope and can support claim acceptance or
document signoff. It does not create E2, E3, or E4 language review evidence.
Accepted risk is still a limitation, not full assurance, and limited-scope
approval does not become global delivery readiness.

`document-claim-resolution.json` summarizes resolved and unresolved
claim/metric risks, accepted and unresolved publicity risks, semantic alignment
risks, rejected wording, accepted limitations, effective scope, forbidden
claims remaining, and signoff requirements. `document-signoff-summary.json`
summarizes whether document-specific delivery can proceed, but it cannot
override the Evaluation Scorecard, Artifact State, QA, repair, provider
policy, handoff, or project signoff gates. If document evidence changes, these
decision artifacts become stale and readiness stays blocked or downgraded
until refreshed.

## Personal Knowledge Pack Builder

Personal Knowledge Pack Builder is the first local-first reuse layer. It exports
scoped, provenance-backed localization knowledge from existing run artifacts
into `.localize-anything/knowledge/packs/<pack-id>/`. The pack contains
`pack.json`, term/glossary CSVs, translation-memory and example JSONL files,
style and claim decision records, revision memory, provenance, a quality
report, and a knowledge review queue.

This is deliberately not RAG and not knowledge-augmented generation. The seed
only builds a pack structure and a deterministic extraction/export pipeline.
Raw generated output, unresolved document risks, stale decisions, rejected
records, superseded records, blocked artifacts, and failed-QA repairs are not
promoted to approved knowledge. They remain candidate or reference-only
knowledge until a reviewer records an explicit decision.

`knowledge-review-queue.json` is the Workbench-ready surface for candidate
knowledge. It includes stable candidate ids, candidate type, source/target
values, proposed status, confidence, source artifact references, provenance,
scope, risk level, recommended decision, blocking reason, and whether human
confirmation is required. `knowledge-review-decisions.jsonl` records explicit
review outcomes such as approve, lock, reject, defer, scope-limit,
reference-only, obsolete, duplicate merge, or follow-up. Only approved, locked,
or scope-specific items can become hard constraints in pack artifacts.

Promotion rules stay tied to the Evidence Spine:

- approved or locked term governance can export to pack term registry and
  glossary;
- forbidden translations need provenance and scope before becoming hard
  negative constraints;
- document and leadership decisions export only within explicit scope;
- accepted repair history exports to revision memory only after deterministic
  QA passes;
- generated segments do not become reviewed translation memory without
  explicit human review or signoff evidence;
- limited-scope decisions remain limited-scope and never become global
  delivery readiness.

Artifact State dynamically tracks generated pack files. If source term
governance, document decisions, review evidence, claim acceptance, signoff, or
scorecard evidence changes, the pack becomes stale and must be regenerated or
reviewed before future loops can rely on it. Pack existence alone never
upgrades the current run's scorecard, delivery readiness, or apply readiness.

## Knowledge Pack Consumption And Working Context

Knowledge Pack Consumption is the deterministic bridge between reviewed pack
artifacts and future generation planning. It produces three state artifacts:

- `knowledge-pack-selection.json` records explicit local pack choices, locale,
  domain, scenario, mode, status, freshness, privacy/sync metadata, provenance,
  and rejected-pack reasons;
- `knowledge-eligibility-report.json` classifies each entry without retrieving
  or generating content;
- `working-context-packet.json` keeps hard constraints, negative constraints,
  TM suggestions, style guidance, examples, claim constraints, revision hints,
  exclusions, and provenance in separate fields.

The packet is deliberately structured rather than flattened into a prompt.
Approved or locked scoped terms may become hard constraints. Provenanced
forbidden translations may become negative constraints. Reviewed TM and style
decisions remain soft context. Reference-only TM/examples remain examples and
never raise terminology or knowledge assurance. Revision memory is a
repair/review hint, never an automatic rewrite instruction. Candidate, raw,
deferred, stale, rejected, superseded, failed, provenance-free, and
scope-mismatched entries are excluded or require review.

`blind_benchmark` is a context firewall: target-language pack terms, TM, and
examples are hidden from generation context. A mode change invalidates the
packet. Locale/domain/scenario compatibility must be exact unless selection
records an explicit allowance. Team-shared metadata is preserved, but the
runtime reads local artifacts only and performs no sync or provider call.

Term Governance consumes eligible pack terms as lower-priority imported scoped
terms. Project-local approved decisions outrank generic pack knowledge;
conflicting locked targets block Generation Strategy instead of being silently
overwritten. Generation Strategy records the knowledge policy and packet
artifacts. Work packets reference the structured packet. Artifact State marks
eligibility/context/strategy stale when pack, brief, term governance, or mode
inputs change. Evaluation Scorecard forbids `knowledge_backed_quality` unless a
future usage artifact plus QA/review evidence can prove that constraints were
actually applied.

This bridge precedes full RAG because deterministic eligibility and policy
boundaries must exist before retrieval can be trusted. It does not implement
semantic search, vector indexes, provider/model generation, repair execution,
or knowledge-augmented quality claims.

## Knowledge Usage Evidence And Constraint Audit

Knowledge Usage Evidence is the audit layer after pack selection and Working
Context Packet creation. It produces:

- `knowledge-usage-report.json`
- `constraint-application-audit.json`
- `knowledge-conflict-report.json`

`knowledge-usage-report.json` records selected packs, eligible entries, applied
hard constraints, applied negative constraints, soft context, reference-only
context, blind-benchmark exclusions, stale/rejected/superseded exclusions,
scope mismatches, conflicts, and unused knowledge. It is a proof of routing,
not a proof of quality.

`constraint-application-audit.json` runs deterministic checks where possible:
approved/locked terms must appear in matching generated target segments, and
forbidden targets must not appear. Style guidance, revision hints, examples,
and claim constraints remain pending review or reference-only unless a
deterministic check can prove them. Missing generated targets leave checks in
`pending_generation`; failed hard or negative checks block full-quality
handoff.

`knowledge-conflict-report.json` mirrors blocking knowledge conflicts such as
locked pack term conflicts, project-local override conflicts, and incompatible
pack constraints. Generation Strategy references the usage, audit, and conflict
artifacts. Artifact State marks them stale when packs, Working Context Packet,
term governance, strategy, or generated segments change.

Evaluation Scorecard may support the narrow `knowledge_constraints_applied`
claim only after deterministic usage and audit evidence exists. It still
forbids `knowledge_backed_quality` and `knowledge_review_complete` in this seed
because applying constraints does not prove semantic quality, review completion,
or provider-backed generation. This layer comes before full RAG so retrieval can
later be audited instead of becoming invisible prompt context.

## Knowledge Audit Enforcement And Workbench Queue

Knowledge Audit Enforcement turns the usage/audit/conflict evidence into a
single gate artifact:

- `knowledge-audit-enforcement-decision.json`
- `workbench-knowledge-review-queue.json`

The enforcement decision checks whether the selected pack, Working Context
Packet, usage report, constraint audit, and conflict report are present, fresh,
and safe to use. It blocks or downgrades full-quality handoff, delivery, apply,
and scorecard claims when usage evidence is missing, Working Context Packet is
stale, hard/negative constraint audit is missing or failed, P1/P2 conflicts are
unresolved, reference-only knowledge leaks into hard constraints,
blind-benchmark target context is exposed, scope-specific knowledge is used
outside scope, or project-local priority is violated.

The decision can be `clear`, `clear_with_warnings`, `review_required`,
`blocked`, `stale`, or `not_applicable`. A clear deterministic audit may support
the narrow `knowledge_constraints_applied` claim, but it still does not prove
`knowledge_backed_quality` or `knowledge_review_complete`. Deterministic audit
is evidence that constraints were checked, not evidence that the translation is
semantically correct.

`workbench-knowledge-review-queue.json` is a projection over enforcement
issues. It exposes missing usage reports, stale working context, missing or
failed audits, negative constraint failures, unresolved conflicts, reference-only
leakage, blind-benchmark firewall risk, project-priority conflicts, and
unsupported knowledge claims. The queue is not a source of truth and does not
resolve issues by display alone.

Generation Strategy consumes the enforcement decision for handoff readiness.
Evaluation Scorecard consumes it for forbidden claims. Claim acceptance and
signoff inherit those forbidden claims, so a user decision cannot silently
accept unsupported knowledge-backed quality. Delivery packages and run summaries
reference the enforcement artifacts when present. This gate comes before full
RAG/model generation because retrieval output must be enforceable before it can
be expanded.

## Knowledge Review Decisions And Human Confirmation

Knowledge Review Decision / Human Confirmation adds explicit artifacts for
resolving knowledge audit blockers without putting decisions in the UI:

- `knowledge-audit-resolution-log.jsonl`
- `knowledge-constraint-review-evidence.jsonl`
- `knowledge-conflict-resolution.json`
- `knowledge-assurance-summary.json`

The resolution log records scoped decisions such as accepting or rejecting
constraint application, resolving conflicts, preferring project terms, limiting
knowledge scope, confirming or rejecting blind-benchmark firewall status,
requesting repair, accepting limited knowledge risk, or keeping a blocker
active. The constraint review evidence records which constraints, negative
constraints, usage entries, conflicts, and generated or staged segments were
actually reviewed.

These artifacts are deliberately conservative. Human confirmation can confirm a
narrow `knowledge_constraints_applied` claim only when deterministic enforcement
is already clear; it cannot replace missing or failed audit evidence. It does not automatically prove
`knowledge_backed_quality`, semantic correctness, global review completion, or
delivery/apply readiness. Reference-only knowledge remains non-binding, stale or
rejected knowledge remains ineligible, and project-local locked terms remain
higher priority unless a scoped decision explicitly records otherwise.

`knowledge-conflict-resolution.json` summarizes resolved and unresolved
knowledge conflicts by conflict id, provenance, and scope.
`knowledge-assurance-summary.json` summarizes supported claims, unsupported
claims, remaining forbidden claims, limitations, and readiness impact.
Evaluation Scorecard consumes this summary but still derives readiness from the
weakest required evidence. Claim acceptance and signoff inherit unsupported
knowledge claims rather than bypassing them. Generation Strategy may treat valid
scoped review as a warning-limited path, while stale review evidence, unresolved
P1/P2 conflicts, failed QA, unsafe provider policy, blocked handoff, and pending
repairs remain blockers.

Workbench knowledge queue entries can display whether a blocker is resolved by
the resolution log or constraint review evidence, but the queue stays a
projection over artifacts. A blocker is not resolved because it was displayed,
acknowledged, or hidden in UI state. This seed still performs no vector search,
RAG, provider/model generation, or provider/model repair.

## Knowledge-Assisted Targeted Repair Planning

Knowledge-assisted repair is planning before execution. The runtime derives
`knowledge-repair-plan.json` from usage, constraint audit, conflict,
enforcement, queue, resolution, assurance, and existing segment-repair
artifacts. Stable items preserve segment/scope, constraint/conflict/queue ids,
knowledge provenance, severity, action, deterministic eligibility, human/model
requirements, readiness impact, and every downstream artifact that must be
refreshed.

`knowledge-repair-request.json` is a handoff into the existing targeted repair
workflow, not a second executor. An automatic-safe request exists only for a
single unambiguous replacement. Semantic rewrites stay human/provider/model
pending; unresolved locked-term conflicts block execution; reference-only
knowledge never becomes an automatic hard repair; blind-benchmark target
context must be removed before context-aware repair.

`knowledge-repair-impact-report.json` keeps scorecard and delivery effects
visible. A candidate is not repaired merely because a plan exists. Only a
current target hash, matching knowledge provenance, and passing QA in
`repair-result.json` can clear it. Repair then invalidates constraint audit,
usage, assurance, scorecard, signoff, delivery decision, and apply readiness.

This layer reuses `segment-regeneration-plan.json`, `repair-request.json`,
`repair-result.json`, and `repair-history.jsonl`; it does not replace or execute
them. Artifact-backed GET endpoints and deterministic CLI commands expose the
three artifacts. There is no provider/model call, semantic retrieval, or full
RAG in this seed. Establishing auditable failure-to-repair handoff before full
RAG prevents retrieved context from bypassing scope, provenance, mode, review,
or readiness controls.

## Knowledge Repair Result Intake And Reconciliation

Result intake closes the evidence loop without adding an executor. A manual,
reviewer, deterministic-local, imported, external-provider, or external-model
result is appended to `knowledge-repair-result-intake.jsonl` with its request,
plan item, scope, actor, hashes, knowledge/constraint/conflict ids, provenance,
fix claims, and limitations. The runtime never applies the submitted text and
never represents external provider/model evidence as a system provider run.

`knowledge-repair-qa-report.json` checks the result against the current repair
request and segment state. Request/base hash, current repaired hash, provenance,
scope, required and forbidden terms, negative constraints,
placeholder/markup/escape signatures, blind-benchmark isolation,
project-local priority, reference/raw knowledge boundaries, conflict resolution,
and required human review are separate QA items. Keeping these checks separate
prevents one passing term check from hiding a stale hash or provenance failure.

`knowledge-repair-reconciliation.json` projects QA back onto every repair-plan
blocker. Intake alone never changes readiness. A blocker clears only when the
request, current target hash, provenance, deterministic QA, active constraints,
conflict resolution, and any required scoped human review all agree. Semantic
or high-risk changes remain review-bound. Failed, partial, stale, or missing
reconciliation keeps scorecard claims, claim acceptance, signoff,
delivery/apply, handoff, and Workbench actions blocked or downgraded.

The reconciliation references rather than replaces generic
`repair-result.json` and `repair-history.jsonl`. Artifact State invalidates the
intake/QA/reconciliation chain when requests, target segments, audit/conflict
evidence, or human review changes. After a clear result, enforcement, assurance,
scorecard, claim acceptance, signoff, delivery decision, and apply readiness
still require recomputation. Passing repair QA does not prove broad
`knowledge_backed_quality`.

## Knowledge Repair Closure And Recompute Orchestration

The repair-closure seed turns reconciliation outcomes into explicit downstream
orchestration evidence. It adds `knowledge-recompute-plan.json`,
`knowledge-recompute-result.json`, `knowledge-repair-closure-decision.json`,
and `knowledge-readiness-impact-report.json`.

The recompute plan identifies derived artifacts that must be refreshed or
invalidated after repair reconciliation: constraint audit, usage/conflict
reports, enforcement, assurance, Workbench knowledge queues, Evaluation
Scorecard, Artifact State, claim acceptance, signoff, delivery decision, run
summary, delivery metadata, and apply readiness where present.

The recompute result runs only deterministic refreshes that already exist in
runtime modules. It never calls providers, applies repair patches, executes
semantic rewrites, mutates generated segments, or renews human-owned
authorization artifacts. Claim acceptance, signoff, delivery package metadata,
and apply authorization are recorded as manual follow-up when their evidence
basis changes.

The closure decision is conservative. A repair can be `closed` only when
reconciliation is clear, deterministic QA passed, blocking conflicts are gone,
and required downstream recomputation completed. It remains
`requires_recompute`, `requires_human_review`, `partially_closed`,
`still_blocked`, or `stale` when evidence is incomplete, stale, failed, scoped,
or human-gated. The readiness impact report carries before/after blocker
counts, forbidden claims, scorecard impact, signoff/claim staleness, remaining
limitations, and next actions.

Generation Strategy, generation handoff, Evaluation Scorecard, Claim
Acceptance, Signoff, delivery decisions, delivery packaging, run summary, and
Artifact State consume these closure artifacts. QA-passed repair evidence is
therefore not allowed to silently become delivery readiness, apply readiness, or
knowledge-backed quality.

## Delivery / Apply Readiness Authorization Matrix

The readiness authorization seed adds a final artifact-backed consolidation
layer after scorecard, repair closure, document evidence, knowledge evidence,
claim acceptance, and signoff. It produces:

- `readiness-authorization-matrix.json`
- `manual-followup-gap-report.json`
- `apply-readiness-report.json`
- `delivery-readiness-report.json`

The matrix answers whether the current run can be delivered, applied, reviewed,
or described as production-ready. It does not override the Evaluation
Scorecard, Artifact State, claim acceptance, signoff, handoff, delivery
decision, or apply plan. It only consolidates their current evidence into
statuses, blockers, warnings, forbidden claims, limitations, effective scope,
authorization requirements, and recommended next actions.

Delivery readiness and apply readiness are intentionally separate. A run may be
safe to hand to a reviewer with warnings while still blocked from writing files
back into the project. Apply readiness requires current evidence for the
affected scope plus explicit apply authorization; delivery readiness alone does
not authorize apply.

`manual-followup-gap-report.json` gathers unresolved human and operator work:
term decisions, blocking questions, human review gaps, claim acceptance,
signoff, document/leadership decisions, knowledge audit and repair follow-up,
artifact refreshes, provider policy blockers, coverage confirmation, and
forbidden claim acknowledgement. The report is a projection over artifacts, not
a new decision writer.

The apply and delivery readiness reports turn the matrix into two focused
answers. Draft-only or review-ready delivery must keep unsupported claims
visible: full quality, production-ready, review-complete, apply-ready,
layout-verified, provider-backed, and knowledge-backed claims remain forbidden
unless current evidence supports them. Production-ready delivery requires
current scorecard, claim acceptance, signoff, repair closure, QA, and evidence
freshness. Readiness reports are included in delivery packages and run
summaries when present, but their existence never upgrades readiness.

## Human Review Evidence And Claim Acceptance

Human Review Evidence Intake records explicit human review in
`human-review-evidence.jsonl`. It is the only seed artifact that can raise
E2-E4 evidence levels. Project-owner signoff can accept risk and authorize
workflow steps, but it does not create bilingual, native-language, or
professional localization review evidence.

The intake is conservative:

- E2 requires a `bilingual_reviewer` record.
- E3 requires a `native_language_reviewer` record.
- E4 requires a `professional_localization_reviewer` record.
- Limited-scope review remains limited-scope evidence and cannot silently
  become global review completion.
- Rejected, stale, superseded, or follow-up review records remain visible and
  do not support review-complete claims.

Claim Acceptance Gate writes `claim-acceptance-decision.json` from the current
scorecard plus human-review evidence. It records which claims are accepted,
accepted only with limitations, rejected, or still forbidden. It cannot override
scorecard blockers such as unsafe provider policy, stale artifacts, pending
repairs, failed QA, partial coverage, or missing human review.

`signoff-record.json` is a separate project-owner authorization record. It may
authorize limited delivery when the scorecard and claim acceptance allow that
risk, but apply authorization remains blocked when `apply_ready` is forbidden
or artifacts are stale. This separation keeps human review evidence, claim
truthfulness, and owner signoff auditable instead of collapsing them into a UI
checkbox.

Artifact state tracks these three artifacts by content hash. If review evidence,
scorecard, delivery decision, or claim acceptance changes afterward, downstream
signoff becomes stale and cannot justify delivery or apply readiness until it is
refreshed. Workbench exposes artifact-backed API paths for the records; a full
visual panel should display these runtime artifacts rather than infer quality
claims in browser state.

## Workbench Review Queue

Workbench Review Queue is a projection layer over existing evidence artifacts.
It writes `workbench-review-queue.json`, `workbench-claim-queue.json`, and
`workbench-signoff-summary.json` so a Workbench UI can show what needs action
without inventing readiness or duplicating runtime policy.

`workbench-review-queue.json` collects actionable items from human review
evidence, claim acceptance, signoff, the evaluation scorecard, blocking
questions, repair artifacts, artifact-state, and delivery decisions. Items use
stable ids and include owner role, severity, status, source artifact
references, affected segments or scope, evidence-level impact, affected
forbidden claims, recommended action, human-confirmation requirement, and
whether stale evidence is involved.

`workbench-claim-queue.json` lists claim decisions such as
`provider_backed_quality`, `full_coverage`, `full_terminology_assurance`,
`review_complete`, `delivery_ready`, `apply_ready`, `production_ready`,
`limited_scope_delivery_ready`, `draft_only`, and `review_ready`. It preserves
scorecard `forbidden_claims`; limited-scope acceptance does not erase global
forbidden claims.

`workbench-signoff-summary.json` exposes current signoff status, accepted and
rejected claims, remaining forbidden claims, delivery/apply authorization,
effective scope, limitations, stale-signoff warnings, and next action.

These artifacts are not a new source of truth. Evaluation Scorecard remains the
source of evidence conclusions, Human Review Evidence and Claim Acceptance
remain the write paths for review/claim decisions, and Delivery/Apply gates
remain responsible for enforcement. Workbench/API endpoints should read these
runtime-generated projections rather than compute readiness in the UI layer.

## Workbench Action Surface

Workbench Action Surface is the seed write path for UI-facing review actions.
It records `workbench-action-log.jsonl` and `workbench-action-result.json`, then
refreshes the scorecard and Workbench queue projections from runtime artifacts.

Supported actions include recording human review evidence, accepting,
rejecting, or downgrading claims, creating or rejecting signoff, requesting
follow-up, acknowledging forbidden claims or limitations, and marking queue
items addressed. These actions delegate to the existing Human Review Evidence,
Claim Acceptance, and Signoff runtime writers. A queue item can be marked
addressed only when regenerating the queue no longer produces that item.

The action surface cannot upgrade evidence levels, remove forbidden claims,
infer E2/E3/E4 from project-owner signoff, or authorize delivery/apply against
scorecard, artifact-state, QA, repair, handoff, or provider-policy blockers.
This keeps business logic in runtime gates while giving Workbench a structured
artifact-backed way to record decisions.

## Workbench Readiness Action Surface

Workbench Readiness Action Surface extends the action model to the readiness
authorization layer. It produces:

- `workbench-readiness-action-queue.json`
- `workbench-readiness-action-result.json`
- `workbench-readiness-action-log.jsonl`

The readiness action queue is derived from `readiness-authorization-matrix.json`,
`manual-followup-gap-report.json`, delivery/apply readiness reports, existing
Workbench queues, term review, human review, claim acceptance, signoff,
document decisions, leadership review, knowledge audit and repair artifacts,
and artifact-state. Each queue item names the gap, owner role, affected scope,
readiness dimension, delivery/apply/production blocking flags, forbidden
claims affected, recommended action, available action types, endpoint hint,
stale-evidence involvement, and limitations.

The POST action path delegates to existing runtime writers where possible:
Human Review Evidence, Claim Acceptance, Signoff, Document Decision,
Leadership Review, Knowledge Audit Resolution, Knowledge Constraint Review,
Knowledge Repair Result Intake, and deterministic recompute orchestration. If
there is no safe writer, the action remains blocked or requires follow-up. The
layer never calls providers, applies repairs, mutates generated segments,
infers semantic quality, directly marks gaps resolved, removes forbidden
claims, or turns limited-scope authorization into global readiness.

`workbench-readiness-action-result.json` and
`workbench-readiness-action-log.jsonl` are audit artifacts. They record what was
requested, which writer was delegated to, which artifacts changed, which
readiness reports were refreshed, what blockers and forbidden claims remain,
and what follow-up is still required. An accepted readiness action does not
mean delivery/apply readiness unless the refreshed matrix and reports support
that readiness.

## Workbench Review Console

Workbench Review Console is the first minimal visual surface over the evidence
spine. It renders run status, Evaluation Scorecard, Evidence Level Report,
Workbench review queue, claim queue, signoff summary, readiness matrix, manual
follow-up gap report, delivery/apply readiness reports, readiness action queue,
forbidden claims, pending repairs, stale artifact warnings, action logs, and
latest action results from artifact-backed runtime reads.

The console is intentionally thin. It can display suggested actions and submit
structured action JSON to `POST /api/workbench-action` or
`POST /api/workbench-readiness-action`, but runtime action writers decide
whether each action is accepted, rejected, blocked, or requires follow-up.
After an action, the console refreshes artifact views. It never marks queue
items resolved locally, hides forbidden claims, converts limited-scope evidence
into global readiness, infers E2/E3/E4 from owner signoff, or authorizes
delivery/apply against runtime blockers.

The seed uses the existing Python Workbench server and adds no frontend
dependency. A full visual Workbench can iterate on layout later, but it should
continue to render these artifact-backed views rather than owning business
logic.

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
## Workflow Orchestration / Run Lifecycle Controller

The workflow controller is a deterministic projection and refresh layer over
the existing evidence spine. It answers what is current, missing, stale,
blocked, ready for a safe builder, or waiting for human/provider evidence. It
does not replace Artifact State, readiness authorization, or the owning
runtime writers.

The lifecycle artifacts are:

- `workflow-run-plan.json`: selected mode, ordered stages, runnable builders,
  skipped/blocked work, and pending human/provider actions;
- `workflow-stage-status.json`: per-stage lifecycle status and exact blockers;
- `workflow-dependency-graph.json`: stage/artifact edges and staleness rules;
- `workflow-execution-result.json`: builders attempted, artifacts changed,
  pending actions, remaining blockers, and forbidden claims;
- `workflow-readiness-summary.json`: a non-upgrading view of delivery, apply,
  review, and production readiness.

Only an explicit whitelist of existing deterministic builders may run. Source
discovery needing project input, provider/model generation, semantic rewrite,
repair application, human review, claim acceptance, signoff, delivery
packaging, and apply planning remain pending or use their owning workflows.
The controller never mutates target project files.

The dependency graph makes readiness depend on Artifact State, Evaluation
Scorecard, claim acceptance, signoff, document evidence, knowledge evidence,
repair closure, provider policy, coverage, and QA. Upstream changes make the
affected workflow projection stale; a workflow run records partial progress
instead of treating orchestration as success.

The Workbench action surface remains the human follow-up path. The workflow
controller may refresh its artifact-backed projections, but cannot resolve a
queue item, remove a forbidden claim, or fabricate review/provider evidence.
The Readiness Authorization Matrix remains authoritative for delivery/apply:
workflow completion alone never authorizes either operation.

This layer comes before provider/model repair or full RAG because lifecycle
ordering, provenance, blocker visibility, and staleness must be deterministic
before external or probabilistic execution can be safely coordinated.

## Incremental Workflow Resume / Selective Recompute

Incremental resume consumes Workflow Orchestration, Artifact State, and the
dependency graph to distinguish dependency-clean outputs from stale, missing,
blocked, human-pending, and provider-pending stages. It emits:

- `workflow-resume-plan.json`: reusable outputs, pending stages, safe resume
  candidates, and the next stage;
- `artifact-invalidation-report.json`: changed dependency/hash evidence and
  the affected downstream artifacts, stages, and readiness claims;
- `selective-recompute-plan.json`: ordered deterministic builders plus reused,
  skipped, blocked, human-required, and provider-required work;
- `selective-recompute-result.json`: honest partial execution, hashes,
  remaining stale artifacts, blockers, and forbidden claims;
- `incremental-workflow-summary.json`: readiness before/after, remaining work,
  limitations, and the next action.

Reuse requires current outputs and dependency-clean Artifact State evidence.
Known upstream changes propagate staleness through the workflow dependency
graph; missing or unknown dependency evidence is handled conservatively.
Selective recompute calls only the existing deterministic workflow builder
whitelist. Provider/model stages, human review, semantic rewrite, repair
application, and target-file mutation remain pending.

The incremental summary consumes the current Readiness Authorization Matrix
when available. Resume or recompute completion cannot authorize delivery or
apply, cannot remove forbidden claims, and cannot infer success from a clean
process exit. Current readiness reports remain authoritative, and stale or
missing readiness evidence stays visible in delivery and run summaries.

## Workflow Checkpoint / Concurrency / Idempotency Hardening

Workflow hardening wraps the deterministic workflow and incremental
recompute layers with local safety evidence. It answers whether a workflow is
currently locked, whether a prior run stopped mid-stage, which artifact writes
were committed, whether a request is a duplicate replay, and what recovery is
required before readiness evidence can be trusted.

The seed emits:

- `workflow-lock-state.json`: local lock status, owner reference, TTL/stale
  detection, locked stages, and recovery recommendation;
- `workflow-checkpoint-log.jsonl`: append-style stage/workflow checkpoints
  for started, completed, skipped, blocked, failed, and recovered states;
- `workflow-transaction-manifest.json`: staged/committed/failed artifact
  writes, hashes before/after, and rollback/recovery status;
- `workflow-idempotency-report.json`: request fingerprint, duplicate status,
  replay policy, result reuse decision, and safety decision;
- `workflow-recovery-plan.json`: stale lock, abandoned workflow, partial
  transaction, failed stage, or stale artifact analysis;
- `workflow-recovery-result.json`: deterministic recovery attempts, artifacts
  recomputed or marked for inspection, and readiness impact.

The lock is local filesystem scope only. A second workflow against the same
state directory receives blocked/in-progress evidence instead of silently
proceeding. Stale lock release requires an explicit option or recovery action.
Transactions are evidence, not database commits; rollback is marked
`not_supported` in this seed, and partial writes require recompute or manual
inspection.

Recovery is deterministic and provider-free. It may release stale locks, mark
partial transactions abandoned, refresh Artifact State, and rebuild readiness
reports. It must not call providers, apply repairs, perform semantic rewrite,
or mutate target files. Provider and human stages remain pending unless their
owning evidence artifacts exist.

Artifact State and the Readiness Authorization Matrix consume hardening
evidence. Active/stale locks, partial transactions, and incomplete recovery
block or stale delivery/apply readiness and appear in manual follow-up gaps.
Workflow recovery does not imply success; readiness improves only when current
scorecard, artifact-state, signoff, claim, QA, delivery/apply, and other
pipeline evidence independently support it.

## Provider / Model Handoff Contract & Execution Evidence

Provider/model handoff evidence separates provider contracts from provider
execution. The runtime can now describe the allowed provider policy, prepare a
handoff request, record execution or external-import evidence, intake external
results, and reconcile that evidence without calling a provider.

The seed emits:

- `provider-execution-policy.json`: execution mode, safety flag, real-provider
  allowance, and claims that remain forbidden;
- `provider-handoff-request.json`: request contract, generation handoff
  references, blockers, warnings, and payload hash;
- `provider-execution-ledger.jsonl`: planned, dry-run, skipped, blocked,
  failed, mock, synthetic, external-imported, or completed execution evidence;
- `provider-result-intake.jsonl`: external or local result evidence with
  provenance, scope, artifact hashes, QA status, and review evidence;
- `provider-evidence-reconciliation.json`: conservative reconciliation against
  policy, request, ledger, provenance, hashes/scope, QA, and review evidence.

Provider-backed means provider-backed. Synthetic, mock, skipped, failed,
dry-run, fallback, or unverified imported output cannot support
`provider_backed_quality`, `provider_execution_complete`,
`provider_repair_complete`, or `model_repair_complete`. External
provider/model result intake is evidence only; it is not quality acceptance and
does not prove that this runtime executed a provider.

Generation handoff, Evaluation Scorecard, Claim Acceptance, Signoff,
Artifact State, Delivery/Apply Readiness, run summaries, and delivery packages
consume provider evidence. Missing, stale, failed, synthetic, or unreconciled
provider evidence keeps provider-backed claims forbidden and blocks or
downgrades downstream readiness when those claims are requested or required.

The Workbench/API surface is deliberately artifact-backed. GET endpoints expose
the five artifacts. POST endpoints are limited to provider policy and provider
result intake; they validate and write structured evidence but never call
providers, run models, apply repairs, rewrite content, or mutate target files.

## Provider Result QA / Review Acceptance Gate

Provider result intake and execution reconciliation establish provenance, not
quality acceptance. The provider result gate adds five conservative artifacts:

- `provider-result-qa-report.json` checks request/reconciliation, provenance,
  current target hashes, scope, placeholders, markup, escapes, forbidden
  translations, required terms, and the blind-benchmark firewall;
- `provider-result-review-evidence.jsonl` records reviewer identity, decision,
  explicit scope, semantic/high-risk coverage, rationale, and limitations;
- `provider-result-acceptance-decision.json` accepts, rejects, or limits result
  use only when QA, reconciliation, review, and scope agree;
- `provider-claim-support-report.json` separates supported, narrowly supported,
  and forbidden provider claims;
- `workbench-provider-review-queue.json` projects unresolved QA, review, and
  acceptance work without resolving it in the UI.

Deterministic QA pass does not prove semantic quality. Semantic or high-risk
output requires scoped human review, and provider-backed quality additionally
requires compatible acceptance and signoff. Synthetic, mock, dry-run, failed,
stale, provenance-missing, or structurally invalid results cannot support
provider-backed claims. Limited acceptance remains limited; it cannot create a
global readiness or quality claim.

Scorecard, Claim Acceptance, Signoff, Readiness Authorization, Artifact State,
delivery packages, and run summaries consume the gate artifacts and preserve
unsupported claims. The API exposes artifact-backed GET routes for all five
artifacts and POST routes only for review evidence and acceptance decisions.
These paths never call providers/models, apply repairs, or mutate target files.

## Locale Capability Report

Locale Capability Report is the first conservative locale-engineering seed. It
does not implement full CLDR, complete product localization, or semantic
translation quality. Its job is to prevent unsupported locale-sensitive claims
from passing silently.

The seed emits:

- `locale-capability-report.json`: target locale profile, directionality,
  seed-level plural complexity, expected plural categories where safely known,
  adapter plural-capability matches, formatting support status, Unicode/bidi
  risk flags, and unsupported locale claims;
- `locale-risk-report.json`: blocking or warning risks such as unknown locale
  capability, RTL without bidi/layout evidence, plural support not proven, and
  locale-aware formatting not proven;
- `locale-readiness-impact.json`: downstream readiness impact, forbidden
  locale claims, claim-acceptance policy, signoff policy, and recommended next
  actions.

Unknown capability downgrades claims. RTL locales without layout/bidi evidence
forbid `rtl_safe` and full-product claims. Complex plural locales require
adapter/runtime plural evidence before `plural_complete` can be supported.
Date/time/number/currency formatting support defaults to unknown in this seed,
so `locale_formatting_complete` remains forbidden unless future evidence says
otherwise.

The report is engineering evidence only. It cannot prove `locale_complete`,
`full_product_localization`, translation quality, or provider/knowledge-backed
quality. Evaluation Scorecard, Claim Acceptance, Signoff, Artifact State,
Generation Handoff, Readiness Authorization, delivery decisions, run summaries,
and delivery packages consume the three locale artifacts and preserve forbidden
claims when evidence is missing, stale, blocked, unknown, or partial.

CLI commands are `locale-capability-report`, `locale-risk-report`,
`locale-readiness-impact`, and `locale-check`. API GET endpoints expose the
same artifacts. They are deterministic and provider-free; there are no locale
write endpoints in this seed beyond generating the report artifacts.
