# -*- coding: utf-8 -*-
"""
数据固化共享工具库
- http_get: 带UA/重试/编码的GET
- save_row: 按数据日期upsert行到CSV（utf-8-sig，Excel可直接打开）
- log_result: 追加采集日志
- hw_check_get: 生意社(100ppi)两步法访问（模拟HW_CHECK cookie）
- em_get / em_kline: 东方财富行情快照与日K历史
- sina_hq / sina_kline: 新浪行情与期货日K
约定：CSV第一列必须为"数据日期"，日期格式 YYYY-MM-DD；数值列存纯数字（不带千分位）。
"""
import csv
import io
import os
import random
import re
import sys
import time
import datetime
import threading

import requests

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 看板数据固化/
CSV_DIR = os.path.join(BASE, 'CSV数据')
LOG_FILE = os.path.join(BASE, '采集日志.csv')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
TODAY = datetime.date.today().isoformat()
_lock = threading.Lock()

# 直连会话（来源归一期P-C2）：requests默认信任系统代理，桌面代理开关会造成偶发失败，显式关闭
_SESSION = requests.Session()
_SESSION.trust_env = False

os.makedirs(CSV_DIR, exist_ok=True)


def http_get(url, referer=None, encoding=None, retries=2, timeout=25, extra_headers=None):
    """GET并返回文本。encoding指定强制编码；否则requests自行判断。失败重试。"""
    headers = {'User-Agent': UA}
    if referer:
        headers['Referer'] = referer
    if extra_headers:
        headers.update(extra_headers)
    last = None
    for i in range(retries + 1):
        try:
            r = _SESSION.get(url, headers=headers, timeout=timeout)
            if encoding:
                r.encoding = encoding
            if r.status_code != 200:
                raise RuntimeError(f'HTTP {r.status_code}')
            return r.text
        except Exception as e:  # noqa: BLE001
            last = e
            if i < retries:
                time.sleep(2)
    raise RuntimeError(f'GET失败 {url}: {last}')


def http_post(url, data=None, referer=None, encoding=None, retries=2, timeout=25, as_json=False):
    headers = {'User-Agent': UA, 'X-Requested-With': 'XMLHttpRequest'}
    if referer:
        headers['Referer'] = referer
    last = None
    for i in range(retries + 1):
        try:
            r = _SESSION.post(url, headers=headers, data=data, timeout=timeout)
            if encoding:
                r.encoding = encoding
            if r.status_code != 200:
                raise RuntimeError(f'HTTP {r.status_code}')
            return r.json() if as_json else r.text
        except Exception as e:  # noqa: BLE001
            last = e
            if i < retries:
                time.sleep(2)
    raise RuntimeError(f'POST失败 {url}: {last}')


def save_row(csv_path, date_str, values: dict, columns: list, key_cols=None):
    """按日期upsert一行。values为{列名:值}，columns为表头（第一列须为'数据日期'）。
    key_cols：联合主键列名列表（默认['数据日期']），多行快照型CSV（如榜单）可用多键。
    schema保护（v12治理）：现存文件表头与请求不一致时拒绝写入（防历史清空），需走迁移流程。"""
    if columns[0] != '数据日期':
        raise ValueError('columns第一列必须为 数据日期')
    values = dict(values)
    values['数据日期'] = date_str
    key_cols = key_cols or ['数据日期']
    rows = []
    if os.path.exists(csv_path):
        with open(csv_path, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if reader.fieldnames and reader.fieldnames != columns:
                raise RuntimeError(
                    f'[save_row]表头不一致，已拒绝写入(防历史丢失): {os.path.basename(csv_path)}\n'
                    f'  现存: {reader.fieldnames}\n  请求: {columns}\n'
                    f'  → 请按 docs/数据治理/11_固化数据存储规范.md §5 执行迁移，或核对采集器COLUMNS')
    keyvals = [str(values.get(k, '')) for k in key_cols]
    replaced = False
    out = []
    for r in rows:
        if [str(r.get(k, '')) for k in key_cols] == keyvals:
            out.append({c: values.get(c, r.get(c, '')) for c in columns})
            replaced = True
        else:
            out.append({c: r.get(c, '') for c in columns})
    if not replaced:
        out.append({c: values.get(c, '') for c in columns})
    out.sort(key=lambda r: str(r.get(columns[0], '')))
    with _lock:
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=columns)
            w.writeheader()
            w.writerows(out)


