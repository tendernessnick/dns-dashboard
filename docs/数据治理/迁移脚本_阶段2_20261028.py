# -*- coding: utf-8 -*-
"""阶段2存储治理迁移脚本（一次性，留痕存档）
步骤：A采集器列定义补丁 → B CSV迁移(来源映射/单位列/链接列) → C 目录分离 → D 词条注册表生成
安全：迁移前已有全量备份(_备份_CSV数据_20261028)；逐文件diff校验；采集器逐一py_compile。"""
import csv
import glob
import os
import py_compile
import re
import sys

BASE = r'E:\个人资料\工作实习相关\2026-2027深圳和宏\研报数据整理\数据看板构建'
CS = os.path.join(BASE, '看板数据固化', '采集脚本')
CSV_DIR = os.path.join(BASE, '看板数据固化', 'CSV数据')
OUT = os.path.join(BASE, 'docs', '数据治理')

SNAPSHOT = {66, 68, 70, 76, 77, 83, 92, 93, 94, 95, 98, 99, 78, 81, 231, 232, 233, 234}
LINKMOVE = {78, 81, 231, 232, 233, 234}
UNIT = {2:'%',3:'%',4:'%',5:'%',6:'%',33:'元/吨',34:'元/颗',35:'元/颗',37:'点',43:'个月',
        44:'百万台',46:'百万台',47:'百万台',48:'百万台',49:'%',56:'条',58:'美元',71:'%',
        72:'美元',79:'%',80:'%',82:'次/年',201:'亿元',202:'亿元',203:'亿元',204:'亿元',205:'亿元',
        211:'次/年',212:'次/年',213:'次/年',214:'次/年',221:'%',222:'%',223:'%',224:'%'}
UNIT_IN_NAME = re.compile(r'元/吨|美元|百万台|亿元|元/颗|指数|点|%')

def src_unit(pid, cols):
    if pid in UNIT: return UNIT[pid]
    for c in cols:
        m = UNIT_IN_NAME.search(c)
        if m: return m.group(0)
    return ''

# ---------- 来源措辞映射（值级精确匹配 + Amazon前缀规则） ----------
SRC_EXACT = {
    '生意社 100ppi.com': '生意社(100ppi)', '生意社': '生意社(100ppi)',
    '新浪财经 GlobalFutures日K': '新浪财经(期货行情)', '新浪财经 hq.sinajs.cn': '新浪财经(行情API)',
    'OECD SDMX(美国CPI总指数)': 'OECD(SDMX·美国CPI)',
    'FRED (St. Louis Fed) RSEAS': 'FRED(RSEAS)',
    '东方财富数据中心RPT_ECONOMY_PPI': '东方财富(数据中心·PPI)',
    '东方财富数据中心RPT_ECONOMY_CPI': '东方财富(数据中心·CPI)',
    '东方财富数据中心RPT_ECONOMICVALUE_USANEW(ISM)': '东方财富(数据中心·ISM)',
    '东方财富数据中心RPT_LICO_FN_CPD': '东方财富(数据中心·业绩报表)',
    '东方财富F10 RPT_F10_FINANCE_MAINFINADATA': '东方财富(F10主要指标)',
    '东方财富F10 BusinessAnalysis/PageAjax(zygcfx) 分产品口径': '东方财富(F10主营构成)',
    '巨潮资讯网 hisAnnouncement/query': '巨潮资讯(公告接口)',
    '互动易 irm.cninfo.com.cn/newircs/index/search': '互动易(接口)',
    '深圳证监局 辅导备案信息栏目AJAX接口 searchList': '深圳证监局(辅导备案)',
    'Kickstarter discover接口(科技类, sort=magic)': 'Kickstarter(discover接口)',
    '摩点金额榜(/all/top_money/going)+get_simple_product接口': '摩点(接口)',
    'WPC认证库 jpsapi.wirelesspowerconsortium.com/ajax/products/qi': 'WPC(认证产品库)',
    'TrendForce 现货价 dram_spot/flash_spot': 'TrendForce(现货页)',
    '立创商城 szlcsc.com': '立创商城(现货页)',
    '上海航运交易所 sse.net.cn': '上海航运交易所',
    'IATA pressrelease RSS': 'IATA(RSS)',
    '欧盟委员会DG ECFIN': '欧盟委员会(DG ECFIN)',
    '新浪财经 财务指标 vFD_FinancialGuideLine(300866)': '新浪财经(财务指标)',
    'Amazon商品详情页 /dp/B0FDQK69GQ': 'Amazon(商品页)',
}
SRC_PREFIX = [
    ('Amazon Best Sellers', 'Amazon(Best Sellers)'),
    ('Counterpoint Research（官网', 'Counterpoint(官网份额页)'),
]
SRC_BARE_DF = {22, 23, 27, 36}   # 裸"东方财富/新浪财经"仅行情类文件映射
report = {'files': [], 'patched': [], 'patch_fail': [], 'src_changed': 0}

