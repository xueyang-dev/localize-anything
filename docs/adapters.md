# Adapter Contract

Adapters implement deterministic localization SOPs without performing translation.

## Lifecycle

```text
detect -> inventory -> extract -> validate-source
       -> rebuild -> validate-output -> plan-apply
```

- `detect`: Return a match score and evidence without modifying files.
- `inventory`: Enumerate source artifacts, locales, and unhandled assets.
- `extract`: Emit protocol-compliant JSONL segments.
- `validate-source`: Report structural defects and ambiguities.
- `rebuild`: Write localized artifacts to staging only.
- `validate-output`: Check parsing, coverage, placeholders, markup, and format rules.
- `plan-apply`: Emit file operations without executing them.

## Implementations

Declarative adapters contain path, extraction, preservation, and QA rules. Scripted adapters expose JSON/JSONL entrypoints and may use any language or runtime declared in `adapter.json`.

Core adapters follow the same contract as third-party adapters. They receive no hidden privileges.

## v0.1 Support Matrix

| Adapter | Formats | Capability | Preserved constraints |
| --- | --- | --- | --- |
| `core.json-locale` | JSON | `full_round_trip` | keys, arrays, types, placeholders |
| `core.gettext-po` | PO/POT | `full_round_trip` | context, comments, flags, plurals, headers, placeholders |
| `core.yaml-toml` | YAML/TOML | `extract_and_rebuild` | keys, comments, scalar style where safe, placeholders |
| `core.tabular` | CSV/TSV/XLSX | `full_round_trip` | table coordinates, keys, formulas/non-text cells, placeholders |
| `core.markup` | Markdown/HTML | `extract_and_rebuild` | code, tags, link destinations, attributes, placeholders |
| `core.subtitles` | SRT/WebVTT | `full_round_trip` | cue identity, timing, inline tags, placeholders |
| `core.xliff` | XLIFF 1.2/2.x | `full_round_trip` | unit IDs, source units, inline tags, placeholders |
| `scenario.wesnoth` | WML + gettext | `extract_only` overlay | campaign, scenario, speaker, occurrence context |

YAML/TOML v0.1 targets localization-resource scalars. Complex YAML block
scalars, anchors, flow collections, and TOML multiline or array strings remain
untouched and therefore are not silently claimed as translated. Install the
`yaml` optional extra for full YAML syntax validation.

CSV/TSV and XLSX default to a locale-table convention: row 1 is a header and
column A is a key column. XLSX formulas, numbers, charts, macros, and workbook
relationships are preserved but not localized. Shared strings used in a
translatable cell are localized at all of their workbook occurrences.

Markdown fenced or indented code and HTML `script`, `style`, `code`, `pre`, and
`svg` content remain untouched. v0.1 does not localize HTML attributes or image
alt text. Markup QA protects link destinations, entities, tags, and placeholders.

Subtitle QA does not perform rendered line-length or reading-speed review; the
agent and human QA channels must record those checks when required.

## Resolution Order

1. User-selected adapter
2. Project-locked custom adapter
3. Core adapter
4. Verified/community adapter
5. Generic fallback

Never switch a locked adapter silently. Record the selected adapter, version, checksum, capabilities, and resolution reason in the delivery manifest.

## Writes and Permissions

Write only to staging until the user approves an apply plan. Declare filesystem, network, and execution permissions. Install dependencies in an isolated adapter environment after explicit approval.

## Project Forks

Fork a core adapter into `.localize-anything/adapters/<custom-id>/` instead of modifying the installed core adapter. Record `forked_from`, upstream version, local version, and checksum.
