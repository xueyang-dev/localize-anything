from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from runtime.localize_anything.android_strings_adapter import android_resource_routing
from runtime.localize_anything.android_strings_adapter import extract_segments as extract_android_segments
from runtime.localize_anything.android_strings_adapter import rebuild as rebuild_android_strings
from runtime.localize_anything.android_strings_adapter import stage_rebuild as stage_android_strings
from runtime.localize_anything.android_strings_adapter import target_resource_path
from runtime.localize_anything.android_strings_adapter import validate_cdata_target
from runtime.localize_anything.android_strings_adapter import validate_escape_signatures
from runtime.localize_anything.android_strings_adapter import validate_markup_signatures
from runtime.localize_anything.android_strings_adapter import validate_pair as validate_android_strings
from runtime.localize_anything.contracts import validate_adapter_tree
from runtime.localize_anything.gettext_adapter import extract_segments as extract_po_segments
from runtime.localize_anything.gettext_adapter import parse_po
from runtime.localize_anything.gettext_adapter import rebuild as rebuild_po
from runtime.localize_anything.gettext_adapter import validate_pair as validate_po_pair
from runtime.localize_anything.ios_strings_adapter import extract_segments as extract_ios_segments
from runtime.localize_anything.ios_strings_adapter import rebuild as rebuild_ios_strings
from runtime.localize_anything.ios_strings_adapter import stage_rebuild as stage_ios_strings
from runtime.localize_anything.ios_strings_adapter import target_resource_path as target_ios_resource_path
from runtime.localize_anything.ios_strings_adapter import validate_pair as validate_ios_strings
from runtime.localize_anything.json_adapter import extract_segments
from runtime.localize_anything.json_adapter import rebuild
from runtime.localize_anything.json_adapter import validate_pair
from runtime.localize_anything.markup_adapter import extract_segments as extract_markup_segments
from runtime.localize_anything.markup_adapter import rebuild as rebuild_markup
from runtime.localize_anything.markup_adapter import validate_pair as validate_markup_pair
from runtime.localize_anything.schema_validation import validate_protocol_tree
from runtime.localize_anything.structured_adapter import extract_segments as extract_structured_segments
from runtime.localize_anything.structured_adapter import rebuild as rebuild_structured
from runtime.localize_anything.structured_adapter import validate_pair as validate_structured_pair
from runtime.localize_anything.subtitle_adapter import extract_segments as extract_subtitle_segments
from runtime.localize_anything.subtitle_adapter import rebuild as rebuild_subtitles
from runtime.localize_anything.subtitle_adapter import validate_pair as validate_subtitle_pair
from runtime.localize_anything.tabular_adapter import extract_segments as extract_tabular_segments
from runtime.localize_anything.tabular_adapter import rebuild as rebuild_tabular
from runtime.localize_anything.tabular_adapter import validate_pair as validate_tabular_pair
from runtime.localize_anything.wesnoth_adapter import enrich_segments
from runtime.localize_anything.wesnoth_adapter import inventory as wesnoth_inventory
from runtime.localize_anything.wesnoth_adapter import validate_source
from runtime.localize_anything.word_adapter import extract_segments as extract_word_segments
from runtime.localize_anything.word_adapter import rebuild as rebuild_word
from runtime.localize_anything.word_adapter import validate_pair as validate_word_pair
from runtime.localize_anything.xcstrings_adapter import extract_segments as extract_xcstrings_segments
from runtime.localize_anything.xcstrings_adapter import rebuild as rebuild_xcstrings
from runtime.localize_anything.xcstrings_adapter import stage_rebuild as stage_xcstrings
from runtime.localize_anything.xcstrings_adapter import validate_pair as validate_xcstrings
from runtime.localize_anything.xliff_adapter import extract_segments as extract_xliff_segments
from runtime.localize_anything.xliff_adapter import rebuild as rebuild_xliff
from runtime.localize_anything.xliff_adapter import validate_pair as validate_xliff_pair

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "json-project"
GETTEXT_WESNOTH_ROOT = Path(__file__).parent / "fixtures" / "gettext-wesnoth"
COMMON_FORMATS_ROOT = Path(__file__).parent / "fixtures" / "common-formats"
ANDROID_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "android-project"
ANDROID_RELIABILITY_ROOT = Path(__file__).parent / "fixtures" / "android-reliability"
IOS_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ios-project"
XCSTRINGS_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "xcstrings-project"
REPOSITORY_ROOT = Path(__file__).parents[1]


class JsonAdapterTests(unittest.TestCase):

    def test_extract_rebuild_and_validate(self) -> None:
        source = FIXTURE_ROOT / 'locales' / 'en-US.json'
        expected = FIXTURE_ROOT / 'locales' / 'zh-CN.json'
        segments = extract_segments(source, 'en-US', 'locales/en-US.json')
        targets = {'/menu/start': '开始游戏', '/menu/welcome': '欢迎你，{player}！', '/inventory/coins': '你有 {{count}} 枚硬币。', '/inventory/weight': '重量：%s kg'}
        for segment in segments:
            segment['target_locale'] = 'zh-CN'
            segment['target'] = targets[segment['context']['json_pointer']]
            segment['status'] = 'generated'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'zh-CN.json'
            rebuild(source, segments, output)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8')), json.loads(expected.read_text(encoding='utf-8')))
            result = validate_pair(source, output)
            self.assertEqual(result['status'], 'pass')

    def test_placeholder_mismatch_fails(self) -> None:
        source = FIXTURE_ROOT / 'locales' / 'en-US.json'
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'broken.json'
            target.write_text(source.read_text(encoding='utf-8').replace('{player}', '{username}'), encoding='utf-8')
            result = validate_pair(source, target)
            self.assertEqual(result['status'], 'fail')
            self.assertTrue(any((item['category'] == 'placeholder_parity' for item in result['items'])))


class GettextAdapterTests(unittest.TestCase):

    def test_extract_rebuild_plural_and_validate(self) -> None:
        source = GETTEXT_WESNOTH_ROOT / 'messages.pot'
        logical_path = 'po/The_South_Guard.pot'
        segments = extract_po_segments(source, 'en-US', logical_path)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]['context']['msgctxt'], 'campaign-dialogue')
        self.assertEqual(segments[0]['constraints']['placeholders'], ['%s'])
        self.assertEqual(segments[1]['context']['source_plural'], '%d turns')
        segments[0]['target'] = '欢迎你，%s！'
        segments[0]['target_locale'] = 'zh-CN'
        segments[1]['target_plural'] = {'0': '%d 回合'}
        segments[1]['target_locale'] = 'zh-CN'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'zh-CN.po'
            rebuild_po(source, segments, output, 'zh-CN')
            target_document = parse_po(output)
            header = target_document.entries[0].msgstr_fields()[0].value
            self.assertIn('Language: zh_CN', header)
            self.assertIn('nplurals=1', header)
            plural = target_document.entries[2]
            self.assertEqual([(field.plural_index, field.value) for field in plural.msgstr_fields()], [(0, '%d 回合')])
            result = validate_po_pair(source, output)
            self.assertEqual(result['status'], 'pass', result['items'])

    def test_placeholder_mismatch_fails(self) -> None:
        source = GETTEXT_WESNOTH_ROOT / 'messages.pot'
        segments = extract_po_segments(source, 'en-US', 'messages.pot')
        segments[0]['target'] = '欢迎你！'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'broken.po'
            rebuild_po(source, segments, output, 'zh-CN')
            result = validate_po_pair(source, output)
            self.assertEqual(result['status'], 'fail')
            self.assertTrue(any((item['category'] == 'placeholder_parity' for item in result['items'])))


