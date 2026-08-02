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
