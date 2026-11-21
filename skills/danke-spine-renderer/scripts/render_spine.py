#!/usr/bin/env python3
"""Render a Spine (.skel + .atlas + .png) asset to a cropped transparent PNG via headless Chrome WebGL."""

import argparse
import glob
import http.server
import os
import re
import shutil
import socketserver
import subprocess
import threading
from PIL import Image
from playwright.sync_api import sync_playwright


def detect_skel_version(skel_path: str) -> str:
    data = open(skel_path, "rb").read(64)
    m = re.search(rb"(\d+\.\d+)\.\d+", data)
    if m:
        return m.group(1).decode("ascii")
    return "4.0"


def detect_pma(atlas_path: str) -> bool:
    txt = open(atlas_path, "r", encoding="utf-8", errors="ignore").read(512)
    m = re.search(r"pma\s*:\s*(true|false)", txt, re.I)
    return m.group(1).lower() == "true" if m else True


def ensure_spine_player(major_minor: str) -> str:
    cache_dir = f"/tmp/spine_render_{major_minor.replace('.', '_')}"
    js_path = os.path.join(
        cache_dir, "node_modules", "@esotericsoftware", "spine-player", "dist", "iife", "spine-player.min.js"
    )
    if os.path.exists(js_path):
        return cache_dir
    os.makedirs(cache_dir, exist_ok=True)
    subprocess.run(["npm", "init", "-y"], cwd=cache_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(
        ["npm", "install", "--no-save", f"@esotericsoftware/spine-player@~{major_minor}.0"],
        cwd=cache_dir,
        check=True,
    )
    return cache_dir


def find_file(input_dir: str, ext: str, explicit: str | None) -> str:
    if explicit:
        return explicit if os.path.isabs(explicit) else os.path.join(input_dir, explicit)
    matches = sorted(glob.glob(os.path.join(input_dir, f"*{ext}")))
    if not matches:
        raise FileNotFoundError(f"No {ext} file found in {input_dir}")
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description="Render Spine skeleton to transparent PNG")
    parser.add_argument("--input-dir", required=True, help="Directory containing .skel, .atlas, .png")
    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument("--skel", help="Optional .skel filename or path")
    parser.add_argument("--atlas", help="Optional .atlas filename or path")
    parser.add_argument("--anim", help="Preferred animation name (defaults to Idle/Stand/first)")
    parser.add_argument("--size", type=int, default=512, help="Max output square size in pixels (default: 512)")
    args = parser.parse_args()

    skel_path = find_file(args.input_dir, ".skel", args.skel)
    atlas_path = find_file(args.input_dir, ".atlas", args.atlas)
    ver = detect_skel_version(skel_path)
    pma = detect_pma(atlas_path)
    print(f"[spine] detected version={ver}.x, pma={pma}")

    runtime_dir = ensure_spine_player(ver)
    work_dir = os.path.join(runtime_dir, "_current_asset")
    if os.path.islink(work_dir) or os.path.exists(work_dir):
        if os.path.islink(work_dir):
            os.unlink(work_dir)
        else:
            shutil.rmtree(work_dir)
    os.symlink(os.path.abspath(args.input_dir), work_dir)

    skel_name = os.path.basename(skel_path)
    atlas_name = os.path.basename(atlas_path)
    anim_pref = args.anim or ""

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{ margin: 0; padding: 0; background: transparent; overflow: hidden; }}
  #player {{ width: 600px; height: 600px; background: transparent; }}
</style>
<script src="/node_modules/@esotericsoftware/spine-player/dist/iife/spine-player.min.js"></script>
</head>
<body>
<div id="player"></div>
<script>
window.__done = false;
window.__err = null;
window.__anims = [];
const preferredAnim = {anim_pref!r};

new spine.SpinePlayer("player", {{
  skelUrl: "/_current_asset/{skel_name}",
  atlasUrl: "/_current_asset/{atlas_name}",
  alpha: true,
  backgroundColor: "#00000000",
  premultipliedAlpha: {"true" if pma else "false"},
  showControls: false,
  preserveDrawingBuffer: true,
  success: (player) => {{
    try {{
      const anims = player.skeleton.data.animations.map(a => a.name);
      window.__anims = anims;
      let target = preferredAnim && anims.includes(preferredAnim)
        ? preferredAnim
        : anims.find(n => /^(idle|stand|wait|daiji)$/i.test(n)) || anims.find(n => /idle|stand|wait/i.test(n)) || anims[0];
      if (target) player.setAnimation(target, true);
      setTimeout(() => {{ window.__done = true; }}, 350);
    }} catch (e) {{
      window.__err = String(e);
      window.__done = true;
    }}
  }},
  error: (player, reason) => {{
    window.__err = reason;
    window.__done = true;
  }}
}});
</script>
</body>
</html>
"""
    viewer_path = os.path.join(runtime_dir, "viewer.html")
    with open(viewer_path, "w", encoding="utf-8") as f:
        f.write(html)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=runtime_dir, **kw)
        def log_message(self, fmt, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), QuietHandler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    raw_tmp = os.path.join(runtime_dir, "_raw_capture.png")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-webgl"],
            )
            page = browser.new_page(viewport={"width": 640, "height": 640}, device_scale_factor=2)
            page.goto(f"http://127.0.0.1:{port}/viewer.html")
            page.wait_for_function("() => window.__done === true", timeout=20000)
            err = page.evaluate("() => window.__err")
            anims = page.evaluate("() => window.__anims")
            if err:
                raise RuntimeError(f"SpinePlayer error: {err}")
            page.locator("#player").screenshot(path=raw_tmp, omit_background=True)
            browser.close()
    finally:
        httpd.shutdown()

    im = Image.open(raw_tmp).convert("RGBA")
    bbox = im.getbbox()
    if not bbox:
        raise RuntimeError("Rendered image is completely transparent")
    cropped = im.crop(bbox)
    w, h = cropped.size
    side = int(max(w, h) * 1.12)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - w) // 2, (side - h) // 2), cropped)
    if side > args.size:
        canvas = canvas.resize((args.size, args.size), Image.Resampling.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    canvas.save(args.output)
    print(f"[spine] anims={anims}, saved={args.output} ({canvas.size[0]}x{canvas.size[1]})")


if __name__ == "__main__":
    main()
