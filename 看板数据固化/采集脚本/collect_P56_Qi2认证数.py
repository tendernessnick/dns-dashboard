# -*- coding: utf-8 -*-
"""P56 产品品类-Qi2认证数：WPC无线充电联盟官方认证库API(/ajax/products/qi)全量拉取，统计Qi2(MPP功率档或2.x版本)数量"""
import csv
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
COLS = ['数据日期', 'Qi2认证数', '全库总数', 'Qi2.2认证数(25W)', '单位', '数据来源', '备注']
URL = 'https://jpsapi.wirelesspowerconsortium.com/ajax/products/qi'


def run():
    try:
        arr = json.loads(common.http_get(URL, timeout=60))
        if not isinstance(arr, list) or not arr:
            raise RuntimeError(f'API返回异常: type={type(arr).__name__}')
        total = len(arr)
        qi2 = 0
        qi22 = 0
        for it in arr:
            power = str(it[5]).upper() if len(it) > 5 else ''
            ver = str(it[7]) if len(it) > 7 else ''
            if power.startswith('MPP') or ver.startswith('2.'):
                qi2 += 1
            if ver.startswith('2.2'):   # Qi2.2=25W档（2025版），版本字段2.2.x经WPC库实抓核验
                qi22 += 1
        # v18.8漂移护栏：位置索引取字段，列序变更会静默错数。Qi2认证只增不减，
        # 且单日增量有限——与上期相比减少或暴增即判列序变更，拒写防污染
        prev = prev22 = None
        try:
            if os.path.exists(CSV):
                with open(CSV, encoding='utf-8-sig', newline='') as f:
                    rows_p = list(csv.DictReader(f))
                if rows_p and str(rows_p[-1].get('Qi2认证数', '')).strip():
                    prev = int(rows_p[-1]['Qi2认证数'])
                if rows_p and str(rows_p[-1].get('Qi2.2认证数(25W)', '') or '').strip():
                    prev22 = int(rows_p[-1]['Qi2.2认证数(25W)'])
        except Exception:  # noqa: BLE001
            prev = prev22 = None
        if prev is not None and (qi2 < prev or qi2 > prev + 1000):
            raise RuntimeError(f'Qi2计数漂移异常(上期{prev}→本期{qi2})，疑似API列序变更，拒写')
        if prev22 is not None and (qi22 < prev22 or qi22 > prev22 + 1000):
            raise RuntimeError(f'Qi2.2计数漂移异常(上期{prev22}→本期{qi22})，疑似API列序变更，拒写')
        # 本月新增（认证日期在本自然月）
        month_start = datetime.date.today().replace(day=1).isoformat()
        new_month = sum(1 for it in arr if len(it) > 8 and str(it[8])[:10] >= month_start)
        common.save_row(CSV, common.TODAY, {
            'Qi2认证数': qi2,
            '全库总数': total,
            'Qi2.2认证数(25W)': qi22,
            '数据来源': 'WPC认证库 jpsapi.wirelesspowerconsortium.com/ajax/products/qi',
            '备注': (f'Qi2=功率档MPP开头或版本2.x；Qi2.2(25W)=版本2.2.x(2026-11-10起统计，'
                     f'历史未回溯)；本月新增认证{new_month}条'),
        }, COLS)
        detail = f'Qi2={qi2}/{total}, 其中Qi2.2(25W)={qi22}, 本月新增{new_month}'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))