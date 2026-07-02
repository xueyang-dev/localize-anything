from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .io_utils import write_json
from .project import inspect_project
from .readiness_authorization import build_readiness_reports
from .run import run_localize


DEFAULT_DEMO_OUTPUT = "localize-anything-demo-output"
DEFAULT_DEMO_RUN_ID = "quickstart-demo"


def run_quickstart_demo(output_root: Path | None = None, run_id: str = DEFAULT_DEMO_RUN_ID) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    fixture = repo_root / "examples" / "quickstart-json"
    if not fixture.is_dir():
        raise ValueError(f"Quickstart fixture is missing: {fixture}")

    output_root = (output_root or Path(DEFAULT_DEMO_OUTPUT)).resolve()
    project = output_root / "project"
    runs = output_root / "runs"
    if project.exists():
        raise ValueError(f"Demo project already exists: {project}. Remove the demo output directory or choose --output-root.")
    if (runs / run_id).exists():
        raise ValueError(f"Demo run already exists: {runs / run_id}. Choose a different --run-id.")

    output_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(fixture, project)

    inspection = inspect_project(project)
    run_summary = run_localize(
        project,
        "en-US",
        ["zh-CN"],
        source_files=["locales/en-US.json"],
        output_root=runs,
        run_id=run_id,
        synthetic_draft=True,
        workflow_depth="fast",
        preflight_mode="light",
        operating_mode="greenfield_localization",
        reference_policy="style_only",
    )

    state_dir = project / ".localize-anything"
    delivery_dir = Path(run_summary["artifacts"]["delivery_directory"])
    readiness = build_readiness_reports(state_dir, delivery_dir=delivery_dir, run_id=run_id)

    summary = {
        "protocol_version": "0.1",
        "schema": "localize-anything-quickstart-demo-summary-v1",
        "status": "pass" if run_summary["status"] == "draft_package_created" else "blocked",
        "run_id": run_id,
        "demo_output_root": output_root.as_posix(),
        "copied_project": project.as_posix(),
        "source_fixture": fixture.as_posix(),
        "inspect": {
            "supported_file_count": len(inspection.get("supported_files", [])),
            "source_files": ["locales/en-US.json"],
        },
        "artifacts": {
            "run_summary": (Path(run_summary["artifacts"]["run_directory"]) / "run-summary.json").as_posix(),
            "staged_files": (Path(run_summary["artifacts"]["run_directory"]) / "staging").as_posix(),
            "qa_report_directory": (Path(run_summary["artifacts"]["run_directory"]) / "qa").as_posix(),
            "readiness_authorization_matrix": (state_dir / "readiness-authorization-matrix.json").as_posix(),
            "delivery_readiness_report": (state_dir / "delivery-readiness-report.json").as_posix(),
            "delivery_package": delivery_dir.as_posix(),
            "apply_plan": run_summary["artifacts"]["apply_plan"],
            "claim_boundary": (repo_root / "docs" / "public-claim-reconciliation.md").as_posix(),
        },
        "readiness_status": {
            "delivery": readiness["delivery_readiness_report"]["delivery_status"],
            "apply": readiness["apply_readiness_report"]["apply_status"],
            "forbidden_claims": readiness["readiness_authorization_matrix"].get("forbidden_claims", []),
        },
        "safety": {
            "provider_or_model_called": False,
            "synthetic_output_quality_claim": "engineering_demo_only",
            "source_fixture_mutated": False,
            "target_project_files_mutated": False,
            "apply_requires_explicit_confirmation": True,
        },
        "next_steps": [
            "Inspect staged files and QA report.",
            "Review readiness and forbidden claims before delivery.",
            "Use the apply plan only after explicit run-id confirmation.",
        ],
    }
    write_json(output_root / "quickstart-demo-summary.json", summary)
    return summary
