import os
import sys
import json
import argparse
import re
import requests
import tempfile
import hashlib
from wechat_api import WeChatClient

CACHE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.wechat_image_cache.json'))

def get_file_md5(file_path):
    """
    Computes the MD5 hash of a file.
    """
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

def load_cache():
    """
    Loads MD5 cache from JSON.
    """
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"content_images": {}, "thumb_materials": {}}

def save_cache(cache):
    """
    Saves MD5 cache to JSON.
    """
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠ Failed to save cache: {e}")

def process_content_images(client, html_content, base_dir, cache):
    """
    Finds all <img> tags, uploads local/remote images to WeChat CDN, 
    and replaces the src attributes. Utilizes MD5 caching to skip duplicate uploads.
    """
    # Pattern to find src in <img> tags
    img_pattern = r'<img([^>]*?)src=["\']([^"\']+)["\']([^>]*?)>'
    
    def replacer(match):
        prefix = match.group(1)
        src = match.group(2)
        suffix = match.group(3)
        
        # Skip if already a WeChat URL
        if "mmbiz.qpic.cn" in src:
            return match.group(0)
            
        temp_file = None
        try:
            if src.startswith(('http://', 'https://')):
                # External URL: Download to temp file
                print(f"  → Downloading remote image: {src[:50]}...")
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
                # Local path
                # Try unquoting URL-encoded path characters
                import urllib.parse
                clean_src = urllib.parse.unquote(src)
                
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                potential_paths = [
                    os.path.join(base_dir, clean_src.lstrip('/')),
                    os.path.join(project_root, clean_src.lstrip('/')),
                    clean_src
                ]
                upload_path = None
                for path in potential_paths:
                    if os.path.exists(path) and os.path.isfile(path):
                        upload_path = path
                        break
                    
                if not upload_path:
                    print(f"  ⚠ Local image not found: {src}")
                    return match.group(0)

            # Compute MD5 and check cache
            md5_val = get_file_md5(upload_path)
            if md5_val and md5_val in cache["content_images"]:
                wechat_url = cache["content_images"][md5_val]
                print(f"  ⚡ Cache hit for {os.path.basename(upload_path)}: {wechat_url[:50]}...")
                return f'<img{prefix}src="{wechat_url}"{suffix}>'

            # Upload to WeChat CDN
            print(f"  → Uploading to WeChat CDN: {os.path.basename(upload_path)}...")
            wechat_url = client.upload_content_image(upload_path)
            print(f"  ✅ Uploaded. URL: {wechat_url[:50]}...")
            
            # Save to cache
            if md5_val:
                cache["content_images"][md5_val] = wechat_url
                save_cache(cache)
                
            return f'<img{prefix}src="{wechat_url}"{suffix}>'
            
        except Exception as e:
            print(f"  ⚠ Error processing image {src}: {e}")
            return match.group(0)
        finally:
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)

    return re.sub(img_pattern, replacer, html_content)

def load_config():
    """Load config from a standard location or local directory."""
    config_paths = [
        'config.json',
        os.path.join(os.path.dirname(__file__), 'config.json'),
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
    """Interactively ask user for WeChat credentials and remind about IP whitelist."""
    print("\n" + "!"*60)
    print("🛠️  WECHAT OFFICIAL ACCOUNT SETUP")
    print("!"*60)
    print("To publish drafts, you need credentials from the WeChat Admin Platform.")
    print("Location: Settings & Development > Basic Configuration")
    print("\n🚨 CRITICAL STEP:")
    print("You MUST add your server/local IP to the 'IP Whitelist' in the")
    print("WeChat Admin Platform, otherwise the API will reject all requests.")
    print("!"*60 + "\n")
    
    appid = input("Enter your WeChat AppID: ").strip()
    appsecret = input("Enter your WeChat AppSecret: ").strip()
    
    if not appid or not appsecret:
        return None, None
        
    save = input("\nSave these credentials to scripts/config.json for future use? (y/n): ")
    if save.lower() == 'y':
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"appid": appid, "appsecret": appsecret}, f, indent=2)
            print(f"✅ Configuration saved to: {config_path}")
        except Exception as e:
            print(f"⚠ Warning: Could not save config file: {e}")
            
    return appid, appsecret

