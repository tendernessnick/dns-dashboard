"""译题质量离线回归，不调用采集器/真实翻译端点，不写生产数据。"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / '看板数据固化' / '采集脚本'
sys.path.insert(0, str(SCRIPTS))
import _news_translation as quality
import _news_common as news


class OfflineQualityTests(unittest.TestCase):
    def test_entities_whitespace_and_original_chinese_author_are_preserved(self):
        self.assertEqual(quality.normalize_title('  A&amp;amp;B\xa0  grows 5％ '), 'A&B grows 5%')
        source = '张三：Apple 新品销量增长 5%'
        result = quality.resolve_cached_title(source, '删除作者后的改写')
        self.assertEqual(result['status'], 'original')
        self.assertEqual(result['title_zh'], '')
        self.assertEqual(source, '张三：Apple 新品销量增长 5%')

    def test_general_terms_and_precision_are_protected_not_whole_titles(self):
        source = 'Nvidia rises 5% after Q3 report'
        protected = quality.protect_title(source)
        self.assertNotIn('Nvidia', protected.request_text)
        self.assertNotIn('5%', protected.request_text)
        self.assertNotIn('Q3', protected.request_text)
        tokens = dict((display, token) for token, display in protected.tokens)
        raw = tokens['英伟达'] + '在' + tokens['Q3'] + '财报后上涨' + tokens['5%']
        restored, errors = quality.restore_tokens(raw, protected)
        self.assertEqual(errors, [])
        self.assertEqual(quality.review_translation(source, restored)['title_zh'], '英伟达在Q3财报后上涨5%')
        self.assertEqual(quality.restore_tokens('无标记的译文', protected)[1], ['protected_token_lost'])

    def test_currency_magnitude_and_decimal_equivalence(self):
        source = "China's goods surplus tops $1 trillion"
        good = '中国商品贸易顺差超过1万亿美元'
        self.assertEqual(quality.review_translation(source, good)['status'], 'translated')
        for bad in ['中国商品贸易顺差超过1万$', '中国商品贸易顺差超过1万亿元', '中国商品贸易顺差超过1亿美元']:
            self.assertIn('quantity_or_unit_changed', quality.review_translation(source, bad)['issues'])
        self.assertEqual(quality.quantity_fingerprint('165,000'), quality.quantity_fingerprint('16.5万'))

    def test_percent_sign_negative_direction_and_negation_cannot_change(self):
        self.assertEqual(quality.review_translation('Prices rose 0.4%', '价格上涨0.4%')['status'], 'translated')
        for candidate in ['价格上涨4%', '价格上涨0.4', '价格下跌0.4%']:
            self.assertEqual(quality.review_translation('Prices rose 0.4%', candidate)['status'], 'needs_review')
        self.assertIn('quantity_or_unit_changed', quality.review_translation('Return is -0.4%', '回报为0.4%')['issues'])
        self.assertIn('quantity_or_unit_changed', quality.review_translation('Return is +0.4%', '回报为0.4%')['issues'])
        self.assertEqual(quality.quantity_fingerprint('-$1 million'), quality.quantity_fingerprint('-100万美元'))
        self.assertNotEqual(quality.quantity_fingerprint('Charging at 5V'), quality.quantity_fingerprint('充电电压为5A'))
        self.assertIn('negation_missing', quality.review_translation('Fed will not hike', '美联储将加息')['issues'])

    def test_known_mistranslated_domain_terms_are_rejected(self):
        self.assertTrue(quality.review_translation('Low-fire trend continues', '低火趋势持续')['issues'])
        self.assertEqual(quality.review_translation('Low-fire trend continues', '低裁员趋势持续')['status'], 'translated')
        self.assertTrue(quality.review_translation('Consumer measure slows', '消费者措施放缓')['issues'])
        self.assertEqual(quality.review_translation('Consumer measure slows', '消费端指标放缓')['status'], 'translated')
        self.assertIn('decade_not_preserved', quality.review_translation('Since the 1960s', '自1960年以来')['issues'])

    def test_listicle_readability_rejects_stray_digits_and_strength_mistranslation(self):
        source = '3 unexpected reasons the October jobs report was so strong'
        bad = '3由于意外原因，10月就业报告非常强烈'
        issues = quality.review_translation(source, bad)['issues']
        self.assertIn('stray_number_before_connector', issues)
        self.assertIn('unnatural_financial_collocation', issues)
        self.assertEqual(quality.review_translation(source, '10月就业报告如此强劲的3个意外原因')['status'], 'translated')
        other = quality.review_translation('5 reasons the earnings report was robust', '5但是财报十分激烈')
        self.assertIn('stray_number_before_connector', other['issues'])
        self.assertIn('unnatural_financial_collocation', other['issues'])
        self.assertEqual(quality.review_translation('Demand was strong', '需求强烈')['status'], 'translated')

    def test_context_specific_financial_and_airline_terms_do_not_change_claims(self):
        stock = 'Stocks making the biggest moves: Nvidia and more'
        self.assertIn('undirected_move_changed_to_directional_ranking', quality.review_translation(stock, '涨幅最大的股票：英伟达等')['issues'])
        self.assertEqual(quality.review_translation(stock, '波动最大的股票：英伟达等')['status'], 'translated')
        self.assertIn('central_bank_board_mistranslated', quality.review_translation("Board's discount rate meetings", '董事会贴现率会议')['issues'])
        self.assertEqual(quality.review_translation("Board's discount rate meetings", '理事会贴现率会议')['status'], 'translated')
        self.assertEqual(quality.review_translation('The company Board met', '公司董事会召开会议')['status'], 'translated')
        airline = 'JetBlue bets on premium to return to profitability'
        self.assertIn('airline_premium_mistranslated', quality.review_translation(airline, '捷蓝航空押注溢价以恢复盈利')['issues'])
        self.assertEqual(quality.review_translation(airline, '捷蓝航空押注高端服务以恢复盈利')['status'], 'translated')
        self.assertEqual(quality.review_translation('Shares trade at a premium', '股票以溢价交易')['status'], 'translated')
        rebuttal = "JetBlue's CEO pushed back on creditor fears"
        self.assertIn('rebuttal_changed_to_resolved_concern', quality.review_translation(rebuttal, '捷蓝航空的CEO已打消债权人的担忧')['issues'])
        self.assertEqual(quality.review_translation(rebuttal, '捷蓝航空的CEO驳斥了债权人的担忧')['status'], 'translated')

    def test_chinese_dates_cannot_end_as_dangling_or_inverted_year(self):
        title = 'Minutes of the meeting on October 17, 2026'
        self.assertEqual(quality.review_translation(title, '2026年10月17日会议纪要')['status'], 'translated')
        for bad in ['10月17日会议纪要，2026', '10月17日2026年会议纪要', '2026年10月17会议纪要']:
            self.assertEqual(quality.review_translation(title, bad)['status'], 'needs_review')
        self.assertIn('incomplete_or_inverted_chinese_date', quality.review_translation(title, '10月17日会议纪要，2026')['issues'])

    def test_abbreviation_equivalents_accept_chinese_without_losing_quarter_identity(self):
        cases = [('CEO discusses AI', '首席执行官讨论人工智能'),
                 ('Q3 report', '第三季度报告'), ('Q3 report', '第3季度报告'),
                 ('2026Q3 report', '2026年第三季度报告'),
                 ('ECB statement', '欧洲央行声明'), ('FOMC statement', '联邦公开市场委员会声明')]
        for source, candidate in cases:
            with self.subTest(source=source, candidate=candidate):
                self.assertEqual(quality.review_translation(source, candidate)['status'], 'translated')
        self.assertIn('abbreviation_not_preserved:Q3', quality.review_translation('Q3 report', '第四季度报告')['issues'])

    def test_legacy_empty_bad_and_version_changed_cache_do_not_become_current_hits(self):
        title = 'Prices rose 0.4%'
        legacy = {title: '价格上涨4%'}
        result = quality.resolve_cached_title(title, cache=legacy)
        self.assertEqual(result['title_zh'], '')
        self.assertEqual(result['cache_state'], 'legacy')
        cache = {}
        entry = quality.review_translation(title, '价格上涨0.4%', provider='test')
        quality.store_cache_result(cache, title, entry)
        self.assertEqual(quality.resolve_cached_title(title, cache=cache)['cache_state'], 'current')
        cache[quality.CACHE_META_KEY]['entries'][title]['version'] = 'old-version'
        self.assertTrue(quality.resolve_cached_title(title, cache=cache)['needs_refresh'])
        cache_before = json.dumps(cache, sort_keys=True)
        quality.store_cache_result(cache, title, quality.review_translation(title, ''))
        self.assertEqual(json.dumps(cache, sort_keys=True), cache_before)

    def test_candidate_cache_schema_and_source_hash_are_checked(self):
        title = 'Prices rose 0.4%'
        entry = quality.review_translation(title, '价格上涨0.4%', provider='test')
        cache = {'schema_version': 2, 'entries': {title: entry}}
        self.assertEqual(quality.resolve_cached_title(title, cache=cache)['cache_state'], 'current')
        cache['entries'][title]['source_hash'] = 'wrong-source'
        self.assertNotEqual(quality.resolve_cached_title(title, cache=cache)['cache_state'], 'current')

    def test_pure_module_has_no_network_or_collector_imports(self):
        code = "import sys;sys.path.insert(0,sys.argv[1]);import _news_translation;assert not any(x in sys.modules for x in ['requests','common','_news_common'])"
        subprocess.run([sys.executable, '-B', '-c', code, str(SCRIPTS)], check=True, capture_output=True)

    def test_candidate_tool_is_offline_by_default_and_never_overwrites_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source.json'
            output = Path(tmp) / 'candidates.json'
            content = {'items': [{'title': 'Prices rose 0.4%', 'title_zh': '价格上涨4%', 'url': 'https://example.invalid/news'}]}
            source.write_text(json.dumps(content), encoding='utf-8')
            before = source.read_bytes()
            command = [sys.executable, '-B', '-X', 'utf8', str(SCRIPTS / '生成_译题候选.py'),
                       '--input', str(source), '--output', str(output)]
            subprocess.run(command, check=True, capture_output=True)
            result = json.loads(output.read_text(encoding='utf-8'))
            self.assertFalse(result['network_allowed'])
            self.assertEqual(result['schema_version'], 2)
            self.assertEqual(result['entries']['Prices rose 0.4%']['title_zh'], '')
            self.assertEqual(source.read_bytes(), before)
            again = subprocess.run(command, capture_output=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(source.read_bytes(), before)


class ProviderValidationTests(unittest.TestCase):
    def response(self, data, status=200, content_type='application/json'):
        response = mock.Mock(status_code=status, headers={'Content-Type': content_type})
        response.json.return_value = data
        return response

    def test_http_business_quota_and_html_errors_are_not_cached(self):
        title = 'Prices rose 0.4%'
        failures = [self.response({}, 429), self.response({'responseStatus': 403, 'responseData': {'translatedText': '配额已用尽'}}),
                    self.response({}, content_type='text/html')]
        for failure in failures:
            with self.subTest(failure=failure), mock.patch.object(news.common._SESSION, 'get', return_value=failure):
                cache = {}
                result = news.translate_title_result(title, cache, allow_network=True)
                self.assertEqual(result['status'], 'needs_review')
                self.assertEqual(cache, {})
        self.assertEqual(quality.review_translation(title, 'MYMEMORY WARNING: 配额已用尽')['status'], 'needs_review')

    def test_legacy_does_not_skip_network_but_current_good_cache_does(self):
        title = 'Prices rose 0.4%'
        token = quality.protect_title(title).tokens[0][0]
        response = self.response({'responseStatus': 200, 'responseData': {'translatedText': '价格上涨' + token}})
        cache = {title: '错误旧译'}
        with mock.patch.object(news.common._SESSION, 'get', return_value=response) as request:
            result = news.translate_title_result(title, cache, allow_network=True)
            self.assertEqual(result['title_zh'], '价格上涨0.4%')
            self.assertEqual(request.call_count, 1)
        with mock.patch.object(news.common._SESSION, 'get', side_effect=AssertionError('must not call')):
            self.assertEqual(news.translate_title_result(title, cache, allow_network=True)['title_zh'], result['title_zh'])

    def test_default_structured_api_is_offline(self):
        with mock.patch.object(news.common._SESSION, 'get', side_effect=AssertionError('must not call')):
            self.assertEqual(news.translate_title_result('Prices rose 0.4%', {})['status'], 'needs_review')

    def test_bad_new_candidate_retains_quality_passed_existing_with_honest_provider(self):
        title = '3 unexpected reasons the October jobs report was so strong'
        existing = '10月就业报告如此强劲的3个意外原因'
        protected = quality.protect_title(title)
        values = {display: token for token, display in protected.tokens}
        bad = values['3'] + '由于意外原因，' + values['10月'] + values['就业报告'] + '非常强烈'
        with mock.patch.object(news, '_provider_response', return_value=bad):
            result = news.translate_title_result(title, {}, allow_network=True, existing_title_zh=existing)
        self.assertEqual(result['title_zh'], existing)
        self.assertTrue(result['quality_passed'])
        self.assertEqual(result['provider'], 'existing_reviewed')
        self.assertTrue(result['retained_existing'])

    def test_oversized_request_is_not_silently_truncated(self):
        with mock.patch.object(news.common._SESSION, 'get', side_effect=AssertionError('must not call')):
            with self.assertRaisesRegex(ValueError, 'too_long'):
                news._provider_response('mymemory', 'x' * 451)


if __name__ == '__main__':
    unittest.main()