class WesnothAdapterTests(unittest.TestCase):

    def test_inventory_enrichment_and_context_validation(self) -> None:
        source = GETTEXT_WESNOTH_ROOT / 'messages.pot'
        segments = extract_po_segments(source, 'en-US', 'messages.pot')
        result = wesnoth_inventory(GETTEXT_WESNOTH_ROOT)
        self.assertEqual(len(result['scenario_files']), 1)
        self.assertEqual(result['pot_files'], ['messages.pot'])
        enriched = enrich_segments(segments, GETTEXT_WESNOTH_ROOT)
        opening = enriched[0]['context']
        self.assertEqual(opening['campaign'], 'The_South_Guard')
        self.assertEqual(opening['scenario'], '01_Born_to_the_Banner')
        self.assertEqual(opening['speaker'], 'Deoran')
        self.assertEqual(opening['content_type'], 'dialogue')
        self.assertEqual(validate_source(GETTEXT_WESNOTH_ROOT, segments)['status'], 'pass')


class StructuredAdapterTests(unittest.TestCase):

    def test_yaml_round_trip_and_placeholder_validation(self) -> None:
        source = COMMON_FORMATS_ROOT / 'messages.yaml'
        segments = extract_structured_segments(source, 'en-US', 'locales/messages.yaml')
        self.assertEqual(len(segments), 5)
        self.assertNotIn('12', [item['source'] for item in segments])
        targets = {'Start game': '开始游戏', 'Welcome, {player}!': '欢迎你，{player}！', 'Try again': '再试一次', 'Sword': '剑', 'Shield': '盾牌'}
        for segment in segments:
            segment['target'] = targets[segment['source']]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'messages.yaml'
            rebuild_structured(source, segments, output)
            self.assertIn('max_items: 12', output.read_text(encoding='utf-8'))
            self.assertIn('# Keep the player token.', output.read_text(encoding='utf-8'))
            self.assertEqual(validate_structured_pair(source, output)['status'], 'pass')

    def test_toml_round_trip_and_parse(self) -> None:
        source = COMMON_FORMATS_ROOT / 'messages.toml'
        segments = extract_structured_segments(source, 'en-US', 'locales/messages.toml')
        self.assertEqual(len(segments), 5)
        for segment in segments:
            segment['target'] = f"译文：{segment['source']}"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'messages.toml'
            rebuild_structured(source, segments, output)
            self.assertIn('max_items = 12', output.read_text(encoding='utf-8'))
            self.assertEqual(validate_structured_pair(source, output)['status'], 'pass')


class TabularAdapterTests(unittest.TestCase):

    def test_csv_and_tsv_round_trip(self) -> None:
        for name in ('messages.csv', 'messages.tsv'):
            with self.subTest(name=name):
                source = COMMON_FORMATS_ROOT / name
                segments = extract_tabular_segments(source, 'en-US', f'locales/{name}')
                self.assertTrue(segments)
                self.assertTrue(all((item['context']['column'] > 0 for item in segments)))
                for segment in segments:
                    segment['target'] = segment['source'].replace('Start game', '开始游戏').replace('Welcome, {player}!', '欢迎你，{player}！')
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / name
                    rebuild_tabular(source, segments, output)
                    self.assertEqual(validate_tabular_pair(source, output)['status'], 'pass')
                    text = output.read_text(encoding='utf-8')
                    output.write_text(text.replace('menu.start', 'menu.changed', 1), encoding='utf-8')
                    self.assertEqual(validate_tabular_pair(source, output)['status'], 'fail')

    def test_xlsx_shared_and_inline_strings_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'messages.xlsx'
            _write_minimal_xlsx(source)
            segments = extract_tabular_segments(source, 'en-US', 'locales/messages.xlsx')
            self.assertEqual({item['source'] for item in segments}, {'Start game', 'Welcome, {player}!'})
            for segment in segments:
                segment['target'] = {'Start game': '开始游戏', 'Welcome, {player}!': '欢迎你，{player}！'}[segment['source']]
            output = root / 'zh-CN.xlsx'
            rebuild_tabular(source, segments, output)
            self.assertEqual(validate_tabular_pair(source, output)['status'], 'pass')
            rebuilt = extract_tabular_segments(output, 'zh-CN', 'locales/messages.xlsx')
            self.assertEqual({item['source'] for item in rebuilt}, {'开始游戏', '欢迎你，{player}！'})


class MarkupAdapterTests(unittest.TestCase):

    def test_markdown_preserves_code_links_and_structure(self) -> None:
        source = COMMON_FORMATS_ROOT / 'guide.md'
        segments = extract_markup_segments(source, 'en-US', 'docs/guide.md')
        self.assertFalse(any(('Do not translate this code' in item['source'] for item in segments)))
        for segment in segments:
            segment['target'] = segment['source'].replace('Getting Started', '入门').replace('Welcome', '欢迎').replace('player guide', '玩家指南').replace('Choose', '选择').replace('Keep', '保持')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'guide.md'
            rebuild_markup(source, segments, output)
            text = output.read_text(encoding='utf-8')
            self.assertIn('print("Do not translate this code")', text)
            self.assertIn('https://example.com/guide', text)
            self.assertEqual(validate_markup_pair(source, output)['status'], 'pass')

    def test_html_preserves_tags_attributes_and_script(self) -> None:
        source = COMMON_FORMATS_ROOT / 'page.html'
        segments = extract_markup_segments(source, 'en-US', 'docs/page.html')
        self.assertFalse(any(('Do not translate' in item['source'] for item in segments)))
        for segment in segments:
            segment['target'] = segment['source'].replace('Game Guide', '游戏指南').replace('Welcome', '欢迎').replace('Choose a', '选择').replace('difficulty', '难度').replace('level', '级别').replace('begin', '开始')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'page.html'
            rebuild_markup(source, segments, output)
            self.assertIn('const message = "Do not translate"', output.read_text(encoding='utf-8'))
            self.assertEqual(validate_markup_pair(source, output)['status'], 'pass')


