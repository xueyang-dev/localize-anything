# Localize Anything Protocol 0.1

## Purpose

Define portable artifacts between agents, runtimes, and adapters. The protocol does not prescribe a model provider or implementation language.

The protocol is the machine-readable part of the optimized architecture's
Evidence Spine. Runtime, agents, Workbench, and delivery tooling should derive
readiness from artifacts, not from prompt text or UI state. Architecture
proposal artifacts such as locale capability reports, task-intent coverage
reports, and non-text asset coverage reports are not canonical protocol
artifacts until this spec adds schemas/examples and the runtime validates them.

## Canonical Artifacts

- Project configuration selects operational policy.
- Project sessions record source-selection policy, routing decisions, resumable
  run state, and links to prior run directories for CLI/Web UI continuation.
- Localization briefs record the deterministic draft of task intent, source
  surface, strategy, constraints, and required human confirmations before
  generation.
- Adapter manifests declare formats, capabilities, permissions, dependencies, and entrypoints.
- Segment JSONL carries source units and optional localized targets.
- Delivery manifests record immutable run facts and scoped status.
- Term decisions record approved, locked, rejected, risky, or scoped
  terminology decisions with provenance. `term-decisions.jsonl` stores one
  `term-decision` record per line; `term-registry.csv` and
  `forbidden-translations.csv` provide deterministic runtime inputs for hard
  terminology constraints.
- Termbase preflight artifacts record deterministic candidate terminology before
  generation: `candidate-terms.jsonl`, `termbase-preflight-report.json`,
  `term-review-queue.json`, and `term-review-decisions.jsonl`. The queue is a
  Workbench/API-first review surface; spreadsheet export is optional future
  convenience, not the primary workflow.
- Generation strategy records the deterministic gate decision before generation
  handoff in `generation-strategy.json`. It consumes the localization brief,
  termbase preflight report, operating mode, reference policy, and batch plan to
  mark generation `ready`, `review_required`, or `blocked`.
- Resolution gate artifacts record explicit human decisions for blocked or
  review-required strategy states: `blocking-questions.json`,
  `resolution-options.json`, `user-resolution-decisions.jsonl`, and optional
  `resolution-summary.md`.
- Generation handoff enforcement records the executable handoff policy in
  `generation-handoff-decision.json`. It consumes Generation Strategy,
  Resolution Gate, termbase preflight, provider policy, terminology assurance,
  and coverage state before handoff or provider execution can claim full quality.
- Artifact state records whether linked artifacts are current, stale,
  superseded, blocked, accepted, or review-required in `artifact-state.json`.
  Handoff, delivery, and apply readiness must not treat stale upstream artifacts
  as valid evidence.
- Evaluation scorecard artifacts record what the run has proven in
  `evaluation-scorecard.json` and explain it in `evidence-level-report.md`.
- Human review evidence records explicit qualified review in
  `human-review-evidence.jsonl`. E2/E3/E4 evidence levels require matching
  bilingual, native-language, or professional localization reviewer records and
  must not be inferred from provider output, synthetic fallback, project-owner
  signoff, or UI state.
- Claim acceptance records in `claim-acceptance-decision.json` bind requested
  quality/readiness claims to scorecard evidence. Unsupported or forbidden
  claims remain rejected or blocked.
- Signoff records in `signoff-record.json` capture project-owner delivery/apply
  authorization after claim acceptance. Signoff can accept scoped risk, but it
  cannot override stale artifacts, unsafe provider policy, failed QA, pending
  repairs, or scorecard-forbidden claims.
- Personal Knowledge Pack artifacts live under
  `.localize-anything/knowledge/packs/<pack-id>/`. The pack builder exports
  reviewed, scoped, provenance-backed localization knowledge from existing
  artifacts and keeps raw extracted knowledge in `knowledge-review-queue.json`
  until an explicit `knowledge-review-decisions.jsonl` decision promotes,
  locks, rejects, defers, or scope-limits it.
- Workbench queue artifacts project existing evidence into UI-ready read models:
  `workbench-review-queue.json`, `workbench-claim-queue.json`, and
  `workbench-signoff-summary.json`. They are views over runtime artifacts, not
  a second source of readiness truth.
- Workbench action artifacts record UI-facing review actions in
  `workbench-action-log.jsonl` and the latest action result in
  `workbench-action-result.json`. They delegate to runtime artifact writers and
  cannot bypass scorecard, signoff, artifact-state, repair, QA, handoff, or
  provider-policy gates.
- Delivery decision reports combine QA findings, staged output state, apply
  plans, and unprocessed assets into explicit owner/developer decisions.
- QA results keep runtime, agent, and human evidence distinct.
- LLM review requests and results keep model-based translation critique as
  segment-level issues, separate from deterministic QA and human acceptance.
- Batch plans group segments by content unit and adapter constraints.
- Work packets carry an ephemeral, budgeted context selection.
- Work packets may include `memory.hard_constraints` for approved or locked
  term-registry entries, forbidden translations, structural rules, and future
  claim constraints. Blind benchmark mode hides target-language term registry
  and translation-memory content from generation-facing packets.
- Work packets may include `memory.terminology_review` from the termbase
  preflight report. If unreviewed high-risk terms or conflicts remain, the
  packet must expose incomplete terminology assurance instead of implying full
  term safety.
- Work packets may include `memory.generation_strategy` from the Generation
  Strategy Gate. A blocked strategy must prevent generation handoff; a
  review-required strategy may still produce handoff artifacts, but cannot claim
  full review or terminology assurance.
- Work packets may include `memory.resolution_gate`. If unresolved blocking
  questions remain, draft requests must not claim full-quality or full-assurance
  output.
- Work packets may include `memory.generation_handoff`. This is a compact
  summary of `generation-handoff-decision.json`, including handoff mode, whether
  full-quality handoff is allowed, apply/delivery policy, and forbidden quality
  claims.
- Draft requests turn a work packet into provider-agnostic host-agent
  instructions and a JSONL segment output contract for translation generation.
- Draft prompts render those requests as paste-ready Markdown for manual
  host-agent LLM workflows.
- Generated response imports normalize single-batch or handoff-wide LLM
  response shapes into canonical generated segment JSONL using work-packet
  source fields as the authority.
- Generation handoff manifests coordinate multi-batch draft requests and
  expected generated JSONL paths for host-agent execution.
- Staging manifests record adapter-routed output files created from generated
  segments before packaging or applying anything to the source project.
- Run summaries record orchestration-level artifact paths and next actions for
  developer-facing command runs.
- Agent summaries separate Project, Generation, Review, and Delivery decisions
  so direct-provider, handoff, CLI, and Web UI workflows can be audited through
  the same protocol artifacts.
- Android app test reports prove an isolated source-project copy can be routed,
  localized, applied, and revalidated without mutating the original project.
- Incremental diffs classify new, unchanged, changed, moved, and deleted segments.
- Acceptance records bind scoped sign-off to an immutable manifest hash.
- Apply plans describe dry-run operations without mutating the project.

## Lifecycle

