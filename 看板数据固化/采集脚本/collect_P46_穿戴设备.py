# -*- coding: utf-8 -*-
"""P46 行业数据-穿戴设备：IDC新闻稿检索(wearable/wrist)解析全球腕上设备稿，取最新季度出货量与同比。
通道升级三期修复（原"抓旧稿"缺陷）：原逻辑取检索结果第一条匹配稿，但IDC常新发旧季度综述稿导致落后；
现逐稿解析（出货量/同比/数据季度/发布时间），取数据季度最新者，同季度取发布时间最新者；
且数据季度早于CSV现存最新行时不写入（防旧稿覆写新数据）。"""
import csv
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


def _csv_max():
    try:
        with open(CSV, encoding='utf-8-sig', newline='') as f:
            ds = [str(r.get('数据日期', '')) for r in csv.DictReader(f)]
        ds = [d for d in ds if re.match(r'^\d{4}-\d{2}-\d{2}$', d)]
        return max(ds) if ds else ''
    except OSError:
        return ''


def _parse_doc(a):
    """解析一稿：{数据季度末日期, 出货量, 同比, 季度标签, 发布时间, 标题}；解析不全返回None。"""
    ti = _clean(a.get('title', {}).get('rendered', ''))
    content = _clean(a.get('content', {}).get('rendered', ''))
    # 全球腕上设备出货：the global wrist-worn device market shipped 45.6 million units in the first quarter of 2025
    m = re.search(r'global wrist[- ]worn[^.]{0,120}?shipped\s+([\d.]+)\s*million units'
                  r'[^.]{0,80}?quarter', content, re.I)
    if not m:
        m = re.search(r'shipped\s+([\d.]+)\s*million units\s+in\s+Q([1-4])\s*(20\d{2})', content, re.I)
    if not m:
        return None
    units = float(m.group(1))
    if not (10 <= units <= 300):
        return None
    my = (re.search(r'(Grew|Fell|Declined|Dropped|Rose)\s+(\d+(?:\.\d+)?)\s*%', ti, re.I)
          or re.search(r'(Grew|Fell|Declined|Dropped|Rose)\s+(\d+(?:\.\d+)?)\s*%', content, re.I))
    if not my:
        return None
    sign = -1 if my.group(1).lower() in ('fell', 'declined', 'dropped') else 1
    mq = (re.search(r'(first|second|third|fourth)\s+quarter\s+of\s+(20\d{2})', content, re.I)
          or re.search(r'Q([1-4])\s*(20\d{2})', ti) or re.search(r'Q([1-4])\s*(20\d{2})', content))
    if not mq:
        return None
    q = WORD2Q.get(mq.group(1).lower()) or int(mq.group(1))
    year = mq.group(2)
    return {'date': common.parse_date_label(f'{year}Q{q}'), 'units': units,
            'yoy': sign * float(my.group(2)), 'qlabel': f'{year}Q{q}',
            'pub': str(a.get('date', '')), 'title': ti}


def run():
    docs = []
    for q in ('wearable', 'wrist'):  # search=wearable 首页10条可能不含全球稿，补充wrist检索
        try:
            docs.extend(_search(q))
        except Exception as e:  # noqa: BLE001
            if q == 'wrist':
                return '失败', f'抓取失败: {e}'
        time.sleep(1)
    cands, skipped = [], 0
    for a in docs:
        ti = _clean(a.get('title', {}).get('rendered', ''))
        if 'wrist' not in ti.lower() and 'wearable' not in ti.lower():
            continue
        if re.search(r'india|japan|日本|한국|china|中国', ti, re.I):
            continue
        if not re.search(r'global|worldwide', ti, re.I):
            continue
        c = _parse_doc(a)
        if c:
            cands.append(c)
        else:
            skipped += 1
    if not cands:
        return '失败', '检索结果中无可完整解析的全球腕上设备稿'
    # 数据季度最新优先；同季度取发布时间最新（修"抓旧稿"）
    cands.sort(key=lambda c: (c['date'], c['pub']), reverse=True)
    best = cands[0]
    csv_max = _csv_max()
    if csv_max and best['date'] < csv_max:
        return '跳过', (f'检索到{len(cands)}稿最新仍为{best["qlabel"]}（数据已至{csv_max[:7]}），'
                       f'不写入以防旧稿覆写；解析不全{skipped}稿')
    common.save_row(CSV, best['date'], {
        '出货量(百万台)': best['units'],
        '同比%': best['yoy'],
        '数据来源': 'IDC Worldwide Quarterly Wearable Device Tracker',
        '备注': f'{best["qlabel"]}全球腕上设备(手表+手环)出货量',
    }, COLUMNS)
    detail = (f'{best["qlabel"]} 全球腕上{best["units"]:g}百万台 同比{best["yoy"]:+g}%'
              f'（候选{len(cands)}稿取最新季度）')
    _miss = common.report_pending(PID, TITLE, common.pending_quarters(CSV))
    if _miss:
        detail += '；⚠缺失已完结季度待考证: ' + ','.join(_miss)
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
