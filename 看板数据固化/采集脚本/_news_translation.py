"""新闻译题的纯离线质量层。仅标准库；不导入采集器/requests，不联网或写文件。

术语表只表达通用词义，不包含整篇标题。原题只读保留，质检不等于内容事实核验。
"""
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata

_TERMS_RAW = Path(__file__).with_name('_news_translation_terms.json').read_bytes()
_TERMS_CONFIG = json.loads(_TERMS_RAW)
TERMS = tuple(tuple(x) for x in _TERMS_CONFIG['terms'])
CONTEXTUAL_TERMS = tuple(_TERMS_CONFIG.get('contextual_terms', ()))
ABBREVIATION_EQUIVALENTS = _TERMS_CONFIG.get('abbreviation_equivalents', {})
TRANSLATION_VERSION = 'news-zh-v2-' + hashlib.sha256(_TERMS_RAW).hexdigest()[:12]
CACHE_META_KEY = '__translation_meta__'
_HAN = re.compile(r'[\u3400-\u9fff]')
_ERROR = re.compile(r'mymemory\s+warning|quota|too many requests|limit exceeded|invalid (?:api|key)|'
                    r'query length|please (?:select|provide|wait)|access denied|service unavailable|'
                    r'免费额度|配额|请求过于频繁|翻译服务不可用', re.I)
_NUM = r'[+\-−]?\d+(?:,\d{3})*(?:\.\d+)?'
_SCALE = r'(?:trillion|billion|million|thousand|万亿|亿|万|千)'
_MONEY_PREFIX = re.compile(r'(?P<sign>[+\-−]?)(?P<currency>US\$|USD\s*|EUR\s*|GBP\s*|CNY\s*|\$|€|£|¥)\s*'
                           r'(?P<number>' + _NUM + r')\s*(?P<scale>' + _SCALE + r')?', re.I)
_MONEY_SUFFIX = re.compile(r'(?P<number>' + _NUM + r')\s*(?P<scale>' + _SCALE + r')?\s*'
                           r'(?P<currency>美元|欧元|英镑|人民币|元|USD|EUR|GBP|CNY|\$|€|£|¥)', re.I)
_UNIT = r'(?:percentage points?|basis points?|percent|bps|bp|GHz|MHz|kHz|Hz|kWh|mAh|Wh|kW|mW|W|mV|V|mA|A|GB|TB|MB|mm|cm|kg|°C|%|％|百分点|基点)(?![A-Za-z])'
_NUMBER = re.compile(r'(?<![A-Za-z0-9_.])(?P<number>' + _NUM + r')\s*(?P<scale>' + _SCALE + r')?\s*(?P<unit>' + _UNIT + r')?', re.I)
_FACTORS = {'trillion': Decimal('1e12'), 'billion': Decimal('1e9'), 'million': Decimal('1e6'),
            'thousand': Decimal('1e3'), '万亿': Decimal('1e12'), '亿': Decimal('1e8'),
            '万': Decimal('1e4'), '千': Decimal('1e3')}
_CURRENCIES = {'$': 'USD', 'US$': 'USD', 'USD': 'USD', '美元': 'USD', '€': 'EUR', 'EUR': 'EUR',
               '欧元': 'EUR', '£': 'GBP', 'GBP': 'GBP', '英镑': 'GBP', '¥': '¥',
               'CNY': 'CNY', '人民币': 'CNY', '元': 'CNY'}
_CURRENCY_ZH = {'USD': '美元', 'EUR': '欧元', 'GBP': '英镑', 'CNY': '元', '¥': '¥'}
_UNIT_CANON = {'percent': '%', '％': '%', 'percentage point': 'pp', 'percentage points': 'pp',
               '百分点': 'pp', 'basis point': 'bp', 'basis points': 'bp', 'bps': 'bp', '基点': 'bp'}


