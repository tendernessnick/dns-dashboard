# -*- coding: utf-8 -*-
"""P37 大宗商品-SCFI运价指数：上海航交所SCFI详情页(SSR表格)解析综合指数两期，SCFIS页补欧线/美西分航线"""
import os
import re
import time

import requests

import common

PID = 37
TITLE = 'SCFI集装箱运价指数'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '大宗商品-P37-SCFI运价指数.csv')
COLUMNS = ['数据日期', '综合指数', '欧线', '美西', '单位', '数据来源', '备注']
BASE = 'https://www.sse.net.cn'


def _nums_cells(fragment):
    return re.findall(r'align="center">([\d.,]+)</td>', fragment)


def run():
    try:
        s = requests.Session()
        s.headers.update({'User-Agent': common.UA, 'Referer': BASE + '/'})
        # 1) SCFI页：综合指数 上期/本期
        h1 = s.get(BASE + '/index/singleIndex?indexType=scfi', timeout=25)
        h1.encoding = 'utf-8'
        if h1.status_code != 200:
            raise RuntimeError(f'SCFI HTTP {h1.status_code}')
        hd = re.search(r'上期<br>([\d-]*)</td>\s*<td>本期<br>([\d-]*)', h1.text)
        mrow = re.search(r'综合指数 Comprehensive Index</td>(.*?)</tr>', h1.text, re.S)
        if not (hd and mrow):
            return '失败', 'SCFI页未解析到表头/综合指数行'
        d_prev, d_curr = hd.group(1), hd.group(2)
        cells = _nums_cells(mrow.group(1))
        if len(cells) < 2 or not d_curr:
            return '失败', f'SCFI综合指数行异常 cells={cells}'
        v_prev, v_curr = cells[0], cells[1]
        if not (500 <= float(v_curr) <= 10000 and 500 <= float(v_prev) <= 10000):
            return '失败', f'综合指数量级异常 {v_prev}/{v_curr}'
        time.sleep(1)
        # 2) SCFIS页：欧线/美西（结算运价指数，周一期）
        h2 = s.get(BASE + '/index/singleIndex?indexType=scfis', timeout=25)
        h2.encoding = 'utf-8'
        if h2.status_code != 200:
            raise RuntimeError(f'SCFIS HTTP {h2.status_code}')
        hs = re.search(r'本期<br>([\d-]+)', h2.text)
        eu = us = None
        m = re.search(r'欧洲航线（基本港）Europe \(Base port\)</p></td>(.*?)</tr>', h2.text, re.S)
        if m:
            c = _nums_cells(m.group(1))
            eu = c[0] if c else None
        m = re.search(r'美西航线（基本港）USWC \(Base port\)</p></td>(.*?)</tr>', h2.text, re.S)
        if m:
            c = _nums_cells(m.group(1))
            us = c[0] if c else None
        scfis_date = hs.group(1) if hs else ''
        remark = 'SCFI综合指数；欧线/美西为SCFIS结算运价指数' + (f'（{scfis_date}期）' if scfis_date else '')
        vals = {'综合指数': v_curr,
                '数据来源': '上海航运交易所 sse.net.cn', '备注': remark}
        if eu:
            vals['欧线'] = eu
        if us:
            vals['美西'] = us
        common.save_row(CSV_PATH, d_curr, vals, COLUMNS)
        detail = f'{d_curr} 综合={v_curr} 欧线={eu} 美西={us}'
        # 3) 上期综合指数补历史行（缺欧线/美西，不覆盖已有值）
        if d_prev and d_prev < d_curr:
            common.save_row(CSV_PATH, d_prev, {
                '综合指数': v_prev,
                '数据来源': '上海航运交易所 sse.net.cn', '备注': 'SCFI综合指数(上期)'},
                COLUMNS)
            detail += f'；{d_prev} 综合={v_prev}'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', repr(e)


if __name__ == '__main__':
    print('P37', TITLE, run())
