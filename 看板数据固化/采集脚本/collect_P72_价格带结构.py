# -*- coding: utf-8 -*-
"""P72 产品品类-价格带结构：读入 P66（Amazon线材榜）与 P68（Amazon充电类榜）最新一批TOP30价格，
分箱统计各价格带占比与均价，写宽表。
分箱（左闭右开，末档为闭）：线材 <5 / 5-10 / 10-15 / 15-20 / 20-30 / 30+（美元）；
充电 <5 / 5-10 / 10-20 / 20-40 / 40+（美元）。
样本=当日榜内价格非空的商品；单类目有价样本<3则判失败（不编造）。
旧口径（从线材榜硬算的静态占比）已移存 CSV数据/产品品类-P72-价格带结构-旧口径存档.csv。"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PID = 72
TITLE = '价格带结构'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '产品品类-P72-价格带结构.csv')
P66 = os.path.join(common.CSV_DIR, '行业数据-P66-Amazon线材榜.csv')
P68 = os.path.join(common.CSV_DIR, '产品品类-P68-Amazon充电类榜单TOP10.csv')

BINS = {
    '线材': [('线材_5美元以下%', lambda p: p < 5),
            ('线材_5-10美元%', lambda p: 5 <= p < 10),
            ('线材_10-15美元%', lambda p: 10 <= p < 15),
            ('线材_15-20美元%', lambda p: 15 <= p < 20),
            ('线材_20-30美元%', lambda p: 20 <= p < 30),
            ('线材_30美元以上%', lambda p: p >= 30)],
    '充电': [('充电_5美元以下%', lambda p: p < 5),
            ('充电_5-10美元%', lambda p: 5 <= p < 10),
            ('充电_10-20美元%', lambda p: 10 <= p < 20),
            ('充电_20-40美元%', lambda p: 20 <= p < 40),
            ('充电_40美元以上%', lambda p: p >= 40)],
}
COLS = (['数据日期', '线材均价USD', '线材_5美元以下%', '线材_5-10美元%', '线材_10-15美元%',
         '线材_15-20美元%', '线材_20-30美元%', '线材_30美元以上%', '线材样本数',
         '充电均价USD', '充电_5美元以下%', '充电_5-10美元%', '充电_10-20美元%',
         '充电_20-40美元%', '充电_40美元以上%', '充电样本数', '单位', '数据来源', '备注'])
MIN_SAMPLE = 3


def _latest_batch(path, source_hint):
    """读榜单CSV最新日期的批次，返回(快照日期, [价格float])。"""
    if not os.path.exists(path):
        raise RuntimeError(f'缺少上游榜单 {os.path.basename(path)}（须先跑P66/P68）')
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = [r for r in csv.DictReader(f)]
    if not rows:
        raise RuntimeError(f'{os.path.basename(path)} 无数据行')
    snap = max(str(r.get('数据日期', '')) for r in rows)
    prices = []
    for r in rows:
        if str(r.get('数据日期', '')) != snap:
            continue
        v = str(r.get('价格USD', '')).strip()
        if not v:
            continue
        try:
            p = float(v)
        except ValueError:
            continue
        if 0 < p < 10000:
            prices.append(p)
    if not prices:
        raise RuntimeError(f'{source_hint} 快照{snap}无有效价格')
    return snap, prices


def _stats(prices, cat):
    n = len(prices)
    out = {'均价': round(sum(prices) / n, 2), '样本数': n}
    for name, cond in BINS[cat]:
        out[name] = round(sum(1 for p in prices if cond(p)) / n * 100, 1)
    return out


def run():
    try:
        snap66, prices66 = _latest_batch(P66, 'P66线材榜')
        snap68, prices68 = _latest_batch(P68, 'P68充电榜')
        s66 = _stats(prices66, '线材')
        s68 = _stats(prices68, '充电')
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)
    if s66['样本数'] < MIN_SAMPLE or s68['样本数'] < MIN_SAMPLE:
        msg = f'有价样本不足(线材{s66["样本数"]}/充电{s68["样本数"]}< {MIN_SAMPLE})，不写统计'
        return '失败', msg
    vals = {'线材均价USD': s66['均价'], '线材样本数': s66['样本数'],
            '充电均价USD': s68['均价'], '充电样本数': s68['样本数']}
    for cat, s in (('线材', s66), ('充电', s68)):
        for name, _ in BINS[cat]:
            vals[name] = s[name]
    date_str = common.TODAY
    vals['数据来源'] = ('Amazon Best Sellers（P66线材榜TOP30/P68充电榜TOP30 商品价格，'
                     f'线材快照{snap66}、充电快照{snap68}）')
    vals['备注'] = ('分箱=左闭右开、30+/40+为闭；样本为榜内价格非空商品；'
                    '线材榜单：Cell Phone Cables & Adapters，充电榜单：Chargers & Power Adapters；'
                    '旧口径(单类目静态占比)见 产品品类-P72-价格带结构-旧口径存档.csv')
    common.save_row(CSV, date_str, vals, COLS)
    detail = (f'线材均价${s66["均价"]}(n={s66["样本数"]}) $5-10占{s66["线材_5-10美元%"]}% '
              f'$10-15占{s66["线材_10-15美元%"]}% $15-20占{s66["线材_15-20美元%"]}% '
              f'$20-30占{s66["线材_20-30美元%"]}% $30+占{s66["线材_30美元以上%"]}% | '
              f'充电均价${s68["均价"]}(n={s68["样本数"]}) $5-10占{s68["充电_5-10美元%"]}% '
              f'$10-20占{s68["充电_10-20美元%"]}% $20-40占{s68["充电_20-40美元%"]}% '
              f'$40+占{s68["充电_40美元以上%"]}%')
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))