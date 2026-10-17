# 抖音大字卡片提纲

提纲是编辑后的源码，保存文章目录 `抖音提纲.json`，内容取自最新文章与同一次预算核算。先编译文章，核对提纲后记录对应HTML的SHA256，避免新正文配旧提纲。公众号源码保持原样。

## 最小格式

```json
{
  "version": 1,
  "author": "弹壳呱呱",
  "includes_cover": true,
  "pages": [
    {
      "kicker": "活动攻略 · 先看结论",
      "title": "开箱建议与目标奖励",
      "blocks": [
        {"type": "text", "text": "每页一个主题，按本期已确认数据说明。"},
        {"type": "note", "text": "预算按实测估算，并非保底。"}
      ]
    }
  ]
}
```

`source_html_sha256` 可选，生产提纲应填写编译HTML的真实SHA256；不匹配时停止。可用 `python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' 文件路径` 获取。

`includes_cover: true` 表示第一张就是封面，上传器不再加旧竖版封面。只有确实做了封面页才设为true。

## 内容块

所有文本是纯文本；换行用 `\n`，图标宏用 `{{名称}}`，不接受任意HTML。正文名称写完整，宏可用short；只能引用本次编译HTML已解析的图片，未知宏直接报错。

| type | 字段 | 用途 |
|---|---|---|
| text | text | 48px正文，过长自动拆页 |
| note | text | 36px补充依据，过长自动拆页 |
| metric | value，label/detail可选 | 88px重点数字，标签和说明36px |
| list | items，ordered/label可选 | items为文字或 `{"text":"完整名称 ×1","icon":"已编译图片名称"}`；可排序，逐项分页 |
| table | headers、rows，label可选 | 超三列按首列＋其余两列拆表；长表逐行续页并重复表头 |
| image | src，height/alt/fit/position可选 | 已有活动配图，src相对提纲位置；高度默认460px、范围80–700px；fit为contain或cover；position如 `50% 42%` |

图片优先复用编译HTML；封面可引用用户提供的本地活动截图。内页不重复通用 `article-top` 横幅、二维码或往期推荐。装饰图片可在固定画框内布局，截图中的关键依据必须另作完整补充。

一页通常不超过10行正文；表格、奖励列表按实际高度安排。超长不可拆分表格行会报错，需要编辑拆成多行或列表。不会缩小字体、裁断行或放大文字填满尾页。页尾只剩一条说明时，调整提纲合并相关内容或均衡主题，避免空洞续页。

## 验收与清单

```bash
python3 scripts/export_cards.py "文章目录/dist/攻略_stage3_wechat.html" --profile douyin
python3 -m unittest discover -s test -v
```

打开 `dist/抖音图文_3x4/preview.html` 查看360px、390px图片效果，核对字号、奖励、预算及条件。`manifest.json` 记录顺序、是否含封面、输入哈希、实际高度和最小字号；输出前须通过溢出、图片加载和字号检查。渲染失败不覆盖上次成功输出。

`douyin-publisher-skill` 识别清单后只取清单图片；无清单目录保留原有封面＋图片排序行为。手机预览留在 `previews/` 子目录，不上传。
