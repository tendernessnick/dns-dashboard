# -*- coding: utf-8 -*-
"""P43 行业数据-换机周期：Counterpoint换机周期预测报告页解析（全球智能手机换机周期，2029E 40.4个月，2023峰值43.4）"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

URL = 'https://counterpointresearch.com/en/reports/smartphone-replacement-cycle-forecast-2016-2029'
CSV = os.path.join(common.CSV_DIR, '行业数据-P43-换机周期.csv')
COLUMNS = ['数据日期', '换机周期(月)', '单位', '数据来源', '备注']


def run():
    try:
        html = common.http_get(URL, retries=2, timeout=30)
    except Exception as e:  # noqa: BLE001
        return '失败', f'抓取失败: {e}'
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\\+"', '"', text)
    text = re.sub(r'\s+', ' ', text)
    # 最新/预测值：shorten to 40.4 months by 2029
    m = re.search(r'(?:gradually\s+)?shorten to ([\d.]+)\s*months? by (\d{4})', text)
    if not m:
        m = re.search(r'([\d.]+)\s*months? by (20\d{2})', text)
    if not m:
        return '失败', '未解析到预测换机周期，页面可能已改版'
    months = float(m.group(1))
    year = m.group(2)
    # 峰值：high of 43.4 months in 2023
    peak = ''
    mp = re.search(r'high of ([\d.]+)\s*months? in (\d{4})', text)
    if mp:
        peak = f'{mp.group(2)}年峰值{mp.group(1)}个月(受疫情影响)；2024年43.0个月'
    if not (20 <= months <= 60):
        return '失败', f'换机周期数值异常: {months}'
    date_str = common.parse_date_label(year)
    common.save_row(CSV, date_str, {
        '换机周期(月)': months,
        '数据来源': 'Counterpoint Research',
        '备注': peak or '全球智能手机换机周期预测值',
    }, COLUMNS)
    detail = f'{year}E换机周期{months}个月; {peak}'
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))