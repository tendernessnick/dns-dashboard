# -*- coding: utf-8 -*-
"""P27 大宗商品-沪铜主连：主通道=新浪期货日K(CU0)近1年；东财113.cuM降为备用。
2026-11-04切换（东财push2限流常发）；固化历史不回写，只补缺失日期；近2日允许勘误(v18.8)。"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 27
TITLE = '沪铜主连'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P27-沪铜主连.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
SECID = '113.cuM'      # 东财备用通道
SINA_SYM = 'CU0'


def run():
    try:
        try:
            kl = common.sina_kline('hf_' + SINA_SYM, y=1)
            src, note = '新浪财经', '沪铜主连收盘(新浪日K)'
        except Exception as se:  # noqa: BLE001
            time.sleep(2)
            kl = common.em_kline(SECID, lmt=120)
            src, note = '东方财富', '沪铜主连收盘(东财备用)'
        if not kl:
            raise RuntimeError('日K为空')
        # v18.8：一次读改写（旧逐日save_row整文件重写O(n²)），rework_days=2——盘中采到的
        # 当日/昨日未收盘价允许随后续运行修正，固化历史仍不回写
        n_new, n_rw = common.bulk_backfill(CSV, kl, '数值', unit='元/吨',
                                           source=src, note=note,
                                           fill_empty_only=True, rework_days=2)
        last_d, last_v = kl[-1]
        try:
            spot = common.sina_hq(['hf_' + SINA_SYM])['hf_' + SINA_SYM]
            chk = '一致' if abs(float(spot[0]) - last_v) / max(float(spot[0]), 1e-9) < 0.02 else '偏差'
        except Exception:  # noqa: BLE001
            chk = '跳过'
        detail = f'新增{n_new}天/近2日勘误{n_rw}天, 最新{last_d}={last_v}({src}), 实时核验{chk}'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        detail = f'失败原因: {e}'
        return '失败', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
