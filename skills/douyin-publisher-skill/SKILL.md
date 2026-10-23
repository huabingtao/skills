---
name: douyin-publisher-skill
description: "将攻略制作成深蓝电竞3:4图文，每个方案独立成图并配真实道具图；按请求上传抖音，默认停在有头编辑页等待用户手动发布。当用户说'发布到抖音'、'上传抖音'、'抖音草稿'、'按上次格式做抖音图文'、'douyin publish' 时触发。"
---

# douyin-publisher-skill

本技能负责攻略图文生成、配图与按请求上传。生成默认使用已认可的深蓝电竞模板；每个方案独立成图。已有成品图片直接使用。上传使用现有 Playwright 上传器，默认供用户手动发布。

## 默认图文生成流程

从攻略生成图片时先读 [排版、道具识别与交付流程](references/card_workflow.md)。用最新文章和核对数据填写 `assets/cards.template.html`，再运行 `scripts/render_cards.py`；每个方案按“目标进度 → 累计奖励 → 补钻预算 → 操作建议 → 估算依据”排列。输出1200×1600图片及手机预览到文章 `dist/抖音图文_3x4/`。

图片宏复用同级 `danke-strategy-skill` 的精确映射；正文名称保持完整。缺少新道具图片时记录原因并保留文字数量。奖励、兑换、正文图标分别128／88／44像素。图文制作与上传是两个独立入口，仅要求生成时交付本地预览。用户明确选择旧直切样式时再调用 `article-to-img-skill`。

```bash
# 只生成图片，不登录、不上传
python3 scripts/render_cards.py <文章dist/抖音卡片源.html> \
  --source <最新攻略.md> --source <实际使用的核对数据.json>
```

生成器自动拆分长段落、奖励列表和表格续页；不可完整容纳的条目报错，不能缩小字号或裁断内容。导出后检查360／390预览，核对奖励、预算、道具图和必要条件，再按以下流程处理上传。

## 使用

### 默认人工发布流程

上传抖音图文时，按以下顺序操作：

1. 在启动抖音浏览器前，先预览并向用户展示待上传的竖版封面和切图素材；素材已经是截图卡片时直接展示原图，不要另行裁切或改写。
2. 使用有头浏览器打开抖音创作者平台，完成登录、图片上传和标题、正文填写。
3. 进入 `--review` 人工审核模式。上传完成后将编辑页面截图保存至文章 `dist/douyin_draft_result.png`，向用户展示截图，并让浏览器停留在编辑页面，等待用户手动发布。
4. 禁止点击“发布”“立即发布”“高清发布”等发布按钮，也不要自动确认发布弹窗。不要点击保存草稿或暂存离开，以免离开待用户审核的编辑页面。
5. 操作结束后保持浏览器开启，不主动关闭浏览器或其上下文；由用户自行发布并关闭窗口。

脚本默认启用有头人工审核，命令仍推荐显式写出 `--headed --review`。未获当次明确代发要求时，不传 `--publish`；只有明确要求暂存离开时才使用 `--save-draft`。示例：

```bash
python3 scripts/publish.py \
  -i <切图文件夹路径> \
  -m <_wechat.json 或 .md 文件路径> \
  --headed --review
```

`--review` 会强制显示浏览器，在图片上传、标题和正文回读核验完成后停在编辑页。任一必填项未找到或回读不完整时，不报告上传完成，保留窗口供检查。

交接证据保留在文章 `dist/`：`douyin_review_content.png` 为内容区全页截图，`douyin_draft_result.png` 为操作区截图，`douyin_review_result.json` 记录标题正文回读、请求上传图片数与审核状态。不能仅凭页面底部的“发布”按钮截图证明内容已经填好。

```bash
# 自动读取元数据与图片，打开编辑页供用户检查并手动发布
python3 scripts/publish.py \
  -i <切图文件夹路径> \
  -m <_wechat.json 或 .md 文件路径> \
  --headed --review

# 首次登录（有头浏览器扫码登录）
python3 scripts/publish.py --login

# 指定封面与标题覆盖
python3 scripts/publish.py \
  -i <切图文件夹路径> \
  -m <元数据路径> \
  --cover <竖版封面路径> \
  --title "自定义标题" \
  --headed --review
```

## 元数据来源

优先级：CLI 参数 > `_wechat.json` > Markdown Frontmatter

| 字段 | 来源 | 说明 |
| :--- | :--- | :--- |
| 标题 | `social_title` → `title` 前 20 字 | 抖音图文标题限 20 字 |
| 正文 | `summary` + `#tags` 拼装 | 自动在末尾追加话题标签 |
| 封面 | `cover_vertical.png` | 竖版 3:4 封面作为第 1 张图 |
| 图片 | 优先 `抖音图文_3x4/`，兼容 `原生网页直切图_3x4/` | 新版按已验证 `manifest.json` 顺序；旧版按文件名排序 |

抖音大字卡片目录若有 `manifest.json`，仅上传清单图片；`includes_cover: true` 时首张已是封面，不重复加入元数据中的旧封面。显式 `--cover` 替换首张封面；没有内置封面时则前置。预览、HTML和文案不上传；无效清单报错，不回退为扫描整个目录。生成或验收卡片本身不授权启动上传。

## 依赖与浏览器

当前 `scripts/douyin_uploader.py` 使用 Playwright 的 Chromium 持久化 Profile。

```bash
pip install -r requirements.txt
python3 -m playwright install chromium
```

## Cookie 持久化与过期自动扫码机制

- 脚本在发布前会自动前置检测 Cookie 有效性：
  - **Cookie 有效**：按命令参数上传；默认人工流程会打开有头浏览器并停在编辑页等待用户处理；
  - **Cookie 过期/失效**：自动触发自动登录逻辑或暂停发布并弹出扫码窗口，提示用户使用抖音 App 扫码更新凭证；若登录未完成则立即中断终止后续操作，绝不带着失效状态强行操作。
- 也可以随时通过 `python3 scripts/publish.py --login` 主动扫码更新 Cookie。
- 登录会话随浏览器 Profile 保存在 `~/.douyin_user_data`。不复制、打印或清除账户凭证；不能为了修复路径而创建另一套空 Profile 并声称原登录已失效。

## 人工发布约定

即使脚本支持 `--publish`，本工作区的抖音上传也默认由用户最终发布。除非用户在当次请求中明确要求代为发布，否则始终遵循上面的“默认人工发布流程”。
