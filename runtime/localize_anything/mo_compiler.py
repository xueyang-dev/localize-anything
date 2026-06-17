from __future__ import annotations

import struct
from pathlib import Path
from typing import Any


DEFAULT_HEADER = (
    "Project-Id-Version: localize-anything\n"
    "Content-Type: text/plain; charset=UTF-8\n"
    "Content-Transfer-Encoding: 8bit\n"
    "Language: zh_CN\n"
    "Plural-Forms: nplurals=1; plural=0;\n"
)


def compile_segments_to_mo(segments: list[dict[str, Any]], output: Path, header: str = DEFAULT_HEADER) -> None:
    catalog: dict[str, str] = {"": header}
    for segment in segments:
        source = str(segment.get("source", ""))
        if not source or "target" not in segment:
            continue
        context = segment.get("context", {})
        msgctxt = context.get("msgctxt") if isinstance(context, dict) else None
        key = f"{msgctxt}\x04{source}" if msgctxt else source
        catalog[key] = str(segment["target"])
    write_mo(catalog, output)


def write_mo(catalog: dict[str, str], output: Path) -> None:
    ordered = sorted(catalog.items(), key=lambda item: item[0].encode("utf-8"))
    ids = [_encoded(source) for source, _target in ordered]
    strings = [_encoded(target) for _source, target in ordered]
    count = len(ordered)
    key_table_offset = 7 * 4
    value_table_offset = key_table_offset + count * 8
    data_offset = value_table_offset + count * 8

    key_offsets: list[tuple[int, int]] = []
    value_offsets: list[tuple[int, int]] = []
    data = bytearray()
    for value in ids:
        key_offsets.append((len(value), data_offset + len(data)))
        data.extend(value)
        data.append(0)
    for value in strings:
        value_offsets.append((len(value), data_offset + len(data)))
        data.extend(value)
        data.append(0)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        handle.write(struct.pack("<7I", 0x950412DE, 0, count, key_table_offset, value_table_offset, 0, 0))
        for length, offset in key_offsets:
            handle.write(struct.pack("<2I", length, offset))
        for length, offset in value_offsets:
            handle.write(struct.pack("<2I", length, offset))
        handle.write(data)


def _encoded(value: str) -> bytes:
    return value.encode("utf-8")
