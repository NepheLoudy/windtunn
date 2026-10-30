#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CONCAT body 折叠舵残留终验 — 正确轴映射版 (B 系↔B 系, 无坐标 bug)
参照: 折叠位舵 = 旧 cfd/fin_*.stl (mm STEP 系) → toB 转 B 系米制 → 与 body (B 系米制) 比对"""
import struct, glob
import numpy as np

COM = np.array([-0.1, 0.2, 105.5])
def toB(P):
    out = np.empty_like(P)
    out[:, 0] = -(P[:, 2] - COM[2]) / 1000.0
    out[:, 1] = (P[:, 1] - COM[1]) / 1000.0
    out[:, 2] = (P[:, 0] + 0.1) / 1000.0
    return out

def load(p, step=1, to_b=False):
    d = open(p, 'rb').read()
    n = int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    P = a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64).reshape(-1, 3)
    return toB(P)[::step] if to_b else P[::step]

def near_count(bpts, fpts, tol=0.0006):
    cell = 0.0012
    g = {}
    for p in fpts:
        g.setdefault((int(p[0]/cell), int(p[1]/cell), int(p[2]/cell)), []).append(p)
    hit = 0
    for p in bpts:
        cx, cy, cz = int(p[0]/cell), int(p[1]/cell), int(p[2]/cell)
        found = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q in g.get((cx+dx, cy+dy, cz+dz), ()):
                        if (p[0]-q[0])**2 + (p[1]-q[1])**2 + (p[2]-q[2])**2 < tol*tol:
                            found = True; break
                    if found: break
                if found: break
            if found: break
        hit += found
    return hit

total = 0
for k in (1, 2, 3, 4):
    folded = load('cad/v1/cfd/fin_%d.stl' % k, 2, to_b=True)   # 折叠位参照, 正确转 B 系
    body = load('cad/v1/cfd_parallel/body.stl', 17)
    body = body[(body[:, 0] > -0.115) & (body[:, 0] < -0.075)]
    h = near_count(body, folded)
    total += h
    print('fin_%d 折叠位贴合: %d' % (k, h))
print('=== 残留判定:', 'CLEAN ✓' if total < 60 else ('STILL-DIRTY ✗ (%d)' % total), '(阈值 60) ===')
