# -*- coding: utf-8 -*-
"""P05 宏观数据-中国CPI同比：主通道=国家统计局dg接口（官方一手，akshare macro_china_nbs_nation封装，
2026-11-05切换：NBS同比指数-100=台账同比%，与东财历史逐月一致）；备用=东财数据中心RPT_ECONOMY_CPI全历史。
NBS通道只补缺失/勘误月份（同值不覆写来源）；wind风控间歇性拦截时自动降级东财。
统计局最新发布页新闻稿标题交叉核验保留（best-effort）。"""
import os
import re
import time
import html as htmllib
import json

import common

PID = '05'
TITLE = '中国CPI同比'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P05-中国CPI同比.csv')
COLUMNS = ['数据日期', '同比%', '环比%', '单位', '数据来源', '备注']
API = ('https://datacenter-web.eastmoney.com/api/data/v1/get'
       '?reportName=RPT_ECONOMY_CPI&columns=ALL&pageSize=300'
       '&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB')
LIST_URL = 'https://www.stats.gov.cn/sj/zxfb/'
MIN_MONTHS = 24
# dg接口路径（月度树"价格指数"子树；分段名随统计五年段轮换，动态尝试）
NBS_LEAF_YOY = '价格指数 > 居民消费价格分类指数 (上年同月=100) > 全国居民消费价格分类指数 (上年同月=100) {seg}'
NBS_LEAF_MOM = '价格指数 > 居民消费价格分类指数 (上月=100) > 全国居民消费价格分类指数 (上月=100) {seg}'
NBS_ROW = '居民消费价格指数(上年同月=100)'


def _nbs_segments():
    y = int(common.TODAY[:4])
    return [f'({y}-)', f'({y - (y % 5) - 4}-{y - (y % 5)})']


def _nbs_series(path_tpl):
    """akshare统计局dg接口：返回{月份label: 同比/环比指数值}（指数-100=涨跌幅%）。
    总指数行=首行（NBS列表总指数在最前），按行名含'居民消费价格指数'且不含'类'定位。"""
    import akshare as ak  # 惰性导入：缺akshare时NBS通道跳过、降级东财
    last = None
    for seg in _nbs_segments():
        try:
            df = ak.macro_china_nbs_nation(kind='月度数据', path=path_tpl.format(seg=seg), period='LAST10')
        except Exception as e:  # noqa: BLE001
            last = e
            continue
        if len(df):
            series = df.set_index('指标') if '指标' in df.columns else df
            target = None
            for name in series.index:
                s = str(name)
                if '居民消费价格指数' in s and '类' not in s:
                    target = name
                    break
            if target is None:
                raise RuntimeError('NBS返回无总指数行')
            out = {}
            for colm in series.columns:
                v = series.loc[target, colm]
                if v is not None and str(v) != 'nan':
                    out[str(colm)] = float(v) - 100.0
            if out:
                return out
    raise RuntimeError(f'NBS dg获取失败: {str(last)[:80]}')


def _fetch_nbs():
    """NBS官方一手：同比（必取）+环比（best-effort）。返回{label: (同比%, 环比%或None)}。"""
    yoy = _nbs_series(NBS_LEAF_YOY)
    mom = {}
    try:
        mom = _nbs_series(NBS_LEAF_MOM)
    except Exception:  # noqa: BLE001
        pass
    out = {}
    for label, v in yoy.items():
        out[label] = (round(v, 2), round(mom[label], 2) if label in mom else None)
    return out


def _fetch_history():
    """备用：东财CPI全历史（2008-01起），返回[{REPORT_DATE,TIME,NATIONAL_SAME,NATIONAL_SEQUENTIAL...}]（新在前）。"""
    txt = common.http_get(API, referer='https://data.eastmoney.com/cjsj/cpi.html',
                          retries=3, timeout=30)
    d = json.loads(txt)
    if not d.get('success'):
        raise RuntimeError(f'东财接口返回失败: {d.get("message")}')
    rows = ((d.get('result') or {}).get('data')) or []
    rows = [r for r in rows
            if r.get('NATIONAL_SAME') is not None and re.match(r'^\d{4}-\d{2}', str(r.get('REPORT_DATE', ''))[:7])]
    if len(rows) < MIN_MONTHS:
        raise RuntimeError(f'东财CPI有效月份数不足: {len(rows)}')
    return rows


