# Coordinator instructions — Hermes French E3 review

## Goal of this package

This directory contains the deterministic review package for the **E3
native-speaker** round of the Hermes Agent French localization. E3 is review
by a real native speaker of French; it is distinct from E2 (AI-assisted
bilingual review) and E4 (professional localization review).

## Reviewer qualification

The reviewer must truthfully attest in `reviewer-metadata-template.json` that
French is one of their native languages. They do not need to be a professional
translator (that would be E4). No personal identifying information may be
collected without explicit consent; the template intentionally avoids names,
addresses, phone numbers, emails, employers, or government IDs.

## Files

- `e3-review-sheet.csv` — the review sheet (508 rows). Reviewer fills
  `review_status`, `native_quality_rating`, `reviewer_target_fr`,
  `reviewer_note`, `terminology_decision`, `needs_bilingual_check`. They must
  NOT fill `user_decision` or `final_accepted_target`.
- `e3-review-sheet.md` — human-readable rendering of the same sheet.
- `e3-review-schema.json` — JSON Schema of one review row.
- `e3-review-manifest.json` — counts, hashes, sampling method.
- `e3-review-package-summary.json` — build summary of this package.
- `REVIEWER-INSTRUCTIONS-FR.md` — instructions for the French-speaking
  reviewer.
- `reviewer-metadata-template.json` — reviewer attestation template.

## Reviewer workflow

1. Send `e3-review-sheet.csv` + `reviewer-metadata-template.json` +
   `REVIEWER-INSTRUCTIONS-FR.md` to the reviewer.
2. The reviewer returns a completed CSV and filled metadata JSON.
3. Validate with `python validate_e3_review.py --decisions <file>` (see
   the benchmark README).
4. Import with `python import_e3_review.py --decisions <file>
   --metadata <file>` (Mode B) — this preserves the original submission,
   updates canonical imports, and regenerates E3 evidence reports.

## Status boundary

Until a completed native-speaker review is imported, this package is
**handoff-only** (Mode A): `human_review_present = false`,
`overall_e3_status = awaiting_review`. Do not claim E3 completion.
