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

import common

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
    # v18.8：统一走common.http_get（trust_env=False防代理劫持+重试+超时元组），裸requests退役
    return common.http_get(url, referer=referer)


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
        if dt is not None and dt.tzinfo is None:
            # pubDate无时区时parsedate返回naive，与aware now相减会TypeError打死整次采集（v18.8）——按UTC补齐
            dt = dt.replace(tzinfo=datetime.timezone.utc)
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
    """英文标题→中文；中文原文/翻译失败返回''（看板回退英文）。缓存避免重复请求。
    v19通道修复（2026-11-10实抓核验）：Google gtx在当前网络不可达（P14/P15一直显示英文的根因），
    主通道换 MyMemory 免费API（免key、每日匿名额度足够标题量），gtx降为备用。"""
    if not title or _is_cjk(title):
        return ''
    if title in cache:
        return cache[title]
    zh = ''
    try:
        r = common._SESSION.get('https://api.mymemory.translated.net/get',
                                params={'q': title[:450], 'langpair': 'en|zh-CN'},
                                headers={'User-Agent': UA}, timeout=(6, 15))
        d = r.json()
        zh = str((d.get('responseData') or {}).get('translatedText') or '').strip()
        if not _is_cjk(zh):
            zh = ''
    except Exception:
        zh = ''
    if not zh:
        try:   # 备用：Google gtx（网络可达时优先质量更好）
            r = common._SESSION.get('https://translate.googleapis.com/translate_a/single',
                                    params={'client': 'gtx', 'sl': 'auto', 'tl': 'zh-CN', 'dt': 't',
                                            'q': title[:450]},
                                    headers={'User-Agent': UA}, timeout=(6, 15))
            arr = r.json()
            zh = ''.join(seg[0] for seg in (arr[0] or []) if seg and seg[0]).strip()
            if not _is_cjk(zh):
                zh = ''
        except Exception:
            zh = ''
    if zh:
        # v18.8：只缓存成功翻译——空值入缓存会让该标题永远不再重译
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


def extract_ctw_article(html, maincats=('拆解', '评测', '新闻', '方案', '专题')):
    """充电头网文章页结构化提取（v19从P90上收公共，P90拆解/P61资讯共用）：
    → (标题, 发布日期YYYY-MM-DD, 子分类tag, 段落列表, 内容图URL列表[≤6])
    分类只认 post-meta 块（全页扫会撞侧栏"城市"链接）；图片只留近400天图床图（更早是站方固定素材）。"""
    import html as _h
    import datetime as _dt

    def _cl(s):
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', _h.unescape(s or ''))).strip()

    t = re.search(r'class="post-title[^"]*">([^<]+)</h1>', html)
    title = _h.unescape(t.group(1)).strip() if t else ''
    dm = (re.search(r'text-xs text-muted"><div>(20\d\d-\d\d-\d\d)</div>', html)
          or re.search(r'(20\d\d-\d\d-\d\d)', html[:2500]))   # 兜底限定页头区，正文首个日期不冒充发布日
    date = dm.group(1) if dm else ''
    tag = ''
    mm = re.search(r'text-xs text-muted">(.*?)</div></div>', html, re.S)
    if mm:
        for c in re.findall(r'category/[a-z_0-9]+"[^>]*>([^<]{1,12})</a>', mm.group(1)):
            c = c.strip()
            if c and c not in maincats:
                tag = c
                break
    seg = re.search(r'class="content-wrapper[^"]*"(.*)', html, re.S)
    body = seg.group(1) if seg else html
    paras = [_cl(p) for p in re.findall(r'<p[^>]*>(.*?)</p>', body, re.S)]
    paras = [p for p in paras if len(p) > 4]
    for i, p in enumerate(paras):                     # 截掉文末版权/推广噪声
        if i > len(paras) * 0.5 and re.search(r'转载|版权声明|免责声明|广告', p):
            paras = paras[:i]
            break
    imgs = []
    floor = (_dt.date.today() - _dt.timedelta(days=400)).strftime('%Y/%m')
    for u in re.findall(r'<img[^>]+src="(https?://[^"]+/(?:uploads|images)/[^"]+)"', body):
        mu = re.search(r'/uploads/(\d{4}/\d{2})/', u)
        if mu and mu.group(1) < floor:
            continue
        if u not in imgs:
            imgs.append(u)
    return title, date, tag, paras, imgs[:6]


# ---------------- IT之家（文章页提取，v19图文卡用） ----------------
def fetch_ithome_article(url):
    """IT之家文章页 → (标题[剥站名后缀], 首图URL[''=无图], 段落列表[纯文本≥12字])。
    实测2026-11-10：文章页均有图（img.ithome.com），段落9~21段。"""
    html = common.http_get(url, referer='https://www.ithome.com/')
    t = re.search(r'<title>([^<]+)</title>', html)
    title = _clean(t.group(1)) if t else ''
    title = re.sub(r'\s*[-–—]\s*IT之家.*$', '', title).strip()
    img = ''
    m = re.search(r'<img[^>]+(?:data-original|src)="(https?://img\.ithome\.com[^"]+)"', html)
    if m:
        img = m.group(1)
    paras = []
    for p in re.findall(r'<p[^>]*>(.*?)</p>', html, re.S):
        p = _clean(p)
        if len(p) > 12 and p not in paras:
            paras.append(p)
    return title, img, paras


def chips_from_title(title, brands=()):
    """从标题机械提取chips（免AI）：价格（X元/X美元）+首个命中品牌。"""
    chips = []
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:元|美元|块钱)', title)
    if m:
        chips.append(re.sub(r'\s+', '', m.group(0)))
    for b in brands:
        if b.lower() in title.lower():
            chips.append(b)
            break
    return chips[:2]


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
