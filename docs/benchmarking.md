# Benchmarking

## Public Benchmark

Use The Battle for Wesnoth, The South Guard campaign, with a pinned upstream commit. Generate `zh-CN` from the canonical English source while hiding existing Chinese translations from the generation environment.

Evaluate existing human translations only after generation. Treat them as references, not unique ground truth.

## Private Stress Test

Disco Elysium may be used only as a local, user-owned stress test. Do not commit extracted dialogue, translations, memory assets, or other copyrighted game data. Publish only aggregate, non-reconstructive results.

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
