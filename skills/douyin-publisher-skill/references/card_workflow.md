# 深蓝电竞攻略卡片流程

从文章生成抖音图文时默认读取本文件。用户已提供成品图片时按现有上传流程直接展示并使用；只有用户另选样式时才回到旧切图器。

## 从资料到卡片

1. 先读磁盘最新攻略、已编译文章和预算核算文件。需要从截图起稿时使用同级 `danke-content-creator-skill`，公众号排版与道具映射使用同级 `danke-strategy-skill`。明确本次要求是生成、上传还是发布。
2. 整理本次活动的档位、累计奖励、消耗、任务资源、开箱预算和兑换顺序。截图或用户确认的事实与按样本推算的数据分开说明；保留“预计”、样本比例、向上取整等必要条件。不要套用历史活动的奖励、档位或数值。
3. 复制 `assets/cards.template.html` 到文章 `dist/抖音卡片源.html`，在 `.gallery` 中写各页内容。每个方案单独一个 `.card.single`，依次为目标进度、累计奖励、补钻预算、操作建议、估算依据。不要把多个方案合在一张预算表里。
4. 封面、先看结论、玩法、资源和兑换按内容需要独立安排。内页不反复插横幅、二维码或往期推荐。封面使用已选定的实际素材；`data-kind="cover"` 仅标记第一张封面。
5. 用下方生成命令导出；打开360和390预览核对信息与视觉效果。长段落、长表格自动续页；单行、单条奖励容纳不下时返回编辑源文件处理，不缩字、不裁字。检查续页不要只剩一句说明，有必要时均衡内容后再生成。
6. 明确要求上传时，先展示竖版封面和本次图片，然后调用上传器，保持 `--headed --review`。生成本身不启动上传或登录。

## 模板结构

默认画布600×800 CSS像素，2倍渲染为1200×1600。深蓝底 `#111F32`、青色重点 `#73DFEC`、浅色正文 `#E8EEF6`；四周间距、字号和页脚直接复用 `assets/cards.css`，不要整页缩放。模板保留原版字体链接；字体网络不可用时回退系统字体，需要检查实际效果。

每页使用 `<section class="card single"><div class="body hybrid">…</div></section>`，正文最后加：

```html
<div class="brand"><b>弹壳呱呱</b><span>当次活动 · 档位</span></div>
```

方案编号使用32px CSS字号（成图64px），活动名称保留13px小字；目标进度数字保持48px CSS字号。页码由生成器统一填写。普通说明页可移除 `single`；封面可用 `.hero` 与 `.cover-body`。

方案的内容结构如下，文字和数字都填写当次已核对内容：

```html
<p class="eyebrow plan-heading"><span class="plan-label">方案1</span><span class="activity">活动名称</span></p>
<div class="target"><span class="metric">目标进度</span><span>目标进度</span></div>
<h3>累计奖励</h3>
<div class="reward-list">
  <div class="reward-line">{{神器核心自选}}<span class="item-name">神器核心自选</span><span class="qty">×1</span></div>
</div>
<h3>补钻预算</h3>
<table class="table">
  <thead><tr><th>开箱次数</th><th>预计补钻（钻石）</th></tr></thead>
  <tbody><!-- 每行填写当次核对数字，推荐的一行使用 class="recommended" --></tbody>
</table>
<div class="callout">当次操作建议，保留预计等条件。</div>
<p class="basis">当次任务资源和实测估算依据。</p>
```

例中的道具只说明语法，不代表其他活动一定产出。预算表最多三列；钻石单位只放表头，数字不用千位逗号。推荐行由文章建议决定，不能默认把最后一行或600箱视为所有活动的推荐。

## 识别道具与配图

- 图片宏和同级 `danke-strategy-skill/packs/danke/image_mapping_short.json`、`image_mapping.json` 用于找图；活动截图、规则及用户补充用于确定奖励事实。素材库不用于推断本期奖励。
- 优先使用已存在的 short，兼容完整名称旧宏与 `img://名称`。精确映射后交给原生 `ImageResolver`，关闭占位图和模糊匹配；不另建一套图名字典。
- 正文写完整道具名；宏单独用short。奖励行使用 `.reward-line .item-name/.qty`，兑换行使用 `.exchange-row .item-name`，行内名称和图片包在 `.item-inline` 中；每个奖励和名称数量作为一个完整单元分页。
- 图片最终像素：奖励128、兑换88、行内44，`object-fit:contain` 保持比例。已编译文章的本地或远程图片也可作为 `<img src="…">` 输入；导出时复制素材并记录来源。
- 新道具确实缺图时不写未知宏，不替换成角色或相似道具图。使用文字行并记录具体原因，例如：

```html
<div class="reward-line text-only" data-missing-reason="本期新增，素材库尚未收录">
  <span class="item-name">当次新道具全名</span><span class="qty">×1</span>
</div>
```

未知宏、现有宏文件失效或空图片均停止导出；改成纯文字前要确认确实缺图，不能把失效路径默默掩盖。

兑换列表使用以下结构；顺位和培养建议根据当次文章填写。正文行内使用 `<span class="item-inline">完整道具名{{short}}</span>`，不要把名称和图标拆开。

```html
<div class="exchange-row">
  <span class="order">01</span>{{SP碎片}}<span class="item-name">SP特工万能碎片</span>
  <span class="hint">本次兑换建议</span>
</div>
```

## 生成与交付

在技能目录运行：

```bash
python3 scripts/render_cards.py /绝对路径/文章/dist/抖音卡片源.html \
  --source /绝对路径/文章/攻略.md \
  --source /绝对路径/文章/dist/已核对数据.json
```

`--source` 可重复，传入实际使用的资料；无数据JSON时只传已有来源。默认输出文章 `dist/抖音图文_3x4/`，`--output-dir` 可指定。技能默认在同级寻找 `danke-strategy-skill`，迁移时可用 `--strategy-skill` 指定真实路径。

输出包括编号卡片、`index.html`、`preview_360.html`、`preview_390.html`、`preview.html`、`contact-sheet.jpg`、`asset-manifest.json`、`validation.json`、`manifest.json`。页面含溢出、缺图或不可拆分内容时验证失败，清单禁止上传；保留诊断产物供修正。渲染不删除之前的素材，但上传器只读取本次清单。

`manifest.json` 继续使用既有 `profile: douyin`、`includes_cover`、`images`、`input_sha256`、`image_sha256`、`validation.passed` 协议。它记录输入、模板、渲染器、映射和本地素材哈希；内容变化后应重新生成。缩略图、HTML、预览及素材文件不进入上传清单。

当用户明确要求上传时，再单独运行：

```bash
python3 scripts/publish.py -i /绝对路径/文章/dist/抖音图文_3x4 \
  -m /绝对路径/文章/攻略.md --headed --review
```

已有首张封面时不再加旧封面；只生成方案卡时 `includes_cover` 为false，上传器沿用元数据竖版封面规则。不要为了测试新样式而登录或实际上传。
