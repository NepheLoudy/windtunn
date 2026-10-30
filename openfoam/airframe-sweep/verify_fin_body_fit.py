#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3 舵与 body 突起配合验证 — 管壁到 body 表面最近距离分布 (贴合应≈0)
对照 v2 (旧偏心轴生成的舵) 的同指标, 量化修复。"""
import struct, json
import numpy as np

def load(p):
    d = open(p, 'rb').read()
    n = int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    return a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64).reshape(-1, 3)

def nn_stats(Q, P, cell=0.0008):
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
    a = np.array(ds)*1000.0
    return float(np.percentile(a, 10)), float(np.median(a))

# body 尾部点云 (26 件里 x < -0.07 的部段)
body_parts = ['cfd_geom_multi/body_17.stl', 'cfd_geom_multi/body_18.stl',
              'cfd_geom_multi/body_19.stl', 'cfd_geom_multi/body_20.stl']
B = []
for p in body_parts:
    P = load(p)
    B.append(P[(P[:, 0] < -0.07)])
B = np.vstack(B)
print('body 尾段点云:', len(B))

asm = json.load(open('cad/v1/cfd_parallel/airframe_assembly.json', encoding='utf-8'))
for s in asm['control_surfaces']:
    nm = s['name']
    P = load('cad/v1/cfd_parallel/%s.stl' % nm)
    c = np.array(s['hinge_line'][0])
    u = np.array(s['hinge_axis'], float); u /= np.linalg.norm(u)
    V = P - c; t = V @ u
    rad = np.sqrt(np.clip((V*V).sum(1)-t*t, 0, None))*1000.0
    wall = P[(rad > 1.85) & (rad < 2.2)]
    if not len(wall):
        print(nm, '无管壁点'); continue
    p10, med = nn_stats(wall, B)
    print('%s: 管壁点 %d, 到 body 最近距离 p10=%.3fmm 中位=%.3fmm' % (nm, len(wall), p10, med))