def _write_minimal_docx(path: Path, include_macro: bool=False, mixed_styles: bool=False) -> None:
    mixed = '\n    <w:p>\n      <w:r><w:rPr><w:b/></w:rPr><w:t>Bold text</w:t></w:r>\n      <w:r><w:rPr><w:i/></w:rPr><w:t>Italic text</w:t></w:r>\n    </w:p>\n' if mixed_styles else ''
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"\n  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n  <w:body>\n    <w:p><w:r><w:t>Hello, {{name}}!</w:t></w:r></w:p>\n    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table total: {{total}}</w:t></w:r></w:p></w:tc></w:tr></w:tbl>\n    <w:p><w:r><w:drawing><w:txbxContent><w:p><w:r><w:t>Box text</w:t></w:r></w:p></w:txbxContent></w:drawing></w:r></w:p>\n    {mixed}\n  </w:body>\n</w:document>\n'
    header = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n  <w:p><w:r><w:t>Header title</w:t></w:r></w:p>\n</w:hdr>\n'
    footer = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n  <w:p><w:r><w:t>Footer note</w:t></w:r></w:p>\n</w:ftr>\n'
    footnotes = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n  <w:footnote w:id="1"><w:p><w:r><w:t>Footnote body</w:t></w:r></w:p></w:footnote>\n</w:footnotes>\n'
    comments = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n  <w:comment w:id="0"><w:p><w:r><w:t>Reviewer comment</w:t></w:r></w:p></w:comment>\n</w:comments>\n'
    chart = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"\n  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">\n  <c:chart><c:title><c:tx><c:rich><a:p><a:r><a:t>Chart title</a:t></a:r></a:p></c:rich></c:tx></c:title></c:chart>\n</c:chartSpace>\n'
    styles = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n  <w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>\n</w:styles>\n'
    rels = '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>\n</Relationships>\n'
    document_rels = '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  <Relationship Id="rIdHeader" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>\n  <Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>\n</Relationships>\n'
    content_types = '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n  <Default Extension="xml" ContentType="application/xml"/>\n  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n  <Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/>\n</Types>\n'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', content_types)
        archive.writestr('_rels/.rels', rels)
        archive.writestr('word/document.xml', document)
        archive.writestr('word/_rels/document.xml.rels', document_rels)
        archive.writestr('word/header1.xml', header)
        archive.writestr('word/footer1.xml', footer)
        archive.writestr('word/footnotes.xml', footnotes)
        archive.writestr('word/comments.xml', comments)
        archive.writestr('word/charts/chart1.xml', chart)
        archive.writestr('word/styles.xml', styles)
        if include_macro:
            archive.writestr('word/vbaProject.bin', b'fake-vba-project')


def _write_minimal_xlsx(path: Path) -> None:
    shared = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="6" uniqueCount="5">\n  <si><t>key</t></si>\n  <si><t>text</t></si>\n  <si><t>menu.start</t></si>\n  <si><t>Start game</t></si>\n  <si><t>menu.welcome</t></si>\n</sst>\n'
    sheet = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">\n  <sheetData>\n    <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>3</v></c></row>\n    <row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="s"><v>3</v></c></row>\n    <row r="3"><c r="A3" t="s"><v>4</v></c><c r="B3" t="inlineStr"><is><t>Welcome, {player}!</t></is></c></row>\n  </sheetData>\n</worksheet>\n'
    content_types = '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n  <Default Extension="xml" ContentType="application/xml"/>\n</Types>\n'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', content_types)
        archive.writestr('xl/sharedStrings.xml', shared)
        archive.writestr('xl/worksheets/sheet1.xml', sheet)


class WordDocumentAdapterTests(unittest.TestCase):

    def test_docx_extract_rebuild_and_validate_visible_parts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'report.docx'
            _write_minimal_docx(source)
            segments = extract_word_segments(source, 'en-US', 'docs/report.docx')
            self.assertTrue({'Hello, {name}!', 'Table total: {total}', 'Header title', 'Footer note', 'Footnote body', 'Reviewer comment', 'Box text', 'Chart title'}.issubset({segment['source'] for segment in segments}))
            for segment in segments:
                segment['target_locale'] = 'zh-CN'
                segment['target'] = f"[zh-CN] {segment['source']}"
                segment['status'] = 'generated'
            output = root / 'report.zh-CN.docx'
            rebuild_word(source, segments, output)
            self.assertEqual(validate_word_pair(source, output)['status'], 'pass')
            rebuilt = extract_word_segments(output, 'zh-CN', 'docs/report.docx')
            self.assertIn('[zh-CN] Hello, {name}!', {segment['source'] for segment in rebuilt})
            with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
                self.assertEqual(before.read('word/styles.xml'), after.read('word/styles.xml'))
                self.assertEqual(before.read('word/_rels/document.xml.rels'), after.read('word/_rels/document.xml.rels'))
                document = ElementTree.fromstring(after.read('word/document.xml'))
                w_ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
                fonts = document.findall(f'.//{{{w_ns}}}rFonts')
                self.assertTrue(fonts)
                self.assertTrue(all((font.get(f'{{{w_ns}}}{name}') == 'Microsoft YaHei' for font in fonts for name in ('ascii', 'hAnsi', 'eastAsia', 'cs'))))

    def test_rebuild_applies_english_font_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'report.docx'
            _write_minimal_docx(source)
            segments = extract_word_segments(source, 'zh-CN', 'docs/report.docx')
            for segment in segments:
                segment['target_locale'] = 'en-US'
                segment['target'] = f"[en-US] {segment['source']}"
                segment['status'] = 'generated'
            output = root / 'report.en-US.docx'
            rebuild_word(source, segments, output)
            self.assertEqual(validate_word_pair(source, output)['status'], 'pass')
            with zipfile.ZipFile(output) as archive:
                document = ElementTree.fromstring(archive.read('word/document.xml'))
                w_ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
                fonts = document.findall(f'.//{{{w_ns}}}rFonts')
                self.assertTrue(fonts)
                self.assertTrue(all((font.get(f'{{{w_ns}}}{name}') == 'Arial' for font in fonts for name in ('ascii', 'hAnsi', 'eastAsia', 'cs'))))
                chart = ElementTree.fromstring(archive.read('word/charts/chart1.xml'))
                a_ns = 'http://schemas.openxmlformats.org/drawingml/2006/main'
                typefaces = {node.get('typeface') for node in chart.findall(f'.//{{{a_ns}}}latin')}
                self.assertEqual(typefaces, {'Arial'})

    def test_mixed_style_runs_are_split_and_styles_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'mixed.docx'
            _write_minimal_docx(source, mixed_styles=True)
            segments = extract_word_segments(source, 'en-US', 'docs/mixed.docx')
            by_source = {segment['source']: segment for segment in segments}
            self.assertIn('Bold text', by_source)
            self.assertIn('Italic text', by_source)
            for segment in segments:
                segment['target_locale'] = 'zh-CN'
                segment['target'] = f"[zh-CN] {segment['source']}"
                segment['status'] = 'generated'
            output = root / 'mixed.zh-CN.docx'
            rebuild_word(source, segments, output)
            self.assertEqual(validate_word_pair(source, output)['status'], 'pass')

    def test_docm_macro_bytes_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'macro.docm'
            _write_minimal_docx(source, include_macro=True)
            segments = extract_word_segments(source, 'en-US', 'docs/macro.docm')
            for segment in segments:
                segment['target_locale'] = 'zh-CN'
                segment['target'] = f"[zh-CN] {segment['source']}"
                segment['status'] = 'generated'
            output = root / 'macro.zh-CN.docm'
            rebuild_word(source, segments, output)
            with zipfile.ZipFile(source) as before, zipfile.ZipFile(output) as after:
                self.assertEqual(before.read('word/vbaProject.bin'), after.read('word/vbaProject.bin'))
            self.assertEqual(validate_word_pair(source, output)['status'], 'pass')


class SubtitleAdapterTests(unittest.TestCase):

    def test_srt_and_vtt_preserve_timing_and_markup(self) -> None:
        for name in ('captions.srt', 'captions.vtt'):
            with self.subTest(name=name):
                source = COMMON_FORMATS_ROOT / name
                segments = extract_subtitle_segments(source, 'en-US', f'subtitles/{name}')
                self.assertEqual(len(segments), 2)
                segments[0]['target'] = '欢迎，<i>{player}</i>！'
                segments[1]['target'] = '旅程开始了。'
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / name
                    rebuild_subtitles(source, segments, output)
                    self.assertEqual(validate_subtitle_pair(source, output)['status'], 'pass')
                    self.assertIn(segments[0]['context']['timing'], output.read_text(encoding='utf-8'))


