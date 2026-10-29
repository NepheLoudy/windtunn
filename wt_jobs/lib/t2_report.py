#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T2 LBM 力数据报告 — 拉 qianli forces.csv (R8b 平行基准), 统计+折叠位对照

输出: out/t2_report.txt + stdout。LBM 单位 (lu), 绝对量级以 FVM 为准 (T2 定位);
本报告看的是趋势: fy 是否归零 (平行基准对称性) / 力是否平稳 (无漂移)。
"""
import os, statistics, subprocess, sys

HERE = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
STATE = os.path.join(HERE, 'state')
OUT = os.path.join(HERE, 'out')
REMOTE = '~/fluidx3d_v3/FluidX3D-master/bin/out/forces.csv'
REMOTE_R8 = '~/fluidx3d_v3/FluidX3D-master/bin/out/forces_r8_folded.csv'

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

def main():
    os.makedirs(STATE, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    f_new = os.path.join(STATE, 'forces_r8b_parallel.csv')
    f_old = os.path.join(STATE, 'forces_r8_folded.csv')
    lines = ['== T2 R8b (平行基准) 力数据报告 — %s ==' % __import__('time').strftime('%m-%d %H:%M')]
    ok = pull(REMOTE, f_new)
    pull(REMOTE_R8, f_old)
    if not ok:
        lines.append('拉取失败 (qianli 不可达或文件不存在)')
    else:
        m_new = stats(rows(f_new), 'R8b body+平行舵组', lines)
        m_old = stats(rows(f_old), 'R8 body-only(无舵对照)', lines)
        if m_new:
            lines.append('fy/fx = %.3f%% — 带舵对称位形的净侧力量级 (手性舵组+阶梯噪声混合;'
                         % (100*abs(m_new[1]/m_new[0]) if m_new[0] else 0))
            lines.append('  舵效的折叠-vs-平行对照以 FVM 红表 CY=-0.13 为准, LBM 薄舵阶梯噪声分辨不了这个)')
        if m_new and m_old:
            lines.append('fy(body+舵)/fy(body-only) = %.3g / %.3g lu — 舵面贡献的侧向残差'
                         % (m_new[1], m_old[1]))
    rep = '\n'.join(lines)
    print(rep)
    open(os.path.join(OUT, 't2_report.txt'), 'w', encoding='utf-8').write(rep + '\n')

if __name__ == '__main__':
    sys.exit(main())
