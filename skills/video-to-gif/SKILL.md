---
name: video-to-gif
description: Persistence of video-to-gif conversion with target size constraints. Triggers on requests like "make video to gif", "convert mp4 to gif", "转gif", "制作gif", "将视频转为gif动图并压缩".
---

# Video to GIF Skill (视频转 GIF 动图工具)

This skill provides an automated solution to convert video files (e.g., MP4) into high-quality, web-optimized GIF files with support for file-size constraints.

## 1. When to Use (使用场景)

- **Converting Gameplay Walkthroughs**: When you need to turn mobile gameplay screen recordings (such as Survivor.io/弹壳特攻队 gameplay clips) into GIF animations to embed in WeChat articles or web pages.
- **GIF Size Control**: When target platforms (like WeChat Official Accounts) have strict upload file size limits (e.g., under 30MB or 10MB) and you need to auto-tune parameters to hit the target.
- **Trimming clips**: When you only want to convert a sub-segment of a longer video clip.

## 2. File Structure (目录结构)

```text
video-to-gif/
├── SKILL.md            # Skill instructions (this file)
└── scripts/
    └── video_to_gif.py # Python automated converter with iterative compression
```

## 3. How to Run (使用方式)

The skill utilizes a Python script located at `scripts/video_to_gif.py` which wraps `ffmpeg` commands.

### Command-line Options:
- `--input`: **(Required)** Path to the input video file (e.g. MP4, MOV).
- `--output`: **(Required)** Path to the destination GIF file.
- `--fps`: Initial frame rate for the GIF (default: `10`).
- `--width`: Target width in pixels (default: `320`, sets height proportionally using aspect ratio).
- `--start`: Start timestamp in `hh:mm:ss` or seconds.
- `--duration`: Trim duration in seconds.
- `--max-size`: Target maximum file size in MB. If specified, the script will automatically and iteratively lower the FPS and width if the generated GIF is too large.

### Execution Example (运行示例):
```bash
python3 /Users/hbt/my-project/skills/video-to-gif/scripts/video_to_gif.py \
  --input "/Users/hbt/my-project/content/danke/my-articles-md/活动攻略/特卖超市/活动玩法.mp4" \
  --output "/Users/hbt/my-project/content/danke/my-articles-md/活动攻略/特卖超市/活动玩法.gif" \
  --fps 10 \
  --width 320 \
  --max-size 30
```

## 4. How it Works (实现原理)

1. **High Quality Palette Generation**:
   The script invokes FFmpeg with a 2-pass filter: `palettegen` to generate an optimal 256-color palette for the specific video frames, and `paletteuse` to apply the palette with Lanczos scaling. This prevents color banding.
2. **Iterative Compression**:
   When `--max-size` is provided:
   - It performs an initial conversion.
   - If the size exceeds the target, it lowers the FPS step-by-step (down to 5 FPS).
   - If the size still exceeds the target, it lowers the width in steps of 20px (down to 160px) and re-evaluates.
   - It repeats until the size falls under the target or minimum boundaries are reached.
