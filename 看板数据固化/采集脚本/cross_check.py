# -*- coding: utf-8 -*-
"""交叉验证-双源对照（v19扩容）：A源=主通道口径现取，B源=独立通道现取，逐对阈值分级。
覆盖12对：P22/P23/P26/P27/P30/P31/P32/P36/P39/P40/P52（行情双通道互对）+ P4（台账 vs FRED官方API，
宏观类对照试点）。P21/P24/P25暂不配对：中间价官方唯一源、东财外汇secid失效且新浪即期无第二免费源。
输出：
  1) 验证/交叉验证-行情双源对照.csv（按(验证日期,指标)upsert，v18.7起表头保护+原子落盘）
  2) 核验状态.json（看板数据固化/，供看板附录「最近核验」徽标；存疑段由 run_all.write_state 维护）
用法：python cross_check.py ｜ run_all 全量批次尾部自动调用 run_checks()。"""
import csv
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common

VERIFY_DIR = os.path.join(os.path.dirname(common.CSV_DIR), '验证')
os.makedirs(VERIFY_DIR, exist_ok=True)
CSV = os.path.join(VERIFY_DIR, '交叉验证-行情双源对照.csv')
STATE = os.path.join(common.BASE, '核验状态.json')
COLUMNS = ['验证日期', '指标', '来源A', '值A', '来源B', '值B', '差异', '差异%', '结论']


def upsert_rows(rows):
    """按(验证日期,指标)upsert写入对照CSV（utf-8-sig）。
    v18.7：表头不符/无表头时拒绝写入（旧行为静默清库重写），改原子落盘。"""
    old = []
    if os.path.exists(CSV):
        with open(CSV, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or reader.fieldnames != COLUMNS:
                raise RuntimeError(f'[cross_check]{os.path.basename(CSV)} 表头不符或文件损坏，'
                                   f'拒绝覆盖(防历史丢失): {reader.fieldnames}')
            old = list(reader)
    for r in rows:
        key = (r['验证日期'], r['指标'])
        old = [o for o in old if (o.get('验证日期'), o.get('指标')) != key]
        old.append(r)
    old.sort(key=lambda o: (o.get('验证日期', ''), o.get('指标', '')))
    common.write_csv_atomic(CSV, COLUMNS, old)


def from_em(secid):
    """东财快照f43（fltt=2已缩放）。"""
    d = common.em_get(secid)
    if d.get('f43') in (None, '-'):
        raise RuntimeError(f'东财{secid}无f43')
    return float(d['f43']), f'东财{secid}'


def from_sina(codes, code, idx):
    """新浪实时行情第idx字段。hf_外盘=0、fx/DINIW=1、nf_国内期货=8。"""
    hq = common.sina_hq(codes)
    f = hq.get(code)
    if not f or len(f) <= idx or f[idx] in ('', '0.0'):
        raise RuntimeError(f'新浪{code}无有效字段: {f}')
    return float(f[idx]), f'新浪{code}'


def _sina_national(sym):
    """国内期货实时（nf_代码，最新价在第8字段）。"""
    return from_sina(['nf_' + sym], 'nf_' + sym, 8)


def from_ledger_last(pid_num):
    """台账末值+日期（宏观对照试点用：与官方源比的不是'现价'而是'已固化的那一天的值'）。"""
    import glob as _g
    import re as _re
    hits = _g.glob(os.path.join(common.CSV_DIR, f'*-P{pid_num}-*.csv'))
    if not hits:
        raise RuntimeError(f'P{pid_num}台账不存在')
    with open(hits[0], encoding='utf-8-sig', newline='') as f:
        rows = [r for r in csv.DictReader(f)]
    rows = [r for r in rows if r.get('数据日期')]
    rows.sort(key=lambda r: r['数据日期'])
    last = rows[-1]
    for c in ('数值', '同比%', '收盘'):
        v = (last.get(c) or '').strip()
        if v:
            try:
                return float(v.replace(',', '')), last['数据日期'], os.path.basename(hits[0])
            except ValueError:
                pass
    raise RuntimeError(f'P{pid_num}台账末行无可用数值列')


def from_fred_at(series_id, date, back_days=6):
    """FRED官方API：取 date 当日（或其前 back_days 内最近交易日）观测值。需 _keys.FRED_API_KEY。"""
    try:
        sys.path.insert(0, HERE)
        from _keys import FRED_API_KEY
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f'_keys.FRED_API_KEY不可用: {e}')
    url = (f'https://api.stlouisfed.org/fred/series/observations?series_id={series_id}'
           f'&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=60')
    import datetime as _dt
    obs = json.loads(common.http_get(url)).get('observations', [])
    d0 = _dt.date.fromisoformat(date)
    for _ in range(back_days):
        for o in obs:
            if o.get('date') == d0.isoformat() and o.get('value') not in ('.', ''):
                return float(o['value']), f'FRED {series_id}@{o["date"]}'
        d0 -= _dt.timedelta(days=1)
    raise RuntimeError(f'FRED {series_id} 无 {date} 前{back_days}日观测')


