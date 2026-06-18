from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_jsonl, write_jsonl


def import_review(
    generated_path: Path,
    reviewed_path: Path,
    state_dir: Path,
    run_id: str,
    target_locale: str,
) -> dict[str, Any]:
    generated = _by_id(read_jsonl(generated_path), "generated")
    reviewed = _by_id(read_jsonl(reviewed_path), "reviewed")
    unknown = sorted(reviewed.keys() - generated.keys())
    if unknown:
        raise ValueError(f"Reviewed segments are absent from generated input: {', '.join(unknown)}")

    changes: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    reviewed_at = datetime.now(UTC).isoformat()
    for segment_id in sorted(reviewed):
        before = generated[segment_id]
        after = reviewed[segment_id]
        if before.get("source_hash") != after.get("source_hash") or before.get("source") != after.get("source"):
            raise ValueError(f"Review import cannot modify source truth: {segment_id}")
        before_target = _target_value(before)
        after_target = _target_value(after)
        if before_target != after_target:
            changes.append(
                {
                    "segment_id": segment_id,
                    "before": before_target,
                    "after": after_target,
                    "classification": after.get("review_classification") or _classify_change(before_target, after_target),
                }
            )
        if after.get("status") not in {"reviewed", "approved"}:
            continue
        target_value = after.get("target")
        target_plural = after.get("target_plural")
        if target_value is None and target_plural is None:
            continue
        tm_identity = f"{segment_id}\0{target_locale}\0{after_target}"
        record: dict[str, Any] = {
            "id": hashlib.sha256(tm_identity.encode("utf-8")).hexdigest()[:24],
            "segment_id": segment_id,
            "source": after["source"],
            "source_hash": after["source_hash"],
            "source_locale": after.get("source_locale"),
            "target_locale": target_locale,
            "content_type": after.get("context", {}).get("content_type"),
            "status": after["status"],
            "reviewed_at": reviewed_at,
            "run_id": run_id,
        }
        if target_value is not None:
            record["target"] = target_value
        if target_plural is not None:
            record["target_plural"] = target_plural
        updates.append(record)

    tm_path = state_dir / "translation-memory.jsonl"
    existing = read_jsonl(tm_path) if tm_path.exists() and tm_path.read_text(encoding="utf-8").strip() else []
    update_keys = {(item["segment_id"], item["target_locale"]) for item in updates}
    merged = [
        item for item in existing if (item.get("segment_id"), item.get("target_locale")) not in update_keys
    ] + updates
    merged.sort(key=lambda item: (str(item.get("target_locale", "")), str(item.get("segment_id", ""))))
    write_jsonl(tm_path, merged)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "target_locale": target_locale,
        "changes": changes,
        "tm_updates": len(updates),
        "reviewed_scope": {"segment_ids": sorted(reviewed)},
    }


def _by_id(records: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        segment_id = record.get("segment_id")
        if not isinstance(segment_id, str) or not segment_id:
            raise ValueError(f"{label} segment lacks segment_id")
        if segment_id in result:
            raise ValueError(f"Duplicate {label} segment_id: {segment_id}")
        result[segment_id] = record
    return result


def _target_value(segment: dict[str, Any]) -> str:
    if "target_plural" in segment:
        return json.dumps(segment["target_plural"], ensure_ascii=False, sort_keys=True)
    return str(segment.get("target", ""))


def _classify_change(before: str, after: str) -> str:
    if "".join(before.split()) == "".join(after.split()):
        return "format_only"
    return "unknown"
