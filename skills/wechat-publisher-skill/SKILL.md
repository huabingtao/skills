---
name: wechat-publisher-skill
description: 将任意微信公众号格式的 _wechat.html 文件一键发布到微信公众号草稿箱。支持自动读取旁注 .json 元数据（标题、封面、作者）、图片上传微信 CDN、MD5 去重缓存、草稿 MediaID 跟踪（避免重复创建）。触发词：发布微信草稿, 推送到公众号, 微信发布, publish wechat, 上传公众号
---

# wechat-publisher-skill

专门负责将已编译好的微信 HTML 文章发布到公众号草稿箱的通用技能包。

> **与 `danke-strategy-skill` 的关系**：`danke-strategy-skill` 负责攻略美化与 HTML 编译，`wechat-publisher-skill` 负责发布，两者通过标准 `_wechat.html` 格式对接，各自独立运行。

---

## 使用方法

```bash
python3 /Users/hbt/my-project/skills/wechat-publisher-skill/scripts/publish.py \
  -c <_wechat.html 路径> \
  [--cover <封面图>] \
  [--new]
```

### 常用示例

```bash
# 发布（自动读取同目录的 .json 元数据作为标题/封面/作者）
python3 scripts/publish.py -c 活动攻略_wechat.html

# 强制创建新草稿（不更新已有草稿）
python3 scripts/publish.py -c 活动攻略_wechat.html --new

# 测试凭证是否有效
python3 scripts/publish.py --test-config
```

---

## 凭证配置

凭证读取优先级（由高到低）：

1. CLI 参数：`--appid` / `--secret`
2. 环境变量：`WECHAT_APPID` / `WECHAT_APPSECRET`
3. `scripts/config.json`：`{"appid": "...", "appsecret": "..."}`
4. `~/.wechat_config.json`

首次使用时运行 `--test-config` 会引导你交互式配置并保存凭证。

---

## 核心能力

| 功能 | 说明 |
| :--- | :--- |
| **自动元数据读取** | 自动读取 `_wechat.json` 旁注文件获取标题、封面、作者 |
| **草稿缓存优先覆盖** | 默认读取 `.wechat_draft_cache.json` 中同路径/同名记录的 MediaID 覆盖更新现有草稿，防止重复建草稿 |
| **图片 CDN 上传** | 本地/远程/base64 图片全自动上传到微信 CDN 并替换 src |
| **MD5 去重缓存** | 相同图片只上传一次，多次运行跳过已上传图片 |
| **草稿 ID 跟踪** | 记录已发布草稿的 MediaID，内容无变化时跳过重复更新 |
| **草稿更新模式** | 如草稿 MediaID 已删除，自动降级为创建新草稿；仅指定 `--new` 时新建草稿 |


---

## 依赖安装

```bash
pip install requests
```
