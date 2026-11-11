# -*- coding: utf-8 -*-
"""P4同观测日/bp容差回归；全部网络为mock，CSV和状态只写临时目录。

运行：python -m unittest discover -s tests -p test_cross_check.py -v
"""
import contextlib
import csv
import importlib.util
import io
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / '看板数据固化' / '采集脚本' / 'cross_check.py'
SPEC = importlib.util.spec_from_file_location('cross_check_under_test', SCRIPT)
cc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cc)


class P4ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.base = pathlib.Path(self.temp)
        self.ledger = self.base / '宏观数据-P04-10年期美债收益率.csv'
        self.output = self.base / '交叉验证.csv'
        self.state = self.base / '核验状态.json'
        self.enterContext(mock.patch.object(cc.common, 'CSV_DIR', self.temp))
        self.enterContext(mock.patch.object(cc.common, 'TODAY', '2026-11-11'))
        self.enterContext(mock.patch.object(cc, 'CSV', str(self.output)))
        self.enterContext(mock.patch.object(cc, 'STATE', str(self.state)))
        self.enterContext(mock.patch.object(cc, 'CHECKS', []))
        self.enterContext(mock.patch.object(cc.time, 'sleep'))
        self.enterContext(mock.patch.object(cc.common, 'http_get', side_effect=AssertionError('禁止真实联网')))

    def write_ledger(self, observations):
        with self.ledger.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['数据日期', '数值', '单位', '数据来源', '备注'])
            writer.writeheader()
            for date, value in observations:
                writer.writerow({'数据日期': date, '数值': value, '单位': '%', '数据来源': 'mock财政部'})

    def run_mocked(self, fred_value=4.90, fred_date='2026-11-10', error=None):
        with mock.patch.object(cc, 'from_fred_at',
                               return_value=(fred_value, fred_date, f'FRED DGS10@{fred_date}'),
                               side_effect=error), contextlib.redirect_stdout(io.StringIO()):
            result = cc.run_checks()
        with self.output.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, cc.COLUMNS)  # 旧9列表头保持不变
            rows = list(reader)
        state = json.loads(self.state.read_text(encoding='utf-8'))
        return result, rows, state

    def test_same_observation_day_passes_with_dates_and_bp_metadata(self):
        self.write_ledger([('2026-11-10', 4.90)])
        result, rows, state = self.run_mocked()
        pair = state['对照']['P4']
        self.assertEqual(result[2]['通过'], 1)
        self.assertEqual(pair['结果'], '通过')
        self.assertEqual(pair['数据日期A'], pair['数据日期B'])
        self.assertEqual(pair['对照日期'], '2026-11-10')
        self.assertEqual((pair['容差'], pair['容差单位'], pair['偏差bp']), (1.0, 'bp', 0.0))
        self.assertIsNone(pair['阈值%'])
        self.assertIn('@2026-11-10', rows[0]['来源A'])
        self.assertIn('≤1bp', rows[0]['结论'])

    def test_exact_one_bp_is_inclusive_despite_float_rounding(self):
        self.write_ledger([('2026-11-10', 4.91)])
        result, _, state = self.run_mocked()
        self.assertEqual(result[2]['通过'], 1)
        self.assertEqual(state['对照']['P4']['偏差bp'], 1.0)

    def test_over_one_bp_warns_even_when_relative_difference_is_under_three_percent(self):
        self.write_ledger([('2026-11-10', 4.92)])
        result, rows, state = self.run_mocked()
        self.assertEqual(result[2]['通过'], 0)
        self.assertEqual(result[2]['偏差'], 1)
        self.assertEqual(state['对照']['P4']['偏差bp'], 2.0)
        self.assertLess(state['对照']['P4']['偏差%'], 3.0)
        self.assertTrue(rows[0]['结论'].startswith('偏差>1bp'))

    def test_fred_fallback_reloads_ledger_at_the_actual_observation_day(self):
        self.write_ledger([('2026-11-09', 4.90), ('2026-11-10', 5.00)])
        result, _, state = self.run_mocked(fred_date='2026-11-09')
        pair = state['对照']['P4']
        self.assertEqual(result[2]['通过'], 1)
        self.assertEqual(pair['值A'], 4.90)  # 必须重取9日，不能沿用10日的5.00
        self.assertEqual((pair['数据日期A'], pair['数据日期B']), ('2026-11-09', '2026-11-09'))
        self.assertEqual(pair['请求日期'], '2026-11-10')

    def test_missing_same_day_ledger_is_pending_even_when_cross_day_values_match(self):
        self.write_ledger([('2026-11-10', 4.90)])
        result, rows, state = self.run_mocked(fred_date='2026-11-09')
        pair = state['对照']['P4']
        self.assertEqual(result[2]['通过'], 0)
        self.assertEqual(result[2]['待对齐'], 1)
        self.assertTrue(pair['结果'].startswith('待对齐'))
        self.assertEqual((pair['数据日期A'], pair['数据日期B']), ('2026-11-10', '2026-11-09'))
        self.assertIsNone(pair['偏差bp'])
        self.assertIsNone(pair['偏差%'])
        self.assertEqual(rows[0]['差异'], '')
        self.assertEqual(pair['对照日期'], '')

    def test_official_fetch_failure_keeps_requested_date_and_never_passes(self):
        self.write_ledger([('2026-11-10', 4.90)])
        result, _, state = self.run_mocked(error=RuntimeError('官方源无观测'))
        self.assertEqual(result[2]['通过'], 0)
        self.assertEqual(result[2]['取数失败'], 1)
        pair = state['对照']['P4']
        self.assertEqual(pair['请求日期'], '2026-11-10')
        self.assertEqual(pair['数据日期B'], '')
        self.assertIn('B源失败', pair['结果'])

    def test_empty_ledger_is_recorded_as_fetch_failure(self):
        self.write_ledger([])
        result, _, state = self.run_mocked()
        self.assertEqual(result[2]['取数失败'], 1)
        self.assertIn('A源失败', state['对照']['P4']['结果'])

    def test_legacy_csv_history_and_other_state_sections_survive_upsert(self):
        self.write_ledger([('2026-11-10', 4.90)])
        legacy = {c: '' for c in cc.COLUMNS}
        legacy.update({'验证日期': '2026-10-23', '指标': 'P4 10年期美债(台账vsFRED)',
                       '值A': '4.8', '结论': '一致'})
        cc.common.write_csv_atomic(str(self.output), cc.COLUMNS, [legacy])
        self.state.write_text(json.dumps({'存疑': {'P30': {'说明': '保留'}}, '资讯': {'P14': {'级别': 'ok'}}}),
                              encoding='utf-8')
        _, rows, state = self.run_mocked()
        self.assertEqual(rows[0], legacy)
        self.assertEqual(len(rows), 2)
        self.assertEqual(state['存疑']['P30']['说明'], '保留')
        self.assertEqual(state['资讯']['P14']['级别'], 'ok')

    def test_market_threshold_logic_and_fetch_failure_still_work(self):
        checks = [
            ('P22', 'P22 mock低于阈值', 0.5, lambda: (100.4, 'A'), lambda: (100.0, 'B')),
            ('P23', 'P23 mock等于阈值', 0.5, lambda: (100.5, 'A'), lambda: (100.0, 'B')),
            ('P26', 'P26 mock取数失败', 1.0, mock.Mock(side_effect=RuntimeError('mock失败')),
             lambda: (100.0, 'B')),
        ]
        with mock.patch.object(cc, 'CHECKS', checks), mock.patch.object(cc, 'SPECIAL_CHECKS', []):
            result, _, state = self.run_mocked()
        self.assertEqual((result[2]['通过'], result[2]['偏差'], result[2]['取数失败']), (1, 1, 1))
        self.assertEqual(state['对照']['P22']['结果'], '通过')
        self.assertEqual(state['对照']['P23']['结果'], '偏差>0.5%')
        self.assertEqual(state['对照']['P22']['容差单位'], '%')


class FredObservationTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(sys.modules, {'_keys': types.SimpleNamespace(FRED_API_KEY='mock-key')}))

    def test_returns_actual_date_and_bounds_the_historical_api_query(self):
        body = {'observations': [{'date': '2020-01-08', 'value': '9.99'},
                                 {'date': '2020-01-07', 'value': '.'},
                                 {'date': '2020-01-06', 'value': '1.81'}]}
        with mock.patch.object(cc.common, 'http_get', return_value=json.dumps(body)) as fetch:
            value, date, source = cc.from_fred_at('DGS10', '2020-01-07')
        self.assertEqual((value, date, source), (1.81, '2020-01-06', 'FRED DGS10@2020-01-06'))
        url = fetch.call_args.args[0]
        self.assertIn('observation_start=2020-01-02', url)
        self.assertIn('observation_end=2020-01-07', url)

    def test_no_valid_observation_in_window_raises_instead_of_using_another_day(self):
        body = {'observations': [{'date': '2020-01-07', 'value': '.'},
                                 {'date': '2020-01-06', 'value': 'NaN'},
                                 {'date': '2020-01-01', 'value': '1.81'}]}
        with mock.patch.object(cc.common, 'http_get', return_value=json.dumps(body)):
            with self.assertRaisesRegex(RuntimeError, '无 .*有效观测'):
                cc.from_fred_at('DGS10', '2020-01-07')

    def test_http_error_redacts_api_key(self):
        with mock.patch.object(cc.common, 'http_get', side_effect=RuntimeError('URL api_key=mock-key')):
            with self.assertRaises(RuntimeError) as result:
                cc.from_fred_at('DGS10', '2020-01-07')
        self.assertNotIn('mock-key', str(result.exception))


if __name__ == '__main__':
    unittest.main()
