# -*- coding: utf-8 -*-
"""批量运行采集器：python run_all.py [P01 P26 ...]（不传参数则运行全部 collect_P*.py）
v18.8改子进程调度：每个采集器独立python进程，超时真正kill（旧线程池超时后僵尸线程
卡在socket里、非daemon线程在解释器退出时被join，整批收尾无限期挂死——Kickstarter慢拦截
549s案例的结构性根源）。子进程内采集器仍走run_collector包装器自行记录采集日志；
超时/异常退出的条目由本调度器补记。批次run_id经环境变量透传给子进程日志。
每个采集器须暴露 run() -> (状态, 详情)，状态 ∈ 成功/失败/跳过"""
import ast
import datetime
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common

# 东财push2行情族（来源归一期P-C4）：单IP渐进式限流，组内采集器间保持≥8s间隔
EM_HEAVY = {'22', '23', '27', '30', '31', '32', '39', '40', '52'}
# 每P号子进程超时秒数（v18.8；未列出的用默认）。93=Kickstarter CF慢拦截合法长跑
# （2026-11-05实测549s最终成功）；95=证监局多指纹重试；69=FRED三通道兜底；
# 4=财政部3年CSV慢站重试+FRED API备用兜底（2026-11-10实测连两次180s超时，财政部时慢时断）
TIMEOUTS = {'93': 620, '95': 300, '69': 300, '4': 420}
DEFAULT_TIMEOUT = 180
LOCK_STALE_SEC = 7200   # 陈旧锁判定（上次异常退出残留）


def _lock_acquire():
    """跨进程单例锁：bat双开/手动与计划任务并跑时防CSV互踩（v18.8）。返回锁路径或None(退出)。"""
    fp = os.path.join(HERE, '_run_all.lock')
    if os.path.exists(fp):
        try:
            age = time.time() - os.path.getmtime(fp)
            if age < LOCK_STALE_SEC:
                old = ''
                try:
                    with open(fp, encoding='utf-8') as f:
                        old = f.read().strip()
                except OSError:
                    pass
                print(f'已有run_all在运行(pid={old or "?"}，{int(age)}s前启动)，本次退出防CSV互踩')
                return None
        except OSError:
            pass
        try:
            os.remove(fp)   # 陈旧锁自动失效
        except OSError:
            pass
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(str(os.getpid()))
    return fp


def _parse_child_output(out, returncode):
    """子进程stdout末行的 ('状态','详情') 元组解析；解析不出按退出码兜底。"""
    text = (out or '').strip()
    if text:
        last = text.splitlines()[-1].strip()
        if last.startswith('('):
            try:
                t = ast.literal_eval(last)
                if isinstance(t, tuple) and len(t) == 3:
                    return t[0], str(t[1])
                if isinstance(t, tuple) and len(t) == 2:
                    return t[0], str(t[1])
            except Exception:  # noqa: BLE001
                pass
        return ('成功' if returncode == 0 else '失败'), text[-150:]
    return ('成功' if returncode == 0 else '失败'), f'无输出, 退出码{returncode}'


