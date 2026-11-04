# -*- coding: utf-8 -*-
"""P22 大宗商品-美元指数DXY：主通道=新浪外汇日K(DINIW)近1年；东财100.UDI降为备用。
2026-11-04切换（东财push2限流常发）；固化历史不回写，只补缺失日期。"""
import csv
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 22
TITLE = '美元指数DXY'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P22-美元指数DXY.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
SECID = '100.UDI'      # 东财备用通道
SINA_SYM = 'DINIW'


def run():
    try:
        try:
            kl = common.sina_forex_kline(SINA_SYM, y=1)
            src, note = '新浪财经', '美元指数(UDI)收盘(新浪日K)'
        except Exception as se:  # noqa: BLE001
            time.sleep(2)
            kl = common.em_kline(SECID, lmt=120)
            src, note = '东方财富', '美元指数(UDI)收盘(东财备用)'
        if not kl:
            raise RuntimeError('日K为空')
        have = set()
        if os.path.exists(CSV):
            with open(CSV, encoding='utf-8-sig', newline='') as f:
                have = {r['数据日期'] for r in csv.DictReader(f)}
        new = [(d, c) for d, c in kl if d not in have]
        for date, close in new:
            common.save_row(CSV, date, {'数值': close, '单位': '点',
                                        '数据来源': src, '备注': note}, COLUMNS)
        last_d, last_v = kl[-1]
        try:
            spot = common.sina_hq([SINA_SYM])[SINA_SYM]
            chk = '一致' if abs(float(spot[1]) - last_v) / max(float(spot[1]), 1e-9) < 0.02 else '偏差'
        except Exception:  # noqa: BLE001
            chk = '跳过'
        detail = f'新增{len(new)}天, 最新{last_d}={last_v}({src}), 实时核验{chk}'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        detail = f'失败原因: {e}'
        return '失败', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
