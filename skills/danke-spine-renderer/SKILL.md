---
name: danke-spine-renderer
description: 根据散落的 Spine 图集贴图（.png + .atlas + .skel）自动拼装并渲染出完整角色/皮肤/造型透明背景高清 PNG 的工作流技能。当用户提到"根据贴图拼装"、"拼装样式"、"Spine 渲染"、"骨骼动画截图"、"把散图拼成完整角色"、"异宠化形/特工/Boss/3D模型贴图拼装"或提供了包含 skeleton_xs.skel/.atlas/.png 的目录（或需要从 XAPK 解包提取 Spine 并渲染导入 danke-assets）时，务必使用本技能。
---

# Danke Spine 贴图自动拼装与渲染技能

将游戏解包得到的散落图集贴图（`*.png` + `*.atlas` + `*.skel`）通过 **匹配对应 Spine 版本的 `@esotericsoftware/spine-player` + Playwright 无头 Chrome (WebGL)** 自动拼装为完整的透明背景高清 PNG，并按需导出或导入 `danke-assets`。

## 核心避坑规则（必须遵守）

1. **二进制 `.skel` 提取禁止走 UTF-8 文本编码**：
   - 使用 `UnityPy` 从 Unity `TextAsset` 提取 `.skel` 时，**禁止**使用 `d.m_Script.encode('utf-8')`（会损坏 `> 0x7F` 的二进制字节，导致 `Skin name must not be null` 报错）。
   - 必须使用 `obj.get_raw_data()` 按 Unity `TextAsset` 二进制布局（`[uint32 name_len][name][4字节对齐][uint32 data_len][raw_bytes]`）直接切片提取原始字节。
2. **严格匹配 Spine 运行时大版本**：
   - 先读取 `.skel` 文件头识别版本（例如 `4.0.63` ➔ 主版本 `4.0`），安装对应 `@esotericsoftware/spine-player@~4.0.0`（如 `4.0.31`）。
   - 禁止用 `^4.0.0`（会装到 `4.3.x`，无法解析 `4.0` 的二进制 `.skel`）。
3. **透明通道（PMA）对齐**：
   - 检查 `.atlas` 中的 `pma:true` / `pma:false`，将 `premultipliedAlpha` 与其保持一致，避免黑边或发灰。

---

## 标准执行流程

### 第一步：准备 Spine 三件套（`.skel` + `.atlas` + `.png`）

- **情况 A（已有目录）**：直接使用包含 `.skel`、`.atlas`、`.png` 的目录。
- **情况 B（需从 XAPK 解包提取）**：使用 `danke-resource/.venv` 运行 `scripts/extract_spine_from_xapk.py`：
  ```bash
  /home/guagua/workspace/project/danke/danke-resource/.venv/bin/python3 \
    /home/guagua/workspace/skills/skills/danke-spine-renderer/scripts/extract_spine_from_xapk.py \
    --query ui3d_guguji02 \
    --out-dir /home/guagua/workspace/project/danke/danke-resource/extracted/spet_skins
  ```
  脚本会自动检索 `com.dxx.firenow.apk` 中的 `globalgamemanagers` `ResourceManager`，BFS 追踪 `UnityDataAssetPack.apk` 中的 `externals`，并无损导出 `Texture2D (.png)` 与原始二进制 `TextAsset (.skel/.atlas)`。

### 第二步：无头浏览器 WebGL 自动拼装与裁边渲染

使用工作区 `.venv` 运行 `scripts/render_spine.py`：
```bash
/home/guagua/workspace/.venv/bin/python3 \
  /home/guagua/workspace/skills/skills/danke-spine-renderer/scripts/render_spine.py \
  --input-dir /home/guagua/workspace/project/danke/danke-resource/extracted/spet_skins/ui3d_guguji02 \
  --output /tmp/sheriff-clucker.png \
  --size 512
```

脚本会自动完成：
1. 读取 `.skel` 版本号与 `.atlas` 的 `pma` 标记；
2. 在 `/tmp/spine_render_<major_minor>` 按需缓存对应版本的 `@esotericsoftware/spine-player`；
3. 启动本地静态 HTTP 服务 + Playwright 无头 Chromium（SwiftShader WebGL，`alpha: true`、`backgroundColor: "#00000000"`、`preserveDrawingBuffer: true`）；
4. 自动优先选择 `Idle` / `Stand` / `Wait` 等待机动画并等待稳定帧；
5. 使用 `omit_background=True` 截图，并通过 Pillow `getbbox()` 自动裁去四周透明留白、居中填充约 12% 边距为正方形高清 PNG。

### 第三步：视觉验收与导入 `danke-assets`（如适用）

1. 用 `read_file` 直接查看生成的 PNG，确认角色完整、无缺件、无黑边、动作自然。
2. 若需入库 `danke-assets`：
   - 缩放为规范尺寸（如 `256×256`）并同时生成 `.png` 与 `.webp`（`quality=90, method=6`），存入 `danke-assets/public/game-assets/<category>/<slug>.{png,webp}`；
   - 更新 `danke-assets/public/manifest.json`（含 `total_assets`）与 `catalog.json`；
   - 通过 `curl` 验证 `http://localhost:6104/game-assets/<category>/<slug>.png` 返回 `HTTP 200`。
