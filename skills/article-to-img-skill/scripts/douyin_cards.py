#!/usr/bin/env python3
"""Warm-paper, fixed-type Douyin cards. Editorial outline + compiled image catalog.

No source rewriting or automatic summarization: the outline records the editorial
choices, while real browser measurements decide continuation pages.
"""
import copy
import hashlib
import html
import json
import math
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

CSS_PATH = Path(__file__).resolve().parents[1] / "assets" / "douyin.css"
MACRO = re.compile(r"\{\{([^{}]+)\}\}")
KINDS = {"text", "note", "metric", "list", "table", "image"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} 必须为非空字符串")
    return value


def load_outline(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("pages"), list) or not data["pages"]:
        raise ValueError("提纲需要 version: 1 和非空 pages 列表")
    for page in data["pages"]:
        nonempty(page.get("title"), "page.title")
        if not isinstance(page.get("blocks"), list) or not page["blocks"]:
            raise ValueError("每页需要非空 blocks")
        for block in page["blocks"]:
            kind = block.get("type")
            if kind not in KINDS:
                raise ValueError(f"不支持的 block.type: {kind}")
            if kind in {"text", "note"}:
                nonempty(block.get("text"), f"{kind}.text")
            elif kind == "metric":
                nonempty(block.get("value"), "metric.value")
            elif kind == "list":
                if not isinstance(block.get("items"), list) or not block["items"]:
                    raise ValueError("list.items 不能为空")
                for item in block["items"]:
                    nonempty(item if isinstance(item, str) else item.get("text"), "list.item")
            elif kind == "table":
                headers, rows = block.get("headers"), block.get("rows")
                if not isinstance(headers, list) or len(headers) < 2 or not rows:
                    raise ValueError("table 需要至少两列及非空 rows")
                for heading in headers:
                    nonempty(heading, "table.header")
                if any(not isinstance(row, list) or len(row) != len(headers) for row in rows):
                    raise ValueError("table 每行列数必须与 headers 一致")
            else:
                nonempty(block.get("src"), "image.src")
                height = block.get("height", 460)
                if type(height) is not int or not 80 <= height <= 700:
                    raise ValueError("image.height 必须为 80–700 的整数")
    return data


def normalize_table(block):
    """Move diamond units to headings; keep explicit mixed/annotated cells intact."""
    result = copy.deepcopy(block)
    for col, header in enumerate(result["headers"]):
        if "钻" not in header:
            continue
        if "（钻石）" not in header:
            result["headers"][col] = re.sub(r"[（(]?钻石?[）)]?", "", header).strip() + "（钻石）"
        for row in result["rows"]:
            cell = str(row[col]).strip()
            match = re.fullmatch(r"([\d,]+)\s*(?:钻石?|\{\{钻石\}\})?", cell)
            if match:
                row[col] = match.group(1)
    return result


def expand_blocks(blocks):
    """Lists paginate between items; wide tables repeat the key column."""
    expanded = []
    for raw in blocks:
        block = copy.deepcopy(raw)
        if block["type"] == "list":
            for index, raw_item in enumerate(block["items"], 1):
                item = {"text": raw_item} if isinstance(raw_item, str) else dict(raw_item)
                expanded.append({"type": "item", **item,
                                 "rank": str(index).zfill(2) if block.get("ordered") else "",
                                 "label": block.get("label", "") if index == 1 else ""})
        elif block["type"] == "table":
            block = normalize_table(block)
            for start in range(1, len(block["headers"]), 2):
                indices = [0] + list(range(start, min(start + 2, len(block["headers"]))))
                expanded.append({**block, "headers": [block["headers"][i] for i in indices],
                                 "rows": [[row[i] for i in indices] for row in block["rows"]]})
        else:
            expanded.append(block)
    return expanded


