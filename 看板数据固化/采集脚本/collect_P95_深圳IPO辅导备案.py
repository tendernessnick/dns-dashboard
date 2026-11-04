# -*- coding: utf-8 -*-
"""P95 竞对同业-深圳证监局IPO辅导：深圳证监局辅导备案信息栏AJAX JSON接口(curl_cffi)统计公告数与最新公示标题"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PID = 95
TITLE = '深圳IPO辅导备案'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '竞对同业-P95-深圳IPO辅导备案.csv')
COLS = ['数据日期', '公告条数', '最新标题', '数据来源', '备注']
CHANNEL_ID = '26d8295b2d8a48eda999402266779130'  # 深圳局"辅导备案信息"栏目
URL = f'https://www.csrc.gov.cn/searchList/{CHANNEL_ID}'


def run():
    try:
        import time
        from curl_cffi import requests as cr
        params = {
            '_isAgg': 'false', '_isJson': 'true', '_pageSize': '18',
            '_template': 'index', '_rangeTimeGte': '', '_channelName': '', 'page': '1',
        }
        headers = {
            'Referer': f'https://www.csrc.gov.cn/shenzhen/c105618/common_list.shtml?channelid={CHANNEL_ID}',
            'X-Requested-With': 'XMLHttpRequest',
        }
        # 官网站时不稳定：多指纹多轮重试
        r, last_err = None, None
        for imp, wait in (('chrome', 5), ('chrome124', 5), ('chrome', 8), ('safari1841', 8), ('chrome', 10)):
            try:
                r = cr.get(URL, impersonate=imp, timeout=40, params=params, headers=headers)
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(wait)
        if r is None:
            raise RuntimeError(f'证监局接口连接失败(重试5次): {last_err}')
        if r.status_code != 200:
            raise RuntimeError(f'HTTP {r.status_code}')
        d = r.json()
        data = d.get('data') or {}
        total = data.get('total')
        results = data.get('results') or []
        if not total or not results:
            raise RuntimeError(f'接口无数据: total={total}')
        # 列表按发布时间倒序, 第1条即最新
        top = results[0]
        title = re.sub(r'\s+', '', str(top.get('title', '')))[:80]
        pub = str(top.get('publishedTimeStr', ''))[:10]
        if '辅导' not in title:
            raise RuntimeError(f'最新条目非辅导公示: {title[:50]}')
        common.save_row(CSV, common.TODAY, {
            '公告条数': total,
            '最新标题': title,
            '数据来源': '深圳证监局 辅导备案信息栏目AJAX接口 searchList',
            '备注': f'最新公告日期{pub}；栏目自2021-09后无新增, EcoFlow(正浩创新)辅导备案在列',
        }, COLS)
        detail = f'共{total}条, 最新"{title[:40]}"({pub})'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == "__main__":
    print(common.run_collector(globals()))