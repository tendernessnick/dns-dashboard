# -*- coding: utf-8 -*-
"""P69 行业数据-美国线下零售：FRED RSEAS月度全量历史（直连超时多重试，仍不通则经web.archive.org回源取同一CSV）
通道升级三期修复：原采集器用裸requests（trust_env=True），桌面系统代理拉起时被劫持到不稳线路导致
持续超时；现统一改走common.http_get（显式直连+重试），同源同口径不变。"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

CSV_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=RSEAS'
SPN_URL = 'https://web.archive.org/save/https://fred.stlouisfed.org/graph/fredgraph.csv?id=RSEAS'
CSV = os.path.join(common.CSV_DIR, '行业数据-P69-美国线下零售.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
BACKFILL_MONTHS = 24


def _fetch_fred(retries=4):
    """直连FRED，偶发超时多重试（common.http_get显式直连，免疫系统代理）"""
    last = None
    for i in range(retries):
        try:
            txt = common.http_get(CSV_URL, retries=0, timeout=30)
            if 'observation_date' in txt[:100]:
                return txt, '直连'
            last = RuntimeError(f'HTTP异常响应(前100字符): {txt[:60]}')
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(3)
    raise RuntimeError(f'直连FRED失败: {last}')


def _fetch_fred_api():
    """备用1：FRED官方API（api.stlouisfed.org，需免费key，见_keys.py）。
    与fredgraph.csv同一序列RSEAS同源同口径；返回[(date, value)]升序。"""
    import json as _json
    try:
        from _keys import FRED_API_KEY
    except ImportError:
        raise RuntimeError('_keys.py不存在')
    if not FRED_API_KEY:
        raise RuntimeError('FRED_API_KEY未配置')
    api = ('https://api.stlouisfed.org/fred/series/observations?series_id=RSEAS'
           f'&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=36')
    d = _json.loads(common.http_get(api, retries=1, timeout=30))
    obs = d.get('observations') or []
    if d.get('error_code') or not obs:
        raise RuntimeError(f'FRED API异常: {str(d.get("error_message"))[:80]}')
    rows = []
    for o in obs:
        v = str(o.get('value', '')).strip()
        if v in ('.', ''):
            continue
        try:
            rows.append((o['date'], float(v)))
        except (KeyError, ValueError):
            continue
    rows.reverse()  # desc→asc
    if len(rows) < BACKFILL_MONTHS:
        raise RuntimeError(f'API有效月份数不足: {len(rows)}')
    return rows, 'FRED官方API'


def _fetch_via_wayback():
    """经web.archive.org获取FRED原CSV（存档爬虫回源抓取的同一文件，非镜像改写）：
    先查已有快照；无快照时触发Save Page Now回源新建。"""
    import json as _json
    import urllib.parse
    api = ('https://archive.org/wayback/available?url='
           + urllib.parse.quote('https://fred.stlouisfed.org/graph/fredgraph.csv?id=RSEAS', safe=''))
    try:
        txt = common.http_get(api, retries=0, timeout=30)
        closest = ((_json.loads(txt).get('archived_snapshots') or {}).get('closest') or {})
        snap_url = closest.get('url')
        if snap_url:
            raw = re.sub(r'/web/(\d{14})/', r'/web/\1id_/', snap_url, count=1)
            t2 = common.http_get(raw, retries=0, timeout=60)
            if 'observation_date' in t2[:200]:
                return t2, 'web.archive.org已有快照'
    except Exception:  # noqa: BLE001
        pass
    # 无快照→Save Page Now回源（有频次限制，429时提示稍后重试）
    try:
        r = common.http_get(SPN_URL, retries=0, timeout=90)
        if 'observation_date' not in r[:200]:
            raise RuntimeError(f'Wayback回源失败: 异常响应')
        return r, 'web.archive.org回源'
    except RuntimeError as e:
        if '429' in str(e):
            raise RuntimeError('Wayback回源限流(HTTP 429)，请稍后重试')
        raise


def run():
    rows, how = None, ''
    try:  # 主：fredgraph.csv直连
        text, how = _fetch_fred()
        rows = []
        for line in text.strip().splitlines():
            parts = line.split(',')
            if len(parts) != 2 or parts[0] == 'observation_date':
                continue
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', parts[0]):
                continue
            v = parts[1].strip()
            if v in ('.', ''):
                continue
            try:
                rows.append((parts[0], float(v)))
            except ValueError:
                continue
        if len(rows) < BACKFILL_MONTHS:
            return '失败', f'RSEAS有效月份数不足: {len(rows)}'
    except Exception as e1:  # noqa: BLE001
        try:  # 备1：FRED官方API（2026-11-05新增，key见_keys.py）
            rows, how = _fetch_fred_api()
        except Exception as e2:  # noqa: BLE001
            try:  # 备2：web.archive.org回源
                text, how = _fetch_via_wayback()
                rows = []
                for line in text.strip().splitlines():
                    parts = line.split(',')
                    if len(parts) != 2 or parts[0] == 'observation_date':
                        continue
                    if not re.match(r'^\d{4}-\d{2}-\d{2}$', parts[0]):
                        continue
                    v = parts[1].strip()
                    if v in ('.', ''):
                        continue
                    try:
                        rows.append((parts[0], float(v)))
                    except ValueError:
                        continue
            except Exception as e3:  # noqa: BLE001
                return '失败', f'FRED直连/API/回源均失败: 直连[{str(e1)[:60]}] API[{str(e2)[:60]}] 回源[{str(e3)[:60]}]'
    rows = rows[-BACKFILL_MONTHS:]
    note = f'美国零售和食品服务销售额(季调,月度)；近{BACKFILL_MONTHS}个月回填'
    if how == 'FRED官方API':
        note += '；fredgraph超时，经FRED官方API获取同一序列'
    elif how != '直连':
        note += f'；本机直连FRED超时，经{how}获取原CSV'
    # v18.8：量级校验提前到落库之前（旧顺序先写24行再验，异常值已固化才报失败）
    last_d, last_v = rows[-1]
    if not (5000 <= last_v <= 20000):
        return '失败', f'最新值量级异常: {last_v}（未写库）'
    for d, v in rows:
        ym = d[:7]  # 月度数据日期=当月期末
        common.save_row(CSV, common.parse_date_label(ym), {
            '数值': v,
            '单位': '百万美元',
            '数据来源': 'FRED (St. Louis Fed) RSEAS',
            '备注': note,
        }, COLUMNS)
    detail = f'回填{len(rows)}个月，最新{last_d[:7]}={last_v:g}百万美元（{how}）'
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))