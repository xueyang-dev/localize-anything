from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from . import PROTOCOL_VERSION


def diff_segments(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> dict[str, Any]:
    previous_by_id = _unique_by_id(previous, "previous")
    current_by_id = _unique_by_id(current, "current")
    results: list[dict[str, Any]] = []

    unmatched_previous: dict[str, dict[str, Any]] = {}
    unmatched_current: dict[str, dict[str, Any]] = {}

    for segment_id in sorted(previous_by_id.keys() | current_by_id.keys()):
        old = previous_by_id.get(segment_id)
        new = current_by_id.get(segment_id)
        if old and new:
            status = "unchanged" if old.get("source_hash") == new.get("source_hash") else "changed"
            results.append(_diff_record(status, new, old))
        elif old:
            unmatched_previous[segment_id] = old
        elif new:
            unmatched_current[segment_id] = new

    previous_by_hash: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for old in unmatched_previous.values():
        previous_by_hash[str(old.get("source_hash", ""))].append(old)

    moved_previous_ids: set[str] = set()
    for segment_id, new in sorted(unmatched_current.items()):
        candidates = previous_by_hash.get(str(new.get("source_hash", "")))
        if candidates:
            old = candidates.popleft()
            moved_previous_ids.add(old["segment_id"])
            results.append(_diff_record("moved", new, old))
        else:
            results.append(_diff_record("new", new, None))

    for segment_id, old in sorted(unmatched_previous.items()):
        if segment_id not in moved_previous_ids:
            results.append(_diff_record("deleted", old, old))

    order = {"changed": 0, "new": 1, "moved": 2, "deleted": 3, "unchanged": 4}
    results.sort(key=lambda item: (order[item["status"]], item["segment_id"]))
    summary = {status: sum(item["status"] == status for item in results) for status in ["new", "unchanged", "changed", "moved", "deleted"]}
    return {"protocol_version": PROTOCOL_VERSION, "summary": summary, "segments": results}


def _unique_by_id(segments: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for segment in segments:
        segment_id = segment.get("segment_id")
        if not isinstance(segment_id, str) or not segment_id:
            raise ValueError(f"{label} segment lacks segment_id")
        if segment_id in result:
            raise ValueError(f"duplicate {label} segment_id: {segment_id}")
        result[segment_id] = segment
    return result


def _diff_record(status: str, current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    record = {
        "status": status,
        "segment_id": current["segment_id"],
        "source_hash": current.get("source_hash"),
    }
    if previous:
        record["previous_segment_id"] = previous["segment_id"]
        record["previous_source_hash"] = previous.get("source_hash")
    return record
