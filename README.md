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

See [Architecture](docs/architecture.md) and
[Adapter Contract](docs/adapters.md) for public documentation.

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
Delivery snapshots can also be summarized with `delivery-dashboard`, and
classified with `delivery-decision`, for developer and translator review.
The first real-project benchmarks target AntennaPod's pinned Android strings
resource under `benchmarks/android-antennapod/` and Signal-iOS's pinned
`Localizable.strings` resource under `benchmarks/ios-signal/`, plus
IceCubesApp's pinned `Localizable.xcstrings` resource under
`benchmarks/ios-icecubes-xcstrings/`. All three have passed synthetic
agent/runtime/staging/QA verification with delivery decision artifacts.
AntennaPod has also passed the Android app-copy E2E path with local Chinese
draft generated segment JSONL and the real-generation gate enabled.
LLM draft generation stays host-agent driven: the runtime emits
provider-agnostic `draft-request` artifacts and validates returned generated
segment JSONL before staging files. Multi-batch runs can use
`generation-handoff` and `collect-generated` to coordinate host-agent output
without binding the runtime to a model provider. `stage-generated` then routes
the returned segment JSONL through the correct adapter so users do not need to
remember platform-specific staging commands. `localize-run` wraps the common
path from preflight through dashboard while still keeping model execution
outside the deterministic runtime.
`agent-run` is the first provider-agnostic agent shell on top of that runtime:
it records routing decisions, prepares parallel translation batches, imports
host LLM responses when available, and reflects through review, QA, dashboard,
delivery-decision, and apply-plan artifacts before any project overwrite. Runs
are indexed under
`.localize-anything/sessions/index.json` so CLI and Web UI workflows can
inspect prior agent/runtime sessions.
v0.2.1 adds explicit localization modes. The default is
`greenfield_localization` with `style_only`, so a new locale can use approved
terminology without treating existing target files as truth. Use
`--operating-mode blind_benchmark` for leakage-safe benchmark packets, or
`--operating-mode existing_locale_maintenance` to preserve reviewed unchanged
translations and generate only missing, stale, conflicting, or unreviewed
segments.

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

Start the local Web Workbench when you want an interface instead of raw CLI
commands:

```bash
python3 -m runtime.localize_anything ui
```

The workbench binds to `127.0.0.1` by default and opens the same
protocol-backed workflow through browser controls: inspect a project, confirm
routing, create LLM handoff batches, import response folders, preview review
sheets, and inspect apply plans. It calls the existing runtime APIs and writes
the same artifacts as `agent-run`.

Confirm source material explicitly during preflight:

```bash
python3 -m runtime.localize_anything preflight ./project \
  --source-locale en-US \
  --source-file locales/en-US.json \
  --target-locale zh-CN
```

For the agent-first workflow, let the runtime route project text, create
parallel handoff prompts, and write an `agent-summary.json`:

```bash
python3 -m runtime.localize_anything agent-run ./project \
  --target-locale zh-CN \
  --output-root localize-anything-output
```

This produces `prompts/`, `draft-requests/`, `responses/`, and
`generation-README.md`, plus an `agent-summary.json` and project session index.
Send each prompt or draft request to the host LLM
translation workflow, save responses under `responses/`, then let the agent
import, validate, stage, package, and prepare review/apply artifacts:

```bash
python3 -m runtime.localize_anything agent-run ./project \
  --target-locale zh-CN \
  --responses-dir localize-anything-output/<agent-run-id>/responses \
  --output-root localize-anything-output
```

`agent-run` does not call a model provider by default. Use `provider-generate`
when you want direct HTTP provider execution, or keep the manual
handoff/import fallback.

### DeepSeek Provider

The first direct LLM provider integration. Translates Android/iOS/JSON segments
via DeepSeek API with automatic placeholder parity:

```bash
localize-anything deepseek-generate segments.jsonl \
  --target-locale ja \
  --generated-output generated.jsonl
```

Proven with AntennaPod en-US→ja+ko (869 segments, 0 QA issues). Requires
`DEEPSEEK_API_KEY` in environment.

`agent-run` can also call the same direct HTTP provider path and continue to
staging/delivery automatically:

```bash
python3 -m runtime.localize_anything agent-run ./project \
  --target-locale zh-CN \
  --provider-url http://127.0.0.1:9000/generate \
  --output-root localize-anything-output
```

List resumable sessions for a project:

```bash
python3 -m runtime.localize_anything sessions ./project
```

For an automated Android source-project localization test, run the agent
against an isolated app copy and apply the generated language resource only to
that copy:

