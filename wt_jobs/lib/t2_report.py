#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T2/T3 LBM 队列报告 — 拉 qianli t2_queue_summary.csv, 相位进度+Nx² 归一化对拍

11-03 升级: 旧版只吃 forces.csv (R8b 单例时代); T2 队列 201 例收官后正主是
t2_queue_summary.csv (队列汇总, 每 case 一行)。本报告输出:
  - 相位覆盖 (gate/粗格/细格/种子/长时序) 与最新动态
  - 收敛标尺: 同工况四级网格 fx/Nx² (11-03 翻案: 晶格面积标度律, 归一化后可比)
  - 手性耦合指纹: sign(α)·sign(β) 检查 (大攻角 fy)
forces.csv 通道保留 (长时序时序分析入口)。
"""
import os, statistics, subprocess, sys, time, json

HERE = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
STATE = os.path.join(HERE, 'state')
OUT = os.path.join(HERE, 'out')
REMOTE = '~/fluidx3d_v3/FluidX3D-master/bin/out/forces.csv'
REMOTE_R8 = '~/fluidx3d_v3/FluidX3D-master/bin/out/forces_r8_folded.csv'
REMOTE_SUM = '~/fluidx3d_v3/FluidX3D-master/bin/out/t2_queue_summary.csv'
LOCAL_SUM = os.path.join(STATE, 't2_queue_summary.csv')

def pull(remote, local):
    r = subprocess.run(['wsl.exe', '-e', 'bash', '-lc',
                        "ssh qianli@100.90.63.31 'cat %s 2>/dev/null'" % remote],
                       capture_output=True, text=True, timeout=120)
    if r.returncode == 0 and r.stdout.strip():
        open(local, 'w', newline='').write(r.stdout)
        return True
    return False

def rows(path):
    out = []
    try:
        for ln in open(path):
            p = ln.strip().split(',')
            if len(p) == 7 and p[0] != 't':
                try: out.append(tuple(float(x) for x in p))
                except ValueError: pass
    except FileNotFoundError:
        pass
    return out

def stats(rs, label, lines):
    if len(rs) < 10:
        lines.append('%s: 采样不足 (%d 行)' % (label, len(rs))); return None
    tail = rs[-50:]
    m = [statistics.mean(c[i] for c in tail) for i in (1, 2, 3)]
    s = [statistics.pstdev(c[i] for c in tail) for i in (1, 2, 3)]
    lines.append('%s: %d 采样 (t=%d), 末50点均值 fx=%.3g fy=%.3g fz=%.3g  波动 ±%.2g/±%.2g/±%.2g'
                 % (label, len(rs), int(rs[-1][0]), m[0], m[1], m[2], s[0], s[1], s[2]))
    return m

def load_sum(path):
    """t2_queue_summary.csv → dict 列表 (tag/alpha/beta/nx/seed/nu/V/steps/fx/fy/fz)"""
    out = []
    try:
        import csv as _csv
        with open(path, encoding='utf-8', errors='replace') as f:
            for r in _csv.DictReader(ln for ln in f if ln.startswith(('tag', 'gate', 'c_', 'cs_', 's_', 'f_', 'fs_', 're_', 'm330', 'f440', 'u660', 'x_', 'lt'))):
                try:
                    out.append({'tag': r['tag'], 'alpha': float(r['alpha']), 'beta': float(r['beta']),
                                'nx': int(r['nx']), 'seed': int(r['seed']), 'steps': int(r['steps']),
                                'fx': float(r['fx']), 'fy': float(r['fy']), 'fz': float(r['fz'])})
                except (KeyError, ValueError):
                    pass
    except FileNotFoundError:
        pass
    return out


def phase_of(tag):
    if tag == 'gate': return 'gate'
    if tag.startswith('c_a'): return '粗格分支'
    if tag.startswith('cs_'): return '粗格种子'
    if tag.startswith('s_a'): return '粗格种子'
    if tag.startswith('re_'): return 'Re阶梯'
    if tag.startswith('m330'): return '330收敛'
    if tag.startswith('f440'): return '440收敛'
    if tag.startswith('fs_'): return '细格种子'
    if tag.startswith('f_a'): return '细格分支'
    if tag.startswith('u660'): return '660锚点'
    if tag.startswith('lt'): return '长时序'
    if tag.startswith('x_'): return '对拍批次'
    return '其他'


def sum_report(srows, lines):
    if not srows:
        lines.append('t2_queue_summary 拉取失败或为空'); return
    from collections import Counter
    ph = Counter(phase_of(r['tag']) for r in srows)
    lines.append('队列汇总: %d 例 — %s' % (len(srows), ' '.join('%s=%d' % kv for kv in sorted(ph.items()))))
    # 最新动态 (按文件序即追加序)
    last = srows[-3:]
    for r in last:
        lines.append('  最新: %-18s a=%+6.1f b=%+5.1f nx=%d fx=%9.2f fy=%+8.2f'
                     % (r['tag'], r['alpha'], r['beta'], r['nx'], r['fx'], r['fy']))
    # 收敛标尺: 同工况 (α,β) 多级 nx 的 fx/Nx² (11-03 翻案结论的仪表化)
    ladder = {}
    for r in srows:
        if r['seed'] == 0:
            ladder.setdefault((r['alpha'], r['beta']), {})[r['nx']] = r['fx']
    multi = {k: v for k, v in ladder.items() if len(v) >= 3}
    if multi:
        lines.append('四级收敛标尺 (fx/Nx², 同工况跨网格应同带 ±2%):')
        for (a, b), nxmap in sorted(multi.items()):
            parts = ['nx%d:%.3e' % (nx, fx / nx / nx) for nx, fx in sorted(nxmap.items())]
            lines.append('  a=%+6.1f b=%+5.1f — %s' % (a, b, '  '.join(parts)))
    # 手性指纹: 细格分支 β=±b 的 sign(α)·sign(β) 检查
    fine = {(r['alpha'], r['beta']): r['fy'] for r in srows
            if phase_of(r['tag']) in ('细格分支',) and r['seed'] == 0 and abs(r['beta']) >= 2.5}
    ok = bad = 0
    for (a, b), fy in fine.items():
        if b > 0 and (a, -b) in fine:
            expect = (1 if a > 0 else -1) * (1 if b > 0 else -1)
            actual = 1 if (fy * fine[(a, -b)] < 0) else 0  # fy(b+) 与 fy(b-) 反号
            # 反号=分支锁定下的对称分量; 同号且 sign 一致=手性交叉
            if fy * fine[(a, -b)] < 0:
                ok += 1
            else:
                bad += 1
    if ok + bad:
        lines.append('手性指纹 (细格 β± 反号率): %d/%d — 反号=分支对称分量, 同号=sign(α)sign(β) 交叉' % (ok, ok + bad))


def main():
    os.makedirs(STATE, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    f_new = os.path.join(STATE, 'forces_r8b_parallel.csv')
    f_old = os.path.join(STATE, 'forces_r8_folded.csv')
    lines = ['== T2/T3 LBM 队列报告 — %s ==' % time.strftime('%m-%d %H:%M')]
    ok_sum = pull(REMOTE_SUM, LOCAL_SUM)
    sum_report(load_sum(LOCAL_SUM) if ok_sum else [], lines)
    ok = pull(REMOTE, f_new)
    pull(REMOTE_R8, f_old)
    if not ok:
        lines.append('forces.csv 拉取失败 (qianli 不可达或文件不存在)')
    else:
        m_new = stats(rows(f_new), 'forces.csv 当前/末例', lines)
        m_old = stats(rows(f_old), 'R8 body-only(无舵对照)', lines)
        if m_new and m_old:
            lines.append('fy(body+舵)/fy(body-only) = %.3g / %.3g lu — 舵面贡献的侧向残差'
                         % (m_new[1], m_old[1]))
    rep = '\n'.join(lines)
    print(rep)
    open(os.path.join(OUT, 't2_report.txt'), 'w', encoding='utf-8').write(rep + '\n')

if __name__ == '__main__':
    sys.exit(main())