def map_src(pid, v):
    if not v: return v, False
    nv = SRC_EXACT.get(v)
    if nv: return nv, True
    for pre, nv in SRC_PREFIX:
        if v.startswith(pre): return nv, True
    if pid in SRC_BARE_DF and v == '东方财富': return '东方财富(行情API)', True
    if pid in SRC_BARE_DF and v == '新浪财经': return '新浪财经(行情API)', True
    return v, False

# ---------- A. 采集器列定义补丁 ----------
need_patch = {}   # collector file -> set of cols to insert ('单位'/'链接')
for f in glob.glob(os.path.join(CSV_DIR, '*.csv')):
    m = re.search(r'-P(\d+)-', os.path.basename(f))
    if not m: continue
    pid = int(m.group(1))
    with open(f, encoding='utf-8-sig', newline='') as fh:
        cols = csv.DictReader(fh).fieldnames or []
    ins = None
    if pid in LINKMOVE and '链接' not in cols: ins = '链接'
    elif pid not in SNAPSHOT and '单位' not in cols and pid in UNIT: ins = '单位'
    if ins:
        for cf in glob.glob(os.path.join(CS, f'collect_P{pid}*.py')) + \
                  (glob.glob(os.path.join(CS, 'collect_P231_公司公告.py')) if pid in LINKMOVE else []):
            need_patch.setdefault(os.path.basename(cf), set()).add(ins)

for name, inserts in sorted(need_patch.items()):
    fp = os.path.join(CS, name)
    src = open(fp, encoding='utf-8').read()
    orig = src
    for ins in inserts:
        # 匹配列定义行（COLUMNS/COLS/cols/columns = [ ... '数据来源' ... ]），在其'数据来源'前插入
        pat = re.compile(
            r'^(\s*(?:COLUMNS|COLS|cols|columns)\s*=\s*\[)([^\]]*?)(\]\s*(?:#.*)?)$',
            re.M)
        def _repl(mo):
            body = mo.group(2)
            if f"'{ins}'" in body or f'"{ins}"' in body: return mo.group(0)
            if "'数据来源'" not in body: return mo.group(0)
            return mo.group(1) + body.replace("'数据来源'", f"'{ins}', '数据来源'", 1) + mo.group(3)
        src = pat.sub(_repl, src, count=2)
    if src != orig:
        open(fp, 'w', encoding='utf-8').write(src)
        try:
            py_compile.compile(fp, doraise=True)
            report['patched'].append(f'{name}(+{",".join(inserts)})')
        except Exception as e:
            report['patch_fail'].append(f'{name}: {e}')
# 双采集器 P84b 补充检查（irm四家JSON，无CSV列，不受影响）

