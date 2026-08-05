#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish.py - CLI entry point for douyin-publisher-skill.

Reads metadata from _wechat.json or Markdown frontmatter, assembles
image list with optional vertical cover, and uploads to Douyin as draft
using the social-auto-upload (Patchright) engine with strict assertions
for title, description, tags, images, and draft saving.

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
from uploader.douyin_uploader.main import (
    DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
    DouYinNote,
    douyin_setup,
    douyin_logger,
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
    """Get social title, falling back to truncated main title."""
    st = meta.get("social_title", "").strip()
    if st:
        return st[:max_len]
    title = meta.get("title", "").strip()
    cleaned = re.sub(r'^【[^】]*】', '', title).strip()
    return (cleaned or title)[:max_len]


def build_body_text(meta: dict) -> str:
    """Assemble post body: summary text."""
    summary = meta.get("summary", "").strip()
    return summary


def collect_images(image_dir: str, meta: dict, meta_dir: str = None, cover_override: str = None) -> list[str]:
    """Build ordered list of absolute image paths for upload."""
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
            candidates = [
                d / "cover_vertical.png",
                d / "cover_vertical.jpg",
            ]
            cv_field = meta.get("cover_vertical", "")
            if cv_field:
                candidates.insert(0, d / cv_field)

            for c in candidates:
                if c.exists():
                    cover_v = c
                    break
            if cover_v:
                break

    if cover_v and cover_v.exists() and cover_v.suffix.lower() != '.webp':
        images.append(str(cover_v.resolve()))
        print(f"📸 封面图: {cover_v.name}")

    card_exts = {'.png', '.jpg', '.jpeg'}
    cards = sorted(
        [f for f in img_dir.rglob('*') if f.is_file() and f.suffix.lower() in card_exts and not f.name.startswith('_')],
        key=lambda f: f.name
    )

    for card in cards:
        card_str = str(card.resolve())
        if card_str not in images:
            images.append(card_str)

    if not images:
        raise FileNotFoundError(f"在 {image_dir} 中未找到任何可上传的 .png/.jpg/.jpeg 图片文件。")

    print(f"📋 共 {len(images)} 张图片将按序上传:")
    for i, img in enumerate(images, 1):
        print(f"   {i}. {Path(img).name}")

    return images


# ─────────────────────────── Patchright Draft Uploader ───────────────────

class DouYinDraftNote(DouYinNote):
    """Subclass of DouYinNote that saves to Draft Box with strict verification assertions."""

    def __init__(self, *args, keep_open: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.keep_open = keep_open

    async def upload_note_content(self, page) -> None:
        douyin_logger.info("🏃 [Patchright] 正在准备上传抖音图文...")

        # 1. 明确等待并点击‘发布图文’ Tab
        douyin_logger.info("🔀 正在切换至‘发布图文’Tab...")
        try:
            tab_post = page.get_by_text("发布图文", exact=True).first
            await tab_post.wait_for(state="visible", timeout=15000)
            await tab_post.click()
            await page.wait_for_timeout(1500)
        except Exception as e:
            douyin_logger.warning(f"切换发布图文Tab提醒: {e}")

        # 2. 清理‘放弃’未完成草稿提示
        try:
            abandon_btn = page.locator("text='放弃'")
            if await abandon_btn.count() > 0:
                douyin_logger.info("🧹 发现未完成草稿拦截提示，点击‘放弃’...")
                await abandon_btn.first.click()
                await page.wait_for_timeout(1500)
        except Exception:
            pass

        # 3. 精准注入图片文件至 input[accept*='image']
        douyin_logger.info("📤 精准注入图文图片文件序列...")
        file_inputs = page.locator("input[type='file']")
        await file_inputs.first.wait_for(state="attached", timeout=15000)

        uploaded = False
        cnt = await file_inputs.count()
        for idx in range(cnt):
            inp = file_inputs.nth(idx)
            acc = await inp.get_attribute("accept") or ""
            if "image" in acc:
                await inp.set_input_files(self.image_paths)
                uploaded = True
                douyin_logger.info(f"✅ 成功通过 input[{idx}] (accept={acc}) 注入图片！")
                break

        if not uploaded:
            douyin_logger.warning("未找到显示 accept=image 的 input，尝试寻找多图 input...")
            for idx in range(cnt):
                inp = file_inputs.nth(idx)
                mult = await inp.get_attribute("multiple")
                if mult is not None:
                    await inp.set_input_files(self.image_paths)
                    uploaded = True
                    douyin_logger.info(f"✅ 兜底注入 multiple input[{idx}] 成功！")
                    break

        assert uploaded, "❌ [硬性断言失败] 无法设置图片文件上传输入框！"

        # 4. 等待跳转至编辑页面
        douyin_logger.info("⏳ 等待进入图文编辑页面...")
        for _ in range(30):
            if "creator-micro/content/post/image" in page.url:
                douyin_logger.info("🥳 已成功进入图文编辑页面")
                break
            await asyncio.sleep(0.5)

        # 5. 等待图片在抖音云端处理完毕
        douyin_logger.info("⏳ 等待图片上传与预处理 (8秒)...")
        await asyncio.sleep(8)

        # 校验图片 DOM 存在
        uploaded_imgs = page.locator("div[class*='image'], div[class*='container'] img, [class*='upload'] img")
        img_count = await uploaded_imgs.count()
        douyin_logger.info(f"📸 检查上传图片 DOM 元素数量: {img_count}")
        assert img_count > 0, "❌ [硬性断言失败] 编辑页面未检测到任何上传成功的图片！"

        # 6. 填写标题与正文描述及话题
        douyin_logger.info("✍️ 正在填写标题、描述正文与话题...")
        await self.fill_title_and_description(page, self.title, self.note, self.tags)
        await asyncio.sleep(2)

        # ────────────────────── 校验 1: 标题验证 ──────────────────────
        title_input = page.locator('input[placeholder*="标题"]').first
        val_title = await title_input.input_value()
        expected_title = self.title[:20]
        douyin_logger.info(f"🔍 校验标题: '{val_title}' (期望: '{expected_title}')")
        assert val_title == expected_title, f"❌ [硬性断言失败] 标题未成功填写！实际: '{val_title}'"

        # ────────────────────── 校验 2: 描述与话题验证 ──────────────────
        editor = page.locator('div.zone-container[contenteditable="true"], div[contenteditable="true"], [placeholder*="作品简介"]').first
        editor_text = await editor.inner_text()
        douyin_logger.info(f"🔍 描述框文本预览 (前60字): {editor_text[:60]}...")

        if self.note:
            note_sub = self.note[:10]
            assert note_sub in editor_text, f"❌ [硬性断言失败] 正文描述未成功填写入编辑框！未找到: '{note_sub}'"

        for tag in self.tags or []:
            clean_tag = tag.strip().lstrip('#')
            if clean_tag:
                assert clean_tag in editor_text, f"❌ [硬性断言失败] 话题 #{clean_tag} 未成功填写入编辑框！"

        douyin_logger.success("🎉 [全量校验通过] 标题、正文描述、话题标签及图片集均验证成功！")

        # 7. 点击‘暂存草稿’ / ‘保存草稿’
        douyin_logger.info("💾 正在保存至抖音草稿箱...")
        draft_clicked = False
        draft_selectors = [
            "button:has-text('暂存草稿')",
            "button:has-text('保存草稿')",
            "button:has-text('暂存')",
            "button:has-text('存草稿')",
            "div[class*='btn']:has-text('草稿')",
            "span:has-text('暂存草稿')",
            "text='暂存草稿'",
        ]

        for sel in draft_selectors:
            loc = page.locator(sel)
            if await loc.count() > 0:
                await loc.first.click()
                draft_clicked = True
                douyin_logger.success("✅ 已成功点击保存草稿按钮")
                break

        assert draft_clicked, "❌ [硬性断言失败] 未找到“暂存草稿”按钮！"

        # 8. 留出 15 秒供抖音服务器写入草稿箱
        douyin_logger.info("⏳ 等待抖音服务器完成草稿保存 (15秒)...")
        await asyncio.sleep(15)

        # 截图保存结果用于确认
        screenshot_path = Path(self.image_paths[0]).parent / "douyin_draft_result.png"
        try:
            await page.screenshot(path=str(screenshot_path))
            douyin_logger.info(f"📸 草稿保存页面截图已留存: {screenshot_path}")
        except Exception:
            pass

        douyin_logger.info("🔒 遵照用户要求，上传抖音草稿箱完成后保持浏览器开启 600 秒 (10分钟) 供观察与编辑...")
        await asyncio.sleep(600)


# ─────────────────────────── CLI Entry Point ─────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="douyin-publisher-skill: 上传图文至抖音草稿箱 (Patchright 引擎)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-i", "--images", help="切图文件夹路径")
    parser.add_argument("-m", "--metadata", help="元数据文件路径 (_wechat.json 或 .md)")
    parser.add_argument("--title", help="覆盖标题 (≤20字)")
    parser.add_argument("--cover", help="覆盖竖版封面图路径")
    parser.add_argument("--login", action="store_true", help="启动 Patchright 浏览器扫码登录抖音")
    parser.add_argument("--headed", action="store_true", help="使用有头浏览器界面")
    parser.add_argument("--keep-open", action="store_true", help="上传后保持浏览器开启不立即关闭")

    args = parser.parse_args()

    account_file = sau_bridge.get_cookie_file("douyin")

    # Login mode
    if args.login:
        print(f"🔑 启动抖音扫码登录，Cookie 将存入: {account_file}")
        res = asyncio.run(douyin_setup(str(account_file), handle=True, headless=False, return_detail=True))
        if res.get("success"):
            print("🎉 抖音登录成功！Cookie 已更新。")
        else:
            print(f"❌ 登录未完成: {res.get('message')}")
        return

    if not args.images or not args.metadata:
        parser.error("发布模式需要同时指定 -i (切图目录) 和 -m (元数据文件)")

    meta_path = os.path.abspath(args.metadata)
    meta = load_metadata(meta_path)
    meta_dir = os.path.dirname(meta_path)

    title = args.title if args.title else resolve_social_title(meta)
    print(f"\n📌 抖音标题: {title}")

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

    uploader = DouYinDraftNote(
        image_paths=image_paths,
        note=body,
        tags=tags,
        publish_date=0,
        account_file=str(account_file),
        title=title,
        publish_strategy=DOUYIN_PUBLISH_STRATEGY_IMMEDIATE,
        headless=not args.headed,
        keep_open=args.keep_open,
    )

    print("\n🚀 正在通过 Patchright 引擎上传至抖音草稿箱...")
    asyncio.run(uploader.douyin_upload_note())
    print("✨ 抖音草稿箱上传程序完成！")


if __name__ == "__main__":
    main()
