## Summary

Describe the change in a few sentences.

## Scope

* [ ] Agent Skill / workflow
* [ ] Glossary / Project Memory
* [ ] Independent review / report
* [ ] Runtime behavior
* [ ] Adapter behavior
* [ ] Protocol/schema
* [ ] Benchmark
* [ ] Documentation only
* [ ] Legacy simplification / compatibility
* [ ] Release/CI hygiene

## Safety checklist

* [ ] This PR has a narrow scope.
* [ ] This PR aligns with `docs/product-direction.md` and improves a Standard or Release workflow.
* [ ] This PR keeps the Skill, deterministic CLI, Coding Agent, Git, and user responsibility boundaries clear.
* [ ] This PR does not expand legacy Workbench, Provider governance, multi-agent orchestration, enterprise authorization, or protocol surface without an accepted product decision.
* [ ] New persistent data fits Glossary or Project Memory instead of creating another user-facing source of truth.
* [ ] Runtime behavior changes include tests.
* [ ] Adapter/resource changes include benchmark coverage.
* [ ] Protocol/contract changes were validated.
* [ ] Generated reports/work dirs are not committed.
* [ ] Public docs do not overclaim unsupported capabilities.
* [ ] If release-related, the tag is created from `main` only after clean validation.
* [ ] Existing public tags are not moved.

## Validation

Paste commands and results.
