"""Final gate: run Localize Anything regressions and aggregate all evidence."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from common import BENCH_ROOT, CONFIG, REPOSITORY_ROOT, REPORTS, evaluate_build_gate, read_json, report_markdown, run, write_json


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    regression = run_regressions()
    write_json(regression, REPORTS / "regression-evidence.json")
    write_json(report_markdown(regression, "regression-evidence.md"), REPORTS / "regression-evidence.md", raw=True)

    checks: dict[str, object] = {
        "source_verification": _load_or_none("source-verification.json"),
        "yaml_benchmark": _load_or_none("yaml-benchmark-report.json"),
        "typescript_web_benchmark": _load_or_none("typescript-web-benchmark-report.json"),
        "typescript_desktop_benchmark": _load_or_none("typescript-desktop-benchmark-report.json"),
        "incremental": _load_or_none("incremental-report.json"),
        "coverage_audit": _load_or_none("coverage-audit.json"),
        "build_validation": _load_or_none("build-validation.json"),
        "regression_evidence": regression,
    }
    build_gate_ok, build_gate_problems = evaluate_build_gate(checks["build_validation"])
    gates = {
        "source_verified": checks["source_verification"] is not None and checks["source_verification"]["status"] == "pass",
        "yaml_qa_pass": checks["yaml_benchmark"] is not None and checks["yaml_benchmark"]["qa"]["status"] == "pass",
        "web_qa_pass": checks["typescript_web_benchmark"] is not None and checks["typescript_web_benchmark"]["qa"]["status"] == "pass",
        "desktop_qa_pass": checks["typescript_desktop_benchmark"] is not None and checks["typescript_desktop_benchmark"]["qa"]["status"] == "pass",
        "semantic_no_blocking": all(
            checks[key]["semantic_review"]["blocking"] == 0
            for key in ("yaml_benchmark", "typescript_web_benchmark", "typescript_desktop_benchmark")
            if checks[key]
        ),
        "incremental_classified": checks["incremental"] is not None
        and all(checks["incremental"]["classification"].get(k, 0) >= 1 for k in ("new", "changed", "moved", "deleted")),
        "desktop_apply_plan": checks["typescript_desktop_benchmark"] is not None and bool(checks["typescript_desktop_benchmark"]["apply_plan"]),
        "build_validation_pass": build_gate_ok,
        "regressions_pass": regression["status"] == "pass",
    }
    all_pass = all(gates.values())
    report = {
        "protocol_version": CONFIG["protocol_version"],
        "benchmark_id": CONFIG["id"],
        "status": "pass" if all_pass else "fail",
        "gates": gates,
        "build_gate_problems": build_gate_problems,
        "checks": checks,
    }
    write_json(report, REPORTS / "verify-results.json")
    write_json(report_markdown(report, "verify-results.md"), REPORTS / "verify-results.md", raw=True)
    print(f"gates: {gates}")
    print(f"overall: {report['status']}")
    return 0 if all_pass else 1


def run_regressions() -> dict[str, object]:
    steps: list[dict[str, object]] = []
    commands = [
        ("localize_anything_unittest", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("adapter_tree_validation", [sys.executable, "-c", _ADAPTER_TREE_CHECK]),
        ("protocol_tree_validation", [sys.executable, "-c", _PROTOCOL_TREE_CHECK]),
        (
            "compileall",
            [sys.executable, "-m", "compileall", "-q", "runtime", "benchmarks", "-x", r"/(work|runs|node_modules)/"],
        ),
    ]
    for label, command in commands:
        started = time.monotonic()
        result = run(command, cwd=REPOSITORY_ROOT, timeout=900)
        steps.append(
            {
                "check": label,
                "command": " ".join(part.strip() for part in command),
                "exit_code": result.returncode,
                "duration_seconds": round(time.monotonic() - started, 2),
                "passed": result.returncode == 0,
                "tail": (result.stdout + result.stderr)[-2000:],
            }
        )
    diff = run(["git", "diff", "--check"], cwd=REPOSITORY_ROOT)
    steps.append(
        {
            "check": "git_diff_check",
            "command": "git diff --check",
            "exit_code": diff.returncode,
            "passed": diff.returncode == 0,
            "tail": diff.stdout[-1000:] + diff.stderr[-1000:],
        }
    )
    passed = all(step["passed"] for step in steps)
    return {"status": "pass" if passed else "fail", "steps": steps}


def _load_or_none(name: str) -> dict[str, object] | None:
    path = REPORTS / name
    return read_json(path) if path.is_file() else None


_ADAPTER_TREE_CHECK = """
import json
from pathlib import Path
from runtime.localize_anything.contracts import validate_adapter_tree
result = validate_adapter_tree(Path('adapters'))
print(json.dumps(result, indent=2))
if result['status'] != 'pass':
    raise SystemExit(1)
if result['manifests_checked'] < 13:
    raise SystemExit('expected >=13 adapter manifests, got ' + str(result['manifests_checked']))
"""

_PROTOCOL_TREE_CHECK = """
import json
from pathlib import Path
from runtime.localize_anything.schema_validation import validate_protocol_tree
result = validate_protocol_tree(Path('protocol'))
print(json.dumps(result, indent=2))
if result['status'] != 'pass':
    raise SystemExit(1)
"""


if __name__ == "__main__":
    raise SystemExit(main())