class XliffAdapterTests(unittest.TestCase):

    def test_xliff_12_and_20_round_trip(self) -> None:
        for name in ('messages.xlf', 'messages-2.xlf'):
            with self.subTest(name=name):
                source = COMMON_FORMATS_ROOT / name
                segments = extract_xliff_segments(source, 'en-US', f'locales/{name}')
                self.assertEqual(len(segments), 2)
                for segment in segments:
                    segment['target'] = segment['source'].replace('Welcome', '欢迎').replace('Start game', '开始游戏').replace('Quit game', '退出游戏')
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / name
                    rebuild_xliff(source, segments, output, 'zh-CN')
                    self.assertEqual(validate_xliff_pair(source, output)['status'], 'pass')
                    rebuilt = extract_xliff_segments(output, 'en-US', f'locales/{name}')
                    self.assertTrue(all((item.get('existing_target') for item in rebuilt)))


class AndroidStringsAdapterTests(unittest.TestCase):

    def test_extract_rebuild_stage_and_validate_android_strings(self) -> None:
        source = ANDROID_FIXTURE_ROOT / 'app' / 'src' / 'main' / 'res' / 'values' / 'strings.xml'
        logical_path = 'app/src/main/res/values/strings.xml'
        segments = extract_android_segments(source, 'en-US', logical_path)
        self.assertEqual({item['source'] for item in segments}, {'Sample App', 'Welcome, %1$s!', 'You have %d coins.', 'Battery at 100%', 'Home', 'Settings', '%d message', '%d messages'})
        self.assertEqual(len(segments), 8)
        self.assertEqual(next((item for item in segments if item['source'] == 'Home'))['context']['resource_type'], 'string-array')
        self.assertEqual(next((item for item in segments if item['source'] == '%d message'))['context']['resource_type'], 'plurals')
        self.assertEqual(next((item for item in segments if item['source'] == 'Welcome, %1$s!'))['constraints']['placeholders'], ['%1$s'])
        self.assertEqual(next((item for item in segments if item['source'] == 'Battery at 100%'))['constraints']['placeholders'], [])
        for segment in segments:
            segment['target_locale'] = 'zh-CN'
            segment['target'] = {'Sample App': '示例应用', 'Welcome, %1$s!': '欢迎，%1$s！', 'You have %d coins.': '你有 %d 枚金币。', 'Battery at 100%': '电量 100%', 'Home': '首页', 'Settings': '设置', '%d message': '%d 条消息', '%d messages': '%d 条消息'}[segment['source']]
            segment['status'] = 'generated'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'strings.xml'
            rebuild_android_strings(source, segments, output)
            text = output.read_text(encoding='utf-8')
            self.assertIn('name="app_name"', text)
            self.assertIn('示例应用', text)
            self.assertIn('<string-array', text)
            self.assertIn('<plurals', text)
            self.assertNotIn('debug_token', text)
            result = validate_android_strings(source, output)
            self.assertEqual(result['status'], 'pass', result['items'])
            self.assertTrue(any((item['category'] == 'unsupported_or_skipped_resource' for item in result['items'])))
            self.assertEqual(target_resource_path(source, 'zh-CN', ANDROID_FIXTURE_ROOT).as_posix(), 'app/src/main/res/values-zh-rCN/strings.xml')
            staged = stage_android_strings(source, segments, root / 'staging', 'zh-CN', ANDROID_FIXTURE_ROOT)
            staged_path = root / 'staging' / 'app' / 'src' / 'main' / 'res' / 'values-zh-rCN' / 'strings.xml'
            self.assertEqual(staged['destination'], 'app/src/main/res/values-zh-rCN/strings.xml')
            self.assertTrue(staged_path.is_file())
            self.assertEqual(validate_android_strings(source, staged_path)['status'], 'pass')

    def test_android_qualifier_target_path_mapping(self) -> None:
        expected = {'app/src/main/res/values/strings.xml': 'app/src/main/res/values-zh-rCN/strings.xml', 'app/src/main/res/values-night/strings.xml': 'app/src/main/res/values-zh-rCN-night/strings.xml', 'app/src/main/res/values-land/strings.xml': 'app/src/main/res/values-zh-rCN-land/strings.xml', 'app/src/main/res/values-sw600dp/strings.xml': 'app/src/main/res/values-zh-rCN-sw600dp/strings.xml', 'app/src/main/res/values-mcc310/strings.xml': 'app/src/main/res/values-mcc310-zh-rCN/strings.xml', 'app/src/main/res/values-mcc310-mnc004/strings.xml': 'app/src/main/res/values-mcc310-mnc004-zh-rCN/strings.xml', 'app/src/main/res/values-mcc310-night/strings.xml': 'app/src/main/res/values-mcc310-zh-rCN-night/strings.xml', 'app/src/main/res/values-mcc310-mnc004-land/strings.xml': 'app/src/main/res/values-mcc310-mnc004-zh-rCN-land/strings.xml', 'app/src/debug/res/values/strings.xml': 'app/src/debug/res/values-zh-rCN/strings.xml', 'app/src/free/res/values/strings.xml': 'app/src/free/res/values-zh-rCN/strings.xml'}
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            for source_file, target_file in expected.items():
                with self.subTest(source_file=source_file):
                    source = project / source_file
                    source.parent.mkdir(parents=True, exist_ok=True)
                    source.write_text('<resources><string name="value">Value</string></resources>', encoding='utf-8')
                    routing = android_resource_routing(source, project, 'zh-CN')
                    self.assertEqual(target_resource_path(source, 'zh-CN', project).as_posix(), target_file)
                    self.assertEqual(routing['target_resource_path'], target_file)
                    self.assertEqual(routing['warnings'], [])
                    segments = extract_android_segments(source, 'en-US', source_file)
                    self.assertTrue(all((segment['context']['android_source_set'] in {'main', 'debug', 'free'} for segment in segments)))
            locale_reference = project / 'app/src/main/res/values-zh-rCN/strings.xml'
            self.assertEqual(android_resource_routing(locale_reference, project)['android_role'], 'locale_reference')
            with self.assertRaises(ValueError):
                target_resource_path(locale_reference, 'zh-CN', project)
        invalid_order = Path('app/src/main/res/values-zh-rCN-mcc310/strings.xml')
        invalid_routing = android_resource_routing(invalid_order, target_locale='zh-CN')
        self.assertEqual(invalid_routing['android_role'], 'locale_reference')
        self.assertTrue(invalid_routing['warnings'])
        self.assertIsNone(invalid_routing['target_resource_path'])
        with self.assertRaises(ValueError):
            target_resource_path(invalid_order, 'zh-CN')
        unknown_order = Path('app/src/main/res/values-night-land/strings.xml')
        unknown_routing = android_resource_routing(unknown_order, target_locale='zh-CN')
        self.assertEqual(unknown_routing['android_role'], 'owner_review_required')
        self.assertTrue(unknown_routing['warnings'])
        with self.assertRaises(ValueError):
            target_resource_path(unknown_order, 'zh-CN')

    def test_android_staging_preserves_target_only_resources_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / 'project'
            shutil.copytree(ANDROID_FIXTURE_ROOT, project)
            source = project / 'app' / 'src' / 'main' / 'res' / 'values' / 'strings.xml'
            target = project / 'app' / 'src' / 'main' / 'res' / 'values-zh-rCN' / 'strings.xml'
            target.parent.mkdir(parents=True)
            target.write_text('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <string name="legacy_removed_key">旧版专属译文_不得自动删除</string>\n</resources>\n', encoding='utf-8')
            segments = extract_android_segments(source, 'en-US', 'app/src/main/res/values/strings.xml')
            for segment in segments:
                segment['target_locale'] = 'zh-CN'
                segment['target'] = segment['source']
                segment['status'] = 'generated'
            stage_android_strings(source, segments, root / 'staging', 'zh-CN', project, preserve_target_only=True)
            staged = root / 'staging' / 'app' / 'src' / 'main' / 'res' / 'values-zh-rCN' / 'strings.xml'
            text = staged.read_text(encoding='utf-8')
            self.assertIn('name="legacy_removed_key"', text)
            self.assertIn('旧版专属译文_不得自动删除', text)
            self.assertEqual(validate_android_strings(source, staged)['status'], 'pass_with_warnings')

    def test_android_escape_signature_extraction(self) -> None:
        source = ANDROID_RELIABILITY_ROOT / 'app' / 'src' / 'main' / 'res' / 'values' / 'strings.xml'
        segments = extract_android_segments(source, 'en-US', 'app/src/main/res/values/strings.xml')
        by_key = {segment['context']['resource_key']: segment for segment in segments}
        self.assertEqual(by_key['string:cant_sync']['constraints']['escape_signature'], ["\\'", '"'])
        self.assertEqual(by_key['string:multiline_help']['constraints']['escape_signature'], ['\\n', '\\t'])
        self.assertEqual(by_key['string:delete_files']['constraints']['placeholders'], ['%1$d', '%2$d'])
        self.assertEqual(by_key['string:delete_files']['constraints']['escape_signature'], ['%%'])
        self.assertNotIn('%%', by_key['string:delete_files']['constraints']['placeholders'])

    def test_android_inline_markup_signature_extraction(self) -> None:
        source = ANDROID_RELIABILITY_ROOT / 'app' / 'src' / 'main' / 'res' / 'values' / 'strings.xml'
        segments = extract_android_segments(source, 'en-US', 'app/src/main/res/values/strings.xml')
        by_key = {segment['context']['resource_key']: segment for segment in segments}
        self.assertEqual(by_key['string:learn_more']['source'], 'Tap <b>Learn more</b> to continue.')
        self.assertEqual([item['tag'] for item in by_key['string:learn_more']['constraints']['markup_signature']], ['b'])
        self.assertEqual([item['tag'] for item in by_key['string:formatting_example']['constraints']['markup_signature']], ['i', 'u'])
        self.assertIn('string:unsupported_link', by_key)

    def test_android_complex_markup_detected_as_owner_review_required(self) -> None:
        source = ANDROID_RELIABILITY_ROOT / 'app' / 'src' / 'main' / 'res' / 'values' / 'strings.xml'
        segments = extract_android_segments(source, 'en-US', 'app/src/main/res/values/strings.xml')
        by_key = {segment['context']['resource_key']: segment for segment in segments}
        expected = {'string:nested_markup': 'complex_nested_markup', 'string:font_markup': 'unsupported_markup_tag', 'string:styled_bold': 'unsupported_markup_attribute', 'string:complex_link': 'unsupported_markup_attribute'}
        for key, category in expected.items():
            with self.subTest(key=key):
                segment = by_key[key]
                self.assertTrue(segment['owner_review_required'])
                self.assertFalse(segment['generation_eligible'])
                self.assertEqual(segment['status'], 'new')
                self.assertEqual(segment['workflow_status'], 'owner_review_required')
                self.assertIn(category, segment['review_required_reasons'])
                self.assertEqual(segment['constraints']['markup_signature'], [])

    def test_android_cdata_signature_extraction(self) -> None:
        source = ANDROID_RELIABILITY_ROOT / 'app' / 'src' / 'main' / 'res' / 'values' / 'strings.xml'
        segments = extract_android_segments(source, 'en-US', 'app/src/main/res/values/strings.xml')
        by_key = {segment['context']['resource_key']: segment for segment in segments}
        self.assertTrue(by_key['string:html_cdata']['constraints']['cdata'])
        self.assertTrue(by_key['string:plain_cdata']['constraints']['cdata'])
        self.assertTrue(by_key['string:html_cdata']['cdata'])
        self.assertEqual(by_key['string:html_cdata']['markup_signature'], [])
        self.assertEqual(by_key['string:plain_cdata']['source'], 'Use < and > safely in this message.')
        self.assertEqual(by_key['string:html_cdata']['cdata_signature'], {'boundary': 'cdata', 'original_had_cdata': True})

    def test_android_cdata_boundary_preserved_in_staging(self) -> None:
        project = ANDROID_RELIABILITY_ROOT
        source = project / 'app' / 'src' / 'main' / 'res' / 'values' / 'strings.xml'
        segments = extract_android_segments(source, 'en-US', 'app/src/main/res/values/strings.xml')
        for segment in segments:
            segment['target_locale'] = 'zh-CN'
            segment['target'] = segment['source']
            segment['status'] = 'generated'
        with tempfile.TemporaryDirectory() as directory:
            staged = stage_android_strings(source, segments, Path(directory), 'zh-CN', project)
            staged_path = Path(staged['output'])
            text = staged_path.read_text(encoding='utf-8')
            self.assertIn('<string name="html_cdata"><![CDATA[Tap <b>Learn more</b> to continue.]]></string>', text)
            self.assertIn('<string name="plain_cdata"><![CDATA[Use < and > safely in this message.]]></string>', text)
            result = validate_android_strings(source, staged_path)
            self.assertNotIn('cdata_boundary_missing', {item['category'] for item in result['items']})

    def test_android_resource_comment_metadata_extraction(self) -> None:
        source = ANDROID_RELIABILITY_ROOT / 'app' / 'src' / 'main' / 'res' / 'values' / 'strings.xml'
        segments = extract_android_segments(source, 'en-US', 'app/src/main/res/values/strings.xml')
        by_key = {segment['context']['resource_key']: segment for segment in segments}
        self.assertEqual(by_key['string:settings_title']['context']['resource_comment'], 'Settings screen')
        self.assertEqual(by_key['string-array:sort_options[0]']['context']['resource_comment'], 'Sort options shown in the queue screen')
        self.assertEqual(by_key['plurals:episode_count#one']['context']['resource_comment'], 'Number of downloaded episodes')
        self.assertFalse(any((segment['source'] == 'Settings screen' for segment in segments)))

    def test_android_resource_comments_round_trip_in_staging(self) -> None:
        project = ANDROID_RELIABILITY_ROOT
        source = project / 'app' / 'src' / 'main' / 'res' / 'values' / 'strings.xml'
        segments = extract_android_segments(source, 'en-US', 'app/src/main/res/values/strings.xml')
        for segment in segments:
            segment['target_locale'] = 'zh-CN'
            segment['target'] = segment['source']
            segment['status'] = 'generated'
        with tempfile.TemporaryDirectory() as directory:
            staged = stage_android_strings(source, segments, Path(directory), 'zh-CN', project, preserve_target_only=True)
            staged_path = Path(staged['output'])
            text = staged_path.read_text(encoding='utf-8')
            self.assertLess(text.index('<!-- Settings screen -->'), text.index('name="settings_title"'))
            self.assertLess(text.index('<!-- Sort options shown in the queue screen -->'), text.index('name="sort_options"'))
            self.assertLess(text.index('<!-- Number of downloaded episodes -->'), text.index('name="episode_count"'))
            self.assertLess(text.index('<!-- Legacy removed key preserved for owner review -->'), text.index('name="legacy_removed_key"'))
            result = validate_android_strings(source, staged_path)
            categories = {item['category'] for item in result['items']}
            self.assertNotIn('comment_missing', categories)
            self.assertNotIn('comment_misattached', categories)

    def test_android_comment_drift_validation(self) -> None:
        project = ANDROID_RELIABILITY_ROOT
        source = project / 'app' / 'src' / 'main' / 'res' / 'values' / 'strings.xml'
        segments = extract_android_segments(source, 'en-US', 'app/src/main/res/values/strings.xml')
        for segment in segments:
            segment['target_locale'] = 'zh-CN'
            segment['target'] = segment['source']
            segment['status'] = 'generated'
        with tempfile.TemporaryDirectory() as directory:
            staged = stage_android_strings(source, segments, Path(directory), 'zh-CN', project)
            staged_path = Path(staged['output'])
            text = staged_path.read_text(encoding='utf-8')
            missing = Path(directory) / 'missing-comment.xml'
            missing.write_text(text.replace('    <!-- Settings screen -->\n', '', 1), encoding='utf-8')
            missing_result = validate_android_strings(source, missing)
            self.assertIn('comment_missing', {item['category'] for item in missing_result['items']})
            misattached = Path(directory) / 'misattached-comment.xml'
            moved = text.replace('    <!-- Settings screen -->\n', '', 1)
            moved = moved.replace('    <string name="app_name"', '    <!-- Settings screen -->\n    <string name="app_name"', 1)
            misattached.write_text(moved, encoding='utf-8')
            misattached_result = validate_android_strings(source, misattached)
            self.assertIn('comment_misattached', {item['category'] for item in misattached_result['items']})

    def test_placeholder_mismatch_fails_android_strings(self) -> None:
        source = ANDROID_FIXTURE_ROOT / 'app' / 'src' / 'main' / 'res' / 'values' / 'strings.xml'
        segments = extract_android_segments(source, 'en-US', 'app/src/main/res/values/strings.xml')
        for segment in segments:
            segment['target'] = '缺少占位符' if segment['source'] == 'Welcome, %1$s!' else segment['source']
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'strings.xml'
            rebuild_android_strings(source, segments, output)
            result = validate_android_strings(source, output)
            self.assertEqual(result['status'], 'fail')
            self.assertTrue(any((item['category'] == 'placeholder_parity' for item in result['items'])))


