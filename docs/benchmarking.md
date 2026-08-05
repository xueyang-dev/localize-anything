# Benchmarking

## Public Benchmark

Use The Battle for Wesnoth, The South Guard campaign, with a pinned upstream commit. Generate `zh-CN` from the canonical English source while hiding existing Chinese translations from the generation environment.

Evaluate existing human translations only after generation. Treat them as references, not unique ground truth.

## Private Stress Test

Disco Elysium may be used only as a local, user-owned stress test. Do not commit extracted dialogue, translations, memory assets, or other copyrighted game data. Publish only aggregate, non-reconstructive results.

## Experimental Real-Project Slices

Vorssaint may be used as a private experimental benchmark candidate for a
`code_embedded_catalog` surface:

```text
Swift
typed constructor catalog
custom project localization architecture
```

Do not publish it as "Swift support." The benchmark target is the specific
catalog structure and the project-local adapter contract.

Benchmark claims must distinguish:

- parser correctness: detection, inventory, extraction, and validation on the catalog structure;
- runtime gate correctness: capability gate, artifact freshness, payload symlink rejection, and execution evidence;
- linguistic quality: E1-E4 review evidence only;
- end-to-end delivery: apply, build, launch, and visible-UI evidence.

E0 inspect verifies surface detection, locale inventory, field coverage, stable IDs,
source hashes, deterministic repeatability, and no source mutation. E0 rebuild, if
later accepted, verifies staging only, syntax parse, interpolation and escape
preservation, source diff scope, the project build script, and unchanged original
source. A build pass is not a full macOS or iOS app localization pass.

## Registered mixed-surface case: Hermes Agent

`benchmarks/hermes-agent/` is an experimental **mixed-surface Web/Desktop/CLI
localization pressure test**, pinned to
[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
commit `91937a6dc3ffbbe2f3be91a500f0ecf962c4cf53` (v0.20.0).

- surfaces: CLI/gateway YAML catalogs, Web TypeScript catalogs, Desktop
  TypeScript catalogs (318 function-valued messages), Docusaurus docs
  (inventoried only);
- tracks: controlled (blind `fr`, official French hidden during generation)
  and agent-system (`reference_policy: style_only`, `tm_assisted` documented
  but not exercised);
- adapter work: `core.typescript-locale` parser-based adapter with contract
  fixtures and tests;
- generation: engineering fixture only (`quality_claim:
  engineering_fixture_only`) plus a provider-agnostic import flow -- no
  translation-quality claims;
- evidence: E0 structural + E1 automated review; Desktop and Web
  typecheck/test/build pass with staged catalogs applied to an isolated copy;
  visual QA and packaging not run;
- known gaps: official Desktop French does not exist; official Web French
  omits optional keys; official YAML French leaves 58 keys in English.

Catalog parity is proven for the staged catalogs; full product localization
is explicitly NOT claimed. See `benchmarks/hermes-agent/README.md` for
reproduction commands.

### Real-translation evidence iteration (separate PR)

A second iteration adds genuine French translations through the same framework
(`--mode import`, provider-agnostic handoff), so the engineering-fixture caveat
above no longer applies to the final runs:

- generation: host-agent-produced translations imported for all 3,683 segments
  (YAML 351, Web 709, Desktop 2,623), labeled `quality_claim:
  host_agent_generated` / `generation_mode: host_agent_import`; no provider API
  was called and no credentials were used; the exact import inputs are
  committed under `benchmarks/hermes-agent/evidence/real-imports/` with a
  SHA-256 manifest, so the run is reproducible without regenerating anything;
- E1: 0 semantic flags; identity targets (target == source) are only cleared
  through the separate retention adjudication
  (`reports/retained-string-adjudication.*`, reviewer type
  `AI-assisted bilingual review`) — an imported candidate classification
  alone never suppresses the untranslated-English finding;
- E2: 180-segment risk-weighted bilingual review (`reviewer_type:
  AI-assisted bilingual review` — not native human review), 2 corrections
  applied and rerun, 0 blocking;
- E3: native-language human review (a real native French speaker) is the next
  round and has now **completed**: a deterministic package
  (`benchmarks/hermes-agent/evidence/e3-review/`) was reviewed by a native
  French speaker (anonymized `fr-native-01`) covering all 508 rows (180 E2 +
  203 identity + 20 terminology + 120 naturalness); 10 human revisions were
  applied to the canonical imports; 203/203 identity retentions were
  independently confirmed; the six round-1 bilingual-check questions were
  resolved in round 2 (status `reviewed_complete`). E4 (professional
  localization review) has not run, and `user_accepted` is not claimed for
  any reviewed segment until explicit user sign-off.
- terminology adjudication for 20 cross-surface terms (18 intentional,
  2 context-dependent, 0 unresolved/errors);
- build validation on the isolated copy: Hermes i18n parity tests, Python
  compileall, Web typecheck/vitest/build, Desktop typecheck/vitest/build —
  8/8 pass;
- runtime DOM smoke: the Web dashboard was served from the isolated copy and
  the `fr` locale rendered live (/sessions, /config, /models; DOM-verified).
  Screenshots are non-durable local artifacts under the ignored
  `work/visual-smoke/`; pixel-level visual layout review was **not**
  completed. Desktop Electron and gateway-dependent views were not launched;
- evidence artifacts live in `benchmarks/hermes-agent/reports/`
  (`real-generation-*`, `e2-review-*`, `terminology-adjudication.*`,
  `retained-string-adjudication.*`, `official-reference-comparison.json`,
  `visual-smoke-report.*`, `real-evidence-verification.*`).

Hardcoded frontend strings, dynamic gateway metadata, and generated content
remain outside the catalog contract (see `hardcoded-string-findings.json` and
the visual smoke findings); full-product localization is still NOT claimed.

## Tracks

- `controlled`: Keep source, skill, adapter, context budget, workflow depth, and tools as consistent as possible.
- `agent-system`: Allow each runtime to use its native tools and record the resulting capability differences.

Do not combine the tracks into one leaderboard.

## Metrics

Measure round-trip correctness, structural QA, cross-batch consistency, context efficiency, incremental performance, and human review outcomes. Do not publish one synthetic quality score.

## Evidence Levels

- `E0`: Structural evaluation only
- `E1`: Automated linguistic diagnostics
- `E2`: Bilingual reviewer
- `E3`: Native-language reviewer
- `E4`: Professional localization reviewer

Record runtime, agent, model, tool versions, adapter versions, source commit, target locale, context budget, privacy mode, human intervention, and whether measurements are exact or estimated.
