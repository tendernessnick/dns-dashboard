# -*- coding: utf-8 -*-
"""P68 产品品类-Amazon充电类榜单快照：Amazon Best Sellers "Cell Phone Chargers & Power Adapters"
节点TOP30快照(排名/ASIN/标题/价格USD)，节点异常回退通用 zgbs/wireless。
历史口径说明：2026-10-23批次为通用类目回退数据；2026-10-27起为充电器/电源适配器类目本榜。
文件名保留"TOP10"（看板引用路径不变），实际采集TOP30。
v18.9：解析/抓取/残留清理收敛至 _amazon_common，本文件仅保留词条常量。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import _amazon_common as amz

PID = 68
TITLE = 'Amazon充电类榜单快照'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '产品品类-P68-Amazon充电类榜单TOP10.csv')
COLS = ['数据日期', '排名', 'ASIN', '标题', '价格USD', '图片URL', '数据来源']  # v11加图片列（须先迁移CSV表头）
TOP_N = 30
# 依次尝试：充电器/电源适配器节点(2407761011)；通用 zgbs/wireless 兜底（衔接2026-10-23历史口径）
NODES = [
    ('2407761011', 'Amazon Best Sellers zgbs/wireless/2407761011（Chargers & Power Adapters 充电类目）'),
    ('', 'Amazon Best Sellers zgbs/wireless（通用类目回退）'),
]


def run():
    best, src, err = amz.fetch_best(NODES, TOP_N)
    priced = sum(1 for it in best.values() if it['价格USD'] is not None)
    if len(best) < 10 or priced < 5:
        reason = f'Amazon榜单解析不足(条目{len(best)}/有价{priced})或访问失败: {err or "页面无榜单数据"}'
        return '失败', reason
    n = 0
    for rank in sorted(best)[:TOP_N]:
        it = best[rank]
        common.save_row(CSV, common.TODAY, {
            '排名': it['排名'], 'ASIN': it['ASIN'], '标题': it['标题'],
            '价格USD': ('' if it['价格USD'] is None else it['价格USD']),
            '图片URL': it.get('图片URL', ''),
            '数据来源': src,
        }, COLS, key_cols=['数据日期', '排名'])
        n += 1
    amz.drop_stale_ranks(CSV, COLS, sorted(best)[:TOP_N])
    top1 = best.get(1, {})
    detail = (f'TOP{n}快照(有价{priced})[{src.split("（")[0]}] '
              f'No.1={top1.get("ASIN", "")} ${top1.get("价格USD", "")}')
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
