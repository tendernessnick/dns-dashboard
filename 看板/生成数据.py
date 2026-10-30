# -*- coding: utf-8 -*-
"""
生成数据 v12：固化CSV + 资讯JSON → data.js（看板唯一需要频繁更新的文件）
页面壳（index.html）长期稳定，本脚本只重写 data.js，毫秒级完成、不联网。
用法：python 生成数据.py    （采集 run_all.py 之后运行）
"""
import csv
import glob
import html as _htmlmod
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(os.path.dirname(BASE), '看板数据固化')
CSV_DIR = os.path.join(FIX, 'CSV数据')
NEWS_DIR = os.path.join(FIX, '资讯数据')
OUT = os.path.join(BASE, 'data.js')

SKIP_COLS = {'数据日期', '数据来源', '备注'}


def num(s):
    try:
        x = float(str(s).replace(',', '').replace('%', '').replace('亿元', '').strip())
        return x
    except Exception:
        return None


PRIMARY = {'P2': '同比%', 'P5': '同比%', 'P6': '同比%', 'P79': '营收占比%'}


def load_data():
    data = {}
    for f in sorted(glob.glob(os.path.join(CSV_DIR, '*.csv'))):
        m = re.search(r'-P(\d+)-', os.path.basename(f))
        if not m:
            continue
        pid = 'P' + str(int(m.group(1)))
        with open(f, encoding='utf-8-sig', newline='') as fh:
            reader = csv.DictReader(fh)
            cols = reader.fieldnames or []
            raw = list(reader)
        if not raw:
            continue
        num_cols = [c for c in cols if c not in SKIP_COLS
                    and any(num(r.get(c)) is not None for r in raw)]
        if pid in PRIMARY and PRIMARY[pid] in num_cols:
            num_cols.remove(PRIMARY[pid])
            num_cols.insert(0, PRIMARY[pid])
        rows = []
        src = ''
        for r in raw:
            row = [r.get('数据日期', '')]
            ok = False
            for c in num_cols:
                v = num(r.get(c))
                row.append(v)
                ok = ok or v is not None
            if ok:
                rows.append(row)
        rows.sort(key=lambda x: x[0])
        for r in reversed(raw):
            if r.get('数据来源'):
                src = r['数据来源']
                break
        data[pid] = {'cols': num_cols, 'rows': rows, 'src': src,
                     'file': os.path.basename(f)}
    return data


DDATA = load_data()

# ============ 元数据：由《词条注册表》驱动（唯一事实源，v12治理） ============
REG_PATH = os.path.join(FIX, '词条注册表.csv')
BIND, WIN, META = {}, {}, {}
with open(REG_PATH, encoding='utf-8-sig', newline='') as _f:
    for _r in csv.DictReader(_f):
        _pid = _r['P号']
        if _r['单位'] or _r['小数位']:
            try:
                BIND[_pid] = [_r['单位'], int(_r['小数位'])]
            except ValueError:
                BIND[_pid] = [_r['单位'], None]
        try:
            _win = int(_r['显示窗口'] or 0)
        except ValueError:
            _win = 0
        if _win:
            WIN[_pid] = _win
        if _r['可靠度'] and not _r['可靠度'].startswith('—'):
            META[_pid] = {'r': _r['可靠度'], 'k': _r['口径说明'], 'f': _r['更新频率']}

# 数据截至 = 全库最新数据日期（不含未来日期，如换机周期2029预测）
import datetime as _dt
_today = _dt.date.today().isoformat()
_all_dates = [row[0] for d in DDATA.values() if isinstance(d, dict)
              for row in (d.get('rows') or []) if row and row[0] <= _today]
ASOF = max(_all_dates) if _all_dates else _today

# 待补录清单（P46/P48缺季检测，采集器维护）
PEND = {}
_pending_fp = os.path.join(FIX, '待补录.csv')
if os.path.exists(_pending_fp):
    with open(_pending_fp, encoding='utf-8-sig', newline='') as _f:
        for _r in csv.DictReader(_f):
            PEND.setdefault(_r['P号'], []).append(_r['缺失季度'])
PEND = {k: '、'.join(v) for k, v in PEND.items()}
DDATA['_bind'] = BIND
DDATA['_win'] = WIN
DDATA['_meta'] = META
DDATA['_pending'] = PEND
DDATA['_asof'] = ASOF
# （旧的手写BIND/WIN字典已删除：单位/小数位/显示窗口改由《词条注册表.csv》驱动，改元数据只需改注册表）

# ============ 资讯feed（近7天新闻/众筹/互动，由资讯采集器生成JSON） ============
NEWS_FILES = {'P14': '财经新闻.json', 'P15': '地缘政治.json',
              'P41': 'apple新闻.json', 'P42': '手机新品.json',
              'P93': 'kickstarter.json', 'P94': 'modian.json',
              'P59': '充电头网早报.json', 'P60': '快充拆解.json',
              'P61': 'avs资讯.json', 'P90': '同业新闻.json',
              '安克互动': 'irm-安克创新.json'}
for _co in ('奥海科技', '佳禾智能', '海能实业', '绿联科技'):
    NEWS_FILES[_co + '公告'] = '公告-%s.json' % _co
    NEWS_FILES[_co + '互动'] = 'irm-%s.json' % _co

