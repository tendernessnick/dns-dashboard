# -*- coding: utf-8 -*-
"""
生成看板 v14（组装器）：看板骨架.html + 布局.csv + 模块/*.json + 渲染器/*.js + _style_v8.css
    → index.html（页面壳，不含数据）

v13 模块化改造（2026-10-29），取代 v12 的「看板模板.html + 字符串补丁」机制：
  - 页面 = 骨架（页头/导航/ticker/附录，长期稳定）
        + 布局.csv（板块/分组/行/卡位的唯一顺序表，挪卡改这里）
        + 模块/*.json（一卡一配置，改卡只动对应文件）
  - 卡片外壳由本脚本的 builder 按配置生成；渲染引擎由 渲染器/*.js 按文件名顺序内联；
  - data.js 仍由 生成数据.py 独立重写，日常更新不触碰本壳。
v14 视觉迭代（2026-10-29）：样式切至 _style_v8.css；行内卡输出固定槽位
  （grid-column:span N;grid-row:M）与 data-mid=卡片ID。变更记录见
  docs/看板模块化/00_模块化设计与规范.md §8。
用法：python 生成看板.py
"""
import csv
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'index.html')
SKEL = os.path.join(BASE, '看板骨架.html')
LAYOUT = os.path.join(BASE, '布局.csv')
MOD_DIR = os.path.join(BASE, '模块')
REN_DIR = os.path.join(BASE, '渲染器')
CSS = os.path.join(BASE, '_style_v8.css')

# ============ 读入 ============
skeleton = open(SKEL, encoding='utf-8').read()
css = open(CSS, encoding='utf-8').read()
with open(LAYOUT, encoding='utf-8-sig', newline='') as f:
    layout = list(csv.DictReader(f))

CARDS = {}
for fp in sorted(glob.glob(os.path.join(MOD_DIR, '*.json'))):
    cfg = json.load(open(fp, encoding='utf-8'))
    cid = cfg.get('ID') or os.path.basename(fp)[:-5]
    if cid in CARDS:
        raise SystemExit(f'卡片ID重复：{cid}（{fp}）')
    CARDS[cid] = cfg

TYPES = {'kpi', 'desc', 'list', 'strip', 'share', 'ring', 'hlines', 'multi', 'cco'}
for cid, cfg in CARDS.items():
    if cfg['类型'] not in TYPES:
        raise SystemExit(f'{cid}：未知卡型 {cfg["类型"]}（允许：{sorted(TYPES)}）')


def Pn(p):
    return p[1:] if p.startswith('P') else p


