# Localize Anything Protocol 0.1

## Purpose

Define portable artifacts between agents, runtimes, and adapters. The protocol does not prescribe a model provider or implementation language.

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
        -> stage-generated -> validate-output -> package
        -> delivery-decision -> review-import -> sign-off -> apply
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
