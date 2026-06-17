# The South Guard Blind Benchmark

This benchmark exercises the v0.1 vertical slice with the official Battle for
Wesnoth repository. It localizes The South Guard from `en-US` to `zh-CN` using
the campaign POT plus WML context.

## Blind Boundary

Generation and evaluation are separate phases. The source workspace contains
the pinned POT, campaign files, and upstream license only. It must not contain
the existing `zh_CN.po`, a derived TM, or excerpts from that translation.

Prepare and verify a source workspace:

```bash
python3 benchmarks/wesnoth-south-guard/prepare.py source \
  benchmarks/wesnoth-south-guard/work
python3 benchmarks/wesnoth-south-guard/verify.py source \
  benchmarks/wesnoth-south-guard/work
```

Run localization in a sandbox that can access `work/source` but not an
evaluation reference. Record all effective variables using
`run-metadata.template.json`.

After generation, prepare the human reference in a separate directory:

```bash
python3 benchmarks/wesnoth-south-guard/prepare.py reference \
  benchmarks/wesnoth-south-guard/work \
  --generated-po /path/to/generated/zh_CN.po
```

The existing translation is optional evaluation evidence, not source truth and
not a sole quality standard. Do not feed it back into context, glossary, or TM
during the generation run.

## Verification Levels

- E0: deterministic parse, coverage, placeholder, plural, and round-trip checks.
- E1: automated linguistic diagnostics with tool and version disclosure.
- E2: bilingual reviewer.
- E3: target-language native reviewer.
- E4: professional game localizer.

A v0.1 engineering run may stop at E0/E1, but its quality claims must state
that no human review was performed.

## Licensing

The benchmark definition and runner code use this repository's MIT license.
Downloaded Wesnoth files retain their upstream GPL-2.0-or-later and asset
licenses. Generated workspaces and references are ignored by this repository.
