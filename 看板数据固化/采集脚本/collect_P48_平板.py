# -*- coding: utf-8 -*-
"""P48 行业数据-平板：IDC新闻稿检索(tablet)取最新全球平板季度总稿（排除印度等区域稿与分品类稿），解析出货量与同比"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

API = 'https://www.idc.com/wp-json/wp/v2/press-release?search=tablet&per_page=10'
CSV = os.path.join(common.CSV_DIR, '行业数据-P48-平板.csv')
COLUMNS = ['数据日期', '出货量(百万台)', '同比%', '单位', '数据来源', '备注']
WORD2Q = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4}



PID = 48
TITLE = '平板出货'
BACKFILL = 'incremental_verify'
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
        if 'tablet' not in ti.lower():
            continue
        # 排除印度/韩国/日本/中国等区域稿
        if re.search(r'india|japan|日本|한국|china|中国|korea|국내', ti, re.I):
            continue
        # 排除分品类/分人群稿（Consumer/Kids等非全球总量稿）
        if re.search(r'consumer|kids|education', ti, re.I):
            continue
        # 须为全球季度总量稿
        if not (re.search(r'worldwide|global', ti, re.I) or re.search(r'Q[1-4]\s*20\d{2}|[1-4]Q\s*20\d{2}', ti, re.I)):
            continue
        picked = (a, ti)
        break
    if not picked:
        return '失败', '检索结果中无全球平板季度总稿'
    a, ti = picked
    content = _clean(a.get('content', {}).get('rendered', ''))
    if not re.search(r'(Worldwide|Global)\s+tablet shipments', content, re.I):
        return '失败', f'正文非全球平板总稿: {ti[:60]}'
    # Worldwide tablet shipments declined 4.4% year-over-year in the third quarter of 2025 (3Q25), totaling 38 million units
    m = re.search(r'(declined|fell|dropped|grew|rose|increased)\s+([\d.]+)\s*%\s*year[- ]over[- ]year\s+in\s+'
                  r'(?:the\s+)?(first|second|third|fourth)\s+quarter\s+of\s+(20\d{2})[^,.]{0,40}?,?\s*'
                  r'totaling\s+([\d.]+)\s*million units', content, re.I)
    if not m:
        return '失败', f'未解析到全球平板出货量: {ti[:60]}'
    verb, pct, qword, year, units = (m.group(1), float(m.group(2)), m.group(3), m.group(4), float(m.group(5)))
    yoy = -pct if verb.lower() in ('declined', 'fell', 'dropped') else pct
    q = WORD2Q[qword.lower()]
    date_str = common.parse_date_label(f'{year}Q{q}')
    if not (20 <= units <= 120):
        return '失败', f'出货量量级异常: {units}'
    common.save_row(CSV, date_str, {
        '出货量(百万台)': units,
        '同比%': yoy,
        '数据来源': 'IDC Worldwide Quarterly Personal Computing Device Tracker',
        '备注': f'{year}Q{q}全球平板电脑出货量',
    }, COLUMNS)
    detail = f'{year}Q{q} 全球平板 {units}百万台 同比{yoy:+g}%'
    _miss = common.report_pending(PID, TITLE, common.pending_quarters(CSV))
    if _miss:
        detail += '；⚠缺失已完结季度待考证: ' + ','.join(_miss)
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))