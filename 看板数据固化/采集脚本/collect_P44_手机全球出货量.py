# -*- coding: utf-8 -*-
"""P44 行业数据-手机全球出货量：IDC新闻稿检索接口取最新全球智能手机稿，解析季度出货量与同比"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

API = 'https://www.idc.com/wp-json/wp/v2/press-release?search=smartphone&per_page=10'
CSV = os.path.join(common.CSV_DIR, '行业数据-P44-手机全球出货量.csv')
COLUMNS = ['数据日期', '出货量(百万台)', '同比%', '单位', '数据来源', '备注']
WORD2Q = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4}


def _clean(html):
    t = re.sub(r'<[^>]+>', ' ', html)
    t = t.replace('&#8217;', "'").replace('&rsquo;', "'").replace('&nbsp;', ' ')
    t = t.replace('&#8211;', '-').replace('&amp;', '&')
    return re.sub(r'\s+', ' ', t)


def _pick_global(arr):
    """取最新一篇全球智能手机稿（排除India/China等区域稿）"""
    for a in arr:
        ti = _clean(a.get('title', {}).get('rendered', ''))
        if not re.search(r'global|worldwide', ti, re.I):
            continue
        if re.search(r'india|china|korea|japan|日本|한국', ti, re.I):
            continue
        if 'smartphone' not in ti.lower():
            continue
        return a, ti
    return None, None


def run():
    try:
        arr = json.loads(common.http_get(API, retries=2, timeout=30))
    except Exception as e:  # noqa: BLE001
        return '失败', f'抓取失败: {e}'
    a, ti = _pick_global(arr)
    if not a:
        return '失败', '检索结果中无全球智能手机稿'
    content = _clean(a.get('content', {}).get('rendered', ''))
    # 形如: shrank 22.0% year-on-year to 255.3 million units in the third quarter of 2026
    m = (re.search(r'(shrank|fell|declined|dropped|grew|rose|increased)\s+([\d.]+)%\s*(?:year[- ]on[- ]year|YoY|year over year)?[^.]{0,80}?'
                   r'to\s+([\d.]+)\s*million units', content, re.I)
         or re.search(r'(?:shipped|totaling)\s+([\d.]+)\s*million units[^.]{0,120}?'
                      r'(shrank|fell|declined|dropped|grew|rose|increased)?\s*(?:by)?\s*([\d.]+)%', content, re.I))
    if not m:
        return '失败', f'未解析到出货量/同比: {ti[:60]}'
    g = m.groups()
    if g[0].lower() in ('shrank', 'fell', 'declined', 'dropped'):
        yoy, units = -float(g[1]), float(g[2])
    elif g[0].lower() in ('grew', 'rose', 'increased'):
        yoy, units = float(g[1]), float(g[2])
    else:  # 单位在前
        units = float(g[0])
        yoy = -float(g[2]) if (g[1] or '').lower() in ('shrank', 'fell', 'declined', 'dropped') else float(g[2])
    mq = (re.search(r'(first|second|third|fourth)\s+quarter\s+of\s+(20\d{2})', content, re.I)
          or re.search(r'Q([1-4])\s*(20\d{2})', content))
    if not mq:
        return '失败', f'未解析到季度: {ti[:60]}'
    q = WORD2Q.get(mq.group(1).lower()) or int(mq.group(1))
    year = mq.group(2)
    date_str = common.parse_date_label(f'{year}Q{q}')
    if not (50 <= units <= 600):
        return '失败', f'出货量量级异常: {units}'
    common.save_row(CSV, date_str, {
        '出货量(百万台)': units,
        '同比%': yoy,
        '数据来源': 'IDC Worldwide Quarterly Mobile Phone Tracker',
        '备注': f'{year}Q{q}全球智能手机出货量',
    }, COLUMNS)
    detail = f'{year}Q{q} 全球{units}百万台 同比{yoy}%'
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))