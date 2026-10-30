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


def run():
    try:
        today = datetime.date.today()
        cut = (today - datetime.timedelta(days=730)).isoformat()
        n, latest, latest_date = 0, None, ''
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
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))