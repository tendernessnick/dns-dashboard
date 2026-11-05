# -*- coding: utf-8 -*-
"""P94 竞对同业-摩点众筹：全站金额榜+科技类金额榜取项目ID，realtime/get_simple_product
JSONP批量接口取已筹/达成率/支持者，Top12快照，写 资讯数据/modian.json(Top8)；
并落盘项目图文（logo2照片+_meta.json[chips接口数值照录]）→ 图文数据/摩点众筹/，
供看板P94图文卡（70_review.js渲染，_crowd_common共用）"""
import json
import os
import re
import sys
import time
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import _news_common
import _crowd_common

PID = 94
TITLE = '摩点众筹热度'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '竞对同业-P94-摩点众筹热度.csv')
COLS = ['数据日期', '排名', '项目名', '已筹金额元', '达成率%', '支持人数', '剩余天数',
        'URL', '数据来源', '备注']
SOURCE = '摩点金额榜(/all/top_money/going)+get_simple_product接口'
TOPN = 12          # 快照保留条数(全站Top10+科技类补充)
NEWS_N = 8         # modian.json条数
LIST_ALL = 'https://zhongchou.modian.com/all/top_money/going'
LIST_TECH = 'https://zhongchou.modian.com/technology/top_money/going'
API = ('https://zhongchou.modian.com/realtime/get_simple_product'
       '?ids={ids}&if_all=1&jsonpcallback=cb')
TUWEN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         '图文数据', '摩点众筹')
# 3C配件相关关键词(项目名匹配即在备注标注)
ACC_KW = ['充电', '数据线', '线材', '支架', '磁吸', '键盘', '鼠标', '耳机', '音响',
          '音箱', '电源', '插线板', '蓝牙', '触控', '摄像头', '屏幕', '指纹',
          '充电宝', '数码', '桌面', 'hub', '扩展坞', '无线充']


def _md_download(url, fp):
    """摩点图片下载(moimg.net直链无反爬，requests直连)。"""
    import requests
    try:
        r = requests.get(url, headers={'User-Agent': common.UA,
                                       'Referer': 'https://zhongchou.modian.com/'}, timeout=40)
        if r.status_code == 200 and len(r.content) > 3000:
            with open(fp, 'wb') as f:
                f.write(r.content)
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def list_ids(url):
    """列表页HTML里的data-pro-id(按页面顺序去重)。"""
    html = common.http_get(url, referer='https://www.modian.com', encoding='utf-8')
    return list(dict.fromkeys(re.findall(r'data-pro-id="(\d+)"', html)))


def batch_detail(ids):
    """get_simple_product JSONP批量接口 → [项目dict]。"""
    time.sleep(1)  # 约定: 同站点请求间隔
    txt = common.http_get(API.format(ids=','.join(ids)),
                          referer='https://zhongchou.modian.com/', encoding='utf-8')
    i = txt.find('([')
    j = txt.rindex(']')
    if i < 0 or j < 0:
        raise RuntimeError('JSONP解析失败')
    return json.loads(txt[i + 1:j + 1])


def days_left(end_time):
    """end_time如'2026-11-15 23:59:00' → 剩余天数(>=0, 1位小数)；解析失败返回''。"""
    try:
        end = datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
        return max(0.0, round((end - datetime.datetime.now()).total_seconds() / 86400, 1))
    except Exception:  # noqa: BLE001
        return ''


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


def acc_note(name):
    if any(k in name.lower() for k in ACC_KW):
        return '3C配件相关'
    return ''


