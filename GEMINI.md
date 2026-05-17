# Gemini 项目上下文：弹壳特攻队攻略美化助手 (danke-strategy-skill)

## 目录概览
本目录是一个 **Gemini CLI 技能包**，专门用于对现有的《弹壳特攻队》(Survivor.io) 攻略文章进行**视觉美化与排版优化**。

## 核心指令：响应式优化 (Reactive Optimization)
根据用户的明确要求，该技能已从“写作助手”转变为**“美化引擎”**。
- **严禁**使用此技能从零开始生成新的攻略文章。
- **仅在**用户提供现有文本并要求“美化”、“优化”或“排版”时才激活。

## 使用与实现指南
1.  **格式化逻辑：**
    - 使用 `references/formatting_rules.md` 进行语义化颜色编码。
    - 使用 `references/image_mapping.md` 注入相关的游戏素材（PNG/WebP）。
    - **微信公众号适配**：项目包含 `scripts/md_to_wechat.py` 脚本，可将美化后的 Markdown 转换为带有行内 CSS 的 HTML，完美适配微信公众号后台。

## 实用工具 (Utilities)
- **Markdown 转微信 HTML**：
  ```bash
  pip install -r requirements.txt
  python scripts/md_to_wechat.py <input_md_file>
  ```
  该脚本会生成一个同名的 `_wechat.html` 文件，包含技术博客风格的行内样式，可直接粘贴至公众号编辑器。
