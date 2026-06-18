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
- Incremental diffs classify new, unchanged, changed, moved, and deleted segments.
- Acceptance records bind scoped sign-off to an immutable manifest hash.
- Apply plans describe dry-run operations without mutating the project.

## Lifecycle

```text
inspect -> preflight -> plan -> retrieve -> draft-request -> draft-prompt
        -> generation-handoff -> localize -> import-generated-response(s)
        -> collect-generated
        -> stage-generated -> validate-output -> package
        -> review-import -> sign-off -> apply
```

`localize-run` is a reference-runtime convenience command for this lifecycle.
It emits provider-agnostic draft requests for host-agent translation generation,
then, once generated segment JSONL is supplied, writes staged target files,
packages them, and produces a dashboard. It does not make model-provider calls
or overwrite source project files.

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
