# -*- coding: utf-8 -*-
"""P49 行业数据-手机品牌份额：Counterpoint全球智能手机份额页解析最新季度Top3(三星/苹果/小米)份额表"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

URL = 'https://counterpointresearch.com/en/insights/global-smartphone-share'
CSV = os.path.join(common.CSV_DIR, '行业数据-P49-手机品牌份额.csv')
COLUMNS = ['数据日期', '三星%', '苹果%', '小米%', 'vivo%', 'OPPO%', '其他%', '单位', '数据来源', '备注']


def run():
    try:
        html = common.http_get(URL, retries=2, timeout=30)
    except Exception as e:  # noqa: BLE001
        return '失败', f'抓取失败: {e}'
    tables = re.findall(r'<table.*?</table>', html, re.S)
    best = None  # (year, q, {brand: share})
    for tb in tables:
        rows = re.findall(r'<tr.*?</tr>', tb, re.S)
        if len(rows) < 4:
            continue
        cells = lambda r: [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', c)).strip()
                           for c in re.findall(r'<t[dh].*?</t[dh]>', r, re.S)]  # noqa: E731
        header = cells(rows[0])
        cols = {}  # 列号 -> (year, q)
        for i, cell in enumerate(header):
            mq = re.match(r'Q([1-4])\s+(20\d{2})', cell)
            if mq:
                cols[i] = (int(mq.group(2)), int(mq.group(1)))
        if not cols:
            continue
        # 该表最新季度列
        latest_i = max(cols, key=lambda i: cols[i])
        shares = {}
        for r in rows[1:]:
            cs = cells(r)
            if len(cs) <= latest_i:
                continue
            brand = cs[0]
            if brand in ('Samsung', 'Apple', 'Xiaomi'):
                mv = re.match(r'([\d.]+)\s*%', cs[latest_i])
                if mv:
                    shares[brand] = float(mv.group(1))
        if {'Samsung', 'Apple', 'Xiaomi'} <= set(shares):
            y, q = cols[latest_i]
            if not best or (y, q) > best[0]:
                best = ((y, q), shares)
    if not best:
        return '失败', '未解析到份额表，页面可能已改版'
    (year, q), shares = best
    date_str = common.parse_date_label(f'{year}Q{q}')
    if not all(0 < shares[b] < 60 for b in ('Samsung', 'Apple', 'Xiaomi')):
        return '失败', f'份额量级异常: {shares}'
    common.save_row(CSV, date_str, {
        '三星%': shares['Samsung'],
        '苹果%': shares['Apple'],
        '小米%': shares['Xiaomi'],
        '数据来源': 'Counterpoint Research',
        '备注': f'{year}Q{q}全球智能手机出货份额（最新季度，口径：全球）',
    }, COLUMNS)
    detail = (f'{year}Q{q} 三星{shares["Samsung"]:g}% 苹果{shares["Apple"]:g}% '
              f'小米{shares["Xiaomi"]:g}%')
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))