class AndroidSafetyValidationTests(unittest.TestCase):
    def test_escape_markup_and_cdata_regressions_are_detected(self) -> None:
        escape_categories = {
            item["category"]
            for item in validate_escape_signatures(r"Line one\nLine two", "Line one Line two")
        }
        self.assertIn("escape_missing", escape_categories)

        markup_categories = {
            item["category"]
            for item in validate_markup_signatures(
                "Tap <b>Learn more</b>",
                "Tap Learn more",
                [{"kind": "pair", "tag": "b"}],
            )
        }
        self.assertIn("markup_missing", markup_categories)

        cdata_categories = {
            item["category"] for item in validate_cdata_target("unsafe ]]> text")
        }
        self.assertEqual(cdata_categories, {"cdata_terminator_unsafe"})


class IOSStringsAdapterTests(unittest.TestCase):

    def test_extract_rebuild_stage_and_validate_strings(self) -> None:
        source = IOS_FIXTURE_ROOT / 'App' / 'en.lproj' / 'Localizable.strings'
        logical_path = 'App/en.lproj/Localizable.strings'
        segments = extract_ios_segments(source, 'en-US', logical_path)
        self.assertEqual({item['source'] for item in segments}, {'Sample App', 'Welcome, %@!', 'You have %d coins.', 'Tap "Continue"', 'Battery at 100%'})
        self.assertEqual(len(segments), 5)
        self.assertEqual(next((item for item in segments if item['source'] == 'Welcome, %@!'))['constraints']['placeholders'], ['%@'])
        self.assertEqual(next((item for item in segments if item['source'] == 'Battery at 100%'))['constraints']['placeholders'], [])
        for segment in segments:
            segment['target_locale'] = 'zh-CN'
            segment['target'] = {'Sample App': '示例应用', 'Welcome, %@!': '欢迎，%@！', 'You have %d coins.': '你有 %d 枚金币。', 'Tap "Continue"': '点按"继续"', 'Battery at 100%': '电量 100%'}[segment['source']]
            segment['status'] = 'generated'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'Localizable.strings'
            rebuild_ios_strings(source, segments, output)
            text = output.read_text(encoding='utf-8')
            self.assertIn('/* Main screen */', text)
            self.assertIn('"welcome.message" = "欢迎，%@！";', text)
            result = validate_ios_strings(source, output)
            self.assertEqual(result['status'], 'pass', result['items'])
            staged = stage_ios_strings(source, segments, root / 'staging', 'zh-CN', IOS_FIXTURE_ROOT)
            staged_path = root / 'staging' / 'App' / 'zh-Hans.lproj' / 'Localizable.strings'
            self.assertEqual(staged['destination'], 'App/zh-Hans.lproj/Localizable.strings')
            self.assertTrue(staged_path.is_file())
            self.assertEqual(validate_ios_strings(source, staged_path)['status'], 'pass')
            self.assertEqual(target_ios_resource_path(source, 'zh-TW', IOS_FIXTURE_ROOT).as_posix(), 'App/zh-Hant.lproj/Localizable.strings')

    def test_stringsdict_plural_round_trip(self) -> None:
        source = IOS_FIXTURE_ROOT / 'App' / 'en.lproj' / 'Localizable.stringsdict'
        logical_path = 'App/en.lproj/Localizable.stringsdict'
        segments = extract_ios_segments(source, 'en-US', logical_path)
        self.assertEqual({item['source'] for item in segments}, {'%d file', '%d files'})
        self.assertEqual(len(segments), 2)
        self.assertTrue(all((item['context']['file_format'] == 'stringsdict' for item in segments)))
        for segment in segments:
            segment['target_locale'] = 'zh-CN'
            segment['target'] = '%d 个文件'
            segment['status'] = 'generated'
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'Localizable.stringsdict'
            rebuild_ios_strings(source, segments, output)
            result = validate_ios_strings(source, output)
            self.assertEqual(result['status'], 'pass', result['items'])

    def test_placeholder_mismatch_fails_ios_strings(self) -> None:
        source = IOS_FIXTURE_ROOT / 'App' / 'en.lproj' / 'Localizable.strings'
        segments = extract_ios_segments(source, 'en-US', 'App/en.lproj/Localizable.strings')
        for segment in segments:
            segment['target'] = '缺少占位符' if segment['source'] == 'Welcome, %@!' else segment['source']
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'Localizable.strings'
            rebuild_ios_strings(source, segments, output)
            result = validate_ios_strings(source, output)
            self.assertEqual(result['status'], 'fail')
            self.assertTrue(any((item['category'] == 'placeholder_parity' for item in result['items'])))


