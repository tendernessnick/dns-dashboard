# -*- coding: utf-8 -*-
"""P11 宏观数据-德国IFO景气指数：ifo.de官网被JS反爬拦截，实测改用TradingEconomics镜像页
解析Ifo商业气候指数最新值。"""
import os
import re
import html as htmllib

import common

PID = '11'
TITLE = '德国IFO景气指数'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P11-德国IFO景气指数.csv')
COLUMNS = ['数据日期', '数值', '单位', '数据来源', '备注']
MONTHS = {m: i for i, m in enumerate(
    ['january', 'february', 'march', 'april', 'may', 'june', 'july',
     'august', 'september', 'october', 'november', 'december'], 1)}
IFO_URL = 'https://www.ifo.de/en/ifo-business-climate-index'
TE_URL = 'https://tradingeconomics.com/germany/business-confidence'


def run():
    try:
        val, label = None, ''
        # 首选ifo.de官网（实测返回"Client Challenge"JS反爬页则降级TE）
        try:
            t = common.http_get(IFO_URL, retries=1, timeout=25)
            if 'Client Challenge' not in t:
                text = htmllib.unescape(re.sub(r'<[^>]+>', ' ', t))
                m = re.search(r'Ifo Business Climate Index[^.]{0,120}?'
                              r'(?:rose|fell|edged|climbed|slipped|increased|declined|dipped)'
                              r'[^0-9]{0,30}([\d.]+)\s+in\s+([A-Za-z]+)\s+(\d{4})', text)
                if m:
                    val = float(m.group(1))
                    mon = MONTHS.get(m.group(2).lower())
                    label = f'{m.group(3)}-{mon:02d}' if mon else ''
                    source = 'Ifo经济研究所'
        except Exception:  # noqa: BLE001
            pass
        if val is None:
            text = htmllib.unescape(re.sub(r'<[^>]+>', ' ', common.http_get(TE_URL, retries=3, timeout=30)))
            m = re.search(r'Ifo Business Climate Index[^.]{0,120}?'
                          r'(?:rose|fell|edged|climbed|slipped|increased|declined|dipped)'
                          r'[^0-9]{0,30}([\d.]+)\s+in\s+([A-Za-z]+)\s+(\d{4})', text)
            if not m:
                m2 = re.search(r'Business Confidence in Germany (?:increased|decreased|rose|fell)'
                               r' to ([\d.]+) points in ([A-Za-z]+)', text)
                if not m2:
                    raise RuntimeError('TE页面未解析到Ifo指数句式')
                mon = MONTHS.get(m2.group(2).lower())
                if not mon:
                    raise RuntimeError(f'月份解析失败: {m2.group(2)}')
                val, label = float(m2.group(1)), f'{common.TODAY[:4]}-{mon:02d}'
            else:
                mon = MONTHS.get(m.group(2).lower())
                if not mon:
                    raise RuntimeError(f'月份解析失败: {m.group(2)}')
                val, label = float(m.group(1)), f'{m.group(3)}-{mon:02d}'
            source = 'TradingEconomics(转Ifo，官网反爬)'
        date = common.parse_date_label(label)
        common.save_row(CSV_PATH, date, {
            '数值': str(round(val, 1)), '单位': '指数',
            '数据来源': source,
            '备注': f'{label}Ifo商业气候指数'}, COLUMNS)
        return '成功', f'{date} IFO={val}'
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))