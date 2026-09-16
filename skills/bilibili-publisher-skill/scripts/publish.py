#!/usr/bin/env python3
"""
publish.py - CLI entry point for bilibili-publisher-skill.

Reads metadata from _wechat.json or Markdown frontmatter, assembles
image list with vertical cover, and uploads to Bilibili Creator Center as draft.

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
        meta = {}
        for line in match.group(1).splitlines():
            if ':' in line and not line.strip().startswith('-'):
                key, val = line.split(':', 1)
                meta[key.strip()] = val.strip().strip('"').strip("'")
        return meta


def load_metadata(meta_path: str) -> dict:
    """Load metadata from a _wechat.json or .md file."""
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


def resolve_title(meta: dict) -> str:
    """Get title for Bilibili article."""
    return meta.get("title", "").strip() or meta.get("social_title", "").strip()


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


def collect_images(image_dir: str, meta: dict, meta_dir: str = None, cover_override: str = None) -> list[str]:
    """Build ordered list of absolute image paths for upload (vertical cover + slices)."""
    img_dir = Path(image_dir)
    if not img_dir.is_dir():
        raise FileNotFoundError(f"切图目录不存在: {image_dir}")

    images = []
    cover_v = None
    if cover_override:
        cover_v = Path(cover_override)
    else:
        search_dirs = []
        if meta_dir:
            search_dirs.append(Path(meta_dir))
        search_dirs.append(img_dir.parent)

        for d in search_dirs:
            candidates = [d / "cover_vertical.png", d / "cover_vertical.jpg"]
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

    card_exts = {'.png', '.jpg', '.jpeg', '.webp'}
    cards = sorted(
        [f for f in img_dir.iterdir() if f.suffix.lower() in card_exts and not f.name.startswith('_')],
        key=lambda f: f.name
    )

    for card in cards:
        images.append(str(card.resolve()))

    if not images:
        raise FileNotFoundError(f"在 {image_dir} 中未找到任何可上传的图片文件。")

    print(f"📋 共 {len(images)} 张图片将按序上传至 B站:")
    for i, img in enumerate(images, 1):
        print(f"   {i}. {Path(img).name}")

    return images


def main():
    parser = argparse.ArgumentParser(description="bilibili-publisher-skill: 上传图文至 B站 创作者中心草稿箱")
    parser.add_argument("-i", "--images", help="切图文件夹路径")
    parser.add_argument("-m", "--metadata", help="元数据文件路径 (_wechat.json 或 .md)")
    parser.add_argument("--title", help="覆盖标题")
    parser.add_argument("--cover", help="覆盖封面图路径")
    parser.add_argument("--login", action="store_true", help="启动浏览器进行扫码登录")
    parser.add_argument("--headed", action="store_true", help="使用有头浏览器（调试用）")

    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ 请先安装 Playwright: pip install playwright && playwright install chromium")
        sys.exit(1)

    if args.login:
        with sync_playwright() as pw:
            from bilibili_uploader import login
            login(pw)
        return

    if not args.images or not args.metadata:
        parser.error("发布模式需要同时指定 -i (切图目录) 和 -m (元数据文件)")

    meta_path = os.path.abspath(args.metadata)
    meta = load_metadata(meta_path)
    meta_dir = os.path.dirname(meta_path)

    title = args.title if args.title else resolve_title(meta)
    print(f"\n📌 B站文章标题: {title}")

    body = build_body_text(meta)
    print(f"📝 正文与话题:\n{body}\n")

    image_paths = collect_images(
        args.images,
        meta,
        meta_dir=meta_dir,
        cover_override=args.cover,
    )

    with sync_playwright() as pw:
        from bilibili_uploader import upload_image_post
        upload_image_post(
            pw,
            image_paths=image_paths,
            title=title,
            body_text=body,
            headless=not args.headed,
        )


if __name__ == "__main__":
    main()
