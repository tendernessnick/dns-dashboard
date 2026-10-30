# -*- coding: utf-8 -*-
"""P08 宏观数据-欧盟HICP同比：全历史回填+最新快报。
历史：Eurostat官方API PRC_HICP_MANR（EA20/EA21聚合合并，1997起全序列，含已发布正式值）。
最新：保留HICP专题页快报解析（正式值发布前先行占位，发布后下次运行被API正式值覆盖）。"""
import os
import re
import html as htmllib

import common

PID = '08'
TITLE = '欧盟HICP同比'
BACKFILL = 'full_refresh'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P08-欧盟HICP同比.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
MONTHS = {m: i for i, m in enumerate(
    ['january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'], 1)}
URL = 'https://ec.europa.eu/eurostat/web/hicp'


def backfill_history():
    """Eurostat PRC_HICP_MANR 全量同比（EA20全历史 + EA21补2026起），返回行数。"""
    series = common.estat_series_merge(
        'PRC_HICP_MANR', {'coicop': 'CP00'}, geos=['EA21', 'EA20'])
    if len(series) < 60:
        raise RuntimeError(f'HICP历史序列过短: {len(series)}')
    n = 0
    for period in sorted(series):
        v = series[period]
        if v is None:
            continue
        common.save_row(CSV_PATH, common.parse_date_label(period), {
            '数值': str(round(v, 2)), '单位': '%',
            '数据来源': 'Eurostat(PRC_HICP_MANR)',
            '备注': f'{period}欧元区HICP同比（全项目，正式序列）'}, COLUMNS)
        n += 1
    return n, sorted(series)[-1]


def run():
    try:
        n, latest = backfill_history()
        # 最新快报（正式值发布前的占位；API正式值发布后由上面回填覆盖）
        flash_note = ''
        try:
            text = htmllib.unescape(re.sub(r'<[^>]+>', ' ', common.http_get(URL, retries=1, timeout=30)))
            text = re.sub(r'\s+', ' ', text)
            m = re.search(r'Annual inflation up to ([\d.]+)% in the euro area(?:.*?(\d{1,2})\s+'
                          r'([A-Za-z]+)\s+(\d{4}))?', text)
            if m:
                val = float(m.group(1))
                label = ''
                if m.group(3) and MONTHS.get(m.group(3).lower()):
                    label = f'{m.group(4)}-{MONTHS[m.group(3).lower()]:02d}'
                if not label:
                    label = common.TODAY[:7]
                if label > latest:  # 仅当快报月比API最新正式值更新时写入
                    common.save_row(CSV_PATH, common.parse_date_label(label), {
                        '数值': str(round(val, 2)), '单位': '%',
                        '数据来源': 'Eurostat(HICP快报)',
                        '备注': f'{label}欧元区HICP同比（快报值，正式值发布后自动替换）'}, COLUMNS)
                    flash_note = f'；快报{label}={val}%'
        except Exception:  # noqa: BLE001
            pass
        msg = f'历史回填{n}个月（至{latest}）{flash_note}'
        return '成功', msg
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))