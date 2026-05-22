import os
import sys
import unittest
import json
import shutil
from unittest.mock import MagicMock

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from engine import publisher

class TestWeChatCaching(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.test_dir)
        
        # Paths for temporary test assets
        self.temp_img = os.path.join(self.test_dir, "temp_test_image.png")
        with open(self.temp_img, "w") as f:
            f.write("mock image content")
            
        # Test cache path
        self.test_cache_file = os.path.join(self.test_dir, ".test_wechat_image_cache.json")
        
        # Clean up any existing test cache file
        if os.path.exists(self.test_cache_file):
            os.remove(self.test_cache_file)

    def tearDown(self):
        # Clean up test files
        if os.path.exists(self.test_cache_file):
            os.remove(self.test_cache_file)
        if os.path.exists(self.temp_img):
            os.remove(self.temp_img)

    def test_get_file_md5(self):
        md5_1 = publisher.get_file_md5(self.temp_img)
        self.assertIsNotNone(md5_1)
        self.assertEqual(len(md5_1), 32)
        
        # Same file should yield same MD5
        md5_2 = publisher.get_file_md5(self.temp_img)
        self.assertEqual(md5_1, md5_2)

    def test_cache_loading_and_saving(self):
        cache = publisher.load_cache(self.test_cache_file)
        self.assertEqual(cache, {"content_images": {}, "thumb_materials": {}})
        
        # Modify cache and save
        cache["content_images"]["test_hash"] = "http://wechat.cdn/test.jpg"
        publisher.save_cache(cache, self.test_cache_file)
        
        # Reload cache and assert
        reloaded = publisher.load_cache(self.test_cache_file)
        self.assertEqual(reloaded["content_images"]["test_hash"], "http://wechat.cdn/test.jpg")

    def test_process_content_images_cache_flow(self):
        # Create a mock client
        mock_client = MagicMock()
        mock_client.upload_content_image.return_value = "http://mmbiz.qpic.cn/mocked_cdn_url"
        
        html_input = f'<img src="{self.temp_img}" style="width: 40px;" />'
        cache = publisher.load_cache(self.test_cache_file)
        
        # 1. First run: cache miss, upload should be called
        html_output_1 = publisher.process_content_images(
            mock_client, html_input, self.test_dir, cache, self.test_cache_file
        )
        self.assertIn("http://mmbiz.qpic.cn/mocked_cdn_url", html_output_1)
        mock_client.upload_content_image.assert_called_once_with(self.temp_img)
        
        # Check cache was updated and saved
        md5_val = publisher.get_file_md5(self.temp_img)
        updated_cache = publisher.load_cache(self.test_cache_file)
        self.assertEqual(updated_cache["content_images"][md5_val], "http://mmbiz.qpic.cn/mocked_cdn_url")
        
        # Reset mock
        mock_client.reset_mock()
        
        # 2. Second run: cache hit, upload should NOT be called
        html_output_2 = publisher.process_content_images(
            mock_client, html_input, self.test_dir, updated_cache, self.test_cache_file
        )
        self.assertIn("http://mmbiz.qpic.cn/mocked_cdn_url", html_output_2)
        mock_client.upload_content_image.assert_not_called()
        print("✅ Cache flow verification succeeded!")

if __name__ == "__main__":
    unittest.main()
