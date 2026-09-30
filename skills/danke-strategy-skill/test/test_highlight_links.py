import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.highlight import apply_highlight_rules, load_highlight_rules
from engine.compiler import convert_to_wechat_html
from scripts.compile import load_project_config


class TestHighlightLinkSafety(unittest.TestCase):
    def setUp(self):
        self.config = load_project_config(str(ROOT / 'packs/danke'))
        self.rules = load_highlight_rules(self.config['highlight_rules_path'])

    def test_wechat_link_survives_highlighting_and_compilation(self):
        url = 'https://mp.weixin.qq.com/s/vN79nJW3Cyn9sy0UDGvKaw'
        md = f'[计算器教程]({url})\n幽灵状态时间上限+3s'
        highlighted = apply_highlight_rules(md, self.rules)
        html, _ = convert_to_wechat_html(highlighted, self.config)
        soup = BeautifulSoup(html, 'html.parser')
        self.assertEqual(soup.find('a')['href'], url)
        self.assertIn('<font', highlighted)
        self.assertIn('+3s</font>', highlighted)

    def test_image_alt_url_attributes_and_shorthand_stay_intact(self):
        md = '![血量10%](./截图9s.jpg){type=center;w=80%}\n{{技能9s}}\n<img src="./截图9s.jpg" alt="10%">'
        self.assertEqual(apply_highlight_rules(md, self.rules), md)

    def test_code_and_bare_urls_are_not_highlighted(self):
        md = '`持续9s`\n```text\n伤害+10%\n```\nhttps://example.com/9s'
        self.assertEqual(apply_highlight_rules(md, self.rules), md)
