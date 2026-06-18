from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .io_utils import read_json, read_jsonl, write_jsonl
from .json_adapter import extract_placeholders


FENCED_BLOCK_RE = re.compile(r"```[^\n`]*\n(.*?)```", re.DOTALL)
RESPONSE_FILE_PATTERNS = (
    "{batch_id}.jsonl",
    "{batch_id}.json",
    "{batch_id}.md",
    "{batch_id}.txt",
    "{batch_id}.response.jsonl",
    "{batch_id}.response.json",
    "{batch_id}.response.md",
    "{batch_id}.response.txt",
    "{batch_id}-response.jsonl",
    "{batch_id}-response.json",
    "{batch_id}-response.md",
    "{batch_id}-response.txt",
)
TARGET_ALIASES = ("target", "translation", "translated", "localized", "value", "text")


def create_draft_request(work_packet: dict[str, Any]) -> dict[str, Any]:
    request_id = hashlib.sha256(
        json.dumps(
            {
                "packet_id": work_packet["packet_id"],
                "batch_id": work_packet["batch_id"],
                "target_locale": work_packet["target_locale"],
                "segments": [segment["segment_id"] for segment in work_packet.get("segments", [])],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "packet_id": work_packet["packet_id"],
        "batch_id": work_packet["batch_id"],
        "source_locale": work_packet["source_locale"],
        "target_locale": work_packet["target_locale"],
        "task": "generate_translation_draft",
        "instructions": [
            "Translate each segment from source_locale to target_locale.",
            "Return JSONL records that preserve segment_id, source, source_hash, source_path, context, constraints, and status.",
            "Set target_locale to the requested target locale.",
            "Set target to the translated draft text.",
            "Set status to generated.",
            "Preserve placeholders exactly as listed in constraints.placeholders.",
            "Do not invent, drop, reorder, or merge segment records.",
            "If a segment cannot be translated safely, preserve the source as target and add a generation.warning field.",
            "If the host agent captures a non-JSONL response, normalize it with import-generated-response before collect-generated.",
        ],
        "output_contract": {
            "format": "jsonl",
            "record_schema": "segment.schema.json",
            "required_fields": ["segment_id", "source", "source_hash", "source_path", "target", "target_locale", "status"],
            "status": "generated",
            "coverage": "exactly_all_segments_in_request",
            "import_command": "localize-anything import-generated-response <work-packet> <response> --generated-output <batch-jsonl>",
        },
        "segments": work_packet.get("segments", []),
        "memory": work_packet.get("memory", {}),
        "budget": work_packet.get("budget", {}),
    }


def render_draft_prompt(draft_request: dict[str, Any]) -> str:
    request_payload = {
        "request_id": draft_request.get("request_id"),
        "batch_id": draft_request.get("batch_id"),
        "source_locale": draft_request.get("source_locale"),
        "target_locale": draft_request.get("target_locale"),
        "task": draft_request.get("task"),
        "instructions": draft_request.get("instructions", []),
        "output_contract": draft_request.get("output_contract", {}),
        "segments": draft_request.get("segments", []),
        "memory": draft_request.get("memory", {}),
    }
    return "\n".join(
        [
            "# Translation Draft Prompt",
            "",
            f"- Request ID: `{draft_request.get('request_id')}`",
            f"- Batch ID: `{draft_request.get('batch_id')}`",
            f"- Source locale: `{draft_request.get('source_locale')}`",
            f"- Target locale: `{draft_request.get('target_locale')}`",
            "",
            "Translate every segment in the request payload.",
            "",
            "Return only generated segment JSONL. Do not wrap the answer in Markdown.",
            "Each JSONL object must preserve segment_id and include target, target_locale, and status.",
            "Set status to generated and preserve placeholders exactly.",
            "",
            "If JSONL output is not possible in your environment, return a JSON array or a segment_id to target map; the runtime can normalize it with import-generated-response.",
            "",
            "## Request Payload",
            "",
            "```json",
            json.dumps(request_payload, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )


def write_handoff_prompts(handoff: dict[str, Any], prompt_dir: Path) -> dict[str, Any]:
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompts: list[dict[str, Any]] = []
    for batch in handoff.get("batches", []):
        batch_id = str(batch.get("batch_id", ""))
        request_path = Path(str(batch.get("draft_request", "")))
        if not batch_id:
            raise ValueError("Handoff batch is missing batch_id")
        if not request_path.is_file():
            raise ValueError(f"Missing draft request for {batch_id}: {request_path}")
        prompt_path = prompt_dir / f"{batch_id}.md"
        prompt_path.write_text(render_draft_prompt(read_json(request_path)), encoding="utf-8", newline="\n")
        prompts.append(
            {
                "batch_id": batch_id,
                "prompt": prompt_path.as_posix(),
                "draft_request": request_path.as_posix(),
                "suggested_response_file": f"{batch_id}-response.md",
                "segment_count": batch.get("segment_count", 0),
            }
        )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "status": "pass",
        "handoff_id": handoff.get("handoff_id"),
        "prompt_dir": prompt_dir.as_posix(),
        "summary": {"prompt_count": len(prompts), "segment_count": sum(int(item.get("segment_count", 0)) for item in prompts)},
        "prompts": prompts,
    }


def render_generation_instructions(
    handoff: dict[str, Any],
    prompt_dir: Path,
    response_dir: Path,
    generated_output: Path | None = None,
) -> str:
    generated_dir = Path(str(handoff.get("generated_dir", "generated-batches")))
    handoff_path = "<generation-handoff.json>"
    if handoff.get("batches"):
        first = handoff["batches"][0]
        draft_request = Path(str(first.get("draft_request", "")))
        if draft_request.parent.parent:
            handoff_path = (draft_request.parent.parent / "generation-handoff.json").as_posix()
    lines = [
        "# Generation Handoff",
        "",
        f"- Handoff ID: `{handoff.get('handoff_id')}`",
        f"- Target locales: `{', '.join(handoff.get('target_locales', []))}`",
        f"- Batch count: {handoff.get('request_count', 0)}",
        "",
        "## Steps",
        "",
        "1. Open each prompt in `prompts/` and send it to the host-agent LLM workflow.",
        "2. Save each LLM response in `responses/` using the matching batch id, such as `batch-0001-response.md`.",
        "3. Normalize all responses into generated batch JSONL:",
        "",
        "```bash",
        f"python -m runtime.localize_anything import-generated-handoff {handoff_path} {response_dir.as_posix()} --generated-output {(generated_output or Path('generated.jsonl')).as_posix()}",
        "```",
        "",
        "4. Continue with `localize-run --generated-dir` or the lower-level collect/stage/package commands.",
        "",
        "## Directories",
        "",
        f"- Prompts: `{prompt_dir.as_posix()}`",
        f"- Responses: `{response_dir.as_posix()}`",
        f"- Generated batches: `{generated_dir.as_posix()}`",
        "",
        "## Batches",
        "",
    ]
    for batch in handoff.get("batches", []):
        lines.append(
            f"- `{batch.get('batch_id')}`: {batch.get('segment_count', 0)} segments, response file `{batch.get('batch_id')}-response.md`"
        )
    lines.append("")
    return "\n".join(lines)


def validate_generated_segments(work_packet: dict[str, Any], generated_segments: list[dict[str, Any]]) -> dict[str, Any]:
    expected = {segment["segment_id"]: segment for segment in work_packet.get("segments", [])}
    generated = {str(segment.get("segment_id", "")): segment for segment in generated_segments if segment.get("segment_id")}
    items: list[dict[str, Any]] = []

    duplicate_ids = _duplicates([str(segment.get("segment_id", "")) for segment in generated_segments if segment.get("segment_id")])
    for segment_id in duplicate_ids:
        items.append(_qa_item("duplicate_generated_segment", "blocking", f"Duplicate generated segment: {segment_id}", segment_id))
    for segment in generated_segments:
        if not segment.get("segment_id"):
            items.append(_qa_item("missing_segment_id", "blocking", "Generated record is missing segment_id"))

    for segment_id in sorted(expected.keys() - generated.keys()):
        items.append(_qa_item("generation_coverage", "blocking", f"Missing generated segment: {segment_id}", segment_id))
    for segment_id in sorted(generated.keys() - expected.keys()):
        items.append(_qa_item("generation_coverage", "blocking", f"Unexpected generated segment: {segment_id}", segment_id))

    target_locale = work_packet["target_locale"]
    for segment_id in sorted(expected.keys() & generated.keys()):
        source = expected[segment_id]
        candidate = generated[segment_id]
        if candidate.get("source_hash") != source.get("source_hash"):
            items.append(_qa_item("source_hash_integrity", "blocking", f"Source hash changed for generated segment: {segment_id}", segment_id))
        if candidate.get("source") != source.get("source"):
            items.append(_qa_item("source_integrity", "blocking", f"Source text changed for generated segment: {segment_id}", segment_id))
        if candidate.get("target_locale") != target_locale:
            items.append(_qa_item("target_locale", "blocking", f"Generated segment has wrong target_locale: {segment_id}", segment_id))
        if candidate.get("status") != "generated":
            items.append(_qa_item("generation_status", "warning", f"Generated segment status should be 'generated': {segment_id}", segment_id))
        if "target" not in candidate:
            items.append(_qa_item("missing_target", "blocking", f"Generated segment is missing target: {segment_id}", segment_id))
            continue
        target = str(candidate.get("target", ""))
        expected_placeholders = sorted(str(item) for item in source.get("constraints", {}).get("placeholders", []))
        actual_placeholders = extract_placeholders(target)
        if expected_placeholders != actual_placeholders:
            items.append(
                _qa_item(
                    "placeholder_parity",
                    "blocking",
                    f"Generated target placeholder mismatch: expected={expected_placeholders}, actual={actual_placeholders}",
                    segment_id,
                )
            )
        if "generation" not in candidate:
            items.append(_qa_item("generation_metadata", "warning", f"Generated segment lacks generation metadata: {segment_id}", segment_id))

    blocking = sum(item["severity"] == "blocking" for item in items)
    warnings = sum(item["severity"] == "warning" for item in items)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "status": "fail" if blocking else "pass_with_warnings" if warnings else "pass",
        "summary": {"blocking_count": blocking, "warning_count": warnings},
        "items": items,
    }


def import_generated_response(
    work_packet: dict[str, Any],
    response_text: str,
    output_jsonl: Path | None = None,
) -> dict[str, Any]:
    parsed_records, response_format = parse_generated_response(response_text)
    generated_segments = canonicalize_generated_response(work_packet, parsed_records, response_format)
    if output_jsonl is not None:
        write_jsonl(output_jsonl, generated_segments)
    qa = validate_generated_segments(work_packet, generated_segments)
    summary = dict(qa.get("summary", {}))
    summary["parsed_record_count"] = len(parsed_records)
    summary["generated_segment_count"] = len(generated_segments)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "status": qa["status"],
        "summary": summary,
        "response_format": response_format,
        "generated_output": output_jsonl.as_posix() if output_jsonl else None,
        "items": qa.get("items", []),
    }


def import_generated_handoff(
    handoff: dict[str, Any],
    response_dir: Path,
    output_jsonl: Path | None = None,
) -> dict[str, Any]:
    response_dir = response_dir.resolve()
    batch_results: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    imported_batches = 0
    for batch in handoff.get("batches", []):
        batch_id = str(batch.get("batch_id", ""))
        work_packet_path = Path(str(batch.get("work_packet", "")))
        generated_path = Path(str(batch.get("generated", "")))
        response_path = _find_response_file(response_dir, batch_id)
        if not batch_id:
            result = _handoff_failure("missing_batch_id", "Handoff batch is missing batch_id")
        elif not work_packet_path.is_file():
            result = _handoff_failure("missing_work_packet", f"Missing work packet for {batch_id}: {work_packet_path}")
        elif response_path is None:
            result = _handoff_failure("missing_generated_response", f"Missing LLM response file for {batch_id} in {response_dir}")
        else:
            try:
                result = import_generated_response(
                    read_json(work_packet_path),
                    response_path.read_text(encoding="utf-8"),
                    generated_path,
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                result = _handoff_failure("generated_response_import", f"Could not import response for {batch_id}: {exc}")
        if result["status"] != "fail":
            imported_batches += 1
        for item in result.get("items", []):
            enriched = dict(item)
            enriched["batch_id"] = batch_id
            items.append(enriched)
        batch_results.append(
            {
                "batch_id": batch_id,
                "response": response_path.as_posix() if response_path else None,
                "generated": generated_path.as_posix(),
                "import_status": result["status"],
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
        "status": "fail" if blocking else "pass_with_warnings" if warnings else "pass",
        "summary": {
            "batch_count": len(batch_results),
            "imported_batch_count": imported_batches,
            "blocking_count": blocking,
            "warning_count": warnings,
            "generated_segment_count": (
                collect_result.get("summary", {}).get("generated_segment_count", 0)
                if collect_result
                else sum(item["generated_segment_count"] for item in batch_results)
            ),
        },
        "response_dir": response_dir.as_posix(),
        "combined_output": output_jsonl.as_posix() if output_jsonl else None,
        "items": items,
        "batches": batch_results,
    }


def parse_generated_response(response_text: str) -> tuple[list[dict[str, Any]], str]:
    candidates = _response_candidates(response_text)
    errors: list[str] = []
    for label, candidate in candidates:
        try:
            records, parsed_format = _parse_response_candidate(candidate)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not records:
            errors.append("Parsed response contains no records")
            continue
        return records, parsed_format if label == "body" else f"{label}:{parsed_format}"
    detail = f": {'; '.join(errors[:3])}" if errors else ""
    raise ValueError(f"Could not parse generated response as JSONL, JSON array, JSON object, or segment map{detail}")


def canonicalize_generated_response(
    work_packet: dict[str, Any],
    parsed_records: list[dict[str, Any]],
    response_format: str,
) -> list[dict[str, Any]]:
    expected = {segment["segment_id"]: segment for segment in work_packet.get("segments", [])}
    target_locale = work_packet["target_locale"]
    canonical: list[dict[str, Any]] = []
    for record in parsed_records:
        segment_id = str(record.get("segment_id", ""))
        if segment_id in expected:
            candidate = dict(expected[segment_id])
            target = _target_value(record)
            if target is not None:
                candidate["target"] = str(target)
            if "target_plural" in record:
                candidate["target_plural"] = record["target_plural"]
            candidate["target_locale"] = str(record.get("target_locale") or target_locale)
            candidate["status"] = str(record.get("status") or "generated")
            candidate["generation"] = _generation_metadata(record, response_format)
            canonical.append(candidate)
            continue

        passthrough = dict(record)
        target = _target_value(record)
        if target is not None:
            passthrough["target"] = str(target)
        if passthrough.get("segment_id"):
            passthrough["target_locale"] = str(passthrough.get("target_locale") or target_locale)
            passthrough["status"] = str(passthrough.get("status") or "generated")
            passthrough["generation"] = _generation_metadata(record, response_format)
        canonical.append(passthrough)
    return canonical


def create_generation_handoff(
    work_packet_dir: Path,
    draft_request_dir: Path,
    generated_dir: Path,
    target_locale: str | None = None,
) -> dict[str, Any]:
    packet_paths = {path.stem: path for path in sorted(work_packet_dir.glob("*.json"))}
    request_paths = {path.stem: path for path in sorted(draft_request_dir.glob("*.json"))}
    batch_ids = sorted(packet_paths.keys() | request_paths.keys())
    if not batch_ids:
        raise ValueError("No work packets or draft requests were found")

    batches: list[dict[str, Any]] = []
    handoff_input: list[dict[str, str]] = []
    for batch_id in batch_ids:
        if batch_id not in packet_paths:
            raise ValueError(f"Missing work packet for {batch_id}")
        if batch_id not in request_paths:
            raise ValueError(f"Missing draft request for {batch_id}")
        packet = read_json(packet_paths[batch_id])
        request = read_json(request_paths[batch_id])
        if packet.get("batch_id") != batch_id:
            raise ValueError(f"Work packet batch_id mismatch for {batch_id}")
        if request.get("batch_id") != batch_id:
            raise ValueError(f"Draft request batch_id mismatch for {batch_id}")
        if packet.get("packet_id") != request.get("packet_id"):
            raise ValueError(f"Packet id mismatch for {batch_id}")
        if target_locale and request.get("target_locale") != target_locale:
            raise ValueError(f"Draft request target locale mismatch for {batch_id}")
        generated_path = generated_dir / f"{batch_id}.jsonl"
        batches.append(
            {
                "batch_id": batch_id,
                "packet_id": packet["packet_id"],
                "request_id": request["request_id"],
                "work_packet": packet_paths[batch_id].as_posix(),
                "draft_request": request_paths[batch_id].as_posix(),
                "generated": generated_path.as_posix(),
                "segment_count": len(packet.get("segments", [])),
                "target_locale": request.get("target_locale"),
                "status": "pending",
            }
        )
        handoff_input.append({"batch_id": batch_id, "request_id": request["request_id"], "packet_id": packet["packet_id"]})

    digest = hashlib.sha256(json.dumps(handoff_input, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    locales = sorted({str(batch.get("target_locale")) for batch in batches if batch.get("target_locale")})
    return {
        "protocol_version": PROTOCOL_VERSION,
        "handoff_id": digest,
        "task": "host_agent_translation_generation",
        "target_locales": locales,
        "request_count": len(batches),
        "generated_dir": generated_dir.as_posix(),
        "output_contract": {
            "format": "jsonl_per_batch",
            "record_schema": "segment.schema.json",
            "required_status": "generated",
            "import_command": "localize-anything import-generated-handoff <handoff> <response-dir>",
            "validation_command": "localize-anything validate-generated <work-packet> <generated-jsonl>",
        },
        "batches": batches,
    }


def collect_generated_handoff(handoff: dict[str, Any], output_jsonl: Path | None = None) -> dict[str, Any]:
    combined: list[dict[str, Any]] = []
    qa_results: list[dict[str, Any]] = []
    batch_results: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for batch in handoff.get("batches", []):
        work_packet_path = Path(str(batch.get("work_packet", "")))
        generated_path = Path(str(batch.get("generated", "")))
        if not work_packet_path.is_file():
            qa = _handoff_failure("missing_work_packet", f"Missing work packet for {batch.get('batch_id')}: {work_packet_path}")
        elif not generated_path.is_file():
            qa = _handoff_failure("missing_generated_batch", f"Missing generated JSONL for {batch.get('batch_id')}: {generated_path}")
        else:
            qa = validate_generated_segments(read_json(work_packet_path), read_jsonl(generated_path))
            if qa["status"] != "fail":
                records = read_jsonl(generated_path)
                combined.extend(records)
        for item in qa.get("items", []):
            enriched = dict(item)
            enriched["batch_id"] = batch.get("batch_id")
            items.append(enriched)
        qa_results.append(qa)
        batch_results.append(
            {
                "batch_id": batch.get("batch_id"),
                "generated": generated_path.as_posix(),
                "qa_status": qa["status"],
                "blocking_count": qa.get("summary", {}).get("blocking_count", 0),
                "warning_count": qa.get("summary", {}).get("warning_count", 0),
            }
        )
    if output_jsonl is not None:
        write_jsonl(output_jsonl, combined)
    blocking = sum(result.get("summary", {}).get("blocking_count", 0) for result in qa_results)
    warnings = sum(result.get("summary", {}).get("warning_count", 0) for result in qa_results)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "handoff_id": handoff.get("handoff_id"),
        "status": "fail" if blocking else "pass_with_warnings" if warnings else "pass",
        "summary": {
            "batch_count": len(batch_results),
            "generated_segment_count": len(combined),
            "blocking_count": blocking,
            "warning_count": warnings,
        },
        "items": items,
        "batches": batch_results,
        "combined_output": output_jsonl.as_posix() if output_jsonl else None,
    }


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _response_candidates(response_text: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for index, match in enumerate(FENCED_BLOCK_RE.finditer(response_text), 1):
        candidates.append((f"fenced-{index}", match.group(1).strip()))
    stripped = response_text.strip()
    if stripped:
        candidates.append(("body", stripped))
    return candidates


def _find_response_file(response_dir: Path, batch_id: str) -> Path | None:
    if not batch_id:
        return None
    for pattern in RESPONSE_FILE_PATTERNS:
        candidate = response_dir / pattern.format(batch_id=batch_id)
        if candidate.is_file():
            return candidate
    matches = sorted(path for path in response_dir.glob(f"{batch_id}*") if path.is_file())
    return matches[0] if matches else None


def _parse_response_candidate(candidate: str) -> tuple[list[dict[str, Any]], str]:
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        return _parse_jsonl_response(candidate), "jsonl"
    return _records_from_json_value(value), "json"


def _parse_jsonl_response(candidate: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(candidate.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at response line {line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Invalid JSONL object at response line {line_number}")
        records.append(value)
    if not records:
        raise ValueError("Response contains no JSONL records")
    return records


def _records_from_json_value(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        if not all(isinstance(item, dict) for item in value):
            raise ValueError("JSON array response must contain only objects")
        return [dict(item) for item in value]
    if isinstance(value, dict):
        if isinstance(value.get("segments"), list):
            return _records_from_json_value(value["segments"])
        if isinstance(value.get("generated_segments"), list):
            return _records_from_json_value(value["generated_segments"])
        if isinstance(value.get("translations"), list):
            return _records_from_json_value(value["translations"])
        if value.get("segment_id"):
            return [dict(value)]
        return _records_from_segment_map(value)
    raise ValueError("JSON response must be an object or array")


def _records_from_segment_map(value: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for segment_id, target in value.items():
        if isinstance(target, dict):
            record = dict(target)
            record.setdefault("segment_id", str(segment_id))
            records.append(record)
        elif isinstance(target, (str, int, float, bool)) or target is None:
            record = {"segment_id": str(segment_id)}
            if target is not None:
                record["target"] = str(target)
            records.append(record)
        else:
            raise ValueError(f"Segment map value for {segment_id!r} must be a target string or object")
    return records


def _target_value(record: dict[str, Any]) -> Any:
    for key in TARGET_ALIASES:
        if key in record:
            return record[key]
    return None


def _generation_metadata(record: dict[str, Any], response_format: str) -> dict[str, Any]:
    generation = record.get("generation")
    metadata = dict(generation) if isinstance(generation, dict) else {}
    metadata.setdefault("provider", "host_agent")
    metadata["imported_from"] = "llm_response"
    metadata["response_format"] = response_format
    return metadata


def _qa_item(category: str, severity: str, message: str, segment_id: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "channel": "runtime",
        "category": category,
        "severity": severity,
        "message": message,
        "checked_by": "runtime",
        "coverage": "complete",
        "confidence": "deterministic",
    }
    if segment_id:
        item["segment_id"] = segment_id
    return item


def _handoff_failure(category: str, message: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "status": "fail",
        "summary": {"blocking_count": 1, "warning_count": 0},
        "items": [_qa_item(category, "blocking", message)],
    }
