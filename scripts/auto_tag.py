#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_tag.py - 弹壳特攻队专有名词自动宏标签标注工具
扫描 Markdown 文本，自动识别 image_mapping.json 中定义的游戏实体名称（如特工、载具、核心、收藏品、宠物等），
并为其添加 {{实体名}} 宏标签包裹，避免重复包裹或破坏已有链接/图片/标题语法。
"""

import os
import sys
import json
import re
import argparse

def load_keywords(mapping_path):
    if not os.path.exists(mapping_path):
        return []
    with open(mapping_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    
    # Filter out single-character or overly generic keys to avoid false positives
    ignored_keys = {'金', '鱼', '马', '狼', '砖', '盾', '鞋', '甲', '枪', '剑', '书', '珠', '星', '黄星'}
    
    keywords = [k for k in mapping.keys() if len(k) >= 2 and k not in ignored_keys]
    # Sort by length descending so longer compound names match first (e.g. "金牛座星辉" before "金牛座")
    keywords.sort(key=len, reverse=True)
    return keywords

def auto_tag_text(content: str, keywords: list) -> str:
    # Separate frontmatter if present
    frontmatter = ""
    body = content
    if content.startswith("---"):
        parts = re.split(r"^---", content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            frontmatter = f"---{parts[1]}---"
            body = parts[2]

    # Split body into protected tokens (code blocks, existing tags {{...}}, markdown images/links !?[...](...))
    token_pattern = re.compile(r'(`[^`]+`|\{\{[^{}]+\}\}|!?\[[^\]]*\]\([^)]+\)|#+[^\n]+)')
    segments = token_pattern.split(body)

    for idx, seg in enumerate(segments):
        # Only process regular text outside protected tokens
        if not seg or token_pattern.match(seg):
            continue

        for kw in keywords:
            # Match keyword if not preceded/succeeded by curly braces or part of markdown link
            pattern = re.compile(rf'(?<!\{{)(?<!\{{\{{)\b({re.escape(kw)})\b(?!}})(?!\}})', flags=re.IGNORECASE)
            # For Chinese characters without word boundaries:
            zh_pattern = re.compile(rf'(?<!\{{)(?<!\{{\{{)({re.escape(kw)})(?!}})(?!\}})')
            seg = zh_pattern.sub(r'{{\1}}', seg)

        segments[idx] = seg

    return frontmatter + "".join(segments)

def process_file(file_path: str, mapping_path: str, in_place: bool = False, output_path: str = None):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    keywords = load_keywords(mapping_path)
    tagged = auto_tag_text(content, keywords)

    out_file = file_path if in_place else (output_path or file_path)
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(tagged)
    print(f"✅ 成功完成宏标签自动标注: {out_file}")

def main():
    parser = argparse.ArgumentParser(description="自动为 Markdown 中的弹壳专有名词添加 {{宏标签}}")
    parser.add_argument("input_file", help="输入 Markdown 文件路径")
    parser.add_argument("-m", "--mapping", default="/home/guagua/workspace/skill/danke-strategy-skill/packs/danke/image_mapping.json", help="image_mapping.json 路径")
    parser.add_argument("-i", "--in-place", action="store_true", help="直接原地修改输入文件")
    parser.add_argument("-o", "--output", help="输出文件路径")
    args = parser.parse_args()

    process_file(args.input_file, args.mapping, args.in_place, args.output)

if __name__ == "__main__":
    main()
