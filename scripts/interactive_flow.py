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
# wechat publishing moved to wechat-publisher-skill (see skills/wechat-publisher-skill/)
from scripts.compile import load_project_config, build_default_config


def is_attribute_mention(text_after):
    text_after = text_after.strip()
    if text_after.startswith('的'):
        text_after = text_after[1:].strip()
    
    # Extract continuous alphanumeric/Chinese characters (stop at punctuation or space)
    match = re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9]+', text_after)
    if not match:
        return False
    
    word_block = match.group(0)
    
    suffixes = [
        '数量', '伤害', '属性', '等级', '增益', '百分比', '加成', '词条', '效果', 
        '时间', '频率', '速度', '范围', '冷却', 'cd', 'CD', '同步率', '共鸣', 
        '同步', '血脉', '充能', '层数', '目标', '系数', '减伤', '控场', '爆发', '上限',
        '攻击', '生命', '防御', '增伤', '减伤', '暴击', '暴击率', '命中率', '闪避率',
        '回复', '治疗', '盾伤', '吸血', '穿透', '攻速', '移速'
    ]
    for s in suffixes:
        idx = word_block.find(s)
        if idx != -1 and idx <= 3:
            return True
    return False


def is_in_header(chunk, start):
    line_start = chunk.rfind('\n', 0, start) + 1
    return chunk[line_start:start].lstrip().startswith('#')


def ensure_output_directory(output_path):
    """Ensure the parent directory for output_path exists."""
    if not output_path:
        return
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)


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

    # 2. 关键词加粗 (已根据用户需求移除自动包裹逻辑)

    # Ensure the output parent directory exists
    ensure_output_directory(output_path)
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
        tag_pattern = re.compile(r'(!?\[.*?\]\(.*?\)(?:\{.*?\})?)')
        parts = tag_pattern.split(body)
        
        for i in range(len(parts)):
            if i % 2 == 1:  # Tag
                tag = parts[i]
                if tag.startswith('[') and 'img://' in tag:
                    parts[i] = '!' + tag
                    
        body = "".join(parts)
        print("✔ 智能配图转换完成")
    else:
        print("⚠ 找不到图片映射字典，跳过配图注入")

    # Ensure the output parent directory exists
    ensure_output_directory(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(front_matter + body)
    return True


def run_stage_3(input_path, output_path, project_config, source_dir=None):
    print("\n🚀 [Stage 3/4] 正在编译微信 HTML...")
    if not os.path.exists(input_path):
        print(f"❌ Error: Stage 2 file not found: {input_path}")
        return False

    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    input_dir = source_dir or os.path.dirname(os.path.abspath(input_path))
    if os.path.basename(input_dir) == "dist":
        input_dir = os.path.dirname(input_dir)
    local_config = project_config.copy()
    local_config["highlight_rules_path"] = None
    wechat_html, metadata = convert_to_wechat_html(content, local_config, input_dir=input_dir)
    # Metadata travels with dist HTML; local covers must remain resolvable there.
    for key in ("cover", "image", "cover_vertical"):
        value = metadata.get(key)
        if isinstance(value, str) and not value.startswith(("http://", "https://", "data:", "img://")):
            candidate = os.path.abspath(os.path.join(input_dir, value))
            if os.path.isfile(candidate):
                metadata[key] = candidate


    # Ensure the output parent directory exists
    ensure_output_directory(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(wechat_html)

    meta_path = os.path.splitext(output_path)[0] + ".json"
    if metadata:
        import datetime
        def json_serial(obj):
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()
            raise TypeError("Type %s not serializable" % type(obj))
        # Ensure metadata parent directory exists as well
        ensure_output_directory(meta_path)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2, default=json_serial)

    print("✔ HTML 编译与 CSS 行内合并完成")
    
    # 统计正文字数并评估公众号文中广告档位
    wc = get_article_word_count(content)
    tier_msg = format_ad_tier_status(wc)
    print(f"  {tier_msg}")
    
    return True


def get_article_word_count(text: str) -> int:
    """计算文章纯正文字数 (去除 Frontmatter、HTML标签、图片链接及宏语法)"""
    if text.startswith("---"):
        parts = re.split(r"^---", text, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            text = parts[2]
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'!\[.*?\]\(.*?\)', '', clean)
    clean = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean)
    clean = re.sub(r'\{\{.*?\}\}', '', clean)
    zh_chars = len(re.findall(r'[\u4e00-\u9fa5]', clean))
    en_words = len(re.findall(r'[a-zA-Z0-9]+', clean))
    return zh_chars + en_words


