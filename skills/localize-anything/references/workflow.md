# Workflow

## Standard Project Flow

```text
Intake -> Capability Scan -> Source Confirmation -> Localization Brief
       -> Adapter Detection -> Preflight -> Memory Initialization
       -> Termbase Preflight -> Generation Strategy -> Resolution Gate
       -> Generation Handoff Enforcement -> Artifact State Check
       -> Segment Staleness / Reuse Decision -> Batch Planning
       -> Context Retrieval -> Localization -> Deterministic QA
       -> Review -> Targeted Repair -> Patch-Based Repair
       -> Evaluation Scorecard -> Human Review Evidence
       -> Claim Acceptance -> Delivery -> Review Import
       -> Signoff Record -> Optional Apply
```

## Intake

Confirm source materials, source locale, target locales, intended audience, delivery intent, project sensitivity, and whether a localization entrypoint exists. Bundle related blocking questions instead of asking one field at a time.

## Preflight

Scan all content when feasible. For oversized material, scan in context-safe layers and update the same compressed project context after each layer. Skip deep preflight for very long, weakly connected, non-literary utility text; still inspect structure, adapters, hard constraints, and delivery requirements.

Assess workflow depth and recommend `fast`, `standard`, or `high-assurance`. Ask the user to choose.

## Batch Planning

Split by semantic unit before size: screen or flow, scene or conversation, chapter, document section, subtitle scene, sheet, campaign, or feature namespace. Preserve speaker and narrative continuity. Use size only as a safety limit.

## Questions

- Ask project-level blocking questions after preflight.
- Ask batch-specific blocking questions before the affected batch.
- Preserve ambiguous low-risk source forms and collect important questions at the batch boundary.
- Put minor questions and review notes in the QA report.

Allow independent batches and locales to continue when one branch is blocked.

## Evidence Spine

Use runtime artifacts as the source of truth for readiness:

- `localization-brief.json` / `.yaml` for task intent.
- Term Governance and termbase preflight artifacts for terminology.
- `generation-strategy.json`, Resolution Gate artifacts, and
  `generation-handoff-decision.json` for generation policy.
- `artifact-state.json`, `stale-segments.jsonl`, and `reuse-decision.json` for
  freshness and reuse.
- `segment-regeneration-plan.json`, `repair-request.json`,
  `repair-result.json`, and `repair-history.jsonl` for repair state.
- `evaluation-scorecard.json` and `evidence-level-report.md` for current
  evidence level, forbidden claims, and next actions.
- `human-review-evidence.jsonl`, `claim-acceptance-decision.json`, and
  `signoff-record.json` for qualified review, accepted claims, and owner
  authorization.

Do not infer readiness from UI state, prompt wording, or a successful file write.
If an upstream evidence artifact is stale, missing, or blocked, downgrade or
block the downstream claim.
