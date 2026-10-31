#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""铰链锚点邻域全表面普查 v2 — 回答"body 侧到底拿什么和舵根半管壳配合"

v1 教训: 只查 Cylinder + axis 忘做 STEP→B 变换 + 混系算线距。
v2: 邻域 15mm 内所有面(任何类型), 记录所属 volume(判 fin/body), Cylinder 面给
解析轴(正确变换到 B 系), 输出每个面的类型/半径/弧段/volume 归属。
"""
import json
import math
import numpy as np
import gmsh

STEP = 'cad/v1/airframe.step'
COM = np.array([-0.1, 0.2, 105.5])


def toB_mm(p):
    return np.array([-(p[2] - COM[2]), p[1] - COM[1], p[0] - COM[0]])


def toB_dir(u):
    return np.array([-u[2], u[1], u[0]])


def circle_from_points(Q):
    c = Q.mean(0)
    U, S, Vt = np.linalg.svd(Q - c)
    n = Vt[2]
    e1, e2 = Vt[0], Vt[1]
    uu = (Q - c) @ e1
    vv = (Q - c) @ e2
    A = np.column_stack([2 * uu, 2 * vv, np.ones(len(uu))])
    b = uu * uu + vv * vv
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cu, cv = sol[0], sol[1]
    r = math.sqrt(max(sol[2] + cu * cu + cv * cv, 0))
    center = c + cu * e1 + cv * e2
    return n, center, r


gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 0)
gmsh.model.add('m')
gmsh.merge(STEP)
gmsh.model.occ.synchronize()

ana = json.load(open('hinges_analytic.json'))
anchors = {t: np.array(ana[t]['point_B']) * 1000.0 for t in ana}
fins = {24: 'fin_1', 26: 'fin_2', 28: 'fin_3', 30: 'fin_4'}

out = []
for dim, s in gmsh.model.getEntities(2):
    vols = gmsh.model.getAdjacencies(2, s)[0].tolist()
    b = gmsh.model.getParametrizationBounds(2, s)
    u0, u1, v0, v1 = b[0][0], b[1][0], b[0][1], b[1][1]
    if (v1 - v0) < 15:            # 轴向 <15mm 跳过 (铰链区特征长 32mm)
        continue
    vv = 0.5 * (v0 + v1)
    us = u0 + (u1 - u0) * np.arange(48) / 47.0
    params = []
    for u in us:
        params += [u, vv]
    try:
        pts = np.array(gmsh.model.getValue(2, s, params)).reshape(-1, 3)
    except Exception:
        continue
    cSTEP = pts.mean(0)
    cB = toB_mm(cSTEP)
    near = [t for t in anchors if np.linalg.norm(cB - anchors[t]) < 15.0]
    if not near:
        continue
    typ = gmsh.model.getType(2, s)
    e = {'surf': s, 'type': typ,
         'vols': vols, 'vol_is_fin': [fins.get(v) for v in vols if v in fins],
         'center_B_mm': [round(float(x), 3) for x in cB],
         'len_mm': round(float(v1 - v0), 1),
         'near': [fins.get(int(t), str(t)) for t in near]}
    if typ == 'Cylinder':
        nSTEP, cST, r = circle_from_points(pts)
        nB = toB_dir(nSTEP)
        nB = nB / np.linalg.norm(nB)
        e['r_mm'] = round(r, 4)
        e['arc_deg'] = round(math.degrees(u1 - u0), 1)
        e['axis_B'] = [round(float(x), 6) for x in nB]
    out.append(e)

out.sort(key=lambda e: (e['near'][0], e['type']))
for e in out:
    print(json.dumps(e, ensure_ascii=False))
print('total faces near hinges:', len(out))
json.dump(out, open('hinge_region_faces.json', 'w'), indent=1)
gmsh.finalize()
