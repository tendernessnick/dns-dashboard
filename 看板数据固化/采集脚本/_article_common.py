# -*- coding: utf-8 -*-
"""文章图文落盘共用（v18.9收敛，P90充电头网拆解/P91我爱音频网评测）：
存量扫描(URL主键) → 新文章落盘(正文md+照片≤2+_meta.json[待提炼]) → 缺照文章补拍。
站点差异（列表解析/正文提取/图片下载函数/来源说明行）由各采集器以参数传入。"""
import datetime
import glob
import json
import os
import re
import time


def sanitize(name):
    return re.sub(r'[\\/:*?"<>|#]+', '', name).strip()[:50] or '未命名'


def scan_existing(dst):
    """目录下全部存量文章 → {url: (meta路径, meta dict)}。"""
    existing = {}
    for fp in glob.glob(os.path.join(dst, '*', '*', '_meta.json')):
        try:
            with open(fp, encoding='utf-8') as f:
                m = json.load(f)
            u = m.get('原文链接')
            if u:
                existing[u] = (fp, m)
        except Exception:
            pass
    return existing


def save_article(dst, *, url, prod_name, md_title, pdate, tag, paras,
                 img_urls, download, source_line, note_line):
    """新文章落盘：建夹(重名加_后缀)→依次尝试候选图至2张(原子写)→写_meta.json[待提炼]→写正文md。
    返回(文章夹名, 照片列表)。"""
    today = datetime.date.today().strftime('%Y%m%d')
    name = sanitize(prod_name)
    ddir = os.path.join(dst, today, name)
    while os.path.isdir(ddir):
        name += '_'
        ddir = os.path.join(dst, today, name)
    os.makedirs(ddir, exist_ok=True)
    photos = []
    for u in img_urls:
        if len(photos) >= 2:
            break
        n = len(photos) + 1
        ext = '.png' if u.lower().split('?')[0].endswith('.png') else '.jpg'
        if download(u, os.path.join(ddir, f'照片{n}{ext}')):
            photos.append(f'照片{n}{ext}')
    meta = {'产品名': prod_name, '品类tag': tag, '发布日期': pdate, '原文链接': url,
            'chips': [], '摘要': '', '照片': photos, '待提炼': True}
    with open(os.path.join(ddir, '_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    lines = ['# ' + md_title, '', '> ' + source_line, '', '> ' + note_line, '']
    lines += paras
    lines += ['', '---', '', '## 文末信息', '',
              '- 配图：' + ('、'.join(photos) if photos else '未下载到'),
              '- 发布日期：' + pdate,
              '- 原文链接：' + url,
              '- 采集日期：' + datetime.date.today().isoformat()]
    with open(os.path.join(ddir, name + '_正文.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return name, photos


def retry_missing_photos(existing, items, fetch, extract, download,
                         cap=5, max_attempts=8):
    """缺照补拍（v18.7语义，v18.9收敛）：建档时下载失败的文章重读原文页补下载。
    items: [(url, 列表标题)]；fetch(url)→HTML、extract(html)→(…, 图URLs)、download(url,fp)→bool。
    只覆盖当前列表页内的缺照文章；成功≤cap篇/轮、总尝试≤max_attempts。返回(fixed, still)。"""
    fixed, still, attempts = [], [], 0
    for url, ltitle in items:
        if len(fixed) >= cap or attempts >= max_attempts:
            break
        hit = existing.get(url)
        if not hit or hit[1].get('照片'):
            continue
        attempts += 1
        try:
            _, _, _, _, imgs = extract(fetch(url))
        except Exception:  # noqa: BLE001
            still.append(hit[1].get('产品名') or ltitle)
            continue
        ddir = os.path.dirname(hit[0])
        photos = []
        for u in imgs:
            if len(photos) >= 2:
                break
            n = len(photos) + 1
            ext = '.png' if u.lower().split('?')[0].endswith('.png') else '.jpg'
            if download(u, os.path.join(ddir, f'照片{n}{ext}')):
                photos.append(f'照片{n}{ext}')
        if photos:
            hit[1]['照片'] = photos
            with open(hit[0], 'w', encoding='utf-8') as f:
                json.dump(hit[1], f, ensure_ascii=False, indent=1)
            fixed.append(hit[1].get('产品名') or ltitle)
        else:
            still.append(hit[1].get('产品名') or ltitle)
        time.sleep(1)
    return fixed, still
