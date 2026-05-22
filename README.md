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
- **`avatar`**：角色头像（30px 微标，带描边，适合特工/宠物行内展示，防拉伸变形）。
- **`icon`**：普通行内小图标（24px 方形，行内垂直居中，防拉伸变形）。

### 4. 微信公众号富文本适配与自动化发布 (WeChat HTML & Publisher)
项目配备了格式转换与一键发布工具集：
- **CSS 主题解耦**：支持通过 `--theme` 参数加载 `references/themes/{theme_name}.css` 中的标准 CSS，不再硬编码，极大地方便了排版样式的定制和扩展。
- **微信外链自动转脚注**：自动识别文章中的外部链接（如非 `mp.weixin.qq.com` 链接），转换成脚注 `<sup>[idx]</sup>` 并在文末生成格式美观的“引用链接”列表，完全适配微信对外部超链接的屏蔽规则。
- **图片尺寸属性清洗**：自动剔除 HTML 中的 `width` 和 `height` 数值属性并转换为 `style` 行内宽高及 `object-fit: cover` 属性，彻底解决微信编辑器拉伸、压瘪图片的渲染 Bug。
- **拼音注音 (Ruby) 语法**：提供 `[文字]{注音}` 转换至 `<ruby>文字<rt>注音</rt></ruby>` 的语法，使游戏名词或生僻字注音更方便。
- **自动化发布与 MD5 缓存**：通过 `scripts/wechat_publisher.py` 可以直接将 HTML 一键发布为公众号后台的草稿，并在上传时利用本地 MD5 缓存（`.wechat_image_cache.json`）跳过重复上传的封面图和正文图片，节省微信 API 额度，大幅缩短二次发布的时间。

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
│   ├── examples.md         # 转换输出排版样式参考示例
│   └── themes/             # 排版主题 CSS 样式目录
│       └── default.css     # 默认精美排版主题 CSS
├── scripts/
│   ├── md_to_wechat.py     # Markdown 转微信公众号 HTML 转换器
│   ├── wechat_api.py       # 封装的微信公众号接口客户端
│   ├── wechat_publisher.py # 微信公众号一键草稿发布器
│   └── config.json         # 公众号 API 配置文件（已在.gitignore中排除）
└── test/
    ├── test_optimization.md      # 外链、注音、防拉伸测试文稿
    ├── test_optimization_wechat.html # 转换后的微信 HTML 验证结果
    └── test_caching.py     # 缓存逻辑单元测试脚本
```

---

## 🚀 快速上手使用说明

### 1. 安装环境依赖
在终端中执行以下命令安装运行所需的 Python 依赖：
```bash
pip install -r requirements.txt
```

### 2. 转换 Markdown 为微信公众号 HTML
执行转换脚本，指定主题（默认为 `default`），将写好的 Markdown 攻略转换为适配微信后台的 HTML 富文本：
```bash
python3 scripts/md_to_wechat.py <input_md_file> [output_html_file] --theme default
```
* **示例**：
  ```bash
  python3 scripts/md_to_wechat.py test/test_optimization.md --theme default
  ```
  执行后会生成 `test/test_optimization_wechat.html` 及提取出的元数据 `test/test_optimization_wechat.json`。

### 3. 一键发布至微信公众号草稿箱
在首次使用或需要配置公众号 API 时，可运行测试连接命令并根据提示输入凭证：
```bash
python3 scripts/wechat_publisher.py --test-config
```
配置完成后，运行以下发布命令：
```bash
python3 scripts/wechat_publisher.py -c test/test_optimization_wechat.html
```
* **参数说明**：
  - `-c, --content`：指定转换后的 HTML 文件路径（脚本会自动关联同名的 `.json` 元数据文件获取标题、封面等信息）。
  - `-t, --title`：指定文章标题（若 HTML 对应的 JSON 中有 title 则可不填）。
  - `--cover`：指定封面图片路径。
  - `-a, --author`：指定作者（默认：`弹壳呱呱`）。

执行后，脚本会先比对 MD5 缓存并上传未缓存的图片，然后一键创建草稿。成功后，可直接前往微信公众号后台的“草稿箱”查看与发布！

---

## 📝 维护指南

### 1. 游戏更新了新道具/装备时
1. 将新的图片素材保存至 `assets/img/` 相应的分类目录下（建议使用 PNG 或 WebP 格式）。
2. 打开 `references/image_mapping.md`，按照分类在表格中追加一行，定义对应的匹配关键词和物理相对路径，例如：
   ```markdown
   | **【月殇护手】** | `![月殇护手](assets/img/装备/ss手套-月殇护手.png)` | 新装备 |
   ```

### 2. 更新或调整排版样式时
如果需要修改微信中各组件的默认字号、行高或颜色，无需修改任何 Python 逻辑，只需编辑 `references/themes/` 下对应的 `.css` 样式表文件（如 `default.css`）。转换引擎在编译时会自动读取对应的 CSS 选择器规则并内联至各个 HTML 标签。
