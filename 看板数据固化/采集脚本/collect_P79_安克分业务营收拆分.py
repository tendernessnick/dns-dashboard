# -*- coding: utf-8 -*-
"""P79 竞对同业-安克分业务营收和毛利率拆分：东财F10经营分析zygcfx年报期"充电储能类"行
（来源归一期M2迁移：原本地年报PDF正则解析→东财emweb API，与P221-224四家同源；
2025年报期三项数值抽样一致[154.02亿/50.47%/41.25%]。仅取年报期(12-31)行以保持原序列节奏，
中报数据zygcfx亦覆盖，如需半年度节奏可再扩展。）"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PID = 79
TITLE = '安克分业务营收拆分'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '竞对同业-P79-安克分业务营收拆分.csv')
COLS = ['数据日期', '充电储能收入(亿元)', '营收占比%', '毛利率%', '单位', '数据来源', '备注']
URL = 'https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax?code=SZ300866'
SOURCE = '东方财富F10 BusinessAnalysis(zygcfx) 分产品口径(300866)'


def run():
    try:
        d = json.loads(common.http_get(URL, referer='https://emweb.securities.eastmoney.com/'))
        items = [x for x in (d.get('zygcfx') or [])
                 if str(x.get('MAINOP_TYPE')) == '2'
                 and str(x.get('REPORT_DATE', ''))[:10].endswith('12-31')]  # 年报期，保持原序列节奏
        # 科目名历史变体：'充电储能类'/'充电储能类产品'，统一按前缀匹配，原始名记入备注
        rows = [x for x in items
                if re.sub(r'\s+', '', str(x.get('ITEM_NAME', ''))).startswith('充电储能')]
        if not rows:
            raise RuntimeError('zygcfx年报期未找到"充电储能*"行，疑似分类名变更')
        for x in rows:
            inc, share, gross = (x.get('MAIN_BUSINESS_INCOME'), x.get('MBI_RATIO'),
                                 x.get('GROSS_RPOFIT_RATIO'))
            if inc is None or share is None or gross is None:
                raise RuntimeError(f'{x["REPORT_DATE"][:10]} 字段缺失')
            inc_yi, share, gross = round(inc / 1e8, 2), round(share * 100, 2), round(gross * 100, 2)
            if not (10 < inc_yi < 500 and 20 < share < 80 and 10 < gross < 70):
                raise RuntimeError(f'数值超出合理量级: {inc_yi}亿/{share}%/{gross}%')
            common.save_row(CSV, str(x['REPORT_DATE'])[:10], {
                '充电储能收入(亿元)': inc_yi, '营收占比%': share, '毛利率%': gross,
                '单位': '%', '数据来源': SOURCE,
                '备注': f'年报口径(东财F10分产品)，科目名[{re.sub(chr(92)+"s+", "", str(x.get("ITEM_NAME", "")))}]',
            }, COLS)
        latest = max(rows, key=lambda x: str(x['REPORT_DATE']))
        detail = (f'{len(rows)}期年报; 最新{latest["REPORT_DATE"][:10]} '
                  f'充电储能收入{latest["MAIN_BUSINESS_INCOME"] / 1e8:.2f}亿, '
                  f'占比{latest["MBI_RATIO"] * 100:.2f}%, '
                  f'毛利率{latest["GROSS_RPOFIT_RATIO"] * 100:.2f}%')
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))
