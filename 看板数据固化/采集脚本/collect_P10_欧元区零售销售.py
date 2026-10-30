# -*- coding: utf-8 -*-
"""P10 宏观数据-欧元区零售销售：Eurostat官方API sts_trtu_m 全历史回填（2000起）
（G47、VOL_SLS、CA口径；指数I21=2021=100定基，环比PCH_SM；EA20/EA21聚合合并）。"""
import os

import common

PID = '10'
TITLE = '欧元区零售销售'
BACKFILL = 'full_refresh'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P10-欧元区零售销售.csv')
COLUMNS = ['数据日期', '零售销售指数', '环比%', '数据来源', '备注']
SINCE = '2000-01'


def run():
    try:
        idx = common.estat_series_merge(
            'sts_trtu_m', {'nace_r2': 'G47', 'indic_bt': 'VOL_SLS', 's_adj': 'CA', 'unit': 'I21'},
            geos=['EA21', 'EA20'], since=SINCE)
        mom = common.estat_series_merge(
            'sts_trtu_m', {'nace_r2': 'G47', 'indic_bt': 'VOL_SLS', 's_adj': 'CA', 'unit': 'PCH_SM'},
            geos=['EA21', 'EA20'], since=SINCE)
        if len(idx) < 60:
            raise RuntimeError(f'零售指数历史序列过短: {len(idx)}')
        n = 0
        for period in sorted(idx):
            iv = idx[period]
            if iv is None:
                continue
            mv = mom.get(period)
            common.save_row(CSV_PATH, common.parse_date_label(period), {
                '零售销售指数': f'{iv:.1f}',
                '环比%': ('' if mv is None else f'{mv:.1f}'),
                '数据来源': 'Eurostat(sts_trtu_m)',
                '备注': f'{period}欧元区零售贸易量指数(2021=100,经日历调整)及环比'}, COLUMNS)
            n += 1
        latest = sorted(idx)[-1]
        msg = (f'历史回填{n}个月（2000起，至{latest}），'
               f'最新指数={idx[latest]:.1f} 环比={mom.get(latest, "-")}%')
        return '成功', msg
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))