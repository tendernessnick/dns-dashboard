# -*- coding: utf-8 -*-
"""P24 大宗商品-EUR/CNY：新浪fx_seurcny实时报价取最新价（仅当前值）"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 24
TITLE = 'EUR/CNY'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P24-EURCNY.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
CODE = 'fx_seurcny'


def run():
    try:
        hq = common.sina_hq([CODE])
        f = hq.get(CODE)
        if not f or len(f) < 18 or not f[1]:
            raise RuntimeError(f'新浪{CODE}无有效字段: {f}')
        val = round(float(f[1]), 4)          # 第2字段=最新价
        date = common.parse_date_label(f[17])  # 末字段=行情日期
        common.save_row(CSV, date, {'数值': val, '单位': '人民币/欧元',
                                    '数据来源': '新浪财经', '备注': '欧元兑人民币即期'}, COLUMNS)
        detail = f'{date} EUR/CNY={val}'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        detail = f'失败原因: {e}'
        return '失败', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))