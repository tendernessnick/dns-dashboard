# -*- coding: utf-8 -*-
"""P211-P214 竞对同业-存货应收周转：东财F10主财务指标RPT_F10_FINANCE_MAINFINADATA年报期CHZZL/YSZKZZL
P211奥海 P212佳禾 P213海能 P214绿联；用法: python collect_P211_存货应收周转.py [P号|代码...]"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _comps import COMPANIES, select

API = ('https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA'
       '&columns=SECUCODE,REPORT_DATE,REPORT_TYPE,REPORT_DATE_NAME,CHZZL,YSZKZZL'
       '&filter=(SECUCODE%3D%22{code}.SZ%22)(REPORT_TYPE%3D%22%E5%B9%B4%E6%8A%A5%22)'
       '&pageNumber=1&pageSize=3&sortTypes=-1&sortColumns=REPORT_DATE&source=HSF10&client=PC')
SOURCE = '东方财富F10 RPT_F10_FINANCE_MAINFINADATA'
JOBS = [(211, '奥海'), (212, '佳禾'), (213, '海能'), (214, '绿联')]



PID = 211
TITLE = '竞对存货应收周转(P211-214)'
BACKFILL = 'full_refresh'
def run_one(pid, short):
    comp = COMPANIES[short]
    csv = os.path.join(common.CSV_DIR, f'竞对同业-P{pid}-{short}存货应收周转.csv')
    cols = ['数据日期', '存货周转率次/年', '应收周转率次/年', '单位', '数据来源', '备注']
    d = json.loads(common.http_get(API.format(code=comp['code']),
                                   referer='https://emweb.securities.eastmoney.com/'))
    rows = (d.get('result') or {}).get('data') or []
    if len(rows) < 3:
        raise RuntimeError(f'{short}年报期数据不足3期: {len(rows)}')
    for r in rows:
        inv, ar = r.get('CHZZL'), r.get('YSZKZZL')
        if inv is None or ar is None:
            raise RuntimeError(f'{short} {r["REPORT_DATE"][:10]} 周转率字段为空')
        if not (0.2 < inv < 60 and 0.5 < ar < 200):
            raise RuntimeError(f'{short} 数值量级异常: 存货{inv} 应收{ar}')
        common.save_row(csv, str(r['REPORT_DATE'])[:10], {
            '存货周转率次/年': round(inv, 4),
            '应收周转率次/年': round(ar, 4),
            '数据来源': SOURCE,
            '备注': f'{r.get("REPORT_DATE_NAME", "")}年报口径(全年周转次数)',
        }, cols)
    latest = rows[0]
    detail = (f'{len(rows)}期年报; 最新{latest["REPORT_DATE"][:10]} '
              f'存货周转{latest["CHZZL"]:.2f}次/年, 应收周转{latest["YSZKZZL"]:.2f}次/年')
    return '成功', detail


def run(argv=None):
    ok, fails = [], []
    for pid, short in select(JOBS, argv):
        try:
            _, detail = run_one(pid, short)
            ok.append(f'P{pid} {detail}')
        except Exception as e:  # noqa: BLE001
            fails.append(f'P{pid} {e}')
        time.sleep(1)
    if fails:
        return '失败', '; '.join(fails)
    return '成功', '; '.join(ok)


if __name__ == '__main__':
    print(common.run_collector(globals()))