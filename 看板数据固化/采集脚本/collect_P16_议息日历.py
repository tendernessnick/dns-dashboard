# -*- coding: utf-8 -*-
"""P16/P20 议息日历动态采集（v18.6，两词条共用本采集器，仿P201先例）：
美联储官网日历(fomccalendars)+决议表(openmarket)、ECB官网日历(mgcgc)+数据API(存款便利利率DFR)
→ 解析出 未来两次议息时间线 + 最近决议说明行，写 资讯数据/议息日历.json。
生成数据.py 注入 var CAL，渲染器 72_calendar.js 动态覆盖卡片时间线与说明；
模块JSON 16/20 的静态快照仅作无数据兜底（渲染器只在CAL有值时覆盖）。
全部内容为官网数据机械解析/照录，不编造；解析失败如实回报失败、旧JSON保留。
用法：python collect_P16_议息日历.py"""
import csv
import datetime
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PID, TITLE = 16, '议息日历（美联储+欧洲央行）'
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, '资讯数据', '议息日历.json')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
MONTHS = {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
          'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12}
TODAY = datetime.date.today()


def _get(url, **kw):
    try:
        from curl_cffi import requests as cr
    except ImportError:
        return common.http_get(url, referer='https://www.federalreserve.gov/')
    try:
        r = cr.get(url, impersonate='safari17_0', timeout=40,
                   headers={'User-Agent': UA, 'Accept-Language': 'en'})
        if r.status_code != 200:
            raise RuntimeError(f'HTTP {r.status_code}')
        return r.text
    except Exception:  # noqa: BLE001
        # v18.8：被拒/超时也降级requests直连（旧版仅ImportError才降级，白丢一条命）
        return common.http_get(url, referer='https://www.federalreserve.gov/')


# ---------- 美联储 ----------
def fed_meetings():
    """官网日历 → [(y, m, d1, d2, 带点阵图*)]按时间升序"""
    html = _get('https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm')
    parts = re.split(r'<a id="\d+">(\d{4}) FOMC Meetings</a>', html)
    out = []
    for i in range(1, len(parts), 2):
        y = int(parts[i])
        for mm, dd in re.findall(
                r'fomc-meeting__month[^>]*><strong>([A-Za-z]+)</strong>.*?'
                r'fomc-meeting__date[^>]*>([\d\- *]+)<', parts[i + 1], re.S):
            m = MONTHS.get(mm)
            if not m:
                continue
            star = '*' in dd
            dd = dd.strip().replace('*', '').strip()
            a, _, b = dd.partition('-')
            out.append((y, m, int(a), int(b or a), star))
    out.sort()
    return out


def fed_rate_rows():
    """openmarket决议表 → [(y, m, d, bp变动, 目标区间)]"""
    html = _get('https://www.federalreserve.gov/monetarypolicy/openmarket.htm')
    secs = re.split(r'<h4>(\d{4})</h4>', html)
    out = []
    for i in range(1, len(secs), 2):
        y = int(secs[i])
        for mo, inc, dsc, lv in re.findall(
                r'<td[^>]*>([A-Za-z]+ \d+)</td>\s*<td[^>]*>\s*(-?\d+)\s*</td>\s*'
                r'<td[^>]*>\s*(-?\d+)\s*</td>\s*<td[^>]*>\s*([\d.]+(?:\s*-\s*[\d.]+)?)\s*</td>', secs[i + 1]):
            mon, day = mo.split()
            # 官网列序经实抓核验(2026-11-08)：第2列=加息bp(Increase)、第3列=降息bp(Decrease)，
            # 净变动bp=加息-降息（v18.7修正：旧版取第2列当净变动，降息行会误报"上调0bp"）
            out.append((y, MONTHS[mon], int(day), int(inc) - int(dsc), lv))
    out.sort()
    return out


def fed_build():
    ms = fed_meetings()
    future = [x for x in ms if datetime.date(x[0], x[1], x[2]) >= TODAY]
    if len(future) < 2:
        raise RuntimeError(f'Fed未来会议不足2场: {len(future)}')
    past = [x for x in ms if datetime.date(x[0], x[1], x[2]) < TODAY]
    if not past:
        raise RuntimeError('Fed未解析到历史会议')

    def txt(x, k):
        y, m, d1, d2, star = x
        if k == 1 and y > future[0][0]:
            t = f'{y}年第一次议息'
        elif m == 12:
            t = f'{y}年内最后一次议息'
        else:
            t = f'{y}年{m}月议息'
        if star:
            t += '（附带更新经济预测与点阵图）'
        return t

    tl = []
    for k, x in enumerate(future[:2]):
        y, m, d1, d2, _ = x
        tl.append({'下一个': k == 0, '日期': f'{m:02d}-{d1:02d}/{d2:02d}', '文本': txt(x, k)})
    rows = fed_rate_rows()
    if not rows:
        raise RuntimeError('Fed决议表未解析到行')
    y, m, d, bp, lv = rows[-1]
    level = lv.replace(' ', '').replace('-', '%-') + '%'
    pm, pd1, pd2 = past[-1][1], past[-1][2], past[-1][3]
    if datetime.date(y, m, d) >= datetime.date(past[-1][0], pm, pd1):
        act = f'{m}月{d}日会议{"上调" if bp > 0 else "下调"}{abs(bp)}bp至 {level}'
    else:
        act = (f'{pm}月{pd1}-{pd2}日会议维持联邦基金目标区间 {level} 不变'
               f'（上次调整：{m}月{d}日{"上调" if bp > 0 else "下调"}{abs(bp)}bp）')
    desc = (f'最近决议：{act}。下一次：{tl[0]["日期"]}，{tl[0]["文本"]}。'
            '会议声明与纪要见官网链接；纪要通常于决议三周后公布。')
    return {'时间线': tl, '说明': desc}


# ---------- 欧洲央行 ----------
def ecb_meetings():
    """官网日历（只列未来会议）→ [(y, m1, d1, m2, d2, 有发布会)] 仅货币政策会议(Day1/Day2成对)。
    注意排除 non-monetary policy meeting（子串会误命中）。"""
    html = _get('https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html')
    pairs = re.findall(r'<dt>\s*(\d{2})/(\d{2})/(\d{4})\s*</dt>\s*<dd>(.*?)</dd>', html, re.S)
    out, pending = [], None
    for d, m, y, txt_ in pairs:
        t = re.sub(r'\s+', ' ', txt_).lower()
        if 'monetary policy meeting' not in t or 'non-monetary' in t:
            continue
        press = 'press conference' in t
        if 'day 1' in t:
            pending = (int(y), int(m), int(d))
        elif pending:                          # Day 2
            out.append((*pending, int(m), int(d), press))
            pending = None
    out.sort()
    return out


def ecb_rate():
    """数据API DFR.LEV → (最新利率, 次新利率, 最近变动生效日)"""
    u = ('https://data-api.ecb.europa.eu/service/data/FM/B.U2.EUR.4F.KR.DFR.LEV'
         '?lastNObservations=6&format=csvdata')
    txt = _get(u)
    rows = list(csv.DictReader(io.StringIO(txt)))
    lv = [float(r['OBS_VALUE']) for r in rows]
    eff = [r['TIME_PERIOD'] for r in rows]
    return lv[-1], lv[-2], eff[-1]


def ecb_build():
    ms = ecb_meetings()
    future = [x for x in ms if datetime.date(x[0], x[1], x[2]) >= TODAY]
    if len(future) < 2:
        raise RuntimeError(f'ECB未来会议不足2场: {len(future)}')

    def txt(x):
        y, m1, d1, m2, d2, press = x
        if m1 == 12:
            t = f'{y}年最后一次议息'
        elif m1 in (1, 2) and y > TODAY.year:
            t = f'{y}年第一次议息'
        else:
            t = f'{y}年{m1}月议息'
        tail = f'{d2}日新闻发布'
        if m1 in (3, 6, 9, 12):
            tail += '·含员工预测更新'
        return f'{t}（{tail}）'

    tl = []
    for k, x in enumerate(future[:2]):
        y, m1, d1, m2, d2, _ = x
        tl.append({'下一个': k == 0, '日期': f'{m1:02d}-{d1:02d}/{d2:02d}', '文本': txt(x)})
    cur, prev, eff = ecb_rate()
    ey, em, ed = (int(x) for x in eff.split('-'))
    diff = round((cur - prev) * 100)
    sign = '上调' if diff > 0 else '下调'
    if datetime.date(ey, em, ed) > TODAY:
        act = f'最近一次会议决定{sign}{abs(diff)}bp，存款便利利率将于{em}月{ed}日生效调整为 {cur:.2f}%'
    else:
        # 决定即公布并录入变动表：无更晚生效行 ⇒ 其后的议息会议均未再调整
        act = (f'存款便利利率现为 {cur:.2f}%（最近一次调整为{em}月{ed}日生效，{sign}{abs(diff)}bp），'
               f'其后的议息会议未再调整利率')
    desc = (f'最近决议：{act}。决议于会议第二日14:15 CET新闻稿发布、拉加德记者会解读。'
            f'下一次：{tl[0]["日期"]}，{tl[0]["文本"]}。')
    return {'时间线': tl, '说明': desc}


def run():
    p16, p20 = fed_build(), ecb_build()
    data = {'updated': TODAY.isoformat(), 'P16': p16, 'P20': p20}
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    return '成功', (f"P16时间线[{';'.join(x['日期'] for x in p16['时间线'])}]"
                  f" P20时间线[{';'.join(x['日期'] for x in p20['时间线'])}] 说明行各1条 已写议息日历.json")


if __name__ == '__main__':
    print(common.run_collector(globals()))
