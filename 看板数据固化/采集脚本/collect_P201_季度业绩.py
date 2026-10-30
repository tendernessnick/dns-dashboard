# -*- coding: utf-8 -*-
"""P201-P205 竞对同业-季度业绩：东财数据中心业绩报表接口RPT_LICO_FN_CPD回填近8个季度营收/净利及同比
P201奥海 P202佳禾 P203海能 P204绿联 P205安克；用法: python collect_P201_季度业绩.py [P号|代码...]"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _comps import COMPANIES, select

API = ('https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_LICO_FN_CPD'
       '&columns=SECURITY_CODE,REPORTDATE,TOTAL_OPERATE_INCOME,YSTZ,PARENT_NETPROFIT,SJLTZ,DATATYPE,ISNEW'
       '&filter=(SECURITY_CODE%3D%22{code}%22)&pageSize=14&sortColumns=REPORTDATE&sortTypes=-1')
SOURCE = '东方财富数据中心RPT_LICO_FN_CPD'
JOBS = [(201, '奥海'), (202, '佳禾'), (203, '海能'), (204, '绿联'), (205, '安克')]



PID = 201
TITLE = '竞对季度业绩(P201-205)'
BACKFILL = 'full_refresh'
def fetch_quarters(code):
    """返回按报告期去重后的行列表（报告期降序）。"""
    d = json.loads(common.http_get(API.format(code=code), referer='https://data.eastmoney.com/'))
    if not d.get('success'):
        raise RuntimeError(f'接口success={d.get("success")} message={d.get("message")}')
    rows, seen = [], set()
    for r in (d.get('result') or {}).get('data') or []:
        date = str(r.get('REPORTDATE', ''))[:10]
        if not date or date in seen:
            continue
        if r.get('TOTAL_OPERATE_INCOME') is None or r.get('PARENT_NETPROFIT') is None:
            continue  # 报告期数据未出全(如仅披露预告)
        seen.add(date)
        rows.append(r)
    return rows


def run_one(pid, short):
    comp = COMPANIES[short]
    csv = os.path.join(common.CSV_DIR, f'竞对同业-P{pid}-{short}季度业绩.csv')
    cols = ['数据日期', '营收亿元', '营收同比%', '净利亿元', '净利同比%', '单位', '数据来源', '备注']
    rows = fetch_quarters(comp['code'])
    if len(rows) < 8:
        raise RuntimeError(f'{short}仅取得{len(rows)}个季度(<8)')
    for r in rows:
        rev = round(r['TOTAL_OPERATE_INCOME'] / 1e8, 2)
        yoy = round(r['YSTZ'], 2) if r.get('YSTZ') is not None else ''
        npf = round(r['PARENT_NETPROFIT'] / 1e8, 2)
        nyoy = round(r['SJLTZ'], 2) if r.get('SJLTZ') is not None else ''
        if not (0.2 < rev < 3000):
            raise RuntimeError(f'{short} {r["REPORTDATE"][:10]} 营收量级异常: {rev}亿')
        common.save_row(csv, str(r['REPORTDATE'])[:10], {
            '营收亿元': rev, '营收同比%': yoy, '净利亿元': npf, '净利同比%': nyoy,
            '数据来源': SOURCE, '备注': r.get('DATATYPE') or '',
        }, cols)
    latest = rows[0]
    detail = (f'{len(rows)}个季度; 最新{latest["REPORTDATE"][:10]} '
              f'营收{latest["TOTAL_OPERATE_INCOME"]/1e8:.2f}亿({latest.get("YSTZ"):.1f}%), '
              f'净利{latest["PARENT_NETPROFIT"]/1e8:.2f}亿({latest.get("SJLTZ"):.1f}%)')
    return '成功', detail


def run(argv=None):
    """逐公司采集并各自写采集日志；整体返回run_all约定的(status, detail)。"""
    import time
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