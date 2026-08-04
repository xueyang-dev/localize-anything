from __future__ import annotations

"""TypeScript locale catalog adapter for ``core.typescript-locale``.

Scope (by design): this adapter parses only the constrained shape of
TypeScript locale catalogs -- object literals whose leaves are strings,
template literals, arrays of strings, and arrow functions whose bodies
contain string/template literals.  It is a real tokenizer/parser, not a
regex rewriter, and it fails closed: any construct outside the supported
shape raises instead of being silently mis-parsed.

Supported source forms (see benchmarks/hermes-agent fixtures and tests):

    export const en = {
      common: { save: 'Save' }
    }

    export const zh: Translations = {
      common: { save: '保存' }
    }

    export const ja = defineLocale({
      common: { save: '保存' }
    })

Extraction emits protocol segments.  Rebuild edits only the exact spans of
translated literals in the source file, so imports, exports, comments, key
names, function signatures, expressions inside ``${...}``, identifiers and
all non-text syntax are preserved byte-for-byte unless a literal is changed.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import PROTOCOL_VERSION
from .json_adapter import extract_placeholders, source_hash


ADAPTER_FORMAT = "typescript-locale"

_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_NUMBER_RE = re.compile(r"0[xX][0-9a-fA-F]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

@dataclass
class Token:
    kind: str  # "ident" | "number" | "string" | "template" | "punct" | "eof"
    value: str
    start: int
    end: int
    # For strings: the quote character.  For templates: parsed parts.
    quote: str | None = None
    parts: list[tuple[str, str]] = field(default_factory=list)  # ("text"|"expr", raw)


class TSParseError(ValueError):
    """Raised when a file is not a supported TypeScript locale catalog."""


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if text.startswith("//", index):
            newline = text.find("\n", index)
            index = length if newline == -1 else newline + 1
            continue
        if text.startswith("/*", index):
            close = text.find("*/", index + 2)
            if close == -1:
                raise TSParseError(f"unterminated block comment at offset {index}")
            index = close + 2
            continue
        if char in {"'", '"'}:
            end, value = _scan_string(text, index, char)
            tokens.append(Token("string", value, index, end, quote=char))
            index = end
            continue
        if char == "`":
            end, parts = _scan_template(text, index)
            raw = text[index + 1 : end - 1]
            tokens.append(Token("template", raw, index, end, parts=parts))
            index = end
            continue
        ident = _IDENT_RE.match(text, index)
        if ident:
            tokens.append(Token("ident", ident.group(0), index, ident.end()))
            index = ident.end()
            continue
        number = _NUMBER_RE.match(text, index)
        if number:
            tokens.append(Token("number", number.group(0), index, number.end()))
            index = number.end()
            continue
        tokens.append(Token("punct", char, index, index + 1))
        index += 1
    tokens.append(Token("eof", "", length, length))
    return tokens


def _scan_string(text: str, start: int, quote: str) -> tuple[int, str]:
    index = start + 1
    out: list[str] = []
    while index < len(text):
        char = text[index]
        if char == "\\":
            if index + 1 >= len(text):
                raise TSParseError(f"unterminated escape at offset {index}")
            out.append(text[index : index + 2])
            index += 2
            continue
        if char == quote:
            return index + 1, "".join(out)
        out.append(char)
        index += 1
    raise TSParseError(f"unterminated string literal at offset {start}")


def _scan_template(text: str, start: int) -> tuple[int, list[tuple[str, str]]]:
    index = start + 1
    parts: list[tuple[str, str]] = []
    text_start = index
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "`":
            if index > text_start:
                parts.append(("text", text[text_start:index]))
            return index + 1, parts
        if char == "$" and index + 1 < len(text) and text[index + 1] == "{":
            if index > text_start:
                parts.append(("text", text[text_start:index]))
            close = _scan_expression(text, index + 2)
            parts.append(("expr", text[index : close + 1]))
            index = close + 1
            text_start = index
            continue
        index += 1
    raise TSParseError(f"unterminated template literal at offset {start}")


def _scan_expression(text: str, start: int) -> int:
    """Return the offset of the ``}`` closing a ``${`` expression at ``start``."""
    index = start
    depth = 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char in {"'", '"'}:
            index = _scan_string(text, index, char)[0]
            continue
        if char == "`":
            index = _scan_template(text, index)[0]
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise TSParseError(f"unterminated template expression starting at offset {start}")


# ---------------------------------------------------------------------------
# Parser (constrained catalog grammar)
# ---------------------------------------------------------------------------

@dataclass
class Literal:
    kind: str  # "string" | "template"
    quote: str | None
    start: int
    end: int
    raw: str
    cooked: str
    expressions: list[str] = field(default_factory=list)


@dataclass
class FunctionValue:
    signature: str
    literals: list[Literal] = field(default_factory=list)


@dataclass
class ObjectValue:
    entries: list[tuple[str, str, Any]] = field(default_factory=list)  # (key, key_kind, value)


@dataclass
class ArrayValue:
    items: list[Any] = field(default_factory=list)


@dataclass
class ExpressionValue:
    name: str = ""


@dataclass
class Catalog:
    root: ObjectValue
    export_name: str
    wrapper: str  # "plain" | "defineLocale"
    duplicates: list[str] = field(default_factory=list)


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.position = 0

    def peek(self, offset: int = 0) -> Token:
        index = min(self.position + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def take(self) -> Token:
        token = self.tokens[self.position]
        if token.kind != "eof":
            self.position += 1
        return token

    def expect(self, value: str) -> Token:
        token = self.take()
        if token.kind != "punct" or token.value != value:
            raise TSParseError(f"expected {value!r}, got {token.value!r} at offset {token.start}")
        return token

    # -- exports -----------------------------------------------------------

    def find_catalog(self) -> Catalog:
        """Find the first ``export const <name> [:<Type>] = <value>`` catalog."""
        while True:
            token = self.take()
            if token.kind == "eof":
                raise TSParseError("no catalog export found (expected `export const <name> = { ... }`)")
            if token.kind != "ident" or token.value != "export":
                continue
            const = self.take()
            if const.kind != "ident" or const.value != "const":
                continue
            name = self.take()
            if name.kind != "ident":
                continue
            # Skip an optional `: Type` annotation.
            if self.peek().kind == "punct" and self.peek().value == ":":
                self.take()
                self._skip_type_annotation()
            return self._finish_export(name.value)

    def _finish_export(self, export_name: str) -> Catalog:
        self.expect("=")
        value, wrapper = self._parse_export_value()
        if not isinstance(value, ObjectValue):
            raise TSParseError(f"export {export_name!r} is not an object literal catalog")
        duplicates = self._collect_duplicates(value)
        return Catalog(value, export_name, wrapper, duplicates)

    def _parse_export_value(self) -> tuple[Any, str]:
        token = self.peek()
        if token.kind == "ident" and token.value == "defineLocale":
            self.take()
            self.expect("(")
            value = self._parse_value()
            self.expect(")")
            return value, "defineLocale"
        return self._parse_value(), "plain"

    def _skip_type_annotation(self) -> None:
        depth = 0
        while True:
            if self.peek().kind == "punct" and self.peek().value == "=" and depth == 0:
                return
            token = self.take()
            if token.kind == "eof":
                raise TSParseError("unterminated type annotation")
            if token.kind != "punct":
                continue
            if token.value in {"{", "[", "("}:
                depth += 1
            elif token.value in {"}", "]", ")"}:
                depth -= 1
                if depth < 0:
                    return
            elif token.value in {",", ";"} and depth == 0:
                return

    # -- values ------------------------------------------------------------

    def _parse_value(self) -> Any:
        token = self.peek()
        if token.kind == "string":
            self.take()
            return self._literal(token)
        if token.kind == "template":
            self.take()
            return self._literal(token)
        if token.kind == "punct" and token.value == "{":
            return self._parse_object()
        if token.kind == "punct" and token.value == "[":
            return self._parse_array()
        if token.kind == "punct" and token.value == "(":
            return self._parse_function()
        if token.kind == "ident":
            self.take()
            if self.peek().kind == "punct" and self.peek().value == "=" and self.peek(1).kind == "punct" and self.peek(1).value == ">":
                return self._parse_function(token)
            # Call-expression values such as `defineFieldCopy({...})` wrap an
            # object literal; unwrap the single object argument.
            if self.peek().kind == "punct" and self.peek().value == "(":
                self.expect("(")
                inner = self._parse_value()
                self.expect(")")
                return inner
            return ExpressionValue(token.value)
        raise TSParseError(f"unsupported value token {token.value!r} at offset {token.start}")

    def _parse_object(self) -> ObjectValue:
        self.expect("{")
        entries: list[tuple[str, str, Any]] = []
        while True:
            token = self.peek()
            if token.kind == "punct" and token.value == "}":
                self.take()
                return ObjectValue(entries)
            if token.kind == "punct" and token.value == ",":
                self.take()
                continue
            key, key_kind = self._parse_key()
            self.expect(":")
            value = self._parse_value()
            entries.append((key, key_kind, value))

    def _parse_key(self) -> tuple[str, str]:
        token = self.take()
        if token.kind == "ident":
            return token.value, "ident"
        if token.kind == "string":
            return _unescape_js(token.value), "string"
        if token.kind == "number":
            return token.value, "number"
        raise TSParseError(f"invalid object key {token.value!r} at offset {token.start}")

    def _parse_array(self) -> ArrayValue:
        self.expect("[")
        items: list[Any] = []
        while True:
            token = self.peek()
            if token.kind == "punct" and token.value == "]":
                self.take()
                return ArrayValue(items)
            if token.kind == "punct" and token.value == ",":
                self.take()
                continue
            items.append(self._parse_value())

    def _parse_function(self, single_param: Token | None = None) -> FunctionValue:
        if single_param is not None:
            signature = single_param.value
            self.expect("=")
            self.expect(">")
        else:
            open_token = self.take()
            signature = self._scan_parens(open_token.start)
            self.expect("=")
            self.expect(">")
        literals = self._collect_body_literals()
        return FunctionValue(signature, literals)

    def _scan_parens(self, start: int) -> str:
        """Consume a balanced (...) parameter list; return normalized signature text."""
        depth = 1
        start_index = self.position
        while depth:
            token = self.take()
            if token.kind == "eof":
                raise TSParseError(f"unterminated parameter list at offset {start}")
            if token.kind == "punct" and token.value == "(":
                depth += 1
            elif token.kind == "punct" and token.value == ")":
                depth -= 1
        return _normalize_space(_tokens_text(self.tokens[start_index : self.position - 1]))

    def _collect_body_literals(self) -> list[Literal]:
        literals: list[Literal] = []
        depth = 0
        while True:
            token = self.peek()
            if token.kind == "eof":
                raise TSParseError("unterminated arrow function body")
            if token.kind == "punct":
                if token.value in {",", "}", ")", "]", ";"} and depth == 0:
                    return [literal for literal in literals if literal.cooked != "" or literal.expressions]
                if token.value in {"{", "[", "("}:
                    depth += 1
                elif token.value in {"}", "]", ")"}:
                    depth -= 1
                self.take()
                continue
            if token.kind in {"string", "template"}:
                self.take()
                literals.append(self._literal(token))
                continue
            if token.kind == "ident":
                self.take()
                # Arrow functions nested in expression bodies.
                if self.peek().kind == "punct" and self.peek().value == "=" and self.peek(1).kind == "punct" and self.peek(1).value == ">":
                    self.take()
                    self.take()
                    literals.extend(self._collect_body_literals())
                continue
            self.take()
        return [literal for literal in literals if literal.cooked != "" or literal.expressions]

    def _literal(self, token: Token) -> Literal:
        if token.kind == "string":
            return Literal("string", token.quote, token.start, token.end, token.value, _unescape_js(token.value))
        cooked_parts: list[str] = []
        expressions: list[str] = []
        for kind, raw in token.parts:
            if kind == "text":
                cooked_parts.append(_unescape_template_text(raw))
            else:
                expressions.append(raw)
        return Literal(
            "template",
            "`",
            token.start,
            token.end,
            token.value,
            "".join(cooked_parts),
            expressions,
        )

    @staticmethod
    def _collect_duplicates(root: ObjectValue) -> list[str]:
        duplicates: list[str] = []
        seen: dict[str, str] = {}

        def visit(node: ObjectValue, pointer: str) -> None:
            for key, _key_kind, value in node.entries:
                child = f"{pointer}/{key}"
                if key in seen and seen[key] == pointer:
                    duplicates.append(child)
                seen[key] = pointer
                if isinstance(value, ObjectValue):
                    visit(value, child)
                elif isinstance(value, ArrayValue):
                    for item in value.items:
                        if isinstance(item, ObjectValue):
                            visit(item, child)

        visit(root, "")
        return sorted(set(duplicates))


# ---------------------------------------------------------------------------
# Public adapter API
# ---------------------------------------------------------------------------

def parse_catalog(text: str) -> Catalog:
    return _Parser(tokenize(text)).find_catalog()


def extract_segments(
    path: Path,
    source_locale: str,
    source_path: str | None = None,
    format_name: str | None = None,
) -> list[dict[str, Any]]:
    """Extract protocol segments from a TypeScript locale catalog."""
    if format_name and format_name != ADAPTER_FORMAT:
        raise ValueError(f"Unsupported format for TypeScript adapter: {format_name}")
    logical_path = source_path or path.as_posix()
    catalog = parse_catalog(path.read_text(encoding="utf-8"))
    if catalog.duplicates:
        raise TSParseError(f"duplicate keys in {logical_path}: {', '.join(catalog.duplicates)}")
    segments: list[dict[str, Any]] = []
    _walk_value(
        catalog.root,
        "",
        logical_path,
        source_locale,
        segments,
        function_pointer=None,
        function_signature=None,
    )
    return segments


def _walk_value(
    value: Any,
    pointer: str,
    logical_path: str,
    source_locale: str,
    segments: list[dict[str, Any]],
    function_pointer: str | None,
    function_signature: str | None,
) -> None:
    if isinstance(value, ObjectValue):
        for key, _key_kind, child in value.entries:
            child_pointer = f"{pointer}/{key}"
            _walk_value(child, child_pointer, logical_path, source_locale, segments, function_pointer, function_signature)
        return
    if isinstance(value, ArrayValue):
        for index, child in enumerate(value.items):
            _walk_value(child, f"{pointer}/{index}", logical_path, source_locale, segments, function_pointer, function_signature)
        return
    if isinstance(value, FunctionValue):
        for index, literal in enumerate(value.literals):
            _segment(
                literal,
                f"{pointer}#fn{index}",
                logical_path,
                source_locale,
                segments,
                function_pointer=pointer,
                function_signature=value.signature,
            )
        return
    if isinstance(value, Literal):
        if value.cooked == "" and not value.expressions:
            return  # empty literals have nothing to translate
        _segment(
            value,
            pointer,
            logical_path,
            source_locale,
            segments,
            function_pointer=function_pointer,
            function_signature=function_signature,
        )


def _segment(
    literal: Literal,
    pointer: str,
    logical_path: str,
    source_locale: str,
    segments: list[dict[str, Any]],
    function_pointer: str | None,
    function_signature: str | None,
) -> None:
    digest = hashlib.sha256(pointer.encode("utf-8")).hexdigest()[:20]
    context: dict[str, Any] = {
        "content_type": "locale_string",
        "ts_kind": literal.kind,
        "pointer": pointer,
        "line_index": None,
        "value_start": literal.start,
        "value_end": literal.end,
        "quote_style": literal.quote,
        "template_expressions": literal.expressions,
        "raw": literal.raw,
        "cooked": literal.cooked,
    }
    if function_pointer is not None:
        context["function_pointer"] = function_pointer
        context["function_signature"] = function_signature
    constraints: dict[str, Any] = {
        "placeholders": extract_placeholders(literal.cooked),
        "template_expressions": list(literal.expressions),
        "markup": [],
    }
    segments.append(
        {
            "protocol_version": PROTOCOL_VERSION,
            "evidence_channels": ["adapter"],
            "segment_id": f"typescript-locale:{logical_path}#{digest}",
            "source": _literal_source(literal),
            "source_locale": source_locale,
            "source_path": logical_path,
            "source_hash": source_hash(literal.raw),
            "context": context,
            "constraints": constraints,
            "status": "new",
        }
    )


def _literal_source(literal: Literal) -> str:
    if literal.kind == "string":
        return literal.cooked
    return literal.raw


def rebuild(
    source_path: Path,
    translated_segments: list[dict[str, Any]],
    output: Path,
    format_name: str | None = None,
    export_name: str | None = None,
) -> None:
    """Rebuild a staged catalog by replacing translated literal spans only."""
    if format_name and format_name != ADAPTER_FORMAT:
        raise ValueError(f"Unsupported format for TypeScript adapter: {format_name}")
    text = source_path.read_text(encoding="utf-8")
    if export_name:
        text = _rename_export(text, export_name)
    edits: list[tuple[int, int, str]] = []
    for segment in translated_segments:
        if "target" not in segment:
            continue
        context = segment.get("context", {})
        start = context.get("value_start")
        end = context.get("value_end")
        if not all(isinstance(item, int) for item in (start, end)):
            raise ValueError(f"Segment lacks TypeScript literal span: {segment.get('segment_id')}")
        # Identity round-trip: if the target is unchanged, write back the
        # original literal bytes so escaping and spacing never drift.
        kind = context.get("ts_kind")
        unchanged = (
            str(segment["target"]) == context.get("raw")
            if kind == "template"
            else str(segment["target"]) == context.get("cooked")
        )
        if unchanged and context.get("raw") is not None:
            edits.append((start, end, text[start:end]))
            continue
        encoded = _encode_target(str(segment["target"]), context)
        edits.append((start, end, encoded))
    for start, end, encoded in sorted(edits, reverse=True):
        if start < 0 or end > len(text) or start >= end:
            raise ValueError(f"TypeScript literal span out of bounds: {start}:{end}")
        text = text[:start] + encoded + text[end:]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8", newline="")


def _rename_export(text: str, export_name: str) -> str:
    """Rename the catalog export identifier (e.g. ``en`` -> ``fr``).

    ``parse_catalog`` already proved the file has exactly one catalog export
    of the constrained shape, so the first ``export const <name>`` declaration
    is unambiguous.  The ``: Translations`` type annotation, when present, is
    preserved.
    """
    catalog = parse_catalog(text)
    pattern = re.compile(r"\bexport\s+const\s+" + re.escape(catalog.export_name) + r"\b")
    match = pattern.search(text)
    if not match:
        raise TSParseError(f"cannot locate export declaration for {catalog.export_name!r}")
    start = match.end() - len(catalog.export_name)
    return text[:start] + export_name + text[match.end() :]


def _encode_target(target: str, context: dict[str, Any]) -> str:
    kind = context.get("ts_kind")
    if kind == "string":
        quote = context.get("quote_style") or "'"
        return _encode_js_string(target, quote)
    if kind == "template":
        return _encode_template(target, context.get("template_expressions") or [])
    raise ValueError(f"Unknown ts_kind {kind!r}")


def _encode_js_string(value: str, quote: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\b", "\\b")
        .replace("\f", "\\f")
    )
    if quote == "'":
        escaped = escaped.replace("'", "\\'")
    else:
        escaped = escaped.replace('"', '\\"')
    return quote + escaped + quote


def _encode_template(target: str, expressions: list[str]) -> str:
    parts = _split_target_template(target)
    expression_count = sum(1 for kind, _raw in parts if kind == "expr")
    if expression_count != len(expressions):
        raise ValueError(
            f"template expression count mismatch: target has {expression_count}, source has {len(expressions)}"
        )
    expression_index = 0
    out: list[str] = []
    for kind, raw in parts:
        if kind == "expr":
            out.append(expressions[expression_index])
            expression_index += 1
        else:
            out.append(raw.replace("\\", "\\\\").replace("`", "\\`"))
    return "`" + "".join(out) + "`"


def _split_target_template(target: str) -> list[tuple[str, str]]:
    """Split translated template text into text parts and ``${...}`` markers."""
    parts: list[tuple[str, str]] = []
    index = 0
    text_start = 0
    while index < len(target):
        char = target[index]
        if char == "\\":
            index += 2
            continue
        if char == "$" and index + 1 < len(target) and target[index + 1] == "{":
            if index > text_start:
                parts.append(("text", target[text_start:index]))
            close = _scan_expression(target, index + 2)
            parts.append(("expr", target[index : close + 1]))
            index = close + 1
            text_start = index
            continue
        index += 1
    if text_start < len(target):
        parts.append(("text", target[text_start:]))
    return parts


def validate_pair(source_path: Path, target_path: Path, format_name: str | None = None) -> dict[str, Any]:
    """Deterministic structural QA between a source and a staged catalog."""
    items: list[dict[str, Any]] = []
    try:
        source = _leaf_map(source_path)
        target = _leaf_map(target_path)
    except (OSError, TSParseError) as exc:
        return _qa_result(items + [_qa_item("parse", "blocking", str(exc), target_path)])

    for pointer in sorted(source.keys() - target.keys()):
        items.append(_qa_item("key_coverage", "blocking", f"Missing localized value at {pointer}", target_path, pointer))
    for pointer in sorted(target.keys() - source.keys()):
        items.append(_qa_item("key_coverage", "blocking", f"Unexpected localized value at {pointer}", target_path, pointer))

    for pointer in sorted(source.keys() & target.keys()):
        src = source[pointer]
        tgt = target[pointer]
        if sorted(src["template_expressions"]) != sorted(tgt["template_expressions"]):
            items.append(
                _qa_item(
                    "template_expression_parity",
                    "blocking",
                    f"Template expression mismatch at {pointer}: source={src['template_expressions']}, target={tgt['template_expressions']}",
                    target_path,
                    pointer,
                )
            )
        if extract_placeholders(src["cooked"]) != extract_placeholders(tgt["cooked"]):
            items.append(
                _qa_item(
                    "placeholder_parity",
                    "blocking",
                    f"Placeholder mismatch at {pointer}: source={extract_placeholders(src['cooked'])}, target={extract_placeholders(tgt['cooked'])}",
                    target_path,
                    pointer,
                )
            )
        if src["signature"] != tgt["signature"]:
            items.append(
                _qa_item(
                    "function_signature_parity",
                    "blocking",
                    f"Function signature mismatch at {pointer}: source={src['signature']!r}, target={tgt['signature']!r}",
                    target_path,
                    pointer,
                )
            )
        if src["quote"] != tgt["quote"]:
            items.append(
                _qa_item(
                    "quote_style",
                    "warning",
                    f"Quote style changed at {pointer}: {src['quote']!r} -> {tgt['quote']!r}",
                    target_path,
                    pointer,
                )
            )
    return _qa_result(items)


def _leaf_map(path: Path) -> dict[str, dict[str, Any]]:
    catalog = parse_catalog(path.read_text(encoding="utf-8"))
    leaves: dict[str, dict[str, Any]] = {}
    duplicates: dict[str, int] = {}

    def visit(value: Any, pointer: str, signature: str | None) -> None:
        if isinstance(value, ObjectValue):
            for key, _key_kind, child in value.entries:
                visit(child, f"{pointer}/{key}", signature)
            return
        if isinstance(value, ArrayValue):
            for index, child in enumerate(value.items):
                visit(child, f"{pointer}/{index}", signature)
            return
        if isinstance(value, FunctionValue):
            for index, literal in enumerate(value.literals):
                visit(literal, f"{pointer}#fn{index}", value.signature)
            return
        if isinstance(value, Literal):
            if pointer in leaves:
                duplicates[pointer] = duplicates.get(pointer, 1) + 1
            leaves[pointer] = {
                "cooked": value.cooked,
                "raw": value.raw,
                "template_expressions": list(value.expressions),
                "quote": value.quote,
                "signature": signature,
            }

    visit(catalog.root, "", None)
    if duplicates:
        raise TSParseError(f"duplicate keys in {path}: {', '.join(sorted(duplicates))}")
    return leaves


def _qa_result(items: list[dict[str, Any]]) -> dict[str, Any]:
    blocking = sum(item["severity"] == "blocking" for item in items)
    warnings = sum(item["severity"] == "warning" for item in items)
    status = "fail" if blocking else "pass_with_warnings" if warnings else "pass"
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": status,
        "summary": {"blocking_count": blocking, "warning_count": warnings},
        "items": items,
    }


def _qa_item(category: str, severity: str, message: str, path: Path, segment_id: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "channel": "adapter",
        "category": category,
        "severity": severity,
        "message": message,
        "path": path.as_posix(),
        "checked_by": "adapter",
        "coverage": "complete",
        "confidence": "deterministic",
    }
    if segment_id:
        item["segment_id"] = segment_id
    return item


# ---------------------------------------------------------------------------
# Escaping helpers
# ---------------------------------------------------------------------------

_ESCAPES = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "b": "\b",
    "f": "\f",
    "v": "\v",
    "0": "\0",
}


def _unescape_js(value: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char != "\\" or index + 1 >= len(value):
            out.append(char)
            index += 1
            continue
        escaped = value[index + 1]
        if escaped in _ESCAPES:
            out.append(_ESCAPES[escaped])
            index += 2
            continue
        if escaped in {"'", '"', "\\"}:
            out.append(escaped)
            index += 2
            continue
        if escaped == "x" and index + 3 < len(value):
            out.append(chr(int(value[index + 2 : index + 4], 16)))
            index += 4
            continue
        if escaped == "u" and index + 5 < len(value) and value[index + 2] != "{":
            out.append(chr(int(value[index + 2 : index + 6], 16)))
            index += 6
            continue
        if escaped == "u" and value[index + 2] == "{":
            close = value.find("}", index + 3)
            if close != -1:
                out.append(chr(int(value[index + 3 : close], 16)))
                index = close + 1
                continue
        out.append(escaped)
        index += 2
    return "".join(out)


def _unescape_template_text(value: str) -> str:
    return _unescape_js(value)


def _normalize_space(value: str) -> str:
    return " ".join(value.split())


def _tokens_text(tokens: list[Token]) -> str:
    return "".join(token.value for token in tokens)
