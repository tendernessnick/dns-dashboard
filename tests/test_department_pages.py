"""页面注册、复用和错误配置保护；不联网、不写生产产物。"""
import copy
import csv
import importlib.util
import json
from html.parser import HTMLParser
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


PAGE_IDS = {'strategy', 'marketing', 'design', 'product', 'hr'}
EXPECTED_PLANNED = {f'M{i}' for i in range(301, 312)}


class FragmentAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes, self.text = [], []

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


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
        self.assertEqual({p['ID'] for p in pages}, PAGE_IDS)
        self.assertEqual(len(pages), len(PAGE_IDS))

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
        self.assertEqual(info['activeModuleCount'], 51)
        self.assertEqual(info['plannedCount'], 2)
        self.assertEqual(info['moduleCount'], 53)
        self.assertEqual(sum(c['类型'] != 'planned' for c in builder.CARDS.values()), 98)
        self.assertEqual(sum(c['类型'] == 'planned' for c in builder.CARDS.values()), 11)
        self.assertEqual(builder.CARDS, before)
        self.assertIn('data-mid="205_营收趋势季度"', html)
        self.assertIn('data-source-pids="P96"', html)
        self.assertNotIn('<!--__', html)
        self.assertNotIn('id="m1"', html)

    def test_strategy_keeps_all_existing_modules_and_only_its_three_plans(self):
        page = next(p for p in builder.PAGES if p['ID'] == 'strategy')
        layout = builder.read_layout(page)
        refs = {row['引用'] for row in layout if row['类型'] == 'C'}
        active = {cid for cid, card in builder.CARDS.items() if card['类型'] != 'planned'}
        planned = {builder.CARDS[cid]['预留编号'] for cid in refs if cid not in active}
        self.assertEqual(len(active), 98)
        self.assertTrue(active.issubset(refs))
        self.assertEqual(planned, {'M301', 'M302', 'M303'})
        _, info = builder.build_page(page)
        self.assertEqual((info['activeModuleCount'], info['plannedCount'], info['moduleCount']), (98, 3, 101))

    def test_every_page_has_unique_existing_references_and_all_plans_are_used(self):
        used_plans = set()
        for page in builder.PAGES:
            with self.subTest(page=page['ID']):
                refs = [row['引用'] for row in builder.read_layout(page) if row['类型'] == 'C']
                self.assertEqual(len(refs), len(set(refs)))
                self.assertTrue(set(refs).issubset(builder.CARDS))
                planned = [builder.CARDS[cid] for cid in refs if builder.CARDS[cid]['类型'] == 'planned']
                used_plans.update(card['预留编号'] for card in planned)
                html, info = builder.build_page(page)
                self.assertEqual(info['moduleCount'], len(refs))
                self.assertEqual(info['plannedCount'], len(planned))
                self.assertEqual(info['activeModuleCount'], len(refs) - len(planned))
                self.assertNotIn('<!--__', html)
        self.assertEqual(used_plans, EXPECTED_PLANNED)

    def test_planned_cards_have_no_values_binding_or_provenance(self):
        planned = [card for card in builder.CARDS.values() if card['类型'] == 'planned']
        self.assertEqual(len(planned), 11)
        self.assertEqual({card['预留编号'] for card in planned}, EXPECTED_PLANNED)
        forbidden_attrs = {'data-k', 'data-source-pids', 'data-news', 'data-review', 'data-toplist',
                           'data-topsub', 'data-ring', 'data-multi', 'data-cal', 'data-cal-desc',
                           'data-vk', 'data-tk', 'data-ref'}
        forbidden_classes = {'val', 'vnum', 'chart', 'sparkrow', 'dpill', 'statline',
                             'revcards', 'src-ref', 'c-ok', 'c-warn'}
        for card in planned:
            with self.subTest(module=card['ID']):
                builder.validate_planned(card)
                self.assertFalse(card.get('主数据'))
                self.assertFalse(card.get('关联数据'))
                self.assertEqual(card['预留编号'][1:], card['ID'].split('_')[0])
                self.assertFalse(builder.module_pids(card))
                audit = FragmentAudit()
                audit.feed(builder.card_html(card))
                root_attrs = audit.nodes[0][1]
                self.assertIn('planned-card', root_attrs.get('class', '').split())
                self.assertEqual(root_attrs.get('data-module-status'), 'planned')
                self.assertEqual(root_attrs.get('data-planned-id'), card['预留编号'])
                self.assertEqual(root_attrs.get('data-mid'), card['ID'])
                for tag, attrs in audit.nodes:
                    self.assertFalse(forbidden_attrs.intersection(attrs))
                    self.assertFalse(forbidden_classes.intersection(attrs.get('class', '').split()))
                    self.assertNotIn(tag, {'script', 'iframe', 'object', 'embed', 'canvas'})
                chips = [attrs for _, attrs in audit.nodes
                         if {'chip', 'c-planned'}.issubset(attrs.get('class', '').split())]
                self.assertEqual(len(chips), 1)
                self.assertIn('规划中', ''.join(audit.text))

    def test_planned_config_rejects_fake_bindings_values_and_invalid_identity(self):
        original = next(card for card in builder.CARDS.values() if card['类型'] == 'planned')
        cases = [('主数据', 'P1'), ('关联数据', ['P1']), ('资讯键', 'P14'),
                 ('图表组', [{'P': 'P1'}]), ('多品类', 'P58'), ('环形', 'P56'),
                 ('榜单', 'P66'), ('数值占位', '123'), ('状态点', 'g'),
                 ('预留编号', 'P301'), ('预留编号', 'M999'),
                 ('预留编号', 301), ('预留编号', None)]
        for key, value in cases:
            with self.subTest(field=key, value=value):
                card = copy.deepcopy(original)
                card[key] = value
                with self.assertRaises(ValueError):
                    builder.validate_planned(card)
        for key in ('用途', '计划内容', '展示字段', '候选来源', '使用边界'):
            with self.subTest(missing=key):
                card = copy.deepcopy(original)
                del card['规划对象'][key]
                with self.assertRaises(ValueError):
                    builder.validate_planned(card)
        for key in ('展示字段', '候选来源'):
            with self.subTest(empty=key):
                card = copy.deepcopy(original)
                card['规划对象'][key] = []
                with self.assertRaises(ValueError):
                    builder.validate_planned(card)

    def test_planned_text_and_arrays_are_escaped_without_executable_markup(self):
        original = next(card for card in builder.CARDS.values() if card['类型'] == 'planned')
        payload = '<img src=x onerror="untrusted()"> & <script>untrusted()</script>'
        for target in ('卡名', '用途', '计划内容', '使用边界', '展示字段', '候选来源'):
            with self.subTest(field=target):
                card = copy.deepcopy(original)
                if target == '卡名':
                    card[target] = payload
                else:
                    card['规划对象'][target] = [payload] if target in {'展示字段', '候选来源'} else payload
                html = builder.b_planned(card)
                audit = FragmentAudit()
                audit.feed(html)
                self.assertIn(payload, ''.join(audit.text))
                self.assertNotIn('<img ', html)
                self.assertNotIn('<script>', html)
                self.assertFalse(any(tag in {'img', 'script'} for tag, _ in audit.nodes))
                self.assertFalse(any(key.startswith('on') for _, attrs in audit.nodes for key in attrs))

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
