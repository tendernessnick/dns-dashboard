# -*- coding: utf-8 -*-
"""P26 大宗商品-LME铜：新浪hf_CAD实时价+全球期货日K回填近1年（美元/吨）"""
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 26
TITLE = 'LME铜'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '大宗商品-P26-LME铜价.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
CODE = 'hf_CAD'  # 新浪伦铜(LEM铜, CAD)
DAILY_URL = ('https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/'
             'GlobalFuturesService.getGlobalFuturesDailyKLine?symbol=CAD')


def sina_global_daily(days=370):
    """新浪全球期货日K（hf_CAD伦铜不适用国内InnerFutures接口）。返回[(date, close)]。"""
    txt = common.http_get(DAILY_URL, referer='https://finance.sina.com.cn/')
    m = re.search(r'\((\[.*\])\)', txt, re.S)
    if not m:
        raise RuntimeError('新浪全球日K解析失败')
    arr = json.loads(m.group(1))
    cut = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    return [(a['date'], float(a['close'])) for a in arr if a.get('date', '') >= cut and a.get('close')]


def run():
    try:
        hq = common.sina_hq([CODE])
        f = hq.get(CODE)
        if not f or not f[0]:
            raise RuntimeError(f'新浪{CODE}无有效字段: {f}')
        snap_v = float(f[0])       # 第1字段=最新价
        snap_d = common.parse_date_label(f[12])  # 日期字段
        kl = sina_global_daily(365)
        if not kl:
            raise RuntimeError('全球日K为空')
        dates = {d for d, _ in kl}
        for date, close in kl:
            common.save_row(CSV, date, {'数值': close, '单位': '美元/吨',
                                        '数据来源': '新浪财经', '备注': 'LME铜(伦铜)收盘'}, COLUMNS)
        extra = ''
        if snap_d not in dates:  # 实时日无K线时补实时行
            common.save_row(CSV, snap_d, {'数值': snap_v, '单位': '美元/吨',
                                          '数据来源': '新浪财经', '备注': 'LME铜(伦铜)实时'}, COLUMNS)
            extra = f'; 补实时{snap_d}={snap_v}'
        last_d, last_v = kl[-1]
        detail = f'回填{len(kl)}天({kl[0][0]}~{last_d}), K线末值{last_v}, 实时{snap_d}={snap_v}{extra}'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        detail = f'失败原因: {e}'
        return '失败', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))