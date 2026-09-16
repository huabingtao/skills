#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_asset.py — 新游戏素材一键同步工具
======================================
把一张新图片同时加入：
  1. 本地 assets/img/<分类>/ 目录
  2. 腾讯云 COS（dankeres.guaguahub.cn）
  3. image_mapping.json（本地路径）
  4. image_mapping_cos.json（CDN URL）

用法：
  python3 scripts/add_asset.py <图片文件> --category <分类> [--alias <别名>...]

分类选项（--category）：
  特工 / 配件 / 宠物 / 宝箱 / 钥匙 / 碎片 / 道具 / 载具 / 其它
  装备SS / 装备S
  收藏品-史诗-s01 ~ 收藏品-史诗-s10
  收藏品-传奇-s01 ~ 收藏品-传奇-s10
  技能-宠物 / 技能-特工 / 技能-debuff
  活动道具-扫雷 / 活动道具-神火 / 活动道具-钓鱼

示例：
  python3 scripts/add_asset.py ~/Downloads/新特工.png --category 特工 --alias 新特工 --alias 新特工头像
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path

# ─────────────── 路径配置 ────────────────────────────────────────────────────
SCRIPT_DIR    = Path(__file__).resolve().parent
PACK_ROOT     = SCRIPT_DIR.parent / "packs" / "danke"
LOCAL_IMG_DIR = PACK_ROOT / "assets" / "img"
MAPPING_LOCAL = PACK_ROOT / "image_mapping.json"
MAPPING_COS   = PACK_ROOT / "image_mapping_cos.json"

# ─────────────── COS 配置 ────────────────────────────────────────────────────
SECRET_ID  = os.environ.get("COS_SECRET_ID",  "")
SECRET_KEY = os.environ.get("COS_SECRET_KEY",  "")
BUCKET     = os.environ.get("COS_BUCKET",      "danke-1309453204")
REGION     = os.environ.get("COS_REGION",      "ap-guangzhou")
COS_BASE_URL = "https://dankeres.guaguahub.cn"

# ─────────────── 分类 → (本地目录, COS目录) 映射表 ──────────────────────────
CATEGORY_MAP = {
    # 一级目录
    "特工":            ("特工",                         "game-assets/agents"),
    "配件":            ("配件",                         "game-assets/accessories"),
    "宠物":            ("宠物",                         "game-assets/pets"),
    "宝箱":            ("宝箱",                         "game-assets/boxes"),
    "钥匙":            ("钥匙",                         "game-assets/keys"),
    "碎片":            ("碎片",                         "game-assets/fragments"),
    "道具":            ("道具",                         "game-assets/items"),
    "载具":            ("载具",                         "game-assets/vehicles"),
    "其它":            ("其它",                         "game-assets/misc"),
    # 装备
    "装备SS":          ("装备/SS级装备",                 "game-assets/equipment/ss-grade"),
    "装备S":           ("装备/S级装备",                  "game-assets/equipment/s-grade"),
    # 技能图标
    "技能-宠物":       ("技能图标/宠物技能",              "game-assets/skill-icons/pet-skills"),
    "技能-特工":       ("技能图标/特工技能",              "game-assets/skill-icons/agent-skills"),
    "技能-debuff":     ("技能图标/战斗中debuff",          "game-assets/skill-icons/debuffs"),
    # 活动道具
    "活动道具-扫雷":   ("活动道具/扫雷",                 "game-assets/event-items/minesweeper"),
    "活动道具-神火":   ("活动道具/神火活动",             "game-assets/event-items/fire-event"),
    "活动道具-钓鱼":   ("活动道具/钓鱼活动",             "game-assets/event-items/fishing"),
    **{
        f"收藏品-史诗-s{i:02d}": (
            f"收藏品/史诗收藏品/第{i}期",
            f"game-assets/collectibles/epic/s{i:02d}"
        ) for i in range(1, 11)
    },
    **{
        f"收藏品-传奇-s{i:02d}": (
            f"收藏品/传奇收藏品/第{i}期",
            f"game-assets/collectibles/legendary/s{i:02d}"
        ) for i in range(1, 11)
    },
}


def _guess_content_type(suffix: str) -> str:
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp",
    }.get(suffix.lower(), "application/octet-stream")


