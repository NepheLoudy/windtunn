#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""铰链配合面终极普查 — 全 STEP 每面到铰链轴点的最小面距离 <2.5mm 者全收

回答: 舵根半管壳 (r=2.0, 180°弧) 在 body 侧到底和什么配合?
v2 教训: 面心邻近+长度过滤会漏; 本版 = 无类型过滤/无长度过滤, 16×16 网格采样
取面到轴点最小距离。配合面 (间隙 0.1-0.4mm) 必然在 2.5mm 内现形。
输出按 min_dist 排序, 记录所属 volume 与 fin/body 归属; Cylinder 面附解析轴(B系)。
"""
import json
import math
import numpy as np
import gmsh

STEP = 'cad/v1/airframe.step'
COM = np.array([-0.1, 0.2, 105.5])
FIN_VOLS = {24: 'fin_1', 26: 'fin_2', 28: 'fin_3', 30: 'fin_4'}


def toB_mm(p):
    return np.array([-(p[2] - COM[2]), p[1] - COM[1], p[0] - COM[0]])


def toB_dir(u):
    u = np.asarray(u, float)
    v = np.array([-u[2], u[1], u[0]])
    return v / np.linalg.norm(v)


def circle_from_points(Q):
    c = Q.mean(0)
    U, S, Vt = np.linalg.svd(Q - c)
    e1, e2 = Vt[0], Vt[1]
    uu = (Q - c) @ e1
    vv = (Q - c) @ e2
    A = np.column_stack([2 * uu, 2 * vv, np.ones(len(uu))])
    b = uu * uu + vv * vv
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    r = math.sqrt(max(sol[2] + sol[0] ** 2 + sol[1] ** 2, 0))
    n = Vt[2]
    center = c + sol[0] * e1 + sol[1] * e2
    return n / np.linalg.norm(n), center, r


def line_line_distance(p1, u1, p2, u2):
    w = np.asarray(p2, float) - np.asarray(p1, float)
    u1 = np.asarray(u1, float); u1 /= np.linalg.norm(u1)
    u2 = np.asarray(u2, float); u2 /= np.linalg.norm(u2)
    c = np.cross(u1, u2)
    if np.linalg.norm(c) < 1e-9:
        return float(np.linalg.norm(w - np.dot(w, u1) * u1))
    return float(abs(np.dot(c, w)) / np.linalg.norm(c))


gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 0)
gmsh.model.add('m')
gmsh.merge(STEP)
gmsh.model.occ.synchronize()

ana = json.load(open('hinges_analytic.json'))
# 轴点 B(m) -> STEP mm
anchors = {}
for t, a in ana.items():
    pB = np.array(a['point_B']) * 1000.0
    anchors[t] = {'step': np.array([pB[2] - 0.1, pB[1] + 0.2, -pB[0] + 105.5]),
                  'axis_B': np.array(a['axis_B'])}

NU, NV = 16, 16
hits = []
for dim, s in gmsh.model.getEntities(2):
    vols = gmsh.model.getAdjacencies(2, s)[0].tolist()
    b = gmsh.model.getParametrizationBounds(2, s)
    u0, u1, v0, v1 = b[0][0], b[1][0], b[0][1], b[1][1]
    us = u0 + (u1 - u0) * np.arange(NU) / (NU - 1)
    vs = v0 + (v1 - v0) * np.arange(NV) / (NV - 1)
    params = []
    for v in vs:
        for u in us:
            params += [u, v]
    try:
        pts = np.array(gmsh.model.getValue(2, s, params)).reshape(-1, 3)
    except Exception:
        continue
    for t, a in anchors.items():
        d = np.linalg.norm(pts - a['step'], axis=1)
        dmin = float(d.min())
        if dmin < 2.5:
            e = {'surf': s, 'type': gmsh.model.getType(2, s),
                 'vols': vols, 'vol': [FIN_VOLS.get(v, 'body%d' % v) for v in vols],
                 'near': FIN_VOLS[int(t)], 'min_dist_mm': round(dmin, 3)}
            if e['type'] == 'Cylinder':
                vv2 = v0 + 0.5 * (v1 - v0)
                us2 = u0 + (u1 - u0) * np.arange(48) / 47.0
                pr = []
                for u in us2:
                    pr += [u, vv2]
                pts2 = np.array(gmsh.model.getValue(2, s, pr)).reshape(-1, 3)
                nSTEP, cST, r = circle_from_points(pts2)
                e['r_mm'] = round(r, 4)
                e['arc_deg'] = round(math.degrees(u1 - u0), 1)
                e['axis_B'] = [round(float(x), 6) for x in toB_dir(nSTEP)]
                cB = toB_mm(cST)
                e['center_B_mm'] = [round(float(x), 3) for x in cB]
                e['dist_axisline_to_fin_axis_mm'] = round(line_line_distance(
                    cB, toB_dir(nSTEP), np.array(ana[t]['point_B']) * 1000.0,
                    ana[t]['axis_B']), 4)
            hits.append(e)
            break

hits.sort(key=lambda e: e['min_dist_mm'])
for e in hits:
    print(json.dumps(e, ensure_ascii=False))
print('faces within 2.5mm of hinge axes:', len(hits))
json.dump(hits, open('hinge_mating_faces.json', 'w'), indent=1)
gmsh.finalize()
