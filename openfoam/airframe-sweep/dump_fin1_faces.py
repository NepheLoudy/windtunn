#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fin_1 (vol 24) 全部面清单 + 全模型小圆柱普查 — 找真正的销轴/运动学轴"""
import json
import math
import numpy as np
import gmsh

STEP = 'cad/v1/airframe.step'
COM = np.array([-0.1, 0.2, 105.5])


def toB_dir(u):
    u = np.asarray(u, float)
    v = np.array([-u[2], u[1], u[0]])
    return v / np.linalg.norm(v)


def toB_mm(p):
    return np.array([-(p[2] - COM[2]), p[1] - COM[1], p[0] - COM[0]])


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
    return Vt[2] / np.linalg.norm(Vt[2]), c + sol[0] * e1 + sol[1] * e2, r


gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 0)
gmsh.model.add('m')
gmsh.merge(STEP)
gmsh.model.occ.synchronize()

print('===== vol 24 (fin_1) 全部面 =====')
for dim, s in gmsh.model.getEntities(2):
    vols = gmsh.model.getAdjacencies(2, s)[0].tolist()
    if vols != [24]:
        continue
    b = gmsh.model.getParametrizationBounds(2, s)
    u0, u1, v0, v1 = b[0][0], b[1][0], b[0][1], b[1][1]
    typ = gmsh.model.getType(2, s)
    vv = 0.5 * (v0 + v1)
    try:
        pts = np.array(gmsh.model.getValue(2, s, [u0, vv, u1, vv])).reshape(-1, 3)
        cB = toB_mm(pts.mean(0))
        loc = '[%.1f %.1f %.1f]' % tuple(cB)
    except Exception:
        loc = '[?]'
    extra = ''
    if typ == 'Cylinder':
        us = u0 + (u1 - u0) * np.arange(48) / 47.0
        params = []
        for u in us:
            params += [u, vv]
        pts = np.array(gmsh.model.getValue(2, s, params)).reshape(-1, 3)
        n, c, r = circle_from_points(pts)
        extra = ' r=%.4f arc=%.0fdeg axis_B=%s cB=%s' % (
            r, math.degrees(u1 - u0),
            [round(float(x), 3) for x in toB_dir(n)], [round(float(x), 2) for x in toB_mm(c)])
    print('surf %4d %-10s u%.2f..%.2f v%.2f..%.2f mid%s%s' % (s, typ, u0, u1, v0, v1, loc, extra))

print('===== 全模型圆柱 r<5mm =====')
seen = set()
for dim, s in gmsh.model.getEntities(2):
    if gmsh.model.getType(2, s) != 'Cylinder':
        continue
    vols = gmsh.model.getAdjacencies(2, s)[0].tolist()
    b = gmsh.model.getParametrizationBounds(2, s)
    u0, u1, v0, v1 = b[0][0], b[1][0], b[0][1], b[1][1]
    vv = 0.5 * (v0 + v1)
    us = u0 + (u1 - u0) * np.arange(32) / 31.0
    params = []
    for u in us:
        params += [u, vv]
    try:
        pts = np.array(gmsh.model.getValue(2, s, params)).reshape(-1, 3)
    except Exception:
        continue
    n, c, r = circle_from_points(pts)
    if not (0.4 <= r <= 5.0):
        continue
    key = (s,)
    if key in seen:
        continue
    seen.add(key)
    cB = toB_mm(c)
    print('surf %4d vol%-3s r=%.3f L=%.1f arc=%.0f cB=[%.1f %.1f %.1f] axB=%s' % (
        s, vols, r, v1 - v0, math.degrees(u1 - u0), *cB,
        [round(float(x), 3) for x in toB_dir(n)]))
gmsh.finalize()
