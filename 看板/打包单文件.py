# -*- coding: utf-8 -*-
"""打包全部已注册部门：共享数据/本地媒体一次内嵌，各页在独立iframe文档执行。

输出仍为 数据看板-单文件版.html；file://与HTTP下均通过父页#page=ID切换。
任何页面或本地媒体缺失即拒绝发布，成功后原子替换；不修改普通页面或原数据。
用法：python 打包单文件.py
"""
import base64
import importlib.util
import json
import mimetypes
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote


BASE = Path(__file__).resolve().parent
OUTPUT_NAME = '数据看板-单文件版.html'
DATA_SCRIPT = re.compile(
    r'<script\b[^>]*\bsrc\s*=\s*([\'\"])(?:\./)?data\.js\1[^>]*>\s*</script\s*>', re.I)
QUOTED_MEDIA = re.compile(r'([\'\"])((?:\./)?媒体/[^\r\n<>]*?)\1')
CSS_MEDIA = re.compile(r'(url\(\s*)((?:\./)?媒体/[^\)\'\"\r\n]+)(\s*\))', re.I)


def _load_page_registry(base):
    """配置模块在调用时加载，导入打包器本身不会读取或改写生产产物。"""
    source = BASE / '页面配置.py'
    spec = importlib.util.spec_from_file_location('_dashboard_page_registry', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_pages(base=str(base))


def _validate_pages(default_id, pages):
    """load_pages已有校验；此处同时保护临时目录/显式配置调用。"""
    ids, files = set(), set()
    for page in pages:
        pid, filename = page.get('ID'), page.get('文件')
        if not isinstance(pid, str) or not pid or pid in ids:
            raise ValueError(f'部门ID无效或重复: {pid!r}')
        if (not isinstance(filename, str) or not filename.lower().endswith('.html')
                or filename in ('.', '..') or re.search(r'[<>:"/\\|?*]', filename)):
            raise ValueError(f'页面文件名不安全: {filename!r}')
        if filename.casefold() in files:
            raise ValueError(f'页面输出文件重复: {filename}')
        ids.add(pid)
        files.add(filename.casefold())
    if not pages or default_id not in ids:
        raise ValueError('默认部门不在页面注册表中')


def _media_uri(relative, base, cache):
    media_root = (base / '媒体').resolve()
    candidate = (base / relative).resolve()
    if not candidate.is_relative_to(media_root):
        raise ValueError(f'本地媒体越出媒体目录: {relative}')
    # 优先精确文件名（文件名可能含%），其次兼容URL百分号编码。
    if not candidate.is_file():
        candidate = (base / unquote(relative)).resolve()
        if not candidate.is_relative_to(media_root):
            raise ValueError(f'本地媒体越出媒体目录: {relative}')
    if not candidate.is_file():
        raise FileNotFoundError(f'打包所需媒体缺失: {relative}')
    if candidate not in cache:
        mime = mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream'
        cache[candidate] = 'data:' + mime + ';base64,' + base64.b64encode(candidate.read_bytes()).decode('ascii')
    return cache[candidate]


def _inline_media(source, base, cache):
    source = QUOTED_MEDIA.sub(
        lambda match: match[1] + _media_uri(match[2], base, cache) + match[1], source)
    return CSS_MEDIA.sub(
        lambda match: match[1] + _media_uri(match[2].rstrip(), base, cache) + match[3], source)


def _b64(source):
    return base64.b64encode(source.encode('utf-8')).decode('ascii')


def _safe_inline_script(source):
    # DOMParser序列化后的内联脚本仍不能包含HTML结束标签，保留JS字符串的原值。
    return re.sub(r'</script', lambda match: '<\\/' + match[0][2:], source, flags=re.I)


ROUTER = r"""
(function(){
  'use strict';
  var payload=JSON.parse(document.getElementById('dashboard-bundle').textContent);
  var byId=new Map(payload.pages.map(function(page){return [page.id,page]}));
  var frame=document.querySelector('[data-dashboard-frame]'),activeId=null;
  function decode(value){
    return new TextDecoder('utf-8').decode(Uint8Array.from(atob(value),function(ch){return ch.charCodeAt(0)}));
  }
  var data=decode(payload.data);
  function selectedId(){
    var id=new URLSearchParams(window.location.hash.slice(1)).get('page');
    return byId.has(id)?id:payload.default;
  }
  function prepare(page){
    var doc=new DOMParser().parseFromString(decode(page.html),'text/html');
    doc.querySelectorAll('base').forEach(function(base){base.remove()});
    var base=doc.createElement('base');base.setAttribute('href','about:srcdoc');doc.head.prepend(base);
    var scripts=Array.from(doc.querySelectorAll('script[src]')).filter(function(script){
      return /^(?:\.\/)?data\.js$/i.test(script.getAttribute('src'));
    });
    if(scripts.length!==1)throw new Error('页面数据脚本引用不唯一');
    scripts[0].removeAttribute('src');scripts[0].textContent=data;
    doc.querySelectorAll('a[data-dashboard-page]').forEach(function(link){
      var target=link.getAttribute('data-dashboard-page');
      if(!byId.has(target))target=payload.default;
      var url=new URL(window.location.href);url.hash='page='+encodeURIComponent(target);
      link.setAttribute('href',url.href);link.setAttribute('target','_top');
      if(target===page.id)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
    });
    return '<!doctype html>\n'+doc.documentElement.outerHTML;
  }
  function render(){
    var id=selectedId();if(id===activeId)return;
    var page=byId.get(id),html=prepare(page);
    frame.setAttribute('title',page.name+' · 数据看板');
    document.title=page.name+' · DNS 数据看板';
    frame.srcdoc=html;activeId=id;
  }
  window.addEventListener('hashchange',render);
  render();
})();
"""


def _wrapper(payload, stamp):
    # 源码以base64存储；配置名称转义<，保证</script>不能提前结束JSON容器。
    encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return (
        f'<!-- 数据看板·单文件快照 ｜ 打包时间: {stamp} ｜ 部门数: {len(payload["pages"])} -->\n'
        '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>DNS 数据看板 · 离线分享</title>'
        '<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#F6F8FB}'
        '[data-dashboard-frame]{display:block;width:100%;height:100vh;height:100dvh;border:0}</style>'
        '</head><body><iframe data-dashboard-frame title="DNS 数据看板"></iframe>'
        '<noscript>请启用JavaScript查看离线数据看板。</noscript>'
        '<script type="application/json" id="dashboard-bundle">' + encoded + '</script>'
        '<script>' + ROUTER + '</script></body></html>\n'
    )


def _write_atomic(output, html):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='',
                                         prefix='.' + output.name + '.', suffix='.tmp',
                                         dir=output.parent, delete=False) as target:
            temp_path = Path(target.name)
            target.write(html)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temp_path, output)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def build_bundle(base=None, default_id=None, pages=None, output=None):
    """完整验证所有输入后才写分享版；显式pages参数用于临时目录测试。"""
    base = Path(base or BASE).resolve()
    if pages is None:
        loaded_default, pages = _load_page_registry(base)
        if default_id is None:
            default_id = loaded_default
    pages = list(pages)
    _validate_pages(default_id, pages)
    output = Path(output) if output is not None else base / OUTPUT_NAME
    cache, embedded = {}, []
    for page in pages:
        path = base / page['文件']
        html = path.read_text(encoding='utf-8')
        if len(DATA_SCRIPT.findall(html)) != 1:
            raise RuntimeError(f'{path.name}: data.js引用缺失或不唯一，请先重建页面')
        html = _inline_media(html, base, cache)
        embedded.append({'id': page['ID'], 'name': page.get('名称') or page['ID'], 'html': _b64(html)})
    data = _safe_inline_script(_inline_media((base / 'data.js').read_text(encoding='utf-8'), base, cache))
    payload = {'default': default_id, 'pages': embedded, 'data': _b64(data)}
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    html = _wrapper(payload, stamp)
    _write_atomic(output, html)
    return {'文件': str(output), '字节': output.stat().st_size,
            '部门数': len(embedded), '媒体数': len(cache), '打包时间': stamp}


if __name__ == '__main__':
    report = build_bundle()
    print('单文件版已生成:', Path(report['文件']).name, report['字节'] // 1024, 'KB',
          f'｜ 部门{report["部门数"]}个 ｜ 内联媒体{report["媒体数"]}张 ｜ 打包时间:', report['打包时间'])
