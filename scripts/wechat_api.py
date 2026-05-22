# -*- coding: utf-8 -*-
"""
【已弃用】此模块已迁移为 engine/wechat_api.py。
为了保持向后兼容，此处导出 WeChatClient。
"""
import sys
import os

# Add project root to path if needed
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from engine.wechat_api import WeChatClient
