# Android Merged Resource Overlay

Localize Anything defaults to source-only Android localization. It reads editable app resources such as `app/src/main/res/values/strings.xml` and does not translate Gradle merged dependency resources unless explicitly requested.

Some Android apps show strings that come from dependency resources, for example shared UI libraries. A source-only run can pass deterministic QA while those visible dependency strings remain in the source language.

## Explicit Overlay Workflow

Merged dependency resource coverage is an explicit, variant-specific workflow:

- provide a Gradle merged values XML file or directory with `--android-merged-resources`;
- opt in with `--include-android-merged-resources`;
- generate an app-owned target-locale overlay file such as `app/src/main/res/values-th/localize_anything_overlay.xml`;
- package the overlay in the delivery artifact;
- apply it only through `apply-delivery` with the matching run id and a clean git tree.

The workflow does not modify the source project during `localize-run`.

Provider-backed overlay validation requires a successful real provider call. If
a provider fails because of SSL, authentication, network, rate limit,
configuration, or malformed response errors, the run must be treated as
provider-failed. Synthetic fallback output only proves coverage, packaging,
build, and apply mechanics; it does not prove translation quality or provider
success.

## What Gets Included

The overlay excludes resources already owned by the app source files selected for the run. It also excludes keys already present in the target locale resource directory, `translatable="false"` entries, unsupported resource types, and resources that require owner review for unsafe markup or placeholder structure.

Included overlay resources preserve Android string, string-array, and plurals structure. Deterministic Android QA still validates the generated overlay before packaging.

## Safety Boundaries

This workflow is not a claim of full Android app localization. It does not cover runtime filesystem labels, OS strings, server-provided strings, WebView content, image text, Compose hardcoded strings, layout hardcoded strings, Gradle editing, APK decompilation, or provider translation quality.

The generated overlay is a delivery artifact until an explicit apply step is run. `apply-delivery` requires the matching run id, refuses dirty git trees, and only allows merged-resource overlay outputs to target a locale `values-*` resource directory.

Delivery packages created from provider-failed synthetic fallback output are
marked with no quality claim and are not apply-allowed by default. Rerun the
provider step successfully before applying overlay delivery files.

## Follow-up Scope

Future improvements can make variant discovery and overlay review easier, but merged dependency resources should remain opt-in because they are build intermediates and can vary by flavor, build type, dependency version, and Gradle configuration.
