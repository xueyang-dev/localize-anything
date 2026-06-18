from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION


REVIEW_COLUMNS = [
    "segment_id",
    "source_path",
    "context",
    "source_locale",
    "target_locale",
    "status",
    "placeholders",
    "source",
    "target",
    "generation_warning",
]


def write_review_sheet(
    generated_segments: list[dict[str, Any]],
    markdown_output: Path | None = None,
    csv_output: Path | None = None,
) -> dict[str, Any]:
    if markdown_output is None and csv_output is None:
        raise ValueError("At least one review sheet output path is required")
    rows = review_rows(generated_segments)
    if markdown_output is not None:
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_review_markdown(rows), encoding="utf-8", newline="\n")
    if csv_output is not None:
        csv_output.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(rows, csv_output)
    return {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_channels": ["runtime"],
        "status": "pass",
        "summary": {
            "segment_count": len(rows),
            "source_file_count": len({row["source_path"] for row in rows}),
            "warning_count": sum(1 for row in rows if row["generation_warning"]),
        },
        "markdown_output": markdown_output.as_posix() if markdown_output else None,
        "csv_output": csv_output.as_posix() if csv_output else None,
    }


def review_rows(generated_segments: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for segment in generated_segments:
        generation = segment.get("generation") if isinstance(segment.get("generation"), dict) else {}
        rows.append(
            {
                "segment_id": str(segment.get("segment_id", "")),
                "source_path": str(segment.get("source_path", "")),
                "context": _context_label(segment.get("context", {})),
                "source_locale": str(segment.get("source_locale", "")),
                "target_locale": str(segment.get("target_locale", "")),
                "status": str(segment.get("status", "")),
                "placeholders": ", ".join(str(item) for item in segment.get("constraints", {}).get("placeholders", [])),
                "source": str(segment.get("source", "")),
                "target": _target_value(segment),
                "generation_warning": str(generation.get("warning", "")),
            }
        )
    rows.sort(key=lambda row: (row["source_path"], row["context"], row["segment_id"]))
    return rows


def render_review_markdown(rows: list[dict[str, str]]) -> str:
    lines = [
        "# Translation Review Sheet",
        "",
        f"- Segment count: {len(rows)}",
        f"- Source files: {len({row['source_path'] for row in rows})}",
        f"- Warnings: {sum(1 for row in rows if row['generation_warning'])}",
        "",
        "Review target text before applying the delivery. Preserve placeholders exactly.",
        "",
    ]
    current_source = None
    for row in rows:
        if row["source_path"] != current_source:
            current_source = row["source_path"]
            lines.extend([f"## {current_source or 'unknown source'}", ""])
        lines.extend(
            [
                f"### `{row['segment_id']}`",
                "",
                f"- Context: `{row['context'] or 'n/a'}`",
                f"- Status: `{row['status'] or 'n/a'}`",
                f"- Target locale: `{row['target_locale'] or 'n/a'}`",
                f"- Placeholders: `{row['placeholders'] or 'none'}`",
            ]
        )
        if row["generation_warning"]:
            lines.append(f"- Generation warning: {row['generation_warning']}")
        lines.extend(
            [
                "",
                "Source:",
                "",
                "````text",
                row["source"],
                "````",
                "",
                "Target:",
                "",
                "````text",
                row["target"],
                "````",
                "",
            ]
        )
    return "\n".join(lines)


def _write_csv(rows: list[dict[str, str]], output: Path) -> None:
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _target_value(segment: dict[str, Any]) -> str:
    if "target_plural" in segment:
        return json.dumps(segment["target_plural"], ensure_ascii=False, sort_keys=True)
    return str(segment.get("target", ""))


def _context_label(context: Any) -> str:
    if not isinstance(context, dict):
        return ""
    for key in ("json_pointer", "resource_name", "key", "cue_id", "row", "id"):
        value = context.get(key)
        if value is not None:
            return str(value)
    if context.get("content_unit"):
        return str(context["content_unit"])
    return ""