```text
inspect -> preflight -> termbase-preflight -> plan -> generation-strategy -> resolution-gate -> generation-handoff-enforcement
        -> artifact-state -> segment-staleness / reuse-decision
        -> retrieve -> draft-request -> draft-prompt -> generation-handoff -> localize -> import-generated-response(s)
        -> collect-generated
        -> stage-generated -> validate-output -> repair -> evaluation-scorecard
        -> human-review-evidence -> claim-acceptance -> package
        -> delivery-decision -> review-import -> signoff-record -> apply
```

`localize-run` is a reference-runtime convenience command for this lifecycle.
It emits provider-agnostic draft requests for host-agent translation generation,
then, once generated segment JSONL is supplied, writes staged target files,
packages them, and produces a dashboard. It does not make model-provider calls
or overwrite source project files.
`agent-run` is the first agent shell over the same lifecycle. It records the
routing decision, exposes parallel translation batches to direct-provider or
host LLM workflows, imports returned responses when available, and reflects
through deterministic QA, optional LLM critique, review sheets, dashboard,
delivery-decision, and apply-plan artifacts. It uses the same generated segment
JSONL contract for direct provider execution and handoff/import fallback, and
does not overwrite source project files.

Adapters implement the narrower lifecycle documented in `docs/adapters.md`.

## Evidence Spine And Claims

Every lifecycle gate that affects generation, delivery, or apply readiness
should produce or consume durable evidence. The protocol deliberately separates:

- task intent evidence (`localization-brief`);
- terminology evidence (Term Governance and termbase preflight artifacts);
- strategy and blocker evidence (Generation Strategy, Resolution Gate, and
  Generation Handoff Enforcement);
- freshness evidence (`artifact-state`, stale segments, and reuse decisions);
- repair evidence (regeneration plans, repair requests/results/history);
- scorecard evidence (`evaluation-scorecard` and evidence-level report);
- human review evidence, claim acceptance, and signoff;
- delivery and apply evidence.

Processed files, generated target text, or passing structural QA are not enough
to claim task completion. Unsupported claims must remain forbidden in
`evaluation-scorecard.json`, `claim-acceptance-decision.json`, delivery
decision artifacts, and apply planning until the required upstream evidence is
current and accepted.

## Termbase Preflight

`termbase-preflight` scans extracted source segments before generation. The
seed implementation extracts repeated short phrases, resource-key-derived
terms, capitalized acronyms, Android high-risk UI terms, document high-risk
patterns, and existing termbase matches. It classifies terms conservatively and
connects candidates to `term-registry.csv`, `term-decisions.jsonl`, and
`forbidden-translations.csv` when those files are present.

The review queue supports statuses `candidate`, `needs_review`, `approved`,
`locked`, `rejected`, `forbidden`, `deferred`, and `scope_specific`. Recording
a queue decision writes `term-review-decisions.jsonl` and updates term
governance assets when the decision can safely become governance input:
approved/locked terms become registry candidates for hard constraints, and
forbidden targets update forbidden translations.

`termbase-preflight-report.json` exposes unreviewed high-risk terms and simple
conflicts. Generation-facing artifacts must carry the report's terminology
assurance state; incomplete review is not equivalent to full terminology
assurance.

## Generation Strategy Gate

`generation-strategy` writes `generation-strategy.json` after batch planning and
before working context packets. The gate is deterministic and provider-agnostic.
It does not generate translations or call external providers.

The seed gate consumes:

- `localization-brief.json` for unresolved human-confirmation requirements;
- `termbase-preflight-report.json` for terminology assurance, high-risk
  unreviewed terms, and conflicts;
- the batch plan scope, operating mode, and reference policy.

It emits `ready`, `review_required`, or `blocked`. `blocked` prevents generation
handoff when unresolved term conflicts are present. `review_required` keeps the
handoff path available, but the work packet and draft request must expose that
the output is review-bound and cannot claim full assurance.

## Resolution Gate

`blocking-questions` writes Resolution Gate artifacts after generation strategy.
The gate converts blocked or review-required states into explicit owner
decisions with stable question ids, source artifact references, severity,
responsible owner type, affected terms or segments, recommended defaults,
available options, option effects, remaining risk, and whether human
confirmation is required.

Resolution options are conservative. They can approve, reject, or defer terms;
allow partial coverage only with an explicit warning; require a localization
brief; block unsafe provider-backed runs until provider policy is safe; or
continue only in draft/review mode for non-provider blockers.

`resolve-question` appends `user-resolution-decisions.jsonl`. Term decisions can
delegate to the Termbase Preflight decision path so Term Governance remains the
source of approved/locked terminology. Coverage decisions can update generation
strategy state without claiming full source or visible UI coverage. Unresolved
blocking questions prevent full-quality generation handoff.

## Generation Handoff Enforcement

`generation-handoff-status` writes `generation-handoff-decision.json` after the
Resolution Gate and before generation handoff execution. The decision is
machine-readable and artifact-backed; Workbench clients may read it, but UI
logic must not be the place where safety policy is enforced.

The enforcement decision blocks full-quality handoff when strategy is blocked,
`allow_generation` is false, blocking questions remain unresolved, terminology
conflicts remain, required brief confirmation is missing, high-risk terms still
need review, partial coverage is unaccepted, or provider policy is unsafe for
provider-controlled generation. Unsafe provider fallback in real provider mode
is non-overridable: ordinary user resolution decisions cannot permit silent
synthetic fallback as provider-backed output.

If handoff proceeds in a downgraded mode, the decision must record the downgrade
reason, unresolved questions, continuation decisions, forbidden quality claims,
and whether apply or delivery should be blocked, warned, or allowed. Downgraded
modes include `draft_only`, `review_required`, `allowed_with_warnings`, and
`source_only_with_partial_coverage_warning`. Run summaries and delivery packages
must not claim full terminology assurance, full source coverage, provider-backed
quality after provider failure, review-complete status while high-risk questions
remain, or safe apply readiness while generation readiness is blocked or
review-required.

Unresolved blockers must remain visible in protocol artifacts rather than being
hidden inside prompts. Prompts can repeat the enforcement state, but they are not
the source of policy truth.

## Artifact State

`artifact-state` writes `artifact-state.json` for a state directory and,
optionally, a run or delivery directory. The artifact tracks key upstream and
downstream files such as project intake/source inventory, localization brief,
termbase preflight, Term Governance, Resolution Gate, Generation Strategy,
Generation Handoff Enforcement, generated segments, review results, delivery
manifest, and delivery decision artifacts.

Each tracked artifact records path, type, status, content hash, source
dependency hashes where practical, producing stage, produced timestamp when the
filesystem can supply it, supersession placeholders, blocking reason, and
downstream artifacts affected by staleness. Status values are `missing`,
`draft`, `current`, `stale`, `superseded`, `blocked`, `accepted`, `rejected`,
and `requires_human_review`.

Staleness is conservative. Source inventory or segment changes stale generated
segments, review results, generation strategy, handoff decision, and delivery
decisions. Localization brief, term governance/review decisions, resolution
decisions, generation strategy, generation handoff decision, generated segments,
and review results stale the downstream artifacts that used them as evidence.
Stale state persists until the affected artifact itself is regenerated or
reviewed.