def run():
    try:
        ids_all = list_ids(LIST_ALL)
        ids_tech = list_ids(LIST_TECH)
        if len(ids_all) < 8:
            raise RuntimeError(f'全站金额榜ID不足8个: {len(ids_all)}')
        pool = {p['id']: p for p in batch_detail(list(dict.fromkeys(ids_all + ids_tech)))}
        live = [p for p in pool.values()
                if p.get('status') == '众筹中' and float(p.get('backer_money_rew') or 0) > 0]
        live.sort(key=lambda p: float(p['backer_money_rew']), reverse=True)
        # 排名口径: 全站金额Top10在前，11-12名优先科技类目(任务要求关注3C/科技)，不足再以全站补齐
        tech_ids = set(ids_tech)
        picked = [p for p in live if str(p['id']) not in tech_ids][:10]

        def _pick_tech():
            return sorted((p for p in live if str(p['id']) in tech_ids),
                          key=lambda p: float(p['backer_money_rew']), reverse=True)
        for p in _pick_tech():
            if len(picked) >= TOPN:
                break
            picked.append(p)
        for p in live:
            if len(picked) >= TOPN:
                break
            if p not in picked:
                picked.append(p)
        if len(picked) < 8:
            raise RuntimeError(f'有效项目不足8个: {len(picked)}')
        now_local = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8)))
        rows, news = [], []
        for rank, p in enumerate(picked, 1):
            amount = round(float(p['backer_money_rew']), 2)
            rate = round(float(p.get('rate') or 0), 2)
            backers = int(p.get('backer_count') or 0)
            name = str(p.get('name', ''))[:60]
            url = f"https://zhongchou.modian.com/item/{p['id']}.html"
            cat = str(p.get('category') or '')
            in_tech = str(p['id']) in tech_ids
            parts = [cat]
            if in_tech and cat != '科技':
                parts.append('科技类目')
            if acc_note(name):
                parts.append('3C配件相关')
            note = ' · '.join(x for x in parts if x)
            rows.append({'排名': rank, '项目名': name, '已筹金额元': amount,
                         '达成率%': rate, '支持人数': backers,
                         '剩余天数': days_left(p.get('end_time', '')),
                         'URL': url, '数据来源': SOURCE, '备注': note})
            news.append((now_local, f'{name} · 已筹¥{amount / 1e4:.1f}万 · 达成{rate:.0f}%',
                         url))
        for r in rows:  # 日期+排名联合主键upsert
            common.save_row(CSV, common.TODAY, r, COLS,
                            key_cols=['数据日期', '排名'])
        _drop_stale_ranks(CSV, [r['排名'] for r in rows])
        n_news = _news_common.save_news('modian.json', '摩点众筹热门(金额榜)',
                                        news[:NEWS_N])
        # —— v18.3 图文落盘：logo2照片+chips(接口数值照录) → 图文数据/摩点众筹/
        n_new, n_ref, n_noimg = 0, 0, 0
        for p in picked:
            url2 = f"https://zhongchou.modian.com/item/{p['id']}.html"
            amount2 = round(float(p['backer_money_rew']), 2)
            rate2 = round(float(p.get('rate') or 0), 2)
            backers2 = int(p.get('backer_count') or 0)
            days2 = days_left(p.get('end_time', ''))
            chips = [f'已筹¥{amount2 / 1e4:.1f}万', f'达成{rate2:.0f}%',
                     f'支持{backers2}人',
                     '已结束' if days2 == '' or days2 <= 0 else f'剩{days2:.0f}天']
            imgs = [str(p.get(k)) for k in ('logo2', 'wb_logo_1')
                    if str(p.get(k) or '').startswith('http')]
            st, _ = _crowd_common.upsert_project(
                TUWEN_DIR, url2, str(p.get('name', ''))[:60],
                str(p.get('category') or ''), chips, amount2,
                summary='', img_urls=tuple(imgs), download=_md_download)
            if st == '新':
                n_new += 1
                time.sleep(1)                     # 约定: 同站点请求间隔
            elif st == '刷新':
                n_ref += 1
            else:
                n_noimg += 1
        detail = (f'Top{len(rows)}快照, Top1 "{rows[0]["项目名"]}" '
                  f'已筹{rows[0]["已筹金额元"]:,.0f}元 达成{rows[0]["达成率%"]}%'
                  f'({rows[0]["支持人数"]}人); JSON {n_news}条; '
                  f'图文 新增{n_new} 刷新{n_ref}'
                  + (f' 缺照片{n_noimg}' if n_noimg else ''))
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))