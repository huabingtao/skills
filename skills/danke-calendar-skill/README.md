# danke-calendar-skill 📅

专为《弹壳特攻队》自媒体运营打造的**每日玩法待办与倒计时日历**内容创作 Skill。
全自动对接数据中心（`danke-mcp-server` / `danke-core`），动态计算当天全部活动规则状态，按统一规范生成客观、真实、无 AI 编造内容的极简每日待办日历初稿。

---

## 🎯 核心功能

1. **100% 后台数据事实驱动**：严格使用后台/API 查询返回的实际文案与备注（`statusText` 与 `digestNote`），零 AI 幻觉编造。
2. **多维紧迫性排序**：自动按剩余天数升序（紧迫性优先）排列生成待办清单。
3. **专属高燃封面自动化合成**：自动基于专属全特工底图合成居中双行标题封面（`弹壳特攻队\n每日日历`）。
4. **Frontmatter 元数据往期推荐**：自动随机精选 3 篇往期硬核攻略以纯文字居中链接插入推荐流。
5. **专有名词宏自动标注**：自动挂载 `auto_tag.py` 进行实体标签包裹。

---

## 🛠️ 使用方法

```bash
# 生成今日待办事项日历文章
python3 scripts/generate_reminder.py

# 指定日期生成
python3 scripts/generate_reminder.py --date 2026-09-06
```

---

## 📄 License
MIT License
