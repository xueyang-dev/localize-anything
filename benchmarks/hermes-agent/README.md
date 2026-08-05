# Hermes Agent mixed-surface localization benchmark

**Mixed-surface Web/Desktop/CLI localization pressure test** pinned to
[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
commit `91937a6dc3ffbbe2f3be91a500f0ecf962c4cf53` (v0.20.0, 2026-08-03).

This is an **experimental** benchmark, not a stable production benchmark.

## Why Hermes is a mixed-surface benchmark

Hermes localizes four very different surfaces from one English source:

| Surface | Shape | Adapter |
| --- | --- | --- |
| CLI / Gateway | `locales/<lang>.yaml`, nested YAML flattened to dotted keys, `{placeholder}` `str.format` tokens, English fallback, parity tests | `core.yaml-toml` |
| Web Dashboard | `web/src/i18n/<lang>.ts` typed object catalogs with `defineLocale` partial overrides, RTL for `ar` | `core.typescript-locale` |
| Desktop | `apps/desktop/src/i18n/<lang>.ts` full typed catalogs with 318 function-valued messages, template literals and `${...}` expressions | `core.typescript-locale` |
| Documentation | Docusaurus `website/` with `en` + `zh-Hans`, 317 translated docs | inventoried only |

Out-of-catalog surfaces (hardcoded JSX strings, plugin manifests, skill
frontmatter, gateway/server metadata, model output, logs, tool output,
images/audio/video) are **inventoried, not silently translated**.

## Tracks

- `controlled`: English is canonical source truth; official French
  (`locales/fr.yaml`, `web/src/i18n/fr.ts`) is hidden from the generation
  environment (`prepare.py blind`) and revealed only after generation as a
  comparison reference, never as generation input and never as unique ground
  truth.
- `agent-system` (`reference_policy: style_only`): reviewed French resources
  from one surface may supply glossary/style evidence to another surface;
  the English source remains source truth. `tm_assisted` is documented but
  was not exercised in the engineering run.

The tracks are never combined into one score.

## Generation modes

- **Import flow (preferred when a real provider is available):** the run
  scripts write complete handoff artifacts under `runs/<surface>/prompts/`
  (source segments, semantic batches, instructions). Generate translations
  externally and import them with `--mode import --import-segments FILE`.
  The import path validates segment ids and never invents responses.
- **Engineering fallback:** with no provider credentials in the approved
  environment, the run uses a conservative local draft labeled
  `quality_claim: engineering_fixture_only`: an identity copy plus a small
  curated French slice that proves extraction, staging, QA, and build
  plumbing. **None of it counts as translation-quality evidence.**

The real-translation iteration (separate PR) ran the import flow with
host-agent-produced French for all 3,683 segments
(`quality_claim: host_agent_generated`, `generation_mode: host_agent_import`;
no provider API called). The final reports under `reports/` reflect that run:
`real-generation-metadata.json`, `e2-review-summary.*`, `e2-review-sheet.csv`,
`terminology-adjudication.*`, `official-reference-comparison.json`,
`visual-smoke-report.*`, `real-evidence-verification.*`. E2 review is
AI-assisted bilingual review, not native human review.

### E3 native-speaker review package

An E3 (native-language human review) round is prepared under
`evidence/e3-review/`:

- `e3-review-sheet.csv` / `e3-review-sheet.md` — deterministic review sheet
  (508 rows): all 180 E2 rows, all 203 retained identity strings, all 20
  terminology decisions, and 120 additional translated non-identity rows
  (40 per surface), deduplicated by `segment_id` with selection reasons.
- `e3-review-schema.json` — row schema; `e3-review-manifest.json` — counts,
  hashes, sampling method (tiered, segment-id-sorted stride; no RNG).
- `REVIEWER-INSTRUCTIONS-FR.md` — French instructions for the native reviewer.
- `COORDINATOR-INSTRUCTIONS.md` — handoff/import workflow.
- `reviewer-metadata-template.json` — attestation (native language, region,
  date, domain, AI assistance, conflict of interest, consent). No personal
  identifying information is collected.

Reproduce the package with:

```bash
../../.venv/bin/python build_e3_review.py
../../.venv/bin/python validate_e3_review.py
```

Status: **E3 review package prepared; human review pending.** The package
contains no fabricated reviewer decisions (`human_review_present = false`).
When a qualifying native French speaker returns the completed CSV plus filled
metadata, import it with `import_e3_review.py` and follow the Mode B workflow
in `evidence/e3-review/COORDINATOR-INSTRUCTIONS.md`.

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[yaml]"

cd benchmarks/hermes-agent

../../.venv/bin/python prepare.py source
../../.venv/bin/python prepare.py blind
../../.venv/bin/python verify_source.py
../../.venv/bin/python audit.py
../../.venv/bin/python run_yaml_benchmark.py \
  --mode import \
  --import-segments evidence/real-imports/yaml.jsonl
../../.venv/bin/python run_typescript_catalog_benchmark.py \
  --surface web \
  --mode import \
  --import-segments evidence/real-imports/web.jsonl
../../.venv/bin/python run_typescript_catalog_benchmark.py \
  --surface desktop \
  --mode import \
  --import-segments evidence/real-imports/desktop.jsonl
../../.venv/bin/python prepare.py reference
# Re-run the surface scripts so reports attach the revealed reference comparison.
../../.venv/bin/python run_yaml_benchmark.py --mode import --import-segments evidence/real-imports/yaml.jsonl
../../.venv/bin/python run_typescript_catalog_benchmark.py --surface web --mode import --import-segments evidence/real-imports/web.jsonl
../../.venv/bin/python run_typescript_catalog_benchmark.py --surface desktop --mode import --import-segments evidence/real-imports/desktop.jsonl
# Identity-target approval is already committed in
# reports/retained-string-adjudication.json (separate from candidate
# classifications) and is loaded automatically. Only a fresh review cycle
# needs: run_retention_adjudication.py --collect --force, then fill the CSV
# decision columns, then run_retention_adjudication.py --decisions FILE.
../../.venv/bin/python prepare.py copy
../../.venv/bin/python run_build_validation.py
../../.venv/bin/python incremental.py
../../.venv/bin/python run_coverage_audit.py
../../.venv/bin/python run_real_evidence_verification.py
../../.venv/bin/python verify_results.py
```

`work/` (source checkout, blind/staging/copy workspaces, test venvs) and
`runs/` (segments, prompts, generated files, QA artifacts) are git-ignored;
`reports/` holds compact aggregate evidence and `evidence/real-imports/`
holds the canonical committed import JSONL files plus their manifest.

## Adapter capability boundaries (`core.typescript-locale`)

- Parses the constrained locale-catalog shape (object literals of strings,
  template literals, string arrays, arrow functions) with a real tokenizer,
  and **fails closed** on any unsupported construct.
- Rebuilds by replacing only translated literal spans: keys, imports,
  exports, comments, function signatures, `${...}` expressions, identifiers
  and all other syntax are byte-preserved unless a literal changes.
- Template `${{...}}` expressions are protected: they must appear in the
  target in the same count and order; deterministic QA blocks drift.
- Changing plural logic or expression structure requires editing the
  function body outside the adapter contract.

## Evidence levels

Evidence levels: E0 (structural) + E1 (automated linguistic diagnostics) +
E2 (AI-assisted bilingual review — not native human review). **E3** is a
native-language human review (a real native French speaker judging
naturalness, fluency, register, terminology suitability, and retained-English
acceptability); the E3 review package is prepared but human review is
pending. **E4** is professional localization review and has not run. Catalog
parity is **not** full product localization: see `reports/coverage-audit.json`
for the delivery decision and coverage gaps.
