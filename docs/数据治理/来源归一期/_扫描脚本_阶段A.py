# -*- coding: utf-8 -*-
"""阶段A只读扫描：采集器实际取数域名 + 采集日志成功率统计。
输出供 00_模块相似性分组表.csv / 01_阶段A报告.md 使用。不写任何项目数据文件。"""
import csv
import glob
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

BASE = r'E:\个人资料\工作实习相关\2026-2027深圳和宏\研报数据整理\数据看板构建\看板数据固化'
SCRIPTS = os.path.join(BASE, '采集脚本')

# ---------- 1) 注册表 ----------
reg = list(csv.DictReader(open(os.path.join(BASE, '词条注册表.csv'), encoding='utf-8-sig')))
print(f'== 注册表 {len(reg)} 行 ==')

# ---------- 2) 采集器域名扫描 ----------
domain_re = re.compile(r'https?://([A-Za-z0-9.\-]+)')
file_domains = {}
for path in sorted(glob.glob(os.path.join(SCRIPTS, '*.py'))):
    name = os.path.basename(path)
    txt = open(path, encoding='utf-8', errors='ignore').read()
    doms = Counter(m.group(1).lower() for m in domain_re.finditer(txt))
    # 过滤纯注释里偶尔出现的 W3C/规范 域名
    file_domains[name] = [d for d, _ in doms.most_common(6)]

pid2files = defaultdict(set)
for r in reg:
    for f in re.split(r'[;；]', r['采集器'] or ''):
        f = f.strip()
        if f:
            pid2files[r['P号']].add(f)

print('\n== PID -> 实际域名（按采集器文件扫描） ==')
for pid in sorted(pid2files, key=lambda x: int(re.sub(r'\D', '', x) or 0)):
    doms = []
    for f in sorted(pid2files[pid]):
        doms += file_domains.get(f, ['<文件不存在>'])
    r = next(x for x in reg if x['P号'] == pid)
    print(f"{pid}\t{r['词条'][:18]}\t通道={r['采集通道'][:14]}\t域名={' '.join(sorted(set(doms)) or ['-'])}")

# ---------- 3) 采集日志统计 ----------
log_path = os.path.join(BASE, '采集日志.csv')
rows = list(csv.DictReader(open(log_path, encoding='utf-8-sig')))
print(f"\n== 采集日志 {len(rows)} 行，列={list(rows[0].keys()) if rows else '-'} ==")
tcol = next((c for c in rows[0] if '时间' in c or '日期' in c), None)
pcol = next((c for c in rows[0] if c.strip() in ('P号', 'PID')), None)
rcol = next((c for c in rows[0] if '结果' in c), None)
scol = next((c for c in rows[0] if '耗时' in c), None)
cut = datetime.now() - timedelta(days=90)
stat = defaultdict(lambda: [0, 0, 0.0, ''])
for r in rows:
    pid = (r.get(pcol) or '').strip()
    if not pid:
        continue
    st = stat[pid]
    st[0] += 1
    if (r.get(rcol) or '') == '成功':
        st[1] += 1
    try:
        st[2] += float(r.get(scol) or 0)
    except ValueError:
        pass
    t = (r.get(tcol) or '')[:19]
    if t > st[3]:
        st[3] = t
print('\n== PID -> 近90天成功率 / 全部次数 / 平均耗时 / 最近运行 ==')
for pid in sorted(stat, key=lambda x: int(re.sub(r'\D', '', x) or 0)):
    tot, ok, secs, last = stat[pid]
    recent = [r for r in rows
              if (r.get(pcol) or '').strip() == pid and (r.get(tcol) or '')[:10] >= cut.strftime('%Y-%m-%d')]
    rok = sum(1 for r in recent if (r.get(rcol) or '') == '成功')
    avg = secs / tot if tot else 0
    print(f"{pid}\t近90天 {rok}/{len(recent)}\t累计{tot}次成功率{ok / tot * 100:.0f}%\t均耗{avg:.1f}s\t最近{last}")
