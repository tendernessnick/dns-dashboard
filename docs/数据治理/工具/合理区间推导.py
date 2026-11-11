# -*- coding: utf-8 -*-
"""合理区间推导工具 v2.1（业务口径修订版）：
v1 的两个生产缺陷（2026-11-11夜间轮区间误杀6词条的根因）——
  ①多列CSV用通配[拒]罩全列：P10/P44/P47/P48 的"同比%/环比%"可为负，被主列正数拒界误杀；
  ②两个人工物理界定错：P12 德债拒界0~20（负收益率历史真实存在，包络-0.65）；P69 拒界0~500
    （单位是百万美元，月值7853全被拒）。
v2 规则（逐列独立）：
  [拒]列级：同比/环比/增速与财报净利只存疑、不拒写；其余①首列有词条级人工界→用之（仅约束首列）
    ②列名语义规则（众筹达成率→0~500000；含%→-1~101；排名→0~60；指数→0~2000；周转→0~200）③同单位广播（生意社双列卡：人工界广播到
    非语义列）④其余→按本列包络推物理界（非负钳0~max×3，可负对称×1.5）；P72 混合构成统计列禁用[拒]
  [疑]列级：本列包络±35%（下限非负钳0）
用法：python 合理区间推导.py  → 重写注册表「合理区间」列 + 重写 07 提案文档（v2.1表）
可重复执行（幂等）。改完无需重启采集（common 每次 _load_ranges 现读）。"""
import csv
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REG = os.path.join(ROOT, '看板数据固化', '词条注册表.csv')
CSV_DIR = os.path.join(ROOT, '看板数据固化', 'CSV数据')
DOC = os.path.join(ROOT, 'docs', '数据治理', '07_数值核验体系_20261110.md')
SKIP = {'数据日期', '单位', '数据来源', '备注', '标题', '链接', '图片URL', 'ASIN', '序号'}

# 词条级人工[拒]界：仅约束第一个数值列（主列）。v2修正：P12允许负、P69口径改百万美元
CURATED_MAIN = {
    'P1': (20, 80), 'P3': (-5, 15), 'P4': (0, 20), 'P5': (-20, 30),
    'P6': (-20, 30), 'P8': (-10, 30), 'P9': (20, 80), 'P10': (0, 500), 'P11': (50, 130),
    'P12': (-5, 20), 'P13': (-100, 50),
    'P21': (4.5, 9.5), 'P22': (80, 130), 'P23': (5, 9.5), 'P24': (5, 11), 'P25': (6, 13),
    'P26': (3000, 25000), 'P27': (20000, 250000), 'P30': (200, 3000), 'P31': (2500, 15000),
    'P32': (4500, 22000), 'P33': (3000, 60000), 'P34': (0, 200), 'P35': (0, 100),
    'P36': (5, 400), 'P37': (0, 15000), 'P38': (-80, 80), 'P39': (80000, 800000),
    'P40': (8000, 60000), 'P52': (1000, 100000),
    'P43': (25, 60), 'P44': (0, 6000), 'P45': (0, 2000), 'P46': (0, 1000),
    'P47': (0, 1000), 'P48': (0, 1000), 'P49': (-1, 101), 'P56': (0, 100000),
    'P58': (0, 5000), 'P66': (0, 10000), 'P67': (0, 1000000), 'P68': (0, 10000),
    'P69': (0, 30000), 'P71': (-150, 150),
    'P79': (-2000, 5000), 'P80': (-1, 101), 'P82': (0, 300),
    'P201': (-2000, 5000), 'P202': (-2000, 5000), 'P203': (-2000, 5000),
    'P204': (-2000, 5000), 'P205': (-2000, 5000),
    'P211': (0, 200), 'P212': (0, 200), 'P213': (0, 200), 'P214': (0, 200),
    'P221': (-1, 101), 'P222': (-1, 101), 'P223': (-1, 101), 'P224': (-1, 101),
}
# 人工界广播词条（生意社现货/期货同单位双列、多型号同单位）：人工界同时约束非语义次列
BROADCAST = {'P31', 'P32', 'P33', 'P34', 'P35', 'P39', 'P40', 'P56', 'P58'}
NO_REJECT = {'P72'}   # 榜单统计混合构成列，禁用[拒]只留[疑]
FINANCIAL_PIDS = {'P201', 'P202', 'P203', 'P204', 'P205'}


