# Android Support in v0.2.3

Localize Anything v0.2.3 is the fix-forward Android reliability release. It
retains the v0.2.2 resource-preservation boundary while correcting Android
qualifier routing and risk-classification evidence. The reference runtime does
not perform translation; semantic work is delegated to an agent or provider.

## 1. Supported Android resource types

- `string`
- `string-array`, with per-item extraction and rebuild
- `plurals`, with per-quantity extraction and rebuild

Resources with `translatable="false"` are skipped. Resources with
`formatted="false"` do not receive placeholder interpolation constraints.

## 2. Protected structures

The adapter extracts, validates, and preserves:

| Structure | Examples | Deterministic QA |
|-----------|----------|------------------|
| Placeholders | `%1$s`, `%2$d`, `%s` | Placeholder parity |
| Escaped percent | `%%` | Literal-percent drift |
| Android escapes | `\'`, `\"`, `\n`, `\t` | Escape-signature parity |
| Inline tags | `<b>`, `<i>`, `<u>` | Markup-signature parity |
| Simple links | `<a href="...">` | Attribute and URL parity |
| CDATA | `<![CDATA[...]]>` | Boundary and terminator safety |
| XML comments | `<!-- comment -->` | Resource comment round-trip |

Unsupported nested markup, unsupported tags, and unsupported attributes are
preserved but excluded from normal generation. Their segments are marked
`owner_review_required`.

## 3. Source sets and canonical qualifier routing

Android source sets such as `main`, `debug`, and `free` remain separate routing
contexts. Existing locale directories are classified as locale references and
cannot be selected as source truth.

Target locale qualifiers are inserted in Android's canonical order. MCC and MNC
come before language/region; later qualifiers retain their source order:

| Source directory | `zh-CN` target directory |
|------------------|---------------------------|
| `values` | `values-zh-rCN` |
| `values-night` | `values-zh-rCN-night` |
| `values-land` | `values-zh-rCN-land` |
| `values-sw600dp` | `values-zh-rCN-sw600dp` |
| `values-mcc310` | `values-mcc310-zh-rCN` |
| `values-mcc310-mnc004` | `values-mcc310-mnc004-zh-rCN` |
| `values-mcc310-night` | `values-mcc310-zh-rCN-night` |
| `values-mcc310-mnc004-land` | `values-mcc310-mnc004-zh-rCN-land` |

Unknown, duplicated, or incorrectly ordered qualifiers produce a routing
warning and `owner_review_required`. Staging fails closed instead of writing to
a guessed directory.

## 4. Mode behavior

| Mode | Behavior |
|------|----------|
| `blind_benchmark` | Existing locale text is excluded from generation-facing artifacts. |
| `greenfield_localization` | Eligible segments are drafted without target-locale reference text. |
| `existing_locale_maintenance` | Reviewed unchanged translations and target-only resources are preserved. |
| `rewrite_or_harmonization` | Explicit rewrite mode may regenerate eligible segments with reference assistance. |

## 5. Deterministic risk classification

Every extracted Android segment receives `ui_risk_classification` metadata:

- `ui_role`
- `risk_level`
- `review_priority`
- `classification_evidence`

Lexical role and baseline-risk heuristics use resource-name and source-text
patterns. Actual structural metadata can escalate review priority or risk and
provides structural evidence: placeholder and escape signatures, markup
signatures, CDATA, protected spans when present, and unsupported-markup
owner-review markers.

`placeholder_or_markup_protected` is emitted only when such protected structure
exists. A high-risk plain-text resource therefore contains name/text evidence
without fabricated structural evidence. XML comments and resource type are not
currently classification inputs.

This deterministic metadata prioritizes review. It is not semantic translation
quality scoring and does not replace human review.

## 6. Known limitations

The Android adapter does not provide:

- Full HTML parsing or arbitrary nested-markup localization
- Arbitrary inline tags or attributes beyond the supported set
- Layout, drawable, asset, or binary-resource localization
- Gradle editing, APK decompilation, or repackaging
- Runtime UI layout analysis
- Semantic translation quality scoring

Unsupported complex markup remains a preserved, explicit owner-review boundary.
