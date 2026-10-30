# -*- coding: utf-8 -*-
"""
打包单文件 v12：页面壳 + data.js 内联 → 数据看板-单文件版.html
用于发给同事：单个HTML文件、离线可用，双击即看（数据为打包时刻的快照）。
用法：python 打包单文件.py
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(BASE, 'index.html')
DATA = os.path.join(BASE, 'data.js')
OUT = os.path.join(BASE, '数据看板-单文件版.html')

TAG = '<script src="data.js"></script>'
shell = open(SHELL, encoding='utf-8').read()
data = open(DATA, encoding='utf-8').read()
if TAG not in shell:
    raise RuntimeError('页面壳中未找到 data.js 引用，请先运行 生成看板.py 重建壳')
html = shell.replace(TAG, '<script>\n' + data + '\n</script>', 1)
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print('单文件版已生成:', os.path.basename(OUT), os.path.getsize(OUT) // 1024, 'KB')
