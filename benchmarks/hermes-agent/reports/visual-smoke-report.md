# Hermes Agent Visual Smoke Report

Method: `hermes dashboard` from the isolated copy (temp HOME, `web_dist` rebuilt with the staged `fr.ts`), driven in the in-app browser. Original smoke on 2026-08-04 (port 9123); **re-verified on 2026-08-05 (port 9124) after the repaired pipeline rerun** — /sessions and /config French markers re-confirmed via DOM, known hardcoded English strings unchanged.

## Schema

| Field | Value |
| --- | --- |
| runtime_smoke_recorded | true |
| dom_text_verified | true |
| screenshots_captured | true |
| screenshots_reviewed | false |
| visual_layout_review_completed | false |
| screenshots_durable | false |

Screenshots are **non-durable local artifacts** under the ignored `work/visual-smoke/`; they are not committed. Pixel-level visual layout QA (clipping/overflow/alignment) was not completed.

## Screens

| Page | Locale | Screenshot (non-durable) | Result |
| --- | --- | --- | --- |
| /sessions | en | `work/visual-smoke/dashboard-landing-en.png` | baseline |
| /sessions | fr | `work/visual-smoke/dashboard-sessions-fr.png` | French nav, gateway status, buttons, radios |
| /config | fr | `work/visual-smoke/dashboard-config-fr.png` | French page title, actions, section labels |
| /models | fr | `work/visual-smoke/dashboard-models-fr.png` | French header; several hardcoded English strings |

## Findings

- **info** — Catalog-covered strings render in French at runtime (DOM-verified).
- **low** — Hardcoded English remains: nav `Sessions`/`Files`/`System`/`Achievements`; sessions page `Prune old sessions`, `Import exported sessions`, `Total`, `Active in store`, `Archived`, `Messages`, `Any chat source`; models page `Model Settings`, `applies to new sessions`, `Main model`, `Auxiliary tasks`, `Change`. These are out-of-catalog hardcoded frontend strings (see `hardcoded-string-findings.json`).
- **info** — No console errors captured.
- **info** — Protected API flows not exercised (gateway Off).

## Limitations

- Desktop (Electron) app was not launched interactively; desktop `fr.ts` evidence = typecheck + vitest + production build.
- Gateway-dependent views (chat, live metadata) not visually exercised.
- Screenshots captured but not pixel-reviewed; text evidence from DOM snapshots.

**Delivery claim:** Web runtime DOM localization verified; visual layout quality not reviewed; full-product localization not claimed.
