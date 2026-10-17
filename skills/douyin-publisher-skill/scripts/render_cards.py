#!/usr/bin/env python3
"""Render reviewed HTML into local Douyin cards. No login or upload operations."""
import argparse
import hashlib
import html
import json
import math
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

from bs4 import BeautifulSoup
from PIL import Image
from playwright.sync_api import sync_playwright

SKILL = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def default_output(source):
    parent = source.parent
    dist = next((p for p in [parent, *parent.parents] if p.name == 'dist'), parent / 'dist')
    return dist / '抖音图文_3x4'


def render(source, output=None, sources=(), strategy=None):
    source = Path(source).resolve()
    output = Path(output).resolve() if output else default_output(source)
    if source == output / 'index.html':
        raise ValueError('请保留独立卡片源文件，不要以渲染结果覆盖源文件')
    output.mkdir(parents=True, exist_ok=True)
    # Immediately invalidate a previous manifest, including on an early macro error.
    manifest = {'profile': 'douyin', 'style': 'danke-hybrid', 'includes_cover': False,
                'images': [], 'validation': {'passed': False}}
    dump(output / 'manifest.json', manifest)
    dump(output / 'validation.json', {'passed': False, 'errors': ['本轮生成尚未完成，请查看命令输出。']})
    tracked = {str(p.resolve()): digest(p) for p in [source, Path(__file__),
               SKILL / 'assets/cards.css', SKILL / 'assets/paginate.js', *map(Path, sources)]}
    strategy = Path(strategy).resolve() if strategy else SKILL.parent / 'danke-strategy-skill'
    pack = strategy / 'packs/danke'
    sys.path.insert(0, str(strategy))
    from engine.compiler import ImageResolver
    mapping = pack / 'image_mapping.json'
    short_mapping = pack / 'image_mapping_short.json'
    for p in [mapping, short_mapping]:
        tracked[str(p)] = digest(p)
    resolver = ImageResolver({'assets_dir': str(pack / 'assets'), 'image_mapping_path': str(mapping),
                             'local_image_mapping_path': str(mapping),
                             'short_image_mapping_path': str(short_mapping)}, output_dir=str(output))
    assets = output / 'assets'
    assets.mkdir(exist_ok=True)
    asset_records = []

    def portable(src, base):
        parsed = urlparse(src)
        if parsed.scheme in ('http', 'https'):
            with urlopen(src, timeout=25) as response:
                payload = response.read()
            suffix = Path(parsed.path).suffix.lower() or '.png'
            if suffix not in {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'}:
                suffix = '.png'
            sha = hashlib.sha256(payload).hexdigest()
            destination = assets / f'item-{sha[:16]}{suffix}'
            destination.write_bytes(payload)
            origin = src
        else:
            local = Path(unquote(parsed.path)) if parsed.scheme == 'file' else Path(src)
            local = local if local.is_absolute() else base / local
            local = local.resolve()
            if not local.is_file():
                raise ValueError(f'素材文件不存在: {local}')
            sha = digest(local)
            destination = assets / f'item-{sha[:16]}{local.suffix.lower()}'
            if local != destination:
                shutil.copy2(local, destination)
            tracked[str(local)] = sha
            origin = str(local)
        return destination.relative_to(output).as_posix(), origin, sha

    def resolve_macro(match):
        name = html.unescape(match.group(1).strip())
        if name not in resolver.short_image_mapping and name not in resolver.local_image_mapping:
            raise ValueError(f'未知图片宏: {name}；请查映射，或改为注明原因的纯文字道具')
        relative = resolver.resolve_image_src('img://' + name, allow_placeholder=False)
        if not relative:
            raise ValueError(f'图片宏缺少素材: {name}')
        asset, origin, sha = portable(relative, output)
        full_name = resolver.short_image_mapping.get(name, name)
        asset_records.append({'macro': name, 'full_name': full_name, 'source': origin, 'asset': asset, 'sha256': sha})
        return f'<img class="item-icon inline" data-macro="{html.escape(name)}" data-render-resolved="true" src="{asset}" alt="{html.escape(full_name)}">'

    soup = BeautifulSoup(re.sub(r'\{\{([^{}]+)\}\}', resolve_macro, source.read_text(encoding='utf-8')), 'html.parser')
    if not soup.head or not soup.select('main.gallery > section.card'):
        raise ValueError('输入需要完整HTML及main.gallery > section.card；请从技能模板开始')
    if soup.select('script'):
        raise ValueError('卡片源文件不应包含脚本')
    missing = []
    for row in soup.select('.reward-line,.exchange-row'):
        if not row.select_one('.item-name'):
            raise ValueError('奖励或兑换条目缺少.item-name')
        if not row.select_one('img'):
            if not row.get('data-missing-reason'):
                raise ValueError('无图道具需要data-missing-reason说明，不能悄悄丢图')
            row['class'] = list(dict.fromkeys(row.get('class', []) + ['text-only']))
    for row in soup.select('.text-only[data-missing-reason]'):
        name = row.select_one('.item-name')
        missing.append({'name': name.get_text(strip=True) if name else row.get_text(' ', strip=True),
                        'reason': row['data-missing-reason']})
    for img in soup.select('img'):
        if not img.get('src'):
            raise ValueError('发现空图片src')
        if img['src'].startswith('img://'):
            # Reuse the exact macro path without fuzzy lookup.
            name = img['src'][6:]
            resolved = BeautifulSoup(re.sub(r'\{\{([^{}]+)\}\}', resolve_macro, '{{' + name + '}}'), 'html.parser').img
            img['src'] = resolved['src']
            img['data-macro'] = name
            img['alt'] = img.get('alt') or resolved['alt']
        elif not img.has_attr('data-render-resolved'):
            asset, origin, sha = portable(img['src'], source.parent)
            asset_records.append({'source': origin, 'asset': asset, 'sha256': sha})
            img['src'] = asset
        img.attrs.pop('data-render-resolved', None)
        if img.find_parent(class_='reward-line') or img.find_parent(class_='exchange-row'):
            img['class'] = ['item-icon']
    css = assets / 'cards.css'
    shutil.copy2(SKILL / 'assets/cards.css', css)
    link = soup.new_tag('link', rel='stylesheet', href='assets/cards.css')
    soup.head.append(link)
    cards = soup.select('section.card')
    for card in cards:
        if not card.select_one(':scope > .body > .brand'):
            raise ValueError('每页必须包含直接的.body容器和.brand页脚')
    cover_positions = [i for i, c in enumerate(cards) if c.get('data-kind') == 'cover']
    if cover_positions not in ([], [0]):
        raise ValueError('封面必须是首张且只出现一次，使用data-kind="cover"')
    manifest['includes_cover'] = bool(cover_positions)
    expected_names = [n.get_text() for n in soup.select('.item-name')]
    expected_cells = [n.get_text() for n in soup.select('tbody td')]
    for table in soup.select('table'):
        if len(table.select('thead th')) > 3:
            raise ValueError('表格最多三列，请拆成多页')
        headers = [th.get_text() for th in table.select('thead th')]
        for row in table.select('tbody tr'):
            for index, cell in enumerate(row.select('td')):
                if index < len(headers) and re.search('钻|钻石', headers[index]) and not re.fullmatch(r'\d+(?:\.\d+)?', cell.get_text(strip=True)):
                    raise ValueError('钻石单位只放表头，单元格仅写数字')
    (output / 'index.html').write_text(str(soup), encoding='utf-8')
    dump(output / 'asset-manifest.json', {'assets': asset_records, 'text_only': missing})
    errors, bounds, images = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 1000}, device_scale_factor=2)
        page.goto((output / 'index.html').as_uri(), wait_until='networkidle')
        page.evaluate('document.fonts.ready')
        bad = page.evaluate('()=>Array.from(document.images).filter(i=>!i.complete||!i.naturalWidth).map(i=>i.src)')
        errors.extend(bad)
        pagination = page.evaluate((SKILL / 'assets/paginate.js').read_text())
        errors.extend(pagination['errors'])
        names_preserved = page.locator('.item-name').all_text_contents() == expected_names
        cells_preserved = page.locator('tbody td').all_text_contents() == expected_cells
        if not names_preserved:
            errors.append('分页未能保留全部道具名称与顺序，请调整源文件')
        if not cells_preserved:
            errors.append('分页未能保留全部表格内容与顺序，请调整源文件')
        # Save the paginated DOM so preview and rendered cards use the same content.
        (output / 'index.html').write_text(page.content(), encoding='utf-8')
        for i, card in enumerate(page.locator('section.card').all(), 1):
            result = card.evaluate('''el=>{
              const b=el.getBoundingClientRect(),body=el.querySelector('.body'),footer=el.querySelector('.brand');
              const limit=el.querySelector('.footer-note')||footer;
              const collisions=Array.from(body.children).filter(n=>!n.matches('.brand,.footer-note')).filter(n=>n.getBoundingClientRect().bottom>limit.getBoundingClientRect().top-6).map(n=>n.tagName);
              const outside=Array.from(el.querySelectorAll('*')).filter(n=>{const r=n.getBoundingClientRect();return r.width>0&&(r.right>b.right+1||r.left<b.left-1||r.bottom>b.bottom+1||n.scrollWidth>n.clientWidth+1)}).map(n=>n.tagName);
              return {width:b.width,height:b.height,collisions,outside};
            }''')
            bounds.append({'page': i, **result})
            if result['collisions'] or result['outside'] or result['width'] != 600 or result['height'] != 800:
                errors.append({'page': i, **result})
            name = f'{i:02d}_卡片.png'
            card.screenshot(path=str(output / name))
            images.append(name)
        browser.close()
    for width in [360, 390]:
        body = ''.join(f'<img src="{name}" alt="第{i}页">' for i, name in enumerate(images, 1))
        preview = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>攻略手机预览</title><style>body{{margin:0;background:#25243b}}main{{width:min(100%,{width}px);margin:auto}}img{{display:block;width:100%;height:auto;margin:0 0 22px}}</style><main>{body}</main></html>'''
        (output / f'preview_{width}.html').write_text(preview, encoding='utf-8')
    shutil.copy2(output / 'preview_390.html', output / 'preview.html')
    cols = min(3, len(images))
    sheet = Image.new('RGB', (cols * 406 + 16, math.ceil(len(images) / cols) * 536 + 16), '#25243b')
    for i, name in enumerate(images):
        with Image.open(output / name) as im:
            sheet.paste(im.convert('RGB').resize((390, 520), Image.Resampling.LANCZOS), (16 + (i % cols) * 406, 16 + (i // cols) * 536))
    sheet.save(output / 'contact-sheet.jpg', quality=94)
    validation = {'passed': not errors, 'errors': errors, 'cards': bounds, 'pagination': pagination,
                  'names_and_tables_preserved': names_preserved and cells_preserved}
    dump(output / 'validation.json', validation)
    manifest.update({'images': images, 'image_sha256': {name: digest(output / name) for name in images},
                     'input_sha256': tracked, 'validation': {'passed': not errors}})
    dump(output / 'manifest.json', manifest)
    if errors:
        raise ValueError('卡片验证未通过，请查看validation.json；不能上传')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', help='按技能模板整理的卡片HTML')
    parser.add_argument('--output-dir', help='默认文章dist/抖音图文_3x4')
    parser.add_argument('--source', action='append', default=[], help='核对过的文章/数据来源，可重复；记录哈希')
    parser.add_argument('--strategy-skill', help='覆盖同级danke-strategy-skill位置')
    args = parser.parse_args(argv)
    try:
        manifest = render(args.html, args.output_dir, args.source, args.strategy_skill)
    except (ValueError, OSError, AssertionError) as exc:
        parser.exit(1, f'生成失败: {exc}\n')
    print(f'已生成{len(manifest["images"])}张1200×1600卡片；仅本地生成。')


if __name__ == '__main__':
    main()
