"""部门视图注册与输入校验；构建期读取，不依赖浏览器fetch本地JSON。"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent


def local_file(base, name, suffix):
    if not isinstance(name, str) or not name or '/' in name or '\\' in name:
        raise ValueError(f'只允许同目录文件名：{name!r}')
    target = (base / name).resolve()
    if target.parent != base.resolve() or target.suffix != suffix:
        raise ValueError(f'文件路径或扩展名无效：{name!r}')
    return target


def load_pages(base=None):
    base = Path(base) if base is not None else BASE
    config = json.loads((base / '页面.json').read_text(encoding='utf-8-sig'))
    pages = config.get('页面')
    if not isinstance(pages, list) or not pages:
        raise ValueError('页面.json必须含非空的“页面”列表')
    ids, outputs = set(), set()
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError('页面配置必须是对象')
        pid = page.get('ID', '')
        if not isinstance(pid, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', pid):
            raise ValueError(f'页面ID无效：{pid!r}')
        if pid in ids:
            raise ValueError(f'页面ID重复：{pid}')
        ids.add(pid)
        filename = page.get('文件')
        local_file(base, filename, '.html')
        if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]*\.html', filename):
            raise ValueError(f'页面文件须为简洁英文HTML文件名：{filename!r}')
        if filename.casefold() in outputs:
            raise ValueError(f'页面输出文件重复：{filename}')
        outputs.add(filename.casefold())
        layout = local_file(base, page.get('布局'), '.csv')
        if not layout.is_file():
            raise ValueError(f'页面布局文件不存在：{layout.name}')
        for field in ('名称', '标题', '副标题', '眉标', '定位', '说明'):
            if not isinstance(page.get(field), str) or not page[field].strip():
                raise ValueError(f'{pid}缺少有效的{field}')
        for field in ('使用布局跨列', '速览'):
            if field in page and not isinstance(page[field], bool):
                raise ValueError(f'{pid}.{field}必须为布尔值')
    default = config.get('默认页面')
    if default not in ids:
        raise ValueError('默认页面没有登记在页面列表中')
    return default, pages
