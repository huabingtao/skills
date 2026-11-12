#!/usr/bin/env python3
"""Build local Danke deployment artifacts. Never connects to a server or approves content."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tarfile
import time
from urllib.parse import unquote, urlsplit

TABLES = ['Item', 'ItemCategory', 'ItemCategoryLink', 'ResourceType', 'Source', 'MonthlyYield', 'Agent', 'WikiEntry', 'ProgressionMatrix']
CODE = ['package.json', 'package-lock.json', 'tsconfig.json', 'tsconfig.build.json', 'nest-cli.json', 'prisma.config.ts', 'src', 'prisma']

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

def inventory(core):
    db = sqlite3.connect((core / 'data/danke.db').as_uri() + '?mode=ro', uri=True)
    db.execute('BEGIN')  # Keep all table and image reads on one SQLite snapshot.
    counts, urls = {}, set()
    try:
        for t in TABLES:
            rows = db.execute(f'SELECT * FROM "{t}"').fetchall()
            counts[t] = len(rows)
            for row in rows:
                for value in row:
                    if isinstance(value, str):
                        urls.update(re.findall(r'/uploads/[^\s"<>]+', value))
        config = (core / 'src/item-classifications/resource-views.ts').read_text()
        names = set(re.findall(r"icon\('([^']+)'\)", config))
        if not names: raise ValueError('No static category icons discovered; inspect resource-views.ts')
        urls.update('/uploads/item-icons/categories/' + n + '.png' for n in names)
        assets = []
        root = (core / 'public/uploads').resolve()
        for url in sorted(urls):
            relative = unquote(urlsplit(url).path.removeprefix('/uploads/'))
            p = root / relative
            if not p.resolve().is_relative_to(root) or not p.is_file(): raise ValueError('Missing/unsafe image: ' + url)
            assets.append({'url': url, 'relative': relative, 'sha256': digest(p)})
        return db, counts, assets
    except Exception:
        db.close()
        raise

def archive(target, entries):
    with tarfile.open(target, 'w:gz') as tar:
        def public_file(info):
            parts = Path(info.name).parts
            if info.issym() or info.islnk(): raise ValueError('Symlink in archive input: ' + info.name)
            if any(p.startswith('.env') or p in {'node_modules', 'id_rsa', 'id_ed25519'} for p in parts): return None
            if info.name == 'prisma/seed.ts': return None
            if info.name.endswith(('.pem', '.key')): return None
            return info
        for source, name in entries: tar.add(source, arcname=name, filter=public_file)

def main():
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'bundle', 'web-bundle'])
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument('--content-package', type=Path)
    parser.add_argument('--web-out', type=Path)
    parser.add_argument('--base-release', type=Path, help='Optional prior content package for incremental asset diff in web-bundle')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    core, creator = workspace / 'project/danke/danke-core', workspace / 'project/danke/danke-creator'
    output = args.output or creator / 'dist/deploy' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = output.resolve()
    if not output.is_relative_to((creator / 'dist').resolve()): raise ValueError('Output must be inside Creator dist')
    if output.exists(): raise ValueError('Output already exists; use a unique release directory')
    if args.command == 'web-bundle':
        latest_file = creator / 'dist/releases/latest.json'
        pkg_arg = args.content_package
        if not pkg_arg and latest_file.is_file():
            pkg_arg = Path(json.loads(latest_file.read_text())['package'])
        web_arg = args.web_out or (workspace / 'project/danke/danke-web/out')
        if not pkg_arg or not web_arg.is_dir():
            raise ValueError('web-bundle requires a finalized content package and built danke-web/out')
        package, web = pkg_arg.resolve(), web_arg.resolve()
        sys.path.insert(0, str(creator / 'scripts'))
        from release_manifest import validate_release
        m = validate_release(package, require_approval=True, governance_root=creator / 'content/governance')
        proof = json.loads((web / 'content-release.json').read_text())
        if proof.get('candidate') or proof.get('releaseId') != m['releaseId'] or proof.get('manifestSha256') != digest(package / 'manifest.json'):
            raise ValueError('Web was not built from this approved package')
        for a in m['assets']:
            if digest(web / 'content' / a['path']) != a['id']: raise ValueError('Public content image differs: ' + a['path'])
        for p in web.rglob('*'):
            if p.is_symlink(): raise ValueError('Symlink in static export')
        prior_asset_ids = set()
        if args.base_release and args.base_release.is_dir():
            prior_m = validate_release(args.base_release.resolve())
            prior_asset_ids = {a['id'] for a in prior_m.get('assets', [])}
        output.mkdir(parents=True)
        try:
            content_entries = []
            for p in sorted(package.rglob('*')):
                if not p.is_file(): continue
                rel = p.relative_to(package)
                if rel.parts and rel.parts[0] == 'assets': continue
                content_entries.append((p, str(Path('content') / rel)))
            archive(output / 'content-production.tar.gz', content_entries)
            incremental_entries = []
            new_assets = 0
            reused_assets = 0
            for p in sorted(web.rglob('*')):
                if not p.is_file(): continue
                rel = p.relative_to(web)
                if len(rel.parts) >= 2 and rel.parts[0] == 'content' and rel.parts[1] == 'assets':
                    stem = p.stem
                    if stem in prior_asset_ids:
                        reused_assets += 1
                        continue
                    new_assets += 1
                incremental_entries.append((p, str(Path('web') / rel)))
            archive(output / 'web-incremental.tar.gz', incremental_entries)
            archive(output / 'web-production.tar.gz', [(web, 'web')])
            result = {
                'mode': 'web-only',
                'releaseId': m['releaseId'],
                'articles': len(m['articles']),
                'contentImageCount': len(m['assets']),
                'newAssetsInIncremental': new_assets,
                'reusedAssetsSkipped': reused_assets,
                'output': str(output),
                'archives': {p.name: digest(p) for p in sorted(output.glob('*.tar.gz'))},
                'serverMutation': False,
                'elapsedSeconds': round(time.perf_counter() - started, 3),
            }
            (output / 'bundle.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        except Exception:
            shutil.rmtree(output)
            raise
    db, counts, assets = inventory(core)
    result = {'gameTables': counts, 'images': len(assets), 'output': str(output), 'serverMutation': False}
    if args.command == 'plan':
        db.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if not args.content_package or not args.web_out: raise ValueError('bundle requires --content-package and --web-out')
    package, web = args.content_package.resolve(), args.web_out.resolve()
    # Use the owning protocol validator rather than duplicating approval semantics.
    sys.path.insert(0, str(creator / 'scripts'))
    from release_manifest import validate_release
    m = validate_release(package, require_approval=True, governance_root=creator / 'content/governance')
    proof = json.loads((web / 'content-release.json').read_text())
    if proof.get('candidate') or proof.get('releaseId') != m['releaseId'] or proof.get('manifestSha256') != digest(package / 'manifest.json'):
        raise ValueError('Web was not built from this approved package')
    for a in m['assets']:
        if digest(web / 'content' / a['path']) != a['id']: raise ValueError('Public content image differs: ' + a['path'])
    for p in web.rglob('*'):
        if p.is_symlink(): raise ValueError('Symlink in static export')
    output.mkdir(parents=True)
    try:
        staged = sqlite3.connect(output / 'game-data.sqlite')
        try:
            for sql, in db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL"): staged.execute(sql)
            for t in TABLES:
                rows = db.execute(f'SELECT * FROM "{t}"').fetchall()
                if rows: staged.executemany(f'INSERT INTO "{t}" VALUES (' + ','.join('?' for _ in rows[0]) + ')', rows)
            for sql, in db.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"): staged.execute(sql)
            if staged.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('Invalid game snapshot')
            if staged.execute('PRAGMA foreign_key_check').fetchall(): raise ValueError('Broken game relationships')
            staged.commit()
        finally: staged.close()
        uploads = output / 'local-uploads'
        uploads.mkdir()
        for a in assets:
            p = uploads / a['relative']; p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(core / 'public/uploads' / a['relative'], p)
        (output / 'game-data.json').write_text(json.dumps({'tables': TABLES, 'counts': counts, 'assets': assets, 'missingAssets': []}, ensure_ascii=False, indent=2))
        archive(output / 'game-data.tar.gz', [(output / n, n) for n in ['game-data.sqlite', 'game-data.json', 'local-uploads']])
        archive(output / 'core-code.tar.gz', [(core / n, n) for n in CODE])
        archive(output / 'web-production.tar.gz', [(web, 'web')])
        # Web's public export already contains the approved content assets under
        # /content/assets. Keep the transport package lean: ship article data
        # and approval manifests, while recording image refs for deployment checks.
        content_entries = []
        for p in sorted(package.rglob('*')):
            if not p.is_file():
                continue
            rel = p.relative_to(package)
            if rel.parts and rel.parts[0] == 'assets':
                continue
            content_entries.append((p, str(Path('content') / rel)))
        archive(output / 'content-production.tar.gz', content_entries)
        result.update(releaseId=m['releaseId'], articles=len(m['articles']), archives={p.name: digest(p) for p in sorted(output.glob('*.tar.gz'))})
        result['contentImageDelivery'] = 'web-production.tar.gz:/web/content/assets'
        result['contentImageCount'] = len(m['assets'])
        result['elapsedSeconds'] = round(time.perf_counter() - started, 3)
        (output / 'bundle.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception:
        shutil.rmtree(output)
        raise
    finally: db.close()

if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
