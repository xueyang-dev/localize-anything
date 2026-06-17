from __future__ import annotations

import argparse
import copy
import gc
import json
import platform
import tempfile
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
import shutil
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from runtime.localize_anything import __version__
from runtime.localize_anything.apply import create_apply_plan
from runtime.localize_anything.delivery import package_delivery
from runtime.localize_anything.io_utils import write_json, write_jsonl
from runtime.localize_anything.json_adapter import extract_segments, rebuild, source_hash, validate_pair
from runtime.localize_anything.planning import create_batch_plan
from runtime.localize_anything.project import initialize_project
from runtime.localize_anything.retrieval import build_work_packet
from runtime.localize_anything.review import import_review
from runtime.localize_anything.segments import diff_segments


def main() -> int:
    args = parse_args()
    report = run_stress(args)
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    print(encoded)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded + "\n", encoding="utf-8")
    return 0 if report["status"] == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the v0.1 synthetic runtime stress benchmark")
    parser.add_argument("--segments", type=int, default=10_000, help="Number of JSON locale string segments")
    parser.add_argument("--namespaces", type=int, default=100, help="Top-level JSON namespaces")
    parser.add_argument("--max-segments-per-batch", type=int, default=80)
    parser.add_argument("--packet-samples", type=int, default=3, help="Number of work packets to build")
    parser.add_argument("--tm-packet-samples", type=int, default=1, help="Number of post-review TM packets to build")
    parser.add_argument("--max-total-seconds", type=float, default=15.0)
    parser.add_argument("--max-peak-mb", type=float, default=512.0)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--keep-workdir", action="store_true", help="Preserve the generated synthetic project")
    return parser.parse_args()


def run_stress(args: argparse.Namespace) -> dict[str, Any]:
    if args.segments < 1:
        raise ValueError("--segments must be positive")
    if args.namespaces < 1:
        raise ValueError("--namespaces must be positive")

    tracemalloc.start()
    stages: list[dict[str, Any]] = []
    workdir = Path(tempfile.mkdtemp(prefix="localize-anything-stress-"))
    try:
        project = workdir / "project"
        source = project / "locales" / "en-US.json"
        staging = workdir / "staging"
        output = staging / "locales" / "zh-CN.json"
        deliveries = workdir / "deliveries"

        stage(stages, "generate_synthetic_project", lambda: write_synthetic_project(source, args.segments, args.namespaces))
        state_dir = stage(
            stages,
            "preflight_initialize",
            lambda: Path(initialize_project(project, "en-US", ["locales/en-US.json"], ["zh-CN"])["state_directory"]),
        )
        segments = stage(stages, "extract_json_segments", lambda: extract_segments(source, "en-US", "locales/en-US.json"))
        translated = stage(stages, "prepare_targets", lambda: translated_segments(segments))
        plan = stage(
            stages,
            "create_batch_plan",
            lambda: create_batch_plan(translated, "en-US", ["zh-CN"], max_segments=args.max_segments_per_batch),
        )
        packet_ids = sampled_batch_ids(plan, args.packet_samples)
        packets = stage(
            stages,
            "build_work_packets",
            lambda: [build_work_packet(plan, batch_id, translated, state_dir, "zh-CN") for batch_id in packet_ids],
        )
        stage(stages, "rebuild_json_target", lambda: rebuild(source, translated, output))
        qa_result = stage(stages, "validate_json_target", lambda: validate_pair(source, output))
        diff_result = stage(stages, "diff_incremental_segments", lambda: diff_segments(translated, mutated_segments(translated)))
        review_result = stage(
            stages,
            "review_import",
            lambda: run_review_import(workdir, translated, state_dir),
        )
        tm_packet_ids = sampled_batch_ids(plan, args.tm_packet_samples)
        tm_packets = stage(
            stages,
            "build_work_packets_with_tm",
            lambda: [build_work_packet(plan, batch_id, translated, state_dir, "zh-CN") for batch_id in tm_packet_ids],
        )
        packaged = stage(
            stages,
            "package_delivery",
            lambda: run_package_delivery(workdir, state_dir, staging, deliveries, qa_result),
        )
        apply_plan = stage(
            stages,
            "plan_apply_dry_run",
            lambda: create_apply_plan(Path(packaged["delivery_directory"]), project),
        )

        total_seconds = sum(item["seconds"] for item in stages)
        peak_mb = max(item["peak_traced_mb"] for item in stages)
        failures = gate_failures(args, total_seconds, peak_mb, qa_result, apply_plan)
        summary = {
            "segments": len(segments),
            "namespaces": min(args.namespaces, args.segments),
            "batches": len(plan["batches"]),
            "packet_samples": len(packets),
            "tm_packet_samples": len(tm_packets),
            "total_seconds": round(total_seconds, 6),
            "peak_traced_mb": round(peak_mb, 3),
            "throughput_segments_per_second": round(len(segments) / total_seconds, 2) if total_seconds else None,
            "qa_status": qa_result["status"],
            "review_tm_updates": review_result["tm_updates"],
            "diff_summary": diff_result["summary"],
            "apply_summary": apply_plan["summary"],
            "delivery_size_bytes": directory_size(Path(packaged["delivery_directory"])),
        }
        return {
            "benchmark": "stress-v01",
            "runtime_version": __version__,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "status": "fail" if failures else "pass",
            "gate": {
                "max_total_seconds": args.max_total_seconds,
                "max_peak_mb": args.max_peak_mb,
                "failures": failures,
            },
            "summary": summary,
            "stages": stages,
            "workdir": str(workdir) if args.keep_workdir else None,
        }
    finally:
        tracemalloc.stop()
        if not args.keep_workdir:
            shutil.rmtree(workdir, ignore_errors=True)


