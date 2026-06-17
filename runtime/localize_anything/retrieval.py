from __future__ import annotations

import csv
import hashlib
import json
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .planning import estimate_tokens


P0_HEADINGS = {
    "Memory Policy",
    "Project Contract",
    "Source Of Truth",
    "Content Strategy",
    "Approved Decisions",
    "Adapter And Format Constraints",
    "QA Contract",
    "Blocking Questions",
}


def build_work_packet(
    batch_plan: dict[str, Any],
    batch_id: str,
    segments: list[dict[str, Any]],
    state_dir: Path,
    target_locale: str,
    limit_tokens: int = 4000,
    glossary_limit: int = 50,
    tm_limit: int = 40,
) -> dict[str, Any]:
    batch = next((item for item in batch_plan.get("batches", []) if item.get("batch_id") == batch_id), None)
    if not batch:
        raise ValueError(f"Unknown batch_id: {batch_id}")
    by_id = {segment["segment_id"]: segment for segment in segments}
    selected = [by_id[segment_id] for segment_id in batch["segment_ids"] if segment_id in by_id]
    if len(selected) != len(batch["segment_ids"]):
        raise ValueError(f"Batch {batch_id} references missing segments")

    context_sections = _select_context_sections(state_dir / "localization-context.md", selected)
    glossary = _select_glossary(state_dir / "glossary.csv", selected, target_locale, glossary_limit)
    tm = _select_tm(state_dir / "translation-memory.jsonl", selected, target_locale, tm_limit)

    trimmed: list[str] = []
    packet = _packet(batch_plan, batch_id, selected, target_locale, context_sections, glossary, tm, limit_tokens, trimmed)
    while packet["budget"]["estimated_tokens"] > limit_tokens and tm:
        tm.pop()
        trimmed.append("low_priority_translation_memory")
        packet = _packet(batch_plan, batch_id, selected, target_locale, context_sections, glossary, tm, limit_tokens, trimmed)
    while packet["budget"]["estimated_tokens"] > limit_tokens and glossary:
        glossary.pop()
        trimmed.append("low_priority_glossary")
        packet = _packet(batch_plan, batch_id, selected, target_locale, context_sections, glossary, tm, limit_tokens, trimmed)
    if packet["budget"]["estimated_tokens"] > limit_tokens:
        trimmed.append("source_or_p0_exceeds_budget_shrink_batch")
        packet["budget"]["trimmed"] = sorted(set(trimmed))
    return packet


