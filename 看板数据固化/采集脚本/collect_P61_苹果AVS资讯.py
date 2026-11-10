# -*- coding: utf-8 -*-
"""P61 苹果AVS资讯图文：充电头网新闻页按 AVS/苹果 关键词过滤 → 逐篇抓文章页落盘
图文数据/苹果AVS资讯/<采集日>/<标题>/（正文md+照片+_meta.json），供看板P61图文卡（70_review渲染）。
通道与P90同（fetch_ctw curl_cffi）；chips机械提取、摘要照录首段，无需AI提炼。
说明：AVS为低频主题，单轮0新增属正常（图文卡展示库存最近6篇）。
原feed(avs资讯.json)通道退役停显。用法：python collect_P61_苹果AVS资讯.py [本次最多采集篇数，默认3]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import _article_common as art
from _news_common import fetch_ctw, parse_ctw, extract_ctw_article, chips_from_title

PID, TITLE = 61, '苹果AVS资讯图文'
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # 看板数据固化
DST = os.path.join(BASE, '图文数据', '苹果AVS资讯')
CTW_HOME = 'https://www.chongdiantou.com'
KEYS = ['AVS', '苹果']
BRANDS = ('苹果', 'Apple', 'AirPods', 'HomePod', 'Siri')


def _download(url, fp):
    from curl_cffi import requests as cr
    try:
        r = cr.get(url, impersonate='chrome', timeout=40, headers={'Referer': CTW_HOME + '/'})
        if r.status_code == 200 and len(r.content) > 3000:
            tmp = fp + '.part'
            with open(tmp, 'wb') as f:
                f.write(r.content)
            os.replace(tmp, fp)   # 原子写
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def run():
    limit = 3
    for a in sys.argv[1:]:
        if a.isdigit():
            limit = max(1, int(a))
    os.makedirs(DST, exist_ok=True)
    existing = art.scan_existing(DST)
    items = parse_ctw(fetch_ctw('/archives/category/news'))
    home = parse_ctw(fetch_ctw('/'))  # 首页合并提高覆盖
    seen, merged = set(), []
    for it in items + home:
        if it[2] not in seen:
            seen.add(it[2])
            merged.append(it)
    picked = [(d, t, u) for d, t, u in merged if any(k.lower() in t.lower() for k in KEYS)]
    if not picked:
        return '成功', '关键词无命中(AVS/苹果低频主题属正常)，库存图文卡继续展示最近篇目'
    new, missing, skipped = [], [], 0
    for dt, title, url in picked:
        if len(new) >= limit:
            break
        if url in existing:
            continue
        t2, pdate, tag, paras, imgs = extract_ctw_article(fetch_ctw(url[len(CTW_HOME):]))
        if len(paras) < 5:                       # 正文过短（嵌入稿/解析异常）不入库
            skipped += 1
            continue
        name_final = (t2 or title)[:60]
        chips = chips_from_title(t2 or title, BRANDS) + ['充电头网']
        name, photos = art.save_article(
            DST, url=url, prod_name=name_final, md_title=(t2 or title),
            pdate=pdate or dt.strftime('%Y-%m-%d'), tag=tag or 'AVS', paras=paras[:12],
            img_urls=imgs[:2], download=_download,
            source_line='来源：充电头网 ｜ 原文：' + url,
            note_line='采集说明：collect_P61_苹果AVS资讯.py 正文段落照录；chips机械提取、摘要照录首段。',
            await_ai=False, summary=paras[0][:160])
        new.append(name)
        if not photos:
            missing.append(name)
    if not new and not existing:
        return '失败', f'无命中落盘(候选{len(picked)}, 短稿跳过{skipped})'
    detail = (f'苹果AVS图文 · 新增{len(new)}篇{new if new else ""}，'
              f'库存{len(existing) + len(new)}篇'
              + (f'，短稿跳过{skipped}篇' if skipped else '')
              + (f'，{len(missing)}篇未取到照片{missing}' if missing else ''))
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
