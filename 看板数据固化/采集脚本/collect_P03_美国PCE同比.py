# -*- coding: utf-8 -*-
"""P03 宏观数据-美国PCE同比：主通道=BEA官方API NIPA T20804（PCE价格指数月度，Line1总指数，
2026-11-10接入；同比由指数水平自算，切换日与页面口径一致）。备用=BEA官网页面文本解析（原逻辑）。
同值(±0.05pp)不覆写来源；key见_keys.py。"""
import csv
import json
import os
import re
import html as htmllib

import common

PID = '03'
TITLE = '美国PCE同比'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P03-美国PCE同比.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
MONTHS = {m: i for i, m in enumerate(
    ['january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'], 1)}
URL = 'https://www.bea.gov/data/personal-consumption-expenditures-price-index'
API_URL = ('https://apps.bea.gov/api/data/?UserID={key}&method=GetData&DataSetName=NIPA'
           '&TableName=T20804&LineNumber=1&Frequency=M&Year={years}&ResultFormat=json')


def _fetch_api():
    """BEA官方API：T20804 Line1 PCE总指数(2017=100)月度水平 → 自算同比。
    返回{YYYYMM: 同比%}。注意：LineNumber参数API不生效，客户端过滤。"""
    try:
        from _keys import BEA_API_KEY
    except ImportError:
        raise RuntimeError('_keys.py不存在')
    if not BEA_API_KEY:
        raise RuntimeError('BEA_API_KEY未配置')
    y = int(common.TODAY[:4])
    years = ','.join(str(v) for v in (y - 2, y - 1, y))
    d = json.loads(common.http_get(API_URL.format(key=BEA_API_KEY, years=years),
                                   retries=2, timeout=40))
    b = d.get('BEAAPI', {})
    if 'Error' in b:
        raise RuntimeError(f"BEA API错误: {str(b['Error'].get('APIErrorDescription'))[:60]}")
    series = {}
    for r in b['Results']['Data']:
        if str(r.get('LineNumber')) == '1':
            tp = str(r.get('TimePeriod'))  # 2026M09
            yy, mm = tp.split('M')
            series[f'{yy}{int(mm):02d}'] = r.get('DataValue')
    if len(series) < 13:
        raise RuntimeError(f'API指数期数不足: {len(series)}')
    out = {}
    for k in sorted(series):
        prev = f'{int(k[:4]) - 1}{k[4:]}'
        try:
            out[k] = round((float(series[k]) / float(series[prev]) - 1) * 100, 2)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue  # 回看窗口最早数月的去年同期不在取数窗口内
    return out


def _fetch_page():
    """备用：BEA官网页面句式解析（原逻辑）。返回(数值, label)。"""
    text = htmllib.unescape(re.sub(r'<[^>]+>', ' ', common.http_get(URL, retries=2, timeout=30)))
    text = re.sub(r'\s+', ' ', text)
    m = re.search(r'Change From Month One Year Ago\s+([A-Za-z]+)\s+(\d{4})\s+([-−–+]?[\d.]+)\s?%', text)
    if not m:
        raise RuntimeError('页面未解析到PCE同比句式')
    mon = MONTHS.get(m.group(1).lower())
    if not mon:
        raise RuntimeError(f'月份解析失败: {m.group(1)}')
    val = float(m.group(3).replace('−', '-').replace('–', '-'))
    return val, f'{m.group(2)}-{mon:02d}'


def _load_ledger():
    existing = {}
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                existing[r['数据日期']] = r
    return existing


def run():
    try:
        # 主通道：BEA官方API（一手结构化），补缺失月份；同值(±0.05pp)不覆写来源
        try:
            yoy = _fetch_api()
            existing = _load_ledger()
            wrote = 0
            for k in sorted(yoy):
                label = f'{k[:4]}-{k[4:]}'
                date = common.parse_date_label(label)
                cur = existing.get(date)
                if cur is not None and cur.get('数值', '').strip():
                    try:
                        if abs(float(cur['数值']) - yoy[k]) <= 0.05:
                            continue  # 同值(±0.05pp，API自算舍入容差)不覆写
                    except ValueError:
                        pass
                common.save_row(CSV_PATH, date, {
                    '数值': str(yoy[k]), '单位': '%',
                    '数据来源': 'BEA(美国经济分析局)',
                    '备注': f'{label}PCE价格指数当月同比（BEA官方API NIPA 2.8.4指数自算）'}, COLUMNS)
                wrote += 1
            latest = max(yoy)
            detail = (f'BEA API通道: 最新{latest[:4]}-{latest[4:]} PCE同比={yoy[latest]}%，'
                      f'新增/勘误{wrote}行')
            return '成功', detail
        except Exception as api_err:  # noqa: BLE001
            # 备用：BEA官网页面解析（原逻辑）
            val, label = _fetch_page()
            date = common.parse_date_label(label)
            common.save_row(CSV_PATH, date, {
                '数值': str(round(val, 2)), '单位': '%',
                '数据来源': 'BEA(美国经济分析局)',
                '备注': f'{label}PCE价格指数当月同比'}, COLUMNS)
            return '成功', f'API不可达({str(api_err)[:60]})，页面备用: {date} PCE同比={val}%'
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))
