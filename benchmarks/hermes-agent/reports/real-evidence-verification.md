# Hermes Agent Real-Evidence Verification

| Flag | Value |
| --- | --- |
| real_generation_present | **true** — host-agent-generated imports (`host_agent_generated` / `host_agent_import`) |
| engineering_fixture_absent | **true** — zero `engineering_fixture_only` segments in the final run |
| E2_review_completed | **true** — 180-segment risk-weighted bilingual review |
| E2_blocking_zero | **true** — 0 blocked; 2 needs_revision corrected and rerun |
| terminology_adjudicated | **true** — 20 terms, 18 intentional / 2 context-dependent / 0 unresolved / 0 errors |
| post_edit_deterministic_QA_pass | **true** — YAML/Web/Desktop QA pass, 0 blocking, 0 warnings, 0 semantic flags |
| build_validation_pass | **true** — 8/8 Hermes checks (i18n parity, compileall, web typecheck/vitest/build, desktop typecheck/vitest/build) |
| visual_smoke_recorded | **true** — web dashboard served from the isolated copy; fr rendered and DOM-verified |
| human_review | **false** — E0/E1 automated; E2 AI-assisted bilingual review (host agent), not native human |
| full_product_localization_claim | **false** |

## Generation

All all 3,683 segments carry quality_claim=host_agent_generated / generation_mode=host_agent_import; report generation.quality_claim=host_agent_generated. No external provider API was called; no credentials were used or exposed.

## QA summary

| Surface | Segments | QA | Semantic flags |
| --- | --- | --- | --- |
| YAML/CLI/Gateway | 351 | pass (0/0) | 0 |
| Web dashboard | 709 | pass (0/0) | 0 |
| Desktop | 2623 | pass (0/0) | 0 |
| **Total** | **3683** | — | — |

## Reference comparison

Official French resources were hidden during generation and revealed only after (`prepare.py reference`). See [official-reference-comparison.json](official-reference-comparison.json):
YAML: 0 missing keys both ways; 217 identical values vs official; staged has 22 untranslated-English segments (retained technical terms, classified); official has 58 stragglers.
Web: staged covers the en.ts contract; official fr.ts contains additional keys absent from en.ts (treated as reference only, not ground truth).
Desktop: no official French catalog exists at the pinned commit.

## Delivery claim

**Catalog localization proven** (YAML + Web + Desktop). **Full-product localization not proven**: hardcoded frontend strings, dynamic/gateway metadata, and generated content remain out of catalog scope (see coverage audit and visual smoke findings).
