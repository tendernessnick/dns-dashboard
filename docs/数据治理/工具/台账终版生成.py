# -*- coding: utf-8 -*-
"""数据来源台账·终版生成（v19.2 项目整理批次3.1）：
从唯一事实源（词条注册表.csv + 溯源表.csv）生成台账 xlsx 终版快照，替代人工维护的
`数据来源/数据看板-数据来源.xlsx`（此后定格归档于 docs/档案/，不再人工同步）。
三sheet：①数据来源台账（合并关键列视图）②词条注册表（全列）③溯源表（全列）。
用法：python 台账终版生成.py [输出路径]；幂等可重跑。"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FIX = os.path.join(ROOT, '看板数据固化')
REG = os.path.join(FIX, '词条注册表.csv')
PROV = os.path.join(FIX, '溯源表.csv')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, 'docs', '档案', '数据来源台账_终版快照_20261111.xlsx')

import openpyxl
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


def read(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def sheet(wb, title, hdr, rows, widths=None):
    ws = wb.create_sheet(title)
    ws.append(hdr)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append(r)
    ws.freeze_panes = 'A2'
    for i, w in enumerate(widths or [], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    return ws


def main():
    reg_hdr, reg_rows = read(REG)
    prov_hdr, prov_rows = read(PROV)
    reg = {r[reg_hdr.index('P号')]: dict(zip(reg_hdr, r)) for r in reg_rows}

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ① 合并视图
    merge_hdr = ['P号', '词条', '板块', '分组', '状态', '更新频率', '可靠度', '口径说明',
                 '单位', '显示窗口', '合理区间', '采集通道', '采集器', '回填策略',
                 '资讯key', '资讯文件', '图文/榜单/日历配置', '来源机构', '来源URL',
                 '采集方式', '实测样例', '溯源备注', '注册表备注']
    merge_rows = []
    for r in reg_rows:
        d = dict(zip(reg_hdr, r))
        p = dict(zip(prov_hdr, next((x for x in prov_rows if x[prov_hdr.index('P号')] == d['P号']), [''] * len(prov_hdr))))
        extra = '；'.join(f'{k}={v}' for k, v in (('榜单标签', d.get('榜单标签', '')),
                                                  ('图文目录', d.get('图文目录', '')),
                                                  ('日历键', d.get('日历键', ''))) if v)
        merge_rows.append([
            d['P号'], d['词条'], d['板块'], p.get('分组', ''), d['状态'], d['更新频率'],
            d['可靠度'], d['口径说明'], d['单位'], d['显示窗口'], d.get('合理区间', ''),
            d['采集通道'], d['采集器'], d['回填策略'], d.get('资讯key', ''), d.get('资讯文件', ''),
            extra, p.get('来源', ''), p.get('来源URL', ''), p.get('采集方式', ''),
            p.get('实测样例', ''), p.get('备注', ''), d.get('备注', '')])
    sheet(wb, '数据来源台账（终版）', merge_hdr, merge_rows,
          [7, 26, 12, 12, 9, 9, 7, 24, 9, 9, 34, 22, 26, 9, 12, 16, 30, 30, 40, 24, 40, 36, 30])

    # ②③ 全列原样
    sheet(wb, '词条注册表（全列）', reg_hdr, reg_rows, [8] + [22] * (len(reg_hdr) - 1))
    sheet(wb, '溯源表（全列）', prov_hdr, prov_rows, [8, 14, 14, 18, 30, 40, 30, 8, 9, 36, 36, 20])

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    print('台账终版已生成:', os.path.relpath(OUT, ROOT), '| 合并行:', len(merge_rows),
          '| 注册表:', len(reg_rows), '| 溯源:', len(prov_rows))


if __name__ == '__main__':
    main()
