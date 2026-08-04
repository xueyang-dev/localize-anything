# Hermes Agent benchmark plan (91937a6dc3ff)

- Target locale: **fr** (official YAML and Web French catalogs exist; Desktop French does not).
- Tracks: controlled (blind French references) and agent-system (style_only reference policy).
- Generation: engineering fixture only (identity + curated slice); import flow provided for real providers.
- Surfaces: YAML CLI/gateway catalogs, Web TypeScript catalogs, Desktop TypeScript catalogs, Docusaurus documentation.
- QA: deterministic parity (keys, placeholders, template expressions, signatures), semantic E1 flags, terminology, incremental, apply-to-copy, builds.
- Deliverable decision: catalog localization proven; full product localization NOT claimed.
