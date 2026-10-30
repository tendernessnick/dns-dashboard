# -*- coding: utf-8 -*-
"""P221-P224 竞对同业-主营构成：东财F10经营分析PageAjax的zygcfx，取最新报告期分产品(MAINOP_TYPE=2)各项占比做列
P221奥海 P222佳禾 P223海能 P224绿联；用法: python collect_P221_主营构成.py [P号|代码...]"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _comps import COMPANIES, select

URL = 'https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax?code=SZ{code}'
SOURCE = '东方财富F10 BusinessAnalysis/PageAjax(zygcfx) 分产品口径'
JOBS = [(221, '奥海'), (222, '佳禾'), (223, '海能'), (224, '绿联')]



PID = 221
TITLE = '竞对主营构成(P221-224)'
BACKFILL = 'full_refresh'
def run_one(pid, short):
    comp = COMPANIES[short]
    csv = os.path.join(common.CSV_DIR, f'竞对同业-P{pid}-{short}主营构成.csv')
    d = json.loads(common.http_get(URL.format(code=comp['code']),
                                   referer='https://emweb.securities.eastmoney.com/'))
    items = [x for x in (d.get('zygcfx') or [])
             if str(x.get('MAINOP_TYPE')) == '2' and x.get('MBI_RATIO') is not None]
    if not items:
        raise RuntimeError(f'{short} zygcfx无分产品行(MAINOP_TYPE=2)')
    date = max(str(x['REPORT_DATE'])[:10] for x in items)
    latest = [x for x in items if str(x['REPORT_DATE'])[:10] == date]
    latest.sort(key=lambda x: x.get('MAIN_BUSINESS_INCOME') or 0, reverse=True)
    # 去掉"合计/小计/其他补充"类汇总行
    latest = [x for x in latest
              if not re.search(r'合计|小计|总计', str(x.get('ITEM_NAME', '')))]
    if not (1 <= len(latest) <= 15):
        raise RuntimeError(f'{short} {date} 分产品行数异常: {len(latest)}')
    names = [re.sub(r'\s+', '', str(x['ITEM_NAME'])) for x in latest]
    cols = ['数据日期'] + [f'{n}%' for n in names] + ['单位', '数据来源', '备注']
    values = {f'{n}%': round(float(x['MBI_RATIO']) * 100, 2)
              for n, x in zip(names, latest)}
    total = sum(values.values())
    values['数据来源'] = SOURCE
    values['备注'] = (f'{len(latest)}项业务合计占比{total:.1f}%, '
                     f'按主营收入降排列(占比为占当期营收比重)')
    common.save_row(csv, date, values, cols)
    detail = f'{date} ' + ', '.join(f'{n}{v}%' for n, v in zip(names, values_list(values, names)))
    return '成功', detail


def values_list(values, names):
    return [values[f'{n}%'] for n in names]


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