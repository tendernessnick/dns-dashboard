# -*- coding: utf-8 -*-
"""P12 宏观数据-德国10年期国债收益率：Eurostat官方API irt_lt_mcby_m 全历史回填
（EMU趋同标准约10年期长端国债月均收益率，DE；1997起全序列）。
ECB Data Portal日度接口本机不可达（data-api 400/超时），月度官方口径替代，备注已标明。"""
import os

import common

PID = '12'
TITLE = '德国10年期国债收益率'
BACKFILL = 'full_refresh'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P12-德国10年期国债收益率.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']


def run():
    try:
        series = common.estat_series('irt_lt_mcby_m', {'geo': 'DE'})
        if len(series) < 60:
            raise RuntimeError(f'德债收益率历史序列过短: {len(series)}')
        n = 0
        for period in sorted(series):
            v = series[period]
            if v is None:
                continue
            common.save_row(CSV_PATH, common.parse_date_label(period), {
                '数值': f'{round(v, 3):g}', '单位': '%',
                '数据来源': 'Eurostat(irt_lt_mcby_m)',
                '备注': f'{period}德国EMU趋同标准长期国债收益率(约10年期,月均)'}, COLUMNS)
            n += 1
        latest = sorted(series)[-1]
        msg = f'历史回填{n}个月（至{latest}），最新={series[latest]}%'
        return '成功', msg
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))