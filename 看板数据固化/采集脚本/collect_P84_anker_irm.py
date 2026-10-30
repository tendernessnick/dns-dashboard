# -*- coding: utf-8 -*-
"""P84 竞对同业-安克投资者关系问答：巨潮互动易IRM搜索接口POST统计安克创新投资者问答条数与最新提问日期"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PID = 84
TITLE = '安克投资者关系问答'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '竞对同业-P84-安克投资者关系问答.csv')
COLS = ['数据日期', '问答条数', '最新问答日期', '数据来源', '备注']
URL = 'https://irm.cninfo.com.cn/newircs/index/search'


def run():
    try:
        d = common.http_post(URL, data={
            'pageNo': '1', 'pageSize': '20',
            'searchTypes': '1,2,3,4,5,6', 'keyWord': '安克创新',
        }, referer='https://irm.cninfo.com.cn/', as_json=True)
        results = d.get('results') or []
        # contentType=1 为投资者提问，其余为公告等
        qa = [x for x in results if x.get('contentType') == 1]
        latest = max((x.get('packageDate', '') for x in qa), default='')
        if not qa:
            raise RuntimeError(f'无问答记录, totalRecord={d.get("totalRecord")}')
        if len(latest) < 10:
            raise RuntimeError(f'最新问答日期解析异常: {latest!r}')
        common.save_row(CSV, common.TODAY, {
            '问答条数': len(qa),
            '最新问答日期': latest[:10],
            '数据来源': '互动易 irm.cninfo.com.cn/newircs/index/search',
            '备注': f'首页返回问答(contentType=1){len(qa)}条, 检索总命中{d.get("totalRecord")}条(含公告)',
        }, COLS)
        detail = f'问答{len(qa)}条, 最新{latest[:10]}'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))