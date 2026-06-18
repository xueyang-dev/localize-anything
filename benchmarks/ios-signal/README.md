# Signal iOS Localizable.strings Benchmark

This benchmark exercises the v0.2 iOS source-project slice against Signal-iOS,
a well-known open-source iOS messaging app. It validates that Localize Anything
can produce a staged drop-in `.lproj` language resource for a real project
layout without editing source code in place or changing the Xcode project.

The benchmark downloads only the pinned upstream
`Signal/translations/en.lproj/Localizable.strings` file. It does not commit or
vendor Signal-iOS source files.

Run:

```bash
python3 benchmarks/ios-signal/run.py \
  benchmarks/ios-signal/work/latest
```

To hand work to a host agent instead of using the synthetic verification draft:

```bash
python3 benchmarks/ios-signal/run.py \
  benchmarks/ios-signal/work/latest \
  --handoff-only
```

The host agent reads `evidence/generation-handoff.json`, writes each generated
batch to the listed JSONL path, then reruns the benchmark with `--keep-existing`
and `--generated-dir <dir>`.

The default run builds provider-agnostic draft requests for each work packet,
then uses a synthetic target draft that preserves source text and placeholders
with a target-locale prefix. That synthetic draft is only evidence for draft
contract validation, adapter staging, QA, packaging, and dashboard behavior. It
is not translation-quality evidence.

The pinned source currently extracts 3486 segments into 175 default batches and
should finish with iOS QA status `pass` and zero warnings.

Expected generated target path:

```text
Signal/translations/zh-Hans.lproj/Localizable.strings
```

## Verification Focus

- Detect the iOS strings adapter on a real `.lproj` project path.
- Extract iOS `.strings` key/value resources into protocol segments.
- Create host-agent draft requests from work packets.
- Validate generated segment JSONL before staging output files.
- Stage the target locale file instead of mutating the source workspace.
- Produce a delivery snapshot and developer/translator dashboard.

## Licensing

The benchmark runner and metadata use this repository's MIT license. Downloaded
Signal-iOS source files retain their upstream AGPL-3.0 license and remain in
the ignored benchmark work directory.