_RUN = {'run_id': ''}


def begin_run(run_id=None):
    """开始一次批量采集：设置run_id，后续log_result自动带上（v12治理）。"""
    _RUN['run_id'] = run_id or datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    return _RUN['run_id']


def run_collector(mod, timeout=180):
    """统一包装器（v12治理）：计时/异常捕获/超时/结构化日志，采集器run()只管返回(状态,详情)。
    mod 为采集器模块、其globals()字典（__main__场景）均可；须暴露 PID/TITLE/run()，可选 BACKFILL。"""
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FutTimeout

    def _get(name, default=None):
        if isinstance(mod, dict):
            return mod.get(name, default)
        return getattr(mod, name, default)

    pid = _get('PID', '?')
    title = _get('TITLE') or str(_get('__name__', mod))
    backfill = _get('BACKFILL', 'latest')
    t0 = time.time()
    ex = ThreadPoolExecutor(max_workers=1)
    try:
        status, detail = ex.submit(_get('run')).result(timeout=timeout)
    except FutTimeout:
        status, detail = '失败', f'超时(>{timeout}s)，放弃等待'
    except Exception as e:  # noqa: BLE001
        status, detail = '失败', f'异常: {e}'
    elapsed = time.time() - t0
    log_result(pid, title, status, detail, elapsed=elapsed, backfill=backfill)
    ex.shutdown(wait=False)
    return status, detail, elapsed


PENDING_FILE = os.path.join(BASE, '待补录.csv')


def pending_quarters(csv_path, today=None):
    """检测CSV缺失的已完结季度（期末早于今天），返回['2026Q3',…]（v12治理：P46/P48考证补录机制）。"""
    dt = datetime.date.today() if today is None else today
    try:
        with open(csv_path, encoding='utf-8-sig', newline='') as f:
            dates = {str(r.get('数据日期', ''))[:10] for r in csv.DictReader(f)}
    except OSError:
        return []
    dates = {d for d in dates if re.match(r'^\d{4}-\d{2}-\d{2}$', d)}
    if not dates:
        return []
    def qend(y, q):
        m = q * 3
        nxt = datetime.date(y + (m == 12), 1 if m == 12 else m + 1, 1)
        return (nxt - datetime.timedelta(days=1)).isoformat()
    out, y, q = [], int(min(dates)[:4]), 1
    while True:
        e = qend(y, q)
        if e >= dt.isoformat():
            break
        if e >= min(dates) and e not in dates:
            out.append(f'{y}Q{q}')
        q += 1
        if q == 5:
            y, q = y + 1, 1
    return out