# ---------- B. CSV迁移 ----------
URL_RE = re.compile(r'https?://[^\s,;，；]+', re.I)
for f in sorted(glob.glob(os.path.join(CSV_DIR, '*.csv'))):
    name = os.path.basename(f)
    m = re.search(r'-P(\d+)-', name)
    if not m: continue
    pid = int(m.group(1))
    with open(f, encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        cols = list(reader.fieldnames or [])
        rows = list(reader)
    before_rows, before_cols = len(rows), list(cols)
    src_changed = url_moved = 0
    unit_added = link_added = False

    # B1 来源映射
    for r in rows:
        v = (r.get('数据来源') or '').strip()
        nv, ch = map_src(pid, v)
        if ch:
            r['数据来源'] = nv; src_changed += 1

    # B2/B3 列变更
    new_cols = list(cols)
    if pid in LINKMOVE and '链接' not in cols:
        new_cols.insert(new_cols.index('数据来源'), '链接')
        link_added = True
        for r in rows:
            note = r.get('备注', '') or ''
            urls = URL_RE.findall(note)
            if urls:
                r['链接'] = ' '.join(urls)
                r['备注'] = URL_RE.sub('', note).strip(' ；;，, ')
                url_moved += 1
    ins_unit = pid not in SNAPSHOT and '单位' not in cols and pid in UNIT
    if ins_unit:
        new_cols.insert(new_cols.index('数据来源'), '单位')
        unit_added = True
        u = src_unit(pid, cols)
        for r in rows:
            r['单位'] = r.get('单位') or u
    if new_cols != cols or src_changed:
        rows = [{c: r.get(c, '') for c in new_cols} for r in rows]
        with open(f, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=new_cols)
            w.writeheader(); w.writerows(rows)
    report['files'].append({
        'file': name, 'rows_before': before_rows, 'rows_after': len(rows),
        'cols_before': len(before_cols), 'cols_after': len(new_cols),
        'unit_added': unit_added, 'link_added': link_added,
        'url_moved': url_moved, 'src_changed': src_changed})
    if len(rows) != before_rows:
        report['patch_fail'].append(f'!! 行数变化 {name}: {before_rows}->{len(rows)}')

# ---------- C. 目录分离 ----------
ARCH = os.path.join(CSV_DIR, '_归档')
VER = os.path.join(BASE, '看板数据固化', '验证')
os.makedirs(ARCH, exist_ok=True); os.makedirs(VER, exist_ok=True)
moves = []
old = os.path.join(CSV_DIR, '产品品类-P72-价格带结构-旧口径存档.csv')
if os.path.exists(old):
    os.rename(old, os.path.join(ARCH, os.path.basename(old))); moves.append('P72旧口径→_归档/')
xv = os.path.join(CSV_DIR, '交叉验证-行情双源对照.csv')
if os.path.exists(xv):
    os.rename(xv, os.path.join(VER, os.path.basename(xv))); moves.append('交叉验证→验证/')

# ---------- D. 词条注册表 ----------
sys.path.insert(0, os.path.join(BASE, '看板数据固化', '采集脚本'))
BIND = {
 'P1':['点',1],'P2':['%',1],'P3':['%',1],'P4':['%',2],'P5':['%',1],'P6':['%',1],'P8':['%',1],
 'P9':['点',1],'P10':['指数',1],'P11':['点',1],'P12':['%',2],'P13':['点',1],
 'P21':['元',4],'P22':['点',2],'P23':['',4],'P24':['',4],'P25':['',4],
 'P26':['美元/吨',0],'P27':['元/吨',0],'P28':['元/吨',0],'P29':['元/吨',0],
 'P31':['元/吨',0],'P32':['元/吨',0],'P33':['元/吨',0],'P34':['元/颗',2],'P35':['元/颗',2],
 'P36':['美元/桶',2],'P37':['点',2],'P38':['%',1],'P39':['元/吨',0],'P40':['元/吨',0],
 'P43':['个月',1],'P44':['百万台',1],'P45':['%',1],'P46':['百万台',1],'P47':['百万台',1],
 'P48':['百万台',1],'P49':['%',0],'P56':['条',0],
 'P58':['',2],'P69':['百万美元',0],'P71':['%',1],'P72':['美元',2],
 'P79':['%',2],'P80':['%',2],'P82':['次/年',2],'P92':['',0],'P93':['%',1],
 'P94':['元',0],'P201':['亿元',2],'P202':['亿元',2],'P203':['亿元',2],'P204':['亿元',2],'P205':['亿元',2],
 'P211':['次/年',2],'P212':['次/年',2],'P213':['次/年',2],'P214':['次/年',2],
 'P221':['%',1],'P222':['%',1],'P223':['%',1],'P224':['%',1]}
WIN = {'P1':36,'P5':36,'P6':36,'P4':60,'P21':60,'P22':60,'P23':60,'P24':60,'P25':60,'P26':60,
 'P27':60,'P31':60,'P32':60,'P36':60,'P39':60,'P40':60,'P58':60,'P8':36,'P10':36,'P12':36,
 'P13':36,'P33':60}
RATE = {}
for p in [21,22,23,24,25,26,27,36,56,69,79,80,81,82,95,8,10,12,13]: RATE[p] = 'A'
for p in [1,2,3,4,5,6,9,31,32,33,34,35,37,38,39,40,43,44,45,47,49,58,66,68,71,72,84,92,93,94,
          14,15,41,42,59,60,61,90]: RATE[p] = 'B'
for p in [11,28,46,48]: RATE[p] = 'C'
KOU = {1:'50荣枯线；FRED/东财全历史',2:'CPI-U同比，OECD口径',3:'PCE物价同比',4:'10年期国债收益率，日频',
 '5':'',5:'同比+环比双列',6:'同比全历史；环比自2026-08积累',8:'全项目同比；快报占位→正式值覆盖',
 9:'S&P口径，TE镜像(历史受限)',10:'零售量定基指数(2021=100)+环比',11:'ifo商业气候，TE镜像(历史受限)',
 12:'EMU约10年期月均；ECB日度受限',13:'SA平衡值；闪估占位→正式值覆盖',
 21:'人民币中间价',22:'美元指数',23:'离岸CNH',26:'伦铜3月，东财双源核验',27:'期货主连',
 28:'代理口径=生意社铜基准价',29:'光亮铜指数；历史待富宝RPA回填',
 31:'曲线=期货主力(回填)；数值=现货',32:'曲线=期货主力(回填)；数值=现货',
 33:'报价动态文章逐日考证(2024-12起)',34:'多SKU现货价',35:'多SKU现货价',36:'双源核验',
 37:'周度；历史12周媒体考证',38:'CTK同比月度',39:'曲线=期货主力(回填)；数值=现货',
 40:'曲线=期货主力(回填)；数值=现货',43:'Counterpoint年度推算',44:'IDC季度',
 45:'Counterpoint年度同比',46:'腕上设备；部分季度推算(考证C)',47:'IDC季度',48:'IDC季度；2026Q3待发布',
 49:'Counterpoint季度份额',56:'Qi2(MPP)累计占比每周',58:'现货均价(合约价未含)',
 66:'TOP30快照，日期+排名主键',68:'TOP30快照，日期+排名主键',69:'Census MARTS月度',
 71:'通讯器材类限额以上',72:'榜单实价自动分箱',79:'年报分业务口径',80:'前五大客户占比',
 81:'募投公告快照',82:'年报周转指标',84:'互动易问答',90:'关键词覆盖非上市同业',
 92:'月销快照',93:'众筹热门快照',94:'众筹热门快照',95:'辅导备案快照',
 201:'东财业绩报表近8季',202:'东财业绩报表近8季',203:'东财业绩报表近8季',204:'东财业绩报表近8季',
 205:'东财业绩报表近8季',211:'年报周转(年度)',212:'年报周转(年度)',213:'年报周转(年度)',214:'年报周转(年度)',
 221:'主营构成最新期',222:'主营构成最新期',223:'主营构成最新期',224:'主营构成最新期',
 231:'巨潮公告快照',232:'巨潮公告快照',233:'巨潮公告快照',234:'巨潮公告快照',
 78:'安克定期报告快照',81:'安克募投快照'}
NEWSKEY = {14:'P14',15:'P15',41:'P41',42:'P42',59:'P59',60:'P60',61:'P61',90:'P90',93:'P93',94:'P94',
           84:'安克互动',231:'奥海科技公告',232:'佳禾智能公告',233:'海能实业公告',234:'绿联科技公告',
           78:'安克公告',81:'安克募投'}
HIDDEN = {29,34,35}; ENTRY = {67,74,75,85,86,87,88,89,97}; STATICW = {16,17,18,20,50,51}

mat = {r['P号']: r for r in csv.DictReader(open(os.path.join(OUT, '01_采集器清单矩阵.csv'), encoding='utf-8-sig', newline=''))}
reg = []
for p in sorted(set(int(k[1:]) for k in mat)):
    key = f'P{p}'
    r = mat.get(key, {})
    b = BIND.get(key)
    status = ('不展示(采集保留)' if p in HIDDEN else '入口/受限' if p in ENTRY else
              '静态维护' if p in STATICW else '在板')
    ktype = ('快照' if p in SNAPSHOT else '时序' if b or p in (201,202,203,204,205,211,212,213,214,221,222,223,224)
             else '不适用(资讯)' if p in {14,15,41,42,59,60,61,90} else '不适用')
    reg.append({'P号': key, '词条': r.get('词条',''), '板块': r.get('板块',''),
        '单位': (b[0] if b else ('百万台' if p in (46,44,47,48) and False else '')) if not (key=='P58') else '美元',
        '小数位': (b[1] if b else ''), '显示窗口': WIN.get(key, 0 if (b or ktype=='时序') else ''),
        '更新频率': r.get('更新频率',''), '可靠度': RATE.get(p, ''),
        '口径说明': KOU.get(p, ''), '状态': status, '主键类型': ktype,
        '采集通道': r.get('采集通道',''), '采集器': r.get('采集器文件',''),
        '回填策略': r.get('回填策略',''), '资讯key': NEWSKEY.get(p, ''), '备注': r.get('可靠度(现)+建议','') if '建议' in r.get('可靠度(现)+建议','') else ''})
with open(os.path.join(BASE, '看板数据固化', '词条注册表.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(reg[0].keys())); w.writeheader(); w.writerows(reg)

print('补丁采集器:', len(report['patched']), '| 补丁失败:', report['patch_fail'] or '无')
print('迁移文件:', len(report['files']),
      '| 加单位列:', sum(1 for x in report['files'] if x['unit_added']),
      '| 加链接列:', sum(1 for x in report['files'] if x['link_added']),
      '| 来源值修改:', sum(x['src_changed'] for x in report['files']),
      '| URL迁移:', sum(x['url_moved'] for x in report['files']))
print('行数校验:', 'PASS' if not report['patch_fail'] else 'FAIL')
print('目录移动:', moves)
print('注册表:', len(reg), '行')
import json
json.dump(report, open(os.path.join(OUT, '_迁移明细.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
