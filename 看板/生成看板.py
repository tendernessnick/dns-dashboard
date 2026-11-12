# -*- coding: utf-8 -*-
"""
生成看板（组装器）：看板骨架.html + 布局.csv + 模块/*.json + 渲染器/*.js + _style.css + _workspace.css
    → 页面.json登记的各部门HTML（页面壳，不含数据）

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
import re
import hashlib
from html import escape
from 页面配置 import load_pages

sys.stdout.reconfigure(encoding='utf-8')
BASE = os.path.dirname(os.path.abspath(__file__))
SKEL = os.path.join(BASE, '看板骨架.html')
MOD_DIR = os.path.join(BASE, '模块')
REN_DIR = os.path.join(BASE, '渲染器')
CSS = os.path.join(BASE, '_style.css')

# ============ 读入 ============
skeleton = open(SKEL, encoding='utf-8').read()
css = open(CSS, encoding='utf-8').read() + '\n' + open(os.path.join(BASE, '_workspace.css'), encoding='utf-8').read()
MEDIA_OMISSIONS = []
media_root = os.path.join(BASE, '媒体')
if os.path.isdir(media_root):
    for folder in sorted(os.scandir(media_root), key=lambda entry: entry.name):
        if not folder.is_dir():
            continue
        duplicate_images = {}
        for fp in sorted(glob.glob(os.path.join(folder.path, '*'))):
            if os.path.isfile(fp) and os.path.splitext(fp)[1].lower() in {'.jpg', '.jpeg', '.png', '.webp'}:
                with open(fp, 'rb') as image_file:
                    digest = hashlib.sha256(image_file.read()).hexdigest()
                duplicate_images.setdefault(digest, []).append(os.path.relpath(fp, BASE).replace(os.sep, '/'))
        for paths in duplicate_images.values():
            if len(paths) > 1:
                MEDIA_OMISSIONS.extend(paths)
DEFAULT_PAGE, PAGES = load_pages(BASE)

CARDS = {}
for fp in sorted(glob.glob(os.path.join(MOD_DIR, '*.json'))):
    try:
        cfg = json.load(open(fp, encoding='utf-8'))
    except Exception as e:
        raise SystemExit(f'模块JSON解析失败: {os.path.basename(fp)}: {e}')   # v18.8：报错带文件名
    cid = cfg.get('ID') or os.path.basename(fp)[:-5]
    cfg.setdefault('ID', cid)
    if cid in CARDS:
        raise SystemExit(f'卡片ID重复：{cid}（{fp}）')
    CARDS[cid] = cfg

TYPES = {'kpi', 'desc', 'list', 'strip', 'share', 'ring', 'hlines', 'multi', 'cco', 'review', 'planned'}


def validate_planned(config):
    """预留模块只描述未来能力；不得绑定尚不存在的数据或伪装成已接入。"""
    cid = config.get('ID', '')
    number = config.get('预留编号', '')
    if (not isinstance(number, str) or not re.fullmatch(r'P[1-9]\d*', number)
            or not isinstance(cid, str) or cid.split('_', 1)[0] != number[1:]):
        raise ValueError(f'{cid}预留编号须沿用P+模块数字编号')
    if config.get('主数据') or config.get('关联数据'):
        raise ValueError(f'{cid}规划模块不能绑定数据P号')
    bindings = {'资讯键', '榜单', '榜单统计', '图表组', '多品类', '份额图', '环形',
                '横排', '指标条', '指标行', '动态日历', '数值占位', '状态点', '按钮', '链接组'}
    if bindings.intersection(config):
        raise ValueError(f'{cid}规划模块不能包含数据绑定、数值或已接入状态')
    plan = config.get('规划对象')
    if not isinstance(plan, dict):
        raise ValueError(f'{cid}缺少规划对象')
    for key in ('用途', '计划内容', '使用边界'):
        if not isinstance(plan.get(key), str) or not plan[key].strip():
            raise ValueError(f'{cid}规划对象缺少{key}')
    for key in ('展示字段', '候选来源'):
        values = plan.get(key)
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError(f'{cid}规划对象{key}须为非空文本列表')
    if not isinstance(config.get('卡名'), str) or not config['卡名'].strip():
        raise ValueError(f'{cid}缺少卡名')


planned_numbers = set()
for cid, cfg in CARDS.items():
    if cfg['类型'] not in TYPES:
        raise SystemExit(f'{cid}：未知卡型 {cfg["类型"]}（允许：{sorted(TYPES)}）')
    if cfg['类型'] == 'planned':
        validate_planned(cfg)
        if cfg['预留编号'] in planned_numbers:
            raise ValueError(f'预留编号重复：{cfg["预留编号"]}')
        planned_numbers.add(cfg['预留编号'])


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
        label = f' data-status-label="{atattr(c["状态文案"])}"' if c.get('状态文案') else ''
        dot = f'<span class="dot {c["状态点"]}"{label}{ti(c.get("状态说明"))}></span>'
    return f'<div class="card-top"><span class="t"{ti(c.get("标题提示"))}>{c["卡名"]}</span>{dot}</div>'


_FOOT_TAGS = {'a', 'span', 'i', 'b', 'em', 'strong'}   # v18.8：脚注标签白名单，防坏配置产出任意标签


def b_foot(c):
    items = c.get('脚注') or []
    if not items:
        return ''
    parts = []
    for it in items:
        tag = str(it.get('标签') or 'span').lower()
        if tag not in _FOOT_TAGS:
            raise SystemExit(f'{c.get("ID", "?")}：脚注标签 {tag!r} 不在白名单 {sorted(_FOOT_TAGS)}')
        a = f' href="{atattr(it["href"])}"' if it.get('href') else ''
        a += f' target="{it["target"]}"' if it.get('target') else ''
        a += f' rel="{it["rel"]}"' if it.get('rel') else ''
        a += st(it.get('style'))
        parts.append(f'<{tag}{a}>{it["文本"]}</{tag}>')
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
    template = f' data-sub-template="{atattr(c["动态副标题"])}"' if c.get('动态副标题') else ''
    return f'<div class="sub"{template}{st(c.get("副标题样式"))}>{c["副标题"]}</div>'


def b_charts(c):
    if c.get('显示趋势') is False:
        return ''
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
    if not c.get('说明'):
        return ''
    anchor = f' data-cal-desc="{atattr(c["主数据"])}"' if c.get('动态日历') else ''   # v18.9：锚点统一存完整P号(P16)，与CAL键同名免拼接
    return f'<p class="desc"{anchor}{st(c.get("说明样式"))}>{c["说明"]}</p>'


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
    label = next((row.get('榜单标签', '') for row in REGISTRY if row['P号'] == t['P']), '')
    label_attr = f' data-top-label="{atattr(label)}"' if label else ''
    return f'<div class="sub" data-topsub="{t["P"]}"{label_attr}{st(t.get("样式"))}>{t.get("占位", "")}</div>'


def b_tllist(c):
    items = c.get('时间线')
    if not items:
        return ''
    parts = []
    for it in items:
        cls = ' class="next"' if it.get('下一个') else ''
        parts.append(f'<li{cls}><b>{it["日期"]}</b>{it["文本"]}</li>')
    anchor = f' data-cal="{atattr(c["主数据"])}"' if c.get('动态日历') else ''   # v18.9：锚点统一存完整P号(P16)
    return f'<ul class="tl-list"{anchor}>{"".join(parts)}</ul>'


def b_share(c):
    return f'<div class="sharechart" data-share="{c["份额图"]}"></div>'


def b_review(c):
    # v18：图文拆解卡（P91我爱音频网）——渲染器70_review.js按REVIEWS数据填充
    return f'<div class="revcards" data-review="{Pn(c["主数据"])}"></div>'


def b_ring(c):
    w = c.get('环形文案', {})
    g = c.get('环形图', {})
    g2 = c.get('环形图2') or {}   # v19.1：可选第二环（对比环，琥珀色，P56 Qi2.2）
    w2 = c.get('环形文案2') or {}

    def _ring(gi, wi, alt):
        altcls = ' ralt' if alt else ''
        cap = f'<span class="rc">{atattr(gi.get("图注", ""))}</span>' if gi.get('图注') else ''
        return (f'<div class="ringu"><div class="ring">'
                f'<svg viewBox="0 0 72 72" role="img" aria-label="{atattr(gi.get("标签", ""))}">'
                f'<circle class="rb" cx="36" cy="36" r="30"/>'
                f'<circle class="rf{altcls}" cx="36" cy="36" r="30" stroke-dasharray="{gi.get("初始占比", "0 188.5")}"/></svg>'
                f'<span class="rt">{atattr(wi.get("占比", ""))}</span></div>{cap}</div>')

    if g2:
        return (f'<div class="ringwrap" data-ring="{c["环形"]}">'
                f'<div class="rings2">{_ring(g, w, False)}{_ring(g2, w2, True)}</div>'
                f'<div class="ringinfo"><div class="rv">{w.get("数值", "")}</div>'
                f'<div class="rs">{w.get("说明", "")}</div></div></div>')
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
        # v18.7：不再注入内联onclick（URL含单引号会破坏HTML/JS），改data-href属性
        # 由渲染器统一委托监听打开（与65_nav事件委托一致），链接经atattr转义
        parts.append(f'<div class="{cls}" data-k="{Pn(it["P"])}" style="cursor:pointer"'
                     f' data-href="{atattr(it["链接"])}"{ti(it.get("点击提示"))}>'
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
    action = '<button type="button" class="detail-open" data-detail-module="' + atattr(c['ID']) + '">查看品牌资料<span aria-hidden="true">↗</span></button>'
    return f'<div class="cco" data-card-kind="cco" data-mid="{atattr(c["ID"])}" data-k="{Pn(c["主数据"])}"{source_attrs(c)}>{head}{cd}{b_btn(c)}{action}</div>'


def b_planned(c):
    plan = c['规划对象']
    fields = ''.join('<span>' + escape(value) + '</span>' for value in plan['展示字段'])
    return ('<div class="card-top"><span class="t">' + escape(c['卡名']) + '</span>'
            '<span class="chip c-planned">规划中</span></div>'
            '<p class="plan-purpose">' + escape(plan['用途']) + '</p>'
            '<p class="plan-content">' + escape(plan['计划内容']) + '</p>'
            '<div class="plan-fields" aria-label="计划展示字段">' + fields + '</div>'
            '<details class="plan-details"><summary>候选来源与使用边界</summary>'
            '<p><b>候选公开来源</b> ' + escape(' / '.join(plan['候选来源'])) + '</p>'
            '<p><b>使用边界</b> ' + escape(plan['使用边界']) + '</p></details>'
            '<div class="foot plan-foot"><span class="plan-number">' + escape(c['预留编号']) + '</span>'
            '<span>尚未接入数据</span></div>'
            '<div class="card-action-row"><button type="button" class="detail-open" data-detail-module="'
            + atattr(c['ID']) + '">查看建设规划<span aria-hidden="true">↗</span></button></div>')


def card_html(c, slot=None):
    t = c['类型']
    if t == 'cco':
        return b_cco(c)
    cls = ['card'] + (c.get('类修饰') or []) + ([f'c{c["跨列"]}'] if c.get('跨列') else [])
    if t == 'planned':
        cls.append('planned-card')
    dk = ' '.join(Pn(p) for p in [c['主数据']] + (c.get('关联数据') or []) if p)
    css = ';'.join(p for p in [(c.get('卡片样式') or '').rstrip(';'), slot or ''] if p)
    attrs = (st(css)
             + ' data-card-kind="' + atattr(t) + '"'
             + (f' data-mid="{atattr(c["ID"])}"' if c.get('ID') else '')
             + source_attrs(c)
             + (f' data-k="{dk}"' if dk else '')
             + (' data-change="none"' if c.get('显示前值变化') is False else '')
             + (' data-trend="none"' if c.get('显示趋势') is False else '')
             + (' data-module-status="planned" data-planned-id="' + atattr(c['预留编号']) + '"' if t == 'planned' else '')
             + (f' data-news="{atattr(c["资讯键"])}"' if c.get('资讯键') else ''))
    if t == 'planned':
        inner = b_planned(c)
    elif t == 'strip':
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
        inner = b_top(c) + b_tllist(c) + b_desc(c) + b_chips(c) + b_feed(c) + b_topsub(c) + b_foot(c)  # v18.5：list卡支持说明/链接组（P16/P20议息日历解读入口）
    elif t == 'multi':
        inner = b_top(c) + b_multi(c) + b_foot(c)
    elif t == 'share':
        inner = b_top(c) + b_share(c) + b_foot(c)
    elif t == 'review':
        inner = b_top(c) + b_review(c) + b_foot(c)
    elif t == 'ring':
        inner = b_top(c) + b_ring(c) + b_foot(c)
    else:
        raise SystemExit(f'{c["ID"]}：无法渲染的卡型 {t}')
    if c.get('使用提示') and t != 'planned':
        inner += '<p class="research-note">' + escape(c['使用提示']) + '</p>'
    if t != 'planned':
        label = ('查看产品与拆解' if t == 'review' else '查看榜单样本' if c.get('榜单')
                 else '查看趋势与数据' if (c.get('图表组') or c.get('多品类') or t in {'share', 'ring', 'strip'})
                 else '查看资讯与来源' if c.get('资讯键') else '查看说明与来源')
        inner += ('<div class="card-action-row"><button type="button" class="detail-open" data-detail-module="'
                  + atattr(c['ID']) + '">' + label + '<span aria-hidden="true">↗</span></button></div>')
    return f'<div class="{" ".join(cls)}"{attrs}>{inner}</div>'

# ============ 板块拼装 ============


def render_sections(layout, use_layout_columns=False):
    sections = []
    for r in layout:
        if r['类型'] == 'S':
            sections.append({'meta': r, 'body': []})
        elif sections:
            sections[-1]['body'].append(r)
        else:
            # v18.8：首个S板块行之前的布局行旧行为是静默丢弃——直接报错防改表踩坑
            raise SystemExit(f'布局第{r.get("序号")}行（{r["类型"]} {r["引用"]}）位于第一个S板块行之前，无处挂载')

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
            nonlocal row_open, wall_open, stack, stack_open, panel_open, slot_line, slot_fill
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
                    out.append(f'  <div class="co-tabs" id="coTabs-{meta["引用"]}" role="group" aria-label="选择公司">{"".join(btns)}</div>')
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
                if use_layout_columns and r.get('跨列'):
                    cfg = dict(cfg, 跨列=int(r['跨列']))
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

    return sections_html, sections

# ============ 溯源注册表（v17：由 看板数据固化/溯源表.csv 注入骨架，替代内嵌PROV） ============
PROV_CSV = os.path.join(os.path.dirname(BASE), '看板数据固化', '溯源表.csv')
with open(PROV_CSV, encoding='utf-8-sig', newline='') as f:
    _prov_rows = sorted(csv.DictReader(f), key=lambda r: int(r['P号'][1:]))
PROV = [{'id': int(r['P号'][1:]), 'cat': r['板块'], 'sub': r['分组'], 'title': r['词条'],
         'source': r['来源'], 'url': r['来源URL'], 'desc': r['条目说明'], 'freq': r['频率'],
         'status': r['状态'], 'sample': r['实测样例'], 'note': r['备注'], 'method': r['采集方式']}
        for r in _prov_rows]

# ============ 注册页面组装 ============


def normalize_pid(value):
    m = re.fullmatch(r'P(\d+)', str(value))
    return 'P' + str(int(m.group(1))) if m else None


REG_PATH = os.path.join(os.path.dirname(BASE), '看板数据固化', '词条注册表.csv')
with open(REG_PATH, encoding='utf-8-sig', newline='') as f:
    REGISTRY = list(csv.DictReader(f))
registered_pids = {normalize_pid(record['P号']) for record in REGISTRY}
registered_pids.update('P' + str(source['id']) for source in PROV)
conflicting_plans = planned_numbers & registered_pids
if conflicting_plans:
    raise ValueError('规划预留编号已被正式词条占用：' + '、'.join(sorted(conflicting_plans)))
STATIC_PIDS = {record['P号'] for record in REGISTRY if record.get('状态') == '静态维护'}
for source in PROV:
    if 'P' + str(source['id']) in STATIC_PIDS:
        source['status'] = '静态维护'
NEWS_PIDS = {}
for record in REGISTRY:
    for key in (record.get('资讯key') or '').split(';'):
        if key.strip():
            NEWS_PIDS.setdefault(key.strip(), set()).add(normalize_pid(record['P号']))


def module_pids(config):
    """数据键来自原模块嵌套配置及资讯键映射，不能把模块编号误当数据P号。"""
    if config.get('类型') == 'planned':
        return set()
    found = set()
    def visit(value):
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, str):
            pid = normalize_pid(value)
            if pid:
                found.add(pid)
    visit(config)
    for key in (config.get('资讯键') or '').split(';'):
        found.update(NEWS_PIDS.get(key.strip(), set()))
    return found - {None}


CARD_PIDS = {cid: module_pids(c) for cid, c in CARDS.items()}


def source_attrs(config):
    pids = sorted(CARD_PIDS.get(config.get('ID'), set()), key=lambda p: int(p[1:]))
    return ' data-source-pids="' + ' '.join(pids) + '"' if pids else ''


def read_layout(page):
    with open(os.path.join(BASE, page['布局']), encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, strict=True)
        if not {'类型', '引用', '跨列', '编号', '标题', '副标题', '角标'}.issubset(reader.fieldnames or []):
            raise ValueError(page['ID'] + '布局表头缺失')
        layout = list(reader)
    seen_cards, seen_sections = set(), set()
    fixed_ids = {'dns-dash', 'appendix', 'dnav', 'provbtn', 'asof', 'toTop',
                 'workspaceOverview', 'moduleSearch', 'moduleSearchResults', 'clearModuleSearch',
                 'readingSize', 'moduleDetail', 'detailTitle',
                 'pfCat', 'pfStatus', 'pfQ', 'provRows', 'provToggle', 'provSum', 'pfCount'}
    for row in layout:
        if None in row or any(value is None for value in row.values()):
            raise ValueError(page['ID'] + '布局列数不符')
        kind, ref = row['类型'], row['引用']
        if kind not in {'S', 'G', 'R', 'K', 'C', 'P'}:
            raise ValueError(f'{page["ID"]}未知布局类型：{kind}')
        if kind == 'S':
            if (not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', ref) or ref in fixed_ids
                    or ref.startswith(('coTabs-', 'card-', 'module-', 'prov-')) or ref in seen_sections):
                raise ValueError(f'{page["ID"]}板块ID无效或重复：{ref}')
            seen_sections.add(ref)
        if kind == 'C':
            if ref not in CARDS or ref in seen_cards:
                raise ValueError(f'{page["ID"]}模块不存在或重复：{ref}')
            seen_cards.add(ref)
        if kind in {'C', 'K'} and row['跨列'] and (not row['跨列'].isdigit() or not 1 <= int(row['跨列']) <= 12):
            raise ValueError(f'{page["ID"]}模块/堆叠跨列须为1~12：{ref}')
    if not seen_sections or not seen_cards:
        raise ValueError(page['ID'] + '必须含板块及模块')
    return layout


ENGINE = ''.join(open(fp, encoding='utf-8').read().rstrip() + '\n'
                 for fp in sorted(glob.glob(os.path.join(REN_DIR, '*.js'))))


def build_page(page):
    layout = read_layout(page)
    body, sections = render_sections(layout, page.get('使用布局跨列', False))
    used = [row['引用'] for row in layout if row['类型'] == 'C']
    pids = set().union(*(CARD_PIDS[cid] for cid in used))
    full_provenance = page.get('完整溯源', page['ID'] == DEFAULT_PAGE)
    sources = PROV if full_provenance else [r for r in PROV if 'P' + str(r['id']) in pids]
    planned_count = sum(CARDS[cid]['类型'] == 'planned' for cid in used)
    active_count = len(used) - planned_count
    page_info = {'id': page['ID'], 'label': page['名称'], 'file': page['文件'],
                 'moduleCount': len(used), 'sourceCount': len(sources),
                 'plannedCount': planned_count, 'activeModuleCount': active_count}
    tabs = ''.join('<a class="department-link' + (' on' if other['ID'] == page['ID'] else '')
                   + '" data-dashboard-page="' + escape(other['ID'], quote=True)
                   + '" href="' + escape(other['文件'], quote=True) + '"'
                   + (' aria-current="page"' if other['ID'] == page['ID'] else '')
                   + '>' + escape(other['名称']) + '</a>' for other in PAGES)
    nav = ''.join('<a class="tlink" href="#' + escape(section['meta']['引用'], quote=True)
                  + '"><span class="nav-no">' + escape(section['meta']['编号']) + '</span>'
                  + '<span class="nav-label">' + escape(section['meta']['标题']) + '</span>'
                  + '<span class="nav-count" title="本板块模块数（含规划）">'
                  + str(sum(row['类型'] == 'C' for row in section['body'])) + '</span></a>' for section in sections)
    metrics = ''.join('<div class="workspace-metric"><span>' + label + '</span><div><b>'
                      + str(value) + '</b><small>' + note + '</small></div></div>'
                      for label, value, note in [('来源词条', len(sources), '本页溯源范围'),
                                                 ('已建模块', active_count, '含原有受限项'),
                                                 ('规划预留', planned_count, '尚未接入数据')])
    focus_map = {
        'strategy': [('26_LME铜伦铜3月', 'series', 'P26', '原材料', '伦铜价格', '伦铜3个月合约，单位见图'),
                     ('21_汇率横条', 'series', 'P21', '汇率', '美元兑人民币', '人民币中间价'),
                     ('71_品类增速3C通讯零售', 'series', 'P71', '消费背景', '通讯器材零售', '同比变化，广义零售口径')],
        'marketing': [('42_手机厂家新品发布近7天', 'review', 'P42', '新品', '终端新品', '已收录的公开发布与产品信息'),
                      ('66_品牌销量排名Amazon线材榜', 'top', 'P66', '渠道', '线材榜单', 'Amazon美国站商品样本'),
                      ('90_充电头网拆解报告', 'review', 'P90', '产品', '充电产品拆解', '已有拆解图片与摘要')],
        'design': [('90_充电头网拆解报告', 'review', 'P90', '结构与工艺', '产品拆解', '从公开拆解了解设计取舍'),
                   ('91_我爱音频网评测', 'review', 'P91', '公开体验', '音频产品评测', '第三方评测，不代表全部用户'),
                   ('42_手机厂家新品发布近7天', 'review', 'P42', '形态与交互', '终端新品', '查看已收录的外观与产品信息')],
        'product': [('42_手机厂家新品发布近7天', 'review', 'P42', '新品', '终端产品动态', '已收录的公开产品信息'),
                    ('68_亚马逊销量榜充电类', 'top', 'P68', '渠道价格', '手机配件榜单', '商品排名与价格，不等同销量'),
                    ('44_全球手机出货量', 'series', 'P44', '需求背景', '全球手机出货', '终端出货不等同配件需求')],
        'hr': [('83_招聘职位量监测', 'module', '', '公开招聘', '同行招聘入口', '职位明细尚未接入'),
               ('81_产能扩产募投公告', 'module', '', '公司公告', '公开项目动态', '公告不直接代表招聘计划'),
               ('84_专利公告投关监控', 'module', '', '公司问答', '同行业务观察', '用公开信息了解业务背景')],
    }
    focus = []
    for cid, kind, pid, category, title, note in focus_map.get(page['ID'], []):
        if cid not in used:
            continue
        focus.append('<article class="focus-item" data-focus-kind="' + kind + '" data-focus-module="'
                     + atattr(cid) + '" data-focus-pid="' + pid + '"><span class="focus-category">'
                     + escape(category) + '</span><h2>' + escape(title) + '</h2><div class="focus-content"></div>'
                     + '<p class="focus-note">' + escape(note) + '</p><button type="button" class="focus-open" data-detail-module="'
                     + atattr(cid) + '">查看详情<span aria-hidden="true">↗</span></button></article>')
    featured = '<section class="focus-section" aria-label="本页精选"><div class="focus-heading"><h2>先看这几项</h2><span>精选现有资料，点击查看完整内容</span></div><div class="focus-grid">' + ''.join(focus) + '</div></section>'
    replacements = {
        '<!--__PAGE_TABS__-->': tabs,
        '<!--__SECTION_NAV__-->': nav,
        '<!--__PAGE_TITLE__-->': escape(page['标题']),
        '<!--__PAGE_SUBTITLE__-->': escape(page['副标题']),
        '<!--__PAGE_EYEBROW__-->': escape(page['眉标']),
        '<!--__PAGE_TAG__-->': escape(page['定位']),
        '<!--__PAGE_DESCRIPTION__-->': escape(page['说明']),
        '<!--__PAGE_METRICS__-->': metrics,
        '<!--__FEATURED__-->': featured,
        '<!--__MEDIA_POLICY__-->': '<script>var MEDIA_OMISSIONS=' + json.dumps(MEDIA_OMISSIONS, ensure_ascii=False).replace('</', '<\\/') + ';</script>',
        '<!--__SECTIONS__-->': body,
        '<!--__DATA_JS__-->': '<script src="data.js"></script>',
        '<!--__ENGINE__-->': '<script>\n' + ENGINE + '</script>',
        '<style>/*__CSS__*/</style>': '<style>\n' + css + '\n</style>',
        'var PROV=/*__PROV__*/[];': 'var PROV=' + json.dumps(sources, ensure_ascii=False).replace('</', '<\\/') + ';',
        'var PAGE_INFO=/*__PAGE_INFO__*/{};': 'var PAGE_INFO=' + json.dumps(page_info, ensure_ascii=False).replace('</', '<\\/') + ';',
    }
    html = skeleton
    if not page.get('速览', True):
        html = re.sub(r'<!--__OVERVIEW_START__-->.*?<!--__OVERVIEW_END__-->', '', html, flags=re.S)
    for old, new in replacements.items():
        if old not in html:
            raise ValueError(f'{page["ID"]}骨架缺少占位符：{old}')
        html = html.replace(old, new, 1)
    html = html.replace('<!--__OVERVIEW_START__-->', '').replace('<!--__OVERVIEW_END__-->', '')
    html = html.replace('<title>DNS 数据看板 · 市场与竞对监测</title>',
                        '<title>DNS · ' + escape(page['名称']) + '</title>', 1)
    if re.search(r'<!--__[A-Z_]+__-->|/\*__[A-Z_]+__\*/', html):
        raise ValueError(page['ID'] + '仍有未替换的骨架占位符')
    return html, page_info


def main():
    # 先完整校验全部视图，再写入，避免坏配置覆盖现有页面。
    outputs = [(page, *build_page(page)) for page in PAGES]
    for page, html, info in outputs:
        output = os.path.join(BASE, page['文件'])
        temp = output + '.tmp'
        with open(temp, 'w', encoding='utf-8') as f:
            f.write(html)
        os.replace(temp, output)
        print(f'{page["名称"]}: {page["文件"]} | {info["moduleCount"]}模块 / {info["sourceCount"]}词条')
    print('所有部门页面共用模块、data.js、媒体及同一套样式；分享请运行 打包单文件.py')


if __name__ == '__main__':
    main()
