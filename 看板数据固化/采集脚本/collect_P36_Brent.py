# -*- coding: utf-8 -*-
"""P36 大宗商品-布伦特原油：新浪hf_OIL实时行情取最新价，GlobalFutures日K接口回填近一年收盘"""
import datetime
import json
import os
import re
import time

import common

PID = 36
TITLE = '布伦特原油'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '大宗商品-P36-布伦特原油.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
KLINE_URL = ('https://stock2.finance.sina.com.cn/futures/api/jsonp.php/x/'
             'GlobalFuturesService.getGlobalFuturesDailyKLine?symbol=OIL')


def run():
    try:
        # 1) 实时行情：字段0=最新价，7=昨结算，12=日期
        hq = common.sina_hq(['hf_OIL'])
        f = hq.get('hf_OIL')
        if not f or not f[0]:
            return '失败', '新浪行情无hf_OIL数据'
        price = float(f[0])
        date_str = f[12] if re.match(r'\d{4}-\d{2}-\d{2}', f[12] or '') else common.TODAY
        if not (20 <= price <= 200):
            return '失败', f'油价量级异常 {price}'
        common.save_row(CSV_PATH, date_str, {
            '数值': f[0], '单位': '美元/桶',
            '数据来源': '新浪财经 hq.sinajs.cn', '备注': '布伦特原油hf_OIL实时价'},
            COLUMNS)
        detail = f'{date_str} 最新价={price} 美元/桶'
        # 2) 日K回填近一年（仅早于实时行日期的交易日）
        time.sleep(1)
        txt = common.http_get(KLINE_URL, referer='https://finance.sina.com.cn/')
        m = re.search(r'\((\[.*\])\)', txt, re.S)
        if not m:
            return '失败', '新浪日K解析失败'
        arr = json.loads(m.group(1))
        cut = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()
        n = 0
        for a in arr:
            d, c = a['date'], a['close']
            if d >= cut and d < date_str and 20 <= float(c) <= 200:
                common.save_row(CSV_PATH, d, {
                    '数值': str(c), '单位': '美元/桶',
                    '数据来源': '新浪财经 GlobalFutures日K', '备注': '布伦特原油日K收盘(回填)'},
                    COLUMNS)
                n += 1
        detail += f'；日K回填{n}行'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', repr(e)


if __name__ == '__main__':
    print('P36', TITLE, run())
