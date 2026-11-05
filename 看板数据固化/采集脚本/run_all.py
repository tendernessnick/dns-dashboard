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

# 东财push2行情族（来源归一期P-C4）：单IP渐进式限流，组内采集器间保持≥8s间隔
EM_HEAVY = {'22', '23', '27', '30', '31', '32', '39', '40', '52'}

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
        m = re.match(r'collect_P(\d+)', f)  # 只取数字段
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
        time.sleep(8 if pid in EM_HEAVY else 1)
    ok = sum(1 for r in results if r[2] == '成功')
    skip = sum(1 for r in results if r[2] == '跳过')
    fail = len(results) - ok - skip
    print(f'\n==== 汇总：共{len(results)} 成功{ok} 跳过{skip} 失败{fail} ====')
    for r in results:
        if r[2] != '成功':
            print(f'  [{r[2]}] {r[0]} {r[1]}: {r[3][:150]}')
    write_state(run_id, only, ok, skip, fail, results)


def write_state(run_id, only, ok, skip, fail, results):
    """v17：采集状态快照（_采集状态.json，机器可读）——连续失败计数跨run累加，供新鲜度/告警消费。"""
    import json
    state_fp = os.path.join(os.path.dirname(HERE), '_采集状态.json')
    streaks = {}
    try:
        with open(state_fp, encoding='utf-8') as f:
            for pid, s in (json.load(f).get('词条') or {}).items():
                streaks[pid] = int(s.get('连续失败', 0))
    except Exception:
        pass
    entries = {}
    for pid, mod, status, detail, elapsed in results:
        st = streaks.get(pid, 0)
        entries[pid] = {'名称': mod, '状态': status, '耗时秒': elapsed,
                        '连续失败': (st + 1) if status == '失败' else 0,
                        '详情': detail[:120]}
    import datetime
    with open(state_fp, 'w', encoding='utf-8') as f:
        json.dump({'run_id': run_id,
                   '结束时间': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   '范围': '全量' if not only else '指定:' + ','.join(sorted(only)),
                   '汇总': {'成功': ok, '跳过': skip, '失败': fail},
                   '词条': entries}, f, ensure_ascii=False, indent=1)
    print('采集状态已写:', os.path.basename(state_fp),
          '| 连续失败≥2:', [p for p, e in entries.items() if e['连续失败'] >= 2] or '无')

if __name__ == '__main__':
    main()
