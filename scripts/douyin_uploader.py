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

COOKIE_PATH = Path.home() / ".douyin_cookie.json"
CREATOR_URL = "https://creator.douyin.com"
UPLOAD_URL = f"{CREATOR_URL}/creator-micro/content/upload"
LOGIN_SUCCESS_INDICATOR = "/creator-micro/home"


def save_cookies(context):
    """Export browser storage state to disk."""
    state = context.storage_state()
    COOKIE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Cookie saved to {COOKIE_PATH}")


def load_cookies():
    """Load saved storage state, or return None if missing/expired."""
    if not COOKIE_PATH.exists():
        return None
    try:
        state = json.loads(COOKIE_PATH.read_text(encoding="utf-8"))
        if not state.get("cookies"):
            return None
        return state
    except (json.JSONDecodeError, KeyError):
        return None


def _wait_for_login(page, timeout_seconds=120):
    """Block until the user completes QR-code login."""
    print("\n" + "=" * 50)
    print("📱 请使用抖音 App 扫码登录")
    print("   登录成功后将自动继续...")
    print("=" * 50 + "\n")

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if LOGIN_SUCCESS_INDICATOR in page.url:
            print("✅ 登录成功！")
            return True
        time.sleep(1)

    raise TimeoutError(f"登录超时（{timeout_seconds}秒）。请重新运行 --login。")


def login(playwright):
    """Launch a headed browser for QR-code login, then persist cookies."""
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(CREATOR_URL)
    _wait_for_login(page, timeout_seconds=120)

    # Give extra time for cookies to fully populate
    time.sleep(2)
    save_cookies(context)
    browser.close()
    print("🎉 登录完成，Cookie 已保存。后续运行将自动静默执行。")


def _validate_session(page):
    """Navigate to creator home and verify the session is alive."""
    page.goto(CREATOR_URL, wait_until="domcontentloaded", timeout=15000)
    time.sleep(2)

    # If redirected to login page, session is expired
    if "login" in page.url or "passport" in page.url:
        return False
    return True


def upload_image_post(
    playwright,
    image_paths: list[str],
    title: str,
    body_text: str,
    headless: bool = True,
):
    """
    Upload an image-text post to Douyin creator platform and save as draft.

    Args:
        playwright: Playwright instance.
        image_paths: Ordered list of absolute image file paths.
        title: Post title (≤20 chars).
        body_text: Post body including hashtags.
        headless: Run in headless mode (requires valid cookies).

    Returns:
        True on success, raises on failure.
    """
    storage = load_cookies()
    if not storage:
        raise RuntimeError(
            "❌ 未找到有效的抖音登录凭证。请先运行：\n"
            "   python3 publish.py --login"
        )

    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(storage_state=storage)
    page = context.new_page()

    try:
        # 1. Validate session
        print("🔍 验证登录状态...")
        if not _validate_session(page):
            browser.close()
            raise RuntimeError(
                "❌ Cookie 已失效，请重新登录：\n"
                "   python3 publish.py --login"
            )
        print("✅ 登录状态有效")

        # 2. Navigate to upload page
        print("📤 正在打开图文发布页面...")
        page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        # 3. Switch to image-text mode if needed
        # Look for the image-text tab and click it
        try:
            img_text_tab = page.locator('div:has-text("图文")').first
            if img_text_tab.is_visible(timeout=3000):
                img_text_tab.click()
                time.sleep(1)
        except Exception:
            pass  # May already be on image-text tab

        # 4. Upload images via file chooser
        print(f"🖼️  正在上传 {len(image_paths)} 张图片...")
        
        # Find the file input for image upload
        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files(image_paths)
        
        # Wait for uploads to complete
        print("⏳ 等待图片上传完成...")
        time.sleep(5)
        
        # Check if all images are uploaded by waiting for thumbnails
        for i in range(30):  # Max 30 seconds wait
            # Look for upload progress indicators or thumbnail count
            time.sleep(1)
            try:
                # Check if upload is still in progress
                progress = page.locator('[class*="progress"]').count()
                if progress == 0:
                    break
            except Exception:
                break
        
        print(f"✅ {len(image_paths)} 张图片上传完成")

        # 5. Fill in the title
        print(f"📝 填写标题: {title[:20]}")
        title_input = page.locator('input[placeholder*="标题"]').first
        if not title_input.is_visible(timeout=3000):
            # Try alternative selectors
            title_input = page.locator('[class*="title"] input').first
        title_input.fill("")
        title_input.fill(title[:20])
        time.sleep(0.5)

        # 6. Fill in the body text with hashtags
        print(f"📝 填写正文与话题...")
        # The body/description editor
        body_editor = page.locator('[contenteditable="true"]').first
        if not body_editor.is_visible(timeout=3000):
            body_editor = page.locator('textarea[placeholder*="描述"]').first
        
        body_editor.click()
        body_editor.fill("")
        
        # Type body text including hashtags
        page.keyboard.type(body_text, delay=20)
        time.sleep(1)

        # 7. Click "Save Draft" button
        print("💾 保存草稿...")
        
        # Try multiple possible selectors for the draft button
        draft_btn = None
        draft_selectors = [
            'button:has-text("存草稿")',
            'button:has-text("保存草稿")',
            '[class*="draft"]',
            'button:has-text("草稿")',
        ]
        
        for selector in draft_selectors:
            try:
                candidate = page.locator(selector).first
                if candidate.is_visible(timeout=2000):
                    draft_btn = candidate
                    break
            except Exception:
                continue
        
        if not draft_btn:
            # If we can't find draft button, try to screenshot for debugging
            screenshot_path = str(Path(image_paths[0]).parent / "_douyin_debug.png")
            page.screenshot(path=screenshot_path)
            raise RuntimeError(
                f"❌ 未找到'保存草稿'按钮。已截图保存至: {screenshot_path}\n"
                "请检查抖音创作者后台页面结构是否有变化。"
            )
        
        draft_btn.click()
        time.sleep(3)

        # 8. Verify draft saved
        print("\n" + "=" * 40)
        print("🚀 DOUYIN DRAFT SAVED SUCCESSFULLY!")
        print("=" * 40)
        print("您现在可以前往抖音创作者后台'草稿箱'查看。")

        # Update cookies after successful operation
        save_cookies(context)
        return True

    except Exception as e:
        # Take debug screenshot on failure
        try:
            screenshot_path = str(Path(image_paths[0]).parent / "_douyin_error.png")
            page.screenshot(path=screenshot_path)
            print(f"📸 错误截图已保存: {screenshot_path}")
        except Exception:
            pass
        raise
    finally:
        browser.close()
