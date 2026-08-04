"""Phase 2: verify the pinned source checkout and blind workspace."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from common import BENCH_ROOT, BLIND, CONFIG, REPORTS, SOURCE, WORK, run, write_json

sys.path.insert(0, str(BENCH_ROOT))

from runtime.localize_anything.structured_adapter import extract_segments as extract_yaml  # noqa: E402
from runtime.localize_anything.typescript_locale_adapter import extract_segments as extract_ts  # noqa: E402


COMMIT = CONFIG["upstream"]["commit"]
YAML_CATALOGS = sorted((SOURCE / "locales").glob("*.yaml"))
WEB_LOCALES = ["af", "ar", "de", "en", "es", "fr", "ga", "hu", "it", "ja", "ko", "pt", "ru", "tr", "uk", "zh", "zh-hant"]
DESKTOP_LOCALES = ["en", "zh", "zh-hant", "ja", "ar"]
TS_CATALOGS = [SOURCE / "web/src/i18n" / f"{locale}.ts" for locale in WEB_LOCALES] + [
    SOURCE / "apps/desktop/src/i18n" / f"{locale}.ts" for locale in DESKTOP_LOCALES
]


def main() -> int:
    items: list[dict[str, object]] = []
    ok = True

    def check(category: str, condition: bool, message: str) -> None:
        nonlocal ok
        severity = "blocking" if not condition else "pass"
        ok = ok and condition
        items.append({"category": category, "severity": severity, "message": message})

    check("pinned_commit", _commit() == COMMIT, f"HEAD is {_commit()}, expected {COMMIT}")
    check("clean_checkout", _clean(), "source checkout has uncommitted changes")
    check("expected_paths", _expected_paths(), "expected catalog paths missing")
    check("yaml_parse", _yaml_parses(), "one or more YAML catalogs fail to parse/extract")
    check("ts_parse", _ts_parses(), "one or more TypeScript catalogs fail to parse/extract")
    check("blind_workspace", BLIND.is_dir(), "blind workspace present (run `python prepare.py blind`)")
    if BLIND.is_dir():
        check("blind_no_french", _blind_has_no_french(), "blind workspace contains no French resources")
        check("blind_english_parity", _blind_matches_source(), "blind English sources match the pinned checkout")
    check("work_ignored", _work_ignored(), "work/ is not ignored by git")

    report = {
        "protocol_version": CONFIG["protocol_version"],
        "benchmark_id": CONFIG["id"],
        "status": "pass" if ok else "fail",
        "pinned_commit": COMMIT,
        "source_hashes": _source_hashes(),
        "items": items,
    }
    REPORTS.mkdir(exist_ok=True)
    write_json(report, REPORTS / "source-verification.json")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def _commit() -> str:
    result = run(["git", "-C", str(SOURCE), "rev-parse", "HEAD"])
    return result.stdout.strip()


def _clean() -> bool:
    result = run(["git", "-C", str(SOURCE), "status", "--porcelain"])
    return result.returncode == 0 and not result.stdout.strip()


def _expected_paths() -> bool:
    required = [
        SOURCE / "locales/en.yaml",
        SOURCE / "locales/fr.yaml",
        SOURCE / "agent/i18n.py",
        SOURCE / "web/src/i18n/en.ts",
        SOURCE / "web/src/i18n/fr.ts",
        SOURCE / "web/src/i18n/types.ts",
        SOURCE / "web/src/i18n/context.tsx",
        SOURCE / "apps/desktop/src/i18n/en.ts",
        SOURCE / "apps/desktop/src/i18n/types.ts",
        SOURCE / "apps/desktop/src/i18n/catalog.ts",
        SOURCE / "apps/desktop/src/i18n/languages.ts",
        SOURCE / "website/docusaurus.config.ts",
    ]
    return all(path.is_file() for path in required)


def _yaml_parses() -> bool:
    try:
        for path in YAML_CATALOGS:
            extract_yaml(path, "en", path.relative_to(SOURCE).as_posix())
        return True
    except Exception:
        return False


def _ts_parses() -> bool:
    try:
        for path in TS_CATALOGS:
            extract_ts(path, "en", path.relative_to(SOURCE).as_posix())
        return True
    except Exception:
        return False


def _blind_has_no_french() -> bool:
    french = [p for p in BLIND.rglob("*") if p.suffix in {".yaml", ".yml", ".ts"} and "fr" in p.name.lower()]
    return not french


def _blind_matches_source() -> bool:
    for path in BLIND.rglob("*.yaml"):
        source = SOURCE / Path(*path.relative_to(BLIND).parts[1:])
        if not source.is_file() or _sha256(path) != _sha256(source):
            return False
    for path in BLIND.rglob("*.ts"):
        source = SOURCE / Path(*path.relative_to(BLIND).parts[1:])
        if not source.is_file() or _sha256(path) != _sha256(source):
            return False
    return True


def _work_ignored() -> bool:
    result = run(["git", "-C", str(BENCH_ROOT.parents[1]), "check-ignore", str(WORK)])
    return result.returncode == 0


def _source_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in [SOURCE / "locales/en.yaml", SOURCE / "locales/fr.yaml", SOURCE / "web/src/i18n/en.ts", SOURCE / "apps/desktop/src/i18n/en.ts"]:
        hashes[path.relative_to(SOURCE).as_posix()] = _sha256(path)
    return hashes


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
