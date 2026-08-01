# Localize Anything Core Data Contracts

Status: current for the five-command `localize` core.

## Purpose

The protocol directory documents only durable files exchanged across the Agent-native path:

`scan → glossary bootstrap → check → review → human confirmation → report`

It does not describe orchestration, Provider, Workbench, readiness, workflow, signoff, release governance, or Knowledge Pack platform artifacts.

## Contract rules

- `protocol_version` is `0.1`.
- Files are UTF-8 JSON.
- Unknown fields may be preserved for forward-compatible project context.
- Project build, test, lint, screenshots, and Git evidence remain project-native and are not protocol artifacts.
- A human confirmation may reference only a finding whose status is `needs_human_confirmation`; the Runtime enforces that relation.
- Severity values are `blocking`, `actionable`, `coverage_limitation`, and `informational`.
- Auto-cleared checks are review items, not findings, and are not counted as findings.

## Current contracts

| File | Producer | Purpose |
| --- | --- | --- |
| `project-memory.json` | `localize scan` | Source/target locales, declared resources, product context, style, TM, and confirmed decisions. |
| `glossary.json` | `localize glossary bootstrap` + Agent | One canonical, concept-centered glossary with candidate or locked concepts. |
| `deterministic-check.json` | `localize check` | Structural, placeholder, locale-resource, and locked-glossary findings. |
| `review-packet.json` | `localize review` | Self-contained packet for a fresh independent review context. |
| `independent-review.json` | `localize review --findings` | Normalized review items, review findings, and the small human-confirmation queue. |
| `human-confirmations.json` | `localize report --confirm` | Decisions linked only to open review findings. |
| `report.json` | `localize report` | Release-facing summary of check, review, confirmations, and limitations. |

Each contract has one schema under `protocol/schemas/` and one canonical example under `protocol/examples/`.

## Status values

Deterministic check:

- `pass`
- `pass_with_warnings`
- `fail`

Independent finding:

- `resolved`
- `needs_human_confirmation`

Review item:

- `auto_cleared`

Severity:

- `blocking`
- `actionable`
- `coverage_limitation`
- `informational`

## Review packet fields

`review-packet.json` contains:

- `instruction`: independent reviewer task and evidence rules.
- `project_memory`: declared locales, source files, style, preserve rules, translation memory, and confirmed decisions.
- `glossary`: canonical concept-centered terminology.
- `deterministic_check`: latest structural check output, or `null`.
- `source_target_mapping`: explicit source-to-target file mapping in scan order.
- `files`: aligned source/target segments.
- `review_result_format`: expected JSON with `review_items` for auto-cleared checks and `findings` for real issues.

Final report:

- `incomplete`
- `needs_human_confirmation`
- `needs_attention`
- `ready`

## Validation

`runtime.localize_anything.schema_validation.validate_protocol_tree` performs a dependency-free schema/example parity check. It is a repository validation helper, not a public workflow command.

## Compatibility boundary

The previous protocol remains historical documentation only in `docs/architecture-v0.4-legacy.md` and Git history. Removed schemas and examples are not accepted by the current five-command core.
