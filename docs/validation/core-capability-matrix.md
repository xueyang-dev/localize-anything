# Phase 5 Core Capability Matrix

Date: 2026-07-31

This matrix covers the five-command core and the deliberately bounded Python
compatibility handlers after Phase 4. It distinguishes a tested capability
from a complete product-localization claim. `partially_covered` means a real
boundary or optional dependency remains; `intentionally_unsupported` is used
only when the product explicitly declines the capability.

## Summary

| Status | Count |
| --- | ---: |
| covered | 19 |
| partially_covered | 4 |
| uncovered | 0 |
| intentionally_unsupported | 0 |
| **total** | **23** |

## Matrix

| Capability | Status | Evidence | Boundary / limitation |
| --- | --- | --- | --- |
| scan | covered | Core/Skill tests and all three fixed slices discovered declared resources. | Does not infer project-specific i18n architecture. |
| glossary bootstrap | partially_covered | Candidate and lock tests pass; each slice writes canonical `glossary.json`. | Conservative heuristics can produce zero candidates; semantic quality remains human-reviewed. |
| check | covered | JSON and Apple passed; Android surfaced an expected informational skipped-resource finding. | Structural and placeholder checks do not judge meaning or naturalness. |
| review packet | covered | All slices generated aligned independent-review packets. | Packet is not automatic semantic approval. |
| independent review | covered | Fresh-context review payloads accepted for all slices. | Reviewer quality is external. |
| finding/confirmation gate | covered | Open findings blocked readiness until the exact finding was confirmed. | Confirmation does not replace product-owner judgment. |
| report readiness | covered | `needs_human_confirmation`, `needs_attention`, and `ready` states observed. | `ready` is not project build/test release approval. |
| Project Memory | covered | scan persists locales/resources and imports confirmed memory. | Build configuration and runtime locale behavior remain project work. |
| concept-centered Glossary | partially_covered | Stable IDs and locked preferred/forbidden targets are tested. | No complete product ontology or guaranteed natural translation. |
| knowledge import | covered | Only confirmed terms, TM, style, decisions, and approved packs enter memory. | Knowledge Pack is not a user-facing core concept. |
| segment identity/diff/staleness | covered | Stable IDs, alignment, hashes, and stale/new/unchanged parity tests pass. | No legacy workflow/artifact lifecycle is carried into core. |
| JSON/YAML | partially_covered | JSON completed clean-install E2E; YAML/TOML round-trip tests pass. | Full YAML syntax needs optional `yaml`; complex syntax remains bounded. |
| Android XML | covered | Extensive adapter tests plus ru fixed-slice run. | Compose/layout/assets/build/APK behavior remains project work. |
| Apple `.strings` | covered | Round-trip tests plus ru slice validated with `plutil`. | Xcode project and application changes remain project work. |
| `.xcstrings` | covered | Catalog round-trip and review pairing tests pass. | Only declared catalogs are checked. |
| PO | covered | Parsing, plural/header/placeholder and identity tests pass. | msgmerge/release tooling remains project-native. |
| XLIFF | covered | XLIFF 1.2/2.x round-trip tests pass. | Vendor-specific extensions are bounded. |
| markup compatibility | covered | Markdown/HTML preservation round-trip tests pass. | Explicit direct handler only; no automatic fallback. |
| subtitles compatibility | covered | SRT/WebVTT cue/timing/tag round-trip tests pass. | Playback and reading-speed review remain external. |
| tabular compatibility | covered | CSV/TSV/XLSX preservation tests pass. | Targets a locale-table convention. |
| Wesnoth compatibility | partially_covered | WML extraction and pinned fixture tests pass. | Extract-only scenario handler, not a general five-command path. |
| Word compatibility | covered | DOCX/DOTX/DOCM/DOTM round-trip tests pass. | Layout, images, embedded objects, legacy/encrypted files need separate handling. |
| clean package installation | covered | Fresh clone/venv wheel install exposed one `localize` entrypoint and ran all five commands; deleted modules were absent. | Repository protocol/adapter catalogs are validation assets, not runtime package data. |

## Evidence boundaries

The three Phase 5 validation targets are fixed resource slices copied into a
temporary clean-clone workspace:

- JSON: `examples/quickstart-json`, including native `python -m json.tool`.
- Android: `tests/fixtures/android-project`, including native `xmllint`.
- Apple: `tests/fixtures/ios-project`, including native `plutil -lint`.

Each followed `scan → glossary bootstrap → resource edit → native validation →
check → review → report`. JSON and Apple exercised an open finding and human
confirmation; Android exercised an auto-cleared review finding and retained
the expected `translatable=false` informational item.

The slices are intentionally narrow. They demonstrate command ordering,
resource discovery, deterministic boundaries, independent review, and report
gating; they do not claim complete localization of a production application.

Machine-readable source: [core-capability-matrix.json](core-capability-matrix.json).
