# -*- coding: utf-8 -*-
"""
生成数据：固化CSV + 资讯JSON → data.js（看板唯一需要频繁更新的文件）
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


# ============ 元数据：由《词条注册表》驱动（唯一事实源，v12治理） ============
# v17：主数值列(PRIMARY)/资讯key/资讯文件 并入注册表，NEWS注入与首列选择均注册表驱动
REG_PATH = os.path.join(FIX, '词条注册表.csv')
REG_ROWS = []
BIND, WIN, META = {}, {}, {}
with open(REG_PATH, encoding='utf-8-sig', newline='') as _f:
    for _r in csv.DictReader(_f):
        REG_ROWS.append(_r)
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
PRIMARY = {_r['P号']: _r['主数值列'] for _r in REG_ROWS if _r.get('主数值列')}

DDATA = load_data()

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

# ============ 资讯feed（v17注册表驱动）：
#   资讯文件非空 → 资讯数据/*.json（键=卡配置的资讯键，多键多文件按分号对齐）；
#   资讯文件为空 → 按本行P号读 CSV公告快照（近10条，PDF链接在链接列/备注列） ============
def _csvpath(pid):
    for f in glob.glob(os.path.join(CSV_DIR, '*.csv')):
        if re.search(r'-%s-' % pid, os.path.basename(f)):
            return f
    return None


def _ann_items(pid):
    """公告CSV快照 → feed items（近10条去重）"""
    fp = _csvpath(pid)
    if not fp:
        return []
    try:
        with open(fp, encoding='utf-8-sig', newline='') as fh:
            rows = list(csv.DictReader(fh))
    except Exception:
        return []
    hdr = rows[0].keys() if rows else []
    tcol = next((c for c in hdr if '标题' in c), None)
    ncol = next((c for c in hdr if '序号' in c), None)
    if not tcol:
        return []
    items = []
    seen_t = set()
    for r in sorted(rows, key=lambda r: r.get('数据日期', ''), reverse=True):
        if r.get(tcol) in seen_t:      # v18.7：用探测出的标题列名去重（旧版硬取'标题'，列名含"标题"但不同名时全key=None致feed只剩1条）
            continue
        seen_t.add(r.get(tcol))
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
    return items


NEWS = {}
_news_stat = []
for _r in REG_ROWS:
    _keys = [k.strip() for k in (_r.get('资讯key') or '').split(';') if k.strip()]
    if not _keys:
        continue
    _files = [f.strip() for f in (_r.get('资讯文件') or '').split(';') if f.strip()]
    if _files:
        for _k, _fn in zip(_keys, _files):
            fp = os.path.join(NEWS_DIR, _fn)
            if not os.path.exists(fp):
                continue
            try:
                items = json.load(open(fp, encoding='utf-8'))['items']
            except Exception:
                continue
            if not items:
                continue
            NEWS[_k] = [{'date': it.get('date', ''), 'title': it.get('title', ''),
                         'title_zh': it.get('title_zh', ''), 'url': it.get('url', '#')}
                        for it in items]
            _news_stat.append('%s:%d条' % (_k, len(NEWS[_k])))
    else:
        for _k in _keys:
            items = _ann_items(_r['P号'])
            if items:
                NEWS[_k] = items
                _news_stat.append('%s:%d条' % (_k, len(items)))

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
for _r in REG_ROWS:                      # v18.9注册表化：榜单标签列驱动（原硬编码P66/P68元组退役）
    _lab = (_r.get('榜单标签') or '').strip()
    if _lab:
        _t = _tops(_r['P号'], _lab)
        if _t:
            TOPS[_r['P号']] = _t

# ============ 图文数据（v18：P91评测；v18.2：P90拆解；v18.3：P93/P94众筹项目图文）→ REVIEWS ============
# 数据契约：图文数据/<任务目录>/*/*/_meta.json（产品名/品类tag/发布日期/原文链接/chips/摘要/照片），
# 本脚本只搬运（按发布日期取最近6篇，同日按排序值），照片压缩后base64内联保持离线可用。
def _img_media(path, pid, width=240, quality=60, max_bytes=18000):
    """照片文件 → 看板/媒体/<pid>/ 下压缩JPEG，返回相对路径（失败返回空串，卡面以占位块渲染）。
    v18.9照片外置：data.js不再base64内联（照片曾占约47%体积且随图文增长无界）；
    媒体目录由本脚本每次重建，打包单文件.py 发同事时把 媒体/ 引用内联回dataURI，离线能力不损失。
    超 max_bytes 逐级降质兜底。"""
    try:
        import io
        from PIL import Image
        im = Image.open(path).convert('RGB')
        if im.width > width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        out_dir = os.path.join(BASE, '媒体', pid)
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(path))[0]
        parent = os.path.basename(os.path.dirname(path))   # 文章/项目夹名——源图都叫照片1.jpg，不带夹名会互相覆盖
        out_fp = os.path.join(out_dir, f'{parent}_{base}.jpg')
        q = quality
        while True:
            buf = io.BytesIO()
            im.save(buf, 'JPEG', quality=q, optimize=True)
            data = buf.getvalue()
            if len(data) <= max_bytes or q <= 30:
                break
            q -= 10
        with open(out_fp, 'wb') as f:
            f.write(data)
        return f'媒体/{pid}/{parent}_{base}.jpg'
    except Exception:
        return ''


def _scan_reviews(rel, noimg='', pid=''):
    """扫描 图文数据/<rel>/*/*/_meta.json → {'items':[最近6篇], 'updated':最大发布日期, 'noimg':占位标签} 或 None
    排序：发布日期 desc，同日按 排序值(如已筹金额) desc（文章无该字段视为0，不影响原序）
    照片经 _img_media 外置到 看板/媒体/<pid>/（v18.9）。"""
    rdir = os.path.join(FIX, '图文数据', rel)
    metas = []
    for _fp in glob.glob(os.path.join(rdir, '*', '*', '_meta.json')):
        try:
            _m = json.load(open(_fp, encoding='utf-8'))
        except Exception:
            continue
        if not (_m.get('产品名') and _m.get('原文链接')):
            continue
        _photos = [os.path.normpath(os.path.join(os.path.dirname(_fp), _ph))
                   for _ph in (_m.get('照片') or [])[:2]]
        metas.append({'m': _m, 'photos': [p for p in _photos if os.path.exists(p)]})
    if not metas:
        return None
    metas.sort(key=lambda x: (x['m'].get('发布日期') or '',
                              float(x['m'].get('排序值') or 0)), reverse=True)
    items = []
    for _x in metas[:6]:
        _m = _x['m']
        items.append({'name': _m['产品名'], 'tag': _m.get('品类tag', ''),
                      'date': (_m.get('发布日期') or '')[5:10],
                      'chips': [str(c) for c in (_m.get('chips') or [])[:6]],
                      'desc': _m.get('摘要', ''), 'url': _m['原文链接'],
                      'img': _img_media(_x['photos'][0], pid) if _x['photos'] else ''})
    return {'items': items, 'noimg': noimg,
            'updated': max(x['m'].get('发布日期') or '' for x in metas)}


import shutil
MEDIA_ROOT = os.path.join(BASE, '媒体')
shutil.rmtree(MEDIA_ROOT, ignore_errors=True)      # 每次重建（只保留当前引用的照片）
os.makedirs(MEDIA_ROOT, exist_ok=True)

REVIEWS = {}
for _r in REG_ROWS:                      # v18.9注册表化：图文目录/图文占位列驱动（原硬编码四元组退役）
    _rel = (_r.get('图文目录') or '').strip()
    if _rel:
        _scan = _scan_reviews(_rel, (_r.get('图文占位') or '').strip(), _r['P号'])
        if _scan:
            REVIEWS[_r['P号']] = _scan

# ============ 议息日历（v18.6 collect_P16产出）→ CAL（v18.9注册表化：日历键列驱动） ============
CAL = {}
for _r in REG_ROWS:
    _cfile = (_r.get('日历键') or '').strip()
    if not _cfile:
        continue
    _fp = os.path.join(FIX, '资讯数据', _cfile)
    if not os.path.exists(_fp):
        continue
    try:
        _c = json.load(open(_fp, encoding='utf-8'))
        _v = _c.get(_r['P号'])
        if isinstance(_v, dict) and _v.get('时间线'):
            CAL[_r['P号']] = _v
    except Exception:
        pass

# ============ 写 data.js ============
def _js(obj):
    return json.dumps(obj, ensure_ascii=False).replace('</', '<\\/')


js = ('// 由 生成数据.py 自动生成——勿手改；页面壳(index.html)通过 <script src="data.js"> 引用\n'
      '// 元数据（单位/小数位/窗口/可靠度/口径）由 看板数据固化/词条注册表.csv 驱动\n'
      'var ACCENT={m1:"#0065B0",m2:"#B45309",m3:"#0F766E",m4:"#6D28D9",m5:"#BE123C"};\n'
      'const DDATA=' + _js(DDATA) + ';\n'
      'DDATA._news=' + _js(NEWS) + ';\n'
      'var TOPS=' + _js(TOPS) + ';\n'
      'var REVIEWS=' + _js(REVIEWS) + ';\n'
      'var CAL=' + _js(CAL) + ';\n')
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(js)

_size = os.path.getsize(OUT)
print('data.js 已生成:', _size // 1024, 'KB |',
      '词条', len(DDATA) - 5, '| 数据截至', ASOF, '| 待补录', PEND or '无', '|',
      '资讯/公告', len(NEWS), '卡 | 榜单', list(TOPS.keys()) or '无',
      '| 图文', list(REVIEWS.keys()) or '无', '| 议息', list(CAL.keys()) or '无')
if _size > 500 * 1024:
    # v18.9体积熔断：照片已外置，data.js超500KB即告警（防无感膨胀回归）
    print(f'⚠ 警告：data.js 已达 {_size // 1024}KB（>500KB阈值），'
          f'请检查是否新增了大体量数据或照片内联回归')