# 每对：(pid, 名称, 阈值%, A源取数, B源取数)。A=主通道口径、B=独立通道；名称首段须为P号（核验状态映射用）。
# P4 为特殊对（A/B一次取齐，fb=None 占位，见 run_checks）：台账末值 vs FRED官方API同日观测。
CHECKS = [
    ('P22', 'P22 美元指数DXY', 0.5, lambda: from_em('100.UDI'),
     lambda: from_sina(['DINIW'], 'DINIW', 1)),
    ('P23', 'P23 离岸USDCNH', 0.5, lambda: from_em('133.USDCNH'),
     lambda: from_sina(['fx_susdcnh'], 'fx_susdcnh', 1)),
    ('P26', 'P26 LME铜', 1.0, lambda: from_sina(['hf_CAD'], 'hf_CAD', 0),
     lambda: from_em('109.LCPT')),
    ('P27', 'P27 沪铜主连', 1.0, lambda: from_em('113.cuM'), lambda: _sina_national('CU0')),
    ('P30', 'P30 沪金主连', 1.0, lambda: from_em('113.aum'), lambda: _sina_national('AU0')),
    ('P31', 'P31 PVC期货主连', 1.5, lambda: from_em('114.VM'), lambda: _sina_national('V0')),
    ('P32', 'P32 PP期货主连', 1.5, lambda: from_em('114.ppM'), lambda: _sina_national('PP0')),
    ('P36', 'P36 布伦特原油', 1.0, lambda: from_sina(['hf_OIL'], 'hf_OIL', 0),
     lambda: from_em('112.B00Y')),
    ('P39', 'P39 锡期货主连', 1.5, lambda: from_em('113.snM'), lambda: _sina_national('SN0')),
    ('P40', 'P40 铝期货主连', 1.5, lambda: from_em('113.alM'), lambda: _sina_national('AL0')),
    ('P52', 'P52 沪银主连', 1.0, lambda: from_em('113.agm'), lambda: _sina_national('AG0')),
]
SPECIAL_CHECKS = [('P4', 'P4 10年期美债(台账vsFRED)', 3.0, None)]


def _pair_p4():
    """P4 特殊：A=台账末值/日期，B=FRED同日官方值（日期对齐由 from_fred_at 回溯最近交易日）。"""
    v, date, fname = from_ledger_last('04')
    vf, src = from_fred_at('DGS10', date)
    return v, f'{fname}@{date}', vf, src


def run_checks():
    """执行全部对照：写对照CSV + 核验状态.json，返回(状态, 详情, summary)。"""
    date = common.TODAY
    rows = []
    state_pairs = {}
    items = list(CHECKS) + [(pid, name, thr, _pair_p4, None) for pid, name, thr, _ in SPECIAL_CHECKS]
    for pid, name, thr, fa, fb in items:
        va = vb = None
        sa = sb = ''
        err = []
        try:
            if fb is None:                  # 特殊对（P4）：A/B一次取齐
                va, sa, vb, sb = fa()
            else:
                va, sa = fa()
        except Exception as e:  # noqa: BLE001
            err.append(f'A源失败:{e}')
        time.sleep(1)  # 同站点间隔
        if fb is not None:
            try:
                vb, sb = fb()
            except Exception as e:  # noqa: BLE001
                err.append(f'B源失败:{e}')
        if va is not None and vb is not None:
            diff = round(va - vb, 4)
            pct = round(abs(va - vb) / abs(vb) * 100, 3) if vb else None
            concl = '一致' if (pct is not None and pct < thr) else f'偏差>{thr}%'
        else:
            diff = pct = ''
            concl = '取数失败:' + ';'.join(err)  # 不编造，如实记录
        rows.append({'验证日期': date, '指标': name, '来源A': sa,
                     '值A': va if va is not None else '', '来源B': sb,
                     '值B': vb if vb is not None else '',
                     '差异': diff, '差异%': pct, '结论': concl})
        state_pairs[pid] = {'词条': name.split(' ', 1)[-1], '值A': va, '源A': sa,
                            '值B': vb, '源B': sb, '偏差%': pct, '阈值%': thr,
                            '结果': concl if (pct is None or pct >= thr) else '通过',
                            '时间': date}
        time.sleep(1)

    upsert_rows(rows)
    ok = sum(1 for r in rows if r['结论'] == '一致')
    warn = sum(1 for r in rows if r['结论'].startswith('偏差'))
    fail = sum(1 for r in rows if r['结论'].startswith('取数失败'))
    _save_state({'对照': state_pairs, '通过': ok, '偏差': warn, '取数失败': fail})

    print(f'交叉验证结果（{date}，逐对阈值）')
    print('-' * 100)
    print(f"{'指标':<20}{'来源A':<14}{'值A':>12}{'来源B':<16}{'值B':>12}{'差异%':>9}  结论")
    for r in rows:
        print(f"{r['指标']:<20}{r['来源A']:<14}{str(r['值A']):>12}{r['来源B']:<16}"
              f"{str(r['值B']):>12}{str(r['差异%']):>9}  {r['结论']}")
    print('-' * 100)
    bad = [f'{r["指标"]}:{r["结论"]}' for r in rows if r['结论'] != '一致']
    print(f'汇总: {ok}/{len(rows)} 一致; 偏差{warn} 失败{fail}; 状态→ 核验状态.json')
    detail = f'{ok}/{len(rows)}一致' + (f'; 异常: {bad}' if bad else '')
    return ('成功' if not bad else '成功(存在偏差/失败)'), detail, \
        {'对照': state_pairs, '通过': ok, '偏差': warn, '取数失败': fail}


def _save_state(patch):
    """核验状态.json 读改写：run_checks 写 对照/汇总 段；存疑段由 run_all.write_state 维护。"""
    try:
        with open(STATE, encoding='utf-8') as f:
            st = json.load(f)
    except Exception:
        st = {}
    st.update(patch)
    st['更新时间'] = common.TODAY + ' ' + time.strftime('%H:%M:%S')
    tmp = STATE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


# 兼容旧调用名
def run():
    status, detail, _ = run_checks()
    return status, detail


if __name__ == '__main__':
    print(run())
