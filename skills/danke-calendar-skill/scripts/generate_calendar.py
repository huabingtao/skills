#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
danke-calendar-skill: Automates daily countdown calendar for 11 activities in 《弹壳特攻队》.
"""

import os
import sys
import json
import argparse
import datetime
import calendar
import subprocess
from PIL import Image, ImageDraw, ImageFont

# Activity notes and descriptions
ACTIVITY_CONFIG = {
    '神秘商人': {
        'cycle': 3,
        'anchor_rem': 1,
        'note': '找好友助力砍完价再买，别原价当冤大头'
    },
    '公会探索': {
        'type': 'weekly_day',
        'target_weekday': 2, # Ends Wednesday 23:59 (resets Thursday 00:00)
        'note': '做完探索任务千万记得打一下BOSS，不然没奖励'
    },
    '日常挑战': {
        'cycle': 3,
        'anchor_rem': 3,
        'note': '穿红甲直接挂机就行，只换芯片和核心'
    },
    '试炼之路': {
        'cycle': 5,
        'anchor_rem': 4,
        'note': '懒得爬塔的，记得卡个排名，18000后住的是单间'
    },
    '周常': {
        'type': 'weekly_sun', # Ends Sunday 23:59 (resets Monday 00:00)
        'note': ''
    },
    '联机挑战': {
        'type': 'weekly_sun',
        'note': '一轮要打半小时左右，建议200万攻击以上打'
    },
    '饼干和联机复活币兑换': {
        'type': 'weekly_sun',
        'note': ''
    },
    '区域行动': {
        'cycle': 14,
        'anchor_rem': 8,
        'note': '奖励也还可以，打不过的可以看看攻略'
    },
    '回响之战': {
        'cycle': 14,
        'anchor_rem': 8,
        'note': '实力达不到王者组记得也要在传说组卡个排名'
    },
    '公会商店刷新': {
        'type': 'month_end',
        'note': '公会币不足的优先把重要的核心和传奇收藏品换了'
    },
    '逃离行动': {
        'type': 'escape_season',
        'anchor_rem': 24,
        'note': '奖励很好但非常费时间，没空打的后台联系找我代肝'
    }
}

ANCHOR_DATE = datetime.date(2026, 9, 16)


def calculate_countdowns(target_date):
    """Calculates remaining days for all 11 activities based on exact mathematical rules."""
    diff = (target_date - ANCHOR_DATE).days
    results = {}

    for act_name, cfg in ACTIVITY_CONFIG.items():
        ctype = cfg.get('type')
        if ctype == 'weekly_sun':
            # Resets Monday 00:00 (ends Sunday 23:59)
            rem = 7 - target_date.weekday()
        elif ctype == 'weekly_day':
            # Resets Thursday 00:00 (ends Wednesday 23:59)
            rem = (cfg['target_weekday'] - target_date.weekday()) % 7 + 1
        elif ctype == 'month_end':
            # Ends on last day of current calendar month
            last_day = calendar.monthrange(target_date.year, target_date.month)[1]
            rem = max(1, last_day - target_date.day)
        elif ctype == 'escape_season':
            # 30-day season cycle
            rem = (cfg['anchor_rem'] - 1 - diff) % 30 + 1
        else:
            # Fixed cycle modulo
            cycle = cfg['cycle']
            anchor_rem = cfg['anchor_rem']
            rem = (anchor_rem - 1 - diff) % cycle + 1

        results[act_name] = {
            'remaining': rem,
            'note': cfg.get('note', '')
        }

    # Sort items by remaining days ascending
    sorted_items = sorted(results.items(), key=lambda x: x[1]['remaining'])
    return sorted_items


def build_markdown_content(target_date, items):
    """Builds standardized calendar Markdown document."""
    yy = str(target_date.year)[-2:]
    m = target_date.month
    d = target_date.day
    date_str = target_date.strftime('%Y-%m-%d')
    folder_name = f"{yy}.{m}.{d}"

    frontmatter = f"""---
