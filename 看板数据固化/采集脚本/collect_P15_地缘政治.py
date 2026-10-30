# -*- coding: utf-8 -*-
"""P15 地缘政治动态：CNBC World RSS → 资讯数据/地缘政治.json（仅保留最近7天）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _news_common import fetch_rss, parse_items, save_news

PID, TITLE = 15, '地缘政治动态'
FEEDS = [
    ('https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362', 'CNBC World'),
    ('https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910', 'CNBC Geopolitics'),
]


def run():
    try:
        items = []
        used = ''
        for url, name in FEEDS:
            try:
                items = parse_items(fetch_rss(url))
                if items:
                    used = name
                    break
            except Exception:
                continue
        if not items:
            raise RuntimeError('全部RSS通道失败')
        n = save_news('地缘政治.json', used, items)
        detail = f'{used} RSS · 近7天保留{n}条'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))