# -*- coding: utf-8 -*-
"""P92 竞对同业-Amazon月销代理：充电类榜单TOP1商品详情页解析"bought in past month"月购量下限"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PID = 92
TITLE = 'Amazon月销代理'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '竞对同业-P92-Amazon月销代理.csv')
COLS = ['数据日期', 'ASIN', '月购下限', '月购上限', '数据来源', '备注']
ZGBS = 'https://www.amazon.com/Best-Sellers-Cell-Phones-Accessories/zgbs/wireless'
UA = {'User-Agent': common.UA, 'Accept-Language': 'en-US,en;q=0.9'}


def _to_int(num, unit):
    v = float(num)
    return int(v * {'K': 1e3, 'M': 1e6}.get(unit, 1))


def run():
    try:
        import requests
        s = requests.Session()
        s.headers.update(UA)
        r0 = s.get(ZGBS, timeout=30)  # 先取榜单页建立会话cookie
        if r0.status_code != 200:
            raise RuntimeError(f'榜单页HTTP {r0.status_code}')
        time.sleep(1)
        asins = re.findall(r'data-asin="([0-9A-Z]{10})"', r0.text)
        if not asins:
            raise RuntimeError('榜单页未解析到商品ASIN')
        asin = asins[0]
        r = s.get(f'https://www.amazon.com/dp/{asin}', timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f'详情页HTTP {r.status_code}')
        t = r.text
        i = t.find('past month')
        if i < 0:
            raise RuntimeError(f'详情页无"past month"月销标识 ASIN={asin}')
        seg = t[max(0, i - 600):i + 100]
        m = re.search(r'([\d.]+)([KM]?)\+?\s*bought', seg)
        if not m:
            raise RuntimeError(f'月销文本解析失败: {re.sub(chr(92)+"s+", " ", seg)[-120:]}')
        # 可见原文（去标签）截取，如 "10K+ bought in past month"
        vis = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', seg))
        mr = re.search(r'([\d.,]+[KM]?\+?\s*bought\s+in\s+past\s+month)', vis) \
            or re.search(r'([\d.,]+[KM]?\+?\s*bought[^,;.]*)', vis)
        raw = mr.group(1).strip() if mr else ''
        has_plus = '+' in seg[max(0, m.start() - 5):m.end()]
        lower = _to_int(m.group(1), m.group(2))
        upper = '' if has_plus else lower  # "N+"为下限, 无+为确切值
        common.save_row(CSV, common.TODAY, {
            'ASIN': asin,
            '月购下限': lower,
            '月购上限': upper,
            '数据来源': f'Amazon商品详情页 /dp/{asin}',
            '备注': f'原文"{raw}"；区间口径: {lower}+' if has_plus else f'原文"{raw}"',
        }, COLS)
        detail = f'TOP1 {asin} 月购下限{lower}' + ('+' if has_plus else '')
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))