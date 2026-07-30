# Deterministic Format Handlers

> **Current implementation reference:** this document describes reusable format
> handling in the v0.4 runtime. In the accepted product direction, these
> handlers are lightweight mechanical tools used by the Agent Skill—not an
> adapter marketplace or the center of the product architecture.

## Role

Format handlers may detect, inventory, extract, compare, validate, rebuild, and
stage localization resources. They do not perform semantic translation, choose
official product terminology, or replace the Coding Agent's understanding of
the project's i18n framework.

Preferred order:

1. use the project's native i18n tooling and conventions;
2. reuse an existing handler when its documented boundary matches;
3. let the Coding Agent make scoped edits and record missing mechanical checks
   when no handler fits safely.

## Mechanical Lifecycle

```text
detect -> inventory -> extract -> validate-source
       -> rebuild -> validate-output -> summarize-diff
```

Current compatibility commands may still emit protocol artifacts and apply
plans. Target v1 keeps only the parts needed for `scan`, `check`, `review`, and
`report` workflows.

## Current Handlers

| Handler | Formats | Current capability | Preserved constraints |
| --- | --- | --- | --- |
| `core.json-locale` | JSON | round trip | keys, arrays, types, placeholders |
| `core.gettext-po` | PO/POT | round trip | context, comments, flags, plurals, headers, placeholders |
| `core.yaml-toml` | YAML/TOML | extract/rebuild | keys, comments and scalar style where safe |
| `core.tabular` | CSV/TSV/XLSX | round trip | coordinates, key columns, formulas/non-text cells |
| `core.markup` | Markdown/HTML | extract/rebuild | code, tags, link destinations, attributes |
| `core.word-document` | DOCX/DOTX/DOCM/DOTM | extract/rebuild | OpenXML parts, relationships, styles, macros |
| `core.subtitles` | SRT/WebVTT | round trip | cue identity, timing, inline tags |
| `core.xliff` | XLIFF 1.2/2.x | round trip | unit IDs, source units, inline tags |
| `core.android-strings` | Android XML | extract/rebuild | resource names, arrays, plurals, placeholders, target paths |
| `core.ios-strings` | `.strings` / `.stringsdict` | extract/rebuild | keys, comments/order, plurals, placeholders |
| `core.xcstrings` | `.xcstrings` | extract/rebuild | source language, variation leaves, metadata |
| `scenario.wesnoth` | WML + gettext | context overlay | campaign, scenario, speaker and occurrence context |

This table describes code that exists; it is not a universal support claim.

## Important Boundaries

### YAML And TOML

Current support targets localization-resource scalars. Complex YAML block
scalars, anchors, flow collections, and TOML multiline or array strings remain
untouched unless the Coding Agent handles them directly. Install the `yaml`
optional extra for full YAML syntax validation.

### Tabular Files

CSV/TSV and XLSX default to a locale-table convention with row 1 as the header
and column A as the key. XLSX formulas, numbers, charts, macros, and workbook
relationships are preserved but not localized.

### Markdown And HTML

Fenced/indented code and HTML `script`, `style`, `code`, `pre`, and `svg`
content remain untouched. Current support does not localize arbitrary HTML
attributes or image text.

### Word OpenXML

The handler supports safely editable visible text in `.docx`, `.dotx`, `.docm`,
and `.dotm`. It preserves non-text package parts and VBA macro bytes without
executing macros. Legacy `.doc`, encrypted/malformed packages, embedded-object
content, image text, and rendered-layout fidelity require separate handling or
review.

### Android

Current code handles `string`, `string-array`, and `plurals` in Android
resources within documented markup limits. It does not imply complete Android
app localization: layouts, drawables, assets, runtime/server copy, hardcoded
Compose strings, build-system changes, APK repackaging, and locale behavior may
still require Coding Agent work.

### Apple Resources

Current `.strings`, `.stringsdict`, and `.xcstrings` support does not edit Xcode
project files, application code, storyboards, assets, build settings, or all
locale variations. The Coding Agent owns those project-level changes.

### Subtitles

Mechanical QA preserves cues, timestamps, tags, and placeholders. Reading
speed, line breaks, cultural context, and rendered results belong in Agent or
human review.

## v1 Priority

The first simplified CLI tier prioritizes:

- JSON and YAML;
- Android XML;
- Apple `.strings` and `.xcstrings`;
- PO/POT;
- XLIFF.

Other current handlers may remain available. Adding more formats is secondary
to better scope discovery, Project Memory, independent review, and lower human
review cost.

## Safety And Degradation

- Never silently damage keys, placeholders, markup, encoding, paths, or target-
  only content.
- Preserve unsupported syntax or surface it for review.
- Do not download or execute third-party handler code without explicit user
  authorization.
- When deterministic handling is unavailable, let the Coding Agent use project
  tooling and state which checks could not be performed.
- Do not claim structural or coverage verification that did not run.
