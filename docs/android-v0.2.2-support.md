# Android Support in v0.2.2

> **Superseded:** the public `v0.2.2` tag is retained for history but was not
> published as a GitHub Release. Use the corrected
> [Android Support in v0.2.3](android-v0.2.3-support.md) boundary.

Localize Anything v0.2.2 provides deterministic Android string-resource handling
for extraction, structural QA, maintenance-mode preservation, and review-risk
metadata. The reference runtime does not perform translation; all semantic work
is delegated to the agent or an external provider.

## 1. Supported Android resource types

- `string`
- `string-array` (with per-item extraction and rebuild)
- `plurals` (with per-quantity extraction and rebuild)

Resources with `translatable="false"` are skipped during extraction.
Resources with `formatted="false"` are extracted but their placeholder
signatures are cleared to signal that format interpolation is not expected
in the target locale.

## 2. Supported protected structures

The adapter detects and preserves the following structures through extraction,
generation validation, and staging rebuild:

| Structure | Example | QA gate |
|-----------|---------|---------|
| Placeholders | `%1$s`, `%2$d`, `%s` | Placeholder parity check |
| Escaped percent | `%%` | Literal-percent drift check |
| Android escapes | `\'`, `\"`, `\n`, `\t` | Escape signature parity check |
| Inline tags | `<b>`, `<i>`, `<u>` | Markup signature parity check |
| Simple links | `<a href="...">` | Attribute and URL parity check |
| CDATA boundaries | `<![CDATA[...]]>` | CDATA terminator safety check |
| XML comments | `<!-- comment -->` before resources | Comment round-trip check |

## 3. Supported project routing

- **Source sets**: `main`, `debug`, `free` and equivalent Android source-set
  directories are detected and treated as separate generation contexts.
  Locale-qualified directories (`values-es`, `values-fr`, `values-zh-rCN`)
  are excluded from source truth and classified as locale references.
- **Resource qualifiers**: Non-locale qualifiers such as `night`, `land`,
  `sw600dp` are preserved in target locale paths.
- **Target locale mapping**: Target resources are written to paths such as
  `values-zh-rCN/strings.xml`, `values-zh-rCN-night/strings.xml`, preserving
  the source set and non-locale qualifier chain.

## 4. Mode behavior

| Mode | Behavior |
|------|----------|
| `blind_benchmark` | Existing target locale translations are hidden from generation; translation memory and glossary are suppressed. |
| `greenfield_localization` | All eligible segments are sent for translation draft. Only style and terminology guidance is provided. |
| `existing_locale_maintenance` | Previously reviewed translations with unchanged source hashes are preserved. Only new, stale, or conflicting segments are sent for generation. |
| `rewrite_or_harmonization` | All segments are eligible for generation with translation memory assistance. |

Target-only resources (keys present in a target locale file but absent from
the source) are preserved during maintenance and flagged for owner review
rather than silently deleted.

Unsupported complex markup (nested tags, unsupported tag types, unsupported
attributes) is blocked from normal generation. The source text is preserved
and the segment is flagged `owner_review_required`.

## 5. Risk classification

v0.2.2 includes deterministic review-priority metadata in the
`ui_risk_classification` field of every extracted Android segment.

The classifier uses deterministic resource-name and source-text patterns. It
also records structural evidence only when the adapter reports actual protected
structure, such as placeholders, escapes, markup, CDATA, or unsupported markup.

- `ui_role` — one or more of `destructive_action`, `auth`, `privacy`,
  `permission`, `legal`, `payment`, `error`, `warning`, `button`, `title`,
  `message`, `unknown`
- `risk_level` — `low`, `medium`, `high`, or `critical`
- `review_priority` — `normal`, `review_recommended`, or `owner_review_required`
- `classification_evidence` — the deterministic basis for each classification

**This is not semantic translation scoring and does not replace human review.**
Classification is based only on deterministic string-matching heuristics.
The metadata supports review prioritization in delivery dashboards and review
sheets. It does not block delivery by itself (unless `owner_review_required`
is already set by structural constraints such as unsupported markup).

## 6. Explicit non-goals / limitations

The v0.2.2 Android adapter does **not** support:

- Full HTML parsing or arbitrary nested markup auto-localization
- Arbitrary tag or attribute support beyond the set documented in §2
- Layout, drawable, or asset file localization
- Gradle build-file editing
- APK decompilation or repackaging
- Runtime UI layout analysis
- Semantic translation quality scoring

Unsupported complex markup is preserved in staging output rather than
automatically localized. Segments requiring owner review are clearly
flagged and excluded from normal generation batches.
