# Architecture Roadmap

This roadmap describes future direction for Localize Anything. It is not a
release claim. A roadmap item becomes a current architecture claim only after
the protocol has schemas/examples, the runtime validates or enforces the
behavior, tests cover it, and release evidence supports it.

For current architecture, implemented seeds, experimental areas, and non-claims,
see [Architecture](architecture.md).

## Roadmap Principles

Localize Anything should evolve as a localization engineering harness:

```text
Model     -> semantic generation and judgment
Runtime   -> deterministic verification, state, and delivery boundaries
Artifacts -> evidence, traceability, and reproducibility
Human     -> high-risk decisions and final authorization
```

The roadmap should not weaken the Evidence Spine. New UI, provider/model repair,
knowledge packs, collaboration workflows, or community adapters must read and
write artifact-backed state rather than hiding policy in prompts or browser
state.

## Promotion Path

Every future capability follows the same promotion path:

```text
proposal -> seed -> reviewed PR -> tests -> release audit -> benchmark or
real-project evidence -> stable claim
```

Until that path is complete, the capability remains a seed, experimental item,
or non-claim in `docs/architecture.md`.

## Near-Term Stabilization

The current seeds should be promoted into stable Evidence Spine capabilities
before larger platform expansion:

- Term Governance
- Localization Brief
- Termbase Preflight
- Generation Strategy Gate
- Resolution Gate
- Generation Handoff Enforcement
- Artifact State Machine
- Segment-Level Staleness / Reuse Decision
- Targeted Repair / Segment Regeneration Plan
- Patch-Based Repair Execution
- Evaluation Scorecard
- Human Review Evidence / Claim Acceptance / Signoff

Exit criteria:

- every gate writes validated artifacts;
- stale, missing, blocked, or downgraded evidence prevents misleading claims;
- delivery and apply readiness are derived from the weakest required evidence;
- real-project runs can show the evidence chain from intake to delivery/apply
  decision.

## Document Evidence Pack

Goal: turn institutional document localization into a review-ready evidence
bundle, not just a translated `.docx`.

Planned artifacts may include:

- document intake and risk profile;
- semantic segmentation by information function;
- bilingual alignment export;
- claim and metric report;
- publicity risk report;
- leadership review brief;
- revision log and open-decision report;
- final delivery bundle references.

This comes after the current evidence gates because document-level claims need
term review, coverage, scorecard, human review evidence, and signoff to be
trustworthy.

## Personal Knowledge Pack

Goal: let users bring reviewed translation memory, glossaries, style guides,
examples, alignment records, and revision decisions into repeatable workflows.

The pack should distinguish:

- raw imports;
- reference material;
- verified assets;
- approved decisions;
- locked constraints;
- rejected or obsolete entries;
- scope-specific entries.

Knowledge packs should feed Term Governance, working context packets, review
rules, and future retrieval. They must not become unreviewed hard constraints.

## Knowledge-Augmented Generation

Goal: use cleaned and classified knowledge assets rather than plain RAG.

Future working context packets should prioritize:

- approved locked terms;
- official source terms;
- exact reviewed translation memory;
- resource-key or segment-function matches;
- fuzzy reviewed translation memory within compatible scope;
- style profiles;
- reviewed examples;
- scenario rules and negative rules.

Blind benchmark mode must continue hiding target-language references and
translation memory from generation-facing packets.

## Translation Provenance

Goal: make each important generated segment explain which evidence influenced
the target text.

Future provenance views may connect a segment to:

- term registry entries;
- style rules;
- scenario rules;
- alignment examples;
- repair history;
- review decisions;
- human review evidence.

This should support review and debugging, not create false certainty about
semantic quality.

## Locale Engineering

Goal: treat locale behavior as engineering evidence, not merely wording.

Roadmap capabilities:

- plural rules;
- grammatical gender;
- RTL and bidirectional text handling;
- date, time, number, and currency formatting;
- Unicode normalization;
- fallback locale chains;
- layout-aware delivery checks where applicable.

Future `locale-capability-report` style artifacts should connect locale support
to coverage and forbidden claims. Until implemented, these remain non-claims.

## Non-Text Asset Pipeline

Goal: surface non-text localization gaps instead of letting text completion imply
full product localization.

Roadmap areas:

- image text detection and localization workflow;
- audio/video transcript and subtitle routing;
- binary resource inspection;
- layout adaptation;
- non-text coverage diagnostics.

Non-text assets should first appear as coverage and scorecard evidence. Actual
asset editing belongs to later adapter-specific work.

## Workbench Review Experience

Goal: turn artifact-backed gates into a usable review surface.

Future Workbench areas:

- run timeline;
- source inventory and coverage diagnostics;
- term review queue;
- blocking questions and resolution decisions;
- stale segments and reuse decisions;
- repair request/result/history;
- scorecard, evidence report, and forbidden claims;
- human review evidence;
- claim acceptance and signoff.

The UI should display and update runtime artifacts. It should not infer readiness
or implement policy separately from the runtime.

## CI/CD Integration

Goal: make localization readiness visible in pull requests and release
automation.

Roadmap areas:

- deterministic CLI checks with stable exit codes;
- protocol and contract validation in CI;
- stale artifact checks;
- scorecard and forbidden-claim checks;
- build/install/launch evidence where platform adapters support it;
- scheduled refresh of stale evidence.

CI should block on deterministic safety failures and report advisory warnings
for evidence gaps that require human review.

## Collaboration And Team Workflow

Goal: support multiple reviewers and translators without losing traceability.

Roadmap areas:

- reviewer assignment and ownership;
- conflicting term/review decisions;
- scoped acceptance by locale, file, segment, or risk class;
- team-shared knowledge packs;
- permission policy for locked terms and final signoff;
- auditable promotion of reviewed changes into reusable memory.

Team workflows must preserve artifact provenance. A shared decision should be
traceable to who made it, what scope it covers, and which downstream artifacts it
affects.

## Community Adapter Registry

Goal: make new platforms and formats extensible without weakening trust.

Future registry metadata should include:

- adapter id;
- supported extensions and project types;
- version and maintainer;
- capability level;
- trust tier;
- permissions and dependencies;
- contract-test status;
- known limitations;
- security notes.

Trust tiers may include official, trusted, community, and experimental. A
community adapter should never be treated as stable until contract tests and
evidence support that claim.

## Evolution Subagent

Goal: mine failures and propose controlled improvements without autonomous
release behavior.

Roadmap responsibilities:

- collect failure patterns from QA, repair, scorecards, and benchmarks;
- propose adapter or runtime improvements;
- suggest new regression tests;
- compare before/after evidence;
- produce patch proposals for human review.

The Evolution Subagent may propose changes. It must not merge, tag, release, or
change safety policy without human approval.

## Version Direction

Indicative future tracks:

| Track | Focus |
| --- | --- |
| v0.5 | Evidence Spine gates become stable claims. |
| v0.6 | Incremental localization and targeted repair stabilize. |
| v0.7 | Human review evidence, claim acceptance, and signoff stabilize. |
| v0.8 | Document Evidence Pack seed. |
| v0.9 | Personal Knowledge Pack builder seed. |
| v0.10 | Knowledge-augmented generation and review. |
| v0.11 | Agent orchestrator and subagent runtime. |
| v0.12 | Workbench review experience. |
| v0.13 | Benchmark lab and evaluation harness. |
| v0.14 | Evolution Subagent. |
| v0.14+ | Ecosystem, community adapters, locale engineering, non-text assets, and collaboration. |