def col_reject(pid, col, first_col, env):
    """列级[拒]界：返回(lo, hi)或None(不设拒界)。"""
    if pid in NO_REJECT:
        return None
    # 增速可因小基数、亏损转盈等超过±150%；主列也适用，优先于人工主列界。
    # 财报净利允许首次亏损，历史全为正不能成为拒写负值的物理依据。
    if any(k in col for k in ('同比', '环比', '增速')):
        return None
    if pid in FINANCIAL_PIDS and '净利' in col:
        return None
    if col == first_col and pid in CURATED_MAIN:
        return CURATED_MAIN[pid]
    if '达成率' in col:
        # v20修正（2026-11-11全量批P93/P94拒写实证）：众筹达成率超额是常态（历史max P93≈3.45万%，P94≈39.7万%），
        # 不能落进通用百分比(-1,101)拒界
        return (0, 500000)
    if '%' in col:
        return (-1, 101)
    if '排名' in col:
        return (0, 60)
    if '指数' in col:
        return (0, 2000)
    if '周转' in col:
        return (0, 200)
    if pid in CURATED_MAIN and pid in BROADCAST:
        return CURATED_MAIN[pid]
    lo, hi = env
    r4 = lambda x: float('%.4g' % x)
    if lo >= 0:
        return (0, r4(max(hi * 3, 1)))
    return (r4(lo * 1.5), r4(hi * 1.5))


def col_spec(pid, col, env):
    """单列 → '[拒]col=a~b;'(可选) + '[疑]col=a~b'。env=(min, max)。"""
    lo, hi = env
    span = hi - lo if hi > lo else max(abs(hi) * 0.5, 1)
    margin = max(span * 0.35, abs(hi) * 0.05)
    alo = max(lo - margin, 0) if lo >= 0 else lo - margin
    ahi = hi + margin
    r4 = lambda x: float('%.4g' % x)
    parts = []
    rj = col_reject(pid, col, FIRST_COL.get(pid, col), (lo, hi))
    if rj:
        parts.append('[拒]%s=%s~%s' % (col, r4(rj[0]), r4(rj[1])))
    parts.append('[疑]%s=%s~%s' % (col, r4(alo), r4(ahi)))
    return ';'.join(parts)


FIRST_COL = {}
TABLE = []


