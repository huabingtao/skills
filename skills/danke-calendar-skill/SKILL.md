---
name: danke-calendar-skill
description: "专为《弹壳特攻队》每日活动待办与倒计时日历打造的专属创作技能。100%严格依据后台/danke-mcp-server查询出来的规则事实(statusText + digestNote)生成极简清单（单行展示），并在文末精选推荐3篇往期攻略以纯文字居中链接展示，封面统一使用全特工专属底图并渲染「弹壳特攻队 提醒日历YYYY.M.D」。输出路径规范为 project/danke-creator/my-articles-md/提醒/YY.M.D/YY.M.D.md。当用户说'生成弹壳日历'、'生成每日提醒'、'写日历文章'、'今天的日历'、'calendar'、'danke calendar'、'daily reminder'、'生成今日待办'时触发。"
---

# danke-calendar-skill

专为《弹壳特攻队》自媒体运营打造的**每日玩法待办与倒计时日历**内容创作 Skill。
全自动对接数据中心（`danke-mcp-server` / `danke-core`），动态计算当天全部活动规则状态，按统一规范生成客观、真实、无 AI 编造内容的极简每日待办日历初稿。

---

## 🎯 触发词

- "生成今天的弹壳日历"
- "生成今天的每日提醒"
- "写一篇每日日历公众号"
- "生成今日待办事项"
- "查询今天有什么活动日历并生成文章"
- "calendar"
- "danke calendar"
- "daily reminder"
- "/danke-calendar-skill"

---

## ⚠️ 核心铁律与事实准则

1. **【100% 严格基于后台事实】**：
   - 文章正文的各规则描述与备注，**必须 100% 严格使用后台/API 查询返回的实际文案与备注（即 `statusText` 与 `digestNote`）**；
   - **严禁 AI 擅自扩写、推测或编造任何非后台配置的打卡建议/游戏攻略！**
2. **【单行紧凑清单格式】**：
   - 简短开篇后，使用自然的无序列表列出玩法名称、倒计时状态与备注。列表项保持单行，不使用数字序号、加粗小标题或 `>` 引用块，例如：
     ```markdown
     - 神秘商人：离本轮【神秘商人】结束还剩 3 天（记得助力后及时购买）
     ```
3. **【Frontmatter 元数据纯自动驱动（废弃正文宏占位符）】**：
   - 往期推荐与二维码完全由 Frontmatter 中的 `recommendations:` 与 `qrcode_image:` 元数据声明；
   - **正文中严禁书写 `{{往期推荐}}` 或 `{{扫码获取更多精彩}}` 等已废弃的旧版手工占位符**，排版编译引擎会自动在免责声明前注入对应模块；
   - 往期推荐采用纯文本水平居中优雅链接风格（无小图标、无卡片图片）。
4. **【专属封面固化规范】**：
   - 封面底图统一使用全特工紫光专属原图（`assets/reminder_cover_bg.jpg`）；
   - 封面文字统一渲染为双行居中：`弹壳特攻队\n每日日历`。
5. **【目录与文件命名规范】**：
   - 必须按短格式日期目录存放：`project/danke-creator/my-articles-md/提醒/YY.M.D/YY.M.D.md`（例如 `26.9.5/26.9.5.md`）。
6. **【专有名词宏自动标注】**：
   - 自动挂载 `auto_tag.py`，为游戏实体包裹 `{{...}}` 宏标签。

---

## 📝 标准 Frontmatter 与正文结构模板

```yaml
---
title: "【弹壳日历】[YY]年[M]月[D]日"
social_title: "[YY]年[M]月[D]日弹壳日历"
summary: "[YY]年[M]月[D]日《弹壳特攻队》全量[N]大玩法待办与倒计时清单汇总。"
tags:
  - 弹壳特攻队
  - 游戏攻略
  - 弹壳日历
  - 每日待办
cover: "./dist/cover.png"
cover_vertical: "./dist/cover_vertical.png"
author: "弹壳呱呱"
date: YYYY-MM-DD
lastmod: YYYY-MM-DD
qrcode_image: "img://弹壳呱呱微信公众号二维码"
recommendations:
  - title: "【推荐文章一标题】"
    url: ""
  - title: "【推荐文章二标题】"
    url: ""
  - title: "【推荐文章三标题】"
    url: ""
---
```

### 正文模板

```markdown
![article-top](img://article-top){type=banner}

# [YY] 年 [M] 月 [D] 日弹壳日历

各位特工大家[早上好/中午好/下午好/晚上好]，我是呱呱！

今天（[YY] 年 [M] 月 [D] 日）游戏内各玩法的最新待办与事项提醒如下：

- [玩法名称1]：[statusText1]（[digestNote1]）
- [玩法名称2]：[statusText2]
- [玩法名称3]：[statusText3]（[digestNote3]）

---

攻略创作不易，如果帮到了你，请大家多多**转发、点赞和关注**！你们的支持是呱呱持续输出干货的最大动力！

【免责声明】本攻略纯属个人**经验分享**，**仅供参考**，不构成任何消费建议。游戏版本更新较快，具体数值以游戏内实际表现为准。本攻略所引用的美术图片及游戏内截图版权均归 Habby 公司所有。
```

---

## 🛠️ 自动化执行命令

```bash
# 生成今日日历清单（自动拉取数据、制作封面、生成文章并宏标注）
python3 .agents/skills/danke-calendar-skill/scripts/generate_reminder.py

# 指定日期生成
python3 .agents/skills/danke-calendar-skill/scripts/generate_reminder.py --date 2026-09-06
```

## Codex 规则来源与输出

先调用 danke MCP 的 get_reminder_rules（date=目标日期，onlyDigest=true），将 text 中的 JSON 保存到文章 dist/digest.json，再传入 generate_reminder.py --date YYYY-MM-DD --digest-file <文章/dist/digest.json>。只有 MCP 返回成功且日期正确才能生成。接口不可用时停止，不使用简化 SQLite 算法推算。封面及排版、切图衍生产物均输出到文章 dist/；列表保留颜色提示但不使用加粗。
