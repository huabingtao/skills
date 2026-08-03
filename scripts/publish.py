#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wechat-publisher-skill: Universal WeChat Official Account Draft Publisher

Accepts any compiled _wechat.html + sidecar metadata JSON,
uploads images to WeChat CDN, and creates/updates a draft in the account's 草稿箱.

Usage:
    python3 publish.py -c <path_to_wechat.html> [--cover <cover.png>] [--new]

Credentials are read from (in order):
    1. --appid / --secret CLI args
    2. WECHAT_APPID / WECHAT_APPSECRET environment variables
    3. scripts/config.json  ({"appid": "...", "appsecret": "..."})
    4. ~/.wechat_config.json
"""

import os
import sys
import json
import argparse
import re
import hashlib
import tempfile
import urllib.parse
from dataclasses import dataclass

import requests

# Resolve wechat_api.py from the same scripts/ directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wechat_api import WeChatClient


@dataclass
class PublishResult:
    media_id: str = None
    action: str = None
    skipped: bool = False


# ─────────────────────────────── Cache helpers ────────────────────────────────

def get_file_md5(file_path):
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return None
    md5_hash = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                md5_hash.update(byte_block)
        return md5_hash.hexdigest()
    except Exception as e:
        print(f"  ⚠ Failed to compute MD5 for {file_path}: {e}")
        return None


def load_cache(cache_file):
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"content_images": {}, "thumb_materials": {}}


def save_cache(cache, cache_file):
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠ Failed to save cache: {e}")


def load_draft_cache(draft_cache_file):
    if os.path.exists(draft_cache_file):
        try:
            with open(draft_cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_draft_cache(cache, draft_cache_file):
    try:
        with open(draft_cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠ Failed to save draft cache: {e}")


# ─────────────────────────────── Image processing ────────────────────────────

def process_content_images(client, html_content, base_dir, cache, cache_file):
    """
    Finds all <img> tags, uploads local/remote images to WeChat CDN,
    and replaces src attributes. Uses MD5 caching to skip duplicate uploads.
    """
    img_pattern = r'<img([^>]*?)src=["\']([^"\']+)["\']([^>]*?)>'

    def replacer(match):
        prefix = match.group(1)
        src = match.group(2)
        suffix = match.group(3)

        if "mmbiz.qpic.cn" in src:
            return match.group(0)

        temp_file = None
        try:
            if src.startswith('data:image/'):
                header, base64_data = src.split(',', 1)
                ext = '.png'
                if 'image/jpeg' in header or 'image/jpg' in header:
                    ext = '.jpg'
                elif 'image/gif' in header:
                    ext = '.gif'
                elif 'image/webp' in header:
                    ext = '.webp'
                import base64
                img_bytes = base64.b64decode(base64_data)
                fd, temp_path = tempfile.mkstemp(suffix=ext)
                with os.fdopen(fd, 'wb') as tmp:
                    tmp.write(img_bytes)
                temp_file = temp_path
                upload_path = temp_path

            elif src.startswith(('http://', 'https://')):
                print(f"  → Downloading remote image: {src[:60]}...")
                response = requests.get(src, timeout=10)
                if response.status_code == 200:
                    ext = os.path.splitext(src.split('?')[0])[1] or '.jpg'
                    fd, temp_path = tempfile.mkstemp(suffix=ext)
                    with os.fdopen(fd, 'wb') as tmp:
                        tmp.write(response.content)
                    temp_file = temp_path
                    upload_path = temp_path
                else:
                    print(f"  ⚠ Failed to download image: {src}")
                    return match.group(0)
            else:
                clean_src = urllib.parse.unquote(src)
                potential_paths = [
                    os.path.join(base_dir, clean_src.lstrip('/')),
                    clean_src
                ]
                upload_path = None
                for path in potential_paths:
                    if os.path.exists(path) and os.path.isfile(path):
                        upload_path = path
                        break

                if not upload_path:
                    # Fallback: walk base_dir for a file with matching suffix
                    norm_src = clean_src.replace('\\', '/')
                    for r, d, files in os.walk(base_dir):
                        d[:] = [dn for dn in d if dn not in ('venv', '.venv', '.git', '__pycache__', 'node_modules')]
                        for f in files:
                            full_f = os.path.join(r, f).replace('\\', '/')
                            if full_f.endswith(norm_src):
                                upload_path = os.path.join(r, f)
                                break
                        if upload_path:
                            break

                if not upload_path:
                    print(f"  ⚠ Local image not found: {src}")
                    return match.group(0)

            md5_val = get_file_md5(upload_path)
            if md5_val and md5_val in cache["content_images"]:
                wechat_url = cache["content_images"][md5_val]
                print(f"  ⚡ Cache hit for {os.path.basename(upload_path)}: {wechat_url[:50]}...")
                return f'<img{prefix}src="{wechat_url}"{suffix}>'

            print(f"  → Uploading to WeChat CDN: {os.path.basename(upload_path)}...")
            wechat_url = client.upload_content_image(upload_path)
            print(f"  ✅ Uploaded. URL: {wechat_url[:50]}...")

            if md5_val:
                cache["content_images"][md5_val] = wechat_url
                save_cache(cache, cache_file)

            return f'<img{prefix}src="{wechat_url}"{suffix}>'

        except Exception as e:
            print(f"  ⚠ Error processing image {src}: {e}")
            return match.group(0)
        finally:
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)

    return re.sub(img_pattern, replacer, html_content)


# ─────────────────────────────── Config & credentials ────────────────────────

def load_config():
    """Load credentials from standard config locations."""
    config_paths = [
        'config.json',
        'scripts/config.json',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json'),
        os.path.expanduser('~/.wechat_config.json')
    ]
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠ Warning: Failed to parse config file '{path}': {e}")
    return {}


def setup_interactive_config():
    """Interactively prompt for credentials and optionally save them."""
    print("\n" + "!"*60)
    print("🛠️  WECHAT OFFICIAL ACCOUNT SETUP")
    print("!"*60)
    print("You need credentials from the WeChat Admin Platform.")
    print("\n🚨 CRITICAL: Add your server IP to the 'IP Whitelist' in WeChat Admin!")
    print("!"*60 + "\n")

    appid = input("Enter your WeChat AppID: ").strip()
    appsecret = input("Enter your WeChat AppSecret: ").strip()

    if not appid or not appsecret:
        return None, None

    save = input("\nSave to scripts/config.json for future use? (y/n): ")
    if save.lower() == 'y':
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"appid": appid, "appsecret": appsecret}, f, indent=2)
            print(f"✅ Credentials saved to: {config_path}")
        except Exception as e:
            print(f"⚠ Warning: Could not save config file: {e}")

    return appid, appsecret


# ─────────────────────────────── Core publish function ───────────────────────

def load_content_metadata(content_path):
    """Loads sidecar metadata JSON for a compiled HTML file."""
    metadata = {}
    meta_path = os.path.splitext(content_path)[0] + ".json"
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            print(f"✅ Loaded metadata from {meta_path}")
        except Exception as e:
            print(f"⚠ Warning: Failed to load metadata file: {e}")
    return metadata


def resolve_cover_path(cover_path, content_path):
    """Resolves a cover path relative to the content file."""
    if not cover_path:
        return cover_path

    cover_path = urllib.parse.unquote(cover_path)
    if os.path.isabs(cover_path) and os.path.exists(cover_path):
        return cover_path

    base = os.path.dirname(os.path.abspath(content_path))
    potential_paths = [
        os.path.join(base, cover_path.lstrip('/')),
    ]
    for path in potential_paths:
        if os.path.exists(path):
            return path

    norm_cover = cover_path.replace('\\', '/')
    for root, dirs, files in os.walk(base):
        dirs[:] = [dn for dn in dirs if dn not in ('venv', '.venv', '.git', '__pycache__', 'node_modules')]
        for filename in files:
            full_file = os.path.join(root, filename).replace('\\', '/')
            if full_file.endswith(norm_cover):
                return os.path.join(root, filename)
    return cover_path


def publish_draft(
    content_path,
    title=None,
    cover_path=None,
    author=None,
    appid=None,
    appsecret=None,
    cache_dir=None,
    force_new=False,
    client_cls=None,
):
    """
    Publishes or updates a WeChat draft from any compiled HTML file.

    Args:
        content_path: Path to _wechat.html file (sidecar .json auto-detected)
        title:        Article title (auto-read from sidecar JSON if omitted)
        cover_path:   Cover image path (auto-read from sidecar JSON if omitted)
        author:       Author name (default: read from sidecar JSON)
        appid:        WeChat AppID
        appsecret:    WeChat AppSecret
        cache_dir:    Directory for caching token/image MD5 (default: same as HTML)
        force_new:    Force creating a brand-new draft (ignore existing media_id)
        client_cls:   Injectable WeChatClient (for testing)
    """
    if not content_path:
        raise ValueError("Path to the HTML content file is required.")
    if not os.path.exists(content_path):
        raise FileNotFoundError(f"Content file not found: {content_path}")
    if not appid or not appsecret:
        raise ValueError("WeChat credentials (appid + appsecret) are required.")

    cache_dir = cache_dir or os.path.dirname(os.path.abspath(content_path))
    os.makedirs(cache_dir, exist_ok=True)

    cache_file = os.path.join(cache_dir, '.wechat_image_cache.json')
    draft_cache_file = os.path.join(cache_dir, '.wechat_draft_cache.json')

    metadata = load_content_metadata(content_path)
    title = title or metadata.get('title')
    author = author or metadata.get('author') or "弹壳呱呱"
    cover_path = resolve_cover_path(cover_path or metadata.get('image'), content_path)

    if not title:
        raise ValueError("Article title is required. Provide via --title or sidecar .json.")
    if not cover_path or not os.path.exists(cover_path):
        raise FileNotFoundError(f"Cover image not found: {cover_path}")

    html_abs_path = os.path.abspath(content_path)
    draft_cache = load_draft_cache(draft_cache_file)
    cached_entry = draft_cache.get(html_abs_path)

    existing_media_id = cached_html_hash = cached_cover_hash = None
    if not force_new and cached_entry:
        if isinstance(cached_entry, dict):
            existing_media_id = cached_entry.get("media_id")
            cached_html_hash = cached_entry.get("html_hash")
            cached_cover_hash = cached_entry.get("cover_hash")
        else:
            existing_media_id = cached_entry

    print("\n" + "="*50)
    print("🚀 PRE-FLIGHT CHECK")
    print("="*50)
    print(f"Title:  {title}")
    print(f"Author: {author}")
    print(f"Cover:  {cover_path}")
    print(f"HTML:   {content_path}")
    if existing_media_id:
        print(f"Action: Update existing draft (MediaID: {existing_media_id})")
    else:
        print("Action: Create new draft")
    print("="*50)

    client_cls = client_cls or WeChatClient
    client = client_cls(appid, appsecret, cache_dir=cache_dir)
    cache = load_cache(cache_file)

    cover_md5 = get_file_md5(cover_path)
    if cover_md5 and cover_md5 in cache["thumb_materials"]:
        thumb_media_id = cache["thumb_materials"][cover_md5]
        print(f"⚡ Cover cache hit. MediaID: {thumb_media_id}")
    else:
        print(f"→ Uploading cover: {os.path.basename(cover_path)}...")
        thumb_media_id = client.upload_image(cover_path, is_thumb=True)
        print(f"✅ Cover uploaded. MediaID: {thumb_media_id}")
        if cover_md5:
            cache["thumb_materials"][cover_md5] = thumb_media_id
            save_cache(cache, cache_file)

    with open(content_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    print("→ Processing content images...")
    html_content = process_content_images(
        client, html_content,
        os.path.dirname(html_abs_path),
        cache, cache_file
    )
    try:
        with open(content_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"  ✅ Saved updated HTML with WeChat CDN image URLs to: {content_path}")
    except Exception as e:
        print(f"  ⚠ Could not save updated CDN HTML back to disk: {e}")

    current_html_hash = hashlib.md5(html_content.encode('utf-8')).hexdigest()
    current_cover_hash = cover_md5

    if (not force_new and existing_media_id
            and cached_html_hash == current_html_hash
            and cached_cover_hash == current_cover_hash):
        print("\n⚡ Draft is already up-to-date on WeChat!")
        print(f"Skipping draft update for '{title}' (MediaID: {existing_media_id})")
        print("="*40)
        return PublishResult(media_id=existing_media_id, action="skip", skipped=True)

    digest = metadata.get('summary') or metadata.get('digest') or ""
    need_open_comment = metadata.get('need_open_comment', 1)
    only_fans_can_comment = metadata.get('only_fans_can_comment', 0)

    def save_current_draft(draft_media_id):
        draft_cache[html_abs_path] = {
            "media_id": draft_media_id,
            "html_hash": current_html_hash,
            "cover_hash": current_cover_hash
        }
        save_draft_cache(draft_cache, draft_cache_file)

    if existing_media_id:
        try:
            print(f"→ Updating draft '{title}' with MediaID: {existing_media_id}...")
            client.update_draft(
                media_id=existing_media_id, title=title,
                html_content=html_content, thumb_media_id=thumb_media_id,
                author=author, digest=digest,
                need_open_comment=need_open_comment,
                only_fans_can_comment=only_fans_can_comment
            )
            save_current_draft(existing_media_id)
            print("\n" + "="*40)
            print("🚀 DRAFT UPDATE SUCCESSFUL!")
            print(f"Draft MediaID: {existing_media_id}")
            print("="*40)
            print("您现在可以前往微信公众号后台‘草稿箱’查看。")
            return PublishResult(media_id=existing_media_id, action="update")
        except Exception as e:
            if "invalid media_id" not in str(e).lower() and "40007" not in str(e):
                raise
            print(f"\n⚠ Warning: Existing draft MediaID {existing_media_id} not found (may have been deleted).")
            print(f"→ Falling back to create a new draft instead: '{title}'...")
    else:
        print(f"→ Creating draft: '{title}'...")

    draft_media_id = client.create_draft(
        title=title, html_content=html_content,
        thumb_media_id=thumb_media_id, author=author, digest=digest,
        need_open_comment=need_open_comment,
        only_fans_can_comment=only_fans_can_comment
    )
    save_current_draft(draft_media_id)

    print("\n" + "="*40)
    print("🚀 DRAFT CREATION SUCCESSFUL!")
    print(f"Draft MediaID: {draft_media_id}")
    print("="*40)
    print("您现在可以前往微信公众号后台‘草稿箱’查看。")
    return PublishResult(media_id=draft_media_id, action="create")


# ─────────────────────────────── CLI entry point ─────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="wechat-publisher-skill: Publish any _wechat.html to WeChat 草稿箱",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 publish.py -c article_wechat.html
  python3 publish.py -c article_wechat.html --cover cover.png --new
  python3 publish.py --test-config
        """
    )
    parser.add_argument("-c", "--content", help="Path to compiled _wechat.html")
    parser.add_argument("-t", "--title", help="Article title (auto-detected if missing)")
    parser.add_argument("--cover", help="Cover image path (auto-detected from sidecar .json)")
    parser.add_argument("-a", "--author", help="Author name (auto-detected if missing)")
    parser.add_argument("--appid", help="WeChat AppID (overrides config)")
    parser.add_argument("--secret", help="WeChat AppSecret (overrides config)")
    parser.add_argument("--new", action="store_true", help="Force creating a new draft")
    parser.add_argument("--cache-dir", default=None, help="Cache directory (default: same as HTML)")
    parser.add_argument("--test-config", action="store_true", help="Test credentials and connection")

    args = parser.parse_args()

    config = load_config()
    appid = args.appid or os.environ.get('WECHAT_APPID') or config.get('appid')
    appsecret = args.secret or os.environ.get('WECHAT_APPSECRET') or config.get('appsecret')

    if args.test_config:
        if not appid or not appsecret:
            print("🔍 No credentials found. Initiating setup...")
            appid, appsecret = setup_interactive_config()
            if not appid or not appsecret:
                print("❌ Error: AppID and AppSecret are required.")
                sys.exit(1)

        print("\n" + "="*50)
        print("🔍 TESTING WECHAT CONFIGURATION")
        print("="*50)
        try:
            client = WeChatClient(appid, appsecret, cache_dir=args.cache_dir or ".")
            token = client.get_access_token(force_refresh=True)
            print("✅ CONNECTION SUCCESSFUL!")
            print(f"Access Token: {token[:10]}...{token[-10:]}")
            sys.exit(0)
        except Exception as e:
            print(f"❌ CONNECTION FAILED: {e}")
            sys.exit(1)

    if not args.content:
        print("❌ Error: --content / -c is required.")
        parser.print_help()
        sys.exit(1)

    if not appid or not appsecret:
        appid, appsecret = setup_interactive_config()
        if not appid or not appsecret:
            print("❌ Error: WeChat credentials are required.")
            sys.exit(1)

    try:
        publish_draft(
            content_path=args.content,
            title=args.title,
            cover_path=args.cover,
            author=args.author,
            appid=appid,
            appsecret=appsecret,
            cache_dir=args.cache_dir,
            force_new=args.new,
        )
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
