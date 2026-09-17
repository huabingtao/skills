#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_reminder.py - 每日玩法待办与倒计时日历文章自动生成工具
专为《弹壳特攻队》自媒体打造，100%严格依据后台/数据中心返回的实际规则与备注生成极简清单。
输出路径规范: project/danke-creator/my-articles-md/提醒/YY.M.D/YY.M.D.md
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path


def find_workspace_root() -> Path:
    """自动向上查找工作区根目录"""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "content" / "danke-creator").is_dir() or (parent / "project" / "danke-creator").is_dir():
            return parent
    if Path("/Users/hbt/my-project").is_dir():
        return Path("/Users/hbt/my-project")
    return Path("/home/guagua/workspace")


def to_short_date_str(date_obj: datetime.date) -> str:
    """将日期转换为短格式字符串，例如 2026-09-07 -> 26.9.7"""
    yy = date_obj.year % 100
    m = date_obj.month
    d = date_obj.day
    return f"{yy}.{m}.{d}"


def clean_status_text(status_text: str, name: str) -> str:
    """去除状态文案中冗余的【玩法名称】，避免前缀已有名称时重复显得呆板"""
    if not status_text:
        return ""
    cleaned = status_text.replace(f"【{name}】", "").replace(f"[{name}]", "").replace(f"本轮{name}", "本轮")
    # 清理多余空格与遗留冒号
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = cleaned.lstrip("：: ")
    return cleaned


