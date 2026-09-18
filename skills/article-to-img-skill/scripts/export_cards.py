#!/usr/bin/env python3
"""
article-to-img-skill (原生 HTML 3:4 智能直切图工具)
标准工作流核心原则：
1. 严禁直接裸切 raw .md 源码：文章中的游戏宏图标 ({{钻石}}、{{装备}})、专属 Banner (img://article-top)、
   往期推荐卡片及主题排版样式，均由 danke-strategy-skill 编译注入到 _wechat.html 中。
2. 切图引擎必须以 danke-strategy-skill 编译后的 `_wechat.html` 为唯一标准源数据进行高保真渲染与切片。
3. 若传入 .md，会自动调用 danke-strategy-skill 全量编译器先行生成完整的 `_wechat.html`。
"""

import os
import sys
import argparse
import subprocess
import json
import re
from bs4 import BeautifulSoup
from PIL import Image

def get_playwright_engine():
    try:
        from patchright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright
        except ImportError:
            raise RuntimeError("请先安装 patchright 或 playwright: pip install patchright playwright")


def resolve_wechat_html(file_path):
    """
    确保输入为经过 danke-strategy-skill 编译解析后的 _wechat.html 文件。
    若传入的是 .md 文件，优先查找同级已编译好的 _wechat.html，或自动调用 danke-strategy-skill 进行全量编译。
    """
    abs_path = os.path.abspath(file_path)
    
    if abs_path.endswith('.html'):
        return abs_path

    if abs_path.endswith('.md'):
        wechat_html = os.path.splitext(abs_path)[0] + "_wechat.html"
        
        # 优先检测同目录下是否已存在编译完成的 _wechat.html
        if os.path.exists(wechat_html) and os.path.getmtime(wechat_html) >= os.path.getmtime(abs_path):
            print(f"📖 读取由 danke-strategy-skill 完整编译的微信富文本 HTML: {wechat_html}")
            return wechat_html

        # 若未编译或 .md 有更新，调用 danke-strategy-skill 编译器进行完整编译
        compile_script = "/home/guagua/workspace/skill/danke-strategy-skill/scripts/compile.py"
        if not os.path.exists(compile_script):
            compile_script = "/home/guagua/workspace/.agents/skills/danke-strategy-skill.backup/scripts/compile.py"

        if os.path.exists(compile_script):
            print(f"🔄 检测到 Markdown 文件，正在通过 danke-strategy-skill 编译全量宏图标与图床样式: {abs_path}")
            res = subprocess.run([sys.executable, compile_script, abs_path], capture_output=True, text=True)
            if res.returncode != 0:
                print(f"⚠ 编译输出: {res.stderr or res.stdout}")
            if os.path.exists(wechat_html):
                return wechat_html
            raise RuntimeError(f"❌ 编译失败，未生成 _wechat.html！请先使用 danke-strategy-skill 编译文章后再切图。")
        else:
            raise FileNotFoundError(f"❌ 未找到 danke-strategy-skill 编译器！请先生成 _wechat.html 后再进行切图。")

    raise ValueError(f"❌ 不支持的文件格式: {file_path}，请提供 _wechat.html 或 .md 文件！")


