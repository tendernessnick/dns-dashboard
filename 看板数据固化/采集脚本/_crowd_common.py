# -*- coding: utf-8 -*-
"""众筹项目图文落盘共用（P93 Kickstarter / P94 摩点，v18.3）：
以项目URL为去重主键维护 图文数据/<目录>/<首见YYYYMMDD>/<项目名>/ 项目夹——
新项目→下载照片+写完整_meta.json（chips机械照录接口数值，无需AI提炼）；
存量项目→仅刷新 _meta.json 的 chips/发布日期(=快照日)/排序值，照片与摘要不动。
_meta.json 契约与图文卡一致，另加 排序值 字段（已筹金额，同日刷新后决定卡内次序）。"""
import datetime
import glob
import json
import os
import re


def sanitize(name):
    return re.sub(r'[\\/:*?"<>|#]+', '', str(name)).strip()[:60] or '未命名'


def existing_urls(dst):
    """目录下全部存量项目URL → {(url): (meta路径, meta dict)}"""
    out = {}
    for fp in glob.glob(os.path.join(dst, '*', '*', '_meta.json')):
        try:
            m = json.load(open(fp, encoding='utf-8'))
            u = m.get('原文链接')
            if u:
                out[u] = (fp, m)
        except Exception:
            pass
    return out


def upsert_project(dst, url, name, tag, chips, sortval, summary='',
                   img_urls=(), download=None, fetch_date=''):
    """按URL upsert 一个项目夹。返回 状态('新'/'刷新'/'照片缺失'), 项目名。
    img_urls: 候选图片URL（依次尝试至成功1张，照片1N.ext）；download(url,本地路径)→bool"""
    name = sanitize(name)
    today = datetime.date.today().isoformat()
    ex = existing_urls(dst)
    if url in ex:
        fp, m = ex[url]
        m['chips'] = [str(c) for c in chips]
        m['发布日期'] = today          # 快照日：图文卡日期列与排序均按数据新鲜度
        if tag:
            m['品类tag'] = tag
        if sortval is not None:
            m['排序值'] = sortval
        if summary and not m.get('摘要'):
            m['摘要'] = summary
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump(m, f, ensure_ascii=False, indent=1)
        return '刷新', m.get('产品名') or name
    ddir = os.path.join(dst, (fetch_date or datetime.date.today().strftime('%Y%m%d')), name)
    while os.path.isdir(ddir):
        name += '_'
        ddir = os.path.join(dst, (fetch_date or datetime.date.today().strftime('%Y%m%d')), name)
    os.makedirs(ddir, exist_ok=True)
    photos = []
    if download:
        for u in img_urls:
            ext = '.png' if u.lower().split('?')[0].endswith('.png') else '.jpg'
            if download(u, os.path.join(ddir, f'照片1{ext}')):
                photos = [f'照片1{ext}']
                break
    meta = {'产品名': name, '品类tag': tag, '发布日期': today, '原文链接': url,
            'chips': [str(c) for c in chips], '摘要': summary, '照片': photos,
            '排序值': sortval}
    with open(os.path.join(ddir, '_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return ('新' if photos else '照片缺失'), name