def absolute_src(src, directory):
    parsed = urlparse(src)
    if parsed.scheme in {"https", "http", "data"}:
        return src
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError(f"不支持的图片地址: {src}")
    local = Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(unquote(src))
    if not local.is_absolute():
        local = directory / local
    if not local.is_file():
        raise ValueError(f"图片不存在: {local}")
    return local.resolve().as_uri()


def image_catalog(source):
    catalog = {}
    for image in BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser").find_all("img"):
        name = image.get("alt", "").strip()
        src = image.get("src") or image.get("data-src")
        # WeChat-only banner/recommendations are intentionally not copied to cards.
        if name and src and name not in {"article-top", "弹壳呱呱微信公众号二维码"}:
            resolved = absolute_src(src, source.parent)
            if name in catalog and catalog[name] != resolved:
                raise ValueError(f"编译 HTML 中同名图片不唯一: {name}")
            catalog[name] = resolved
    return catalog


class CardRenderer:
    def __init__(self, catalog, outline_dir):
        self.catalog = dict(catalog)
        self.outline_dir = outline_dir
        self.used_images = {}
        mapping = Path(__file__).resolve().parents[2] / "danke-strategy-skill/packs/danke/image_mapping_short.json"
        self.aliases = json.loads(mapping.read_text(encoding="utf-8")) if mapping.is_file() else {}
        # Compiled alt may retain either the short macro or the old full macro.
        for short, full in self.aliases.items():
            if short in self.catalog:
                self.catalog.setdefault(full, self.catalog[short])

    def icon(self, name):
        target = name if name in self.catalog else self.aliases.get(name, name)
        if target not in self.catalog:
            raise ValueError("提纲图标 {{" + name + "}} 未出现在本次编译 HTML；请先在正文登记并编译，不能猜图")
        src = self.catalog[target]
        self.used_images[name] = src
        return f'<img class="icon" alt="{html.escape(name, quote=True)}" src="{html.escape(src, quote=True)}">'

    def inline(self, value):
        value = str(value)
        parts, start = [], 0
        for match in MACRO.finditer(value):
            parts.extend([html.escape(value[start:match.start()]), self.icon(match.group(1))])
            start = match.end()
        parts.append(html.escape(value[start:]))
        return "".join(parts).replace("\n", "<br>")

    def block(self, block):
        kind = block["type"]
        label = f'<div class="label">{self.inline(block["label"])}</div>' if block.get("label") else ""
        if kind in {"text", "note"}:
            return f'<div class="block {kind}">{self.inline(block["text"])}</div>'
        if kind == "metric":
            detail = f'<div class="metric-detail">{self.inline(block["detail"])}</div>' if block.get("detail") else ""
            return f'<div class="block metric">{label}<div class="metric-value">{self.inline(block["value"])}</div>{detail}</div>'
        if kind == "item":
            rank = f'<span class="rank">{block["rank"]}</span>' if block.get("rank") else ""
            icon = self.icon(block["icon"]) if block.get("icon") else ""
            return f'<div class="block item">{label}<div class="item-line">{rank}{icon}<div class="item-text">{self.inline(block["text"])}</div></div></div>'
        if kind == "table":
            header = "".join(f"<th>{self.inline(cell)}</th>" for cell in block["headers"])
            rows = "".join("<tr>" + "".join(f"<td>{self.inline(cell)}</td>" for cell in row) + "</tr>" for row in block["rows"])
            return f'<div class="block table">{label}<table><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div>'
        if kind == "image":
            src = absolute_src(block["src"], self.outline_dir)
            self.used_images[block.get("alt", block["src"])] = src
            fit = block.get("fit", "contain")
            position = block.get("position", "50% 50%")
            if fit not in {"cover", "contain"} or not re.fullmatch(r"[\d.]+% [\d.]+%", position):
                raise ValueError("image.fit 只能为 cover/contain；position 使用两个百分比")
            return f'<div class="block"><img class="figure" style="height:{block.get("height", 460)}px;object-fit:{fit};object-position:{position}" src="{html.escape(src, quote=True)}" alt="{html.escape(block.get("alt", "活动配图"), quote=True)}"></div>'
        raise ValueError(f"未知块类型: {kind}")


