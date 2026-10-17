"""Local integration checks; never log in or upload to Douyin."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from bs4 import BeautifulSoup
from PIL import Image

SKILL = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

renderer = load('douyin_renderer', SKILL / 'scripts/render_cards.py')
publisher = load('douyin_manifest_consumer', SKILL / 'scripts/publish.py')


def card(content, kind=''):
    return f'<section class="card single" {kind}><div class="body hybrid"><p class="eyebrow">示例攻略</p><div class="target"><span class="metric">目标</span><span>进度</span></div>{content}<div class="brand"><b>弹壳呱呱</b><span>内容页</span></div></div></section>'


def document(cards):
    return '<html><head><meta charset="utf-8"></head><body><main class="gallery">'+cards+'</main></body></html>'


class RendererTests(unittest.TestCase):
    def test_pagination_mixed_macros_missing_new_item_and_manifest_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            full_name = '名称比较长的游戏道具' * 5
            story = '这一段说明需要保留每一个字。' * 180 + '<span class="item-inline">核心{{神器核心}}</span>仍须完整。'
            rows = ''.join(f'<tr><td>{i}</td><td>{i*100}</td></tr>' for i in range(24))
            rewards = '<h3>累计奖励</h3><div class="reward-list">' + ''.join(
                f'<div class="reward-line">{{{{{macro}}}}}<span class="item-name">{name}</span><span class="qty">×1</span></div>'
                for macro, name in [('神器核心自选', full_name), ('神器核心自选宝箱', '神器核心自选宝箱')])
            rewards += '<div class="reward-line text-only" data-missing-reason="新内容缺图"><span class="item-name">新头像</span><span class="qty">×1</span></div></div>'
            source = root / 'cards.html'
            source.write_text(document(card('<h2>封面</h2>', 'data-kind="cover"') +
                card(rewards) + card('<p class="story">'+story+'</p>') +
                card('<h3>预算</h3><table class="table"><thead><tr><th>开箱</th><th>预计补钻（钻石）</th></tr></thead><tbody>'+rows+'</tbody></table>')))
            out = root / 'dist/抖音图文_3x4'
            with patch.object(publisher, 'main', side_effect=AssertionError('不应上传')):
                manifest = renderer.render(source, out)
            self.assertTrue(manifest['validation']['passed'])
            self.assertTrue(manifest['includes_cover'])
            self.assertGreater(len(manifest['images']), 4)
            result = BeautifulSoup((out/'index.html').read_text(), 'html.parser')
            self.assertEqual([n.get_text() for n in result.select('.item-name')], [full_name, '神器核心自选宝箱', '新头像'])
            expected_story = BeautifulSoup(story, 'html.parser').get_text().replace('{{神器核心}}', '')
            self.assertEqual(''.join(n.get_text() for n in result.select('.story')), expected_story)
            self.assertEqual([td.get_text() for td in result.select('tbody td')], [s for i in range(24) for s in (str(i), str(i*100))])
            self.assertGreater(len(result.select('thead')), 1)
            assets = json.loads((out/'asset-manifest.json').read_text())
            by_macro = {a.get('macro'): a for a in assets['assets']}
            self.assertEqual(by_macro['神器核心自选']['asset'], by_macro['神器核心自选宝箱']['asset'])
            self.assertEqual(assets['text_only'][0]['name'], '新头像')
            # Preview files and stale files are never included in the upload list.
            (out/'stale.png').write_bytes(b'ignored')
            collected = publisher.collect_images(str(out), {'cover_vertical': 'old.png'})
            self.assertEqual([Path(p).name for p in collected], manifest['images'])
            for name in manifest['images']:
                with Image.open(out/name) as im:
                    self.assertEqual(im.size, (1200, 1600))
            original = source.read_text()
            source.write_text(original+' ')
            with self.assertRaisesRegex(ValueError, '来源已变化'):
                publisher.collect_images(str(out), {})
            source.write_text(original)
            (out/manifest['images'][0]).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, '图片与验证结果不一致'):
                publisher.collect_images(str(out), {})

    def test_compiled_local_and_remote_images_become_portable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root/'compiled.png'
            Image.new('RGB', (32, 32), 'purple').save(image)
            source = root/'cards.html'
            source.write_text(document(card('<p>本地图<img class="item-icon inline" data-macro="已编译" src="compiled.png"></p>'
                '<p>远程图<img class="item-icon inline" src="https://example.invalid/cos/item.png"></p>')))
            response = MagicMock()
            response.__enter__.return_value.read.return_value = image.read_bytes()
            with patch.object(renderer, 'urlopen', return_value=response) as request:
                manifest = renderer.render(source, root/'out')
            request.assert_called_once()
            self.assertTrue(manifest['validation']['passed'])
            assets = json.loads((root/'out/asset-manifest.json').read_text())['assets']
            self.assertEqual(len(assets), 2)
            self.assertEqual(assets[0]['asset'], assets[1]['asset'])
            self.assertTrue((root/'out'/assets[0]['asset']).is_file())

    def test_macro_and_asset_failures_invalidate_prior_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'cards.html'
            out = root/'out'
            for markup in ['<p>{{绝对不存在的测试道具}}</p>', '<img src="missing.png">']:
                source.write_text(document(card(markup)))
                with self.assertRaises(ValueError):
                    renderer.render(source, out)
                self.assertFalse(json.loads((out/'manifest.json').read_text())['validation']['passed'])
            source.write_text(document(card('<p>{{神器核心}}</p>')))
            with patch('engine.compiler.ImageResolver.resolve_image_src', return_value='missing-mapped.png'):
                with self.assertRaisesRegex(ValueError, '素材文件不存在'):
                    renderer.render(source, out)

    def test_unsplittable_atomic_row_fails_without_shrinking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'cards.html'
            source.write_text(document(card('<div class="reward-line text-only" data-missing-reason="测试名称"><span class="item-name">'+'超长名称'*200+'</span><span class="qty">×1</span></div>')))
            with self.assertRaisesRegex(ValueError, '验证未通过'):
                renderer.render(source, root/'out')
            report = json.loads((root/'out/validation.json').read_text())
            self.assertFalse(report['passed'])
            self.assertTrue(any('不缩小字号' in str(e) for e in report['errors']))


if __name__ == '__main__':
    unittest.main()
