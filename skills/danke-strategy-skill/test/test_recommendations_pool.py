import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POOL_PATH = ROOT / 'packs/danke/config/recommendations_pool.json'

sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT.parent / 'danke-content-creator-skill/scripts'))

class TestRecommendationsPool(unittest.TestCase):
    def test_pool_file_exists_and_valid(self):
        self.assertTrue(POOL_PATH.exists(), f'Pool file does not exist: {POOL_PATH}')
        with open(POOL_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 8, f'Expected at least 8 articles, got {len(data)}')

        titles = set()
        urls = set()
        for item in data:
            self.assertIn('title', item)
            self.assertIn('url', item)
            self.assertTrue(item['title'].strip(), 'Title should not be empty')
            self.assertTrue(item['url'].startswith('https://mp.weixin.qq.com/s/'), f'Invalid URL: {item["url"]}')
            titles.add(item['title'])
            urls.add(item['url'])
        self.assertEqual(len(titles), len(data), 'Duplicate titles found in pool')
        self.assertEqual(len(urls), len(data), 'Duplicate URLs found in pool')

    def test_pick_recommendations_function(self):
        from pick_recommendations import pick_recommendations, format_recommendations_yaml

        # Test default count is 3
        recs = pick_recommendations(count=3, seed=42)
        self.assertEqual(len(recs), 3)
        self.assertEqual(len(set(r['title'] for r in recs)), 3)

        # Test seed reproducibility
        recs2 = pick_recommendations(count=3, seed=42)
        self.assertEqual(recs, recs2)

        # Test exclude logic
        recs_no_carrier = pick_recommendations(count=3, exclude='载具')
        self.assertEqual(len(recs_no_carrier), 3)
        for r in recs_no_carrier:
            self.assertNotIn('载具', r['title'])

        # Test YAML formatting
        yaml_str = format_recommendations_yaml(recs)
        self.assertIn('recommendations:', yaml_str)
        self.assertIn('title:', yaml_str)
        self.assertIn('url:', yaml_str)

if __name__ == '__main__':
    unittest.main()
