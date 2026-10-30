# -*- coding: utf-8 -*-
"""P03 宏观数据-美国PCE同比：BEA官方页面文本解析PCE价格指数当月同比。"""
import os
import re
import html as htmllib

import common

PID = '03'
TITLE = '美国PCE同比'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P03-美国PCE同比.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
MONTHS = {m: i for i, m in enumerate(
    ['january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'], 1)}
URL = 'https://www.bea.gov/data/personal-consumption-expenditures-price-index'


def run():
    try:
        text = htmllib.unescape(re.sub(r'<[^>]+>', ' ', common.http_get(URL, retries=2, timeout=30)))
        text = re.sub(r'\s+', ' ', text)
        # 页面片段: Change From Month One Year Ago August 2026 +3.4% July 2026 +3.4% ...
        m = re.search(r'Change From Month One Year Ago\s+([A-Za-z]+)\s+(\d{4})\s+([-−–+]?[\d.]+)\s?%', text)
        if not m:
            raise RuntimeError('页面未解析到PCE同比句式')
        mon = MONTHS.get(m.group(1).lower())
        if not mon:
            raise RuntimeError(f'月份解析失败: {m.group(1)}')
        val = float(m.group(3).replace('−', '-').replace('–', '-'))
        label = f'{m.group(2)}-{mon:02d}'
        date = common.parse_date_label(label)
        common.save_row(CSV_PATH, date, {
            '数值': str(round(val, 2)), '单位': '%',
            '数据来源': 'BEA(美国经济分析局)',
            '备注': f'{label}PCE价格指数当月同比'}, COLUMNS)
        return '成功', f'{date} PCE同比={val}%'
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))