# verify-results.md

- protocol_version: 0.1
- benchmark_id: hermes-agent
- status: pass
- gates:
  - source_verified: True
  - yaml_qa_pass: True
  - web_qa_pass: True
  - desktop_qa_pass: True
  - semantic_no_blocking: True
  - incremental_classified: True
  - desktop_apply_plan: True
  - build_validation_pass: True
  - regressions_pass: True
- build_gate_problems:
- checks:
  - source_verification:
    - protocol_version: 0.1
    - benchmark_id: hermes-agent
    - status: pass
    - pinned_commit: 91937a6dc3ffbbe2f3be91a500f0ecf962c4cf53
    - source_hashes:
      - locales/en.yaml: fe06b52df673b817691f761b6650bb7513cbc755eca7adef16303df1e4770c8c
      - locales/fr.yaml: 44a0a249621099dc7186a02293437c34cd8240378c08612d82955a3424577341
      - web/src/i18n/en.ts: 37d65853e79abedcbbe12f7fe8165c69e15b8401db4b8057229f02ee3597528c
      - apps/desktop/src/i18n/en.ts: a357847504e26bba914ae35305d4e808a9dcc5dcf8eff0207b2393913b6d1605
    - items:
      - 9 items (sample):
        - category: pinned_commit
        - severity: pass
        - message: HEAD is 91937a6dc3ffbbe2f3be91a500f0ecf962c4cf53, expected 91937a6dc3ffbbe2f3be91a500f0ecf962c4cf53
        - category: clean_checkout
        - severity: pass
        - message: source checkout has uncommitted changes
        - category: expected_paths
        - severity: pass
        - message: expected catalog paths missing
        - category: yaml_parse
        - severity: pass
        - message: one or more YAML catalogs fail to parse/extract
        - category: ts_parse
        - severity: pass
        - message: one or more TypeScript catalogs fail to parse/extract
        - category: blind_workspace
        - severity: pass
        - message: blind workspace present (run `python prepare.py blind`)
        - category: blind_no_french
        - severity: pass
        - message: blind workspace contains no French resources
        - category: blind_english_parity
        - severity: pass
        - message: blind English sources match the pinned checkout
  - yaml_benchmark:
    - protocol_version: 0.1
    - benchmark_id: hermes-agent
    - surface: yaml_cli_gateway
    - track: controlled
    - commit: 91937a6dc3ffbbe2f3be91a500f0ecf962c4cf53
    - target_locale: fr
    - generation:
      - mode: engineering_fixture_only
      - quality_claim: engineering_fixture_only
      - provider: None
      - curated_slice_segments: 9
      - identity_segments: 342
    - extraction:
      - segments: 351
      - deterministic: True
      - duplicate_ids: False
      - source_hash: fe06b52df673b817691f761b6650bb7513cbc755eca7adef16303df1e4770c8c
    - batch_plan:
      - surface: yaml
      - target_locale: fr
      - batches:
        - 15 items (sample):
          - common
          - app_shell
          - status
          - sessions
          - analytics
          - models
          - logs
          - settings
    - qa:
      - status: pass
      - summary:
        - blocking_count: 0
        - warning_count: 0
    - semantic_review:
      - flags: 342
      - blocking: 0
      - untranslated_english: 342
    - staging:
      - path: <work>/staging/yaml/fr.yaml
      - source_unchanged: True
    - reference_comparison:
      - official_is_reference_not_ground_truth: True
      - official_key_missing_vs_staged:
      - staged_key_missing_vs_official:
      - official_untranslated_english_stragglers: 58
      - staged_untranslated_english_segments: 342
      - identical_translated_values: 1
      - identical_translated_sample:
        - gateway.usage.header_session
  - typescript_web_benchmark:
    - protocol_version: 0.1
    - benchmark_id: hermes-agent
    - surface: web_dashboard
    - track: controlled
    - commit: 91937a6dc3ffbbe2f3be91a500f0ecf962c4cf53
    - target_locale: fr
    - generation:
      - mode: engineering_fixture_only
      - quality_claim: engineering_fixture_only
      - provider: None
      - curated_slice_segments: 9
      - identity_segments: 700
    - extraction:
      - segments: 709
      - deterministic: True
      - duplicate_ids: False
      - source_hash: 37d65853e79abedcbbe12f7fe8165c69e15b8401db4b8057229f02ee3597528c
      - function_valued: 0
      - template_expression_bearing: 0
    - batch_plan:
      - surface: web
      - target_locale: fr
      - batches:
        - 15 items (sample):
          - common
          - app_shell
          - status
          - sessions
          - analytics
          - models
          - logs
          - settings
    - qa:
      - status: pass
      - summary:
        - blocking_count: 0
        - warning_count: 0
    - semantic_review:
      - flags: 701
      - blocking: 0
      - untranslated_english: 701
    - staging:
      - path: <work>/staging/web/fr.ts
      - source_unchanged: True
    - reference_comparison:
      - official_is_reference_not_ground_truth: True
      - official_key_missing_vs_staged:
        - 71 items (sample):
          - /app/currentProfileOption
          - /app/managingProfile
          - /app/managingProfileBanner
          - /common/gateway
          - /common/gatewayHint
          - /cron/delivery/needsHomeChannel
          - /cron/delivery/noneConfigured
          - /kanban/assigneeLabel
      - staged_key_missing_vs_official:
      - official_untranslated_english_stragglers: 62
      - staged_untranslated_english_segments: 701
      - identical_translated_values: 6
      - identical_translated_sample:
        - /common/cancel
        - /common/delete
        - /common/retry
        - /common/save
        - /language/switchTo
        - /status/running
    - apply_plan: None
  - typescript_desktop_benchmark:
    - protocol_version: 0.1
    - benchmark_id: hermes-agent
    - surface: desktop
    - track: controlled
    - commit: 91937a6dc3ffbbe2f3be91a500f0ecf962c4cf53
    - target_locale: fr
    - generation:
      - mode: engineering_fixture_only
      - quality_claim: engineering_fixture_only
      - provider: None
      - curated_slice_segments: 5
      - identity_segments: 2618
    - extraction:
      - segments: 2623
      - deterministic: True
      - duplicate_ids: False
      - source_hash: a357847504e26bba914ae35305d4e808a9dcc5dcf8eff0207b2393913b6d1605
      - function_valued: 319
      - template_expression_bearing: 315
    - batch_plan:
      - surface: desktop
      - target_locale: fr
      - batches:
        - 15 items (sample):
          - common
          - app_shell
          - status
          - sessions
          - analytics
          - models
          - logs
          - settings
    - qa:
      - status: pass
      - summary:
        - blocking_count: 0
        - warning_count: 0
    - semantic_review:
      - flags: 2618
      - blocking: 0
      - untranslated_english: 2618
    - staging:
      - path: <work>/staging/desktop/fr.ts
      - source_unchanged: True
    - reference_comparison:
      - official_reference_exists: False
    - apply_plan:
      - description: Desktop fr enablement requires registering the staged catalog in the locale contract.
      - files:
        - path: apps/desktop/src/i18n/fr.ts
        - action: copy_staged
        - source: <work>/staging/desktop/fr.ts
        - path: apps/desktop/src/i18n/types.ts
        - action: edit_locale_union
        - edit: add 'fr' to the `export type Locale` union
        - path: apps/desktop/src/i18n/catalog.ts
        - action: edit_translations_record
        - edit: import fr and register it in TRANSLATIONS
        - path: apps/desktop/src/i18n/languages.ts
        - action: edit_locale_options
        - edit: add the Français LOCALE_OPTIONS entry and fr aliases
      - staged_only: True
      - original_checkout_mutation: False
  - incremental:
    - protocol_version: 0.1
    - benchmark_id: hermes-agent
    - phase: incremental
    - classification:
      - new: 1
      - unchanged: 347
      - changed: 2
      - moved: 1
      - deleted: 1
    - expected:
      - new: 1
      - changed: 2
      - moved: 1
      - deleted: 1
    - regenerated_segments: 4
    - preserved_reviewed_segments: 2
    - preserved_translations_intact: True
    - staged_output: <work>/incremental/fr-mutated.yaml
  - coverage_audit:
    - protocol_version: 0.1
    - benchmark_id: hermes-agent
    - categories:
      - resource_catalog_coverage:
        - status: verified_for_staged_catalogs
        - evidence: YAML + Web + Desktop staged fr catalogs rebuild and pass deterministic QA
      - static_frontend_coverage:
        - status: partial
        - evidence: catalogs covered; hardcoded JSX strings inventoried but not translated
      - backend_metadata_coverage:
        - status: partial
        - evidence: gateway labels routed through YAML catalog; dynamic values stay English
      - plugin_metadata_coverage:
        - status: not_translated
        - evidence: plugin manifests inventory only
      - skill_metadata_coverage:
        - status: not_translated
        - evidence: skill frontmatter/descriptions inventory only
      - documentation_coverage:
        - status: analyzed_not_generated
        - evidence: 378 English docs, 317 zh-Hans translations; no fr docs generated in engineering run
      - dynamic_server_content_coverage:
        - status: partial
        - evidence: agent replies/logs/tool output intentionally English per agent/i18n.py
      - runtime_generated_content:
        - status: intentionally_out_of_scope
        - evidence: model output is never catalog-routed
      - non_text_asset_coverage:
        - status: not_run
        - evidence: images/audio/video assets inventoried; no OCR/visual QA
      - visual_qa:
        - status: not_run
        - evidence: no UI screenshots or runtime smoke tests in engineering run
    - delivery_decision:
      - catalog_localization_proven: True
      - full_product_localization_proven: False
      - statement: Catalog localization is proven for the staged fr catalogs; full product localization is NOT proven.
      - incremental_classification:
        - new: 1
        - unchanged: 347
        - changed: 2
        - moved: 1
        - deleted: 1
      - desktop_official_french_missing: True
  - build_validation:
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
      - duration_seconds: 1.38
      - passed: True
      - status: passed
      - required: True
      - tail: ....................................                                     [100%]
