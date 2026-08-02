# Architecture

Localize Anything is an Agent-native localization workflow and review layer.
The active implementation has one public CLI and no platform fallback.

The canonical product boundary is [Product Direction](product-direction.md).
The removed v0.4 platform remains documented only in the
[legacy snapshot](architecture-v0.4-legacy.md) and Git history.

## Anything Definition

"Anything" means surface-aware coverage, not universal automatic mutation.
Localize Anything discovers and classifies localization surfaces, routes
supported surfaces to reliable deterministic handlers, produces enablement
plans when project structure must change, and reports unsupported, unscanned,
dynamic, or non-text content as limitations.

The system must be able to explain:

- where user-visible content may originate;
- which surfaces were scanned;
- which surfaces can be extracted;
- which surfaces can be rebuilt safely;
- which surfaces require source or project-structure changes;
- which surfaces require build, launch, runtime, or visual verification;
- which surfaces are unsupported; and
- why a run cannot claim complete product localization.

## Localization Surface Model

`LocalizationSurface` is the first-class model for scope, adapter resolution,
coverage, and delivery claims.

| Surface type | Definition and examples | Default treatment | Claim impact |
| --- | --- | --- | --- |
| `resource_catalog` | Standard structured resources: JSON locale files, PO/POT, `.strings`, `.stringsdict`, `.xcstrings`, Android `strings.xml`, XLIFF, ARB, RESX. | Detect, inventory, extract, validate, and rebuild when a handler exists. Enablement is not required for already-declared resources. | Passing checks applies only to the catalog and declared scope, not the whole app. |
| `code_embedded_catalog` | Source-code structures with stable localization semantics: Swift `Strings(...)` typed constructors, Kotlin objects, TypeScript locale objects, Python dictionaries, Rust static maps. | Support only through explicit AST, parser, or syntax-aware adapters. Rebuild must stage first and validate syntax/build evidence before apply. | "Swift supported" is not a valid claim; the claim must name the detected catalog structure and evidence. |
| `inline_code_string` | Scattered string literals in application code. | Inventory, classify candidates, estimate user-visible likelihood, and produce enablement plans. Do not automatically treat every literal as translatable. | Unprocessed candidate strings are coverage limitations; internal strings are exclusions, not missing translations. |
| `template_or_markup` | HTML, Markdown, email templates, server-rendered templates, and page markup. | Use bounded markup handlers or project-native tools; preserve code, scripts, styles, attributes, and unsafe syntax unless explicitly supported. | Extracted text coverage does not prove rendered page coverage. |
| `runtime_external_content` | API, CMS, database, remote config, push notifications, A/B tests, help centers, and server-provided copy. | Usually requires a connector, export/import, API workflow, or manual project plan. | File-only runs must report these surfaces as external or unscanned. |
| `non_text_asset` | Image text, screenshots, posters, icons with text, audio, video, voiceover, fonts, and other visual or sound assets. | Requires separate tooling such as OCR, design/media workflows, visual QA, or human review. | Not covered by text extraction; must remain visible in limitations. |
| `binary_or_compiled_resource` | Compiled or binary resources: `.qm`, some storyboard/xib or game-engine assets, compiled bundles. | Inspect only unless a specialized toolchain is available and authorized. | Unsupported binary content cannot be silently ignored in product-complete claims. |

### Code String Boundary

Source-code text has three distinct boundaries:

- structured code-embedded catalogs can be supported by explicit adapters;
- unstructured inline user-facing strings default to detection,
  classification, and enablement planning, not bulk source rewrites;
- internal or non-user-facing strings, such as logs, paths, commands, API keys,
  identifiers, notification names, SQL, regexes, internal errors, and test
  fixtures, must not be automatically extracted as localization objects.

## Capability Expression

The existing round-trip levels remain useful:

```text
full_round_trip
extract_and_rebuild
extract_only
inspect_only
unsupported
```

They are not sufficient by themselves. Capability claims must also state
orthogonal dimensions when relevant:

```text
surface_detection
content_extraction
staged_rebuild
project_enablement
source_code_mutation
syntax_validation
build_verification
launch_verification
runtime_surface_verification
visual_verification
```