def format_ad_tier_status(word_count: int) -> str:
    if word_count <= 350:
        return f"📊 文章字数: {word_count} 字 [档位一: 1~300字 · 极短快讯/竞猜档 (无文中广告)]"
    elif 480 <= word_count <= 720:
        return f"📊 文章字数: {word_count} 字 [档位二: 550字左右 · 单条文中广告黄金档 ⭐ (稳定支持 1 条文中广告)]"
    elif 780 <= word_count <= 1150:
        return f"📊 文章字数: {word_count} 字 [档位三: 850字左右 · 双条文中广告深度档 ⭐⭐ (稳定支持 2 条文中广告)]"
    elif 350 < word_count < 480:
        return f"📊 文章字数: {word_count} 字 [提示: 略低于 1 条广告基准线 (~550字)，如需插入广告建议微调充实]"
    elif 720 < word_count < 780:
        return f"📊 文章字数: {word_count} 字 [提示: 处于单条与双条广告过渡区间，支持 1 条广告，如需双广告建议充实至 850+ 字]"
    else:
        return f"📊 文章字数: {word_count} 字 [超长深度长文 · 稳定支持 2 条以上文中广告]"


def main():
    parser = argparse.ArgumentParser(
        description="交互式分步美化与发布流程工具"
    )
    parser.add_argument("input_file", help="输入 Markdown 文件路径")
    parser.add_argument("--pack", help="内容包目录路径（如 packs/danke）")
    parser.add_argument("--theme", help="CSS 主题名称")
    parser.add_argument('-y', '--yes', '--non-interactive', action='store_true', help='运行非交互模式，无需用户确认直接完成所有阶段')
    parser.add_argument('-n', '--new', '--force-new', dest='force_new', action='store_true', help='强制创建新草稿')

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

    # Determine stage paths (Auto-isolated in dist/ directory)
    base_dir = os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    
    dist_dir = os.path.join(base_dir, "dist")
    os.makedirs(dist_dir, exist_ok=True)
    
    stage1_path = os.path.join(dist_dir, f"{base_name}_stage1.md")
    stage2_path = os.path.join(dist_dir, f"{base_name}_stage2.md")
    stage3_path = os.path.join(dist_dir, f"{base_name}_stage3_wechat.html")

    # ==================== STAGE 1 ====================
    run_stage_1(input_path, stage1_path, highlight_rules_path, image_mapping_path)
    if not args.yes:
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
    else:
        print(f"\n➡️ [Stage 1] 文本高亮整理完成！文件已保存至:\n   {stage1_path}")

    # ==================== STAGE 2 ====================
    # Read from stage1_path to preserve manual edits
    run_stage_2(stage1_path, stage2_path, image_mapping_path)
    if not args.yes:
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
    else:
        print(f"\n➡️ [Stage 2] 智能配图与样式注入完成！文件已保存至:\n   {stage2_path}")

    # ==================== STAGE 3 ====================
    # Read from stage2_path to preserve manual edits
    run_stage_3(stage2_path, stage3_path, project_config, source_dir=base_dir)
    if not args.yes:
        while True:
            ans = input(
                f"\n➡️ [Stage 3] 微信 HTML 编译完成！文件已保存至:\n   {stage3_path}\n"
                "   (您可以在浏览器或编辑器中查看和编辑生成的 HTML 效果)\n"
                "   请输入操作: [y] 完成排版并显示发布命令 | [r] 重新加载 Stage 2 文件重跑 Stage 3 | [q] 退出: "
            ).strip().lower()
            if ans in ('', 'y', 'yes'):
                break
            elif ans == 'r':
                run_stage_3(stage2_path, stage3_path, project_config, source_dir=base_dir)
            elif ans == 'q':
                print("👋 已退出流程")
                sys.exit(0)
    else:
        print(f"\n➡️ [Stage 3] 微信 HTML 编译完成！文件已保存至:\n   {stage3_path}")

    # ==================== STAGE 4 (已迁移) ====================
    # 微信发布能力已独立为 wechat-publisher-skill，请单独调用：
    #
    #   python3 /home/guagua/workspace/.agents/skills/wechat-publisher-skill/scripts/publish.py \
    #     -c <_wechat.html 路径>
    print(f"\n✅ [Stage 3] 完成！HTML 已保存至：\n   {stage3_path}")
    print("\n💡 如需发布到微信公众号草稿箱，请使用 wechat-publisher-skill：")
    print(f"   python3 /home/guagua/workspace/.agents/skills/wechat-publisher-skill/scripts/publish.py -c {stage3_path}")



if __name__ == "__main__":
    main()
