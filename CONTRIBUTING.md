# Contributing to Localize Anything

Localize Anything is the localization workflow and review layer for Coding
Agents. Read [Product Direction](docs/product-direction.md) and
[Architecture](docs/architecture.md) before proposing product or architecture
changes.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[yaml]"
python -m unittest discover -s tests -v
python -m runtime.localize_anything validate-protocol
python -m runtime.localize_anything validate-contracts
python -m compileall -q runtime benchmarks
python benchmarks/v022-android-resource-reliability/run.py
python benchmarks/v022-android-resource-reliability/source_sets.py
python benchmarks/v022-android-resource-reliability/risk_classification.py
python benchmarks/v021-mode-system/run.py
```

## Validation expectations

- Runtime behavior changes require tests.
- Adapter or resource-handling changes require benchmark coverage.
- Protocol or schema changes require protocol validation.
- Contract or manifest changes require contract validation.
- Release-related changes require validation from a clean checkout or worktree.

## Contribution rules

- Keep pull requests narrow.
- Prefer simplifying and consolidating existing capabilities over expanding the
  legacy platform surface.
- Keep the Agent Skill as the primary interface, the CLI deterministic and
  small, and Git as the change-management layer.
- Do not introduce a parallel Workbench, Provider-management platform,
  multi-agent framework, enterprise approval workflow, or user-facing protocol
  surface without a new accepted product decision.
- Treat Glossary and Project Memory as the canonical user-facing memory
  concepts.
- Do not commit generated reports, benchmark work directories, caches, or local
  scratch files.
- Do not expose private roadmaps or internal planning documents.
- Do not overclaim support boundaries in public documentation.
- Do not move public tags; fix forward with a new version.
- When unsupported input is detected, prefer fail-closed behavior and owner
  review over silent corruption.

## Pull request checklist

- What changed?
- What validation was run, and what were the results?
- Does the change affect source safety, staging, apply, or review behavior?
- Does the change support Standard or Release workflow and reduce user Review
  cost?
- Does it add a user-facing concept that should instead be consolidated into
  Glossary or Project Memory?
- Does the change require public documentation updates?

## License

By contributing, you agree that your contributions will be licensed under the
MIT License.