def normalize_title(value):
    """用于比较/翻译的规范文本；调用者仍保留原title，不用本函数覆盖它。"""
    text = str(value or '')
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    text = re.sub(r'<!\[CDATA\[|\]\]>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = unicodedata.normalize('NFC', text).translate(str.maketrans({'\xa0': ' ', '\u202f': ' ', '\u200b': '', '\ufeff': '', '％': '%'}))
    return re.sub(r'\s+', ' ', text).strip()


def _term_pattern(term):
    return r'(?<![A-Za-z0-9])' + re.escape(term) + r'(?![A-Za-z0-9])'


def _term_values(text):
    matches = []
    occupied = set()
    applicable = list(TERMS) + [(rule['source'], rule['target']) for rule in CONTEXTUAL_TERMS
                                if re.search(rule['when'], text, re.I)]
    for source, target in sorted(applicable, key=lambda x: len(x[0]), reverse=True):
        for match in re.finditer(_term_pattern(source), text, re.I):
            if any(x in occupied for x in range(match.start(), match.end())):
                continue
            occupied.update(range(match.start(), match.end()))
            matches.append((match.start(), match.end(), source, target))
    return matches


def _decimal(value, scale=''):
    return Decimal(value.replace(',', '').replace('−', '-')) * _FACTORS.get((scale or '').lower(), Decimal(1))


def _format_decimal(value):
    return format(value, 'f').rstrip('0').rstrip('.') if '.' in format(value, 'f') else format(value, 'f')


def _money_display(match):
    raw_number = (match.groupdict().get('sign') or '') + match.group('number')
    value = _decimal(raw_number, match.group('scale'))
    positive = '+' if raw_number.startswith('+') else ''
    currency = _CURRENCIES[match.group('currency').strip().upper()]
    if currency == '¥':
        return match.group(0).strip()  # ¥本身不能区分人民币/日元，不擅自推定。
    for factor, unit in [(Decimal('1e12'), '万亿'), (Decimal('1e8'), '亿'), (Decimal('1e4'), '万')]:
        if abs(value) >= factor:
            return positive + _format_decimal(value / factor) + unit + _CURRENCY_ZH[currency]
    return positive + _format_decimal(value) + _CURRENCY_ZH[currency]


def canonical_source(title):
    text = normalize_title(title)
    replacements = _term_values(text)
    for start, end, _, target in sorted(replacements, reverse=True):
        text = text[:start] + target + text[end:]
    return _MONEY_PREFIX.sub(_money_display, text)


@dataclass(frozen=True)
class ProtectedTitle:
    original: str
    normalized: str
    request_text: str
    tokens: tuple


def protect_title(title):
    """先保护术语、品牌缩写及精确数量，再交给翻译服务调整句法。"""
    text = normalize_title(title)
    replacements = _term_values(text)
    occupied = {i for start, end, _, _ in replacements for i in range(start, end)}
    extra = [(_MONEY_PREFIX, _money_display),
             (re.compile(r'\b(?:18|19|20)\d0s\b'), lambda m: m[0][:-1] + '年代'),
             (re.compile(r'(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9+.-]*\d[A-Za-z0-9+.-]*(?![A-Za-z0-9])'), lambda m: m[0]),
             (re.compile(r'\b(?:USB-C|USB-A|Wi-Fi|[A-Z][A-Z0-9-]{1,}|[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+)\b'), lambda m: m[0]),
             (_NUMBER, lambda m: m[0].strip())]
    for pattern, display in extra:
        for match in pattern.finditer(text):
            if any(i in occupied for i in range(match.start(), match.end())):
                continue
            occupied.update(range(match.start(), match.end()))
            replacements.append((match.start(), match.end(), match[0], display(match)))
    tokens, chunks, at = [], [], 0
    for index, (start, end, _, display) in enumerate(sorted(replacements)):
        # 字母标记不混入数值；响应若损坏任何标记，整条拒用。
        a, b = divmod(index, 26)
        token = 'ZXQ' + chr(65 + a) + chr(65 + b) + 'ZXQ'
        tokens.append((token, display))
        chunks.extend([text[at:start], token])
        at = end
    chunks.append(text[at:])
    return ProtectedTitle(str(title or ''), text, ''.join(chunks), tuple(tokens))


def restore_tokens(candidate, protected):
    text = normalize_title(candidate)
    missing = []
    for token, display in protected.tokens:
        pattern = r'\s*'.join(re.escape(c) for c in token)
        if not re.search(pattern, text, re.I):
            missing.append(token)
        text = re.sub(pattern, lambda _: display, text, flags=re.I)
    if missing or re.search(r'ZXQ[A-Z\s]+ZXQ', text, re.I):
        return '', ['protected_token_lost']
    return text, []


def polish_title(candidate, source=''):
    """只规范格式及源文实际出现的术语，不删作者、不改写句子事实。"""
    text = normalize_title(candidate)
    for _, _, term, target in _term_values(normalize_title(source)):
        text = re.sub(_term_pattern(term), lambda _: target, text, flags=re.I)
    text = re.sub(r'\s+([%，。；：！？、])', r'\1', text)
    text = re.sub(r'([\u3400-\u9fff])\s+(?=[\u3400-\u9fff])', r'\1', text)
    text = re.sub(r'(\d)\s+([%％])', r'\1\2', text)
    text = re.sub(r'([$€£¥])\s+(?=\d)', r'\1', text)
    return text.strip()


def quantity_fingerprint(title):
    """数值、数量级、货币、百分比、单位及符号的精确多重集，允许16.5万=165000。"""
    text = normalize_title(title)
    # 季度是语义编号；第3季度与Q3等价，不能把译法转换误判成新增数值。
    quarters = {'一': '1', '二': '2', '三': '3', '四': '4'}
    text = re.sub(r'第?([一二三四1-4])季度', lambda m: 'Q' + quarters.get(m[1], m[1]), text)
    values, used = [], set()
    for pattern in (_MONEY_PREFIX, _MONEY_SUFFIX):
        for match in pattern.finditer(text):
            if any(i in used for i in range(match.start(), match.end())):
                continue
            used.update(range(match.start(), match.end()))
            currency = _CURRENCIES[match.group('currency').strip().upper()]
            raw_number = (match.groupdict().get('sign') or '') + match.group('number')
            number = str(_decimal(raw_number, match.group('scale')).normalize())
            values.append((('+' if raw_number.startswith('+') else '') + number, currency))
    for match in _NUMBER.finditer(text):
        if any(i in used for i in range(match.start(), match.end())):
            continue
        unit = (match.group('unit') or '').lower()
        unit = _UNIT_CANON.get(unit, unit)
        number = str(_decimal(match.group('number'), match.group('scale')).normalize())
        values.append((('+' if match.group('number').startswith('+') else '') + number, unit))
    return Counter(values)


def _result(title, zh='', status='needs_review', issues=(), provider='', **extra):
    return {'title_zh': zh, 'status': status, 'issues': list(dict.fromkeys(issues)),
            'provider': provider, 'version': TRANSLATION_VERSION,
            'source_hash': hashlib.sha256(normalize_title(title).encode('utf-8')).hexdigest(),
            'fallback': 'original' if not zh else '', 'quality_passed': status in ('translated', 'original'),
            'fact_verified': False, **extra}


def review_translation(title, candidate, *, provider='existing'):
    """离线质检候选。不能可靠修复语义时返回空title_zh，由界面明确回退原题。"""
    source = normalize_title(title)
    if not source:
        return _result(title, status='original', issues=['empty_source'], provider=provider)
    if len(_HAN.findall(source)) >= 2:
        return _result(title, status='original', provider='original')
    raw = str(candidate or '')
    text = polish_title(raw, source)
    issues = []
    if not text:
        issues.append('translation_missing')
    elif _ERROR.search(text) or re.search(r'<(?:html|body|script)\b', raw, re.I):
        issues.append('provider_error_text')
    elif len(_HAN.findall(text)) < 2 or text == source:
        issues.append('not_chinese_translation')
    if text:
        # 数字型清单标题须有名词/量词承接；数字不能直接悬挂在因果/转折连接词前。
        # 同时适用于“5由于…”“10但是…”，不针对某一整句标题。
        if re.search(r'^\d+(?:\.\d+)?\s*(?:由于|因为|因此|所以|但是|然而|不过|尽管|而且|随着|同时|此外|于是)', text):
            issues.append('stray_number_before_connector')
        if (re.search(r'\b(?:strong|robust|solid)\b', source, re.I)
                and re.search(r'(?:报告|财报|业绩|数据)(?:非常|十分|特别|如此|相当|更为|较为|很|依然|仍然|持续|更加)?(?:强烈|凶猛|激烈)', text)):
            issues.append('unnatural_financial_collocation')
        if (re.search(r'\bbiggest moves\b', source, re.I) and re.search(r'\b(?:stocks?|shares?|markets?)\b', source, re.I)
                and re.search(r'涨幅最大|上涨最多|涨得最多|跌幅最大|下跌最多|跌得最多', text)):
            issues.append('undirected_move_changed_to_directional_ranking')
        if re.search(r'\bdiscount rate\b', source, re.I) and re.search(r'\bBoard\b', source) and '董事会' in text:
            issues.append('central_bank_board_mistranslated')
        if (re.search(r'\bpremium\b', source, re.I) and re.search(r'\b(?:JetBlue|airlines?|airways|aviation|flights?)\b', source, re.I)
                and '溢价' in text):
            issues.append('airline_premium_mistranslated')
        if (re.search(r'\bpushed back on\b', source, re.I)
                and re.search(r'(?:打消|消除|化解|解除)(?:了)?[^，。；]{0,12}(?:担忧|忧虑|顾虑)', text)
                and not re.search(r'试图|尝试|力图|希望|旨在', text)):
            issues.append('rebuttal_changed_to_resolved_concern')
        source_has_day = re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?!\d)', source, re.I)
        if (re.search(r'[,，、；;：:]\s*(?:19|20)\d{2}年?\s*[。.]?$', text)
                or re.search(r'(?:日|月)\s*(?:19|20)\d{2}年', text)
                or (source_has_day and re.search(r'(?:19|20)\d{2}年\d{1,2}月\d{1,2}(?![\d日])', text))):
            issues.append('incomplete_or_inverted_chinese_date')
        if len(source) > 30 and len(text) < 6:
            issues.append('translation_too_short')
        if text.endswith(('...', '…')) and not source.endswith(('...', '…')):
            issues.append('truncated_translation')
        for decade in re.findall(r'\b((?:18|19|20)\d0)s\b', source):
            century, within = int(decade) // 100 + 1, int(decade) % 100
            if decade + '年代' not in text and not re.search(str(century) + r'世纪\s*' + str(within) + r'年代', text):
                issues.append('decade_not_preserved')
        try:
            expected = quantity_fingerprint(canonical_source(source))
            actual = quantity_fingerprint(text)
            # 英文four等数词可译成阿拉伯数字；此时额外数字需人工确认，不猜其含义。
            if expected != actual:
                issues.append('quantity_or_unit_changed')
        except (InvalidOperation, KeyError):
            issues.append('quantity_parse_error')
        for _, _, term, target in _term_values(source):
            if target not in text:
                issues.append('term_not_preserved:' + term)
        abbreviations = re.findall(r'\b(?:USB-C|USB-A|Wi-Fi|[A-Z][A-Z0-9-]{1,})\b', source)
        abbreviations += re.findall(r'(?<![A-Za-z])Q[1-4](?!\d)', source)
        for word in abbreviations:
            equivalents = ABBREVIATION_EQUIVALENTS.get(word, [word])
            if not any(term.lower() == word.lower() for term, _ in TERMS) and not any(alias in text for alias in equivalents):
                issues.append('abbreviation_not_preserved:' + word)
        up = bool(re.search(r'\b(?:rise|rises|rose|surge|surges|soar|soars|increase|increases|hike|hikes)\b', source, re.I))
        down = bool(re.search(r'\b(?:fall|falls|fell|drop|drops|decline|declines|slip|slips|decrease|decreases|cut|cuts|slows)\b', source, re.I))
        if up != down:
            opposite = r'下降|下跌|减少|下滑|降息' if up else r'上升|上涨|增加|飙升|加息'
            same = r'上升|上涨|增长|增加|飙升|加息|走高' if up else r'下降|下跌|减少|下滑|降息|放缓|走低'
            if re.search(opposite, text) and not re.search(same, text):
                issues.append('direction_changed')
        if re.search(r'\b(?:not|never|without)\b', source, re.I) and not re.search(r'不|没|未|无|非|否|零', text):
            issues.append('negation_missing')
    return _result(title, '' if issues else text, 'needs_review' if issues else 'translated', issues, provider)


