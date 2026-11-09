# -*- coding: utf-8 -*-
"""
打包单文件：页面壳 + data.js 内联 → 数据看板-单文件版.html
用于发给同事：单个HTML文件、离线可用，双击即看。
文件头注释内嵌打包时间，用于分辨不同时点的快照（数据截至看板页内治理标注）。
v18.9：图文照片已外置到 看板/媒体/（data.js只存相对路径），打包时把 媒体/ 引用
内联回dataURI，单文件版离线能力不损失；本机看 index.html 则需 媒体/ 目录随行（生成数据.py自动重建）。
用法：python 打包单文件.py
"""
import base64
import os
import re
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(BASE, 'index.html')
DATA = os.path.join(BASE, 'data.js')
OUT = os.path.join(BASE, '数据看板-单文件版.html')

TAG = '<script src="data.js"></script>'
shell = open(SHELL, encoding='utf-8').read()
data = open(DATA, encoding='utf-8').read()
if TAG not in shell:
    raise RuntimeError('页面壳中未找到 data.js 引用，请先运行 生成看板.py 重建壳')


def _inline_media(m):
    """媒体/<pid>/<name>.jpg → dataURI（文件缺失时原样保留，卡面有占位兜底）。"""
    fp = os.path.join(BASE, m.group(1).replace('/', os.sep))
    if not os.path.exists(fp):
        return m.group(0)
    with open(fp, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    return '"data:image/jpeg;base64,' + b64 + '"'


n_media = len(re.findall(r'"媒体/[^"]+\.jpg"', data))
data = re.sub(r'"(媒体/[^"]+\.jpg)"', _inline_media, data)
html = shell.replace(TAG, '<script>\n' + data + '\n</script>', 1)
stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
html = '<!-- 数据看板·单文件快照 ｜ 打包时间: %s ｜ 数据截至见看板页内治理标注 -->\n' % stamp + html
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print('单文件版已生成:', os.path.basename(OUT), os.path.getsize(OUT) // 1024, 'KB',
      f'｜ 内联媒体{n_media}张 ｜ 打包时间:', stamp)