def direct_slice_html(input_file_path, output_dir=None, target_width=1080, target_height=1440, dpr=2, overlap_px=140):
    """
    将经过 danke-strategy-skill 编译的 _wechat.html 渲染并切片为 3:4 比例的高清图集
    """
    html_file_path = resolve_wechat_html(input_file_path)
    abs_html = os.path.abspath(html_file_path)
    html_dir = os.path.dirname(abs_html)

    if not output_dir:
        if os.path.basename(html_dir) == "dist":
            output_dir = os.path.join(html_dir, "原生网页直切图_3x4")
        else:
            output_dir = os.path.join(html_dir, "dist", "原生网页直切图_3x4")
    os.makedirs(output_dir, exist_ok=True)

    # 1. 清理旧切图文件与临时渲染文件
    for old_f in os.listdir(output_dir):
        if old_f.endswith(".png") or old_f.endswith(".html"):
            try:
                os.remove(os.path.join(output_dir, old_f))
            except Exception:
                pass

    print(f"📖 正在加载并预处理 HTML 页面: {abs_html}")
    
    # 2. 预处理 HTML 中的图片路径，确保本地相对路径转换为绝对 file:// 协议
    with open(abs_html, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')

    # 2.0 彻底剔除微信专属的“往期精彩推荐”与“扫码关注”容器
    for sec in list(soup.find_all('section')):
        text = sec.get_text()
        if '往期精彩推荐' in text or '扫码获取更多精彩' in text:
            sec.decompose()

    # 2.1 跨平台敏感引流话术与微信专属元素独立脱敏 (仅对临时切图 DOM 生效，严禁改动用户 Markdown 原文)
    for elem in list(soup.find_all(['p', 'span', 'div', 'section', 'blockquote'])):
        if not hasattr(elem, 'attrs') or elem.attrs is None:
            continue

        # 处理显式声明为 wechat-only 的元素
        classes = elem.attrs.get('class', [])
        if isinstance(classes, list) and any('wechat-only' in str(c) for c in classes):
            elem.decompose()
            continue
        elif isinstance(classes, str) and 'wechat-only' in classes:
            elem.decompose()
            continue

        # 仅针对叶子级/最小段落节点做敏感词判断，避免误删整篇父级 section/div
        has_child_blocks = bool(elem.find(['p', 'table', 'h1', 'h2', 'h3', 'section', 'ul', 'ol']))
        if has_child_blocks:
            continue

        text_content = elem.get_text().strip() if hasattr(elem, 'get_text') else ''
        if not text_content:
            continue

        sensitive_patterns = [
            r'公众号(后台)?回复',
            r'关注(微信)?公众号',
            r'点击上方蓝字',
            r'扫描二维码(关注)?',
            r'进会方式.*公众号'
        ]
        if any(re.search(pat, text_content) for pat in sensitive_patterns):
            # 若包含敏感引流词句，将其从切图 DOM 中安全移除
            elem.decompose()
            continue

    # 替换所有文本节点中的敏感外站引流词汇（仅在切图临时 DOM 中生效，保留原文）
    for text_node in list(soup.find_all(string=True)):
        if text_node.parent and text_node.parent.name not in ['script', 'style']:
            t = str(text_node)
            if '公众号' in t:
                new_t = re.sub(r'在我的公众号中', '在后续动态中', t)
                new_t = re.sub(r'在公众号中', '在后续动态中', new_t)
                new_t = re.sub(r'公众号', '动态', new_t)
                text_node.replace_with(new_t)

    # 2.2 预处理 HTML 中的图片路径，确保本地相对路径转换为绝对 file:// 协议
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if src and not src.startswith(('http://', 'https://', 'data:', 'file://')):
            candidates = [
                os.path.normpath(os.path.join(html_dir, src)),
                os.path.normpath(os.path.join(os.path.dirname(html_dir), src)),
                os.path.normpath(os.path.join(os.getcwd(), src)),
                os.path.normpath(os.path.join("/home/guagua/workspace/skill/danke-strategy-skill/packs/danke/assets/img", os.path.basename(src)))
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    img['src'] = 'file://' + cand
                    break

    patched_html_path = os.path.abspath(os.path.join(output_dir, "_temp_render.html"))
    with open(patched_html_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))

    file_url = "file://" + patched_html_path
    full_page_path = os.path.join(output_dir, "_full_page_clean.png")
    exported_files = []

    # 3. Playwright 渲染网页
    playwright_engine = get_playwright_engine()
    with playwright_engine() as p:
        browser_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--font-render-hinting=none'
        ]
        browser = p.chromium.launch(headless=True, args=browser_args)
        page = browser.new_page(viewport={'width': target_width, 'height': target_height}, device_scale_factor=dpr)

        try:
            page.goto(file_url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1000)
        except Exception as e:
            print(f"⚠ 页面加载轻微超时或中断 (继续渲染): {e}")

        # 4. 注入样式优化：字体统一、大图自适应、小图标内联、清理多余二维码
        page.evaluate("""() => {
            const fontStyle = document.createElement('style');
            fontStyle.innerHTML = `
                @font-face {
                    font-family: 'Segoe UI Emoji';
                    src: local('Segoe UI Emoji'), url('file:///mnt/c/Windows/Fonts/seguiemj.ttf');
                }
                * {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI Emoji", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
                }
                html, body {
                    font-size: 24px !important;
                }
                p, span, li, section, td, th {
                    font-size: 22px !important;
                    line-height: 1.7 !important;
                }
                h1 { font-size: 34px !important; line-height: 1.4 !important; }
                h2 { font-size: 28px !important; line-height: 1.4 !important; }
                h3 { font-size: 25px !important; line-height: 1.4 !important; }
            `;
            document.head.appendChild(fontStyle);

            document.body.style.margin = '0';
            document.body.style.padding = '50px 40px 40px 40px';
            document.body.style.background = '#ffffff';
            document.body.style.boxSizing = 'border-box';

            // 严格区分微型宏图标、article-top Banner 与普通大图
            document.querySelectorAll('img').forEach(img => {
                const alt = img.getAttribute('alt') || '';
                const src = img.getAttribute('src') || '';
                const styleW = parseInt(img.style.width) || parseInt(img.getAttribute('width')) || 0;
                const styleH = parseInt(img.style.height) || parseInt(img.getAttribute('height')) || 0;
                
                // 1. 判定微型宏图标 ({{钻石}}, {{装备}}等)
                const isIcon = img.classList.contains('macro-icon') ||
                               src.includes('/icons/') || 
                               src.includes('emoji') || 
                               (alt && (alt.startsWith('{{') || alt.endsWith('}}'))) ||
                               ((styleW > 0 && styleW <= 36) && (styleH > 0 && styleH <= 36));

                if (isIcon) {
                    img.style.width = '28px';
                    img.style.height = '28px';
                    img.style.verticalAlign = 'middle';
                    img.style.display = 'inline-block';
                    img.style.margin = '-3px 4px 0 4px';
                    img.style.boxShadow = 'none';
                    img.style.borderRadius = '0';
                    img.style.maxHeight = 'none';
                    img.style.maxWidth = 'none';
                    return;
                }

                // 2. 清理二维码
                if (alt.includes('二维码') || src.includes('二维码') || alt.includes('QR') || src.includes('qrcode')) {
                    let container = img.closest('section, div') || img;
                    container.remove();
                    return;
                }

                // 3. 顶部 Header Banner 专属样式
                if (alt === 'article-top' || src.includes('article-top')) {
                    img.style.width = '100%';
                    img.style.height = 'auto';
                    img.style.display = 'block';
                    img.style.marginTop = '5px';
                    img.style.marginBottom = '20px';
                    img.style.borderRadius = '14px';
                    img.style.boxShadow = '0 4px 12px rgba(0,0,0,0.06)';
                    return;
                }

                // 4. 普通大图默认缩放
                const rawStyle = img.getAttribute('style') || '';
                if (!rawStyle.includes('23%') && !rawStyle.includes('48%') && !rawStyle.includes('grid')) {
                    img.style.maxHeight = '480px';
                    img.style.width = 'auto';
                    img.style.maxWidth = '90%';
                    img.style.display = 'block';
                    img.style.margin = '16px auto';
                    img.style.borderRadius = '12px';
                    img.style.boxShadow = '0 4px 12px rgba(0,0,0,0.06)';
                }
            });

            // 5. 将包含 Grid 多栏图片的父段落 (<p>) 直接重构为 Flexbox 单行无缝平铺容器
            document.querySelectorAll('p').forEach(parent => {
                const imgs = Array.from(parent.querySelectorAll('img'));
                if (imgs.length === 0) return;

                const grid4Imgs = imgs.filter(img => {
                    const style = img.getAttribute('style') || '';
                    return style.includes('23%') || style.includes('grid4');
                });
                const grid2Imgs = imgs.filter(img => {
                    const style = img.getAttribute('style') || '';
                    return style.includes('48%') || style.includes('grid2');
                });

                if (grid4Imgs.length > 0) {
                    parent.style.display = 'flex';
                    parent.style.flexDirection = 'row';
                    parent.style.flexWrap = 'nowrap';
                    parent.style.justifyContent = 'space-between';
                    parent.style.alignItems = 'flex-start';
                    parent.style.width = '100%';
                    parent.style.margin = '12px 0';
                    parent.style.clear = 'both';

                    grid4Imgs.forEach(img => {
                        img.style.flex = '0 0 23.5%';
                        img.style.width = '23.5%';
                        img.style.maxWidth = '23.5%';
                        img.style.height = 'auto';
                        img.style.maxHeight = 'none';
                        img.style.display = 'block';
                        img.style.margin = '0';
                        img.style.borderRadius = '6px';
                        img.style.boxShadow = '0 3px 8px rgba(0,0,0,0.08)';
                        img.style.boxSizing = 'border-box';
                    });
                } else if (grid2Imgs.length > 0) {
                    parent.style.display = 'flex';
                    parent.style.flexDirection = 'row';
                    parent.style.flexWrap = 'nowrap';
                    parent.style.justifyContent = 'space-between';
                    parent.style.alignItems = 'flex-start';
                    parent.style.width = '100%';
                    parent.style.margin = '12px 0';
                    parent.style.clear = 'both';

                    grid2Imgs.forEach(img => {
                        img.style.flex = '0 0 48.5%';
                        img.style.width = '48.5%';
                        img.style.maxWidth = '48.5%';
                        img.style.height = 'auto';
                        img.style.maxHeight = 'none';
                        img.style.display = 'block';
                        img.style.margin = '0';
                        img.style.borderRadius = '8px';
                        img.style.boxShadow = '0 3px 8px rgba(0,0,0,0.08)';
                        img.style.boxSizing = 'border-box';
                    });
                }
            });

            // 清理底部的推荐卡片与关注二维码
            document.querySelectorAll('span, section, div, p, a').forEach(el => {
                const text = (el.innerText || '').trim();
                if (text === '下方查看' || text.includes('往期精彩推荐') || text.includes('扫码获取更多精彩') || text.includes('最新活动 · 特工 · 配件') || text.includes('长按识别二维码关注') || text.includes('【活动攻略】') || text.includes('【互动征集】') || text.includes('【宠物攻略】')) {
                    let box = el.closest('section[style*="margin: 30px auto"]') || el.closest('section[style*="border"]') || el.closest('a') || el;
                    if (box) {
                        box.remove();
                    }
                }
            });
        }""")

        page.wait_for_timeout(1500)

        # 收集语义断点 (H2, HR, H3, Section, P 等)
        breakpoints = page.evaluate("""() => {
            const points = [];
            document.querySelectorAll('h1, h2, hr, section, blockquote, p, tr, div').forEach(el => {
                const rect = el.getBoundingClientRect();
                const top = rect.top + window.scrollY;
                const bottom = rect.bottom + window.scrollY;
                if (rect.height > 0) {
                    let priority = 1;
                    if (el.tagName === 'H2') priority = 1000;
                    else if (el.tagName === 'HR') priority = 500;
                    else if (el.tagName === 'H3') priority = 200;
                    else if (el.tagName === 'P' || el.tagName === 'SECTION') priority = 10;
                    points.push({ top: top, bottom: bottom, priority: priority, tag: el.tagName });
                }
            });
            return points;
        }""")

        full_height = page.evaluate("document.body.scrollHeight")
        print(f"📏 清洗后网页渲染高度: {full_height}px, 单张目标高度: {target_height}px")

        page.screenshot(path=full_page_path, full_page=True)
        browser.close()

    # 5. 高清切图计算 (智能语义分割，互斥零重复，保护标题与图片完整性)
    full_img = Image.open(full_page_path)
    img_w, img_h = full_img.size

    scale = img_w / target_width
    card_w_px = int(target_width * dpr)
    card_h_px = int(target_height * dpr)

    if full_height <= target_height * 1.15:
        # 单张卡片模式
        canvas = Image.new("RGB", (card_w_px, card_h_px), (255, 255, 255))
        canvas.paste(full_img, (0, 0))
        save_path = os.path.join(output_dir, "01_切图.png")
        canvas.save(save_path, "PNG", quality=95)
        print(f"  ✅ 单图已自适应保存: 01_切图.png ({canvas.size})")
        exported_files.append(save_path)
    else:
        # 多图智能语义分割模式：互斥无缝推进，彻底杜绝内容重复截取与图片截断
        current_y = 0
        cards = []

        while current_y < full_height - 30:
            remaining_h = full_height - current_y
            if remaining_h <= target_height * 1.25:
                cards.append((current_y, full_height))
                break

            # 优先检测当前卡片范围内的下一个章节 H2 大标题断点（距离起点至少 0.75 * target_height）
            min_h2_top = current_y + int(target_height * 0.75)
            max_h2_top = current_y + int(target_height * 1.45)
            h2_cands = [bp for bp in breakpoints if bp["priority"] >= 1000 and min_h2_top <= bp["top"] <= max_h2_top]
            if h2_cands:
                h2_top = h2_cands[0]["top"]
                # 检查 H2 前方 60px 内是否有配套的分割线 HR
                hr_before = [bp for bp in breakpoints if bp["priority"] >= 500 and h2_top - 60 <= bp["top"] <= h2_top]
                if hr_before:
                    best_cut = hr_before[0]["top"]
                else:
                    best_cut = h2_top - 10
            else:
                min_cut = current_y + int(target_height * 0.65)
                ideal_cut = current_y + target_height
                max_cut = current_y + int(target_height * 1.15)
                cands = [bp for bp in breakpoints if min_cut <= bp["top"] <= max_cut]
                if cands:
                    cands.sort(key=lambda x: (-x["priority"], abs(x["top"] - ideal_cut)))
                    best_cut = cands[0]["top"]
                else:
                    best_cut = ideal_cut

            cards.append((current_y, best_cut))
            current_y = best_cut

        print(f"✂️ 智能语义拆分为 {len(cards)} 张 3:4 高清独立卡片（互斥零重复）...")

        for i, (y_start, y_end) in enumerate(cards):
            sy = int(round(y_start * scale))
            ey = int(round(y_end * scale))
            crop_h = ey - sy

            cropped = full_img.crop((0, sy, img_w, ey))

            # 若内容高度略超单张标准高度，等比微缩至画布高度，保持整洁
            if crop_h > card_h_px:
                ratio = card_h_px / crop_h
                new_w = int(cropped.width * ratio)
                scaled_crop = cropped.resize((new_w, card_h_px), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (card_w_px, card_h_px), (255, 255, 255))
                paste_x = (card_w_px - new_w) // 2
                canvas.paste(scaled_crop, (paste_x, 0))
            else:
                canvas = Image.new("RGB", (card_w_px, card_h_px), (255, 255, 255))
                canvas.paste(cropped, (0, 0))

            file_name = f"{i+1:02d}_切图.png"
            save_path = os.path.join(output_dir, file_name)
            canvas.save(save_path, "PNG", quality=95)
            print(f"  ✅ 已生成 3:4 独立切图: {file_name} (y: {sy}px ~ {ey}px, 内容高: {crop_h}px / 画布: {card_h_px}px)")
            exported_files.append(save_path)

    # 6. 清理临时渲染文件
    for temp_f in [full_page_path, patched_html_path]:
        if os.path.exists(temp_f):
            try:
                os.remove(temp_f)
            except Exception:
                pass

    # 7. 提取元数据生成发布文案
    meta_json_path = os.path.splitext(abs_html)[0] + ".json"
    title = "最新图文攻略"
    tags_str = "#弹壳特攻队 #弹壳特攻队攻略 #游戏攻略 #小红书图文 #抖音图文"
    summary = "高清无损长图拆解，建议收藏保存～"

    if os.path.exists(meta_json_path):
        try:
            with open(meta_json_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                title = meta.get('social_title') or meta.get('title') or title
                summary = meta.get('summary') or summary
                if meta.get('tags'):
                    tags_str = " ".join([f"#{t}" for t in meta['tags']])
        except Exception:
            pass

    copywriting_path = os.path.join(output_dir, "copywriting.txt")
    with open(copywriting_path, 'w', encoding='utf-8') as f:
        f.write(f"【小红书/抖音图文发布文案】\n\n")
        f.write(f"📌 {title}\n\n")
        f.write(f"📝 {summary}\n\n")
        f.write(f"💬 高清无损长图拆解，建议收藏保存～\n\n")
        f.write(f"{tags_str}\n")

    print(f"\n🎉 原生网页 3:4 切图制作完成！全套 {len(exported_files)} 张高清图片保存在:\n   {output_dir}\n")
    return exported_files, output_dir


def main():
    parser = argparse.ArgumentParser(description="微信文章 3:4 高清直切图工具（以 danke-strategy-skill 编译后的 _wechat.html 为标准源）")
    parser.add_argument("input_path", help="HTML 文件路径 (_wechat.html) 或 Markdown 源码路径 (.md)")
    parser.add_argument("-o", "--output", help="输出图片目录", default=None)
    parser.add_argument("--width", type=int, default=1080, help="卡片基准宽度 (默认: 1080)")
    parser.add_argument("--height", type=int, default=1440, help="卡片基准高度 (默认: 1440)")
    parser.add_argument("--dpr", type=int, default=2, help="设备像素比 DPR (默认: 2，生成 2160x2880)")
    parser.add_argument("--overlap", type=int, default=140, help="多图重叠像素深度 (默认: 140)")

    args = parser.parse_args()
    direct_slice_html(
        args.input_path,
        output_dir=args.output,
        target_width=args.width,
        target_height=args.height,
        dpr=args.dpr,
        overlap_px=args.overlap
    )


if __name__ == "__main__":
    main()