Generation handoff enforcement consumes artifact state when present and blocks
full-quality handoff if stale upstream evidence affects the handoff decision.
Delivery decision and apply planning surface artifact-state blockers so stale
evidence cannot justify delivery or source-project writes. Workbench exposes
`GET /api/artifact-state` as an artifact-backed read path; UI panels should show
this artifact rather than reimplementing freshness rules in presentation code.

## Segment-Level Staleness / Reuse Decision

`reuse-decision` writes `stale-segments.jsonl` and `reuse-decision.json` after
source segments and prior generated or reviewed segments are available. The
seed is deterministic. It does not implement Translation Memory, Personal
Knowledge Pack, Document Evidence Pack, or provider calls.

Each stale-segment record tracks a segment id or resource key, source text hash,
source context hash, placeholder/markup signature hash, localization brief
hash, term-governance hash, term-review decision hash, generation-strategy
hash, provider-policy hash when supplied, previous generated target hash, and
previous review or review-policy hash when supplied. The classifier supports
`current`, `stale_source_changed`, `stale_context_changed`,
`stale_term_policy_changed`, `stale_generation_strategy_changed`,
`stale_provider_policy_changed`, `needs_regeneration`, `needs_re_review`,
`reusable`, and `blocked`.

Reuse decisions are conservative:

- source text changes require regeneration;
- placeholder or markup signature changes require regeneration and
  deterministic QA;
- term policy changes require regeneration or targeted repair only for segments
  containing affected terms;
- generation strategy, provider policy, or review policy changes require
  re-review when the existing target may still be reused;
- unrelated artifact changes do not invalidate segment reuse;
- high-risk segments affected by policy changes require review even if the
  target text is reused.

Artifact State Machine consumes the reuse decision summary. Full-quality
generation handoff is blocked when required stale segments remain unresolved and
is downgraded when re-review is required. Delivery/apply readiness is blocked
when stale generated segments affect staged files. Run summaries and delivery
packages surface the stale segment counts and include references to both
segment-level artifacts.

Workbench exposes `GET /api/stale-segments` and `GET /api/reuse-decision` as
artifact-backed read paths. UI should display these artifacts rather than
inferring segment freshness from filenames, mtimes, or presentation state.

This loop comes before Document Evidence Pack because segment reuse boundaries
must be known before document-level evidence can safely say which prior target
text, review result, or policy decision remains current.

## Targeted Repair / Segment Regeneration Plan

`segment-regeneration-plan` consumes `stale-segments.jsonl`,
`reuse-decision.json`, `generation-strategy.json`,
`generation-handoff-decision.json`, review artifacts when present, termbase
preflight artifacts when present, and `artifact-state.json` when present. It
writes:

- `segment-regeneration-plan.json`;
- `repair-request.json`;
- `repair-result.json`;
- `repair-history.jsonl`.

The planner is deterministic and does not call a provider or LLM. It assigns
one action per segment: `reuse`, `regenerate`, `re_review`,
`targeted_repair`, `human_confirm`, or `blocked`.

Conservative action rules:

- unchanged low-risk segments with matching hashes are reused;
- source text changes regenerate the segment;
- placeholder or markup signature changes regenerate the segment and require
  deterministic QA;
- term-policy changes in segments containing affected known terms create
  targeted repair when allowed, otherwise regeneration;
- generation strategy or provider policy changes require regeneration or
  re-review depending on severity;
- review policy changes require re-review;
- high-risk unresolved segments require human confirmation or are blocked.

`repair-request.json` is the work queue for actionable repairs. Each request
has a stable repair id, segment id, source artifact references, repair type,
reason, previous target hash when available, required constraints, risk level,
and human-confirmation requirement. Supported repair types are `term_patch`,
`placeholder_patch`, `markup_patch`, `risk_wording_patch`, `style_patch`,
`coverage_patch`, `review_only`, and `regenerate_segment`.

`repair-result.json` records deterministic outcomes only. When a repair would
require provider or model generation, it is marked
`pending_provider_or_model_repair` and no target text is fabricated.
`repair-history.jsonl` appends repair decisions for auditability.

Generation Handoff Enforcement consumes the regeneration plan. Pending
regeneration, targeted repair, human confirmation, or blocked segments prevent
full-quality handoff and safe apply claims. Re-review-only segments downgrade
handoff readiness. Delivery/apply readiness is blocked when required repairs
remain pending for staged output.

Workbench exposes `GET /api/segment-regeneration-plan`,
`GET /api/repair-request`, and `GET /api/repair-history` as artifact-backed
read paths. UI should render these artifacts rather than infer repair state.

## Patch-Based Repair Execution

`apply-repair-plan` consumes `segment-regeneration-plan.json`,
`repair-request.json`, generated segment artifacts when supplied, term
governance artifacts when present, and the existing generation/handoff/artifact
state context. It updates `repair-result.json` and appends
`repair-history.jsonl`.

This seed is provider-free. It may apply only mechanically verifiable repairs:

- `placeholder_patch` when the source placeholder signature is known and a
  malformed target placeholder can be normalized without semantic rewriting;
- `markup_patch` when one known tag pair is structurally recoverable;
- `escape_patch` for mechanical XML/Android escaping fixes;
- `term_patch` when the source term is approved or locked, the replacement is
  unambiguous, and the target contains an exact rejected/forbidden/old term
  match;
- `review_only` when no target text change is required.

All semantic or provider/model work remains pending: `risk_wording_patch`,
`style_patch`, `coverage_patch`, `regenerate_segment`, missing old target text,
ambiguous term replacements, high-risk repairs without human confirmation, and
anything that would alter placeholder, markup, or resource-key signatures.

Execution statuses are `applied`, `pending_provider`, `pending_human`,
`blocked`, `skipped_not_deterministic`, `failed_qa`, and `not_applicable`.
Applied repairs record old/new target hashes, the deterministic rule used, QA
result, source artifact references, and whether a generated-segment artifact was
updated. Failed QA does not claim repaired readiness.

Generation handoff, delivery decisions, and apply planning continue to consume
artifact-backed repair state. Pending, blocked, skipped, or failed repairs block
or downgrade readiness; applied or not-applicable deterministic repairs may
clear repair readiness after artifact state is recomputed. Delivery packages
include repair result/history references so repair provenance remains visible.

Workbench exposes `GET /api/repair-result` and
`POST /api/apply-repair-plan`. The POST endpoint runs only deterministic repair
rules and does not accept provider configuration or call provider/model code.

## Evaluation Scorecard

`evaluation-scorecard.json` is the unified machine-readable evidence summary
for a run. `evidence-level-report.md` is the human-readable companion report.
The scorecard reads existing artifacts when present, including localization
brief, term governance, termbase preflight, generation strategy, Resolution
Gate artifacts, Generation Handoff Enforcement, artifact state, stale segment
and reuse decisions, segment regeneration and repair artifacts, generated
segments, deterministic QA, review results, delivery decisions, apply status,
provider status, and coverage diagnostics.

The schema `evaluation-scorecard` records these dimensions:
`structural_qa`, `provider_status`, `terminology_assurance`,
`coverage_assurance`, `resolution_status`, `handoff_readiness`,
`artifact_freshness`, `segment_reuse_readiness`, `repair_readiness`,
`review_readiness`, `delivery_readiness`, and `apply_readiness`. It also
records `evidence_level`, `overall_claim`, `forbidden_claims`, and
`recommended_next_actions`.

