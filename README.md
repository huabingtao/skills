# 弹壳特攻队攻略美化与通用排版助手 (danke-strategy-skill)

这是一个专为《弹壳特攻队》(Survivor.io) 设计的 **Gemini CLI 技能包与排版引擎**。它由一个通用的 Markdown-to-WeChat 排版引擎（`engine/`）和具体的游戏内容包（`packs/danke/`）组成，能将粗糙的原始攻略转化为排版精美、带自动配图、符合微信公众号后台发布标准的专业图文稿。

---

## 🌟 核心功能

### 1. 自动化排版美化 (Text Beautification)
根据内容包定义的规则，自动执行：
- **数值高亮 (HTML Color)**：由内容包 `highlight_rules.json` 正则动态配置。例如在弹壳攻略中：
  - <font color="#FF4D4F">**攻击/伤害/暴击类**</font>数值自动标红。
  - <font color="#1890FF">**生命/防御/减伤类**</font>数值自动标蓝。
  - <font color="#52C41A">**冷却/范围/异常类**</font>数值自动标绿。

### 2. 智能免路径配图 (Path-Free Image Resolution)
通过内容包内置的图片映射字典 `image_mapping.json`，提供便捷的免路径配图机制：
- **宽泛名称匹配**：用户在 Markdown 中无需记忆和书写复杂的本地绝对路径，可以直接书写裸名（如 `![等离子剑](等离子剑)`）或带后缀名（如 `![双生导弹](双生导弹.png)`）或使用虚拟协议 `![双绝枪](img://双绝枪)`。
- **字典自动检索**：转换脚本会自动提取名称，去字典中智能匹配为真实本地素材物理路径（如 `packs/danke/assets/img/收藏品/等离子剑.png`）。
- **外部链接智能放行**：对 `http://` 或 `https://` 的外网图片链接自动忽略检索，保持原样，实现本地与外网图床混排。

### 3. 多种通用公众号图片排版样式
支持通过 Markdown 图片后追加 `{type=样式名}` 来调用以下 8 种高品质排版样式（内含防拉伸变形的 `object-fit: cover` 优化）：
- **`card`**：大卡片展示（90% 宽，居中圆角，带柔和阴影，适合重点单图）。
- **`banner`**：宽幅海报图（100% 宽，微圆角，适合首图或章节分割线）。
- **`grid2`**：双栏对比（48% 宽，双图并排，适合装备/流派对比）。
- **`grid3`**：三栏并排（31.3% 宽，三图并排，适合推荐三件套或演进路线）。
- **`grid4`**：四栏并排（23% 宽，四图并排，适合展示同系列配件）。
- **`float-left` / `float-right`**：图文混排（80x80px 悬浮，文字环绕，防拉伸变形）。
- **`avatar`**：角色头像（30px 微标，适合特工/宠物行内展示，防拉伸变形）。
- **`icon`**：普通行内小图标（24px 方形，行内垂直居中，防拉伸变形）。

### 4. 微信公众号富文本适配与自动化发布 (WeChat HTML & Publisher)
项目配备了格式转换与一键发布工具集：
- **CSS 主题解耦**：支持通过 `--theme` 参数加载 `themes/{theme_name}.css` 中的标准 CSS，不再硬编码，极大地方便了排版样式的定制和扩展。
- **微信外链自动转脚注**：自动识别文章中的外部链接（如非 `mp.weixin.qq.com` 链接），转换成脚注 `<sup>[idx]</sup>` 并在文末生成格式美观的“引用链接”列表，完全适配微信对外部超链接的屏蔽规则。
- **图片尺寸属性清洗**：自动剔除 HTML 中的 `width` 和 `height` 数值属性并转换为 `style` 行内宽高及 `object-fit: cover` 属性，彻底解决微信编辑器拉伸、压瘪图片的渲染 Bug。
- **拼音注音 (Ruby) 语法**：提供 `[文字]{注音}` 转换至 `<ruby>文字<rt>注音</rt></ruby>` 的语法，使游戏名词或生僻字注音更方便。
- **自动化发布与 MD5 缓存**：通过 `scripts/publish.py` 可以直接将 HTML 一键发布为公众号后台的草稿，并在上传时利用本地 MD5 缓存（`.wechat_image_cache.json`）跳过重复上传的封面图和正文图片，节省微信 API 额度，大幅缩短二次发布的时间。

