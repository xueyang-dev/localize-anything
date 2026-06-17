# Localize Anything Protocol 0.1

## Purpose

Define portable artifacts between agents, runtimes, and adapters. The protocol does not prescribe a model provider or implementation language.

## Canonical Artifacts

- Project configuration selects operational policy.
- Adapter manifests declare formats, capabilities, permissions, dependencies, and entrypoints.
- Segment JSONL carries source units and optional localized targets.
- Delivery manifests record immutable run facts and scoped status.
- QA results keep runtime, agent, and human evidence distinct.
- Batch plans group segments by content unit and adapter constraints.
- Work packets carry an ephemeral, budgeted context selection.
- Incremental diffs classify new, unchanged, changed, moved, and deleted segments.
- Acceptance records bind scoped sign-off to an immutable manifest hash.
- Apply plans describe dry-run operations without mutating the project.

## Lifecycle

```text
inspect -> preflight -> plan -> localize -> validate -> package
        -> review-import -> sign-off -> apply
```

Adapters implement the narrower lifecycle documented in `docs/adapters.md`.

## Delivery Status

- `draft_package`
- `review_ready`
- `blocked`
- `applied_draft`
- `user_accepted`

Only an explicit user action can produce `user_accepted`.

## Compatibility

All protocol documents carry `protocol_version`. A runtime must reject unsupported major versions and may accept additive minor-version fields when its schema permits them.
