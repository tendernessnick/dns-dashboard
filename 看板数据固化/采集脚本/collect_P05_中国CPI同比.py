# -*- coding: utf-8 -*-
"""P05 宏观数据-中国CPI同比：东方财富数据中心 RPT_ECONOMY_CPI 全历史回填（同比NATIONAL_SAME+环比NATIONAL_SEQUENTIAL）；
并以国家统计局最新发布页当月CPI新闻稿标题交叉核验（stats不可达时跳过核验不判失败）。"""
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


def _fetch_history():
    """东财CPI全历史（2008-01起），返回[{REPORT_DATE,TIME,NATIONAL_SAME,NATIONAL_SEQUENTIAL...}]（新在前）。"""
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


def run():
    try:
        rows = _fetch_history()
        n = 0
        for r in rows:
            label = str(r['REPORT_DATE'])[:7]
            seq = r.get('NATIONAL_SEQUENTIAL')
            common.save_row(CSV_PATH, common.parse_date_label(label), {
                '同比%': round(float(r['NATIONAL_SAME']), 2),
                '环比%': '' if seq is None else round(float(seq), 2),
                '数据来源': '东方财富数据中心RPT_ECONOMY_CPI',
                '备注': f'{r.get("TIME", "")}全国居民消费价格当月同比/环比'}, COLUMNS)
            n += 1
        latest = rows[0]
        latest_label = str(latest['REPORT_DATE'])[:7]
        # 官方交叉核验（best-effort，不判失败）
        time.sleep(1)
        st = _stats_latest()
        chk = ''
        if st:
            label, val, title = st
            em_val = float(latest['NATIONAL_SAME'])
            if label == latest_label:
                ok = abs(em_val - val) <= 0.15
                chk = (f';官方核验{"一致" if ok else "不一致!"}（统计局{label}同比{val}%）')
                if not ok:
                    chk += f' 东财={em_val}'
            else:
                chk = f';官方最新发布为{label}，东财最新为{latest_label}'
        else:
            chk = ';stats.gov.cn当轮不可达，未做官方核验'
        detail = (f'回填{n}个月（2008-01起），最新{latest_label} 同比={latest["NATIONAL_SAME"]}% '
                  f'环比={latest.get("NATIONAL_SEQUENTIAL")}%{chk}')
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))