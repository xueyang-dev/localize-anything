# Localize Anything

Localize Anything is an agent-native, adapter-driven localization workflow. It turns source artifacts into review-ready localization packages while preserving format, context, terminology, provenance, and delivery state.

The project is protocol-first:

1. The protocol defines portable artifacts and lifecycle rules.
2. The reference runtime performs deterministic file operations and QA.
3. Agent integrations handle intake, interpretation, localization, and user decisions.
4. Adapters implement format- and scenario-specific SOPs.

## v0.1 Scope

The v0.1 workflow covers:

- JSON, YAML, and TOML locale resources
- GNU gettext PO/POT and XLIFF
- CSV, TSV, and XLSX tables
- Markdown and HTML documents
- SRT and WebVTT subtitles
- the Battle for Wesnoth campaign workflow
- `en-US` to `zh-CN` blind-generation benchmarking on The South Guard

Every standard-project adapter participates in the same delivery lifecycle:

```text
inspect -> preflight -> plan -> localize -> validate -> package
        -> review import -> scoped sign-off -> apply dry-run
```

See [Grill Decisions](docs/grill-decisions.md) for the canonical product
decisions, plus [Architecture](docs/architecture.md),
[Roadmap](docs/roadmap.md), and [Adapter Contract](docs/adapters.md).
The completed release gates are mapped in
[v0.1 Verification](docs/v0.1-verification.md).

## Repository Layout

```text
protocol/        Portable schemas and lifecycle specification
runtime/         Reference CLI and deterministic workflow implementation
skills/          Agent-facing integration
adapters/        Core format and scenario adapters
benchmarks/      Reproducible public benchmarks
tests/           Contract, fixture, and round-trip tests
docs/            Architecture, roadmap, security, and decisions
```

## Runtime

Run the reference runtime from the repository root:

```bash
python3 -m runtime.localize_anything --help
python3 -m runtime.localize_anything validate-contracts
python3 -m runtime.localize_anything validate-protocol
python3 -m unittest discover -s tests -v
```

Confirm source material explicitly during preflight:

```bash
python3 -m runtime.localize_anything preflight ./project \
  --source-locale en-US \
  --source-file locales/en-US.json \
  --target-locale zh-CN
```

## License

MIT. Third-party benchmark sources and fixtures retain their original licenses.
