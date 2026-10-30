# -*- coding: utf-8 -*-
"""P02 宏观数据-美国CPI：OECD SDMX接口取美国CPI总指数并计算同比，回填2024-01至今月度。"""
import csv
import datetime
import io
import os

import common

PID = '02'
TITLE = '美国CPI'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P02-美国CPI.csv')
COLUMNS = ['数据日期', 'CPI指数', '同比%', '单位', '数据来源', '备注']
URL = ('https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/'
       'USA.M.N.CPI.IX._T.N.?startPeriod=2023-01&format=csvfilewithlabels')


def shift_month(period, n):
    """'2026-09' 平移n个月 → '2025-09'"""
    y, m = int(period[:4]), int(period[5:7])
    t = (y * 12 + (m - 1)) + n
    return f'{t // 12:04d}-{t % 12 + 1:02d}'


def run():
    try:
        txt = common.http_get(URL, retries=2, timeout=60)
        series = {}
        for row in csv.DictReader(io.StringIO(txt)):
            try:
                series[row['TIME_PERIOD']] = float(row['OBS_VALUE'])
            except (KeyError, ValueError, TypeError):
                continue
        if not series:
            raise RuntimeError('OECD接口无数据行')
        out = 0
        for period in sorted(series):
            if period < '2024-01':
                continue
            yoy = ''
            prev = series.get(shift_month(period, -12))
            if prev:
                yoy = f'{(series[period] / prev - 1) * 100:.2f}'
            date = common.parse_date_label(period)
            common.save_row(CSV_PATH, date, {
                'CPI指数': f'{series[period]:.4f}', '同比%': yoy,
                '数据来源': 'OECD SDMX(美国CPI总指数)',
                '备注': f'{period}月度，2015=100'}, COLUMNS)
            out += 1
        latest = max(series)
        latest_yoy = series.get(shift_month(latest, -12))
        msg = (f'回填{out}个月，最新{latest} 指数={series[latest]:.4f}'
               + (f' 同比={(series[latest] / latest_yoy - 1) * 100:.2f}%' if latest_yoy else ' 同比缺12个月前基数'))
        return '成功', msg
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))