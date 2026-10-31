#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真铰链轴定案 (曼波 10-31 第四次目视指控裁决) — 双耳孔心连线 = 运动学轴

v3 错轴根因: 用的"解析轴"是舵根半管壳 (r=2.0, 180°弧, x=-85.73) 的轴 —
那是导引套, 不是铰链! 真轴 = 舵上两个整圆孔 (360°) 的孔心连线:
  fin_1: r=1.9 孔 (−87.62, 20.69, 20.99) + r=1.15 孔 (−87.62, 40.08, 40.38)
  连线严格 ∥ (0,0.707,0.707), x=-87.62 — 与半管壳轴平行但横移 1.89mm。
绕错轴转 45° → 舵平移 2·1.89·sin(22.5°) ≈ 1.45mm → 管孔与 body 安装位不同轴。

本脚本: 每片舵找全部整圆孔 → 孔对共线校验 → 真轴 JSON;
再对 body 侧做真轴线邻域 (2.5mm) 面普查 — 验证销/座配合 (指控②的 body 侧证据)。
"""
import json
import math
import numpy as np
import gmsh

STEP = 'cad/v1/airframe.step'
COM = np.array([-0.1, 0.2, 105.5])
FINS = {24: 'fin_1', 26: 'fin_2', 28: 'fin_3', 30: 'fin_4'}


def toB_mm(p):
    return np.array([-(p[2] - COM[2]), p[1] - COM[1], p[0] - COM[0]])


def toB_dir(u):
    v = np.array([-u[2], u[1], u[0]])
    return v / np.linalg.norm(v)


def toSTEP_mm(pB):
    return np.array([pB[2] - 0.1, pB[1] + 0.2, -pB[0] + 105.5])


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

# ---- 1) 每片舵的整圆孔 ----
holes = {}
for vol, name in FINS.items():
    found = []
    for dim, s in gmsh.model.getEntities(2):
        if gmsh.model.getType(2, s) != 'Cylinder':
            continue
        if gmsh.model.getAdjacencies(2, s)[0].tolist() != [vol]:
            continue
        b = gmsh.model.getParametrizationBounds(2, s)
        u0, u1, v0, v1 = b[0][0], b[1][0], b[0][1], b[1][1]
        if abs((u1 - u0) - 2 * math.pi) > 0.05:   # 只要整圆孔
            continue
        vv = 0.5 * (v0 + v1)
        us = u0 + (u1 - u0) * np.arange(48) / 47.0
        params = []
        for u in us:
            params += [u, vv]
        pts = np.array(gmsh.model.getValue(2, s, params)).reshape(-1, 3)
        n, c, r = circle_from_points(pts)
        found.append({'surf': s, 'r_mm': round(r, 4), 'len_mm': round(v1 - v0, 2),
                      'cB_mm': [round(float(x), 4) for x in toB_mm(c)],
                      'axis_B': [round(float(x), 6) for x in toB_dir(n)]})
    holes[name] = found
    print('%s: %d 个整圆孔 -> %s' % (name, len(found),
          [(h['r_mm'], h['cB_mm']) for h in found]))

# ---- 2) 孔对共线 → 真轴 ----
result = {}
for name, hs in holes.items():
    if len(hs) != 2:
        print('%s: 孔数 %d != 2, 人工复核!' % (name, len(hs)))
        continue
    c1 = np.array(hs[0]['cB_mm']); c2 = np.array(hs[1]['cB_mm'])
    d = c2 - c1
    dnorm = d / np.linalg.norm(d)
    ideal = np.array([0.0, 0.707107, 0.707107])
    align = min(float(np.dot(dnorm, ideal)), float(np.dot(dnorm, -ideal)))
    mid = 0.5 * (c1 + c2)
    result[name] = {
        'point_B_mm': [round(float(x), 4) for x in mid],
        'axis_B': [round(float(x), 6) for x in dnorm],
        'span_mm': round(float(np.linalg.norm(d)), 3),
        'holes': hs,
        'align_with_span_dir': round(align, 6),
    }
    print('%s 真轴: 点=%s 轴=%s 跨距=%.2fmm 与展向夹角余弦=%.6f' % (
        name, result[name]['point_B_mm'], result[name]['axis_B'],
        result[name]['span_mm'], align))

json.dump(result, open('hinges_true.json', 'w'), indent=1)

# ---- 3) body 侧真轴邻域配合面普查 ----
print('===== body 侧真轴 2.5mm 邻域面 =====')
NU = NV = 14
for name, h in result.items():
    pSTEP = toSTEP_mm(np.array(h['point_B_mm']))
    uB = np.array(h['axis_B'])
    uSTEP = np.array([uB[2], uB[1], -uB[0]])   # B->STEP 方向
    found = []
    for dim, s in gmsh.model.getEntities(2):
        vols = gmsh.model.getAdjacencies(2, s)[0].tolist()
        if vols in ([24], [26], [28], [30]):
            continue
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
        rel = pts - pSTEP
        t = rel @ uSTEP
        dist = np.linalg.norm(rel - np.outer(t, uSTEP), axis=1)
        dmin = float(dist.min())
        if dmin < 2.5:
            e = {'surf': s, 'type': gmsh.model.getType(2, s), 'vols': vols,
                 'dmin_mm': round(dmin, 3)}
            if e['type'] == 'Cylinder':
                vv2 = 0.5 * (v0 + v1)
                us2 = u0 + (u1 - u0) * np.arange(48) / 47.0
                pr = []
                for u in us2:
                    pr += [u, vv2]
                pts2 = np.array(gmsh.model.getValue(2, s, pr)).reshape(-1, 3)
                n2, c2, r2 = circle_from_points(pts2)
                e['r_mm'] = round(r2, 4)
                e['arc_deg'] = round(math.degrees(u1 - u0), 0)
                e['dist_to_true_axis_mm'] = round(line_line_distance(
                    toB_mm(c2), toB_dir(n2), h['point_B_mm'], uB), 4)
            found.append(e)
    found.sort(key=lambda x: x['dmin_mm'])
    print('%s 真轴邻域 body 面 %d 个:' % (name, len(found)))
    for e in found[:10]:
        print('  ', json.dumps(e, ensure_ascii=False))

gmsh.finalize()
print('-> hinges_true.json')
