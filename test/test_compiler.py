# -*- coding: utf-8 -*-
import os
import sys
import unittest
import json
from bs4 import BeautifulSoup

# Ensure project root is in python path to import engine
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from engine.compiler import convert_to_wechat_html
from engine.compiler import convert_to_optimized_markdown, preprocess_markdown
from scripts.compile import load_project_config

class TestWeChatCompiler(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.pack_dir = os.path.join(PROJECT_ROOT, "packs", "danke")
        cls.project_config = load_project_config(cls.pack_dir)

    def test_numerical_highlighting(self):
        """Verify status values like +5% and +3s are highlighted in red strong font tags when rules are applied directly."""
        from engine.highlight import apply_highlight_rules, load_highlight_rules
        md = "暴击率+5%\n幽灵状态时间上限+3s"
        rules = load_highlight_rules(self.project_config.get('highlight_rules_path'))
        res = apply_highlight_rules(md, rules)
        self.assertIn('<strong><font color="#FF4D4F">+5%</font></strong>', res)
        self.assertIn('<strong><font color="#FF4D4F">+3s</font></strong>', res)

    def test_highlight_nesting_prevention(self):
        """Verify that auto-highlighting is disabled by default in convert_to_wechat_html."""
        md = "暴击率+5%\n幽灵状态时间上限+3s"
        html, _ = convert_to_wechat_html(md, self.project_config)
        soup = BeautifulSoup(html, 'html.parser')
        # Since auto-highlighting is commented out, there should be no font tags
        self.assertEqual(len(soup.find_all('font')), 0)

    def test_image_center_layout(self):
        """Verify the new type=center image layout with custom width."""
        # Test default center layout (no custom width -> auto)
        md_default = "![等离子剑](img://等离子剑){type=center}"
        html_default, _ = convert_to_wechat_html(md_default, self.project_config)
        soup_default = BeautifulSoup(html_default, 'html.parser')
        img_default = soup_default.find('img')
        self.assertIsNotNone(img_default)
        style_default = img_default.get('style', '')
        self.assertIn("display: block", style_default)
        self.assertIn("margin: 20px auto", style_default)
        self.assertIn("width: auto", style_default)

        # Test center layout with custom percentage width
        md_pct = "![等离子剑](img://等离子剑){type=center;w=60%}"
        html_pct, _ = convert_to_wechat_html(md_pct, self.project_config)
        soup_pct = BeautifulSoup(html_pct, 'html.parser')
        img_pct = soup_pct.find('img')
        style_pct = img_pct.get('style', '')
        self.assertIn("width: 60%", style_pct)

        # Test center layout with custom pixel width (no unit -> automatically appends px)
        md_px = "![等离子剑](img://等离子剑){type=center;w=250}"
        html_px, _ = convert_to_wechat_html(md_px, self.project_config)
        soup_px = BeautifulSoup(html_px, 'html.parser')
        img_px = soup_px.find('img')
        style_px = img_px.get('style', '')
        self.assertIn("width: 250px", style_px)

    def test_other_image_layouts(self):
        """Verify standard card and banner image layouts are correctly styled."""
        md = "![等离子剑](img://等离子剑){type=card}\n![追光者](img://追光者){type=banner}"
        html, _ = convert_to_wechat_html(md, self.project_config)
        soup = BeautifulSoup(html, 'html.parser')
        imgs = soup.find_all('img')
        self.assertEqual(len(imgs), 2)
        
        # Verify card style
        self.assertIn("width: 90%", imgs[0].get('style', ''))
        self.assertIn("border-radius: 12px", imgs[0].get('style', ''))
        
        # Verify banner style
        self.assertIn("width: 100%", imgs[1].get('style', ''))
        self.assertIn("border-radius: 8px", imgs[1].get('style', ''))

    def test_list_colon_nowrap(self):
        """Verify list item keys and colons are wrapped in nowrap font tags."""
        md = (
            "* **专属效果**：对应S级装备破坏者风衣。\n"
            "* 培养建议: 推荐拉到3[红星]\n"
            "* 3[红星](img://红星){type=icon}：暴击率+5%\n"
        )
        html, _ = convert_to_wechat_html(md, self.project_config)
        soup = BeautifulSoup(html, 'html.parser')
        lis = soup.find_all('li')
        self.assertEqual(len(lis), 3)

        # 1. First li has bold prefix and Chinese colon
        # Expected: <strong style="...white-space: nowrap !important;">专属效果：</strong>对应S级装备破坏者风衣。
        li1 = lis[0]
        strong1 = li1.find('strong')
        self.assertIsNotNone(strong1)
        self.assertIn("white-space: nowrap", strong1.get('style', ''))
        self.assertEqual(strong1.text, "专属效果：")
        self.assertNotIn("对应S级装备", strong1.text)

        # 2. Second li has no bold but English colon followed by space
        # Expected: <span style="white-space: nowrap !important;">培养建议: </span>推荐拉到3[红星]
        li2 = lis[1]
        span2 = li2.find('span')
        self.assertIsNotNone(span2)
        self.assertEqual(span2.get('style'), 'white-space: nowrap !important;')
        self.assertEqual(span2.text, "培养建议: ")
        self.assertNotIn("推荐拉到", span2.text)

        # 3. Third li is a star list item, which should have style="white-space: nowrap !important;" on the <li> tag itself,
        # and NOT have nested colon nowrap span wrapper (since we skipped it).
        li3 = lis[2]
        self.assertIn("white-space: nowrap", li3.get('style', ''))
        # Ensure it doesn't have the nowrap span tag wrapping the colon
        span3 = li3.find('span', attrs={'style': 'white-space: nowrap !important;'})
        self.assertIsNone(span3)

    def test_non_capturing_highlighting(self):
        """Verify that highlight rules with non-capturing patterns (no groups) are correctly highlighted."""
        custom_rules = {
            "colors": {
                "red": "#FF4D4F",
                "green": "#52C41A"
            },
            "red": [
                # Capturing group pattern
                {"pattern": r"(\+5%)"}
            ],
            "green": [
                # Non-capturing group pattern
                {"pattern": r"\+10%"}
            ]
        }
        
        from engine.highlight import apply_highlight_rules
        
        # Test capturing group pattern
        text1 = "暴击率+5%"
        res1 = apply_highlight_rules(text1, custom_rules)
        self.assertIn('<strong><font color="#FF4D4F">+5%</font></strong>', res1)
        
        # Test non-capturing pattern (used to crash before optimization)
        text2 = "生命值+10%"
        res2 = apply_highlight_rules(text2, custom_rules)
        self.assertIn('<strong><font color="#52C41A">+10%</font></strong>', res2)

    def test_ruby_annotations_collision_prevention(self):
        """Verify that Ruby annotations regex only matches phonetic annotations, and does not collide with attributes."""
        # 1. Normal Ruby annotation should work
        md_ruby = "[拼音]{pin1 yin1}"
        html_ruby, _ = convert_to_wechat_html(md_ruby, self.project_config)
        self.assertIn("<ruby>拼音<rt>pin1 yin1</rt></ruby>", html_ruby)

        # 2. Image/link attribute style should NOT be matched as Ruby annotation
        md_attr = "[追光者]{type=card}"
        html_attr, _ = convert_to_wechat_html(md_attr, self.project_config)
        # Should stay plain text instead of converting to <ruby>
        self.assertNotIn("<ruby>", html_attr)

    def test_frontmatter_cover_and_shorthand_resolution(self):
        """Verify metadata cover and {{name}} shorthand use the shared resolver."""
        md = "---\ntitle: 封面测试\nimage: img://等离子剑\n---\n共鸣伤害{{共鸣伤害}}"
        html, metadata = convert_to_wechat_html(md, self.project_config)
        self.assertEqual(metadata["image"], "assets/img/收藏品/第4期/4-等离子剑.png")
        soup = BeautifulSoup(html, 'html.parser')
        img = soup.find('img', attrs={'alt': '共鸣伤害'})
        self.assertIsNotNone(img)
        self.assertIn("assets/img/技能图标/宠物技能/共鸣伤害.png", img.get('src', ''))
        self.assertIn("width: 24px", img.get('style', ''))

    def test_external_link_footnotes_deduplicate(self):
        """Verify repeated external links share a single footnote index."""
        md = "[A](https://example.com)\n[B](https://example.com)"
        html, _ = convert_to_wechat_html(md, self.project_config)
        soup = BeautifulSoup(html, 'html.parser')
        self.assertEqual([sup.text for sup in soup.find_all('sup')], ["[1]", "[1]"])
        self.assertEqual(soup.get_text().count("https://example.com"), 1)

    def test_optimized_markdown_uses_shared_image_resolver(self):
        """Verify optimized markdown resolves img:// paths through the same resolver."""
        md = "---\nimage: img://等离子剑\n---\n{{共鸣伤害}}"
        optimized = convert_to_optimized_markdown(md, self.project_config)
        self.assertIn("image: assets/img/收藏品/第4期/4-等离子剑.png", optimized)
        self.assertIn("![共鸣伤害](assets/img/技能图标/宠物技能/共鸣伤害.png){width=24px height=24px}", optimized)

    def test_highlight_is_explicitly_opt_in_for_preprocess(self):
        """Document the Stage 1/Stage 3 highlight contract in code."""
        md = "暴击率+5%"
        self.assertNotIn("<font", preprocess_markdown(md, self.project_config))
        self.assertIn("<font", preprocess_markdown(md, self.project_config, enable_highlight=True))

if __name__ == '__main__':
    unittest.main()