def report_pending(pid, title, quarters):
    """维护待补录清单（当前状态型：每pid保留最新检测）。返回本次缺失列表。"""
    rows = []
    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, encoding='utf-8-sig', newline='') as f:
            rows = [r for r in csv.DictReader(f) if r.get('P号') != f'P{pid}']
    if quarters:
        for q in quarters:
            rows.append({'P号': f'P{pid}', '词条': title, '缺失季度': q,
                         '发现时间': datetime.date.today().isoformat(), '状态': '待考证补录'})
    if rows:
        cols = ['P号', '词条', '缺失季度', '发现时间', '状态']
        with open(PENDING_FILE, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader(); w.writerows(rows)
    elif os.path.exists(PENDING_FILE):
        os.remove(PENDING_FILE)   # 缺口已补齐则清空
    return quarters


_LOG_HEADER = ['run_id', '采集时间', 'P号', '词条', '状态', '耗时秒', '回填策略', '详情']


def _ensure_log():
    """日志表头升级：旧格式归档为 采集日志_v1归档.csv，新文件用结构化表头。"""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', encoding='utf-8-sig', newline='') as f:
            csv.writer(f).writerow(_LOG_HEADER)
        return
    with open(LOG_FILE, encoding='utf-8-sig', newline='') as f:
        first = next(csv.reader(f), [])
    if first and first[0] != 'run_id':
        arch = os.path.join(os.path.dirname(LOG_FILE), '采集日志_v1归档.csv')
        os.replace(LOG_FILE, arch)
        with open(LOG_FILE, 'w', encoding='utf-8-sig', newline='') as f:
            csv.writer(f).writerow(_LOG_HEADER)


def log_result(p_id, title, status, detail='', elapsed=None, backfill=None):
    """追加采集日志：状态 ∈ 成功/失败/跳过。日志文件被占用（如Excel打开）时跳过，不影响采集本身。
    v12结构化列：run_id(批次自动带出)/耗时秒/回填策略 可选传入。"""
    _ensure_log()
    try:
        with _lock:
            with open(LOG_FILE, 'a', encoding='utf-8-sig', newline='') as f:
                w = csv.writer(f)
                w.writerow([_RUN['run_id'],
                            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            f'P{p_id}', title, status,
                            ('' if elapsed is None else round(elapsed, 1)),
                            backfill or '', str(detail)[:300]])
    except PermissionError:
        print(f'[warn] 采集日志被占用，未记录：P{p_id} {title} {status} {str(detail)[:80]}')


# ---------------- 生意社（HW_CHECK两步法） ----------------
_HW_SESSION = requests.Session()
_HW_SESSION.trust_env = False
_HW_SESSION.headers.update({'User-Agent': UA})


def hw_check_get(url):
    """生意社页面两步法：先取HW_CHECK cookie再带cookie访问。"""
    try:
        html = http_get(url)
        if 'HW_CHECK' not in html and len(html) > 5000:
            return html
    except Exception:  # noqa: BLE001
        pass
    m = re.search(r"cookieWithCheck\('([^']*)'\)", http_get(url))
    if not m:
        html0 = http_get(url)
        m = re.search(r"([A-Za-z0-9_+/=]{20,})", html0[:2000])
    token = m.group(1) if m else '1'
    _HW_SESSION.cookies.set('HW_CHECK', token, domain='.100ppi.com')
    r = _HW_SESSION.get(url, headers={'User-Agent': UA,
                                      'Referer': 'https://www.100ppi.com/'}, timeout=25)
    r.encoding = 'utf-8'
    if r.status_code != 200:
        raise RuntimeError(f'HTTP {r.status_code}')
    return r.text


# ---------------- 东方财富 ----------------
def _backoff(fn, waits=(5, 15, 30)):
    """指数退避重试（来源归一期P-C1）：push2系对单IP渐进式限流，短间隔重试会自我供给限流池，
    故首试后按5/15/30s+抖动退避，共4次机会。"""
    last = None
    for w in (0,) + waits:
        if w:
            time.sleep(w + random.uniform(0, 2))
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def em_get(secid, fields='f43,f57,f58,f60,f86,f169,f170', fltt=2):
    """东财行情快照。f43通常为最新价（fltt=2时已缩放）。push2限流敏感，走指数退避。"""
    import json

    def _one():
        d = json.loads(http_get(f'https://push2.eastmoney.com/api/qt/stock/get?secid={secid}'
                                f'&fields={fields}&fltt={fltt}&invt=2', retries=0))
        if not d.get('data'):
            raise RuntimeError(f'东财无数据 {secid}')
        return d['data']
    return _backoff(_one)


def em_kline(secid, klt=101, fqt=1, lmt=120):
    """东财日K历史。klt:101=日线,102=周线; 返回[(date, close)]。push2his限流敏感，走指数退避。"""
    import json

    def _one():
        txt = http_get(f'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}'
                       f'&klt={klt}&fqt={fqt}&lmt={lmt}&end=20500101'
                       f'&fields1=f1,f2,f3&fields2=f51,f53', retries=0)
        d = json.loads(txt)
        kl = (d.get('data') or {}).get('klines') or []
        if not kl:
            raise RuntimeError(f'东财日K为空 {secid}')
        return [(line.split(',')[0], float(line.split(',')[1])) for line in kl]
    return _backoff(_one)


def bulk_backfill(csv_path, klines, column, unit='元/吨', source='东方财富', note=''):
    """期货日K批量回填（一次读改写，供P31/P32/P39/P40复用）。
    klines: [(date, close)]；column如'期货主力元/吨'。
    已有行仅更新column列并保留原数据来源/备注（不覆盖现货口径）；仅当字段为空时补unit/source/note。"""
    rows = {}
    cols = None
    if os.path.exists(csv_path):
        with open(csv_path, encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames
            if cols:
                for r in reader:
                    rows[str(r.get(cols[0], ''))] = r
    if not cols:
        raise RuntimeError(f'{csv_path} 无表头，须先由采集器建表')
    for date, close in klines:
        r = rows.setdefault(date, {c: '' for c in cols})
        r[cols[0]] = date
        r[column] = close
        if not r.get('单位'):
            r['单位'] = unit
        if not r.get('数据来源'):
            r['数据来源'] = source
        if not r.get('备注'):
            r['备注'] = note
    out = [{c: rows[d].get(c, '') for c in cols} for d in sorted(rows)]
    with _lock:
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(out)


# ---------------- 新浪 ----------------
def sina_hq(codes):
    """新浪实时行情。codes如['hf_CAD','fx_seurcny','DINIW']。返回{code:[字段...]}（GBK已转）。"""
    url = 'https://hq.sinajs.cn/list=' + ','.join(codes)
    txt = http_get(url, referer='https://finance.sina.com.cn/', encoding='gbk')
    out = {}
    for line in txt.strip().splitlines():
        m = re.match(r'var hq_str_(\w+)="(.*)"', line.strip())
        if m:
            out[m.group(1)] = m.group(2).split(',')
    return out


def sina_kline(symbol, y=1):
    """新浪期货/外盘日K。symbol如 hf_CAD。返回[(date, close)]（最近y年）。"""
    txt = http_get(f'https://stock2.finance.sina.com.cn/futures/api/jsonp.php/'
                   f'x/InnerFuturesNewService.getDailyKLine?symbol={symbol.replace("hf_", "")}',
                   referer='https://finance.sina.com.cn/')
    import json
    m = re.search(r'\((\[.*\])\)', txt, re.S)
    if not m:
        raise RuntimeError('新浪日K解析失败')
    arr = json.loads(m.group(1))
    cut = (datetime.date.today() - datetime.timedelta(days=365 * y)).isoformat()
    return [(a['d'], float(a['c'])) for a in arr if a['d'] >= cut]


def parse_date_label(label):
    """把'2026-09'/'2026-09-30'/'2026Q3'/'2025'规范化为期末日期YYYY-MM-DD；解析失败返回抓取日。"""
    s = str(label).strip()
    m = re.match(r'^(\d{4})[-/年](\d{1,2})月?$', s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        nxt = datetime.date(y + (mo == 12), 1 if mo == 12 else mo + 1, 1)
        return (nxt - datetime.timedelta(days=1)).isoformat()
    m = re.match(r'^(\d{4})Q([1-4])$', s, re.I)
    if m:
        y, q = int(m.group(1)), int(m.group(2))
        mo = q * 3
        nxt = datetime.date(y + (mo == 12), 1 if mo == 12 else mo + 1, 1)
        return (nxt - datetime.timedelta(days=1)).isoformat()
    m = re.match(r'^(\d{4})$', s)
    if m:
        return f'{m.group(1)}-12-31'
    m = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})', s)
    if m:
        return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    return TODAY


# ---------------- Eurostat ----------------
def estat_series(dataset, params, since=None, retries=2, timeout=60):
    """Eurostat JSON API取序列，返回{period: value}（period=YYYY-MM）。
    params: dict，如{'geo':'EA20','coicop':'CP00'}；since: 'YYYY-MM'。"""
    import json
    q = ['format=JSON', 'lang=EN']
    for k, v in params.items():
        q.append(f'{k}={v}')
    if since:
        q.append(f'sinceTimePeriod={since}')
    url = (f'https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/'
           f'{dataset}?{"&".join(q)}')
    d = json.loads(http_get(url, retries=retries, timeout=timeout))
    dims = d.get('dimension') or {}
    size = d.get('size') or []
    names = [k for k in dims if isinstance(dims[k], dict) and 'category' in dims[k]]
    tid = dims['time']['category']['index']
    inv = {v: k for k, v in tid.items()}
    out = {}
    for k, v in (d.get('value') or {}).items():
        idxs, rem = [], int(k)
        for s in reversed(size):
            idxs.append(rem % s)
            rem //= s
        ti = dict(zip(names, reversed(idxs))).get('time')
        if ti is not None:
            out[inv[ti]] = v
    return out


def estat_series_merge(dataset, params, geos, since=None):
    """多geo聚合合并（欧元区聚合代码换代：EA20=2023-2025、EA21=2026起）。
    geos按优先级排列，取并集，靠前者优先。"""
    out = {}
    for g in geos:
        for period, v in estat_series(dataset, dict(params, geo=g), since=since).items():
            if v is not None:
                out.setdefault(period, v)
    return out


if __name__ == '__main__':
    print('common.py 自检：', CSV_DIR)
