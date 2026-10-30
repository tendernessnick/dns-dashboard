# -*- coding: utf-8 -*-
"""P34 大宗商品-快充协议芯片(多SKU)：立创商城商品页JSON-LD解析 LDR6028/CH224K/IP2726/LDR6328 单价(元/颗)与库存。
商品页ID经 Bing(site:item.szlcsc.com)/实测确认在售：LDR6028=3222591, CH224K=1060460, IP2726=3269586, LDR6328=3222592。
so.szlcsc.com搜索接口有WAF(JS挑战)，故直接抓商品页。"""
import csv
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 34
TITLE = '快充协议芯片LDR6028'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '大宗商品-P34-LDR6028芯片.csv')
# (CSV列名, 立创商品页ID, 型号)
SKUS = [
    ('LDR6028元', 3222591, 'LDR6028'),
    ('CH224K元', 1060460, 'CH224K'),
    ('IP2726元', 3269586, 'IP2726'),
    ('LDR6328元', 3222592, 'LDR6328'),
]
COLUMNS = ['数据日期'] + [c for c, _, _ in SKUS] + ['单位', '数据来源', '备注']


def _parse(html):
    m = re.search(r'"offers":\{"@type":"Offer","priceCurrency":"CNY","price":([\d.]+)'
                  r'.*?"inventoryLevel":\{"@type":"QuantitativeValue","value":(\d+)', html)
    if m:
        return m.group(1), m.group(2)
    p = re.search(r'og:product:price" content="([\d.]+)"', html)
    s = re.search(r'"stockNumber":(\d+)', html)
    if p and s:
        return p.group(1), s.group(1)
    return None, None


def _migrate():
    """旧单SKU表头(单价(元)/库存) → 新多SKU表头：历史LDR6028价归入LDR6028元列，库存折入备注。"""
    if not os.path.exists(CSV_PATH):
        return
    with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames == COLUMNS:
            return
        if list(reader.fieldnames or []) != OLD_COLUMNS:
            return  # 未知表头不擅动，交由save_row兜底
        rows = list(reader)
    out = []
    for r in rows:
        note = r.get('备注', '') or ''
        if r.get('库存'):
            note = (note + f'；库存{r["库存"]}').strip('；')
        out.append({'数据日期': r.get('数据日期', ''), 'LDR6028元': r.get('单价(元)', ''),
                    'CH224K元': '', 'IP2726元': '', 'LDR6328元': '',
                    '数据来源': r.get('数据来源', ''), '备注': note})
    with open(CSV_PATH, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out)


def run():
    try:
        _migrate()
        vals, stocks, misses = {}, [], []
        for col, item_id, mpn in SKUS:
            html = common.http_get(f'https://item.szlcsc.com/{item_id}.html',
                                   referer='https://www.szlcsc.com/')
            if mpn not in html:
                misses.append(f'{mpn}:页面无型号')
                time.sleep(1)
                continue
            price, stock = _parse(html)
            if price and 0.01 <= float(price) <= 1000:
                vals[col] = price
            else:
                misses.append(f'{mpn}:价格未解析或异常({price})')
            if stock is not None:
                stocks.append(f'{mpn}库存{stock}')
            time.sleep(1)
        if not vals:
            return '失败', f'全部SKU解析失败: {misses}'
        parts = ['立创现货报价'] + stocks
        if misses:
            parts.append('缺:' + ','.join(misses))
        note = ';'.join(parts)
        common.save_row(CSV_PATH, common.TODAY, {
            **vals, '数据来源': '立创商城 szlcsc.com', '备注': note}, COLUMNS)
        ok = ' '.join(f'{k.rstrip("元")}={v}' for k, v in vals.items())
        detail = f'{common.TODAY} {ok}; {";".join(stocks)}' + (f'; 缺{misses}' if misses else '')
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', repr(e)


if __name__ == '__main__':
    print('P34', TITLE, run())
