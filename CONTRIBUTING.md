# Contributing to Localize Anything

Localize Anything is an agent-native localization framework for safely
extracting, translating, reviewing, and applying localized resources.

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
- Does the change require public documentation updates?

## License

By contributing, you agree that your contributions will be licensed under the
MIT License.
