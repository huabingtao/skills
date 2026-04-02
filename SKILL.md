---
name: danke-strategy-skill
description: 弹壳特攻队攻略专业美化与自动化配图工具。
---

# 弹壳攻略美化指令集 (Orchestrator)

## 1. 任务流 (Workflow)
当接收到一段原始攻略文本时，按以下顺序执行：
1. **读取规则**：检索 `references/formatting_rules.md` 中的所有视觉样式规则。
2. **应用格式**：将规则应用于原始文本（加粗、数值上色、插入 Emoji、转换引用块）。
3. **注入图片**：检索 `references/image_mapping.md` 中的图片映射字典，识别到匹配的关键词后，在其后（或适当位置）追加 Markdown 图片语法。
4. **表格对齐**：若文本含数值对比，自动转化为美化表格。
5. **最终输出**：输出排版完美、带图片的 Markdown 推文内容。

## 2. 核心限制
- **仅输出 Markdown**。
- **严禁擅自修改用户攻略的原意**，仅做格式修饰和图片补全。
- 若 `image_mapping.md` 中图片路径为“待补齐”，则仅对关键词执行 `**【 】**` 处理。