def fetch_daily_digest(target_date: str, api_base: str = "http://localhost:3000") -> dict:
    """只接受 danke-core 规则引擎的结果；服务失败时停止生成。"""
    url = f"{api_base.rstrip('/')}/reminders/daily-digest?date={target_date}"
    req = urllib.request.Request(url, headers={"User-Agent": "danke-calendar-skill/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        return validate_digest(data, target_date)
    except Exception as exc:
        raise RuntimeError("规则服务不可用或返回无效数据；请启动 danke-core，或用 --digest-file 传入 MCP 查询结果。") from exc


def validate_digest(data: dict, target_date: str) -> dict:
    if not isinstance(data, dict) or data.get("date") != target_date:
        raise ValueError("规则结果日期必须与 --date 一致")
    if not isinstance(data.get("items"), list):
        raise ValueError("规则结果必须包含 items 数组")
    for item in data["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not isinstance(item.get("statusText"), str):
            raise ValueError("规则项目必须包含名称和状态文案")
    return data


RECOMMENDED_ARTICLES_POOL = [
    {
        "title": "【攻略】高频问答FAQ第一弹：特工选择、狼马对比与配件过载全指南",
        "url": "https://mp.weixin.qq.com/s/QMfvpK7okI0yFyg2kRYkXQ",
    },
    {
        "title": "【工具】手把手教你使用弹壳特攻队伤害计算器",
        "url": "https://mp.weixin.qq.com/s/vN79nJW3Cyn9sy0UDGvKaw",
    },
    {
        "title": "【攻略】s宠物从入门到入土！",
        "url": "https://mp.weixin.qq.com/s/pJitLL_Vu7wI9ctzSM-EMg",
    },
]


def highlight_urgent_status(status_text: str, days_remaining: int, is_redeem_day: bool = False) -> str:
    """把倒计时 3 天内的天数/兑换日标记为醒目的红色"""
    if is_redeem_day:
        return f'<font color="#dc2626">{status_text}</font>'
    
    if days_remaining <= 3:
        # Match "还剩 X 天" or "剩 X 天" and insert clean spacing
        highlighted = re.sub(
            r'(还剩\s*\d+\s*天|剩\s*\d+\s*天)',
            r' <font color="#dc2626">\1</font>',
            status_text
        )
        highlighted = re.sub(r'\s+', ' ', highlighted).strip()
        return highlighted
    
    return status_text


def build_reminder_article(data: dict) -> str:
    """严格基于后台数据组装极简日历清单 Markdown 文章，往期推荐使用 Frontmatter recommendations 元数据"""
    import random
    date_str = data.get("date", datetime.date.today().strftime("%Y-%m-%d"))
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    yy = dt.year % 100
    month = dt.month
    day = dt.day

    items = data.get("items") or data.get("reminders") or []
    # 按照结束时间/剩余天数从小到大排序
    items = sorted(items, key=lambda x: (x.get("daysRemaining", 9999), x.get("name", "")))
    count = len(items)

    # 随机挑选 3 篇推荐文章（使用目标日期作为随机种子以保证同一天生成的幂等性）
    random.seed(int(dt.strftime("%Y%m%d")))
    selected_articles = random.sample(RECOMMENDED_ARTICLES_POOL, min(3, len(RECOMMENDED_ARTICLES_POOL)))

    lines = []
    lines.append("---")
    lines.append(f'title: "【弹壳日历】{yy}年{month}月{day}日每日事项清单"')
    lines.append(f'social_title: "{yy}年{month}月{day}日弹壳每日事项清单"')
    lines.append(f'summary: "{yy}年{month}月{day}日《弹壳特攻队》全量{count}大玩法待办与倒计时清单汇总。"')
    lines.append("tags:")
    lines.append("  - 弹壳特攻队")
    lines.append("  - 游戏攻略")
    lines.append("  - 弹壳日历")
    lines.append("  - 每日待办")
    lines.append('cover: "./dist/cover.png"')
    lines.append('cover_vertical: "./dist/cover_vertical.png"')
    lines.append('author: "弹壳呱呱"')
    lines.append(f"date: {date_str}")
    lines.append(f"lastmod: {date_str}")
    lines.append('qrcode_image: "img://弹壳呱呱微信公众号二维码"')
    lines.append("recommendations:")
    for article in selected_articles:
        lines.append(f'  - title: "{article["title"]}"')
        lines.append(f'    url: "{article.get("url", "")}"')
    lines.append("---")
    lines.append("")
    lines.append("![article-top](img://article-top){type=banner}")
    lines.append("")
    lines.append(f"# {yy} 年 {month} 月 {day} 日弹壳每日事项清单")
    lines.append("")
    lines.append("各位特工大家早上好，我是呱呱！")
    lines.append("")
    lines.append(f"今天（{yy} 年 {month} 月 {day} 日）游戏内各玩法的最新待办与事项提醒如下：")
    lines.append("")

    for item in items:
        name = item.get("name", "")
        raw_status_text = item.get("statusText", "")
        days_remaining = item.get("daysRemaining", 9999)
        is_redeem_day = item.get("isRedeemDay", False)
        
        status_text = clean_status_text(raw_status_text, name)
        status_text = highlight_urgent_status(status_text, days_remaining, is_redeem_day)
        note = item.get("digestNote")
        
        # 单行展示：自然无序列表 + 玩法名称 + 状态文案（备注）
        if note and note.strip():
            lines.append(f"- {name}：{status_text}（{note.strip()}）")
        else:
            lines.append(f"- {name}：{status_text}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("攻略创作不易，如果帮到了你，请大家多多**转发、点赞和关注**！你们的支持是呱呱持续输出干货的最大动力！")
    lines.append("")
    lines.append("【免责声明】本攻略纯属个人**经验分享**，**仅供参考**，不构成任何消费建议。游戏版本更新较快，具体数值以游戏内实际表现为准。本攻略所引用的美术图片及游戏内截图版权均归 Habby 公司所有。")
    lines.append("")

    return "\n".join(lines)


def auto_tag_file(file_path: Path):
    """自动调用 auto_tag.py 进行专有名词宏标签标注"""
    ws = find_workspace_root()
    candidates = [
        ws / "skills" / "danke-strategy-skill" / "scripts" / "auto_tag.py",
        ws / "skill" / "danke-strategy-skill" / "scripts" / "auto_tag.py",
        Path.home() / "skills" / "skills" / "danke-strategy-skill" / "scripts" / "auto_tag.py",
    ]
    auto_tag_script = next((c for c in candidates if c.exists()), None)
    if auto_tag_script:
        try:
            subprocess.run([sys.executable, str(auto_tag_script), str(file_path)], check=True)
            print("✔ 专有名词宏自动标注完成")
        except Exception as e:
            print(f"⚠️ 自动宏标注跳过: {e}")


def generate_covers(out_dir: Path, target_date_obj: datetime.date = None):
    """使用全特工专属底图与带当天日期的文案生成封面（横屏与竖屏双模）"""
    out_dir.mkdir(parents=True, exist_ok=True)
    ws = find_workspace_root()
    make_cover_script = None
    for cand in [
        ws / "skills" / "wechat-cover-generator" / "scripts" / "make_cover.py",
        ws / ".agents" / "skills" / "wechat-cover-generator" / "scripts" / "make_cover.py",
        Path.home() / "skills" / "skills" / "wechat-cover-generator" / "scripts" / "make_cover.py",
    ]:
        if cand.exists():
            make_cover_script = cand
            break

    bg_img = Path(__file__).resolve().parent.parent / "assets" / "reminder_cover_bg.jpg"
    if not bg_img.exists():
        for cand_bg in [
            ws / "skills" / "danke-calendar-skill" / "assets" / "reminder_cover_bg.jpg",
            ws / ".agents" / "skills" / "danke-calendar-skill" / "assets" / "reminder_cover_bg.jpg",
            Path.home() / "skills" / "skills" / "danke-calendar-skill" / "assets" / "reminder_cover_bg.jpg",
        ]:
            if cand_bg.exists():
                bg_img = cand_bg
                break

    if target_date_obj is None:
        target_date_obj = datetime.date.today()

    cover_text = f"弹壳特攻队\n提醒日历{target_date_obj.year}.{target_date_obj.month}.{target_date_obj.day}"

    if make_cover_script and make_cover_script.exists() and bg_img.exists():
        try:
            # 1. 横屏封面 900x384
            cmd_h = [
                sys.executable,
                str(make_cover_script),
                "-i", str(bg_img),
                "-t", cover_text,
                "-o", str(out_dir / "cover.png"),
                "--style", "horizontal",
            ]
            subprocess.run(cmd_h, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # 2. 竖屏封面 640x853
            cmd_v = [
                sys.executable,
                str(make_cover_script),
                "-i", str(bg_img),
                "-t", cover_text,
                "-o", str(out_dir / "cover_vertical.png"),
                "--style", "vertical",
            ]
            subprocess.run(cmd_v, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"🖼️ 专属双模封面已自动生成: {out_dir / 'cover.png'}, {out_dir / 'cover_vertical.png'} (文字: {cover_text})")
        except Exception as e:
            raise RuntimeError("封面生成失败") from e
    else:
        raise FileNotFoundError(f"缺少封面脚本 ({make_cover_script}) 或背景素材 ({bg_img})")


def main():
    parser = argparse.ArgumentParser(description="自动生成《弹壳特攻队》每日玩法待办与倒计时日历文章")
    parser.add_argument("--date", help="指定生成日期 (YYYY-MM-DD)，默认为当天", default=datetime.date.today().strftime("%Y-%m-%d"))
    parser.add_argument("--api-base", help="danke-core API 地址", default=os.environ.get("DANKE_API_BASE_URL", "http://localhost:3000"))
    parser.add_argument("--output-dir", help="自定义输出目录")

    parser.add_argument("--digest-file", type=Path, help="MCP get_reminder_rules 返回的 JSON 文件")

    args = parser.parse_args()
    target_date_str = args.date
    target_date_obj = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()

    print(f"📡 正在拉取 {target_date_str} 提醒规则数据...")
    if args.digest_file:
        digest_data = validate_digest(json.loads(args.digest_file.read_text(encoding="utf-8-sig")), target_date_str)
    else:
        digest_data = fetch_daily_digest(target_date_str, api_base=args.api_base)

    items = digest_data.get("items") or digest_data.get("reminders") or []
    total_rules = len(items)
    print(f"✅ 成功获取 {total_rules} 项生效规则（100% 严格使用后台配置文案）")

    article_content = build_reminder_article(digest_data)

    # 确定短格式输出目录：project/danke-creator/my-articles-md/提醒/YY.M.D/YY.M.D.md
    ws = find_workspace_root()
    short_date = to_short_date_str(target_date_obj)

    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        creator_root = ws / "content" / "danke-creator" if (ws / "content" / "danke-creator").is_dir() else ws / "project" / "danke-creator"
        out_dir = creator_root / "my-articles-md" / "提醒" / short_date

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{short_date}.md"

    out_file.write_text(article_content, encoding="utf-8")
    print(f"💾 文章已写入: {out_file}")

    # 自动生成专属封面
    generate_covers(out_dir / "dist", target_date_obj)

    # 自动宏标注
    auto_tag_file(out_file)

    print(f"🎉 【{short_date} ({target_date_str}) 弹壳日历事项清单生成完毕】！")


if __name__ == "__main__":
    main()
