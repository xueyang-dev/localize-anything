# Hermes Agent Visual Smoke Report

Method: `hermes dashboard` from the isolated copy (temp HOME, `web_dist` rebuilt with the staged `fr.ts`), driven in the in-app browser at `http://127.0.0.1:9123`.

## Screens

| Page | Locale | Screenshot | Result |
| --- | --- | --- | --- |
| /sessions | en | [dashboard-landing-en.png](visual-smoke/dashboard-landing-en.png) | baseline |
| /sessions | fr | [dashboard-sessions-fr.png](visual-smoke/dashboard-sessions-fr.png) | French nav, gateway status, buttons, radios |
| /config | fr | [dashboard-config-fr.png](visual-smoke/dashboard-config-fr.png) | French page title, actions, section labels |
| /models | fr | [dashboard-models-fr.png](visual-smoke/dashboard-models-fr.png) | French header; several hardcoded English strings |

## Findings

- **info** — Catalog-covered strings render in French at runtime (DOM-verified).
- **low** — Hardcoded English remains: nav `Sessions`/`Files`/`System`/`Achievements`; sessions page `Prune old sessions`, `Import exported sessions`, `Total`, `Active in store`, `Archived`, `Messages`, `Any chat source`; models page `Model Settings`, `applies to new sessions`, `Main model`, `Auxiliary tasks`, `Change`. These are out-of-catalog hardcoded frontend strings (see `hardcoded-string-findings.json`).
- **info** — No console errors captured.
- **info** — Protected API flows not exercised (gateway Off).

## Limitations

- Desktop (Electron) app was not launched interactively; desktop `fr.ts` evidence = typecheck + vitest + production build.
- Gateway-dependent views (chat, live metadata) not visually exercised.
- Screenshots are artifacts; text evidence from DOM snapshots.

**Delivery claim:** web catalog localization visually verified — full-product localization is not claimed.
