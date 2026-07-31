# Localize Anything

<p align="center">
  <img src="docs/assets/logo-localize-anything-transparent.png" alt="Localize Anything logo" width="220" />
</p>

<p align="center">
  <strong>The localization expertise layer for Coding Agents.</strong>
</p>

<p align="center">
  English · <a href="README.md">简体中文</a>
</p>

Localize Anything gives Coding Agents a clear, reviewable workflow for real
application repositories:

```text
scan
→ glossary bootstrap
→ Coding Agent localization
→ project-native build/test
→ check
→ independent review
→ human confirmation
→ report
```

It does not replace the Coding Agent, project build system, Git, or human
product judgment. It owns scope, Project Memory, the Glossary, deterministic
checks, independent review, and a small set of high-risk confirmations.

## Current Implementation

The repository has one public CLI: `localize`. Its default path contains only
five commands:

```bash
localize scan
localize glossary bootstrap
localize check
localize review
localize report
```

The old `localize-anything` platform CLI, Provider, Workbench, readiness,
workflow, signoff, Knowledge Pack, generation/delivery orchestration, and their
protocols have been removed. A missing format handler is handled with
project-native Coding Agent work; it never triggers an automatic fallback to
the old platform.

The core currently provides:

- Git-shareable Project Memory;
- one product-concept-centered `glossary.json`;
- conservative import of confirmed legacy terms, TM, style, and decisions;
- scan and structural checks for JSON, YAML/TOML, Android XML, Apple `.strings`
  and `.xcstrings`, PO/POT, and XLIFF;
- placeholder, key, markup, Android escape/CDATA, and locked-Glossary checks;
- a self-contained review packet for a fresh Agent context;
- a finding-linked human confirmation gate;
- concise JSON and Markdown reports.

Markdown/HTML, CSV/TSV/XLSX, Word OpenXML, subtitle, and Wesnoth handlers remain
as limited Python compatibility capabilities. They are not a default CLI
fallback.

## Install

Python 3.11+ is required:

```bash
git clone https://github.com/xueyang-dev/localize-anything.git
cd localize-anything
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[yaml]"
```

## Use

Scan a project. Without declared source files, `scan` only inventories
recognized resources:

```bash
localize scan /path/to/project
```

Declare a localization task:

```bash
localize scan /path/to/project \
  --source-locale en \
  --target-locale ru \
  --source locales/en.json
```

Bootstrap the canonical Glossary:

```bash
localize glossary bootstrap /path/to/project
```

The Coding Agent then edits application code and target-locale resources and
runs the project's own verification, for example:

```bash
npm test
npm run build
git diff
```

Localize Anything does not wrap or replace those commands. After the
engineering changes:

```bash
localize check /path/to/project \
  --target locales/ru.json

localize review /path/to/project \
  --target locales/ru.json
```

Give `.localize-anything/review-packet.json` to a fresh Agent context that did
not generate the translation. The review result has this shape:

```json
{
  "reviewer": "independent-agent",
  "findings": [
    {
      "id": "navigation.share",
      "severity": "high",
      "status": "needs_human_confirmation",
      "note": "The product action needs an official wording decision."
    }
  ]
}
```

Import the review and build the report:

```bash
localize review /path/to/project \
  --target locales/ru.json \
  --findings review.json

localize report /path/to/project
```

Only an open `needs_human_confirmation` finding can receive a human decision:

```bash
localize report /path/to/project --confirm confirmations.json
```

Example confirmation file:

```json
{
  "confirmations": [
    {
      "finding_id": "navigation.share",
      "decision": "Use “Поделиться”",
      "note": "Confirmed by the product owner."
    }
  ]
}
```

All core state lives under `.localize-anything/` in the target project.

## Responsibility Boundary

| Role | Responsibility |
| --- | --- |
| Localize Anything Skill | Scope, Glossary, Project Memory, workflow, independent review, risk summary |
| `localize` CLI | Scan, structural checks, review packet, finding/confirmation constraint, report |
| Coding Agent | i18n architecture, code/resources, locale behavior, fallback, build/test, screenshots, Git |
| User | Product meaning, brands, official terminology, high-risk ambiguity, release judgment |

Deterministic checks do not prove natural or semantically correct translation,
and independent Agent review is not human release approval. `ready` means only
that core checks, review, and confirmations for the declared scope are
complete. It does not replace project-native build/test, screenshots, or Git
review.

## Development Validation

```bash
python -m unittest discover -s tests -p 'test_*.py'
python -m compileall -q runtime tests
```

Protocol and adapter manifests use dependency-free repository validators:

```python
from pathlib import Path
from runtime.localize_anything.contracts import validate_adapter_tree
from runtime.localize_anything.schema_validation import validate_protocol_tree

assert validate_protocol_tree(Path("protocol"))["status"] == "pass"
assert validate_adapter_tree(Path("adapters"))["status"] == "pass"
```

## Documentation

- [Product Direction](docs/product-direction.md)
- [Current Architecture](docs/architecture.md)
- [Architecture Roadmap](docs/architecture-roadmap.md)
- [Format Handler Boundaries](docs/adapters.md)
- [Core Data Contracts](protocol/SPEC.md)
- [Agent Skill](skills/localize-anything/SKILL.md)
- [Phase 2 Real-Project Validation](docs/validation/phase2-live-dry-run.md)

The v0.4 platform design remains only in the
[Legacy Architecture Snapshot](docs/architecture-v0.4-legacy.md) and Git
history.

## Non-Goals

Localize Anything is not:

- a translation model or Provider platform;
- an enterprise TMS;
- a general multi-Agent orchestration framework;
- a Workbench or release-governance system;
- a replacement for Git, CI, or project build tools;
- automated certification of “zero source-language characters” or
  professional translation quality.

## License

MIT
