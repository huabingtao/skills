#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
danke-strategy-skill 资源上传腾讯云 COS 脚本
=============================================
上传 packs/danke/assets/img/ 下所有游戏图片到 COS，
同时将中文目录名映射为英文路径，并生成 image_mapping_cos.json。

用法：
    python3 upload_to_cos.py --region ap-guangzhou [--dry-run]
"""

import os
import json
import argparse
from pathlib import Path

# ─────────────── 腾讯云 COS 凭证（优先从环境变量读取） ──────────────────
SECRET_ID  = os.environ.get("COS_SECRET_ID",  "")
SECRET_KEY = os.environ.get("COS_SECRET_KEY",  "")
BUCKET     = os.environ.get("COS_BUCKET",      "danke-1309453204")

# 自定义 CDN 域名（COS 存储桶已绑定）
COS_BASE_URL = os.environ.get("COS_BASE_URL", "https://dankeres.guaguahub.cn")

# ─────────────── 本地路径 ────────────────────────────────────────────────
SCRIPT_DIR    = Path(__file__).resolve().parent
PACK_ROOT     = SCRIPT_DIR.parent / "packs" / "danke"
LOCAL_IMG_DIR = PACK_ROOT / "assets" / "img"
IMAGE_MAPPING = PACK_ROOT / "image_mapping.json"

# ─────────────── COS 目录结构：中文 → 英文映射（最长优先匹配）────────────
DIR_MAPPING = [
    # 收藏品子目录（最长匹配优先，须放在父目录前面）
    *[(f"收藏品/史诗收藏品/第{i}期",  f"game-assets/collectibles/epic/s{i:02d}") for i in range(1, 11)],
    *[(f"收藏品/传奇收藏品/第{i}期",  f"game-assets/collectibles/legendary/s{i:02d}") for i in range(1, 11)],
    ("收藏品/史诗收藏品",             "game-assets/collectibles/epic"),
    ("收藏品/传奇收藏品",             "game-assets/collectibles/legendary"),
    ("收藏品",                        "game-assets/collectibles"),
    # 装备子目录
    ("装备/SS级装备",                 "game-assets/equipment/ss-grade"),
    ("装备/S级装备",                  "game-assets/equipment/s-grade"),
    ("装备",                         "game-assets/equipment"),
    # 技能图标子目录
    ("技能图标/宠物技能",              "game-assets/skill-icons/pet-skills"),
    ("技能图标/战斗中debuff",          "game-assets/skill-icons/debuffs"),
    ("技能图标/特工技能",              "game-assets/skill-icons/agent-skills"),
    ("技能图标",                      "game-assets/skill-icons"),
    # 活动道具子目录
    ("活动道具/扫雷",                 "game-assets/event-items/minesweeper"),
    ("活动道具/神火活动",             "game-assets/event-items/fire-event"),
    ("活动道具/钓鱼活动",             "game-assets/event-items/fishing"),
    ("活动道具",                      "game-assets/event-items"),
    # 一级目录
    ("特工",                         "game-assets/agents"),
    ("配件",                         "game-assets/accessories"),
    ("宠物",                         "game-assets/pets"),
    ("宝箱",                         "game-assets/boxes"),
    ("钥匙",                         "game-assets/keys"),
    ("碎片",                         "game-assets/fragments"),
    ("道具",                         "game-assets/items"),
    ("载具",                         "game-assets/vehicles"),
    ("其它",                          "game-assets/misc"),
]


def chinese_dir_to_cos_key(local_rel_path: str) -> str:
    """将本地相对于 assets/img/ 的中文路径转换为 COS key（带 danke-assets/ 前缀）。"""
    local_rel_path = local_rel_path.replace("\\", "/").strip("/")
    for cn_prefix, cos_prefix in DIR_MAPPING:
        cn_norm = cn_prefix.replace("\\", "/")
        if local_rel_path.startswith(cn_norm + "/") or local_rel_path == cn_norm:
            rest = local_rel_path[len(cn_norm):]
            return f"danke-assets/{cos_prefix}{rest}"
    # 兜底：放到 misc
    return f"danke-assets/game-assets/misc/{local_rel_path}"


def build_cos_url(region: str, key: str) -> str:
    return f"{COS_BASE_URL}/{key}"


def should_skip(filename: str) -> bool:
    return filename.startswith(".") or filename in ("Thumbs.db",)


def _guess_content_type(suffix: str) -> str:
    return {
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif":  "image/gif",
        ".webp": "image/webp",
        ".svg":  "image/svg+xml",
        ".json": "application/json",
    }.get(suffix.lower(), "application/octet-stream")


def upload_assets(region: str, dry_run: bool = False):
    try:
        from qcloud_cos import CosConfig, CosS3Client
        from qcloud_cos.cos_exception import CosClientError, CosServiceError
    except ImportError:
        print("❌ 请先安装 SDK：python3 -m pip install cos-python-sdk-v5 --break-system-packages")
        return

    config = CosConfig(Region=region, SecretId=SECRET_ID, SecretKey=SECRET_KEY)
    client = CosS3Client(config)

    # ── 收集所有图片文件 ──────────────────────────────────────────────────
    all_files = []
    for root, dirs, files in os.walk(LOCAL_IMG_DIR):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if should_skip(fname):
                continue
            full_path = Path(root) / fname
            rel_path  = str(full_path.relative_to(LOCAL_IMG_DIR)).replace("\\", "/")
            cos_key   = chinese_dir_to_cos_key(rel_path)
            all_files.append((full_path, rel_path, cos_key))

    print(f"\n{'='*60}")
    print(f"📦 共发现 {len(all_files)} 个文件待上传")
    print(f"🪣 存储桶：{BUCKET}  地域：{region}")
    print(f"{'🔍 [DRY RUN] 模拟运行，不实际上传' if dry_run else '🚀 开始上传...'}")
    print(f"{'='*60}\n")

    # ── 构建 rel_from_pack → cos_key 反查表（用于更新 image_mapping）───────
    local_to_cos = {}
    for full_path, rel_path, cos_key in all_files:
        # rel_path 相对于 LOCAL_IMG_DIR；image_mapping 里路径形如 assets/img/xxx
        local_to_cos[f"assets/img/{rel_path}"] = cos_key

    # ── 上传循环 ──────────────────────────────────────────────────────────
    success_count = 0
    fail_count    = 0
    failed_files  = []

    for i, (full_path, rel_display, cos_key) in enumerate(all_files, 1):
        print(f"[{i:3d}/{len(all_files)}] {rel_display}")
        print(f"         → danke-assets/.../{cos_key.split('danke-assets/')[-1]}")

        if dry_run:
            success_count += 1
            continue

        try:
            with open(full_path, "rb") as fp:
                client.put_object(
                    Bucket=BUCKET,
                    Body=fp,
                    Key=cos_key,
                    StorageClass="STANDARD",
                    ContentType=_guess_content_type(full_path.suffix),
                )
            success_count += 1
        except (CosClientError, CosServiceError) as e:
            print(f"         ❌ 失败: {e}")
            fail_count += 1
            failed_files.append((str(full_path), cos_key, str(e)))

    # ── 生成 image_mapping_cos.json ────────────────────────────────────
    with open(IMAGE_MAPPING, "r", encoding="utf-8") as f:
        original_mapping = json.load(f)

    cos_mapping = {}
    for alias, local_path in original_mapping.items():
        local_path_norm = local_path.replace("\\", "/")
        mapped_key = local_to_cos.get(local_path_norm)
        if mapped_key:
            cos_mapping[alias] = build_cos_url(region, mapped_key)
        else:
            cos_mapping[alias] = local_path  # 保留原值兜底

    out_path = PACK_ROOT / "image_mapping_cos.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cos_mapping, f, ensure_ascii=False, indent=2)

    # ── 汇总报告 ──────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"✅ 成功：{success_count}   ❌ 失败：{fail_count}")
    print(f"📝 image_mapping_cos.json 已写入 → {out_path}")
    if not dry_run:
        print(f"🌐 访问前缀：https://{BUCKET}.cos.{region}.myqcloud.com/danke-assets/")

    if failed_files:
        print("\n❌ 失败文件：")
        for fp, key, err in failed_files:
            print(f"  {fp}")
            print(f"  → {key}  原因：{err}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="上传 danke-strategy-skill 资源到腾讯云 COS")
    parser.add_argument("--region",  required=True, help="COS 地域，如 ap-guangzhou")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不实际上传")
    args = parser.parse_args()

    upload_assets(region=args.region, dry_run=args.dry_run)
