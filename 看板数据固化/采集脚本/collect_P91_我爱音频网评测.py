# -*- coding: utf-8 -*-
"""P91 我爱音频网·耳机评测图文：评测分类列表 → 新文章落盘 图文数据/我爱音频网评测/<采集日>/<产品名>/
（正文md + 照片N原图 + 基础_meta.json[待提炼=true]），供看板P91图文卡（70_review.js渲染）。
通道：requests 直连（52audio 无反爬，2026-11-05 验证，可行性验证结论归档于目录 索引.md）；
文章URL为去重主键；图片优先 OSS 原图（52audio-images.oss-cn-shenzhen.aliyuncs.com）。
chips/摘要由每日21:15定时任务AI提炼，提炼后删除"待提炼"字段。
v18.9：存量扫描/落盘/缺照补拍收敛至 _article_common，HTTP统一common会话，本文件仅保留站点钩子。
用法：python collect_P91_我爱音频网评测.py [本次最多采集篇数，默认3]"""
import datetime
import html as H
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import _article_common as art

PID, TITLE = 91, '我爱音频网·耳机评测图文'
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # 看板数据固化
DST = os.path.join(BASE, '图文数据', '我爱音频网评测')
LIST_PATH = '/archives/category/reviews/earphone'
_PREFIX = re.compile(r'^(评测|拆解报告|视频拆解|拆解)[：:｜]\s*')
_OSS = 'oss-cn-shenzhen'


def _cl(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', H.unescape(s or ''))).strip()


def _product(title):
    t = _cl(title)
    while True:
        t2 = _PREFIX.sub('', t).strip()
        if t2 == t:
            return t or _cl(title)
        t = t2


def _extract_article(html):
    """→ (标题, 发布日期, 子分类tag, 段落列表, 内容图URL列表[OSS优先])"""
    t = re.search(r'<title>([^<]+)</title>', html)
    title = _cl(t.group(1).split(' - ')[0]) if t else ''
    dm = (re.search(r'(20\d\d-\d\d-\d\d)', html[:2500])
          or re.search(r'(20\d\d年\d+月\d+日)', html[:2500]))   # v18.8：限定页头区，正文首个日期不再冒充发布日
    date = dm.group(1) if dm else ''
    if '年' in date and '月' in date:
        m = re.search(r'(20\d\d)年(\d+)月(\d+)日', date)
        date = f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    tag = ''
    for c in re.findall(r'category/reviews/([a-z_0-9]+)"[^>]*>([^<]{1,12})</a>', html):
        if c[1].strip() and c[1].strip() != '评测':
            tag = c[1].strip()
            break
    seg = (re.search(r'class="content-wrapper[^"]*"(.*)', html, re.S)
           or re.search(r'class="post-content[^"]*"(.*)', html, re.S)
           or re.search(r'<article(.*)', html, re.S))
    body = seg.group(1) if seg else html
    paras = [_cl(p) for p in re.findall(r'<p[^>]*>(.*?)</p>', body, re.S)]
    paras += [_cl(p) for p in re.findall(r'<li[^>]*>(.*?)</li>', body, re.S)]
    paras += [_cl(p) for p in re.findall(r'<div class="ace-line[^"]*"[^>]*>(.*?)</div>', body, re.S)]
    paras = [p for p in paras if len(p) > 4]
    noise = ('我爱音频网是国内最早', '稿件投递', 'info@52audio')
    paras = [p for p in paras if not any(p.startswith(n) or n in p[:30] for n in noise)]
    seen, uniq = set(), []
    for p in paras:
        if p not in uniq:
            uniq.append(p)
    paras = uniq
    for i, p in enumerate(paras):                     # 截掉文末版权/推广噪声
        if i > len(paras) * 0.6 and re.search(r'转载|版权|免责|内容说明', p):
            paras = paras[:i]
            break
    imgs, lazy = [], re.findall(r'data-(?:src|original)="(https?://[^"]+)"', body)
    for u in lazy + re.findall(r'<img[^>]+src="(https?://[^"]+)"', body):
        if u not in imgs:
            imgs.append(u)
    imgs.sort(key=lambda u: 0 if _OSS in u else 1)    # OSS原图优先
    return title, date, tag, paras, imgs[:6]


def _download(url, fp):
    data = common.http_bin(url, referer='https://www.52audio.com/', min_bytes=3000)
    if data:
        tmp = fp + '.part'
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, fp)   # v18.8：原子写
        return True
    return False


def run():
    limit = 3
    for a in sys.argv[1:]:
        if a.isdigit():
            limit = max(1, int(a))
    os.makedirs(DST, exist_ok=True)
    existing = art.scan_existing(DST)
    list_html = common.http_get('https://www.52audio.com' + LIST_PATH,
                                referer='https://www.52audio.com/')
    items = []
    seen = set()
    for u, t in re.findall(r'href="(https://www\.52audio\.com/archives/\d+\.html)"[^>]*>([^<]{6,80})<', list_html):
        if u not in seen:
            seen.add(u)
            items.append((u, H.unescape(t).strip()))
    if not items:
        # v18.8：列表解析0条时报失败而非静默"成功 新增0"
        return '失败', '我爱音频网列表页解析0条，选择器疑似变更'
    new, missing, skipped = [], [], 0
    for url, ltitle in items:
        if len(new) >= limit:
            break
        if url in existing:
            continue
        t2, pdate, tag, paras, imgs = _extract_article(
            common.http_get(url, referer='https://www.52audio.com/'))
        if len(paras) < 6:
            skipped += 1
            continue
        name, photos = art.save_article(
            DST, url=url, prod_name=_product(t2 or ltitle), md_title='评测｜' + (t2 or ltitle),
            pdate=pdate or datetime.date.today().isoformat(), tag=tag, paras=paras,
            img_urls=imgs, download=_download,
            source_line='来源：我爱音频网 · 耳机评测栏目 ｜ 原文：' + url,
            note_line='采集说明：collect_P91_我爱音频网评测.py（requests直连）正文段落照录，未改动表述；'
                      'chips/摘要由每日定时任务提炼。')
        new.append(name)
        if not photos:
            missing.append(name)
    # 缺照补拍（v18.8语义收敛至 _article_common）：只覆盖当前列表页内的缺照文章
    fixed, still = art.retry_missing_photos(
        existing, items,
        fetch=lambda u: common.http_get(u, referer='https://www.52audio.com/'),
        extract=_extract_article, download=_download)
    detail = (f'我爱音频网评测 · 新增{len(new)}篇{new if new else ""}，'
              f'库存{len(existing) + len(new)}篇'
              + (f'，跳过短稿{skipped}篇' if skipped else '')
              + (f'，{len(missing)}篇未取到照片{missing}' if missing else '')
              + (f'，补照{len(fixed)}篇{fixed if fixed else ""}' if fixed else '')
              + (f'，补照未果{len(still)}篇' if still else ''))
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