FIT_JS = """() => {
 const box = document.querySelector('.content'), rect = box.getBoundingClientRect();
 return box.scrollHeight <= box.clientHeight + 1 && [...box.querySelectorAll('*')].every(e => {
   const r = e.getBoundingClientRect();
   return r.right <= rect.right + 1 && r.left >= rect.left - 1 &&
     r.bottom <= rect.bottom + 1 && e.scrollWidth <= e.clientWidth + 1;
 });
}"""


def document_html(title, kicker, blocks, renderer, author="弹壳呱呱", page_number=""):
    title_markup = re.sub(r"\d{2,}", lambda m: '<span class="key-number">' + m.group() + '</span>', html.escape(title))
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="referrer" content="no-referrer"><style>' + CSS_PATH.read_text(encoding="utf-8") + '</style>'
            '<article class="card"><header><div class="kicker">' + html.escape(kicker) + '</div><h1>' +
            title_markup + '</h1></header><main class="content">' +
            ''.join(renderer.block(b) for b in blocks) + '</main><footer class="footer"><span>' +
            html.escape(author) + '</span><span>' + html.escape(page_number) + '</span></footer></article></html>')


def paginate_topic(page, topic, renderer):
    """Fit real DOM at fixed font sizes; split text tokens/table rows, never scale."""
    pending = expand_blocks(topic["blocks"])
    pages, current = [], []

    def set_blocks(blocks):
        page.set_content(document_html(topic["title"], topic.get("kicker", "活动攻略"), [], renderer))
        page.evaluate("s => document.querySelector('.content').innerHTML = s",
                      "".join(renderer.block(b) for b in blocks))

    def fits(blocks):
        set_blocks(blocks)
        return page.evaluate(FIT_JS)

    def flush():
        if not current:
            raise ValueError(f"标题或单个不可拆分内容过高：{topic['title']}。请缩短标题/表格单行或拆分信息，禁止缩小字号。")
        pages.append(current.copy())
        current.clear()

    while pending:
        block = pending.pop(0)
        if fits(current + [block]):
            current.append(block)
            continue
        kind = block["type"]
        # Prefer carrying short text/items intact to avoid tiny fragments.
        if kind in {"text", "note", "item"} and current and fits([block]):
            flush()
            pending.insert(0, block)
            continue
        if kind == "table":
            units = block["rows"]
            make = lambda seq: {**block, "rows": seq}
        elif kind in {"text", "note", "item"}:
            units = re.findall(r"\{\{[^{}]+\}\}|[A-Za-z0-9]+(?:[./]\d+)*|[\s\S]", block["text"])
            make = lambda seq: {**block, "text": "".join(seq)}
        else:
            units = []
        lo, hi = 0, len(units)
        while lo < hi:
            middle = math.ceil((lo + hi) / 2)
            if fits(current + [make(units[:middle])]):
                lo = middle
            else:
                hi = middle - 1
        if lo:
            current.append(make(units[:lo]))
            remainder = make(units[lo:])
            if remainder.get("rank"):
                remainder["rank"] = ""
            pending.insert(0, remainder)
        else:
            pending.insert(0, block)
        flush()
    if current:
        pages.append(current)
    return [{**topic, "blocks": blocks, "continuation": i > 0} for i, blocks in enumerate(pages)]


def inspect_card(page):
    return page.evaluate("""() => {
      const c = document.querySelector('.content'), r = c.getBoundingClientRect();
      const fonts = [...document.querySelectorAll('.block, .label, th, td, .metric-detail, .metric-value, .footer')]
        .map(e => parseFloat(getComputedStyle(e).fontSize));
      return {content_height: c.scrollHeight, available_height: c.clientHeight,
        min_font: Math.min(...fonts), background: getComputedStyle(document.querySelector('.card')).backgroundColor,
        content_used: c.lastElementChild ? Math.round(c.lastElementChild.getBoundingClientRect().bottom - r.top) : 0,
        text: document.querySelector('.card').innerText};
    }""")