Evidence levels are ordered from deterministic runtime evidence to explicit
professional review:

- `E0_deterministic_structural_qa`
- `E1_automated_semantic_or_policy_review`
- `E2_bilingual_human_spot_check`
- `E3_native_language_review`
- `E4_professional_localization_review`

The seed computes E0/E1 from existing deterministic and automated policy
artifacts. E2-E4 must remain `not_provided` unless explicit human/native/
professional review artifacts exist. The runtime must not fabricate review
evidence from provider output, synthetic fallback, or UI state.

`overall_claim` is one of `blocked`, `not_ready`, `draft_only`,
`review_required`, `review_ready`, `delivery_ready_with_warnings`,
`delivery_ready`, or `apply_ready`. It is derived from the weakest required
evidence. Missing, stale, blocked, downgraded, or incomplete upstream evidence
must prevent stronger claims.

`forbidden_claims` explicitly lists statements the project must not make for
the current run, including `full_coverage`, `provider_backed_quality`,
`full_terminology_assurance`, `review_complete`, `delivery_ready`,
`apply_ready`, and `production_ready` when unsupported. Partial/source-only/
unknown coverage forbids full coverage. Failed, missing, or synthetic provider
evidence forbids provider-backed quality. Incomplete or stale term review
forbids full terminology assurance. Pending required repairs, failed QA, stale
artifacts, blocked handoff, unresolved blockers, or unsafe provider policy
forbid delivery/apply readiness as applicable.

Run summaries and delivery packages include or reference both scorecard
artifacts. The deterministic CLI command is `evaluation-scorecard`. Workbench
exposes `GET /api/evaluation-scorecard`, which returns the artifact-backed
scorecard only; UI must not hide scoring policy in browser state.

## Document Evidence Pack

Document Evidence Pack adds review evidence for high-context document
localization without becoming a second translation system. The deterministic
CLI command is `document-evidence-pack`. It reads existing artifacts in a state
directory and writes:

- `document-intake-report.json`
- `semantic-alignment.jsonl`
- `claim-metric-report.json`
- `publicity-risk-report.json`
- `leadership-review-brief.md`
- `open-decisions.md`
- `document-evidence-manifest.json`

The initial supported scenario is `institutional_publicity_case`. Unsupported
document scenarios are marked unsupported or pending. `document-intake-report`
records the document type, source genre, target delivery mode, audience,
scenario adapter, locales, risk profile, required confirmations, limitations,
source artifacts, and evidence dependencies.

`semantic-alignment` is a JSONL artifact with one
`localize-anything-semantic-alignment-record-v1` object per segment. Alignment
modes are `direct_rendering`, `split`, `merged`, `localized_rewrite`,
`explanatory_expansion`, `structural_relocation`, `english_only_bridge`,
`source_only_omitted`, and `unknown`. English-only bridge and source-only
omission must be flagged. Explanatory expansion must require traceable source
intent or human confirmation. Missing target text stays pending; target text
must not be fabricated.

`claim-metric-report` checks source/target claim boundaries for numbers, years,
dates, course/school/student/participant counts, person-times, person-days,
awards, official recognitions, employment intention/outcome, trial use versus
official adoption, partnership claims, and project status. It does not prove
real-world truth. When target text is unavailable, checks are pending/not
evaluable.

`publicity-risk-report` records external-facing risks including
official-recognition overstatement, unsupported external-facing claims,
achievement inflation, metric boundary changes, institution/partner/award name
uncertainty, policy slogan literalism, unconfirmed project status, sensitive
wording, promotional tone, and audience mismatch.

`leadership-review-brief.md` is the concise human-readable brief. It summarizes
purpose, target audience, high-risk terms, claim/metric risks, publicity risks,
open decisions, forbidden claims, scorecard status, signoff status, and
recommended review actions. `open-decisions.md` lists unresolved items from
blocking questions, term review, human review, claim acceptance, signoff,
publicity risks, claim/metric risks, stale artifacts, and pending repairs.

`document-evidence-manifest` references every pack artifact plus scorecard,
evidence-level report, human review, claim acceptance, signoff, and delivery
decision evidence when present. Delivery packages may include the pack, but
its existence does not upgrade delivery/apply readiness. Enforcement remains
with the scorecard, handoff, artifact-state, repair, QA, signoff, and delivery
gates.

Workbench exposes artifact-backed read paths:

- `GET /api/document-evidence-manifest`
- `GET /api/document-intake-report`
- `GET /api/semantic-alignment`
- `GET /api/claim-metric-report`
- `GET /api/publicity-risk-report`
- `GET /api/leadership-review-brief`
- `GET /api/open-decisions`

Spreadsheet exports, including CSV, are optional future outputs only. JSON,
JSONL, and Markdown artifacts are the source of truth.

### Document Evidence Enforcement

Document evidence artifacts are tracked by `artifact-state.json` once present.
Source segment/source inventory changes make semantic alignment, claim/metric
reports, publicity reports, leadership briefs, open decisions, the document
evidence manifest, scorecard, and delivery decisions stale. Generated segment,
Localization Brief, term-governance, claim-acceptance, signoff, and delivery
changes similarly require recomputation or review where those hashes are
recorded. Stale document evidence must not be treated as valid proof for
generation, delivery, or apply decisions.

The Evaluation Scorecard consumes document evidence as evidence, not
completion. Open high-risk document decisions, unresolved claim/metric
blockers, unresolved publicity blockers, unsupported scenarios, stale document
evidence, or missing document signoff block or downgrade review, delivery, and
apply readiness. The scorecard must forbid unsupported claims including
`review_complete`, `delivery_ready`, `apply_ready`, `production_ready`, and
`layout_verified` when document evidence is incomplete, stale, unsupported, or
unsigned. This protocol does not claim DOCX layout/render verification or
real-world factual truth verification.

`workbench-document-evidence-queue.json` is an artifact-backed projection with
items for `document_intake_incomplete`, `semantic_alignment_risk`,
`english_only_bridge_review_required`, `source_only_omitted_review_required`,
`claim_metric_review_required`, `publicity_risk_review_required`,
`leadership_review_required`, `open_decision_required`,
`document_evidence_stale`, `document_signoff_required`, and
`unsupported_document_scenario`. Each item records stable id, severity, owner
role, source artifact references, affected segments or scope, related
claim/metric or publicity risk, related open decision, evidence-level impact,
affected forbidden claims, recommended action, human confirmation requirement,
and stale-evidence involvement. Workbench exposes it at
`GET /api/workbench-document-evidence-queue`; write actions remain delegated to
existing runtime action writers.

### Document Evidence Decision Resolution

Document evidence risks are resolved through explicit artifacts, not by being
displayed in a queue. `document-decision-log.jsonl` records auditable decisions
for terms, institution names, partner names, project names, metric boundaries,
claim wording, publicity risk, rewrite requests, semantic alignment,
explanatory expansion, source omission, limited-scope delivery, follow-up, and
leadership confirmation. Supported decision statuses are `accepted`,
`accepted_with_limitations`, `rejected`, `blocked`, `requires_follow_up`,
`superseded`, and `stale`.

