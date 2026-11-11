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
import math
import os
import sys
import time
from decimal import Decimal

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


def _from_ledger(pid_num, date=None):
    """台账末值或指定观测日；指定日期缺失时拒绝用相邻日代替。"""
    import glob as _g
    hits = _g.glob(os.path.join(common.CSV_DIR, f'*-P{pid_num}-*.csv'))
    if not hits:
        raise RuntimeError(f'P{pid_num}台账不存在')
    with open(hits[0], encoding='utf-8-sig', newline='') as f:
        rows = [r for r in csv.DictReader(f)]
    rows = [r for r in rows if r.get('数据日期')]
    if date is not None:
        rows = [r for r in rows if r['数据日期'] == date]
    if not rows:
        raise RuntimeError(f'P{pid_num}台账无{date or "有效日期"}数据')
    rows.sort(key=lambda r: r['数据日期'])
    last = rows[-1]
    for c in ('数值', '同比%', '收盘'):
        v = (last.get(c) or '').strip()
        if v:
            try:
                value = float(v.replace(',', ''))
                if math.isfinite(value):
                    return value, last['数据日期'], os.path.basename(hits[0])
            except ValueError:
                pass
    raise RuntimeError(f'P{pid_num}台账末行无可用数值列')


def from_ledger_last(pid_num):
    """台账末值+观测日+文件名。"""
    return _from_ledger(pid_num)


def from_ledger_at(pid_num, date):
    """台账指定观测日的值；不做日期回退。"""
    return _from_ledger(pid_num, date)


def from_fred_at(series_id, date, back_days=6):
    """返回(值, 实际观测日, 来源)；含请求当日在内回看back_days个自然日。"""
    try:
        sys.path.insert(0, HERE)
        from _keys import FRED_API_KEY
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f'_keys.FRED_API_KEY不可用: {e}')
    import datetime as _dt
    d0 = _dt.date.fromisoformat(date)
    days = max(1, back_days)
    start = (d0 - _dt.timedelta(days=days - 1)).isoformat()
    # 显式限定观测区间，避免校验历史台账时只拿到全库最近60条。
    url = (f'https://api.stlouisfed.org/fred/series/observations?series_id={series_id}'
           f'&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit={days}'
           f'&observation_start={start}&observation_end={date}')
    try:
        obs = json.loads(common.http_get(url)).get('observations', [])
    except Exception as e:
        # common的HTTP错误会包含完整URL，避免密钥进入对照CSV或核验状态。
        detail = str(e).replace(FRED_API_KEY, '[已隐藏]') if FRED_API_KEY else str(e)
        raise RuntimeError(f'FRED {series_id} 请求失败:{detail}') from None
    for _ in range(days):
        for o in obs:
            if o.get('date') == d0.isoformat() and o.get('value') not in ('.', ''):
                try:
                    value = float(o['value'])
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value):
                    return value, o['date'], f'FRED {series_id}@{o["date"]}'
        d0 -= _dt.timedelta(days=1)
    raise RuntimeError(f'FRED {series_id} 无 {start}至{date}有效观测')


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
# P4收益率数值以百分数表示：1bp=0.01个百分点；容差含边界。
SPECIAL_CHECKS = [('P4', 'P4 10年期美债(台账vsFRED)', 1.0, None)]


def _pair_p4():
    """P4只比较同一观测日；FRED回溯后，台账必须重取该日，缺失则待对齐。"""
    pair = {'va': None, 'vb': None, 'sa': '', 'sb': '',
            'date_a': '', 'date_b': '', 'requested_date': '', 'error': '', 'alignment_error': ''}
    try:
        v, date, fname = from_ledger_last('04')
    except Exception as e:
        pair['error'] = f'A源失败:{e}'
        return pair
    pair.update(va=v, sa=f'{fname}@{date}', date_a=date, requested_date=date)
    try:
        vf, fred_date, src = from_fred_at('DGS10', date)
    except Exception as e:
        pair['error'] = f'B源失败:{e}'
        return pair
    pair.update(vb=vf, sb=src, date_b=fred_date)
    if fred_date != date:
        try:
            v, ledger_date, fname = from_ledger_at('04', fred_date)
        except Exception as e:
            pair['alignment_error'] = f'FRED观测日{fred_date}，台账未能取同日数据:{e}'
            return pair
        pair.update(va=v, sa=f'{fname}@{ledger_date}', date_a=ledger_date)
    if pair['date_a'] != pair['date_b']:
        pair['alignment_error'] = f'观测日不同:{pair["date_a"]}/{pair["date_b"]}'
    return pair


