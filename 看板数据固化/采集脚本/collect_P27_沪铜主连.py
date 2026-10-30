# -*- coding: utf-8 -*-
"""P27 大宗商品-沪铜主连：东方财富113.cuM日K回填近120个交易日（元/吨）"""
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
SECID = '113.cuM'


def run():
    try:
        try:
            snap = common.em_get(SECID)
            snap_note = None
        except Exception as se:  # noqa: BLE001
            # 快照降级（来源归一期P-C3）：快照仅作核验，日K成功即写入
            snap, snap_note = None, f'快照失败降级({str(se)[:40]})'
        time.sleep(1)
        kl = common.em_kline(SECID, lmt=120)
        if not kl:
            raise RuntimeError('日K为空')
        for date, close in kl:
            common.save_row(CSV, date, {'数值': close, '单位': '元/吨',
                                        '数据来源': '东方财富', '备注': '沪铜主连收盘'}, COLUMNS)
        last_d, last_v = kl[-1]
        if snap is None:
            detail = f'回填{len(kl)}天, 最新{last_d}={last_v}, {snap_note}'
        else:
            snap_v = float(snap.get('f43'))
            chk = '一致' if abs(snap_v - last_v) / max(snap_v, 1e-9) < 0.02 else '偏差'
            detail = f'回填{len(kl)}天, 最新{last_d}={last_v}, 快照{snap_v}({chk})'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        detail = f'失败原因: {e}'
        return '失败', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))