# -*- coding: utf-8 -*-
"""P38 大宗商品-空运CTK同比：IATA官方RSS找"Air Cargo Demand"新闻稿，正则提取同比百分比（月度，日期=对应月月末）"""
import calendar
import os
import re

import common

PID = 38
TITLE = '空运CTK同比'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '大宗商品-P38-空运CTK同比.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
RSS_URL = 'https://www.iata.org/api/rss/pressrelease'
MONTHS = {m: i for i, m in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July',
     'August', 'September', 'October', 'November', 'December'], 1)}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})  # 兼容pubDate缩写 Sep/Oct...
NEG = re.compile(r'\b(slips?|falls?|declines?|drops?|dips?|down)\b', re.I)


def _month_end(y, mo):
    return f'{y:04d}-{mo:02d}-{calendar.monthrange(y, mo)[1]:02d}'


def run():
    try:
        x = common.http_get(RSS_URL)
        items = re.findall(r'<item>(.*?)</item>', x, re.S)
        found = []
        for it in items:
            t = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', it, re.S)
            d = re.search(r'<pubDate>(.*?)</pubDate>', it)
            if not (t and d):
                continue
            title = t.group(1).strip()
            if 'air cargo demand' not in title.lower():
                continue
            pm = re.search(r'(\d+(?:\.\d+)?)\s*%', title)
            mm = re.search(r'\bin\s+([A-Za-z]+)', title)
            if not (pm and mm and mm.group(1).rstrip(',') in MONTHS):
                continue  # 标题格式不符则跳过该条，不编造
            mo = MONTHS[mm.group(1).rstrip(',')]
            pd_ = re.search(r'(\w+), (\d+) (\w+) (\d+)', d.group(1))
            if not pd_:
                continue
            y = int(pd_.group(4))
            pub_mo = MONTHS.get(pd_.group(3), 1)
            year = y - 1 if mo > pub_mo else y  # 1月发布的12月数据
            val = float(pm.group(1))
            if NEG.search(title):
                val = -val
            if abs(val) > 30:
                continue
            date_str = _month_end(year, mo)
            found.append((date_str, val, title))
        if not found:
            return '失败', 'RSS中未找到Air Cargo Demand条目'
        for date_str, val, title in found:
            common.save_row(CSV_PATH, date_str, {
                '数值': f'{val:g}', '单位': '%',
                '数据来源': 'IATA pressrelease RSS',
                '备注': f'全球空运货物需求同比（{title}）'},
                COLUMNS)
        found.sort()
        detail = '；'.join(f'{d_}: {v:+g}%' for d_, v, _ in found)
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', repr(e)


if __name__ == '__main__':
    print('P38', TITLE, run())