def run_checks():
    """执行全部对照：写对照CSV + 核验状态.json，返回(状态, 详情, summary)。"""
    date = common.TODAY
    rows = []
    state_pairs = {}
    items = list(CHECKS) + [(pid, name, thr, _pair_p4, None) for pid, name, thr, _ in SPECIAL_CHECKS]
    for pid, name, thr, fa, fb in items:
        va = vb = None
        sa = sb = ''
        date_a = date_b = requested_date = alignment_error = ''
        is_p4 = pid == 'P4'
        err = []
        try:
            if fb is None:                  # 特殊对（P4）：A/B一次取齐
                pair = fa()
                va, sa, vb, sb = pair['va'], pair['sa'], pair['vb'], pair['sb']
                date_a, date_b = pair['date_a'], pair['date_b']
                requested_date, alignment_error = pair['requested_date'], pair['alignment_error']
                if pair['error']:
                    err.append(pair['error'])
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
        passed = False
        diff = pct = bp = None
        if alignment_error or (is_p4 and not err and (not date_a or not date_b or date_a != date_b)):
            concl = '待对齐:' + (alignment_error or f'观测日不同:{date_a}/{date_b}')
        elif va is not None and vb is not None and not err:
            diff = round(va - vb, 4)
            pct = round(abs(va - vb) / abs(vb) * 100, 3) if vb else None
            if is_p4:
                # Decimal避免4.91-4.90的浮点误差将恰好1bp误判为超限。
                bp = float(abs(Decimal(str(va)) - Decimal(str(vb))) * 100)
                passed = bp <= thr
                concl = (f'一致（同日{date_a}；偏差{bp:g}bp≤{thr:g}bp）' if passed else
                         f'偏差>{thr:g}bp（同日{date_a}；偏差{bp:g}bp）')
            else:
                passed = pct is not None and pct < thr
                concl = '一致' if passed else f'偏差>{thr}%'
        else:
            concl = '取数失败:' + ';'.join(err)  # 不编造，如实记录
        if is_p4 and not (concl.startswith('一致') or concl.startswith('偏差')):
            concl += f'（容差≤{thr:g}bp）'
        rows.append({'验证日期': date, '指标': name, '来源A': sa,
                     '值A': va if va is not None else '', '来源B': sb,
                     '值B': vb if vb is not None else '',
                     '差异': diff if diff is not None else '',
                     '差异%': pct if pct is not None else '', '结论': concl})
        state_pairs[pid] = {'词条': name.split(' ', 1)[-1], '值A': va, '源A': sa,
                            '值B': vb, '源B': sb, '偏差%': pct, '阈值%': None if is_p4 else thr,
                            '结果': '通过' if passed else concl,
                            '时间': date, '数据日期A': date_a, '数据日期B': date_b,
                            '对照日期': date_a if passed or (date_a and date_a == date_b) else '',
                            '请求日期': requested_date, '容差单位': 'bp' if is_p4 else '%', '容差': thr}
        if is_p4:
            state_pairs[pid].update({'偏差bp': bp, '阈值bp': thr})
        time.sleep(1)

    upsert_rows(rows)
    ok = sum(1 for r in rows if r['结论'].startswith('一致'))
    warn = sum(1 for r in rows if r['结论'].startswith('偏差'))
    fail = sum(1 for r in rows if r['结论'].startswith('取数失败'))
    pending = sum(1 for r in rows if r['结论'].startswith('待对齐'))
    _save_state({'对照': state_pairs, '对照汇总': {'通过': ok, '偏差': warn, '取数失败': fail, '待对齐': pending}})

    print(f'交叉验证结果（{date}，逐对阈值）')
    print('-' * 100)
    print(f"{'指标':<20}{'来源A':<14}{'值A':>12}{'来源B':<16}{'值B':>12}{'差异%':>9}  结论")
    for r in rows:
        print(f"{r['指标']:<20}{r['来源A']:<14}{str(r['值A']):>12}{r['来源B']:<16}"
              f"{str(r['值B']):>12}{str(r['差异%']):>9}  {r['结论']}")
    print('-' * 100)
    bad = [f'{r["指标"]}:{r["结论"]}' for r in rows if not r['结论'].startswith('一致')]
    print(f'汇总: {ok}/{len(rows)} 一致; 偏差{warn} 失败{fail} 待对齐{pending}; 状态→ 核验状态.json')
    detail = f'{ok}/{len(rows)}一致' + (f'; 异常: {bad}' if bad else '')
    return ('成功' if not bad else '成功(存在偏差/失败/待对齐)'), detail, \
        {'对照': state_pairs, '通过': ok, '偏差': warn, '取数失败': fail, '待对齐': pending}


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
