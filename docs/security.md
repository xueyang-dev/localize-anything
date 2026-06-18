# Security and Privacy

## Data Classification

Support `public`, `internal`, `confidential`, and `restricted` project classifications. Privacy handling is opt-in during intake and persisted in project configuration.

- `public`: Permit normal external lookup.
- `internal`: Permit generic terminology searches without full project content.
- `confidential`: Use de-identified minimal queries only.
- `restricted`: Do not send project content to external services.

Never store credentials, tokens, private keys, or passwords in project memory or delivery packages.

## Adapter Trust

Distinguish declarative, scripted, and verified adapters. A future registry may discover candidates automatically, but must not silently download or execute community code.

## Apply Safety

Require staged writes, dry-run output, explicit confirmation, diff reporting, original hashes, and post-apply validation. Do not delete source or target artifacts by default.

## Commercial Game Data

Do not distribute extracted commercial game text or assets. Keep private benchmarks outside Git and publish aggregate results only.
