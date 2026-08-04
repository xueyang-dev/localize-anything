# Hermes Agent Real-Translation Benchmark Summary

This iteration runs the merged Hermes benchmark framework (PR #85) with genuinely produced French translations instead of engineering fixtures.

## What was produced

- **3,683 segments** translated into French by the host agent (YAML/CLI/Gateway: 351, Web dashboard: 709, Desktop: 2,623), imported through the provider-agnostic handoff flow (`--mode import`).
- All segments labeled `quality_claim: host_agent_generated`, `generation_mode: host_agent_import`. **No real provider API was called**; no synthetic/identity fixtures remain in the final runs.
- Retained product terms, brands, and identifiers carry `classification` + `classification_note` (69 desktop segments re-adjudicated after E1).

## Quality gates

- Deterministic QA (key parity, template-expression parity, placeholders, syntax): **pass** on all three surfaces (0 blocking, 0 warnings).
- E1 automated semantic review: **0 flags** after classification.
- E2 bilingual review: **180 segments** risk-weighted (approval/destructive/errors/templates/terminology/general); 178 approved, 2 corrected (`goal_cleared`, `reasoning/choice_reset`), 0 blocked; YAML rerun passed after fixes.
- Terminology adjudication: 20 terms; 18 intentional, 2 context-dependent, 0 unresolved, 0 errors.
- Build validation on the isolated copy: **8/8 pass** (Hermes i18n parity tests, Python compileall, Web typecheck/vitest/build, Desktop typecheck/vitest/build).
- Visual smoke: web dashboard served from the isolated copy with the staged `fr.ts`; French renders on /sessions, /config, /models (DOM-verified, screenshots saved). Desktop Electron not launched (limitation).

## Evidence artifacts (this iteration)

- `work/real-generation-metadata.json`
- `work/real-generation-summary.md`
- `work/e2-review-sheet.csv`, `work/e2-review-summary.json/md`
- `work/terminology-adjudication.csv/md`
- `work/official-reference-comparison.json`
- `work/visual-smoke-report.json/md` + screenshots in `work/visual-smoke/`
- `work/real-evidence-verification.json/md`

## Honest limits

- Translations are AI-produced and AI-reviewed; **no native human review** was performed.
- Official French catalogs were hidden during generation and used only as post-hoc references, never as generation input.
- Hardcoded/dynamic text remains out of scope; catalog parity is not full-product localization.
