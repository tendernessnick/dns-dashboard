# -*- coding: utf-8 -*-
"""P23 大宗商品-离岸USDCNH：东方财富133.USDCNH日K回填近120个交易日"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 23
TITLE = '离岸USDCNH'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P23-离岸USDCNH.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
SECID = '133.USDCNH'


def run():
    try:
        snap = common.em_get(SECID)
        time.sleep(1)
        kl = common.em_kline(SECID, lmt=120)
        if not kl:
            raise RuntimeError('日K为空')
        for date, close in kl:
            common.save_row(CSV, date, {'数值': close, '单位': '人民币/美元',
                                        '数据来源': '东方财富', '备注': '美元兑离岸人民币收盘'}, COLUMNS)
        snap_v = float(snap.get('f43'))
        last_d, last_v = kl[-1]
        chk = '一致' if abs(snap_v - last_v) / max(snap_v, 1e-9) < 0.02 else '偏差'
        detail = f'回填{len(kl)}天, 最新{last_d}={last_v}, 快照{snap_v}({chk})'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        detail = f'失败原因: {e}'
        return '失败', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))