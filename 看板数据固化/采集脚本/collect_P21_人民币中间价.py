# -*- coding: utf-8 -*-
"""P21 大宗商品-人民币中间价：中国货币网CcprHisNew接口取USD/CNY中间价，回填近60个交易日"""
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 21
TITLE = '人民币中间价'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P21-人民币中间价.csv')
COLUMNS = ['数据日期', '中间价', '单位', '数据来源', '备注']
URL = 'https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew'


def fetch_parity(days=60):
    """POST分页取USD/CNY中间价，返回近days条[(date, rate)]。"""
    start = (datetime.date.today() - datetime.timedelta(days=days + 45)).isoformat()
    end = datetime.date.today().isoformat()
    d = common.http_post(
        URL, as_json=True,
        data={'lang': 'CN', 'reference': '1', 'startDate': start, 'endDate': end,
              'pageNo': '1', 'pageSize': str(days)},
        referer='https://www.chinamoney.com.cn/chinese/bkccpr/')
    if str((d.get('head') or {}).get('rep_code')) != '200':
        raise RuntimeError(f'货币网返回异常: {str(d)[:200]}')
    head = (d.get('data') or {}).get('head') or []
    if 'USD/CNY' not in head:
        raise RuntimeError(f'返回货币对中无USD/CNY: {head[:5]}')
    idx = head.index('USD/CNY')
    records = d.get('records') or []
    out = []
    for rec in records:
        date = common.parse_date_label(rec.get('date', ''))
        vals = rec.get('values') or []
        if len(vals) > idx and vals[idx]:
            out.append((date, float(vals[idx])))
    if not out:
        raise RuntimeError('records为空，未取到中间价')
    out.sort(key=lambda x: x[0])
    return out[-days:]


def run():
    try:
        rows = fetch_parity(60)
        for date, rate in rows:
            common.save_row(CSV, date, {'中间价': rate, '数据来源': '中国货币网',
                                        '备注': '人民币兑美元中间价(USD/CNY)'}, COLUMNS)
        detail = f'回填{len(rows)}天, 最新{rows[-1][0]} 中间价{rows[-1][1]}'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        detail = f'失败原因: {e}'
        return '失败', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))