---
name: bilibili-publisher-skill
description: "将 3:4 切图集与攻略元数据自动上传至 B站 (哔哩哔哩) 创作者中心草稿箱。当用户说'发布到B站'、'上传B站'、'B站草稿'、'bilibili publish' 时触发。"
---

# bilibili-publisher-skill

将 `article-to-img-skill` 生成的 3:4 切图集以及攻略元数据自动上传至 **B站 (哔哩哔哩) 创作者中心草稿箱**。

## 使用

```bash
# 自动读取元数据与图片，保存至 B站草稿箱
python3 scripts/publish.py \
  -i <切图文件夹路径> \
  -m <_wechat.json 或 .md 文件路径>

# 首次登录（有头浏览器扫码）
python3 scripts/publish.py --login
```

## 元数据来源

| 字段 | 来源 | 说明 |
| :--- | :--- | :--- |
| 标题 | `social_title` → `title` | B站专栏/动态标题 |
| 正文 | `summary` + `#tags` 拼装 | 自动在末尾追加话题标签 |
| 封面 | `cover_vertical.png` / `cover.png` | 封面图片 |
| 图片 | `原生网页直切图_3x4/` 目录 | 按文件名排序批量上传 |

## 依赖

```bash
pip install -r requirements.txt
playwright install chromium
```
