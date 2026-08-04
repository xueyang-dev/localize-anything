# Deterministic Format Handlers

> These handlers are lightweight mechanical tools used by the five-command
> core or retained as focused Python compatibility code. They are not an
> adapter marketplace or independent CLI surface.

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

## Role Separation

- Format handlers process a resource syntax, such as JSON, PO, XLIFF,
  `.xcstrings`, or Android `strings.xml`.
- Platform overlays describe project or platform conventions around resources,
  such as Android qualifier routing or Apple locale bundles. They do not make a
  whole app localized.
- Scenario adapters add domain context for a specific project family, such as
  Wesnoth campaign/speaker context. They do not become generic format support
  unless that boundary is separately proven.

Adapter selection is surface-aware. A handler target is a localization surface
and its detected structure, not merely a filename extension or programming
language.

Preferred resolution:

```text
project
-> surface discovery
-> surface classification
-> adapter candidate detection
-> user/project lock
-> core handler
-> verified/community handler
-> generic fallback
-> inspect-only / enablement / unsupported report
```

The current implementation has core handlers and bounded compatibility
handlers, not a marketplace. `verified/community` remains a future trust tier
only if a later accepted decision reintroduces it.

## Mechanical Lifecycle

```text
detect -> inventory -> extract -> validate-source
       -> rebuild -> validate-output -> summarize-diff
```

The old adapter CLI commands and apply-plan surface have been removed. Core
handlers are called internally by `scan`, `check`, and `review`; compatibility
handlers are imported directly only when explicitly needed.

For source-code mutation, the lifecycle is stricter:

```text
detect -> inventory -> extract -> validate-source
       -> rebuild to staging -> syntax-aware patch/diff
       -> syntax/build validation -> apply plan -> user confirmation
       -> backup/rollback evidence
```

Build pass does not imply launch pass, and launch pass does not imply visible UI
coverage pass.

## Capability Vocabulary

Adapter manifests currently expose capability names and a `round_trip_level`:
`full_round_trip`, `extract_and_rebuild`, `extract_only`, `inspect_only`, or
`unsupported`. Documentation and future reports must add surface dimensions
when they matter: surface detection, content extraction, staged rebuild,
project enablement, source-code mutation, syntax validation, build
verification, launch verification, runtime-surface verification, and visual
verification.

Do not use claims such as "Swift supported" or "JSON supported" as complete
project-localization capability statements.

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

### Source-Code Catalogs And Inline Strings

Source-code content has three classes:

- structured code-embedded catalogs may be supported by an explicit,
  syntax-aware adapter for that structure;
- unstructured inline user-facing strings default to inventory, candidate
  classification, user-visible likelihood assessment, and enablement planning;
- internal strings such as logs, paths, commands, API keys, identifiers,
  notification names, SQL, regexes, internal errors, and test fixtures are not
  automatic localization objects.

Do not choose a source-code adapter only because a file ends in `.swift`,
`.kt`, `.ts`, `.py`, or another programming-language extension. The detector
must record structural evidence, adapter version, capability, resolution
reason, and any required tools. Scripted adapters must declare runtime,
dependencies, permissions, and any source write capability. Project-local
adapters do not receive hidden permissions.

### Vorssaint Swift Catalog Slice

Vorssaint is a planned experimental `code_embedded_catalog` vertical slice, not
generic Swift support. The adapter target is a typed Swift catalog structure,
currently expected to include:

- `AppLanguage` enum and language display-name mapping;
- system-locale matching and language selection switch;
- `Strings` type definition;
- `Strings+<Locale>.swift` implementations;
- feature-specific `Strings` extensions;
- `Info.plist` `CFBundleLocalizations`;
- Swift package or project build validation.

The runtime-validated slice is extract-only with report-only review: detect,
inventory, extract, and validate-source, with no source mutation. It must find
supported languages, fields, locale implementations, feature-specific files,
`Info.plist` language declarations, per-locale field coverage,
missing/duplicate/extra fields, stable segment IDs, source files, type names,
parameter labels, and context without modifying source. Inspect-only scope and
generic Swift support remain planned.

A project-local adapter belongs under a path such as:

```text
.localize-anything/adapters/vorssaint.swift-catalog/
```

Do not promote this to `core.swift` or `format.swift-static-catalog` until the
same structural model is verified across multiple independent Swift projects.

### Project-local Extract-only Adapters

Project-local adapters are discovered only from:

```text
.localize-anything/adapters/<adapter-id>/adapter.json
```

