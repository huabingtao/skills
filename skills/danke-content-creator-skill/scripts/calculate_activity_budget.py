#!/usr/bin/env python3
"""Calculate activity budgets from confirmed inputs, without rounded ratios."""

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} 必须为不小于 {minimum} 的整数")
    return value


def calculate_budget(data):
    initial = integer(data["initial_items"], "initial_items")
    tasks = data["tasks"]
    if not isinstance(tasks, dict):
        raise ValueError("tasks 必须为已确认的非开箱任务及固定来源数量字典")
    task_items = sum(integer(n, f"tasks.{name}") for name, n in tasks.items())
    base = initial + task_items
    sample = data["sample"]
    spent = integer(sample["items_consumed"], "sample.items_consumed", 1)
    gained = integer(sample["progress_gained"], "sample.progress_gained", 1)
    ratio = Fraction(gained, spent)
    price = integer(data["item_price_diamonds"], "item_price_diamonds", 1)
    box_rewards = {0: 0}
    for key, value in data["box_rewards"].items():
        boxes = int(key)
        if str(boxes) != str(key) or boxes <= 0:
            raise ValueError("box_rewards 键必须为正整数开箱节点；0 箱自动计算")
        box_rewards[boxes] = integer(value, f"box_rewards.{key}")
    if not all(a <= b for a, b in zip(
            [box_rewards[k] for k in sorted(box_rewards)],
            [box_rewards[k] for k in sorted(box_rewards)][1:])):
        raise ValueError("开箱奖励为累计值，不能随开箱数量增加而减少")

    plans, warnings = [], []
    for plan in data["plans"]:
        progress = integer(plan["progress"], "plans.progress", 1)
        if any(p["target_progress"] == progress for p in plans):
            raise ValueError(f"重复的目标进度：{progress}")
        rewards = plan.get("cumulative_rewards")
        if rewards is None:
            warnings.append(f"{progress} 进度累计奖励尚未确认，不能自行补造")
        elif not isinstance(rewards, list):
            raise ValueError("cumulative_rewards 必须为列表或 null")
        else:
            for reward in rewards:
                if not isinstance(reward.get("name"), str) or not reward["name"].strip():
                    raise ValueError("奖励名称不能为空")
                integer(reward["quantity"], "reward.quantity", 1)
        plans.append({
            "target_progress": progress,
            "required_items": math.ceil(Fraction(progress) / ratio),
            "cumulative_rewards": rewards,
            "source": plan.get("source", ""),
        })
    if not plans:
        raise ValueError("至少提供一个目标进度")

    rows = []
    for boxes, reward in sorted(box_rewards.items()):
        total = base + reward
        progress = total * ratio
        missing = {str(p["target_progress"]): max(0, p["required_items"] - total)
                   for p in plans}
        rows.append({
            "boxes": boxes, "box_items": reward, "total_items": total,
            "estimated_progress_exact": str(progress),
            "estimated_progress_rounded": math.floor(progress + Fraction(1, 2)),
            "missing_items": missing,
            "diamond_budget": {target: count * price for target, count in missing.items()},
        })
    return {
        "initial_items": initial, "non_box_task_items": task_items,
        "base_items": base,
        "task_total_excluding_initial": task_items + max(box_rewards.values()),
        "full_task_items": base + max(box_rewards.values()),
        "progress_per_item": str(ratio), "item_price_diamonds": price,
        "sample_source": sample.get("source", ""), "plans": plans, "rows": rows,
        "warnings": warnings,
        "basis": "仅按输入的已确认来源及样本比例估算；初始赠送只加一次，实测库存不重复加入产出。",
    }


def format_markdown(result):
    lines = ["> 预算按原始实测比例估算，所需道具向上取整，并非保底。", "",
             "| 开箱次数 | 开箱道具 | 累计道具 | 预计进度 |",
             "| ---: | ---: | ---: | ---: |"]
    for row in result["rows"]:
        lines.append(f"| {row['boxes']} | {row['box_items']} | {row['total_items']} | {row['estimated_progress_rounded']} |")
    plans = result["plans"]
    lines += ["", "| 开箱次数 | " + " | ".join(
        f"补至 {p['target_progress']}（钻石）" for p in plans) + " |",
        "| " + " | ".join(["---:"] * (len(plans) + 1)) + " |"]
    for row in result["rows"]:
        lines.append("| " + " | ".join([str(row["boxes"])] + [
            str(row["diamond_budget"][str(p["target_progress"])]) for p in plans]) + " |")
    for plan in plans:
        rewards = plan["cumulative_rewards"]
        text = "待用户确认" if rewards is None else "、".join(
            f"{r['name']} ×{r['quantity']}" for r in rewards) or "已确认无进度奖励"
        lines += ["", f"{plan['target_progress']} 进度累计奖励：{text}。预计需要 {plan['required_items']} 个道具。"]
    return "\n".join(lines) + "\n"


def write_output(path, text):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="文章目录中的活动数据 JSON")
    parser.add_argument("-o", "--output", help="核算 JSON 输出路径；不指定则输出到标准输出")
    parser.add_argument("--markdown", help="同源预算表与累计奖励 Markdown 的输出路径")
    args = parser.parse_args(argv)
    try:
        result = calculate_budget(json.loads(Path(args.input).read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        write_output(args.output, output)
    else:
        print(output, end="")
    if args.markdown:
        write_output(args.markdown, format_markdown(result))
    for warning in result["warnings"]:
        print("⚠ " + warning, file=sys.stderr)


if __name__ == "__main__":
    main()
