# -*- coding: utf-8 -*-
"""P42 手机厂商新品动态图文：IT之家RSS关键词过滤 → 逐篇抓文章页(标题/首图/段落)落盘
图文数据/手机新品发布/<采集日>/<标题>/（正文md+照片+_meta.json），供看板P42图文卡（70_review渲染）。
chips机械提取(价格/品牌)、摘要照录文章首段，无需AI提炼。
原RSS feed(手机新品.json)通道退役停显。用法：python collect_P42_手机新品.py [本次最多采集篇数，默认4]"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import _article_common as art
from _news_common import fetch_rss, parse_items, fetch_ithome_article, chips_from_title

PID, TITLE = 42, '手机厂商新品动态图文'
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # 看板数据固化
DST = os.path.join(BASE, '图文数据', '手机新品发布')
KEYS = ['手机', '旗舰', '快充', '充电', '电池', '发布', '首发', '折叠屏',
        'iphone', 'galaxy', '小米', '华为', 'oppo', 'vivo', '荣耀', '一加', '真我']
BRANDS = ('小米', '华为', 'OPPO', 'vivo', '荣耀', '三星', '一加', '真我', '苹果', 'iPhone', 'Galaxy', '红米')


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
    items = parse_items(xml, keywords=KEYS)
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
        if not img or len(paras) < 3:      # 无图/正文过短不入库
            skipped += 1
            continue
        pdate = (dt or now).astimezone(tz8).date().isoformat()
        name_final = (t2 or title)[:60]
        chips = chips_from_title(t2 or title, BRANDS) + ['IT之家']
        name, photos = art.save_article(
            DST, url=url, prod_name=name_final, md_title=(t2 or title),
            pdate=pdate, tag='新品动态', paras=paras[:12], img_urls=[img], download=_download,
            source_line='来源：IT之家 ｜ 原文：' + url,
            note_line='采集说明：collect_P42_手机新品.py 正文段落照录；chips机械提取、摘要照录首段。',
            await_ai=False, summary=paras[0][:160])
        new.append(name)
        if not photos:
            missing.append(name)
    if not new and not existing:
        return '失败', f'无命中落盘(候选{len(items)}, 无图/短稿跳过{skipped})'
    detail = (f'手机新品图文 · 新增{len(new)}篇{new if new else ""}，'
              f'库存{len(existing) + len(new)}篇'
              + (f'，无图/短稿跳过{skipped}篇' if skipped else ''))
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
