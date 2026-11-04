# -*- coding: utf-8 -*-
"""P58 产品品类-存储芯片价格：TrendForce现货价页(DRAM/NAND Flash)解析
DDR4 8Gb、DDR4 16Gb、DDR5 16Gb 与 NAND 256Gb/512Gb TLC 的当日Session Average。
固定页可得性：/price/dram/dram_spot 与 /price/flash/flash_spot 即官方公开固定页（无RSS），
2026-10-27验证两页均含全部5个品类条目。"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

PID = 58
TITLE = '存储芯片价格'
BACKFILL = 'latest'
CSV = os.path.join(common.CSV_DIR, '产品品类-P58-存储芯片价格.csv')
COLS = ['数据日期', 'DDR4_8Gb均价USD', 'DDR4_16Gb均价USD', 'DDR5_16Gb均价USD',
        'NAND_256Gb均价USD', 'NAND_512Gb均价USD', '单位', '数据来源', '备注']
DRAM_URL = 'https://www.trendforce.com/price/dram/dram_spot'
NAND_URL = 'https://www.trendforce.com/price/flash/flash_spot'  # 旧路径/price/nand/nand_spot已404

# (CSV列名, 条目行正则, 量级下限, 上限)
ITEMS = [
    ('DDR4_8Gb均价USD', r'>DDR4 8Gb \(1Gx8\) 3200<', 5, 200),
    ('DDR4_16Gb均价USD', r'>DDR4 16Gb \(2Gx8\) 3200<', 10, 300),
    ('DDR5_16Gb均价USD', r'>DDR5 16Gb \(2Gx8\) 4800/5600<', 20, 200),
    ('NAND_256Gb均价USD', r'>256Gb TLC<', 3, 100),
    ('NAND_512Gb均价USD', r'>512Gb TLC<', 3, 150),
]


def _session_avg(html, item_pat):
    """在含item_pat的表格行(至</tr>为止)内取Session Average（percent-cell前最后一个lcd-num-l数值）。"""
    m = re.search(item_pat, html)
    if not m:
        raise RuntimeError(f'未找到条目 {item_pat}')
    end = html.find('</tr>', m.start())
    if end < 0:
        raise RuntimeError(f'条目 {item_pat} 行未闭合')
    seg = html[m.start():end]
    cells = re.findall(r'class="lcd-num-l">([\d.]+)</td>', seg)
    if not cells:
        raise RuntimeError(f'条目 {item_pat} 行内无数值单元格')
    return float(cells[-1])  # 列序: Daily High,Daily Low,Session High,Session Low,Session Average


def run():
    try:
        dram_html = common.http_get(DRAM_URL)
        time.sleep(1)
        nand_html = common.http_get(NAND_URL)
        vals = {}
        parts = []
        for col, pat, lo, hi in ITEMS:
            html = dram_html if col.startswith('DDR') else nand_html
            v = _session_avg(html, pat)
            if not (lo < v < hi):
                raise RuntimeError(f'{col} 数值超量级: {v}')
            vals[col] = v
            parts.append(f'{col}=${v}')
        common.save_row(CSV, common.TODAY, {
            **vals,
            '数据来源': 'TrendForce 现货价 dram_spot/flash_spot',
            '备注': '各项为TrendForce现货页当日Session Average：DDR4 8Gb(1Gx8)3200、DDR4 16Gb(2Gx8)3200、'
                    'DDR5 16Gb(2Gx8)4800/5600、NAND 256Gb TLC、512Gb TLC；NAND现价页路径为/price/flash/flash_spot',
        }, COLS)
        detail = ', '.join(parts)
        return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))