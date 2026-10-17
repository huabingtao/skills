import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


cli = load('douyin_publish_cli', 'publish.py')
uploader = load('douyin_uploader_tested', 'douyin_uploader.py')


class ReviewDefaultTests(unittest.TestCase):
    def test_no_flags_and_review_flag_both_open_headed_review(self):
        for flags in [[], ['--review'], ['--headed']]:
            args = cli.parse_args(flags)
            self.assertTrue(args.headed)
            self.assertTrue(args.review)
            self.assertFalse(args.publish)
            self.assertFalse(args.save_draft)

    def test_publishing_and_saving_require_separate_explicit_flags(self):
        args = cli.parse_args(['--save-draft'])
        self.assertTrue(args.save_draft)
        self.assertFalse(args.review)
        args = cli.parse_args(['--publish'])
        self.assertTrue(args.publish)
        self.assertFalse(args.review)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.parse_args(['--review', '--publish'])

    def test_actual_cli_handoff_defaults_without_launching_browser(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / '01_切图.png').write_bytes(b'test fixture')
            meta = root / 'article.json'
            meta.write_text('{"social_title":"时光拼图","summary":"三档方案"}', encoding='utf-8')
            upload = MagicMock()
            sync = MagicMock()
            with patch.dict(sys.modules, {
                'playwright.sync_api': SimpleNamespace(sync_playwright=sync),
                'douyin_uploader': SimpleNamespace(upload_image_post=upload),
            }), redirect_stdout(io.StringIO()):
                cli.main(['-i', temp, '-m', str(meta)])
            self.assertFalse(upload.call_args.kwargs['headless'])
            self.assertTrue(upload.call_args.kwargs['review'])
            self.assertFalse(upload.call_args.kwargs['publish_now'])

    def test_missing_fields_and_incomplete_body_cannot_report_success(self):
        with self.assertRaises(RuntimeError):
            uploader.verify_post_fields(None, None, '标题', '正文')
        title = MagicMock()
        title.input_value.return_value = '标题'
        body = MagicMock()
        body.get_attribute.return_value = 'true'
        body.inner_text.return_value = '未完成'
        with self.assertRaises(RuntimeError):
            uploader.verify_post_fields(title, body, '标题', '完整正文 #活动')
        body.inner_text.return_value = '完整正文\n#活动\u200b'
        self.assertEqual(uploader.verify_post_fields(title, body, '标题', '完整正文 #活动')['title'], '标题')


if __name__ == '__main__':
    unittest.main()