def parse_markdown_sections(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    sections: list[dict[str, str]] = []
    heading = "Preamble"
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if lines:
                sections.append({"heading": heading, "content": "\n".join(lines).strip()})
            heading = line[3:].strip()
            lines = []
        else:
            lines.append(line)
    if lines:
        sections.append({"heading": heading, "content": "\n".join(lines).strip()})
    return sections


def _select_context_sections(path: Path, segments: list[dict[str, Any]]) -> list[dict[str, str]]:
    sections = parse_markdown_sections(path)
    signals = set()
    for segment in segments:
        context = segment.get("context", {})
        for key in ("speaker", "scene", "chapter", "scenario"):
            if context.get(key):
                signals.add(str(context[key]).casefold())
        for entity in context.get("entities", []) if isinstance(context.get("entities"), list) else []:
            signals.add(str(entity).casefold())
    selected = []
    for section in sections:
        content_folded = section["content"].casefold()
        if section["heading"] in P0_HEADINGS or any(signal and signal in content_folded for signal in signals):
            selected.append(section)
    return selected


def _select_glossary(path: Path, segments: list[dict[str, Any]], target_locale: str, limit: int) -> list[dict[str, str]]:
    if not path.exists():
        return []
    source_text = "\n".join(str(segment.get("source", "")) for segment in segments).casefold()
    matches: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            term = (row.get("term") or "").strip()
            row_locale = (row.get("target_locale") or "").strip()
            status = (row.get("status") or "").strip()
            if term and term.casefold() in source_text and row_locale in ("", target_locale) and status in ("approved", "reviewed"):
                matches.append(row)
    matches.sort(key=lambda row: (-len(row.get("term", "")), row.get("term", "")))
    return matches[:limit]


def _select_tm(path: Path, segments: list[dict[str, Any]], target_locale: str, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return []
    records = [json.loads(line) for line in content.splitlines() if line.strip()]
    candidate_records = [
        record
        for record in records
        if record.get("target_locale") == target_locale and record.get("status") in ("approved", "reviewed")
    ]
    by_segment_id: dict[str, list[dict[str, Any]]] = {}
    by_source: dict[str, list[dict[str, Any]]] = {}
    for record in candidate_records:
        segment_id = record.get("segment_id")
        if isinstance(segment_id, str) and segment_id:
            by_segment_id.setdefault(segment_id, []).append(record)
        source = record.get("source")
        if isinstance(source, str):
            by_source.setdefault(source, []).append(record)

    candidates: list[dict[str, Any]] = []
    for segment in segments:
        source = str(segment.get("source", ""))
        content_type = segment.get("context", {}).get("content_type")
        exact_matches = False
        for record in by_segment_id.get(str(segment.get("segment_id", "")), []):
            if _tm_type_matches(record, content_type):
                exact_matches = True
                candidates.append(_tm_candidate(segment, record, 1.0, "exact_id"))
        for record in by_source.get(source, []):
            if _tm_type_matches(record, content_type):
                exact_matches = True
                candidates.append(_tm_candidate(segment, record, 0.99, "exact_source"))
        if exact_matches:
            continue
        for record in candidate_records:
            if _tm_type_matches(record, content_type):
                score = SequenceMatcher(None, str(record.get("source", "")).casefold(), source.casefold()).ratio()
                if score >= 0.82:
                    candidates.append(_tm_candidate(segment, record, score, "high_fuzzy_match"))
    candidates.sort(key=lambda item: (-item["score"], str(item["tm_id"])))
    deduped: list[dict[str, Any]] = []
    seen = set()
    for candidate in candidates:
        key = (candidate["for_segment_id"], candidate["tm_id"])
        if key not in seen:
            deduped.append(candidate)
            seen.add(key)
        if len(deduped) >= limit:
            break
    return deduped


def _tm_type_matches(record: dict[str, Any], content_type: Any) -> bool:
    record_type = record.get("content_type")
    return not (content_type and record_type and content_type != record_type)


def _tm_candidate(segment: dict[str, Any], record: dict[str, Any], score: float, kind: str) -> dict[str, Any]:
    return {
        "for_segment_id": segment["segment_id"],
        "tm_id": record.get("id") or record.get("segment_id"),
        "source": record.get("source"),
        "target": record.get("target"),
        "status": record.get("status"),
        "match_kind": kind,
        "score": round(score, 4),
    }


def _packet(
    plan: dict[str, Any],
    batch_id: str,
    segments: list[dict[str, Any]],
    target_locale: str,
    context_sections: list[dict[str, str]],
    glossary: list[dict[str, str]],
    tm: list[dict[str, Any]],
    limit_tokens: int,
    trimmed: list[str],
) -> dict[str, Any]:
    memory = {"context_sections": context_sections, "glossary": glossary, "translation_memory": tm}
    body = {"segments": segments, "memory": memory}
    estimated = estimate_tokens(json.dumps(body, ensure_ascii=False))
    digest = hashlib.sha256(
        json.dumps({"batch": batch_id, "target": target_locale, "segments": [item["segment_id"] for item in segments]}, sort_keys=True).encode()
    ).hexdigest()[:16]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "packet_id": digest,
        "batch_id": batch_id,
        "source_locale": plan["source_locale"],
        "target_locale": target_locale,
        "segments": segments,
        "memory": memory,
        "budget": {
            "estimated_tokens": estimated,
            "limit_tokens": limit_tokens,
            "estimation": "estimated",
            "trimmed": sorted(set(trimmed)),
        },
    }