def preview_html(images, width):
    figures = ''.join(f'<figure><img src="{html.escape(name, quote=True)}" alt="第 {i} 页"><figcaption>{i} / {len(images)}</figcaption></figure>'
                      for i, name in enumerate(images, 1))
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>抖音大字卡片 · 手机预览</title>
<style>body{{margin:0;background:#D8D3C9;font-family:sans-serif;color:#242424}}header{{padding:18px}}
nav a{{margin-right:20px;color:#79351F}}main{{display:flex;flex-wrap:wrap;gap:24px;padding:0 16px 24px}}
figure{{width:min({width}px,100%);margin:0}}img{{width:100%;display:block}}figcaption{{font-size:14px;padding:8px 0}}</style>
<header><strong>弹壳呱呱 · 暖灰大字版</strong><p>每张按手机显示尺寸预览；点击图片可查看高清原图。</p>
<nav><a href="preview_360.html">360px 预览</a><a href="preview_390.html">390px 预览</a></nav></header>
<main>{figures}</main><script>document.querySelectorAll('img').forEach(i=>i.onclick=()=>window.open(i.src));</script></html>'''


def render_douyin_cards(input_path, outline_path=None, output_dir=None, width=1080, height=1440, dpr=2):
    from export_cards import get_playwright_engine
    if (width, height) != (1080, 1440) or dpr < 1 or dpr > 3:
        raise ValueError("douyin profile 固定 1080×1440 基准画布，DPR 可选 1–3；不能通过缩小画布压缩文字")
    source = Path(input_path).resolve()
    article_dir = source.parent.parent if source.parent.name == "dist" else source.parent
    outline_path = Path(outline_path).resolve() if outline_path else article_dir / "抖音提纲.json"
    if not outline_path.is_file():
        raise ValueError(f"缺少抖音提纲：{outline_path}；请按 references/douyin_cards.md 整理重点卡与补充页")
    outline = load_outline(outline_path)
    if outline.get("source_html_sha256") and outline["source_html_sha256"] != digest(source):
        raise ValueError("提纲对应的编译 HTML 已变化，请先核对并更新提纲与 source_html_sha256")
    output = Path(output_dir).resolve() if output_dir else article_dir / "dist/抖音图文_3x4"
    output.parent.mkdir(parents=True, exist_ok=True)
    renderer = CardRenderer(image_catalog(source), outline_path.parent)
    metadata_path = source.with_suffix('.json')
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
    hashes = {str(source): digest(source), str(outline_path): digest(outline_path)}
    # Stage outputs; a failed page must not leave a partially publishable manifest.
    with tempfile.TemporaryDirectory(prefix=".douyin-render-", dir=output.parent) as temporary:
        stage = Path(temporary)
        with get_playwright_engine()() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=dpr)
                pages = []
                for topic in outline["pages"]:
                    pages.extend(paginate_topic(page, topic, renderer))
                reports, images = [], []
                for index, topic in enumerate(pages, 1):
                    name = f"{index:02d}_卡片.png"
                    kicker = topic.get("kicker", "活动攻略") + (" · 续页" if topic["continuation"] else "")
                    markup = document_html(topic["title"], kicker, topic["blocks"], renderer,
                                           outline.get("author", "弹壳呱呱"), f"{index:02d} / {len(pages):02d}")
                    (stage / f"{index:02d}.html").write_text(markup, encoding="utf-8")
                    page.goto((stage / f"{index:02d}.html").as_uri(), wait_until="load")
                    page.evaluate("() => document.fonts.ready")
                    page.wait_for_function("() => [...document.images].every(i => i.complete)", timeout=20000)
                    broken = page.evaluate("() => [...document.images].filter(i => !i.naturalWidth).map(i => i.src)")
                    if broken:
                        raise ValueError(f"图片未加载，停止输出：{broken}")
                    if not page.evaluate(FIT_JS):
                        raise ValueError(f"第 {index} 页最终布局溢出，停止输出；不能缩小字体")
                    report = inspect_card(page)
                    if report["min_font"] < 36:
                        raise ValueError(f"第 {index} 页字号小于 36px")
                    report.update({"file": name, "title": topic["title"], "continuation": topic["continuation"], "fits": True})
                    reports.append(report)
                    page.locator('.card').screenshot(path=str(stage / name))
                    images.append(name)
                    print(f"✅ {name}  {topic['title'].replace(chr(10), ' / ')}")
                # These screenshots show exactly what the exported cards look like at phone widths.
                for phone_width in (360, 390):
                    phone = browser.new_page(viewport={"width": phone_width, "height": phone_width * 4 // 3}, device_scale_factor=1)
                    # A file origin is needed for Chromium to load local PNGs.
                    phone.goto((stage / '01.html').as_uri(), wait_until="load")
                    phone_dir = stage / "previews" / str(phone_width)
                    phone_dir.mkdir(parents=True)
                    for image_name in images:
                        phone.set_content(f'<style>body{{margin:0}}img{{display:block;width:100%}}</style><img src="{(stage / image_name).as_uri()}">')
                        phone.wait_for_function("() => document.images[0].complete && document.images[0].naturalWidth > 0")
                        phone.screenshot(path=str(phone_dir / image_name))
                    phone.close()
                    (stage / f"preview_{phone_width}.html").write_text(preview_html(images, phone_width), encoding="utf-8")
            finally:
                browser.close()
        for path, sha in hashes.items():
            if digest(path) != sha:
                raise ValueError(f"渲染过程中输入被修改，停止输出：{path}")
        manifest = {"version": 1, "profile": "douyin", "includes_cover": outline.get("includes_cover", False),
                    "images": images, "source_html": str(source), "outline": str(outline_path),
                    "image_sha256": {name: digest(stage / name) for name in images},
                    "input_sha256": hashes, "used_images": renderer.used_images,
                    "canvas": [width, height], "dpr": dpr, "validation": {"passed": True, "cards": reports}}
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        (stage / "分页文案.json").write_text(json.dumps({"version": 1, "pages": pages}, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = [f"第 {i} 页｜{report['title']}\n{report['text']}\n" for i, report in enumerate(reports, 1)]
        (stage / "分页文案.txt").write_text("\n".join(lines), encoding="utf-8")
        tags = ' '.join('#' + t for t in metadata.get('tags', []))
        caption = f"{metadata.get('social_title', metadata.get('title', '活动攻略'))}\n\n{metadata.get('summary', '')}\n\n{tags}\n"
        (stage / "copywriting.txt").write_text(caption, encoding="utf-8")
        (stage / "preview.html").write_text(preview_html(images, 360), encoding="utf-8")
        # Only remove old, explicitly owned card files, never arbitrary images.
        previous = output / "manifest.json"
        old_images = json.loads(previous.read_text(encoding="utf-8")).get("images", []) if previous.is_file() else []
        output.mkdir(parents=True, exist_ok=True)
        for name in old_images:
            if re.fullmatch(r"\d+_卡片\.png", name) and name not in images:
                (output / name).unlink(missing_ok=True)
                (output / (Path(name).stem.split('_')[0] + '.html')).unlink(missing_ok=True)
        for item in stage.iterdir():
            if item.name != 'manifest.json':
                if item.is_dir():
                    shutil.copytree(item, output / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, output / item.name)
        shutil.copy2(stage / 'manifest.json', output / 'manifest.json')
    print(f"完成 {len(images)} 页。手机预览：{output / 'preview.html'}")
    return [str(output / name) for name in images], str(output)
