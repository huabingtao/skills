---
name: video-summarizer-skill
description: 视频与音频内容详细总结工具。支持解析 YouTube 链接和本地视频/音频文件，自动提取已有字幕或利用本地 Whisper 模型进行语音转文字，并由 Agent 最终生成带时间戳、要点大纲的结构化 Markdown 报告。
---

# 视频/音频内容智能总结指令集 (Video Summarizer Skill)

## 1. 核心定位 (Scope)

当用户要求“总结视频”、“视频转文字”、“总结 YouTube”、“提取视频内容”或传入本地视频/音频文件时触发。通过调用本地 Python 脚本提取出带有时间戳的完整文本，然后由 Agent 进行翻译、整理，并输出高质量的结构化 Markdown 总结报告。

## 2. 触发条件 (Triggers)

当用户输入包含以下关键词或动作时激活：

- **总结视频**、**视频总结**、**YouTube总结**、**B站总结**、**视频转文字**、**提取字幕**、**总结这期视频**、**总结本地视频**。
- 用户上传或指明了本地的 `.mp4`、`.mkv`、`.mov`、`.mp3`、`.wav`、`.m4a` 等音视频文件路径，并要求提取/总结内容。

## 3. 目录结构 (File Structure)

```text
skills/video-summarizer-skill/
├── SKILL.md            # 本技能指令文件（当前文件）
├── requirements.txt    # Python 依赖包
└── scripts/
    └── summarize.py    # 音视频处理、字幕获取与 Whisper 本地转录脚本
```

## 4. 运行依赖 (System & Python Dependencies)

- 系统中需安装 `ffmpeg` 并加入环境变量（已确认 Mac 环境下位于 `/usr/local/bin/ffmpeg`）。
- Python 环境（建议在虚拟环境中运行）需安装 `requirements.txt` 中的依赖：

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

## 5. 执行命令 (Execution Command)

在 `skills/video-summarizer-skill/` 目录下运行：

```bash
python3 scripts/summarize.py --input "<YouTube链接或本地视频路径>" --output "output_transcript.json" --model "base"
```

### 参数说明

- `--input`: **(必填)** 支持 YouTube 视频链接 (如 `https://www.youtube.com/watch?v=...`)、Bilibili 视频链接 (如 `https://www.bilibili.com/video/...` 或 `https://b23.tv/...`) 或本地视频/音频文件的绝对路径。
- `--output`: **(选填)** 转录文本的输出 JSON 路径，默认保存在当前目录下。
- `--model`: **(选填)** 本地 Whisper 模型大小（可选 `tiny`、`base`、`small`、`medium` 等，默认 `base`，在 Intel CPU 上建议使用 `tiny` 或 `base`）。
- `--language`: **(选填)** 强制指定转录语言（如 `zh`、`en`），默认由 Whisper 自动检测。

## 6. 交互与输出规范 (Output & Format Specification)

在 Python 脚本运行完毕并输出转录文件（包含时间戳的文本片段）后，Agent（我）需要读取转录内容，并为用户生成以下格式的**结构化 Markdown 总结报告**：

### 报告结构模板

````markdown
# 🎥 视频内容详细总结：[视频标题/文件名]

## 📝 一句话简介 (Overview)
[用一到两句话精炼概括视频的核心主题与结论]

## 🕒 视频时间轴与章节大纲 (Timeline & Outline)
- **[00:00 - 02:15] 章节标题一**
  - 要点 1：描述该阶段视频讨论的核心内容。
  - 要点 2：涉及的数据或结论。
- **[02:15 - 05:40] 章节标题二**
  - 要点 1：...
  - 要点 2：...

## 💡 核心知识点与深度提炼 (Key Takeaways)
1. **[核心概念 1]**：详细展开解释，提取视频中的论据和推导过程。
2. **[核心概念 2]**：详细展开解释。
````

### 语言规则

如果原始视频为英文或其它外语，转录文本为英文，Agent 在总结时应**自动将其翻译并使用中文**生成上述 Markdown 报告。

