import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('publisher_manifest', Path(__file__).resolve().parents[1] / 'scripts/publish.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ['01_卡片.png', '02_卡片.png', 'preview.png', 'cover_vertical.png']:
            (self.root / name).write_bytes(b'image')
        self.manifest = {'profile': 'douyin', 'includes_cover': True,
                         'images': ['01_卡片.png', '02_卡片.png'], 'validation': {'passed': True}}
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest))

    def test_only_manifest_cards_no_preview_or_duplicate_cover(self):
        images = publisher.collect_images(str(self.root), {'cover_vertical': str(self.root / 'cover_vertical.png')})
        self.assertEqual([Path(p).name for p in images], self.manifest['images'])

    def test_explicit_cover_replaces_first_card(self):
        images = publisher.collect_images(str(self.root), {}, cover_override=str(self.root / 'cover_vertical.png'))
        self.assertEqual([Path(p).name for p in images], ['cover_vertical.png', '02_卡片.png'])

    def test_invalid_manifest_stops_instead_of_collecting_preview(self):
        for images in [['missing.png'], ['../preview.png'], ['01_卡片.png', '01_卡片.png']]:
            self.manifest['images'] = images
            self.save()
            with self.assertRaises(ValueError):
                publisher.collect_images(str(self.root), {})

    def test_failed_validation_stops(self):
        self.manifest['validation']['passed'] = False
        self.save()
        with self.assertRaisesRegex(ValueError, '未通过验证'):
            publisher.collect_images(str(self.root), {})

    def test_changed_outline_or_image_stops(self):
        outline = self.root / 'outline.json'
        outline.write_bytes(b'old')
        self.manifest['input_sha256'] = {str(outline): hashlib.sha256(b'old').hexdigest()}
        self.save()
        outline.write_bytes(b'new')
        with self.assertRaisesRegex(ValueError, '来源已变化'):
            publisher.collect_images(str(self.root), {})
        self.manifest.pop('input_sha256')
        self.manifest['image_sha256'] = {'01_卡片.png': 'incorrect'}
        self.save()
        with self.assertRaisesRegex(ValueError, '图片与验证结果不一致'):
            publisher.collect_images(str(self.root), {})


if __name__ == '__main__':
    unittest.main()
