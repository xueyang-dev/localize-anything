from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
sys.path.insert(0, str(REPOSITORY))

from runtime.localize_anything.gettext_adapter import parse_po  # noqa: E402


CONFIG = json.loads((ROOT / "benchmark.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the pinned The South Guard blind benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)
    source = subparsers.add_parser("source", help="Prepare generation-only POT and WML source")
    source.add_argument("workspace", type=Path)
    reference = subparsers.add_parser("reference", help="Prepare the isolated evaluation reference after generation")
    reference.add_argument("workspace", type=Path)
    reference.add_argument("--generated-po", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "source":
        prepare_source(args.workspace)
    else:
        prepare_reference(args.workspace, args.generated_po)
    return 0


def prepare_source(workspace: Path) -> None:
    workspace = workspace.resolve()
    source_root = workspace / "source"
    if source_root.exists():
        raise ValueError(f"Source workspace already exists: {source_root}")
    upstream = CONFIG["upstream"]
    workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="localize-anything-wesnoth-") as directory:
        checkout = Path(directory) / "checkout"
        _checkout_paths(
            checkout,
            [upstream["scenario_root"] + "/", upstream["source_template"], "COPYING"],
        )
        pot = checkout / upstream["source_template"]
        _verify_hash(pot, upstream["source_template_sha256"])
        source_root.mkdir()
        shutil.copytree(checkout / upstream["scenario_root"], source_root / upstream["scenario_root"])
        destination_pot = source_root / upstream["source_template"]
        destination_pot.parent.mkdir(parents=True)
        shutil.copy2(pot, destination_pot)
        shutil.copy2(checkout / "COPYING", source_root / "UPSTREAM-COPYING")
    provenance = {
        "benchmark_id": CONFIG["id"],
        "repository": upstream["repository"],
        "commit": upstream["commit"],
        "source_template": upstream["source_template"],
        "source_template_sha256": upstream["source_template_sha256"],
        "blind_generation_workspace": True,
        "reference_present": False,
    }
    (workspace / "source-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")


def prepare_reference(workspace: Path, generated_po: Path) -> None:
    workspace = workspace.resolve()
    generated_po = generated_po.resolve()
    if not generated_po.is_file() or generated_po.stat().st_size == 0:
        raise ValueError("A non-empty generated PO is required before releasing the evaluation reference")
    source_root = workspace / "source"
    if generated_po.is_relative_to(source_root):
        raise ValueError("The generated PO must be outside the blind source workspace")
    generated_hash = _sha256(generated_po)
    if generated_hash == CONFIG["upstream"]["source_template_sha256"]:
        raise ValueError("The generated PO is identical to the source POT")
    generated_document = parse_po(generated_po)
    if not any(entry.msgid and any(field.value for field in entry.msgstr_fields()) for entry in generated_document.entries):
        raise ValueError("The generated PO contains no non-empty target translation")
    reference_root = workspace / "reference"
    if reference_root.exists():
        raise ValueError(f"Reference directory already exists: {reference_root}")
    upstream = CONFIG["upstream"]
    temporary = Path(tempfile.mkdtemp(prefix=".reference.", dir=workspace))
    try:
        checkout = temporary / "checkout"
        _checkout_paths(checkout, [upstream["evaluation_reference"]])
        destination = temporary / "zh_CN.po"
        shutil.copy2(checkout / upstream["evaluation_reference"], destination)
        shutil.rmtree(checkout)
        _verify_hash(destination, upstream["evaluation_reference_sha256"])
        metadata = {
            "benchmark_id": CONFIG["id"],
            "commit": upstream["commit"],
            "reference_sha256": upstream["evaluation_reference_sha256"],
            "released_after_generated_file": generated_po.as_posix(),
            "generated_sha256": generated_hash,
        }
        (temporary / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, reference_root)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _checkout_paths(checkout: Path, paths: list[str]) -> None:
    upstream = CONFIG["upstream"]
    _run(["git", "init", "--quiet", str(checkout)])
    _run(["git", "-C", str(checkout), "remote", "add", "origin", upstream["repository"]])
    _run(["git", "-C", str(checkout), "config", "core.autocrlf", "false"])
    _run(["git", "-C", str(checkout), "config", "core.eol", "lf"])
    _run(["git", "-C", str(checkout), "config", "remote.origin.promisor", "true"])
    _run(["git", "-C", str(checkout), "config", "remote.origin.partialclonefilter", "blob:none"])
    _run(["git", "-C", str(checkout), "config", "core.sparseCheckout", "true"])
    sparse_file = checkout / ".git" / "info" / "sparse-checkout"
    sparse_file.write_text("".join(f"/{path}\n" for path in paths), encoding="utf-8")
    _run(
        [
            "git",
            "-C",
            str(checkout),
            "fetch",
            "--quiet",
            "--depth=1",
            "--filter=blob:none",
            "--no-tags",
            "origin",
            upstream["commit"],
        ]
    )
    _run(["git", "-C", str(checkout), "checkout", "--quiet", "--detach", "FETCH_HEAD"])
    actual = _run(["git", "-C", str(checkout), "rev-parse", "HEAD"], capture=True).strip()
    if actual != upstream["commit"]:
        raise ValueError(f"Fetched unexpected commit: {actual}")


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


def _run(command: list[str], capture: bool = False) -> str:
    result = subprocess.run(command, check=True, text=True, capture_output=capture)
    return result.stdout if capture else ""


if __name__ == "__main__":
    raise SystemExit(main())
