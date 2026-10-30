# -*- coding: utf-8 -*-
"""P13 宏观数据-欧盟消费者信心：全历史回填+最新闪估值。
历史：Eurostat官方API EI_BSSI_M_R2（消费者信心指数BS-CSMCI-BAL，SA口径，
EA20/EA21聚合合并，1985起全序列，负值正常）。最新：保留DG ECFIN闪估值解析
（闪估值先行占位，Eurostat正式值发布后下次运行覆盖）。"""
import os
import re
import html as htmllib

import common

PID = '13'
TITLE = '欧盟消费者信心'
BACKFILL = 'full_refresh'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P13-欧盟消费者信心.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
MONTHS = {m: i for i, m in enumerate(
    ['january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'], 1)}
URL = ('https://economy-finance.ec.europa.eu/economic-forecast-and-surveys/'
       'business-and-consumer-surveys/latest-business-and-consumer-surveys_en')


def backfill_history():
    series = common.estat_series_merge(
        'EI_BSSI_M_R2', {'indic': 'BS-CSMCI-BAL', 's_adj': 'SA'}, geos=['EA21', 'EA20'])
    series = {k: v for k, v in series.items() if v is not None}
    if len(series) < 60:
        raise RuntimeError(f'消费者信心历史序列过短: {len(series)}')
    n = 0
    for period in sorted(series):
        common.save_row(CSV_PATH, common.parse_date_label(period), {
            '数值': str(round(series[period], 1)), '单位': '点',
            '数据来源': 'Eurostat(EI_BSSI_M_R2)',
            '备注': f'{period}欧元区消费者信心指数(经季调,零为分界,负=悲观)'}, COLUMNS)
        n += 1
    return n, sorted(series)[-1]


def run():
    try:
        n, latest = backfill_history()
        flash_note = ''
        try:
            text = htmllib.unescape(re.sub(r'<[^>]+>', ' ', common.http_get(URL, retries=1, timeout=30)))
            text = re.sub(r'\s+', ' ', text)
            m = re.search(r'(-?\d+(?:\.\d+)?)\s*points?\s*\(euro area\)', text)
            if m:
                val = float(m.group(1))
                label = ''
                pm = re.search(r'([A-Za-z]+)\s+(\d{4})\s*:?\s*Flash Consumer Confidence', text)
                if pm and pm.group(1).lower() in MONTHS:
                    label = f'{pm.group(2)}-{MONTHS[pm.group(1).lower()]:02d}'
                if not label:
                    label = common.TODAY[:7]
                if label > latest:  # 仅当闪估月比API最新正式值更新时写入
                    common.save_row(CSV_PATH, common.parse_date_label(label), {
                        '数值': str(round(val, 1)), '单位': '点',
                        '数据来源': '欧盟委员会DG ECFIN',
                        '备注': f'{label}欧元区消费者信心闪估值（正式值发布后自动替换）'}, COLUMNS)
                    flash_note = f'；闪估{label}={val}'
        except Exception:  # noqa: BLE001
            pass
        msg = f'历史回填{n}个月（至{latest}）{flash_note}'
        return '成功', msg
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))