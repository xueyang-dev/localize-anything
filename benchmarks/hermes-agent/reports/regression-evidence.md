# regression-evidence.md

- status: pass
- steps:
  - check: localize_anything_unittest
  - command: <repo>/.venv/bin/python -m unittest discover -s tests -v
  - exit_code: 0
  - duration_seconds: 8.33
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
Ran 137 tests in 8.159s

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
  - duration_seconds: 3.04
  - passed: True
  - tail:
  - check: git_diff_check
  - command: git diff --check
  - exit_code: 0
  - passed: True
  - tail:
