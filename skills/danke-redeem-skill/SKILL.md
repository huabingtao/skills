---
name: danke-redeem-skill
description: 批量自动兑换《弹壳特攻队》官网礼包码，支持离线验证码识别。支持导入包含玩家ID的TXT、CSV、Excel文件，自动处理验证码识别和重试。
---

# 弹壳特攻队礼包码自动兑换 Skill

此 Skill 用于批量自动兑换《弹壳特攻队》官网（`https://danke.habby.cn/`）的礼包码。支持通过表格（Excel/CSV）或文本文件导入玩家 ID，自动使用本地离线 OCR 识别验证码，并输出详细的兑换统计报告。

## 使用方法

你可以直接让 AI 助手运行此兑换任务，或者自己在终端中运行。

### 1. 准备玩家 ID 文件

支持以下三种格式：
*   **TXT 文本文件**：每行一个玩家 ID（例如 `12345678`），或者包含备注的格式（如 `微信用户-12345678`，脚本会自动提取末尾的数字作为 ID）。
*   **Excel 文件 (.xlsx / .xls)**：需要包含一列玩家 ID。脚本会自动识别列名为 `ID`、`玩家ID` 或 `userId` 的列。如果未找到这些列名，默认使用第一列。
*   **CSV 文件 (.csv)**：要求同 Excel 文件。

### 2. 在终端中运行

你可以使用以下命令运行脚本：

```bash
# 使用虚拟环境中的 Python 运行脚本
/Users/hbt/my-project/skills/danke-redeem-skill/venv/bin/python3 /Users/hbt/my-project/skills/danke-redeem-skill/scripts/redeem.py --file <玩家ID文件路径> --code <兑换码> --output <输出报告路径>
```

**参数说明：**
*   `--file` / `-f` (必填): 玩家 ID 文件路径。
*   `--code` / `-c` (必填): 礼包兑换码（例如 `中秋节快乐`）。
*   `--output` / `-o` (可选): 导出的结果报告路径，默认为当前目录下的 `redeem_report.xlsx`。
*   `--delay` / `-d` (可选): 每次请求之间的间隔时间（秒），默认 `0.5` 秒，用于防止请求过快被服务器屏蔽。

### 3. 让 AI 助手帮我运行

你可以直接在对话中发送类似以下的要求：
> 帮我把文件 `/Users/hbt/ids.txt` 里的玩家 ID 用兑换码 `中秋节快乐` 进行兑换，结果保存到 `/Users/hbt/result.xlsx`。
