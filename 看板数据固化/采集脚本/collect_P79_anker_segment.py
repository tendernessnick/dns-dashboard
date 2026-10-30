# -*- coding: utf-8 -*-
"""P79 竞对同业-安克分业务营收拆分：pymupdf解析安克创新2025年年报PDF，提取充电储能类收入/占比/毛利率（年度低频）"""
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
PDF = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   '看板数据固化', '源文件', '安克创新2025年报.pdf')
DATE = '2025-12-31'


def _text():
    import pymupdf
    doc = pymupdf.open(PDF)
    return '\n'.join(page.get_text() for page in doc)


def run():
    try:
        if not os.path.exists(PDF):
            raise RuntimeError(f'年报PDF不存在: {PDF}')
        text = _text()
        if '2025' not in text[:2000] or '年度报告' not in text[:2000]:
            raise RuntimeError('文件不是2025年年度报告，需更新脚本')
        # 营业收入构成-分产品行: 充电储能类 [收入] [占比%] [上年收入] [上年占比%] [同比%]
        m = re.search(r'充电储能类\s*([\d,]+\.\d{2})\s*([\d.]+)%\s*[\d,]+\.\d{2}\s*[\d.]+%\s*(-?[\d.]+)%', text)
        # 占10%以上产品表行: 充电储能类 [收入] [成本] [毛利率%] ...
        m2 = re.search(r'充电储能类\s*[\d,]+\.\d{2}\s*[\d,]+\.\d{2}\s*([\d.]+)%', text)
        if not m or not m2:
            raise RuntimeError('年报中未找到充电储能类收入/毛利率行，疑似版式变更')
        income_yuan = float(m.group(1).replace(',', ''))
        share = float(m.group(2))
        gross = float(m2.group(1))
        income_yi = round(income_yuan / 1e8, 2)
        if not (100 < income_yi < 500 and 30 < share < 70 and 20 < gross < 60):
            raise RuntimeError(f'数值超出合理量级: 收入{income_yi}亿, 占比{share}%, 毛利率{gross}%')
        common.save_row(CSV, DATE, {
            '充电储能收入(亿元)': income_yi,
            '营收占比%': share,
            '毛利率%': gross,
            '数据来源': '安克创新2025年年度报告PDF(第三节 管理层讨论与分析)',
            '备注': f'充电储能类年报口径, 收入同比{m.group(3)}%',
        }, COLS)
        detail = f'充电储能收入{income_yi}亿元, 占比{share}%, 毛利率{gross}%'
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))