# -*- coding: utf-8 -*-
"""批量运行采集器：python run_all.py [P01 P26 ...]（不传参数则运行全部 collect_P*.py）
每个采集器须暴露 run() -> (状态, 详情)，状态 ∈ 成功/失败/跳过"""
import importlib
import os
import re
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common

def main():
    only = {str(int(a.upper().lstrip('P'))) for a in sys.argv[1:]} if len(sys.argv) > 1 else None
    run_id = common.begin_run()
    print(f'==== run_id={run_id} ====')
    files = sorted(f for f in os.listdir(HERE)
                   if f.startswith('collect_P') and f.endswith('.py'))
    if not files:
        print('未发现任何 collect_P*.py 采集器')
        return
    results = []
    for f in files:
        m = re.match(r'collect_P(\d+)', f)  # 只取数字段，兼容 P43_huanji / P84b 等命名
        pid = m.group(1) if m else f[len('collect_P'):].split('_')[0]
        if only and pid.lstrip('0') not in only:
            continue
        mod_name = f[:-3]
        t0 = time.time()
        try:
            mod = importlib.import_module(mod_name)
            status, detail, _elapsed = common.run_collector(mod)
        except Exception as e:  # noqa: BLE001
            status, detail = '失败', f'异常: {e}'
        results.append((f'P{pid}', mod_name, status, detail, round(time.time() - t0, 1)))
        print(f'[{status}] {mod_name}  {detail[:80]}  ({results[-1][4]}s)')
        time.sleep(1)
    ok = sum(1 for r in results if r[2] == '成功')
    skip = sum(1 for r in results if r[2] == '跳过')
    fail = len(results) - ok - skip
    print(f'\n==== 汇总：共{len(results)} 成功{ok} 跳过{skip} 失败{fail} ====')
    for r in results:
        if r[2] != '成功':
            print(f'  [{r[2]}] {r[0]} {r[1]}: {r[3][:150]}')

if __name__ == '__main__':
    main()