title: "【弹壳日历】{yy}年{m}月{d}日每日事项清单"
social_title: "{yy}年{m}月{d}日弹壳每日事项清单"
summary: "{yy}年{m}月{d}日《弹壳特攻队》全量11大玩法待办与倒计时清单汇总。"
tags:
  - 弹壳特攻队
  - 游戏攻略
  - 弹壳日历
  - 每日待办
cover: "./dist/cover.png"
cover_vertical: "./dist/cover_vertical.png"
author: "弹壳呱呱"
date: {date_str}
lastmod: {date_str}
qrcode_image: "img://弹壳呱呱微信公众号二维码"
recommendations:
  - title: "【攻略】高频问答FAQ第一弹：特工选择、狼马对比与配件过载全指南"
    url: "https://mp.weixin.qq.com/s/QMfvpK7okI0yFyg2kRYkXQ"
  - title: "【工具】手把手教你使用弹壳特攻队伤害计算器"
    url: "https://mp.weixin.qq.com/s/vN79nJW3Cyn9sy0UDGvKaw"
  - title: "【攻略】s宠物从入门到入土！"
    url: "https://mp.weixin.qq.com/s/pJitLL_Vu7wI9ctzSM-EMg"
---

![article-top](img://article-top){{type=banner}}

# {yy} 年 {m} 月 {d} 日弹壳每日事项清单

各位特工大家早上好，我是呱呱！

今天（{yy} 年 {m} 月 {d} 日）游戏内各玩法的最新待办与事项提醒如下：

"""

    body_lines = []
    for act_name, info in items:
        rem = info['remaining']
        note = f"（{info['note']}）" if info['note'] else ""
        if rem <= 3:
            rem_str = f'<font color="#dc2626">还剩 {rem} 天</font>'
        else:
            rem_str = f'还剩 {rem} 天'

        body_lines.append(f"- {act_name}：离本轮结束 {rem_str}{note}")

    footer = """

---

攻略创作不易，如果帮到了你，请大家多多**转发、点赞和关注**！你们的支持是呱呱持续输出干货的最大动力！

【免责声明】本攻略纯属个人**经验分享**，**仅供参考**，不构成任何消费建议。游戏版本更新较快，具体数值以游戏内实际表现为准。本攻略所引用的美术图片及游戏内截图版权均归 Habby 公司所有。
"""

    return frontmatter + "\n".join(body_lines) + footer


def generate_covers(target_date, dist_dir, base_remind_dir):
    """Generates horizontal and vertical covers for the calendar."""
    os.makedirs(dist_dir, exist_ok=True)
    h_out = os.path.join(dist_dir, "cover.png")
    v_out = os.path.join(dist_dir, "cover_vertical.png")

    # If covers already exist, preserve them
    if os.path.exists(h_out) and os.path.exists(v_out):
        print(f"✔ 封面已存在于: {dist_dir}")
        return h_out, v_out

    # Find closest template cover in 提醒/ directory
    template_dirs = []
    if os.path.isdir(base_remind_dir):
        for entry in os.listdir(base_remind_dir):
            edir = os.path.join(base_remind_dir, entry, "dist")
            if os.path.isfile(os.path.join(edir, "cover.png")) and os.path.isfile(os.path.join(edir, "cover_vertical.png")):
                template_dirs.append(edir)

    if template_dirs:
        # Use latest template as base
        template_dirs.sort()
        best_tpl = template_dirs[-1]
        try:
            im_h = Image.open(os.path.join(best_tpl, "cover.png"))
            im_h.save(h_out)
            im_v = Image.open(os.path.join(best_tpl, "cover_vertical.png"))
            im_v.save(v_out)
            print(f"✔ 成功基于最新模版 [{os.path.basename(os.path.dirname(best_tpl))}] 生成封面: {h_out}")
            return h_out, v_out
        except Exception as e:
            print(f"⚠ 模版复制失败: {e}")

    # Fallback to wechat-cover-generator if available
    return h_out, v_out


def main():
    parser = argparse.ArgumentParser(description="danke-calendar-skill: 弹壳日历自动化生成工具")
    parser.add_argument("--date", type=str, default=None, help="目标日期 (YYYY-MM-DD), 默认为今天")
    parser.add_argument("--workspace", type=str, default="/Users/hbt/my-project/content/danke-creator", help="danke-creator 工作区根目录")
    parser.add_argument("--compile", action="store_true", default=True, help="是否自动编译为微信 HTML")
    parser.add_argument("--no-compile", dest="compile", action="store_false", help="不自动编译 HTML")
    parser.add_argument("--cards", action="store_true", default=True, help="是否自动切图 3:4 卡片")
    parser.add_argument("--publish", action="store_true", default=False, help="是否直接推送到微信草稿箱")
    args = parser.parse_args()

    if args.date:
        try:
            target_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"❌ 日期格式错误: {args.date}，应为 YYYY-MM-DD")
            sys.exit(1)
    else:
        target_date = datetime.date.today()

    yy = str(target_date.year)[-2:]
    m = target_date.month
    d = target_date.day
    folder_name = f"{yy}.{m}.{d}"

    base_remind_dir = os.path.join(args.workspace, "my-articles-md", "提醒")
    article_dir = os.path.join(base_remind_dir, folder_name)
    dist_dir = os.path.join(article_dir, "dist")
    os.makedirs(dist_dir, exist_ok=True)

    md_filename = f"{folder_name}.md"
    md_path = os.path.join(article_dir, md_filename)

    print(f"\n📅 [弹壳日历生成器] 目标日期: {target_date.strftime('%Y-%m-%d')} ({folder_name})")

    # 1. Calculate countdowns
    countdowns = calculate_countdowns(target_date)
    print("✔ 11大玩法倒计时计算完毕:")
    for act_name, info in countdowns:
        print(f"   • {act_name:12s}: 剩余 {info['remaining']} 天")

    # 2. Generate Markdown
    md_content = build_markdown_content(target_date, countdowns)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n✔ Markdown 文章已生成: {md_path}")

    # 3. Generate Covers
    generate_covers(target_date, dist_dir, base_remind_dir)

    # 4. Compile HTML
    wechat_html_path = os.path.join(dist_dir, f"{folder_name}_stage3_wechat.html")
    if args.compile:
        compiler_script = "/Users/hbt/my-project/skills/danke-strategy-skill/scripts/interactive_flow.py"
        if os.path.isfile(compiler_script):
            print(f"\n🚀 正在调用 danke-strategy-skill 编译文章...")
            cmd = ["python3", compiler_script, md_path, "-y", "--pack", "/Users/hbt/my-project/skills/danke-strategy-skill/packs/danke"]
            subprocess.run(cmd, check=True)
            print(f"✔ 微信 HTML 编译完成: {wechat_html_path}")
        else:
            print(f"⚠ 未找到编译器脚本: {compiler_script}")

    # 5. Export 3:4 Cards
    if args.cards and os.path.isfile(wechat_html_path):
        cards_script = "/Users/hbt/my-project/skills/article-to-img-skill/scripts/export_cards.py"
        if os.path.isfile(cards_script):
            print(f"\n📸 正在切图 3:4 高清卡片...")
            out_cards_dir = os.path.join(dist_dir, "原生网页直切图_3x4")
            cmd = ["python3", cards_script, wechat_html_path, "-o", out_cards_dir]
            subprocess.run(cmd, check=False)
            print(f"✔ 3:4 卡片切图完成: {out_cards_dir}")
        else:
            print(f"⚠ 未找到切图脚本: {cards_script}")

    # 6. Publish to WeChat Draft Box
    if args.publish and os.path.isfile(wechat_html_path):
        publish_script = "/Users/hbt/my-project/skills/wechat-publisher-skill/scripts/publish.py"
        if os.path.isfile(publish_script):
            print(f"\n📤 正在推送至微信草稿箱...")
            cmd = ["python3", publish_script, "-c", wechat_html_path]
            subprocess.run(cmd, check=True)
            print(f"🎉 微信公众号草稿箱发布成功！")
        else:
            print(f"⚠ 未找到发布脚本: {publish_script}")

    print("\n✨ 弹壳每日日历全流程执行完毕！")


if __name__ == "__main__":
    main()
