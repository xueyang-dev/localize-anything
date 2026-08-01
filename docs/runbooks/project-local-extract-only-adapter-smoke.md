# Project-local extract-only adapter smoke

Use this runbook after an experimental project-local adapter is stable enough
to test inside a disposable worktree. Do not use it to claim generic Swift or
full product localization support.

## Setup

1. Create or choose a disposable test worktree for the target project.
2. Copy the adapter into the target project at:

   ```text
   .localize-anything/adapters/<adapter-id>/
   ```

3. Verify the adapter descriptor declares `round_trip_level: "extract_only"`,
   read-only capabilities, read-only permissions, source scope, provenance, and
   a SHA-256 checksum for its entrypoint.
4. Confirm the target project source tree is clean or that all existing changes
   are understood.

## Smoke Commands

Run scan with explicit selection:

```bash
localize scan PROJECT \
  --source-locale SOURCE \
  --target-locale TARGET \
  --source SOURCE_PATH \
  --adapter ADAPTER_ID
```

Then run check and review packet generation:

```bash
localize check PROJECT --target TARGET_PATH
localize review PROJECT --target TARGET_PATH
```

## Evidence To Inspect

Check these artifacts under `.localize-anything/`:

- `source-surface-inventory.json`
- `capability-report.json`
- `inventory.json`
- `source-validation.json`
- `deterministic-check.json`
- `extracted-segments.json`
- `review-packet.json`
- `adapter-runs/*.json`
- `adapter-runs/*.stderr.txt`

Confirm adapter ID, version, checksum, descriptor hash, entrypoint, command
duration, exit status, source/target fingerprints, inventory hash, validation
hash, and extraction hash are recorded.

Adapter stdout is accepted only up to the runtime safety ceiling of 8,000,000
bytes, with stderr captured separately for evidence. Treat larger payloads as a
scalability backlog item for a future streaming protocol, not as a successful
smoke.

## Required Negative Checks

- Run scan without `--adapter`; the adapter must be reported as a candidate but
  not executed.
- Change the source file; review must be blocked until `localize check` reruns.
- Change the descriptor or entrypoint; review must become stale or fail with a
  checksum blocker.
- Try to claim or trigger rebuild, apply, or editable delivery; the capability
  report must show these as blocked.
- Confirm the project source tree has no adapter-created modifications.

## Hermes/Vorssaint Use

When Hermes publishes a stable Vorssaint adapter, copy only that adapter into
the disposable worktree path above, select it explicitly with `--adapter`, and
run this smoke. Do not copy the Hermes worktree into Localize Anything tests,
and do not promote the result to generic Swift support.
