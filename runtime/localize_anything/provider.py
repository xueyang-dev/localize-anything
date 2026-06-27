from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .generation import collect_generated_handoff, import_generated_response
from .generation_handoff_policy import provider_generation_blocker
from .io_utils import read_json


def generate_handoff_with_http_provider(
    handoff: dict[str, Any],
    provider_url: str,
    output_jsonl: Path | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 60,
    handoff_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocker = provider_generation_blocker(handoff_decision)
    if blocker:
        return _provider_failure(blocker["category"], blocker["message"])
    batch_results: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    imported_batches = 0
    for batch in handoff.get("batches", []):
        batch_id = str(batch.get("batch_id", ""))
        work_packet_path = Path(str(batch.get("work_packet", "")))
        draft_request_path = Path(str(batch.get("draft_request", "")))
        generated_path = Path(str(batch.get("generated", "")))
        if not batch_id:
            result = _provider_failure("missing_batch_id", "Handoff batch is missing batch_id")
        elif not work_packet_path.is_file():
            result = _provider_failure("missing_work_packet", f"Missing work packet for {batch_id}: {work_packet_path}")
        elif not draft_request_path.is_file():
            result = _provider_failure("missing_draft_request", f"Missing draft request for {batch_id}: {draft_request_path}")
        else:
            try:
                response_text = _post_provider_request(
                    provider_url,
                    {
                        "handoff_id": handoff.get("handoff_id"),
                        "batch": batch,
                        "draft_request": read_json(draft_request_path),
                    },
                    headers or {},
                    timeout_seconds,
                )
                result = import_generated_response(read_json(work_packet_path), response_text, generated_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                result = _provider_failure("provider_generation", f"Provider generation failed for {batch_id}: {exc}")
        if result["status"] != "fail":
            imported_batches += 1
        for item in result.get("items", []):
            enriched = dict(item)
            enriched["batch_id"] = batch_id
            items.append(enriched)
        batch_results.append(
            {
                "batch_id": batch_id,
                "generated": generated_path.as_posix(),
                "provider_status": result["status"],
                "blocking_count": result.get("summary", {}).get("blocking_count", 0),
                "warning_count": result.get("summary", {}).get("warning_count", 0),
                "generated_segment_count": result.get("summary", {}).get("generated_segment_count", 0),
            }
        )
    blocking = sum(item.get("severity") == "blocking" for item in items)
    warnings = sum(item.get("severity") == "warning" for item in items)
    collect_result = None
    if output_jsonl is not None and not blocking:
        collect_result = collect_generated_handoff(handoff, output_jsonl)
        for item in collect_result.get("items", []):
            enriched = dict(item)
            enriched.setdefault("batch_id", item.get("batch_id"))
            items.append(enriched)
        blocking = sum(item.get("severity") == "blocking" for item in items)
        warnings = sum(item.get("severity") == "warning" for item in items)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "handoff_id": handoff.get("handoff_id"),
        "provider": {"type": "http_json", "url": provider_url},
        "status": "fail" if blocking else "pass_with_warnings" if warnings else "pass",
        "summary": {
            "batch_count": len(batch_results),
            "generated_batch_count": imported_batches,
            "blocking_count": blocking,
            "warning_count": warnings,
            "generated_segment_count": (
                collect_result.get("summary", {}).get("generated_segment_count", 0)
                if collect_result
                else sum(item["generated_segment_count"] for item in batch_results)
            ),
        },
        "combined_output": output_jsonl.as_posix() if output_jsonl else None,
        "items": items,
        "batches": batch_results,
    }


def _post_provider_request(provider_url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: int) -> str:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Content-Type": "application/json", "Accept": "application/json, text/plain"}
    request_headers.update(headers)
    request = urllib.request.Request(provider_url, data=encoded, headers=request_headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8-sig")


def _provider_failure(category: str, message: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "status": "fail",
        "summary": {"blocking_count": 1, "warning_count": 0, "generated_segment_count": 0},
        "items": [
            {
                "channel": "runtime",
                "category": category,
                "severity": "blocking",
                "message": message,
                "checked_by": "runtime",
                "coverage": "complete",
                "confidence": "deterministic",
            }
        ],
    }
