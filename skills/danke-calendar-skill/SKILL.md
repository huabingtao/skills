---
name: danke-calendar-skill
description: "专为《弹壳特攻队》每日活动待办与倒计时日历打造的专属创作技能。严格依据后台规则生成单行清单；每期将逃离行动、区域行动、联机挑战的玩法名称标红，保留道具{{宏}}并在排版后发布公众号草稿。文末推荐3篇往期攻略，复用共同系列封面。输出到 my-articles-md/提醒/YY.M.D/YY.M.D.md。当用户说'生成弹壳日历'、'生成每日提醒'、'写日历文章'、'今天的日历'、'calendar'、'danke calendar'、'daily reminder'、'生成今日待办'时触发。"
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
3. **【Frontmatter 元数据纯自动驱动（8篇优质往期推荐池随机精选）】**：
   - 往期推荐与二维码完全由 Frontmatter 中的 `recommendations:` 与 `qrcode_image:` 元数据声明；
   - **正文中严禁书写 `{{往期推荐}}` 或 `{{扫码获取更多精彩}}` 等已废弃的旧版手工占位符**，排版编译引擎会自动在免责声明前注入对应模块；
   - 往期推荐采用纯文本水平居中优雅链接风格（无小图标、无卡片图片）。
4. **【日历封面规范】**：公众号日历沿用共同系列封面 `my-articles-md/提醒/日历系列封面/dist/cover_calendar_series.png`，复制到当天文章 `dist/cover_calendar_series.png`，同步 Frontmatter 与微信元数据。不使用自动生成的带日期横版封面。
5. **【目录与文件命名规范】**：
   - 必须按短格式日期目录存放：`project/danke-creator/my-articles-md/提醒/YY.M.D/YY.M.D.md`（例如 `26.9.5/26.9.5.md`）。
6. **【专有名词宏自动标注】**：
   - 自动挂载 `auto_tag.py`，为游戏实体包裹 `{{...}}` 宏标签。
   - 道具、装备等命中 `image_mapping.json` 的实体必须保留 `{{...}}` 宏；不得在整理、强调或公众号排版时删除宏。宏用于公众号编译器映射对应游戏图标。

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
cover: "./dist/cover_calendar_series.png"
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

### 重点玩法显示

“逃离行动”“区域行动”“联机挑战”仅将玩法名称显示为红色，不增加额外标签文字；不对列表内容加粗，保持单行，状态与备注严格沿用 MCP 原文。其他玩法不额外着色。

这是每一期日历的固定规范：不得因用户只要求生成、更新或发布而省略名称强调或道具宏。

### 道具宏保留

生成后运行 `auto_tag.py`，对照 danke-strategy-skill 的 `packs/danke/image_mapping.json` 保留游戏道具与实体的 `{{...}}` 宏。遇到倒计时红色 `<font color="#dc2626">` 时，不得把其颜色代码误判成标题或跳过整行标注。公众号排版后，确认这些宏已编译为对应的图标图片；列表仍保持单行且不加粗。

### 生成、排版与发布顺序

1. 调用 danke MCP 的 `get_reminder_rules`（`date=目标日期`、`onlyDigest=true`），将返回 JSON 保存到文章 `dist/digest.json`。
2. 仅在 MCP 成功且返回日期与目标日期一致时，运行 `generate_reminder.py --date YYYY-MM-DD --digest-file <文章目录>/dist/digest.json --output-dir <文章目录>` 生成源码。接口失败时停止，不使用本地简化算法推算。
3. 将共同系列封面复制到当天文章 `dist/cover_calendar_series.png`，并更新 Frontmatter 封面路径。
4. 使用 danke-strategy-skill 美化并编译微信公众号 HTML：

   ```bash
   python3 .agents/skills/danke-strategy-skill/scripts/interactive_flow.py -y <文章目录>/<短日期>.md --pack .agents/skills/danke-strategy-skill/packs/danke
   ```

5. 美化编译成功并确认三项名称着色、道具图标、共同封面后，使用 wechat-publisher-skill 上传草稿（默认按发布器缓存更新同篇已有草稿）：

   ```bash
   python3 .agents/skills/wechat-publisher-skill/scripts/publish.py -c <文章目录>/dist/<短日期>_stage3_wechat.html
   ```

排版失败时不发布；发布失败时保留源码和 `dist/` 产物，报告失败阶段以便重试。封面、排版、切图及验证产物均放在当天文章的 `dist/` 目录。
