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
RANGES_FILE = os.path.join(BASE, '词条注册表.csv')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
TODAY = datetime.date.today().isoformat()
_lock = threading.Lock()

# 直连会话（来源归一期P-C2）：requests默认信任系统代理，桌面代理开关会造成偶发失败，显式关闭
_SESSION = requests.Session()
_SESSION.trust_env = False

os.makedirs(CSV_DIR, exist_ok=True)


def http_get(url, referer=None, encoding=None, retries=2, timeout=(6, 20), extra_headers=None):
    """GET并返回文本。encoding指定强制编码；否则requests自行判断。失败重试。
    v18.8：timeout默认改(连接,读取)元组——标量timeout挡不住"慢滴流"挂死。"""
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


def http_post(url, data=None, referer=None, encoding=None, retries=2, timeout=(6, 20), as_json=False):
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


def write_csv_atomic(csv_path, fieldnames, rows):
    """CSV原子落盘（v18.7 P0止血）：先写同目录.tmp再os.replace——写入中途崩溃/断电
    不会截断原文件（旧行为是直接open('w')全量重写，坏过半截风险）。调用方自行持锁。"""
    tmp = csv_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, csv_path)


# ---------------- 数值核验（v19）：合理区间(硬拒绝) + 突变检测(软存疑) ----------------
# 区间规格来自 词条注册表.csv「合理区间」列，段式：'[拒]min~max' / '[疑]列名=min~max' / 'min~max'
# （默认级别=疑、适用全部数值列），多段';'分隔；显式列名段优先于'*'段，同级中'拒'优先于'疑'。
# 未配置区间的词条不做数值校验（资讯/图文类不经过此层）。存疑不拦截落库，由 run_collector
# 汇入 detail（采集日志/采集状态JSON可见）；拒写直接抛错放弃本次写入，保护台账。
SKIP_CHECK_COLS = {'数据日期', '单位', '数据来源', '备注', '标题', '链接', '图片URL', 'ASIN',
                   '验证日期', '指标', '来源A', '来源B', '差异', '差异%', '结论', '缺失季度', '序号'}
MUT_SKIP_COLS = {'排名'}          # 排名跳变属正常，不做突变检测
_MUT_BY_FREQ = {'每日': 0.25, '每周': 0.5, '每月': 0.8, '每季': 1.2, '半年度': 1.5, '每年': 2.0}
_RANGE_CACHE = None
SUSPECTS = []                     # 本次run()累计的存疑告警，run_collector收尾取走汇入detail


def _pid_from_csv(csv_path):
    """从CSV文件名取注册表P号（大宗商品-P22-xxx.csv → P22；-P201- → P201）。"""
    m = re.search(r'-P(\d+)-', os.path.basename(csv_path))
    return ('P' + m.group(1).lstrip('0')) if m else None


def _load_ranges():
    """惰性加载注册表「合理区间」列 → {P号: (更新频率, [(mode, col, lo, hi), ...])}。"""
    global _RANGE_CACHE
    if _RANGE_CACHE is None:
        _RANGE_CACHE = {}
        try:
            with open(RANGES_FILE, encoding='utf-8-sig', newline='') as f:
                for r in csv.DictReader(f):
                    spec = (r.get('合理区间') or '').strip()
                    if not spec:
                        continue
                    segs = []
                    for part in spec.split(';'):
                        part = part.strip()
                        if not part:
                            continue
                        mode = '疑'
                        m = re.match(r'^\[(拒|疑)\](.*)$', part)
                        if m:
                            mode, part = m.group(1), m.group(2).strip()
                        col = '*'
                        if '=' in part:
                            col, part = part.split('=', 1)
                            col, part = col.strip(), part.strip()
                        lohi = part.split('~')
                        lo = float(lohi[0]) if lohi and lohi[0].strip() != '' else None
                        hi = float(lohi[1]) if len(lohi) > 1 and lohi[1].strip() != '' else None
                        segs.append((mode, col, lo, hi))
                    if segs:
                        _RANGE_CACHE[str(r.get('P号', ''))] = ((r.get('更新频率') or '').strip(), segs)
        except Exception as e:  # noqa: BLE001
            print(f'[warn] 合理区间加载失败（本次运行不做区间校验，不影响采集）: {e}')
            _RANGE_CACHE = {}
    return _RANGE_CACHE


