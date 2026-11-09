# -*- coding: utf-8 -*-
"""P93 竞对同业-Kickstarter：discover JSON接口抓科技类(sort=magic)热门Top12项目快照，
写 资讯数据/kickstarter.json(Top8资讯卡片)；并落盘项目图文（照片+blurb+_meta.json）→
图文数据/Kickstarter众筹/，供看板P93图文卡（70_review.js渲染，_crowd_common共用）"""
import os
import sys
import time
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import _news_common
import _crowd_common

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
# v18.3.1 消费电子聚焦：科技类目下仅这些子类算消费电子（Fabrication Tools/3D Printing/
# Robots/Software 等制造工具与纯软件不入图文卡；CSV快照不足8个消费电子时以泛科技补足并标注）
CE_CATS = {'Consumer Electronics', 'Hardware', 'Gadgets', 'Sound',
           'Camera Equipment', 'Wearables'}


TUWEN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         '图文数据', 'Kickstarter众筹')
IMPersonates = ('chrome', 'chrome131', 'safari17_0')   # CF盾指纹轮换(2026-11-05验证safari17_0过盾)


def kick_get(url):
    """Kickstarter有Cloudflare：curl_cffi按指纹序列尝试(解析出JSON即成功)；无curl_cffi时降级requests。"""
    try:
        import json as _json
        from curl_cffi import requests as cr
        last = '无响应'
        for imp in IMPersonates:
            try:
                r = cr.get(url, impersonate=imp, timeout=40, headers={
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Referer': 'https://www.kickstarter.com/discover/categories/technology',
                })
                last = f'{imp} HTTP {r.status_code}'
                if r.status_code != 200:
                    continue
                _json.loads(r.text)               # 盾页是HTML，解析失败换下一指纹
                return r.text
            except ValueError:
                last = f'{imp} 返回非JSON(Cloudflare盾页)'
        raise RuntimeError(f'curl_cffi全指纹失败(可能被Cloudflare拦截): {last}')
    except ImportError:
        r = common.http_get(url, referer='https://www.kickstarter.com/discover/categories/technology')
        return r


def _ks_download(url, fp):
    """Kickstarter图片下载(curl_cffi chrome指纹，i.kickstarter.com无盾)。"""
    try:
        from curl_cffi import requests as cr
        r = cr.get(url, impersonate='chrome', timeout=40,
                   headers={'Referer': 'https://www.kickstarter.com/'})
        if r.status_code == 200 and len(r.content) > 3000:
            tmp = fp + '.part'
            with open(tmp, 'wb') as f:
                f.write(r.content)
            os.replace(tmp, fp)   # v18.8：原子写——进程被超时kill不再留半张损坏图
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


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
    common.write_csv_atomic(csv_path, COLS, kept)


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
        # v18.3.1 消费电子优先排序：CE子类在前（原magic序），泛科技垫底仅在CSV补足
        ce = [p for p in live
              if str((p.get('category') or {}).get('name', '')) in CE_CATS]
        others = [p for p in live if p not in ce]
        picked = (ce + others)[:TOPN]
        if len(ce) < 4:
            raise RuntimeError(f'消费电子子类项目不足4个: {len(ce)}')
        now = time.time()
        now_local = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8)))
        rows, news = [], []
        for rank, p in enumerate(picked, 1):
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
            if p in others:                      # CSV快照里的泛科技补足项
                note = (note + ' · 泛科技').strip(' ·')
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
        # —— v18.3 图文落盘：项目照片+blurb+chips(接口数值照录) → 图文数据/Kickstarter众筹/
        #    v18.3.1 起仅落消费电子子类（CE_CATS），Fabrication Tools/纯软件等不入图文卡
        n_new, n_ref, n_noimg = 0, 0, 0
        for p in ce[:TOPN]:
            usd2 = int(round(float(p.get('usd_pledged')
                                    or p.get('converted_pledged_amount') or 0)))
            url2 = (p.get('urls') or {}).get('web', {}).get('project', '')
            if not url2:
                continue
            pct2 = round(float(p['percent_funded']), 1)
            backers2 = int(p.get('backers_count') or 0)
            days2 = max(0.0, round((float(p.get('deadline', now)) - now) / 86400, 1))
            chips = [f'已筹${usd2:,}', f'达成{pct2:.0f}%', f'支持{backers2}人',
                     '已结束' if days2 <= 0 else f'剩{days2:.0f}天']
            photo = p.get('photo') or {}
            img = photo.get('1024x576') or photo.get('med') or photo.get('full') or ''
            st, _ = _crowd_common.upsert_project(
                TUWEN_DIR, url2, str(p.get('name', ''))[:80],
                str((p.get('category') or {}).get('name', '')), chips, usd2,
                summary=str(p.get('blurb', ''))[:160],
                img_urls=(img,) if img else (), download=_ks_download)
            if st == '新':
                n_new += 1
                time.sleep(1)                     # 约定: 同站点请求间隔
            elif st == '刷新':
                n_ref += 1
            else:
                n_noimg += 1
        detail = (f'Top{len(rows)}快照(消费电子{len(ce)}个优先), Top1 "{rows[0]["项目名"]}" '
                  f'已筹${rows[0]["已筹美元"]:,} 达成{rows[0]["达成率%"]}%'
                  f'({rows[0]["支持者数"]}人); JSON {n_news}条; '
                  f'图文 新增{n_new} 刷新{n_ref}'
                  + (f' 缺照片{n_noimg}' if n_noimg else ''))
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))