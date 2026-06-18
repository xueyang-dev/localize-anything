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
inspect -> preflight -> plan -> draft-request -> host-agent generation
        -> collect-generated -> stage-generated -> validate -> package
        -> review import -> scoped sign-off -> apply dry-run
```

See [Grill Decisions](docs/grill-decisions.md) for the canonical product
decisions, plus [Architecture](docs/architecture.md),
[Roadmap](docs/roadmap.md), and [Adapter Contract](docs/adapters.md).
The completed release gates are mapped in
[v0.1 Verification](docs/v0.1-verification.md).

## Current Iteration

The v0.2 iteration starts with source-owned Android and iOS projects for
individual developers. Localize Anything generates drop-in language resources
in staging instead of repackaging apps. The Android platform slice supports
`res/values/strings.xml` extraction for `<string>`, `<string-array>`, and
`<plurals>` resources, `res/values-<locale>/strings.xml` staged delivery,
deterministic resource QA, and explicit run-id-confirmed apply.
The iOS platform slice supports `.lproj` `.strings` and `.stringsdict`
resources, including staged `zh-Hans.lproj` output for `zh-CN`.
The String Catalog slice supports `.xcstrings` files by updating target
language entries inside a staged catalog copy.
Delivery snapshots can also be summarized with `delivery-dashboard` for
developer and translator review.
The first real-project benchmarks target AntennaPod's pinned Android strings
resource under `benchmarks/android-antennapod/` and Signal-iOS's pinned
`Localizable.strings` resource under `benchmarks/ios-signal/`, plus
IceCubesApp's pinned `Localizable.xcstrings` resource under
`benchmarks/ios-icecubes-xcstrings/`.
LLM draft generation stays host-agent driven: the runtime emits
provider-agnostic `draft-request` artifacts and validates returned generated
segment JSONL before staging files. Multi-batch runs can use
`generation-handoff` and `collect-generated` to coordinate host-agent output
without binding the runtime to a model provider. `stage-generated` then routes
the returned segment JSONL through the correct adapter so users do not need to
remember platform-specific staging commands. `localize-run` wraps the common
path from preflight through dashboard while still keeping model execution
outside the deterministic runtime.

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

For the common developer workflow, create provider-agnostic LLM prompt and
request artifacts first:

```bash
python3 -m runtime.localize_anything localize-run ./project \
  --source-locale en-US \
  --target-locale zh-CN \
  --source-file locales/en-US.json \
  --handoff-only \
  --output-root localize-anything-output
```

Open the generated `generation-README.md`. For manual workflows, send each
`prompts/*.md` file to the host-agent LLM workflow and save each response under
`responses/` using the matching batch id, such as `batch-0001-response.md`.
For automated workflows, consume `draft-requests/*.json` directly.

When the run's `generated-batches/` directory contains one generated JSONL file
per batch, create staged files, a delivery package, and a dashboard:

```bash
python3 -m runtime.localize_anything localize-run ./project \
  --source-locale en-US \
  --target-locale zh-CN \
  --source-file locales/en-US.json \
  --generated-dir localize-anything-output/<handoff-run-id>/generated-batches \
  --output-root localize-anything-output
```

The completed run also writes `review-sheet.md`, `review-sheet.csv`, and
`apply-plan.md` so the developer or translator can inspect source/target text
and exact create/replace operations before any apply step.

If the model returns fenced JSON blocks, JSON arrays, or `segment_id -> target`
maps instead of strict JSONL, place each response in a directory named by batch
id, for example `batch-0001-response.md`, then normalize the whole handoff:

```bash
python3 -m runtime.localize_anything import-generated-handoff \
  localize-anything-output/<run-id>/generation-handoff.json \
  localize-anything-output/<run-id>/responses \
  --generated-output localize-anything-output/<run-id>/generated.jsonl
```

To normalize one batch directly:

```bash
python3 -m runtime.localize_anything import-generated-response \
  localize-anything-output/<run-id>/work-packets/batch-0001.json \
  llm-response.md \
  --generated-output localize-anything-output/<run-id>/generated-batches/batch-0001.jsonl
```

After LLM draft generation returns segment JSONL, create staged target files
with a single routing command:

```bash
python3 -m runtime.localize_anything stage-generated ./project generated.jsonl \
  --source-locale en-US \
  --target-locale zh-CN \
  --staging-dir localize-anything-output/staging
```

To export a standalone review sheet from generated segment JSONL:

```bash
python3 -m runtime.localize_anything review-sheet generated.jsonl \
  --markdown-output review-sheet.md \
  --csv-output review-sheet.csv
```

To inspect an apply plan without writing files:

```bash
python3 -m runtime.localize_anything plan-apply <delivery-dir> ./project \
  --markdown-output apply-plan.md
```

Only after the project owner approves that plan should the delivery be applied
with `apply-delivery --confirm-run-id <run-id>`.

## License

MIT. Third-party benchmark sources and fixtures retain their original licenses.