def main():
    lock = _lock_acquire()
    if lock is None:
        return
    only = set()
    for a in sys.argv[1:]:
        m = re.match(r'^P?(\d+)([a-z]?)$', a, re.IGNORECASE)   # 后缀大小写不敏感（P90b/P90B均可）
        only.add((m.group(1) + m.group(2).lower()) if m else a.upper().lstrip('P'))
    only = only or None
    run_id = common.begin_run()
    os.environ[common.RUN_ID_ENV] = run_id
    print(f'==== run_id={run_id} ====')
    files = sorted(f for f in os.listdir(HERE)
                   if f.startswith('collect_P') and f.endswith('.py'))
    if not files:
        print('未发现任何 collect_P*.py 采集器')
        os.remove(lock)
        return
    results = []
    for f in files:
        m = re.match(r'collect_P(\d+)([a-z]?)', f)  # 数字段+可选字母后缀（P90b=v19.2状态键分离）
        pid = (m.group(1) + (m.group(2) or '')) if m else f[len('collect_P'):].split('_')[0]
        if only and pid.lstrip('0') not in only:
            continue
        t0 = time.time()
        timeout = TIMEOUTS.get(pid.lstrip('0'), DEFAULT_TIMEOUT)
        status = detail = None
        try:
            proc = subprocess.Popen(
                [sys.executable, '-X', 'utf8', os.path.join(HERE, f)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=HERE, text=True, encoding='utf-8', errors='replace',
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
            try:
                out, _ = proc.communicate(timeout=timeout)
                status, detail = _parse_child_output(out, proc.returncode)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    out, _ = proc.communicate(timeout=10)
                except Exception:  # noqa: BLE001
                    out = ''
                status, detail = '失败', f'超时(>{timeout}s)已终止(子进程)'
                common.log_result(pid.lstrip('0'), f, status, detail,
                                  elapsed=round(time.time() - t0, 1), backfill='latest')
        except Exception as e:  # noqa: BLE001
            status, detail = '失败', f'调度异常: {e}'
            common.log_result(pid.lstrip('0'), f, status, detail,
                              elapsed=round(time.time() - t0, 1), backfill='latest')
        results.append((f'P{pid}', f[:-3], status, detail, round(time.time() - t0, 1)))
        print(f'[{status}] {f[:-3]}  {detail[:80]}  ({results[-1][4]}s)')
        time.sleep(8 if pid in EM_HEAVY else 1)
    ok = sum(1 for r in results if r[2] == '成功')
    skip = sum(1 for r in results if r[2] == '跳过')
    silent = sum(1 for r in results if r[2] == '静默')
    fail = len(results) - ok - skip - silent
    print(f'\n==== 汇总：共{len(results)} 成功{ok} 静默{silent} 跳过{skip} 失败{fail} ====')
    for r in results:
        if r[2] != '成功':
            print(f'  [{r[2]}] {r[0]} {r[1]}: {r[3][:150]}')
    write_state(run_id, only, ok, skip, fail, results)
    write_news_health(results)
    if not only:
        # v19：全量批次尾部自动跑双源对照（12对，逐对阈值），结果入 核验状态.json（对照段）
        try:
            import cross_check
            vstatus, vdetail, _summary = cross_check.run_checks()
            print(f'[核验对照] {vstatus}: {vdetail}')
        except Exception as e:  # noqa: BLE001
            print(f'[核验对照] 失败(不影响采集结果): {e}')
    try:
        os.remove(lock)
    except OSError:
        pass


def write_state(run_id, only, ok, skip, fail, results):
    """v17：采集状态快照（_采集状态.json，机器可读）——连续失败计数跨run累加，供新鲜度/告警消费。
    v18.7：先继承旧文件全部条目再覆盖本次涉及的P号——子集运行（如手动跑单个采集器）
    不再把其余词条的状态与连续失败计数整体抹掉。"""
    import json
    state_fp = os.path.join(os.path.dirname(HERE), '_采集状态.json')
    streaks = {}
    entries = {}
    try:
        with open(state_fp, encoding='utf-8') as f:
            for pid, s in (json.load(f).get('词条') or {}).items():
                streaks[pid] = int(s.get('连续失败', 0))
                entries[pid] = s
    except Exception:
        pass
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
                   '汇总': {'成功': ok, '静默': sum(1 for r in results if r[2] == '静默'),
                           '跳过': skip, '失败': fail},
                   '词条': entries}, f, ensure_ascii=False, indent=1)
    print('采集状态已写:', os.path.basename(state_fp),
          '| 连续失败≥2:', [p for p, e in entries.items() if e['连续失败'] >= 2] or '无')
    # v19：存疑事件并入 核验状态.json（看板附录「最近核验」徽标消费）；已恢复的词条清除旧记录
    # v19.2修正：只扫本次运行的 results——继承自旧状态文件的条目不参与（修复前的噪音残留不会复活）
    vfp = os.path.join(os.path.dirname(HERE), '核验状态.json')
    try:
        with open(vfp, encoding='utf-8') as f:
            vst = json.load(f)
    except Exception:
        vst = {}
    sus = [(pid, d) for pid, _mod, _st, d, _el in results if '⚠存疑' in d]
    vst.setdefault('存疑', {})
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for pid, d in sus:
        vst['存疑'][pid] = {'最近': now, '说明': d.split('⚠存疑:')[-1][:160]}
    for pid in {p for p, *_ in results} - {p for p, _ in sus}:
        vst['存疑'].pop(pid, None)          # 本次运行无存疑→清除历史告警（恢复即消警）
    if sus:
        print('存疑告警已并入 核验状态.json:', [p for p, _ in sus])
    vst['更新时间'] = now
    with open(vfp, 'w', encoding='utf-8', ) as f:
        json.dump(vst, f, ensure_ascii=False, indent=1)


