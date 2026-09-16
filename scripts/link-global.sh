#!/bin/bash
# 一键将本仓库 skills/ 下所有技能软链接到全局配置目录 (~/.gemini/config/skills)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
SKILLS_SRC="$REPO_DIR/skills"
TARGET_DIR="${1:-$HOME/.gemini/config/skills}"

echo "🚀 开始链接技能到目标目录: $TARGET_DIR"
mkdir -p "$TARGET_DIR"

COUNT=0
for skill_path in "$SKILLS_SRC"/*; do
  if [ -d "$skill_path" ]; then
    skill_name="$(basename "$skill_path")"
    target_link="$TARGET_DIR/$skill_name"
    
    # 如果已存在文件或软链，先移除
    if [ -L "$target_link" ] || [ -e "$target_link" ]; then
      rm -rf "$target_link"
    fi
    
    ln -s "$skill_path" "$target_link"
    echo "  ✅ 已链接: $skill_name -> $skill_path"
    COUNT=$((COUNT + 1))
  fi
done

echo "🎉 成功链接 $COUNT 个技能至 $TARGET_DIR !"
