# -*- coding: utf-8 -*-
"""P47 行业数据-PC出货：IDC新闻稿检索(PC tracker)取最新全球PC稿，解析季度出货量与同比"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

API = 'https://www.idc.com/wp-json/wp/v2/press-release?search=PC%20tracker&per_page=10'
CSV = os.path.join(common.CSV_DIR, '行业数据-P47-PC出货.csv')
COLUMNS = ['数据日期', '出货量(百万台)', '同比%', '单位', '数据来源', '备注']


def _clean(html):
    t = re.sub(r'<[^>]+>', ' ', html)
    t = t.replace('&#8217;', "'").replace('&rsquo;', "'").replace('&nbsp;', ' ')
    t = t.replace('&#8211;', '-').replace('&amp;', '&')
    return re.sub(r'\s+', ' ', t)


def run():
    try:
        arr = json.loads(common.http_get(API, retries=2, timeout=30))
    except Exception as e:  # noqa: BLE001
        return '失败', f'抓取失败: {e}'
    picked = None
    for a in arr:
        ti = _clean(a.get('title', {}).get('rendered', ''))
        if 'PC' not in ti:
            continue
        if re.search(r'india|japan|日本|한국|china|中国|korea', ti, re.I):
            continue
        # 全球PC季度出货稿（IDC Worldwide Quarterly Personal Computing Device Tracker）
        picked = (a, ti)
        break
    if not picked:
        return '失败', '检索结果中无全球PC稿'
    a, ti = picked
    content = _clean(a.get('content', {}).get('rendered', ''))
    # Worldwide PC shipments fell 20.1% year over year in Q3 2026 to 62.7 million units
    m = re.search(r'(?:Worldwide|Global)\s+PC shipments\s+(fell|grew|declined|rose|dropped)\s+([\d.]+)%\s*'
                  r'year over year\s+in\s+Q([1-4])\s+(20\d{2})\s+to\s+([\d.]+)\s*million units', content, re.I)
    if not m:
        m = re.search(r'PC (?:market|shipments)[^.]{0,160}?(fell|grew|declined|rose|dropped)\s+([\d.]+)%'
                      r'[^.]{0,120}?([\d.]+)\s*million units', content, re.I)
    if not m:
        return '失败', f'未解析到全球PC出货量: {ti[:60]}'
    g = m.groups()
    verb, pct = g[0], float(g[1])
    yoy = -pct if verb.lower() in ('fell', 'declined', 'dropped') else pct
    if len(g) == 5:
        q, year, units = int(g[2]), g[3], float(g[4])
    else:
        mq = re.search(r'Q([1-4])\s*(20\d{2})', content)
        if not mq:
            return '失败', f'未解析到季度: {ti[:60]}'
        q, year = int(mq.group(1)), mq.group(2)
        mu = re.search(r'([\d.]+)\s*million units', content)
        if not mu:
            return '失败', f'未解析到出货量: {ti[:60]}'
        units = float(mu.group(1))
    date_str = common.parse_date_label(f'{year}Q{q}')
    if not (30 <= units <= 200):
        return '失败', f'出货量量级异常: {units}'
    common.save_row(CSV, date_str, {
        '出货量(百万台)': units,
        '同比%': yoy,
        '数据来源': 'IDC Worldwide Quarterly Personal Computing Device Tracker',
        '备注': f'{year}Q{q}全球传统PC(台式机+笔记本)出货量',
    }, COLUMNS)
    detail = f'{year}Q{q} 全球PC {units}百万台 同比{yoy:+g}%'
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))