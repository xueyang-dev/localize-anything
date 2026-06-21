# AntennaPod Android Smoke Test

## Purpose

This smoke test exercises Localize Anything against a real Android project. It
is intended to verify:

- project inspection and Android resource detection;
- Android string extraction, staging, deterministic QA, and delivery evidence;
- tracked source files remain unchanged unless an apply command is explicitly
  approved and run;
- existing target-locale resources do not leak into blind generation-facing
  artifacts;
- source-set and resource-qualifier routing is visible in inspection evidence;
- review sheets and deterministic risk metadata appear in run artifacts.

[AntennaPod](https://github.com/AntennaPod/AntennaPod) is an external open-source
project. Localize Anything does not vendor AntennaPod, its translations, or
generated smoke-test outputs. Clone AntennaPod separately into a temporary
directory, and keep all evidence outside both repositories or in an ignored
output directory.

## Prerequisites

Run the smoke test from a Localize Anything source checkout with its environment
activated and dependencies installed:

```bash
python -m pip install -e ".[yaml]"
python -m runtime.localize_anything --help
```

The current CLI provides `inspect` and `localize-run`. It does not provide
commands named `detect` or general-purpose `inventory`; do not use those names
in automation.

## Clone and pin AntennaPod

From outside this repository:

```bash
tmpdir=$(mktemp -d)
cd "$tmpdir"

git clone https://github.com/AntennaPod/AntennaPod.git
cd AntennaPod
git rev-parse HEAD
```

Record the commit hash. Reuse that exact commit when comparing smoke-test runs.

## Read-only inspection

From the Localize Anything repository, run the helper with the external clone
and an output directory outside both source trees:

```bash
scripts/smoke-antennapod.sh \
  "$tmpdir/AntennaPod" \
  "$tmpdir/localize-anything-evidence"
```

The helper records both repository commits, writes `inspection.json`, validates
the Localize Anything protocol and contracts, and checks that AntennaPod's Git
status did not change. It does not run generation, staging, apply, or any
network translation provider.

The equivalent inspection command is:

```bash
python -m runtime.localize_anything inspect \
  "$tmpdir/AntennaPod" \
  --output "$tmpdir/localize-anything-evidence/inspection.json"
```

`inspection.json` includes `android_generation_source_files`,
`android_locale_reference_files`, and per-file routing metadata such as
`android_source_set`, `android_res_dir`, and `android_qualifiers`. These fields
are the source-detection and routing inventory for this smoke test.

## Isolated full pipeline

This phase is manual because `localize-run` creates Localize Anything project
state under `.localize-anything/` in the target checkout. Run it only against
the disposable AntennaPod clone. The command below uses synthetic drafts, keeps
delivery outputs outside AntennaPod, selects blind mode, and never invokes an
apply command:

The full pipeline was not executed against AntennaPod as part of this
documentation PR. Running and reviewing the command below is the manual smoke
test, not evidence claimed by this document.

```bash
evidence="$tmpdir/localize-anything-evidence"

python -m runtime.localize_anything localize-run \
  "$tmpdir/AntennaPod" \
  --source-locale en-US \
  --target-locale zh-CN \
  --output-root "$evidence/runs" \
  --run-id antennapod-blind-smoke \
  --synthetic-draft \
  --operating-mode blind_benchmark \
  --reference-policy blind \
  --workflow-depth standard \
  --output "$evidence/run-summary.json"
```

`localize-run` produces staged files, deterministic QA, a review sheet,
delivery manifests, and a delivery dashboard under the external output root.
It does not call `apply-delivery`. Do not run `apply-delivery` as part of this
smoke test.

Inspect the artifact paths without copying their contents into this repository:

```bash
python - "$evidence/run-summary.json" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
print("mode:", summary.get("operating_mode"))
print("reference policy:", summary.get("reference_policy"))
print("source files:", len(summary.get("source_files", [])))
for name, path in sorted(summary.get("artifacts", {}).items()):
    print(f"{name}: {path}")
PY
```

Confirm risk metadata is present by listing files that contain its field name:

```bash
grep -R -l '"ui_risk_classification"' "$evidence/runs"
```

For blind-reference isolation, select a distinctive existing `zh-CN` target
string locally and verify that it does not occur in generation-facing work
packets, draft requests, prompts, handoff files, or generated JSONL. Do not paste
private translations into shell history or public reports. Treat any match as a
failed smoke test.

Finally, verify tracked AntennaPod files remain unchanged:

```bash
git -C "$tmpdir/AntennaPod" diff --exit-code
git -C "$tmpdir/AntennaPod" status --short --untracked-files=no
```

The `.localize-anything/` directory created by the manual full pipeline is local
project state in the disposable clone. Delete the temporary directory when the
evidence has been reviewed.

## Evidence checklist

- [ ] AntennaPod commit hash recorded
- [ ] Localize Anything commit hash recorded
- [ ] Detection completed
- [ ] Android resource inventory produced
- [ ] Existing target locale resources excluded from blind generation-facing artifacts
- [ ] Source sets / qualifiers summarized
- [ ] Review sheet generated
- [ ] Risk metadata present
- [ ] No source files modified
- [ ] Generated outputs stored outside source tree or in ignored output dir
- [ ] All validation gates passed

## Validation gates

Run the repository regression suite before treating smoke-test evidence as
reviewable:

```bash
python -m unittest discover -s tests -v
python -m runtime.localize_anything validate-protocol
python -m runtime.localize_anything validate-contracts
python -m compileall -q runtime benchmarks
python benchmarks/v022-android-resource-reliability/run.py
python benchmarks/v022-android-resource-reliability/source_sets.py
python benchmarks/v022-android-resource-reliability/risk_classification.py
python benchmarks/v021-mode-system/run.py
```

## Non-goals

- This smoke test does not evaluate translation quality.
- This smoke test does not apply changes to AntennaPod by default.
- This smoke test does not claim full Android project localization.
- This smoke test does not test layout, drawable, or asset localization.
- This smoke test does not vendor AntennaPod or generated outputs.