NEWS = {}
_news_stat = []
for pid, fn in NEWS_FILES.items():
    fp = os.path.join(NEWS_DIR, fn)
    if not os.path.exists(fp):
        continue
    try:
        items = json.load(open(fp, encoding='utf-8'))['items']
    except Exception:
        continue
    if not items:
        continue
    NEWS[pid] = [{'date': it.get('date', ''), 'title': it.get('title', ''),
                  'title_zh': it.get('title_zh', ''), 'url': it.get('url', '#')}
                 for it in items]
    _news_stat.append('%s:%d条' % (pid, len(NEWS[pid])))

# ============ 公司公告（P231-P234/P78/P81 CSV快照 → feed items，PDF链接在备注列） ============
_GG = {co + '公告': pid for co, pid in
       (('奥海科技', 'P231'), ('佳禾智能', 'P232'), ('海能实业', 'P233'), ('绿联科技', 'P234'),
        ('安克', 'P78'))}
_GG['安克募投'] = 'P81'


def _csvpath(pid):
    for f in glob.glob(os.path.join(CSV_DIR, '*.csv')):
        if re.search(r'-%s-' % pid, os.path.basename(f)):
            return f
    return None


for key, pid in _GG.items():
    fp = _csvpath(pid)
    if not fp:
        continue
    try:
        with open(fp, encoding='utf-8-sig', newline='') as fh:
            rows = list(csv.DictReader(fh))
    except Exception:
        continue
    hdr = rows[0].keys() if rows else []
    tcol = next((c for c in hdr if '标题' in c), None)
    ncol = next((c for c in hdr if '序号' in c), None)
    if not tcol:
        continue
    items = []
    seen_t = set()
    for r in sorted(rows, key=lambda r: r.get('数据日期', ''), reverse=True):
        if r.get('标题') in seen_t:
            continue
        seen_t.add(r.get('标题'))
        if len(items) >= 10:
            break
        url = (r.get('链接') or '').strip()  # v12治理：链接专用列优先
        if not url:
            for c in ('备注', '数据来源'):
                v = r.get(c) or ''
                m = re.search(r'https?://[^\s,;，；]+\.pdf', v, re.I)
                if m:
                    url = m.group(0)
                    break
        url = url or 'http://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice'
        no = r.get(ncol, '') if ncol else ''
        items.append({'date': (r.get('数据日期') or '')[5:10],
                      'title': (('[%s] ' % no) if no else '') + (r.get(tcol) or ''),
                      'title_zh': '', 'url': url})
    if items:
        NEWS[key] = items
        _news_stat.append('%s:%d条' % (key, len(items)))

# ============ 榜单快照（P66线材榜/P68充电榜）→ TOPS：TOP5条目(带图)+Anker席数+均价 ============
def _tops(pid, label):
    fp = _csvpath(pid)
    if not fp:
        return None
    try:
        with open(fp, encoding='utf-8-sig', newline='') as fh:
            rows = list(csv.DictReader(fh))
    except Exception:
        return None
    if not rows:
        return None
    last = max(r.get('数据日期', '') for r in rows)
    snap = [r for r in rows if r.get('数据日期') == last]

    def _rk(r):
        try:
            return int(float(r.get('排名', 99)))
        except Exception:
            return 99
    snap.sort(key=_rk)
    prices = []
    for r in snap:
        try:
            prices.append(float(r.get('价格USD')))
        except Exception:
            pass
    titles = [(r.get('标题') or '') for r in snap]
    anker = sum(1 for x in titles if 'anker' in x.lower())
    items = []
    for r in snap[:5]:
        try:
            price = float(r.get('价格USD'))
        except Exception:
            price = None
        raw = _htmlmod.unescape(r.get('标题') or '')
        items.append({'rank': _rk(r), 'title': _htmlmod.escape(raw[:64]),
                      'price': price, 'asin': r.get('ASIN', ''),
                      'img': _htmlmod.escape(r.get('图片URL') or '', quote=True)})
    if not items:
        return None
    avg = round(sum(prices) / len(prices), 2) if prices else None
    return {'date': last, 'total': len(snap), 'anker': anker, 'avg': avg, 'items': items,
            'label': label}


TOPS = {}
for _p, _lab in (('P66', '线材榜'), ('P68', '充电榜')):
    _t = _tops(_p, _lab)
    if _t:
        TOPS[_p] = _t

# ============ 写 data.js ============
def _js(obj):
    return json.dumps(obj, ensure_ascii=False).replace('</', '<\\/')


js = ('// 由 生成数据.py 自动生成——勿手改；页面壳(index.html)通过 <script src="data.js"> 引用\n'
      '// 元数据（单位/小数位/窗口/可靠度/口径）由 看板数据固化/词条注册表.csv 驱动\n'
      'var ACCENT={m1:"#0065B0",m2:"#B45309",m3:"#0F766E",m4:"#6D28D9",m5:"#BE123C"};\n'
      'const DDATA=' + _js(DDATA) + ';\n'
      'DDATA._news=' + _js(NEWS) + ';\n'
      'var TOPS=' + _js(TOPS) + ';\n')
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(js)

print('data.js 已生成:', os.path.getsize(OUT) // 1024, 'KB |',
      '词条', len(DDATA) - 5, '| 数据截至', ASOF, '| 待补录', PEND or '无', '|',
      '资讯/公告', len(NEWS), '卡 | 榜单', list(TOPS.keys()) or '无')
