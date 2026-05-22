#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式分步美化与发布流程工具
"""
import argparse
import os
import sys
import re
import json

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from engine.compiler import convert_to_wechat_html
from engine.utils import load_image_mapping
from engine.highlight import load_highlight_rules, apply_highlight_rules
from engine.publisher import main as publisher_main
from scripts.compile import load_project_config, build_default_config


def run_stage_1(input_path, output_path, highlight_rules_path, image_mapping_path):
    print("\n🚀 [Stage 1/4] 正在进行文本整理与数值高亮...")
    if not os.path.exists(input_path):
        print(f"❌ Error: Source file not found: {input_path}")
        return False

    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    front_matter = ""
    body = content
    if content.startswith('---'):
        parts = re.split(r'^---', content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            front_matter = f"---{parts[1]}---"
            body = parts[2]

    # 1. Apply numeric highlight rules
    if highlight_rules_path and os.path.exists(highlight_rules_path):
        rules = load_highlight_rules(highlight_rules_path)
        body = apply_highlight_rules(body, rules)
        print("✔ 数值高亮处理完成")
    else:
        print("⚠ 找不到数值高亮规则，跳过数值高亮")

    # 2. Bold keywords (using image_mapping dictionary keys)
    if image_mapping_path and os.path.exists(image_mapping_path):
        mapping = load_image_mapping(image_mapping_path)
        
        # Regex to split tags so we don't modify them
        tag_pattern = re.compile(r'(!?\[.*?\]\(.*?\)(?:\{.*?\})?)')
        parts = tag_pattern.split(body)
        
        # Filter and sort keys by length descending to match longer keywords first
        sorted_keys = sorted([k for k in mapping.keys() if len(k.strip()) >= 2], key=len, reverse=True)
        
        for i in range(len(parts)):
            if i % 2 == 0:  # Plain text chunks
                chunk = parts[i]
                matches = []
                occupied = []
                
                # Pre-mark already bolded/bracketed regions to avoid double-bolding
                for pattern in [r'\*\*【[^】]+】\*\*', r'\*\*[^*]+\*\*', r'【[^】]+】']:
                    for m in re.finditer(pattern, chunk):
                        occupied.append((m.start(), m.end()))
                
                for key in sorted_keys:
                    escaped_key = re.escape(key)
                    for m in re.finditer(escaped_key, chunk):
                        start, end = m.start(), m.end()
                        # Check overlaps
                        overlap = False
                        for o_start, o_end in occupied:
                            if not (end <= o_start or start >= o_end):
                                overlap = True
                                break
                        if not overlap:
                            for m_start, m_end, _ in matches:
                                if not (end <= m_start or start >= m_end):
                                    overlap = True
                                    break
                        if not overlap:
                            matches.append((start, end, key))
                
                # Replace back-to-front to preserve offsets
                matches.sort(key=lambda x: x[0], reverse=True)
                for start, end, key in matches:
                    chunk = chunk[:start] + f"**【{key}】**" + chunk[end:]
                parts[i] = chunk
                
        body = "".join(parts)
        print("✔ 专有名词加粗处理完成")
    else:
        print("⚠ 找不到图片映射字典，跳过名词加粗")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(front_matter + body)
    return True


def run_stage_2(input_path, output_path, image_mapping_path):
    print("\n🚀 [Stage 2/4] 正在进行智能配图与样式注入...")
    if not os.path.exists(input_path):
        print(f"❌ Error: Stage 1 file not found: {input_path}")
        return False

    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    front_matter = ""
    body = content
    if content.startswith('---'):
        parts = re.split(r'^---', content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            front_matter = f"---{parts[1]}---"
            body = parts[2]

    if image_mapping_path and os.path.exists(image_mapping_path):
        mapping = load_image_mapping(image_mapping_path)
        
        tag_pattern = re.compile(r'(!?\[.*?\]\(.*?\)(?:\{.*?\})?)')
        parts = tag_pattern.split(body)
        
        sorted_keys = sorted([k for k in mapping.keys() if len(k.strip()) >= 2], key=len, reverse=True)
        
        for i in range(len(parts)):
            if i % 2 == 0:  # Plain text
                chunk = parts[i]
                matches = []
                occupied = []
                
                for key in sorted_keys:
                    escaped_key = re.escape(key)
                    # We match either **【key】** or key
                    pattern = re.compile(rf'\*\*【{escaped_key}】\*\*|{escaped_key}')
                    for m in pattern.finditer(chunk):
                        start, end = m.start(), m.end()
                        
                        # Check overlaps to prevent shorter keys matching inside longer matched/occupied keywords
                        overlap = False
                        for o_start, o_end in occupied:
                            if not (end <= o_start or start >= o_end):
                                overlap = True
                                break
                        if not overlap:
                            for m_start, m_end, _, _ in matches:
                                if not (end <= m_start or start >= m_end):
                                    overlap = True
                                    break
                        
                        if not overlap:
                            occupied.append((start, end))
                            already_has_image = False
                            
                            # Check if followed by a markdown image in the same chunk (ignoring bolding/brackets)
                            remaining = chunk[end:].lstrip('*_【】 ')
                            if remaining.startswith('!['):
                                already_has_image = True
                            
                            # Check if followed by a markdown image in the next chunk
                            if not remaining and i + 1 < len(parts):
                                next_part = parts[i+1].lstrip('*_【】 ')
                                if next_part.startswith('!['):
                                    already_has_image = True
                            
                            # Check if followed by a markdown image separated by a few connector words/chars (e.g. 的套装)
                            in_between = chunk[end:].strip('*_【】 ')
                            if not already_has_image and len(in_between) <= 5 and i + 1 < len(parts):
                                next_tag = parts[i+1]
                                if next_tag.startswith(f"![{key}]") or next_tag.startswith(f"![{key}("):
                                    already_has_image = True
                                    
                            if not already_has_image:
                                matched_str = m.group(0)
                                if key in ['黄星', '红星']:
                                    layout = '{type=icon}'
                                else:
                                    layout = '{type=avatar}'
                                formatted_str = f"{matched_str}![{key}](img://{key}){layout}"
                                matches.append((start, end, key, formatted_str))
                                
                # Replace back-to-front to preserve offsets
                matches.sort(key=lambda x: x[0], reverse=True)
                for start, end, _, formatted_str in matches:
                    chunk = chunk[:start] + formatted_str + chunk[end:]
                parts[i] = chunk
                
        body = "".join(parts)
        print("✔ 智能配图注入完成")
    else:
        print("⚠ 找不到图片映射字典，跳过配图注入")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(front_matter + body)
    return True


def run_stage_3(input_path, output_path, project_config):
    print("\n🚀 [Stage 3/4] 正在编译微信 HTML...")
    if not os.path.exists(input_path):
        print(f"❌ Error: Stage 2 file not found: {input_path}")
        return False

    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    input_dir = os.path.dirname(os.path.abspath(input_path))
    wechat_html, metadata = convert_to_wechat_html(content, project_config, input_dir=input_dir)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(wechat_html)

    meta_path = os.path.splitext(output_path)[0] + ".json"
    if metadata:
        import datetime
        def json_serial(obj):
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()
            raise TypeError("Type %s not serializable" % type(obj))
            
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2, default=json_serial)

    print("✔ HTML 编译与 CSS 行内合并完成")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="交互式分步美化与发布流程工具"
    )
    parser.add_argument("input_file", help="输入 Markdown 文件路径")
    parser.add_argument("--pack", help="内容包目录路径（如 packs/danke）")
    parser.add_argument("--theme", help="CSS 主题名称")

    args = parser.parse_args()

    input_path = os.path.abspath(args.input_file)
    if not os.path.exists(input_path):
        print(f"❌ Error: File not found: {input_path}")
        sys.exit(1)

    # 1. Resolve project config
    if args.pack:
        project_config = load_project_config(args.pack, args.theme)
    else:
        project_config = build_default_config(args.theme)

    highlight_rules_path = project_config.get("highlight_rules_path")
    image_mapping_path = project_config.get("image_mapping_path")

    # Determine stage paths
    base_dir = os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    
    stage1_path = os.path.join(base_dir, f"{base_name}_stage1.md")
    stage2_path = os.path.join(base_dir, f"{base_name}_stage2.md")
    stage3_path = os.path.join(base_dir, f"{base_name}_stage3_wechat.html")

    # ==================== STAGE 1 ====================
    run_stage_1(input_path, stage1_path, highlight_rules_path, image_mapping_path)
    while True:
        ans = input(
            f"\n➡️ [Stage 1] 文本高亮整理完成！文件已保存至:\n   {stage1_path}\n"
            "   (您可以在编辑器中打开该文件进行审查与修改)\n"
            "   请输入操作: [y] 继续至 Stage 2 | [r] 重新加载源文件重跑 Stage 1 | [q] 退出: "
        ).strip().lower()
        if ans in ('', 'y', 'yes'):
            break
        elif ans == 'r':
            run_stage_1(input_path, stage1_path, highlight_rules_path, image_mapping_path)
        elif ans == 'q':
            print("👋 已退出流程")
            sys.exit(0)

    # ==================== STAGE 2 ====================
    # Read from stage1_path to preserve manual edits
    run_stage_2(stage1_path, stage2_path, image_mapping_path)
    while True:
        ans = input(
            f"\n➡️ [Stage 2] 智能配图与样式注入完成！文件已保存至:\n   {stage2_path}\n"
            "   (您可以在编辑器中打开该文件进行审查与修改)\n"
            "   请输入操作: [y] 继续至 Stage 3 | [r] 重新加载 Stage 1 文件重跑 Stage 2 | [q] 退出: "
        ).strip().lower()
        if ans in ('', 'y', 'yes'):
            break
        elif ans == 'r':
            run_stage_2(stage1_path, stage2_path, image_mapping_path)
        elif ans == 'q':
            print("👋 已退出流程")
            sys.exit(0)

    # ==================== STAGE 3 ====================
    # Read from stage2_path to preserve manual edits
    run_stage_3(stage2_path, stage3_path, project_config)
    while True:
        ans = input(
            f"\n➡️ [Stage 3] 微信 HTML 编译完成！文件已保存至:\n   {stage3_path}\n"
            "   (您可以在浏览器或编辑器中查看和编辑生成的 HTML 效果)\n"
            "   请输入操作: [y] 继续至 Stage 4 (发布公众号) | [r] 重新加载 Stage 2 文件重跑 Stage 3 | [q] 退出: "
        ).strip().lower()
        if ans in ('', 'y', 'yes'):
            break
        elif ans == 'r':
            run_stage_3(stage2_path, stage3_path, project_config)
        elif ans == 'q':
            print("👋 已退出流程")
            sys.exit(0)

    # ==================== STAGE 4 ====================
    print("\n🚀 [Stage 4/4] 正在调用发布程序发布至公众号草稿箱...")
    
    # Resolve cover image path from metadata and pass as --cover argument
    cover_arg = []
    meta_path = os.path.splitext(stage3_path)[0] + ".json"
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            img_rel = meta.get('image')
            if img_rel:
                pack_root = os.path.dirname(project_config.get('assets_dir')) if project_config.get('assets_dir') else PROJECT_ROOT
                resolved_cover = os.path.abspath(os.path.join(pack_root, img_rel))
                if os.path.exists(resolved_cover):
                    cover_arg = ['--cover', resolved_cover]
                else:
                    if args.pack:
                        resolved_cover2 = os.path.abspath(os.path.join(args.pack, img_rel))
                        if os.path.exists(resolved_cover2):
                            cover_arg = ['--cover', resolved_cover2]
        except Exception as e:
            print(f"Warning resolving cover path: {e}")

    # Run publisher by redirecting argv
    sys.argv = ['publish.py', '-c', stage3_path] + cover_arg
    publisher_main()
    print("\n🎉 微信公众号发布流程结束！")



if __name__ == "__main__":
    main()
