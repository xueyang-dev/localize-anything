from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION


def validate_document(value: Any, schema: dict[str, Any], schema_dir: Path, location: str = "$") -> list[str]:
    errors: list[str] = []
    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str) or "://" in reference or reference.startswith("#"):
            return [f"{location}: unsupported schema reference {reference!r}"]
        referenced = json.loads((schema_dir / reference).read_text(encoding="utf-8"))
        return validate_document(value, referenced, schema_dir, location)

    if "oneOf" in schema:
        variants = [validate_document(value, variant, schema_dir, location) for variant in schema["oneOf"]]
        passing = sum(not variant_errors for variant_errors in variants)
        if passing != 1:
            errors.append(f"{location}: expected exactly one oneOf variant, got {passing}")
        return errors

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        return [f"{location}: expected type {expected_type!r}, got {_type_name(value)}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{location}: expected constant {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{location}: expected one of {schema['enum']!r}, got {value!r}")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{location}: string is shorter than minLength")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{location}: string does not match {schema['pattern']!r}")
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{location}: invalid date-time")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{location}: value is less than minimum {schema['minimum']}")
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{location}: array is shorter than minItems")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{location}: array items are not unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_document(item, item_schema, schema_dir, f"{location}[{index}]"))
    elif isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{location}: missing required property {key!r}")
        properties = schema.get("properties", {})
        for key, child in value.items():
            if key in properties:
                errors.extend(validate_document(child, properties[key], schema_dir, f"{location}.{key}"))
                continue
            additional = schema.get("additionalProperties", True)
            if additional is False:
                errors.append(f"{location}: unexpected property {key!r}")
            elif isinstance(additional, dict):
                errors.extend(validate_document(child, additional, schema_dir, f"{location}.{key}"))
    return errors


def validate_protocol_tree(protocol_root: Path) -> dict[str, Any]:
    schema_dir = protocol_root / "schemas"
    example_dir = protocol_root / "examples"
    schemas = {
        path.name.removesuffix(".schema.json"): path for path in sorted(schema_dir.glob("*.schema.json"))
    }
    examples = {path.stem: path for path in sorted(example_dir.glob("*.json"))}
    errors: list[str] = []
    missing_examples = sorted(schemas.keys() - examples.keys())
    extra_examples = sorted(examples.keys() - schemas.keys())
    if missing_examples:
        errors.append(f"Missing protocol examples: {', '.join(missing_examples)}")
    if extra_examples:
        errors.append(f"Examples without schemas: {', '.join(extra_examples)}")
    for name in sorted(schemas.keys() & examples.keys()):
        try:
            schema = json.loads(schemas[name].read_text(encoding="utf-8"))
            example = json.loads(examples[name].read_text(encoding="utf-8"))
            errors.extend(f"{name}: {error}" for error in validate_document(example, schema, schema_dir))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{name}: cannot validate: {exc}")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": "fail" if errors else "pass",
        "schemas_checked": len(schemas),
        "examples_checked": len(examples),
        "errors": errors,
    }


def _matches_type(value: Any, expected: str | list[str]) -> bool:
    names = [expected] if isinstance(expected, str) else expected
    return any(
        {
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "string": isinstance(value, str),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
            "null": value is None,
        }.get(name, False)
        for name in names
    )


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__
