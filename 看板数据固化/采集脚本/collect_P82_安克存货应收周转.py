# -*- coding: utf-8 -*-
"""P82 竞对同业-安克存货应收周转：东财F10主财务指标RPT_F10_FINANCE_MAINFINADATA年报期CHZZL/YSZKZZL
（来源归一期M1迁移：原新浪财务指标页解析→东财datacenter API，与P211-214四家同源；
2025年报期两源数值抽样一致[4.0733/17.3042]，历史由save_row按日期自然补齐，旧行不被覆盖丢弃。）"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PID = 82
TITLE = '安克存货应收周转'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '竞对同业-P82-安克存货应收周转.csv')
COLS = ['数据日期', '存货周转率', '应收账款周转率', '单位', '数据来源', '备注']
API = ('https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA'
       '&columns=SECUCODE,REPORT_DATE,REPORT_TYPE,REPORT_DATE_NAME,CHZZL,YSZKZZL'
       '&filter=(SECUCODE%3D%22300866.SZ%22)(REPORT_TYPE%3D%22%E5%B9%B4%E6%8A%A5%22)'
       '&pageNumber=1&pageSize=8&sortTypes=-1&sortColumns=REPORT_DATE&source=HSF10&client=PC')


def run():
    try:
        d = json.loads(common.http_get(API, referer='https://emweb.securities.eastmoney.com/'))
        rows = (d.get('result') or {}).get('data') or []
        if not rows:
            raise RuntimeError('东财年报期数据为空')
        for r in rows:
            inv, ar = r.get('CHZZL'), r.get('YSZKZZL')
            if inv is None or ar is None:
                raise RuntimeError(f'{r["REPORT_DATE"][:10]} 周转率字段为空')
            if not (0.5 < inv < 20 and 1 < ar < 100):
                raise RuntimeError(f'数值超出合理量级: 存货周转{inv}, 应收周转{ar}')
            common.save_row(CSV, str(r['REPORT_DATE'])[:10], {
                '存货周转率': round(inv, 4),
                '应收账款周转率': round(ar, 4),
                '单位': '次/年',
                '数据来源': '东方财富F10 RPT_F10_FINANCE_MAINFINADATA(300866)',
                '备注': '年报期(12-31)口径，周转率年内累计可与季报期不可直接比较',
            }, COLS)
        latest = rows[0]
        detail = (f'{len(rows)}期年报; 最新{latest["REPORT_DATE"][:10]} '
                  f'存货周转{latest["CHZZL"]:.4f}, 应收周转{latest["YSZKZZL"]:.4f}')
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))
