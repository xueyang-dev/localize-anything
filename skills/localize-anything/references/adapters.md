# Adapters

## Selection

Prefer, in order: explicit user selection, project lock, core adapter, verified/community adapter, generic fallback. Never change a locked adapter silently.

Distinguish format adapters from scenario adapters and platform overlays. A game scenario adapter should orchestrate engine detection, format adapters, platform risks, and delivery conventions rather than parse every format itself.

## Capability Levels

- `full_round_trip`
- `extract_and_rebuild`
- `extract_only`
- `inspect_only`
- `unsupported`

Record actual runtime capability. Missing rendering, OCR, network, dependency, or parser support must degrade the claim and QA scope.

## Contract

Follow the lifecycle `detect -> inventory -> extract -> validate-source -> rebuild -> validate-output -> plan-apply`. Exchange schema-defined JSON and JSONL. Write to staging until apply is confirmed.

Keep dependencies isolated and version-locked. Ask before downloading packages or executable community adapters. Permit project-local forks without requiring publication.

## Core v0.1 Routing

- JSON -> `core.json-locale`
- PO/POT -> `core.gettext-po`
- YAML/TOML -> `core.yaml-toml`
- CSV/TSV/XLSX -> `core.tabular`
- Markdown/HTML -> `core.markup`
- SRT/WebVTT -> `core.subtitles`
- XLIFF -> `core.xliff`
- Wesnoth WML context -> compose `scenario.wesnoth` over `core.gettext-po`

Read `docs/adapters.md` from the companion repository when exact v0.1 format
limitations matter. Do not claim unsupported YAML complex scalars, HTML
attributes, workbook visual QA, or subtitle reading-speed QA as completed.
