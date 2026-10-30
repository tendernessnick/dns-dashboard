# -*- coding: utf-8 -*-
"""P71 行业数据-品类增速：国家统计局最新发布页找社会消费品零售总额新闻稿，解析通讯器材类当月零售额与同比
历史回填（2024-06~2026-09共26点）为一次性考证：见 _p71_backfill.py 与 ../品类增速考证-E.md；
本采集器只负责每月自动抓"最新月"，历史行按日期upsert保留、勿手工改。"""
import os
import re
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

LIST_URL = 'https://www.stats.gov.cn/sj/zxfb/'
BASE = 'https://www.stats.gov.cn'
CSV = os.path.join(common.CSV_DIR, '行业数据-P71-品类增速.csv')
COLUMNS = ['数据日期', '通讯器材类同比%', '零售额(亿元)', '单位', '数据来源', '备注']

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


def _find_latest_article():
    html = _get(LIST_URL)
    links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]*社会消费品零售总额[^<]*)', html)
    if not links:
        raise RuntimeError('发布列表未找到社会消费品零售总额条目')
    href, title = links[0]
    if href.startswith('./'):
        href = href[2:]
    if href.startswith('/'):
        href = BASE + href
    elif not href.startswith('http'):
        href = f'{LIST_URL.rstrip("/")}/{href}'
    return href, title.strip()


def run():
    try:
        art_url, title = _find_latest_article()
        html = _get(art_url)
    except Exception as e:  # noqa: BLE001
        return '失败', f'抓取失败: {e}'
    # 表格行解析：通讯器材类 | 当月值 | 当月同比 | 累计值 | 累计同比
    text = re.sub(r'<[^>]+>', '|', html)
    text = re.sub(r'&nbsp;|&#160;', ' ', text)
    text = re.sub(r'\|+', '|', text)
    text = re.sub(r'\s+', ' ', text)
    nums = None
    for m in re.finditer(r'通讯器材类((?:\|[\s|.-]*)*\|[-\d.]+(?:\|[\s|.-]*)*\|[-\d.]+(?:\|[\s|.-]*)*\|[-\d.]+)', text):
        vals = [x for x in re.split(r'\|+', m.group(1)) if re.fullmatch(r'-?\d+(?:\.\d+)?', x.strip())]
        if len(vals) >= 2:
            nums = [float(v) for v in vals[:4]]
            break
    if not nums:
        return '失败', f'未解析到通讯器材类数据行: {title}'
    yoy, retail = nums[1], nums[0]
    cum_retail, cum_yoy = (nums[2], nums[3]) if len(nums) >= 4 else (None, None)
    if not (0 < retail < 100000 and -100 < yoy < 200):
        return '失败', f'量级异常: 零售额{retail} 同比{yoy}'
    # 数据期：标题“2026年1—9月份”→当月为9月；“2026年9月份”→9月
    my = (re.search(r'(\d{4})年1\s*[—–-]\s*(\d{1,2})月份', title)
          or re.search(r'(\d{4})年(\d{1,2})月份', title))
    if not my:
        return '失败', f'标题未解析到数据期: {title}'
    date_str = common.parse_date_label(f'{my.group(1)}-{int(my.group(2)):02d}')
    cum_note = f'；{my.group(1)}年1-{my.group(2)}月累计{cum_retail:g}亿元、同比{cum_yoy:+g}%' if cum_retail else ''
    common.save_row(CSV, date_str, {
        '通讯器材类同比%': yoy,
        '零售额(亿元)': retail,
        '数据来源': '国家统计局',
        '备注': f'当月值（{title[:40]}）{cum_note}',
    }, COLUMNS)
    detail = f'{date_str[:7]}月 通讯器材类同比{yoy:+g}% 零售额{retail:g}亿元'
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))