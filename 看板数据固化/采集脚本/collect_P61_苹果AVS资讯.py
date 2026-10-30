# -*- coding: utf-8 -*-
"""P61 苹果AVS新品/资讯：充电头网新闻页按 AVS/苹果 关键词过滤 → 资讯数据/avs资讯.json（近7天）
说明：AVS为低频主题，近7天可能为0条属正常（JSON为空时看板保留占位文案）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _news_common import fetch_ctw, parse_ctw, save_news

PID, TITLE = 61, '苹果AVS新品/资讯'
KEYS = ['AVS', '苹果']


def run():
    try:
        items = parse_ctw(fetch_ctw('/archives/category/news'))
        home = parse_ctw(fetch_ctw('/'))  # 首页合并提高覆盖
        seen, merged = set(), []
        for it in items + home:
            if it[2] not in seen:
                seen.add(it[2]); merged.append(it)
        picked = [(d, t, u) for d, t, u in merged if any(k.lower() in t.lower() for k in KEYS)]
        n = save_news('avs资讯.json', '充电头网（AVS/苹果关键词）', picked)
        detail = f'关键词过滤 · 近7天{n}条'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))