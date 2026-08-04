"""Phase 11: apply staged catalogs to the isolated copy and run Hermes checks."""

from __future__ import annotations

import json
import re
import shutil
import sys
import time
from pathlib import Path

from common import BENCH_ROOT, CONFIG, COPY, REPORTS, STAGING, report_markdown, run, write_json


def main() -> int:
    hermes = COPY / "hermes"
    if not hermes.is_dir():
        raise ValueError("isolated copy missing; run `python prepare.py copy` first")
    _apply_staged(hermes)
    evidence: dict[str, object] = {
        "protocol_version": CONFIG["protocol_version"],
        "benchmark_id": CONFIG["id"],
        "commit": CONFIG["upstream"]["commit"],
        "steps": [],
    }
    _python_checks(hermes, evidence)
    _web_checks(hermes, evidence)
    _desktop_checks(hermes, evidence)
    REPORTS.mkdir(exist_ok=True)
    write_json(evidence, REPORTS / "build-validation.json")
    write_json(report_markdown(evidence, "build-validation.md"), REPORTS / "build-validation.md", raw=True)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


def _apply_staged(hermes: Path) -> None:
    shutil.copy2(STAGING / "yaml" / "fr.yaml", hermes / "locales" / "fr.yaml")
    shutil.copy2(STAGING / "web" / "fr.ts", hermes / "web/src/i18n" / "fr.ts")
    shutil.copy2(STAGING / "desktop" / "fr.ts", hermes / "apps/desktop/src/i18n" / "fr.ts")
    _edit_desktop_registration(hermes)


def _edit_desktop_registration(hermes: Path) -> None:
    types_path = hermes / "apps/desktop/src/i18n/types.ts"
    types_text = types_path.read_text(encoding="utf-8")
    anchor = "export type Locale = 'en' | 'zh' | 'zh-hant' | 'ja' | 'ar'"
    if "| 'fr'" not in types_text:
        if anchor not in types_text:
            raise ValueError("desktop types.ts Locale anchor not found")
        types_path.write_text(types_text.replace(anchor, "export type Locale = 'en' | 'zh' | 'zh-hant' | 'ja' | 'ar' | 'fr'"), encoding="utf-8")

    catalog_path = hermes / "apps/desktop/src/i18n/catalog.ts"
    catalog_text = catalog_path.read_text(encoding="utf-8")
    if "from './fr'" not in catalog_text:
        if "import { en } from './en'" not in catalog_text:
            raise ValueError("desktop catalog.ts import anchor not found")
        catalog_text = catalog_text.replace("import { en } from './en'", "import { en } from './en'\nimport { fr } from './fr'", 1)
    if re.search(r"^\s*fr,?\s*$", catalog_text, re.M) is None:
        if "  ar\n}" not in catalog_text:
            raise ValueError("desktop catalog.ts record anchor not found")
        catalog_text = catalog_text.replace("  ar\n}", "  ar,\n  fr\n}", 1)
    catalog_path.write_text(catalog_text, encoding="utf-8")

    languages_path = hermes / "apps/desktop/src/i18n/languages.ts"
    languages_text = languages_path.read_text(encoding="utf-8")
    fr_option = "{\n    id: 'fr',\n    name: 'Français',\n    englishName: 'French',\n    configValue: 'fr'\n  },"
    if "id: 'fr'" not in languages_text:
        ar_anchor = "  {\n    id: 'ar',"
        if ar_anchor not in languages_text:
            raise ValueError("desktop languages.ts option anchor not found")
        languages_text = languages_text.replace(ar_anchor, fr_option + "\n" + ar_anchor, 1)
    if re.search(r"^\s{2}fr: 'fr',$", languages_text, re.M) is None:
        alias_anchor = "  ar: 'ar',"
        if alias_anchor not in languages_text:
            raise ValueError("desktop languages.ts alias anchor not found")
        languages_text = languages_text.replace(
            alias_anchor,
            "  ar: 'ar',\n  fr: 'fr',\n  'fr-fr': 'fr',\n  'fr-ca': 'fr',\n  'fr-be': 'fr',\n  'fr-ch': 'fr',\n  francais: 'fr',\n  français: 'fr',",
            1,
        )
    languages_path.write_text(languages_text, encoding="utf-8")


def _python_checks(hermes: Path, evidence: dict[str, object]) -> None:
    venv_python = hermes / ".venv/bin/python"
    if not venv_python.is_file():
        raise ValueError(
            "hermes test venv missing; create it with `cd work/copy/hermes && uv sync --frozen` "
            "or pip install -e . into work/venv"
        )
    steps = evidence["steps"]
    for label, command in [
        ("hermes_i18n_parity_tests", [str(venv_python), "-m", "pytest", "tests/agent/test_i18n.py", "-q"]),
        ("hermes_python_compileall", ["python3", "-m", "compileall", "-q", "agent", "hermes_cli", "gateway"]),
    ]:
        started = time.monotonic()
        result = run(command, cwd=hermes, timeout=600)
        steps.append(
            {
                "check": label,
                "command": " ".join(command),
                "exit_code": result.returncode,
                "duration_seconds": round(time.monotonic() - started, 2),
                "passed": result.returncode == 0,
                "tail": (result.stdout + result.stderr)[-1500:],
            }
        )


def _web_checks(hermes: Path, evidence: dict[str, object]) -> None:
    steps = evidence["steps"]
    for label, script in [
        ("web_typecheck", "typecheck"),
        ("web_vitest", "test"),
        ("web_build", "build"),
    ]:
        started = time.monotonic()
        result = run(["npm", "run", script], cwd=hermes / "web", timeout=900)
        steps.append(
            {
                "check": label,
                "command": f"npm run {script}",
                "exit_code": result.returncode,
                "duration_seconds": round(time.monotonic() - started, 2),
                "passed": result.returncode == 0,
                "tail": (result.stdout + result.stderr)[-1500:],
            }
        )


def _desktop_checks(hermes: Path, evidence: dict[str, object]) -> None:
    steps = evidence["steps"]
    for label, script in [
        ("desktop_typecheck", "typecheck"),
        ("desktop_vitest", "test"),
    ]:
        started = time.monotonic()
        result = run(["npm", "run", script], cwd=hermes / "apps/desktop", timeout=900)
        steps.append(
            {
                "check": label,
                "command": f"npm run {script}",
                "exit_code": result.returncode,
                "duration_seconds": round(time.monotonic() - started, 2),
                "passed": result.returncode == 0,
                "tail": (result.stdout + result.stderr)[-1500:],
            }
        )
    started = time.monotonic()
    result = run(["npm", "run", "build"], cwd=hermes / "apps/desktop", timeout=1200)
    steps.append(
        {
            "check": "desktop_build",
            "command": "npm run build",
            "exit_code": result.returncode,
            "duration_seconds": round(time.monotonic() - started, 2),
            "passed": result.returncode == 0,
            "tail": (result.stdout + result.stderr)[-1500:],
            "note": "Full electron packaging (npm run dist) is environment-dependent and not part of this validation.",
        }
    )


if __name__ == "__main__":
    raise SystemExit(main())
