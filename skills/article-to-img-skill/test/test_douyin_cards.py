import copy
import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import douyin_cards as cards
import export_cards


class OutlineTests(unittest.TestCase):
    def test_diamond_units_and_wide_tables(self):
        blocks = cards.expand_blocks([{'type': 'table', 'headers': ['开箱次数', '补至 850（钻石）', '补至 1000（钻石）', '补至 1650（钻石）'],
                                       'rows': [[600, '0 钻', '0{{钻石}}', '43200 钻石']]}])
        self.assertEqual([len(b['headers']) for b in blocks], [3, 2])
        self.assertEqual(blocks[0]['rows'], [[600, '0', '0']])
        self.assertEqual(blocks[1]['rows'], [[600, '43200']])

    def test_macro_requires_current_compiled_asset_and_escapes_text(self):
        renderer = cards.CardRenderer({'s级军备钥匙': 'data:image/png;base64,AA=='}, Path('.'))
        self.assertIn('data:image/png', renderer.inline('S 级军备钥匙{{S钥匙}}'))
        self.assertIn('&lt;script&gt;', renderer.inline('<script>'))
        with self.assertRaisesRegex(ValueError, '未出现在本次编译'):
            renderer.inline('{{不存在的图标}}')

    def test_compiled_short_alt_also_serves_full_name(self):
        renderer = cards.CardRenderer({'S钥匙': 'data:image/png;base64,AA=='}, Path('.'))
        self.assertIn('data:image/png', renderer.inline('S 级军备钥匙{{s级军备钥匙}}'))

    def test_stale_outline_rejected_before_any_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'article.html'
            source.write_text('<p>原文</p>')
            outline = root / 'outline.json'
            outline.write_text(json.dumps({'version': 1, 'source_html_sha256': 'stale', 'pages': [
                {'title': '标题', 'blocks': [{'type': 'text', 'text': '内容'}]}]}))
            with self.assertRaisesRegex(ValueError, '已变化'):
                cards.render_douyin_cards(source, outline, root / 'output')
            self.assertFalse((root / 'output').exists())

    def test_invalid_rows_rejected_before_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'outline.json'
            p.write_text(json.dumps({'version': 1, 'pages': [{'title': '标题', 'blocks': [
                {'type': 'table', 'headers': ['A', 'B'], 'rows': [['only one']]}]}]}))
            with self.assertRaisesRegex(ValueError, '列数'):
                cards.load_outline(p)

    def test_legacy_cli_still_calls_original_renderer(self):
        with patch.object(sys, 'argv', ['export_cards.py', 'article.html']), patch.object(export_cards, 'direct_slice_html') as old:
            export_cards.main()
        old.assert_called_once_with('article.html', output_dir=None, target_width=1080, target_height=1440, dpr=2, overlap_px=140)

    def test_new_cli_uses_profile_without_touching_legacy(self):
        with patch.object(sys, 'argv', ['export_cards.py', 'article.html', '--profile', 'douyin', '--outline', 'plan.json']), \
             patch.object(cards, 'render_douyin_cards') as new, patch.object(export_cards, 'direct_slice_html') as old:
            export_cards.main()
        self.assertEqual(new.call_args.args[1], 'plan.json')
        old.assert_not_called()


class PaginationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = export_cards.get_playwright_engine()().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1080, 'height': 1440})
        self.renderer = cards.CardRenderer({}, Path('.'))

    def tearDown(self):
        self.page.close()

    def verify_pages(self, pages):
        for topic in pages:
            self.page.set_content(cards.document_html(topic['title'], '测试 · 续页', topic['blocks'], self.renderer))
            self.assertTrue(self.page.evaluate(cards.FIT_JS))
            self.assertGreaterEqual(cards.inspect_card(self.page)['min_font'], 36)
            self.assertEqual(self.page.evaluate("getComputedStyle(document.querySelector('.card')).backgroundColor"), 'rgb(242, 239, 232)')

    def test_long_paragraph_preserves_every_character(self):
        text = '活动预算使用实测比例估算，长段落必须拆页，不能降低字号。' * 70
        topic = {'title': '长段落测试', 'blocks': [{'type': 'text', 'text': text}]}
        before = copy.deepcopy(topic)
        pages = cards.paginate_topic(self.page, topic, self.renderer)
        self.assertGreater(len(pages), 2)
        self.assertEqual(''.join(b['text'] for p in pages for b in p['blocks']), text)
        self.assertEqual(topic, before)
        self.verify_pages(pages)

    def test_table_continuations_preserve_rows_and_repeat_header(self):
        rows = [[f'任务 {i}', i] for i in range(35)]
        topic = {'title': '任务明细', 'blocks': [{'type': 'table', 'headers': ['任务要求', '道具数量'], 'rows': rows}]}
        pages = cards.paginate_topic(self.page, topic, self.renderer)
        self.assertGreater(len(pages), 2)
        self.assertEqual([r for p in pages for b in p['blocks'] for r in b['rows']], rows)
        for p in pages:
            self.assertEqual(p['blocks'][0]['headers'], ['任务要求', '道具数量'])
        self.verify_pages(pages)

    def test_long_item_name_wraps_without_cutting_or_losing_text(self):
        name = '传奇载具科技滑板电动平衡车神器核心自选宝箱' * 24
        pages = cards.paginate_topic(self.page, {'title': '长道具名', 'blocks': [
            {'type': 'list', 'ordered': True, 'items': [name, '第二个道具']} ]}, self.renderer)
        self.assertEqual(''.join(b['text'] for p in pages for b in p['blocks']), name + '第二个道具')
        self.verify_pages(pages)

    def test_oversize_atomic_row_fails_without_shrinking(self):
        topic = {'title': '过长单行', 'blocks': [{'type': 'table', 'headers': ['道具', '数量'],
                 'rows': [['道具' * 1200, 1]]}]}
        with self.assertRaisesRegex(ValueError, '禁止缩小字号'):
            cards.paginate_topic(self.page, topic, self.renderer)

    def test_short_final_page_keeps_font_size(self):
        pages = cards.paginate_topic(self.page, {'title': '最后提醒', 'blocks': [
            {'type': 'text', 'text': '先用完任务道具，再按实际进度补钻。'}]}, self.renderer)
        self.assertEqual(len(pages), 1)
        self.verify_pages(pages)
        self.assertEqual(self.page.evaluate("getComputedStyle(document.querySelector('.text')).fontSize"), '48px')

    def test_broken_image_does_not_overwrite_successful_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'article.html'
            source.write_text('<img alt="坏图" src="data:image/png;base64,AA==">')
            outline = root / 'outline.json'
            outline.write_text(json.dumps({'version': 1, 'pages': [
                {'title': '图片校验', 'blocks': [{'type': 'text', 'text': '坏图{{坏图}}'}]}]}))
            output = root / 'output'
            output.mkdir()
            manifest = output / 'manifest.json'
            manifest.write_text('{"previous":"success"}')
            # Exercise the real CLI in another process (no nested Playwright loop).
            result = subprocess.run([sys.executable, str(Path(export_cards.__file__)), str(source),
                                     '--profile', 'douyin', '--outline', str(outline),
                                     '--output', str(output), '--dpr', '1'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('图片未加载', result.stderr)
            self.assertEqual(manifest.read_text(), '{"previous":"success"}')
            self.assertFalse((output / '01_卡片.png').exists())


if __name__ == '__main__':
    unittest.main()
