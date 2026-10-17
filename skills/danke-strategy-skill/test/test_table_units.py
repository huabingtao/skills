import unittest
from bs4 import BeautifulSoup
from engine.compiler import convert_to_wechat_html
from engine.table_units import normalize_diamond_table_units


class DiamondTableTests(unittest.TestCase):
    def test_moves_units_keeps_highlight_and_is_idempotent(self):
        soup = BeautifulSoup('<table><tr><th>开箱</th><th>补至 1650</th></tr><tr><td>600</td><td><strong><font color="red">43200</font></strong> 钻</td></tr><tr><td>500</td><td>55700 钻石</td></tr></table>', 'html.parser')
        normalize_diamond_table_units(soup)
        self.assertEqual(soup.find_all('th')[1].get_text(), '补至 1650（钻石）')
        self.assertEqual([x.get_text(strip=True) for x in soup.find_all('td')], ['600', '43200', '500', '55700'])
        self.assertEqual(soup.font['color'], 'red')
        once = str(soup)
        normalize_diamond_table_units(soup)
        self.assertEqual(str(soup), once)

    def test_mixed_prose_and_currency_are_not_rewritten(self):
        for values in [('100 钻', '2 钥匙'), ('100 钻', '按需补钻'), ('100 钻', '50 金币')]:
            source = f'<table><tr><th>奖励</th></tr><tr><td>{values[0]}</td></tr><tr><td>{values[1]}</td></tr></table>'
            soup = BeautifulSoup(source, 'html.parser')
            normalize_diamond_table_units(soup)
            self.assertEqual(str(soup), source)

    def test_icon_units_and_existing_header(self):
        soup = BeautifulSoup('<table><tr><th>预算（钻石）</th></tr><tr><td>100<img alt="钻石" src="x"></td></tr><tr><td>0</td></tr></table>', 'html.parser')
        normalize_diamond_table_units(soup)
        self.assertEqual(soup.th.get_text(), '预算（钻石）')
        self.assertIsNone(soup.img)
        self.assertEqual(soup.td.get_text(), '100')

    def test_multiline_values_are_not_merged_into_one_number(self):
        source = '<table><tr><th>方案</th></tr><tr><td>100<br/>200 钻</td></tr></table>'
        soup = BeautifulSoup(source, 'html.parser')
        normalize_diamond_table_units(soup)
        self.assertEqual(str(soup), source)

    def test_both_compile_routes_use_pack_setting_without_altering_prose(self):
        md = '正文需要 100 钻。\n\n| 箱数 | 补钻 |\n| --- | --- |\n| 500 | 3800 钻 |\n| 600 | 0 钻 |'
        html, _ = convert_to_wechat_html(md, {'diamond_table_unit_in_header': True})
        soup = BeautifulSoup(html, 'html.parser')
        self.assertEqual(soup.find_all('th')[1].get_text(), '补钻（钻石）')
        self.assertIn('正文需要 100 钻', soup.get_text())
        self.assertEqual([x.get_text(strip=True) for x in soup.find_all('td')], ['500', '3800', '600', '0'])
        html, _ = convert_to_wechat_html(md, {})
        self.assertIn('3800 钻', BeautifulSoup(html, 'html.parser').get_text())


if __name__ == '__main__':
    unittest.main()