# v20资讯治理A2：内容feed按"最新条目日期"判新鲜（item模式），API快照feed按"采集时间"判（collect模式）
NEWS_COLLECT_MODE = {'P84', 'P93', 'P94', 'P96'}   # 问答/榜单类：无新条目是常态，看采集是否停滞
NEWS_FRESH_LIM = {'每日': 3}                        # 其余更新频率默认7天


def write_news_health(results):
    """v20资讯治理A2：注册表驱动扫描 资讯数据/*.json → 核验状态.json['资讯']（附录徽标消费）。
    item模式: 最新条目距今超阈值→sus（P59式源静默、关键词漂移都从这里暴露）；
    collect模式: 文件updated距今>3天→warn（采集停滞；P96多文件取最差）。
    本次运行结果为"失败"的资讯P号直接warn（fetch异常即时可见，不等阈值）。
    每次调用全量重算（无跨run状态，幂等）。"""
    import csv as _csv
    import datetime
    import json
    base = os.path.dirname(HERE)
    reg_fp = os.path.join(base, '词条注册表.csv')
    news_dir = os.path.join(base, '资讯数据')
    now = datetime.datetime.now()
    try:
        with open(reg_fp, encoding='utf-8-sig', newline='') as f:
            rows = list(_csv.DictReader(f))
    except Exception:
        return
    rank = {'ok': 0, 'warn': 1, 'sus': 2}
    ent = {}
    for r in rows:
        pid = (r.get('P号') or '').strip()
        files = [x.strip() for x in (r.get('资讯文件') or '').split(';') if x.strip()]
        if not files:
            continue
        lim = NEWS_FRESH_LIM.get((r.get('更新频率') or '').strip(), 7)
        worst = None
        for fn in files:
            try:
                d = json.load(open(os.path.join(news_dir, fn), encoding='utf-8'))
            except Exception:
                cand = ('warn', f'{fn} 读取失败（缺失或损坏）')
            else:
                items = d.get('items') or []
                if pid in NEWS_COLLECT_MODE:
                    upd = (d.get('updated') or '')[:10]
                    try:
                        dd = (now.date() - datetime.date.fromisoformat(upd)).days
                    except Exception:
                        dd = 99
                    cand = ('ok', f'采集正常({upd[5:]})') if dd <= 3 else \
                           ('warn', f'采集停滞{dd}天(>3) 更新于{upd[5:]}')
                elif not items:
                    cand = ('sus', f'{fn} 近7天窗内0条（源静默或关键词待校）')
                else:
                    isos = [str(i.get('iso') or '') for i in items]
                    if not all(isos):
                        from _news_common import _mmdd_to_iso
                        isos = [x or _mmdd_to_iso(i.get('date', ''), now) for x, i in zip(isos, items)]
                    iso = max(isos)
                    try:
                        dd = (now.date() - datetime.date.fromisoformat(iso)).days
                    except Exception:
                        dd = 99
                    cand = ('ok', f'最新条目{iso[5:]}') if dd <= lim else \
                           ('sus', f'最新条目{iso[5:]} 距今{dd}天(>{lim}天阈值)')
            if worst is None or rank[cand[0]] > rank[worst[0]]:
                worst = cand
        for p, _m, st, dtl, _e in results:
            if p == pid and st == '失败':
                worst = ('warn', '本次采集异常: ' + dtl[:80])
                break
        ent[pid] = {'级别': worst[0], '说明': worst[1][:120],
                    '最近': now.strftime('%Y-%m-%d %H:%M')}
    vfp = os.path.join(base, '核验状态.json')
    try:
        with open(vfp, encoding='utf-8') as f:
            vst = json.load(f)
    except Exception:
        vst = {}
    vst['资讯'] = ent
    vst['更新时间'] = now.strftime('%Y-%m-%d %H:%M')
    payload = json.dumps(vst, ensure_ascii=False, indent=1)   # 先序列化再落盘：防半途异常截断状态文件
    with open(vfp, 'w', encoding='utf-8') as f:
        f.write(payload)
    flagged = [p for p, e in ent.items() if e['级别'] != 'ok']
    print('资讯健康已写 核验状态.json | 喂入', len(ent), 'feed | 异常:',
          flagged or '无')


if __name__ == '__main__':
    try:
        main()
    finally:
        # v20资讯治理A2加固：异常路径也立即解锁（只清自己持有的锁，双开场景不误删他人锁）
        _lk = os.path.join(HERE, '_run_all.lock')
        if os.path.exists(_lk):
            try:
                with open(_lk, encoding='utf-8') as f:
                    if f.read().strip() == str(os.getpid()):
                        os.remove(_lk)
            except OSError:
                pass
