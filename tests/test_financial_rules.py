# -*- coding: utf-8 -*-
"""财报区间和累计口径离线回归；只向临时目录写入，不访问外部数据源。"""
import csv
import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / '看板数据固化'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rules = load_module('financial_range_rules', ROOT / 'docs/数据治理/工具/合理区间推导.py')
common = load_module('financial_range_common', FIX / '采集脚本/common.py')


class FinancialRulesTests(unittest.TestCase):
    def setUp(self):
        with (FIX / '词条注册表.csv').open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        self.registry = {r['P号']: r for r in rows}
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.block_network = mock.patch(
            'requests.sessions.Session.request',
            side_effect=AssertionError('离线回归禁止网络请求'),
        )
        self.block_network.start()
        self.addCleanup(self.block_network.stop)
        self.old_cache = common._RANGE_CACHE
        common._RANGE_CACHE = None
        self.addCleanup(setattr, common, '_RANGE_CACHE', self.old_cache)
        common.pop_suspects()
        self.addCleanup(common.pop_suspects)

    def test_growth_is_soft_even_when_it_is_the_primary_column(self):
        for pid, col in [('P5', '同比%'), ('P6', '环比%'), ('P71', '通讯器材类同比%'),
                         ('P201', '营收同比%'), ('P202', '净利同比%'), ('P45', '销量增速%')]:
            with self.subTest(pid=pid, col=col):
                self.assertIsNone(rules.col_reject(pid, col, col, (-10, 100)))
                spec = rules.col_spec(pid, col, (-10, 100))
                self.assertIn('[疑]' + col + '=', spec)
                self.assertNotIn('[拒]', spec)

    def test_first_loss_is_not_rejected_from_positive_history(self):
        for pid in rules.FINANCIAL_PIDS:
            with self.subTest(pid=pid):
                self.assertIsNone(rules.col_reject(pid, '净利亿元', '营收亿元', (0.24, 4.65)))
                spec = self.registry[pid]['合理区间']
                self.assertNotIn('[拒]净利亿元=', spec)
                self.assertIn('[疑]净利亿元=', spec)
                self.assertNotIn('[拒]营收同比%=', spec)
                self.assertNotIn('[拒]净利同比%=', spec)
                self.assertIn('年初至报告期累计', self.registry[pid]['口径说明'])

    def test_real_financial_history_passes_hard_checks(self):
        checked = 0
        for pid in sorted(rules.FINANCIAL_PIDS):
            path, = (FIX / 'CSV数据').glob('*-' + pid + '-*.csv')
            with path.open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                with self.subTest(pid=pid, date=row['数据日期']):
                    flags = common.verify_row(str(path), row, [], row['数据日期'], mutation=False)
                    self.assertFalse([x for x in flags if x[0] == 'REJECT'], flags)
            checked += len(rows)
        self.assertGreaterEqual(checked, 60)

    def test_small_base_growth_and_loss_are_saved_with_warning(self):
        path = self.work / '竞对同业-P201-离线测试.csv'
        cols = ['数据日期', '营收亿元', '营收同比%', '净利亿元', '净利同比%']
        values = {'营收亿元': 137.34, '营收同比%': 164.71,
                  '净利亿元': -0.5, '净利同比%': -474.38}
        common.save_row(str(path), datetime.date.today().isoformat(), values, cols)
        with path.open(encoding='utf-8-sig', newline='') as f:
            row, = list(csv.DictReader(f))
        self.assertEqual(float(row['营收同比%']), 164.71)
        self.assertEqual(float(row['净利亿元']), -0.5)
        warnings = ';'.join(common.pop_suspects())
        self.assertIn('净利亿元', warnings)
        self.assertIn('净利同比%', warnings)

    def test_hard_revenue_bound_still_protects_existing_csv(self):
        path = self.work / '竞对同业-P201-离线测试.csv'
        cols = ['数据日期', '营收亿元', '营收同比%', '净利亿元', '净利同比%']
        date = datetime.date.today().isoformat()
        common.save_row(str(path), date,
                        {'营收亿元': 137.34, '营收同比%': 164.71,
                         '净利亿元': 0.24, '净利同比%': -93.39}, cols)
        before = path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, '拒绝写入'):
            common.save_row(str(path), date, {'营收亿元': 999999}, cols)
        self.assertEqual(path.read_bytes(), before)

    def test_crowdfunding_overfunding_stays_valid_and_share_bound_remains(self):
        self.assertEqual(rules.col_reject('P93', '达成率%', '排名', (117, 34500)), (0, 500000))
        self.assertEqual(rules.col_reject('P94', '达成率%', '排名', (0.6, 396700)), (0, 500000))
        self.assertEqual(rules.col_reject('P49', '苹果%', '三星%', (17, 25)), (-1, 101))

    def test_company_cards_expose_cumulative_period_without_previous_delta(self):
        for pid in sorted(rules.FINANCIAL_PIDS):
            path, = (ROOT / '看板/模块').glob(pid[1:] + '_*.json')
            with path.open(encoding='utf-8') as f:
                card = json.load(f)
            with self.subTest(pid=pid):
                self.assertIn('年初累计', card['卡名'])
                self.assertNotIn('季度', card['卡名'])
                self.assertIs(card['显示前值变化'], False)
                self.assertIn('{期间}', card['动态副标题'])
                self.assertIn('跨年重置', card['动态副标题'])


if __name__ == '__main__':
    unittest.main()
