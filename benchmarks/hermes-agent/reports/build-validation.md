# build-validation.md

- protocol_version: 0.1
- benchmark_id: hermes-agent
- commit: 91937a6dc3ffbbe2f3be91a500f0ecf962c4cf53
- steps:
  - check: hermes_i18n_parity_tests
  - command: /Users/xueyang/Dev/localize-anything-hermes-benchmark/benchmarks/hermes-agent/work/copy/hermes/.venv/bin/python -m pytest tests/agent/test_i18n.py -q
  - exit_code: 0
  - duration_seconds: 2.5
  - passed: True
  - tail: ....................................                                     [100%]
36 passed in 2.26s

  - check: hermes_python_compileall
  - command: python3 -m compileall -q agent hermes_cli gateway
  - exit_code: 0
  - duration_seconds: 0.1
  - passed: True
  - tail: 
  - check: web_typecheck
  - command: npm run typecheck
  - exit_code: 0
  - duration_seconds: 0.34
  - passed: True
  - tail: 
> web@0.0.0 typecheck
> tsc -p . --noEmit


  - check: web_vitest
  - command: npm run test
  - exit_code: 0
  - duration_seconds: 1.15
  - passed: True
  - tail: 
> web@0.0.0 test
> vitest run


 RUN  v4.1.10 /Users/xueyang/Dev/localize-anything-hermes-benchmark/benchmarks/hermes-agent/work/copy/hermes/web


 Test Files  22 passed (22)
      Tests  156 passed (156)
   Start at  12:41:34
   Duration  717ms (transform 732ms, setup 0ms, import 1.53s, tests 163ms, environment 1ms)

(!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
  - `__dirname` (vitest.config.ts:9:25). Use `import.meta.dirname` instead
Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.

  - check: web_build
  - command: npm run build
  - exit_code: 0
  - duration_seconds: 4.19
  - passed: True
  - tail: B
../hermes_cli/web_dist/assets/EnvPage-C0YbBZqt.js                      29.97 kB │ gzip:   8.14 kB
../hermes_cli/web_dist/assets/CronPage-C7itHUS_.js                     31.60 kB │ gzip:   8.86 kB
../hermes_cli/web_dist/assets/ChatPage-Wp8EJaje.js                     38.70 kB │ gzip:  13.15 kB
../hermes_cli/web_dist/assets/SkillsPage-F1QeC6Yk.js                   39.62 kB │ gzip:  10.57 kB
../hermes_cli/web_dist/assets/SessionsPage-Csd1SGuI.js                 40.62 kB │ gzip:  11.87 kB
../hermes_cli/web_dist/assets/SystemPage-CVRN8M78.js                   40.63 kB │ gzip:  10.90 kB
../hermes_cli/web_dist/assets/index-DQwjY7jm.js                        42.41 kB │ gzip:  12.65 kB
../hermes_cli/web_dist/assets/vendor-BLReI8FQ.js                       50.06 kB │ gzip:  17.82 kB
../hermes_cli/web_dist/assets/react-vendor-B6GYCG81.js                226.82 kB │ gzip:  72.67 kB
../hermes_cli/web_dist/assets/ui-CGB0TYQ8.js                          289.93 kB │ gzip:  94.82 kB
../hermes_cli/web_dist/assets/i18n-ORg-xQMU.js                        471.65 kB │ gzip: 139.58 kB
../hermes_cli/web_dist/assets/xterm-CXxU4Y2B.js                       474.38 kB │ gzip: 122.64 kB

✓ built in 413ms
(!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
  - `__dirname` (vite.config.ts:64:25). Use `import.meta.dirname` instead
Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.

  - check: desktop_typecheck
  - command: npm run typecheck
  - exit_code: 0
  - duration_seconds: 12.55
  - passed: True
  - tail: 
> hermes@0.17.0 typecheck
> tsc -p . --noEmit && tsc -p tsconfig.electron.json --noEmit && tsc -p tsconfig.e2e.json --noEmit


  - check: desktop_vitest
  - command: npm run test
  - exit_code: 0
  - duration_seconds: 93.61
  - passed: True
  - tail: 
> hermes@0.17.0 test
> vitest run


 RUN  v4.1.10 /Users/xueyang/Dev/localize-anything-hermes-benchmark/benchmarks/hermes-agent/work/copy/hermes/apps/desktop


 Test Files  465 passed | 1 skipped (466)
      Tests  4295 passed | 2 skipped (4297)
   Start at  12:41:52
   Duration  93.04s (transform 14.60s, setup 56.84s, import 265.38s, tests 86.79s, environment 341.11s)

(!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
  - `__dirname` (vite.config.ts:21:20). Use `import.meta.dirname` instead
Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.
Preparing worktree (new branch 'wt')
Switched to a new branch 'rawr'
Switched to a new branch 'rawr'
Cloning into '/var/folders/70/m56f428103j8mb2ssqj6zr4c0000gn/T/hermes-clone-t9DXY8'...
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
  - duration_seconds: 4.97
  - passed: True
  - tail: idF.js                        349.01 kB │ gzip:   106.93 kB
dist/assets/i18n-BPpNvoEX.js                             700.43 kB │ gzip:   225.89 kB
dist/assets/index-CXHG8Pd7.js                          2,126.91 kB │ gzip:   635.95 kB
dist/assets/mermaid-BVb1m2iz.js                        2,973.15 kB │ gzip:   783.39 kB
dist/assets/shiki-6BOFvr6A.js                         18,983.25 kB │ gzip: 3,308.84 kB

✓ built in 3.48s
bundled /Users/xueyang/Dev/localize-anything-hermes-benchmark/benchmarks/hermes-agent/work/copy/hermes/apps/desktop/dist/electron-main.mjs
bundled /Users/xueyang/Dev/localize-anything-hermes-benchmark/benchmarks/hermes-agent/work/copy/hermes/apps/desktop/dist/electron-preload.js
[stage-native-deps] staged node-pty (darwin-arm64) -> /Users/xueyang/Dev/localize-anything-hermes-benchmark/benchmarks/hermes-agent/work/copy/hermes/apps/desktop/dist/node_modules/node-pty

> hermes@0.17.0 postbuild
> node scripts/assert-dist-built.mjs

✓ assert-dist-built: dist/index.html + assets present
(!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
  - `__dirname` (vite.config.ts:21:20). Use `import.meta.dirname` instead
Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.

 WARN  advancedChunks option is deprecated, please use codeSplitting instead.


  dist/electron-main.mjs  680.5kb

⚡ Done in 50ms

  dist/electron-preload.js  21.8kb

⚡ Done in 3ms

  - note: Full electron packaging (npm run dist) is environment-dependent and not part of this validation.
