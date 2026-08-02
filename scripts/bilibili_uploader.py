#!/usr/bin/env python3
"""
bilibili_uploader.py - Playwright-based Bilibili Creator Platform automation.

Handles:
  - Session persistence via ~/.bilibili_user_data
  - Headed login with QR code scanning if needed
  - Automated image-text post upload and draft saving
"""

import json
import os
import sys
import time
from pathlib import Path

USER_DATA_DIR = Path.home() / ".bilibili_user_data"
MEMBER_URL = "https://member.bilibili.com"
ARTICLE_UPLOAD_URL = f"{MEMBER_URL}/platform/upload/text/apply"


def _cleanup_profile_lock():
    """Remove SingletonLock if present to prevent browser startup conflicts."""
    lock_file = USER_DATA_DIR / "SingletonLock"
    if lock_file.exists() or lock_file.is_symlink():
        try:
            lock_file.unlink()
            print("🧹 已自动清理浏览器 Profile 锁 (SingletonLock)")
        except Exception:
            pass


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
    print("\n" + "=" * 50)
    print("📱 请使用 B站 (哔哩哔哩) App 扫码登录")
    print(f"   超时时间：{timeout_seconds} 秒")
    print("   登录成功后将自动继续...")
    print("=" * 50 + "\n")

    deadline = time.time() + timeout_seconds
    last_remaining = timeout_seconds
    last_url = ""
    while time.time() < deadline:
        current_url = page.url
        if current_url != last_url:
            print(f"🔗 当前页面: {current_url}")
            last_url = current_url

        if _is_logged_in(page):
            print("✅ 登录成功！")
            return True

        remaining = int(deadline - time.time())
        if remaining != last_remaining and remaining % 30 == 0 and remaining > 0:
            print(f"⏳ 等待扫码中... 剩余 {remaining} 秒")
            last_remaining = remaining
        time.sleep(1)

    print(f"❌ 最后一次检测到的 URL: {page.url}")
    raise TimeoutError(f"登录超时（{timeout_seconds}秒）。请重新运行 --login。")


def login(playwright):
    """Launch a headed browser for QR-code login using persistent user_data_dir."""
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_profile_lock()

    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(USER_DATA_DIR),
        headless=False,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    page = context.pages[0] if context.pages else context.new_page()

    page.goto(MEMBER_URL, wait_until="domcontentloaded", timeout=20000)
    _wait_for_login(page, timeout_seconds=300)

    print("🔄 正在跳转至 B站 创作者专栏/图文投稿页...")
    page.goto(ARTICLE_UPLOAD_URL, wait_until="domcontentloaded", timeout=20000)
    time.sleep(4)

    context.close()
    print(f"🎉 登录完成！浏览器 Profile 已持久化保存至 {USER_DATA_DIR}。")


