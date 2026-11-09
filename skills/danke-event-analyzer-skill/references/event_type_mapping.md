# 弹壳特攻队活动底层架构与映射字典 (Event Pattern Mapping)

本文档归纳了《弹壳特攻队》底层解包资源中各类常见限时活动的**玩法标识、配置表名、界面代码及关联逻辑**。

---

## 一、 常见限时活动玩法与 Base 配置表映射

| 活动类型 / 英文名 | 玩法类型（col 1） | Base 配置表 | Rank 排行表 | 核心界面 (PanelUI) | 代表活动实例 |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **Gourmet / Appraise** | 37 (主) / 19 (任务) | `AppraiseBase.csv` | `AppraisePushRank.csv` | `GourmetMainPanel (548)` | 鲜花手工坊、女神美食家、水果总动员 |
| **Fishing (钓鱼)** | 19 / 6 | `FishBase.csv` | `FishRank.csv` | `FishGatherPanel` | 盛夏捕鱼、冬日海滨钓鱼 |
| **Flip / FlipCard (翻牌)** | 19 / 26 | `FlipBase.csv` / `FlipDynamicLayer.csv` | `FlipRank.csv` | `FlipCardPanel` | 彩笔翻牌、拼图大冒险 |
| **Plinko (弹珠台)** | 19 / 6 | `PlinkoBase.csv` / `PlinkoDynamic.csv` | `PlinkoRank.csv` | `PlinkoMainPanel` | 梦幻弹珠台 |
| **Monopoly / Stroll (大富翁)** | 19 / 6 | `MonopolyBase.csv` / `StrollBase.csv` | `MonopolyRank.csv` | `MonopolyMainPanel` | 假日漫游、黄金大富翁 |
| **Bingo / MatchRemove (消消乐)** | 19 / 6 | `MatchRemoveBase.csv` | `MatchRemoveRank.csv` | `MatchRemoveMainPanel` | 消除大作战、宾果派对 |
| **Dice / RainbowDice (彩虹骰子)** | 19 / 6 | `RainbowDiceBase.csv` | `RainbowDiceRank.csv` | `RainbowDiceMainPanel` | 幸运骰子、飞行棋 |
| **LuckyParty (宝箱派对)** | 19 / 6 | `LuckyPartyBase.csv` | `LuckyPartyRank.csv` | `LuckyPartyMainPanel` | 周年庆幸运宝箱派对 |

---

## 二、 活动关联 ID 架构逻辑 (EventOpenTime.csv)

在 `EventOpenTime.csv` 中，一个完整的限时活动通常由**三组强关联的条目**构成：

1. **主玩法入口（ActivityType = 37 / 6 / 26 等）**：
   - 包含主活动 ID（如 `20260807`）；
   - 对应前端的主 UI 页面（PanelUI 如 `548: GourmetMainPanel`）；
   - 在 Base 表（如 `AppraiseBase.csv`）中以 `col[1] == 20260807` 关联核心数值。
2. **任务与兑换活动（ActivityType = 19）**：
   - 包含任务活动 ID（如 `20260808`）；
   - 绑定积分代币（如 `col[13] = 2330` 聚会好感度）；
   - 在 `FestivalTask.csv` 中以 `col[1] == 20260808` 绑定所有任务档位；
   - 在 `FestivalExChange.csv` 中以 `col[1] == 20260808` 绑定兑换商店。
3. **特惠商城礼包（ActivityType = 7）**：
   - 包含商城活动条目（如 `20260809`）；
   - 字段标记特惠包标识（如 `GourmetSale`）。

---

## 三、 任务类型编号与行为定义 (FestivalTask.csv)

| 任务类型代码 (col 3) | 行为名称 | 常见最高档位 | 攻略统计重点 |
| :---: | :--- | :---: | :--- |
| **`1`** | 累计登录游戏（天数） | 5 天 | 每日直接稳定白嫖 |
| **`2`** | 参与主线关卡（次数） | 40 次 | 可进关直接自杀/退出计入次数 |
| **`4`** | 开启任意宝箱（次数） | 600 箱 | 攻略测算的核心变量，需统计各档收益与性价比断点 |
| **`5`** | 快速巡逻（次数） | 35 次 | 需消耗体力并利用大月卡免费巡逻 |
| **`25`** | 完成特别行动（次数） | 50 次 | 每日日常任务累积 |