`leadership-review-evidence.jsonl` records scoped leadership review of
document artifacts, risks, open decisions, and claims. Leadership review may
support claim acceptance and document signoff within scope, but it must not be
treated as E2/E3/E4 language review evidence. It also cannot override stale
evidence, failed QA, pending required repairs, unsafe provider policy, blocked
handoff, unsupported scenarios, or missing factual/layout evidence.

`document-claim-resolution.json` summarizes resolved and unresolved
claim/metric risks, accepted and unresolved publicity risks, semantic
alignment risk resolution, rejected or blocked claim wording, accepted
limitations, effective scope, forbidden claims remaining, delivery readiness
impact, and signoff requirements. Matching is artifact-backed: a risk is
resolved only when a matching document decision or leadership evidence refers
to the relevant risk id or alignment id.

`document-signoff-summary.json` summarizes document signoff status,
leadership review status, accepted and rejected document claims, unresolved
risks, limitations, effective scope, delivery/apply authorization, remaining
forbidden claims, stale warnings, and next required action. Limited-scope
document signoff can support limited delivery only when the broader scorecard,
artifact-state, signoff, handoff, QA, and repair evidence also allow it.
Limited-scope approval must not create global `delivery_ready`,
`apply_ready`, `production_ready`, `review_complete`, or `layout_verified`
claims.

Workbench/API read paths:

- `GET /api/document-decision-log`
- `GET /api/leadership-review-evidence`
- `GET /api/document-claim-resolution`
- `GET /api/document-signoff-summary`

Workbench/API write paths:

- `POST /api/document-decision-log`
- `POST /api/leadership-review-evidence`

These POST endpoints write structured artifacts only. They do not call
providers, infer language review evidence, or bypass runtime gates.

## Personal Knowledge Pack Builder

Personal Knowledge Pack Builder is a local-first export pipeline. It creates
`.localize-anything/knowledge/packs/<pack-id>/pack.json` and companion pack
artifacts for reusable localization knowledge:

- `term-registry.csv`
- `glossary.csv`
- `translation-memory.jsonl`
- `examples.jsonl`
- `style-profile.md`
- `forbidden-translations.csv`
- `claim-patterns.jsonl`
- `style-decisions.jsonl`
- `alignment-examples.jsonl`
- `revision-memory.jsonl`
- `provenance.jsonl`
- `quality-report.md`
- `knowledge-review-queue.json`
- `knowledge-review-decisions.jsonl`

The builder is conservative. It may export approved or locked term decisions as
hard constraints, reviewed forbidden translations as negative constraints, and
scoped document/leadership decisions as claim, style, or alignment knowledge.
Repair history becomes revision memory only when the repair was applied or
accepted and deterministic QA passed. Generated segments do not become reviewed
translation memory unless explicit human review or signoff evidence supports
that status; otherwise they remain candidate or reference-only entries.

`knowledge-review-queue.json` exposes candidate knowledge with stable ids,
source/target values, proposed status, confidence, provenance, scope, risk,
recommended decision, blocking reason, and whether human confirmation is
required. `knowledge-review-decisions.jsonl` records explicit `approve`,
`lock`, `reject`, `defer`, `scope_limit`, `mark_reference_only`,
`mark_obsolete`, `merge_duplicate`, or `requires_follow_up` decisions. Only
approved, locked, or scope-specific decisions can become hard constraints.

Pack quality is summarized in `quality-report.md`. It lists source artifacts,
approved/locked/reference/rejected counts, skipped or stale inputs, limitations,
and whether the pack is safe for scoped hard constraints. Pack existence never
upgrades the current run's scorecard, delivery readiness, or apply readiness.
Artifact State tracks generated pack artifacts and marks them stale when source
term governance, document decisions, review evidence, claim acceptance, signoff,
or scorecard evidence changes.

Workbench/API paths are artifact-backed:

- `GET /api/knowledge-pack`
- `POST /api/knowledge-pack/init`
- `POST /api/knowledge-pack/export`
- `GET /api/knowledge-review-queue`
- `POST /api/knowledge-review-decision`
- `GET /api/knowledge-quality-report`

The seed does not implement hybrid retrieval or knowledge-augmented generation.
It only creates reviewed, auditable pack artifacts so future generation loops
can consume knowledge without treating raw previous output as truth.

## Knowledge Pack Consumption

Knowledge Pack Consumption reads local Personal Knowledge Pack artifacts and
produces:

- `knowledge-pack-selection.json`
- `knowledge-eligibility-report.json`
- `working-context-packet.json`

Selection records pack ids and paths, selection source, locales, domains,
scenario, operating mode, pack status/freshness, selector, reasons, rejected
packs, privacy/sync metadata, and source artifact references. Invalid metadata,
locale mismatch, unallowed domain/scenario mismatch, stale packs, and
unallowed experimental packs reject selection. `team_shared` metadata remains
visible, but selection is local-first and does not sync.

Eligibility classifications are `hard_constraint`, `soft_context`,
`reference_only`, `negative_constraint`, `review_required`, `not_eligible`,
`stale`, `scope_mismatch`, and `rejected`. Approved/locked scoped terms may be
hard constraints. Provenanced forbidden translations may be negative
constraints. Reviewed TM is soft context. Reference TM/examples never become
hard constraints. Approved scoped style and claim decisions become guidance or
review constraints. Revision memory remains a repair/review hint. Raw,
candidate, deferred, stale, rejected, superseded, failed, provenance-free, and
scope-mismatched entries cannot become constraints.

The Working Context Packet has separate `hard_constraints`,
`negative_constraints`, `tm_suggestions`, `style_guidance`,
`retrieved_examples`, `claim_constraints`, `revision_hints`, `risk_notes`,
`scenario_rules`, `excluded_knowledge`, and `provenance` fields. Consumers must
not flatten these classes into a single prompt string. `blind_benchmark` hides
target-language pack terms, TM, and examples from generation context.

Eligible pack terms enter Term Governance as imported scoped terms with
provenance and lower priority than project-local approved decisions. Locked
target conflicts appear as blocking Generation Strategy evidence. Generation
Strategy records whether knowledge is enabled, allowed classes, and the three
artifact references. A stale, mode-mismatched, or conflicting packet blocks or
downgrades handoff. Pack existence and reference-only context never upgrade run
readiness or authorize `knowledge_backed_quality`; Evaluation Scorecard keeps
that claim forbidden without usage plus QA/review evidence.

Artifact State tracks all three artifacts. Pack changes stale eligibility and
context; brief changes may stale both; term governance changes stale context and
strategy; mode mismatch blocks strategy. Workbench/API paths are artifact-backed:

- `GET|POST /api/knowledge-pack-selection`
- `GET /api/knowledge-eligibility-report`
- `GET /api/working-context-packet`

CLI commands are `knowledge-pack-select`, `knowledge-eligibility-report`, and
`working-context-packet`. Selection POST/CLI performs only deterministic local
validation, classification, and packet construction. This bridge comes before
full RAG so retrieval cannot bypass status, scope, provenance, freshness, mode,
or project-term priority. It performs no semantic/vector retrieval, provider
generation, provider repair, TM server operation, or quality claim.

## Knowledge Usage Evidence

