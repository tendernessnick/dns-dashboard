# -*- coding: utf-8 -*-
"""P11 宏观数据-德国IFO景气指数：主通道=东财数据中心RPT_ECONOMICVALUE_GER(EMG00179154)
2026-11-05切换（切换日与TE双源一致2026-10=90.2）；备用=ifo.de官网→TradingEconomics镜像页解析。
台账已有同值日期不覆写（保留原来源）。"""
import csv
import json
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
EM_API = ('https://datacenter-web.eastmoney.com/api/data/v1/get'
          '?reportName=RPT_ECONOMICVALUE_GER&columns=ALL'
          '&filter=(INDICATOR_ID%3D%22EMG00179154%22)'
          '&pageSize=30&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB')


def _fetch_em():
    """东财数据中心IFO：REPORT_DATE_CH如'2026年10月'，VALUE=现值（未来月份为null，跳过）。
    返回(label, 现值)。"""
    d = json.loads(common.http_get(EM_API, referer='https://data.eastmoney.com/cjsj/foreign_1_0.html',
                                   retries=2, timeout=30))
    if not d.get('success'):
        raise RuntimeError(f'东财接口返回失败: {d.get("message")}')
    for r in (d.get('result') or {}).get('data') or []:
        v = r.get('VALUE')
        if v is None:
            continue  # 已排期未发布
        return str(r.get('REPORT_DATE_CH', '')), float(v)
    raise RuntimeError('东财IFO无有效现值行')


def _fetch_te():
    """备用通道：ifo.de官网（JS反爬常拦）→TE镜像页句子解析。返回(数值, label, 来源)。"""
    val, label = None, ''
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
    return val, label, source


def run():
    try:
        try:
            label, val = _fetch_em()
            src = '东方财富数据中心(转Ifo)'
        except Exception as em_err:  # noqa: BLE001
            try:
                val, label, src = _fetch_te()
            except Exception as te_err:  # noqa: BLE001
                return '失败', f'东财与TE均失败: EM[{str(em_err)[:80]}] TE[{str(te_err)[:80]}]'
        date = common.parse_date_label(label)
        val_r = round(val, 1)
        existing = {}
        if os.path.exists(CSV_PATH):
            with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
                for r in csv.DictReader(f):
                    existing[r['数据日期']] = r.get('数值')
        if existing.get(date) == str(val_r):
            return '成功', f'{date} IFO={val_r}（台账已有同值，未覆写来源）'
        common.save_row(CSV_PATH, date, {
            '数值': str(val_r), '单位': '指数',
            '数据来源': src,
            '备注': f'{label}Ifo商业气候指数'}, COLUMNS)
        return '成功', f'{date} IFO={val_r}（{src}）'
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))
