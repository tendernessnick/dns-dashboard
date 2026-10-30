# -*- coding: utf-8 -*-
"""P40 大宗商品-铝A00现货+期货：现货=生意社铝基准价(detail-482,代理口径)；期货主力=东财113.alM(沪铝主连)日K回填近250个交易日"""
import csv
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common
from ppi_100ppi import parse_ppi_detail

PID = 40
TITLE = '铝A00'
BACKFILL = 'full_refresh'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P40-铝A00.csv')
COLUMNS = ['数据日期', '数值', '单位', '期货主力元/吨', '数据来源', '备注']
OLD_COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
URL = 'https://www.100ppi.com/rawmex/detail-482.html'  # 生意社"铝"基准价页
FUT_SECID = '113.alM'
FUT_NAME = '沪铝主连'
FUT_NOTE = '沪铝主连收盘(东财回填)'
SPOT_NOTE = '铝A00代理口径(生意社铝基准价)'


def _migrate():
    """旧5列表头 → 新6列(插入期货主力元/吨)，保留历史行。"""
    if not os.path.exists(CSV):
        return
    with open(CSV, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames == COLUMNS:
            return
        if list(reader.fieldnames or []) != OLD_COLUMNS:
            return
        rows = list(reader)
    out = [{**r, '期货主力元/吨': ''} for r in rows]
    with open(CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out)


def run():
    try:
        _migrate()
        kl = common.em_kline(FUT_SECID, lmt=250)
        if not kl:
            raise RuntimeError('期货日K为空')
        common.bulk_backfill(CSV, kl, '期货主力元/吨',
                             unit='元/吨', source='东方财富', note=FUT_NOTE)
        time.sleep(1)
        info = parse_ppi_detail(common.hw_check_get(URL))
        common.save_row(CSV, info['date'], {'数值': info['price'], '单位': info['unit'],
                                            '数据来源': '生意社', '备注': SPOT_NOTE}, COLUMNS)
        detail = (f"{info['date']} 现货={info['price']}{info['unit']}, 较昨日{info['change'] or 'NA'}; "
                  f"期货{FUT_NAME}({FUT_SECID})回填{len(kl)}天, 最新{kl[-1][0]}={kl[-1][1]}")
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        detail = f'失败原因: {e}'
        return '失败', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))