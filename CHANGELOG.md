# Changelog

## Unreleased

## v0.3.0 - Real-Project Workflow Hardening

### Added

- Add read-only inspect summaries with JSON and Markdown outputs.
- Document the inspect-summary workflow for real-project source detection.
- Add refreshed AntennaPod disposable-clone smoke-test evidence for the
  v0.3.0 pre-release workflow.

### Changed

- Improve CLI help so `inspect` is clearly read-only and `localize-run` is
  clearly non-apply.
- Refuse `inspect --output-dir` paths inside the inspected source project.
- Improve the AntennaPod smoke-test helper output by reporting raw inspection
  and compact inspect-summary artifact paths.
- Normalize shell helper line endings for Bash compatibility.
- Bump package/runtime version metadata to `0.3.0`.

### Fixed

- Harden generated-segment markup validation so generic markup constraint lists
  do not enter the Android inline-markup validator.

### Notes

- `PROTOCOL_VERSION` remains `0.1`.
- This release does not validate provider-backed AntennaPod translation.
- This release does not validate destructive apply against AntennaPod.
- Known limitations remain: no full HTML parser, no layout/drawable/asset
  localization, no Gradle editing, and no APK decompilation.

## v0.2.5 — Public Readiness and Smoke Test Evidence

### Changed

- Improve release hygiene, README clarity, and CI benchmark coverage.
- Synchronize package/runtime version metadata with the public release line.
- Complete public readiness cleanup for the repository presentation.
- Polish the bilingual README and public launch documentation.
- Add contributor guidance, issue templates, a pull request template, and a
  SECURITY entry point.
- Document the AntennaPod disposable-clone smoke-test guide and smoke-test
  results.
- Bump package/runtime version metadata to `0.2.5`.

### Notes

- This release does not change runtime localization behavior.
- This release does not add adapter support.

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
