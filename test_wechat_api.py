# -*- coding: utf-8 -*-
import os
import sys
import json
import unittest
import time
from unittest.mock import MagicMock, patch

# Ensure project root is in python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from engine.wechat_api import WeChatClient


class TestWeChatClient(unittest.TestCase):

    def setUp(self):
        self.appid = "mock_appid"
        self.appsecret = "mock_secret"
        self.cache_dir = os.path.dirname(os.path.abspath(__file__))
        self.token_cache_file = os.path.join(self.cache_dir, ".wechat_token_cache.json")
        if os.path.exists(self.token_cache_file):
            os.remove(self.token_cache_file)
        
        self.client = WeChatClient(self.appid, self.appsecret, self.cache_dir)

    def tearDown(self):
        if os.path.exists(self.token_cache_file):
            os.remove(self.token_cache_file)

    @patch('requests.get')
    def test_get_access_token_caching(self, mock_get):
        # Setup mock response for fetching token
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "token_123",
            "expires_in": 7200
        }
        mock_get.return_value = mock_response

        # 1. First fetch (cache miss, fetches from API)
        token1 = self.client.get_access_token()
        self.assertEqual(token1, "token_123")
        mock_get.assert_called_once()

        # Reset mock
        mock_get.reset_mock()

        # 2. Second fetch (in-memory cache hit, does not call API)
        token2 = self.client.get_access_token()
        self.assertEqual(token2, "token_123")
        mock_get.assert_not_called()

        # 3. Third fetch with force_refresh=True (forces API reload)
        mock_response.json.return_value = {
            "access_token": "token_456",
            "expires_in": 7200
        }
        token3 = self.client.get_access_token(force_refresh=True)
        self.assertEqual(token3, "token_456")
        mock_get.assert_called_once()

        # 4. Check that token was saved to file cache
        self.assertTrue(os.path.exists(self.token_cache_file))
        with open(self.token_cache_file, 'r') as f:
            saved_cache = json.load(f)
        self.assertEqual(saved_cache["access_token"], "token_456")

    @patch('requests.post')
    @patch('requests.get')
    def test_upload_image_success_and_retry(self, mock_get, mock_post):
        # Mock token fetch
        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {"access_token": "valid_token", "expires_in": 7200}
        mock_get.return_value = mock_get_response

        # Create temporary dummy image file
        temp_img_path = os.path.join(self.cache_dir, "temp_test_upload.png")
        with open(temp_img_path, "wb") as f:
            f.write(b"dummy image bytes")

        try:
            # 1. Test normal successful upload
            mock_post_response = MagicMock()
            mock_post_response.json.return_value = {"media_id": "media_id_999"}
            mock_post.return_value = mock_post_response

            media_id = self.client.upload_image(temp_img_path, is_thumb=True)
            self.assertEqual(media_id, "media_id_999")
            self.assertEqual(mock_post.call_count, 1)

            # 2. Test retry flow when token is expired (40001)
            mock_post.reset_mock()
            mock_get.reset_mock()
            self.client.access_token = "expired_token"
            self.client.access_token_expires_at = time.time() + 3600

            # First post returns 40001, second post succeeds
            res_fail = MagicMock()
            res_fail.json.return_value = {"errcode": 40001, "errmsg": "invalid credential, access_token is invalid"}
            res_success = MagicMock()
            res_success.json.return_value = {"media_id": "media_id_retry"}
            mock_post.side_effect = [res_fail, res_success]

            media_id_retry = self.client.upload_image(temp_img_path, is_thumb=False)
            self.assertEqual(media_id_retry, "media_id_retry")
            # Should have requested token refresh from API
            mock_get.assert_called_once()
            # Should have called post twice
            self.assertEqual(mock_post.call_count, 2)

        finally:
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)

    @patch('requests.post')
    @patch('requests.get')
    def test_create_and_update_draft(self, mock_get, mock_post):
        # Mock token fetch
        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {"access_token": "valid_token", "expires_in": 7200}
        mock_get.return_value = mock_get_response

        # Mock draft success response
        mock_post_response = MagicMock()
        mock_post_response.json.return_value = {"media_id": "new_draft_media_id", "errcode": 0}
        mock_post.return_value = mock_post_response

        # Test create draft
        media_id = self.client.create_draft(
            title="My Title",
            html_content="<p>hello</p>",
            thumb_media_id="thumb_id",
            author="Author",
            digest="Digest"
        )
        self.assertEqual(media_id, "new_draft_media_id")
        mock_post.assert_called_once()

        # Mock update draft success response
        mock_post.reset_mock()
        mock_post_response.json.return_value = {"errcode": 0}
        
        # Test update draft
        self.client.update_draft(
            media_id="existing_draft_media_id",
            title="Updated Title",
            html_content="<p>updated</p>",
            thumb_media_id="thumb_id",
            index=0
        )
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
