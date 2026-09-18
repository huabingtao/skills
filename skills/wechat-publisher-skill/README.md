> [!NOTE]
> 📢 **Repository Migrated**: This skill has been migrated into the unified monorepo repository: [huabingtao/skills](https://github.com/huabingtao/skills).
> For the latest updates, issues, and documentation, please visit [huabingtao/skills](https://github.com/huabingtao/skills).

# wechat-publisher-skill

> **职责**：将任意 `_wechat.html` 发布到微信公众号草稿箱。

这是从 `danke-strategy-skill` 独立拆分出来的微信发布技能包，遵循**单一职责原则**。

---

## 使用

```bash
python3 scripts/publish.py -c <_wechat.html 路径>
python3 scripts/publish.py -c <_wechat.html 路径> --new    # 强制新建草稿
python3 scripts/publish.py --test-config                    # 测试凭证
```

## 凭证配置

优先级：CLI 参数 > 环境变量 > `scripts/config.json` > `~/.wechat_config.json`

```json
// scripts/config.json
{
  "appid": "wx...",
  "appsecret": "..."
}
```

> 🚨 **重要**：需在微信公众平台管理后台将服务器 IP 加入 IP 白名单，否则 API 调用会报错。

## 依赖安装

```bash
pip install -r requirements.txt
```

## 与其他 Skill 的关系

| Skill | 职责 |
| :--- | :--- |
| `danke-strategy-skill` | 攻略 Markdown → 微信 HTML 编译 |
| **`wechat-publisher-skill`** | 编译好的 HTML → 微信公众号草稿箱 |
| `article-to-img-skill` | 编译好的 HTML → 3:4 切图 |
