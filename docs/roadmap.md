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

## Later Releases

Add Unity, Godot, Unreal, Ren'Py, DOCX, PPTX, PDF, image, and audio workflows. Add MCP and community adapter distribution only after the core adapter contract and security model are stable.

## Community Direction

Keep core adapters open and forkable. Allow project-local private adapters. A future registry may discover remote adapters, but must require explicit installation, version locking, checksums, permissions, fixtures, and contract tests.
