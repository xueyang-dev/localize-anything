# AntennaPod Android Strings Benchmark

This benchmark exercises the v0.2 Android source-project slice against
AntennaPod, a well-known open-source Android podcast client. It validates that
Localize Anything can produce a staged drop-in language resource for a real
project layout without repackaging an APK or editing source code in place.

The benchmark downloads only the pinned upstream
`ui/i18n/src/main/res/values/strings.xml` file. It does not commit or vendor
AntennaPod source files.

Run:

```bash
python3 benchmarks/android-antennapod/run.py \
  benchmarks/android-antennapod/work/latest
```

To hand work to a host agent instead of using the synthetic verification draft:

```bash
python3 benchmarks/android-antennapod/run.py \
  benchmarks/android-antennapod/work/latest \
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

The pinned source currently extracts 869 segments into 44 default batches and
should finish with Android QA status `pass` and zero warnings.

Expected generated target path:

```text
ui/i18n/src/main/res/values-zh-rCN/strings.xml
```

## Verification Focus

- Detect the Android strings adapter on a real project path.
- Extract Android `<string>`, `<string-array>`, and `<plurals>` resources into
  protocol segments.
- Create host-agent draft requests from work packets.
- Validate generated segment JSONL before staging output files.
- Keep `translatable="false"` resources out of the generated target, with QA
  evidence for skipped resources.
- Stage the target locale file instead of mutating the source workspace.
- Produce a delivery snapshot and developer/translator dashboard.

## Licensing

The benchmark runner and metadata use this repository's MIT license. Downloaded
AntennaPod source files retain their upstream GPL-3.0 license and remain in the
ignored benchmark work directory.