Dimension status values should reuse existing protocol style where possible:
`supported`, `experimental`, `required`, `not_required`, `not_run`,
`unsupported`, `blocked`, and `unknown`.

Examples of valid claims:

```text
Swift code catalog detected
Extraction supported
Staged rebuild experimental
Project enablement required
Source mutation required
Syntax validation supported
Build verification not run
Visual verification not run
```

Invalid claims:

- `Swift supported`
- `JSON supported` as proof of React application localization
- `strings.xml translated` as proof of Android app localization
- `DOCX text rebuilt` as proof of rendered document verification
- `all extracted strings translated` as proof of full product localization

## Project-Local Adapter Runtime Boundary

Project-local scripted adapters extend the core for a specific project surface
through a constrained runtime boundary:

```text
Capability Scan
-> Adapter Selection
-> Capability Gate
-> Artifact Preconditions
-> Allowed Phase Execution
```

- Adapter candidates are discovered but never executed until explicitly
  selected.
- Unsupported surfaces fail closed before Project Memory and review.
- Selection validates the descriptor, checksum, entrypoint, source scope, and
  the complete payload.
- `extract_only` adapters allow check and report-only review; rebuild, apply,
  and editable/full-round-trip claims remain blocked.
- Artifact preconditions bind review to current, valid, mapping-consistent
  canonical artifacts.
- Full payload freshness: every regular file in the adapter payload
  (descriptor, entrypoint, helper modules, data files) is fingerprinted; any
  change invalidates downstream artifacts.
- Payloads must be vendored regular files and directories. Symlinks and
  special files are rejected; the runtime never follows links.
- This boundary is not an OS-level sandbox and does not imply built-in
  support for any programming language or platform.

## Delivery And Enablement

Delivery Mode applies only to declared surfaces whose adapters and project
workflow can extract, rebuild or review, validate, stage, and report evidence
for the requested scope.

Enablement Mode applies when localization requires source-code mutation,
project-structure changes, connector setup, build configuration, runtime
workflow, or media tooling before delivery can be safe. Enablement output is a
plan with risks, affected files, validation commands, staging/apply policy, and
rollback requirements. It is not a delivery success for that surface.

## Preserved Principles

The surface model does not reintroduce the removed platform. It preserves:

- protocol-first data contracts;
- deterministic Runtime versus semantic Agent responsibility;
- adapter-extensible handling without hidden permissions;
- artifact-first evidence;
- staged output before project writes;
- explicit apply plans, run-id or equivalent confirmation, and backup/rollback
  evidence for any future source mutation;
- Delivery versus Enablement distinction;
- Format handler, Platform overlay, and Scenario adapter role separation;
- Runtime/adapter QA, Agent QA, and Human Review as separate evidence channels;
- no partial-file success wrapped as complete localization success.

## Active Flow

```text
Localize Anything Skill
    |
    +--> localize scan --------------------> Project Memory
    +--> localize glossary bootstrap ------> canonical Glossary
    |
    +--> Coding Agent edits the project
    |       +--> project-native build/test
    |       +--> screenshots and Git diff
    |
    +--> localize check -------------------> deterministic findings
    +--> localize review ------------------> independent review packet
    |       +--> fresh Agent context
    |       +--> normalized review findings
    +--> human confirmation ---------------> open findings only
    +--> localize report ------------------> concise completion state
```

## Runtime Boundary

`core_cli.py` exposes exactly five command groups. `core.py` coordinates their
small data flow and delegates reusable work to focused modules:

| Module | Responsibility |
| --- | --- |
| `core_preflight.py` | project boundary checks, resource detection and discovery |
| `core_glossary.py` | candidate concepts, normalization and locked-term checks |
| `core_memory.py` | confirmed legacy terminology, TM, style and decision import |
| `core_segments.py` | review identity/alignment and deterministic diff/staleness |
| `core_formats.py` | supported-format extraction and pair-validation boundary |
| `io_utils.py` | atomic local writes |

The core does not import Provider, Workbench, workflow, readiness, signoff,
Knowledge Pack, generation, delivery, retrieval, repair, or artifact-state
modules. Those product surfaces and their CLI/protocol chains have been
removed.

## State

The target project owns the state under `.localize-anything/`:

```text
project-memory.json
glossary.json
deterministic-check.json
review-packet.json
independent-review.json
human-confirmations.json
report.json
report.md
```