def _stats_latest():
    """统计局最新发布页最新一篇CPI新闻稿，返回(label, 同比值, 标题)；页面不可达/未找到返回None。
    列表按时间倒序，取第一处命中即最新。"""
    try:
        listing = htmllib.unescape(common.http_get(LIST_URL, encoding='utf-8', retries=1, timeout=20))
        m = re.search(r'href="(\./\d{6}/t\d+_\d+\.html)"[^>]*title=[\'"]([^\'"]*居民消费价格[^\'"]*)[\'"]', listing)
        if not m:
            return None
        title = m.group(2)
        mt = re.search(r'(\d{4})年(\d{1,2})月份', title)
        mv = re.search(r'同比(上涨|下降|持平)([\d.]+)?%', title)
        if not (mt and mv):
            return None
        val = 0.0 if mv.group(1) == '持平' else float(mv.group(2)) * (1 if mv.group(1) == '上涨' else -1)
        return f'{mt.group(1)}-{int(mt.group(2)):02d}', val, title
    except Exception:  # noqa: BLE001
        return None


def _load_ledger():
    existing = {}
    if os.path.exists(CSV_PATH):
        import csv as _csv
        with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
            for r in _csv.DictReader(f):
                existing[r['数据日期']] = r
    return existing


def run():
    try:
        # 主通道：统计局dg接口（一手），只补缺失/勘误月份
        try:
            nbs = _fetch_nbs()
            existing = _load_ledger()
            wrote = 0
            for label, (yoy, mom) in sorted(nbs.items()):
                date = common.parse_date_label(label)
                cur = existing.get(date)
                if cur is not None and cur.get('同比%', '').strip() == str(yoy):
                    continue  # 同值不覆写（保留原来源）
                values = {'同比%': yoy, '数据来源': '国家统计局dg接口(一手)',
                          '备注': f'{label}全国居民消费价格当月同比（同比指数{round(yoy + 100, 1)}-100）'}
                if mom is not None:
                    values['环比%'] = mom
                common.save_row(CSV_PATH, date, values, COLUMNS)
                wrote += 1
            detail = f'NBS一手通道: 最新{max(nbs)} 同比={nbs[max(nbs)][0]}%' \
                     f' 环比={nbs[max(nbs)][1]}%，新增/勘误{wrote}行'
            # 官方新闻稿标题核验保留（best-effort）
            time.sleep(1)
            st = _stats_latest()
            if st and st[0] in nbs:
                ok = abs(nbs[st[0]][0] - st[1]) <= 0.15
                detail += f'；官方核验{"一致" if ok else "不一致!"}（{st[0]}稿同比{st[1]}%）'
            return '成功', detail
        except Exception as nbs_err:  # noqa: BLE001
            # 备用：东财全历史（原有逻辑）
            rows = _fetch_history()
            n = 0
            for r in rows:
                label = str(r['REPORT_DATE'])[:7]
                seq = r.get('NATIONAL_SEQUENTIAL')
                values = {'同比%': round(float(r['NATIONAL_SAME']), 2),
                          '数据来源': '东方财富数据中心RPT_ECONOMY_CPI',
                          '备注': f'{r.get("TIME", "")}全国居民消费价格当月同比/环比'}
                if seq is not None:
                    # 东财无环比时不带'环比%'键→save_row保留既有值（官方稿/一手回填的环比不被清空，仿P06）
                    values['环比%'] = round(float(seq), 2)
                common.save_row(CSV_PATH, common.parse_date_label(label), values, COLUMNS)
                n += 1
            latest = rows[0]
            latest_label = str(latest['REPORT_DATE'])[:7]
            detail = (f'NBS不可达({str(nbs_err)[:60]})，东财备用: 回填{n}个月，'
                      f'最新{latest_label} 同比={latest["NATIONAL_SAME"]}%')
            return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))
