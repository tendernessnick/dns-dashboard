# -*- coding: utf-8 -*-
"""P09 宏观数据-欧元区制造业PMI：TradingEconomics欧元区页面文本解析最新S&P Global制造业PMI
（pmi.spglobal.com首页ticker无数值且正文JS渲染，故取TE镜像口径）。"""
import os
import re
import html as htmllib

import common

PID = '09'
TITLE = '欧元区制造业PMI'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P09-欧元区制造业PMI.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
MONTHS = {m: i for i, m in enumerate(
    ['january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'], 1)}
URL = 'https://tradingeconomics.com/euro-area/manufacturing-pmi'


def run():
    try:
        text = htmllib.unescape(re.sub(r'<[^>]+>', ' ', common.http_get(URL, retries=3, timeout=30)))
        # 例句: The S&P Global Eurozone Manufacturing PMI edged down to 52.4 in October 2026, ...
        m = re.search(r'Manufacturing PMI[^.]{0,150}?(?:edged up to|edged down to|rose to|fell to'
                      r'|slipped to|climbed to|dipped to|increased to|decreased to|declined to'
                      r'|came in at)\s+([\d.]+)\s+in\s+([A-Za-z]+)\s+(\d{4})', text)
        if not m:
            raise RuntimeError('页面未解析到PMI数值句式')
        val = float(m.group(1))
        mon = MONTHS.get(m.group(2).lower())
        if not mon:
            raise RuntimeError(f'月份解析失败: {m.group(2)}')
        label = f'{m.group(3)}-{mon:02d}'
        date = common.parse_date_label(label)
        common.save_row(CSV_PATH, date, {
            '数值': str(round(val, 2)), '单位': '指数',
            '数据来源': 'TradingEconomics(S&P Global)',
            '备注': f'{label}读数，荣枯线50'}, COLUMNS)
        return '成功', f'{date} PMI={val}'
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))