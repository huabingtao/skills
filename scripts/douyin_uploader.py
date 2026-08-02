#!/usr/bin/env python3
"""
douyin_uploader.py - Playwright-based Douyin Creator Platform automation.

Handles:
  - Cookie-based session persistence (~/.douyin_cookie.json)
  - Headful login with QR code scanning
  - Headless image-text post creation (draft mode)
"""

import json
import os
import sys
import time
from pathlib import Path

USER_DATA_DIR = Path.home() / ".douyin_user_data"
STORAGE_STATE_PATH = Path.home() / ".douyin_storage_state.json"
CREATOR_URL = "https://creator.douyin.com"
UPLOAD_URL = f"{CREATOR_URL}/creator-micro/content/upload"


def _is_logged_in(page) -> bool:
    """Check if current page is logged in by examining URL and DOM."""
    url = page.url
    if "login" in url or "passport" in url:
        return False

    # Root URL is NOT guaranteed to be logged in (it shows login QR form by default)
    if url.strip('/') == "https://creator.douyin.com":
        # Check if the home dashboard or creator profile elements exist
        try:
            if page.locator('text=发布视频').is_visible(timeout=1000) or page.locator('text=发布图文').is_visible(timeout=1000):
                return True
        except Exception:
            pass
        return False

    # Creator micro backend paths indicate successful login
    if "/creator-micro/" in url:
        return True

    return False


def _wait_for_login(page, timeout_seconds=300):
    """Block until the user completes QR-code login."""
    print("\n" + "=" * 50)
    print("📱 请使用抖音 App 扫码登录")
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
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(USER_DATA_DIR),
        headless=False,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    page = context.pages[0] if context.pages else context.new_page()

    page.goto(CREATOR_URL, wait_until="domcontentloaded", timeout=20000)
    _wait_for_login(page, timeout_seconds=300)

    print("🔄 正在跳转至创作者发布页...")
    page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=20000)
    time.sleep(5)

    context.close()
    print(f"🎉 登录完成！浏览器 Profile 已持久化保存至 {USER_DATA_DIR}。")


def _validate_session(page):
    """Navigate to creator upload page and verify session."""
    page.goto(CREATOR_URL, wait_until="domcontentloaded", timeout=15000)
    time.sleep(3)

    url = page.url
    print(f"🔗 验证 Login Session，当前 URL: {url}")
    if "login" in url or "passport" in url:
        return False

    # Check if login qr code form is visible
    try:
        if page.locator('text=扫码登录').is_visible(timeout=2000) and page.locator('text=我是创作者').is_visible(timeout=2000):
            print("⚠️ 检测到扫码登录表单，Session 已失效")
            return False
    except Exception:
        pass

    return True


