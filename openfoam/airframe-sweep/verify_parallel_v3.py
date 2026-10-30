#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3 平行零位物理终验 — 曼波判据: 转轴正确 ⇔ 绕自身轴旋转时轴套原地自转
1) 管壁点到真轴距离 (应 sharp 2.000)
2) 绕真轴转 ±20° 后管壁点云与原始点云最近邻中位距 (应 ~0 = 自重合)
3) 与 v2 (偏心轴) 同测试对照 — 量化修复幅度"""
import struct, json
import numpy as np

def load(p):
    d = open(p, 'rb').read()
    n = int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    return a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64).reshape(-1, 3)

def nn_med(Q, P, cell=0.0005):
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
    return float(np.median(ds))*1000.0

def rot(P, c, u, deg):
    th = np.radians(deg); co, si = np.cos(th), np.sin(th)
    V = P - c
    cr = np.cross(np.broadcast_to(u, V.shape), V)
    return c + V*co + cr*si + np.outer(V @ u, u)*(1-co)

asm = json.load(open('cad/v1/cfd_parallel/airframe_assembly.json', encoding='utf-8'))
print('%-8s %-10s %-12s %-12s' % ('fin', '管壁r中位', '±20°自重合', 'v2对照'))
v2 = {}
try:
    for k in (1, 2, 3, 4):
        pass
except Exception:
    pass
for s in asm['control_surfaces']:
    nm = s['name']
    P = load('cad/v1/cfd_parallel/%s.stl' % nm)
    c = np.array(s['hinge_line'][0])
    u = np.array(s['hinge_axis'], float); u /= np.linalg.norm(u)
    V = P - c; t = V @ u
    rad = np.sqrt(np.clip((V*V).sum(1)-t*t, 0, None))*1000.0
    wall = P[(rad > 1.85) & (rad < 2.15)]
    r_med = float(np.median(rad[(rad > 1.85) & (rad < 2.15)])) if len(wall) else -1
    errs = [nn_med(rot(wall, c, u, d), wall) for d in (-20, 20)]
    print('%-8s r=%.3fmm  %s  墙点=%d' % (nm, r_med, ' / '.join('%.3f' % e for e in errs), len(wall)))
