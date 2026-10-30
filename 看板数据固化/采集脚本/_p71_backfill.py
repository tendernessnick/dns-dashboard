# -*- coding: utf-8 -*-
"""P71 品类增速历史回填辅助（一次性考证工具，非run_all采集器，文件名不带collect_前缀）。
爬 stats.gov.cn/sj/zxfb 列表页(index.html, index_1.html…)回溯到 START_MONTH，
抓每月《社会消费品零售总额》新闻稿，解析"通讯器材类"行（当月零售额/当月同比），
upsert进 行业数据-P71-品类增速.csv，并打印品类增速考证-E.md所需的markdown表。
用法：python _p71_backfill.py [起始月YYYY-MM，默认2024-07]
"""
import html as htmllib
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

BASE = 'https://www.stats.gov.cn'
LIST_URL = f'{BASE}/sj/zxfb/'
CSV = os.path.join(common.CSV_DIR, '行业数据-P71-品类增速.csv')
COLUMNS = ['数据日期', '通讯器材类同比%', '零售额(亿元)', '数据来源', '备注']
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': common.UA, 'Accept-Language': 'zh-CN,zh;q=0.9'})


def _get(url, retries=3, timeout=35):
    last = None
    for i in range(retries):
        try:
            r = SESSION.get(url, timeout=timeout)
            r.encoding = 'utf-8'
            if r.status_code == 200:
                return r.text
            last = RuntimeError(f'HTTP {r.status_code}')
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(3)
    raise RuntimeError(f'GET失败 {url}: {last}')


def _abs(href):
    if href.startswith('./'):
        href = href[2:]
    if href.startswith('/'):
        return BASE + href
    if not href.startswith('http'):
        return f'{LIST_URL.rstrip("/")}/{href}'
    return href


def crawl_articles(start_month):
    """翻列表页直到最旧条目早于start_month，收集社零月度稿[(标题, URL)]。"""
    found, seen = [], set()
    for page in range(0, 80):
        url = LIST_URL if page == 0 else f'{LIST_URL}index_{page}.html'
        html = _get(url)
        items = re.findall(r'<a[^>]+href="([^"]+)"[^>]*title=["\']([^"\']*)["\']', html)
        items += re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]{6,120})', html)
        for href, title in items:
            title = htmllib.unescape(title).strip()
            if '社会消费品零售总额' in title and re.search(r'202\d年', title):
                u = _abs(href)
                if u not in seen:
                    seen.add(u)
                    found.append((title, u))
        # 用页面上的日期文本判断是否够旧（列表页每条目带发布日期）
        dates = re.findall(r'202\d-\d\d-\d\d', html)
        oldest = min(dates) if dates else ''
        print(f'  列表页{page}: {oldest}~{max(dates) if dates else ""}，累计社零稿{len(found)}篇', flush=True)
        if oldest and oldest[:7] < start_month:
            break
        time.sleep(1.5)
    return found


SEP = r'(?:[\s|.-]*\|)*[\s|.-]*'  # 表格压平后的空白/竖线分隔（只在后续确有数字时才吞管道）
NUM = r'[-\d.]+'
NUM_RE = re.compile(r'通讯器材类(' + SEP + NUM + SEP + NUM
                    + ''.join('(?:' + SEP + NUM + ')?' for _ in range(6)) + r')')