---

## 🛠️ 项目目录结构

```text
.
├── SKILL.md                # 技能核心指令集与人设定义
├── GEMINI.md               # 项目上下文与开发规范
├── requirements.txt        # 运行依赖包定义
├── engine/                 # 🔧 通用微信排版编译器与 API 引擎 (100% 通用)
│   ├── compiler.py         # Markdown 转 HTML 核心逻辑
│   ├── highlight.py        # 动态数值高亮规则加载器
│   ├── wechat_api.py       # 封装 of 微信公众号 API 客户端
│   ├── publisher.py        # 微信公众号一键草稿发布器
│   └── utils.py            # 资源扫描与占位图辅助工具
├── themes/                 # 🎨 公用排版主题 CSS 目录
│   └── default.css         # 默认精美排版主题 CSS
├── packs/                  # 📦 专属内容包目录 (按游戏或垂直领域拆分)
│   └── danke/              # 弹壳特攻队攻略专属内容包
│       ├── project.json    # 内容包配置 (指定图片字典、高亮规则与资源目录)
│       ├── formatting_rules.md # 文本排版与颜色规则说明
│       ├── image_mapping.json  # 关键词 -> 物理图片路径映射表
│       ├── highlight_rules.json # 正则提取的数值高亮规则
│       ├── examples.md     # 转换输出排版样式参考示例
│       ├── templates/      # 攻略模板
│       └── assets/         # 弹壳专属游戏素材库
├── scripts/                # 🚀 命令行 CLI 入口
│   ├── compile.py          # 通用编译 CLI（支持 --pack 参数）
│   ├── publish.py          # 通用发布 CLI
│   ├── md_to_wechat.py     # 【向后兼容】调用 compile.py --pack packs/danke
│   ├── wechat_publisher.py # 【向后兼容】调用 publish.py
│   └── config.json         # 公众号 API 配置文件（已在.gitignore中排除）
└── test/
    ├── test_optimization.md      # 外链、注音、防拉伸测试文稿
    ├── test_optimization_wechat.html # 转换后的微信 HTML 验证结果
    └── test_caching.py     # 缓存逻辑单元测试脚本
```

---

## 🚀 快速上手使用说明 (Agent Workflow)

这是一个专门为 AI Agent 设计的自动化技能包。作为用户，您**无需手动运行任何 Python 脚本**，大模型会自动根据您的指令调用相关底层脚本和功能。

### 1. 触发指令
您只需要在对话中提供需要处理的攻略文章（或直接告诉 Agent 文件的路径），并给出明确的需求，例如：
> "帮我美化/优化一下这篇弹壳攻略"
> "排版这篇攻略，并发布到我的微信公众号草稿箱"

### 2. 自动化执行流程
AI Agent 接收到您的指令后，将通过该 Skill 在后台全自动代您执行以下流程：
1. **文本整理与数值高亮**：扫描纯文本，根据预设给关键数值应用标准 HTML 色彩与加粗样式。
2. **智能插图映射**：自动寻找文中提到的专用武器和收藏品名词，基于本地词典注入图片代码和排版布局类型。
3. **微信公众号 HTML 编译**：将其转换为微信兼容的内联 CSS 排版，解决图片拉伸与外链失效问题。
4. **全自动微信发布**：自动处理本地图片的 MD5 缓存去重，并将 HTML 文章一键推送到您的微信草稿箱。

### 3. 环境与依赖（仅供首次配置）
如果你是在全新的终端或系统上部署该项目，Agent 需要确保底层已安装必要的 Python 依赖：
```bash
pip install -r requirements.txt
```

---

## 📝 维护指南

### 1. 游戏更新了新道具/装备时
1. 将新的图片素材保存至 `packs/danke/assets/img/` 相应的分类目录下。
2. 打开 `packs/danke/image_mapping.json`，在字典中追加一项，定义关键词和物理相对路径，例如：
   ```json
   "月殇护手": "packs/danke/assets/img/装备/ss手套-月殇护手.png"
   ```

### 2. 更新或调整排版样式时
编辑 `themes/` 下对应的 `.css` 样式表文件（如 `default.css`）。转换引擎在编译时会自动读取对应的 CSS 选择器规则并内联至各个 HTML 标签。