class XCStringsAdapterTests(unittest.TestCase):

    def test_extract_rebuild_stage_and_validate_catalog(self) -> None:
        source = XCSTRINGS_FIXTURE_ROOT / 'App' / 'Localizable.xcstrings'
        logical_path = 'App/Localizable.xcstrings'
        segments = extract_xcstrings_segments(source, 'en-US', logical_path)
        self.assertEqual({item['source'] for item in segments}, {'Sample App', 'Settings', 'Welcome, %@!', '%lld file', '%lld files'})
        self.assertEqual(len(segments), 5)
        self.assertEqual(next((item for item in segments if item['source'] == 'Settings'))['context']['resource_type'], 'stringUnit')
        self.assertEqual(next((item for item in segments if item['source'] == '%lld file'))['context']['resource_type'], 'variation')
        self.assertEqual(next((item for item in segments if item['source'] == '%lld file'))['constraints']['placeholders'], ['%lld'])
        for segment in segments:
            segment['target_locale'] = 'zh-CN'
            segment['target'] = {'Sample App': '示例应用', 'Settings': '设置', 'Welcome, %@!': '欢迎，%@！', '%lld file': '%lld 个文件', '%lld files': '%lld 个文件'}[segment['source']]
            segment['status'] = 'generated'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'Localizable.xcstrings'
            rebuild_xcstrings(source, segments, output, 'zh-CN')
            text = output.read_text(encoding='utf-8')
            self.assertIn('"zh-Hans"', text)
            self.assertIn('"value": "欢迎，%@！"', text)
            result = validate_xcstrings(source, output, 'zh-CN')
            self.assertEqual(result['status'], 'pass', result['items'])
            staged = stage_xcstrings(source, segments, root / 'staging', 'zh-CN', XCSTRINGS_FIXTURE_ROOT)
            staged_path = root / 'staging' / 'App' / 'Localizable.xcstrings'
            self.assertEqual(staged['destination'], 'App/Localizable.xcstrings')
            self.assertTrue(staged_path.is_file())
            self.assertEqual(validate_xcstrings(source, staged_path, 'zh-CN')['status'], 'pass')

    def test_placeholder_mismatch_fails_xcstrings(self) -> None:
        source = XCSTRINGS_FIXTURE_ROOT / 'App' / 'Localizable.xcstrings'
        segments = extract_xcstrings_segments(source, 'en-US', 'App/Localizable.xcstrings')
        for segment in segments:
            segment['target_locale'] = 'zh-CN'
            segment['target'] = '缺少占位符' if segment['source'] == 'Welcome, %@!' else segment['source']
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'Localizable.xcstrings'
            rebuild_xcstrings(source, segments, output, 'zh-CN')
            result = validate_xcstrings(source, output, 'zh-CN')
            self.assertEqual(result['status'], 'fail')
            self.assertTrue(any((item['category'] == 'placeholder_parity' for item in result['items'])))


