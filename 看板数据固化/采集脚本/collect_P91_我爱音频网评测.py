# -*- coding: utf-8 -*-
"""P91 我爱音频网·耳机评测图文：评测分类列表 → 新文章落盘 图文数据/我爱音频网评测/<采集日>/<产品名>/
（正文md + 照片N原图 + 基础_meta.json[待提炼=true]），供看板P91图文卡（70_review.js渲染）。
通道：requests 直连（52audio 无反爬，2026-11-05 验证，可行性验证结论归档于目录 索引.md）；
文章URL为去重主键；图片优先 OSS 原图（52audio-images.oss-cn-shenzhen.aliyuncs.com）。
chips/摘要由每日21:15定时任务AI提炼，提炼后删除"待提炼"字段。
用法：python collect_P91_我爱音频网评测.py [本次最多采集篇数，默认3]"""
import datetime
import glob
import html as H
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PID, TITLE = 91, '我爱音频网·耳机评测图文'
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # 看板数据固化
DST = os.path.join(BASE, '图文数据', '我爱音频网评测')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
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


def _sanitize(name):
    return re.sub(r'[\\/:*?"<>|#]+', '', name).strip()[:50] or '未命名'


def _get(url):
    import requests
    r = requests.get(url, headers={'User-Agent': UA, 'Referer': 'https://www.52audio.com/'}, timeout=25)
    r.raise_for_status()
    return r.text


def _extract_article(html):
    """→ (标题, 发布日期, 子分类tag, 段落列表, 内容图URL列表[OSS优先])"""
    t = re.search(r'<title>([^<]+)</title>', html)
    title = _cl(t.group(1).split(' - ')[0]) if t else ''
    dm = (re.search(r'(20\d\d-\d\d-\d\d)', html) or re.search(r'(20\d\d年\d+月\d+日)', html))
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
    import requests
    try:
        r = requests.get(url, headers={'User-Agent': UA, 'Referer': 'https://www.52audio.com/'}, timeout=40)
        if r.status_code == 200 and len(r.content) > 3000:
            with open(fp, 'wb') as f:
                f.write(r.content)
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
    existing = {}                                # url → (meta路径, meta dict)
    for fp in glob.glob(os.path.join(DST, '*', '*', '_meta.json')):
        try:
            m = json.load(open(fp, encoding='utf-8'))
            u = m.get('原文链接')
            if u:
                existing[u] = (fp, m)
        except Exception:
            pass
    list_html = _get('https://www.52audio.com' + LIST_PATH)
    items = []
    seen = set()
    for u, t in re.findall(r'href="(https://www\.52audio\.com/archives/\d+\.html)"[^>]*>([^<]{6,80})<', list_html):
        if u not in seen:
            seen.add(u)
            items.append((u, H.unescape(t).strip()))
    today = datetime.date.today().strftime('%Y%m%d')
    new, missing, skipped = [], [], 0
    for url, ltitle in items:
        if len(new) >= limit:
            break
        if url in existing:
            continue
        art = _get(url)
        t2, pdate, tag, paras, imgs = _extract_article(art)
        if len(paras) < 6:
            skipped += 1
            continue
        name = _sanitize(_product(t2 or ltitle))
        ddir = os.path.join(DST, today, name)
        while os.path.isdir(ddir):
            name += '_'
            ddir = os.path.join(DST, today, name)
        os.makedirs(ddir, exist_ok=True)
        photos = []
        for u in imgs:                               # 依次尝试候选图，直到成功2张
            if len(photos) >= 2:
                break
            n = len(photos) + 1
            ext = '.png' if u.lower().split('?')[0].endswith('.png') else '.jpg'
            if _download(u, os.path.join(ddir, f'照片{n}{ext}')):
                photos.append(f'照片{n}{ext}')
        meta = {'产品名': _product(t2 or ltitle), '品类tag': tag,
                '发布日期': pdate or datetime.date.today().isoformat(), '原文链接': url,
                'chips': [], '摘要': '', '照片': photos, '待提炼': True}
        with open(os.path.join(ddir, '_meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        lines = ['# 评测｜' + (t2 or ltitle), '',
                 '> 来源：我爱音频网 · 耳机评测栏目 ｜ 原文：' + url, '',
                 '> 采集说明：collect_P91_我爱音频网评测.py（requests直连）正文段落照录，未改动表述；'
                 'chips/摘要由每日定时任务提炼。', '']
        lines += paras
        lines += ['', '---', '', '## 文末信息', '',
                  '- 配图：' + ('、'.join(photos) if photos else '未下载到'),
                  '- 发布日期：' + meta['发布日期'],
                  '- 原文链接：' + url,
                  '- 采集日期：' + datetime.date.today().isoformat()]
        with open(os.path.join(ddir, name + '_正文.md'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        new.append(name)
        if not photos:
            missing.append(name)
    # 缺照补拍（v18.7 P0止血）：建档时下载失败的文章重读原文页补下载，成功≤5篇/轮、
    # 总尝试≤8次；只覆盖当前列表页内的缺照文章（翻页滚出的旧文靠后续列表轮换遇到再补）
    fixed, still, attempts = [], [], 0
    for u2, ltitle2 in items:
        if len(fixed) >= 5 or attempts >= 8:
            break
        hit = existing.get(u2)
        if not hit or hit[1].get('照片'):
            continue
        attempts += 1
        try:
            art = _get(u2)
            _, _, _, _, imgs2 = _extract_article(art)
        except Exception:  # noqa: BLE001
            still.append(hit[1].get('产品名') or ltitle2)
            continue
        ddir = os.path.dirname(hit[0])
        photos2 = []
        for iu in imgs2:
            if len(photos2) >= 2:
                break
            n = len(photos2) + 1
            ext = '.png' if iu.lower().split('?')[0].endswith('.png') else '.jpg'
            if _download(iu, os.path.join(ddir, f'照片{n}{ext}')):
                photos2.append(f'照片{n}{ext}')
        if photos2:
            hit[1]['照片'] = photos2
            with open(hit[0], 'w', encoding='utf-8') as f:
                json.dump(hit[1], f, ensure_ascii=False, indent=1)
            fixed.append(hit[1].get('产品名') or ltitle2)
        else:
            still.append(hit[1].get('产品名') or ltitle2)
        time.sleep(1)
    detail = (f'我爱音频网评测 · 新增{len(new)}篇{new if new else ""}，'
              f'库存{len(existing) + len(new)}篇'
              + (f'，跳过短稿{skipped}篇' if skipped else '')
              + (f'，{len(missing)}篇未取到照片{missing}' if missing else '')
              + (f'，补照{len(fixed)}篇{fixed if fixed else ""}' if fixed else '')
              + (f'，补照未果{len(still)}篇' if still else ''))
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
