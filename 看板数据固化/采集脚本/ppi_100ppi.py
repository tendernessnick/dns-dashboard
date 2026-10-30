# -*- coding: utf-8 -*-
"""生意社(100ppi) rawmex 详情页通用解析器（供P28/P39/P40复用）。
用法：html = common.hw_check_get(url); info = parse_ppi_detail(html)
返回 {name, price, unit, date, change}；date为YYYY-MM-DD（由"更新时间:MM-DD"补全年份）。"""
import datetime
import re


def parse_ppi_detail(html):
    """从生意社详情页HTML解析基准价信息。解析不到价格时抛RuntimeError。"""
    if not html or len(html) < 2000:
        raise RuntimeError('生意社页面内容过短')

    def _find(pat, cast=str):
        m = re.search(pat, html)
        return cast(m.group(1).strip()) if m else None

    price = _find(r'price-fb01_1"[^>]*>\s*([\d,\.]+)', lambda s: float(s.replace(',', '')))
    if price is None:
        raise RuntimeError('未解析到基准价(price-fb01_1)')

    unit = _find(r'price-fb01_2">([^<]+)') or '元/吨'
    name = _find(r'<title>\s*([^<]*?)基准价') or ''
    upd = _find(r'更新时间：</span>([\d\- :]+)')

    # MM-DD 补全年份：若落在未来则归为去年（跨年保护）
    date = None
    if upd:
        m = re.match(r'(\d{1,2})-(\d{1,2})', upd.strip())
        if m:
            mo, dy = int(m.group(1)), int(m.group(2))
            y = datetime.date.today().year
            try:
                d = datetime.date(y, mo, dy)
                if d > datetime.date.today() + datetime.timedelta(days=1):
                    d = datetime.date(y - 1, mo, dy)
                date = d.isoformat()
            except ValueError:
                pass
    if date is None:
        date = datetime.date.today().isoformat()

    change = _find(r'title="较昨日">\s*([+\-][\d.]+%)\s*<')
    return {'name': name, 'price': price, 'unit': unit, 'date': date, 'change': change}


if __name__ == '__main__':
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import common
    info = parse_ppi_detail(common.hw_check_get('https://www.100ppi.com/rawmex/detail-492.html'))
    print(info)
