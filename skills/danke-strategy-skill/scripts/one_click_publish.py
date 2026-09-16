#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
one_click_publish.py - 弹壳特攻队攻略全渠道一键极速发布流水线

支持一条指令端到端完成：
1. [Stage 1~3] Markdown 排版编译 ➔ 生成 _wechat.html
2. [WeChat] 微信公众号草稿箱极速发布 (支持全局图床缓存)
3. [Cards 3:4] 原生网页自适应 3:4 高清切图 (自动 DOM 级脱敏)
4. [Douyin] 抖音创作者中心实体窗口自动上传与保活

用法:
    python3 one_click_publish.py <攻略.md 路径> [--new] [--skip-douyin] [--skip-wechat]
"""

import os
import sys
import argparse
import subprocess
import time
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent


def run_step(step_name, cmd, cwd=None):
    print(f"\n==================================================")
    print(f"🚀 [{step_name}] 正在执行: {' '.join(cmd)}")
    print(f"==================================================")
    t0 = time.time()
    res = subprocess.run(cmd, cwd=cwd, text=True)
    cost = time.time() - t0
    if res.returncode != 0:
        print(f"❌ [{step_name}] 执行失败 (耗时 {cost:.2f}s)！")
        return False
    print(f"✅ [{step_name}] 执行成功 (耗时 {cost:.2f}s)")
    return True


def main():
    parser = argparse.ArgumentParser(description="弹壳特攻队攻略全渠道一键发布流水线")
    parser.add_argument("markdown", help="Markdown 攻略文件路径")
    parser.add_argument("--new", action="store_true", help="强制在微信公众号创建新草稿 (而非覆盖已有)")
    parser.add_argument("--skip-wechat", action="store_true", help="跳过微信发布")
    parser.add_argument("--skip-douyin", action="store_true", help="跳过抖音发布")
    parser.add_argument("--headless", action="store_true", help="抖音使用无头浏览器 (默认弹出实体窗口)")
    parser.add_argument("--no-keep-open", action="store_true", help="抖音上传完成后自动关闭浏览器 (默认保持开启)")

    args = parser.parse_args()

    md_path = os.path.abspath(args.markdown)
    if not os.path.exists(md_path):
        print(f"❌ 找不到 Markdown 文件: {md_path}")
        sys.exit(1)

    article_dir = os.path.dirname(md_path)
    base_name = os.path.splitext(os.path.basename(md_path))[0]
    wechat_html = os.path.join(article_dir, f"{base_name}_stage3_wechat.html")
    wechat_json = os.path.join(article_dir, f"{base_name}_stage3_wechat.json")
    cards_dir = os.path.join(article_dir, "原生网页直切图_3x4")

    total_t0 = time.time()

    # 1. 编译 Markdown ➔ 微信富文本 HTML
    interactive_flow = str(SKILLS_DIR / "danke-strategy-skill" / "scripts" / "interactive_flow.py")
    pack_dir = str(SKILLS_DIR / "danke-strategy-skill" / "packs" / "danke")
    compile_cmd = [sys.executable, interactive_flow, "-y", md_path, "--pack", pack_dir]
    if not run_step("Stage 1~3 微信 HTML 编译", compile_cmd, cwd=str(SKILLS_DIR / "danke-strategy-skill")):
        sys.exit(1)

    # 2. 微信公众号草稿箱发布
    if not args.skip_wechat:
        wechat_pub_script = str(SKILLS_DIR / "wechat-publisher-skill" / "scripts" / "publish.py")
        wechat_cmd = [sys.executable, wechat_pub_script, "-c", wechat_html]
        if args.new:
            wechat_cmd.append("--new")
        if not run_step("微信草稿箱发布", wechat_cmd, cwd=str(SKILLS_DIR / "wechat-publisher-skill")):
            print("⚠ 微信发布出现异常，继续后续流程...")

    # 3. 原生网页 3:4 独立脱敏切图
    if not args.skip_douyin:
        slice_script = str(SKILLS_DIR / "article-to-img-skill" / "scripts" / "export_cards.py")
        slice_cmd = [sys.executable, slice_script, wechat_html, "-o", cards_dir]
        if not run_step("3:4 原生网页高清切图 (自动脱敏)", slice_cmd, cwd=str(SKILLS_DIR / "article-to-img-skill")):
            sys.exit(1)

        # 4. 抖音创作者中心上传
        douyin_script = str(SKILLS_DIR / "douyin-publisher-skill" / "scripts" / "publish.py")
        douyin_cmd = [sys.executable, douyin_script, "-i", cards_dir, "-m", wechat_json]
        if args.headless:
            douyin_cmd.append("--headless")
        if args.no_keep_open:
            douyin_cmd.append("--no-keep-open")

        print("\n==================================================")
        print("🚀 [抖音发布] 正在拉起实体可视化窗口进行上传与保活...")
        print("==================================================")
        # 抖音发布是保活进程，直接接管
        subprocess.run(douyin_cmd, cwd=str(SKILLS_DIR / "douyin-publisher-skill"))

    total_cost = time.time() - total_t0
    print(f"\n🎉 [全链路完成] 一键发布流水线总耗时: {total_cost:.2f} 秒！")


if __name__ == "__main__":
    main()
