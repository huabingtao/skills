#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish.py - CLI entry point for bilibili-publisher-skill.

Reads metadata from _wechat.json or Markdown frontmatter, assembles
image list with vertical cover, and uploads to Bilibili Creator Center as draft
using Patchright engine and centralized cookies.

Usage:
    python3 publish.py -i <image_dir> -m <metadata_file>
    python3 publish.py --login
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# Add deps/sau_bridge to sys.path
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEPS_DIR = WORKSPACE_DIR / "deps"
if str(DEPS_DIR) not in sys.path:
    sys.path.insert(0, str(DEPS_DIR))

import sau_bridge

MEMBER_URL = "https://member.bilibili.com"
ARTICLE_UPLOAD_URL = f"{MEMBER_URL}/platform/upload/text/apply"


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


# ─────────────────────────── Patchright Engine ───────────────────────────

def _is_logged_in(page) -> bool:
    """Check if current page indicates a logged-in session on Bilibili Member center."""
    url = page.url
    if "passport.bilibili.com" in url or "login" in url:
        return False

    try:
        if page.locator('[class*="avatar"]').is_visible(timeout=1500) or page.locator('text=投稿').is_visible(timeout=1500):
            return True
        if page.locator('text=个人中心').is_visible(timeout=1500):
            return True
    except Exception:
        pass

    if "/platform/" in url or "/home" in url:
        return True

    return False


