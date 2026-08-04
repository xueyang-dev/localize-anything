"""Prepare the pinned Hermes Agent blind benchmark workspace."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path

from common import (
    BENCH_ROOT,
    BLIND,
    CONFIG,
    COPY,
    REFERENCE,
    SOURCE,
    STAGING,
    WORK,
    environment_record,
    run,
    write_json,
)


UPSTREAM = CONFIG["upstream"]
COMMIT = UPSTREAM["commit"]
SURFACES = CONFIG["surfaces"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the Hermes Agent blind benchmark")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("source", help="Clone/pin the upstream source checkout")
    subparsers.add_parser("blind", help="Build the blind English-only generation workspace")
    subparsers.add_parser("reference", help="Reveal official French references after generation")
    subparsers.add_parser("copy", help="Create the isolated apply-to-copy checkout")
    args = parser.parse_args()
    if args.command == "source":
        prepare_source()
    elif args.command == "blind":
        prepare_blind()
    elif args.command == "reference":
        prepare_reference()
    else:
        prepare_copy()
    return 0


def prepare_source() -> None:
    if SOURCE.is_dir() and _commit(SOURCE) == COMMIT:
        _verify_clean(SOURCE)
        _record_source_provenance(existing=True)
        print(f"source already pinned at {COMMIT}")
        return
    if SOURCE.exists():
        raise ValueError(f"source exists with unexpected commit {_commit(SOURCE)}; remove {SOURCE} manually")
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    result = run(["git", "init", "--quiet", str(SOURCE)])
    if result.returncode != 0:
        raise ValueError(f"git init failed: {result.stderr[-2000:]}")
    for argument in (
        ["remote", "add", "origin", UPSTREAM["repository"]],
        ["config", "core.autocrlf", "false"],
        ["config", "remote.origin.promisor", "true"],
        ["config", "remote.origin.partialclonefilter", "blob:none"],
    ):
        result = run(["git", "-C", str(SOURCE), *argument])
        if result.returncode != 0:
            raise ValueError(f"git {argument[0]} failed: {result.stderr[-2000:]}")
    result = run(["git", "-C", str(SOURCE), "fetch", "--depth=1", "--filter=blob:none", "--no-tags", "origin", COMMIT])
    if result.returncode != 0:
        raise ValueError(f"pinned fetch failed: {result.stderr[-2000:]}")
    result = run(["git", "-C", str(SOURCE), "checkout", "--quiet", "--detach", "FETCH_HEAD"])
    if result.returncode != 0:
        raise ValueError(f"pinned checkout failed: {result.stderr[-2000:]}")
    if _commit(SOURCE) != COMMIT:
        raise ValueError(f"unexpected HEAD {_commit(SOURCE)}; expected {COMMIT}")
    _verify_clean(SOURCE)
    _record_source_provenance(existing=False)
    print(f"source pinned at {COMMIT}")


def prepare_blind() -> None:
    if BLIND.exists():
        raise ValueError(f"blind workspace already exists: {BLIND}")
    source_files = {
        "yaml": ["locales/en.yaml"],
        "web": ["web/src/i18n/en.ts"],
        "desktop": ["apps/desktop/src/i18n/en.ts"],
    }
    surface_keys = {"yaml": "yaml_cli_gateway", "web": "web_dashboard", "desktop": "desktop"}
    BLIND.mkdir(parents=True)
    hidden: dict[str, dict[str, str]] = {}
    for surface, relative_paths in source_files.items():
        for relative_path in relative_paths:
            source_path = SOURCE / relative_path
            if not source_path.is_file():
                raise ValueError(f"missing source file: {source_path}")
            destination = BLIND / surface / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
        hidden[surface] = {
            reference: _sha256(SOURCE / reference)
            for reference in SURFACES[surface_keys[surface]].get("reference", [])
        }
    _assert_no_french(BLIND)
    write_json(
        {
            "benchmark_id": CONFIG["id"],
            "commit": COMMIT,
            "target_locale": CONFIG["target_locale"],
            "blind_generation_workspace": True,
            "hidden_reference_sha256": hidden,
            "note": "Official French resources exist in the source checkout but were NOT copied into the blind workspace; only their hashes are recorded here.",
            "environment": environment_record(),
        },
        BLIND / "blind-provenance.json",
    )
    print(f"blind workspace ready at {BLIND}")


def prepare_reference() -> None:
    if REFERENCE.exists():
        raise ValueError(f"reference workspace already exists: {REFERENCE}")
    for surface in ("yaml", "web"):
        staged = STAGING / surface
        if not (staged / "fr.yaml").is_file() and not (staged / "fr.ts").is_file():
            raise ValueError(f"staged output missing for {surface}; run the benchmark before revealing references")
    REFERENCE.mkdir(parents=True)
    surface_keys = {"yaml": "yaml_cli_gateway", "web": "web_dashboard"}
    for surface in ("yaml", "web"):
        official = SURFACES[surface_keys[surface]].get("reference", [])
        if not official:
            continue
        destination_dir = REFERENCE / surface
        destination_dir.mkdir(parents=True, exist_ok=True)
        revealed: dict[str, str] = {}
        for relative_path in official:
            source_path = SOURCE / relative_path
            destination = destination_dir / Path(relative_path).name
            shutil.copy2(source_path, destination)
            revealed[relative_path] = _sha256(destination)
        write_json(
            {
                "benchmark_id": CONFIG["id"],
                "commit": COMMIT,
                "surface": surface,
                "revealed_reference_sha256": revealed,
                "released_after_generation": True,
                "note": "Official translations are references for comparison, not unique ground truth.",
            },
            destination_dir / "reference-provenance.json",
        )
    print(f"references revealed at {REFERENCE}")


def prepare_copy() -> None:
    if COPY.exists():
        raise ValueError(f"isolated copy already exists: {COPY}")
    if not SOURCE.is_dir():
        raise ValueError("source checkout missing; run `python prepare.py source` first")
    COPY.mkdir(parents=True)
    shutil.copytree(SOURCE, COPY / "hermes", ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", ".venv"))
    write_json(
        {
            "benchmark_id": CONFIG["id"],
            "commit": COMMIT,
            "isolated_copy": True,
            "note": "Staged localizations are applied only to this copy; the original checkout is never mutated.",
        },
        COPY / "copy-provenance.json",
    )
    print(f"isolated copy ready at {COPY / 'hermes'}")


def _assert_no_french(root: Path) -> None:
    french = [path for path in root.rglob("*") if path.suffix in {".yaml", ".yml", ".ts"} and "fr" in path.name.lower()]
    if french:
        raise ValueError(f"blind workspace leaks French resources: {[p.as_posix() for p in french]}")


def _record_source_provenance(existing: bool) -> None:
    write_json(
        {
            "benchmark_id": CONFIG["id"],
            "repository": UPSTREAM["repository"],
            "commit": COMMIT,
            "commit_date": UPSTREAM["commit_date"],
            "version": UPSTREAM["version"],
            "clone": "existing_pinned_checkout" if existing else "shallow_blobless_clone",
            "environment": environment_record(),
        },
        WORK / "source-provenance.json",
    )


def _verify_clean(path: Path) -> None:
    result = run(["git", "-C", str(path), "status", "--porcelain"])
    if result.returncode != 0 or result.stdout.strip():
        raise ValueError(f"source checkout is not clean: {result.stdout.strip()[:2000]}")


def _commit(path: Path) -> str:
    result = run(["git", "-C", str(path), "rev-parse", "HEAD"])
    if result.returncode != 0:
        raise ValueError(f"cannot resolve HEAD in {path}: {result.stderr[-500:]}")
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
