# -*- coding: utf-8 -*-
"""Amazon Best Sellers 榜单共用（v18.9收敛，P66线材榜/P68充电类榜）：
排名徽章切块解析(ASIN/标题/价格/图片) + 节点优先级抓取 + 同日残留行清理。
价格解析优先级：a-price-whole+fraction → p13n-sc-price → a-offscreen带小数 → 文本$带小数
（注意 a-offscreen 会把$9.99渲染成"$999"，无小数的一律不采，防虚高）。"""
import os
import re
import time

import requests

import common

BASE_URL = 'https://www.amazon.com/Best-Sellers-Cell-Phones-Accessories/zgbs/wireless/'
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': common.UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',  # requests自动解压gzip，勿手工设Accept-Encoding
})
PRICE_RE = re.compile(
    r'a-price-whole">([\d,]+)(?:<span class="a-price-decimal"></span>)?</span>'
    r'<span class="a-price-fraction">(\d\d)'          # 1: 拆分式 $9.99
    r'|p13n-sc-price[^>]*>\$\s?([0-9,]+\.\d\d)<'      # 2: 列表页价签 $8.99
    r'|a-offscreen">\$\s?([0-9,]+\.\d\d)<'            # 3: 屏读价（必须带小数）
    r'|\$\s?([0-9,]+\.\d\d)\b')                       # 4: 兜底纯文本（必须带小数，防$999陷阱）
BADGE_RE = re.compile(r'zg-bdg-text[^>]*>\s*#\s*(\d+)')
# v18.8：图床双域都收（Amazon切换m.media-amazon.com时旧正则整列静默置空）
IMG_RE = re.compile(r'(?:https://images-na\.ssl-images-amazon\.com'
                    r'|https://m\.media-amazon\.com)/images/I/[A-Za-z0-9%,\-._]+\.jpg')


def parse_items(html, top_n=30):
    """按排名徽章切块，每块取ASIN/标题/价格/图片；价格为空的商品保留行、价格留空。返回{rank: item}。"""
    out = {}
    badges = list(BADGE_RE.finditer(html))
    for i, m in enumerate(badges):
        rank = int(m.group(1))
        if rank > top_n or rank in out:
            continue
        end = badges[i + 1].start() if i + 1 < len(badges) else m.start() + 8000
        blk = html[m.start():min(end, m.start() + 8000)]
        ma = re.search(r'/dp/([A-Z0-9]{10})', blk)
        mt = re.search(r'alt="([^"]{5,300})"', blk) or re.search(
            r'class="[^"]*a-link-normal[^"]*"[^>]*>\s*([^<]{10,200})<', blk)
        if not (ma and mt):
            continue
        price = None
        mp = PRICE_RE.search(blk)
        if mp:
            whole, frac, p1, p2, p3 = mp.groups()
            price = float((whole.replace(',', '') + '.' + frac) if whole
                          else (p1 or p2 or p3).replace(',', ''))
        mi = IMG_RE.search(blk)
        img = re.sub(r'\._[^/]*?_\.', '._AC_UL160_.', mi.group(0)) if mi else ''
        out[rank] = {'排名': rank, 'ASIN': ma.group(1),
                     '标题': re.sub(r'\s+', ' ', mt.group(1)).strip()[:80],
                     '价格USD': price, '图片URL': img}
    return out


def fetch_best(nodes, top_n=30, tries=3):
    """按节点优先级逐节点试tries次，取该节点内"有价样本最多"的一批；
    节点可用(条目>=10且有价>=5)即采纳，不再回退下一节点。返回(items, 来源名, 最后错误)。"""
    last_err = '无请求成功'
    for node, name in nodes:
        best, best_priced = {}, -1
        for _ in range(tries):
            try:
                r = SESSION.get(BASE_URL + node, timeout=(8, 25))
                if r.status_code != 200:
                    raise RuntimeError(f'HTTP {r.status_code}')
                items = parse_items(r.text, top_n)
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


def drop_stale_ranks(csv_path, columns, keep_ranks):
    """同日重跑且榜单解析变短时（反爬降级页常见），清掉当天不在当前排名里的残留行（v18.7起）。"""
    import csv as _csv
    if not os.path.exists(csv_path):
        return
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        rows = list(_csv.DictReader(f))
    kept = [r for r in rows
            if r.get('数据日期') != common.TODAY
            or int(r.get('排名') or 0) in keep_ranks]
    if len(kept) == len(rows):
        return
    common.write_csv_atomic(csv_path, columns, kept)
