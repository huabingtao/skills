#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for WeChat formatting fixes (Emoji Paragraph list conversion & strong nowrap) in danke-strategy-skill
"""

import unittest
from bs4 import BeautifulSoup
from engine.compiler import convert_to_wechat_html


class TestWeChatFormatting(unittest.TestCase):

    def setUp(self):
        self.project_config = {
            "title": "测试文章",
            "author": "弹壳呱呱"
        }

    def test_list_converted_to_emoji_paragraphs(self):
        """Test that <ul>/<li> lists are converted into clean <p> paragraphs without <ul> or <li> tags."""
        md = """
## 测试列表

- **大佬指导**：专属微信群技术支持
- **顶级战力**：人均攻击力 180万

#### 要求：
- 月矿积分 2200分
"""
        html, _ = convert_to_wechat_html(md, self.project_config)
        soup = BeautifulSoup(html, 'html.parser')
        
        self.assertEqual(len(soup.find_all('ul')), 0, "No <ul> tags should remain in compiled HTML")
        self.assertEqual(len(soup.find_all('li')), 0, "No <li> tags should remain in compiled HTML")
        
        paragraphs = soup.find_all('p')
        self.assertTrue(len(paragraphs) >= 3, "List items should be converted to <p> elements")
        
        text_content = "".join([p.get_text() for p in paragraphs])
        self.assertIn("🔹", text_content)
        self.assertIn("大佬指导", text_content)

    def test_strong_tag_bold_and_nowrap(self):
        """Test that <strong> tags retain bold styling and apply white-space: nowrap."""
        md = "测试 **高额远征奖励**：远征难度 15"
        html, _ = convert_to_wechat_html(md, self.project_config)
        soup = BeautifulSoup(html, 'html.parser')
        
        strong = soup.find('strong')
        self.assertIsNotNone(strong, "strong element should exist")
        style = strong.get('style', '')
        self.assertIn("white-space: nowrap", style)

    def test_colon_moved_inside_strong(self):
        """Test that colons after bold text are moved inside strong tags to prevent awkward line breaks."""
        md = "* **主会**：死亡圣器（ID：33352）"
        html, _ = convert_to_wechat_html(md, self.project_config)
        soup = BeautifulSoup(html, 'html.parser')
        
        strongs = soup.find_all('strong')
        self.assertTrue(len(strongs) >= 1)
        strong_texts = [s.get_text() for s in strongs]
        self.assertTrue(any("主会：" in text or "主会:" in text for text in strong_texts),
                        f"Expected colon inside strong tag, got strong texts: {strong_texts}")


if __name__ == '__main__':
    unittest.main()
