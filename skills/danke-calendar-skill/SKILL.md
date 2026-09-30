---
name: danke-calendar-skill
description: 根据 danke MCP 的当日规则生成《弹壳特攻队》每日提醒 Markdown 和双规格封面。用于“生成弹壳日历”“今天的弹壳待办”“写每日日历”；普通日程安排、月度活动预告和系统定时提醒不使用本技能。
---

# 弹壳每日提醒

## 输入与事实来源

- 目标日期默认取 Asia/Shanghai 当天，格式 `YYYY-MM-DD`；用户指定日期优先。
- 先调用 danke MCP `get_reminder_rules(date=目标日期, onlyDigest=true)`，检查无错误，再解析 `content` 中 text 的 JSON，保存至文章 `dist/digest.json`。只接受日期匹配、包含 `items` 数组的数据。
- MCP 不可用时核对注册配置和重启状态，不能假装调用成功。不要用缓存、旧文章或本地简化算法计算当日状态。
- 用户明确接受直接查询 danke-core 时，可用 `--api-base http://localhost:3000`；这是 HTTP 来源，不能描述为 MCP 查询。脚本不静默切换来源。
- 清单仅来自 `name`、`statusText`、`digestNote`，允许去除重复名称和换行、添加颜色；不扩写后台未提供的建议。剩余天数为空的项目排最后，不当成 0 天。空数组说明本次返回 0 项，不推断游戏无活动。

## 生成

命令从技能仓库根目录运行；在其他目录执行时，将脚本路径替换为当前技能真实路径。不要依赖旧的 `workspace/skill/` 目录。

```bash
python3 skills/danke-calendar-skill/scripts/generate_reminder.py \
  --date 2026-09-30 --digest-file /文章目录/dist/digest.json \
  --output-dir /文章目录
```

- 默认文章位置：工作区 `project/danke-creator/my-articles-md/提醒/YY.M.D/YY.M.D.md`；兼容已有 `content/danke-creator`。工作区可用 `WORKSPACE_ROOT` 指定，独立安装可直接用 `--output-dir`。
- 原文存在时停止；用户已要求覆盖/更新同日日历时加 `--force`，不必重复确认。
- 默认生成 `dist/cover.png`、`dist/cover_vertical.png`，并调用同级排版技能进行宏标注。底图为本技能 `assets/reminder_cover_bg.jpg`；标题双行居中：`弹壳特攻队\n提醒日历YYYY.M.D`。
- `--skip-covers --no-auto-tag` 用于只生成文本或离线检查。跳过封面时元数据仍是约定路径，发布前必须补齐文件。
- 缺少脚本、封面生成失败或数据无效时退出失败，不覆盖已有文章，也不声称完整生成。

## 文章约定

Frontmatter 包含 title、social_title、summary、tags、cover、cover_vertical、author、date、lastmod，以及按需配置的 recommendations、qrcode_image。封面路径为 `./dist/cover.png` 和 `./dist/cover_vertical.png`。

正文保留 Banner、纯文本标题、短开场、单行自然列表及既定文末声明。列表格式：

```markdown
- 玩法名称：后台状态文案（后台备注）
```

没有备注就省略括号，不给列表文字加粗。三篇往期推荐只在 Frontmatter 声明，链接来自已有可核对链接池；不写旧版正文宏占位符。问候语取生成时刻的上海时间，推荐顺序由目标日期确定。

## 验收与后续

核对日期、项目数、清单文案、封面日期及文件存在性。报告实际产物与跳过的步骤。仅请求日历时完成源文和封面即可；排版交给 `danke-strategy-skill`，只有用户要求发布才进入 `wechat-publisher-skill`。
