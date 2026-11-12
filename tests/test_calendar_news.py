"""议息相关新闻：离线验证主题、原文链接、日期窗口与保留日历。"""
import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'calendar_news', ROOT / '看板数据固化' / '采集脚本' / 'collect_P16_议息日历.py')
CALENDAR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CALENDAR)


def rss(items):
    from xml.sax.saxutils import escape
    return '<rss><channel>' + ''.join(
        '<item>' + ''.join(f'<{key}>{escape(value)}</{key}>' for key, value in item.items()) + '</item>'
        for item in items) + '</channel></rss>'


class CalendarNewsTests(unittest.TestCase):
    def setUp(self):
        today = mock.patch.object(CALENDAR, 'TODAY', datetime.date(2026, 11, 12))
        today.start()
        self.addCleanup(today.stop)

    def test_official_items_require_recent_date_topic_and_article_link(self):
        item = {'title': 'Monetary policy decisions', 'pubDate': 'Thu, 29 Oct 2026 14:15:00 +0100',
                'link': 'https://www.ecb.europa.eu//press/pr/date/2026/html/ecb.mp261029.en.html'}
        data = rss([item, item,
                    {**item, 'pubDate': 'Wed, 1 Jul 2026 12:00:00 GMT'},
                    {**item, 'pubDate': 'Fri, 13 Nov 2026 12:00:00 GMT'},
                    {**item, 'link': 'https://example.com/press/fake.html'},
                    {**item, 'link': 'https://www.ecb.europa.eu/'},
                    {**item, 'title': 'ECB consolidated banking data'},
                    {**item, 'title': 'Decisions taken (in addition to decisions setting interest rates)'}])
        found = CALENDAR.parse_policy_feed(data, 'P20')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['title'], item['title'])
        self.assertEqual(found[0]['iso'], '2026-10-29')
        self.assertEqual(found[0]['url'], item['link'].replace('.europa.eu//', '.europa.eu/'))

    def test_fallback_requires_bank_and_explicit_policy_topic(self):
        self.assertTrue(CALENDAR._news_relevant('P16', 'Fed considers another rate cut'))
        self.assertFalse(CALENDAR._news_relevant('P16', "CPI complicates Fed's inflation fight"))
        self.assertFalse(CALENDAR._news_relevant('P20', 'Fed monetary policy statement'))
        self.assertFalse(CALENDAR._news_relevant('P20', 'ECB non-monetary policy decisions'))

    def test_empty_or_failed_feed_keeps_truthful_status_and_no_invented_news(self):
        feed = rss([{'title': 'Monetary policy decisions', 'pubDate': 'Wed, 1 Jul 2026 12:00:00 GMT',
                     'link': 'https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp260701.en.html'}])
        with mock.patch.object(CALENDAR, '_get', return_value=feed), mock.patch.object(CALENDAR, '_fallback_news', return_value=[]):
            result = CALENDAR.collect_news('P20')
        self.assertEqual(result['相关新闻'], [])
        self.assertEqual(result['资讯采集']['状态'], '静默')
        previous = {'相关新闻': [{'title': 'Federal Reserve issues FOMC statement', 'iso': '2026-10-28',
                                 'url': 'https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm'}],
                    '资讯采集': {'抓取时间': '2026-11-10T00:00:00+00:00'}}
        with mock.patch.object(CALENDAR, '_get', side_effect=RuntimeError('network unavailable')):
            result = CALENDAR.collect_news('P16', previous)
        self.assertEqual(result['相关新闻'], previous['相关新闻'])
        self.assertEqual(result['资讯采集']['状态'], '失败')
        self.assertEqual(result['资讯采集']['沿用抓取时间'], previous['资讯采集']['抓取时间'])

    def test_news_only_preserves_all_calendar_fields(self):
        data = {'updated': '2026-11-11', 'custom': 'keep',
                'P16': {'时间线': [{'日期': '12-08/09'}], '说明': '既有决议'},
                'P20': {'时间线': [{'日期': '12-16/17'}], '说明': '既有ECB决议'}}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'calendar.json'
            out.write_text(json.dumps(data), encoding='utf-8')
            with mock.patch.object(CALENDAR, 'OUT', str(out)), mock.patch.object(
                    CALENDAR, 'collect_news', return_value={'相关新闻': [], '资讯采集': {'状态': '静默'}}):
                self.assertEqual(CALENDAR.refresh_news_only()[0], '成功')
            after = json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(after['updated'], data['updated'])
        self.assertEqual(after['custom'], data['custom'])
        for pid in ['P16', 'P20']:
            self.assertEqual(after[pid]['时间线'], data[pid]['时间线'])
            self.assertEqual(after[pid]['说明'], data[pid]['说明'])

    def test_refresh_preserves_translation_only_for_same_article_and_original_title(self):
        title = 'Federal Reserve issues FOMC statement'
        url = 'https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm'
        feed = rss([{'title': title, 'link': url, 'pubDate': 'Wed, 28 Oct 2026 18:00:00 GMT'}])
        previous = {'相关新闻': [{'title': title, 'url': url, 'title_zh': '人工校译标题'}]}
        with mock.patch.object(CALENDAR, '_get', return_value=feed):
            result = CALENDAR.collect_news('P16', previous)
        self.assertEqual(result['相关新闻'][0]['title_zh'], '人工校译标题')
        self.assertEqual(result['相关新闻'][0]['title'], title)
        previous['相关新闻'][0]['title'] = 'Different original title'
        with mock.patch.object(CALENDAR, '_get', return_value=feed):
            result = CALENDAR.collect_news('P16', previous)
        self.assertNotEqual(result['相关新闻'][0]['title_zh'], '人工校译标题')


if __name__ == '__main__':
    unittest.main()
