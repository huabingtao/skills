#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish.py - CLI entry point for xiaohongshu-publisher-skill.

Reads metadata from _wechat.json or Markdown frontmatter, assembles
image list with vertical cover, and uploads to Xiaohongshu as draft
using the social-auto-upload (Patchright) engine.

Usage:
    python3 publish.py -i <image_dir> -m <metadata_file>
    python3 publish.py --login
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

# Add deps/sau_bridge to sys.path
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEPS_DIR = WORKSPACE_DIR / "deps"
if str(DEPS_DIR) not in sys.path:
    sys.path.insert(0, str(DEPS_DIR))

import sau_bridge
from uploader.xiaohongshu_uploader.main import (
    XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
    XiaoHongShuNote,
    xiaohongshu_setup,
    xiaohongshu_logger,
)


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


def resolve_social_title(meta: dict, max_len: int = 20) -> str:
    """Get social title, falling back to truncated main title without brackets."""
    st = meta.get("social_title", "").strip()
    if st:
        return st[:max_len]
    title = meta.get("title", "").strip()
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

    print(f"📋 共 {len(images)} 张图片将按序上传至小红书:")
    for i, img in enumerate(images, 1):
        print(f"   {i}. {Path(img).name}")

    return images


# ─────────────────────────── Patchright Draft Uploader ───────────────────

class XiaoHongShuDraftNote(XiaoHongShuNote):
    """Subclass of XiaoHongShuNote that saves to Draft Box instead of publishing."""

    async def upload_note_content(self, page) -> None:
        from uploader.xiaohongshu_uploader.main import _build_xhs_creator_url

        xiaohongshu_logger.info("🏃 [Patchright] 开始上传小红书图文...")
        publish_url = _build_xhs_creator_url("/publish/publish?from=homepage&target=image")
        await page.goto(publish_url)
        await page.wait_for_url(publish_url)

        upload_input = page.locator('input[type="file"][accept*="image"]').first
        if not await upload_input.count():
            upload_input = page.locator("div[class^='upload-content'] input[class='upload-input']").first

        await upload_input.wait_for(state="attached", timeout=30000)
        xiaohongshu_logger.info("📤 上传图片序列...")
        await upload_input.set_input_files(self.image_paths)

        while True:
            try:
                title_container = page.locator('input[placeholder*="填写标题"]').first
                await title_container.wait_for(state="visible", timeout=3000)
                xiaohongshu_logger.info("🥳 已进入图文编辑页面")
                break
            except Exception:
                await asyncio.sleep(1)

        xiaohongshu_logger.info("✍️ 正在填写标题与正文...")
        await self.fill_meta(page)
        await self.check_original_declaration(page)

        # Enforce saving to Draft Box
        xiaohongshu_logger.info("💾 正在保存至小红书草稿箱...")
        draft_clicked = False
        draft_selectors = [
            "button:has-text('保存草稿')",
            "button:has-text('存草稿')",
            "button:has-text('草稿')",
        ]
        for sel in draft_selectors:
            loc = page.locator(sel)
            if await loc.count() > 0:
                await loc.first.click()
                draft_clicked = True
                xiaohongshu_logger.success("✅ 已成功点击保存草稿按钮")
                break

        if not draft_clicked:
            xiaohongshu_logger.warning("⚠️ 未找到明确的“保存草稿”按钮，为安全起见不自动点击公开“发布”。请在已打开页面中人工点击存草稿。")

        xiaohongshu_logger.info("🔒 遵照用户要求，上传小红书草稿箱完成后保持浏览器开启 600 秒 (10分钟) 供观察与编辑...")
        await asyncio.sleep(600)


# ─────────────────────────── CLI Entry Point ─────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="xiaohongshu-publisher-skill: 上传图文至小红书草稿箱 (Patchright 引擎)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-i", "--images", help="切图文件夹路径")
    parser.add_argument("-m", "--metadata", help="元数据文件路径 (_wechat.json 或 .md)")
    parser.add_argument("--title", help="覆盖标题 (≤20字)")
    parser.add_argument("--cover", help="覆盖竖版封面图路径")
    parser.add_argument("--login", action="store_true", help="启动 Patchright 浏览器扫码登录小红书")
    parser.add_argument("--headed", action="store_true", help="使用有头浏览器界面")
    parser.add_argument("--keep-open", action="store_true", help="上传后保持浏览器开启不立即关闭")

    args = parser.parse_args()

    account_file = sau_bridge.get_cookie_file("xiaohongshu")

    # Login mode
    if args.login:
        print(f"🔑 启动小红书扫码登录，Cookie 将存入: {account_file}")
        res = asyncio.run(xiaohongshu_setup(str(account_file), handle=True, headless=False, return_detail=True))
        if res.get("success"):
            print("🎉 小红书登录成功！Cookie 已更新。")
        else:
            print(f"❌ 登录未完成: {res.get('message')}")
        return

    if not args.images or not args.metadata:
        parser.error("发布模式需要同时指定 -i (切图目录) 和 -m (元数据文件)")

    meta_path = os.path.abspath(args.metadata)
    meta = load_metadata(meta_path)
    meta_dir = os.path.dirname(meta_path)

    title = args.title if args.title else resolve_social_title(meta)
    print(f"\n📌 小红书标题: {title}")

    body = build_body_text(meta)
    print(f"📝 正文预览:\n{body}\n")

    image_paths = collect_images(
        args.images,
        meta,
        meta_dir=meta_dir,
        cover_override=args.cover,
    )

    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    uploader = XiaoHongShuDraftNote(
        image_paths=image_paths,
        note=body,
        tags=tags,
        publish_date=0,
        account_file=str(account_file),
        title=title,
        publish_strategy=XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
        headless=not args.headed,
    )

    print("\n🚀 正在通过 Patchright 引擎上传至小红书草稿箱...")
    asyncio.run(uploader.xiaohongshu_upload_note())
    print("✨ 小红书草稿箱上传完成！")


if __name__ == "__main__":
    main()