def upload_to_cos(local_path: Path, cos_key: str) -> str:
    """上传单个文件到 COS，返回完整 CDN URL。"""
    try:
        from qcloud_cos import CosConfig, CosS3Client
        from qcloud_cos.cos_exception import CosClientError, CosServiceError
    except ImportError:
        print("❌ 请先安装 SDK：python3 -m pip install cos-python-sdk-v5 --break-system-packages")
        sys.exit(1)

    config = CosConfig(Region=REGION, SecretId=SECRET_ID, SecretKey=SECRET_KEY)
    client = CosS3Client(config)

    with open(local_path, "rb") as fp:
        client.put_object(
            Bucket=BUCKET,
            Body=fp,
            Key=cos_key,
            StorageClass="STANDARD",
            ContentType=_guess_content_type(local_path.suffix),
        )
    return f"{COS_BASE_URL}/{cos_key}"


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="新游戏素材一键同步到本地 + COS + 两个 mapping")
    parser.add_argument("image", help="图片文件路径")
    parser.add_argument("--category", required=True,
                        help=f"图片分类，可选：{', '.join(CATEGORY_MAP.keys())}")
    parser.add_argument("--alias", action="append", default=[],
                        help="额外别名（可多次指定），默认使用文件名（去扩展名）作为 key")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不实际上传或修改文件")
    args = parser.parse_args()

    # ── 校验输入 ──────────────────────────────────────────────────────────────
    src_file = Path(args.image).resolve()
    if not src_file.exists():
        print(f"❌ 文件不存在：{src_file}")
        sys.exit(1)

    if args.category not in CATEGORY_MAP:
        print(f"❌ 未知分类：{args.category}")
        print(f"   可选值：{', '.join(CATEGORY_MAP.keys())}")
        sys.exit(1)

    local_subdir, cos_subdir = CATEGORY_MAP[args.category]
    fname       = src_file.name
    stem        = src_file.stem

    # 构建所有 alias key（默认包含文件名去扩展名）
    all_aliases = list(dict.fromkeys([stem] + args.alias))  # 去重保序

    local_dest  = LOCAL_IMG_DIR / local_subdir / fname
    cos_key     = f"danke-assets/{cos_subdir}/{fname}"
    local_path_in_mapping = f"assets/img/{local_subdir}/{fname}"
    cdn_url     = f"{COS_BASE_URL}/{cos_key}"

    print(f"\n{'='*60}")
    print(f"📁 图片文件    : {src_file}")
    print(f"🗂  本地目标    : {local_dest}")
    print(f"☁️  COS Key    : {cos_key}")
    print(f"🌐 CDN URL     : {cdn_url}")
    print(f"🔑 写入别名    : {all_aliases}")
    print(f"{'='*60}")

    if args.dry_run:
        print("🔍 [DRY RUN] 模拟完成，未实际操作。")
        return

    # ── Step 1：复制到本地 assets ─────────────────────────────────────────────
    local_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, local_dest)
    print(f"\n✅ Step1 复制完成：{local_dest}")

    # ── Step 2：上传 COS ──────────────────────────────────────────────────────
    cdn_url = upload_to_cos(local_dest, cos_key)
    print(f"✅ Step2 COS 上传完成：{cdn_url}")

    # ── Step 3：更新两个 mapping 文件 ─────────────────────────────────────────
    mapping_local = load_json(MAPPING_LOCAL)
    mapping_cos   = load_json(MAPPING_COS)

    added = []
    for alias in all_aliases:
        if alias in mapping_local:
            print(f"   ⚠ 别名 '{alias}' 在 image_mapping.json 中已存在，已覆盖")
        mapping_local[alias] = local_path_in_mapping
        mapping_cos[alias]   = cdn_url
        added.append(alias)

    save_json(MAPPING_LOCAL, mapping_local)
    save_json(MAPPING_COS,   mapping_cos)

    print(f"✅ Step3 两个 mapping 已更新，写入 key：{added}")
    print(f"\n🎉 完成！现在可在攻略中使用 {{{{{'}}或{{'.join(all_aliases)}}}}}")


if __name__ == "__main__":
    main()
