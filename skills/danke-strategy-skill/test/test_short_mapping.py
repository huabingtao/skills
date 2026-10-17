import base64
import json
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from engine.compiler import ImageResolver, convert_to_wechat_html
from engine.short_mapping import inspect_short_mapping, load_short_mapping, read_short_mapping
from scripts.compile import load_project_config


ROOT = Path(__file__).resolve().parents[1]


class ShortMappingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pack = Path(self.temp.name)
        self.assets = self.pack / 'assets/img'
        self.assets.mkdir(parents=True)
        self.first = 's级杰出装备自选宝箱'
        self.second = '神器核心自选宝箱'
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jf3sAAAAASUVORK5CYII=')
        for name in [self.first, self.second]:
            (self.assets / (name + '.png')).write_bytes(png)
        self.local = {
            self.first: f'assets/img/{self.first}.png',
            'S级杰出宝箱': f'assets/img/{self.first}.png',
            self.second: f'assets/img/{self.second}.png',
        }
        self.shorts = {'S自选箱': self.first, '神器核心自选': self.second}
        self.write('image_mapping.json', self.local)
        self.write('image_mapping_short.json', self.shorts)
        self.config = {
            'assets_dir': str(self.pack / 'assets'),
            'image_mapping_path': str(self.pack / 'image_mapping.json'),
            'local_image_mapping_path': str(self.pack / 'image_mapping.json'),
            'short_image_mapping_path': str(self.pack / 'image_mapping_short.json'),
        }

    def write(self, filename, value):
        (self.pack / filename).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def test_short_and_long_names_resolve_to_same_local_image(self):
        resolver = ImageResolver(self.config)
        for short, full in self.shorts.items():
            self.assertEqual(resolver.resolve_image_src('img://' + short), resolver.resolve_image_src('img://' + full))
        self.assertEqual(resolver.resolve_image_src('img://S级杰出宝箱'), resolver.resolve_image_src('img://S自选箱'))

    def test_cos_and_missing_cos_name_local_fallback(self):
        self.write('cos.json', {self.first: 'https://cdn.example.test/first.png'})
        resolver = ImageResolver(dict(self.config, image_mapping_path=str(self.pack / 'cos.json')))
        self.assertEqual(resolver.resolve_image_src('img://S自选箱'), 'https://cdn.example.test/first.png')
        self.assertEqual(resolver.resolve_image_src('img://神器核心自选'), resolver.resolve_image_src('img://' + self.second))
        self.assertTrue(resolver.resolve_image_src('img://神器核心自选').endswith(self.second + '.png'))

    def test_pack_loader_wires_same_short_table_in_cos_mode(self):
        self.write('cos.json', {self.first: 'https://cdn.example.test/first.png'})
        self.write('project.json', {
            'image_mapping': 'image_mapping.json', 'image_mapping_cos': 'cos.json',
            'image_mapping_short': 'image_mapping_short.json', 'cos_mode': True,
            'assets_dir': 'assets',
        })
        config = load_project_config(str(self.pack))
        self.assertEqual(config['image_mapping_path'], str(self.pack / 'cos.json'))
        self.assertEqual(config['local_image_mapping_path'], str(self.pack / 'image_mapping.json'))
        self.assertEqual(ImageResolver(config).resolve_image_src('img://S自选箱'), 'https://cdn.example.test/first.png')

    def test_short_and_old_macros_compile_together_without_changing_prose(self):
        md = f'兑换 S 级杰出装备自选宝箱{{{{S自选箱}}}}，再看神器核心自选{{{{{self.second}}}}}。'
        rendered, _ = convert_to_wechat_html(md, self.config)
        soup = BeautifulSoup(rendered, 'html.parser')
        self.assertEqual(soup.get_text(strip=True), '兑换 S 级杰出装备自选宝箱，再看神器核心自选。')
        self.assertEqual(len(soup.find_all('img')), 2)
        self.assertNotIn('{{', rendered)
        self.assertTrue(all(img.get('src') for img in soup.find_all('img')))

    def test_duplicate_asset_and_legacy_name_collision_are_rejected(self):
        for shorts in [
            dict(self.shorts, 另一个箱=self.first),
            {'S级杰出宝箱': self.second},
            {'S自选箱': self.first, 's自选箱': self.second},
        ]:
            with self.subTest(shorts=shorts):
                report = inspect_short_mapping(shorts, self.local, self.pack)
                self.assertFalse(report['passed'])
                self.write('invalid.json', shorts)
                with self.assertRaises(ValueError):
                    load_short_mapping(self.pack / 'invalid.json', self.local, self.pack)

    def test_unknown_target_missing_asset_and_alias_chains_are_rejected(self):
        local = dict(self.local, 失效道具='assets/img/missing.png')
        for shorts in [{'未知': '不存在'}, {'失效': '失效道具'}, {'别名': 'S自选箱'}]:
            self.assertFalse(inspect_short_mapping(shorts, local, self.pack)['passed'])
        report = inspect_short_mapping(self.shorts, local, self.pack, require_coverage=True)
        self.assertTrue(report['passed'])
        self.assertEqual(len(report['missing_legacy_assets']), 1)
        self.assertFalse(inspect_short_mapping({'S自选箱': self.first}, self.local, self.pack, require_coverage=True)['passed'])

    def test_identical_bytes_different_items_are_not_deduplicated(self):
        # Both fixture files have identical PNG bytes, but are separate items.
        report = inspect_short_mapping(self.shorts, self.local, self.pack, require_coverage=True)
        self.assertTrue(report['passed'])
        self.assertEqual(report['available_asset_count'], 2)
        self.assertEqual(report['short_count'], 2)

    def test_duplicate_json_keys_are_not_silently_overwritten(self):
        path = self.pack / 'duplicate.json'
        path.write_text('{"短名":"旧名一","短名":"旧名二"}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '重复名称'):
            read_short_mapping(path)


class ActualPackShortMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = ROOT / 'packs/danke'
        cls.config = load_project_config(str(cls.pack))
        cls.local = json.loads((cls.pack / 'image_mapping.json').read_text())
        cls.shorts = read_short_mapping(cls.pack / 'image_mapping_short.json')

    def test_every_available_asset_has_one_short_and_no_missing_target(self):
        report = inspect_short_mapping(self.shorts, self.local, self.pack, require_coverage=True)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['short_count'], report['available_asset_count'])
        for short, full in {
            'S自选箱': 's级杰出装备自选宝箱', 'S钥匙': 's级军备钥匙',
            'SP碎片': 'sp特工万能碎片', '神器核心自选': '神器核心自选宝箱',
            '史诗收藏箱': '史诗收藏品宝箱', '滑板碎片': '科技滑板碎片',
            '平衡车碎片': '电动平衡车碎片',
        }.items():
            self.assertEqual(self.shorts[short], full)
        self.assertNotEqual(self.local[self.shorts['传奇载具碎片']], self.local[self.shorts['战马碎片']])

    def test_all_old_names_keep_original_resolution_in_local_and_cos_modes(self):
        for path in ['image_mapping.json', 'image_mapping_cos.json']:
            config = dict(self.config, image_mapping_path=str(self.pack / path))
            baseline = dict(config)
            baseline.pop('short_image_mapping_path')
            old = ImageResolver(baseline)
            new = ImageResolver(config)
            for full in self.local:
                with self.subTest(mode=path, full=full):
                    self.assertEqual(new.resolve_image_src('img://' + full), old.resolve_image_src('img://' + full))

    def test_all_recommended_shorts_match_full_names_in_both_modes(self):
        for path in ['image_mapping.json', 'image_mapping_cos.json']:
            resolver = ImageResolver(dict(self.config, image_mapping_path=str(self.pack / path)))
            for short, full in self.shorts.items():
                with self.subTest(mode=path, short=short):
                    resolved = resolver.resolve_image_src('img://' + short)
                    self.assertTrue(resolved)
                    self.assertEqual(resolved, resolver.resolve_image_src('img://' + full))

    def test_cos_gaps_and_whitespace_do_not_fuzzy_match_other_items(self):
        resolver = ImageResolver(dict(self.config, image_mapping_path=str(self.pack / 'image_mapping_cos.json')))
        for short, full in [('平衡车', '电动平衡车'), ('滑板', '科技滑板'),
                            ('原子机器人', '原子机器人 '), ('扭曲腰带', '混沌腰带-扭曲腰带 ')]:
            with self.subTest(short=short):
                resolved = resolver.resolve_image_src('img://' + short)
                self.assertTrue(resolved.startswith('https://'))
                self.assertEqual(resolved, resolver.resolve_image_src('img://' + full))
        self.assertNotEqual(resolver.resolve_image_src('img://平衡车'), resolver.resolve_image_src('img://平衡车碎片'))


if __name__ == '__main__':
    unittest.main()
