# -*- coding: utf-8 -*-
"""P30 大宗商品-沪金主连：东财113.aum日K主通道（元/克），限流自动降级新浪期货日K（AU0）；
东财快照f43核验（跨源/快照失败如实标注）。
v18.9起主流程收敛至 common.collect_series（五件套样板），本文件仅保留词条常量。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 30
TITLE = '沪金主连'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P30-沪金主连.csv')


def run():
    return common.collect_series(
        CSV, primary='em', kind='fut', sina_sym='AU0', em_secid='113.aum',
        unit='元/克', note='沪金主连收盘', fill_empty_only=False)


if __name__ == '__main__':
    print(common.run_collector(globals()))
