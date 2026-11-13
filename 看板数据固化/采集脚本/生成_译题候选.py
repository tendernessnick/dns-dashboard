"""仅输出译题候选与质量元信息；不写原资讯/缓存/图文，默认离线。

例：python -B -X utf8 生成_译题候选.py --allow-network --limit 20 --output <会话目录>/translation-candidates.json
--input 可重复指定资讯JSON；默认仅财经新闻和地缘政治。--cache 可重复加入已有候选缓存。
"""
import argparse
import datetime
import json
from pathlib import Path
import sys

import _news_translation as quality

BASE = Path(__file__).resolve().parents[1]


def _articles(value):
    if isinstance(value, dict):
        if isinstance(value.get('title'), str) and value['title'].strip():
            yield value
        for item in value.values():
            yield from _articles(item)
    elif isinstance(value, list):
        for item in value:
            yield from _articles(item)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', action='append', type=Path)
    parser.add_argument('--cache', action='append', type=Path, default=[])
    parser.add_argument('--include-cached-titles', action='store_true', help='同时审阅旧缓存原题，仍受limit限制')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-network', action='store_true', help='显式开启公开翻译端点，仅翻译标题，不采集新闻')
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 100:
        parser.error('--limit须为1到100，防止意外扩大网络调用')
    inputs = args.input or [BASE / '资讯数据' / '财经新闻.json', BASE / '资讯数据' / '地缘政治.json']
    caches = [BASE / '资讯数据' / '翻译缓存.json', *args.cache]
    output = args.output.resolve()
    if output.suffix.lower() != '.json' or output.exists():
        parser.error('输出须为尚不存在的候选JSON，禁止覆盖已有文件')
    if any(output.is_relative_to((BASE / folder).resolve()) for folder in ('资讯数据', '图文数据', 'CSV数据')):
        parser.error('候选输出不得位于生产资讯、图文或CSV目录')
    if output in {p.resolve() for p in [*inputs, *caches]}:
        parser.error('候选输出不得覆盖输入或原缓存')
    runtime_cache = {}
    for path in caches:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if isinstance(data, dict) and isinstance(data.get('entries'), dict):
            for title, entry in data['entries'].items():
                if isinstance(entry, dict) and entry.get('version') == quality.TRANSLATION_VERSION:
                    quality.store_cache_result(runtime_cache, title, entry)
        elif isinstance(data, dict):
            runtime_cache.update(data)
    articles = []
    seen = set()
    for path in inputs:
        for item in _articles(json.loads(path.read_text(encoding='utf-8-sig'))):
            source = item['title']  # 原文不经清洗覆写。
            key = quality.normalize_title(source)
            if key in seen or quality.review_translation(source, '')['status'] == 'original':
                continue
            seen.add(key)
            articles.append((source, item.get('title_zh', '')))
    if args.include_cached_titles:
        for source, candidate in runtime_cache.items():
            if not isinstance(candidate, str):
                continue
            key = quality.normalize_title(source)
            if key in seen or quality.review_translation(source, '')['status'] == 'original':
                continue
            seen.add(key)
            articles.append((source, candidate))
    entries = {}
    if args.allow_network:
        # 只有显式联网路径才导入采集网络依赖；离线路径不依赖它们。
        from _news_common import translate_title_result
    for source, candidate in articles[:args.limit]:
        if args.allow_network:
            result = translate_title_result(source, runtime_cache, allow_network=True, existing_title_zh=candidate)
        else:
            result = quality.resolve_cached_title(source, candidate, runtime_cache)
        entries[quality.normalize_title(source)] = {**result, 'source_title': source}
        print(json.dumps({'title': source, 'title_zh': result['title_zh'], 'status': result['status'],
                          'issues': result['issues'], 'provider': result['provider']}, ensure_ascii=False), flush=True)
    payload = {'schema_version': 2, 'translation_version': quality.TRANSLATION_VERSION,
               'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
               'network_allowed': args.allow_network, 'inputs': [str(p.resolve()) for p in inputs],
               'total_english_titles': len(articles), 'processed': len(entries),
               'counts': {state: sum(e['status'] == state for e in entries.values())
                          for state in ('translated', 'needs_review', 'original')},
               'entries': entries}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(json.dumps({'output': str(output), 'counts': payload['counts']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
