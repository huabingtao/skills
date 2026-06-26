# -*- coding: utf-8 -*-
"""
Utility functions for asset scanning, placeholder image generation, and image mapping.
Extracted from scripts/md_to_wechat.py.
"""

import os
import re
import struct
import zlib
import json


_SCAN_ASSETS_CACHE = {}


def scan_assets(assets_dir):
    """
    Scans the assets directory recursively and returns a dict mapping
    {filename_without_extension.lower(): absolute_path}
    and {filename.lower(): absolute_path}

    Unlike the original script version which computed paths relative to a
    hardcoded project root, this version stores absolute paths so callers
    can decide how to relativize them.
    """
    if not assets_dir:
        return {}

    abs_dir = os.path.abspath(assets_dir)
    if abs_dir in _SCAN_ASSETS_CACHE:
        return _SCAN_ASSETS_CACHE[abs_dir].copy()

    assets_cache = {}
    if not os.path.exists(abs_dir):
        return assets_cache

    for root, dirs, files in os.walk(abs_dir):
        # Prune directories in-place to avoid walking down env or git directories
        dirs[:] = [d for d in dirs if d not in ('venv', '.venv', '.git', '__pycache__', 'node_modules')]
        for file in files:
            if file.startswith('.'):
                continue
            name, ext = os.path.splitext(file)
            abs_path = os.path.join(root, file)
            assets_cache[name.lower()] = abs_path
            assets_cache[file.lower()] = abs_path

    _SCAN_ASSETS_CACHE[abs_dir] = assets_cache
    return assets_cache.copy()


def clear_scan_assets_cache():
    """
    Clears the scan_assets static cache.
    Useful for tests or manual invalidation.
    """
    global _SCAN_ASSETS_CACHE
    _SCAN_ASSETS_CACHE.clear()


def ensure_placeholder_exists(placeholder_dir):
    """
    Ensures 占位图.png exists in the given directory.
    If not, generates a 100x100 light grey PNG (#E0E0E0) dynamically.

    Args:
        placeholder_dir: Directory where the placeholder image should reside.

    Returns:
        The absolute path to the placeholder image.
    """
    path = os.path.join(placeholder_dir, "占位图.png")
    if not os.path.exists(path):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # 100x100 light grey PNG (#E0E0E0)
            png_data = b'\x89PNG\r\n\x1a\n'
            ihdr_data = struct.pack('>IIBBBB B', 100, 100, 8, 6, 0, 0, 0)
            png_data += struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', zlib.crc32(b'IHDR' + ihdr_data))
            row = b'\x00' + b'\xe0\xe0\xe0\xff' * 100
            raw_data = row * 100
            compressed_data = zlib.compress(raw_data)
            png_data += struct.pack('>I', len(compressed_data)) + b'IDAT' + compressed_data + struct.pack('>I', zlib.crc32(b'IDAT' + compressed_data))
            png_data += struct.pack('>I', 0) + b'IEND' + struct.pack('>I', zlib.crc32(b'IEND'))
            with open(path, 'wb') as f:
                f.write(png_data)
            print("✅ Placeholder image created at:", path)
        except Exception as e:
            print(f"⚠ Warning: Failed to create placeholder image: {e}")
    return path


def load_image_mapping(mapping_path):
    """
    Parses image_mapping.json (or legacy image_mapping.md) to build a dictionary of {keyword: image_path}.

    For JSON, the file is expected to be a simple dictionary mapping keys to values.
    For legacy markdown, it is expected to contain Markdown table rows of the form:
        | **【keyword】** | `![alt](path)` |

    Args:
        mapping_path: Absolute path to the image_mapping.json/md file.

    Returns:
        A dict mapping keyword strings to image path strings.
    """
    mapping = {}
    if not os.path.exists(mapping_path):
        return mapping

    if mapping_path.endswith('.json'):
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
        except Exception as e:
            print(f"⚠ Warning: Failed to parse JSON image mapping: {e}")
        return mapping

    line_pattern = re.compile(r'^\s*\|\s*(?:\*\*)?【?([^】\*]+)】?(?:\*\*)?\s*\|\s*`?!\s*\[[^\]]*\]\(([^)]+)\)`?\s*\|')

    try:
        with open(mapping_path, 'r', encoding='utf-8') as f:
            for line in f:
                match = line_pattern.match(line)
                if match:
                    key = match.group(1).strip()
                    path = match.group(2).strip()
                    mapping[key] = path
    except Exception as e:
        print(f"⚠ Warning: Failed to parse image mapping dictionary: {e}")

    return mapping
