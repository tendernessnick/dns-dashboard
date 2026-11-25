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
EXPECTED_PLANNED = {f'P{i}' for i in range(255, 266)} | {f'P{i}' for i in range(270, 275)}
STRATEGY_PLANNED = {'P255', 'P256', 'P257'} | {f'P{i}' for i in range(270, 275)}
MARKET_CARDS = {'275_电商大盘_各类产品': ['P275', 'P276', 'P277', 'P278', 'P279'],
                '280_电商大盘_各品牌': ['P280', 'P281', 'P282', 'P283', 'P284', 'P285']}


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
        self.assertEqual(sum(c['类型'] != 'planned' for c in builder.CARDS.values()), 104)
        self.assertEqual(sum(c['类型'] == 'planned' for c in builder.CARDS.values()), 16)
        self.assertEqual(builder.CARDS, before)
        self.assertIn('data-mid="205_营收趋势季度"', html)
        self.assertIn('data-source-pids="P96"', html)
        self.assertNotIn('<!--__', html)
        self.assertNotIn('id="m1"', html)

    def test_strategy_keeps_all_existing_modules_and_its_eight_plans(self):
        page = next(p for p in builder.PAGES if p['ID'] == 'strategy')
        layout = builder.read_layout(page)
        refs = {row['引用'] for row in layout if row['类型'] == 'C'}
        active = {cid for cid, card in builder.CARDS.items() if card['类型'] != 'planned'}
        planned = {builder.CARDS[cid]['预留编号'] for cid in refs if cid not in active}
        self.assertEqual(len(active), 104)
        self.assertTrue(active.issubset(refs))
        self.assertEqual(planned, STRATEGY_PLANNED)
        _, info = builder.build_page(page)
        self.assertEqual((info['activeModuleCount'], info['plannedCount'], info['moduleCount']), (104, 8, 112))

    def test_new_product_plans_close_every_company_panel_without_data(self):
        """v29：五家上市公司页签各留一张新品发布监测规划卡（页签内最后一张），只描述未来能力，不登记词条。"""
        plans = {'安克创新': 'P270', '奥海科技': 'P271', '佳禾智能': 'P272', '海能实业': 'P273', '绿联科技': 'P274'}
        strategy = next(p for p in builder.PAGES if p['ID'] == 'strategy')
        panels, current = {}, None
        for row in builder.read_layout(strategy):
            if row['类型'] == 'P':
                current = panels.setdefault(row['引用'], [])
            elif row['类型'] == 'G':
                current = None
            elif row['类型'] == 'C' and current is not None:
                current.append(row['引用'])
        self.assertEqual(set(panels), set(plans))
        for company, number in plans.items():
            with self.subTest(company=company):
                cid = number[1:] + '_新品发布监测'
                self.assertEqual(panels[company][-1], cid)
                self.assertEqual(panels[company].count(cid), 1)
                card = builder.CARDS[cid]
                builder.validate_planned(card)
                self.assertEqual((card['类型'], card['预留编号'], card['面板'], card['跨列']), ('planned', number, company, 12))
                self.assertIn(company, card['规划对象']['用途'])
                self.assertNotIn(number, {row['P号'] for row in builder.REGISTRY})
                self.assertNotIn(number, {'P' + str(item['id']) for item in builder.PROV})
        for other in builder.PAGES:
            if other['ID'] != 'strategy':
                refs = [row['引用'] for row in builder.read_layout(other) if row['类型'] == 'C']
                self.assertFalse([ref for ref in refs if ref.endswith('_新品发布监测')], other['ID'])

    def test_market_cards_bind_one_registered_term_per_page_without_data(self):
        """v29：电商大盘两张翻页卡一卡多词条（每页一个P号、按站点分列）；词条已登记来源但尚未采集，不绑定采集器。"""
        registry = {row['P号']: row for row in builder.REGISTRY}
        sources = {'P' + str(item['id']): item for item in builder.PROV}
        strategy = next(p for p in builder.PAGES if p['ID'] == 'strategy')
        refs = [row['引用'] for row in builder.read_layout(strategy) if row['类型'] == 'C']
        self.assertEqual([ref for ref in refs if builder.CARDS[ref]['类型'] == 'market'], list(MARKET_CARDS))
        self.assertLess(refs.index('280_电商大盘_各品牌'), refs.index('59_充电头网早报'))
        for cid, pids in MARKET_CARDS.items():
            with self.subTest(module=cid):
                card = builder.CARDS[cid]
                builder.validate_market(card)
                self.assertEqual((card['跨列'], card['主数据'], card['关联数据']), (12, pids[0], pids[1:]))
                self.assertEqual([page['P'] for page in card['页面']], pids)
                self.assertEqual(builder.CARD_PIDS[cid], set(pids))
                self.assertEqual({market['键'] for market in card['市场']}, {'美国', '欧洲', '日本'})
                self.assertEqual(sum(1 for metric in card['指标'] if metric.get('主')), 1)
                html = builder.card_html(card)
                audit = FragmentAudit()
                audit.feed(html)
                self.assertIn('market-card', audit.nodes[0][1]['class'].split())
                self.assertEqual(audit.nodes[0][1]['data-card-kind'], 'market')
                self.assertEqual(audit.nodes[0][1]['data-k'], ' '.join(pid[1:] for pid in pids))
                pages = [attrs for tag, attrs in audit.nodes if 'market-page' in attrs.get('class', '').split()]
                self.assertEqual([page['data-market-pid'] for page in pages], pids)
                tabs = [attrs for tag, attrs in audit.nodes if 'mtab' in attrs.get('class', '').split()]
                self.assertEqual(len(tabs), len(pids))
                self.assertEqual([tab['data-market-tab'] for tab in tabs], [str(i) for i in range(len(pids))])
                self.assertEqual([tab['aria-pressed'] for tab in tabs], ['true'] + ['false'] * (len(pids) - 1))
                self.assertEqual([tab['data-market-pid'] for tab in tabs], pids)
                actions = [attrs for tag, attrs in audit.nodes if 'detail-open' in attrs.get('class', '').split()]
                self.assertEqual(len(actions), 1)
                self.assertEqual(actions[0]['data-detail-pid'], pids[0])
                for pid in pids:
                    self.assertEqual(registry[pid]['状态'], '入口/受限')
                    self.assertEqual((registry[pid]['采集器'], registry[pid]['可靠度']), ('', '—(无数值数据)'))
                    self.assertEqual((sources[pid]['source'], sources[pid]['url'], sources[pid]['status']),
                                     ('Sorftime 类目报告（美/欧/日）', '', '部分成功'))

    def test_market_config_rejects_mismatched_or_duplicated_pages(self):
        original = builder.CARDS['275_电商大盘_各类产品']
        cases = [('关联数据', ['P276', 'P277', 'P278']), ('主数据', 'P276'), ('页面', []), ('市场', []), ('页名', ' '),
                 ('页面', [{'P': 'P275', '名称': '线材'}, {'P': 'P275', '名称': '线材'}]),
                 ('页面', [{'P': 'P275', '名称': '线材'}, {'P': '276', '名称': '充电器'}]),
                 ('市场', [{'键': '美国', '名称': '美国'}, {'键': '美国', '名称': '美国'}])]
        for key, value in cases:
            with self.subTest(field=key, value=value):
                card = copy.deepcopy(original)
                card[key] = value
                with self.assertRaises(ValueError):
                    builder.validate_market(card)

    def test_merged_cards_are_split_into_customer_and_recruitment_modules(self):
        """v28：四家公司合并卡拆为独立的大客户集中度与招聘职位量卡，每家公司页签各一张。"""
        companies = {'奥海科技': ('251', '266'), '佳禾智能': ('252', '267'),
                     '海能实业': ('253', '268'), '绿联科技': ('254', '269')}
        self.assertFalse([cid for cid in builder.CARDS if cid.endswith('_大客户招聘监测')])
        for company, (customer, recruit) in companies.items():
            for number, title in ((customer, '大客户集中度'), (recruit, '招聘职位量监测')):
                card = builder.CARDS[f'{number}_{title}']
                self.assertEqual((card['面板'], card['主数据'], card['类型']), (company, 'P' + number, 'desc'))
                self.assertEqual(card['状态点'], 'y')
                self.assertNotIn('数值占位', card)
        page = next(p for p in builder.PAGES if p['ID'] == 'strategy')
        panels, current = {}, None
        for row in builder.read_layout(page):
            if row['类型'] == 'P':
                current = panels.setdefault(row['引用'], [])
            elif row['类型'] == 'C' and current is not None:
                current.append(row['引用'])
        expected = dict(companies, 安克创新=('80', '83'))
        self.assertEqual(set(panels), set(expected))
        for company, (customer, recruit) in expected.items():
            self.assertEqual([r for r in panels[company] if r.endswith('_大客户集中度')],
                             [f'{customer}_大客户集中度'])
            self.assertEqual([r for r in panels[company] if r.endswith('_招聘职位量监测')],
                             [f'{recruit}_招聘职位量监测'])

    def test_recruitment_modules_are_registered_without_source_bindings(self):
        """v28：招聘职位量五卡不接入官方招聘站点——模块无外链，注册表无采集器，溯源表来源与网址留空。"""
        registry = {row['P号']: row for row in builder.REGISTRY}
        sources = {'P' + str(item['id']): item for item in builder.PROV}
        for pid in ('P83', 'P266', 'P267', 'P268', 'P269'):
            with self.subTest(pid=pid):
                self.assertEqual(registry[pid]['采集器'], '')
                self.assertEqual(registry[pid]['状态'], '入口/受限')
                self.assertEqual((sources[pid]['source'], sources[pid]['url']), ('', ''))
                card = next(c for c in builder.CARDS.values() if c['主数据'] == pid)
                self.assertNotIn('按钮', card)
                self.assertEqual(card['脚注'][0]['文本'], '')
                self.assertNotIn('<a ', builder.card_html(card))
        hr = next(p for p in builder.PAGES if p['ID'] == 'hr')
        refs = [row['引用'] for row in builder.read_layout(hr) if row['类型'] == 'C']
        self.assertEqual([r for r in refs if r.endswith('_招聘职位量监测')],
                         ['83_招聘职位量监测', '266_招聘职位量监测', '267_招聘职位量监测',
                          '268_招聘职位量监测', '269_招聘职位量监测'])
        self.assertEqual([r for r in refs if r.endswith('_大客户集中度')], [])

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
        self.assertEqual(len(planned), 16)
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
                 ('预留编号', 'M255'), ('预留编号', 'P999'),
                 ('预留编号', 255), ('预留编号', None)]
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
