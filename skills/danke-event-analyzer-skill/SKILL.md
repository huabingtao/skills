---
name: danke-event-analyzer-skill
description: "从《弹壳特攻队》解包资源（配置表/代码/多语言）中逆向提取任意限时活动全景数值与素材（玩法规则、门票单价、初始票数、任务详情、兑换商店、里程碑奖励及排行榜）。当用户说'查下一个活动'、'分析下期活动'、'查活动数据'、'活动解包分析'、'活动数值提取'、'提取活动素材'、'danke event analyze' 时触发。"
---

# danke-event-analyzer-skill

专为《弹壳特攻队》日常活动攻略创作、数值测算与知识库归档打造的**解包活动全景逆向分析技能**。直接基于官方解密底层配置表（CSVs）、多语言字典（`Language.csv`）与反编译业务逻辑，在活动正式上线前精确提取攻略所需的 7 大核心要素。

---

## 触发词

- "查出弹壳下一个活动"
- "分析明天的活动 X 的内容"
- "帮我提取 X 活动攻略需要用到的素材"
- "查活动数据 / 活动解包分析"
- "提取下期活动任务、兑换和里程碑"
- "/danke-event-analyzer"
- "danke event analyze"

---

## 📁 底层数据源与 SSOT 索引

解包资源根目录：`/home/guagua/workspace/project/danke/danke-resource/`

| 配置文件 | 相对路径 (extracted/tables/) | 核心职责 |
| :--- | :--- | :--- |
| **`EventOpenTime.csv`** | `EventOpenTime.csv` | 活动开放时间戳、主活动类型（col 1）、子活动 ID（col 0/13）、特惠礼包名（col 17） |
| **`Item.csv`** | `Item.csv` | 道具代码（col 0）、分类（col 4: 如 Gourmet）、名称 ID（col 10）、描述 ID（col 11） |
| **`Language.csv`** | `Language.csv` | 官方多语言对照表（col 0: ID, col 2: 简体中文），含玩法规则、概率公示与官方命名 |
| **`FestivalTask.csv`** | `FestivalTask.csv` | 活动专属任务线（col 1: 关联子活动 ID, col 3: 任务类别, col 4: 达成数量, col 6: 奖励票数） |
| **`FestivalExChange.csv`** | `FestivalExChange.csv` | 活动兑换商店（col 1: 关联子活动 ID, col 3: 消耗代币, col 5: 限购次数, col 6: 兑换物品） |
| **`Reward.csv`** | `Reward.csv` | 通用奖励映射字典（col 0: Reward ID, col 2: 包含物品及数量） |
| **各玩法 Base 表** | `*Base.csv`（如 `AppraiseBase.csv`） | 抽奖门票、单价、初始赠送、倍率档位、里程碑进度条奖励绑定（`BigReward`） |
| **各玩法 Rank 表** | `*Rank.csv`（如 `AppraisePushRank.csv`） | 排行榜战力分组阶梯与每日发放奖励映射 |
| **`PanelUI.csv`** | `PanelUI.csv` | 界面预制体与控制器窗口映射（确认所属玩法代码） |

---

## 🛠️ 自动化 CLI 辅助工具

本技能内置自动化一键分析工具，位于 `scripts/analyze_event.py`：

```bash
# 查看指定主活动与子活动完整数据
python3 skills/skills/danke-event-analyzer-skill/scripts/analyze_event.py --main-id 20260807 --task-id 20260808

# 按日期查找并分析活动
python3 skills/skills/danke-event-analyzer-skill/scripts/analyze_event.py --date 2026-11-10
```

---

## 🧭 6 步标准解包分析 SOP 流程

当用户要求分析或提取下期活动时，严格按照以下 6 步工作流执行：

```text
[用户输入活动名称/起止时间]
   │
   ├── Step 1: 时间戳转换与 EventOpenTime.csv 检索 ──► 锁定主活动 ID、任务 ID 与礼包标识
   ├── Step 2: Language.csv & Item.csv 双向反查   ──► 锁定门票 ID、积分代币 ID 与消除物品
   ├── Step 3: Base 表与 C# 控制器逆向挖掘          ──► 提取钻石单价、初始票数、倍率、玩法规则与概率
   ├── Step 4: FestivalTask.csv 5大任务线统计      ──► 归纳登录/主线/巡逻/特别行动/宝箱档位与总收益
   ├── Step 5: FestivalExChange.csv 商店映射       ──► 提取全部 18 项道具名、数量、消耗好感度与限购
   └── Step 6: 里程碑 (BigReward) 与排行榜奖励解析 ──► 锁定 2000 进度与至宝自选等核心大奖档位
```

### 步骤 1：时间戳转换与活动 ID 逆向定位
1. **时间戳计算**：将北京时间（UTC+8）起止时间转化为 Unix Timestamp（UTC）。
   - 例如：`2026-11-10 00:00:00 (UTC+8)` = `1794240000`；`2026-11-14 23:59:59 (UTC+8)` = `1794671999`。
