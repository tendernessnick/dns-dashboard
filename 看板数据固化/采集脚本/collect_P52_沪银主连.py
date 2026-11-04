# -*- coding: utf-8 -*-
"""P52 大宗商品-沪银主连：东方财富113.agm日K回填近120个交易日（元/千克）；东财限流自动降级新浪期货日K（AG0）"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 52
TITLE = '沪银主连'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P52-沪银主连.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
SECID = '113.agm'
SINA_SYM = 'AG0'   # 限流备用通道：新浪国内期货主力连续


def run():
    try:
        try:
            snap = common.em_get(SECID)
            snap_note = None
        except Exception as se:  # noqa: BLE001
            # 快照降级（来源归一期P-C3）：快照仅作核验，日K成功即写入
            snap, snap_note = None, f'快照失败降级({str(se)[:40]})'
        time.sleep(1)
        src = '东方财富'
        try:
            kl = common.em_kline(SECID, lmt=120)
        except Exception as ee:  # noqa: BLE001
            # 日K限流降级：新浪国内期货主力连续日K（收盘口径，缺当日盘中，次日采集自动补齐）
            time.sleep(2)
            kl = common.sina_kline('hf_' + SINA_SYM, y=1)
            src = '新浪财经'
        if not kl:
            raise RuntimeError('日K为空')
        note = '沪银主连收盘' if src == '东方财富' else '沪银主连收盘（东财限流降级·新浪通道）'
        for date, close in kl:
            common.save_row(CSV, date, {'数值': close, '单位': '元/千克',
                                        '数据来源': src, '备注': note}, COLUMNS)
        last_d, last_v = kl[-1]
        tag = f'回填{len(kl)}天' + ('' if src == '东方财富' else '(新浪降级)')
        if snap is None:
            detail = f'{tag}, 最新{last_d}={last_v}, {snap_note}'
        elif src != '东方财富':
            detail = f'{tag}, 最新{last_d}={last_v}, 快照核验跳过(跨源)'
        else:
            snap_v = float(snap.get('f43'))
            chk = '一致' if abs(snap_v - last_v) / max(snap_v, 1e-9) < 0.02 else '偏差'
            detail = f'{tag}, 最新{last_d}={last_v}, 快照{snap_v}({chk})'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        detail = f'失败原因: {e}'
        return '失败', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
