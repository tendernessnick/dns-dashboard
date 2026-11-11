"""资讯关键词离线回归；所有采集入口均隔离网络及生产数据写入。"""
import contextlib
import csv
import datetime
import importlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / '看板数据固化' / '采集脚本'
sys.path.insert(0, str(SCRIPTS))
import _news_common as news


COLLECTORS = [importlib.import_module(name) for name in (
    'collect_P41_Apple新闻', 'collect_P42_手机新品', 'collect_P59_充电头网早报',
    'collect_P61_苹果AVS资讯', 'collect_P90b_非上市同业新闻',
)]


class KeywordConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / '关键词表.csv'
        patcher = mock.patch.object(news, 'KEYWORDS_FILE', str(self.path))
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_rows(self, rows, fields=('P号', '层级', '词')):
        with self.path.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(fields)
            writer.writerows(rows)

    def assert_fallback(self, reason):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            keys = news.load_keys('P41', fallback=['原关注词'])
        self.assertEqual(keys['core'], ['原关注词'])
        self.assertEqual(keys['exclude'], [])
        self.assertIn(reason, out.getvalue())
        detail = news.keys_detail(keys, '近7天1条')
        self.assertTrue(detail.startswith('关键词回退[P41]'))
        self.assertIn(reason, detail)
        return keys

    def test_pids_accept_prefix_case_suffix_and_leading_zeros(self):
        self.write_rows([['p090B', '核心', '专属词'], ['P59', '核心', '早报']])
        for pid in ('90b', 'P90b', 'P90B', ' p090b '):
            with self.subTest(pid=pid):
                self.assertEqual(news.load_keys(pid), {'core': ['专属词'], 'exclude': []})
        for pid in (59, '59', 'P59', 'p059'):
            with self.subTest(pid=pid):
                self.assertEqual(news.load_keys(pid)['core'], ['早报'])

    def test_core_and_exclude_apply_case_insensitively_to_both_matchers(self):
        self.write_rows([['P41', '核心', 'Apple'], ['P41', '排除', '广告']])
        keys = news.load_keys(41)
        self.assertTrue(news.keymatch('APPLE 新品', keys))
        self.assertFalse(news.keymatch('Apple 广告', keys))
        self.assertFalse(news.keymatch('完全无关的报道', keys))
        xml = ''.join(f'<item><title>{title}</title><link>https://test.invalid/{i}</link></item>'
                      for i, title in enumerate(('APPLE 新品', 'Apple 广告', '完全无关的报道')))
        drops = []
        picked = news.parse_items(xml, keywords=keys['core'], exclude=keys['exclude'], _drop=drops)
        self.assertEqual([title for _, title, _ in picked], ['APPLE 新品'])
        self.assertEqual(len(drops), 2)

    def test_only_excludes_does_not_require_a_core_match(self):
        self.write_rows([['P41', '排除', '广告']])
        keys = news.load_keys('P41')
        self.assertEqual(keys['core'], [])
        self.assertTrue(news.keymatch('任意产品新闻', keys))
        self.assertFalse(news.keymatch('任意产品广告', keys))
        xml = '<item><title>任意产品新闻</title><link>https://test.invalid/1</link></item>'
        self.assertEqual(len(news.parse_items(xml, keywords=keys['core'] or None,
                                             exclude=keys['exclude'] or None)), 1)

    def test_intentional_trailing_space_is_retained(self):
        self.write_rows([['P41', '核心', ' mac '], ['P41', '核心', 'ios ']])
        keys = news.load_keys('P41')
        self.assertEqual(keys['core'], ['mac ', 'ios '])
        self.assertTrue(news.keymatch('Mac 新品', keys))
        self.assertFalse(news.keymatch('macaron 食谱', keys))
        self.assertFalse(news.keymatch('IOSurface 图像', keys))

    def test_existing_csv_and_all_five_fallback_scopes_are_identical(self):
        with mock.patch.object(news, 'KEYWORDS_FILE', str(SCRIPTS.parent / '关键词表.csv')):
            for collector in COLLECTORS:
                with self.subTest(pid=collector.PID):
                    self.assertEqual(news.load_keys(collector.PID),
                                     {'core': collector.KEYS, 'exclude': []})

    def test_missing_file_reports_reason_and_uses_fallback(self):
        self.assert_fallback('词表文件缺失')

    def test_legacy_no_fallback_call_returns_none_with_visible_reason(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertIsNone(news.load_keys('P41'))
        self.assertIn('词表文件缺失', out.getvalue())

    def test_missing_pid_reports_reason(self):
        self.write_rows([['P59', '核心', '早报']])
        self.assert_fallback('无该P号有效配置')

    def test_invalid_pid_reports_reason(self):
        self.write_rows([['P41', '核心', 'Apple']])
        with contextlib.redirect_stdout(io.StringIO()):
            keys = news.load_keys('P?', fallback=['原关注词'])
        self.assertIn('P号格式无效', keys['_fallback'])

    def test_malformed_headers_rows_and_levels_fall_back(self):
        cases = (
            ('P号,词\nP41,Apple\n', '表头'),
            ('P号,层级,词,词\nP41,核心,Apple,苹果\n', '表头'),
            ('P号,层级,词\nP41,核心,Apple,多余一列\n', '列数不符'),
            ('P号,层级,词\nP41,核心\n', '列数不符'),
            ('P号,层级,词\nP41,关注,Apple\n', '层级'),
            ('P号,层级,词\nP41,核心, \n', '关键词为空'),
            ('P号,层级,词\nP41,核心,"Apple\n', 'unexpected end of data'),
        )
        for content, reason in cases:
            with self.subTest(reason=reason, content=content):
                self.path.write_text(content, encoding='utf-8-sig')
                self.assert_fallback(reason)

    def test_bad_encoding_reports_fallback(self):
        self.path.write_bytes(b'\xff\xfeinvalid')
        self.assert_fallback('codec')

    def test_normal_external_config_does_not_emit_fallback_notice(self):
        self.write_rows([['P41', '核心', 'Apple']])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            keys = news.load_keys('P41', fallback=['原关注词'])
        self.assertEqual(out.getvalue(), '')
        self.assertEqual(news.keys_detail(keys, '正常详情'), '正常详情')

    def test_all_five_consumer_entries_use_external_core_and_exclude(self):
        # 调用真实run，但以fixture替代所有HTTP/图文写入/JSON写入；不触碰生产数据。
        self.write_rows([[f'P{collector.PID}', level, word]
                         for collector in COLLECTORS
                         for level, word in (('核心', '独立配置'), ('排除', '广告'))])
        now = datetime.datetime.now(datetime.timezone.utc)
        candidates = [(now, title, f'https://test.invalid/{i}') for i, title in enumerate(
            ('独立配置新品', '独立配置广告', '完全不相关'))]
        good_url = candidates[0][2]
        xml = ''.join(f'<item><title>{title}</title><link>{url}</link></item>'
                      for _, title, url in candidates)
        for collector in COLLECTORS:
            with self.subTest(pid=collector.PID), contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(sys, 'argv', ['offline-test']))
                audit = stack.enter_context(mock.patch.object(collector, 'audit_discards'))
                if hasattr(collector, 'DST'):
                    stack.enter_context(mock.patch.object(collector, 'DST', self.tmp.name))
                    stack.enter_context(mock.patch.object(collector.art, 'scan_existing',
                                                         return_value={good_url: {}}))
                if hasattr(collector, 'fetch_rss'):
                    stack.enter_context(mock.patch.object(collector, 'fetch_rss', return_value=xml))
                    article = stack.enter_context(mock.patch.object(collector, 'fetch_ithome_article'))
                else:
                    stack.enter_context(mock.patch.object(collector, 'fetch_ctw', return_value='fixture'))
                    stack.enter_context(mock.patch.object(collector, 'parse_ctw', return_value=candidates))
                if hasattr(collector, 'merge_rolling'):
                    merge = stack.enter_context(mock.patch.object(collector, 'merge_rolling',
                                                                  return_value=(1, 1)))
                status, detail = collector.run()
                self.assertEqual(status, '成功')
                self.assertNotIn('关键词回退', detail)
                if hasattr(collector, 'fetch_rss'):
                    article.assert_not_called()
                    self.assertEqual({item[2] for item in audit.call_args.args[1]},
                                     {candidates[1][2], candidates[2][2]})
                else:
                    self.assertEqual(audit.call_args.args[2], {good_url})
                    if hasattr(collector, 'merge_rolling'):
                        self.assertEqual(merge.call_args.args[2], [candidates[0]])

    def test_all_five_consumer_entries_keep_fallback_reason_in_result(self):
        # 缺词表时即便没有新文章，返回详情仍须携带原因，不能只打印后被run_all吞掉。
        for collector in COLLECTORS:
            with self.subTest(pid=collector.PID), contextlib.ExitStack() as stack:
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                stack.enter_context(mock.patch.object(sys, 'argv', ['offline-test']))
                stack.enter_context(mock.patch.object(collector, 'audit_discards'))
                if hasattr(collector, 'DST'):
                    stack.enter_context(mock.patch.object(collector, 'DST', self.tmp.name))
                    stack.enter_context(mock.patch.object(collector.art, 'scan_existing', return_value={}))
                if hasattr(collector, 'fetch_rss'):
                    stack.enter_context(mock.patch.object(collector, 'fetch_rss', return_value='<rss/>'))
                else:
                    stack.enter_context(mock.patch.object(collector, 'fetch_ctw', return_value='fixture'))
                    stack.enter_context(mock.patch.object(collector, 'parse_ctw', return_value=[]))
                if hasattr(collector, 'merge_rolling'):
                    stack.enter_context(mock.patch.object(collector, 'merge_rolling', return_value=(0, 0)))
                _status, detail = collector.run()
                self.assertTrue(detail.startswith('关键词回退['))
                self.assertIn('词表文件缺失', detail)


if __name__ == '__main__':
    unittest.main()