class AndroidRiskClassificationTests(unittest.TestCase):
    """Android UI-role and high-risk context classification baseline."""

    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def _write_fixture(self, content: str) -> Path:
        res_dir = self.temp / 'res' / 'values'
        res_dir.mkdir(parents=True)
        path = res_dir / 'strings.xml'
        path.write_text(content, encoding='utf-8')
        return path

    def _extract(self, path: Path) -> list[dict[str, Any]]:
        from runtime.localize_anything.android_strings_adapter import extract_segments
        return extract_segments(path, 'en-US', 'res/values/strings.xml')

    def test_android_ui_risk_classification_destructive_action(self) -> None:
        content = '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <!-- Destructive account action -->\n    <string name="delete_account_button">Delete account</string>\n    <string name="delete_account_warning">This action cannot be undone.</string>\n    <string name="confirm_remove_device">Remove this device</string>\n</resources>'
        path = self._write_fixture(content)
        segments = self._extract(path)
        by_key = {s['context']['resource_key']: s for s in segments}
        seg = by_key['string:delete_account_button']
        self.assertIn('destructive_action', seg['ui_risk_classification']['ui_role'])
        self.assertEqual(seg['ui_risk_classification']['risk_level'], 'critical')
        self.assertEqual(seg['ui_risk_classification']['review_priority'], 'owner_review_required')
        self.assertTrue(len(seg['ui_risk_classification']['classification_evidence']) > 0)
        self.assertIn('resource_name_pattern', seg['ui_risk_classification']['classification_evidence'])
        self.assertIn('source_text_pattern', seg['ui_risk_classification']['classification_evidence'])
        self.assertNotIn('placeholder_or_markup_protected', seg['ui_risk_classification']['classification_evidence'])
        seg2 = by_key['string:delete_account_warning']
        self.assertIn('destructive_action', seg2['ui_risk_classification']['ui_role'])
        self.assertEqual(seg2['ui_risk_classification']['risk_level'], 'high')
        seg3 = by_key['string:confirm_remove_device']
        self.assertIn('destructive_action', seg3['ui_risk_classification']['ui_role'])
        self.assertIn(seg3['ui_risk_classification']['risk_level'], ('high', 'critical'))
        review = seg3['ui_risk_classification']['review_priority']
        self.assertIn(review, ('review_recommended', 'owner_review_required'))

    def test_android_ui_risk_classification_legal_and_payment(self) -> None:
        content = '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <string name="accept_terms_checkbox">I agree to the Terms of Service.</string>\n    <string name="onboarding_consent">I consent to data processing.</string>\n    <string name="purchase_subscription_button">Subscribe for %1$s/month</string>\n    <string name="privacy_policy_link">Read our <a href="https://example.com/privacy">privacy policy</a>.</string>\n    <string name="billing_error">Payment failed. Please update your billing method.</string>\n</resources>'
        path = self._write_fixture(content)
        segments = self._extract(path)
        by_key = {s['context']['resource_key']: s for s in segments}
        seg = by_key['string:accept_terms_checkbox']
        self.assertIn('legal', seg['ui_risk_classification']['ui_role'])
        self.assertEqual(seg['ui_risk_classification']['risk_level'], 'high')
        self.assertIn(seg['ui_risk_classification']['review_priority'], ('review_recommended', 'owner_review_required'))
        seg2 = by_key['string:onboarding_consent']
        self.assertIn('legal', seg2['ui_risk_classification']['ui_role'])
        self.assertEqual(seg2['ui_risk_classification']['risk_level'], 'high')
        self.assertEqual(seg2['ui_risk_classification']['review_priority'], 'owner_review_required')
        seg3 = by_key['string:purchase_subscription_button']
        self.assertIn('payment', seg3['ui_risk_classification']['ui_role'])
        self.assertEqual(seg3['ui_risk_classification']['risk_level'], 'high')
        self.assertIn(seg3['ui_risk_classification']['review_priority'], ('review_recommended', 'owner_review_required'))
        self.assertIn('placeholder_or_markup_protected', seg3['ui_risk_classification']['classification_evidence'])
        seg4 = by_key['string:privacy_policy_link']
        self.assertIn('privacy', seg4['ui_risk_classification']['ui_role'])
        self.assertEqual(seg4['ui_risk_classification']['risk_level'], 'high')
        self.assertIn('placeholder_or_markup_protected', seg4['ui_risk_classification']['classification_evidence'])
        seg5 = by_key['string:billing_error']
        roles = seg5['ui_risk_classification']['ui_role']
        self.assertTrue({'error', 'payment'} & set(roles))
        self.assertEqual(seg5['ui_risk_classification']['risk_level'], 'high')

    def test_android_ui_risk_classification_avoids_generic_false_positive(self) -> None:
        content = '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <string name="generic_title">Library</string>\n    <string name="playlist_name">My playlist</string>\n    <string name="settings_title">Settings</string>\n</resources>'
        path = self._write_fixture(content)
        segments = self._extract(path)
        by_key = {s['context']['resource_key']: s for s in segments}
        risky_roles = {'destructive_action', 'legal', 'payment', 'auth', 'privacy', 'permission'}
        for key, safe_levels in [('string:generic_title', {'low', 'medium'}), ('string:playlist_name', {'low', 'medium'}), ('string:settings_title', {'low', 'medium'})]:
            seg = by_key[key]
            cls = seg['ui_risk_classification']
            overlap = set(cls.get('ui_role', [])) & risky_roles
            self.assertEqual(len(overlap), 0, f'{key} should not have risky roles, got {overlap}')
            self.assertIn(cls['risk_level'], safe_levels, f"{key} risk_level={cls['risk_level']}, expected {safe_levels}")
            self.assertNotIn('placeholder_or_markup_protected', cls['classification_evidence'])

    def test_v022_android_resource_reliability_risk_classification(self) -> None:
        """Full benchmark fixture smoke test: high-risk classified, generics not."""
        content = '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <!-- Destructive account action -->\n    <string name="delete_account_button">Delete account</string>\n    <string name="delete_account_warning">This action cannot be undone.</string>\n    <string name="reset_password_title">Reset password</string>\n    <string name="two_factor_code_message">Enter your verification code.</string>\n    <string name="allow_location_permission">Allow location access</string>\n    <string name="privacy_policy_link">Read our <a href="https://example.com/privacy">privacy policy</a>.</string>\n    <string name="accept_terms_checkbox">I agree to the Terms of Service.</string>\n    <string name="purchase_subscription_button">Subscribe for %1$s/month</string>\n    <string name="billing_error">Payment failed. Please update your billing method.</string>\n    <string name="generic_title">Library</string>\n    <string name="playlist_name">My playlist</string>\n    <!-- Destructive account action -->\n    <string name="confirm_remove_device">Remove this device</string>\n    <!-- Legal consent shown during onboarding -->\n    <string name="onboarding_consent">I consent to data processing.</string>\n</resources>'
        path = self._write_fixture(content)
        segments = self._extract(path)
        by_key = {s['context']['resource_key']: s for s in segments}
        seg = by_key['string:delete_account_button']
        self.assertIn(seg['ui_risk_classification']['risk_level'], ('high', 'critical'), 'destructive_account_button MUST be high or critical')
        self.assertNotEqual(seg['ui_risk_classification']['review_priority'], 'normal', 'destructive_account_button MUST NOT be normal priority')
        seg = by_key['string:accept_terms_checkbox']
        self.assertIn(seg['ui_risk_classification']['review_priority'], ('review_recommended', 'owner_review_required'), 'accept_terms_checkbox MUST be review_recommended or higher')
        seg2 = by_key['string:onboarding_consent']
        self.assertIn(seg2['ui_risk_classification']['review_priority'], ('review_recommended', 'owner_review_required'), 'onboarding_consent MUST be review_recommended or higher')
        for key in ('string:generic_title', 'string:playlist_name'):
            seg = by_key[key]
            self.assertNotIn(seg['ui_risk_classification']['risk_level'], ('high', 'critical'), f'{key} MUST NOT be high/critical')
        seg = by_key['string:purchase_subscription_button']
        self.assertIn(seg['ui_risk_classification']['review_priority'], ('review_recommended', 'owner_review_required'), 'purchase_subscription_button MUST be review_recommended or higher')
        for seg in segments:
            cls = seg['ui_risk_classification']
            if cls['risk_level'] != 'low':
                self.assertTrue(len(cls['classification_evidence']) > 0, f"{seg['context']['resource_key']} risk={cls['risk_level']} missing classification_evidence")


