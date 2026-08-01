from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    request = json.loads(sys.stdin.read())
    phase = request["phase"]
    project = Path(request["project_root"])
    source = project / request["source"]
    target = project / request["target"]
    if phase == "detect":
        result = {"detected": source.is_file() and _read_catalog(source).get("messages") is not None}
    elif phase == "inventory":
        result = {"items": [{"id": item["id"], "source_path": request["source"]} for item in _messages(source)]}
    elif phase == "extract":
        result = {
            "source_segments": _segments(source, request["source"], request["source_locale"]),
            "target_segments": _segments(target, request["target"], request["target_locale"]),
        }
    elif phase == "validate_source":
        result = {"validation": _validate_source(source)}
    else:
        raise ValueError(f"unsupported phase: {phase}")
    print(json.dumps({"schema": f"localize-anything-project-adapter-{phase.replace('_', '-')}-result-v1", "status": "pass", **result}))
    return 0


def _read_catalog(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("messages"), list):
        raise ValueError(f"sample catalog requires a messages list: {path}")
    return value


def _messages(path: Path) -> list[dict[str, str]]:
    messages = []
    for item in _read_catalog(path)["messages"]:
        if isinstance(item, dict) and isinstance(item.get("id"), str) and isinstance(item.get("text"), str):
            messages.append({"id": item["id"], "text": item["text"]})
    return messages


def _segments(path: Path, logical_path: str, locale: str) -> list[dict[str, Any]]:
    segments = []
    for item in _messages(path):
        segments.append(
            {
                "segment_id": f"sample:{item['id']}",
                "source_path": logical_path,
                "source_locale": locale,
                "source": item["text"],
                "source_hash": hashlib.sha256(item["text"].encode("utf-8")).hexdigest(),
                "context": {"resource_key": item["id"]},
            }
        )
    return segments


def _validate_source(path: Path) -> dict[str, Any]:
    seen = set()
    items = []
    for item in _messages(path):
        if item["id"] in seen:
            items.append({"severity": "blocking", "kind": "duplicate_message", "message": f"Duplicate sample message id: {item['id']}"})
        seen.add(item["id"])
    return {"status": "fail" if items else "pass", "items": items}


if __name__ == "__main__":
    raise SystemExit(main())
