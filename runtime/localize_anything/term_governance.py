from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .knowledge_consumption import imported_term_rows


TERM_REGISTRY_COLUMNS = [
    "source_term",
    "target_term",
    "type",
    "status",
    "priority",
    "scope",
    "notes",
    "source_locale",
    "target_locale",
    "forbidden_targets",
    "provenance",
]

FORBIDDEN_TRANSLATION_COLUMNS = [
    "source_term",
    "forbidden_target",
    "target_locale",
    "scope",
    "reason",
    "status",
    "provenance",
]

TERM_GOVERNANCE_ASSETS = {
    "term_registry": "term-registry.csv",
    "forbidden_translations": "forbidden-translations.csv",
    "term_decisions": "term-decisions.jsonl",
    "term_conflicts": "term-conflicts.jsonl",
    "term_provenance": "term-provenance.jsonl",
}

HARD_TERM_STATUSES = {"approved", "locked"}
FORBIDDEN_STATUSES = {"approved", "locked", "rejected", "verified"}
STATUS_PRIORITY = {
    "locked": 0,
    "approved": 1,
    "verified": 2,
    "scope_specific": 3,
    "reference": 4,
    "suggested": 5,
    "risk": 6,
    "raw": 7,
    "deprecated": 8,
    "obsolete": 9,
    "rejected": 10,
}
PRIORITY_ORDER = {
    "user_confirmed": 0,
    "official": 1,
    "project_specific": 2,
    "reviewed_tm": 3,
    "style_guide": 4,
    "model_suggestion": 5,
    "literal_guess": 6,
}


def write_term_governance_seed(state_dir: Path) -> None:
    _write_csv_if_missing(state_dir / "term-registry.csv", TERM_REGISTRY_COLUMNS)
    _write_csv_if_missing(state_dir / "forbidden-translations.csv", FORBIDDEN_TRANSLATION_COLUMNS)
    for name in ("term-decisions.jsonl", "term-conflicts.jsonl", "term-provenance.jsonl"):
        path = state_dir / name
        if not path.exists():
            path.write_text("", encoding="utf-8")


def term_governance_asset_paths(state_dir: Path) -> dict[str, str]:
    return {
        key: value
        for key, value in TERM_GOVERNANCE_ASSETS.items()
        if (state_dir / value).is_file()
    }


def select_term_constraints(
    state_dir: Path,
    segments: list[dict[str, Any]],
    target_locale: str,
    reference_policy: str,
    limit: int = 50,
) -> dict[str, Any]:
    if reference_policy == "blind":
        return {
            "term_registry": [],
            "forbidden_translations": [],
            "visibility": "hidden_by_reference_policy",
        }

    source_text = "\n".join(str(segment.get("source", "")) for segment in segments).casefold()
    local_registry = _read_csv_rows(state_dir / "term-registry.csv")
    imported_registry, imported_forbidden = imported_term_rows(state_dir)
    local_sources = {
        row.get("source_term", "").casefold()
        for row in local_registry
        if row.get("status") in HARD_TERM_STATUSES and _locale_matches(row.get("target_locale", ""), target_locale)
    }
    registry_rows = [*local_registry, *[row for row in imported_registry if row.get("source_term", "").casefold() not in local_sources]]
    terms = [
        _term_constraint(row)
        for row in registry_rows
        if _term_row_matches(row, source_text, target_locale)
    ]
    forbidden = _forbidden_from_registry(state_dir / "term-registry.csv", source_text, target_locale)
    forbidden.extend(_forbidden_from_file(state_dir / "forbidden-translations.csv", source_text, target_locale))
    forbidden.extend(_forbidden_from_rows(imported_forbidden, source_text, target_locale))
    terms.sort(key=_term_sort_key)
    forbidden.sort(
        key=lambda item: (
            str(item.get("source_term", "")).casefold(),
            str(item.get("forbidden_target", "")).casefold(),
        )
    )
    return {
        "term_registry": terms[:limit],
        "forbidden_translations": _dedupe_forbidden(forbidden)[:limit],
        "visibility": "approved_locked_terms_only",
    }