```bash
python3 -m runtime.localize_anything android-app-test ./android-project \
  --source-locale en-US \
  --target-locale zh-CN \
  --output-root localize-anything-output/android-app-e2e \
  --run-id android-app-e2e-001
```

The report proves the original project was not mutated, the localized app copy
contains `res/values-zh-rCN/strings.xml`, and Android resource QA passes after
apply. If the project has multiple Android source `strings.xml` files, pass
`--source-file` to constrain the test. The default generation mode is synthetic
draft for engineering verification; use real LLM/provider output before making
translation quality claims.

For a single-command local generated-input Android E2E run before wiring a
provider, use the local Chinese draft mode:

```bash
python3 -m runtime.localize_anything android-app-test ./android-project \
  --source-locale en-US \
  --target-locale zh-CN \
  --local-chinese-draft \
  --require-real-generation \
  --output-root localize-anything-output/android-app-e2e \
  --run-id android-app-e2e-local-001
```

This creates generated segment JSONL inside the test directory, marks it as
`provider: codex-local` and `quality_claim: local_chinese_draft_for_e2e`, then
continues through the same agent, delivery, apply, and Android QA path. It is
useful for proving the app-copy pipeline, not for translation quality claims.

When Codex or a host LLM has produced generated segment JSONL, pass it into the
same Android app-copy test:

```bash
python3 -m runtime.localize_anything android-app-test ./android-project \
  --source-locale en-US \
  --target-locale zh-CN \
  --generated generated.jsonl \
  --require-real-generation \
  --output-root localize-anything-output/android-app-e2e \
  --run-id android-app-e2e-codex-001
```

The generated JSONL must use the same segment contract as `agent-run`:
`segment_id`, source fields preserved from extraction, `target_locale`,
`target`, `status: generated`, and optional `generation` metadata such as
`provider: codex`. Use `--require-real-generation` when the run should fail
unless it is using non-synthetic generated text with a non-empty quality claim.

For local engineering tests before wiring a provider, create a conservative
Chinese draft JSONL from extracted segments:

```bash
python3 -m runtime.localize_anything generate-chinese-draft segments.jsonl \
  --target-locale zh-CN \
  --generated-output generated.jsonl
```

This helper marks output as `provider: codex-local` and
`quality_claim: local_chinese_draft_for_e2e`. It is useful when you want to
inspect or reuse the generated JSONL outside the single-command app-copy test.

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

The completed run also writes `review-sheet.md`, `review-sheet.csv`,
`llm-review-request.json`, `llm-review-prompt.md`, `delivery-decision.md`, and
`apply-plan.md` so the developer or translator can inspect source/target text,
request LLM reflection, and review exact create/replace operations before any
apply step.

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

If a handoff import or collect report has failed or missing batches, create a
smaller retry handoff without rerunning extraction:

```bash
python3 -m runtime.localize_anything retry-handoff \
  localize-anything-output/<run-id>/generation-handoff.json \
  localize-anything-output/<run-id>/response-import.json \
  --generated-dir localize-anything-output/<run-id>/retry-generated-batches \
  --output localize-anything-output/<run-id>/retry-handoff.json
```

To run a direct HTTP JSON provider instead of manually copying prompts, post
each draft request through `provider-generate`. The provider response is still
normalized and validated through the same generated segment JSONL contract:

```bash
python3 -m runtime.localize_anything provider-generate \
  localize-anything-output/<run-id>/generation-handoff.json \
  --provider-url http://127.0.0.1:9000/generate \
  --generated-output localize-anything-output/<run-id>/generated.jsonl
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

To request and import LLM reflection as actionable segment-level issues:

```bash
python3 -m runtime.localize_anything llm-review-request generated.jsonl \
  --source-locale en-US \
  --target-locale zh-CN \
  --prompt-output llm-review-prompt.md \
  --output llm-review-request.json

python3 -m runtime.localize_anything import-llm-review \
  llm-review-request.json llm-review-response.md \
  --review-output llm-review-result.json
```

To inspect an apply plan without writing files:

```bash
python3 -m runtime.localize_anything plan-apply <delivery-dir> ./project \
  --markdown-output apply-plan.md
```

To ask the Delivery Agent for an explicit owner/developer decision report:

```bash
python3 -m runtime.localize_anything delivery-decision <delivery-dir> ./project \
  --markdown-output delivery-decision.md
```

Only after the project owner approves that plan should the delivery be applied
with `apply-delivery --confirm-run-id <run-id>`.

## License

MIT. Third-party benchmark sources and fixtures retain their original licenses.
