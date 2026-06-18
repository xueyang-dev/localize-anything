# Roadmap

## v0.1-alpha: Vertical Slice

Status: implemented and covered by protocol, runtime, adapter, lifecycle, and
public benchmark tests.

Prove the full protocol and workflow with gettext PO/POT, a Wesnoth scenario adapter, and generic JSON locale files.

Required outcomes:

- protocol schemas and examples
- lightweight reference CLI
- four-layer memory initialization
- preflight inventory and batch planning contracts
- stable segment IDs and source hashes
- staged rebuild and deterministic QA
- immutable delivery package
- incremental update detection
- review import and scoped sign-off
- apply dry-run
- The South Guard blind-generation benchmark definition

## v0.1-beta: Common Text Formats

Status: implemented with fixture-based extraction, rebuild, and deterministic
QA coverage.

Includes YAML/TOML, CSV/TSV/XLSX, Markdown/HTML, SRT/VTT, and XLIFF adapters.
Format-specific limitations and capability levels are documented in
`docs/adapters.md`.

## v0.2: Platform Enablement

Add Android/iOS resource adapters, generic game and web enablement flows, pseudo-localization, and conditional visual QA integrations.

Current iteration slice:

- Android and iOS source projects first; APK/IPA repackaging is out of scope.
- Generate drop-in `res/values-<locale>/strings.xml` language resources from
  `res/values/strings.xml`.
- Generate drop-in `.lproj` `.strings` and `.stringsdict` language resources
  for iOS source projects.
- Generate staged `.xcstrings` String Catalog updates for iOS/macOS source
  projects.
- Treat LLM translation as the central workflow stage executed by the host
  agent through work packets and review-compatible segment JSONL, not as a
  provider-specific runtime dependency.
- Emit `draft-request` artifacts and validate generated segment JSONL before
  staging platform resources.
- Render paste-ready prompt files and a generation README so individual
  developers can run host-agent LLM generation manually without learning the
  internal JSON request format.
- Normalize common host-agent LLM response shapes with
  `import-generated-response` and `import-generated-handoff` before batch
  collection, including fenced JSON, JSON arrays, and `segment_id -> target`
  maps.
- Coordinate multi-batch host-agent output with `generation-handoff` and
  `collect-generated`.
- Route generated segment JSONL through `stage-generated` so mixed projects can
  write all staged language resources through one command.
- Export generated source/target review sheets in Markdown and CSV so
  developers or translators can inspect drafts before applying files.
- Provide `localize-run` as the developer-facing orchestration command for
  preflight, extraction, LLM handoff, generated-batch collection, staging,
  deterministic QA, delivery packaging, and dashboard output.
- Default to staged copies. Applying to the original project requires explicit
  run-id confirmation and creates backups for replacements.
- Render a non-mutating apply plan by default so users can review exact
  create/replace/conflict operations before confirming overwrite.
- Emit developer/translator delivery dashboards from package metadata so
  generated files, QA state, unprocessed assets, and next actions are visible.
- Use well-known open-source mobile projects as real-world benchmarks. The
  first pinned benchmarks target AntennaPod's Android strings resource and
  Signal-iOS's `Localizable.strings` resource. The first String Catalog
  benchmark targets IceCubesApp's `Localizable.xcstrings` resource.

## Later Releases

Add Unity, Godot, Unreal, Ren'Py, DOCX, PPTX, PDF, image, and audio workflows. Add MCP and community adapter distribution only after the core adapter contract and security model are stable.

## Community Direction

Keep core adapters open and forkable. Allow project-local private adapters. A future registry may discover remote adapters, but must require explicit installation, version locking, checksums, permissions, fixtures, and contract tests.
