from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY))

from runtime.localize_anything.gettext_adapter import extract_segments, validate_pair  # noqa: E402
from runtime.localize_anything.wesnoth_adapter import enrich_segments, validate_source  # noqa: E402


CONFIG = json.loads((ROOT / "benchmark.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify The South Guard benchmark boundaries and E0 results")
    subparsers = parser.add_subparsers(dest="command", required=True)
    source = subparsers.add_parser("source", help="Verify the blind generation workspace")
    source.add_argument("workspace", type=Path)
    result = subparsers.add_parser("result", help="Run E0 structural checks on a generated PO")
    result.add_argument("workspace", type=Path)
    result.add_argument("generated_po", type=Path)
    result.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "source":
        value = verify_source(args.workspace)
    else:
        value = verify_result(args.workspace, args.generated_po)
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if getattr(args, "output", None):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0 if value["status"] in {"pass", "pass_with_warnings"} else 1


def verify_source(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    source_root = workspace / "source"
    upstream = CONFIG["upstream"]
    provenance_path = workspace / "source-provenance.json"
    if not provenance_path.is_file():
        raise ValueError("Missing source-provenance.json")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance.get("commit") != upstream["commit"]:
        raise ValueError("Workspace provenance does not match the pinned commit")
    pot = source_root / upstream["source_template"]
    if _sha256(pot) != upstream["source_template_sha256"]:
        raise ValueError("Source POT hash does not match benchmark.json")
    forbidden = [path for path in source_root.rglob("*") if path.is_file() and path.name.lower() == "zh_cn.po"]
    if (workspace / "reference").exists():
        forbidden.append(workspace / "reference")
    if forbidden:
        raise ValueError("Blind source workspace contains forbidden target reference material")
    segments = extract_segments(pot, CONFIG["locales"]["source"], upstream["source_template"])
    enriched = enrich_segments(segments, source_root)
    context_qa = validate_source(source_root, segments)
    enriched_count = sum(bool(item.get("context", {}).get("scenario")) for item in enriched)
    return {
        "status": context_qa["status"],
        "benchmark_id": CONFIG["id"],
        "commit": upstream["commit"],
        "source_segments": len(segments),
        "segments_with_scenario_context": enriched_count,
        "context_warning_count": context_qa["summary"]["warning_count"],
        "blind_boundary": "pass",
    }


def verify_result(workspace: Path, generated_po: Path) -> dict[str, object]:
    source_summary = verify_source(workspace)
    source_pot = workspace.resolve() / "source" / CONFIG["upstream"]["source_template"]
    qa = validate_pair(source_pot, generated_po.resolve())
    return {
        "status": qa["status"],
        "benchmark_id": CONFIG["id"],
        "evidence_level": "E0",
        "source": source_summary,
        "structural_qa": qa,
        "generated_sha256": _sha256(generated_po.resolve()),
        "human_review_performed": False,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
