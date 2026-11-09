# -*- coding: utf-8 -*-
"""P90 充电头网·拆解图文：拆解分类列表 → 新文章落盘 图文数据/充电头网拆解/<采集日>/<产品名>/
（正文md + 照片N + 基础_meta.json[待提炼=true]），供看板P90图文卡（70_review.js渲染）。
复用 fetch_ctw（curl_cffi过JS验证，与P60同通道）；文章URL为去重主键；子分类自动填品类tag；
chips/摘要由每日21:15定时任务AI提炼（数值照录原文），提炼后删除"待提炼"字段。
用法：python collect_P90_充电头网拆解图文.py [本次最多采集篇数，默认3]"""
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
from _news_common import fetch_ctw, parse_ctw

PID, TITLE = 90, '充电头网·拆解图文'
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # 看板数据固化
DST = os.path.join(BASE, '图文数据', '充电头网拆解')
_PREFIX = re.compile(r'^(拆解报告|视频拆解|拆解|评测|方案)[：:]\s*')
_MAINCAT = {'拆解', '评测', '新闻', '方案', '专题'}


def _cl(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', H.unescape(s or ''))).strip()


def _product(title):
    return _PREFIX.sub('', _cl(title)).strip() or _cl(title)


def _sanitize(name):
    return re.sub(r'[\\/:*?"<>|#]+', '', name).strip()[:50] or '未命名'


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
        r = cr.get(url, impersonate='chrome', timeout=40, headers={'Referer': 'https://www.chongdiantou.com/'})
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
    existing = {}                                # url → (meta路径, meta dict)
    for fp in glob.glob(os.path.join(DST, '*', '*', '_meta.json')):
        try:
            m = json.load(open(fp, encoding='utf-8'))
            u = m.get('原文链接')
            if u:
                existing[u] = (fp, m)
        except Exception:
            pass
    items = parse_ctw(fetch_ctw('/archives/category/teardowns'))
    if not items:
        # v18.8：列表解析0条时报失败而非静默"成功 新增0"（选择器腐坏不可感知是图文卡最大风险）
        return '失败', '充电头网列表页解析0条，选择器疑似变更'
    today = datetime.date.today().strftime('%Y%m%d')
    new, missing, skip_video = [], [], 0
    for dt, title, url in items:
        if len(new) >= limit:
            break
        if url in existing:
            continue
        if title.startswith('视频拆解'):            # 视频稿正文只有嵌入播放器，跳过
            skip_video += 1
            continue
        art = fetch_ctw(url[len('https://www.chongdiantou.com'):])
        t2, pdate, tag, paras, imgs = _extract_article(art)
        if len(paras) < 6:                           # 正文过短（嵌入稿/解析异常）不入库
            skip_video += 1
            continue
        name = _sanitize(_product(t2 or title))
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
        meta = {'产品名': _product(t2 or title), '品类tag': tag,
                '发布日期': pdate or dt.strftime('%Y-%m-%d'), '原文链接': url,
                'chips': [], '摘要': '', '照片': photos, '待提炼': True}
        with open(os.path.join(ddir, '_meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        lines = ['# 拆解｜' + (t2 or title), '',
                 '> 来源：充电头网 · 拆解栏目 ｜ 原文：' + url, '',
                 '> 采集说明：collect_P90_充电头网拆解图文.py（curl_cffi）正文段落照录，未改动表述；'
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
    for dt2, t2b, u2 in items:
        if len(fixed) >= 5 or attempts >= 8:
            break
        hit = existing.get(u2)
        if not hit or hit[1].get('照片'):
            continue
        attempts += 1
        try:
            art = fetch_ctw(u2[len('https://www.chongdiantou.com'):])
            _, _, _, _, imgs2 = _extract_article(art)
        except Exception:  # noqa: BLE001
            still.append(hit[1].get('产品名') or t2b)
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
            fixed.append(hit[1].get('产品名') or t2b)
        else:
            still.append(hit[1].get('产品名') or t2b)
        time.sleep(1)
    detail = (f'充电头网拆解 · 新增{len(new)}篇{new if new else ""}，'
              f'库存{len(existing) + len(new)}篇'
              + (f'，跳过视频/嵌入稿{skip_video}篇' if skip_video else '')
              + (f'，{len(missing)}篇未取到照片{missing}' if missing else '')
              + (f'，补照{len(fixed)}篇{fixed if fixed else ""}' if fixed else '')
              + (f'，补照未果{len(still)}篇' if still else ''))
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
