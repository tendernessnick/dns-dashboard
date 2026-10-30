# -*- coding: utf-8 -*-
"""P29 大宗商品-废铜(光亮铜)：富宝f139铜链SSR页解析"光亮铜价格指数"（单指标）"""
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 29
TITLE = '废铜(光亮铜)'
BACKFILL = 'rpa'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P29-废铜光亮铜.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
URL = 'https://www.f139.com/chain/copper'
PAT = re.compile(r'(\d{4})年(\d{1,2})月(\d{1,2})日光亮铜价格指数报([\d,]+)元/吨')


def run():
    try:
        html = common.http_get(URL, referer='https://www.f139.com/')
        hits = []
        for m in PAT.finditer(html):
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
            hits.append((d, float(m.group(4).replace(',', ''))))
        if not hits:
            raise RuntimeError('页面未解析到"光亮铜价格指数报N元/吨"')
        hits.sort()
        date, val = hits[-1]  # 取最新一期
        common.save_row(CSV, date, {'数值': val, '单位': '元/吨',
                                    '数据来源': '富宝资讯', '备注': '光亮铜价格指数'}, COLUMNS)
        detail = f'{date} 光亮铜价格指数={val:g}元/吨 (页面命中{len(hits)}期)'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        detail = f'失败原因: {e}'
        return '失败', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))