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
    try:
        text, how = _fetch_fred()
    except Exception:  # noqa: BLE001
        try:
            text, how = _fetch_via_wayback()
        except Exception as e:  # noqa: BLE001
            return '失败', f'FRED直连与回源均失败: {e}'
    lines = text.strip().splitlines()
    rows = []
    for line in lines:
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
    rows = rows[-BACKFILL_MONTHS:]
    note = f'美国零售和食品服务销售额(季调,月度)；近{BACKFILL_MONTHS}个月回填'
    if how != '直连':
        note += f'；本机直连FRED超时，经{how}获取原CSV'
    for d, v in rows:
        ym = d[:7]  # 月度数据日期=当月期末
        common.save_row(CSV, common.parse_date_label(ym), {
            '数值': v,
            '单位': '百万美元',
            '数据来源': 'FRED (St. Louis Fed) RSEAS',
            '备注': note,
        }, COLUMNS)
    last_d, last_v = rows[-1]
    if not (5000 <= last_v <= 20000):
        return '失败', f'最新值量级异常: {last_v}'
    detail = f'回填{len(rows)}个月，最新{last_d[:7]}={last_v:g}百万美元（{how}）'
    return '成功', detail


if __name__ == '__main__':
    print(common.run_collector(globals()))