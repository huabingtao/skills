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
from scripts.compile import load_project_config

class TestWeChatCompiler(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.pack_dir = os.path.join(PROJECT_ROOT, "packs", "danke")
        cls.project_config = load_project_config(cls.pack_dir)

    def test_numerical_highlighting(self):
        """Verify status values like +5% and +3s are highlighted in red strong font tags."""
        md = "暴击率+5%\n幽灵状态时间上限+3s"
        html, _ = convert_to_wechat_html(md, self.project_config)
        
        soup = BeautifulSoup(html, 'html.parser')
        fonts = soup.find_all('font')
        
        # Verify both values are wrapped in font tags with color #FF4D4F and strong tags
        red_fonts = [f for f in fonts if f.get('color') == '#FF4D4F']
        self.assertEqual(len(red_fonts), 2)
        self.assertIn("+5%", red_fonts[0].text)
        self.assertIn("+3s", red_fonts[1].text)
        
        for rf in red_fonts:
            self.assertEqual(rf.parent.name, 'strong')

    def test_highlight_nesting_prevention(self):
        """Verify that lookahead assertions prevent double-wrapping/nesting of highlights."""
        md = "暴击率+5%\n幽灵状态时间上限+3s"
        html, _ = convert_to_wechat_html(md, self.project_config)
        
        soup = BeautifulSoup(html, 'html.parser')
        # Check there are no nested font tags or strong tags
        for strong in soup.find_all('strong'):
            self.assertEqual(len(strong.find_all('strong')), 0, "Found nested strong tags!")
            for font in strong.find_all('font'):
                self.assertEqual(len(font.find_all('font')), 0, "Found nested font tags!")

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
        # Expected: <font style="white-space: nowrap !important;"><strong>专属效果</strong>：</font>对应S级装备破坏者风衣。
        li1 = lis[0]
        font1 = li1.find('font')
        self.assertIsNotNone(font1)
        self.assertEqual(font1.get('style'), 'white-space: nowrap !important;')
        self.assertIn("专属效果", font1.text)
        self.assertIn("：", font1.text)
        self.assertNotIn("对应S级装备", font1.text)
        # Check that <strong> is inside the font tag
        self.assertEqual(font1.find('strong').text, "专属效果")

        # 2. Second li has no bold but English colon followed by space
        # Expected: <font style="white-space: nowrap !important;">培养建议: </font>推荐拉到3[红星]
        li2 = lis[1]
        font2 = li2.find('font')
        self.assertIsNotNone(font2)
        self.assertEqual(font2.get('style'), 'white-space: nowrap !important;')
        self.assertEqual(font2.text, "培养建议: ")
        self.assertNotIn("推荐拉到", font2.text)

        # 3. Third li is a star list item, which should have style="white-space: nowrap !important;" on the <li> tag itself,
        # and NOT have nested colon nowrap font wrapper (since we skipped it).
        li3 = lis[2]
        self.assertIn("white-space: nowrap", li3.get('style', ''))
        # Ensure it doesn't have the nowrap font tag wrapping the colon
        font3 = li3.find('font', attrs={'style': 'white-space: nowrap !important;'})
        self.assertIsNone(font3)

if __name__ == '__main__':
    unittest.main()
