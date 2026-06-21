# Localize Anything

<p align="center">
  <strong>Agent-native localization infrastructure for real source projects.</strong><br>
  <em>LLMs can translate strings. Localize Anything makes localization deliverable.</em>
</p>

<p align="center">
  <a href="#localize-anything">English</a> ·
  <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT">
  <img src="https://github.com/xueyang-dev/localize-anything/actions/workflows/ci.yml/badge.svg" alt="CI">
  <a href="https://github.com/xueyang-dev/localize-anything/releases/tag/v0.2.4"><img src="https://img.shields.io/badge/release-v0.2.4-blue" alt="Release: v0.2.4"></a>
  <img src="https://img.shields.io/badge/QA-deterministic-green" alt="QA: deterministic">
  <img src="https://img.shields.io/badge/apply-staged%20first-blueviolet" alt="Apply: staged first">
</p>

Localize Anything is an agent-native localization framework for developers and
localization teams working with real source projects. It turns model- or
human-generated translations into a safe, reviewable, and reproducible delivery
workflow: extract content, generate drafts through agents or providers, validate
structure deterministically, stage output, review it, and apply changes only
after explicit run-id confirmation.

## Status

**Current release:** [v0.2.4 — Release Hygiene and CI Benchmark Coverage](https://github.com/xueyang-dev/localize-anything/releases/tag/v0.2.4)

v0.2.4 adds release hygiene and runs the full regression benchmark suite in CI
on Python 3.11 and 3.12. It does not add localization features; the current
Android capability boundary remains documented by the v0.2.3 reliability
release. See the [changelog](CHANGELOG.md) and [release checklist](docs/release-checklist.md).

Verified engineering evidence:

- v0.2.4 CI benchmark coverage on Python 3.11 and 3.12: pass
- v0.2.3 Android resource reliability regressions: pass
- v0.2.1 mode-system benchmark: pass
- AntennaPod DeepSeek test: 869 segments in each of 2 locales, 0 deterministic QA issues, both builds successful

These results demonstrate pipeline and structural correctness. They are not a
claim of native-level translation quality.

## Why this exists

An LLM can produce plausible strings. A real localization delivery must also
protect placeholders and markup, preserve reviewed work, track evidence, surface
conflicts, and avoid damaging the source project.

Localize Anything is the missing engineering layer between a source project, an
LLM or human translator, and the final deliverable. The runtime handles
deterministic work; agents and providers handle semantic work.

## What Localize Anything does

**Extract → Generate → QA → Stage → Review → Apply**

- Extracts translatable content from real project formats
- Plans what to generate and what to preserve based on operating mode
- Generates drafts through host agents or direct providers, with scoped context
- Validates placeholders, markup, escapes, keys, and file structure programmatically
- Stages output outside the source project for review
- Packages manifests, QA evidence, review state, and an apply plan
- Applies only after explicit run-id confirmation, with backups

<p align="center">
  <img src="docs/assets/workflow-dark.svg" alt="Localize Anything workflow: 9 steps from Project Agent to Apply with Backups" width="900">
</p>

## Core guarantees

| Guarantee | Enforcement |
|-----------|-------------|
| **Staging first** | Generated files are written to an isolated staging directory, not the source project. |
| **Deterministic QA** | Placeholder parity, markup integrity, escapes, keys, and format rules are checked in code. |
| **No silent overwrite** | Conflicts block apply until they are resolved. |
| **Confirmed apply** | Apply requires a matching `--confirm-run-id`; replaced files are backed up. |
| **Source mutation detection** | SHA-256 checks detect unexpected changes during a run. |
| **Maintenance preservation** | Reviewed unchanged translations and Android target-only resources are preserved in verified maintenance workflows. |
| **Reference isolation** | Blind benchmarks keep existing translations out of generation-facing artifacts. |
| **Reviewable delivery** | Manifests, QA results, sign-off scope, and file operations remain inspectable. |

See [Security](docs/security.md) for the complete safety architecture.

## Quick start

### From source

```bash
git clone https://github.com/xueyang-dev/localize-anything.git
cd localize-anything
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[yaml]"
python -m unittest discover -s tests -v
```

### Try the regression benchmarks

```bash
python benchmarks/v022-android-resource-reliability/run.py
python benchmarks/v022-android-resource-reliability/source_sets.py
python benchmarks/v022-android-resource-reliability/risk_classification.py
python benchmarks/v021-mode-system/run.py
```

### Inspect a real project

```bash
localize-anything inspect /path/to/project
```

## Example workflow

Create a staged Japanese greenfield delivery from an Android source file using
synthetic drafts, without calling an external model:

```bash
localize-anything localize-run /path/to/project \
  --source-locale en-US \
  --target-locale ja \
  --source-file app/src/main/res/values/strings.xml \
  --operating-mode greenfield_localization \
  --reference-policy style_only \
  --run-id greenfield-001 \
  --synthetic-draft
```

The run produces staged files and delivery evidence. Writing into the project is
a separate, dry-run-planned action that requires explicit run-id confirmation.

## Current support

### Implemented core adapters

These adapters are marked `implemented` in their manifests:

- JSON locale files
- YAML and TOML
- CSV, TSV, and XLSX
- Markdown and HTML text extraction/rebuild; code, attributes, and
  `script`/`style`/`svg` content remain untouched
- SRT and WebVTT
- XLIFF 1.2 and 2.x
- GNU gettext PO/POT

### Experimental platform adapters

- Android `strings.xml`
- iOS `.strings` and `.stringsdict`
- Xcode `.xcstrings` String Catalogs

See the [Adapter Contract](docs/adapters.md) for adapter IDs, preservation rules,
and the full format boundary.

## Evidence

### v0.2.1 mode-system benchmark

| Mode | Reference policy | Result |
|------|------------------|--------|
| `blind_benchmark` | `blind` | pass — no leakage to generation artifacts |
| `greenfield_localization` | `style_only` | pass |
| `existing_locale_maintenance` | `preserve_existing` | pass — 10 preserved, 2 generated |
| `rewrite_or_harmonization` | `tm_assisted` | pass |

The synthetic Android fixture contains 12 source segments and 10 existing
`zh-CN` translations. The benchmark also verifies target-only key protection
and unchanged source hashes. Run it with
`python benchmarks/v021-mode-system/run.py`.

### v0.2.4 release hygiene and CI coverage

v0.2.4 adds no localization features. It validates the unit tests, protocol,
adapter contracts, compilation, and all four public regression runners in CI on
Python 3.11 and 3.12.

### v0.2.3 Android resource reliability

The experimental Android adapter covers:

- `string`, `string-array`, and `plurals`
- placeholders, escaped percent signs, and Android escapes such as `\n`, `\t`,
  `\'`, and `\"`
- inline `<b>`, `<i>`, and `<u>` tags, plus simple `<a href="...">` links
- CDATA boundaries and XML comments before resources
- separate source sets and canonical resource qualifier routing, including
  MCC/MNC ordering
- blind reference isolation and existing-locale maintenance behavior
- target-only obsolete resource preservation and fail-closed routing
- unsupported complex markup preservation with `owner_review_required`
- deterministic review-risk metadata for prioritization, not semantic
  translation quality scoring

See [Android Support in v0.2.3](docs/android-v0.2.3-support.md) for supported
structures, known limitations, and explicit non-goals.

### AntennaPod DeepSeek test

<p align="center">
  <img src="docs/assets/benchmark-antennapod.svg" alt="AntennaPod en-US to Japanese and Korean DeepSeek benchmark: 869 segments, 0 QA issues, builds successful" width="640">
</p>

| Metric | Japanese (`ja`) | Korean (`ko`) |
|--------|-----------------|---------------|
| Source | AntennaPod `develop` branch | same |
| Segments | 869 | 869 |
| Batches | 29 | 29 |
| Model | `deepseek-chat` | `deepseek-chat` |
| Deterministic QA | 0 blocking, 0 warnings | 0 blocking, 0 warnings |
| Build | `:app:assembleFreeDebug` ✓ | `:app:assembleFreeDebug` ✓ |

Full pipeline: extract → batch → DeepSeek API → collect → stage → QA → deliver.

Reproduce a public-safe external-project check with the
[AntennaPod Android smoke-test guide](docs/antennapod-smoke-test.md).

## Concepts

### Operating modes

| Mode | Intended use | Reference policy |
|------|--------------|------------------|
| `greenfield_localization` | Add a new locale | `style_only` |
| `existing_locale_maintenance` | Maintain reviewed translations | `preserve_existing` |
| `rewrite_or_harmonization` | Intentionally rewrite or align style | `tm_assisted` |
| `blind_benchmark` | Evaluate without translation leakage | `blind` |

### Project memory

Localize Anything persists reviewed translation memory, session history, and
project configuration under `.localize-anything/`. In maintenance mode, reviewed
translations with unchanged source hashes survive subsequent runs without
retranslation or churn.

### Review and delivery

```text
Review Agent → scoped sign-off → Delivery Decision → Apply Plan → Apply with backups
```

Human acceptance is segment-scoped. The apply plan lists each create, replace,
unchanged, or conflicting operation before any source file is written.

<p align="center">
  <img src="docs/assets/architecture-layers.svg" alt="Architecture layers: Protocol, Runtime, Agent, Adapters, Source and Delivery" width="640">
</p>

## What it is not

Localize Anything is not:

- a prompt collection
- a generic machine translation wrapper
- a finished enterprise translation management system
- a full HTML parser or automatic localizer for arbitrary nested markup
- a layout, drawable, or asset localizer; Gradle editor; or APK decompiler
- a semantic translation quality scorer
- an APK or IPA repackaging tool
- a replacement for qualified human review
- a tool that silently rewrites a source project
- a claim that LLM output is production-ready without evidence

## Repository layout

```text
protocol/         Portable schemas and lifecycle specification
runtime/          Reference runtime (Python)
adapters/         Adapter manifests and entrypoints
benchmarks/       Public benchmark fixtures and runners
tests/            Runtime unit and integration tests
docs/             Public documentation
```

## License

MIT — see [LICENSE](LICENSE).
