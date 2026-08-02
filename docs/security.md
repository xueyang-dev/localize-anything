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
and checksum mismatches are blocking failures. Freshness covers the complete
adapter runtime payload: every regular file under the adapter directory
(entrypoint, helper modules, data files) is fingerprinted, so any adapter
payload change invalidates downstream artifacts.

Project-local adapter payloads must be vendored trees of regular files and
directories. Symlinks are unsupported anywhere in the payload: file symlinks,
directory symlinks, nested symlinks, symlinks that stay inside the adapter
root, symlinks elsewhere in the project, symlinks outside the project, and
broken symlinks are all rejected with the stable code `adapter_payload_symlink`
before the adapter can execute. FIFOs, sockets, and device nodes are rejected
with `adapter_payload_special_file`. Adapters that need shared helper code or
data must copy it into their own payload or use a constrained dependency
contract; the runtime does not follow links.

The scripted runner uses argv arrays with `shell=False`, runs from the adapter
root, sends a JSON stdin request, accepts only bounded JSON stdout, stores
stderr separately under `.localize-anything/adapter-runs/`, uses a timeout, and
does not pass project credentials or user environment variables. The current
stdout safety ceiling is 8,000,000 bytes, with a separate stderr evidence
ceiling; output size is validated after the process finishes, not enforced
while it streams, and larger adapter output is blocked rather than treated as
partial success. The timeout terminates the direct subprocess and does not
guarantee cleanup of the entire process tree. This is a bounded extract-only
bridge, not an unlimited streaming protocol, and it is not an OS-level
sandbox. The first project-local tier is read-only: no rebuild, apply,
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
