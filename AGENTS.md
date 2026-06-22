# Agent Instructions

## Ponytail Check

When writing or editing code in this repository, use the installed `ponytail`
skill as a pre-flight and review check.

Before adding code, ask:

- Does this need to exist at all?
- Can deletion, configuration, the Python standard library, or existing project
  code solve it?
- Is this abstraction needed now, or is it scaffolding for a future that has not
  arrived?

Prefer the smallest working diff. Do not add one-implementation interfaces,
factories, wrappers, broad refactors, or new dependencies unless the current
problem proves they are needed.

Never simplify away trust-boundary validation, data-loss prevention, security
checks, explicit user requirements, or benchmark evidence. For non-trivial
logic, leave the smallest runnable check that would fail if the logic regresses.
