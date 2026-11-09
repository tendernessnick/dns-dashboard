# -*- coding: utf-8 -*-
"""P27 大宗商品-沪铜主连：主通道=新浪期货日K(CU0)；东财113.cuM自动降级。
2026-11-04切换（东财push2限流常发）；固化历史不回写只补缺失，近2日允许勘误(v18.8)。
v18.9起主流程收敛至 common.collect_series（五件套样板），本文件仅保留词条常量。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 27
TITLE = '沪铜主连'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P27-沪铜主连.csv')


def run():
    return common.collect_series(
        CSV, primary='sina', kind='fut', sina_sym='CU0', em_secid='113.cuM',
        unit='元/吨', note='沪铜主连收盘')


if __name__ == '__main__':
    print(common.run_collector(globals()))
