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
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

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
NEWS_DAYS = 30
NEWS_FEEDS = {
    'P16': ('美联储官方货币政策资讯', 'https://www.federalreserve.gov/feeds/press_monetary.xml',
            'www.federalreserve.gov'),
    'P20': ('欧洲央行官方新闻', 'https://www.ecb.europa.eu/rss/press.html', 'www.ecb.europa.eu'),
}


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


def _news_relevant(pid, title, official=False):
    """按原题明确命中银行及货币政策；不从宏观报道或摘要推导关联。"""
    if re.search(r'non-monetary|in addition to decisions setting interest rates|非货币政策', title, re.I):
        return False
    bank = (r'\b(?:fed|fomc|federal reserve)\b|美联储|联邦公开市场' if pid == 'P16'
            else r'\b(?:ecb|european central bank)\b|欧洲央行')
    policy = r'\b(?:fomc|monetary policy|interest rates?|discount rate|rate (?:cut|hike|decision)s?)\b|货币政策|议息|利率|加息|降息|决议|纪要'
    return bool(re.search(policy, title, re.I) and (official or re.search(bank, title, re.I)))


def _date_iso(item):
    value = item.get('iso') or ''
    if value:
        return value[:10]
    md = item.get('date') or ''
    try:
        year = TODAY.year - (md > TODAY.strftime('%m-%d'))
        return datetime.date.fromisoformat(f'{year}-{md}').isoformat()
    except (TypeError, ValueError):
        return ''


def _recent(items):
    cutoff = (TODAY - datetime.timedelta(days=NEWS_DAYS)).isoformat()
    return [it for it in items if cutoff <= _date_iso(it) <= TODAY.isoformat()]


def parse_policy_feed(text, pid):
    """官方RSS原题/原文URL/发布日期，近30天、去重；不把来源入口当新闻。"""
    root_xml = ET.fromstring(text)
    nodes = root_xml.findall('.//item')
    if not nodes:
        raise RuntimeError('官方RSS未解析到item，保留上次资讯')
    source, _, expected_host = NEWS_FEEDS[pid]
    items, seen = [], set()
    for node in nodes:
        title = html.unescape(re.sub(r'\s+', ' ', node.findtext('title') or '')).strip()
        raw_url = html.unescape((node.findtext('link') or '').strip())
        url = urlsplit(raw_url)
        path = re.sub(r'/{2,}', '/', url.path)
        if (url.scheme != 'https' or url.netloc.lower() != expected_host
                or not path.startswith(('/newsevents/pressreleases/', '/press/'))
                or not path.endswith(('.htm', '.html')) or not title
                or not _news_relevant(pid, title, official=True)):
            continue
        try:
            published = parsedate_to_datetime(node.findtext('pubDate') or '').date().isoformat()
        except (TypeError, ValueError):
            continue
        link = urlunsplit((url.scheme, url.netloc, path, url.query, ''))
        if link in seen:
            continue
        seen.add(link)
        items.append({'date': published[5:], 'iso': published, 'title': title, 'title_zh': '',
                      'url': link, 'source': source})
    return sorted(_recent(items), key=lambda it: (it['iso'], it['url']), reverse=True)


def _fallback_news(pid):
    """仅复用现有财经新闻的精确相关标题，明确保留其二手来源身份。"""
    fp = os.path.join(BASE, '资讯数据', '财经新闻.json')
    try:
        with open(fp, encoding='utf-8') as f:
            feed = json.load(f)
    except (OSError, ValueError):
        return []
    items = []
    for it in _recent(feed.get('items') or []):
        link = urlsplit(it.get('url') or '')
        if (not _news_relevant(pid, ' '.join([it.get('title', ''), it.get('title_zh', '')]))
                or link.scheme not in ('http', 'https') or not link.netloc
                or not link.path.strip('/') or link.path.endswith('/')
                or re.search(r'/(?:index|home)(?:\.[^/]+)?$', link.path, re.I)):
            continue
        items.append({**it, 'iso': _date_iso(it), 'source': feed.get('source') or '已有财经资讯'})
    return sorted(items, key=lambda it: it['iso'], reverse=True)


def collect_news(pid, previous=None):
    source, feed_url, _ = NEWS_FEEDS[pid]
    info = {'来源': source, '来源URL': feed_url, '窗口天数': NEWS_DAYS,
            '抓取时间': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
    try:
        items = parse_policy_feed(_get(feed_url), pid)
        info['状态'] = '成功' if items else '静默'
        info['说明'] = '官方RSS原题与原文链接' if items else '官方RSS近30天无符合货币政策主题的条目'
    except Exception as e:  # noqa: BLE001
        items = _recent((previous or {}).get('相关新闻') or [])
        info['状态'], info['说明'] = '失败', str(e)[:200]
        # 缓存保留原抓取日期，避免把失败重试伪装为新内容。
        if items:
            info['沿用抓取时间'] = ((previous or {}).get('资讯采集') or {}).get('抓取时间', '')
    if not items:
        items = _fallback_news(pid)
        if items:
            info['说明'] += '；回退已有财经资讯的精确相关原题'
    # 只读项目现有翻译缓存；同URL、同原题继承已有译题，避免每日刷新覆盖人工校译。
    try:
        with open(os.path.join(BASE, '资讯数据', '翻译缓存.json'), encoding='utf-8') as f:
            title_cache = json.load(f)
    except (OSError, ValueError):
        title_cache = {}
    previous_titles = {(it.get('url'), it.get('title')): it.get('title_zh')
                       for it in (previous or {}).get('相关新闻') or [] if it.get('title_zh')}
    for it in items:
        zh = previous_titles.get((it.get('url'), it.get('title'))) or it.get('title_zh') or title_cache.get(it.get('title'))
        if zh:
            it['title_zh'] = zh
    info['条数'] = len(items)
    return {'相关新闻': items, '资讯采集': info}


def _existing():
    try:
        with open(OUT, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write(data):
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)


def refresh_news_only():
    """仅更新相关资讯，保留当前会议、决议及其他日历字段。"""
    data = _existing()
    for pid in NEWS_FEEDS:
        previous = data.get(pid) or {}
        data[pid] = {**previous, **collect_news(pid, previous)}
    _write(data)
    failed = [p for p in NEWS_FEEDS if data[p]['资讯采集']['状态'] == '失败']
    return ('失败' if failed else '成功'), '；'.join(
        f"{pid}资讯{len(data[pid]['相关新闻'])}条({data[pid]['资讯采集']['状态']})" for pid in NEWS_FEEDS)


def run():
    if '--news-only' in sys.argv:
        return refresh_news_only()
    data = _existing()
    p16, p20 = fed_build(), ecb_build()
    for pid, calendar in [('P16', p16), ('P20', p20)]:
        previous = data.get(pid) or {}
        data[pid] = {**previous, **calendar, **collect_news(pid, previous)}
    data['updated'] = TODAY.isoformat()
    _write(data)
    failed = [p for p in NEWS_FEEDS if data[p]['资讯采集']['状态'] == '失败']
    detail = (f"P16时间线[{';'.join(x['日期'] for x in p16['时间线'])}]"
              f" P20时间线[{';'.join(x['日期'] for x in p20['时间线'])}] 说明行各1条"
              f" 相关资讯P16={len(data['P16']['相关新闻'])}条/P20={len(data['P20']['相关新闻'])}条 已写议息日历.json")
    if failed:
        detail += '；日历已更新，官方资讯采集失败：' + '/'.join(failed)
    return ('失败' if failed else '成功'), detail


if __name__ == '__main__':
    print(common.run_collector(globals()))
