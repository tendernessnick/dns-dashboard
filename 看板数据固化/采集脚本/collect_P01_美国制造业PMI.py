# -*- coding: utf-8 -*-
"""P01 宏观数据-美国制造业PMI(ISM)：月度全历史回填+最新读数。
历史：首选FRED NAPM(fredgraph.csv，ISM官方序列)；FRED间歇性拦截(超时)时改用
东财数据中心 RPT_ECONOMICVALUE_USANEW(INDICATOR_ID=EMG00002790，美国:供应管理协会(ISM):PMI:季调)。
最新：保留TradingEconomics页面快读(S&P Global口径，当月先于ISM发布，备注已标明口径差异)。"""
import os
import re
import time
import html as htmllib
import json

import common

PID = '01'
TITLE = '美国制造业PMI'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P01-美国制造业PMI.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
FRED_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=NAPM'
EM_API = ('https://datacenter-web.eastmoney.com/api/data/v1/get'
          '?reportName=RPT_ECONOMICVALUE_USANEW&columns=ALL'
          '&filter=(INDICATOR_ID%3D%22EMG00002790%22)'
          '&pageSize=300&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB')
TE_URL = 'https://tradingeconomics.com/united-states/manufacturing-pmi'
MIN_MONTHS = 36
MONTHS = {m: i for i, m in enumerate(
    ['january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'], 1)}


def _fetch_fred(retries=3):
    """FRED NAPM全序列，返回[(label, value)]，label=YYYY-MM。偶发拦截靠重试。"""
    last = None
    for i in range(retries):
        try:
            txt = common.http_get(FRED_URL, referer='https://fred.stlouisfed.org/series/NAPM',
                                  retries=0, timeout=30)
            rows = []
            for line in txt.strip().splitlines():
                parts = line.split(',')
                if len(parts) != 2 or parts[0] == 'observation_date':
                    continue
                if not re.match(r'^\d{4}-\d{2}-\d{2}$', parts[0]):
                    continue
                v = parts[1].strip()
                if v in ('.', ''):
                    continue
                rows.append((parts[0][:7], float(v)))
            if len(rows) >= MIN_MONTHS:
                return rows, 'FRED (St. Louis Fed) NAPM'
            raise RuntimeError(f'FRED有效月份数不足: {len(rows)}')
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3)
    raise RuntimeError(f'FRED直连失败: {last}')


def _fetch_eastmoney():
    """东财数据中心美国ISM制造业PMI全历史(2008-01起)，返回[(label, value)]。"""
    txt = common.http_get(EM_API, referer='https://data.eastmoney.com/cjsj/foreign_0_0.html',
                          retries=3, timeout=30)
    d = json.loads(txt)
    if not d.get('success'):
        raise RuntimeError(f'东财接口返回失败: {d.get("message")}')
    rows = []
    for r in ((d.get('result') or {}).get('data')) or []:
        v = r.get('VALUE')
        label = str(r.get('REPORT_DATE', ''))[:7]
        if v is None or not re.match(r'^\d{4}-\d{2}$', label):
            continue
        rows.append((label, float(v)))
    if len(rows) < MIN_MONTHS:
        raise RuntimeError(f'东财ISM有效月份数不足: {len(rows)}')
    return rows, '东方财富数据中心RPT_ECONOMICVALUE_USANEW(ISM)'


def _fetch_te_latest():
    """TradingEconomics快读当月S&P Global制造业PMI，返回(date, value)或None。"""
    try:
        text = htmllib.unescape(re.sub(r'<[^>]+>', ' ', common.http_get(TE_URL, retries=2, timeout=30)))
        m = re.search(r'PMI[^.]{0,150}?(?:edged up to|edged down to|rose to|fell to|slipped to|climbed to'
                      r'|dipped to|increased to|decreased to|declined to|came in at)\s+([\d.]+)\s+in\s+'
                      r'([A-Za-z]+)\s+(\d{4})', text)
        if not m:
            return None
        mon = MONTHS.get(m.group(2).lower())
        if not mon:
            return None
        label = f'{m.group(3)}-{mon:02d}'
        return label, float(m.group(1))
    except Exception:  # noqa: BLE001
        return None


def run():
    try:
        try:
            rows, src = _fetch_fred()
        except Exception as fe:  # noqa: BLE001
            rows, src = _fetch_eastmoney()
            src_note = f'{src}（FRED当轮不可达: {str(fe)[:60]}）'
        else:
            src_note = src
        rows.sort(key=lambda x: x[0], reverse=True)  # 统一为新在前（FRED序列为旧在前）
        for label, v in rows:
            if not (20 <= v <= 80):
                raise RuntimeError(f'ISM量级异常: {label}={v}')
            common.save_row(CSV_PATH, common.parse_date_label(label), {
                '数值': round(v, 2), '单位': '指数',
                '数据来源': src,
                '备注': f'{label}读数，荣枯线50'}, COLUMNS)
        last_label, last_v = rows[0]
        # 最新月快读（S&P Global口径，当月先于ISM发布；upsert不覆盖已有行）
        te = _fetch_te_latest()
        te_note = ''
        if te:
            label, v = te
            common.save_row(CSV_PATH, common.parse_date_label(label), {
                '数值': round(v, 2), '单位': '指数',
                '数据来源': 'TradingEconomics(S&P Global)',
                '备注': f'{label}读数，荣枯线50（S&P Global口径，非ISM）'}, COLUMNS)
            te_note = f'；TE快读{label}={v}(S&P Global)'
        detail = (f'历史回填{len(rows)}个月（{src_note}），ISM最新{last_label}={last_v}{te_note}')
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))