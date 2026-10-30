# -*- coding: utf-8 -*-
"""P42 手机厂家新品发布：IT之家RSS关键词过滤 → 资讯数据/手机新品.json（仅保留最近7天）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _news_common import fetch_rss, parse_items, save_news

PID, TITLE = 42, '手机厂家新品发布'
KEYS = ['手机', '旗舰', '快充', '充电', '电池', '发布', '首发', '折叠屏',
        'iphone', 'galaxy', '小米', '华为', 'oppo', 'vivo', '荣耀', '一加', '真我']
FEEDS = [
    ('https://www.ithome.com/rss/', 'IT之家（关键词过滤）'),
]


def run():
    try:
        items, used = [], ''
        for url, name in FEEDS:
            try:
                its = parse_items(fetch_rss(url, referer='https://www.ithome.com/'), keywords=KEYS)
                if its:
                    items, used = its, name
                    break
            except Exception:
                continue
        if not items:
            raise RuntimeError('全部RSS通道失败')
        n = save_news('手机新品.json', used, items)
        detail = f'{used} · 近7天保留{n}条'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))