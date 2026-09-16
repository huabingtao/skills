#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
article-to-img-skill (Direct Page Slicing Mode + Smart Tail Merging)
直接渲染微信 HTML 原生网页，自动过滤/移除末尾“往期精彩”与“微信二维码”（防止抖音/小红书下架屏蔽），
按 3:4 (1080x1440) 比例带段落缝隙避让切图，并将末尾剩余内容合并至前一张，拒绝半截空白卡片！
"""

import os
import sys
import argparse
from playwright.sync_api import sync_playwright
from PIL import Image


def direct_slice_html(html_file_path, output_dir=None, target_width=1080, target_height=1440):
    """
    直接渲染原生 HTML 页面，自动清洗防下架节点，按 3:4 比例切割，末尾短内容智能合并
    """
    abs_html = os.path.abspath(html_file_path)
    if not output_dir:
        output_dir = os.path.join(os.path.dirname(abs_html), "原生网页直切图_3x4")
    os.makedirs(output_dir, exist_ok=True)

    print(f"📖 正在直接加载渲染原生 HTML 页面: {abs_html}")
    file_url = "file://" + abs_html

    exported_files = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': target_width, 'height': target_height}, device_scale_factor=2)
        
        page.goto(file_url, wait_until="networkidle")

        # 清洗/移除二维码与页脚往期精彩推荐节点
        page.evaluate("""() => {
            document.body.style.margin = '0';
            document.body.style.padding = '30px 40px';
            document.body.style.background = '#ffffff';
            document.body.style.boxSizing = 'border-box';

            // 移除二维码容器
            document.querySelectorAll('img').forEach(img => {
                const alt = img.getAttribute('alt') || '';
                const src = img.getAttribute('src') || '';
                if (alt.includes('二维码') || src.includes('二维码') || alt.includes('QR') || src.includes('qrcode')) {
                    let container = img.closest('section, div') || img;
                    container.remove();
                }
            });

            // 仅清理底部的推荐卡片与二维码，严禁删除主页面容器
            document.querySelectorAll('span, section, div, p').forEach(el => {
                const text = (el.innerText || '').trim();
                if (text === '下方查看' || text === '往期精彩推荐' || text === '扫码获取更多精彩') {
                    let box = el.closest('section[style*="margin: 30px auto"]') || el.closest('section[style*="border"]') || el.closest('a');
                    if (box && box.parentElement && box.parentElement !== document.body && box.parentElement.children.length > 1) {
                        box.remove();
                    }
                }
            });

        }""")


        full_height = page.evaluate("document.body.scrollHeight")
        print(f"📏 清洗后网页总高度: {full_height}px, 目标卡片高度: {target_height}px")

        element_bottoms = page.evaluate("""() => {
            const elems = document.querySelectorAll('p, section, div, h1, h2, h3, li, tr, table, img');
            const bottoms = [];
            for (let el of elems) {
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') continue;
                
                const rect = el.getBoundingClientRect();
                if (rect.height > 5 && rect.bottom > 0) {
                    bottoms.push(Math.round(rect.bottom + window.scrollY));
                }
            }
            return Array.from(new Set(bottoms)).sort((a, b) => a - b);
        }""")

        full_page_path = os.path.join(output_dir, "_full_page_clean.png")
        page.screenshot(path=full_page_path, full_page=True)
        browser.close()

    full_img = Image.open(full_page_path)
    img_w, img_h = full_img.size

    scale = img_w / target_width
    scaled_target_h = int(target_height * scale)
    scaled_bottoms = [int(b * scale) for b in element_bottoms]

    y_top = 0
    slice_idx = 1
    last_slice_range = None

    while y_top < img_h:
        remaining_h = img_h - y_top

        # 智能末尾合并：如果剩余高度不足 0.75 倍卡片高度（即半截），直接追加合并到前一张切图上！
        if remaining_h <= int(scaled_target_h * 0.75) and exported_files and last_slice_range:
            last_save_path = exported_files.pop()
            prev_top, _ = last_slice_range
            
            merged_crop_box = (0, prev_top, img_w, img_h)
            merged_img = full_img.crop(merged_crop_box)
            
            card_canvas = Image.new("RGB", (img_w, merged_img.height), (255, 255, 255))
            card_canvas.paste(merged_img, (0, 0))
            card_canvas.save(last_save_path, "PNG")
            
            print(f"  ⚡ 智能将末尾剩余内容完美合并至前一张切图 ({os.path.basename(last_save_path)})，消灭半截留白卡片！")
            exported_files.append(last_save_path)
            break

        ideal_bottom = y_top + scaled_target_h

        if ideal_bottom >= img_h:
            y_bottom = img_h
        else:
            search_min = ideal_bottom - int(180 * scale)
            candidates = [b for b in scaled_bottoms if search_min <= b <= ideal_bottom]
            
            if candidates:
                y_bottom = max(candidates)
            else:
                y_bottom = ideal_bottom

        crop_box = (0, y_top, img_w, y_bottom)
        slice_img = full_img.crop(crop_box)

        card_canvas = Image.new("RGB", (img_w, scaled_target_h), (255, 255, 255))
        card_canvas.paste(slice_img, (0, 0))

        file_name = f"{slice_idx:02d}_切图.png"
        save_path = os.path.join(output_dir, file_name)
        card_canvas.save(save_path, "PNG")
        print(f"  ✅ 已生成 3:4 切图: {file_name} (y: {y_top}px ~ {y_bottom}px)")

        exported_files.append(save_path)
        last_slice_range = (y_top, y_bottom)

        y_top = y_bottom
        slice_idx += 1

    if os.path.exists(full_page_path):
        os.remove(full_page_path)

    copywriting_path = os.path.join(output_dir, "copywriting.txt")
    with open(copywriting_path, 'w', encoding='utf-8') as f:
        f.write(f"【小红书/抖音图文发布文案】\n\n")
        f.write(f"📌 《弹壳特攻队》最新图文攻略\n\n")
        f.write(f"💬 高清无损长图拆解，建议收藏保存～\n\n")
        f.write(f"#弹壳特攻队 #弹壳特攻队攻略 #游戏攻略 #小红书图文\n")

    print(f"\n🎉 原生网页 3:4 切图制作完成 (已合并末尾短卡片，拒绝留白)！全套图片保存在:\n   {output_dir}\n")
    return exported_files, output_dir


def main():
    parser = argparse.ArgumentParser(description="微信原生 HTML 页面 3:4 直切图工具（支持智能尾部合并）")
    parser.add_argument("html_path", help="微信文章 _wechat.html 路径")
    parser.add_argument("-o", "--output", help="输出图片目录", default=None)

    args = parser.parse_args()
    direct_slice_html(args.html_path, args.output)


if __name__ == "__main__":
    main()
