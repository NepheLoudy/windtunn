#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析法提取铰链孔圆柱轴 — 终局正解 (曼波 10-30)
不用网格拟合! gmsh OCC 面的解析参数化: 圆柱面 p(u,v), u=角度 v=轴向。
固定 v 采一圈 → 空间圆 → 圆法向=真实轴向, 圆心=真实轴点, 半径=精确值。
对 4 片舵的孔面 (1849/1912/1975/2038) + 搜索其它候选圆柱面 (轴≈(0.707,0.707,0))。
"""
import json, math
import numpy as np
import gmsh

STEP = 'cad/v1/airframe.step'
SURFS = {24: 1849, 26: 1912, 28: 1975, 30: 2038}
COM = np.array([-0.1, 0.2, 105.5])

def toB_mm(p):
    return np.array([-(p[2]-COM[2]), p[1]-COM[1], p[0]-COM[0]])

def circle_from_points(Q):
    """空间圆拟合: 平面法向 + 圆心 + 半径 (SVD 平面 + 平面内代数圆)"""
    c = Q.mean(0)
    U, S, Vt = np.linalg.svd(Q - c)
    n = Vt[2]                       # 平面法向
    e1 = Vt[0]; e2 = Vt[1]
    uu = (Q - c) @ e1
    vv = (Q - c) @ e2
    A = np.column_stack([2*uu, 2*vv, np.ones(len(uu))])
    b = uu*uu + vv*vv
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cu, cv = sol[0], sol[1]
    r = math.sqrt(max(sol[2] + cu*cu + cv*cv, 0))
    center = c + cu*e1 + cv*e2
    resid = np.abs(np.sqrt((uu-cu)**2 + (vv-cv)**2) - r)
    return n, center, r, float(resid.max())

gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 0)
gmsh.model.add('m')
gmsh.merge(STEP)
gmsh.model.occ.synchronize()

result = {}
for tag, surf in sorted(SURFS.items()):
    typ = gmsh.model.getType(2, surf)
    b = gmsh.model.getParametrizationBounds(2, surf)
    u0, u1, v0, v1 = b[0][0], b[1][0], b[0][1], b[1][1]
    # 圆柱: u=角度 v=轴向。固定 v=中值, 采 64 点一圈
    vs = [v0 + (v1-v0)*f for f in (0.25, 0.5, 0.75)]
    circles = []
    for vv in vs:
        us = u0 + (u1-u0)*np.arange(64)/63.0
        params = []
        for u in us:
            params += [u, vv]
        pts = np.array(gmsh.model.getValue(2, surf, params)).reshape(-1, 3)
        n, c, r, resid = circle_from_points(pts)
        circles.append((n, c, r, resid))
    # 三圈一致性
    ns = np.array([c[0] for c in circles])
    cs = np.array([c[1] for c in circles])
    rs = [c[2] for c in circles]
    rms_res = max(c[3] for c in circles)
    # 轴向符号统一
    n0 = ns[0]
    for i in range(1, 3):
        if ns[i] @ n0 < 0: ns[i] = -ns[i]
    axis_dir = ns.mean(0); axis_dir /= np.linalg.norm(axis_dir)
    # 轴点: 三圆心投影到轴的公共点 (取平均, 圆心的轴向分量沿轴自然分布)
    axis_pt = cs.mean(0)
    # 圆心串沿轴的标准差 = 三圈圆心在轴向的散布 (应为圈间距的一定量)
    ts = [(c - axis_pt) @ axis_dir for c in cs]
    radial_dev = float(np.sqrt(sum(np.linalg.norm((c - axis_pt) - ((c-axis_pt)@axis_dir)*axis_dir)**2 for c in cs)/3))
    pB = toB_mm(axis_pt) / 1000.0
    aB = np.array([-axis_dir[2], axis_dir[1], axis_dir[0]]); aB /= np.linalg.norm(aB)
    result[tag] = {'surf': surf, 'type': typ,
                   'axis_B': [round(float(x), 6) for x in aB],
                   'point_B': [round(float(x), 6) for x in pB],
                   'r_mm': round(float(np.mean(rs)), 4),
                   'circle_resid_max_mm': round(rms_res, 5),
                   'circles_radial_dev_mm': round(radial_dev, 5),
                   'param_range': [round(float(u0), 4), round(float(u1), 4), round(float(v0), 4), round(float(v1), 4)]}
    print('vol%d surf=%d (%s): r=%.4fmm 圆心残差 max=%.5fmm 三圈轴心散布=%.5fmm' %
          (tag, surf, typ, np.mean(rs), rms_res, radial_dev))
    print('   STEP系: 轴=[%.6f,%.6f,%.6f] 轴点=[%.3f,%.3f,%.3f]' % (*axis_dir, *axis_pt))
    print('   B  系: 轴=[%.6f,%.6f,%.6f] 轴点=[%.6f,%.6f,%.6f]' % (*aB, *pB))

gmsh.finalize()
json.dump(result, open('hinges_analytic.json', 'w'), indent=1)
print('-> hinges_analytic.json')