def atattr(v):
    return (v or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def st(v):
    return f' style="{atattr(v)}"' if v else ''


def ti(v):
    return f' title="{atattr(v)}"' if v else ''

# ============ 卡壳 builders（输出与v12模板逐元素一致） ============


def b_top(c):
    if not (c.get('卡名') or c.get('标题提示') or c.get('状态点')):
        return ''
    dot = ''
    if c.get('状态点'):
        dot = f'<span class="dot {c["状态点"]}"{ti(c.get("状态说明"))}></span>'
    return f'<div class="card-top"><span class="t"{ti(c.get("标题提示"))}>{c["卡名"]}</span>{dot}</div>'


def b_foot(c):
    items = c.get('脚注') or []
    if not items:
        return ''
    parts = []
    for it in items:
        a = f' href="{atattr(it["href"])}"' if it.get('href') else ''
        a += f' target="{it["target"]}"' if it.get('target') else ''
        a += f' rel="{it["rel"]}"' if it.get('rel') else ''
        a += st(it.get('style'))
        parts.append(f'<{it["标签"]}{a}>{it["文本"]}</{it["标签"]}>')
    return f'<div class="foot">{"".join(parts)}</div>'


def b_val(c):
    return f'<div class="val">{c["数值占位"]}</div>' if c.get('数值占位') else ''


def b_sub(c, after=None):
    """副标题；after=True只输出图后副标题，False只输出图前，None都输出"""
    if '副标题' not in c:
        return ''
    want_after = bool(c.get('副标题在图后'))
    if after is not None and want_after != after:
        return ''
    return f'<div class="sub"{st(c.get("副标题样式"))}>{c["副标题"]}</div>'


def b_charts(c):
    chs = c.get('图表组') or []
    out = []
    for ch in chs:
        if ch.get('标题'):
            out.append(f'<div class="chart-cap">{ch["标题"]}</div>')
        col = (f' data-col="{ch["列"]}"'
               if (ch.get('显式列') or len(chs) > 1 or ch["列"] != 1) else '')
        out.append(f'<div class="chart" data-chart="{ch["P"]}"{col}{st(ch.get("样式"))}></div>')
    return ''.join(out)


def b_multi(c):
    if not c.get('多品类'):
        return ''
    if c.get('形态') == '容器':
        return (f'<div{st(c.get("容器样式"))} data-multi="{c["多品类"]}">'
                f'<span data-multi-note style="display:none"></span></div>')
    return f'<ul class="multi" data-multi="{c["多品类"]}"></ul>'


def b_statlines(c):
    items = c.get('指标行')
    if not items:
        return ''
    parts = []
    for it in items:
        parts.append(f'<div class="statline" data-vk="{it["P"]}" data-k="{Pn(it["P"])}"{st(it.get("样式"))}>'
                     f'<span class="k">{it["标签"]}</span><b>{it.get("占位", "")}</b></div>')
    inner = ''.join(parts)
    if c.get('指标行容器样式'):
        return f'<div{st(c["指标行容器样式"])}>{inner}</div>'
    return inner


def b_chips(c):
    links = c.get('链接组')
    if not links:
        return ''
    parts = [f'<a href="{atattr(l["链接"])}" target="_blank" rel="noopener" data-k="{Pn(l["P"])}">{l["文本"]}</a>'
             for l in links]
    return f'<div class="chips">{"".join(parts)}</div>'


def b_desc(c):
    return f'<p class="desc"{st(c.get("说明样式"))}>{c["说明"]}</p>' if c.get('说明') else ''


def b_btn(c):
    b = c.get('按钮')
    if not b or not b.get('链接'):
        return ''
    return f'<a class="btn-ext" href="{atattr(b["链接"])}" target="_blank" rel="noopener">{b["文本"]}</a>'


def b_feed(c):
    if c.get('榜单'):
        return f'<ul class="feed" data-toplist="{c["榜单"]}"></ul>'
    if c.get('资讯键') is not None and '资讯键' in c:
        return '<ul class="feed"></ul>'
    return ''


def b_topsub(c):
    t = c.get('榜单统计')
    if not t:
        return ''
    return f'<div class="sub" data-topsub="{t["P"]}"{st(t.get("样式"))}>{t.get("占位", "")}</div>'


def b_tllist(c):
    items = c.get('时间线')
    if not items:
        return ''
    parts = []
    for it in items:
        cls = ' class="next"' if it.get('下一个') else ''
        parts.append(f'<li{cls}><b>{it["日期"]}</b>{it["文本"]}</li>')
    return f'<ul class="tl-list">{"".join(parts)}</ul>'


def b_share(c):
    return f'<div class="sharechart" data-share="{c["份额图"]}"></div>'


def b_ring(c):
    w = c.get('环形文案', {})
    g = c.get('环形图', {})
    return (f'<div class="ringwrap" data-ring="{c["环形"]}">'
            f'<div class="ring"><svg viewBox="0 0 72 72" role="img" aria-label="{atattr(g.get("标签", ""))}">'
            f'<circle class="rb" cx="36" cy="36" r="30"/>'
            f'<circle class="rf" cx="36" cy="36" r="30" stroke-dasharray="{g.get("初始占比", "0 188.5")}"/></svg>'
            f'<span class="rt">{w.get("占比", "")}</span></div>'
            f'<div class="ringinfo"><div class="rv">{w.get("数值", "")}</div>'
            f'<div class="rs">{w.get("说明", "")}</div></div></div>')


def b_strip(c):
    parts = []
    for it in c.get('指标条', []):
        cls = 'sc hi' if it.get('高亮') else 'sc'
        parts.append(f'<div class="{cls}" data-k="{Pn(it["P"])}">'
                     f'<span class="k">{it["标签"]}</span><span class="v">{it["值占位"]}</span>'
                     f'<span class="s">{it["说明"]}</span></div>')
    return ''.join(parts)


def b_hlines(c):
    parts = []
    for it in c.get('横排', []):
        cls = 'hln next' if it.get('置顶') else 'hln'
        parts.append(f'<div class="{cls}" data-k="{Pn(it["P"])}" style="cursor:pointer"'
                     f' onclick="window.open(\'{it["链接"]}\',\'_blank\',\'noopener\')"{ti(it.get("点击提示"))}>'
                     f'<div class="hd">{it["日期"]}</div><div class="hn">{it["名称"]}</div>'
                     f'<div class="hs">{it["说明"]}</div></div>')
    return f'<div class="hlines">{"".join(parts)}</div>'


def b_cco(c):
    dot = ''
    if c.get('状态点'):
        dot = (f'<span class="dot {c["状态点"]}"{ti(c.get("状态说明"))}{st(c.get("状态点样式"))}></span>')
    head = (f'<div class="chead"><span class="mono">{c.get("角标字", "")}</span>'
            f'<span><div class="cn">{c["卡名"]}</div><div class="cs">{c.get("代码", "")}</div></span>{dot}</div>')
    cd = f'<div class="cd">{c["说明"]}</div>' if c.get('说明') else ''
    return f'<div class="cco" data-k="{Pn(c["主数据"])}">{head}{cd}{b_btn(c)}</div>'


def card_html(c, slot=None):
    t = c['类型']
    if t == 'cco':
        return b_cco(c)
    cls = ['card'] + (c.get('类修饰') or []) + ([f'c{c["跨列"]}'] if c.get('跨列') else [])
    dk = ' '.join(Pn(p) for p in [c['主数据']] + (c.get('关联数据') or []) if p)
    css = ';'.join(p for p in [(c.get('卡片样式') or '').rstrip(';'), slot or ''] if p)
    attrs = (st(css)
             + (f' data-mid="{atattr(c["ID"])}"' if c.get('ID') else '')
             + (f' data-k="{dk}"' if dk else '')
             + (f' data-news="{atattr(c["资讯键"])}"' if c.get('资讯键') else ''))
    if t == 'strip':
        inner = b_strip(c)
    elif t == 'hlines':
        inner = b_hlines(c)
    elif t == 'kpi':
        after = bool(c.get('副标题在图后'))
        inner = (b_top(c) + b_val(c) + b_sub(c, after=False) + b_multi(c)
                 + b_charts(c) + b_sub(c, after=True) + b_statlines(c) + b_foot(c))
    elif t == 'desc':
        inner = b_top(c) + b_val(c) + b_sub(c) + b_chips(c) + b_desc(c) + b_btn(c) + b_foot(c)
    elif t == 'list':
        inner = b_top(c) + b_tllist(c) + b_feed(c) + b_topsub(c) + b_foot(c)
    elif t == 'multi':
        inner = b_top(c) + b_multi(c) + b_foot(c)
    elif t == 'share':
        inner = b_top(c) + b_share(c) + b_foot(c)
    elif t == 'ring':
        inner = b_top(c) + b_ring(c) + b_foot(c)
    else:
        raise SystemExit(f'{c["ID"]}：无法渲染的卡型 {t}')
    return f'<div class="{" ".join(cls)}"{attrs}>{inner}</div>'

# ============ 板块拼装 ============


sections = []
for r in layout:
    if r['类型'] == 'S':
        sections.append({'meta': r, 'body': []})
    elif sections is not None and sections:
        sections[-1]['body'].append(r)

out = []
for sec in sections:
    meta, body = sec['meta'], sec['body']
    out.append(f'<section class="mod" id="{meta["引用"]}">')
    out.append('  <div class="sec-head"><div class="sec-no">%s</div><div><h2>%s</h2><p>%s</p></div><div class="sec-meta">%s</div></div>'
               % (meta['编号'], meta['标题'], meta['副标题'], meta['角标']))
    companies = [r for r in body if r['类型'] == 'P']
    row_open = wall_open = panel_open = tabs_done = False
    stack = None        # (堆叠名, span, 容器样式)
    stack_open = False
    slot_line, slot_fill = 1, 0   # v14固定槽位：行内当前网格行 / 已占列数

    def close_row():
        global row_open, wall_open, stack, stack_open, panel_open, slot_line, slot_fill
        if stack_open:
            out.append('  </div>')
            stack_open = False
        stack = None  # 待用的堆叠容器定义一并失效
        if row_open:
            out.append('  </div>')
            row_open = False
        if wall_open:
            out.append('  </div>')
            wall_open = False
        slot_line, slot_fill = 1, 0

    for r in body:
        t = r['类型']
        if t == 'G':
            close_row()
            if panel_open:
                out.append('  </div>')
                panel_open = False
            out.append(f'  <h3 class="grp">{r["引用"]}</h3>')
        elif t == 'P':
            close_row()
            if panel_open:
                out.append('  </div>')
                panel_open = False
            if not tabs_done:
                btns = []
                for i, co in enumerate(companies):
                    on = ' on' if i == 0 else ''
                    btns.append(f'<button class="cotab{on}" data-cotab="{co["引用"]}">{co["引用"]} <small>{co["代码"]}</small></button>')
                out.append(f'  <div class="co-tabs" id="coTabs">{"".join(btns)}</div>')
                tabs_done = True
            hidden = ' hidden' if r.get('隐藏') == '是' else ''
            out.append(f'  <div class="co-panel" data-copanel="{r["引用"]}"{hidden}>')
            panel_open = True
        elif t == 'R':
            close_row()
            if r.get('容器') == '卡墙':
                out.append('  <div class="crow">')
                wall_open = True
        elif t == 'K':
            # 行内堆叠容器（如 议息双卡 flex c4）：先确保所在行已打开
            if not row_open:
                out.append('  <div class="row">')
                row_open = True
                slot_line, slot_fill = 1, 0
            stack = (r['堆叠'], r.get('跨列') or '', r.get('容器样式', ''))
        elif t == 'C':
            cfg = CARDS.get(r['引用'])
            if cfg is None:
                raise SystemExit(f'布局.csv 引用了不存在的卡片：{r["引用"]}')
            if wall_open:
                out.append('    ' + card_html(cfg))
            elif r.get('堆叠'):
                if stack is None:
                    stack = (r['堆叠'], str(r.get('跨列') or cfg['跨列']), '')
                if not stack_open:
                    span_k = int(stack[1]) if str(stack[1]).strip().isdigit() else 0
                    slot_k = None
                    if span_k > 0:
                        if slot_fill + span_k > 12:
                            slot_line += 1
                            slot_fill = 0
                        slot_k = f'grid-column:span {span_k};grid-row:{slot_line}'
                        slot_fill += span_k
                    css_k = ';'.join(p for p in [(stack[2] or '').rstrip(';'), slot_k or ''] if p)
                    out.append(f'  <div class="c{stack[1]}"{st(css_k)}>')
                    stack_open = True
                out.append('    ' + card_html(cfg))
            else:
                if not row_open:
                    out.append('  <div class="row">')
                    row_open = True
                    slot_line, slot_fill = 1, 0
                span = cfg.get('跨列') or 0
                slot = None
                if span > 0:
                    if slot_fill + span > 12:
                        slot_line += 1
                        slot_fill = 0
                    slot = f'grid-column:span {span};grid-row:{slot_line}'
                    slot_fill += span
                out.append('    ' + card_html(cfg, slot))
    close_row()
    if panel_open:
        out.append('</div>')
    out.append('</section>')

sections_html = '\n'.join(x for x in out if x != '' and not x.startswith('<!--stack:'))

# ============ 组装输出 ============
js = ''
for fp in sorted(glob.glob(os.path.join(REN_DIR, '*.js'))):
    js += open(fp, encoding='utf-8').read().rstrip() + '\n'

html = skeleton
html = html.replace('<style>/*__CSS__*/</style>', '<style>\n' + css + '\n</style>', 1)
html = html.replace('<!--__SECTIONS__-->', sections_html, 1)
html = html.replace('<!--__DATA_JS__-->', '<script src="data.js"></script>', 1)
html = html.replace('<!--__ENGINE__-->', '<script>\n' + js + '</script>', 1)
for mark in ('<!--__SECTIONS__-->', '<!--__DATA_JS__-->', '<!--__ENGINE__-->', '/*__CSS__*/'):
    if mark in html:
        raise SystemExit(f'骨架占位符未替换：{mark}')

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)

unused = set(CARDS) - {r['引用'] for r in layout if r['类型'] == 'C'}
print('页面壳已重建(v14):', os.path.basename(OUT), os.path.getsize(OUT) // 1024, 'KB（不含数据）')
print('卡片', sum(1 for r in layout if r['类型'] == 'C'), '张 / 板块', len(sections),
      '个 / 渲染器', len(glob.glob(os.path.join(REN_DIR, "*.js"))), '个')
if unused:
    print('警告：以下卡片配置未被布局引用：', sorted(unused))
print('日常更新数据请运行: python 生成数据.py；发同事用: python 打包单文件.py')