class ProtocolFilesTests(unittest.TestCase):

    def test_protocol_json_files_parse(self) -> None:
        root = Path(__file__).parents[1]
        paths = list((root / 'protocol' / 'schemas').glob('*.json'))
        paths.extend((root / 'protocol' / 'examples').glob('*.json'))
        paths.extend((root / 'adapters').rglob('adapter.json'))
        self.assertGreater(len(paths), 5)
        for path in paths:
            with self.subTest(path=path):
                json.loads(path.read_text(encoding='utf-8'))
        schema_names = {path.name.removesuffix('.schema.json') for path in (root / 'protocol' / 'schemas').glob('*.json')}
        example_names = {path.stem for path in (root / 'protocol' / 'examples').glob('*.json')}
        self.assertEqual(schema_names, example_names)

    def test_adapter_manifests_satisfy_builtin_contract(self) -> None:
        root = Path(__file__).parents[1]
        result = validate_adapter_tree(root / 'adapters')
        self.assertEqual(result['status'], 'pass', result['errors'])
        self.assertGreaterEqual(result['manifests_checked'], 5)

    def test_public_benchmark_definition_is_pinned_and_blind(self) -> None:
        root = Path(__file__).parents[1]
        benchmark = json.loads((root / 'benchmarks' / 'wesnoth-south-guard' / 'benchmark.json').read_text(encoding='utf-8'))
        self.assertEqual(len(benchmark['upstream']['commit']), 40)
        self.assertEqual(len(benchmark['upstream']['source_template_sha256']), 64)
        self.assertTrue(benchmark['generation_policy']['blind'])
        self.assertIn('po/wesnoth-tsg/zh_CN.po', benchmark['generation_policy']['forbidden_during_generation'])

    def test_protocol_examples_validate_against_schemas(self) -> None:
        root = Path(__file__).parents[1]
        result = validate_protocol_tree(root / 'protocol')
        self.assertEqual(result['status'], 'pass', result['errors'])
        self.assertEqual(result['schemas_checked'], 7)


class SkillFilesTests(unittest.TestCase):

    def test_skill_metadata_and_progressive_disclosure_contract(self) -> None:
        skill_root = REPOSITORY_ROOT / 'skills' / 'localize-anything'
        text = (skill_root / 'SKILL.md').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('---\n'))
        frontmatter = text.split('---', 2)[1]
        self.assertIn('name: localize-anything', frontmatter)
        self.assertIn('description:', frontmatter)
        self.assertLess(len(text.splitlines()), 500)
        metadata = (skill_root / 'agents' / 'openai.yaml').read_text(encoding='utf-8')
        self.assertIn('display_name: "Localize Anything"', metadata)
        self.assertIn('$localize-anything', metadata)
        for reference in ('workflow.md', 'memory-and-context.md', 'qa-and-delivery.md', 'adapters.md'):
            self.assertTrue((skill_root / 'references' / reference).is_file())


if __name__ == "__main__":
    unittest.main()
