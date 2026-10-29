#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""舵根铰链孔真轴拟合 — 修曼波指出的"转轴圆心偏了" (2026-10-29)

方法 (对每片舵的孔面, fin 24/26/28/30 → surf 1849/1912/1975/2038):
  1. 细网格 (0.35mm) 取面孔面全部节点
  2. 以旧轴 (hinges.json) 为方向种子, 沿轴切片 (1mm)
  3. 每片切片只取孔径带节点 (径向 1.2-2.2mm, 排除端部沉割/倒角), 平面最小二乘圆拟合 → 切片圆心
  4. 对圆心串做 TLS 直线拟合 (numpy SVD) → 真轴 (方向 + 中点)
  5. 报告新旧轴的: 中点垂偏 / 方向夹角 / 每片圆心残差 RMS

输出: hinges_refined.json + stdout。B 系换算同 build_geometry.toB_mm。
"""
import json, math
import numpy as np
import gmsh

STEP = 'cad/v1/airframe.step'
FIN_FACES = {24: 1849, 26: 1912, 28: 1975, 30: 2038}
COM = np.array([-0.1, 0.2, 105.5])
BAND = (1.15, 2.25)  # 孔径带 (径向 mm), 排除 <1.15 的深层和 >2.25 的沉割

def toB_mm(p):
    return [-(p[2] - COM[2]), p[1] - COM[1], p[0] - COM[0]]

gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 0)
gmsh.model.add('m')
gmsh.merge(STEP)
gmsh.model.occ.synchronize()
gmsh.option.setNumber('Mesh.MeshSizeMax', 0.35)
gmsh.model.mesh.generate(2)

old = {h['part_tag']: h for h in json.load(open('cad/v1/hinges.json')) if h['part_tag'] in FIN_FACES and h.get('length_mm', 0) > 20}
out = []
for tag, surf in sorted(FIN_FACES.items()):
    atags, axyz, _ = gmsh.model.mesh.getNodes(2, surf, includeBoundary=True)
    P = np.array(axyz).reshape(-1, 3)
    o = old[tag]
    ax0 = np.array(o['axis'], float); ax0 /= np.linalg.norm(ax0)
    c0 = np.array(o['center_mm'], float)
    V = P - c0
    t = V @ ax0
    rad = np.sqrt(np.clip((V * V).sum(1) - t * t, 0, None))
    band = (rad > BAND[0]) & (rad < BAND[1])
    # 切片
    tmin, tmax = t[band].min(), t[band].max()
    centers, ts = [], []
    nb = 12
    for i in range(nb):
        lo = tmin + (tmax - tmin) * i / nb
        hi = tmin + (tmax - tmin) * (i + 1) / nb
        m = band & (t >= lo) & (t < hi if i < nb - 1 else t <= hi)
        if m.sum() < 8:
            continue
        Q = P[m]
        tc = (lo + hi) / 2
        # 平面 (垂直 ax0, 过 c0+tc*ax0) 内圆拟合: 换正交基
        e1 = np.cross(ax0, [0, 0, 1.0])
        if np.linalg.norm(e1) < 1e-6:
            e1 = np.cross(ax0, [0, 1.0, 0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax0, e1)
        W = Q - (c0 + tc * ax0)
        u = W @ e1; v = W @ e2
        # 最小二乘圆: u²+v² = 2a*u + 2b*v + c
        A = np.column_stack([2 * u, 2 * v, np.ones(len(u))])
        b = u * u + v * v
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        a_, b_, c_ = sol
        cu, cv = a_, b_
        rr = math.sqrt(c_ + cu * cu + cv * cv)
        center = c0 + tc * ax0 + cu * e1 + cv * e2
        centers.append(center); ts.append(tc)
    centers = np.array(centers); ts = np.array(ts)
    # TLS 直线: SVD on 中心串
    cmean = centers.mean(0)
    U, S, Vt = np.linalg.svd(centers - cmean)
    ax_new = Vt[0]
    if ax_new @ ax0 < 0:
        ax_new = -ax_new
    # 新轴上与旧轴中点同参数的点 (用 cmean 作轴上点)
    # 新旧偏差: 旧轴中点 c0 到新轴线的垂距 + 方向夹角
    d = c0 - cmean
    perp = d - (d @ ax_new) * ax_new
    off = np.linalg.norm(perp)
    ang = math.degrees(math.acos(np.clip(ax_new @ ax0, -1, 1)))
    # 圆心串残差 (对直线的 RMS 垂距)
    res = centers - cmean
    res = res - np.outer(res @ ax_new, ax_new)
    rms = float(np.sqrt((res * res).sum(1).mean()))
    r_mean = float(rad[band].mean())
    out.append({'fin_vol': tag, 'surf': surf,
                'old_axis': ax0.tolist(), 'old_center': c0.tolist(),
                'new_axis': [round(float(x), 6) for x in ax_new],
                'new_point_mm': [round(float(x), 3) for x in cmean],
                'offset_old_to_new_mm': round(float(off), 3),
                'dir_angle_deg': round(ang, 3),
                'slice_center_rms_mm': round(rms, 3),
                'bore_r_mean_mm': round(r_mean, 3),
                'n_band_nodes': int(band.sum())})
    print('vol%d: 新轴中点 %s | 旧→新垂偏 %.3fmm 方向差 %.2f° 圆心RMS %.3fmm 孔径带均值 r=%.3f'
          % (tag, ['%.2f' % x for x in cmean], off, ang, rms, r_mean))

gmsh.finalize()
json.dump(out, open('hinges_refined.json', 'w'), indent=1)

print('\n=== B 系 (米制) 新铰链轴 ===')
for r in out:
    pB = toB_mm(r['new_point_mm'])
    # 方向变换: STEP(x,y,z)→B(−z,y,x) (不含平移, 方向向量只做轴映射)
    a = r['new_axis']
    aB = [-a[2], a[1], a[0]]
    n = math.sqrt(sum(x * x for x in aB)); aB = [x / n for x in aB]
    print('%s: point_B=[%.5f, %.5f, %.5f] axis_B=[%.5f, %.5f, %.5f]' %
          (r['fin_vol'], pB[0] / 1000, pB[1] / 1000, pB[2] / 1000, aB[0], aB[1], aB[2]))
print('-> hinges_refined.json')
