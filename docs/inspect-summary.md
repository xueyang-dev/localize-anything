# Inspect Summary

`inspect` is the safest first command to run against a real project. It scans
the project for supported localization resources and reports routing evidence
before any generation, staging, packaging, or apply step.

Inspection is read-only. It does not create `.localize-anything/` project state,
does not generate translations, does not stage files, and does not apply
changes.

## Commands

Write the raw inspection JSON to stdout:

```bash
python -m runtime.localize_anything inspect --project /path/to/project
```

Write a compact JSON and Markdown summary:

```bash
python -m runtime.localize_anything inspect \
  --project /path/to/project \
  --output-dir /tmp/la-inspect
```

The output directory receives:

- `inspect-summary.json`
- `inspect-summary.md`

For compatibility, the positional form still works:

```bash
python -m runtime.localize_anything inspect /path/to/project
```

## Summary Contents

The summary includes only information available from read-only inspection:

- project path;
- detected project type;
- primary adapter and adapter file counts;
- supported resource files;
- Android source sets, qualifiers, generation source files, and target-locale
  reference files when Android resources are detected;
- Android resource type counts for `string`, `string-array`, and `plurals`
  when resource XML can be parsed;
- unprocessed non-text asset count;
- skipped or ignored path counts;
- preflight assessment;
- whether risk/review metadata is available during inspect.

If information is not available during read-only inspection, the summary marks
it unavailable instead of inventing a value. For example, segment-level risk and
review metadata is not available from `inspect` because no extraction,
generation, or review artifact creation has run.

## Source Safety

By default, `inspect` writes nothing to the source project. When `--output-dir`
is provided, only the requested summary files are written to that directory.
`inspect --output-dir` refuses paths inside the inspected source project so
summary artifacts do not get mixed into a real checkout.

Use an output directory outside real project checkouts when collecting evidence
for public smoke tests:

```bash
python -m runtime.localize_anything inspect \
  --project /tmp/AntennaPod \
  --output-dir /tmp/localize-anything-antennapod-inspect
```

After inspection, verify the project source is unchanged with the source
control tool used by that project, for example:

```bash
git -C /tmp/AntennaPod status --short
git -C /tmp/AntennaPod diff --exit-code
```

## Boundaries

`inspect` does not validate translation quality, provider-backed generation,
staging output, delivery packaging, apply behavior, Android layouts, drawables,
assets, Gradle edits, APK decompilation, or full production localization of an
external app. Use later workflow steps only after reviewing the inspection
summary and choosing an explicit non-destructive output location.
