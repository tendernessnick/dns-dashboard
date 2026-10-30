# -*- coding: utf-8 -*-
"""阶段5回归：迁移前备份(_备份_CSV数据_20261028) vs 当前CSV 逐文件历史行零丢失校验。
判定：备份中每一行（按主键）必须在当前文件中存在，且数值列/备注列的值完全一致；
数据来源列允许按治理映射表标准化（差异计入'标准化数'，不算丢失）。"""
import csv
import glob
import os
import re
import sys

BASE = r'E:\个人资料\工作实习相关\2026-2027深圳和宏\研报数据整理\数据看板构建'
BK = os.path.join(BASE, '看板数据固化', '_备份_CSV数据_20261028')
CU = os.path.join(BASE, '看板数据固化', 'CSV数据')
SKIP_COLS = {'数据日期', '数据来源'}

def pk(r, cols):
    keys = [c for c in cols if c not in SKIP_COLS and not re.match(r'^单位$', c)]
    return tuple(r.get(c, '') for c in (['数据日期'] + [c for c in keys if c != '数据日期']))

def main():
    total_lost, files_ok, files_warn = 0, 0, []
    for fb in sorted(glob.glob(os.path.join(BK, '*.csv'))):
        name = os.path.basename(fb)
        if '存档' in name:            # 归档文件已移入 _归档/，单独存在不校验
            continue
        fc = os.path.join(CU, name)
        if not os.path.exists(fc):
            files_warn.append(f'{name}: 当前目录缺失(可能已迁移更名)')
            continue
        rb = list(csv.DictReader(open(fb, encoding='utf-8-sig', newline='')))
        rc = list(csv.DictReader(open(fc, encoding='utf-8-sig', newline='')))
        cur = {}
        for r in rc:
            cur[pk(r, rc[0].keys() if rc else [])] = r
        lost, norm = [], 0
        for r in rb:
            k = pk(r, rb[0].keys() if rb else [])
            hit = cur.get(k)
            if hit is None:
                # 快照型历史行可能被同日重采覆盖主键集合不变——主键找不到=丢失
                lost.append(k)
                continue
            for c in set(list(r.keys()) + list(hit.keys())):
                if c in SKIP_COLS or c == '单位':
                    continue
                vb, vc = (r.get(c) or '').strip(), (hit.get(c) or '').strip()
                if vb != vc and not (vb == '' and vc == ''):
                    lost.append((k, c, vb[:30], vc[:30]))
            if (r.get('数据来源') or '') != (hit.get('数据来源') or ''):
                norm += 1
        if lost:
            total_lost += len(lost)
            files_warn.append(f'{name}: 异常{len(lost)}处 例:{lost[:2]}')
        else:
            files_ok += 1
        if norm:
            pass
    print(f'校验文件: {files_ok} 个零丢失 | 异常: {total_lost} 处')
    for w in files_warn:
        print(' ⚠', w)
    return 0 if total_lost == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
