# -*- coding: utf-8 -*-
"""P46 行业数据-穿戴设备：IDC新闻稿检索(wearable/wrist)取最新全球腕上设备稿，解析出货量与同比"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

CSV = os.path.join(common.CSV_DIR, '行业数据-P46-穿戴设备.csv')
COLUMNS = ['数据日期', '出货量(百万台)', '同比%', '单位', '数据来源', '备注']
WORD2Q = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4}



PID = 46
TITLE = '穿戴设备(腕上)'
BACKFILL = 'incremental_verify'
def _clean(html):
    t = re.sub(r'<[^>]+>', ' ', html)
    t = t.replace('&#8217;', "'").replace('&rsquo;', "'").replace('&nbsp;', ' ')
    t = t.replace('&#8211;', '-').replace('&amp;', '&')
    return re.sub(r'\s+', ' ', t)


def _search(q):
    url = f'https://www.idc.com/wp-json/wp/v2/press-release?search={q}&per_page=10'
    return json.loads(common.http_get(url, retries=2, timeout=30))


def run():
    docs = []
    for q in ('wearable', 'wrist'):  # search=wearable 首页10条可能不含全球稿，补充wrist检索
        try:
            docs.extend(_search(q))
        except Exception as e:  # noqa: BLE001
            if q == 'wrist':
                return '失败', f'抓取失败: {e}'
        time.sleep(1)
    # 取最新全球腕上设备稿（排除India/Japan/China区域稿）
    picked = None
    for a in docs:
        ti = _clean(a.get('title', {}).get('rendered', ''))
        if 'wrist' not in ti.lower() and 'wearable' not in ti.lower():
            continue
        if re.search(r'india|japan|日本|한국|china|中国', ti, re.I):
            continue
        if not re.search(r'global|worldwide', ti, re.I):
            continue
        picked = (a, ti)
        break
    if not picked:
        return '失败', '检索结果中无全球腕上设备稿'
    a, ti = picked
    content = _clean(a.get('content', {}).get('rendered', ''))
    # 全球腕上设备出货：the global wrist-worn device market shipped 45.6 million units in the first quarter of 2025
    m = re.search(r'global wrist[- ]worn[^.]{0,120}?shipped\s+([\d.]+)\s*million units'
                  r'[^.]{0,80}?quarter', content, re.I)
    if not m:
        m = re.search(r'shipped\s+([\d.]+)\s*million units\s+in\s+Q([1-4])\s*(20\d{2})', content, re.I)
    if not m:
        return '失败', f'未解析到全球腕上出货量: {ti[:60]}'
    units = float(m.group(1))
    # 同比优先取标题：Global Wrist-Worn Device Shipments Grew 10.5% in Q1 2025
    my = re.search(r'(Grew|Fell|Declined|Dropped|Rose)\s+(\d+(?:\.\d+)?)\s*%', ti, re.I)
    if not my:
        my = re.search(r'(Grew|Fell|Declined|Dropped|Rose)\s+(\d+(?:\.\d+)?)\s*%', content, re.I)
    if not my:
        return '失败', f'未解析到同比: {ti[:60]}'
    sign = -1 if my.group(1).lower() in ('fell', 'declined', 'dropped') else 1
    yoy = sign * float(my.group(2))
    mq = (re.search(r'(first|second|third|fourth)\s+quarter\s+of\s+(20\d{2})', content, re.I)
          or re.search(r'Q([1-4])\s*(20\d{2})', ti) or re.search(r'Q([1-4])\s*(20\d{2})', content))
    if not mq:
        return '失败', f'未解析到季度: {ti[:60]}'
    q = WORD2Q.get(mq.group(1).lower()) or int(mq.group(1))
    year = mq.group(2)
    date_str = common.parse_date_label(f'{year}Q{q}')
    if not (10 <= units <= 300):
        return '失败', f'出货量量级异常: {units}'
    common.save_row(CSV, date_str, {
        '出货量(百万台)': units,
        '同比%': yoy,
        '数据来源': 'IDC Worldwide Quarterly Wearable Device Tracker',
        '备注': f'{year}Q{q}全球腕上设备(手表+手环)出货量',
    }, COLUMNS)
    detail = f'{year}Q{q} 全球腕上{units}百万台 同比{yoy:+g}%'
    _miss = common.report_pending(PID, TITLE, common.pending_quarters(CSV))
    if _miss:
        detail += '；⚠缺失已完结季度待考证: ' + ','.join(_miss)
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))