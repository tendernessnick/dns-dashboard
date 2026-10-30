# -*- coding: utf-8 -*-
"""P41 Apple相关新闻：IT之家RSS关键词过滤 → 资讯数据/apple新闻.json（仅保留最近7天）
说明：Apple Newsroom官网无可用RSS且首页为JS渲染，改用IT之家中文资讯（关键词：苹果生态）；
备选通道：MacRumors RSS（英文）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _news_common import fetch_rss, parse_items, save_news

PID, TITLE = 41, 'Apple相关新闻'
KEYS = ['苹果', 'apple', 'iphone', 'ipad', 'macbook', 'mac ', 'imac', 'airpods',
        'apple watch', 'vision pro', 'ios ', 'macos', 'm5', 'a19']
FEEDS = [
    ('https://www.ithome.com/rss/', 'IT之家（关键词过滤）'),
    ('https://www.macrumors.com/rss/', 'MacRumors'),
]


def run():
    try:
        items, used = [], ''
        for url, name in FEEDS:
            try:
                xml = fetch_rss(url, referer='https://www.ithome.com/' if 'ithome' in url else None)
                its = parse_items(xml, keywords=KEYS if 'ithome' in url else None)
                if its:
                    items, used = its, name
                    break
            except Exception:
                continue
        if not items:
            raise RuntimeError('全部RSS通道失败')
        n = save_news('apple新闻.json', used, items)
        detail = f'{used} · 近7天保留{n}条'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))