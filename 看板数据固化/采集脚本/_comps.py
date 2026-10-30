# -*- coding: utf-8 -*-
"""竞对同业公司参数表（P201-P234系列共用）。
orgId 为巨潮 topSearch/query 实测值（2026-10-27），仅作兜底，采集器运行时会实时解析。"""
import sys

COMPANIES = {
    '奥海': dict(name='奥海科技', code='002993', org='9900038941'),
    '佳禾': dict(name='佳禾智能', code='300793', org='9900037230'),
    '海能': dict(name='海能实业', code='300787', org='9900030659'),
    '绿联': dict(name='绿联科技', code='301606', org='9900055793'),
    '安克': dict(name='安克创新', code='300866', org='gfbj0839473'),
}


def select(jobs, argv=None):
    """jobs: [(pid:int, 短名:str)]。命令行参数为空→全部；
    否则按P号(201/202…)或股票代码(002993…)过滤，支持带不带P前缀。"""
    argv = [a for a in (argv or sys.argv[1:]) if a]
    if not argv:
        return jobs
    toks = {a.upper().lstrip('P') for a in argv}
    out = [(pid, short) for pid, short in jobs
           if str(pid) in toks or COMPANIES[short]['code'] in argv]
    if not out:
        raise SystemExit(f'参数未匹配到任何P号/代码: {argv}')
    return out
