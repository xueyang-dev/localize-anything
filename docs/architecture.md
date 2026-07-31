# Architecture

Localize Anything is an Agent-native localization workflow and review layer.
The active implementation has one public CLI and no platform fallback.

The canonical product boundary is [Product Direction](product-direction.md).
The removed v0.4 platform remains documented only in the
[legacy snapshot](architecture-v0.4-legacy.md) and Git history.

## Active Flow

```text
Localize Anything Skill
    |
    +--> localize scan --------------------> Project Memory
    +--> localize glossary bootstrap ------> canonical Glossary
    |
    +--> Coding Agent edits the project
    |       +--> project-native build/test
    |       +--> screenshots and Git diff
    |
    +--> localize check -------------------> deterministic findings
    +--> localize review ------------------> independent review packet
    |       +--> fresh Agent context
    |       +--> normalized review findings
    +--> human confirmation ---------------> open findings only
    +--> localize report ------------------> concise completion state
```

## Runtime Boundary

`core_cli.py` exposes exactly five command groups. `core.py` coordinates their
small data flow and delegates reusable work to focused modules:

| Module | Responsibility |
| --- | --- |
| `core_preflight.py` | project boundary checks, resource detection and discovery |
| `core_glossary.py` | candidate concepts, normalization and locked-term checks |
| `core_memory.py` | confirmed legacy terminology, TM, style and decision import |
| `core_segments.py` | review identity/alignment and deterministic diff/staleness |
| `core_formats.py` | supported-format extraction and pair-validation boundary |
| `io_utils.py` | atomic local writes and small serialization helpers |

The core does not import Provider, Workbench, workflow, readiness, signoff,
Knowledge Pack, generation, delivery, retrieval, repair, or artifact-state
modules. Those product surfaces and their CLI/protocol chains have been
removed.

## State

The target project owns the state under `.localize-anything/`:

```text
project-memory.json
glossary.json
deterministic-check.json
review-packet.json
independent-review.json
human-confirmations.json
report.json
report.md
```

Project Memory holds source/target locale, declared resources, product context,
style, preserve rules, confirmed decisions, and reviewed Translation Memory.
The canonical Glossary is the only user-facing terminology truth.

Git remains the state-management and collaboration layer. Localize Anything
does not create a parallel branch, lock, approval, recovery, delivery, or
release system.

## Format Boundary

The five-command core directly supports:

- JSON;
- YAML/TOML;
- Android string resources;
- Apple `.strings` / `.stringsdict`;
- Apple `.xcstrings`;
- PO/POT;
- XLIFF 1.2/2.x.

Focused Markdown/HTML, tabular, Word OpenXML, subtitle, and Wesnoth handlers
remain as tested Python compatibility code. They have no standalone legacy CLI
entrypoint and are never selected as an automatic platform fallback.

The Coding Agent handles missing formats with project-native code and tools,
then records the deterministic coverage limitation.

## Review Boundary

Quality evidence stays separated:

1. deterministic checks cover structure, keys, placeholders, markup, escapes,
   paths, and locked terminology;
2. an independent Agent context reviews meaning, naturalness, tone, page
   context, and product concepts;
3. the user decides only open, high-risk product findings.

A confirmation cannot be recorded for a finding that is not open with
`needs_human_confirmation`.

## Responsibility Boundary

| Owner | Responsibility |
| --- | --- |
| Skill | scope, workflow, memory use, independent review and final explanation |
| `localize` core | deterministic state and trust-boundary validation |
| Coding Agent | i18n engineering, resources, locale behavior, build/test, screenshots and Git |
| User | official terminology, brands, product meaning, high-risk ambiguity and release judgment |

`report: ready` means the five-command evidence for the declared scope is
complete. It does not certify translation quality or replace project-native
build/test, screenshots, Git review, or human release approval.

## Dependency Rule

New core modules may depend only on focused core modules, format handlers,
`io_utils.py`, and the Python standard library. Compatibility handlers must not
import removed platform concepts. No future capability should reintroduce an
orchestrator, registry, state machine, readiness matrix, compatibility wrapper,
or broad protocol inventory without a new accepted product decision.
