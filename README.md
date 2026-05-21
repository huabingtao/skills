# 弹壳特攻队攻略美化助手 (danke-strategy-skill)

这是一个专为《弹壳特攻队》(Survivor.io) 设计的 **Gemini CLI 技能包**。它作为一个高效、专业的 **“攻略美化引擎”**，旨在将粗糙的原始攻略转化为排版精美、带自动配图、符合微信公众号后台发布标准的专业图文稿。

---

## 🌟 核心功能

### 1. 自动化排版美化 (Text Beautification)
根据 [formatting_rules.md](references/formatting_rules.md) 定义的规则，自动执行：
- **关键词强调**：所有装备、技能、道具名称自动包裹为 `**【关键词】**`。
- **数值高亮 (HTML Color)**：
  - <font color="#FF4D4F">**攻击/伤害/暴击类**</font>数值自动标红。
  - <font color="#1890FF">**生命/防御/减伤类**</font>数值自动标蓝。
  - <font color="#52C41A">**冷却/范围/异常类**</font>数值自动标绿。

### 2. 智能免路径配图 (Path-Free Image Resolution)
内置强大的图片映射字典 [image_mapping.md](references/image_mapping.md)，提供便捷的免路径配图机制：
- **宽泛名称匹配**：用户在 Markdown 中无需记忆和书写复杂的本地绝对路径，可以直接书写裸名（如 `![等离子剑](等离子剑)`）或带后缀名（如 `![双生导弹](双生导弹.png)`）或使用虚拟协议 `![双绝枪](img://双绝枪)`。
- **字典自动检索**：转换脚本会自动提取名称，去字典中智能匹配为真实本地素材相对路径（如 `assets/img/收藏品/等离子剑.png`）。
- **外部链接智能放行**：对 `http://` 或 `https://` 的外网图片链接自动忽略检索，保持原样，实现本地与外网图床混排。

### 3. 多种通用公众号图片排版样式
支持通过 Markdown 图片后追加 `{type=样式名}` 来调用以下 8 种高品质排版样式（内含防拉伸变形的 `object-fit: cover` 优化）：
- **`card`**：大卡片展示（90% 宽，居中圆角，带柔和阴影，适合重点单图）。
- **`banner`**：宽幅海报图（100% 宽，微圆角，适合首图或章节分割线）。
- **`grid2`**：双栏对比（48% 宽，双图并排，适合装备/流派对比）。
- **`grid3`**：三栏并排（31.3% 宽，三图并排，适合推荐三件套或演进路线）。
- **`grid4`**：四栏并排（23% 宽，四图并排，适合展示同系列配件）。
- **`float-left` / `float-right`**：图文混排（80x80px 悬浮，文字环绕，防拉伸变形）。
- **`avatar`**：圆形角色头像（30px 圆形微标，带描边，适合特工/宠物行内展示，防拉伸变形）。
- **`icon`**：普通行内小图标（24px 方形，行内垂直居中，防拉伸变形）。

### 4. 微信公众号富文本适配 (WeChat HTML Compatibility)
项目配备了格式转换工具 `scripts/md_to_wechat.py`：
- **行内 CSS 注入**：将所有的 Markdown 标签转化为带有 inline CSS 样式的 HTML 标签，完美兼容微信公众平台后台的富文本渲染。
- **高亮继承修复**：优化了 strong 标签的颜色覆盖问题，确保加粗文本在微信编辑器中能够 100% 继承外层的高亮色。

---

## 🛠️ 项目目录结构

```text
.
├── SKILL.md                # 技能核心指令集与人设定义
├── GEMINI.md               # 项目上下文与开发规范
├── requirements.txt        # 运行依赖包定义
├── assets/
│   └── img/                # 游戏素材库 (分类存储)
│       ├── 装备/           # S/SS装备、核心材料
│       ├── 宝箱/           # 各类宝箱、自选礼包
│       ├── 配件/           # 科技配件相关
│       ├── 收藏品/         # 具体收藏品图片
│       ├── 道具/           # 钥匙、碎片、核心、货币
│       ├── 宠物/           # 宠物相关
│       └── 其它/           # 预留目录
├── references/
│   ├── formatting_rules.md # 文本排版与颜色规则说明
│   ├── image_mapping.md    # 关键词 -> 物理图片路径映射表
│   └── examples.md         # 转换输出排版样式参考示例
├── scripts/
│   ├── md_to_wechat.py     # Markdown 转微信公众号 HTML 转换器
│   └── config.json         # 公众号 API 配置文件（已在.gitignore中排除）
└── test/
    ├── test_images.md      # 多通用图片样式测试文稿
    └── test_images_wechat.html # 转换后的微信 HTML 验证结果
```

---

## 🚀 快速上手使用说明

### 1. 安装环境依赖
在终端中执行以下命令安装运行所需的 Python 依赖：
```bash
pip install -r requirements.txt
```

### 2. 转换 Markdown 为微信公众号 HTML
执行转换脚本，将写好的 Markdown 攻略转换为适配微信后台的 HTML 富文本：
```bash
python3 scripts/md_to_wechat.py <input_md_file> [output_html_file]
```
- **示例**：
  ```bash
  python3 scripts/md_to_wechat.py test/test_images.md
  ```
  执行后会生成 `test/test_images_wechat.html`。打开此文件，直接复制代码粘贴到微信公众号推文编辑器中，即可实现无缝的精美排版和配图展示。

---

## 📝 维护指南

### 1. 游戏更新了新道具/装备时
1. 将新的图片素材保存至 `assets/img/` 相应的分类目录下（建议使用 PNG 或 WebP 格式）。
2. 打开 `references/image_mapping.md`，按照分类在表格中追加一行，定义对应的匹配关键词和物理相对路径，例如：
   ```markdown
   | **【月殇护手】** | `![月殇护手](assets/img/装备/ss手套-月殇护手.png)` | 新装备 |
   ```

### 2. 更新或调整排版样式时
如果需要修改微信中各组件的默认字号、行高或颜色，可编辑 `scripts/md_to_wechat.py` 中 `styles` 字典下的内联样式配置。
