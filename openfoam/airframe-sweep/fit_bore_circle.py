#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第三条路仲裁: fin STL 孔面点条件筛选 + 逐切片圆拟合 (不依赖 Hough 峰)
对每片舵: 取距现轴 r∈[1.3,1.95] 的根部点 → 沿轴切片(1mm) → 每片平面圆拟合 →
圆心串 TLS 直线 = 孔轴 → 与 assembly / Hough 两版对比。"""
import json, math
import numpy as np
import struct

def load_verts(p):
    d = open(p, 'rb').read()
    n = int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    return a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64).reshape(-1, 3)

asm = json.load(open('cad/v1/cfd_parallel/airframe_assembly.json', encoding='utf-8'))
hough = json.load(open('bore_axis_independent.json'))
out = {}
for i, s in enumerate(asm['control_surfaces'], 1):
    name = s['name']
    P = load_verts('cad/v1/cfd_parallel/%s.stl' % name)
    ax = np.array(s['hinge_axis'], float); ax /= np.linalg.norm(ax)
    ref = np.array(s['hinge_line'][0], float)
    V = P - ref
    t = V @ ax
    rad = np.sqrt(np.clip((V*V).sum(1) - t*t, 0, None)) * 1000.0
    band = (rad > 2.0) & (rad < 2.9) & (np.abs(t) < 0.014)  # 轴套外圆柱: 点多弧长长, 拟合最稳
    Q = P[band]
    if len(Q) < 30:
        print('%s: 带内点不足 %d' % (name, band.sum())); continue
    e1 = np.cross(ax, [1.0, 0, 0])
    if np.linalg.norm(e1) < 1e-6: e1 = np.cross(ax, [0, 1.0, 0])
    e1 /= np.linalg.norm(e1); e2 = np.cross(ax, e1)
    centers = []
    nb = 8
    tmin, tmax = t[band].min(), t[band].max()
    for k in range(nb):
        lo = tmin + (tmax-tmin)*k/nb; hi = tmin + (tmax-tmin)*(k+1)/nb
        m = band & (t >= lo) & (t <= hi)
        if m.sum() < 6: continue
        W = P[m] - (ref + 0.5*(lo+hi)*ax)
        uu = W @ e1; vv = W @ e2
        A = np.column_stack([2*uu, 2*vv, np.ones(m.sum())])
        b = uu*uu + vv*vv
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        rr = math.sqrt(max(sol[2] + sol[0]**2 + sol[1]**2, 0))
        centers.append(ref + 0.5*(lo+hi)*ax + sol[0]*e1 + sol[1]*e2)
        if k == nb//2:
            pass
    C = np.array(centers)
    cm = C.mean(0)
    _, _, Vt = np.linalg.svd(C - cm)
    axs = Vt[0]
    if axs @ ax < 0: axs = -axs
    r_fit = float(np.mean([rr])) if centers else -1
    dev_asm = float(np.linalg.norm(cm - ref) * 1000.0)
    hv = np.array(hough[name]['center_B'])
    dev_hough = float(np.linalg.norm(cm - hv) * 1000.0)
    out[name] = {'center_B': [round(float(x), 6) for x in cm],
                 'axis_B': [round(float(x), 6) for x in axs],
                 'r_fit_mm': round(r_fit, 3),
                 'n_band': int(band.sum()), 'n_slice': len(centers)}
    print('%s: STL圆拟合孔心 B=[%.5f,%.5f,%.5f] r=%.2fmm | vs assembly %.2fmm | vs Hough %.2fmm (带内 %d 点)'
          % (name, *cm, r_fit, dev_asm, dev_hough, band.sum()))

json.dump(out, open('bore_axis_circle.json', 'w'), indent=1)
print('-> bore_axis_circle.json')
