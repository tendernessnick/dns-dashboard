# -*- coding: utf-8 -*-
"""P26 大宗商品-LME铜：新浪hf_CAD实时价+全球期货日K回填近1年（美元/吨）。
v18.9：日K取数收敛至 common.sina_global_kline，落库改bulk_backfill一次读写。"""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 26
TITLE = 'LME铜'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P26-LME铜价.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
CODE = 'hf_CAD'  # 新浪伦铜(LEM铜, CAD)


def run():
    try:
        hq = common.sina_hq([CODE])
        f = hq.get(CODE)
        if not f or not f[0]:
            raise RuntimeError(f'新浪{CODE}无有效字段: {f}')
        snap_v = float(f[0])       # 第1字段=最新价
        snap_d = common.parse_date_label(f[12])  # 日期字段
        kl = common.sina_global_kline('CAD', 365)
        if not kl:
            raise RuntimeError('全球日K为空')
        dates = {d for d, _ in kl}
        n_new, _ = common.bulk_backfill(CSV, kl, '数值', unit='美元/吨',
                                        source='新浪财经', note='LME铜(伦铜)收盘',
                                        fill_empty_only=False)
        extra = ''
        if snap_d not in dates:  # 实时日无K线时补实时行
            common.save_row(CSV, snap_d, {'数值': snap_v, '单位': '美元/吨',
                                          '数据来源': '新浪财经', '备注': 'LME铜(伦铜)实时'}, COLUMNS)
            extra = f'; 补实时{snap_d}={snap_v}'
        last_d, last_v = kl[-1]
        detail = f'回填{n_new}天({kl[0][0]}~{last_d}), K线末值{last_v}, 实时{snap_d}={snap_v}{extra}'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        detail = f'失败原因: {e}'
        return '失败', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