Discovery is read-only. A candidate is listed in `source-surface-inventory.json`
and `capability-report.json`, but its script is not executed until selected
explicitly with:

```bash
localize scan PROJECT --source-locale SOURCE --target-locale TARGET \
  --source PATH --adapter ADAPTER_ID
```

The descriptor uses the existing adapter manifest vocabulary plus
project-local fields:

- `id`, `name`, `version`, `protocol_version`, `implementation_status`;
- `adapter_type: "scripted"`;
- `trust: "project"`;
- `round_trip_level: "inspect_only"` or `"extract_only"`;
- `capabilities`, limited to `detect`, `inventory`, `extract`, and
  `validate_source`;
- `permissions`, limited to `read_project` and `execute`;
- `runtime.dependencies`, recorded but not installed by Localize Anything;
- `entrypoints` as argv arrays;
- `checksum.type: "sha256"` and `checksum.value` for the entrypoint script;
- `source_scope.paths`;
- `provenance` or `maintainer`;
- `notes` and `limitations`.

For `extract_only`, allowed evidence is detect, inventory, extraction,
source validation, deterministic check, and report-only review packet
generation. Blocked claims and phases are rebuild, validate-output as
round-trip proof, plan-apply, apply, full-round-trip, editable delivery, and
generic language/platform support.

Adapter output is ingested into the same runtime artifacts as core handlers:
`source-surface-inventory.json`, `capability-report.json`, `inventory.json`,
`source-validation.json`, `deterministic-check.json`,
`extracted-segments.json`, and `review-packet.json`. Descriptor, entrypoint,
source, target, inventory, source-validation, and extraction hashes are recorded
so downstream artifacts become stale when any dependency changes.

Failure codes are blocking evidence, not warnings:
`descriptor_invalid`, `capability_not_allowed`, `checksum_mismatch`,
`entrypoint_missing`, `path_escape`, `adapter_timeout`,
`adapter_nonzero_exit`, `adapter_invalid_json`,
`adapter_schema_violation`, `adapter_output_too_large`, `adapter_phase_failed`,
`adapter_payload_symlink`, `adapter_payload_special_file`, and
`undeclared_dependency`.

### Subtitles

Mechanical QA preserves cues, timestamps, tags, and placeholders. Reading
speed, line breaks, cultural context, and rendered results belong in Agent or
human review.

### TypeScript locale catalogs (`core.typescript-locale`)

Parses the constrained shape of TypeScript locale catalogs -- object literals
whose leaves are strings, template literals, string arrays, and arrow
functions -- with a real tokenizer/parser and fails closed on anything else.
It is not a regex rewriter and not a general TypeScript parser.

- Extraction covers typed catalogs (`export const fr: Translations = { ... }`),
  partial `defineLocale({ ... })` catalogs, wrapper calls such as
  `defineFieldCopy({ ... })`, weekday-style string tuples, and function-valued
  messages (each translatable literal inside a function is a segment).
- Rebuild replaces only translated literal spans, so imports, exports, keys,
  comments, function signatures, `${...}` expressions, identifiers and all
  non-text syntax are byte-preserved unless a literal changes. The catalog
  export identifier is renamed when `export_name` is supplied (e.g. `en` ->
  `fr`) so a staged target file registers under the target locale.
- Template `${{...}}` expressions are protected: targets must keep the same
  expressions in the same order; deterministic QA blocks drift. Changing
  plural logic or expression structure requires editing the function body
  outside the adapter contract.
- Deterministic validation covers parsing, key identity and coverage,
  duplicate/missing/unexpected keys, function-signature parity, template
  expression parity, placeholder parity, quote-style drift warnings, and
  syntax integrity (reparse).

Verified against the 22 real Hermes Agent locale catalogs (byte-identical
identity round-trip) and the contract fixtures in
`tests/fixtures/typescript-locale/`.

## v1 Priority

The first simplified CLI tier prioritizes:

- JSON and YAML;
- Android XML;
- Apple `.strings` and `.xcstrings`;
- PO/POT;
- XLIFF.

Other listed handlers remain as tested Python compatibility code. Adding more
formats is secondary to better scope discovery, Project Memory, independent
review, and lower human review cost.

## Safety And Degradation

- Never silently damage keys, placeholders, markup, encoding, paths, or target-
  only content.
- Preserve unsupported syntax or surface it for review.
- Do not download or execute third-party handler code without explicit user
  authorization.
- When deterministic handling is unavailable, let the Coding Agent use project
  tooling and state which checks could not be performed.
- Do not claim structural or coverage verification that did not run.
- Do not wrap partial resource success as complete product localization.
