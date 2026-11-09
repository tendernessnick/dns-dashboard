# -*- coding: utf-8 -*-
"""P66 行业数据-Amazon线材榜：Amazon Best Sellers "Cell Phone Cables & Adapters"类目TOP30快照
（排名/ASIN/标题/价格USD），节点失效回退通用 zgbs/wireless。
历史口径说明：2026-10-23批次为通用充电配件类目回退数据；2026-10-27起为线材类目本榜。
v18.9：解析/抓取/残留清理收敛至 _amazon_common，本文件仅保留词条常量。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import _amazon_common as amz

PID = 66
TITLE = 'Amazon线材榜'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '行业数据-P66-Amazon线材榜.csv')
COLUMNS = ['数据日期', '排名', 'ASIN', '标题', '价格USD', '图片URL', '数据来源']  # v11加图片列（须先迁移CSV表头）
TOP_N = 30
# 依次尝试：现行线材节点(21209107011)；旧节点16676470011已死("Best undefined")不再尝试；
# 通用 zgbs/wireless 作为兜底（与2026-10-23历史口径衔接）
NODES = [
    ('21209107011', 'Amazon Best Sellers（Cell Phone Cables & Adapters 线材类目）'),
    ('', 'Amazon Best Sellers（Cell Phones & Accessories 通用类目回退）'),
]


def run():
    items, src, err = amz.fetch_best(NODES, TOP_N)
    priced = sum(1 for it in items.values() if it['价格USD'] is not None)
    if len(items) < 10 or priced < 5:
        reason = f'Amazon榜单解析不足(条目{len(items)}/有价{priced})或访问失败: {err or "页面无榜单数据"}'
        return '失败', reason
    n = 0
    for rank in sorted(items)[:TOP_N]:
        it = items[rank]
        common.save_row(CSV, common.TODAY, {
            '排名': rank, 'ASIN': it['ASIN'], '标题': it['标题'],
            '价格USD': ('' if it['价格USD'] is None else it['价格USD']),
            '图片URL': it.get('图片URL', ''),
            '数据来源': src,
        }, COLUMNS, key_cols=['数据日期', '排名'])
        n += 1
    amz.drop_stale_ranks(CSV, COLUMNS, sorted(items)[:TOP_N])
    top1 = items.get(1, {})
    detail = (f'TOP{n}快照(有价{priced})[{src.split("（")[-1].rstrip("）")}] '
              f'No.1 {top1.get("ASIN", "")} ${top1.get("价格USD", "")}')
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