def main():
    parser = argparse.ArgumentParser(description="Universal WeChat Official Account Draft Publisher")
    parser.add_argument("-t", "--title", help="Article title (auto-detected if missing)")
    parser.add_argument("-c", "--content", help="Path to the HTML content file")
    parser.add_argument("--cover", help="Path to the cover image file (auto-detected if missing)")
    parser.add_argument("-a", "--author", help="Article author (auto-detected if missing, default: 弹壳呱呱)")
    parser.add_argument("--appid", help="WeChat AppID (overrides config)")
    parser.add_argument("--secret", help="WeChat AppSecret (overrides config)")
    parser.add_argument("--test-config", action="store_true", help="Validate WeChat API configuration and credentials without publishing")

    args = parser.parse_args()

    # Resolve credentials
    config = load_config()
    appid = args.appid or os.environ.get('WECHAT_APPID') or config.get('appid')
    appsecret = args.secret or os.environ.get('WECHAT_APPSECRET') or config.get('appsecret')

    if args.test_config:
        if not appid or not appsecret:
            print("🔍 No credentials found in config/env. Initiating setup...")
            appid, appsecret = setup_interactive_config()
            if not appid or not appsecret:
                print("❌ Error: AppID and AppSecret are required to test configuration.")
                sys.exit(1)
        
        print("\n" + "="*50)
        print("🔍 TESTING WECHAT CONFIGURATION")
        print("="*50)
        print(f"AppID: {appid}")
        print("Connecting to WeChat API...")
        try:
            client = WeChatClient(appid, appsecret)
            # Force refresh to make sure we hit the API
            token = client.get_access_token(force_refresh=True)
            print("✅ CONNECTION SUCCESSFUL!")
            print(f"Successfully obtained Access Token: {token[:10]}...{token[-10:]}")
            print("Please ensure your IP is whitelisted in WeChat Admin Platform if you encounter issues later.")
            print("="*50)
            sys.exit(0)
        except Exception as e:
            print(f"❌ CONNECTION FAILED: {e}")
            print("="*50)
            sys.exit(1)

    if not args.content:
        print("❌ Error: Path to the HTML content file is required. Provide via -c/--content.")
        parser.print_help()
        sys.exit(1)

    if not os.path.exists(args.content):
        print(f"❌ Error: Content file not found: {args.content}")
        sys.exit(1)

    # Try to load metadata from sibling JSON file (generated by md_to_wechat.py)
    metadata = {}
    meta_path = os.path.splitext(args.content)[0] + ".json"
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            print(f"✅ Loaded metadata from {meta_path}")
        except Exception as e:
            print(f"⚠ Warning: Failed to load metadata file: {e}")

    # Resolve Article Info (Arg > Metadata > Default)
    title = args.title or metadata.get('title')
    author = args.author or metadata.get('author') or "弹壳呱呱"
    cover_path = args.cover or metadata.get('image')
    
    # Handle relative image path in frontmatter
    if cover_path:
        import urllib.parse
        cover_path = urllib.parse.unquote(cover_path)
        if not os.path.isabs(cover_path) and not os.path.exists(cover_path):
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            potential_paths = [
                os.path.join(os.path.dirname(args.content), cover_path.lstrip('/')),
                os.path.join(project_root, cover_path.lstrip('/')),
            ]
            for path in potential_paths:
                if os.path.exists(path):
                    cover_path = path
                    break

    if not title:
        print("❌ Error: Article title is required. Provide via --title or Frontmatter.")
        sys.exit(1)
        
    if not cover_path:
        print("❌ Error: Cover image is required. Provide via --cover or Frontmatter.")
        sys.exit(1)

    if not os.path.exists(cover_path):
        print(f"❌ Error: Cover image not found: {cover_path}")
        sys.exit(1)

    if not appid or not appsecret:
        appid, appsecret = setup_interactive_config()
        if not appid or not appsecret:
            print("❌ Error: WeChat credentials are required to proceed.")
            sys.exit(1)

    # Confirmation Prompt
    print("\n" + "="*50)
    print("🚀 PRE-FLIGHT CHECK")
    print("="*50)
    print(f"Title:  {title}")
    print(f"Author: {author}")
    print(f"Cover:  {cover_path}")
    print(f"HTML:   {args.content}")
    print("="*50)
    
    confirm = input("\nReady to push to WeChat Official Account Drafts? (y/n): ")
    if confirm.lower() != 'y':
        print("❌ Upload cancelled by user.")
        sys.exit(0)

    client = WeChatClient(appid, appsecret)
    cache = load_cache()

    try:
        # 1. Upload Cover (with Cache)
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
                save_cache(cache)

        # 2. Read Content
        with open(args.content, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        # 3. Process and Upload content images (with Cache)
        print("→ Processing content images...")
        html_content = process_content_images(client, html_content, os.path.dirname(os.path.abspath(args.content)), cache)

        # 4. Create Draft
        print(f"→ Creating draft: '{title}'...")
        digest = metadata.get('summary') or metadata.get('digest') or ""
        draft_media_id = client.create_draft(
            title=title,
            html_content=html_content,
            thumb_media_id=thumb_media_id,
            author=author,
            digest=digest
        )
        
        print("\n" + "="*40)
        print("🚀 PUBLISH SUCCESSFUL!")
        print(f"Draft MediaID: {draft_media_id}")
        print("="*40)
        print("您现在可以前往微信公众号后台“草稿箱”查看。")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
