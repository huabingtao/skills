# -*- coding: utf-8 -*-
"""
Engine package for danke-strategy-skill.
Provides Markdown-to-WeChat HTML conversion, highlight rules, and publishing utilities.
"""

from .compiler import convert_to_wechat_html
from .highlight import load_highlight_rules, apply_highlight_rules
from .utils import scan_assets, ensure_placeholder_exists, load_image_mapping, clear_scan_assets_cache