def stage(stages: list[dict[str, Any]], name: str, action: Callable[[], Any]) -> Any:
    gc.collect()
    tracemalloc.reset_peak()
    started = time.perf_counter()
    result = action()
    seconds = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    stages.append(
        {
            "name": name,
            "seconds": round(seconds, 6),
            "peak_traced_mb": round(peak / (1024 * 1024), 3),
        }
    )
    return result


def write_synthetic_project(path: Path, segment_count: int, namespace_count: int) -> None:
    namespace_count = min(namespace_count, segment_count)
    document: dict[str, dict[str, str]] = {f"screen_{index:04d}": {} for index in range(namespace_count)}
    for index in range(segment_count):
        namespace = f"screen_{index % namespace_count:04d}"
        document[namespace][f"message_{index:06d}"] = (
            f"Quest {index:06d}: {{player}} has {{{{count}}}} coins and %s kg in zone {index % 17}."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def translated_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    translated = copy.deepcopy(segments)
    for index, segment in enumerate(translated):
        segment["target_locale"] = "zh-CN"
        segment["target"] = f"\u8bd1\u6587 {index:06d}: {{player}} has {{{{count}}}} coins and %s kg."
        segment["status"] = "generated"
    return translated


def sampled_batch_ids(plan: dict[str, Any], count: int) -> list[str]:
    batches = plan["batches"]
    if count <= 0 or not batches:
        return []
    indexes = sorted(set(round(index) for index in linspace(0, len(batches) - 1, min(count, len(batches)))))
    return [batches[index]["batch_id"] for index in indexes]


def linspace(start: int, stop: int, count: int) -> list[float]:
    if count == 1:
        return [float(start)]
    step = (stop - start) / (count - 1)
    return [start + step * index for index in range(count)]


def mutated_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = copy.deepcopy(segments)
    if len(current) < 4:
        return current
    current[0]["source_hash"] = source_hash(current[0]["source"] + " changed")
    current[1]["segment_id"] = current[1]["segment_id"] + "#moved"
    del current[2]
    new_segment = copy.deepcopy(current[2])
    new_segment["segment_id"] = "json:locales/en-US.json#/stress/new"
    new_segment["source"] = "New stress segment {player}"
    new_segment["source_hash"] = source_hash(new_segment["source"])
    current.append(new_segment)
    return current


def run_review_import(workdir: Path, generated: list[dict[str, Any]], state_dir: Path) -> dict[str, Any]:
    reviewed = copy.deepcopy(generated)
    for segment in reviewed:
        segment["status"] = "reviewed"
    if reviewed:
        reviewed[0]["target"] = reviewed[0]["target"] + " reviewed"
    generated_path = workdir / "generated.jsonl"
    reviewed_path = workdir / "reviewed.jsonl"
    write_jsonl(generated_path, generated)
    write_jsonl(reviewed_path, reviewed)
    return import_review(generated_path, reviewed_path, state_dir, "stress-v01", "zh-CN")


def run_package_delivery(
    workdir: Path,
    state_dir: Path,
    staging: Path,
    deliveries: Path,
    qa_result: dict[str, Any],
) -> dict[str, Any]:
    adapter_qa = workdir / "adapter-qa.json"
    agent_qa = workdir / "agent-qa.json"
    write_json(adapter_qa, qa_result)
    write_json(agent_qa, {"protocol_version": "0.1", "status": "pass", "evidence_channels": ["agent"], "items": []})
    return package_delivery(state_dir, staging, deliveries, [adapter_qa, agent_qa], "review_ready", "stress-v01")


def gate_failures(
    args: argparse.Namespace,
    total_seconds: float,
    peak_mb: float,
    qa_result: dict[str, Any],
    apply_plan: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    if total_seconds > args.max_total_seconds:
        failures.append(f"total_seconds {total_seconds:.3f} > {args.max_total_seconds:.3f}")
    if peak_mb > args.max_peak_mb:
        failures.append(f"peak_traced_mb {peak_mb:.3f} > {args.max_peak_mb:.3f}")
    if qa_result.get("status") != "pass":
        failures.append(f"qa_status {qa_result.get('status')!r} != 'pass'")
    if apply_plan.get("blocked_by_conflicts"):
        failures.append("apply dry run reported conflicts")
    return failures


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


if __name__ == "__main__":
    raise SystemExit(main())
