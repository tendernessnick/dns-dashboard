# -*- coding: utf-8 -*-
"""P28 大宗商品-无氧铜杆(代理)：生意社铜基准价(detail-524)作代理口径（绝对价在登录墙内）"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common
from ppi_100ppi import parse_ppi_detail

PID = 28
TITLE = '无氧铜杆(代理)'
BACKFILL = 'rpa'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P28-无氧铜杆.csv')
COLUMNS = ['数据日期', '铜基准价(元/吨)', '单位', '数据来源', '备注']
URL = 'https://www.100ppi.com/rawmex/detail-524.html'  # 生意社"铜"基准价页


def run():
    try:
        info = parse_ppi_detail(common.hw_check_get(URL))
        common.save_row(CSV, info['date'],
                        {'铜基准价(元/吨)': info['price'], '单位': info['unit'], '数据来源': '生意社',
                         '备注': '无氧铜杆代理口径(生意社铜基准价)'}, COLUMNS)
        detail = (f"{info['date']} 铜(生意社)基准价={info['price']}{info['unit']}, "
                  f"较昨日{info['change'] or 'NA'}")
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        detail = f'失败原因: {e}'
        return '失败', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))