def cache_entry(cache, title):
    """兼容原平面缓存+元信息、迁移工具的版本化entries格式。"""
    cache = cache or {}
    key = normalize_title(title)
    entries = cache.get('entries') if isinstance(cache.get('entries'), dict) else {}
    entry = entries.get(key) or entries.get(str(title))
    if isinstance(entry, dict):
        return entry
    meta = cache.get(CACHE_META_KEY) or {}
    entry = (meta.get('entries') or {}).get(key) if isinstance(meta, dict) else None
    if isinstance(entry, dict):
        return {**entry, 'title_zh': cache.get(key) or cache.get(str(title)) or entry.get('title_zh', '')}
    value = cache.get(key) or cache.get(str(title))
    return {'title_zh': value, 'version': 'legacy', 'provider': 'legacy'} if isinstance(value, str) and value else {}


def store_cache_result(cache, title, result):
    """只存质量通过的正缓存，版本绑定术语表；保持title→str供旧只读消费者兼容。"""
    if result.get('status') != 'translated' or not result.get('title_zh'):
        return
    key = normalize_title(title)
    cache[key] = result['title_zh']
    meta = cache.setdefault(CACHE_META_KEY, {'schema_version': 2, 'entries': {}})
    meta.setdefault('entries', {})[key] = dict(result)


def resolve_cached_title(title, candidate='', cache=None):
    """生成器可直接使用的离线接口；无网络/写入/采集依赖，英文原题从不改写。"""
    entry = cache_entry(cache, title)
    current = entry.get('version') == TRANSLATION_VERSION
    if current:
        result = review_translation(title, entry.get('title_zh'), provider=entry.get('provider', 'cache'))
        if result['status'] == 'translated' and entry.get('source_hash') == result['source_hash']:
            return {**result, 'cache_state': 'current', 'needs_refresh': False}
    chosen = candidate or entry.get('title_zh') or ''
    provider = 'existing_reviewed' if candidate and candidate != entry.get('title_zh') else entry.get('provider') or 'existing'
    result = review_translation(title, chosen, provider=provider)
    return {**result, 'cache_state': 'legacy' if chosen else 'missing', 'needs_refresh': result['status'] != 'original'}