def upload_image_post(
    playwright,
    image_paths: list[str],
    title: str,
    body_text: str,
    headless: bool = True,
):
    """
    Upload an image-text post to Bilibili Creator Center and save as draft.
    """
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_profile_lock()

    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(USER_DATA_DIR),
        headless=headless,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    page = context.pages[0] if context.pages else context.new_page()

    try:
        # 1. Validate session, prompt for scan if needed
        print("🔍 验证 B站登录状态...")
        page.goto(MEMBER_URL, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)

        if not _is_logged_in(page):
            if headless:
                context.close()
                print("⚠️  Session 已失效，正在唤起有头浏览器进行扫码登录...")
                return upload_image_post(playwright, image_paths, title, body_text, headless=False)
            else:
                _wait_for_login(page, timeout_seconds=300)

        print("✅ B站登录状态有效")

        # 2. Open专栏/图文发布页
        print("📤 正在进入 B站专栏/图文投稿页面...")
        page.goto(ARTICLE_UPLOAD_URL, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        if len(context.pages) > 1:
            page = context.pages[-1]

        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(2)

        print(f"🔗 当前投稿页 URL: {page.url}")

        # 3. Upload images
        print(f"🖼️  正在上传 {len(image_paths)} 张图片...")

        file_inputs = page.locator('input[type="file"]')
        if file_inputs.count() > 0:
            file_inputs.first.set_input_files(image_paths, timeout=15000)
            print("   ✅ 通过 file input 批量上传成功")
        else:
            upload_trigger = page.locator('text=上传图片').first
            with page.expect_file_chooser(timeout=5000) as fc_info:
                upload_trigger.click()
            file_chooser = fc_info.value
            file_chooser.set_files(image_paths)
            print("   ✅ 通过 file_chooser 批量上传成功")

        print("⏳ 等待图片上传与预处理...")
        time.sleep(8)

        for _ in range(60):
            time.sleep(1)
            try:
                loading = page.locator('[class*="loading"], [class*="progress"]')
                if loading.count() == 0:
                    break
            except Exception:
                break

        debug_uploaded = str(Path(image_paths[0]).parent / "_bili_step2_uploaded.png")
        page.screenshot(path=debug_uploaded)
        print(f"✅ 图片上传完成，截图已保存: {debug_uploaded}")

        # 4. Fill title
        print(f"📝 填写标题: {title[:80]}")
        title_selectors = [
            'input[placeholder*="请输入标题"]',
            'input[placeholder*="标题"]',
            '[class*="title"] input',
        ]
        title_filled = False
        for selector in title_selectors:
            try:
                inp = page.locator(selector).first
                if inp.is_visible(timeout=2000):
                    inp.click()
                    inp.fill(title[:80])
                    title_filled = True
                    print(f"   ✅ 标题已填写 (selector: {selector})")
                    break
            except Exception:
                continue

        # 5. Fill body text
        print("📝 填写正文与话题...")
        body_selectors = [
            '[contenteditable="true"]',
            'textarea[placeholder*="正文"]',
            'textarea[placeholder*="请输入正文"]',
        ]
        body_filled = False
        for selector in body_selectors:
            try:
                editor = page.locator(selector).first
                if editor.is_visible(timeout=2000):
                    editor.click()
                    time.sleep(0.3)
                    page.keyboard.type(body_text, delay=20)
                    body_filled = True
                    print(f"   ✅ 正文已填写 (selector: {selector})")
                    break
            except Exception:
                continue

        time.sleep(1)
        debug_filled = str(Path(image_paths[0]).parent / "_bili_step3_filled.png")
        page.screenshot(path=debug_filled)

        # 6. Save Draft
        print("💾 正在寻找 B站草稿/存草稿按钮...")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        draft_selectors = [
            'button:has-text("保存草稿")',
            'button:has-text("存草稿")',
            'text=保存草稿',
            'text=存草稿',
            '[class*="draft"]',
        ]

        draft_saved = False
        for selector in draft_selectors:
            try:
                candidate = page.locator(selector).last
                if candidate.is_visible(timeout=1500):
                    candidate.scroll_into_view_if_needed()
                    time.sleep(0.5)
                    candidate.click(force=True)
                    draft_saved = True
                    print(f"   ✅ 已成功点击保存草稿 (selector: {selector})")
                    break
            except Exception:
                continue

        if not draft_saved:
            debug_draft = str(Path(image_paths[0]).parent / "_bili_draft_debug.png")
            page.screenshot(path=debug_draft)
            raise RuntimeError(f"❌ 未找到 B站'保存草稿'按钮。截图已存至: {debug_draft}")

        time.sleep(3)
        debug_done = str(Path(image_paths[0]).parent / "_bili_step4_done.png")
        page.screenshot(path=debug_done)

        print("\n" + "=" * 50)
        print("🚀 BILIBILI DRAFT SAVED SUCCESSFULLY!")
        print("=" * 50)
        print("您现在可以前往 B站创作者中心查看草稿。")
        print(f"📸 最终截图: {debug_done}")

        if not headless:
            print("\n⏳ 有头模式下保留 5 秒供您预览，随后将自动关闭...")
            time.sleep(5)

        return True

    except Exception as e:
        try:
            screenshot_path = str(Path(image_paths[0]).parent / "_bili_error.png")
            page.screenshot(path=screenshot_path)
            print(f"📸 错误截图已保存: {screenshot_path}")
        except Exception:
            pass
        raise
    finally:
        context.close()
