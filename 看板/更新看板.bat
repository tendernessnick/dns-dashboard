@echo off
rem 一键更新看板数据：全量采集 + 重写 data.js（页面壳不动）
rem 改卡片配置(模块/*.json)/布局.csv/渲染器后才需要另跑 生成看板.py 重建页面壳
chcp 65001 >nul
cd /d "%~dp0..\看板数据固化\采集脚本"
echo ==== 1/2 采集数据（约5-8分钟） ====
python run_all.py
cd /d "%~dp0"
echo ==== 2/2 重写 data.js ====
python 生成数据.py
echo ==== 完成：刷新浏览器即可看到最新数据 ====
pause
