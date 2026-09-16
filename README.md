# 🧰 Agent Skills Collection (`huabingtao/skills`)

专为 AI Coding Agent（如 Google Antigravity、Claude Code、Cursor 等）打造的生产级技能集（Skills Monorepo）。涵盖**游戏攻略撰写**、**自媒体跨平台自动发布**、**图片切图与处理**以及**音视频提取总结**等实战自动化能力。

---

## 📦 技能矩阵表 (Skills Matrix)

| 技能名称 (Directory) | 功能定位 | 主要触发词 | 依赖环境 |
| :--- | :--- | :--- | :--- |
| [`article-to-img-skill`](skills/article-to-img-skill) | 微信文章/HTML智能切图为 3:4 (1080x1440) 高清图文 | `切图`、`文章转图文`、`微信文章转小红书` | Node.js / Python |
| [`bilibili-publisher-skill`](skills/bilibili-publisher-skill) | 自动上传 3:4 切图集至 B站 (哔哩哔哩) 创作者中心草稿箱 | `发布到B站`、`B站草稿`、`bilibili publish` | Python, Playwright |
| [`danke-calendar-skill`](skills/danke-calendar-skill) | 《弹壳特攻队》11大玩法周期倒计时日历与待办生成 | `弹壳日历`、`今日日历`、`生成日历` | Python |
| [`danke-content-creator-skill`](skills/danke-content-creator-skill) | 弹壳特攻队原始素材分析与标准 Markdown 攻略初稿撰写 | `写攻略`、`生成攻略`、`撰写文章` | Agent Native |
| [`danke-strategy-skill`](skills/danke-strategy-skill) | 弹壳攻略一键美化排版与微信公众号草稿自动化发布 | `美化文章`、`排版攻略`、`发布微信` | Node.js, Python |
| [`douyin-publisher-skill`](skills/douyin-publisher-skill) | 自动上传 3:4 图文切图集至抖音创作者后台草稿箱 | `发布到抖音`、`抖音草稿`、`douyin publish` | Python, Playwright |
| [`wechat-publisher-skill`](skills/wechat-publisher-skill) | 将微信格式 HTML 文章一键直推微信公众号官方草稿箱 | `发布微信草稿`、`推送到公众号`、`微信发布` | Python, WeChat API |
| [`xiaohongshu-publisher-skill`](skills/xiaohongshu-publisher-skill) | 自动上传 3:4 图文切图集至小红书创作者服务平台草稿箱 | `发布到小红书`、`小红书草稿`、`xhs publish` | Python, Playwright |
| [`danke-redeem-skill`](skills/danke-redeem-skill) | 《弹壳特攻队》官网批量自动兑换礼包码（含离线验证码识别） | `兑换礼包码`、`批量兑换`、`danke redeem` | Python, ddddocr |
| [`wechat-cover-generator`](skills/wechat-cover-generator) | 公众号（2.35:1）与小红书（3:4）双模精美封面生成 | `生成封面`、`制作封面`、`做个封面` | Python, Pillow |
| [`image-slicer-skill`](skills/image-slicer-skill) | 基于 CCA 连通域分析的自动雪碧图/图标裁切工具 | `切图`、`雪碧图切图`、`分割图标` | Python, OpenCV/Pillow |
| [`video-summarizer-skill`](skills/video-summarizer-skill) | 本地音视频及 YouTube/B站在线视频音轨提取与多语言智能总结 | `总结视频`、`视频转文字`、`总结YouTube` | Python, Whisper, ffmpeg |
| [`video-to-gif`](skills/video-to-gif) | 高保真视频转 GIF 动图与目标文件大小自动压缩 | `转gif`、`制作gif`、`video to gif` | Python, ffmpeg |

---

## 🚀 快速开始与安装 (Getting Started)

### 1. 克隆本仓库
```bash
git clone git@github.com:huabingtao/skills.git
cd skills
```

### 2. 全局安装到 Antigravity / Claude Code
运行内置的软链接脚本，将所有技能一键链接至 `~/.gemini/config/skills`：
```bash
bash scripts/link-global.sh
```

### 3. 单独或按需挂载到特定项目
若只需在某个特定项目中启用部分技能，可直接软链接到该项目的 `.agents/skills/` 目录：
```bash
mkdir -p .agents/skills
ln -s /path/to/skills/skills/danke-calendar-skill .agents/skills/danke-calendar-skill
```

---

## 📄 开源协议 (License)
本项目采用 [MIT License](LICENSE) 开源。
