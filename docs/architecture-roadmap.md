# Architecture Roadmap

This roadmap separates implemented architecture seeds from stable release
capabilities. It is not a release promise. Current classifications and public
claim boundaries live in [Architecture](architecture.md).

## Promotion Rule

```text
proposal -> seed -> reviewed PR -> tests -> release audit -> real-project and
benchmark evidence -> documentation/public-claim audit -> stable release claim
```

Merging a seed proves that its contracts and conservative runtime behavior
exist. It does not prove production translation quality, broad platform or
locale coverage, or public release readiness.

## Architecture Seed Track

The following areas are implemented as artifact-backed seeds through PR #57:

- Evidence Spine foundations, including brief, term governance, preflight,
  generation strategy, resolution, handoff, Artifact State, repair, evaluation,
  human review, claim acceptance, and signoff;
- Workbench review/action/console projections;
- Document Evidence enforcement, decisions, leadership review, claim
  resolution, and signoff summary;
- Personal Knowledge Pack building, knowledge consumption, Working Context
  Packet, usage/constraint/conflict audit, enforcement, resolution, assurance,
  repair planning, result QA/reconciliation, closure, and recompute;
- Delivery/Apply Readiness Authorization Matrix and Workbench readiness actions;
- workflow orchestration, incremental resume/selective recompute, checkpoint,
  concurrency, transaction, recovery, and idempotency hardening;
- provider/model handoff contracts and evidence reconciliation;
- provider result deterministic QA, scoped review evidence, acceptance, claim
  support, and Workbench review queue.

These seeds remain subject to release audit, real-project regression evidence,
benchmark evidence, documentation audit, and public claim-boundary review.

## Optimized Target Agent Architecture

The target architecture from the optimized agent proposal remains the design
direction, not a stable capability claim:

```text
CLI / Workbench / API
        |
Main Orchestrator -- artifact state, intent, next action
        |
        +-- Project Subagent -------- source truth, mode, intent coverage
        +-- Knowledge Curator ------- terms, TM, examples, scoped user knowledge
        +-- Generation Subagent ----- provider/model request and result evidence
        +-- Review Subagent --------- deterministic QA, risk and semantic review
        +-- Delivery Subagent ------- staging, bundles, apply plan and decision
        +-- Evolution Subagent ------ failure mining and reviewed patch proposals
        |
Deterministic Runtime Kernel
        |
Format Adapters + Platform Overlays + Scenario Adapters
```

Current workflow orchestration seeds coordinate deterministic artifact builders;
they are not yet this full subagent runtime. Subagents may propose or coordinate,
but runtime validation, durable artifacts, and scoped human authorization remain
the trust boundary. The Evolution Subagent stays P2 and must never merge, tag,
release, or change safety policy autonomously.

## Stable Release Track

The stable track contains only released, documented behavior supported by the
corresponding release evidence. The current public baseline is v0.4.1:

- protocol and runtime contracts;
- deterministic structural validation and staged delivery artifacts;
- explicit apply planning/confirmation rather than automatic source mutation;
- released Workbench and adapter behavior within documented format boundaries;
- Word OpenXML and Android source-resource behavior only within their published
  support boundaries.

Architecture seeds should be promoted in small audited groups. Promotion must
state the exact supported scenario, locale, format, evidence level, limitations,
and forbidden claims. A seed must not be promoted because it exists on `main`.

## Near-Term Route

1. Provider Result QA / Review Acceptance Gate — implemented seed in PR #57;
   retain as seed until release evidence supports promotion.
2. Architecture & Roadmap Progress Sync — align architecture, roadmap, README
   wording, and public non-claims with the actual repository.
3. Locale Capability Report Seed — expose locale-specific implemented checks,
   missing checks, coverage, and forbidden claims.
4. Translation Provenance View Seed — show which terms, knowledge, provider
   evidence, repair, and review decisions influenced each important segment.
5. Benchmark Lab Minimal Seed — provide a small reproducible harness for
   fixture and selected real-project evidence without claiming broad quality.
6. Release Audit / Public Claims Boundary — audit seed promotion candidates,
   docs, examples, regression evidence, and public wording.
7. Provider-safe mock execution harness or explicitly authorized real-provider
   execution only after the evidence and release boundaries above are clear.

Provider Result Staging Admission is intentionally deferred to P1. Acceptance
artifacts first need a documented release boundary and provenance view so a
staging gate cannot accidentally turn narrow review evidence into broad
readiness or mutate target projects without an auditable chain.

## Priorities

### P0 — Evidence Visibility And Release Boundary

- Architecture & Roadmap Progress Sync
- Locale Capability Report
- Translation Provenance View
- Benchmark Lab Minimal Seed
- Release Audit / Public Claims Boundary

### P1 — Controlled Execution And Product Usability

- Provider-safe mock execution harness
- Provider result staging admission
- Real provider adapter hardening
- Workbench UX simplification
- Android/iOS real-project benchmark expansion

P1 execution work must remain provider-safe by default, preserve provenance,
stage output outside target projects, and require explicit apply confirmation.

### P2 — Broader Platform And Ecosystem Depth

- Deep locale engineering: plural/gender rules, RTL/bidi, formatting, Unicode,
  fallback chains, and locale-specific QA
- Non-text asset pipeline
- Visual/layout QA
- Team knowledge governance
- Community adapter registry
- Evolution subagent

P2 items are non-claims until separately implemented, tested, audited, and
released.

## Seed Status By PR Range

| PR range | Area | Status |
| --- | --- | --- |
| #25–#36 | Evidence Spine foundations | Implemented seeds; release status varies by underlying capability. |
| #37–#39 | Workbench review/action/console | Implemented seeds. |
| #40–#42 | Document Evidence | Implemented seeds. |
| #43–#47 | Personal Knowledge, Knowledge Audit, Knowledge Assurance | Implemented seeds. |
| #48–#50 | Knowledge Repair, Closure, Recompute | Implemented seeds. |
| #51–#52 | Readiness Matrix, Workbench Readiness Actions | Implemented seeds. |
| #53–#55 | Workflow Orchestration, Incremental Resume, Hardening | Implemented seeds. |
| #56–#57 | Provider Evidence, Provider Result QA/Review Acceptance | Implemented seeds; provider-backed quality remains evidence-gated. |

## Required Evidence Before Stable Promotion

Every promoted capability needs:

- a release audit tied to an exact commit;
- protocol/contract and regression validation;
- representative fixture evidence and, where applicable, real-project evidence;
- benchmark results that state scope and limitations;
- stale/missing/conflicting evidence behavior that fails closed;
- documentation and README claim review;
- explicit non-claims for unsupported formats, locales, surfaces, quality
  levels, and destructive operations.

## Persistent Non-Claims

The roadmap does not promise complete Android or full-product localization,
zero residual English, locale-complete behavior, DOCX render fidelity,
real-world factual truth verification, production provider/model quality,
knowledge-backed quality without scoped review/signoff, or automatic destructive
apply. Roadmap position and merged code do not override those boundaries.
