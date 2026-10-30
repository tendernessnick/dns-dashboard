# -*- coding: utf-8 -*-
"""P60 快充瓦数趋势（拆解）：充电头网"拆解"分类列表 → 资讯数据/快充拆解.json（近7天）
说明：拆解分类页全量即目标内容（拆解稿标题自带瓦数/功率信息），不做额外关键词过滤。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _news_common import fetch_ctw, parse_ctw, save_news

PID, TITLE = 60, '快充瓦数趋势（拆解）'


def run():
    try:
        items = parse_ctw(fetch_ctw('/archives/category/teardowns'))
        if not items:  # 兜底：首页按"拆解"过滤
            items = [(d, t, u) for d, t, u in parse_ctw(fetch_ctw('/')) if '拆解' in t]
        if not items:
            raise RuntimeError('拆解分类页无条目（页面改版？）')
        n = save_news('快充拆解.json', '充电头网·拆解', items)
        detail = f'充电头网拆解分类 · 近7天{n}条'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))