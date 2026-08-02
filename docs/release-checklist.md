# Release Checklist

Before publishing a release:

1. Confirm README, Agent Skill, Product Direction, Architecture, Roadmap, and
   public claims describe the same product boundary.
2. Confirm surface-aware coverage, unsupported/dynamic/non-text limitations,
   and programming-language non-claims are reflected in delivery wording.
3. Confirm current implementation, limited format compatibility, and historical
   evidence are labeled accurately.
4. Merge release code into `main`.
5. Run unit tests, protocol validation, adapter validation, `compileall`, and
   the five-command end-to-end tests.
6. Create the release tag from `main`, not from a side branch.
7. Validate the tag from a clean checkout or worktree.
8. Push the tag.
9. Create the GitHub Release only after clean tag validation passes.
10. Never move a public tag; fix forward with a new version.
