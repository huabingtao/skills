import unittest
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.auto_tag import auto_tag_text, load_keywords

class TestAutoTag(unittest.TestCase):
    def setUp(self):
        self.mapping_path = os.path.join(PROJECT_ROOT, "packs", "danke", "image_mapping.json")
        self.keywords = load_keywords(self.mapping_path)

    def test_keywords_loaded(self):
        self.assertTrue(len(self.keywords) > 50)
        self.assertIn("塔洛西娅", self.keywords)
        self.assertIn("幽焰逐影", self.keywords)
        self.assertIn("末世战马", self.keywords)
        self.assertIn("谐振芯片", self.keywords)
        self.assertIn("幽暗之灵", self.keywords)

    def test_auto_tag_basic(self):
        text = "觉醒5之前用塔洛西娅，觉醒5之后换维托尔。载具选幽焰逐影比末世战马强。开谐振芯片，宠物用幽暗之灵。"
        res = auto_tag_text(text, self.keywords)
        self.assertIn("{{塔洛西娅}}", res)
        self.assertIn("{{维托尔}}", res)
        self.assertIn("{{幽焰逐影}}", res)
        self.assertIn("{{末世战马}}", res)
        self.assertIn("{{谐振芯片}}", res)
        self.assertIn("{{幽暗之灵}}", res)

    def test_no_double_tagging(self):
        text = "已经有{{塔洛西娅}}和{{维托尔}}，不要重复加标签。"
        res = auto_tag_text(text, self.keywords)
        self.assertNotIn("{{{{塔洛西娅}}}}", res)
        self.assertIn("{{塔洛西娅}}", res)
        self.assertNotIn("{{{{维托尔}}}}", res)
        self.assertIn("{{维托尔}}", res)

    def test_protect_markdown_links(self):
        text = "[查看塔洛西娅详情](http://example.com/塔洛西娅) 这是正文中的塔洛西娅。"
        res = auto_tag_text(text, self.keywords)
        self.assertIn("[查看塔洛西娅详情](http://example.com/塔洛西娅)", res)
        self.assertIn("这是正文中的{{塔洛西娅}}", res)

if __name__ == "__main__":
    unittest.main()
