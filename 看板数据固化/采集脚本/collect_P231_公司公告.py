# -*- coding: utf-8 -*-
"""P231-P234+P78/P81 公司公告：巨潮hisAnnouncement/query取公告快照(日期+序号联合主键)，orgId由topSearch实时解析
P231奥海 P232佳禾 P233海能 P234绿联 P78安克定期报告 P81安克募投；用法: python collect_P231_公司公告.py [P号|代码...]"""
import datetime
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from _comps import COMPANIES, select

QUERY = 'https://www.cninfo.com.cn/new/hisAnnouncement/query'
TOPSEARCH = 'https://www.cninfo.com.cn/new/information/topSearch/query'
SOURCE = '巨潮资讯网 hisAnnouncement/query'
JOBS = [(231, '奥海'), (232, '佳禾'), (233, '海能'), (234, '绿联'),
        (78, '安克'), (81, '安克')]
# 类型过滤：P78=定期报告卡（季报/年报），P81=募投产能卡
PRED = {
    78: lambda t: classify(t) in ('年报', '半年报', '季报'),
    81: lambda t: any(k in t for k in ('募集', '募投', '产能', '扩产', '可转换')),
}


def resolve_org(name, fallback):
    """巨潮topSearch按公司名解析orgId，失败用参数表兜底。"""
    try:
        d = common.http_post(TOPSEARCH, data={'keyWord': name, 'maxNum': '10'},
                             referer='http://www.cninfo.com.cn/new/fulltextSearch', as_json=True)
        for x in d:
            if isinstance(x, dict) and x.get('zwjc') == name and x.get('code'):
                return x['code'], x['orgId']
    except Exception:  # noqa: BLE001
        pass
    return None, fallback


def classify(title):
    """公告首分类：年报/半年报/季报/募集/回购/股东会/董监事会/其他。"""
    t = title
    if '年度报告' in t:
        return '年报'
    if '半年度报告' in t or '中报' in t:
        return '半年报'
    if '季度报告' in t:
        return '季报'
    if any(k in t for k in ('募集', '招股', '上市公告书', '向不特定合格投资者', '发行股票', '发行H股', '可转换公司债券')):
        return '募集'
    if '回购' in t:
        return '回购'
    if '股东会' in t:
        return '股东会'
    if '董事会' in t or '监事会' in t:
        return '董监事会'
    return '其他'


def run_one(pid, short, pred=None):
    comp = COMPANIES[short]
    fname = '安克募投公告' if pid == 81 else f'{short}公告'
    csv = os.path.join(common.CSV_DIR, f'竞对同业-P{pid}-{fname}.csv')
    pred = pred if pred is not None else PRED.get(pid)
    cols = ['数据日期', '序号', '标题', '类型', '链接', '数据来源', '备注']
    code, org = resolve_org(comp['name'], comp['org'])
    code = code or comp['code']
    def _fetch(page):
        return common.http_post(QUERY, data={
            'pageNum': str(page), 'pageSize': '30', 'column': 'szse', 'tabName': 'fulltext',
            'plate': '', 'stock': f'{code},{org}', 'searchkey': '', 'secid': '',
            'category': '', 'trade': '', 'seDate': '', 'sortName': '', 'sortType': '',
            'isHLtitle': 'true',
        }, referer='http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search',
            as_json=True)
    d = _fetch(1)
    anns = d.get('announcements') or []
    if pred:  # 类型过滤需要更大样本：合并前两页
        anns = anns + (_fetch(2).get('announcements') or [])
    if not anns:
        raise RuntimeError(f'{short}公告0条')
    if pred:  # 类型过滤后取前10（不足3条视为异常）
        anns = [a for a in anns if pred(re.sub(r'<[^>]+>', '', a.get('announcementTitle', '')))]
        if len(anns) < 2:
            raise RuntimeError(f'{short}过滤后仅{len(anns)}条')  # 定期报告一年仅4次，2条属正常
    for i, a in enumerate(anns[:10], 1):
        date = datetime.datetime.fromtimestamp(a['announcementTime'] / 1000).strftime('%Y-%m-%d')
        title = re.sub(r'<[^>]+>', '', a.get('announcementTitle', '')).strip()
        pdf = 'https://static.cninfo.com.cn/' + str(a.get('adjunctUrl', '')).strip()
        if not title or len(pdf) < 30:
            raise RuntimeError(f'{short}第{i}条标题/附件异常: {title!r} {pdf!r}')
        common.save_row(csv, date, {
            '序号': i, '标题': title, '类型': classify(title), '链接': pdf,
            '数据来源': SOURCE, '备注': '',
        }, cols, key_cols=['数据日期', '序号'])
    latest = anns[0]
    latest_title = re.sub(r'<[^>]+>', '', latest.get('announcementTitle', ''))[:30]
    detail = f'最新{datetime.datetime.fromtimestamp(latest["announcementTime"]/1000).strftime("%Y-%m-%d")} {latest_title} (共{min(len(anns),10)}条)'
    return '成功', detail


def run(argv=None):
    ok, fails = [], []
    for pid, short in select(JOBS, argv):
        try:
            _, detail = run_one(pid, short)
            ok.append(f'P{pid} {detail}')
        except Exception as e:  # noqa: BLE001
            fails.append(f'P{pid} {e}')
        time.sleep(1)
    if fails:
        return '失败', '; '.join(fails)
    return '成功', '; '.join(ok)


if __name__ == '__main__':
    print(common.run_collector(globals()))