def parse_article(title, url):
    """解析通讯器材类行。返回dict或None。
    月度稿表为4列（当月额/当月同比/累计额/累计同比）；1—2月合并稿仅2列（1-2月合计额/同比）。
    2026年起标题改为累计口径（如"1—4月份"/"上半年"），表内仍含当月列，按4列解析当月(N月)。"""
    html = _get(url)
    text = re.sub(r'<[^>]+>', '|', html)
    text = re.sub(r'&nbsp;|&#160;', ' ', text)
    text = re.sub(r'\|+', '|', text)
    text = re.sub(r'\s+', ' ', text)
    m = NUM_RE.search(text)
    if not m:
        return None
    vals = [x for x in re.split(r'\|+', m.group(1)) if re.fullmatch(r'-?\d+(?:\.\d+)?', x.strip())]
    if not vals:
        return None
    nums = [float(v) for v in vals[:4]] + [None] * (4 - min(4, len(vals)))
    my1 = re.search(r'(\d{4})年1\s*[—–－-]\s*(\d{1,2})月份', title)
    myh = re.search(r'(\d{4})年上半年', title)
    my2 = re.search(r'(\d{4})年(\d{1,2})月份', title)
    if my1:
        y, mo = int(my1.group(1)), int(my1.group(2))
        combined = mo == 2
    elif myh:
        y, mo, combined = int(myh.group(1)), 6, False
    elif my2:
        y, mo, combined = int(my2.group(1)), int(my2.group(2)), False
    else:
        return None
    retail, yoy = nums[0], nums[1]
    if not combined and len(vals) < 4:
        return None  # 非合并稿必须4列（当月额/当月同比/累计额/累计同比），防止把累计额当当月
    if yoy is None or not (-100 < yoy < 200) or not (0 < retail < 100000):
        return None
    pub = re.search(r'/t(\d{8})_\d+', url)
    pub_date = f'{pub.group(1)[:4]}-{pub.group(1)[4:6]}-{pub.group(1)[6:]}' if pub else ''
    return {'year': y, 'month': mo, 'combined': combined, 'retail': nums[0], 'yoy': nums[1],
            'cum_retail': nums[2], 'cum_yoy': nums[3], 'pub_date': pub_date, 'url': url, 'title': title}


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else '2024-07'
    print(f'回溯起始月：{start}')
    arts = crawl_articles(start)
    arts.sort(key=lambda t: t[1])
    print(f'\n共{len(arts)}篇社零月度稿，开始逐篇解析：')
    rows = []
    for title, url in arts:
        try:
            r = parse_article(title, url)
        except Exception as e:  # noqa: BLE001
            r = None
            print(f'  [失败] {title}: {e}')
        time.sleep(1.5)
        if not r:
            print(f'  [未解析] {title}')
            continue
        label = f'{r["year"]}年{r["month"]:02d}月' + ('(1-2月合并)' if r['combined'] else '')
        print(f'  {label}: 当月零售额{r["retail"]}亿元, 同比{r["yoy"]:+}% | {r["title"][:44]}')
        rows.append(r)
    rows.sort(key=lambda r: (r['year'], r['month']))
    print('\n==== 写CSV ====')
    for r in rows:
        if r['combined']:
            if r['month'] != 2:
                print(f'  跳过异常合并稿 {r["year"]}-{r["month"]}')
                continue
            date_str = f'{r["year"]}-02-28'
            note = f'1—2月合并发布口径（单月值统计局不拆分），期末记2月末；{r["title"][:44]}'
        else:
            date_str = common.parse_date_label(f'{r["year"]}-{r["month"]:02d}')
            cum = f'；{r["year"]}年1-{r["month"]}月累计{r["cum_retail"]:g}亿元、同比{r["cum_yoy"]:+g}%' \
                if r['cum_retail'] else ''
            note = f'当月值（{r["title"][:44]}）{cum}'
        common.save_row(CSV, date_str, {
            '通讯器材类同比%': r['yoy'],
            '零售额(亿元)': r['retail'],
            '数据来源': f'国家统计局月度稿（原文, {r["pub_date"]}）',
            '备注': note,
        }, COLUMNS)
        print(f'  {date_str}  同比{r["yoy"]:+g}%  额{r["retail"]:g}')
    print('\n==== 考证E.md表格（复制用） ====')
    print('| 月份 | 通讯器材类当月同比% | 当月零售额(亿元) | 来源 | 发布日期 | URL |')
    print('|---|---|---|---|---|---|')
    for r in rows:
        label = f'{r["year"]}-{r["month"]:02d}' + ('(1—2月合并)' if r['combined'] else '')
        print(f'| {label} | {r["yoy"]:+g}% | {r["retail"]:g} | 国家统计局《{r["title"]}》 | {r["pub_date"]} | {r["url"]} |')


if __name__ == '__main__':
    main()