Knowledge Usage Evidence records how selected pack knowledge affected a run. It
adds:

- `knowledge-usage-report.json`
- `constraint-application-audit.json`
- `knowledge-conflict-report.json`

`knowledge-usage-report.json` classifies every eligible or excluded pack entry
as `applied_hard_constraint`, `applied_negative_constraint`,
`used_soft_context`, `shown_reference_only`, `excluded_scope_mismatch`,
`excluded_stale`, `excluded_rejected`, `excluded_superseded`,
`excluded_blind_benchmark`, `excluded_raw_or_candidate`, `conflicted`, or
`not_used`. Pack selection alone is not evidence that knowledge was applied.

`constraint-application-audit.json` records deterministic checks for hard and
negative constraints. Approved/locked term constraints can be checked against
matching generated target segments. Forbidden translations can be checked as
negative constraints. Reference-only entries are recorded as
`reference_only_not_enforced`. Soft style, revision, alignment, and claim
context remain pending review unless another deterministic artifact proves
application.

`knowledge-conflict-report.json` records incompatible pack/project knowledge,
including conflicting locked terms, forbidden-vs-approved target conflicts,
scope misuse, stale-current conflicts, and attempts to promote reference-only
items to hard constraints. Blocking P1/P2 conflicts must block or downgrade
Generation Strategy and Handoff.

Generation Strategy references these artifacts when present. Artifact State
marks them stale when selected packs, Working Context Packet, term governance,
generation strategy, or generated segments change. Evaluation Scorecard keeps
`knowledge_backed_quality` and `knowledge_review_complete` forbidden in this
seed; a successful deterministic audit can only support the narrower
`knowledge_constraints_applied` claim. Workbench/API reads are artifact-backed:

- `GET /api/knowledge-usage-report`
- `GET /api/constraint-application-audit`
- `GET /api/knowledge-conflict-report`

CLI commands are `knowledge-usage-report`, `constraint-application-audit`, and
`knowledge-conflict-report`. The seed performs no semantic retrieval, vector
search, provider/model generation, provider repair, or Translation Memory
server operation.

## Knowledge Audit Enforcement

Knowledge Audit Enforcement makes selected pack usage enforceable downstream.
It adds:

- `knowledge-audit-enforcement-decision.json`
- `workbench-knowledge-review-queue.json`

`knowledge-audit-enforcement-decision.json` summarizes pack selection status,
Working Context freshness, usage report status, constraint audit status,
conflict report status, hard and negative constraint check status,
reference-only leakage, blind-benchmark firewall status, unresolved conflicts,
failed audits, pending reviews, stale evidence, readiness impact, forbidden
claims, and required next actions.

Decision status is one of `clear`, `clear_with_warnings`, `review_required`,
`blocked`, `stale`, or `not_applicable`. Full-quality handoff, delivery, apply,
and strong scorecard claims are blocked or downgraded when selected knowledge is
missing usage evidence, audit evidence is missing/stale/failed, the Working
Context Packet is stale, P1/P2 conflicts remain unresolved, reference-only
knowledge leaks into constraints, target-language knowledge leaks in
`blind_benchmark`, scope mismatches affect constraints, or project-local
priority is violated.

`workbench-knowledge-review-queue.json` is an artifact-backed projection over
the enforcement decision. Supported item types include
`knowledge_usage_missing`, `working_context_stale`,
`constraint_audit_missing`, `hard_constraint_failed`,
`negative_constraint_failed`, `knowledge_conflict_unresolved`,
`reference_only_leakage`, `scope_mismatch`,
`blind_benchmark_firewall_risk`, `project_priority_conflict`,
`knowledge_review_required`, `knowledge_claim_not_supported`, and
`stale_knowledge_evidence`.

Generation Strategy references enforcement for handoff readiness. Evaluation
Scorecard uses it to forbid unsupported `knowledge_backed_quality`,
`knowledge_constraints_applied`, `knowledge_review_complete`, `delivery_ready`,
`apply_ready`, and `production_ready` claims. Claim acceptance and signoff
consume those forbidden claims rather than bypassing them. A successful
deterministic audit can support only the narrow
`knowledge_constraints_applied` claim; it is not semantic review and does not
prove full knowledge-backed quality.

Workbench/API reads are artifact-backed:

- `GET /api/knowledge-audit-enforcement-decision`
- `GET /api/workbench-knowledge-review-queue`

CLI commands are `knowledge-audit-enforcement-decision` and
`workbench-knowledge-review-queue`. The seed performs no semantic retrieval,
vector search, provider/model generation, provider repair, or TM server
operation.

## Knowledge Review Decision / Human Confirmation

Knowledge audit blockers are resolved only through explicit artifacts:

- `knowledge-audit-resolution-log.jsonl`
- `knowledge-constraint-review-evidence.jsonl`
- `knowledge-conflict-resolution.json`
- `knowledge-assurance-summary.json`

`knowledge-audit-resolution-log.jsonl` records one decision per line. Supported
decision types include accepting or rejecting constraint application, resolving
knowledge conflicts, preferring project or pack terms within scope, scope
limiting knowledge, accepting or rejecting reference-only use, confirming or
rejecting blind-benchmark firewall status, requesting repair, accepting limited
knowledge risk, keeping a blocker active, and requesting follow-up. Supported
statuses are `accepted`, `accepted_with_limitations`, `rejected`, `blocked`,
`requires_follow_up`, `superseded`, and `stale`.

`knowledge-constraint-review-evidence.jsonl` records scoped human review of
constraints, negative constraints, usage entries, conflicts, and generated or
staged segments. It may confirm the narrow
`knowledge_constraints_applied` claim only when deterministic enforcement is
already clear; it cannot replace missing or failed audit evidence. It does not
automatically support `knowledge_backed_quality`,
`knowledge_review_complete`, semantic quality, or delivery/apply readiness.

`knowledge-conflict-resolution.json` summarizes resolved and unresolved
conflicts by id, provenance, scope, priority decision, rejected knowledge items,
limitations, and remaining blockers. Project-local locked terms remain higher
priority than generic pack knowledge unless an explicit scoped decision records
otherwise. Reference-only knowledge cannot become a hard constraint through
conflict resolution.

`knowledge-assurance-summary.json` summarizes pack/context/usage/audit/
enforcement status, human review status, conflict resolution status, supported
claims, unsupported claims, forbidden claims remaining, limitations, and
readiness impact. Evaluation Scorecard, claim acceptance, signoff, Generation
Strategy, delivery decisions, run summary, and delivery packages consume or
reference this artifact conservatively. Limited-scope assurance remains limited
scope and must not become global readiness.

Workbench/API access is artifact-backed:

- `GET /api/knowledge-audit-resolution-log`
- `POST /api/knowledge-audit-resolution-log`
- `GET /api/knowledge-constraint-review-evidence`
- `POST /api/knowledge-constraint-review-evidence`
- `GET /api/knowledge-conflict-resolution`
- `GET /api/knowledge-assurance-summary`

POST endpoints validate payload shape and write structured artifacts only. They
do not call providers, perform semantic retrieval, promote knowledge without
provenance, or infer broad quality claims.

