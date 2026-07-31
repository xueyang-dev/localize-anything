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

## Apply Safety

The Coding Agent owns project edits and Git delivery. Inspect existing changes,
keep localization edits visible in the diff, run deterministic checks before
completion, and do not delete or overwrite uncertain source or target artifacts.
The five-command core writes only `.localize-anything/` state in the target
project. Application and locale-resource edits remain visible Coding Agent
changes guarded by project-native tests and Git.

## Commercial Game Data

Do not distribute extracted commercial game text or assets. Keep private benchmarks outside Git and publish aggregate results only.