def verify_row(csv_path, values, existing_rows, date_str, mutation=True):
    """对一行待写数值做两级校验，返回[(level, msg)]，level ∈ REJECT/SUSPECT。
    [拒]全日期生效（越界抛错放弃写入）；[疑]仅近7日日期生效（历史行疑告警会在每日重跑中反复出现=噪音）。
    突变检测（近7日日期才启用）：与本列按日期序近24点局部中位数比，双条件=相对偏离超阈值
    （每日25%/每周50%/每月80%/每季120%/半年150%/每年200%，其余60%）且绝对偏离>近24点窗口跨度×10%
    （防空比噪声）。历史点<5不启用。
    mutation=False 用于横截面快照类CSV（联合主键，如Amazon榜单）——列构成逐日变化，
    突变无统计意义，只保留区间校验。"""
    pid = _pid_from_csv(csv_path)
    cache = _load_ranges()
    if not pid or pid not in cache:
        return []
    freq, segs = cache[pid]
    mut_lim = _MUT_BY_FREQ.get(freq, 0.6)
    cutoff7 = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    recent = str(date_str) >= cutoff7   # [疑]与突变仅对近7日日期生效；[拒]全日期生效（历史行疑告警会在每日重跑中反复出现=噪音）
    out = []
    for col, raw in values.items():
        if col in SKIP_CHECK_COLS or col == '数据日期':
            continue
        try:
            v = float(str(raw).replace(',', '').strip())
        except (TypeError, ValueError):
            continue
        hit_rej = hit_sus = None
        has_col_specific = any(s_col == col for _, s_col, _, _ in segs)
        for s_mode, s_col, lo, hi in segs:
            if s_col != col and not (s_col == '*' and not has_col_specific):
                continue
            if s_mode == '疑' and not recent:
                continue
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                msg = f'{col}={v} 超出{s_mode}写区间[{lo},{hi}]'
                if s_mode == '拒':
                    hit_rej = hit_rej or msg
                else:
                    hit_sus = hit_sus or msg
        if hit_rej:
            out.append(('REJECT', hit_rej))
        elif hit_sus:
            out.append(('SUSPECT', hit_sus))
        if not mutation or col in MUT_SKIP_COLS or not existing_rows:
            continue
        # 突变检测（v19.2三修正）：①只对近7日日期生效（历史回填行不做——趋势序列必然"突变"）；
        # ②基线=按日期序近24点局部中位数（全历史中位数对长期趋势是坏基线，如P12利率长期下行）；
        # ③双条件：相对偏离>阈值 且 绝对偏离>近24点窗口跨度×10%（防空比噪声，如环比-0.4vs中位2.2=118%）
        pts = []
        for r in existing_rows:
            d = str(r.get('数据日期', ''))
            if d and str(date_str) > d >= cutoff7:
                try:
                    pts.append((d, float(str(r.get(col, '')).replace(',', '').strip())))
                except (TypeError, ValueError):
                    continue
        pts.sort(key=lambda p: p[0])
        if len(pts) >= 5:
            w = [v for _, v in pts[-24:]]
            w.sort()
            m = len(w)
            med = w[m // 2] if m % 2 else (w[m // 2 - 1] + w[m // 2]) / 2
            span = w[-1] - w[0]
            dev = abs(v - med)
            if med and dev > abs(span) * 0.10 and dev / abs(med) > mut_lim:
                pct = round(dev / abs(med) * 100, 1)
                out.append(('SUSPECT', f'{col}={v} 较近24点中位数{round(med, 4)}突变({pct}%>'
                                        f'{int(mut_lim * 100)}%)'))
    return out


def pop_suspects():
    """取走本次run()累计的存疑告警（run_collector收尾汇入detail后清空）。"""
    global SUSPECTS
    s, SUSPECTS = SUSPECTS, []
    return s


def http_bin(url, referer=None, timeout=(8, 25), min_bytes=0, retries=1):
    """GET并返回bytes（图片下载用，v18.8）：trust_env=False会话+连接级超时元组。
    返回 None 表示失败（HTTP非200不重试——换候选图比等重试划算），调用方自行兜底。"""
    headers = {'User-Agent': UA}
    if referer:
        headers['Referer'] = referer
    for i in range(retries + 1):
        try:
            r = _SESSION.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200 and len(r.content) > min_bytes:
                return r.content
            if r.status_code != 200:
                return None
        except Exception:  # noqa: BLE001
            if i < retries:
                time.sleep(1)
    return None


def save_row(csv_path, date_str, values: dict, columns: list, key_cols=None):
    """按日期upsert一行。values为{列名:值}，columns为表头（第一列须为'数据日期'）。
    key_cols：联合主键列名列表（默认['数据日期']），多行快照型CSV（如榜单）可用多键。
    schema保护（v12治理）：现存文件表头与请求不一致时拒绝写入（防历史清空），需走迁移流程。
    v18.7：文件存在但无表头（0字节/截断）同样拒绝写入（旧行为会静默当空表重建只剩1行）。"""
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
            if not reader.fieldnames:
                raise RuntimeError(
                    f'[save_row]{os.path.basename(csv_path)} 无表头(0字节或截断损坏)，'
                    f'已拒绝写入(防历史丢失)——请先从git历史/归档恢复该CSV再采集')
            if reader.fieldnames != columns:
                raise RuntimeError(
                    f'[save_row]表头不一致，已拒绝写入(防历史丢失): {os.path.basename(csv_path)}\n'
                    f'  现存: {reader.fieldnames}\n  请求: {columns}\n'
                    f'  → 请按 docs/数据治理/11_固化数据存储规范.md §5 执行迁移，或核对采集器COLUMNS')
    # 数值核验（v19）：[拒]区间越界=放弃写入；[疑]越界/突变=告警汇入采集详情
    # 横截面快照类（联合主键）跳过突变检测——列构成逐日变化，中位数无统计意义
    for lvl, msg in verify_row(csv_path, values, rows, date_str,
                               mutation=(key_cols == ['数据日期'])):
        if lvl == 'REJECT':
            raise RuntimeError(f'[save_row]数值核验拒绝写入: {msg}（数据未落库；'
                               f'如确属真实值请核对采集器/注册表合理区间配置）')
        SUSPECTS.append(msg)
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
        write_csv_atomic(csv_path, columns, out)


RUN_ID_ENV = 'DNS_RUN_ID'   # run_all子进程调度时经环境变量透传批次run_id（v18.8）
_RUN = {'run_id': os.environ.get(RUN_ID_ENV, '')}


def begin_run(run_id=None):
    """开始一次批量采集：设置run_id，后续log_result自动带上（v12治理）。"""
    _RUN['run_id'] = run_id or datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    return _RUN['run_id']


def run_collector(mod, timeout=180):
    """统一包装器（v12治理，v18.8改造）：计时/异常捕获/超时/结构化日志，采集器run()只管返回(状态,详情)。
    mod 为采集器模块、其globals()字典（__main__场景）均可；须暴露 PID/TITLE/run()，可选 BACKFILL。
    超时改守护线程+队列：旧ThreadPoolExecutor的工作线程卡在socket里且非daemon、解释器退出时
    被atexit join，把整个run_all批次收尾无限期挂死（Kickstarter慢拦截549s案例的放大器）。
    daemon线程不阻塞退出；迟到结果经容量1队列丢弃。run_all已改子进程硬超时，本包装器兜底直接调用。"""
    import queue
    import threading

    def _get(name, default=None):
        if isinstance(mod, dict):
            return mod.get(name, default)
        return getattr(mod, name, default)

    pid = _get('PID', '?')
    title = _get('TITLE') or str(_get('__name__', mod))
    backfill = _get('BACKFILL', 'latest')
    t0 = time.time()
    q = queue.Queue(maxsize=1)

    def _worker():
        try:
            q.put(('ok', _get('run')()))
        except Exception as e:  # noqa: BLE001
            try:
                q.put(('err', e))
            except Exception:  # noqa: BLE001
                pass

    threading.Thread(target=_worker, daemon=True).start()
    try:
        kind, payload = q.get(timeout=timeout)
        if kind == 'ok':
            status, detail = payload
            susp = pop_suspects()
            if susp:
                detail = (str(detail) + ' | ⚠存疑:' + '; '.join(susp[:4]))[:380]
        else:
            status, detail = '失败', f'异常: {payload}'
    except queue.Empty:
        status, detail = '失败', f'超时(>{timeout}s)，放弃等待(daemon线程已托管)'
    elapsed = time.time() - t0
    log_result(pid, title, status, detail, elapsed=elapsed, backfill=backfill)
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
        with _lock:
            write_csv_atomic(PENDING_FILE, cols, rows)
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
    try:
        _ensure_log()   # v18.7：纳入try——日志被Excel占用时不再让PermissionError上抛把成功采集记成失败
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
class FatalError(RuntimeError):
    """不可重试错误（如接口明确返回空数据）——_backoff立即上抛，不再空耗5/15/30s退避
    （v18.8：周末跑EM_HEAVY九采集器曾各白烧约52s）。"""


def _backoff(fn, waits=(5, 15, 30)):
    """指数退避重试（来源归一期P-C1）：push2系对单IP渐进式限流，短间隔重试会自我供给限流池，
    故首试后按5/15/30s+抖动退避，共4次机会。FatalError（空数据等确定性失败）立即上抛。"""
    last = None
    for w in (0,) + waits:
        if w:
            time.sleep(w + random.uniform(0, 2))
        try:
            return fn()
        except FatalError:
            raise
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
            raise FatalError(f'东财无数据 {secid}')
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
            raise FatalError(f'东财日K为空 {secid}')
        return [(line.split(',')[0], float(line.split(',')[1])) for line in kl]
    return _backoff(_one)


def bulk_backfill(csv_path, klines, column, unit='元/吨', source='东方财富', note='',
                  fill_empty_only=False, rework_days=0):
    """期货日K批量回填（一次读改写，供P22/P23/P27/P31/P32/P39/P40复用）。
    klines: [(date, close)]；column如'期货主力元/吨'。
    已有行仅更新column列并保留原数据来源/备注（不覆盖现货口径）；仅当字段为空时补unit/source/note。
    fill_empty_only=True时只补空缺单元格，不回写已有值（2026-11-04通道切换起用：固化历史不回写）。
    rework_days=N（v18.8）：近N日内已有值也覆写并刷新来源/备注——盘中采集的当日/昨日未收盘价
    允许随后续运行修正；0=保持只补缺失语义。返回(新增行数, 勘误行数)。"""
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
    cutoff = ''
    if rework_days > 0:
        cutoff = (datetime.date.today() - datetime.timedelta(days=rework_days - 1)).isoformat()
    recent = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    known = [d for d, r in rows.items() if str(r.get(column, '')).strip()]
    first_known = min(known) if known else None
    rejects = []
    n_new = n_rework = 0
    for date, close in klines:
        r = rows.setdefault(date, {c: '' for c in cols})
        had = str(r.get(column, '')).strip()
        if fill_empty_only and had and (not cutoff or date < cutoff):
            continue
        # 数值核验（v19）：全部写入值过[拒]/[疑]区间；近7日写入值另做突变检测。
        # 早于既有台账最早日期的历史延伸：仅做[拒]物理界校验（疑区间基于现有包络，
        # 对历史延伸必然误报，如回填到更早的价格峰值）。
        if first_known and date < first_known:
            for lvl, msg in verify_row(csv_path, {column: close}, [], date):
                if lvl == 'REJECT':
                    rejects.append(f'{date} {msg}')
        else:
            for lvl, msg in verify_row(csv_path, {column: close}, list(rows.values()) if date >= recent else [], date):
                if lvl == 'REJECT':
                    rejects.append(f'{date} {msg}')
                else:
                    SUSPECTS.append(f'{date} {msg}')
        if had:
            n_rework += 1
        else:
            n_new += 1
        r[cols[0]] = date
        r[column] = close
        if not r.get('单位'):
            r['单位'] = unit
        if not had or (cutoff and date >= cutoff):
            r['数据来源'] = source
            r['备注'] = note
    if rejects:
        raise RuntimeError('[bulk_backfill]数值核验拒绝写入(数据未落库): ' + '; '.join(rejects[:5])
                           + (f' 等共{len(rejects)}条' if len(rejects) > 5 else ''))
    out = [{c: rows[d].get(c, '') for c in cols} for d in sorted(rows)]
    with _lock:
        write_csv_atomic(csv_path, cols, out)
    return n_new, n_rework


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


def sina_forex_kline(symbol, y=1):
    """新浪外汇日K。symbol如 DINIW/fx_susdcnh/fx_seurcny。返回[(date, close)]（最近y年）。
    记录为'date,open,low,high,close,'管道分隔；字段顺序经2026-11-04腾讯whUSDX今开/昨收交叉核验，
    解析时校验高低收自洽，异常即抛错（防静默错位）。"""
    txt = http_get('https://vip.stock.finance.sina.com.cn/forex/api/jsonp.php/'
                   f'var%20t=/NewForexService.getDayKLine?symbol={symbol}',
                   referer='https://finance.sina.com.cn/')
    m = re.search(r'\("(.*)"\)', txt, re.S)
    if not m:
        raise RuntimeError('新浪外汇日K解析失败')
    cut = (datetime.date.today() - datetime.timedelta(days=365 * y)).isoformat()
    out = []
    for rec in m.group(1).split('|'):
        f = rec.strip().split(',')
        if len(f) < 5 or not f[0]:
            continue
        d, o, l, h, c = f[0], float(f[1]), float(f[2]), float(f[3]), float(f[4])
        if h < l or h < o or h < c or l > o or l > c:
            raise RuntimeError(f'新浪外汇日K高低收异常 {d}')
        if d >= cut:
            out.append((d, c))
    return out


def sina_global_kline(symbol, days=365):
    """新浪全球期货日K（hf_*国内InnerFutures不适用，如LME铜CAD、布伦特OIL）。返回[(date, close)]。"""
    import json
    txt = http_get('https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20t=/'
                   f'GlobalFuturesService.getGlobalFuturesDailyKLine?symbol={symbol}',
                   referer='https://finance.sina.com.cn/')
    m = re.search(r'\((\[.*\])\)', txt, re.S)
    if not m:
        raise RuntimeError('新浪全球日K解析失败')
    cut = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    return [(a['date'], float(a['close'])) for a in json.loads(m.group(1))
            if a.get('date', '') >= cut and a.get('close')]


def collect_series(csv_path, *, primary='sina', kind='fx', sina_sym='', em_secid='',
                   column='数值', unit='', note='', fill_empty_only=True, rework_days=2):
    """行情日K五件套（v18.9样板收敛）：主通道取日K→备用通道自动降级→bulk_backfill一次落库→
    实时快照核验。采集器run()直接 `return common.collect_series(...)` 即可。
    primary='sina'：新浪主（kind='fx'走sina_forex_kline、'fut'走sina_kline('hf_'+sym)），
                    东财em_kline(secid)自动降级——P22/P23/P27形态；
    primary='em'：东财主em_kline，新浪自动降级，另取东财快照f43核验（跨源/快照失败如实标注）——
                  P30/P52形态（该形态fill_empty_only=False沿用整表覆写语义）。
    核验：新浪hq取最新价与日K尾值比（fx取字段1、fut取字段0），2%阈值。"""
    time.sleep(1)
    snap = snap_note = None
    src_note_sina = '新浪财经'
    src_note_em = '东方财富'
    sina = (sina_forex_kline if kind == 'fx' else
            (lambda s, y=1: sina_kline('hf_' + s, y=y)))
    hq_code = sina_sym if kind == 'fx' else 'hf_' + sina_sym
    hq_idx = 1 if kind == 'fx' else 0
    try:
        if primary == 'sina':
            kl = sina(sina_sym, y=1)
            src = src_note_sina
        else:
            try:
                snap = em_get(em_secid)
                snap_note = None
            except Exception as se:  # noqa: BLE001
                snap, snap_note = None, f'快照失败降级({str(se)[:40]})'
            time.sleep(1)
            try:
                kl = em_kline(em_secid, lmt=120)
                src = src_note_em
            except Exception:  # noqa: BLE001
                time.sleep(2)
                kl = sina(sina_sym, y=1)
                src = src_note_sina
    except Exception as e:  # noqa: BLE001
        return '失败', f'双通道均失败: {e}'
    if not kl:
        return '失败', '日K为空'
    n_new, n_rw = bulk_backfill(csv_path, kl, column, unit=unit,
                                source=src, note=note,
                                fill_empty_only=fill_empty_only, rework_days=rework_days)
    last_d, last_v = kl[-1]
    parts = [f'新增{n_new}天' + (f'/勘误{n_rw}天' if fill_empty_only and n_rw else ''),
             f'最新{last_d}={last_v}({src})']
    if primary == 'em':
        tag = f'回填{len(kl)}天' + ('' if src == src_note_em else '(新浪降级)')
        if snap is None:
            parts = [tag, f'最新{last_d}={last_v}', snap_note or '']
        elif src != src_note_em:
            parts = [tag, f'最新{last_d}={last_v}', '快照核验跳过(跨源)']
        else:
            snap_v = float(snap.get('f43'))
            chk = '一致' if abs(snap_v - last_v) / max(snap_v, 1e-9) < 0.02 else '偏差'
            parts = [tag, f'最新{last_d}={last_v}', f'快照{snap_v}({chk})']
    else:
        try:
            spot = sina_hq([hq_code])[hq_code]
            chk = '一致' if abs(float(spot[hq_idx]) - last_v) / max(float(spot[hq_idx]), 1e-9) < 0.02 else '偏差'
            parts.append(f'实时核验{chk}')
        except Exception:  # noqa: BLE001
            parts.append('实时核验跳过')
    return '成功', ', '.join(p for p in parts if p)


def fut_dual_kline(sina_sym, secid, name_cn, lmt=250):
    """生意社双列卡的期货主力日K（v18.9收敛，P31/P32/P39/P40共用）：
    主=新浪(hf_符号)，东财(secid)自动降级。返回([(date, close), 来源, 备注])。
    现货半边页面形态不同（vane/rawmex），由各采集器自留解析。"""
    try:
        return sina_kline('hf_' + sina_sym, y=1), '新浪财经', f'{name_cn}收盘(新浪日K)'
    except Exception:  # noqa: BLE001
        time.sleep(2)
        return em_kline(secid, lmt=lmt), '东方财富', f'{name_cn}收盘(东财回填)'


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
