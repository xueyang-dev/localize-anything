# Workflow

## Standard Project Flow

```text
Intake -> Capability Scan -> Source Confirmation -> Adapter Detection
       -> Preflight -> Workflow Recommendation -> Memory Initialization
       -> Batch Planning -> Context Retrieval -> Localization
       -> QA and Repair -> Delivery -> Review Import -> Scoped Sign-off
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
