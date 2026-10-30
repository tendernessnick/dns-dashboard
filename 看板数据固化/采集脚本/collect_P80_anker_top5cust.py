# -*- coding: utf-8 -*-
"""P80 竞对同业-安克大客户集中度：pymupdf解析安克创新2025年年报PDF，提取前五名客户合计销售金额与占比（年度低频）"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PID = 80
TITLE = '安克大客户集中度'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '竞对同业-P80-安克大客户集中度.csv')
COLS = ['数据日期', '前五大客户占比%', '金额(亿元)', '单位', '数据来源', '备注']
PDF = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   '看板数据固化', '源文件', '安克创新2025年报.pdf')
DATE = '2025-12-31'


def run():
    try:
        if not os.path.exists(PDF):
            raise RuntimeError(f'年报PDF不存在: {PDF}')
        import pymupdf
        doc = pymupdf.open(PDF)
        text = '\n'.join(page.get_text() for page in doc)
        m = re.search(r'前五名客户合计销售金额（元）\s*([\d,]+\.\d{2})', text)
        m2 = re.search(r'前五名客户合计销售金额占年度销售总额比例\s*([\d.]+)%', text)
        if not m or not m2:
            raise RuntimeError('年报中未找到前五名客户合计行，疑似版式变更')
        amount_yi = round(float(m.group(1).replace(',', '')) / 1e8, 2)
        share = float(m2.group(1))
        if not (5 < amount_yi < 100 and 1 < share < 30):
            raise RuntimeError(f'数值超出合理量级: 金额{amount_yi}亿, 占比{share}%')
        common.save_row(CSV, DATE, {
            '前五大客户占比%': share,
            '金额(亿元)': amount_yi,
            '数据来源': '安克创新2025年年度报告PDF(前五名客户合计)',
            '备注': '前五名客户合计销售金额及占年度销售总额比例',
        }, COLS)
        detail = f'前五大客户占比{share}%, 金额{amount_yi}亿元'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))