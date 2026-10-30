# -*- coding: utf-8 -*-
"""P82 竞对同业-安克存货应收周转：新浪财经财务指标页(GB2312)解析安克创新(300866)最新年报期存货/应收账款周转率"""
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PID = 82
TITLE = '安克存货应收周转'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '竞对同业-P82-安克存货应收周转.csv')
COLS = ['数据日期', '存货周转率', '应收账款周转率', '单位', '数据来源', '备注']
URL = ('https://money.finance.sina.com.cn/corp/go.php/vFD_FinancialGuideLine/'
       'stockid/300866/ctrl/{y}/displaytype/4.phtml')


def _year_rows(year):
    """抓取某年指标页，返回{报告期日期: (存货周转率, 应收账款周转率)}。"""
    html = common.http_get(URL.format(y=year), encoding='gb2312')
    dates = [d for d in re.findall(r'(20\d\d-\d\d-\d\d)', html)
             if d.startswith(str(year))]  # 表头报告期(按列序)
    if not dates:
        return {}
    rows = {}
    for name in ('存货周转率', '应收账款周转率'):
        m = re.search(name + r'\(次\)</a></td>(.*?)</tr>', html, re.S)
        if not m:
            raise RuntimeError(f'{year}页未找到{name}')
        vals = re.findall(r'<td>([\d.]+|--)</td>', m.group(1))
        if len(vals) < len(dates):
            raise RuntimeError(f'{year}页{name}值列数不足')
        for i, d in enumerate(dates):
            rows.setdefault(d, {})[name] = vals[i]
    return {d: (v['存货周转率'], v['应收账款周转率']) for d, v in rows.items()}


def run():
    try:
        today = datetime.date.today()
        # 取最新年报期(12-31)：先查当年页，无年报列再查上年页
        result, period = None, None
        for y in (today.year, today.year - 1):
            for d, v in sorted(_year_rows(y).items(), reverse=True):
                if d.endswith('-12-31') and v[0] not in ('--', '') and v[1] not in ('--', ''):
                    result, period = v, d
                    break
            if result:
                break
        if not result:
            raise RuntimeError('未找到最新年报期(12-31)的周转率数据')
        inv, ar = float(result[0]), float(result[1])
        if not (0.5 < inv < 20 and 1 < ar < 100):
            raise RuntimeError(f'数值超出合理量级: 存货周转{inv}, 应收周转{ar}')
        common.save_row(CSV, period, {
            '存货周转率': inv,
            '应收账款周转率': ar,
            '数据来源': '新浪财经 财务指标 vFD_FinancialGuideLine(300866)',
            '备注': '年报期(12-31)口径，周转率年内累计可与季报期不可直接比较',
        }, COLS)
        detail = f'{period} 存货周转率={inv}, 应收账款周转率={ar}'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))