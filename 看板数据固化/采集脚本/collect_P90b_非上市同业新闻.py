# -*- coding: utf-8 -*-
"""P90 非上市同业新闻：充电头网新闻页按非上市品牌关键词过滤 → 资讯数据/同业新闻.json（近7天）
品牌口径与看板"非上市公司·品牌官网"区一致：倍思/酷态科/iWALK/闪极/Zendure/SHARGE/Vention。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _news_common import (fetch_ctw, parse_ctw, merge_rolling, load_keys, keymatch,
                          audit_discards)

PID, TITLE = '90b', '非上市同业新闻'   # b后缀：与P90图文采集器状态键分离（v19.2整理）
KEYS = ['倍思', 'Baseus', '酷态科', 'CUKTECH', 'iWALK', '爱沃可', '闪极', 'SHARGE',
        'Zendure', '征拓', 'Vention', '威迅', '摩点', '众筹']   # 兜底词表（词表csv缺失时回退；运营改词请编辑 关键词表.csv）


def run():
    try:
        keys = load_keys(PID) or {'core': KEYS, 'exclude': []}
        items = parse_ctw(fetch_ctw('/archives/category/news'))
        picked = [(d, t, u) for d, t, u in items if keymatch(t, keys)]
        if not picked:  # 兜底：全站首页再扫一遍
            picked = [(d, t, u) for d, t, u in parse_ctw(fetch_ctw('/')) if keymatch(t, keys)]
        audit_discards(PID, items, {u for _, _, u in picked})   # B3: 被过滤标题留痕供周度召回审计
        n, n_new = merge_rolling('同业新闻.json', '充电头网（非上市品牌关键词）', picked)
        if n == 0 and n_new == 0:
            # v20三态：通道通但关键词无命中=源静默（也可能词表待扩充，周度召回审计会复核）
            return '静默', '源静默: 近7天窗内0条（页面首屏无品牌命中）'
        detail = f'品牌关键词过滤 · 近7天{n}条(新见{n_new})'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))