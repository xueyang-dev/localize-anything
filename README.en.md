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

You've already handed your coding to an Agent. Now ask it to add Russian support to your project — it can translate, but then what? Are terms consistent across the app? Did it get the key concepts right? How do you review a few hundred translated strings without reading all of them? An Agent alone has no answer to these.

**Localize Anything gives it a professional localization workflow:** scan the scope, build a project glossary, systematically review every translation, and shrink what needs your personal sign-off down to a handful of high-risk decisions. It is not a translation tool, and it is not another CI platform — it is an expertise layer embedded in the Agent workflow. Project memory carries across sessions, and review changes from "read everything" to "decide the few things only you can."

## Workflow

```text
localize scan
→ localize glossary bootstrap
→ Coding Agent localization (project-native build/test)
→ localize check
→ localize review
→ human confirmation
→ localize report
```

Localize Anything does not replace the Coding Agent, the project build system, Git, or human product judgment. It owns scope, Project Memory, the Glossary, deterministic checks, independent review, and a small set of high-risk confirmations.

## Quick start

Requires Python 3.11+:

```bash
git clone https://github.com/xueyang-dev/localize-anything.git
cd localize-anything
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[yaml]"
```

Declare a localization task for the target project and establish Project Memory:

For a project with no i18n yet, the Coding Agent must first add the smallest
project-native i18n setup and create the source-locale resource file. Do not
run `localize scan` until every declared `--source` file exists; `scan` records
existing source resources, it does not create them.

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

The Coding Agent then edits application code and target-locale resources, and runs the project's own verification (`npm test`, `npm run build`, `git diff`, etc.). Once the engineering work is done:

```bash
localize check /path/to/project --target locales/ru.json
localize review /path/to/project --target locales/ru.json
```

When multiple sources are declared, pass one `--target` per source in the same
order. `check` and `review` output `source_target_mapping` and reject count
mismatches, obvious source-locale targets, adapter mismatches, and clear path
shape contradictions.

Hand `.localize-anything/review-packet.json` to a fresh Agent context that did not generate the translation, import its findings, and build the report:

```bash
localize review /path/to/project --target locales/ru.json --findings review.json
localize report /path/to/project
```

Use these severities everywhere in check, review, report, and Skill notes:
`blocking`, `actionable`, `coverage_limitation`, and `informational`.
Auto-cleared checks belong in `review_items`; only real issues belong in
`findings`.

Minimal `review.json`:

```json
{
  "reviewer": "fresh-review-context",
  "review_items": [
    {
      "id": "checked-placeholders",
      "severity": "informational",
      "status": "auto_cleared",
      "note": "Placeholders were checked and no issue was found."
    }
  ],
  "findings": [
    {
      "id": "brand-name",
      "severity": "actionable",
      "status": "needs_human_confirmation",
      "note": "Confirm whether the product name remains untranslated."
    }
  ]
}
```

Only an open finding with status `needs_human_confirmation` can receive a human decision:

```bash
localize report /path/to/project --confirm confirmations.json
```

All core state lives in the target project's `.localize-anything/` directory and can be committed and shared with Git.

## Review Packet Fields

`.localize-anything/review-packet.json` is self-contained for an independent
review context:

- `instruction`: reviewer task and independence rules.
- `project_memory`: declared locales, source files, style, preserve rules,
  translation memory, and confirmed decisions.
- `glossary`: canonical concepts; lock a translation with
  `status: "locked"` and `target.preferred`, or preserve a term with
  `behavior: "preserve"` plus `status: "locked"`.
- `deterministic_check`: latest structural check result, or `null`.
- `source_target_mapping`: explicit source-to-target file mapping in scan
  order.
- `files`: aligned source and target segments to review.
- `review_result_format`: JSON shape the fresh reviewer should return.

## Using it with your Coding Agent

The entry point is the Agent Skill; the CLI is its deterministic tool.

- **Codex:** expose the repository's `skills/localize-anything/` directory as an available Skill (or copy it into your Codex skills directory), then ask:
  > Use Localize Anything to add Russian support to this project.
- **Claude Code:** place the same directory under the project's `.claude/skills/localize-anything/` (keeping `SKILL.md` and `references/`), then use the same natural-language request.

The Skill only guides the workflow. Code edits, resource changes, build/test, and Git operations remain the Coding Agent's job using the project's native commands.

## Two levels of depth

| Level | When to use | What it includes |
| --- | --- | --- |
| **Standard** | Routine locale additions, copy updates | Scope, Glossary, Agent implementation, deterministic checks, independent review, high-risk confirmations |
| **Release** | Formal releases | Everything in Standard + page screenshots, page-level review, project-native build/test, locale switch/persistence/detection/fallback verification, a clean Git diff, release evidence |

## Responsibility boundary

| Role | Responsibility |
| --- | --- |
| Localize Anything Skill | Scope, Glossary, Project Memory, workflow, independent review, risk summary |
| `localize` CLI | Scan, structural checks, review packet, finding/confirmation constraint, report |
| Coding Agent | i18n architecture, code and resource changes, locale switching, fallback, build/test, screenshots, Git |
| User | Product meaning, brands, official terminology, high-risk ambiguity, release judgment |

Deterministic checks do not prove that translations are natural or semantically correct, and an independent Agent review is not human release approval. `ready` means only that the core checks, review, and confirmations for the declared scope are complete — it does not replace project-native build/test, screenshots, or Git review.

## Development validation

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

- [Product Direction](docs/product-direction.md) — the positioning and scope baseline every document follows
- [Current Architecture](docs/architecture.md)
- [Architecture Roadmap](docs/architecture-roadmap.md)
- [Format Handler Boundaries](docs/adapters.md) — full detail on core formats and restricted compatibility directions
- [Core Data Contracts](protocol/SPEC.md)
- [Agent Skill](skills/localize-anything/SKILL.md)
- [Migration Guide](docs/migration/agent-native-core-migration.md) — moving from the legacy platform to the five-command core
- [0.5.1 Release Notes](docs/releases/0.5.1-release-notes.md)

The v0.4 platform design survives only in the [Legacy Architecture Snapshot](docs/architecture-v0.4-legacy.md) and Git history.

## Non-goals

Localize Anything is not:

- a translation model or Provider platform;
- an enterprise TMS;
- a general multi-Agent orchestration framework;
- a Workbench or release-governance system;
- a replacement for Git, CI, or project build tools;
- automated certification of "zero source-language characters" or professional translation quality.

## License

MIT
