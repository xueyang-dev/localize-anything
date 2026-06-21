# Changelog

## Unreleased

### Changed

- Improve release hygiene, README clarity, and CI benchmark coverage.

## v0.2.3 — Android Resource Reliability Fixes

### Fixed

- Corrected Android resource qualifier ordering for target locale paths.
  - `values-mcc310` now maps to `values-mcc310-zh-rCN`.
  - `values-mcc310-mnc004-land` now maps to `values-mcc310-mnc004-zh-rCN-land`.
- Fixed risk classification evidence truthfulness.
  - Protected-structure evidence is emitted only when placeholders, escapes,
    markup, CDATA, or structural review markers actually exist.

### Added

- Android support boundary documentation in `docs/android-v0.2.3-support.md`.
- MCC/MNC source-set regression fixtures and fail-closed routing checks.
- Clean release validation flow for v0.2.3.

### Notes

- v0.2.3 supersedes the unpublished v0.2.2 tag.
- v0.2.2 remains in history but should not be used as a public release.
