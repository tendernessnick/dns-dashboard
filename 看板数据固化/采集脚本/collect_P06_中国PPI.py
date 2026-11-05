# -*- coding: utf-8 -*-
"""P06 宏观数据-中国PPI同比：主通道=国家统计局dg接口（官方一手，akshare封装，2026-11-05切换：
NBS同比指数-100=台账同比%，与东财历史逐月一致）；备用=东财数据中心RPT_ECONOMY_PPI。
NBS通道只补缺失/勘误月份（同值不覆写来源）；dg风控间歇性拦截时自动降级东财。
东财备用路径保留统计局新闻稿标题环比回填与官方核验（best-effort）。"""
import os
import re
import time
import html as htmllib
import json

import common

PID = '06'
TITLE = '中国PPI同比'
BACKFILL = 'latest'
CSV_PATH = os.path.join(common.CSV_DIR, '宏观数据-P06-中国PPI同比.csv')
COLUMNS = ['数据日期', '同比%', '环比%', '单位', '数据来源', '备注']
API = ('https://datacenter-web.eastmoney.com/api/data/v1/get'
       '?reportName=RPT_ECONOMY_PPI&columns=ALL&pageSize=300'
       '&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB')
LIST_URL = 'https://www.stats.gov.cn/sj/zxfb/'
MIN_MONTHS = 24
NBS_LEAF_YOY = '价格指数 > 分行业工业生产者出厂价格指数 (上年同月=100) {seg}'
NBS_LEAF_MOM = '价格指数 > 分行业工业生产者出厂价格指数 (上月=100) {seg}'
NBS_ROW_PREFIX = '工业生产者出厂价格指数'


def _nbs_segments():
    y = int(common.TODAY[:4])
    return [f'({y}-)', f'({y - (y % 5) - 4}-{y - (y % 5)})']


def _nbs_series(path_tpl):
    """akshare统计局dg接口：返回{月份label: 指数值}（指数-100=涨跌幅%）。总指数行名以
    '工业生产者出厂价格指数'开头（行业行前缀为行业名，以此区分）。"""
    import akshare as ak  # 惰性导入：缺akshare时NBS通道跳过、降级东财
    last = None
    for seg in _nbs_segments():
        try:
            df = ak.macro_china_nbs_nation(kind='月度数据', path=path_tpl.format(seg=seg), period='LAST10')
        except Exception as e:  # noqa: BLE001
            last = e
            continue
        if len(df):
            series = df.set_index('指标') if '指标' in df.columns else df
            target = None
            for name in series.index:
                if str(name).startswith(NBS_ROW_PREFIX):
                    target = name
                    break
            if target is None:
                raise RuntimeError('NBS返回无总指数行')
            out = {}
            for colm in series.columns:
                v = series.loc[target, colm]
                if v is not None and str(v) != 'nan':
                    out[str(colm)] = float(v) - 100.0
            if out:
                return out
    raise RuntimeError(f'NBS dg获取失败: {str(last)[:80]}')


def _fetch_nbs():
    """NBS官方一手：同比（必取）+环比（best-effort）。返回{label: (同比%, 环比%或None)}。"""
    yoy = _nbs_series(NBS_LEAF_YOY)
    mom = {}
    try:
        mom = _nbs_series(NBS_LEAF_MOM)
    except Exception:  # noqa: BLE001
        pass
    out = {}
    for label, v in yoy.items():
        out[label] = (round(v, 2), round(mom[label], 2) if label in mom else None)
    return out


def _fetch_history():
    """备用：东财PPI全历史（2006-01起），返回[{REPORT_DATE,TIME,BASE,BASE_SAME...}]（新在前）。"""
    txt = common.http_get(API, referer='https://data.eastmoney.com/cjsj/ppi.html',
                          retries=3, timeout=30)
    d = json.loads(txt)
    if not d.get('success'):
        raise RuntimeError(f'东财接口返回失败: {d.get("message")}')
    rows = ((d.get('result') or {}).get('data')) or []
    rows = [r for r in rows
            if r.get('BASE_SAME') is not None and re.match(r'^\d{4}-\d{2}', str(r.get('REPORT_DATE', ''))[:7])]
    if len(rows) < MIN_MONTHS:
        raise RuntimeError(f'东财PPI有效月份数不足: {len(rows)}')
    return rows


def _dir_val(direction, num):
    if direction == '持平':
        return 0.0
    return float(num) * (1 if direction == '上涨' else -1)


