# Android Real-Project Stress Matrix

This document summarizes public-safe, non-destructive stress-test evidence for Localize Anything against real Android open-source projects.

The goal is not to claim full production localization of these projects. The goal is to record what Localize Anything can safely inspect, where synthetic workflows succeed, where they block safely, and whether source mutation is avoided.

Provider-backed translation and destructive apply are not covered unless explicitly stated.

Generated outputs and external source projects are not committed as part of this evidence.

## Status Definitions

- `PASS — inspect`: read-only inspection completed and produced evidence.
- `PASS — synthetic workflow`: synthetic draft generation completed and produced a draft package for owner review.
- `BLOCKED SAFELY`: Localize Anything detected a structural or workflow blocker and did not produce a corrupted draft package.
- `NOT RUN`: the workflow step was intentionally not executed.
- `UNSUPPORTED / BOUNDARY`: the case is outside the currently claimed support boundary.

## Matrix

| Project | Commit | Size | Scope tested | Android resources detected | Locales detected | Workflow result | Source mutation | Provider-backed translation | Apply | Recommended status |
|---|---|---:|---|---|---|---|---|---|---|---|
| AntennaPod | `f7f0314888631208fedb26518fd924cb7805062f` | not recorded in matrix source | Disposable-clone inspect/smoke helper; scoped synthetic blind `localize-run` evidence in committed smoke-test docs | 53 Android resource files in the v0.3.1 audit; 125 supported files in smoke docs | Existing target locales detected; exact locale list not recorded in matrix source | PASS — disposable-clone smoke evidence. Synthetic blind workflow evidence is documented in AntennaPod smoke-test docs. | No tracked source mutation | NOT RUN in the v0.3.1 audit | NOT RUN | Keep as disposable-clone smoke evidence. It does not claim provider-backed translation, destructive apply, or full production localization. |
| NewPipe | `46a59640cdf8a2e75fbd9166c6407405fec49a44` | 20.73 MB tracked files | Large locale/resource read-only inspect stress | 110 files | Large existing locale set detected, including Thai; exact list is retained only in the local ignored report | PASS — large locale/resource inspect stress | No tracked source mutation | NOT RUN | NOT RUN | Large real Android project inspect passed. Provider-backed stress testing should be explicit and separate if needed. |
| Tusky | `43ae0bb4556392393a3d759ce42a93f3a003e83a` | 17.4 MB tracked files | Thai (`th`) and Khmer (`km`) synthetic blind `localize-run` after inspect | 63 files; 1 source candidate | Existing Android locale set detected, including Thai; Khmer target file was missing | BLOCKED SAFELY — malformed `<a>` markup. Both Thai and Khmer reached generation, generated 649/729 segments, then failed with `malformed_markup: Target has malformed <a> pair: close before open`. No draft package was created. | No tracked source mutation | NOT RUN | NOT RUN | Review the workflow blocker before provider-backed testing. The fail-closed behavior is useful and should not be weakened. |
| Fossify File Manager | `f53f84677cf767b03585a876311213eff480b247` | 6.42 MB tracked files | Thai (`th`) and Khmer (`km`) synthetic blind `localize-run` after inspect | 83 files; 2 source candidates | Existing Android locale set detected, including Thai; Khmer target files were missing | PASS — synthetic workflow. Thai and Khmer both reached `draft_package_created`; each generated 45/45 segments with 0 blockers. | No tracked source mutation | NOT RUN | NOT RUN | Synthetic full workflow passed. Fossify File Manager is a reasonable candidate for a future provider-backed Thai/Khmer test only with explicit approval. |

## Findings

- Android real-project inspect is stable across several open-source projects.
- Source mutation safety held in all tested projects.
- Synthetic full workflow passed on Fossify File Manager.
- NewPipe provides larger locale/resource stress evidence.
- Tusky exposed a useful markup validation blocker that failed closed.
- Provider-backed translation remains intentionally untested in this matrix.
- Destructive apply remains intentionally untested.

## What This Does Not Claim

- Full production localization of these apps.
- Provider-backed translation quality.
- Human linguistic review.
- Destructive apply safety on these projects.
- Complete Android project localization.
- Layout, drawable, or asset support.
- Gradle editing.
- APK decompilation.
- Full HTML parser support.

## Follow-up Work

- Track the Tusky malformed `<a>` blocker in a GitHub issue.
- Related issue: https://github.com/xueyang-dev/localize-anything/issues/20
- Consider Fossify File Manager as the first controlled provider-backed test candidate, only with explicit approval.
- Continue to treat provider-backed runs and apply as separate safety milestones.
- Consider Windows/WSL helper usability polish if it affects real users.
