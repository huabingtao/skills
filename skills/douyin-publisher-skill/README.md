> [!NOTE]
> 📢 **Repository Migrated**: This skill has been migrated into the unified monorepo repository: [huabingtao/skills](https://github.com/huabingtao/skills).
> For the latest updates, issues, and documentation, please visit [huabingtao/skills](https://github.com/huabingtao/skills).

# douyin-publisher-skill

> **职责**：将 3:4 切图集与攻略元数据自动上传至抖音创作者后台草稿箱。

这是从弹壳自媒体发布链路中独立拆分出来的抖音发布技能包，遵循**单一职责原则**。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 2. 首次登录（扫码）
python3 scripts/publish.py --login

# 3. 发布图文至草稿箱
python3 scripts/publish.py \
  -i /path/to/原生网页直切图_3x4 \
  -m /path/to/article_stage3_wechat.json
```

## 凭证管理

- **Cookie 路径**：`~/.douyin_cookie.json`
- 首次运行 `--login` 后自动保存
- 失效后重新运行 `--login` 即可刷新

## 与其他 Skill 的关系

| Skill | 职责 |
| :--- | :--- |
| `danke-content-creator-skill` | 分析素材 → 生成攻略 Markdown |
| `danke-strategy-skill` | Markdown → 微信 HTML 编译 |
| `article-to-img-skill` | HTML → 3:4 切图 |
| `wechat-publisher-skill` | HTML → 微信公众号草稿箱 |
| **`douyin-publisher-skill`** | 切图 + 元数据 → 抖音草稿箱 |
