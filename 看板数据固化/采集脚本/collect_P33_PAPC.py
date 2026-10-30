# -*- coding: utf-8 -*-
"""P33 大宗商品-PA/PC工程塑料：生意社PC/PA6/PA66参考价（多指标）。
当日：hw_check_get工程塑料频道(gcsl)解析最新参考价（原逻辑）。
历史：逐页爬取各品种"商品报价动态"新闻列表→文章正文提取每日基准价
（生意社无公开结构化历史；文章正文含"X月X日生意社XX基准价为YYYY元/吨"。
已存在的日期行自动跳过，日常运行仅增量爬新文章）。"""
import datetime
import os
import re
import time

import common

PID = 33
TITLE = 'PA/PC工程塑料'
CSV_PATH = os.path.join(common.CSV_DIR, '大宗商品-P33-PA-PC工程塑料.csv')
COLUMNS = ['数据日期', 'PC', 'PA6', 'PA66', '单位', '数据来源', '备注']
URL = 'https://www.100ppi.com/chanye/gcsl.html'
# 品种 → (新闻列表产品id, 量级区间)
PRODUCTS = {'PC': (825, (8000, 40000)), 'PA6': (826, (5000, 40000)), 'PA66': (824, (5000, 60000))}
LIST_URL = 'https://www.100ppi.com/news/list-15-121111-{pid}-{page}.html'
BACKFILL_PAGES = 8  # 每品种回填页数（每页约20天，8页≈4个月）


def _pick(html, name):
    """优先"M月D日，PC参考价为xxxx"行（带完整时间戳）；退回新闻标题"PC基准价"。返回(日期, 值字符串)"""
    m = re.search(rf'(\d{{1,2}})月(\d{{1,2}})日，{name}参考价为([\d.]+)', html)
    if m:
        ts = re.search(r'(\d{4})-(\d{2})-(\d{2}) \d{2}:\d{2}:\d{2}', html[m.end():m.end() + 400])
        if ts:
            return f'{ts.group(1)}-{ts.group(2)}-{ts.group(3)}', m.group(3)
        y = datetime.date.today().year
        return common.parse_date_label(f'{y}-{int(m.group(1)):02d}-{int(m.group(2)):02d}'), m.group(3)
    m = re.search(rf'/news/detail-(\d{{8}})-\d+\.html"[^>]*>\s*\d{{1,2}}月\d{{1,2}}日生意社{name}基准价为([\d.]+)元/吨', html)
    if m:
        ymd, val = m.group(1), m.group(2)
        return f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}', val
    return None, None


def _existing_cells():
    """CSV中已有数值的(日期, 列)集合——CSV一天多列，须按列判断避免串品种跳过。"""
    out = set()
    if os.path.exists(CSV_PATH):
        import csv as _csv
        with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
            for r in _csv.DictReader(f):
                d = r.get('数据日期', '')
                for col in ('PC', 'PA6', 'PA66'):
                    if (r.get(col) or '').strip():
                        out.add((d, col))
    return out


def backfill_news(pages=BACKFILL_PAGES):
    """逐品种爬"商品报价动态"文章回填历史基准价，返回新增行数。"""
    have = _existing_cells()
    added = 0
    for name, (pid, (lo, hi)) in PRODUCTS.items():
        for page in range(1, pages + 1):
            try:
                html = common.hw_check_get(LIST_URL.format(pid=pid, page=page))
            except Exception:  # noqa: BLE001
                break  # 翻到底/被拦截则该品种结束
            arts = re.findall(
                r'href="(https?://www\.100ppi\.com/news/detail-(\d{8})-\d+\.html)"[^>]*>\s*'
                rf'{name}商品报价动态（(\d{{4}}-\d{{2}}-\d{{2}}）)', html)
            if not arts:
                break
            for url, ymd, tdate in arts:
                date = f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}'
                if (date, name) in have:
                    continue
                try:
                    body = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', common.hw_check_get(url)))
                    m = re.search(rf'\d{{1,2}}月\d{{1,2}}日生意社{name}基准价为([\d,\.]+)元/吨', body)
                    if not m:
                        continue
                    v = float(m.group(1).replace(',', ''))
                    if not (lo <= v <= hi):
                        continue
                    common.save_row(CSV_PATH, date, {
                        name: f'{v:g}', '数据来源': '生意社 100ppi.com',
                        '备注': f'{name}基准价（报价动态文章考证）'}, COLUMNS)
                    added += 1
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(0.15)
    return added


def run():
    try:
        html = common.hw_check_get(URL)
        vals, dates = {}, {}
        for name in ('PC', 'PA6', 'PA66'):
            d, v = _pick(html, name)
            if not d or not v:
                return '失败', f'{name}未解析到参考价'
            lo, hi = PRODUCTS[name][1]
            if not (lo <= float(v) <= hi):
                return '失败', f'{name}量级异常 {v}'
            vals[name], dates[name] = v, d
        date_str = max(dates.values())
        remark = '生意社工程塑料参考价'
        if len(set(dates.values())) > 1:
            remark += '；期次:' + ','.join(f'{k}={dates[k]}' for k in ('PC', 'PA6', 'PA66'))
        common.save_row(CSV_PATH, date_str, {
            'PC': vals['PC'], 'PA6': vals['PA6'], 'PA66': vals['PA66'],
            '数据来源': '生意社 100ppi.com', '备注': remark},
            COLUMNS)
        n = backfill_news()
        detail = (f'{date_str} PC={vals["PC"]} PA6={vals["PA6"]} PA66={vals["PA66"]} 元/吨'
                  + (f'；历史新增{n}天' if n else ''))
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', repr(e)


if __name__ == '__main__':
    print('P33', TITLE, run())
