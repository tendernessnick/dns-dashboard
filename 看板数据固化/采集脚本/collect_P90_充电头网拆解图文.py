# -*- coding: utf-8 -*-
"""P90 充电头网·拆解图文：拆解分类列表 → 新文章落盘 图文数据/充电头网拆解/<采集日>/<产品名>/
（正文md + 照片N + 基础_meta.json[待提炼=true]），供看板P90图文卡（70_review.js渲染）。
复用 fetch_ctw（curl_cffi过JS验证，与P60同通道）；文章URL为去重主键；子分类自动填品类tag；
chips/摘要由每日21:15定时任务AI提炼（数值照录原文），提炼后删除"待提炼"字段。
v18.9：存量扫描/落盘/缺照补拍收敛至 _article_common，本文件仅保留站点解析与下载钩子。
用法：python collect_P90_充电头网拆解图文.py [本次最多采集篇数，默认3]"""
import datetime
import html as H
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import _article_common as art
from _news_common import fetch_ctw, parse_ctw

PID, TITLE = 90, '充电头网·拆解图文'
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # 看板数据固化
DST = os.path.join(BASE, '图文数据', '充电头网拆解')
CTW_HOME = 'https://www.chongdiantou.com'
_PREFIX = re.compile(r'^(拆解报告|视频拆解|拆解|评测|方案)[：:]\s*')
_MAINCAT = {'拆解', '评测', '新闻', '方案', '专题'}


def _cl(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', H.unescape(s or ''))).strip()


def _product(title):
    return _PREFIX.sub('', _cl(title)).strip() or _cl(title)


def _extract_article(html):
    """→ (标题, 发布日期, 子分类tag, 段落列表, 内容图URL列表)"""
    t = re.search(r'class="post-title[^"]*">([^<]+)</h1>', html)
    title = H.unescape(t.group(1)).strip() if t else ''
    dm = (re.search(r'text-xs text-muted"><div>(20\d\d-\d\d-\d\d)</div>', html)
          or re.search(r'(20\d\d-\d\d-\d\d)', html[:2500]))   # v18.8：兜底限定页头区，正文首个日期不再冒充发布日
    date = dm.group(1) if dm else ''
    tag = ''                                            # 分类只认 post-meta 块（全页扫会撞侧栏"城市"链接）
    mm = re.search(r'text-xs text-muted">(.*?)</div></div>', html, re.S)
    if mm:
        for c in re.findall(r'category/[a-z_0-9]+"[^>]*>([^<]{1,12})</a>', mm.group(1)):
            c = c.strip()
            if c and c not in _MAINCAT:
                tag = c
                break
    seg = re.search(r'class="content-wrapper[^"]*"(.*)', html, re.S)
    body = seg.group(1) if seg else html
    paras = [_cl(p) for p in re.findall(r'<p[^>]*>(.*?)</p>', body, re.S)]
    paras = [p for p in paras if len(p) > 4]
    for i, p in enumerate(paras):                     # 截掉文末版权/推广噪声
        if i > len(paras) * 0.5 and re.search(r'转载|版权声明|免责声明|广告', p):
            paras = paras[:i]
            break
    imgs = []                                          # 只留发布日期前后1个月内的图床图（更早的是站方头像等固定素材）
    floor = (datetime.date.today() - datetime.timedelta(days=400)).strftime('%Y/%m')
    for u in re.findall(r'<img[^>]+src="(https?://[^"]+/(?:uploads|images)/[^\"]+)"', body):
        mu = re.search(r'/uploads/(\d{4}/\d{2})/', u)
        if mu and mu.group(1) < floor:
            continue
        if u not in imgs:
            imgs.append(u)
    return title, date, tag, paras, imgs[:6]


def _download(url, fp):
    from curl_cffi import requests as cr
    try:
        r = cr.get(url, impersonate='chrome', timeout=40, headers={'Referer': CTW_HOME + '/'})
        if r.status_code == 200 and len(r.content) > 3000:
            tmp = fp + '.part'
            with open(tmp, 'wb') as f:
                f.write(r.content)
            os.replace(tmp, fp)   # v18.8：原子写——进程被超时kill不再留半张损坏图
            return True
    except Exception:
        pass
    return False


def run():
    limit = 3
    for a in sys.argv[1:]:
        if a.isdigit():
            limit = max(1, int(a))
    os.makedirs(DST, exist_ok=True)
    existing = art.scan_existing(DST)
    items = parse_ctw(fetch_ctw('/archives/category/teardowns'))
    if not items:
        # v18.8：列表解析0条时报失败而非静默"成功 新增0"（选择器腐坏不可感知是图文卡最大风险）
        return '失败', '充电头网列表页解析0条，选择器疑似变更'
    new, missing, skip_video = [], [], 0
    for dt, title, url in items:
        if len(new) >= limit:
            break
        if url in existing:
            continue
        if title.startswith('视频拆解'):            # 视频稿正文只有嵌入播放器，跳过
            skip_video += 1
            continue
        t2, pdate, tag, paras, imgs = _extract_article(fetch_ctw(url[len(CTW_HOME):]))
        if len(paras) < 6:                           # 正文过短（嵌入稿/解析异常）不入库
            skip_video += 1
            continue
        name, photos = art.save_article(
            DST, url=url, prod_name=_product(t2 or title), md_title='拆解｜' + (t2 or title),
            pdate=pdate or dt.strftime('%Y-%m-%d'), tag=tag, paras=paras,
            img_urls=imgs, download=_download,
            source_line='来源：充电头网 · 拆解栏目 ｜ 原文：' + url,
            note_line='采集说明：collect_P90_充电头网拆解图文.py（curl_cffi）正文段落照录，未改动表述；'
                      'chips/摘要由每日定时任务提炼。')
        new.append(name)
        if not photos:
            missing.append(name)
    # 缺照补拍（v18.8语义收敛至 _article_common）：只覆盖当前列表页内的缺照文章
    fixed, still = art.retry_missing_photos(
        existing, [(u, t) for _, t, u in items],
        fetch=lambda u: fetch_ctw(u[len(CTW_HOME):]),
        extract=_extract_article, download=_download)
    detail = (f'充电头网拆解 · 新增{len(new)}篇{new if new else ""}，'
              f'库存{len(existing) + len(new)}篇'
              + (f'，跳过视频/嵌入稿{skip_video}篇' if skip_video else '')
              + (f'，{len(missing)}篇未取到照片{missing}' if missing else '')
              + (f'，补照{len(fixed)}篇{fixed if fixed else ""}' if fixed else '')
              + (f'，补照未果{len(still)}篇' if still else ''))
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
