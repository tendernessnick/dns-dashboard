# -*- coding: utf-8 -*-
"""P59 充电头网早报：充电头网新闻分类页标题过滤"早报" → 资讯数据/充电头网早报.json（近7天）
说明：充电头网为自定义CMS（无RSS，有JS验证墙），走curl_cffi抓分类列表页解析。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _news_common import fetch_ctw, parse_ctw, save_news

PID, TITLE = 59, '充电头网早报'
KEYS = ['早报']


def run():
    try:
        items = parse_ctw(fetch_ctw('/archives/category/news'))
        picked = [(d, t, u) for d, t, u in items if any(k in t for k in KEYS)]
        if not picked:  # 兜底：首页再试一次
            picked = [(d, t, u) for d, t, u in parse_ctw(fetch_ctw('/')) if any(k in t for k in KEYS)]
        if not picked:
            raise RuntimeError('列表页无"早报"条目（页面改版？）')
        n = save_news('充电头网早报.json', '充电头网', picked)
        detail = f'充电头网分类页 · 近7天{n}条'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))