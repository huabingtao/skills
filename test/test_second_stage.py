# -*- coding: utf-8 -*-
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in python path to import engine
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import engine.publisher as wechat_publisher

class TestSecondStageOptimizations(unittest.TestCase):
    
    def test_load_config_handling_invalid_json(self):
        """Verify load_config handles malformed json without crashing."""
        bad_json_content = "{\n  \"appid\": \"test_appid\",\n  \"appsecret\": \n" # Malformed JSON
        
        # We will write to a temp file and patch the config_paths in load_config
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(bad_json_content)
            temp_path = f.name
            
        try:
            # Whenever os.path.exists is checked, return True for our fake config files
            # to force it to open and read them.
            def mock_exists(p):
                return "config.json" in p or "wechat_config.json" in p
                
            # Patch exists and open
            with patch('engine.publisher.os.path.exists', mock_exists):
                def mock_open(file, *args, **kwargs):
                    return open(temp_path, *args, **kwargs)
                
                with patch('builtins.open', mock_open):
                    # This should read the bad JSON from temp_path, throw warning and return {}
                    config = wechat_publisher.load_config()
                    self.assertEqual(config, {})
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @patch('engine.publisher.WeChatClient')
    @patch('builtins.input', return_value='y')
    @patch('engine.publisher.process_content_images', lambda client, html, *args, **kwargs: html)
    def test_digest_passed_to_create_draft(self, mock_input, mock_wechat_client):
        """Verify metadata summary/digest is parsed and passed to create_draft."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_wechat_client.return_value = mock_client_instance
        mock_client_instance.upload_image.return_value = "mock_thumb_media_id"
        mock_client_instance.create_draft.return_value = "mock_draft_media_id"
        
        # Create a mock HTML file and a mock JSON metadata file
        import tempfile
        html_content = "<div>Test article body</div>"
        metadata = {
            "title": "测试文章标题",
            "author": "测试作者",
            "summary": "这是测试文章的摘要内容。",
            "image": "test_cover.png"
        }
        
        # Write to temp files
        html_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
        html_file.write(html_content)
        html_file.close()
        
        json_path = os.path.splitext(html_file.name)[0] + ".json"
        with open(json_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(metadata, f, ensure_ascii=False)
            
        # Create mock cover image
        cover_path = os.path.join(os.path.dirname(html_file.name), "test_cover.png")
        with open(cover_path, 'w') as f:
            f.write("mock_image_data")
            
        try:
            # Set up command line arguments
            sys_argv_backup = sys.argv
            sys.argv = [
                'wechat_publisher.py',
                '-c', html_file.name,
                '--appid', 'test_appid_123',
                '--secret', 'test_secret_123'
            ]
            
            # Run publisher main
            wechat_publisher.main()
            
            # Verify create_draft call parameters
            mock_client_instance.create_draft.assert_called_once_with(
                title="测试文章标题",
                html_content=html_content,
                thumb_media_id="mock_thumb_media_id",
                author="测试作者",
                digest="这是测试文章的摘要内容。"
            )
            print("✅ Successfully verified summary/digest is correctly passed to WeChat API client!")
            
        finally:
            # Clean up files
            sys.argv = sys_argv_backup
            for path in [html_file.name, json_path, cover_path]:
                if os.path.exists(path):
                    os.remove(path)

if __name__ == '__main__':
    unittest.main()
