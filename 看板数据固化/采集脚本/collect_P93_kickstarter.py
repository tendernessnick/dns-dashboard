# -*- coding: utf-8 -*-
"""P93 竞对同业-Kickstarter：discover JSON接口(curl_cffi过CF)抓科技类(sort=magic)热门Top12项目快照，
并写 资讯数据/kickstarter.json(Top8资讯卡片)"""
import os
import sys
import time
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import _news_common

PID = 93
TITLE = 'Kickstarter科技热门'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '竞对同业-P93-Kickstarter科技热门.csv')
COLS = ['数据日期', '排名', '项目名', '已筹美元', '达成率%', '支持者数', '剩余天数',
        'URL', '数据来源', '备注']
URL = ('https://www.kickstarter.com/discover/advanced'
       '?category_id=16&sort=magic&page=1&format=json')
SOURCE = 'Kickstarter discover接口(科技类, sort=magic)'
TOPN = 12          # 快照保留条数(任务要求8-12)
NEWS_N = 8         # kickstarter.json条数
# 充电/电子配件类关键词(项目名/简介/子类目匹配即在备注标注)
ACC_KW = ['charg', 'power bank', 'battery', 'cable', 'usb',
          'dock', 'stand', 'holder', 'mount', 'magsafe', 'wireless',
          'keychain', 'screwdriv', 'keyboard', 'mouse', 'earbud', 'speaker',
          'display', 'monitor', 'adapter', 'hub', 'edc']


def kick_get(url):
    """Kickstarter有Cloudflare：优先curl_cffi模拟chrome；无curl_cffi时降级requests。"""
    try:
        from curl_cffi import requests as cr
        r = cr.get(url, impersonate='chrome', timeout=40, headers={
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.kickstarter.com/discover/categories/technology',
        })
        if r.status_code != 200:
            raise RuntimeError(f'curl_cffi HTTP {r.status_code}(可能被Cloudflare拦截)')
        return r.text
    except ImportError:
        r = common.http_get(url, referer='https://www.kickstarter.com/discover/categories/technology')
        return r


def _drop_stale_ranks(csv_path, keep_ranks):
    """同日重跑且榜单变短时，清掉当天不在当前排名里的残留行。"""
    import csv as _csv
    if not os.path.exists(csv_path):
        return
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        rows = list(_csv.DictReader(f))
    kept = [r for r in rows
            if r.get('数据日期') != common.TODAY
            or int(r.get('排名') or 0) in keep_ranks]
    if len(kept) == len(rows):
        return
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = _csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(kept)


def acc_note(p):
    """判断是否充电/电子配件类项目，返回备注前缀。"""
    text = ' '.join([str(p.get('name', '')), str(p.get('blurb', '')),
                     str((p.get('category') or {}).get('name', ''))]).lower()
    if any(k in text for k in ACC_KW):
        return '充电/电子配件相关'
    return ''


def run():
    try:
        import json
        d = json.loads(kick_get(URL))
        projects = d.get('projects') or []
        live = [p for p in projects if p.get('state') == 'live']
        if len(live) < 8:
            raise RuntimeError(f'live项目不足8个: {len(live)}')
        now = time.time()
        now_local = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8)))
        rows, news = [], []
        for rank, p in enumerate(live[:TOPN], 1):
            pct = round(float(p['percent_funded']), 1)
            usd = int(round(float(p.get('usd_pledged')
                                or p.get('converted_pledged_amount') or 0)))
            backers = int(p.get('backers_count') or 0)
            days = max(0.0, round((float(p.get('deadline', now)) - now) / 86400, 1))
            name = str(p.get('name', ''))[:80]
            url = (p.get('urls') or {}).get('web', {}).get('project', '')
            if not name or not url or usd <= 0:
                raise RuntimeError(f'排名{rank}字段异常: {name} usd={usd}')
            cat = (p.get('category') or {}).get('name', '')
            note = ' · '.join(x for x in [cat, acc_note(p)] if x)
            rows.append({'排名': rank, '项目名': name, '已筹美元': usd,
                         '达成率%': pct, '支持者数': backers, '剩余天数': days,
                         'URL': url, '数据来源': SOURCE, '备注': note})
            news.append((now_local, f'{name} · 已筹${usd:,} · 达成{pct:.0f}%', url))
        for r in rows:  # 日期+排名联合主键upsert，逐行落库
            common.save_row(CSV, common.TODAY, r, COLS,
                            key_cols=['数据日期', '排名'])
        _drop_stale_ranks(CSV, [r['排名'] for r in rows])
        n_news = _news_common.save_news('kickstarter.json',
                                        'Kickstarter科技类热门(sort=magic)', news)
        detail = (f'Top{len(rows)}快照, Top1 "{rows[0]["项目名"]}" '
                  f'已筹${rows[0]["已筹美元"]:,} 达成{rows[0]["达成率%"]}%'
                  f'({rows[0]["支持者数"]}人); JSON {n_news}条')
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))