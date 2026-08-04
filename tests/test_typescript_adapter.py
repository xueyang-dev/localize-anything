from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.localize_anything.typescript_locale_adapter import (
    TSParseError,
    extract_segments,
    parse_catalog,
    rebuild,
    validate_pair,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "typescript-locale"


class TypeScriptAdapterTests(unittest.TestCase):

    def test_extract_strings_arrays_and_placeholders(self) -> None:
        source = FIXTURE_ROOT / "basic.ts"
        segments = extract_segments(source, "en", "i18n/basic.ts")
        pointers = {segment["context"]["pointer"] for segment in segments}
        self.assertEqual(
            pointers,
            {
                "/common/save",
                "/common/welcome",
                "/common/weekdaysShort/0",
                "/common/weekdaysShort/1",
                "/common/weekdaysShort/2",
                "/common/weekdaysShort/3",
                "/common/weekdaysShort/4",
                "/common/weekdaysShort/5",
                "/common/weekdaysShort/6",
                "/errors/retryCount",
            },
        )
        by_pointer = {segment["context"]["pointer"]: segment for segment in segments}
        self.assertEqual(by_pointer["/common/welcome"]["source"], "Hello {name}")
        self.assertEqual(by_pointer["/common/welcome"]["constraints"]["placeholders"], ["{name}"])
        self.assertEqual(by_pointer["/errors/retryCount"]["constraints"]["placeholders"], ["{count}"])

    def test_extract_typed_catalog(self) -> None:
        segments = extract_segments(FIXTURE_ROOT / "typed.ts", "en", "i18n/typed.ts")
        self.assertEqual({s["context"]["pointer"] for s in segments}, {"/common/save", "/common/welcome"})
        self.assertEqual(segments[0]["segment_id"].startswith("typescript-locale:i18n/typed.ts#"), True)

    def test_extract_define_locale_wrapper(self) -> None:
        segments = extract_segments(FIXTURE_ROOT / "define-locale.ts", "en", "i18n/define-locale.ts")
        self.assertEqual([s["context"]["pointer"] for s in segments], ["/common/save"])
        self.assertEqual(segments[0]["source"], "保存")

    def test_function_literals_and_expression_parity(self) -> None:
        source = FIXTURE_ROOT / "functions.ts"
        segments = extract_segments(source, "en", "i18n/functions.ts")
        by_pointer = {segment["context"]["pointer"]: segment for segment in segments}
        more = by_pointer["/common/more#fn0"]
        self.assertEqual(more["context"]["function_pointer"], "/common/more")
        self.assertEqual(more["context"]["function_signature"], "count")
        self.assertEqual(
            more["constraints"]["template_expressions"],
            ["${count}", "${count === 1 ? 'notification' : 'notifications'}"],
        )
        self.assertEqual(by_pointer["/common/waitingSince#fn0"]["source"], "just now")
        waiting = by_pointer["/common/waitingSince#fn1"]
        self.assertEqual(waiting["constraints"]["template_expressions"], ["${minutes}"])
        self.assertEqual(by_pointer["/common/branchOff#fn0"]["source"], "branch off ")
        self.assertNotIn("/common/bytes#fn0", by_pointer)  # identifier-only body: no text
        self.assertNotIn("/common/branchOff#fn1", by_pointer)  # empty string literal skipped

    def test_identity_round_trip_is_byte_identical(self) -> None:
        for fixture in ("basic.ts", "typed.ts", "functions.ts", "define-locale.ts"):
            source = FIXTURE_ROOT / fixture
            segments = extract_segments(source, "en", f"i18n/{fixture}")
            for segment in segments:
                segment["target"] = segment["source"]
                segment["target_locale"] = "fr"
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "fr.ts"
                rebuild(source, segments, output)
                self.assertEqual(output.read_bytes(), source.read_bytes(), fixture)
                result = validate_pair(source, output)
                self.assertEqual(result["status"], "pass", fixture)

    def test_rebuild_translated_strings_and_arrays(self) -> None:
        source = FIXTURE_ROOT / "basic.ts"
        segments = extract_segments(source, "en", "i18n/basic.ts")
        targets = {
            "/common/save": "Enregistrer",
            "/common/welcome": "Bonjour {name} !",
            "/common/weekdaysShort/0": "Dim",
            "/errors/retryCount": "Réessayer {count} fois",
        }
        for segment in segments:
            pointer = segment["context"]["pointer"]
            if pointer in targets:
                segment["target"] = targets[pointer]
                segment["target_locale"] = "fr"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fr.ts"
            rebuild(source, segments, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("save: 'Enregistrer',", text)
            self.assertIn('welcome: "Bonjour {name} !",', text)
            self.assertIn('"Dim"', text)
            self.assertIn("// Save button label", text)  # comments preserved
            result = validate_pair(source, output)
            self.assertEqual(result["status"], "pass")

    def test_rebuild_renames_export_to_target_locale(self) -> None:
        source = FIXTURE_ROOT / "typed.ts"
        segments = extract_segments(source, "en", "i18n/typed.ts")
        for segment in segments:
            segment["target"] = segment["source"]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fr.ts"
            rebuild(source, segments, output, export_name="fr")
            text = output.read_text(encoding="utf-8")
            self.assertIn("export const fr: Translations = {", text)
            self.assertNotIn("export const zh", text)
            catalog = parse_catalog(text)
            self.assertEqual(catalog.export_name, "fr")

    def test_rebuild_longer_export_name_keeps_literal_spans(self) -> None:
        source = FIXTURE_ROOT / "basic.ts"
        segments = extract_segments(source, "en", "i18n/basic.ts")
        targets = {
            "/common/save": "保存",
            "/common/welcome": "你好，{name}！",
            "/errors/retryCount": "再试 {count} 次",
        }
        for segment in segments:
            pointer = segment["context"]["pointer"]
            if pointer in targets:
                segment["target"] = targets[pointer]
                segment["target_locale"] = "zh-hant"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "zh-hant.ts"
            rebuild(source, segments, output, export_name="zhHant")
            text = output.read_text(encoding="utf-8")
            self.assertIn("export const zhHant = {", text)
            self.assertIn("save: '保存',", text)
            self.assertIn('welcome: "你好，{name}！",', text)
            self.assertIn("retryCount: '再试 {count} 次',", text)
            self.assertIn("// Save button label", text)  # comments untouched
            catalog = parse_catalog(text)
            self.assertEqual(catalog.export_name, "zhHant")
            self.assertEqual(catalog.duplicates, [])
            result = validate_pair(source, output)
            self.assertEqual(result["status"], "pass")

    def test_rebuild_shorter_export_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "en.ts"
            source.write_text(
                "export const english: Translations = {\n"
                "  common: {\n"
                "    save: 'Save',\n"
                "    welcome: 'Hello {name}',\n"
                "  },\n"
                "}\n",
                encoding="utf-8",
            )
            segments = extract_segments(source, "en", "i18n/english.ts")
            for segment in segments:
                if segment["context"]["pointer"] == "/common/save":
                    segment["target"] = "Enregistrer"
                elif segment["context"]["pointer"] == "/common/welcome":
                    segment["target"] = "Bonjour {name}"
            output = Path(directory) / "fr.ts"
            rebuild(source, segments, output, export_name="fr")
            text = output.read_text(encoding="utf-8")
            self.assertIn("export const fr: Translations = {", text)
            self.assertIn("save: 'Enregistrer',", text)
            self.assertIn("welcome: 'Bonjour {name}',", text)
            self.assertEqual(parse_catalog(text).export_name, "fr")
            result = validate_pair(source, output)
            self.assertEqual(result["status"], "pass")

    def test_invalid_export_identifiers_fail_closed(self) -> None:
        source = FIXTURE_ROOT / "basic.ts"
        segments = extract_segments(source, "en", "i18n/basic.ts")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fr.ts"
            for invalid in ("pt-BR", "123fr", "fr locale", "fr.ts"):
                with self.assertRaises(ValueError, msg=invalid):
                    rebuild(source, segments, output, export_name=invalid)

    def test_overlapping_edits_fail_closed(self) -> None:
        source = FIXTURE_ROOT / "basic.ts"
        segments = extract_segments(source, "en", "i18n/basic.ts")
        for segment in segments[:2]:
            segment["target"] = "Changed"
        segments[0]["context"]["value_start"] = 20
        segments[0]["context"]["value_end"] = 40
        segments[1]["context"]["value_start"] = 30
        segments[1]["context"]["value_end"] = 50
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fr.ts"
            with self.assertRaises(ValueError) as raised:
                rebuild(source, segments, output)
            self.assertIn("overlapping", str(raised.exception))

    def test_template_expression_order_change_is_blocking(self) -> None:
        source = FIXTURE_ROOT / "pager.ts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "fr.ts"
            target.write_text(
                source.read_text(encoding="utf-8").replace(
                    "${current} of ${total}", "${total} sur ${current}"
                ),
                encoding="utf-8",
            )
            result = validate_pair(source, target)
            self.assertEqual(result["status"], "fail")
            matches = [item for item in result["items"] if item["category"] == "template_expression_parity"]
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["severity"], "blocking")
            self.assertIn("${current}", matches[0]["message"])
            self.assertIn("${total}", matches[0]["message"])

    def test_template_expression_order_preserved_passes(self) -> None:
        source = FIXTURE_ROOT / "pager.ts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "fr.ts"
            target.write_text(
                source.read_text(encoding="utf-8").replace(
                    "${current} of ${total}", "Page ${current} sur ${total}"
                ),
                encoding="utf-8",
            )
            result = validate_pair(source, target)
            self.assertEqual(result["status"], "pass")

    def test_rebuild_preserves_function_signatures_and_expressions(self) -> None:
        source = FIXTURE_ROOT / "functions.ts"
        segments = extract_segments(source, "en", "i18n/functions.ts")
        for segment in segments:
            if segment["context"]["pointer"] == "/common/more#fn0":
                segment["target"] = "${count} autres ${count === 1 ? 'notification' : 'notifications'}"
            if segment["context"]["pointer"] == "/common/branchOff#fn0":
                segment["target"] = "embranchement "
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fr.ts"
            rebuild(source, segments, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("more: count => `${count} autres ${count === 1 ? 'notification' : 'notifications'}`,", text)
            self.assertIn("branchOff: () => ({ after: '', before: 'embranchement ' }),", text)
            self.assertIn("bytes: size => size,", text)
            result = validate_pair(source, output)
            self.assertEqual(result["status"], "pass")

    def test_placeholder_mismatch_fails(self) -> None:
        source = FIXTURE_ROOT / "basic.ts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "fr.ts"
            target.write_text(
                source.read_text(encoding="utf-8").replace("Hello {name}", "Hello {username}"),
                encoding="utf-8",
            )
            result = validate_pair(source, target)
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any(item["category"] == "placeholder_parity" for item in result["items"]))

    def test_template_expression_mismatch_fails(self) -> None:
        source = FIXTURE_ROOT / "functions.ts"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "fr.ts"
            target.write_text(
                source.read_text(encoding="utf-8").replace("${minutes}m ago", "${seconds}s ago"),
                encoding="utf-8",
            )
            result = validate_pair(source, target)
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any(item["category"] == "template_expression_parity" for item in result["items"]))

    def test_missing_and_unexpected_keys_fail(self) -> None:
        source = FIXTURE_ROOT / "basic.ts"
        text = source.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "fr.ts"
            target.write_text(
                text.replace("save: 'Save',", "extra: 'Extra',").replace("welcome:", "// welcome:"),
                encoding="utf-8",
            )
            result = validate_pair(source, target)
            self.assertEqual(result["status"], "fail")
            categories = {item["category"] for item in result["items"]}
            self.assertTrue({"key_coverage"} <= categories)

    def test_duplicate_keys_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dup.ts"
            path.write_text("export const en = { common: { save: 'a', save: 'b' } }\n", encoding="utf-8")
            with self.assertRaises(TSParseError):
                extract_segments(path, "en", "i18n/dup.ts")

    def test_unsupported_shape_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-a-catalog.ts"
            path.write_text("export class Foo {}\n", encoding="utf-8")
            with self.assertRaises(TSParseError):
                extract_segments(path, "en", "i18n/not-a-catalog.ts")

    def test_catalog_parse_duplicate_detection(self) -> None:
        text = "export const en = { a: { b: 'x', b: 'y' } }\n"
        catalog = parse_catalog(text)
        self.assertEqual(catalog.duplicates, ["/a/b"])


if __name__ == "__main__":
    unittest.main()
