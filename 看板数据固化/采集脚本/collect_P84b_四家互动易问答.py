# -*- coding: utf-8 -*-
"""P84b 竞对同业-互动易问答：巨潮互动易searchResult接口(GET)按公司(orgId_代码)拉最新问答(含公司回复优先)
各写 资讯数据/irm-{公司名}.json（奥海/佳禾/海能/绿联/安克，安克供P70/P84卡注入）
用法: python collect_P84b_四家互动易问答.py [奥海|佳禾|海能|绿联|002993...]"""
import datetime
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import _news_common
from _comps import COMPANIES

API = 'https://irm.cninfo.com.cn/newircs/search/searchResult'
SOURCE = '互动易 irm.cninfo.com.cn(newircs/search/searchResult)'
PID = '84b'
MEMBERS = ['奥海', '佳禾', '海能', '绿联', '安克']


def fetch_qa(comp):
    """返回[{pubDate(ms), mainContent, attachedContent, indexId}]，按(有回复, 提问日期)降序。"""
    start = '2015-01-01 00:00:00'
    end = common.TODAY + ' 23:59:59'
    from urllib.parse import urlencode
    qs = urlencode({'stockCodes': f'{comp["org"]}_{comp["code"]}', 'keywords': '',
                    'infoTypes': '1,11', 'startDate': start, 'endDate': end,
                    'pageNum': 1, 'pageSize': 50, 'onlyAttentionCompany': 2})
    d = json.loads(common.http_get(f'{API}?{qs}', referer='https://irm.cninfo.com.cn/ircs/search',
                                   extra_headers={'X-Requested-With': 'XMLHttpRequest'}))
    data = d.get('data') or {}
    rows = data.get('results') or []
    rows.sort(key=lambda x: (1 if x.get('attachedContent') else 0, x.get('pubDate') or 0), reverse=True)
    return rows


def clean(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def run_one(short):
    comp = COMPANIES[short]
    rows = fetch_qa(comp)
    answered = sum(1 for x in rows if x.get('attachedContent'))
    if not rows:
        raise RuntimeError(f'{short}互动易无问答记录')
    items = []
    for x in rows:
        ts = x.get('pubDate')
        if not ts:
            continue
        d = datetime.datetime.fromtimestamp(int(ts) / 1000,
                                            datetime.timezone(datetime.timedelta(hours=8)))
        q = clean(x.get('mainContent'))
        a = clean(x.get('attachedContent'))
        title = f'问：{q}／答：{a}' if a else f'问：{q}'
        items.append({'date': d.strftime('%m-%d'), 'title': title[:120],
                      'url': f'https://irm.cninfo.com.cn/ircs/question/questionDetail?questionId={x.get("indexId")}'})
        if len(items) >= 8:
            break
    if not items:
        raise RuntimeError(f'{short}问答均无有效日期')
    payload = {'updated': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
               'source': SOURCE.split(' ')[0], 'items': items}
    path = os.path.join(_news_common.NEWS_DIR, f'irm-{comp["name"]}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    detail = f'{comp["name"]} 问答{len(rows)}条(含回复{answered}) 存{len(items)}条 最新{items[0]["date"]}'
    return '成功', detail


def run(argv=None):
    argv = [a for a in (argv or sys.argv[1:]) if a]
    members = MEMBERS
    if argv:
        members = [m for m in MEMBERS if m in argv or COMPANIES[m]['code'] in argv]
        if not members:
            raise SystemExit(f'参数未匹配到公司: {argv}')
    ok, fails = [], []
    for m in members:
        try:
            _, detail = run_one(m)
            ok.append(detail)
        except Exception as e:  # noqa: BLE001
            fails.append(f'{m} {e}')
        time.sleep(1)
    if fails:
        return '失败', '; '.join(fails)
    return '成功', '; '.join(ok)


if __name__ == '__main__':
    print(common.run_collector(globals()))