Project Memory holds source/target locale, declared resources, product context,
style, preserve rules, confirmed decisions, and reviewed Translation Memory.
The canonical Glossary is the only user-facing terminology truth.

Git remains the state-management and collaboration layer. Localize Anything
does not create a parallel branch, lock, approval, recovery, delivery, or
release system.

Workbench, historical run state, readiness matrices, artifact projection, and
UI-derived business status were removed during the Phase 4 migration. The
current implementation therefore has no active Workbench path that can mix a
historical run with current project state. Missing artifacts are reported by
the five-command core as missing state or incomplete report inputs; they are
not silently substituted from an old run.

## Planned Surface Artifacts

The current protocol has seven stable contracts and does not yet generate
surface discovery artifacts. The following are architecture contracts and
planned protocol artifacts, not stable schema files:

- `source-surface-inventory.json`: answers where user-visible content may come
  from. It should include fields such as `surface_id`, `surface_type`,
  `path_or_locator`, `framework_or_platform`, `detector`,
  `detection_evidence`, `source_truth_status`, `estimated_units`,
  `scan_status`, `adapter_resolution`, `capability_summary`,
  `user_visible_likelihood`, `runtime_reachability`, `coverage_impact`, and
  `notes`.
- `capability-report.json`: answers how far each surface can be processed. It
  should combine round-trip level, capability dimensions, evidence,
  limitations, required tools, verification status, claim downgrades, and
  forbidden claims.
- `enablement-plan.json`: answers what must change before unsupported or
  project-structure surfaces can be delivered. It should include `surface_id`,
  `reason`, `required_changes`, `affected_files`, `proposed_adapter`,
  `mutation_type`, `risk_level`, `validation_commands`, `staging_policy`,
  `apply_policy`, `rollback_requirements`, `human_decisions`, and `status`.

Promotion requires Runtime generation, schema/example validation, contract
tests, and evidence that the artifacts do not duplicate Project Memory,
Glossary, deterministic checks, independent review, or report state.

## Format Boundary

The five-command core directly supports:

- JSON;
- YAML/TOML;
- Android string resources;
- Apple `.strings` / `.stringsdict`;
- Apple `.xcstrings`;
- PO/POT;
- XLIFF 1.2/2.x.

Focused Markdown/HTML, tabular, Word OpenXML, subtitle, and Wesnoth handlers
remain as tested Python compatibility code. They have no standalone legacy CLI
entrypoint and are never selected as an automatic platform fallback.

The Coding Agent handles missing formats with project-native code and tools,
then records the deterministic coverage limitation.

Resource-format support is not platform support. The current Apple handlers
cover `.strings`, `.stringsdict`, and `.xcstrings` resource catalogs; they do
not imply generic iOS, Swift, storyboard/xib, asset, source-code, build, launch,
or visual coverage. Android XML support covers declared string resources; it
does not cover Compose source strings, layouts, drawables, runtime/server copy,
build-system changes, APK packaging, or locale behavior.

## Review Boundary

Quality evidence stays separated:

1. deterministic checks cover structure, keys, placeholders, markup, escapes,
   paths, and locked terminology;
2. an independent Agent context reviews meaning, naturalness, tone, page
   context, and product concepts;
3. the user decides only open, high-risk product findings.

A confirmation cannot be recorded for a finding that is not open with
`needs_human_confirmation`.

## Responsibility Boundary

| Owner | Responsibility |
| --- | --- |
| Skill | scope, workflow, memory use, independent review and final explanation |
| `localize` core | deterministic state and trust-boundary validation |
| Coding Agent | i18n engineering, resources, locale behavior, build/test, screenshots and Git |
| User | official terminology, brands, product meaning, high-risk ambiguity and release judgment |

`report: ready` means the five-command evidence for the declared scope is
complete. It does not certify translation quality or replace project-native
build/test, screenshots, Git review, or human release approval.

## Dependency Rule

New core modules may depend only on focused core modules, format handlers,
`io_utils.py`, and the Python standard library. Compatibility handlers must not
import removed platform concepts. No future capability should reintroduce an
orchestrator, registry, state machine, readiness matrix, compatibility wrapper,
or broad protocol inventory without a new accepted product decision.
