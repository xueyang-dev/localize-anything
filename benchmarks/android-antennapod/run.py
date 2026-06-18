from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY))

from runtime.localize_anything.android_strings_adapter import extract_segments, stage_rebuild, validate_pair  # noqa: E402
from runtime.localize_anything.dashboard import build_delivery_dashboard, render_dashboard_markdown  # noqa: E402
from runtime.localize_anything.delivery import package_delivery  # noqa: E402
from runtime.localize_anything.generation import collect_generated_handoff, create_draft_request, create_generation_handoff, validate_generated_segments  # noqa: E402
from runtime.localize_anything.io_utils import read_jsonl, write_json, write_jsonl  # noqa: E402
from runtime.localize_anything.planning import create_batch_plan  # noqa: E402
from runtime.localize_anything.project import initialize_project, inspect_project  # noqa: E402
from runtime.localize_anything.retrieval import build_work_packet  # noqa: E402


CONFIG = json.loads((ROOT / "benchmark.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the pinned AntennaPod Android strings benchmark")
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--target-locale", default=CONFIG["locales"]["target"])
    parser.add_argument("--max-segments", type=int, default=20)
    parser.add_argument("--generated-dir", type=Path, help="Use host-agent generated JSONL batches from this directory")
    parser.add_argument("--handoff-only", action="store_true", help="Prepare draft requests and stop before staging")
    parser.add_argument("--keep-existing", action="store_true")
    args = parser.parse_args()
    result = run_benchmark(args.workspace, args.target_locale, args.max_segments, args.generated_dir, args.handoff_only, args.keep_existing)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def run_benchmark(
    workspace: Path,
    target_locale: str,
    max_segments: int,
    external_generated_dir: Path | None = None,
    handoff_only: bool = False,
    keep_existing: bool = False,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    if workspace.exists() and not keep_existing:
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    source_root = workspace / "source"
    staging_dir = workspace / "staging"
    evidence_dir = workspace / "evidence"
    deliveries_dir = workspace / "deliveries"
    source_file = CONFIG["upstream"]["source_file"]
    source_path = source_root / source_file
    source_path.parent.mkdir(parents=True, exist_ok=True)

    _download(CONFIG["upstream"]["raw_url"], source_path)
    _verify_hash(source_path, CONFIG["upstream"]["source_file_sha256"])
    write_json(
        workspace / "source-provenance.json",
        {
            "benchmark_id": CONFIG["id"],
            "repository": CONFIG["upstream"]["repository"],
            "commit": CONFIG["upstream"]["commit"],
            "source_file": source_file,
            "source_file_sha256": CONFIG["upstream"]["source_file_sha256"],
            "source_owned_workspace": False,
        },
    )

    inspection = inspect_project(source_root)
    initialized = initialize_project(source_root, CONFIG["locales"]["source"], [source_file], [target_locale])
    state_dir = Path(initialized["state_directory"])

    segments = extract_segments(source_path, CONFIG["locales"]["source"], source_file)
    write_jsonl(evidence_dir / "segments.jsonl", segments)
    plan = create_batch_plan(segments, CONFIG["locales"]["source"], [target_locale], max_segments)
    write_json(evidence_dir / "batch-plan.json", plan)

    packet_dir = evidence_dir / "work-packets"
    request_dir = evidence_dir / "draft-requests"
    for batch in plan["batches"]:
        batch_id = batch["batch_id"]
        packet = build_work_packet(plan, batch_id, segments, state_dir, target_locale)
        write_json(packet_dir / f"{batch_id}.json", packet)
        draft_request = create_draft_request(packet)
        write_json(request_dir / f"{batch_id}.json", draft_request)

    generated_dir = (external_generated_dir.resolve() if external_generated_dir else evidence_dir / "generated-batches")
    handoff = create_generation_handoff(packet_dir, request_dir, generated_dir, target_locale)
    write_json(evidence_dir / "generation-handoff.json", handoff)
    if handoff_only:
        summary = {
            "benchmark_id": CONFIG["id"],
            "workspace": workspace.as_posix(),
            "mode": "handoff_only",
            "source_file": source_file,
            "source_sha256": _sha256(source_path),
            "adapter_counts": inspection["adapter_counts"],
            "segments": len(segments),
            "batches": len(plan["batches"]),
            "handoff_manifest": (evidence_dir / "generation-handoff.json").as_posix(),
            "generated_dir": generated_dir.as_posix(),
        }
        write_json(evidence_dir / "summary.json", summary)
        return summary

    if external_generated_dir is None:
        for batch in plan["batches"]:
            packet = json.loads((packet_dir / f"{batch['batch_id']}.json").read_text(encoding="utf-8"))
            generated_batch = [_synthetic_target(segment, target_locale) for segment in packet["segments"]]
            write_jsonl(generated_dir / f"{batch['batch_id']}.jsonl", generated_batch)

    collected_path = evidence_dir / "generated.jsonl"
    generation_collect = collect_generated_handoff(handoff, collected_path)
    write_json(evidence_dir / "generation-collect.json", generation_collect)
    if generation_collect["status"] == "fail":
        raise ValueError("Generated batches failed validation; see generation-collect.json")
    generated = read_jsonl(collected_path)
    staging = stage_rebuild(source_path, generated, staging_dir, target_locale, source_root)
    write_json(evidence_dir / "staging-result.json", staging)

    staged_target = staging_dir / staging["destination"]
    qa = validate_pair(source_path, staged_target)
    write_json(evidence_dir / "android-qa.json", qa)
    packaged = package_delivery(
        state_dir,
        staging_dir,
        deliveries_dir,
        [evidence_dir / "generation-collect.json", evidence_dir / "android-qa.json"],
        "draft_package",
        CONFIG["id"],
    )
    delivery_dir = Path(packaged["delivery_directory"])
    dashboard = build_delivery_dashboard(delivery_dir)
    write_json(evidence_dir / "delivery-dashboard.json", dashboard)
    (evidence_dir / "delivery-dashboard.md").write_text(render_dashboard_markdown(dashboard), encoding="utf-8", newline="\n")

    summary = {
        "benchmark_id": CONFIG["id"],
        "workspace": workspace.as_posix(),
        "source_file": source_file,
        "source_sha256": _sha256(source_path),
        "generation_mode": "external" if external_generated_dir else "synthetic",
        "adapter_counts": inspection["adapter_counts"],
        "segments": len(segments),
        "batches": len(plan["batches"]),
        "staged_destination": staging["destination"],
        "qa_status": qa["status"],
        "qa_blocking": qa["summary"]["blocking_count"],
        "qa_warnings": qa["summary"]["warning_count"],
        "delivery_directory": delivery_dir.as_posix(),
        "dashboard_json": (evidence_dir / "delivery-dashboard.json").as_posix(),
        "dashboard_markdown": (evidence_dir / "delivery-dashboard.md").as_posix(),
        "handoff_manifest": (evidence_dir / "generation-handoff.json").as_posix(),
        "generation_collect": (evidence_dir / "generation-collect.json").as_posix(),
    }
    write_json(evidence_dir / "summary.json", summary)
    return summary


def _synthetic_target(segment: dict[str, Any], target_locale: str) -> dict[str, Any]:
    generated = dict(segment)
    generated["target_locale"] = target_locale
    generated["target"] = f"[{target_locale}] {segment['source']}"
    generated["status"] = "generated"
    generated["generation"] = {
        "kind": "synthetic_draft",
        "quality_claim": "none",
        "purpose": "adapter_delivery_verification",
    }
    return generated


def _download(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:
        destination.write_bytes(response.read())


def _verify_hash(path: Path, expected: str) -> None:
    actual = _sha256(path)
    if actual != expected:
        raise ValueError(f"Hash mismatch for {path}: expected {expected}, got {actual}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