def main():
    with open(REG, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    hdr = rows[0]
    i_pid, i_status, i_freq, i_word = (hdr.index(k) for k in ('P号', '状态', '更新频率', '词条'))
    if '合理区间' not in hdr:
        print('注册表无合理区间列（先跑过v1才可跑v2）'); sys.exit(1)
    i_range = hdr.index('合理区间')
    for i in range(1, len(rows)):
        while len(rows[i]) < len(hdr):
            rows[i].append('')

    configured = 0
    for idx in range(1, len(rows)):
        r = rows[idx]
        pid, status = r[i_pid], r[i_status]
        freq, word = r[i_freq], r[i_word]
        spec = ''
        if status in ('在板', '静态维护'):
            num = pid[1:].lstrip('0')
            hits = None
            for pat in (f'*-P{num}-*.csv', f'*-P{num:0>2}-*.csv'):
                hits = glob.glob(os.path.join(CSV_DIR, pat))
                if hits:
                    break
            cols = {}
            npts = 0
            if hits:
                with open(hits[0], encoding='utf-8-sig', newline='') as f:
                    for row in csv.DictReader(f):
                        for c, v in row.items():
                            if c in SKIP or c == '数据日期':
                                continue
                            try:
                                x = float(str(v).replace(',', '').strip())
                            except (TypeError, ValueError):
                                continue
                            npts += 1                      # 数据点数（数值单元格），与核验粒度一致
                            e = cols.setdefault(c, [x, x])
                            e[0] = min(e[0], x)
                            e[1] = max(e[1], x)
            if not cols or npts < 5:
                TABLE.append((pid, word, freq, '-', '-', '无数值CSV/历史点<5'))
            else:
                col_names = [c for c in next(csv.reader(open(hits[0], encoding='utf-8-sig')))
                             if c in cols]
                FIRST_COL.clear()
                FIRST_COL[pid] = col_names[0]
                segs = [col_spec(pid, c, tuple(cols[c])) for c in col_names]
                spec = ';'.join(segs)
                det = ' / '.join('%s[%.4g,%.4g]' % (c, cols[c][0], cols[c][1]) for c in col_names)
                TABLE.append((pid, word, freq, det, spec, f'{len(col_names)}列·{npts}点'))
        else:
            TABLE.append((pid, word, freq, '-', '-', '状态=%s' % status))
        r[i_range] = spec
        if spec:
            configured += 1

    with open(REG, 'w', encoding='utf-8-sig', newline='') as f:
        csv.writer(f).writerows(rows)

    with open(DOC, 'w', encoding='utf-8') as f:
        f.write('# v19 数值核验体系：合理区间提案与设计\n\n')
        f.write('> v1：2026-11-10 初版（通配拒界）。v2：2026-11-11 修正夜间轮区间误杀6词条'
                '（P10/P12/P44/P47/P48/P69）——通配拒界改**逐列显式**（同比/环比等次要列按列名语义规则），'
                'P12 允许负收益率（包络-0.65）、P69 口径修正为百万美元（0~30000）。'
                'v2.1：同比/环比/增速及财报净利改为只存疑，避免高增长、亏损或小基数同比被拒写；'
                '众筹达成率单独设0~500000%拒界。P201~P205按年初累计报告期口径展示。'
                '本文件由 '
                '`docs/数据治理/工具/合理区间推导.py` 生成，可重复执行。\n\n')
        f.write('## 一、机制（三层防线）\n\n')
        f.write('| 层 | 时机 | 行为 | 配置 |\n|---|---|---|---|\n')
        f.write('| 拒写 | save_row/bulk_backfill 落库前 | 超出[拒]列界→抛错放弃写入 | 注册表「合理区间」`[拒]列=`段 |\n')
        f.write('| 存疑 | 同上 | 超[疑]界或较近期中位数突变→照常落库，detail带⚠存疑 | `[疑]列=`段+突变阈值(日25%/周50%/月80%/季120%) |\n')
        f.write('| 对照 | run_all 全量尾部 | cross_check 12对双源互对 → 验证/CSV + 核验状态.json | cross_check.py |\n')
        f.write('| 抽查 | 每周 | 生成_周度抽查.py 核对单人工勾选 | 建议挂定时任务 |\n\n')
        f.write('## 二、v2.1 列级规则\n\n'
                '1. 同比/环比/增速（含主列）及P201~P205净利：仅[疑]包络检查，无固定[拒]界；合法高增长、亏损、小基数同比允许落库\n'
                '2. 其余首列（主列）：词条级人工界（CURATED_MAIN，见工具源码注释）；其余列名语义：众筹达成率→[0,500000]；含%→[-1,101]；排名→[0,60]；指数→[0,2000]；周转→[0,200]\n'
                '3. 同单位广播（生意社双列/多型号，BROADCAST集）：人工界广播到非语义次列\n'
                '4. 其余：本列包络推物理界（非负钳0~max×3；可负对称×1.5）；P72 混合构成禁[拒]\n'
                '5. [疑]：本列包络±35%（下限非负钳0）；历史点<5 不配置\n\n')
        f.write('## 三、全词条区间表（v2.1，%d条配置）\n\n' % configured)
        f.write('| P号 | 词条 | 频率 | 逐列历史包络 | 合理区间 | 说明 |\n|---|---|---|---|---|---|\n')
        for row in TABLE:
            if row[4]:
                f.write('| %s | %s | %s | %s | %s | %s |\n' % row)
        f.write('\n## 四、未配置清单\n\n')
        for row in TABLE:
            if not row[4]:
                f.write('- %s %s（%s）\n' % (row[0], row[1], row[5]))
        f.write('\n## 五、验收核对\n\n'
                '1. 附录「最近数据」列核验徽标正常（✓核验/⚠存疑）\n'
                '2. 六个曾误杀词条（P10/P12/P44/P47/P48/P69）真采成功\n'
                '3. 区间不合适→直接改注册表该行（格式`[拒]列=a~b;[疑]列=a~b`），保存即生效\n')
    print('注册表已重推 %d 条（v2.1逐列）；提案文档已更新' % configured)


if __name__ == '__main__':
    main()
