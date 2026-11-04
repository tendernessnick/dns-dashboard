# -*- coding: utf-8 -*-
"""P56 产品品类-Qi2认证数：WPC无线充电联盟官方认证库API(/ajax/products/qi)全量拉取，统计Qi2(MPP功率档或2.x版本)数量"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PID = 56
TITLE = 'Qi2认证数'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '产品品类-P56-Qi2认证数.csv')
COLS = ['数据日期', 'Qi2认证数', '全库总数', '单位', '数据来源', '备注']
URL = 'https://jpsapi.wirelesspowerconsortium.com/ajax/products/qi'


def run():
    try:
        arr = json.loads(common.http_get(URL, timeout=60))
        if not isinstance(arr, list) or not arr:
            raise RuntimeError(f'API返回异常: type={type(arr).__name__}')
        total = len(arr)
        qi2 = 0
        for it in arr:
            power = str(it[5]).upper() if len(it) > 5 else ''
            ver = str(it[7]) if len(it) > 7 else ''
            if power.startswith('MPP') or ver.startswith('2.'):
                qi2 += 1
        # 本月新增（认证日期在本自然月）
        month_start = datetime.date.today().replace(day=1).isoformat()
        new_month = sum(1 for it in arr if len(it) > 8 and str(it[8])[:10] >= month_start)
        common.save_row(CSV, common.TODAY, {
            'Qi2认证数': qi2,
            '全库总数': total,
            '数据来源': 'WPC认证库 jpsapi.wirelesspowerconsortium.com/ajax/products/qi',
            '备注': f'Qi2=功率档MPP开头或版本2.x；本月新增认证{new_month}条',
        }, COLS)
        detail = f'Qi2={qi2}/{total}, 本月新增{new_month}'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))