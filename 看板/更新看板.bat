@echo off
rem 一键更新看板数据：全量采集 + 评测图文同步(P91) + 重写 data.js（页面壳不动）
rem 改卡片配置(模块/*.json)/布局.csv/渲染器后才需要另跑 生成看板.py 重建页面壳
rem v18.9：逐步检查errorlevel——采集失败不再打印"完成"误导（最终以run_all汇总与data.js行为准）
chcp 65001 >nul
cd /d "%~dp0..\看板数据固化\采集脚本"
echo ==== 1/3 采集数据（约5-8分钟） ====
python run_all.py
if errorlevel 1 (
  echo [警告] run_all 退出码非0，请查看上方汇总中的失败词条
)
cd /d "%~dp0..\看板数据固化\图文数据\我爱音频网评测"
echo ==== 2/3 同步评测图文（P91，源：标准化任务每日评测） ====
python 同步构建.py
if errorlevel 1 (
  echo [警告] 同步构建失败（备用通道，主脚本采集不受影响）
)
cd /d "%~dp0"
echo ==== 3/3 重写 data.js ====
python 生成数据.py
if errorlevel 1 (
  echo [错误] data.js 生成失败，看板数据未更新！
  pause
  exit /b 1
)
echo ==== 完成：刷新浏览器即可看到最新数据 ====
pause
