# -*- coding: utf-8 -*-
"""P35 大宗商品-eMarker芯片(多SKU)：立创商城商品页JSON-LD解析 HUSB332A/HUSB332B 单价(元/颗)与库存。
商品页ID实测确认在售：HUSB332A_U31DA=8528245, HUSB332B_U31DA=8528243（同页相邻ID探测发现）。"""
import csv
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

PID = 35
TITLE = 'eMarker芯片HUSB332A'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '大宗商品-P35-HUSB332A芯片.csv')
# (CSV列名, 立创商品页ID, 型号)
SKUS = [
    ('HUSB332A元', 8528245, 'HUSB332A'),
    ('HUSB332B元', 8528243, 'HUSB332B'),
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
    """旧单SKU表头(单价(元)/库存) → 新多SKU表头：历史HUSB332A价归入HUSB332A元列，库存折入备注。"""
    if not os.path.exists(CSV_PATH):
        return
    with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames == COLUMNS:
            return
        if list(reader.fieldnames or []) != OLD_COLUMNS:
            return
        rows = list(reader)
    out = []
    for r in rows:
        note = r.get('备注', '') or ''
        if r.get('库存'):
            note = (note + f'；库存{r["库存"]}').strip('；')
        out.append({'数据日期': r.get('数据日期', ''), 'HUSB332A元': r.get('单价(元)', ''),
                    'HUSB332B元': '',
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
        parts = ['立创现货报价(USB Type-C eMarker)'] + stocks
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
    print('P35', TITLE, run())
