# -*- coding: utf-8 -*-
"""P23 大宗商品-离岸USDCNH：主通道=新浪外汇日K(fx_susdcnh)；东财133.USDCNH自动降级。
2026-11-04切换（东财push2限流常发）；固化历史不回写只补缺失，近2日允许勘误(v18.8)。
v18.9起主流程收敛至 common.collect_series（五件套样板），本文件仅保留词条常量。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 23
TITLE = '离岸USDCNH'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P23-离岸USDCNH.csv')


def run():
    return common.collect_series(
        CSV, primary='sina', kind='fx', sina_sym='fx_susdcnh', em_secid='133.USDCNH',
        unit='人民币/美元', note='美元兑离岸人民币收盘')


if __name__ == '__main__':
    print(common.run_collector(globals()))
