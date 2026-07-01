# Public Claim Reconciliation

This note records the public documentation boundary after the Release Audit /
Public Claims Boundary seed.

## Source Of Truth

Public-facing claims should be checked against the release audit artifacts when
they exist for a run:

- `release-readiness-audit.json`
- `public-claims-report.json`
- `public-claims-report.md`
- `non-claims.md`
- `release-blockers.json`
- `release-evidence-manifest.json`

The protocol examples for these artifacts are conservative examples, not a
release candidate. A release audit artifact can classify claims and blockers;
it does not create a release, tag, or stable product claim by itself.

## Current Public Boundary

Stable public claims are limited to the released baseline and documented
regression evidence: staged delivery, deterministic structural QA, explicit
apply planning/confirmation, Workbench UI wiring, and released adapter behavior
within documented format boundaries.

Implemented architecture seeds may be described as seeds. They include evidence
spine gates, document evidence, personal knowledge, provider evidence, locale
capability, translation provenance, benchmark comparison, workflow hardening,
readiness authorization, and release audit. A seed is not a production-stable
capability until a release audit, benchmark or real-project evidence, review
evidence, documentation audit, and public claim review support promotion.

Experimental capabilities must remain clearly scoped and opt-in. Unsupported
capabilities must remain non-claims.

## Claims To Keep Forbidden Unless Evidence Supports Them

- provider-backed quality
- knowledge-backed quality
- locale-complete support
- full-product localization
- production-ready quality
- zero residual source-language text
- DOCX layout or rendered-page fidelity
- factual truth verification
- automatic destructive apply or apply readiness without current authorization

## README Safe Path

The public quickstart should steer users through:

```text
inspect -> preflight -> generate/import -> review -> readiness-check -> deliver/apply-plan
```

Drafts, benchmark output, external provider intake, knowledge pack selection,
locale reports, and provenance reports are evidence. They are not acceptance,
signoff, or apply authorization by themselves.
