---
name: article-to-img-skill
description: "直接渲染微信公众号文章 / 本地 HTML 网页，按 3:4 (1080x1440) 比例从上到下智能切图（含段落缝隙防切字保护），自动生成适合小红书及抖音的高清图文图集。触发词：微信文章转小红书, 公众号生成切图, 文章转图文, xhs卡片生成, 分割文章, 切图, 直接切图"
---

# article-to-img-skill (原生 HTML 3:4 智能直切图)

`article-to-img-skill` 是一款专为微信公众号文章/HTML 打造的原生网页 3:4 智能直切图技能。直接渲染微信原汁原味的网页排版与配色，按小红书 & 抖音官方推荐的 **3:4 比例 (1080x1440)** 从上到下无缝切割，并具备 **段落缝隙自动避让功能（防切字/防切图）**。

---

## 核心功能与亮点

1. **原汁原味网页分屏**：100% 保留公众号原生排版、图标、配色与表格。
2. **段落缝隙防切字 protection**：在 1440px 高度临界点自动寻找最近的 `<p>`, `<li>`, `<section>` 缝隙处切割，绝不把单行文字或图片切成半截。
3. **超高清 DPR=2 采样**：每张卡片均为标准 1080px × 1440px，字迹清晰无比。
4. **配套文案导出**：自动生成 `copywriting.txt`（包含小红书/抖音标题与热门话题标签）。

---

## 使用方法

在终端运行 Python 直切脚本：

```bash
python3 /Users/hbt/my-project/skills/article-to-img-skill/scripts/export_cards.py <HTML文件路径> [-o 输出目录]
```

### 示例：
```bash
python3 /Users/hbt/my-project/skills/article-to-img-skill/scripts/export_cards.py /Users/hbt/my-project/content/danke/my-articles-md/活动/彩笔奇妙屋活动攻略/彩笔奇妙屋活动攻略_wechat.html
```

---

## 输出结构

```text
原生网页切图_3x4/
├── 01_切图.png             # 1080x1440 原生网页切图 1
├── 02_切图.png             # 1080x1440 原生网页切图 2
├── 03_切图.png             # 1080x1440 原生网页切图 3
└── copywriting.txt        # 小红书/抖音发布文案
```
