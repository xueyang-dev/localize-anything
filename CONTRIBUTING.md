# Contributing to Localize Anything

Localize Anything is in early development. Contributions are welcome
in the form of bug reports, protocol feedback, adapter ideas, and
benchmark improvements.

## Ways to contribute

- **Bug reports**: Open an issue with reproduction steps, expected behavior,
  and actual output.
- **Protocol feedback**: The protocol schemas define the project's contract.
  Feedback on schema design, lifecycle, and artifact formats is valuable.
- **Adapter proposals**: If you want to add a new format adapter, open an
  issue describing the format, extraction strategy, preservation requirements,
  and QA invariants.
- **Benchmark improvements**: The v021 mode-system benchmark is a good
  starting point. Full-app benchmarks and translation quality benchmarks
  are planned.
- **Docs**: Documentation improvements, corrections, and translations are
  welcome.

## Development

```bash
# Install in editable mode
pip install -e ".[yaml]"

# Run tests
python -m unittest discover -s tests -v

# Validate protocol
python -m runtime.localize_anything validate-protocol
python -m runtime.localize_anything validate-contracts

# Run benchmark
python benchmarks/v021-mode-system/run.py
```

## Code style

- Python 3.11+
- `from __future__ import annotations` at the top of every module
- Type annotations on public functions
- Docstrings are optional but helpful
- Follow existing patterns in `runtime/localize_anything/`

## Adding an adapter

1. Read [Adapter Contract](docs/adapters.md)
2. Implement extraction, rebuild, staging, and validation
3. Register the adapter in `adapters/core/<adapter-id>/adapter.json`
4. Add tests that exercise the adapter with real-world fixtures
5. Add the adapter to `runtime/localize_anything/cli.py`

## Commit conventions

- Short imperative commit messages
- Group related changes into logical commits
- No generated files in commits (use `.gitignore`)
- No credentials, API keys, or tokens

## License

By contributing, you agree that your contributions will be licensed
under the MIT License.
