---
name: douyin-publisher-skill
description: "将 3:4 切图集与攻略文案自动上传至抖音创作者后台草稿箱。当用户说'发布到抖音'、'上传抖音'、'抖音草稿'、'douyin publish' 时触发。"
---

# douyin-publisher-skill

基于 **social-auto-upload (Patchright 引擎)**，将 `article-to-img-skill` 生成的 3:4 切图集以及攻略元数据自动上传至**抖音创作者后台草稿箱**。

## 使用

```bash
# 自动读取元数据与图片，保存至抖音草稿箱
python3 scripts/publish.py \
  -i <切图文件夹路径> \
  -m <_wechat.json 或 .md 文件路径>

# 首次登录（有头浏览器扫码登录）
python3 scripts/publish.py --login

# 指定封面与标题覆盖
python3 scripts/publish.py \
  -i <切图文件夹路径> \
  -m <元数据路径> \
  --cover <竖版封面路径> \
  --title "自定义标题"
```

## 元数据来源

优先级：CLI 参数 > `_wechat.json` > Markdown Frontmatter

| 字段 | 来源 | 说明 |
| :--- | :--- | :--- |
| 标题 | `social_title` → `title` 前 20 字 | 抖音图文标题限 20 字 |
| 正文 | `summary` + `#tags` 拼装 | 自动在末尾追加话题标签 |
| 封面 | `cover_vertical.png` | 竖版 3:4 封面作为第 1 张图 |
| 图片 | `原生网页直切图_3x4/` 目录 | 按文件名排序批量上传 |

## 依赖与底座引擎

由 `deps/social-auto-upload` (Patchright 驱动) 提供反爬防护与 UI 交互能力。

```bash
pip install patchright requests pillow pyyaml
python3 -m patchright install chromium
```

## Cookie 持久化与过期自动扫码机制

- 脚本在发布前会自动前置检测 Cookie 有效性：
  - **Cookie 有效**：直接进行静默无感知上传与草稿保存；
  - **Cookie 过期/失效**：自动触发自动登录逻辑或暂停发布并弹出扫码窗口，提示用户使用抖音 App 扫码更新凭证；若登录未完成则立即中断终止后续操作，绝不带着失效状态强行操作。
- 也可以随时通过 `python3 scripts/publish.py --login` 主动扫码更新 Cookie。
- Cookie 统一集中保存至 `deps/social-auto-upload/cookies/douyin_uploader/account.json`。
