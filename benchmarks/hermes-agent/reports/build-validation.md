# build-validation.md

- protocol_version: 0.1
- benchmark_id: hermes-agent
- commit: 91937a6dc3ffbbe2f3be91a500f0ecf962c4cf53
- status: pass
- summary:
  - total: 8
  - passed: 8
  - failed: 0
  - skipped: 0
  - not_run: 0
- steps:
  - check: hermes_i18n_parity_tests
  - command: <hermes-copy>/.venv/bin/python -m pytest tests/agent/test_i18n.py -q
  - exit_code: 0
  - duration_seconds: 2.46
  - passed: True
  - status: passed
  - required: True
  - tail: ....................................                                     [100%]
36 passed in 2.07s

  - check: hermes_python_compileall
  - command: python3 -m compileall -q agent hermes_cli gateway
  - exit_code: 0
  - duration_seconds: 0.85
  - passed: True
  - status: passed
  - required: True
  - tail:
  - check: web_typecheck
  - command: npm run typecheck
  - exit_code: 0
  - duration_seconds: 0.41
  - passed: True
  - status: passed
  - required: True
  - tail:
> web@0.0.0 typecheck
> tsc -p . --noEmit


  - check: web_vitest
  - command: npm run test
  - exit_code: 0
  - duration_seconds: 2.62
  - passed: True
  - status: passed
  - required: True
  - tail:
> web@0.0.0 test
> vitest run


 RUN  v4.1.10 <hermes-copy>/web


 Test Files  22 passed (22)
      Tests  156 passed (156)
   Start at  14:33:08
   Duration  612ms (transform 812ms, setup 0ms, import 1.58s, tests 143ms, environment 1ms)

(!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
  - `__dirname` (vitest.config.ts:9:25). Use `import.meta.dirname` instead
Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.

  - check: web_build
  - command: npm run build
  - exit_code: 0
  - duration_seconds: 5.38
  - passed: True
  - status: passed
  - required: True
  - tail: B
../hermes_cli/web_dist/assets/EnvPage-cYkcXTXN.js                      29.97 kB │ gzip:   8.13 kB
../hermes_cli/web_dist/assets/CronPage-BWM_t59l.js                     31.60 kB │ gzip:   8.86 kB
../hermes_cli/web_dist/assets/ChatPage-DdJSH7F2.js                     38.70 kB │ gzip:  13.15 kB
../hermes_cli/web_dist/assets/SkillsPage-CbT3KPb_.js                   39.62 kB │ gzip:  10.57 kB
../hermes_cli/web_dist/assets/SessionsPage-f8gkmFC9.js                 40.62 kB │ gzip:  11.87 kB
../hermes_cli/web_dist/assets/SystemPage-BGAKUzUV.js                   40.63 kB │ gzip:  10.90 kB
../hermes_cli/web_dist/assets/index-ChVli4_g.js                        42.41 kB │ gzip:  12.64 kB
../hermes_cli/web_dist/assets/vendor-BLReI8FQ.js                       50.06 kB │ gzip:  17.82 kB
../hermes_cli/web_dist/assets/react-vendor-B6GYCG81.js                226.82 kB │ gzip:  72.67 kB
../hermes_cli/web_dist/assets/ui-CGB0TYQ8.js                          289.93 kB │ gzip:  94.82 kB
../hermes_cli/web_dist/assets/xterm-CXxU4Y2B.js                       474.38 kB │ gzip: 122.64 kB
../hermes_cli/web_dist/assets/i18n-WOnQlfa9.js                        476.54 kB │ gzip: 141.05 kB

✓ built in 347ms
(!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
  - `__dirname` (vite.config.ts:64:25). Use `import.meta.dirname` instead
Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.

  - check: desktop_typecheck
  - command: npm run typecheck
  - exit_code: 0
  - duration_seconds: 11.28
  - passed: True
  - status: passed
  - required: True
  - tail:
> hermes@0.17.0 typecheck
> tsc -p . --noEmit && tsc -p tsconfig.electron.json --noEmit && tsc -p tsconfig.e2e.json --noEmit


  - check: desktop_vitest
  - command: npm run test
  - exit_code: 0
  - duration_seconds: 62.75
  - passed: True
  - status: passed
  - required: True
  - tail:
> hermes@0.17.0 test
> vitest run


 RUN  v4.1.10 <hermes-copy>/apps/desktop


 Test Files  465 passed | 1 skipped (466)
      Tests  4295 passed | 2 skipped (4297)
   Start at  14:33:26
   Duration  62.38s (transform 12.52s, setup 36.58s, import 186.87s, tests 77.44s, environment 200.78s)

(!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
  - `__dirname` (vite.config.ts:21:20). Use `import.meta.dirname` instead
Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.
Preparing worktree (new branch 'wt')
Switched to a new branch 'rawr'
Switched to a new branch 'rawr'
Cloning into '<temporary-directory>'...
done.
fatal: no upstream configured for branch 'feature-branch'
Not implemented: HTMLCanvasElement's getContext() method: without installing the canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the canvas npm package

  - check: desktop_build
  - command: npm run build
  - exit_code: 0
  - duration_seconds: 2.61
  - passed: True
  - status: passed
  - required: True
  - tail:                      2,126.91 kB │ gzip:   635.95 kB
dist/assets/mermaid-BVb1m2iz.js                        2,973.15 kB │ gzip:   783.39 kB
dist/assets/shiki-6BOFvr6A.js                         18,983.25 kB │ gzip: 3,308.84 kB

✓ built in 1.51s
bundled <hermes-copy>/apps/desktop/dist/electron-main.mjs
bundled <hermes-copy>/apps/desktop/dist/electron-preload.js
[stage-native-deps] staged node-pty (darwin-arm64) -> <hermes-copy>/apps/desktop/dist/node_modules/node-pty

> hermes@0.17.0 postbuild
> node scripts/assert-dist-built.mjs

✓ assert-dist-built: dist/index.html + assets present
[write-build-stamp] WARNING: working tree is dirty.
  Pinning to 5482e64b3510 but the packaged code may differ from that commit.
  Commit your changes before publishing this build.
(!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
  - `__dirname` (vite.config.ts:21:20). Use `import.meta.dirname` instead
Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.

 WARN  advancedChunks option is deprecated, please use codeSplitting instead.


  dist/electron-main.mjs  680.5kb

⚡ Done in 33ms

  dist/electron-preload.js  21.8kb

⚡ Done in 2ms

  - note: Full electron packaging (npm run dist) is environment-dependent and not part of this validation.
