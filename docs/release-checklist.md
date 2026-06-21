# Release Checklist

Before publishing a release:

1. Merge release code into `main`.
2. Run unit tests, protocol validation, contract validation, `compileall`, and
   all regression benchmarks.
3. Create the release tag from `main`, not from a side branch.
4. Validate the tag from a clean checkout or worktree.
5. Push the tag.
6. Create the GitHub Release only after clean tag validation passes.
7. Never move a public tag; fix forward with a new version.

v0.2.3 followed this process after v0.2.2 was retained as an unpublished
historical tag.
