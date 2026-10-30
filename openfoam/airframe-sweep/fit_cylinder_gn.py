#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gauss-Newton 全局圆柱拟合 — 曼波 10-30 终版 (切片法病态, 改标准 GN)
参数化: 轴点 c(垂直平面内 2 自由度) + 轴方向偏角 α,β(2) + 半径 r(1)
残差: e_i = |radial_i| - r, 雅可比解析, Levenberg 阻尼。
数据: STEP 精细网格孔面 (surf 1849/1912/1975/2038, ~1900 点/面, 带内 ~480)"""
import json, math
import numpy as np
import gmsh

STEP = 'cad/v1/airframe.step'
FACES = {24: 1849, 26: 1912, 28: 1975, 30: 2038}
COM = np.array([-0.1, 0.2, 105.5])

def toB_mm(p):
    return np.array([-(p[2]-COM[2]), p[1]-COM[1], p[0]-COM[0]])

def ortho(u):
    e1 = np.cross(u, [1.0, 0, 0])
    if np.linalg.norm(e1) < 1e-6:
        e1 = np.cross(u, [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    return e1, np.cross(u, e1)

def gn_cylinder(P, ax, c, r0, iters=30):
    u = ax.copy()
    e1, e2 = ortho(u)
    # 参数: c 的 (e1,e2) 偏移 dc1,dc2; u 的偏转 (du1=e1, du2=e2 小角度); r
    c0 = c.copy(); r = r0
    lam = 1e-3
    for it in range(iters):
        V = P - c
        t = V @ u
        w = V - np.outer(t, u)          # 径向向量
        rw = np.linalg.norm(w, axis=1)  # 径向距离
        e = rw - r
        # 雅可比: ∂e_i/∂dc_j = -w_j/rw ; ∂e/∂du_j = -(t * w_j)/rw ; ∂e/∂r = -1
        n = len(P)
        J = np.zeros((n, 5))
        J[:, 0] = -w @ e1 / rw
        J[:, 1] = -w @ e2 / rw
        J[:, 2] = -t * (w @ e1) / rw
        J[:, 3] = -t * (w @ e2) / rw
        J[:, 4] = -1.0
        H = J.T @ J + lam * np.diag(np.diag(H0 if False else np.eye(5)))
        g = J.T @ e
        try:
            step = np.linalg.solve(H, -g)
        except np.linalg.LinAlgError:
            break
        # 应用 (小角度近似)
        c = c + step[0]*e1 + step[1]*e2
        u = u + step[2]*e1 + step[3]*e2
        u /= np.linalg.norm(u)
        r = r + step[4]
        e1, e2 = ortho(u)
        rms = float(np.sqrt((e*e).mean()))
        if it % 5 == 0 or it == iters-1:
            print('    it%d rms=%.4fmm r=%.4f' % (it, rms, r))
        if np.abs(step).max() < 1e-9:
            break
    return u, c, r, float(np.sqrt((e*e).mean()))

gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 0)
gmsh.model.add('m')
gmsh.merge(STEP)
gmsh.model.occ.synchronize()
gmsh.option.setNumber('Mesh.MeshSizeMax', 0.35)
gmsh.model.mesh.generate(2)

old = {h['part_tag']: h for h in json.load(open('cad/v1/hinges.json')) if h['part_tag'] in FACES and h.get('length_mm', 0) > 20}
result = {}
for tag, surf in sorted(FACES.items()):
    atags, axyz, _ = gmsh.model.mesh.getNodes(2, surf, includeBoundary=True)
    P = np.array(axyz).reshape(-1, 3)
    o = old[tag]
    ax = np.array(o['axis'], float); ax /= np.linalg.norm(ax)
    c = np.array(o['center_mm'], float)
    # 带内孔面点 (初始 r0=1.63)
    V = P - c
    t = V @ ax
    rad = np.sqrt(np.clip((V*V).sum(1) - t*t, 0, None))
    band = (rad > 1.30) & (rad < 1.98)
    Q = P[band]
    u, cfit, r, rms = gn_cylinder(Q, ax, c, 1.63)
    pB = toB_mm(cfit) / 1000.0
    aB = np.array([-u[2], u[1], u[0]]); aB /= np.linalg.norm(aB)
    result[tag] = {'center_B': [round(float(x), 6) for x in pB],
                   'axis_B': [round(float(x), 6) for x in aB],
                   'r_mm': round(float(r), 3), 'rms_mm': round(rms, 4)}
    print('vol%d GN: 孔心 B=[%.5f, %.5f, %.5f] 轴=[%.5f,%.5f,%.5f] r=%.3f rms=%.4fmm (带内 %d)' %
          (tag, pB[0], pB[1], pB[2], aB[0], aB[1], aB[2], r, rms, band.sum()))

gmsh.finalize()
json.dump(result, open('hinges_gn.json', 'w'), indent=1)
print('-> hinges_gn.json')
