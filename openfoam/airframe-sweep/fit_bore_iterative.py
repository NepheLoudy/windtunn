#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迭代自洽铰链孔拟合 — 修"偏心月牙弧"系统偏差 (曼波 10-30 两轮指正的根因)
初值 = 旧轴 (方向对/位置偏 2mm)。每轮:
  1. 带选: r ∈ [r_core±0.35] (r_core = 上轮带内中位半径, 随轴对准自动聚焦真孔)
  2. 逐切片圆拟合 (STEP surf 1849/1912/1975/2038 精细节点, 每面 ~1900 点)
  3. 圆心串 TLS → 新轴/新点
  收敛: 轴中点移动 < 0.005mm。输出四舵独立孔心 + 偏差历史。"""
import json, math
import numpy as np
import gmsh

STEP = 'cad/v1/airframe.step'
FACES = {24: 1849, 26: 1912, 28: 1975, 30: 2038}
COM = np.array([-0.1, 0.2, 105.5])

def toB_mm(p):
    return np.array([-(p[2]-COM[2]), p[1]-COM[1], p[0]-COM[0]])

gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 0)
gmsh.model.add('m')
gmsh.merge(STEP)
gmsh.model.occ.synchronize()
gmsh.option.setNumber('Mesh.MeshSizeMax', 0.35)
gmsh.model.mesh.generate(2)

old = {h['part_tag']: h for h in json.load(open('cad/v1/hinges.json')) if h['part_tag'] in FACES and h.get('length_mm', 0) > 20}

for tag, surf in sorted(FACES.items()):
    atags, axyz, _ = gmsh.model.mesh.getNodes(2, surf, includeBoundary=True)
    P = np.array(axyz).reshape(-1, 3)
    o = old[tag]
    ax = np.array(o['axis'], float); ax /= np.linalg.norm(ax)
    c = np.array(o['center_mm'], float)
    r_core = 1.63
    hist = []
    for it in range(6):
        V = P - c
        t = V @ ax
        rad = np.sqrt(np.clip((V*V).sum(1) - t*t, 0, None))
        band = (rad > r_core-0.35) & (rad < r_core+0.35)
        if band.sum() < 50:
            # fallback: 取径向中位 40% 窗口 (防迭代中带选走飞)
            lo, hi = np.percentile(rad, 30), np.percentile(rad, 70)
            band = (rad > lo) & (rad < hi)
        tmin, tmax = t[band].min(), t[band].max()
        e1 = np.cross(ax, [1.0, 0, 0])
        if np.linalg.norm(e1) < 1e-6: e1 = np.cross(ax, [0, 1.0, 0])
        e1 /= np.linalg.norm(e1); e2 = np.cross(ax, e1)
        centers, radii = [], []
        nb = 12
        for k in range(nb):
            lo = tmin + (tmax-tmin)*k/nb; hi = tmin + (tmax-tmin)*(k+1)/nb
            m = band & (t >= lo) & (t <= hi)
            if m.sum() < 8: continue
            tc = 0.5*(lo+hi)
            W = P[m] - (c + tc*ax)
            uu, vv = W @ e1, W @ e2
            A = np.column_stack([2*uu, 2*vv, np.ones(m.sum())])
            b = uu*uu + vv*vv
            sol, *_ = np.linalg.lstsq(A, b, rcond=None)
            rr = math.sqrt(max(sol[2] + sol[0]**2 + sol[1]**2, 0))
            centers.append(c + tc*ax + sol[0]*e1 + sol[1]*e2)
            radii.append(rr)
        C = np.array(centers)
        cm = C.mean(0)
        _, _, Vt = np.linalg.svd(C - cm)
        axn = Vt[0]
        if axn @ ax < 0: axn = -axn
        move = float(np.linalg.norm(cm - c) * 1000)
        r_core = float(np.median(rad[band]))
        hist.append('it%d: move=%.3fmm r=%.3f n=%d' % (it, move, r_core, band.sum()))
        ax, c = axn, cm
        if move < 0.005 and it >= 1:
            break
    # 偏心自检: 每切片圆心到最终轴的 RMS
    res = C - cm
    res = res - np.outer(res @ ax, ax)
    rms = float(np.sqrt((res*res).sum(1).mean()))
    pB = toB_mm(c) / 1000.0
    aB = np.array([-ax[2], ax[1], ax[0]]); aB /= np.linalg.norm(aB)
    print('vol%d %s' % (tag, ' | '.join(hist)))
    print('  收敛孔心 B=[%.5f, %.5f, %.5f] 轴=[%.5f,%.5f,%.5f] r=%.3f 圆心RMS=%.3fmm' %
          (pB[0], pB[1], pB[2], aB[0], aB[1], aB[2], r_core, rms))

gmsh.finalize()
