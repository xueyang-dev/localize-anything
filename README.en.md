# Localize Anything

<p align="center">
  <img src="docs/assets/logo-localize-anything-transparent.png" alt="Localize Anything logo" width="220" />
</p>

<p align="center">
  Agent-native localization delivery for real source projects.
</p>

<p align="center">
  LLMs can translate strings. Localize Anything turns translations into staged, validated, reviewable deliverables.
</p>

<p align="center">
  English · <a href="README.md">简体中文</a>
</p>

<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue" />
  <img alt="CI" src="https://github.com/xueyang-dev/localize-anything/actions/workflows/ci.yml/badge.svg" />
  <img alt="Release: v0.4.1" src="https://img.shields.io/badge/release-v0.4.1-blue" />
  <img alt="QA: deterministic" src="https://img.shields.io/badge/QA-deterministic-green" />
  <img alt="Apply: staged first" src="https://img.shields.io/badge/apply-staged%20first-blueviolet" />
</p>

---

Localize Anything is built for developers and localization teams working with real source projects. It is not a translation script, and it does not write model output directly back into your repository. It provides a traceable, reviewable, and reproducible delivery workflow: extract translatable content, generate target-locale drafts, validate structure with deterministic checks, stage output, and write changes only after the apply plan is reviewed and the run ID is explicitly confirmed.

## Use this when

Use Localize Anything when you need to:

- localize real source projects, not isolated strings;
- protect placeholders, XML/HTML markup, resource keys, escapes, and file structure;
- generate reviewable target-locale files for Word documents, Android, iOS, or common text resources;
- inspect staged files, QA evidence, delivery decisions, and apply plans before writing changes;
- preserve reviewed translations during existing-locale maintenance instead of re-translating unchanged content;
- use different reference-translation policies for blind benchmarks, greenfield localization, maintenance, and rewrite workflows.

## Status

