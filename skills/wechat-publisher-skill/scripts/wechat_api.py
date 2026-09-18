# -*- coding: utf-8 -*-
"""
WeChat Official Account API Client.
Handles AccessToken management, image uploading, and Draft (草稿箱) creation/update.
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
        self.access_token_expires_at = 0.0
        self.TOKEN_CACHE_PATH = os.path.join(cache_dir, ".wechat_token_cache.json")

    def get_access_token(self, force_refresh: bool = False) -> str:
        if not force_refresh and self.access_token and time.time() < self.access_token_expires_at - 600:
            return self.access_token

        if not force_refresh and os.path.exists(self.TOKEN_CACHE_PATH):
            try:
                with open(self.TOKEN_CACHE_PATH, 'r') as f:
                    cache = json.load(f)
                if time.time() < cache.get('expires_at', 0) - 600:
                    self.access_token = cache['access_token']
                    self.access_token_expires_at = cache.get('expires_at', 0.0)
                    return self.access_token
            except (json.JSONDecodeError, KeyError, Exception):
                pass

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
        expires_at = time.time() + expires_in

        self.access_token = token
        self.access_token_expires_at = expires_at

        cache_data = {"access_token": token, "expires_at": expires_at}
        try:
            os.makedirs(os.path.dirname(self.TOKEN_CACHE_PATH) or '.', exist_ok=True)
        except OSError:
            pass
        with open(self.TOKEN_CACHE_PATH, 'w') as f:
            json.dump(cache_data, f)

        return token

    def _post(self, path_suffix: str, files: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None, force_refresh: bool = False) -> Dict[str, Any]:
        token = self.get_access_token(force_refresh=force_refresh)
        separator = "&" if "?" in path_suffix else "?"
        url = f"{self.BASE_URL}{path_suffix}{separator}access_token={token}"

        if files:
            response = requests.post(url, files=files)
        elif json_data:
            payload = json.dumps(json_data, ensure_ascii=False).encode('utf-8')
            req_headers = {'Content-Type': 'application/json; charset=utf-8'}
            if headers:
                req_headers.update(headers)
            response = requests.post(url, data=payload, headers=req_headers)
        else:
            response = requests.post(url)

        response.encoding = 'utf-8'
        return json.loads(response.content.decode('utf-8'))

    def _post_with_retry(self, path_suffix: str, files_builder_func=None, json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        files = files_builder_func() if files_builder_func else None
        try:
            result = self._post(path_suffix, files=files, json_data=json_data, headers=headers)
        finally:
            if files:
                for _, file_tuple in files.items():
                    if isinstance(file_tuple, tuple) and len(file_tuple) >= 2:
                        file_handle = file_tuple[1]
                        if hasattr(file_handle, 'close'):
                            file_handle.close()

        errcode = result.get("errcode", 0)
        if errcode in [40001, 42001]:
            files = files_builder_func() if files_builder_func else None
            try:
                result = self._post(path_suffix, files=files, json_data=json_data, headers=headers, force_refresh=True)
            finally:
                if files:
                    for _, file_tuple in files.items():
                        if isinstance(file_tuple, tuple) and len(file_tuple) >= 2:
                            file_handle = file_tuple[1]
                            if hasattr(file_handle, 'close'):
                                file_handle.close()
        return result

    def upload_image(self, image_path: str, is_thumb: bool = False) -> str:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        filename = os.path.basename(image_path)
        material_type = "thumb" if is_thumb else "image"
        path_suffix = f"/material/add_material?type={material_type}"

        def files_builder():
            return {'media': (filename, open(image_path, 'rb'))}

        result = self._post_with_retry(path_suffix, files_builder_func=files_builder)

        if "media_id" not in result:
            raise Exception(f"Failed to upload permanent material: {result.get('errmsg')} (Code: {result.get('errcode')})")

        return result["media_id"]

    def upload_content_image(self, image_path: str) -> str:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        filename = os.path.basename(image_path)
        path_suffix = "/media/uploadimg"

        def files_builder():
            return {'media': (filename, open(image_path, 'rb'))}

        result = self._post_with_retry(path_suffix, files_builder_func=files_builder)

        if "url" not in result:
            raise Exception(f"Failed to upload to WeChat CDN: {result.get('errmsg')} (Code: {result.get('errcode')})")

        return result["url"]

    def create_draft(self, title: str, html_content: str, thumb_media_id: str,
                     author: str = "Admin", digest: str = "", show_cover_pic: int = 1,
                     need_open_comment: int = 1, only_fans_can_comment: int = 0) -> str:
        article_data = {
            "articles": [{
                "title": title, "author": author, "digest": digest,
                "content": html_content, "thumb_media_id": thumb_media_id,
                "show_cover_pic": show_cover_pic, "need_open_comment": need_open_comment,
                "only_fans_can_comment": only_fans_can_comment
            }]
        }
        result = self._post_with_retry("/draft/add", json_data=article_data)
        if "media_id" not in result:
            raise Exception(f"Failed to create draft: {result.get('errmsg')} (Code: {result.get('errcode')})")
        return result["media_id"]

    def update_draft(self, media_id: str, title: str, html_content: str, thumb_media_id: str,
                     index: int = 0, author: str = "Admin", digest: str = "", show_cover_pic: int = 1,
                     need_open_comment: int = 1, only_fans_can_comment: int = 0) -> None:
        article_data = {
            "title": title, "author": author, "digest": digest,
            "content": html_content, "thumb_media_id": thumb_media_id,
            "show_cover_pic": show_cover_pic, "need_open_comment": need_open_comment,
            "only_fans_can_comment": only_fans_can_comment,
            "pic_crop_235_1": "0_0_1_1",
            "pic_crop_1_1": "0_0_1_1"
        }
        update_data = {
            "media_id": media_id, "index": index,
            "articles": article_data
        }
        result = self._post_with_retry("/draft/update", json_data=update_data)
        if result.get("errcode", 0) != 0:
            # Retry without pic_crop fields in case the error is caused by crop parameters
            article_data.pop("pic_crop_235_1", None)
            article_data.pop("pic_crop_1_1", None)
            result = self._post_with_retry("/draft/update", json_data=update_data)
            if result.get("errcode", 0) != 0:
                raise Exception(f"Failed to update draft: {result.get('errmsg')} (Code: {result.get('errcode')})")
