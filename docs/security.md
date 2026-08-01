# Security and Privacy

## Data Classification

Support `public`, `internal`, `confidential`, and `restricted` project classifications. Privacy handling is opt-in during intake and persisted in project configuration.

- `public`: Permit normal external lookup.
- `internal`: Permit generic terminology searches without full project content.
- `confidential`: Use de-identified minimal queries only.
- `restricted`: Do not send project content to external services.

Never store credentials, tokens, private keys, or passwords in Project Memory
or localization reports.

## Adapter Trust

Existing format handlers may be declarative or scripted. Localize Anything does
not need a community registry for v1. Never silently download or execute
third-party handler code; prefer the project's existing tooling and explicit
user authorization.

Project-local scripted adapters are restricted to the fixed project path
`.localize-anything/adapters/<adapter-id>/`. They are discovered but not
executed unless explicitly selected. Before execution, the runtime validates the
adapter ID, descriptor, trust tier, read-only capability, source scope,
entrypoint path, checksum, and canonicalized paths. Symlink or `..` escapes,
shell metacharacter entrypoints, undeclared executables, missing entrypoints,
and checksum mismatches are blocking failures.

The scripted runner uses argv arrays with `shell=False`, runs from the adapter
root, sends a JSON stdin request, accepts only bounded JSON stdout, stores
stderr separately under `.localize-anything/adapter-runs/`, uses a timeout, and
does not pass project credentials or user environment variables. The current
stdout safety ceiling is 8,000,000 bytes, with a separate stderr evidence
ceiling; larger adapter output is blocked rather than treated as partial
success. This is a bounded extract-only bridge, not an unlimited streaming
protocol. The first project-local tier is read-only: no rebuild, apply,
network, or source-project write phase is authorized.

## Apply Safety

The Coding Agent owns project edits and Git delivery. Inspect existing changes,
keep localization edits visible in the diff, run deterministic checks before
completion, and do not delete or overwrite uncertain source or target artifacts.
The five-command core writes only `.localize-anything/` state in the target
project. Application and locale-resource edits remain visible Coding Agent
changes guarded by project-native tests and Git.

## Commercial Game Data

Do not distribute extracted commercial game text or assets. Keep private benchmarks outside Git and publish aggregate results only.
