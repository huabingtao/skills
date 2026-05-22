# -*- coding: utf-8 -*-
"""
WeChat Official Account API Client.
Handles AccessToken management, image uploading, and Draft (草稿箱) creation/update.

Copied from scripts/wechat_api.py with the following change:
- TOKEN_CACHE_PATH is now resolved relative to a configurable cache_dir
  parameter instead of being a fixed class-level constant.
"""

import os
import json
import time
import requests
from typing import Dict, Any, Optional


class WeChatClient:
    """
    WeChat Official Account API Client.
    Handles AccessToken management and Draft (草稿箱) creation.
    """

    BASE_URL = "https://api.weixin.qq.com/cgi-bin"

    def __init__(self, appid: str, appsecret: str, cache_dir: str = "."):
        self.appid = appid
        self.appsecret = appsecret
        self.access_token = None
        self.TOKEN_CACHE_PATH = os.path.join(cache_dir, ".wechat_token_cache.json")

    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        Retrieves the access_token, using local cache if valid.
        Automatically refreshes if expired.
        """
        # 1. Try to load from cache
        if not force_refresh and os.path.exists(self.TOKEN_CACHE_PATH):
            try:
                with open(self.TOKEN_CACHE_PATH, 'r') as f:
                    cache = json.load(f)

                # Check if token is still valid (refresh 10 minutes early)
                if time.time() < cache.get('expires_at', 0) - 600:
                    return cache['access_token']
            except (json.JSONDecodeError, KeyError, Exception):
                pass

        # 2. Fetch new token from WeChat API
        url = f"{self.BASE_URL}/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.appsecret
        }

        response = requests.get(url, params=params)
        data = response.json()

        if "access_token" not in data:
            raise Exception(f"Failed to get AccessToken: {data.get('errmsg', 'Unknown Error')} (Code: {data.get('errcode')})")

        token = data["access_token"]
        expires_in = data.get("expires_in", 7200)

        # 3. Save to cache
        cache_data = {
            "access_token": token,
            "expires_at": time.time() + expires_in
        }
        try:
            os.makedirs(os.path.dirname(self.TOKEN_CACHE_PATH) or '.', exist_ok=True)
        except OSError:
            pass
        with open(self.TOKEN_CACHE_PATH, 'w') as f:
            json.dump(cache_data, f)

        return token

    def upload_image(self, image_path: str, is_thumb: bool = False) -> str:
        """
        Uploads an image as a permanent material to get a MediaID.
        Mainly used for cover images (thumb).
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        token = self.get_access_token()
        material_type = "thumb" if is_thumb else "image"
        url = f"{self.BASE_URL}/material/add_material?access_token={token}&type={material_type}"

        filename = os.path.basename(image_path)

        with open(image_path, 'rb') as f:
            files = {'media': (filename, f)}
            response = requests.post(url, files=files)

        result = response.json()
        if "media_id" not in result:
            raise Exception(f"Failed to upload permanent material: {result.get('errmsg')} (Code: {result.get('errcode')})")

        return result["media_id"]

    def upload_content_image(self, image_path: str) -> str:
        """
        Uploads an image to WeChat CDN (图床接口) to get a persistent URL.
        Used for images within the article content.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        token = self.get_access_token()
        # WeChat Content CDN API
        url = f"{self.BASE_URL}/media/uploadimg?access_token={token}"

        filename = os.path.basename(image_path)

        with open(image_path, 'rb') as f:
            files = {'media': (filename, f)}
            response = requests.post(url, files=files)

        result = response.json()
        if "url" not in result:
            raise Exception(f"Failed to upload to WeChat CDN: {result.get('errmsg')} (Code: {result.get('errcode')})")

        return result["url"]

    def create_draft(self,
                     title: str,
                     html_content: str,
                     thumb_media_id: str,
                     author: str = "Admin",
                     digest: str = "",
                     show_cover_pic: int = 1) -> str:
        """
        Creates a draft in the WeChat Official Account.

        Args:
            title: Article title.
            html_content: Converted HTML content.
            thumb_media_id: MediaID of the uploaded cover image.
            author: Article author.
            digest: Article summary (optional).
            show_cover_pic: 1 to show cover in article, 0 to hide.

        Returns:
            The media_id of the created draft.
        """
        token = self.get_access_token()
        url = f"{self.BASE_URL}/draft/add?access_token={token}"

        # Article structure
        article_data = {
            "articles": [
                {
                    "title": title,
                    "author": author,
                    "digest": digest,
                    "content": html_content,
                    "thumb_media_id": thumb_media_id,
                    "show_cover_pic": show_cover_pic,
                    "need_open_comment": 0,
                    "only_fans_can_comment": 0
                }
            ]
        }

        # Send request
        # ensure_ascii=False is critical for Chinese characters
        payload = json.dumps(article_data, ensure_ascii=False).encode('utf-8')
        headers = {'Content-Type': 'application/json; charset=utf-8'}

        response = requests.post(url, data=payload, headers=headers)
        result = response.json()

        if result.get("errcode", 0) != 0:
            # Handle token expiration and retry once
            if result.get("errcode") in [40001, 42001]:
                token = self.get_access_token(force_refresh=True)
                url = f"{self.BASE_URL}/draft/add?access_token={token}"
                response = requests.post(url, data=payload, headers=headers)
                result = response.json()

            if result.get("errcode", 0) != 0:
                raise Exception(f"Failed to create draft: {result.get('errmsg')} (Code: {result.get('errcode')})")

        return result["media_id"]

    def update_draft(self,
                     media_id: str,
                     title: str,
                     html_content: str,
                     thumb_media_id: str,
                     index: int = 0,
                     author: str = "Admin",
                     digest: str = "",
                     show_cover_pic: int = 1) -> None:
        """
        Updates an existing draft in the WeChat Official Account.

        Args:
            media_id: The media_id of the draft to update.
            title: Article title.
            html_content: Converted HTML content.
            thumb_media_id: MediaID of the uploaded cover image.
            index: The index of the article in the draft (0-based).
            author: Article author.
            digest: Article summary (optional).
            show_cover_pic: 1 to show cover in article, 0 to hide.
        """
        token = self.get_access_token()
        url = f"{self.BASE_URL}/draft/update?access_token={token}"

        # Update structure
        update_data = {
            "media_id": media_id,
            "index": index,
            "articles": {
                "title": title,
                "author": author,
                "digest": digest,
                "content": html_content,
                "thumb_media_id": thumb_media_id,
                "show_cover_pic": show_cover_pic,
                "need_open_comment": 0,
                "only_fans_can_comment": 0
            }
        }

        # Send request
        payload = json.dumps(update_data, ensure_ascii=False).encode('utf-8')
        headers = {'Content-Type': 'application/json; charset=utf-8'}

        response = requests.post(url, data=payload, headers=headers)
        result = response.json()

        if result.get("errcode", 0) != 0:
            # Handle token expiration and retry once
            if result.get("errcode") in [40001, 42001]:
                token = self.get_access_token(force_refresh=True)
                url = f"{self.BASE_URL}/draft/update?access_token={token}"
                response = requests.post(url, data=payload, headers=headers)
                result = response.json()

            if result.get("errcode", 0) != 0:
                raise Exception(f"Failed to update draft: {result.get('errmsg')} (Code: {result.get('errcode')})")
