# -*- coding: utf-8 -*-
"""P68 产品品类-Amazon充电类榜单快照：Amazon Best Sellers "Cell Phone Chargers & Power Adapters"
节点TOP30快照(排名/ASIN/标题/价格USD)，节点异常回退通用 zgbs/wireless。
价格解析优先级：a-price-whole+fraction → p13n-sc-price → a-offscreen带小数 → 文本$带小数
（a-offscreen会把$9.99渲染成"$999"，无小数一律不采，防虚高）。
历史口径说明：2026-10-23批次为通用类目回退数据；2026-10-27起为充电器/电源适配器类目本榜。
文件名保留"TOP10"（看板引用路径不变），实际采集TOP30。"""
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

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
BASE = 'https://www.amazon.com/Best-Sellers-Cell-Phones-Accessories/zgbs/wireless/'
PRICE_RE = re.compile(
    r'a-price-whole">([\d,]+)(?:<span class="a-price-decimal"></span>)?</span>'
    r'<span class="a-price-fraction">(\d\d)'
    r'|p13n-sc-price[^>]*>\$\s?([0-9,]+\.\d\d)<'
    r'|a-offscreen">\$\s?([0-9,]+\.\d\d)<'
    r'|\$\s?([0-9,]+\.\d\d)\b')
BADGE_RE = re.compile(r'zg-bdg-text[^>]*>\s*#\s*(\d+)')
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': common.UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
})


def _parse_cards(html, top_n=TOP_N):
    """按排名徽章切块，每块取ASIN/标题/价格；价格为空的商品保留行、价格留空。"""
    items = {}
    badges = list(BADGE_RE.finditer(html))
    for i, m in enumerate(badges):
        rank = int(m.group(1))
        if rank > top_n or rank in items:
            continue
        end = badges[i + 1].start() if i + 1 < len(badges) else m.start() + 8000
        seg = html[m.start():min(end, m.start() + 8000)]
        ma = re.search(r'/dp/([A-Z0-9]{10})', seg)
        mt = re.search(r'<img[^>]*alt="([^"]{5,300})"', seg)
        if not (ma and mt):
            continue
        mi = re.search(r'https://images-na\.ssl-images-amazon\.com/images/I/[A-Za-z0-9%,\-._]+\.jpg', seg)
        img = re.sub(r'\._[^/]*?_\.', '._AC_UL160_.', mi.group(0)) if mi else ''
        price = None
        mp = PRICE_RE.search(seg)
        if mp:
            whole, frac, p1, p2, p3 = mp.groups()
            price = float((whole.replace(',', '') + '.' + frac) if whole
                          else (p1 or p2 or p3).replace(',', ''))
        items[rank] = {
            '排名': rank,
            'ASIN': ma.group(1),
            '标题': re.sub(r'\s+', ' ', mt.group(1)).strip()[:80],
            '价格USD': price,
            '图片URL': img,
        }
    return items


def _fetch_best(top_n=TOP_N, tries=3):
    """按节点优先级逐节点试tries次，取该节点内"有价样本最多"的一批；
    节点可用(条目>=10且有价>=5)即采纳，不再回退下一节点。返回(items, 来源名, 最后错误)。"""
    last_err = '无请求成功'
    for node, name in NODES:
        best, best_priced = {}, -1
        for _ in range(tries):
            try:
                r = SESSION.get(BASE + node, timeout=30)
                if r.status_code != 200:
                    raise RuntimeError(f'HTTP {r.status_code}')
                items = _parse_cards(r.text)
                priced = sum(1 for it in items.values() if it['价格USD'] is not None)
                if priced > best_priced or (priced == best_priced and len(items) > len(best)):
                    best, best_priced = items, priced
                if len(items) >= top_n and priced >= top_n * 2 // 3:
                    return best, name, ''
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
            time.sleep(2)
        if len(best) >= 10 and best_priced >= 5:
            return best, name, ''
    return {}, '', last_err


def run():
    best, src, err = _fetch_best()
    priced = sum(1 for it in best.values() if it['价格USD'] is not None)
    if len(best) < 10 or priced < 5:
        reason = f'Amazon榜单解析不足(条目{len(best)}/有价{priced})或访问失败: {err or "页面无榜单数据"}'
        return '失败', reason
    date_str = common.TODAY
    n = 0
    for rank in sorted(best)[:TOP_N]:
        it = best[rank]
        common.save_row(CSV, date_str, {
            '排名': it['排名'], 'ASIN': it['ASIN'], '标题': it['标题'],
            '价格USD': ('' if it['价格USD'] is None else it['价格USD']),
            '图片URL': it.get('图片URL', ''),
            '数据来源': src,
        }, COLS, key_cols=['数据日期', '排名'])
        n += 1
    top1 = best.get(1, {})
    detail = (f'TOP{n}快照(有价{priced})[{src.split("（")[0]}] '
              f'No.1={top1.get("ASIN", "")} ${top1.get("价格USD", "")}')
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))