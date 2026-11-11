# -*- coding: utf-8 -*-
"""P59 充电头网早报：充电头网新闻分类页标题过滤"早报" → 资讯数据/充电头网早报.json（近7天）
说明：充电头网为自定义CMS（无RSS，有JS验证墙），走curl_cffi抓分类列表页解析。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _news_common import (fetch_ctw, parse_ctw, merge_rolling, load_keys, keymatch,
                          keys_detail, audit_discards)

PID, TITLE = 59, '充电头网早报'
KEYS = ['早报']   # 兜底词表（词表csv缺失时回退；运营改词请编辑 关键词表.csv）


def run():
    keys = load_keys(PID, fallback=KEYS)
    try:
        items = parse_ctw(fetch_ctw('/archives/category/news'))
        picked = [(d, t, u) for d, t, u in items if keymatch(t, keys)]
        if not picked:  # 兜底：首页再试一次
            picked = [(d, t, u) for d, t, u in parse_ctw(fetch_ctw('/')) if keymatch(t, keys)]
        audit_discards(PID, items, {u for _, _, u in picked})   # B3: 被过滤标题留痕供周度召回审计
        if not picked:
            # v20三态：通道通但今日无早报=源静默（区别于通道异常的"失败"，不触发连续失败计数）
            return '静默', keys_detail(keys, '源静默: 分类页与首页均无"早报"条目（源今日未发或栏目调整）')
        n, n_new = merge_rolling('充电头网早报.json', '充电头网', picked)
        detail = f'充电头网分类页 · 近7天{n}条(新见{n_new})'
        return '成功', keys_detail(keys, detail)
    except Exception as e:  # noqa: BLE001
        return '失败', keys_detail(keys, str(e))


if __name__ == '__main__':
    print(common.run_collector(globals()))