36 passed in 1.17s
      - check: hermes_python_compileall
      - command: python3 -m compileall -q agent hermes_cli gateway
      - exit_code: 0
      - duration_seconds: 0.09
      - passed: True
      - status: passed
      - required: True
      - tail:
      - check: web_typecheck
      - command: npm run typecheck
      - exit_code: 0
      - duration_seconds: 0.37
      - passed: True
      - status: passed
      - required: True
      - tail: 
> web@0.0.0 typecheck
> tsc -p . --noEmit
      - check: web_vitest
      - command: npm run test
      - exit_code: 0
      - duration_seconds: 1.16
      - passed: True
      - status: passed
      - required: True
      - tail: 
> web@0.0.0 test
> vitest run


 RUN  v4.1.10 <hermes-copy>/web


 Test Files  22 passed (22)
      Tests  156 passed (156)
   Start at  13:27:55
   Duration  751ms (transform 928ms, setup 0ms, import 1.79s, tests 154ms, environment 1ms)

(!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
  - `__dirname` (vitest.config.ts:9:25). Use `import.meta.dirname` instead
Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.
      - check: web_build
      - command: npm run build
      - exit_code: 0
      - duration_seconds: 6.05
      - passed: True
      - status: passed
      - required: True
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

✓ built in 534ms
(!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
  - `__dirname` (vite.config.ts:64:25). Use `import.meta.dirname` instead
Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.
      - check: desktop_typecheck
      - command: npm run typecheck
      - exit_code: 0
      - duration_seconds: 17.78
      - passed: True
      - status: passed
      - required: True
      - tail: 
> hermes@0.17.0 typecheck
> tsc -p . --noEmit && tsc -p tsconfig.electron.json --noEmit && tsc -p tsconfig.e2e.json --noEmit
      - check: desktop_vitest
      - command: npm run test
      - exit_code: 0
      - duration_seconds: 142.29
      - passed: True
      - status: passed
      - required: True
      - tail: 
> hermes@0.17.0 test
> vitest run


 RUN  v4.1.10 <hermes-copy>/apps/desktop


 Test Files  465 passed | 1 skipped (466)
      Tests  4295 passed | 2 skipped (4297)
   Start at  13:28:21
   Duration  141.45s (transform 24.05s, setup 85.27s, import 409.22s, tests 129.31s, environment 522.25s)

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
      - duration_seconds: 7.7
      - passed: True
      - status: passed
      - required: True
      - tail:                      2,126.91 kB │ gzip:   635.95 kB
dist/assets/mermaid-BVb1m2iz.js                        2,973.15 kB │ gzip:   783.39 kB
dist/assets/shiki-6BOFvr6A.js                         18,983.25 kB │ gzip: 3,308.84 kB

✓ built in 4.77s
bundled <hermes-copy>/apps/desktop/dist/electron-main.mjs
bundled <hermes-copy>/apps/desktop/dist/electron-preload.js
[stage-native-deps] staged node-pty (darwin-arm64) -> <hermes-copy>/apps/desktop/dist/node_modules/node-pty

> hermes@0.17.0 postbuild
> node scripts/assert-dist-built.mjs

✓ assert-dist-built: dist/index.html + assets present
[write-build-stamp] WARNING: working tree is dirty.
  Pinning to 71b1f1b13ebc but the packaged code may differ from that commit.
  Commit your changes before publishing this build.
(!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
  - `__dirname` (vite.config.ts:21:20). Use `import.meta.dirname` instead
Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.

 WARN  advancedChunks option is deprecated, please use codeSplitting instead.


  dist/electron-main.mjs  680.5kb

⚡ Done in 36ms

  dist/electron-preload.js  21.8kb

⚡ Done in 3ms
      - note: Full electron packaging (npm run dist) is environment-dependent and not part of this validation.
  - regression_evidence:
    - status: pass
    - steps:
      - check: localize_anything_unittest
      - command: <repo>/.venv/bin/python -m unittest discover -s tests -v
      - exit_code: 0
      - duration_seconds: 7.95
      - passed: True
      - tail: apterTests.test_identity_round_trip_is_byte_identical) ... ok
test_invalid_export_identifiers_fail_closed (test_typescript_adapter.TypeScriptAdapterTests.test_invalid_export_identifiers_fail_closed) ... ok
test_missing_and_unexpected_keys_fail (test_typescript_adapter.TypeScriptAdapterTests.test_missing_and_unexpected_keys_fail) ... ok
test_overlapping_edits_fail_closed (test_typescript_adapter.TypeScriptAdapterTests.test_overlapping_edits_fail_closed) ... ok
test_placeholder_mismatch_fails (test_typescript_adapter.TypeScriptAdapterTests.test_placeholder_mismatch_fails) ... ok
test_rebuild_longer_export_name_keeps_literal_spans (test_typescript_adapter.TypeScriptAdapterTests.test_rebuild_longer_export_name_keeps_literal_spans) ... ok
test_rebuild_preserves_function_signatures_and_expressions (test_typescript_adapter.TypeScriptAdapterTests.test_rebuild_preserves_function_signatures_and_expressions) ... ok
test_rebuild_renames_export_to_target_locale (test_typescript_adapter.TypeScriptAdapterTests.test_rebuild_renames_export_to_target_locale) ... ok
test_rebuild_shorter_export_name (test_typescript_adapter.TypeScriptAdapterTests.test_rebuild_shorter_export_name) ... ok
test_rebuild_translated_strings_and_arrays (test_typescript_adapter.TypeScriptAdapterTests.test_rebuild_translated_strings_and_arrays) ... ok
test_template_expression_mismatch_fails (test_typescript_adapter.TypeScriptAdapterTests.test_template_expression_mismatch_fails) ... ok
test_template_expression_order_change_is_blocking (test_typescript_adapter.TypeScriptAdapterTests.test_template_expression_order_change_is_blocking) ... ok
test_template_expression_order_preserved_passes (test_typescript_adapter.TypeScriptAdapterTests.test_template_expression_order_preserved_passes) ... ok
test_unsupported_shape_fails_closed (test_typescript_adapter.TypeScriptAdapterTests.test_unsupported_shape_fails_closed) ... ok

----------------------------------------------------------------------
Ran 110 tests in 7.860s

OK
      - check: adapter_tree_validation
      - command: <repo>/.venv/bin/python -c import json
from pathlib import Path
from runtime.localize_anything.contracts import validate_adapter_tree
result = validate_adapter_tree(Path('adapters'))
print(json.dumps(result, indent=2))
if result['status'] != 'pass':
    raise SystemExit(1)
if result['manifests_checked'] < 13:
    raise SystemExit('expected >=13 adapter manifests, got ' + str(result['manifests_checked']))
      - exit_code: 0
      - duration_seconds: 0.02
      - passed: True
      - tail: {
  "protocol_version": "0.1",
  "status": "pass",
  "manifests_checked": 13,
  "errors": []
}
      - check: protocol_tree_validation
      - command: <repo>/.venv/bin/python -c import json
from pathlib import Path
from runtime.localize_anything.schema_validation import validate_protocol_tree
result = validate_protocol_tree(Path('protocol'))
print(json.dumps(result, indent=2))
if result['status'] != 'pass':
    raise SystemExit(1)
      - exit_code: 0
      - duration_seconds: 0.02
      - passed: True
      - tail: {
  "protocol_version": "0.1",
  "status": "pass",
  "schemas_checked": 7,
  "examples_checked": 7,
  "errors": []
}
      - check: compileall
      - command: <repo>/.venv/bin/python -m compileall -q runtime benchmarks -x /(work|runs|node_modules)/
      - exit_code: 0
      - duration_seconds: 2.59
      - passed: True
      - tail:
      - check: git_diff_check
      - command: git diff --check
      - exit_code: 0
      - passed: True
      - tail:
