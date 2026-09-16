---
name: image-slicer
description: Automated spritesheet slicing tool using Connected Component Analysis (CCA) to segment and crop icons from an atlas. Trigger this skill whenever the user asks to slice an image, crop a spritesheet, split an atlas, or says phrases like "我要切图", "帮我切图", "把这张图片的所有图标切出来", "切图".
---

# Image Slicer Skill (图片连通域自动切图工具)

This skill provides an automated solution to segment, crop, and save individual icons (e.g., items, chests, cards, avatars) from a spritesheet with a transparent or white background.

## 1. When to Use (使用场景)

- **Unpacking Sprite Sheets**: When you unpack mobile game assets (e.g. from Survivor.io / 弹壳特攻队) and receive merged atlas files or sheets that you need to slice into individual transparent PNGs.
- **Visual Asset Categorization**: Slicing UI layouts or custom screenshots shared by users containing multiple item rewards.
- **Handling Non-uniform Grids**: Traditional grid-slicing fails when items are not spaced in uniform rows or columns. This tool uses Connected Component Analysis (CCA) to dynamically find exact bounding boxes of elements.

## 2. File Structure (目录结构)

```text
image-slicer-skill/
├── SKILL.md            # Skill instructions (this file)
└── scripts/
    └── slice_image.py  # Python automated BFS/CCA slicing script
```

## 3. How to Run (使用方式)

The skill utilizes a Python script located at `scripts/slice_image.py`. It requires `Pillow` (the standard Python Imaging Library).

### Command-line Options:
- `--image`: **(Required)** Path to the input spritesheet image (PNG).
- `--output`: **(Required)** Path to the output folder where sliced PNGs will be saved.
- `--prefix`: Filename prefix for cropped items (default: `sprite`). Output files are named as `{prefix}_row{R}_col{C}.png`.
- `--min-size`: Minimum width/height (in pixels) for components to crop (default: `50`). Helps ignore tiny background noise.
- `--alpha`: Alpha channel threshold (0-255) to detect non-transparent pixels (default: `10`).
- `--color`: RGB color threshold to exclude white backgrounds (default: `250`).

### Execution Example (运行示例):
```bash
python3 /Users/hbt/my-project/image-slicer-skill/scripts/slice_image.py \
  --image "/Users/hbt/拆包素材/media__1780830921684.png" \
  --output "/Users/hbt/拆包素材/切图/chests/" \
  --prefix "chest" \
  --min-size 50
```

## 4. How it Works (算法原理)

1. **二值蒙版生成 (Binary Mask Generation)**:
   The script scans every pixel in the source image. Any pixel that is non-transparent (Alpha > threshold) and not solid white (RGB values < threshold) is marked as a **foreground pixel**.
2. **广度阶层搜索连通域 (BFS Connected Component Labeling)**:
   It iterates over the image and initiates a **Breadth-First Search (BFS)** whenever it hits an unvisited foreground pixel. It traverses all adjacent foreground pixels in 8 directions, identifying them as a single connected component (an individual icon).
3. **边界计算与尺寸过滤 (Bounding Box & Size Filter)**:
   For each component, it records the minimum and maximum X/Y coordinates to form the bounding box `(min_x, min_y, max_x, max_y)`. It drops any component smaller than `--min-size` to prevent cropping background speckles.
4. **行列重排 (Row/Column Logical Ordering)**:
   To ensure the outputs are named logically following a reading order (left-to-right, top-to-bottom), the script clusters the bounding boxes into rows based on vertical proximity and sorts each row horizontally.
5. **透明裁剪与保存 (Transparent Cropping)**:
   It calls Pillow's `crop()` on the source RGBA image using the sorted bounding boxes, preserving the transparency channel, and writes them out as clean PNGs.
