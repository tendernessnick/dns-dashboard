# -*- coding: utf-8 -*-
"""P41 Apple生态新闻图文：IT之家RSS关键词过滤 → 逐篇抓文章页(标题/首图/段落)落盘
图文数据/苹果生态新闻/<采集日>/<标题>/（正文md+照片+_meta.json），供看板P41图文卡（70_review渲染）。
chips机械提取(价格/品牌)、摘要照录文章首段，无需AI提炼（仿P93/P94免AI先例）。
原RSS feed(apple新闻.json)通道退役停显；MacRumors英文备选一并退役（图文卡以中文源为准）。
用法：python collect_P41_Apple新闻.py [本次最多采集篇数，默认4]"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import _article_common as art
from _news_common import (fetch_rss, parse_items, fetch_ithome_article, chips_from_title,
                          load_keys, audit_discards)

PID, TITLE = 41, 'Apple生态新闻图文'
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # 看板数据固化
DST = os.path.join(BASE, '图文数据', '苹果生态新闻')
KEYS = ['苹果',   # 兜底词表（词表csv缺失时回退；运营改词请编辑 关键词表.csv） 'apple', 'iphone', 'ipad', 'macbook', 'mac ', 'imac', 'airpods',
        'apple watch', 'vision pro', 'ios ', 'macos', 'm5', 'a19']
BRANDS = ('苹果', 'Apple', 'iPhone', 'iPad', 'MacBook', 'AirPods', 'Watch', 'Vision')


def _download(url, fp):
    data = common.http_bin(url, referer='https://www.ithome.com/', min_bytes=3000)
    if data:
        tmp = fp + '.part'
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, fp)   # 原子写
        return True
    return False


def run():
    limit = 4
    for a in sys.argv[1:]:
        if a.isdigit():
            limit = max(1, int(a))
    os.makedirs(DST, exist_ok=True)
    existing = art.scan_existing(DST)
    xml = fetch_rss('https://www.ithome.com/rss/', referer='https://www.ithome.com/')
    keys = load_keys('P41') or {'core': KEYS, 'exclude': []}
    drops = []
    items = parse_items(xml, keywords=keys['core'] or None, exclude=keys['exclude'] or None, _drop=drops)
    audit_discards('P41', [(None, t, u) for t, u in drops], set())   # B3: 被过滤标题留痕
    if not items:
        return '失败', 'IT之家RSS解析0条或关键词无命中'
    now = datetime.datetime.now(datetime.timezone.utc)
    tz8 = datetime.timezone(datetime.timedelta(hours=8))
    new, missing, skipped = [], [], 0
    for dt, title, url in items:
        if len(new) >= limit:
            break
        if url in existing:
            continue
        try:
            t2, img, paras = fetch_ithome_article(url)
        except Exception:  # noqa: BLE001
            skipped += 1
            continue
        if not img or len(paras) < 3:      # 无图/正文过短不入库（图文卡以图为要件）
            skipped += 1
            continue
        pdate = (dt or now).astimezone(tz8).date().isoformat()
        name_final = (t2 or title)[:60]
        chips = chips_from_title(t2 or title, BRANDS) + ['IT之家']
        name, photos = art.save_article(
            DST, url=url, prod_name=name_final, md_title=(t2 or title),
            pdate=pdate, tag='苹果生态', paras=paras[:12], img_urls=[img], download=_download,
            source_line='来源：IT之家 ｜ 原文：' + url,
            note_line='采集说明：collect_P41_Apple新闻.py 正文段落照录；chips机械提取、摘要照录首段。',
            await_ai=False, summary=paras[0][:160])
        new.append(name)
        if not photos:
            missing.append(name)
    if not new and not existing:
        return '失败', f'无命中落盘(候选{len(items)}, 无图/短稿跳过{skipped})'
    detail = (f'Apple生态图文 · 新增{len(new)}篇{new if new else ""}，'
              f'库存{len(existing) + len(new)}篇'
              + (f'，无图/短稿跳过{skipped}篇' if skipped else ''))
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
