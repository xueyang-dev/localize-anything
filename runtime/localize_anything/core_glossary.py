from __future__ import annotations

import hashlib
import re
from typing import Any


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)?")
ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9&]{1,}(?:-[A-Z0-9]+)?\b")
STOP_TERMS = {
    "a",
    "an",
    "and",
    "app",
    "button",
    "cancel",
    "for",
    "label",
    "message",
    "new",
    "ok",
    "save",
    "settings",
    "the",
    "title",
}


def normalize_concept(value: str) -> str:
    return " ".join(value.casefold().split())


def extract_candidate_concepts(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    occurrences: dict[str, dict[str, Any]] = {}

    def add(term: str, segment: dict[str, Any]) -> None:
        normalized = normalize_concept(term)
        if normalized:
            occurrences.setdefault(normalized, {"term": term, "matches": []})["matches"].append(segment)

    for segment in segments:
        value = str(segment.get("source", "")).strip()
        if _reviewable(value):
            add(value, segment)
        for acronym in ACRONYM_RE.findall(value):
            add(acronym, segment)

    return sorted(
        [
            {
                "id": "concept-" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12],
                "source_terms": [str(entry["term"])],
                "behavior": "translate",
                "status": "candidate",
                "target": {"preferred": "", "forbidden": []},
                "evidence": [
                    {"segment_id": item.get("segment_id"), "source_path": item.get("source_path")}
                    for item in entry["matches"][:8]
                ],
            }
            for normalized, entry in occurrences.items()
            if len(entry["matches"]) >= 2 or str(entry["term"]).isupper()
        ],
        key=lambda item: normalize_concept(item["source_terms"][0]),
    )


def check_locked_concepts(
    glossary: dict[str, Any] | None,
    source_text: list[str],
    target_text: list[str],
) -> list[dict[str, Any]]:
    if not glossary:
        return []
    source = "\n".join(source_text).casefold()
    target = "\n".join(target_text).casefold()
    findings = []
    for concept in glossary.get("concepts", []):
        if concept.get("status") != "locked":
            continue
        terms = [str(item).strip() for item in concept.get("source_terms", []) if str(item).strip()]
        if not terms or not any(term.casefold() in source for term in terms):
            continue
        rules = concept.get("target", {}) if isinstance(concept.get("target"), dict) else {}
        preferred = str(rules.get("preferred", "")).strip()
        if concept.get("behavior") == "preserve":
            preferred = preferred or terms[0]
        if preferred and preferred.casefold() not in target:
            findings.append(
                {
                    "severity": "blocking",
                    "kind": "locked_glossary",
                    "concept_id": concept.get("id"),
                    "message": f"Locked term is absent from target output: {preferred}",
                }
            )
        for forbidden in rules.get("forbidden", []):
            value = str(forbidden).strip()
            if value and value.casefold() in target:
                findings.append(
                    {
                        "severity": "blocking",
                        "kind": "forbidden_glossary",
                        "concept_id": concept.get("id"),
                        "message": f"Forbidden glossary target is present: {value}",
                    }
                )
    return findings


def _reviewable(value: str) -> bool:
    words = WORD_RE.findall(value)
    return 1 <= len(words) <= 5 and 2 <= len(value) <= 72 and normalize_concept(value) not in STOP_TERMS
