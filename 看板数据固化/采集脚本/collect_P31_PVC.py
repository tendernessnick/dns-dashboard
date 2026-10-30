# -*- coding: utf-8 -*-
"""P31 大宗商品-PVC现货+期货：现货=生意社PVC基准价(vane/detail-107,SG-5)；期货主力=东财114.VM(PVC主连)日K回填近250个交易日"""
import csv
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 31
TITLE = 'PVC现货价'
BACKFILL = 'full_refresh'
CSV_PATH = os.path.join(common.CSV_DIR, '大宗商品-P31-PVC现货价.csv')
COLUMNS = ['数据日期', '数值', '单位', '期货主力元/吨', '数据来源', '备注']
OLD_COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
URL = 'https://www.100ppi.com/vane/detail-107.html'
FUT_SECID = '114.VM'
FUT_NAME = 'PVC主连'
FUT_NOTE = 'PVC主连收盘(东财回填)'
SPOT_NOTE = 'PVC SG-5现货基准价'
SPOT_RANGE = (1000, 20000)


def _migrate():
    """旧5列表头 → 新6列(插入期货主力元/吨)，保留历史行。"""
    if not os.path.exists(CSV_PATH):
        return
    with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames == COLUMNS:
            return
        if list(reader.fieldnames or []) != OLD_COLUMNS:
            return
        rows = list(reader)
    out = [{**r, '期货主力元/吨': ''} for r in rows]
    with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out)


def _spot(html):
    m = re.search(r'/news/detail-(\d{8})-\d+\.html"[^>]*>\s*\d{1,2}月\d{1,2}日生意社PVC基准价为([\d.]+)元/吨', html)
    if not m:
        return None, None
    ymd, val = m.group(1), m.group(2)
    return f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}', val


def run():
    try:
        _migrate()
        kl = common.em_kline(FUT_SECID, lmt=250)
        if not kl:
            raise RuntimeError('期货日K为空')
        common.bulk_backfill(CSV_PATH, kl, '期货主力元/吨',
                             unit='元/吨', source='东方财富', note=FUT_NOTE)
        time.sleep(1)
        html = common.hw_check_get(URL)
        date_str, val = _spot(html)
        fut_detail = f'期货{FUT_NAME}({FUT_SECID})回填{len(kl)}天, 最新{kl[-1][0]}={kl[-1][1]}'
        if not date_str or not val:
            return '失败', f'未匹配到现货基准价条目; {fut_detail}'
        v = float(val)
        if not (SPOT_RANGE[0] <= v <= SPOT_RANGE[1]):
            return '失败', f'基准价量级异常 {v}; {fut_detail}'
        common.save_row(CSV_PATH, date_str, {'数值': val, '单位': '元/吨',
                                             '数据来源': '生意社 100ppi.com', '备注': SPOT_NOTE}, COLUMNS)
        detail = f'{date_str} 现货={val}元/吨; {fut_detail}'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', repr(e)


if __name__ == '__main__':
    print('P31', TITLE, run())
