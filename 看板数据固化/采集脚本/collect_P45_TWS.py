# -*- coding: utf-8 -*-
"""P45 行业数据-TWS：Counterpoint TWS成熟期洞察页解析（全球TWS销量2025E同比+3%）"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

URL = 'https://counterpointresearch.com/en/insights/tws-market-entering-maturity-poised-for-moderate-growth-through-2028'
CSV = os.path.join(common.CSV_DIR, '行业数据-P45-TWS.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']


def run():
    try:
        html = common.http_get(URL, retries=2, timeout=30)
    except Exception as e:  # noqa: BLE001
        return '失败', f'抓取失败: {e}'
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\\+"', '"', text)
    text = re.sub(r'\s+', ' ', text)
    # 全球TWS销量2025年同比+3%
    m = (re.search(r'increase by (\d+(?:\.\d+)?)\s*% YoY in (20\d{2})', text)
         or re.search(r'increase of (\d+(?:\.\d+)?)\s*% YoY in (20\d{2})', text)
         or re.search(r'grow(?:\w*) by (\d+(?:\.\d+)?)\s*% (?:YoY|year[- ]on[- ]year) in (20\d{2})', text, re.I))
    if not m:
        return '失败', '未解析到TWS销量同比，页面可能已改版'
    pct = float(m.group(1))
    year = m.group(2)
    if not (0 < pct < 50):
        return '失败', f'同比量级异常: {pct}%'
    date_str = common.parse_date_label(year)
    common.save_row(CSV, date_str, {
        '数值': pct,
        '单位': '%',
        '数据来源': 'Counterpoint Research',
        '备注': f'{year}E全球TWS销量同比增速（+{pct:g}%），50美元以下入门款为主要增长驱动',
    }, COLUMNS)
    detail = f'{year}E全球TWS销量同比+{pct:g}%'
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))