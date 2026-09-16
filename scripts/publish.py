#!/usr/bin/env python3
"""
publish.py - CLI entry point for douyin-publisher-skill.

Reads metadata from _wechat.json or Markdown frontmatter, assembles
image list with optional vertical cover, and uploads to Douyin as draft.

Usage:
    python3 publish.py -i <image_dir> -m <metadata_file>
    python3 publish.py --login
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ─────────────────────────── Metadata parsing ────────────────────────────

def parse_frontmatter(md_path: str) -> dict:
    """Extract YAML frontmatter from a Markdown file."""
    content = Path(md_path).read_text(encoding="utf-8")
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return {}

    try:
        import yaml
        return yaml.safe_load(match.group(1)) or {}
    except ImportError:
        # Minimal fallback parser for key: value lines
        meta = {}
        for line in match.group(1).splitlines():
            if ':' in line and not line.strip().startswith('-'):
                key, val = line.split(':', 1)
                meta[key.strip()] = val.strip().strip('"').strip("'")
        return meta


def load_metadata(meta_path: str) -> dict:
    """
    Load metadata from a _wechat.json or .md file.

    Returns a dict with keys: title, social_title, summary, tags,
    cover, cover_vertical.
    """
    p = Path(meta_path)

    if p.suffix == '.json':
        raw = json.loads(p.read_text(encoding="utf-8"))
    elif p.suffix == '.md':
        raw = parse_frontmatter(str(p))
    else:
        raise ValueError(f"不支持的元数据格式: {p.suffix}（需要 .json 或 .md）")

    return {
        "title": raw.get("title", ""),
        "social_title": raw.get("social_title", ""),
        "summary": raw.get("summary") or raw.get("digest", ""),
        "tags": raw.get("tags") or raw.get("hashtags") or [],
        "cover": raw.get("cover") or raw.get("image", ""),
        "cover_vertical": raw.get("cover_vertical", ""),
    }


def resolve_social_title(meta: dict, max_len: int = 20) -> str:
    """Get social title, falling back to truncated main title."""
    st = meta.get("social_title", "").strip()
    if st:
        return st[:max_len]
    title = meta.get("title", "").strip()
    # Strip 【...】 prefix for shorter social title
    cleaned = re.sub(r'^【[^】]*】', '', title).strip()
    return (cleaned or title)[:max_len]


def build_body_text(meta: dict) -> str:
    """Assemble post body: summary + newline + #tag1 #tag2."""
    parts = []

    summary = meta.get("summary", "").strip()
    if summary:
        parts.append(summary)

    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if tags:
        hashtags = " ".join(f"#{t}" for t in tags)
        parts.append(hashtags)

    return "\n\n".join(parts)


# ─────────────────────────── Image list assembly ─────────────────────────

def collect_images(image_dir: str, meta: dict, meta_dir: str = None, cover_override: str = None) -> list[str]:
    """
    Build ordered list of absolute image paths for upload.

    Order:
      1. cover_vertical.png (if exists) — as the first/cover image
      2. Sliced cards (01_切图.png, 02_切图.png, ...) sorted by name
    """
    img_dir = Path(image_dir)
    if not img_dir.is_dir():
        raise FileNotFoundError(f"切图目录不存在: {image_dir}")

    images = []

    # 1. Resolve vertical cover
    cover_v = None
    if cover_override:
        cover_v = Path(cover_override)
    else:
        # Check metadata directory for cover_vertical.png
        search_dirs = []
        if meta_dir:
            search_dirs.append(Path(meta_dir))
        search_dirs.append(img_dir.parent)  # parent of the slice dir

        for d in search_dirs:
            candidates = [
                d / "cover_vertical.png",
                d / "cover_vertical.jpg",
            ]
            # Also check metadata field
            cv_field = meta.get("cover_vertical", "")
            if cv_field:
                candidates.insert(0, d / cv_field)

            for c in candidates:
                if c.exists():
                    cover_v = c
                    break
            if cover_v:
                break

    if cover_v and cover_v.exists():
        images.append(str(cover_v.resolve()))
        print(f"📸 封面图: {cover_v.name}")

    # 2. Collect sliced cards, sorted by filename
    card_exts = {'.png', '.jpg', '.jpeg', '.webp'}
    cards = sorted(
        [f for f in img_dir.iterdir() if f.suffix.lower() in card_exts and not f.name.startswith('_')],
        key=lambda f: f.name
    )

    for card in cards:
        images.append(str(card.resolve()))

    if not images:
        raise FileNotFoundError(f"在 {image_dir} 中未找到任何可上传的图片文件。")

    print(f"📋 共 {len(images)} 张图片将按序上传:")
    for i, img in enumerate(images, 1):
        print(f"   {i}. {Path(img).name}")

    return images


# ─────────────────────────── CLI entry point ─────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="douyin-publisher-skill: 上传图文至抖音草稿箱",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 publish.py -i /path/to/原生网页直切图_3x4 -m /path/to/article_wechat.json
  python3 publish.py -i /path/to/原生网页直切图_3x4 -m /path/to/article.md --title "自定义标题"
  python3 publish.py --login
        """,
    )
    parser.add_argument("-i", "--images", help="切图文件夹路径")
    parser.add_argument("-m", "--metadata", help="元数据文件路径 (_wechat.json 或 .md)")
    parser.add_argument("--title", help="覆盖标题 (≤20字)")
    parser.add_argument("--cover", help="覆盖竖版封面图路径")
    parser.add_argument("--login", action="store_true", help="启动浏览器进行扫码登录")
    parser.add_argument("--headed", action="store_true", help="使用有头浏览器（调试用）")

    args = parser.parse_args()

    # Import Playwright
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ 请先安装 Playwright:")
        print("   pip install playwright")
        print("   playwright install chromium")
        sys.exit(1)

    # Login mode
    if args.login:
        with sync_playwright() as pw:
            from douyin_uploader import login
            login(pw)
        return

    # Publish mode — require images and metadata
    if not args.images or not args.metadata:
        parser.error("发布模式需要同时指定 -i (切图目录) 和 -m (元数据文件)")

    # Load metadata
    meta_path = os.path.abspath(args.metadata)
    meta = load_metadata(meta_path)
    meta_dir = os.path.dirname(meta_path)

    # Resolve title
    title = args.title if args.title else resolve_social_title(meta)
    print(f"\n📌 标题: {title}")

    # Build body text
    body = build_body_text(meta)
    print(f"📝 正文预览:\n{body}\n")

    # Collect images
    image_paths = collect_images(
        args.images,
        meta,
        meta_dir=meta_dir,
        cover_override=args.cover,
    )

    # Upload
    with sync_playwright() as pw:
        from douyin_uploader import upload_image_post
        upload_image_post(
            pw,
            image_paths=image_paths,
            title=title,
            body_text=body,
            headless=not args.headed,
        )


if __name__ == "__main__":
    main()