CLI commands are `record-knowledge-audit-resolution`,
`knowledge-audit-resolution-log`, `record-knowledge-constraint-review`,
`knowledge-constraint-review-evidence`, `knowledge-conflict-resolution`, and
`knowledge-assurance-summary`. This seed still performs no full RAG, vector
search, provider/model generation, provider/model repair, or TM server
operation.

## Knowledge-Assisted Targeted Repair Planning

Knowledge repair is a planning layer between audit evidence and the existing
segment repair workflow. It adds:

- `knowledge-repair-plan.json`
- `knowledge-repair-request.json`
- `knowledge-repair-impact-report.json`

The plan deterministically maps failed hard terms, forbidden translations,
negative constraints, unresolved conflicts, project-priority violations, scope
mismatches, reference-only leakage, blind-benchmark firewall violations,
stale/raw knowledge use, and review follow-up into stable repair items. Each
item retains segment/scope, knowledge, constraint, conflict, queue, provenance,
readiness, and downstream refresh references.

Only an unambiguous scoped replacement may produce a deterministic `term_patch`
or `forbidden_translation_patch` request. Semantic changes remain human,
provider, or model pending. Reference-only leakage cannot create an automatic
hard repair, blind-benchmark firewall violations block context repair, and
unresolved locked-term conflicts block execution until a scoped provenance-
backed conflict decision exists.

These artifacts enrich rather than replace `segment-regeneration-plan.json`,
`repair-request.json`, `repair-result.json`, and `repair-history.jsonl`.
Planning never invokes repair execution. A repair item is cleared only by a
matching current target hash, linked knowledge provenance, and passing QA
evidence; stale repair results do not clear current blockers. Completed repairs
require regeneration of constraint audit, usage evidence, scorecard, signoff,
delivery decision, and apply readiness as applicable.

Generation Strategy and generation handoff reference pending repair plans.
Evaluation Scorecard forbids `knowledge_constraints_applied`,
`knowledge_review_complete`, `review_complete`, `delivery_ready`, `apply_ready`,
and `production_ready` while required repairs remain. Artifact State makes the
three repair artifacts stale when audit, conflict, assurance, generated segment,
or repair-result inputs change.

Workbench/API reads are artifact-backed:

- `GET /api/knowledge-repair-plan`
- `GET /api/knowledge-repair-request`
- `GET /api/knowledge-repair-impact-report`

CLI commands are `knowledge-repair-plan`, `knowledge-repair-request`, and
`knowledge-repair-impact-report`. No endpoint or command performs provider/model
generation or repair.

## Knowledge Repair Result Intake And QA Reconciliation

Repair result intake is evidence intake, not repair execution or acceptance.
The seed adds:

- `knowledge-repair-result-intake.jsonl`
- `knowledge-repair-qa-report.json`
- `knowledge-repair-reconciliation.json`

Each intake record links a known knowledge repair request and plan item to its
segment scope, actor, source, repair mode, request/base hash, repaired hash,
knowledge/constraint/conflict ids, provenance, claimed fix types, limitations,
and status. Manual, deterministic-local, reviewer, imported, external-provider,
and external-model results may be recorded, but external sources remain
external evidence and never imply that this runtime executed a provider/model.
The intake endpoint writes evidence only; it does not apply target text.

Deterministic QA checks request and scope matching, request/base and current
target hashes, provenance, required terms, forbidden and negative constraints,
placeholder/markup/escape signatures, blind-benchmark firewall state,
project-local priority, reference/raw/candidate promotion, conflict resolution,
and scoped qualified human review for semantic/high-risk changes. A repaired
hash must already match the current segment artifact before the result can
clear a blocker.

Reconciliation maps every repair-plan blocker to matching result ids and QA
status. It records cleared and remaining constraints/conflicts, stale evidence,
follow-up, readiness impact, and remaining forbidden claims. Missing, stale,
hash-mismatched, provenance-mismatched, failed-QA, unresolved-conflict, or
human-review-required evidence keeps the blocker active. Generic
`repair-result.json` and `repair-history.jsonl` remain referenced evidence; the
knowledge workflow does not replace them.

Generation Strategy, handoff, Evaluation Scorecard, Claim Acceptance, Signoff,
delivery decisions, Workbench queues, run summaries, and Artifact State consume
or track reconciliation conservatively. Intake alone never unblocks them.
Cleared deterministic reconciliation can support only the narrow
`knowledge_constraints_applied` path after audit/readiness recomputation;
`knowledge_backed_quality` remains unsupported by repair QA alone.

Workbench/API endpoints are artifact-backed:

- `GET /api/knowledge-repair-result-intake`
- `POST /api/knowledge-repair-result-intake`
- `GET /api/knowledge-repair-qa-report`
- `GET /api/knowledge-repair-reconciliation`

CLI commands are `record-knowledge-repair-result`,
`knowledge-repair-result-intake`, `knowledge-repair-qa-report`, and
`knowledge-repair-reconciliation`. No command or endpoint performs semantic,
provider, or model repair.

## Knowledge Repair Closure And Recompute Orchestration

Knowledge repair closure is the deterministic orchestration layer after repair
result QA and reconciliation. It records that a QA-passed repair result is not
the same as accepted readiness. Downstream evidence must be refreshed, or kept
explicitly stale/limited.

The seed adds:

- `knowledge-repair-closure-decision.json`
- `knowledge-recompute-plan.json`
- `knowledge-recompute-result.json`
- `knowledge-readiness-impact-report.json`

`knowledge-recompute-plan.json` lists downstream artifacts affected by repair
reconciliation, including constraint audit, usage/conflict reports,
enforcement, assurance, Workbench queues, scorecard, artifact-state, claim
acceptance, signoff, delivery decision, run summary, and delivery metadata.
Each item records dependencies, order, deterministic/manual status, and the
blocking effect if it is not recomputed.

`knowledge-recompute-result.json` records deterministic refresh attempts. It may
refresh existing derived artifacts, but it never calls providers, applies repair
patches, executes semantic rewrites, or renews human-owned authorization
artifacts. Claim acceptance, signoff, delivery package metadata, and apply
authorization remain explicit follow-up.

`knowledge-repair-closure-decision.json` may be `closed`,
`closed_with_warnings`, `partially_closed`, `still_blocked`,
`requires_recompute`, `requires_human_review`, `stale`, or `not_applicable`.
`closed` requires clear reconciliation, passing QA, no unresolved blocking
conflicts, and completed required deterministic recomputation. Stale
reconciliation, failed QA, semantic/high-risk repair without review, partial
recompute, or missing recompute keeps strong claims blocked or downgraded.

`knowledge-readiness-impact-report.json` summarizes before/after blockers,
forbidden claims, scorecard readiness, signoff/claim staleness, remaining
review and repair requirements, limitations, and recommended next actions.

Workbench/API endpoints are artifact-backed:

- `GET /api/knowledge-repair-closure-decision`
- `GET /api/knowledge-recompute-plan`
- `GET /api/knowledge-recompute-result`
- `GET /api/knowledge-readiness-impact-report`

CLI commands are `knowledge-repair-closure-decision`,
`knowledge-recompute-plan`, `knowledge-recompute-result`,
`knowledge-readiness-impact-report`, and `knowledge-repair-recompute`.
`knowledge-repair-recompute` is provider-free and repair-application-free; it
only orchestrates deterministic recomputation of existing derived artifacts.

