# IceCubesApp String Catalog Benchmark

This benchmark exercises the v0.2 Xcode String Catalog slice against
IceCubesApp, a well-known open-source iOS Mastodon client. It validates that
Localize Anything can update a staged `.xcstrings` copy for a real project
layout without editing source code in place or changing the Xcode project.

The benchmark downloads only the pinned upstream
`IceCubesApp/Resources/Localization/Localizable.xcstrings` file. It does not
commit or vendor IceCubesApp source files.

Run:

```bash
python3 benchmarks/ios-icecubes-xcstrings/run.py \
  benchmarks/ios-icecubes-xcstrings/work/latest
```

To hand work to a host agent instead of using the synthetic verification draft:

```bash
python3 benchmarks/ios-icecubes-xcstrings/run.py \
  benchmarks/ios-icecubes-xcstrings/work/latest \
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

The pinned source currently extracts 747 segments into 38 default batches and
should finish with String Catalog QA status `pass` and zero warnings.

Expected generated target path:

```text
IceCubesApp/Resources/Localization/Localizable.xcstrings
```

## Verification Focus

- Detect the String Catalog adapter on a real `.xcstrings` project path.
- Extract source-language `stringUnit` values and variation leaves into
  protocol segments.
- Create host-agent draft requests from work packets.
- Validate generated segment JSONL before staging output files.
- Stage the updated catalog copy instead of mutating the source workspace.
- Produce a delivery snapshot and developer/translator dashboard.

## Licensing

The benchmark runner and metadata use this repository's MIT license. Downloaded
IceCubesApp source files retain their upstream AGPL-3.0 license and remain in
the ignored benchmark work directory.
