from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from .core_glossary import normalize_concept


CONFIRMED_STATUSES = {"approved", "confirmed", "locked", "reviewed", "scope_specific"}
CONFIRMED_DECISIONS = {"approve", "lock", "scope_limit"}


def import_confirmed_knowledge(state_dir: Path) -> dict[str, Any]:
    roots = [state_dir]
    for packs_root in (state_dir / "knowledge" / "packs", state_dir / ".localize-anything" / "knowledge" / "packs"):
        if packs_root.is_dir():
            roots.extend(path for path in sorted(packs_root.iterdir()) if path.is_dir() and _approved_pack(path))

    concepts = []
    translation_memory = []
    style_rules = []
    confirmed_decisions = []
    for root in roots:
        for name in ("term-registry.csv", "glossary.csv"):
            concepts.extend(_concepts(root / name))
        translation_memory.extend(_confirmed_jsonl(root / "translation-memory.jsonl"))
        for name in ("term-decisions.jsonl", "knowledge-review-decisions.jsonl", "style-decisions.jsonl"):
            confirmed_decisions.extend(_confirmed_jsonl(root / name, decisions=True))
        for name in ("localization-context.md", "style-profile.md"):
            style_rules.extend(_style_rules(root / name))

    return {
        "product_context": _context(state_dir / "localization-context.md"),
        "style_rules": _unique(style_rules),
        "preserve_rules": _unique(
            str(concept["source_terms"][0])
            for concept in concepts
            if concept.get("behavior") == "preserve"
        ),
        "translation_memory": _unique(translation_memory),
        "confirmed_decisions": _unique(confirmed_decisions),
        "concepts": _unique(concepts),
    }


def _approved_pack(path: Path) -> bool:
    pack = _json(path / "pack.json")
    return str(pack.get("status") or "").casefold() in CONFIRMED_STATUSES


def _concepts(path: Path) -> list[dict[str, Any]]:
    rows = _csv(path)
    concepts = []
    for row in rows:
        status = str(row.get("status") or "").casefold()
        if status not in CONFIRMED_STATUSES:
            continue
        source = str(row.get("source_term") or row.get("source") or "").strip()
        target = str(row.get("target_term") or row.get("target") or "").strip()
        if not source:
            continue
        concepts.append(
            {
                "id": "concept-" + hashlib.sha256(normalize_concept(source).encode("utf-8")).hexdigest()[:12],
                "source_terms": [source],
                "behavior": "preserve" if not target or target == source else "translate",
                "status": "locked",
                "target": {"preferred": target, "forbidden": []},
                "evidence": [{"source_path": path.as_posix(), "imported": True}],
            }
        )
    return concepts


def _confirmed_jsonl(path: Path, *, decisions: bool = False) -> list[dict[str, Any]]:
    values = _jsonl(path)
    return [
        value
        for value in values
        if (
            str(value.get("decision") or "").casefold() in CONFIRMED_DECISIONS
            if decisions
            else str(value.get("status") or "").casefold() in CONFIRMED_STATUSES
        )
    ]


def _style_rules(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [
        line[2:].strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("- ") and line[2:].strip()
    ]


def _context(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def _csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            values.append(value)
    return values


def _unique(values: Any) -> list[Any]:
    result = []
    seen = set()
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result