## Human Review Evidence, Claim Acceptance, And Signoff

`human-review-evidence.jsonl` stores one `human-review-evidence` record per
line. Review roles are explicit: `bilingual_reviewer` can support E2,
`native_language_reviewer` can support E3, and
`professional_localization_reviewer` can support E4. `project_owner` may record
ownership context but does not raise E2-E4. Review scope is part of the record;
limited-scope evidence remains limited-scope and cannot silently support global
review-complete claims.

`claim-acceptance-decision.json` consumes the current scorecard and human review
evidence. Each requested claim is accepted, accepted with limitations, rejected,
or blocked. Claims in scorecard `forbidden_claims` cannot be accepted by an
ordinary decision. This gate prevents partial/source-only coverage, synthetic or
failed provider output, stale artifacts, pending repairs, failed QA, blocked
handoff, unsafe provider policy, or incomplete human review from becoming
stronger claims in delivery or apply summaries.

`signoff-record.json` records project-owner authorization after claim
acceptance. Delivery can be authorized only when scorecard and claim acceptance
support the requested scope. Apply can be authorized only when the scorecard
supports `apply_ready` and no signoff, claim, or artifact-state blocker remains.
Stale review evidence or stale signoff is tracked by `artifact-state.json` and
blocks or downgrades downstream readiness.

CLI commands:

- `record-human-review`
- `human-review-evidence`
- `claim-acceptance`
- `signoff-record`

Workbench API paths are artifact-backed:

- `GET /api/human-review-evidence`
- `POST /api/human-review-evidence`
- `GET /api/claim-acceptance-decision`
- `POST /api/claim-acceptance-decision`
- `GET /api/signoff-record`
- `POST /api/signoff-record`

These endpoints do not call providers and do not hide scoring logic in the UI.

## Workbench Review Queue

`workbench-review-queue` writes `workbench-review-queue.json` from current
human review, claim acceptance, signoff, scorecard, blocking-question, repair,
artifact-state, and delivery-decision evidence. Queue items are actionable
runtime projections with stable ids, item type, severity, status, owner role,
source artifact references, affected segments or scope, evidence-level impact,
affected forbidden claims, recommended action, human-confirmation requirement,
and stale-evidence marker.

Supported item types are `human_review_required`, `native_review_required`,
`professional_review_required`, `claim_acceptance_required`, `signoff_required`,
`stale_review_evidence`, `pending_repair`, `blocked_handoff`,
`forbidden_claim_remaining`, `delivery_authorization_required`, and
`apply_authorization_required`.

`workbench-claim-queue` writes `workbench-claim-queue.json`, one item per
quality/readiness claim. Each item records the current claim status, supporting
and blocking evidence, related forbidden claim, whether it can be accepted,
whether only limited-scope acceptance is possible, recommended next action, and
risk if accepted.

`workbench-signoff-summary` writes `workbench-signoff-summary.json`, a compact
authorization view over scorecard, claim acceptance, signoff, and artifact-state
evidence.

Workbench APIs expose these artifacts through:

- `GET /api/workbench-review-queue`
- `GET /api/workbench-claim-queue`
- `GET /api/workbench-signoff-summary`

These queues must not infer E2/E3/E4 from project-owner signoff, hide forbidden
claims after limited-scope acceptance, turn limited-scope review into global
readiness, or mark delivery/apply ready when scorecard, signoff, artifact-state,
repair, QA, or handoff evidence is blocked. UI layers should render these
artifacts and delegate writes to existing human-review, claim-acceptance, and
signoff artifact writers.

## Workbench Action Surface

`workbench-action` executes one structured Workbench action against a state
directory and writes `workbench-action-result.json`. It appends every accepted,
rejected, blocked, or failed action to `workbench-action-log.jsonl`.
`workbench-action-log` reads the action log deterministically.

Supported action types are `record_human_review_evidence`, `accept_claim`,
`reject_claim`, `downgrade_claim`, `create_signoff`, `reject_signoff`,
`request_follow_up`, `acknowledge_forbidden_claim`,
`acknowledge_limitation`, and `mark_queue_item_addressed`.

`record_human_review_evidence` must use the Human Review Evidence writer.
Claim actions must use Claim Acceptance. Signoff actions must use Signoff
Record. Follow-up, acknowledgement, and queue-addressed actions may add action
log records, but they must not mutate queue artifacts directly or invent
readiness.

Workbench APIs expose these artifacts through:

- `POST /api/workbench-action`
- `GET /api/workbench-action-log`
- `GET /api/workbench-action-result`

The POST endpoint only delegates to the runtime action surface and must not
call providers. It cannot remove scorecard `forbidden_claims`, infer E2/E3/E4
from project-owner signoff, turn limited-scope acceptance into global
readiness, or authorize delivery/apply when runtime gates remain blocked.

## Workbench Review Console

`workbench-console` renders a deterministic HTML review console for a state
directory. The Workbench server exposes the same surface at
`GET /workbench-review-console?state_dir=...` and a JSON projection at
`GET /api/workbench-console`.

The console reads current evidence from existing artifact-backed endpoints and
artifacts: Evaluation Scorecard, Evidence Level Report, Workbench review queue,
claim queue, signoff summary, human review evidence, claim acceptance, signoff,
artifact-state, repair artifacts, generation handoff status, action log, and
latest action result. It does not add a protocol schema because it is a view,
not durable state.

Writes from the console must go through `POST /api/workbench-action`. The UI
may display suggested actions and submit action requests, but it must display
the runtime result exactly and refresh artifact views after submission. It must
not locally resolve queue items, hide forbidden claims, infer readiness, infer
E2/E3/E4 from project-owner signoff, or allow limited-scope acceptance to appear
as global readiness. Forbidden claims and stale evidence remain visible until
the underlying runtime artifacts change.

## Localization Modes

`operating_mode` and `reference_policy` are first-class protocol fields on
project config, batch plans, work packets, draft requests, delivery manifests,
project sessions, and agent summaries.

Supported `operating_mode` values:

- `blind_benchmark`: generate without target-locale reference text.
- `greenfield_localization`: create a new locale from source material.
- `existing_locale_maintenance`: update an existing locale while preserving
  reviewed unchanged translations.
- `rewrite_or_harmonization`: intentionally revise or harmonize existing
  translations.

Supported `reference_policy` values:

- `blind`: no glossary target terms or translation memory target text may be
  exposed to generation packets.
- `style_only`: approved terminology and style guidance may be exposed, but
  existing target segment translations are excluded.
- `tm_assisted`: approved translation memory may be exposed as generation
  context.
- `preserve_existing`: reviewed unchanged translations are preserved outside
  generation, and only unresolved segments become generation candidates.

Default mode is `greenfield_localization` with `style_only`. Blind benchmarks
must use `blind`; existing-locale maintenance cannot use `blind`.

## Delivery Status

- `draft_package`
- `review_ready`
- `blocked`
- `applied_draft`
- `user_accepted`

Only an explicit user action can produce `user_accepted`.

## Compatibility

All protocol documents carry `protocol_version`. A runtime must reject unsupported major versions and may accept additive minor-version fields when its schema permits them.