2. **检索 `EventOpenTime.csv`**：
   - 匹配 `col[5] == 1794240000`；
   - 提取三组强关联活动条目：
     - **主活动条目**（如 `col[0]=20260807`, `col[1]=37`）：用于在 Base 表中查询核心抽奖规则与里程碑；
     - **任务与商店条目**（如 `col[0]=20260808`, `col[1]=19`, `col[13]=2330`）：用于在 `FestivalTask` 和 `FestivalExChange` 中查询任务与商店；
     - **商城特惠条目**（如 `col[0]=20260809`, `col[17]=GourmetSale`）：活动商城礼包。

### 步骤 2：多语言与道具代币反查
1. **活动名称与规则文本反查**：
   - 在 `Language.csv` 中检索活动名称（如“鲜花手工坊”），获取对应段落（例如 `501701` 为标题，`501702` 为官方规则）；
2. **道具与代币反查**：
   - 在 `Item.csv` 中反查抽奖门票（如 `2331: 鲜花礼券`）与积分代币（如 `2330: 聚会好感度`）；
   - 反查消除/抽奖元素道具（如 `2324`~`2328` 为蓝/白/粉/黄/红普通花束，`2329` 为限量款花篮）。

### 步骤 3：玩法机制与底层数值挖掘
1. **确定底层玩法 Base 表**：
   - 参考 [活动类型映射字典](references/event_type_mapping.md) 找到对应的 Base 表（如 Gourmet 对应 `AppraiseBase.csv`）；
2. **提取基础数值参数**：
   - **道具单价**：`AppraisePrice`（通常为 40 钻石/张）；
   - **初始免费票**：`DefaultTrickOrTreat`（通常为 10 张）；
   - **倍率系统**：`TicketUseMulti`（根据持有礼券数量阶梯解锁 1x/3x/5x/10x）；
   - **玩法规则与概率**：读取 `Language.csv` 中的官方连线规则、起始连线行数条件、万能道具限制、暴击特殊模式（如聚会模式免费次数）及各项物品出现概率。

### 步骤 4：任务线全景提取与产出精算
1. 检索 `FestivalTask.csv`（`ConnectActivityId == 任务条目ID`）；
2. 分类归纳 5 大标准任务线：
   - `Type 1`：累计登录游戏（通常 5 天，每天 20 张，计 100 张）
   - `Type 2`：参与主线关卡（通常 19 档，最大 40 次，计 222 张）
   - `Type 4`：开启任意宝箱（通常 47 档，最大 600 箱，计 1,455 张）
   - `Type 5`：快速巡逻（通常 18 档，最大 35 次，计 159 张）
   - `Type 25`：完成特别行动（通常 19 档，最大 50 次，计 320 张）
3. 计算核心攻略速算断点：
   - **非开箱全做**（登录+主线+巡逻+特巡）总票数（如 801 张）；
   - **开箱关键节点产出**（0/100/200/260/320/350/380/460/500/600 箱累计增量与累计总票数）。

### 步骤 5：兑换商店全量清单解析
1. 检索 `FestivalExChange.csv`（`ConnectActivityId == 任务条目ID`）；
2. 关联 `Item.csv` 将 Reward ID 解析为规范道具中文名；
3. 输出完整商品表格：商品名称、奖励数量、消耗代币、限购次数；
4. 标注重磅优先项：
   - **门票返还项**（鲜花礼券回血，通常 1,000 代币换 10 张票，限购 40 次可得 400 张门票）；
   - **SP特工碎片 / 至宝伴生配件 / 自选红配件 / 传奇收藏品自选**。

### 步骤 6：累积里程碑与排行榜奖励映射
1. **里程碑进度条 (`BigReward`)**：
   - 解析 Base 表中的 `BigReward` 字段（积分阈值对应 `Reward.csv` 中的 Reward ID）；
   - 在 `Reward.csv` 中反查物品构成；
   - 重点标识：2,000 进度（通常为传奇自选/谐振芯片核心分水岭）与 3,650 进度（通常为至宝收藏品自选礼包）；
2. **排行榜每日分组与奖励 (`*PushRank.csv`)**：
   - 查看每日重置、分组人数（通常 5 人一组）；
   - 提取最高战力阶梯组（第 6 档）前 5 名奖励明细（如史诗配件自选、杰出配件自选等）。

---

## 📝 产出归档标准

分析产出的攻略素材必须同时执行以下归档：
1. **知识库沉淀**：以 Markdown 文件格式保存至工作区 `project/danke/danke-wiki/events/YYYY-MM-DD_活动名称.md`；
2. **符合去 AI 味排版**：大标题（H1）、小章节（H2/H3）严禁使用 Emoji 图标，保持极简专业；
3. **附带耗时统计**：通报各解析环节耗时与总耗时。
