#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scipy least_squares 圆柱拟合 — 终版仲裁 (曼波 10-30)
参数 p = [cx, cy, cz(轴上点3), ux,uy,uz(方向3), r(1)] = 7 参数
残差: e_i = |(P_i - c) - ((P_i-c)·u)u| - r
TRF + 数值雅可比。从旧轴出发。输出 vs assembly/旧轴偏差。"""
import json
import numpy as np
import gmsh
from scipy.optimize import least_squares

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
result = {}
for tag, surf in sorted(FACES.items()):
    atags, axyz, _ = gmsh.model.mesh.getNodes(2, surf, includeBoundary=True)
    P = np.array(axyz).reshape(-1, 3)
    o = old[tag]
    ax0 = np.array(o['axis'], float); ax0 /= np.linalg.norm(ax0)
    c0 = np.array(o['center_mm'], float)

    def residual(p):
        c, u, r = p[0:3], p[3:6], p[6]
        V = P - c
        t = V @ u
        w = V - np.outer(t, u)
        return np.linalg.norm(w, axis=1) - r

    p0 = np.concatenate([c0, ax0, [1.63]])
    r0 = residual(p0)
    print('vol%d 带前 rms=%.4f (旧轴, 全点 %d)' % (tag, np.sqrt((r0**2).mean()), len(P)))
    sol = least_squares(residual, p0, method='lm', max_nfev=200)
    c, u, r = sol.x[0:3], sol.x[3:6], sol.x[6]
    u = u / np.linalg.norm(u)
    rms = float(np.sqrt((sol.fun**2).mean()))
    pB = toB_mm(c) / 1000.0
    aB = np.array([-u[2], u[1], u[0]]); aB = aB / np.linalg.norm(aB)
    # 带内 (真解附近) 精修一轮: 只取距新轴 r±0.4 的点
    V = P - c
    t = V @ u
    rad = np.sqrt(np.clip((V*V).sum(1) - t*t, 0, None))
    band = (rad > r-0.4) & (rad < r+0.4)
    sol2 = least_squares(residual, np.concatenate([c, u, [r]]), args=(), method='lm', max_nfev=200) if False else None
    def residual_band(pp):
        cc, uu, rr = pp[0:3], pp[3:6], pp[6]
        VV = P[band] - cc
        tt = VV @ uu
        ww = VV - np.outer(tt, uu)
        return np.linalg.norm(ww, axis=1) - rr
    sol2 = least_squares(residual_band, np.concatenate([c, u, [r]]), method='lm', max_nfev=200)
    c2, u2, r2 = sol2.x[0:3], sol2.x[3:6] / np.linalg.norm(sol2.x[3:6]), sol2.x[6]
    rms2 = float(np.sqrt((sol2.fun**2).mean()))
    pB2 = toB_mm(c2) / 1000.0
    aB2 = np.array([-u2[2], u2[1], u2[0]]); aB2 = aB2 / np.linalg.norm(aB2)
    dshift = float(np.linalg.norm(c2 - c) )
    result[tag] = {'full_fit': {'center_B': [round(float(x), 6) for x in pB], 'r_mm': round(float(r), 3), 'rms_mm': round(rms, 4)},
                   'band_fit': {'center_B': [round(float(x), 6) for x in pB2], 'axis_B': [round(float(x), 6) for x in aB2],
                                'r_mm': round(float(r2), 3), 'rms_mm': round(rms2, 4), 'shift_from_full_mm': round(dshift, 3)}}
    print('vol%d 全点拟合: 孔心 B=[%.5f,%.5f,%.5f] r=%.3f rms=%.4f' % (tag, *pB, r, rms))
    print('      带内精修:   孔心 B=[%.5f,%.5f,%.5f] r=%.3f rms=%.4f | 轴点移动 %.3fmm' % (*pB2, r2, rms2, dshift))

gmsh.finalize()
json.dump(result, open('hinges_scipy.json', 'w'), indent=1)
print('-> hinges_scipy.json')
