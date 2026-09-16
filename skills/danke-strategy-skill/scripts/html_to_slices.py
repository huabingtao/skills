#!/usr/bin/env python3
import sys
import os
from pathlib import Path
from patchright.sync_api import sync_playwright

def convert_html_to_slices(html_file_path: str, out_dir_path: str = None) -> list:
    html_file = Path(html_file_path).resolve()
    if not html_file.exists():
        print(f"❌ 错误: HTML 文件不存在: {html_file}")
        sys.exit(1)

    if out_dir_path:
        out_dir = Path(out_dir_path).resolve()
    else:
        out_dir = html_file.parent / "原生网页直切图_3x4"
    
    out_dir.mkdir(parents=True, exist_ok=True)

    generated_files = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1080, "height": 1440})
        
        page.goto(html_file.as_uri())
        page.wait_for_timeout(1000)

        # 注入 Emoji & 常用中文字体
        page.add_style_tag(content="""
            @import url('https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&display=swap');
            body, div, h1, h2, h3, h4, p, span, li, td, th {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI Emoji", "Noto Color Emoji", "Apple Color Emoji", "Noto Sans SC", sans-serif !important;
            }
        """)

        # 动态重构与拆解页面 DOM，生成 Perfect 3:4 比例卡片集
        js_code = """() => {
            // 1. 精准删除尾部二维码与免责声明（避免误删正文容器）
            const allElements = Array.from(document.querySelectorAll('section, div, p, footer, h4'));
            allElements.forEach(el => {
                const text = (el.innerText || '').trim();
                if ((text.includes('扫码获取') || text.includes('长按识别二维码')) && el.children.length < 5) {
                    el.remove();
                } else if (text.startsWith('【免责声明】') && el.tagName.toLowerCase() === 'p') {
                    el.remove();
                } else if (text.includes('引用链接') && el.tagName.toLowerCase() === 'h4') {
                    el.remove();
                }
            });

            // 2. 网址自动打码（防止平台外链检测风控）
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
            let node;
            while (node = walker.nextNode()) {
                if (node.nodeValue) {
                    node.nodeValue = node.nodeValue.replace(/https?:\/\/[^\s<\[\]]+/gi, '[ 网址已打码 · 见主页链接 ]');
                    node.nodeValue = node.nodeValue.replace(/cloudcalc\.guaguahub\.cn/gi, 'cloudcalc.***.cn');
                    node.nodeValue = node.nodeValue.replace(/guaguahub\.cn/gi, '***.cn');
                }
            }

            // 3. 递归扁平化拆解嵌套容器，提取独立的 Content Blocks
            const rawBlocks = [];
            function collectBlocks(container) {
                Array.from(container.children).forEach(child => {
                    const tag = child.tagName ? child.tagName.toLowerCase() : '';
                    // 如果 child 是包含多个子段落/图片的大 section/div 容器，则进行深度拆解
                    if (['section', 'div', 'article', 'main'].includes(tag) && child.children.length > 0) {
                        collectBlocks(child);
                    } else {
                        rawBlocks.push(child);
                    }
                });
            }

            const rootContainer = document.querySelector('div') || document.querySelector('section') || document.body;
            collectBlocks(rootContainer);

            // 4. 重置 body 结构
            const body = document.body;
            body.innerHTML = '';
            body.style.padding = '0';
            body.style.margin = '0';
            body.style.backgroundColor = '#f1f5f9';

            const MAX_INNER_HEIGHT = 1240;
            const cards = [];

            function createCardElement() {
                const card = document.createElement('div');
                card.className = 'slice-card';
                card.style.width = '1080px';
                card.style.height = '1440px';
                card.style.boxSizing = 'border-box';
                card.style.padding = '60px 55px 90px';
                card.style.backgroundColor = '#ffffff';
                card.style.display = 'flex';
                card.style.flexDirection = 'column';
                card.style.justifyContent = 'flex-start';
                card.style.alignItems = 'stretch';
                card.style.position = 'relative';
                card.style.overflow = 'hidden';
                card.style.borderBottom = '12px solid #f1f5f9';

                const inner = document.createElement('div');
                inner.className = 'card-inner';
                inner.style.width = '100%';
                card.appendChild(inner);

                return { card, inner };
            }

            let currentObj = createCardElement();
            body.appendChild(currentObj.card);
            cards.push(currentObj);

            // 5. 逐个处理与追加元素
            rawBlocks.forEach(element => {
                // 重设图片样式，防止右侧截断/横向溢出
                const imgs = element.tagName.toLowerCase() === 'img' ? [element] : element.querySelectorAll('img');
                imgs.forEach(img => {
                    img.style.maxWidth = '100%';
                    img.style.width = '100%';
                    img.style.height = 'auto';
                    img.style.maxHeight = '650px';
                    img.style.objectFit = 'contain';
                    img.style.display = 'block';
                    img.style.margin = '16px auto';
                    img.style.borderRadius = '12px';
                    img.style.boxSizing = 'border-box';
                });

                // 重设块元素在 1080px 宽度下的外边距与最大宽度
                element.style.maxWidth = '100%';
                element.style.boxSizing = 'border-box';
                element.style.marginLeft = '0';
                element.style.marginRight = '0';

                const tag = element.tagName ? element.tagName.toLowerCase() : '';
                if (tag === 'h1' || tag === 'h2') {
                    element.style.fontSize = '30px';
                    element.style.lineHeight = '1.45';
                    element.style.marginTop = '22px';
                    element.style.marginBottom = '18px';
                    element.style.fontWeight = 'bold';
                    element.style.color = '#0f172a';
                } else if (tag === 'h3' || tag === 'h4') {
                    element.style.fontSize = '26px';
                    element.style.lineHeight = '1.5';
                    element.style.marginTop = '18px';
                    element.style.marginBottom = '14px';
                    element.style.fontWeight = 'bold';
                    element.style.color = '#1e293b';
                } else if (tag === 'p' || tag === 'li') {
                    element.style.fontSize = '23px';
                    element.style.lineHeight = '1.75';
                    element.style.marginBottom = '18px';
                    element.style.color = '#334155';
                }

                currentObj.inner.appendChild(element);

                // 判断高度溢出，自动分卡
                if (currentObj.inner.scrollHeight > MAX_INNER_HEIGHT && currentObj.inner.children.length > 1) {
                    currentObj.inner.removeChild(element);

                    currentObj = createCardElement();
                    body.appendChild(currentObj.card);
                    cards.push(currentObj);

                    currentObj.inner.appendChild(element);
                }
            });

            // 6. 添加精美品牌页脚与页码
            const totalCards = cards.length;
            cards.forEach(({ card, inner }, idx) => {
                const footer = document.createElement('div');
                footer.style.position = 'absolute';
                footer.style.bottom = '24px';
                footer.style.left = '55px';
                footer.style.right = '55px';
                footer.style.display = 'flex';
                footer.style.justifyContent = 'space-between';
                footer.style.alignItems = 'center';
                footer.style.paddingTop = '16px';
                footer.style.borderTop = '2px solid #f1f5f9';

                const brandPill = document.createElement('div');
                brandPill.style.display = 'inline-flex';
                brandPill.style.alignItems = 'center';
                brandPill.style.backgroundColor = '#f8fafc';
                brandPill.style.border = '1px solid #e2e8f0';
                brandPill.style.borderRadius = '20px';
                brandPill.style.padding = '6px 16px';
                brandPill.style.fontSize = '17px';
                brandPill.style.color = '#475569';
                brandPill.style.fontWeight = '600';
                brandPill.innerHTML = `💡 弹壳特攻队攻略组 · 独家拆解`;

                const pageBadge = document.createElement('div');
                pageBadge.style.fontSize = '18px';
                pageBadge.style.color = '#64748b';
                pageBadge.style.fontWeight = 'bold';
                pageBadge.innerText = `第 ${idx + 1} 页 / 共 ${totalCards} 页`;

                footer.appendChild(brandPill);
                footer.appendChild(pageBadge);
                card.appendChild(footer);
            });
        }"""

        page.evaluate(js_code)
        page.wait_for_timeout(1000)

        for old in out_dir.glob("*.png"):
            old.unlink()

        num_cards = page.evaluate("document.querySelectorAll('.slice-card').length")
        print(f"✂️  成功生成 {num_cards} 张 3:4 动态美化卡片")

        for i in range(num_cards):
            card_handle = page.query_selector_all(".slice-card")[i]
            out_file = out_dir / f"slice_{i+1:02d}.png"
            card_handle.screenshot(path=str(out_file))
            generated_files.append(str(out_file))
            print(f"  ✅ [{i+1}/{num_cards}] {out_file.name}")

        browser.close()

    return generated_files

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python html_to_slices.py <path_to_html> [output_dir]")
        sys.exit(1)
    
    html_input = sys.argv[1]
    out_input = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_html_to_slices(html_input, out_input)