def upload_image_post(
    playwright,
    image_paths: list[str],
    title: str,
    body_text: str,
    headless: bool = True,
):
    """
    Upload an image-text post to Douyin creator platform using persistent context.
    If session is invalid/expired, automatically prompts for QR scan in headed mode.
    """
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(USER_DATA_DIR),
        headless=headless,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    page = context.pages[0] if context.pages else context.new_page()

    try:
        # 1. Validate session, prompt for scan if needed
        print("🔍 验证登录状态...")
        page.goto(CREATOR_URL, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)

        if not _validate_session(page):
            if headless:
                # Close headless browser and restart headed
                context.close()
                print("⚠️  Session 已失效，正在唤起有头浏览器进行扫码登录...")
                return upload_image_post(playwright, image_paths, title, body_text, headless=False)
            else:
                # Prompt user to scan QR in current headed window
                _wait_for_login(page, timeout_seconds=300)

        print("✅ 登录状态有效")

        # 2. Click "发布图文" card on creator home page
        print("📤 正在进入图文发布页面...")
        time.sleep(2)

        # Look for "发布图文" card on home page
        publish_card = page.locator('text=发布图文').first
        if publish_card.is_visible(timeout=3000):
            publish_card.click()
            time.sleep(3)
        else:
            print("⚠️ 未在首页找到'发布图文'卡片，直接跳转至发布页...")
            page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)

        # Switch to latest tab if opened in new tab
        if len(context.pages) > 1:
            page = context.pages[-1]
            print(f"🔗 切换到新标签页: {page.url}")

        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(2)

        print(f"🔗 当前发布页 URL: {page.url}")

        # 3. Upload images
        print(f"🖼️  正在上传 {len(image_paths)} 张图片...")

        file_inputs = page.locator('input[type="file"]')
        file_input_count = file_inputs.count()
        print(f"   找到 {file_input_count} 个 file input 元素")

        if file_input_count > 0:
            for i in range(file_input_count):
                fi = file_inputs.nth(i)
                accept = fi.get_attribute("accept") or ""
                if "image" in accept or "png" in accept or "jpg" in accept or accept == "":
                    fi.set_input_files(image_paths, timeout=15000)
                    print("   ✅ 通过 file input 上传成功")
                    break
        else:
            upload_triggers = [
                'text=上传图片',
                'text=点击上传',
                'text=添加图片',
                '[class*="upload"]',
                '[class*="Upload"]',
                '[class*="add"]',
            ]

            clicked = False
            for selector in upload_triggers:
                try:
                    trigger = page.locator(selector).first
                    if trigger.is_visible(timeout=2000):
                        with page.expect_file_chooser(timeout=5000) as fc_info:
                            trigger.click()
                        file_chooser = fc_info.value
                        file_chooser.set_files(image_paths)
                        clicked = True
                        print(f"   ✅ 通过 file_chooser 上传成功 (selector: {selector})")
                        break
                except Exception:
                    continue

            if not clicked:
                debug_path = str(Path(image_paths[0]).parent / "_douyin_upload_debug.png")
                page.screenshot(path=debug_path)
                raise RuntimeError(
                    f"❌ 无法找到图片上传入口。截图: {debug_path}\n"
                    f"当前 URL: {page.url}"
                )

        print("⏳ 等待图片上传与处理...")
        time.sleep(8)

        # Wait for loading spinners to clear
        for _ in range(60):
            time.sleep(1)
            try:
                loading = page.locator('[class*="loading"], [class*="progress"], [class*="uploading"]')
                if loading.count() == 0:
                    break
            except Exception:
                break

        debug_path_uploaded = str(Path(image_paths[0]).parent / "_douyin_step2_uploaded.png")
        page.screenshot(path=debug_path_uploaded)
        print(f"✅ 图片上传完成，截图已保存: {debug_path_uploaded}")

        # 4. Fill in title
        print(f"📝 填写标题: {title[:20]}")
        title_selectors = [
            'input[placeholder*="标题"]',
            'input[placeholder*="填写标题"]',
            '[class*="title"] input',
            'input[maxlength]',
        ]

        title_filled = False
        for selector in title_selectors:
            try:
                title_input = page.locator(selector).first
                if title_input.is_visible(timeout=2000):
                    title_input.click()
                    title_input.fill(title[:20])
                    title_filled = True
                    print(f"   ✅ 标题已填写 (selector: {selector})")
                    break
            except Exception:
                continue

        if not title_filled:
            print("   ⚠️ 未找到标题输入框")

        time.sleep(0.5)

        # 5. Fill in body text with hashtags
        print("📝 填写正文与话题...")
        body_selectors = [
            '[contenteditable="true"]',
            'textarea[placeholder*="描述"]',
            'textarea[placeholder*="正文"]',
            '[class*="desc"] [contenteditable]',
            'textarea',
        ]

        body_filled = False
        for selector in body_selectors:
            try:
                body_editor = page.locator(selector).first
                if body_editor.is_visible(timeout=2000):
                    body_editor.click()
                    time.sleep(0.3)
                    page.keyboard.type(body_text, delay=20)
                    body_filled = True
                    print(f"   ✅ 正文已填写 (selector: {selector})")
                    break
            except Exception:
                continue

        if not body_filled:
            print("   ⚠️ 未找到正文编辑器")

        time.sleep(1)

        debug_path_filled = str(Path(image_paths[0]).parent / "_douyin_step3_filled.png")
        page.screenshot(path=debug_path_filled)

        # 6. Scroll down to show bottom action buttons and click "Save Draft"
        print("💾 正在向下滚动页面以寻找'保存草稿'按钮...")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        # Additional selector list for Douyin creator platform draft button ("暂存离开")
        draft_selectors = [
            'button:has-text("暂存离开")',
            'text=暂存离开',
            'div:has-text("暂存离开")',
            'button:has-text("存草稿")',
            'button:has-text("保存草稿")',
            'button:has-text("保存为草稿")',
            'text=存草稿',
            'text=保存草稿',
            '[class*="draft"]',
            '[class*="Draft"]',
        ]

        draft_saved = False
        for selector in draft_selectors:
            try:
                candidate = page.locator(selector).last  # Bottom button
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
            # Take debugging screenshots after scrolling
            debug_path_draft = str(Path(image_paths[0]).parent / "_douyin_draft_debug.png")
            page.screenshot(path=debug_path_draft)
            raise RuntimeError(
                f"❌ 未找到'保存草稿'按钮。截图: {debug_path_draft}\n"
                "请检查抖音创作者后台页面结构是否有变化。"
            )

        time.sleep(3)

        # 7. Final verification
        debug_path_done = str(Path(image_paths[0]).parent / "_douyin_step4_done.png")
        page.screenshot(path=debug_path_done)

        print("\n" + "=" * 50)
        print("🚀 抖音图文草稿保存成功！(DOUYIN DRAFT SAVED SUCCESSFULLY)")
        print("=" * 50)
        print("您现在可以前往抖音创作者后台'草稿箱'查看。")
        print(f"📸 最终截图: {debug_path_done}")

        if not headless:
            print("\n⏳ 有头模式下保留 5 秒供您预览，随后将自动关闭...")
            time.sleep(5)

        return True

    except Exception as e:
        try:
            screenshot_path = str(Path(image_paths[0]).parent / "_douyin_error.png")
            page.screenshot(path=screenshot_path)
            print(f"📸 错误截图已保存: {screenshot_path}")
        except Exception:
            pass
        raise
    finally:
        context.close()

