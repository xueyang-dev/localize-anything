from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any

from . import PROTOCOL_VERSION


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4)) if text else 0


def create_batch_plan(
    segments: list[dict[str, Any]], source_locale: str, target_locales: list[str], max_segments: int = 80
) -> dict[str, Any]:
    if max_segments < 1:
        raise ValueError("max_segments must be positive")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for segment in segments:
        groups[_content_unit(segment)].append(segment)

    batches: list[dict[str, Any]] = []
    batch_number = 1
    for content_unit in sorted(groups):
        group = groups[content_unit]
        for start in range(0, len(group), max_segments):
            chunk = group[start : start + max_segments]
            batch_id = f"batch-{batch_number:04d}"
            batches.append(
                {
                    "batch_id": batch_id,
                    "content_unit": content_unit,
                    "source_paths": sorted({str(segment.get("source_path", "")) for segment in chunk}),
                    "segment_ids": [segment["segment_id"] for segment in chunk],
                    "estimated_source_tokens": sum(estimate_tokens(str(segment.get("source", ""))) for segment in chunk),
                    "blocking_questions": [],
                }
            )
            batch_number += 1

    digest_input = json.dumps(
        {"ids": [segment["segment_id"] for segment in segments], "targets": target_locales}, sort_keys=True
    ).encode("utf-8")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "plan_id": hashlib.sha256(digest_input).hexdigest()[:16],
        "source_locale": source_locale,
        "target_locales": target_locales,
        "strategy": "content_unit_then_adapter_constraints",
        "batches": batches,
    }


def _content_unit(segment: dict[str, Any]) -> str:
    context = segment.get("context", {})
    for key in ("content_unit", "scene", "chapter", "scenario", "namespace"):
        value = context.get(key)
        if value:
            return f"{key}:{value}"
    pointer = context.get("json_pointer")
    if isinstance(pointer, str) and pointer.startswith("/"):
        top = pointer[1:].split("/", 1)[0]
        if top:
            return f"json:{top}"
    occurrences = context.get("occurrences")
    if isinstance(occurrences, list) and occurrences:
        first = occurrences[0]
        path = first[0] if isinstance(first, list) and first else str(first)
        return f"path:{PurePosixPath(path).parent.as_posix()}"
    return f"file:{segment.get('source_path', 'unknown')}"
