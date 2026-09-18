---
name: article-to-img-skill
description: "直接渲染经过 danke-strategy-skill 编译的微信文章 _wechat.html 网页，按 3:4 (1080x1440 / 2160x2880) 比例进行零留白平滑自适应切图，自动生成适合小红书及抖音的高清图文图集。触发词：微信文章转小红书, 公众号生成切图, 文章转图文, xhs卡片生成, 分割文章, 切图, 直接切图, 导出卡片, article to img"
---

# article-to-img-skill (微信文章 3:4 智能直切图)

`article-to-img-skill` 是一款专为微信公众号富文本页面打造的高稳定性 **3:4 智能自适应直切图技能**。

---

## ⚠️ 标准数据流规范 (重要)

- **严禁直接裸切 raw Markdown 源码**：文章中的游戏宏图标（如 `{{钻石}}`、`{{神器核心}}`）、专属配图（如 `img://article-top`、`img://弹壳呱呱微信公众号二维码`）、往期推荐模块及专属主题样式，必须先经过 **`danke-strategy-skill`** 编译生成完整的 `_wechat.html`。
- **唯一标准输入源**：切图引擎必须以编译后的 **`_wechat.html`** 作为唯一标准渲染源。如果传入 `.md` 文件，脚本会自动优先使用同级最新编译的 `_wechat.html`，或自动调用 `danke-strategy-skill` 全量编译器完成图床与宏解析后再进行切图。

---

## ✨ 核心功能与亮点

1. **零底部留白自适应平滑切片（Zero Blank Padding）**：
   - 采用多图平滑重叠步长算法，保证输出的每一张卡片均 **100% 充满 2160x2880 (3:4) 黄金画布**，彻底杜绝底部大面积空白。
2. **大图自适应约束 + 内联小微标对齐**：
   - 自动识别正文截图并施加黄金比例缩放（`max-height: 440px; max-width: 88%`），防止长图撑爆网页高度。
   - 钻石、钥匙、神器核心等游戏宏图标精准内联（`1.25em`），排版工整优雅。
3. **超高清 DPR=2 采样与手机大字号排版优化**：
   - 默认以 Device Scale Factor = 2 进行渲染截图，输出 **2160px × 2880px** 视网膜级高清大图。
   - **大字号易读规范**：HTML 渲染基准字号为 `24px`，正文 `22px`（行高 1.7），标题 H1 `34px`/H2 `28px`/H3 `25px`，游戏宏图标 `28px`。确保卡片在抖音/小红书手机端展示时字号清晰醒目、无阅读门槛。
4. **配套文案自动生成**：
   - 自动解析文章 frontmatter 与 metadata，在切图目录生成带标题、摘要与热门话题标签的 `copywriting.txt`。

---

## 🚀 使用方法

```bash
# 标准用法：传入经 danke-strategy-skill 编译后的 HTML 文件
python3 /home/guagua/workspace/skill/article-to-img-skill/scripts/export_cards.py <_wechat.html路径> [-o 输出目录]

# 快捷用法：若传入 .md，会自动调用 danke-strategy-skill 编译后再切图
python3 /home/guagua/workspace/skill/article-to-img-skill/scripts/export_cards.py <Markdown文件路径> [-o 输出目录]
```

### 示例：
```bash
# 切割周年庆 Day9 攻略
python3 /home/guagua/workspace/skill/article-to-img-skill/scripts/export_cards.py /home/guagua/workspace/project/danke-creator/my-articles-md/活动/4周年庆活动介绍/周年庆每天进度/day9/弹壳特攻队4周年庆Day9_wechat.html
```

---

## 📁 输出目录结构

```text
原生网页直切图_3x4/
├── 01_切图.png             # 2160x2880 高清 3:4 卡片 1
├── 02_切图.png             # 2160x2880 高清 3:4 卡片 2
├── 03_切图.png             # 2160x2880 高清 3:4 卡片 3
└── copywriting.txt        # 小红书/抖音一键发布文案
```
