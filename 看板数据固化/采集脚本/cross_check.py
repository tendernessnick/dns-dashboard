# -*- coding: utf-8 -*-
"""交叉验证-行情双源对照：A源=批次采集器逻辑，B源=独立通道现取，阈值1%。
覆盖：P22 DXY、P23 CNH、P26 LME铜、P36 布伦特。
输出 CSV数据/交叉验证-行情双源对照.csv（表头按任务指定以"验证日期"开头，
与common.save_row的首列断言不兼容，故此处自带upsert），并打印结果表。"""
import csv
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

VERIFY_DIR = os.path.join(os.path.dirname(common.CSV_DIR), '验证')
os.makedirs(VERIFY_DIR, exist_ok=True)
CSV = os.path.join(VERIFY_DIR, '交叉验证-行情双源对照.csv')
COLUMNS = ['验证日期', '指标', '来源A', '值A', '来源B', '值B', '差异', '差异%', '结论']
THRESHOLD_PCT = 1.0


def upsert_rows(rows):
    """按(验证日期,指标)upsert写入对照CSV（utf-8-sig）。"""
    old = []
    if os.path.exists(CSV):
        with open(CSV, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames == COLUMNS:
                old = list(reader)
    for r in rows:
        key = (r['验证日期'], r['指标'])
        old = [o for o in old if (o.get('验证日期'), o.get('指标')) != key]
        old.append(r)
    old.sort(key=lambda o: (o.get('验证日期', ''), o.get('指标', '')))
    with open(CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(old)


def from_em(secid):
    """A/B通道：东财快照f43（fltt=2已缩放）。"""
    d = common.em_get(secid)
    if d.get('f43') in (None, '-'):
        raise RuntimeError(f'东财{secid}无f43')
    return float(d['f43']), f'东财{secid}'


def from_sina(codes, code, idx):
    """A/B通道：新浪实时行情第idx字段。"""
    hq = common.sina_hq(codes)
    f = hq.get(code)
    if not f or len(f) <= idx or f[idx] in ('', '0.0'):
        raise RuntimeError(f'新浪{code}无有效字段: {f}')
    return float(f[idx]), f'新浪{code}'


# 指标 -> (A源取数, B源取数)
CHECKS = [
    ('P22 美元指数DXY', lambda: from_em('100.UDI'),
     lambda: from_sina(['DINIW'], 'DINIW', 1)),
    ('P23 离岸USDCNH', lambda: from_em('133.USDCNH'),
     lambda: from_sina(['fx_susdcnh', 'fx_suusdcnh'], 'fx_susdcnh', 1)),
    ('P26 LME铜', lambda: from_sina(['hf_CAD'], 'hf_CAD', 0),
     lambda: from_em('109.LCPT')),
    ('P36 布伦特原油', lambda: from_sina(['hf_OIL'], 'hf_OIL', 0),
     lambda: from_em('112.B00Y')),
]


def run():
    date = common.TODAY
    rows = []
    for i, (name, fa, fb) in enumerate(CHECKS):
        va = vb = None
        sa = sb = ''
        err = []
        try:
            va, sa = fa()
        except Exception as e:  # noqa: BLE001
            err.append(f'A源失败:{e}')
        time.sleep(1)  # 同站点间隔
        try:
            vb, sb = fb()
        except Exception as e:  # noqa: BLE001
            err.append(f'B源失败:{e}')
        if va is not None and vb is not None:
            diff = round(va - vb, 4)
            pct = round(abs(va - vb) / abs(vb) * 100, 3) if vb else None
            concl = '一致' if (pct is not None and pct < THRESHOLD_PCT) else '偏差>1%'
        else:
            diff = pct = ''
            concl = '取数失败:' + ';'.join(err)  # 不编造，如实记录
        rows.append({'验证日期': date, '指标': name, '来源A': sa,
                     '值A': va if va is not None else '', '来源B': sb,
                     '值B': vb if vb is not None else '',
                     '差异': diff, '差异%': pct, '结论': concl})
        time.sleep(1)

    upsert_rows(rows)

    # 打印结果表
    print(f'交叉验证结果（{date}，阈值{THRESHOLD_PCT}%）')
    print('-' * 100)
    print(f"{'指标':<14}{'来源A':<12}{'值A':>12}{'来源B':<16}{'值B':>12}{'差异':>10}{'差异%':>9}  结论")
    for r in rows:
        print(f"{r['指标']:<14}{r['来源A']:<12}{r['值A']:>12}{r['来源B']:<16}"
              f"{r['值B']:>12}{r['差异']:>10}{r['差异%']:>9}  {r['结论']}")
    ok = sum(1 for r in rows if r['结论'] == '一致')
    print('-' * 100)
    print(f'汇总: {ok}/{len(rows)} 一致; CSV已写入 {CSV}')
    fail = [r for r in rows if r['结论'] != '一致']
    return ('成功' if not fail else '成功(存在偏差/失败)',
            f'{ok}/{len(rows)}一致'
            + (f'; 异常: {[r["指标"] + ":" + r["结论"] for r in fail]}' if fail else ''))


if __name__ == '__main__':
    print(run())
