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
| `core.word-document` | DOCX/DOTX/DOCM/DOTM | `extract_and_rebuild` | OpenXML package entries, relationships, styles, run and paragraph non-font properties, target-locale fonts, macros, placeholders |
| `core.subtitles` | SRT/WebVTT | `full_round_trip` | cue identity, timing, inline tags, placeholders |
| `core.xliff` | XLIFF 1.2/2.x | `full_round_trip` | unit IDs, source units, inline tags, placeholders |
| `core.android-strings` | Android `strings.xml` | `extract_and_rebuild` | string, string-array, plurals, resource names, `translatable="false"`, `formatted="false"`, placeholders, target resource path |
| `core.ios-strings` | iOS `.strings` / `.stringsdict` | `extract_and_rebuild` | keys, comments/order for `.strings`, plural forms for `.stringsdict`, placeholders, target `.lproj` path |
| `core.xcstrings` | Xcode `.xcstrings` | `extract_and_rebuild` | sourceLanguage, stringUnit values, variation leaves, comments/metadata, placeholders, target language entries |
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

Word OpenXML support is an experimental v0.3 document slice. It handles
`.docx`, `.dotx`, `.docm`, and `.dotm` packages with Python standard-library
ZIP/XML parsing, translating visible WordprocessingML and DrawingML text in
body, tables, headers, footers, notes, comments, text boxes, charts, and
diagrams where the XML is safely editable. It preserves non-text package parts,
relationships, styles, paragraph properties, run properties other than the font
family, and VBA macro bytes without executing macros. Localized runs normalize
the font family by target locale, for example English uses Arial and Simplified
Chinese uses Microsoft YaHei, while size, bold/italic, spacing, relationships,
and non-text resources remain protected by deterministic QA. Legacy binary
`.doc`, encrypted documents, embedded object content, and image text are not
localized and must be reported as unsupported or unchecked instead of silently
claimed as complete coverage.

Subtitle QA does not perform rendered line-length or reading-speed review; the
agent and human QA channels must record those checks when required.

Android strings support is an experimental v0.2 platform slice. It handles
simple `<string>`, `<string-array>`, and `<plurals>` resources from
`res/values/strings.xml` and writes target locale files such as
`res/values-zh-rCN/strings.xml` to staging. It skips `translatable="false"`
resources and warns on inline markup instead of silently claiming complete
Android resource coverage.
APK decompilation, repackaging, signing, layouts, drawables, and build-system
changes remain out of scope for this adapter.

iOS strings support is an experimental v0.2 platform slice. It handles
`.lproj` `.strings` key/value resources and `.stringsdict` plural category
strings, then writes target locale files such as `zh-Hans.lproj` to staging.
It does not edit Xcode project files, Swift/Objective-C code, storyboards,
assets, or build settings.

String Catalog support is an experimental v0.2 platform slice for `.xcstrings`
files. It extracts source-language `stringUnit` values and variation leaves,
then writes target language entries such as `zh-Hans` into a staged copy of the
same catalog. It preserves non-localization catalog metadata and does not edit
Xcode project files or application code.

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
