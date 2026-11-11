# -*- coding: utf-8 -*-
"""周度抽查核对单生成器（v19）：机器出题，人工勾答案——把"被质疑时拿得出证据链"落成5分钟例行动作。
抽样策略：①当前存疑词条全部列入（最该看的）②可靠度C级优先（考证/代理口径，天然最脆）③其余随机补足至9条
输出：看板数据固化/周度抽查核对单_<YYYYMMDD>.md（表格含：看板当前值/数据日期/来源链接/核验状态/人工勾选框）
用法：python 生成_周度抽查.py [数量]（默认9；可挂定时任务每周一次，或手动运行）"""
import csv
import glob
import json
import os
import random
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

FIX = common.BASE
REG = os.path.join(FIX, '词条注册表.csv')
PROV = os.path.join(FIX, '溯源表.csv')
STATE = os.path.join(FIX, '核验状态.json')
ARCHIVE = os.path.join(FIX, '抽查归档')            # 归档目录：保留最近12份，旧的自动清理（v19.2整理约定）
OUT = os.path.join(ARCHIVE, '周度抽查核对单_%s.md' % date.today().strftime('%Y%m%d'))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 9


def last_value(pid_num):
    """数值CSV末值：(日期, 列名, 值, 数据来源)。无CSV返回None。"""
    hits = glob.glob(os.path.join(common.CSV_DIR, f'*-P{pid_num}-*.csv'))
    if not hits:
        return None
    with open(hits[0], encoding='utf-8-sig', newline='') as f:
        rows = [r for r in csv.DictReader(f) if r.get('数据日期')]
    rows.sort(key=lambda r: r['数据日期'])
    if not rows:
        return None
    last = rows[-1]
    for c, v in last.items():
        if c in ('数据日期', '单位', '数据来源', '备注', '标题', '链接', '序号'):
            continue
        try:
            float(str(v).replace(',', ''))
            return last['数据日期'], c, v, last.get('数据来源', '')
        except (TypeError, ValueError):
            continue
    return None


def main():
    reg = {r['P号']: r for r in csv.DictReader(open(REG, encoding='utf-8-sig'))}
    prov = {r['P号']: r for r in csv.DictReader(open(PROV, encoding='utf-8-sig'))}
    try:
        vst = json.load(open(STATE, encoding='utf-8'))
    except Exception:
        vst = {}
    sus = set((vst.get('存疑') or {}).keys())
    vrf = vst.get('对照') or {}

    pool = []
    for pid, r in reg.items():
        if r['状态'] not in ('在板', '静态维护') or not r.get('采集器'):
            continue
        num = pid[1:].lstrip('0')
        lv = last_value(num)
        if not lv:
            continue
        pool.append({'pid': pid, 'word': r['词条'], 'grade': r.get('可靠度', ''),
                     'freq': r.get('更新频率', ''), 'lv': lv,
                     'url': (prov.get(pid, {}) or {}).get('来源URL', ''),
                     'sus': pid in sus,
                     'vrf': vrf.get(pid, {})})
    if not pool:
        print('无可抽查词条'); return
    picks = [p for p in pool if p['sus']]                      # ①存疑必查
    rest = [p for p in pool if p not in picks]
    c_grade = [p for p in rest if p['grade'] == 'C']           # ②C级优先
    random.shuffle(c_grade)
    picks += c_grade[:max(0, N - len(picks))]
    remain = [p for p in rest if p not in picks]
    random.shuffle(remain)
    picks += remain[:max(0, N - len(picks))]
    picks = picks[:N]

    today = date.today()
    week = today.isocalendar()[1]
    os.makedirs(ARCHIVE, exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(f'# 周度抽查核对单 · {today.isoformat()}（第{week}周）\n\n')
        f.write(f'> 用法：逐条打开「来源链接」，核对源站数值是否与「看板当前值」一致，在"人工结论"列填 ✅一致 / ❌不一致（不一致请顺手截屏存档并登记注册表备注）。\n'
                f'> 抽样构成：存疑{len([p for p in picks if p["sus"]])} + C级优先 + 随机补足，共{len(picks)}条，预计5分钟。\n'
                f'> 存疑/对照状态来自 核验状态.json（cross_check对照 + 区间/突变存疑，run_all自动维护）。\n\n')
        f.write('| P号 | 词条 | 看板当前值 | 数据日期 | 来源链接 | 核验状态 | 人工结论 | 备注 |\n')
        f.write('|---|---|---|---|---|---|---|---|\n')
        for p in picks:
            d, col, v, src = p['lv']
            vtag = f'{v}（{col}）'
            st = []
            if p['sus']:
                st.append('⚠存疑')
            vr = p['vrf']
            if vr:
                st.append(('✓' if vr.get('结果') == '通过' else '⚠') + str(vr.get('时间', ''))[5:10])
            if not st:
                st.append('—')
            url = p['url'] or '—'
            f.write(f'| {p["pid"]} | {p["word"]} | {vtag} | {d} | {url} | {"、".join(st)} | ☐一致 ☐不一致 | 来源:{src[:20]} |\n')
        f.write('\n---\n完成后归档：本文件留在 看板数据固化/ 即为证据链一环；发现不一致→核对采集器与源站口径→修正后重采→在注册表备注登记。\n')

        # v20资讯治理B3：资讯召回审计——被关键词过滤的标题过目（资讯侧的cross check）
        try:
            dis = json.load(open(os.path.join(FIX, '资讯数据', '_弃用标题.json'), encoding='utf-8'))
        except Exception:
            dis = {}
        f.write('\n## 资讯召回审计：近7天被关键词过滤的标题过目\n\n')
        f.write('> 逐条扫一眼：有没有"其实该收"的？有→把词补进 看板数据固化/关键词表.csv 对应P号（核心层），下轮采集自动生效。全没有→勾✅无遗漏。\n\n')
        if not dis:
            f.write('（本周无留痕数据：各资讯采集器尚未产生弃用标题）\n')
        any_row = False
        for pid, bucket in sorted(dis.items()):
            rows_ = sorted(bucket.values(), key=lambda v: v.get('d', ''), reverse=True)
            if not rows_:
                continue
            any_row = True
            f.write(f'**{pid}**（{len(rows_)}条）\n\n')
            for v in rows_[:8]:
                f.write(f'- [{v.get("d", "")}] {v.get("t", "")[:64]}\n')
            if len(rows_) > 8:
                f.write(f'- …另有{len(rows_) - 8}条见 资讯数据/_弃用标题.json\n')
            f.write('\n')
        if not any_row:
            f.write('（本周各feed留痕均为空）\n')
        f.write('召回审计结论：☐无遗漏 ☐已补词（P号/词:______）\n')
    olds = sorted(glob.glob(os.path.join(ARCHIVE, '周度抽查核对单_*.md')))
    for fp in olds[:-12]:
        try:
            os.remove(fp)
        except OSError:
            pass
    print('周度抽查核对单已生成:', os.path.basename(OUT), f'（{len(picks)}条：存疑{len([p for p in picks if p["sus"]])}）')
    for p in picks:
        tag = '⚠存疑' if p['sus'] else (p['grade'] + '级' if p['grade'] == 'C' else '随机')
        print(f'  {p["pid"]} {p["word"][:16]} [{tag}]')


if __name__ == '__main__':
    main()
