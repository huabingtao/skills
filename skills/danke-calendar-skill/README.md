# danke-calendar-skill

从已计算的后台规则生成弹壳每日提醒，输出 Markdown、封面和可追溯的规则 JSON。

使用流程及参数见 [SKILL.md](SKILL.md)。Python 3.9+；日历文本逻辑仅依赖标准库，封面依赖同仓库 `wechat-cover-generator`，宏标注依赖 `danke-strategy-skill`。

推荐先经 MCP 获取目标日 JSON，再从技能仓库根目录执行：

```bash
python3 skills/danke-calendar-skill/scripts/generate_reminder.py --date 2026-09-30 --digest-file /文章目录/dist/digest.json --output-dir /文章目录
```

只检查文本时加 `--skip-covers --no-auto-tag`；明确覆盖已有原文时加 `--force`。HTTP 直连需显式传入 `--api-base http://localhost:3000`，不作为 MCP 失败后的自动替代。
