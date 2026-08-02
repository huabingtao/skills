# bilibili-publisher-skill

> **职责**：将 3:4 切图集与攻略元数据自动上传至 B站 (哔哩哔哩) 创作者中心草稿箱。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 2. 首次扫码登录
python3 scripts/publish.py --login

# 3. 发布图文至 B站 草稿箱
python3 scripts/publish.py \
  -i /path/to/原生网页直切图_3x4 \
  -m /path/to/article_stage3_wechat.json
```

## 凭证管理

- **Profile 目录**：`~/.bilibili_user_data`
- 首次运行 `--login` 后自动持久化 Profile 状态