**Current release:** [v0.4.1 — Workbench UI Wiring](https://github.com/xueyang-dev/localize-anything/releases/tag/v0.4.1)

v0.4.1 refines the Workbench WebUI: it removes copied macOS window controls, connects localization mode selection to the agent `operating_mode` and `reference_policy`, adds a `/api/sessions`-backed sessions panel, and shows inline validation before backend calls when the project path, target locale, or responses directory is missing.

The v0.4.0 Word OpenXML localization and explicit opt-in Android merged dependency resource overlay remain the current feature baseline. Legacy binary `.doc` files, image text, embedded objects, and provider-backed translation quality remain outside the deterministic coverage claim.

Verified engineering evidence includes:

- v0.4.1 Workbench UI state, mode forwarding, sessions endpoint, and inline validation: pass;
- v0.4.0 Word adapter extract/rebuild/validate coverage: pass;
- Word `.docm` macro-byte preservation: pass;
- Workbench file/folder import API and UI smoke tests: pass;
- opt-in Android merged dependency resource overlay tests: pass;
- v0.3.2 Android coverage diagnostics: pass;
- v0.3.1 release audit: pass;
- runtime code verified against checked private local path patterns;
- unit tests, protocol validation, adapter contract validation, compile checks, and public regression runners: pass;
- disposable AntennaPod read-only inspect and smoke helper: pass with no tracked source mutation;
- Android real-project stress matrix: inspect/synthetic evidence recorded for AntennaPod, NewPipe, Tusky, and Fossify File Manager;
- v0.2.3 Android resource reliability regressions: pass;
- v0.2.1 mode-system benchmark: pass;
- AntennaPod DeepSeek test: 869 segments in each of two target locales, 0 deterministic QA blockers or warnings, and successful builds for both locales.

These results demonstrate pipeline behavior, structural preservation, and delivery evidence. They are not a claim of native-level translation quality, and they do not mean generated translations should ship without review. See the [changelog](CHANGELOG.md), [Adapter Contract](docs/adapters.md), [Android coverage model](docs/android-coverage-model.md), [v0.3.1 release audit](docs/v0.3.1-release-audit.md), and [real-project stress matrix](docs/android-real-project-stress-matrix.md) for details.

## Why this exists

An LLM can produce plausible strings. Real software localization delivery also needs to solve engineering problems:

- placeholders, markup, escapes, and resource keys must not be damaged;
- reviewed translations should not be rewritten without reason;
- existing translations need different visibility rules in benchmark and maintenance modes;
- every run should leave inspectable manifests, QA results, review state, and apply plans;
- tools must not overwrite, delete, or pollute the source project without explicit confirmation.

Localize Anything provides the engineering layer between a source repository, an agent or human translator, and the final deliverable. The runtime handles structure, staging, conflict detection, packaging, and apply plans. Agents and model providers handle semantic generation. Human review remains the final acceptance step.

## Workflow

**Extract → Generate → QA → Stage → Review → Apply**

1. Extract translatable content from supported real-project formats.
2. Decide what to generate and what to preserve based on operating mode.
3. Generate target-locale drafts through a host agent, provider, or human workflow.
4. Validate placeholders, markup, escapes, keys, and file structure in code.
5. Stage output outside the source project for review.
6. Package manifests, QA evidence, review state, delivery decisions, and an apply plan.
7. Apply changes only after explicit run-id confirmation, with backups before replacement.

![Localize Anything workflow: 9 steps from Project Agent to Apply with Backups](docs/assets/workflow-dark.svg)

## Core guarantees

| Guarantee | Enforcement |
| --- | --- |
| Staging first | Generated files are written to an isolated staging directory, not the source project. |
| Deterministic QA | Placeholder parity, markup integrity, escapes, keys, and format rules are checked in code. |
| No silent overwrite | Conflicts block apply until they are resolved. |
| Confirmed apply | Apply requires a matching `--confirm-run-id`; replaced files are backed up. |
| Source mutation detection | SHA-256 checks detect unexpected changes during a run. |
| Maintenance preservation | Reviewed unchanged translations and Android target-only resources are preserved in verified maintenance workflows. |
| Reference isolation | Blind benchmarks keep existing translations out of generation-facing artifacts. |
| Reviewable delivery | Manifests, QA results, sign-off scope, and file operations remain inspectable. |

See [Security](docs/security.md) for the complete safety architecture.

## Quick start

### Install from source

Python 3.11+ is required.

```bash
git clone https://github.com/xueyang-dev/localize-anything.git
cd localize-anything
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[yaml]"
python -m unittest discover -s tests -v
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

### Run regression benchmarks

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

Create a staged Japanese greenfield delivery from an Android source file using synthetic drafts. This does not call an external model and does not write into the project.

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

The run produces staged files, a QA report, a delivery decision, and an apply plan. Writing into the source project is a separate step: review the dry-run plan first, then explicitly confirm the matching run ID.

## Current support

### Implemented core adapters

| Format | Current capability |
| --- | --- |
| JSON locale files | Extraction, rebuild, and structural preservation |
| YAML / TOML | Localization-resource scalar extraction and rebuild |
| CSV / TSV / XLSX | Table coordinates, key columns, and non-text cell protection |
| Markdown / HTML | Visible text extraction/rebuild; code, attributes, and `script`/`style`/`svg` content remain untouched |
| Word OpenXML documents | `.docx`, `.dotx`, `.docm`, and `.dotm` visible text extraction/rebuild with target-locale font normalization and deterministic package QA |
| SRT / WebVTT | Cue identity, timing, and inline tag preservation |
| XLIFF 1.2 / 2.x | Unit IDs, source text, and inline XML preservation |
| GNU gettext PO/POT | Context, comments, plurals, headers, and placeholder preservation |

### Experimental platform adapters

| Platform resource | Current boundary |
| --- | --- |
| Android `strings.xml` | Supports `string`, `string-array`, and `plurals`, with staging, deterministic QA, and explicit opt-in merged dependency resource overlays |
| iOS `.strings` / `.stringsdict` | Supports basic resource extraction, rebuild, and target `.lproj` staging |
| Xcode `.xcstrings` | Supports source-language units and variation leaves written as target-language entries |

See the [Adapter Contract](docs/adapters.md) for adapter IDs, preservation rules, and the full format boundary.

## Evidence

### v0.4.0 Word document localization

v0.4.0 adds a stdlib-only Word OpenXML adapter and CLI path for `.docx`, `.dotx`, `.docm`, and `.dotm` files. It localizes visible editable XML text, normalizes target-locale fonts on localized runs, preserves non-text package content, and verifies macro bytes without executing macros. The Workbench can import selected files, folders, or dropped files into a temporary project before running the normal staged delivery workflow.

Legacy `.doc`, encrypted or malformed packages, image text, and embedded object content are not silently claimed as localized.

### v0.3.1 release audit

v0.3.1 removes a hardcoded private DeepSeek provider env-file path and requires provider credentials through explicit environment configuration. The release audit passed unit tests, protocol validation, adapter contract validation, compile checks, and public regression runners. It also verified that runtime code contains no checked private local path patterns.

See [v0.3.1 Release Audit](docs/v0.3.1-release-audit.md).

### v0.3.0 real-project workflow hardening

v0.3.0 adds read-only inspect summaries and refreshed disposable-clone AntennaPod smoke evidence. The workflow evidence focuses on source mutation safety, inspect-summary artifacts, scoped synthetic drafts, and reviewable delivery artifacts. It does not claim provider-backed translation quality, destructive apply safety, or full production localization of external projects.

See [AntennaPod v0.3.0 smoke results](docs/antennapod-smoke-test-results-v0.3.0.md) and the [Android real-project stress matrix](docs/android-real-project-stress-matrix.md).

### v0.2.3 Android resource reliability

The experimental Android adapter currently covers:

- `string`, `string-array`, and `plurals`;
- placeholders, escaped percent signs, and Android escapes such as `\n`, `\t`, `\'`, and `\"`;
- inline `<b>`, `<i>`, and `<u>` tags, plus simple `<a href="...">` links;
- CDATA boundaries and XML comments before resources;
- separate source sets and canonical resource qualifier routing, including MCC/MNC ordering;
- blind reference isolation and existing-locale maintenance behavior;
- target-only obsolete resource preservation and fail-closed routing;
- unsupported complex markup preservation with `owner_review_required`;
- deterministic review-risk metadata for prioritization, not semantic translation quality scoring.

See [Android Support in v0.2.3](docs/android-v0.2.3-support.md) for supported structures, known limitations, and explicit non-goals.

### v0.2.1 mode-system benchmark

| Mode | Reference policy | Result |
| --- | --- | --- |
| `blind_benchmark` | `blind` | pass: no leakage to generation artifacts |
| `greenfield_localization` | `style_only` | pass |
| `existing_locale_maintenance` | `preserve_existing` | pass: 10 preserved, 2 generated |
| `rewrite_or_harmonization` | `tm_assisted` | pass |

The synthetic Android fixture contains 12 source segments and 10 existing `zh-CN` translations. The benchmark also verifies target-only key protection and unchanged source hashes.

```bash
python benchmarks/v021-mode-system/run.py
```

### AntennaPod DeepSeek test

![AntennaPod en-US to Japanese and Korean DeepSeek benchmark: 869 segments, 0 QA issues, builds successful](docs/assets/benchmark-antennapod.svg)

| Metric | Japanese (`ja`) | Korean (`ko`) |
| --- | --- | --- |
| Source | AntennaPod `develop` branch | same |
| Segments | 869 | 869 |
| Batches | 29 | 29 |
| Model | `deepseek-chat` | `deepseek-chat` |
| Deterministic QA | 0 blockers, 0 warnings | 0 blockers, 0 warnings |
| Build | `:app:assembleFreeDebug` ✓ | `:app:assembleFreeDebug` ✓ |

Full pipeline: extract → batch → DeepSeek API → collect → stage → QA → deliver. Reproduce a public-safe external-project check with the [AntennaPod Android smoke-test guide](docs/antennapod-smoke-test.md).

## Concepts

### Operating modes

| Mode | Intended use | Default reference policy |
| --- | --- | --- |
| `greenfield_localization` | Add a new locale | `style_only` |
| `existing_locale_maintenance` | Maintain reviewed translations | `preserve_existing` |
| `rewrite_or_harmonization` | Intentionally rewrite or align style | `tm_assisted` |
| `blind_benchmark` | Evaluate without reference-translation leakage | `blind` |

### Project memory

Localize Anything persists reviewed translation memory, session history, and project configuration under `.localize-anything/`. In maintenance mode, reviewed translations with unchanged source hashes survive subsequent runs without retranslation or churn.

### Review and delivery

```text
Review Agent → scoped sign-off → Delivery Decision → Apply Plan → Apply with backups
```

Human acceptance is segment-scoped. The apply plan lists every create, replace, unchanged, or conflicting file operation before any source file is written.

![Architecture layers: Protocol, Runtime, Agent, Adapters, Source and Delivery](docs/assets/architecture-layers.svg)

## What it is not

Localize Anything is not:

- a prompt collection;
- a generic machine translation wrapper;
- a finished enterprise translation management system;
- a full HTML parser or automatic localizer for arbitrary nested markup;
- an Android layout, drawable, or asset localizer;
- a Gradle editor or APK decompiler;
- a semantic translation quality scorer;
- an APK or IPA repackaging tool;
- a replacement for qualified human review;
- a tool that silently rewrites a source project;
- a claim that LLM output is production-ready without evidence.

## Project maturity

Localize Anything is best understood today as a developer tool and localization-engineering framework. It already provides reproducible structure validation, staged delivery, and safe apply workflows, while platform adapters are still expanding and semantic translation quality still requires human review or higher-level evaluation evidence.

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
