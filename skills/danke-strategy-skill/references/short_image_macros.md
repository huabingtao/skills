# 图片 short 宏

推荐表位于 `packs/danke/image_mapping_short.json`，结构是 `short → image_mapping.json 中已有名称`。每个可用素材路径只有一个推荐 short；不删除旧别名，也不复制或改名图片。

```markdown
S 级杰出装备自选宝箱{{S自选箱}}
S 级军备钥匙{{S钥匙}}
SP 特工万能碎片{{SP碎片}}
神器核心自选宝箱{{神器核心自选}}
史诗收藏品宝箱{{史诗收藏箱}}
科技滑板碎片{{滑板碎片}}
电动平衡车碎片{{平衡车碎片}}
```

正文使用完整名称或用户原有写法，宏使用表内推荐拼写。已有长宏、short、新旧宏混用、`img://short` 均可解析，正文不会被自动缩写。没有独立简称的专名沿用名称；不截字生成不明含义的缩写。

## 维护与检查

在技能目录执行：

```bash
python3 scripts/check_short_mapping.py
python3 scripts/check_short_mapping.py --output-dir /绝对路径/dist/图片short映射
```

第一条只检查；第二条额外输出 `report.json` 和可搜索的 `preview.html`（完整名称、宏、图片对照）。检查覆盖重复 JSON 键、名称碰撞、目标缺失、同一素材多个 short，以及可用素材是否全部覆盖。

新增素材后，在推荐表中登记一个 short，目标必须是原始映射的现有名称，不能链式指向另一 short。推荐名不能覆盖指向不同素材的旧名称。多个旧名称指向同一路径时只保留一个推荐 short；图片字节相同但道具含义不同的条目仍分别保留。

当前失效的旧素材路径只列入报告，不生成 short，也不猜图替代。修复真实素材后再新增推荐项。`image_mapping.json` 与 `image_mapping_cos.json` 保持兼容；本地和 COS 模式都加载同一 short 表。COS 缺某个别名时先按已知完整名称与同路径别名解析，再回退到已确认的本地素材，避免模糊匹配到碎片等其他图片。
