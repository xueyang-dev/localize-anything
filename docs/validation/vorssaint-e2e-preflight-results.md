# Vorssaint runtime E2E preflight results

Status: pass

Generated: `2026-08-01T14:18:53Z`

Integration worktree:
`/Users/xueyang/Dev/localize-anything-vorssaint-e2e`

Branch:
`test/vorssaint-project-adapter-e2e`

Base HEAD:
`76eb1c189b1cb48aa188b10b340b1360f9c28b6c`

## Commands

| Command | Exit code | Result |
| --- | ---: | --- |
| `python3 -m unittest discover -s tests` | 0 | `Ran 70 tests in 5.922s`; `OK`. Test count did not decrease from the previous 70-test baseline. |
| `python3 -m compileall runtime` | 0 | Compileall completed for `runtime` and `runtime/localize_anything`. |
| `git diff --check` | 0 | No whitespace or patch-format errors. |

Ignored `__pycache__` output created by Python verification was removed after
recording the successful exit codes. No generated cache files are present in
`git status --porcelain=v1 --untracked-files=all`.

## Failures And Fixes

No Phase 0.7 command failed.

The later real Vorssaint E2E exposed two integration-only runtime bridge bugs,
both now documented in
`docs/validation/vorssaint-e2e-change-import-manifest.md`:

- `runtime/localize_anything/project_adapters.py`: raised
  `MAX_STDOUT_BYTES` to `8_000_000` while retaining the oversized-output
  blocker regression test, because real Vorssaint extract stdout is 3,829,242
  bytes.
- `runtime/localize_anything/project_adapters.py`: stdout/stderr now write to
  temporary files before bounded reads, and oversized-output blockers include
  actual/max byte evidence. This keeps the current bridge bounded without
  implementing a streaming protocol in this round.
- `runtime/localize_anything/project_adapters.py`: adapter run evidence now
  records `execution_mode = runtime_project_local_adapter`; canonical
  project-local files and review packets carry the same evidence. Synthetic
  tests assert this so runtime output cannot be confused with standalone output.

After those fixes, the same full regression commands above still pass with 70
tests.

## Integration Diff Hash

Command:

```bash
python3 - <<'PY'
from pathlib import Path
import hashlib, subprocess
repo = Path('/Users/xueyang/Dev/localize-anything-vorssaint-e2e')
tracked = subprocess.check_output(['git', 'diff', '--binary'], cwd=repo)
others = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=repo)
h = hashlib.sha256(); h.update(tracked)
for raw in sorted(item for item in others.split(b'\0') if item):
    name = raw.decode()
    if name == 'docs/validation/vorssaint-e2e-preflight-results.md':
        continue
    p = repo / name
    h.update(b'\0UNTRACKED\0'); h.update(raw); h.update(b'\0')
    h.update(hashlib.sha256(p.read_bytes()).hexdigest().encode())
print(h.hexdigest())
PY
```

Result:
`1788574a48e2ec52db300386c0e3b72b1c2ebff596c30487a5262b16fa7f6f36`

The hash intentionally excludes this preflight report to avoid a self-referential
digest. It includes the isolation audit, import manifest, owned untracked files,
and tracked runtime/documentation/test diffs.

## Original Worktree Unchanged Proof

Command:

```bash
git -C /Users/xueyang/Dev/localize-anything status --porcelain=v1 --untracked-files=all
```

Current status SHA-256:
`9c4a26bb881201d4756077feec23b44256f20b29ea00767435b4195b56bb56bd`

The status remains the known mixed-owner dirty set from the original worktree.
It does not include:

- `docs/validation/vorssaint-e2e-change-import-manifest.md`
- `docs/validation/vorssaint-e2e-isolation-audit.md`
- `docs/validation/vorssaint-e2e-preflight-results.md`

No staging, commit, reset, stash, cleanup, push, or PR action was performed in
the original worktree.

## Preflight Verdict

The isolated Localize Anything integration worktree is regression-clean before
the Hermes/Vorssaint runtime E2E evidence is relied on. The test count remains
at 70, compileall passes, diff check passes, and the original mixed worktree was
not modified by the isolation or validation work.
