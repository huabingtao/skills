#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键自动修复 image_mapping.json 映射关系，并自动扫描/补全未映射的收藏品
"""
import os
import json

def update_all_mappings():
    skill_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    pack_dir = os.path.join(skill_root, "packs/danke")
    mapping_path = os.path.join(pack_dir, "image_mapping.json")
    assets_dir = os.path.join(pack_dir, "assets/img")

    if not os.path.exists(mapping_path):
        print("❌ image_mapping.json not found")
        return

    # Load existing mappings
    with open(mapping_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)

    # 1. 扫描磁盘上所有的实际图片文件
    disk_files = {}
    disk_files_stripped = {}  # 剥离前缀的字典
    for r, d, fs in os.walk(assets_dir):
        for f in fs:
            if f.endswith(('.png', '.jpg', '.jpeg')):
                full_path = os.path.join(r, f)
                rel_path = os.path.relpath(full_path, pack_dir)
                basename = os.path.basename(f)
                name_only = os.path.splitext(basename)[0]
                
                # 记录原始名字
                disk_files[name_only] = rel_path
                
                # 记录剥离了 '第X期'、'传奇收藏品-' 等前缀后的纯净名字
                stripped = name_only
                if '-' in stripped:
                    parts = stripped.split('-', 1)
                    if parts[0].isdigit() or parts[0] == "传奇收藏品":
                        stripped = parts[1]
                disk_files_stripped[stripped] = rel_path

    # Helper to strip prefixes
    def strip_prefix(s):
        parts = s.split('-', 1)
        if len(parts) >= 2 and (parts[0].isdigit() or parts[0] == "传奇收藏品"):
            return parts[1]
        return s

    fixed_count = 0
    # 2. 修复已有的但物理文件路径发生变化的映射
    for key, path in list(mapping.items()):
        full_mapped_path = os.path.join(pack_dir, path)
        if not os.path.exists(full_mapped_path):
            basename = os.path.basename(path)
            name_only = os.path.splitext(basename)[0]
            stripped_key = strip_prefix(key)

            if name_only in disk_files:
                mapping[key] = disk_files[name_only]
                print(f"Fixed: '{key}': {path} -> {disk_files[name_only]}")
                fixed_count += 1
            elif stripped_key in disk_files:
                mapping[key] = disk_files[stripped_key]
                print(f"Fixed: '{key}': {path} -> {disk_files[stripped_key]}")
                fixed_count += 1
            elif key in disk_files_stripped:
                mapping[key] = disk_files_stripped[key]
                print(f"Fixed: '{key}': {path} -> {disk_files_stripped[key]}")
                fixed_count += 1
            elif stripped_key in disk_files_stripped:
                mapping[key] = disk_files_stripped[stripped_key]
                print(f"Fixed: '{key}': {path} -> {disk_files_stripped[stripped_key]}")
                fixed_count += 1

    # 3. 扫盘自动补充：将新扫描到但不在映射字典中的所有图片文件注册进去
    added_count = 0
    if os.path.exists(assets_dir):
        for r, d, fs in os.walk(assets_dir):
            for f in fs:
                if f.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    full_path = os.path.join(r, f)
                    rel_path = os.path.relpath(full_path, pack_dir)
                    basename = os.path.basename(f)
                    name_only = os.path.splitext(basename)[0]
                    
                    # 如果这个图片原始名字没有映射，直接添加
                    if name_only not in mapping:
                        mapping[name_only] = rel_path
                        print(f"Added new mapping for '{name_only}': {rel_path}")
                        added_count += 1
                    
                    # 尝试添加剥离前缀的名字映射
                    stripped_name = strip_prefix(name_only)
                    if stripped_name not in mapping and stripped_name != name_only:
                        mapping[stripped_name] = rel_path
                        print(f"Added new stripped mapping for '{stripped_name}': {rel_path}")
                        added_count += 1

    if fixed_count > 0 or added_count > 0:
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        print(f"✔ Successfully fixed {fixed_count} and added {added_count} mappings in image_mapping.json")
    else:
        print("✔ No changes needed in image_mapping.json")

if __name__ == "__main__":
    update_all_mappings()
