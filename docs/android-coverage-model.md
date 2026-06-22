# Android Coverage Model

Android `res/values` source resources are not always the full visible UI string surface.

Localize Anything treats editable Android project resources as the default source of truth. A source-only run can be structurally correct, pass QA, and still leave visible UI strings in the source language when those strings come from another surface.

## Coverage Categories

- `app_source_resources`: editable Android source resources such as `app/src/main/res/values/strings.xml`.
- `build_variant_resources`: editable variant source resources such as `app/src/debug/res/values/strings.xml`.
- `merged_dependency_resources`: Gradle merged resources from dependencies. These can include strings from libraries such as shared UI components.
- `non_resource_runtime_text`: text that is not Android resource-file content.

## Important Boundaries

Gradle merged resources may include dependency strings that are visible in the app UI. If a run only localizes source `res/values` files, those dependency strings are not translated by that run.

Device folders such as `Alarms`, `Documents`, and `DCIM` are runtime filesystem content, not Android string resources. Server-provided strings, WebView content, image text, Compose hardcoded strings, layout hardcoded strings, and OS strings are also outside this resource workflow.

Merged dependency overlay support should remain explicit and experimental. It should not become a default source-only behavior because merged resources are build intermediates and variant-specific. See `docs/android-merged-resource-overlay.md` for the opt-in overlay workflow.

Apply/write-back is out of scope for this coverage model. This document only explains detection and reporting.
