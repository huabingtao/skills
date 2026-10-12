#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
弹壳特攻队文章推荐池抽样工具 (Recommendations Picker)
用于从中央文章池中随机挑选推荐链接，注入新文章 Frontmatter。
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path

DEFAULT_POOL = [
    {
        "title": "【载具攻略】载具零件怎么摆？四种摆法与分配顺序参考",
        "url": "https://mp.weixin.qq.com/s/Y2qGmNvrl6uhn8TE53dG-g",
    },
    {
        "title": "【特工攻略】弹壳特攻队从入门到入土特工篇",
        "url": "https://mp.weixin.qq.com/s/5Ar4FIsI0YvgqDk46-fHyw",
    },
    {
        "title": "【载具攻略】从入门到入土载具篇",
        "url": "https://mp.weixin.qq.com/s/U4MdV7UYFi4unPy6PawVog",
    },
    {
        "title": "【宠物攻略】S宠物培养全指南——从入门到入土",
        "url": "https://mp.weixin.qq.com/s/pJitLL_Vu7wI9ctzSM-EMg",
    },
    {
        "title": "弹壳特攻队高频问答第一弹",
        "url": "https://mp.weixin.qq.com/s/QMfvpK7okI0yFyg2kRYkXQ",
    },
    {
        "title": "手把手教会你用弹壳伤害计算器",
        "url": "https://mp.weixin.qq.com/s/vN79nJW3Cyn9sy0UDGvKaw",
    },
    {
        "title": "SS神装打造优先级——合成顺序深度解析",
        "url": "https://mp.weixin.qq.com/s/DvQ9EJ7Yu4lVLtPLhkqPeg",
    },
    {
        "title": "【高频问答第二弹】《弹壳特攻队》",
        "url": "https://mp.weixin.qq.com/s/LFca8kzXxbcglBcQP19hoA",
    },
]


def find_pool_path(custom_path=None) -> Path | None:
    """定位 recommendations_pool.json 文件位置"""
    if custom_path:
        p = Path(custom_path)
        if p.exists():
            return p

    candidates = [
        # Relative to current file
        Path(__file__).resolve().parents[2] / "danke-strategy-skill/packs/danke/config/recommendations_pool.json",
        Path(__file__).resolve().parents[1] / "packs/danke/config/recommendations_pool.json",
        # Workspace root paths
        Path.cwd() / ".agents/skills/danke-strategy-skill/packs/danke/config/recommendations_pool.json",
        Path("/Users/hbt/skills/skills/danke-strategy-skill/packs/danke/config/recommendations_pool.json"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def get_pool(pool_path=None) -> list[dict]:
    """加载文章池列表，加载失败则回退至内置 DEFAULT_POOL"""
    target = find_pool_path(pool_path)
    if target and target.exists():
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            print(f"⚠ 读取推荐池失败 ({e})，使用默认配置", file=sys.stderr)
    return DEFAULT_POOL.copy()


def pick_recommendations(
    pool: list[dict] | None = None,
    count: int = 3,
    exclude: str | list[str] | None = None,
    seed: int | None = None,
) -> list[dict]:
    """
    从推荐池中随机抽取 count 篇推荐文章。

    :param pool: 自定义文章池，若为空则自动加载
    :param count: 抽样数量，默认 3
    :param exclude: 需排除的关键词或标题（字符串或列表），用于避免同名同主题重复推荐
    :param seed: 随机数种子（可选）
    """
    current_pool = pool if pool is not None else get_pool()

    if exclude:
        excludes = [exclude.lower()] if isinstance(exclude, str) else [e.lower() for e in exclude]
        filtered = [
            item for item in current_pool
            if not any(exc in item.get("title", "").lower() for exc in excludes)
        ]
        # 如果排除后数量不足 count，回退使用原池以确保数量充足
        if len(filtered) >= count:
            current_pool = filtered

    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random.Random()

    sample_size = min(count, len(current_pool))
    return rng.sample(current_pool, sample_size)


def format_recommendations_yaml(articles: list[dict]) -> str:
    """格式化为标准 YAML Frontmatter 片段"""
    lines = ["recommendations:"]
    for art in articles:
        lines.append(f'  - title: "{art["title"]}"')
        lines.append(f'    url: "{art["url"]}"')
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="弹壳特攻队文章推荐池抽样工具")
    parser.add_argument("-c", "--count", type=int, default=3, help="抽取文章数量 (默认: 3)")
    parser.add_argument("-e", "--exclude", type=str, default=None, help="排除包含特定关键词的文章（避免重复）")
    parser.add_argument("-s", "--seed", type=int, default=None, help="随机种子 (可选)")
    parser.add_argument("-f", "--format", choices=["yaml", "json"], default="yaml", help="输出格式 (yaml/json)")
    parser.add_argument("-p", "--pool", type=str, default=None, help="自定义 recommendations_pool.json 路径")

    args = parser.parse_args()

    pool_data = get_pool(args.pool)
    recs = pick_recommendations(pool=pool_data, count=args.count, exclude=args.exclude, seed=args.seed)

    if args.format == "json":
        print(json.dumps(recs, ensure_ascii=False, indent=2))
    else:
        print(format_recommendations_yaml(recs))


if __name__ == "__main__":
    main()