def _write_csv_if_missing(path: Path, columns: list[str]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(columns)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [
            {str(key): str(value or "").strip() for key, value in row.items() if key}
            for row in csv.DictReader(handle)
        ]


def _term_row_matches(row: dict[str, str], source_text: str, target_locale: str) -> bool:
    source_term = row.get("source_term", "").strip()
    target_term = row.get("target_term", "").strip()
    status = row.get("status", "").strip()
    return (
        bool(source_term)
        and bool(target_term)
        and source_term.casefold() in source_text
        and _locale_matches(row.get("target_locale", ""), target_locale)
        and status in HARD_TERM_STATUSES
    )


def _forbidden_row_matches(row: dict[str, str], source_text: str, target_locale: str) -> bool:
    source_term = row.get("source_term", "").strip()
    forbidden_target = row.get("forbidden_target", "").strip()
    status = row.get("status", "").strip()
    return (
        bool(source_term)
        and bool(forbidden_target)
        and source_term.casefold() in source_text
        and _locale_matches(row.get("target_locale", ""), target_locale)
        and (not status or status in FORBIDDEN_STATUSES)
    )


def _locale_matches(value: str, target_locale: str) -> bool:
    normalized = value.strip()
    return normalized in ("", target_locale)


def _term_constraint(row: dict[str, str]) -> dict[str, Any]:
    item: dict[str, Any] = {
        "source_term": row.get("source_term", ""),
        "target_term": row.get("target_term", ""),
        "type": row.get("type", ""),
        "status": row.get("status", ""),
        "priority": row.get("priority", ""),
        "scope": row.get("scope", ""),
        "notes": row.get("notes", ""),
    }
    for key in ("source_locale", "target_locale"):
        if row.get(key):
            item[key] = row[key]
    provenance = _parse_provenance(row.get("provenance", ""))
    if provenance:
        item["provenance"] = provenance
    return item


def _forbidden_from_registry(path: Path, source_text: str, target_locale: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in _read_csv_rows(path):
        if not row.get("source_term", "").strip() or row["source_term"].casefold() not in source_text:
            continue
        if not _locale_matches(row.get("target_locale", ""), target_locale):
            continue
        for forbidden_target in _split_multi_value(row.get("forbidden_targets", "")):
            items.append(
                {
                    "source_term": row["source_term"],
                    "forbidden_target": forbidden_target,
                    "target_locale": row.get("target_locale", ""),
                    "scope": row.get("scope", ""),
                    "reason": "term_registry_forbidden_target",
                    "status": "rejected",
                }
            )
    return items


def _forbidden_from_file(path: Path, source_text: str, target_locale: str) -> list[dict[str, Any]]:
    return _forbidden_from_rows(_read_csv_rows(path), source_text, target_locale)


def _forbidden_from_rows(rows: list[dict[str, str]], source_text: str, target_locale: str) -> list[dict[str, Any]]:
    return [
        {
            "source_term": row.get("source_term", ""),
            "forbidden_target": row.get("forbidden_target", ""),
            "target_locale": row.get("target_locale", ""),
            "scope": row.get("scope", ""),
            "reason": row.get("reason", ""),
            "status": row.get("status", ""),
            "provenance": _parse_provenance(row.get("provenance", "")),
        }
        for row in rows
        if _forbidden_row_matches(row, source_text, target_locale)
    ]


def _split_multi_value(value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []
    if value.startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    separator = "|" if "|" in value else ";"
    return [item.strip() for item in value.split(separator) if item.strip()]


def _parse_provenance(value: str) -> list[dict[str, str]]:
    value = value.strip()
    if not value:
        return []
    if value.startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            return [
                {str(key): str(child_value) for key, child_value in item.items()}
                for item in parsed
                if isinstance(item, dict)
            ]
    return [{"type": value}]


def _term_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    status = str(item.get("status", ""))
    priority = str(item.get("priority", ""))
    source_term = str(item.get("source_term", ""))
    return (
        STATUS_PRIORITY.get(status, 99),
        PRIORITY_ORDER.get(priority, 99),
        -len(source_term),
        source_term.casefold(),
    )


def _dedupe_forbidden(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (
            str(item.get("source_term", "")),
            str(item.get("forbidden_target", "")),
            str(item.get("target_locale", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
