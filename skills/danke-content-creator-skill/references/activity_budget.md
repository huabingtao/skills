# 活动预算输入与同源输出

将已确认的数据保留为文章目录中的 `活动数据.json`。计算产物输出到该文章 `dist/`，不覆盖源码。

```bash
python3 .agents/skills/danke-content-creator-skill/scripts/calculate_activity_budget.py \
  "文章目录/活动数据.json" \
  -o "文章目录/dist/数值核算.json" \
  --markdown "文章目录/dist/预算表.md"
```

输入示例取自 2026-10-17 时光拼图，仅用于说明字段，不能作为新活动的默认数据：

```json
{
  "initial_items": 5,
  "tasks": {"每日登录": 50, "主线章节": 65, "快速巡逻": 100, "特别行动": 97},
  "box_rewards": {"400": 345, "500": 445, "600": 570},
  "sample": {"items_consumed": 203, "progress_gained": 254, "source": "用户实测前后截图"},
  "item_price_diamonds": 100,
  "plans": [
    {"progress": 850, "cumulative_rewards": [{"name": "神器核心自选", "quantity": 1}], "source": "用户明确的850档奖励"},
    {"progress": 1000, "cumulative_rewards": [{"name": "神器核心自选", "quantity": 1}, {"name": "月咏动态头像", "quantity": 1}], "source": "用户明确的累计奖励"},
    {"progress": 1650, "cumulative_rewards": [{"name": "神炼核心", "quantity": 1}, {"name": "神器核心", "quantity": 1}, {"name": "月咏动态头像", "quantity": 1}], "source": "用户补充的1650档累计奖励"}
  ]
}
```

- `tasks` 只包含非开箱任务及已确认的固定来源，不含初始赠送、当前库存或实测已消耗道具。已确认的广告等来源可单列，并在来源名称或文章中标清条件；未确认的不填。
- `box_rewards` 是各开箱节点对应的累计道具产出，不能用相邻节点差额代替；不插值推算未知节点。
- `sample.progress_gained` 是实测前后进度差，不一定是截图显示的最终进度。`items_consumed` 是本次净消耗，应排除测试期间另外领取或购买的道具。
- 每个方案的 `cumulative_rewards` 为截至该进度已确认的全部进度奖励。`null` 表示尚未确认；`[]` 表示已确认没有进度奖励。不能把随机过程掉落加到累计必得奖励。
- 计算器输出的是实测比例下的估算；不会宣称保底或自动决定是否消费。生成的表格和奖励行用于核对并纳入正文，不将“待用户确认”当成成稿发布。

此例应得到：非开箱加初始 317、全任务 887；500 箱 762 道具约 953 进度，冲 1000 差 38 道具、3800 钻；1650 需 1319 道具，600 箱后差 432 道具、43200 钻。正文、表格和进展消息均引用同一次计算结果。
