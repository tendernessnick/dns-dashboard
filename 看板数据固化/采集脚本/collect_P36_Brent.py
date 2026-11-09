# -*- coding: utf-8 -*-
"""P36 大宗商品-布伦特原油：新浪hf_OIL实时行情取最新价，GlobalFutures日K回填近一年收盘。
v18.9：日K取数收敛至 common.sina_global_kline，落库改bulk_backfill一次读写。"""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 36
TITLE = '布伦特原油'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '大宗商品-P36-布伦特原油.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']


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
        kl = common.sina_global_kline('OIL', 365)
        kl = [(d, c) for d, c in kl if d < date_str and 20 <= c <= 200]
        if kl:
            n, _ = common.bulk_backfill(CSV_PATH, kl, '数值', unit='美元/桶',
                                        source='新浪财经', note='布伦特原油日K收盘',
                                        fill_empty_only=False)
            detail += f'；日K回填{n}行'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', repr(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))   # v18.8：统一走包装器（计时/日志/超时兜底）
