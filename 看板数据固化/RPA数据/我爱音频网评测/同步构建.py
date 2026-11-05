# -*- coding: utf-8 -*-
"""
同步构建：标准化任务「每日评测」新文章 → RPA数据/我爱音频网评测/（P91看板图文卡数据）
机械部分全自动：复制正文md+照片、从正文文末解析原文链接/发布日期、生成基础_meta.json（待提炼=true）。
chips/摘要的AI提炼由每日定时任务（21:15）或人工完成；提炼后删除"待提炼"字段即可。
用法：python 同步构建.py    （更新看板.bat 第2步自动调用；也可单独运行）
"""
import glob
import json
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
# 采集源（标准化任务侧，采集契约正本所在；仅读取，不回写）
SRC = r'E:\个人资料\工作实习相关\2026-2027深圳和宏\研报数据整理\标准化任务\prompt目录\我爱音频网\每日评测'


def parse_body(fp):
    """从正文md文末信息解析原文链接与发布日期"""
    try:
        text = open(fp, encoding='utf-8').read()
    except Exception:
        return '', ''
    url = ''
    pdate = ''
    m = re.search(r'原文链接[：:]\s*(https?://\S+)', text)
    if m:
        url = m.group(1).rstrip('。')
    m = re.search(r'发布日期[：:]\s*(\d{4}-\d{2}-\d{2})', text)
    if m:
        pdate = m.group(1)
    return url, pdate


def main():
    if not os.path.isdir(SRC):
        print('同步跳过：采集源目录不存在（%s）' % SRC)
        return
    new, pending = [], []
    for day_dir in sorted(glob.glob(os.path.join(SRC, '*'))):
        if not os.path.isdir(day_dir) or not re.fullmatch(r'\d{8}', os.path.basename(day_dir)):
            continue
        for art_dir in sorted(glob.glob(os.path.join(day_dir, '*'))):
            if not os.path.isdir(art_dir):
                continue
            rel = os.path.relpath(art_dir, SRC)
            dst_dir = os.path.join(HERE, rel)
            meta_fp = os.path.join(dst_dir, '_meta.json')
            if not os.path.isdir(dst_dir):
                os.makedirs(dst_dir, exist_ok=True)
                n = 0
                for f in glob.glob(os.path.join(art_dir, '*')):
                    base = os.path.basename(f)
                    if base.endswith('正文.md') or '_照片' in base:
                        shutil.copy2(f, os.path.join(dst_dir, base))
                        n += 1
                body_fp = glob.glob(os.path.join(dst_dir, '*正文.md'))
                url, pdate = parse_body(body_fp[0]) if body_fp else ('', '')
                meta = {'产品名': os.path.basename(art_dir), '品类tag': '',
                        '发布日期': pdate, '原文链接': url, 'chips': [], '摘要': '',
                        '照片': sorted(os.path.basename(p) for p in glob.glob(os.path.join(dst_dir, '*_照片*.png'))),
                        '待提炼': True}
                with open(meta_fp, 'w', encoding='utf-8') as fh:
                    json.dump(meta, fh, ensure_ascii=False, indent=1)
                new.append(rel)
                pending.append(rel)
            elif os.path.exists(meta_fp):
                try:
                    meta = json.load(open(meta_fp, encoding='utf-8'))
                except Exception:
                    meta = {}
                if meta.get('待提炼') or not meta.get('chips') or not meta.get('摘要'):
                    pending.append(rel)
    print('同步完成：新增 %d 篇 %s' % (len(new), new if new else ''))
    if pending:
        print('待提炼（chips/摘要缺失，需AI定时任务或人工补写）：%d 篇 %s' % (len(pending), pending))


if __name__ == '__main__':
    main()
