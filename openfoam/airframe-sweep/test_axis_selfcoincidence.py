#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""转轴仲裁·物理判据 — 轴套自重合测试 (曼波 10-30: 舵根应原地自转, 不离开镖体突起)
原理: 舵根轴套是旋转对称体。绕自身轴线转任意角, 轴套点云形态不变 (自重合)。
     绕偏离轴线的轴转 δ, 轴套中心偏移 ≈ 2·sin(δ/2)·dev — 一测便知轴对不对。
测试: 对三个候选轴 (assembly / STL-Hough / 旧find_hinges), 把轴套区点绕其转 ±30°,
     测转后点云到原点云的最近邻中位距离。谁≈0 谁是真轴。
另外: 网格搜索轴心偏移, 找"自重合最优"的轴心 — 反推真轴位置。"""
import struct, json
import numpy as np

def load(p):
    d = open(p, 'rb').read()
    n = int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    return a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64).reshape(-1, 3)

P = load('cad/v1/cfd_parallel/fin_1.stl')

def nn_med(Q, P, cell=0.001):
    """Q 每点到 P 的最近邻中位距离 (mm)"""
    g = {}
    for p in P:
        g.setdefault((int(p[0]/cell), int(p[1]/cell), int(p[2]/cell)), []).append(p)
    ds = []
    for p in Q:
        cx, cy, cz = int(p[0]/cell), int(p[1]/cell), int(p[2]/cell)
        best = 1e9
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q in g.get((cx+dx, cy+dy, cz+dz), ()):
                        d = (p[0]-q[0])**2+(p[1]-q[1])**2+(p[2]-q[2])**2
                        if d < best: best = d
        if best < 1e8: ds.append(best**0.5)
    return float(np.median(ds)) * 1000.0

def rot(P, point, axis, deg):
    q = np.radians(deg); c, s = np.cos(q), np.sin(q)
    W = P - point
    cr = np.cross(np.broadcast_to(axis, W.shape), W)
    return point + W*c + cr*s + np.outer(W @ axis, axis)*(1-c)

u = np.array([0.0, np.sqrt(.5), np.sqrt(.5)])
e1 = np.array([0.0, np.sqrt(.5), -np.sqrt(.5)])
e2 = np.array([-1.0, 0.0, 0.0])

# 轴套区: 距 assembly 轴线 < 2.6mm 且 |t|<12mm 的点 (圆柱套筒段)
c_asm = np.array([-0.08573, 0.02946, 0.03242])
V = P - c_asm
t = V @ u
rad = np.sqrt(np.clip((V*V).sum(1) - t*t, 0, None))
sleeve = P[(rad < 0.0026) & (np.abs(t) < 0.012)]
print('轴套区点数:', len(sleeve))

def eval_axis(name, c):
    """绕轴 c(±30°) 转轴套, 返回自重合误差 mm; 并做偏移扫描"""
    errs = []
    for deg in (-30, 30):
        Q = rot(sleeve, c, u, deg)
        errs.append(nn_med(Q, sleeve))
    e = max(errs)
    print('%-10s 轴心%s → ±30° 自重合误差 %.3f / %.3f mm  %s' %
          (name, np.round(c, 5), errs[0], errs[1], '← 真轴' if e < 0.15 else ('✗ 偏轴' if e > 0.5 else '~接近')))
    return e

# 三候选
e1v = eval_axis('assembly', c_asm)
hough = json.load(open('bore_axis_independent.json'))['fin_1']['center_B']
e2v = eval_axis('hough  ', np.array(hough))
olds = json.load(open('cad/v1/hinges.json'))
o1 = [h for h in olds if h['part_tag'] == 24][0]
c_old = np.array([-(o1['center_mm'][2]-105.5), o1['center_mm'][1]-0.2, o1['center_mm'][0]+0.1])/1000.0
e3v = eval_axis('old    ', c_old)

# 偏移扫描: 在垂直平面内找自重合最优轴心 (±3mm, 0.1 步)
print('偏移扫描 (找自重合最优轴心):')
best = (1e9, 0.0, 0.0)
for ox in np.arange(-2.5, 2.51, 0.25):
    for oy in np.arange(-2.5, 2.51, 0.25):
        cc = c_asm + ox/1000.0*e1 + oy/1000.0*e2
        Q = rot(sleeve, cc, u, 30)
        e = nn_med(Q, sleeve)
        if e < best[0]: best = (e, ox, oy)
print('最优偏移: (%.2f, %.2f) mm, 误差 %.3f mm' % (best[1], best[2], best[0]))
print('→ 真轴心 B ≈', np.round(c_asm + best[1]/1000.0*e1 + best[2]/1000.0*e2, 5))
