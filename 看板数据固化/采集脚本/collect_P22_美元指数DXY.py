# -*- coding: utf-8 -*-
"""P22 大宗商品-美元指数DXY：主通道=新浪外汇日K(DINIW)；东财100.UDI自动降级。
2026-11-04切换（东财push2限流常发）；固化历史不回写只补缺失，近2日允许勘误(v18.8)。
v18.9起主流程收敛至 common.collect_series（五件套样板），本文件仅保留词条常量。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 22
TITLE = '美元指数DXY'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P22-美元指数DXY.csv')


def run():
    return common.collect_series(
        CSV, primary='sina', kind='fx', sina_sym='DINIW', em_secid='100.UDI',
        unit='点', note='美元指数(UDI)收盘')


if __name__ == '__main__':
    print(common.run_collector(globals()))
