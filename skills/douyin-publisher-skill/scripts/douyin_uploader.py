#!/usr/bin/env python3
"""
douyin_uploader.py - Playwright-based Douyin Creator Platform automation.

Handles:
  - Persistent browser session (~/.douyin_user_data)
  - Headful login with QR code scanning
  - Headed image-text upload with manual review by default
"""

import json
import os
import re
import sys
import time
from pathlib import Path

USER_DATA_DIR = Path.home() / ".douyin_user_data"
STORAGE_STATE_PATH = Path.home() / ".douyin_storage_state.json"
CREATOR_URL = "https://creator.douyin.com"
UPLOAD_URL = f"{CREATOR_URL}/creator-micro/content/upload?default-tab=3"


def verify_post_fields(title_input, body_editor, title, body_text):
    """Read back the filled controls; a successful typing call alone is insufficient."""
    if title_input is None or body_editor is None:
        raise RuntimeError("标题或正文编辑器未填写完成，不能报告审核页就绪")
    actual_title = title_input.input_value()
    actual_body = (body_editor.inner_text()
                   if body_editor.get_attribute("contenteditable") == "true"
                   else body_editor.input_value())
    normalize = lambda value: re.sub(r"[\s\u200b\ufeff]+", "", value)
    if actual_title != title[:20]:
        raise RuntimeError("标题回读与预期不一致，保留页面供检查")
    if normalize(body_text) not in normalize(actual_body):
        raise RuntimeError("正文或话题回读不完整，保留页面供检查")
    return {"title": actual_title, "body": actual_body}


def _get_dist_dir(image_paths: list[str] = None) -> Path:
    """Find the dist directory corresponding to the given images."""
    if image_paths:
        first_p = Path(image_paths[0]).resolve()
        for candidate in [first_p.parent, first_p.parent.parent]:
            if candidate.name == "dist":
                return candidate
            if (candidate / "dist").is_dir():
                return candidate / "dist"
        return first_p.parent
    return Path.cwd()


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


