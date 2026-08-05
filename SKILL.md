---
name: xiaohongshu-publisher-skill
description: "将 3:4 切图集与攻略元数据自动上传至小红书创作者后台草稿箱。当用户说'发布到小红书'、'上传小红书'、'小红书草稿'、'xhs publish' 时触发。"
---

# xiaohongshu-publisher-skill

基于 **social-auto-upload (Patchright 引擎)**，将 `article-to-img-skill` 生成的 3:4 切图集以及攻略元数据自动上传至**小红书创作者后台草稿箱**。

## 使用

```bash
# 自动读取元数据与图片，保存至小红书草稿箱
python3 scripts/publish.py \
  -i <切图文件夹路径> \
  -m <_wechat.json 或 .md 文件路径>

# 首次登录（有头浏览器扫码登录）
python3 scripts/publish.py --login
```

## 元数据来源

优先级：CLI 参数 > `_wechat.json` > Markdown Frontmatter

| 字段 | 来源 | 说明 |
| :--- | :--- | :--- |
| 标题 | `social_title` → `title` 前 20 字 | 小红书笔记标题限 20 字 |
| 正文 | `summary` + `#tags` 拼装 | 自动在末尾追加话题标签 |
| 封面 | `cover_vertical.png` | 竖版 3:4 封面作为第 1 张图 |
| 图片 | `原生网页直切图_3x4/` 目录 | 按文件名排序批量上传 |

## 依赖与底座引擎

由 `deps/social-auto-upload` (Patchright 驱动) 提供反爬防护与 UI 交互能力。

```bash
pip install patchright requests pillow pyyaml
python3 -m patchright install chromium
```

## Cookie 持久化 (集中式)

- 首次运行 `--login` 打开有头浏览器扫码登录
- Cookie 统一集中保存至 `deps/social-auto-upload/cookies/xiaohongshu_uploader/account.json`
- 后续静默上传自动加载 Cookie 并存草稿箱
