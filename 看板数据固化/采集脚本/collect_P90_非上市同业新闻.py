# -*- coding: utf-8 -*-
"""P90 非上市同业新闻：充电头网新闻页按非上市品牌关键词过滤 → 资讯数据/同业新闻.json（近7天）
品牌口径与看板"非上市公司·品牌官网"区一致：倍思/酷态科/iWALK/闪极/Zendure/SHARGE/Vention。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _news_common import fetch_ctw, parse_ctw, save_news

PID, TITLE = 90, '非上市同业新闻'
KEYS = ['倍思', 'Baseus', '酷态科', 'CUKTECH', 'iWALK', '爱沃可', '闪极', 'SHARGE',
        'Zendure', '征拓', 'Vention', '威迅', '摩点', '众筹']


def run():
    try:
        items = parse_ctw(fetch_ctw('/archives/category/news'))
        picked = [(d, t, u) for d, t, u in items if any(k.lower() in t.lower() for k in KEYS)]
        if not picked:  # 兜底：全站首页再扫一遍
            picked = [(d, t, u) for d, t, u in parse_ctw(fetch_ctw('/'))
                      if any(k.lower() in t.lower() for k in KEYS)]
        n = save_news('同业新闻.json', '充电头网（非上市品牌关键词）', picked)
        detail = f'品牌关键词过滤 · 近7天{n}条'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))