def _stats_ppi_releases(max_pages=3):
    """统计局最新发布页（前max_pages页）能看到的PPI新闻稿，按新→旧返回[(label, 同比, 环比, 标题)]。
    用于交叉核验最新同比，并尽量多回填几个月的环比（新闻稿标题自带同比+环比）。"""
    out, seen = [], set()
    for page in range(max_pages):
        try:
            url = LIST_URL if page == 0 else f'{LIST_URL}index_{page}.html'
            listing = htmllib.unescape(common.http_get(url, encoding='utf-8', retries=1, timeout=20))
            for m in re.finditer(r'href="(\./\d{6}/t\d+_\d+\.html)"[^>]*title=[\'"]([^\'"]*工业生产者出厂价格[^\'"]*)[\'"]',
                                 listing):
                title = m.group(2)
                mt = re.search(r'(\d{4})年(\d{1,2})月份', title)
                ms = re.search(r'同比(上涨|下降|持平)([\d.]+)?%', title)
                mc = re.search(r'环比(上涨|下降|持平)([\d.]+)?%', title)
                if not (mt and ms):
                    continue
                label = f'{mt.group(1)}-{int(mt.group(2)):02d}'
                if label in seen:
                    continue
                seen.add(label)
                yoy = _dir_val(ms.group(1), ms.group(2) or 0)
                mom = _dir_val(mc.group(1), mc.group(2) or 0) if mc else None
                out.append((label, yoy, mom, title))
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    return out  # 列表新→旧，天然按期倒序


def _load_ledger():
    existing = {}
    if os.path.exists(CSV_PATH):
        import csv as _csv
        with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
            for r in _csv.DictReader(f):
                existing[r['数据日期']] = r
    return existing


def run():
    try:
        # 主通道：统计局dg接口（一手），只补缺失/勘误月份
        try:
            nbs = _fetch_nbs()
            existing = _load_ledger()
            wrote = 0
            for label, (yoy, mom) in sorted(nbs.items()):
                date = common.parse_date_label(label)
                cur = existing.get(date)
                if cur is not None and cur.get('同比%', '').strip() == str(yoy):
                    continue  # 同值不覆写（保留原来源与既有环比）
                values = {'同比%': yoy, '数据来源': '国家统计局dg接口(一手)',
                          '备注': f'{label}工业生产者出厂价格当月同比（同比指数{round(yoy + 100, 1)}-100）'}
                if mom is not None:
                    values['环比%'] = mom
                common.save_row(CSV_PATH, date, values, COLUMNS)
                wrote += 1
            latest = max(nbs)
            detail = f'NBS一手通道: 最新{latest} 同比={nbs[latest][0]}%' \
                     f' 环比={nbs[latest][1]}%，新增/勘误{wrote}行'
            # 官方新闻稿核验保留（best-effort）
            time.sleep(1)
            rels = _stats_ppi_releases(max_pages=1)
            if rels and rels[0][0] in nbs:
                ok = abs(nbs[rels[0][0]][0] - rels[0][1]) <= 0.15
                detail += f'；官方核验{"一致" if ok else "不一致!"}（{rels[0][0]}稿同比{rels[0][1]}%）'
            return '成功', detail
        except Exception as nbs_err:  # noqa: BLE001
            # 备用：东财全历史 + 新闻稿环比回填（原有逻辑不变）
            rows = _fetch_history()
            n = 0
            labels = set()
            for r in rows:
                label = str(r['REPORT_DATE'])[:7]
                common.save_row(CSV_PATH, common.parse_date_label(label), {
                    '同比%': round(float(r['BASE_SAME']), 2),
                    # 不带'环比%'键 → save_row保留已有行的环比（官方稿回填值不被清掉）
                    '数据来源': '东方财富数据中心RPT_ECONOMY_PPI',
                    '备注': f'{r.get("TIME", "")}工业生产者出厂价格当月同比(当月值指数{r.get("BASE", "")})'}, COLUMNS)
                labels.add(label)
                n += 1
            latest = rows[0]
            latest_label = str(latest['REPORT_DATE'])[:7]
            rels = _stats_ppi_releases()
            chk, filled = '', 0
            if rels:
                label0, yoy0, _, title0 = rels[0]
                em_val = float(latest['BASE_SAME'])
                if label0 == latest_label:
                    ok = abs(em_val - yoy0) <= 0.15
                    chk = f';官方核验{"一致" if ok else "不一致!"}（统计局{label0}同比{yoy0}%）'
                else:
                    chk = f';官方最新发布为{label0}，东财最新为{latest_label}'
                for label, yoy, mom, title in rels:
                    if mom is not None and label in labels:
                        common.save_row(CSV_PATH, common.parse_date_label(label), {
                            '环比%': round(mom, 2),
                            '备注': f'{title}（环比取自国家统计局新闻稿标题）'}, COLUMNS)
                        filled += 1
                chk += f'；官方稿环比已回填{filled}行'
            else:
                chk = ';stats.gov.cn当轮不可达，未核验且环比未更新'
            detail = (f'NBS不可达({str(nbs_err)[:60]})，东财备用: 回填{n}个月，'
                      f'最新{latest_label} 同比={latest["BASE_SAME"]}%{chk}')
            return '成功', detail
    except Exception as e:  # noqa: BLE001
        return '失败', str(e)


if __name__ == '__main__':
    print(common.run_collector(globals()))
