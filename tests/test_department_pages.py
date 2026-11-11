"""页面注册、复用和错误配置保护；不联网、不写生产产物。"""
import copy
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / '看板'
sys.path.insert(0, str(BOARD))
from 页面配置 import load_pages

spec = importlib.util.spec_from_file_location('department_builder', BOARD / '生成看板.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PageConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((BOARD / '页面.json').read_text(encoding='utf-8'))

    def validate(self, config):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            for page in self.config['页面']:
                (base / page['布局']).write_text('', encoding='utf-8')
            (base / '页面.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
            return load_pages(base)

    def test_registered_pages_are_distinct_and_use_existing_layouts(self):
        default, pages = load_pages(BOARD)
        self.assertEqual(default, 'strategy')
        self.assertEqual({p['ID'] for p in pages}, {'strategy', 'marketing'})

    def test_paths_outputs_and_ids_are_validated_before_build(self):
        bad = [
            ('ID', '../unsafe'), ('文件', '../index.html'), ('文件', 'https://other.test/a.html'),
            ('布局', '..\\布局.csv'), ('布局', 'missing.csv'), ('使用布局跨列', 'true')]
        for key, value in bad:
            with self.subTest(key=key, value=value):
                config = copy.deepcopy(self.config)
                config['页面'][1][key] = value
                with self.assertRaises(ValueError):
                    self.validate(config)

    def test_duplicate_page_ids_and_case_insensitive_outputs_are_rejected(self):
        for key, value in [('ID', 'strategy'), ('文件', 'INDEX.html')]:
            config = copy.deepcopy(self.config)
            config['页面'][1][key] = value
            with self.assertRaises(ValueError):
                self.validate(config)

    def test_market_reuses_modules_without_mutating_card_configs(self):
        before = copy.deepcopy(builder.CARDS)
        page = next(p for p in builder.PAGES if p['ID'] == 'marketing')
        html, info = builder.build_page(page)
        self.assertEqual(info['moduleCount'], 51)
        self.assertEqual(len(builder.CARDS), 98)
        self.assertEqual(builder.CARDS, before)
        self.assertIn('data-mid="205_营收趋势季度"', html)
        self.assertIn('data-source-pids="P96"', html)
        self.assertNotIn('<!--__', html)
        self.assertNotIn('id="m1"', html)

    def test_invalid_module_reference_does_not_overwrite_existing_pages(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            for page in builder.PAGES:
                (base / page['布局']).write_bytes((BOARD / page['布局']).read_bytes())
            market = base / '布局_市场部.csv'
            with market.open(encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                fields, rows = reader.fieldnames, list(reader)
            next(r for r in rows if r['类型'] == 'C')['引用'] = '不存在的模块'
            with market.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            original = b'existing complete page'
            (base / 'index.html').write_bytes(original)
            with patch.object(builder, 'BASE', str(base)):
                with self.assertRaises(ValueError):
                    builder.main()
            self.assertEqual((base / 'index.html').read_bytes(), original)
            self.assertFalse((base / 'marketing.html').exists())

    def test_page_label_cannot_close_inline_metadata_script(self):
        page = dict(next(p for p in builder.PAGES if p['ID'] == 'marketing'))
        page['名称'] = '</script><script>untrusted()</script>'
        html, _ = builder.build_page(page)
        self.assertNotIn('</script><script>untrusted()', html)
        self.assertIn('<\\/script>', html)

    def test_layout_cannot_take_reserved_ids_or_inject_stack_columns(self):
        page = next(p for p in builder.PAGES if p['ID'] == 'marketing')
        with (BOARD / page['布局']).open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            fields, original = reader.fieldnames, list(reader)
        cases = [('S', '引用', 'provToggle'), ('S', '引用', 'coTabs-fake'),
                 ('K', '跨列', '6" onclick="bad()'), ('K', '跨列', '13')]
        for kind, key, value in cases:
            with self.subTest(kind=kind, value=value), tempfile.TemporaryDirectory() as folder:
                rows = copy.deepcopy(original)
                if kind == 'S':
                    rows[0][key] = value
                else:
                    row = {k: '' for k in fields}
                    row.update({'类型': 'K', '跨列': value, '堆叠': 'test'})
                    rows.insert(1, row)
                target = Path(folder) / page['布局']
                with target.open('w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)
                with patch.object(builder, 'BASE', folder), self.assertRaises(ValueError):
                    builder.read_layout(page)


if __name__ == '__main__':
    unittest.main()
