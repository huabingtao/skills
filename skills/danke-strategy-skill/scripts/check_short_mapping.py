#!/usr/bin/env python3
"""Check short aliases and optionally export a full-name / macro / image preview."""

import argparse
import hashlib
import html
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.short_mapping import inspect_short_mapping, read_short_mapping


def check_pack(pack):
    local = json.loads((pack / "image_mapping.json").read_text(encoding="utf-8"))
    shorts = read_short_mapping(pack / "image_mapping_short.json")
    report = inspect_short_mapping(shorts, local, pack, require_coverage=True)
    hashes = defaultdict(list)
    for entry in report["entries"]:
        hashes[hashlib.sha256(Path(entry["absolute_path"]).read_bytes()).hexdigest()].append(
            {"short": entry["short"], "full_name": entry["full_name"], "path": entry["path"]})
    report["identical_bytes_kept_separate"] = [v for v in hashes.values() if len(v) > 1]
    return report


def preview_html(report):
    rows = []
    for entry in report["entries"]:
        full, short = html.escape(entry["full_name"]), html.escape(entry["short"])
        src = html.escape(Path(entry["absolute_path"]).as_uri(), quote=True)
        rows.append(f'<tr><td>{full}</td><td><code>{{{{{short}}}}}</code></td>'
                    f'<td><img src="{src}" alt="{full}"></td></tr>')
    missing = "".join(f'<li>{html.escape(x["path"])}</li>' for x in report["missing_legacy_assets"])
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>图片 short 宏对照</title>
<style>body{font:16px/1.6 system-ui,sans-serif;max-width:1000px;margin:32px auto;padding:0 18px;color:#172033}
table{width:100%;border-collapse:collapse}th,td{padding:10px 14px;border-bottom:1px solid #e2e8f0;text-align:left}
thead{background:#f1f5f9}img{width:56px;height:56px;object-fit:contain}code{font-size:15px;color:#1755a1}
input{box-sizing:border-box;width:100%;padding:12px;font:inherit;margin:16px 0}p,summary{color:#526174}
</style><h1>图片 short 宏对照</h1>''' + (
        f'<p>{report["legacy_name_count"]} 个旧名称，{report["short_count"]} 个推荐 short。旧宏继续兼容；正文名称不变。</p>'
        '<input id="search" aria-label="搜索完整名称或short" placeholder="搜索完整名称或 short…">'
        '<table><thead><tr><th>现有完整名称</th><th>推荐宏</th><th>图片</th></tr></thead><tbody>'
        + "".join(rows) + '</tbody></table>'
        f'<details><summary>{len(report["missing_legacy_assets"])} 个失效路径，未生成 short</summary><ul>{missing}</ul></details>'
        '<script>document.querySelector("#search").addEventListener("input",e=>{'
        'let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>'
        'r.hidden=!r.textContent.toLowerCase().includes(q))})</script></html>')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=ROOT / "packs/danke")
    parser.add_argument("--output-dir", type=Path, help="可选：保存 report.json 与 preview.html，不修改旧映射或图片")
    args = parser.parse_args(argv)
    try:
        report = check_pack(args.pack.resolve())
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (args.output_dir / "preview.html").write_text(preview_html(report), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("entries", "identical_bytes_kept_separate")}, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
