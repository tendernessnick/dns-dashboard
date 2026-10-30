# -*- coding: utf-8 -*-
"""
资讯采集公共库：RSS拉取 → 近7天过滤 → 写JSON供生成看板.py注入
JSON格式：{"updated": ISO时间, "source": 名称, "items": [{"date":"MM-DD","title":..,"url":..}]}
"""
import json
import os
import re
import datetime
from email.utils import parsedate_to_datetime

import requests

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS_DIR = os.path.join(BASE, '资讯数据')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
DAYS = 7          # 只保留最近7天
MAX_ITEMS = 8


def _clean(s):
    import html as _h
    s = re.sub(r'<!\[CDATA\[|\]\]>', '', s or '')
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'\s+', ' ', _h.unescape(s)).strip()


def fetch_rss(url, referer=None):
    headers = {'User-Agent': UA}
    if referer:
        headers['Referer'] = referer
    r = requests.get(url, headers=headers, timeout=25)
    r.raise_for_status()
    return r.text


def parse_items(xml, keywords=None, exclude=None):
    """解析RSS的<item>，返回[(datetime_utc, title, url)]，已按keywords/exclude过滤。"""
    out = []
    for m in re.finditer(r'<item>(.*?)</item>', xml, re.S):
        blk = m.group(1)
        tm = re.search(r'<title>(.*?)</title>', blk, re.S)
        lm = re.search(r'<link>\s*(.*?)\s*</link>', blk, re.S)
        dm = re.search(r'<pubDate>(.*?)</pubDate>', blk, re.S)
        if not tm or not lm:
            continue
        title = _clean(tm.group(1))
        url = _clean(lm.group(1))
        if not title or not url.startswith('http'):
            continue
        if keywords and not any(k.lower() in title.lower() for k in keywords):
            continue
        if exclude and any(k.lower() in title.lower() for k in exclude):
            continue
        dt = None
        if dm:
            try:
                dt = parsedate_to_datetime(_clean(dm.group(1)))
            except Exception:
                dt = None
        out.append((dt, title, url))
    return out


def save_news(filename, source, items):
    """items: [(dt|None,title,url)] → 过滤7天 → 翻译英文标题 → 写JSON。返回保留条数。
    翻译：Google gtx免费接口（sl=auto→zh-CN），结果缓存到 资讯数据/翻译缓存.json；
    失败或已是中文时 title_zh 留空，看板回退显示英文原题。"""
    now = datetime.datetime.now(datetime.timezone.utc)
    kept = []
    for dt, title, url in items:
        if dt is None:
            continue                      # 无法判日期的一律丢弃，保证"近7天"口径
        if (now - dt).total_seconds() > DAYS * 86400 or dt > now + datetime.timedelta(hours=2):
            continue
        local = dt.astimezone(datetime.timezone(datetime.timedelta(hours=8)))
        kept.append((local, title, url))
    kept.sort(key=lambda x: x[0], reverse=True)
    kept = kept[:MAX_ITEMS]
    cache = _load_tcache()
    os.makedirs(NEWS_DIR, exist_ok=True)
    data = {'updated': now.isoformat(timespec='seconds'), 'source': source,
            'items': [{'date': d.strftime('%m-%d'), 'title': t, 'title_zh': translate_title(t, cache),
                       'url': u}
                      for d, t, u in kept]}
    with open(os.path.join(NEWS_DIR, filename), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    _save_tcache(cache)
    return len(kept)


# ---------------- 英文标题翻译（v11：看板展示中文，悬停见英文原题） ----------------
_TCACHE_FILE = os.path.join(NEWS_DIR, '翻译缓存.json')


def _load_tcache():
    try:
        with open(_TCACHE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_tcache(cache):
    try:
        with open(_TCACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass


def _is_cjk(s):
    return len(re.findall(r'[\u4e00-\u9fff]', s or '')) * 2 > len(s or '')


def translate_title(title, cache):
    """英文标题→中文；中文原文/翻译失败返回''（看板回退英文）。缓存避免重复请求。"""
    if not title or _is_cjk(title):
        return ''
    if title in cache:
        return cache[title]
    zh = ''
    try:
        r = requests.get('https://translate.googleapis.com/translate_a/single',
                         params={'client': 'gtx', 'sl': 'auto', 'tl': 'zh-CN', 'dt': 't',
                                 'q': title[:450]},
                         headers={'User-Agent': UA}, timeout=15)
        arr = r.json()
        zh = ''.join(seg[0] for seg in (arr[0] or []) if seg and seg[0]).strip()
        if not _is_cjk(zh):
            zh = ''
    except Exception:
        zh = ''
    cache[title] = zh
    return zh


# ---------------- 充电头网（自定义CMS，curl_cffi过JS验证） ----------------
def fetch_ctw(path='/'):
    """抓充电头网页面（需curl_cffi伪装浏览器），返回文本。path如 '/'、'/archives/category/news'。"""
    from curl_cffi import requests as cr
    r = cr.get('https://www.chongdiantou.com' + path, impersonate='chrome', timeout=25)
    if r.status_code != 200:
        raise RuntimeError(f'HTTP {r.status_code}')
    return r.text


def parse_ctw(html):
    """解析列表页文章块 → [(datetime, title, url)]，按日期降序去重。"""
    import datetime
    out, seen = [], set()
    for chunk in html.split('list-item block')[1:]:
        tm = re.search(r'href="(https://www\.chongdiantou\.com/archives/\d+\.html)"[^>]*class="h-2x">([^<]{4,80})<', chunk)
        dm = re.search(r'(20\d\d-\d\d-\d\d)', chunk)
        if not tm or not dm:
            continue
        url, title = tm.group(1), _clean(tm.group(2))
        if url in seen:
            continue
        seen.add(url)
        out.append((datetime.datetime.strptime(dm.group(1), '%Y-%m-%d').replace(
            tzinfo=datetime.timezone(datetime.timedelta(hours=8))), title, url))
    out.sort(key=lambda x: x[0], reverse=True)
    return out
