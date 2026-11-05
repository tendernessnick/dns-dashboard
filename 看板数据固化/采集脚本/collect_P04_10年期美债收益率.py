# -*- coding: utf-8 -*-
"""P04 宏观数据-10年期美债收益率：美国财政部官方日频收益率曲线CSV回填近2年
（注：FRED在本网络不可达，改用财政部daily treasury yield curve原始源，口径同DGS10）。"""
import csv
import datetime
import io
import os
import time

import common

PID = '04'
TITLE = '10年期美债收益率'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P04-10年期美债收益率.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
BASE_URL = ('https://home.treasury.gov/resource-center/data-chart-center/interest-rates/'
            'daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve'
            '&field_tdr_date_value={year}&page&_format=csv')
YEARS = 3  # 抓3个自然年，截取近2年


def _fetch_fred_api(cut):
    """备用：FRED官方API DGS10（同口径10年期CMT，免费key见_keys.py）。返回[(date, value)]。"""
    import json as _json
    try:
        from _keys import FRED_API_KEY
    except ImportError:
        raise RuntimeError('_keys.py不存在')
    if not FRED_API_KEY:
        raise RuntimeError('FRED_API_KEY未配置')
    api = ('https://api.stlouisfed.org/fred/series/observations?series_id=DGS10'
           f'&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=730')
    d = _json.loads(common.http_get(api, retries=1, timeout=30))
    obs = d.get('observations') or []
    if d.get('error_code') or not obs:
        raise RuntimeError(f'FRED API异常: {str(d.get("error_message"))[:80]}')
    rows = []
    for o in obs:
        v = str(o.get('value', '')).strip()
        if v in ('.', ''):
            continue
        try:
            d2 = o['date']
            if d2 >= cut and float(v) > 0:
                rows.append((d2, float(v)))
        except (KeyError, ValueError):
            continue
    rows.reverse()  # desc→asc
    if not rows:
        raise RuntimeError('API无有效收益率行')
    return rows


def run():
    try:
        today = datetime.date.today()
        cut = (today - datetime.timedelta(days=730)).isoformat()
        n, latest, latest_date = 0, None, ''
        try:
            for y in range(today.year - YEARS + 1, today.year + 1):
                txt = common.http_get(BASE_URL.format(year=y), retries=3, timeout=60)
                time.sleep(1)
                for row in csv.DictReader(io.StringIO(txt)):
                    v = (row.get('10 Yr') or '').strip()
                    if not v:
                        continue
                    try:
                        d = datetime.datetime.strptime(row['Date'].strip(), '%m/%d/%Y').date()
                    except (KeyError, ValueError):
                        continue
                    if d.isoformat() < cut:
                        continue
                    common.save_row(CSV_PATH, d.isoformat(), {
                        '数值': f'{float(v):.2f}', '单位': '%',
                        '数据来源': '美国财政部(日频国债收益率曲线)',
                        '备注': '10年期固定期限国债收益率CMT'}, COLUMNS)
                    n += 1
                    if d.isoformat() >= latest_date:
                        latest_date, latest = d.isoformat(), float(v)
            if not n:
                raise RuntimeError('未取到任何收益率数据行')
            msg = f'回填{n}个交易日，最新{latest_date} 10Y={latest}%'
            return '成功', msg
        except Exception as treasury_err:  # noqa: BLE001
            # 备用：FRED官方API DGS10（2026-11-05接入，同口径10年期CMT）
            rows = _fetch_fred_api(cut)
            for d, v in rows:
                common.save_row(CSV_PATH, d, {
                    '数值': f'{v:.2f}', '单位': '%',
                    '数据来源': 'FRED (St. Louis Fed) DGS10(备用)',
                    '备注': '10年期固定期限国债收益率CMT；财政部官网当轮不可达，经FRED官方API获取'}, COLUMNS)
            latest_date, latest = rows[-1]
            return '成功', (f'财政部不可达({str(treasury_err)[:50]})，经FRED API备用通道回填'
                           f'{len(rows)}个交易日，最新{latest_date} 10Y={latest}%')
    except Exception as e:
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))