def _wait_for_login(page, timeout_seconds=300):
    """Block until the user completes QR-code login on Bilibili."""
    qr_path = Path("/tmp/bilibili_qr.png")
    try:
        page.goto("https://passport.bilibili.com/login", wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
        # Try capturing QR code element screenshot
        qr_elem = page.locator('.qrcode-img, [class*="qrcode"], img[alt*="code"]').first
        if qr_elem.count() > 0:
            qr_elem.screenshot(path=str(qr_path))
            print(f"📸 登录二维码图片已保存至: {qr_path}")
        else:
            page.screenshot(path=str(qr_path))
            print(f"📸 登录页面截图已保存至: {qr_path}")
    except Exception as e:
        print(f"⚠️ 无法自动截图二维码: {e}")

    print("\n" + "=" * 50)
    print("📱 请使用 B站 (哔哩哔哩) App 扫码登录")
    if qr_path.exists():
        print(f"🖼️ 二维码图片位置: file://{qr_path.resolve()}")
        # Try printing ASCII QR code in terminal
        try:
            from utils.login_qrcode import decode_qrcode_from_path, _print_ascii_qrcode
            import segno
            content = decode_qrcode_from_path(qr_path)
            if content:
                print("⏬ 终端二维码（直接用手机 B站 App 扫描）：")
                qr = segno.make(content)
                _print_ascii_qrcode(qr)
        except Exception:
            pass
    print(f"   超时时间：{timeout_seconds} 秒")
    print("   登录成功后将自动继续...")
    print("=" * 50 + "\n")

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _is_logged_in(page):
            print("✅ B站登录成功！")
            return True
        time.sleep(1)

    raise TimeoutError(f"登录超时（{timeout_seconds}秒）。请重新运行 --login。")


def upload_to_bilibili_draft(
    pw,
    image_paths: list[str],
    title: str,
    body_text: str,
    headless: bool = True,
):
    profile_dir = sau_bridge.COOKIES_DIR / "bilibili_uploader" / "profile"
    account_file = sau_bridge.BILI_COOKIE_FILE
    profile_dir.mkdir(parents=True, exist_ok=True)

    kwargs = {
        "user_data_dir": str(profile_dir),
        "headless": headless,
        "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    }

    context = pw.chromium.launch_persistent_context(**kwargs)
    page = context.pages[0] if context.pages else context.new_page()

    if account_file.exists():
        try:
            cookies_data = json.loads(account_file.read_text(encoding="utf-8")).get("cookies", [])
            if cookies_data:
                context.add_cookies(cookies_data)
        except Exception:
            pass

    try:
        print("🔍 [Patchright] 验证 B站登录状态...")
        page.goto(MEMBER_URL, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)

        if not _is_logged_in(page):
            if headless:
                context.close()
                print("⚠️  B站 Session 已失效，正在唤起有头浏览器进行扫码登录...")
                return upload_to_bilibili_draft(pw, image_paths, title, body_text, headless=False)
            else:
                _wait_for_login(page, timeout_seconds=300)

        print("✅ B站登录状态有效")
        print("📤 正在进入 B站专栏/图文投稿页面...")
        page.goto(ARTICLE_UPLOAD_URL, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        if len(context.pages) > 1:
            page = context.pages[-1]

        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(2)

        print(f"🖼️  正在上传 {len(image_paths)} 张图片...")
        file_inputs = page.locator('input[type="file"]')
        if file_inputs.count() > 0:
            file_inputs.first.set_input_files(image_paths, timeout=15000)
        else:
            upload_trigger = page.locator('text=上传图片').first
            with page.expect_file_chooser(timeout=5000) as fc_info:
                upload_trigger.click()
            file_chooser = fc_info.value
            file_chooser.set_files(image_paths)

        print("⏳ 等待图片上传与预处理...")
        time.sleep(5)

        print(f"📝 填写标题: {title[:80]}")
        title_selectors = ['input[placeholder*="请输入标题"]', 'input[placeholder*="标题"]', '[class*="title"] input']
        for selector in title_selectors:
            try:
                inp = page.locator(selector).first
                if inp.is_visible(timeout=2000):
                    inp.click()
                    inp.fill(title[:80])
                    break
            except Exception:
                continue

        print("📝 填写正文与话题...")
        body_selectors = ['[contenteditable="true"]', 'textarea[placeholder*="正文"]', 'textarea[placeholder*="请输入正文"]']
        for selector in body_selectors:
            try:
                editor = page.locator(selector).first
                if editor.is_visible(timeout=2000):
                    editor.click()
                    time.sleep(0.3)
                    page.keyboard.type(body_text, delay=20)
                    break
            except Exception:
                continue

        time.sleep(1)
        print("💾 正在保存至 B站草稿箱...")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        draft_selectors = ['button:has-text("保存草稿")', 'button:has-text("存草稿")', 'text=保存草稿', 'text=存草稿']
        draft_saved = False
        for selector in draft_selectors:
            try:
                candidate = page.locator(selector).last
                if candidate.is_visible(timeout=1500):
                    candidate.scroll_into_view_if_needed()
                    time.sleep(0.5)
                    candidate.click(force=True)
                    draft_saved = True
                    print("✅ 已成功点击 B站保存草稿按钮！")
                    break
            except Exception:
                continue

        if not draft_saved:
            print("⚠️ 未找到明确的“保存草稿”按钮，请在打开的页面中人工存草稿。")

        print("🔒 遵照用户要求，上传 B站 草稿箱完成后保持浏览器开启 600 秒 (10分钟) 供观察与编辑...")
        time.sleep(600)
        return True
    finally:
        try:
            context.close()
        except Exception:
            pass


# ─────────────────────────── CLI Entry Point ─────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="bilibili-publisher-skill: 上传图文至 B站 创作者中心草稿箱 (Patchright 引擎)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-i", "--images", help="切图文件夹路径")
    parser.add_argument("-m", "--metadata", help="元数据文件路径 (_wechat.json 或 .md)")
    parser.add_argument("--title", help="覆盖标题")
    parser.add_argument("--cover", help="覆盖封面图路径")
    parser.add_argument("--login", action="store_true", help="启动 Patchright 浏览器扫码登录 B站")
    parser.add_argument("--headed", action="store_true", help="使用有头浏览器界面")
    parser.add_argument("--keep-open", action="store_true", help="上传后保持浏览器开启不立即关闭")

    args = parser.parse_args()

    try:
        from patchright.sync_api import sync_playwright
    except ImportError:
        print("❌ 请先安装 Patchright: pip install patchright && python3 -m patchright install chromium")
        sys.exit(1)

    profile_dir = sau_bridge.COOKIES_DIR / "bilibili_uploader" / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    if args.login:
        print(f"🔑 启动 B站 扫码登录，Profile 将存入: {profile_dir}")
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(MEMBER_URL, wait_until="domcontentloaded", timeout=20000)
            _wait_for_login(page, timeout_seconds=300)
            time.sleep(2)
            try:
                context.storage_state(path=str(sau_bridge.BILI_COOKIE_FILE))
            except Exception:
                pass
            context.close()
            print("🎉 B站登录成功！Profile 与 Cookie 已自动保存。")
        return

    if not args.images or not args.metadata:
        parser.error("发布模式需要同时指定 -i (切图目录) 和 -m (元数据文件)")

    meta_path = os.path.abspath(args.metadata)
    meta = load_metadata(meta_path)
    meta_dir = os.path.dirname(meta_path)

    title = args.title if args.title else resolve_title(meta)
    print(f"\n📌 B站标题: {title}")

    body = build_body_text(meta)
    print(f"📝 正文预览:\n{body}\n")

    image_paths = collect_images(
        args.images,
        meta,
        meta_dir=meta_dir,
        cover_override=args.cover,
    )

    print("\n🚀 正在通过 Patchright 引擎上传至 B站草稿箱...")
    with sync_playwright() as pw:
        upload_to_bilibili_draft(
            pw,
            image_paths=image_paths,
            title=title,
            body_text=body,
            headless=not args.headed,
        )
    print("✨ B站草稿箱上传完成！")


if __name__ == "__main__":
    main()
