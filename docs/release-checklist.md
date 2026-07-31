# Release Checklist

Before publishing a release:

1. Confirm README, Agent Skill, Product Direction, Architecture, Roadmap, and
   public claims describe the same product boundary.
2. Confirm current implementation, limited format compatibility, and historical
   evidence are labeled accurately.
3. Merge release code into `main`.
4. Run unit tests, protocol validation, adapter validation, `compileall`, and
   the five-command end-to-end tests.
5. Create the release tag from `main`, not from a side branch.
6. Validate the tag from a clean checkout or worktree.
7. Push the tag.
8. Create the GitHub Release only after clean tag validation passes.
9. Never move a public tag; fix forward with a new version.
