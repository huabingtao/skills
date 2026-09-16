#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用微信 Markdown 编译器 CLI

用法:
  python scripts/compile.py --pack packs/danke taozhuang1.md
  python scripts/compile.py --pack packs/danke taozhuang1.md --theme tech
  python scripts/compile.py taozhuang1.md  # 不使用内容包（纯排版）
"""
import argparse
import os
import sys
import json

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from engine.compiler import convert_to_wechat_html, convert_to_optimized_markdown


def load_project_config(pack_dir, theme_override=None):
    """
    Loads a content pack's project.json and resolves all paths to absolute.
    """
    project_json_path = os.path.join(pack_dir, "project.json")
    if not os.path.exists(project_json_path):
        print("❌ Error: project.json not found in pack directory: " + str(pack_dir))
        sys.exit(1)

    with open(project_json_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    pack_abs = os.path.abspath(pack_dir)

    # Resolve relative paths to absolute
    project_config = {}

    # Image mapping：COS 模式下优先使用 image_mapping_cos.json
    cos_mode = config.get("cos_mode", False)
    if cos_mode and config.get("image_mapping_cos"):
        cos_mapping_path = os.path.join(pack_abs, config["image_mapping_cos"])
        if os.path.exists(cos_mapping_path):
            project_config["image_mapping_path"] = cos_mapping_path
            print("☁️  COS 模式：使用 image_mapping_cos.json")
        else:
            print("⚠ COS mapping 文件不存在，回退到本地 mapping")
            cos_mode = False
    if not cos_mode and config.get("image_mapping"):
        project_config["image_mapping_path"] = os.path.join(pack_abs, config["image_mapping"])

    # Assets directory
    if config.get("assets_dir"):
        project_config["assets_dir"] = os.path.join(pack_abs, config["assets_dir"])

    # Highlight rules
    if config.get("highlight_rules"):
        rules_path = os.path.join(pack_abs, config["highlight_rules"])
        if os.path.exists(rules_path):
            project_config["highlight_rules_path"] = rules_path

    # Links map
    links_map_path = os.path.join(pack_abs, "config", "links_map.json")
    if os.path.exists(links_map_path):
        try:
            with open(links_map_path, "r", encoding="utf-8") as f:
                project_config["links_map"] = json.load(f)
        except Exception as e:
            print(f"⚠ Warning: Failed to load links_map.json: {e}")

    # Theme: override > pack config > default (minimal as default)
    theme_name = theme_override or config.get("theme", "minimal")
    themes_dir = os.path.join(PROJECT_ROOT, "themes")
    theme_path = os.path.join(themes_dir, theme_name + ".css")
    if os.path.exists(theme_path):
        project_config["theme_path"] = theme_path
    else:
        print("⚠ Warning: Theme '" + str(theme_name) + "' not found at " + str(theme_path) + ", using default")
        default_theme = os.path.join(themes_dir, "default.css")
        if os.path.exists(default_theme):
            project_config["theme_path"] = default_theme

    # Placeholder directory
    if project_config.get("assets_dir"):
        project_config["placeholder_dir"] = os.path.join(project_config["assets_dir"], "img")

    # Container font
    if config.get("container_font"):
        project_config["container_font"] = config["container_font"]

    return project_config


def build_default_config(theme_override=None):
    """
    Builds a minimal config when no content pack is specified (pure layout mode).
    """
    project_config = {}

    theme_name = theme_override or "minimal"
    themes_dir = os.path.join(PROJECT_ROOT, "themes")
    theme_path = os.path.join(themes_dir, theme_name + ".css")
    if os.path.exists(theme_path):
        project_config["theme_path"] = theme_path

    return project_config


def main():
    parser = argparse.ArgumentParser(
        description="通用微信 Markdown 编译器 (WeChat MD Compiler)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/compile.py --pack packs/danke article.md
  python scripts/compile.py --pack packs/danke article.md -o output.html
  python scripts/compile.py article.md --theme tech
        """
    )
    parser.add_argument("input_file", help="输入 Markdown 文件路径")
    parser.add_argument("-o", "--output", help="输出 HTML 文件路径（默认: <input>_wechat.html）")
    parser.add_argument("--pack", help="内容包目录路径（如 packs/danke）")
    parser.add_argument("--theme", help="CSS 主题名称（覆盖内容包配置）")

    args = parser.parse_args()

    input_path = args.input_file
    output_path = args.output or os.path.splitext(input_path)[0] + "_wechat.html"
    meta_path = os.path.splitext(output_path)[0] + ".json"

    if not os.path.exists(input_path):
        print("❌ Error: File not found: " + str(input_path))
        sys.exit(1)

    # Build project config
    if args.pack:
        project_config = load_project_config(args.pack, args.theme)
        print("📦 Using content pack: " + str(args.pack))
    else:
        default_pack = os.path.join(PROJECT_ROOT, "packs", "danke")
        if os.path.exists(default_pack):
            project_config = load_project_config(default_pack, args.theme)
            print("📦 Auto-detected default content pack: packs/danke")
        else:
            project_config = build_default_config(args.theme)
            print("ℹ No content pack specified, using pure layout mode")


    try:
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()

        input_dir = os.path.dirname(os.path.abspath(input_path))
        output_dir = os.path.dirname(os.path.abspath(output_path))
        wechat_html, metadata = convert_to_wechat_html(content, project_config, input_dir=input_dir, output_dir=output_dir)

        # Save HTML
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(wechat_html)

        # Save Optimized Markdown (Commented out)
        # optimized_md = convert_to_optimized_markdown(content, project_config, input_dir=input_dir)
        # output_md_path = os.path.splitext(output_path)[0] + ".md"
        # with open(output_md_path, "w", encoding="utf-8") as f:
        #     f.write(optimized_md)

        # Save DOCX using pandoc if available (Commented out)
        # output_docx_path = os.path.splitext(output_path)[0] + ".docx"
        # resource_paths = [input_dir]
        # if project_config.get("assets_dir"):
        #     pack_dir = os.path.dirname(project_config["assets_dir"])
        #     resource_paths.append(pack_dir)

        # import subprocess
        # pandoc_cmd = [
        #     "pandoc",
        #     "-s",
        #     "--resource-path=" + ":".join(resource_paths),
        #     "-f", "markdown",
        #     "-t", "docx",
        #     "-o", output_docx_path,
        #     output_md_path
        # ]
        # docx_ok = False
        # try:
        #     subprocess.run(pandoc_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        #     docx_ok = True
        # except Exception as e:
        #     print("⚠ Warning: Failed to generate DOCX using pandoc: " + str(e))

        # Save Metadata
        if metadata:
            import datetime

            def json_serial(obj):
                if isinstance(obj, (datetime.date, datetime.datetime)):
                    return obj.isoformat()
                raise TypeError("Type %s not serializable" % type(obj))

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2, default=json_serial)

        print("✅ Successfully converted '" + str(input_path) + "' → '" + str(output_path) + "'")
        # print("✅ Optimized Markdown saved to '" + str(output_md_path) + "'")
        # if docx_ok:
        #     print("✅ Optimized DOCX saved to '" + str(output_docx_path) + "'")
        if metadata:
            print("✅ Metadata saved to '" + str(meta_path) + "'")

    except Exception as e:
        print("❌ Error during conversion: " + str(e))
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