def _wait_for_login(page, timeout_seconds=300, qr_dir=None):
    """Block until the user completes QR-code login."""
    print("\n" + "=" * 50, flush=True)
    print("📱 请使用抖音 App 扫码登录", flush=True)
    print(f"   超时时间：{timeout_seconds} 秒", flush=True)
    print("   登录成功后将自动继续...", flush=True)
    print("=" * 50 + "\n", flush=True)

    # Take screenshot and crop clean QR code after initial rendering
    time.sleep(3)
    target_qr_dir = Path(qr_dir) if qr_dir and Path(qr_dir).exists() else Path.cwd()

    qr_path = Path(target_qr_dir) / "抖音扫码登录.png"
    
    def _save_cropped_qr():
        try:
            temp_full = Path(target_qr_dir) / "_temp_full_login.png"
            page.screenshot(path=str(temp_full))
            from PIL import Image
            im = Image.open(str(temp_full))
            w, h = im.size
            # In 1280x720 or 1280x900, crop around center modal QR code
            if w >= 1200 and h >= 700:
                cy = int(h * 0.49) if h >= 850 else 445
                qr_crop = im.crop((530, cy - 140, 830, cy + 140))
                qr_crop.save(str(qr_path))
            else:
                im.save(str(qr_path))
            if temp_full.exists():
                temp_full.unlink()
            print(f"📸 登录二维码已精准保存至: {qr_path}")
        except Exception as e:
            try:
                page.screenshot(path=str(qr_path))
            except Exception:
                pass

    _save_cropped_qr()

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
            # Refresh screenshot periodically in case QR refreshed
            _save_cropped_qr()
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
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--window-position=50,50",
            "--window-size=1280,900",
            "--start-maximized",
        ],
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.bring_to_front()

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
    headless: bool = False,
    publish_now: bool = False,
    review: bool = None,
):
    """
    Upload an image-text post to Douyin creator platform using persistent context.
    If session is invalid/expired, automatically prompts for QR scan in headed mode.
    """
    if review is None:
        review = not publish_now
    if review and (headless or publish_now):
        raise ValueError("人工审核必须使用有头浏览器，不能同时请求自动发布")
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(USER_DATA_DIR),
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--window-position=50,50",
            "--window-size=1280,900",
            "--start-maximized",
        ],
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.bring_to_front()

    dist_dir = _get_dist_dir(image_paths)

    try:
        # 1. Validate session, prompt for scan if needed
        print("🔍 验证登录状态...", flush=True)
        page.goto(CREATOR_URL, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)

        if not _validate_session(page):
            if headless:
                # Close headless browser and restart headed
                context.close()
                print("⚠️  Session 已失效，正在唤起有头浏览器进行扫码登录...", flush=True)
                return upload_image_post(playwright, image_paths, title, body_text, headless=False, publish_now=publish_now, review=review)
            else:
                # Prompt user to scan QR in current headed window
                _wait_for_login(page, timeout_seconds=300, qr_dir=dist_dir)

        print("✅ 登录状态有效", flush=True)

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
        print(f"🖼️  正在上传 {len(image_paths)} 张图片...", flush=True)

        print("⏳ 等待上传区域加载就绪...", flush=True)
        # Wait up to 15 seconds for file input or upload trigger to appear
        for _ in range(15):
            time.sleep(1)
            try:
                page.evaluate("""() => {
                    document.querySelectorAll('.shepherd-modal-overlay-container, .shepherd-element, .shepherd-modal-is-visible, [class*="shepherd"]')
                        .forEach(el => el.remove());
                }""")
            except Exception:
                pass
            if page.locator('input[type="file"]').count() > 0:
                break
            try:
                if page.locator('text=上传图片').is_visible() or page.locator('text=点击上传').is_visible():
                    break
            except Exception:
                pass

        file_inputs = page.locator('input[type="file"]')
        file_input_count = file_inputs.count()
        print(f"   找到 {file_input_count} 个 file input 元素", flush=True)

        if file_input_count > 0:
            uploaded = False
            for i in range(file_input_count):
                fi = file_inputs.nth(i)
                accept = fi.get_attribute("accept") or ""
                if "image" in accept or "png" in accept or "jpg" in accept or accept == "":
                    try:
                        fi.set_input_files(image_paths, timeout=15000)
                        print("   ✅ 通过 file input 上传成功", flush=True)
                        uploaded = True
                        break
                    except Exception as e:
                        print(f"   ⚠️ file input 设置失败: {e}", flush=True)
            if not uploaded:
                file_inputs.first.set_input_files(image_paths, timeout=15000)
                print("   ✅ 通过 first file input 强制上传成功", flush=True)
        else:
            upload_triggers = [
                'text=上传图片',
                'text=点击上传',
                'text=添加图片',
                '[class*="upload-btn"]',
                '[class*="upload"]',
                '[class*="Upload"]',
                '[class*="add"]',
            ]

            clicked = False
            for selector in upload_triggers:
                try:
                    trigger = page.locator(selector).first
                    if trigger.is_visible(timeout=3000):
                        with page.expect_file_chooser(timeout=8000) as fc_info:
                            trigger.click()
                        file_chooser = fc_info.value
                        file_chooser.set_files(image_paths)
                        clicked = True
                        print(f"   ✅ 通过 file_chooser 上传成功 (selector: {selector})", flush=True)
                        break
                except Exception:
                    continue

            if not clicked:
                debug_path = str(dist_dir / "_douyin_upload_debug.png")
                page.screenshot(path=debug_path)
                raise RuntimeError(
                    f"❌ 无法找到图片上传入口。截图: {debug_path}\n"
                    f"当前 URL: {page.url}"
                )

        print("⏳ 等待图片上传与处理...", flush=True)
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

        debug_path_uploaded = str(dist_dir / "_douyin_step2_uploaded.png")
        page.screenshot(path=debug_path_uploaded)
        print(f"✅ 图片上传完成，截图已保存: {debug_path_uploaded}", flush=True)

        # 4. Fill in title
        print(f"📝 填写标题: {title[:20]}")
        title_selectors = [
            'input[placeholder*="标题"]',
            'input[placeholder*="填写标题"]',
            '[class*="title"] input',
            'input[maxlength]',
        ]

        title_filled = False
        filled_title_input = None
        for selector in title_selectors:
            try:
                title_input = page.locator(selector).first
                if title_input.is_visible(timeout=2000):
                    title_input.click()
                    title_input.fill(title[:20])
                    title_filled = True
                    filled_title_input = title_input
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
        filled_body_editor = None
        for selector in body_selectors:
            try:
                body_editor = page.locator(selector).first
                if body_editor.is_visible(timeout=2000):
                    body_editor.click()
                    time.sleep(0.3)
                    page.keyboard.type(body_text, delay=20)
                    body_filled = True
                    filled_body_editor = body_editor
                    print(f"   ✅ 正文已填写 (selector: {selector})")
                    break
            except Exception:
                continue

        if not body_filled:
            print("   ⚠️ 未找到正文编辑器")

        time.sleep(1)

        verified_fields = verify_post_fields(filled_title_input, filled_body_editor, title, body_text)
        debug_path_filled = str(dist_dir / "_douyin_step3_filled.png")
        page.screenshot(path=debug_path_filled)
        if review:
            page.screenshot(path=str(dist_dir / "douyin_review_content.png"), full_page=True)

        # 6. Action: Review, Publish or Save Draft
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        if review:
            print("\n" + "=" * 50)
            print("👀 页面已就绪！已为您停留在编辑页面供人工审核 (REVIEW MODE)")
            print("=" * 50)
            print("您可以直接在桌面浏览器中逐项核对：")
            print(f"  1. {len(image_paths)} 张图片与封面排版")
            print("  2. 标题、文案与话题标签")
            print("浏览器保留在编辑页，由您自行决定并手动发布；本流程不点击发布或暂存离开。")

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
                debug_path_draft = str(dist_dir / "_douyin_draft_debug.png")
                page.screenshot(path=debug_path_draft)
                raise RuntimeError(
                    f"❌ 未找到'保存草稿'按钮。截图: {debug_path_draft}\n"
                    "请检查抖音创作者后台页面结构是否有变化。"
                )

            print("\n" + "=" * 50, flush=True)
            print("🎯 === DOUYIN_DRAFT_SUCCESS ===", flush=True)
            print("🚀 抖音图文草稿保存成功！(DOUYIN DRAFT SAVED SUCCESSFULLY)", flush=True)
            print("=" * 50, flush=True)
            print("您现在可以前往抖音创作者后台'草稿箱'查看。", flush=True)

        time.sleep(2)

        # 7. Final verification
        draft_result_path = str(dist_dir / "douyin_draft_result.png")
        page.screenshot(path=draft_result_path)
        print(f"📸 最终草稿截图已保存至: {draft_result_path}", flush=True)

        if review:
            record = {
                "status": "review_ready", "url": page.url,
                "requested_image_count": len(image_paths),
                "images": image_paths, "verified_fields": verified_fields,
                "publish_clicked": False, "save_draft_clicked": False,
                "screenshots": ["douyin_review_content.png", "douyin_draft_result.png"],
            }
            (dist_dir / "douyin_review_result.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            page.evaluate("window.scrollTo(0, 0)")

        if not headless:
            print("\n🌟 浏览器窗口已在桌面打开并保持开启，方便您查看与确认！", flush=True)
            print("   （如需关闭，可直接手动关闭浏览器窗口）", flush=True)
            try:
                page.wait_for_event("close", timeout=0)
            except Exception:
                pass

        return True

    except Exception as e:
        try:
            screenshot_path = str(dist_dir / "_douyin_error.png")
            page.screenshot(path=screenshot_path)
            print(f"📸 错误截图已保存: {screenshot_path}", flush=True)
        except Exception:
            pass
        if review and not headless:
            print(f"❌ 上传未完整完成：{e}。保留浏览器供人工检查，不执行发布或保存草稿。", flush=True)
            try:
                page.wait_for_event("close", timeout=0)
            except Exception:
                pass
        raise
    finally:
        context.close()

