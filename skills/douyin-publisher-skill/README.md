> [!NOTE]
> 📢 **Repository Migrated**: This skill has been migrated into the unified monorepo repository: [huabingtao/skills](https://github.com/huabingtao/skills).
> For the latest updates, issues, and documentation, please visit [huabingtao/skills](https://github.com/huabingtao/skills).

# douyin-publisher-skill

> **职责**：将攻略制作成深蓝电竞3:4图文，每个方案独立成图；按请求上传，停在编辑页由用户手动发布。

完整操作以 [SKILL.md](SKILL.md) 和 [卡片流程](references/card_workflow.md) 为准。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 2. 从已整理、核对的卡片HTML生成本地预览
python3 scripts/render_cards.py /path/to/文章/dist/抖音卡片源.html --source /path/to/文章/攻略.md

# 3. 明确要求上传后，首次登录（扫码）
python3 scripts/publish.py --login

# 4. 上传并停在编辑页供用户手动发布
python3 scripts/publish.py \
  -i /path/to/文章/dist/抖音图文_3x4 \
  -m /path/to/article_stage3_wechat.json --headed --review
```

## 凭证管理

- **Cookie 路径**：`~/.douyin_user_data`（浏览器Profile）
- 首次运行 `--login` 后自动保存
- 失效后重新运行 `--login` 即可刷新

## 与其他 Skill 的关系

| Skill | 职责 |
| :--- | :--- |
| `danke-content-creator-skill` | 分析素材 → 生成攻略 Markdown |
| `danke-strategy-skill` | Markdown → 微信 HTML 编译 |
| `article-to-img-skill` | 用户另选时使用旧版切图 |
| `wechat-publisher-skill` | HTML → 微信公众号草稿箱 |
| **`douyin-publisher-skill`** | 方案独立卡片 → 本地预览 → 按请求上传人工审核 |
