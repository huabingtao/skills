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
UPLOAD_URL = f"{CREATOR_URL}/creator-micro/content/upload?default-tab=3"


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
    publish_now: bool = False,
    review: bool = False,
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
                return upload_image_post(playwright, image_paths, title, body_text, headless=False, publish_now=publish_now, review=review)
            else:
                # Prompt user to scan QR in current headed window
                _wait_for_login(page, timeout_seconds=300)

        print("✅ 登录状态有效")

        # 2. Click "发布图文" card on creator home page
        print("📤 正在进入图文发布页面...")
        time.sleep(2)

        # Dismiss any shepherd onboarding modal / overlay
        try:
            for btn_text in ["我知道了", "跳过", "下一步", "知道了", "关闭", "立即体验"]:
                btn = page.locator(f'button:has-text("{btn_text}"), span:has-text("{btn_text}")').first
                if btn.is_visible(timeout=500):
                    btn.click(force=True)
                    time.sleep(0.5)
        except Exception:
            pass

        try:
            page.evaluate("""() => {
                document.querySelectorAll('.shepherd-modal-overlay-container, .shepherd-element, .shepherd-modal-is-visible, [class*="shepherd"], [class*="guide-overlay"]')
                    .forEach(el => el.remove());
            }""")
        except Exception:
            pass

        # Look for "发布图文" card on home page
        publish_card = page.locator('text=发布图文').first
        if publish_card.is_visible(timeout=3000):
            try:
                publish_card.click(force=True, timeout=5000)
            except Exception:
                publish_card.dispatch_event('click')
            time.sleep(3)
        else:
            print("⚠️ 未在首页找到'发布图文'卡片，直接跳转至发布页...")
            page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)

        # Switch to latest tab if opened in new tab
        if len(context.pages) > 1:
            for p in context.pages:
                if "/content/upload" in p.url:
                    page = p
                    break
            else:
                page = context.pages[-1]
            print(f"🔗 当前选中标签页: {page.url}")

        if "/content/upload" not in page.url:
            print(f"🔄 正在强制导航至发布页: {UPLOAD_URL}")
            page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)

        page.wait_for_load_state("domcontentloaded", timeout=15000)
        time.sleep(2)

        # Also dismiss any overlay on upload page
        try:
            page.evaluate("""() => {
                document.querySelectorAll('.shepherd-modal-overlay-container, .shepherd-element, .shepherd-modal-is-visible, [class*="shepherd"]')
                    .forEach(el => el.remove());
            }""")
        except Exception:
            pass

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

        # 6. Action: Review, Publish or Save Draft
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        if review:
            print("\n" + "=" * 50)
            print("👀 页面已就绪！已为您停留在编辑页面供人工审核 (REVIEW MODE)")
            print("=" * 50)
            print("您可以直接在桌面浏览器中逐项核对：")
            print("  1. 4 张切图与封面排版")
            print("  2. 标题、文案与话题标签")
            print("核对完毕后，您可直接在页面右下角手动点击【发布】或【暂存离开】。")

        elif publish_now:
            print("🚀 正在查找并点击'发布'按钮...")
            publish_selectors = [
                'button:has-text("高清发布")',
                'button:has-text("发布")',
                'button:has-text("立即发布")',
                '[class*="publish-btn"]',
                'div[role="button"]:has-text("发布")',
                'text=发布',
            ]

            published = False
            for selector in publish_selectors:
                try:
                    btn = page.locator(selector).last
                    if btn.is_visible(timeout=2000):
                        btn.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        btn.click(force=True)
                        published = True
                        print(f"   ✅ 已成功点击发布按钮 (selector: {selector})")
                        break
                except Exception:
                    continue

            if not published:
                print("   ⚠️ 未能自动定位到'发布'按钮，浏览器将保持在桌面，您可以直接在窗口中手动点击【发布】")
            else:
                time.sleep(4)
                # Check for secondary confirmation popups
                for confirm_word in ["确定", "确认", "继续发布", "我知道了", "完成"]:
                    try:
                        c_btn = page.locator(f'button:has-text("{confirm_word}"), span:has-text("{confirm_word}")').last
                        if c_btn.is_visible(timeout=1000):
                            c_btn.click(force=True)
                            print(f"   ✅ 点击弹窗确认: {confirm_word}")
                            time.sleep(1)
                    except Exception:
                        pass

            print("\n" + "=" * 50)
            print("🚀 抖音图文发布指令已执行！(DOUYIN PUBLISHED)")
            print("=" * 50)

        else:
            print("💾 正在向下滚动页面以寻找'保存草稿'按钮...")
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

            print("\n" + "=" * 50)
            print("🚀 抖音图文草稿保存成功！(DOUYIN DRAFT SAVED SUCCESSFULLY)")
            print("=" * 50)
            print("您现在可以前往抖音创作者后台'草稿箱'查看。")

        time.sleep(2)

        # 7. Final verification
        debug_path_done = str(Path(image_paths[0]).parent / "_douyin_step4_done.png")
        page.screenshot(path=debug_path_done)
        print(f"📸 最终截图: {debug_path_done}")

        if not headless:
            print("\n🌟 浏览器窗口已在桌面打开并保持开启，方便您查看与确认！")
            print("   （如需关闭，可直接手动关闭浏览器窗口）")
            try:
                page.wait_for_event("close", timeout=0)
            except Exception:
                pass

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

