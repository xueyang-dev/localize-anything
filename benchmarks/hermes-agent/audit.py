"""Phase 1: inventory and audit Hermes localization surfaces."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from common import BENCH_ROOT, CONFIG, REPORTS, SOURCE, flatten_yaml, write_json

sys.path.insert(0, str(BENCH_ROOT))

from runtime.localize_anything.typescript_locale_adapter import extract_segments as extract_ts  # noqa: E402


PLACEHOLDER_HINT = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_.]*|%[sd]")
MARKDOWN_HINT = re.compile(r"\*\*|`|^\s*[-*] |\[[^\]]+\]\([^)]+\)|#")

# Conservative hardcoded-string heuristics for JSX/TSX sources outside i18n.
JSX_TEXT_RE = re.compile(r">\s*([A-Za-z][A-Za-z0-9 ,.'!?:()/-]{2,})\s*<")
ATTR_TEXT_RE = re.compile(r'(?:title|placeholder|aria-label|alt)="([A-Za-z][A-Za-z0-9 ,.\'!?:()/-]{2,})"')
def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    inventory = source_inventory()
    surface_report = localization_surface_report(inventory)
    locale_matrix = locale_matrix_report(inventory)
    hardcoded = hardcoded_string_findings()
    dynamic = dynamic_content_findings()
    write_json(inventory, REPORTS / "source-inventory.json")
    write_json(surface_report, REPORTS / "localization-surface-report.json")
    write_json(locale_matrix, REPORTS / "locale-matrix.json")
    write_json(hardcoded, REPORTS / "hardcoded-string-findings.json")
    write_json(dynamic, REPORTS / "dynamic-content-findings.json")
    write_json(benchmark_plan(), REPORTS / "benchmark-plan.md", raw=True)
    print(json.dumps({"surfaces": list(inventory["surfaces"]), "status": "written"}, ensure_ascii=False, indent=2))
    return 0


def source_inventory() -> dict[str, object]:
    yaml_files = sorted((SOURCE / "locales").glob("*.yaml"))
    web_locales = {"af", "ar", "de", "en", "es", "fr", "ga", "hu", "it", "ja", "ko", "pt", "ru", "tr", "uk", "zh", "zh-hant"}
    desktop_locales = {"en", "zh", "zh-hant", "ja", "ar"}
    web_files = sorted(p for p in (SOURCE / "web/src/i18n").glob("*.ts") if p.stem in web_locales)
    desktop_files = sorted(p for p in (SOURCE / "apps/desktop/src/i18n").glob("*.ts") if p.stem in desktop_locales)
    docs = sorted((SOURCE / "website/docs").rglob("*.md"))
    docs_translated = sorted((SOURCE / "website/i18n").rglob("*.md"))

    surfaces: dict[str, object] = {}
    surfaces["yaml_cli_gateway"] = _yaml_surface(yaml_files)
    surfaces["web_dashboard"] = _ts_surface(web_files, "web")
    surfaces["desktop"] = _ts_surface(desktop_files, "desktop")
    surfaces["documentation"] = {
        "surface": "documentation",
        "files": len(docs),
        "translated_docs": len(docs_translated),
        "locales": ["en", "zh-Hans"],
        "docusaurus_config": (SOURCE / "website/docusaurus.config.ts").is_file(),
    }
    summary = {key: value for key, value in surfaces.items()}
    return {"benchmark_id": CONFIG["id"], "commit": CONFIG["upstream"]["commit"], "surfaces": summary}


def _yaml_surface(paths: list[Path]) -> dict[str, object]:
    catalogs: list[dict[str, object]] = []
    for path in paths:
        flat = flatten_yaml(path)
        catalogs.append(
            {
                "file": path.relative_to(SOURCE).as_posix(),
                "keys": len(flat),
                "placeholder_bearing": sum(bool(PLACEHOLDER_HINT.search(value)) for value in flat.values()),
                "markdown_bearing": sum(bool(MARKDOWN_HINT.search(value)) for value in flat.values()),
                "escaped_newlines": sum("\\n" in value for value in flat.values()),
            }
        )
    return {
        "surface": "yaml_cli_gateway",
        "adapter": "core.yaml-toml",
        "catalog_files": len(catalogs),
        "catalogs": catalogs,
        "totals": {
            "keys": sum(catalog["keys"] for catalog in catalogs),
            "placeholder_bearing": sum(catalog["placeholder_bearing"] for catalog in catalogs),
            "markdown_bearing": sum(catalog["markdown_bearing"] for catalog in catalogs),
        },
    }


def _ts_surface(paths: list[Path], surface: str) -> dict[str, object]:
    catalogs: list[dict[str, object]] = []
    for path in paths:
        segments = extract_ts(path, "en", path.relative_to(SOURCE).as_posix())
        catalogs.append(
            {
                "file": path.relative_to(SOURCE).as_posix(),
                "leaves": len(segments),
                "string_leaves": sum(segment["context"]["ts_kind"] == "string" for segment in segments),
                "template_leaves": sum(segment["context"]["ts_kind"] == "template" for segment in segments),
                "function_valued": sum(bool(segment["context"].get("function_pointer")) for segment in segments),
                "template_expression_bearing": sum(bool(segment["constraints"]["template_expressions"]) for segment in segments),
                "placeholder_bearing": sum(bool(segment["constraints"]["placeholders"]) for segment in segments),
            }
        )
    return {
        "surface": surface,
        "adapter": "core.typescript-locale",
        "catalog_files": len(catalogs),
        "catalogs": catalogs,
        "totals": {
            "leaves": sum(catalog["leaves"] for catalog in catalogs),
            "function_valued": sum(catalog["function_valued"] for catalog in catalogs),
            "template_expression_bearing": sum(catalog["template_expression_bearing"] for catalog in catalogs),
        },
    }


def locale_matrix_report(inventory: dict[str, object]) -> dict[str, object]:
    matrix: dict[str, object] = {}
    for surface in ("yaml_cli_gateway", "web_dashboard", "desktop"):
        catalogs = inventory["surfaces"][surface]["catalogs"]
        key_field = "keys" if surface == "yaml_cli_gateway" else "leaves"
        english = next((c for c in catalogs if c["file"].endswith("en.yaml") or c["file"].endswith("i18n/en.ts")), None)
        english_keys = int(english[key_field]) if english else 0
        rows = []
        for catalog in catalogs:
            keys = int(catalog[key_field])
            rows.append(
                {
                    "locale": _locale_from_name(catalog["file"]),
                    "file": catalog["file"],
                    "keys": keys,
                    "coverage_vs_english": round(keys / english_keys, 4) if english_keys else None,
                }
            )
        matrix[surface] = {
            "locales": len(rows),
            "rows": rows,
            "coverage_classification": "full" if all(row["coverage_vs_english"] == 1.0 for row in rows if row["locale"] != "en") else "partial",
        }
    matrix["documentation"] = {
        "locales": ["en", "zh-Hans"],
        "english_docs": inventory["surfaces"]["documentation"]["files"],
        "zh_hans_docs": inventory["surfaces"]["documentation"]["translated_docs"],
    }
    return matrix


def _locale_from_name(file: str) -> str:
    return Path(file).stem


def localization_surface_report(inventory: dict[str, object]) -> dict[str, object]:
    return {
        "benchmark_id": CONFIG["id"],
        "commit": CONFIG["upstream"]["commit"],
        "surfaces": {
            "yaml_cli_gateway": {
                "classification": "catalog_covered",
                "evidence": "agent/i18n.py dotted-key runtime, English fallback, parity tests in tests/agent/test_i18n.py",
            },
            "web_dashboard": {
                "classification": "catalog_covered",
                "evidence": "web/src/i18n typed object catalogs, defineLocale partial overrides, RTL for ar",
            },
            "desktop": {
                "classification": "catalog_covered",
                "evidence": "apps/desktop/src/i18n full typed catalogs with function-valued messages",
            },
            "documentation": {
                "classification": "catalog_covered",
                "evidence": "Docusaurus i18n (en + zh-Hans), translated docs under website/i18n",
            },
            "tui_ui_tui": {
                "classification": "unknown",
                "evidence": "ui-tui package exists; no locale catalog detected in engineering audit",
            },
            "plugins": {
                "classification": "dynamic_metadata",
                "evidence": "plugins/ manifests and dashboard slots provide English metadata at runtime",
            },
            "skills": {
                "classification": "generated_content",
                "evidence": "skills/ and optional-skills/ frontmatter and descriptions; generated skill docs excluded from search index by design",
            },
            "gateway_server_output": {
                "classification": "dynamic_metadata",
                "evidence": "agent-generated replies, tool outputs, log lines, tracebacks intentionally stay in English per agent/i18n.py",
            },
            "billing_provider_responses": {
                "classification": "intentionally_out_of_scope",
                "evidence": "provider/billing responses are external English content",
            },
        },
        "counts": {
            surface: {
                "files": inventory["surfaces"][surface].get("catalog_files", inventory["surfaces"][surface].get("files")),
                "keys": inventory["surfaces"][surface].get("totals", {}).get("keys", inventory["surfaces"][surface].get("files")),
            }
            for surface in inventory["surfaces"]
        },
    }


def hardcoded_string_findings() -> dict[str, object]:
    findings: dict[str, object] = {}
    for area, root in (("web", SOURCE / "web/src"), ("desktop", SOURCE / "apps/desktop/src")):
        samples: list[dict[str, object]] = []
        total = 0
        for path in root.rglob("*.tsx"):
            if "i18n" in path.parts or "node_modules" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            matches = list(JSX_TEXT_RE.finditer(text)) + list(ATTR_TEXT_RE.finditer(text))
            total += len(matches)
            for match in matches[:2]:
                samples.append(
                    {
                        "file": path.relative_to(SOURCE).as_posix(),
                        "line": text[: match.start()].count("\n") + 1,
                        "sample": match.group(1)[:80],
                    }
                )
            if len(samples) > 12:
                break
        findings[area] = {
            "classification": "hardcoded_detected",
            "candidate_count_tsx_text_attributes": total,
            "note": "Conservative heuristic over .tsx JSX text nodes and title/placeholder/aria-label attributes; not a complete inventory.",
            "samples": samples[:12],
        }
    return findings


def dynamic_content_findings() -> dict[str, object]:
    return {
        "generated_model_output": {
            "classification": "generated_content",
            "evidence": "model replies are never catalog-routed (agent/i18n.py scope note)",
        },
        "log_lines_and_tracebacks": {
            "classification": "generated_content",
            "evidence": "hermes_logging.py and tracebacks remain English by design",
        },
        "tool_outputs_and_tool_results": {
            "classification": "generated_content",
            "evidence": "tool result text rendered verbatim in chat",
        },
        "plugin_manifests": {
            "classification": "dynamic_metadata",
            "evidence": "plugins/ manifests register English display metadata at runtime",
        },
        "skill_frontmatter_and_descriptions": {
            "classification": "dynamic_metadata",
            "evidence": "skills/SKILL.md frontmatter/descriptions; generated per-skill docs are excluded from search",
        },
        "gateway_server_metadata": {
            "classification": "dynamic_metadata",
            "evidence": "session ids, model names, provider slugs, timestamps, costs rendered as values",
        },
        "billing_and_provider_responses": {
            "classification": "intentionally_out_of_scope",
            "evidence": "external English content",
        },
        "images_audio_video_binary": {
            "classification": "non_text_asset",
            "evidence": "assets/ contains images and media; no OCR/visual QA in engineering run",
        },
    }


def benchmark_plan() -> str:
    return (
        f"# Hermes Agent benchmark plan ({CONFIG['upstream']['commit'][:12]})\n\n"
        "- Target locale: **fr** (official YAML and Web French catalogs exist; Desktop French does not).\n"
        "- Tracks: controlled (blind French references) and agent-system (style_only reference policy).\n"
        "- Generation: engineering fixture only (identity + curated slice); import flow provided for real providers.\n"
        "- Surfaces: YAML CLI/gateway catalogs, Web TypeScript catalogs, Desktop TypeScript catalogs, Docusaurus documentation.\n"
        "- QA: deterministic parity (keys, placeholders, template expressions, signatures), semantic E1 flags, terminology, incremental, apply-to-copy, builds.\n"
        "- Deliverable decision: catalog localization proven; full product localization NOT claimed.\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
