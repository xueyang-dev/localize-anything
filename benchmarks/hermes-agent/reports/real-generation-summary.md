# Hermes Agent Real-Translation Benchmark Summary

This iteration runs the merged Hermes benchmark framework (PR #85) with genuinely produced French translations instead of engineering fixtures.

## What was produced

- **3,683 segments** translated into French by the host agent (YAML/CLI/Gateway: 351, Web dashboard: 709, Desktop: 2,623), imported through the provider-agnostic handoff flow (`--mode import`).
- Canonical inputs are committed under `evidence/real-imports/` (`yaml.jsonl`, `web.jsonl`, `desktop.jsonl`, `manifest.json` with SHA-256 hashes), so the exact run is reproducible without regenerating translations.
- All segments are labeled `quality_claim: host_agent_generated`, `generation_mode: host_agent_import`. **No provider API was called**; no synthetic/identity fixtures remain in the final runs. Producer model identity is not exposed to the benchmark process and is recorded as `unknown` (see `reports/real-generation-metadata.json`).
- Identity targets (target == source) carry candidate classifications from the producer, but are cleared only through the separate retention adjudication (`reports/retained-string-adjudication.csv` / `.json`, reviewer type `AI-assisted bilingual review`). All 203 identity segments were approved; zero remain unapproved.

## Quality gates

- Deterministic QA (key parity, template-expression parity, placeholders, syntax): **pass** on all three surfaces (0 blocking, 0 warnings).
- E1 automated semantic review: **0 flags** after retention adjudication.
- E2 bilingual review: **180 segments** risk-weighted (approval/destructive/errors/templates/terminology/general); 178 approved, 2 corrected (`goal_cleared`, `reasoning/choice_reset`), 0 blocked; YAML rerun passed after fixes.
- Terminology adjudication: 20 terms; 18 intentional, 2 context-dependent, 0 unresolved, 0 errors.
- Build validation on the isolated copy: **8/8 pass** (Hermes i18n parity tests, Python compileall, Web typecheck/vitest/build, Desktop typecheck/vitest/build).
- Runtime DOM smoke: web dashboard served from the isolated copy with the staged `fr.ts`; French renders on /sessions, /config, /models (DOM-verified). Screenshots are **non-durable local artifacts** (ignored `work/visual-smoke/`); pixel-level visual layout review was **not** completed. Desktop Electron not launched (limitation).

## Evidence artifacts

Committed under `benchmarks/hermes-agent/reports/`:

- `real-generation-metadata.json`
- `real-generation-summary.md` (this file)
- `e2-review-sheet.csv`, `e2-review-summary.json/md`
- `terminology-adjudication.csv/md`
- `retained-string-adjudication.csv/json`
- `official-reference-comparison.json`
- `visual-smoke-report.json/md`
- `real-evidence-verification.json/md`

Canonical import inputs: `benchmarks/hermes-agent/evidence/real-imports/`.

## Honest limits

- Translations are AI-produced and AI-reviewed; **no native human (E3) review** was performed.
- Official French catalogs were hidden during generation and used only as post-hoc references, never as generation input.
- Exact model identity is unknown to the benchmark process; retries were not tracked.
- Hardcoded/dynamic text remains out of scope; catalog parity is not full-product localization.
