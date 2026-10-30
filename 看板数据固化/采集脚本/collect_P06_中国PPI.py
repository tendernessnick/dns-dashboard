# -*- coding: utf-8 -*-
"""P06 宏观数据-中国PPI同比：东方财富数据中心 RPT_ECONOMY_PPI 全历史回填（同比BASE_SAME；
注意实测该接口无环比字段，仅 BASE/BASE_SAME/BASE_ACCUMULATE）。
环比：best-effort 从国家统计局最新发布页可见的各月PPI新闻稿标题解析（标题自带"同比上涨X% 环比上涨Y%"，
能覆盖最近几个月并逐月积累），同时用官方值交叉核验东财同比；stats不可达时环比留空不判失败。"""
import os
import re
import time
import html as htmllib
import json

import common

PID = '06'
TITLE = '中国PPI同比'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P06-中国PPI同比.csv')
COLUMNS = ['数据日期', '同比%', '环比%', '单位', '数据来源', '备注']
API = ('https://datacenter-web.eastmoney.com/api/data/v1/get'
       '?reportName=RPT_ECONOMY_PPI&columns=ALL&pageSize=300'
       '&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB')
LIST_URL = 'https://www.stats.gov.cn/sj/zxfb/'
MIN_MONTHS = 24


def _fetch_history():
    """东财PPI全历史（2006-01起），返回[{REPORT_DATE,TIME,BASE,BASE_SAME...}]（新在前）。"""
    txt = common.http_get(API, referer='https://data.eastmoney.com/cjsj/ppi.html',
                          retries=3, timeout=30)
    d = json.loads(txt)
    if not d.get('success'):
        raise RuntimeError(f'东财接口返回失败: {d.get("message")}')
    rows = ((d.get('result') or {}).get('data')) or []
    rows = [r for r in rows
            if r.get('BASE_SAME') is not None and re.match(r'^\d{4}-\d{2}', str(r.get('REPORT_DATE', ''))[:7])]
    if len(rows) < MIN_MONTHS:
        raise RuntimeError(f'东财PPI有效月份数不足: {len(rows)}')
    return rows


def _dir_val(direction, num):
    if direction == '持平':
        return 0.0
    return float(num) * (1 if direction == '上涨' else -1)


def _stats_ppi_releases(max_pages=3):
    """统计局最新发布页（前max_pages页）能看到的PPI新闻稿，按新→旧返回[(label, 同比, 环比, 标题)]。
    用于交叉核验最新同比，并尽量多回填几个月的环比（新闻稿标题自带同比+环比）。"""
    out, seen = [], set()
    for page in range(max_pages):
        try:
            url = LIST_URL if page == 0 else f'{LIST_URL}index_{page}.html'
            listing = htmllib.unescape(common.http_get(url, encoding='utf-8', retries=1, timeout=20))
            for m in re.finditer(r'href="(\./\d{6}/t\d+_\d+\.html)"[^>]*title=[\'"]([^\'"]*工业生产者出厂价格[^\'"]*)[\'"]',
                                 listing):
                title = m.group(2)
                mt = re.search(r'(\d{4})年(\d{1,2})月份', title)
                ms = re.search(r'同比(上涨|下降|持平)([\d.]+)?%', title)
                mc = re.search(r'环比(上涨|下降|持平)([\d.]+)?%', title)
                if not (mt and ms):
                    continue
                label = f'{mt.group(1)}-{int(mt.group(2)):02d}'
                if label in seen:
                    continue
                seen.add(label)
                yoy = _dir_val(ms.group(1), ms.group(2) or 0)
                mom = _dir_val(mc.group(1), mc.group(2) or 0) if mc else None
                out.append((label, yoy, mom, title))
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    return out  # 列表新→旧，天然按期倒序


def run():
    try:
        rows = _fetch_history()
        n = 0
        labels = set()
        for r in rows:
            label = str(r['REPORT_DATE'])[:7]
            common.save_row(CSV_PATH, common.parse_date_label(label), {
                '同比%': round(float(r['BASE_SAME']), 2),
                # 注意：不带'环比%'键 → save_row保留已有行的环比（官方稿回填值不被清掉）
                '数据来源': '东方财富数据中心RPT_ECONOMY_PPI',
                '备注': f'{r.get("TIME", "")}工业生产者出厂价格当月同比(当月值指数{r.get("BASE", "")})'}, COLUMNS)
            labels.add(label)
            n += 1
        latest = rows[0]
        latest_label = str(latest['REPORT_DATE'])[:7]
        # 官方新闻稿：核验最新同比 + 回填环比（best-effort，逐月积累）
        time.sleep(1)
        rels = _stats_ppi_releases()
        chk = ''
        filled = 0
        if rels:
            label0, yoy0, _, title0 = rels[0]
            em_val = float(latest['BASE_SAME'])
            if label0 == latest_label:
                ok = abs(em_val - yoy0) <= 0.15
                chk = f';官方核验{"一致" if ok else "不一致!"}（统计局{label0}同比{yoy0}%）'
                if not ok:
                    chk += f' 东财={em_val}'
            else:
                chk = f';官方最新发布为{label0}，东财最新为{latest_label}'
            for label, yoy, mom, title in rels:
                if mom is not None and label in labels:
                    common.save_row(CSV_PATH, common.parse_date_label(label), {
                        '环比%': round(mom, 2),
                        '备注': f'{title}（环比取自国家统计局新闻稿标题）'}, COLUMNS)
                    filled += 1
            chk += f'；官方稿环比已回填{filled}行'
        else:
            chk = ';stats.gov.cn当轮不可达，未核验且环比未更新'
        detail = (f'回填{n}个月（2006-01起），最新{latest_label} 同比={latest["BASE_SAME"]}%{chk}')
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))