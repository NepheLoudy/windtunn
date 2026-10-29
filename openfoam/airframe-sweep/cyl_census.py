#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP 圆柱面普查 (gmsh 全局系) — 两个任务的地基:
  1) 镖头圆孔: STEP z<40 区域 (B_x>65mm 鼻端) 的圆柱面 → 填实参数
  2) 舵根轴套孔: 每片舵 (24/26/28/30) 附近 r∈[1.2,2.2] 的圆柱面聚类 → 真铰链轴 (对照旧轴)

用法: python cyl_census.py <step> [--nose-zmax 40] [--hinge-rmin 1.2] [--hinge-rmax 2.2]
输出: stdout 报告 + cyl_census.json
"""
import json, math, sys
import gmsh

STEP = sys.argv[1] if len(sys.argv) > 1 else 'cad/v1/airframe.step'
NOSE_ZMAX = 40.0

gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 0)
gmsh.model.add('m')
gmsh.merge(STEP)
gmsh.model.occ.synchronize()
gmsh.option.setNumber('Mesh.MeshSizeMax', 0.5)  # 细一点, 轴拟合更准
gmsh.model.mesh.generate(2)

# 表面→实体归属
surf2vol = {}
for dim, tag in gmsh.model.getEntities(3):
    for sdim, stag in gmsh.model.getBoundary([(3, tag)], oriented=False, recursive=False):
        surf2vol.setdefault(stag, []).append(tag)

ntags, nxyz, _ = gmsh.model.mesh.getNodes()
node = {int(t): (nxyz[3*i], nxyz[3*i+1], nxyz[3*i+2]) for i, t in enumerate(ntags)}

def fit_axis(pts):
    """PCA: 最小特征值方向=轴向; 返回(axis, centroid, radius_lateral_spread)"""
    n = len(pts)
    c = [sum(p[j] for p in pts)/n for j in range(3)]
    C = [[sum((p[a]-c[a])*(p[b]-c[b]) for p in pts)/n for b in range(3)] for a in range(3)]
    # 幂迭代求最小特征值方向: 对 C+eps*I 求最大 (逆迭代近似), 直接雅可比更稳 — 用 numpy 不在, 手写 3x3 雅可比
    def eig_min(M):
        # 雅可比旋转法
        A = [row[:] for row in M]
        for _ in range(60):
            # 找最大非对角
            p, q = 0, 1
            if abs(A[0][1]) < abs(A[0][2]): p, q = 0, 2
            if abs(A[p][q]) < abs(A[1][2]): p, q = 1, 2
            if abs(A[p][q]) < 1e-14: break
            apq = A[p][q]
            theta = 0.5*math.atan2(2*apq, A[q][q]-A[p][p])
            ct, st = math.cos(theta), math.sin(theta)
            for k in range(3):
                akp, akq = A[k][p], A[k][q]
                A[k][p] = ct*akp - st*akq
                A[p][k] = A[k][p]
                A[k][q] = st*akp + ct*akq
                A[q][k] = A[k][q]
            A[p][p], A[q][q] = ct*ct*A[p][p]-2*ct*st*apq+st*st*A[q][q], st*st*A[p][p]+2*ct*st*apq+ct*ct*A[q][q]
            A[p][q] = A[q][p] = 0.0
        idx = min(range(3), key=lambda i: A[i][i])
        v = [A[0][idx] if False else 0.0]*3
        # 特征向量: 解 (M-λI)v=0 用两行
        lam = A[idx][idx]
        M2 = [[M[0][0]-lam, M[0][1], M[0][2]], [M[1][0], M[1][1]-lam, M[1][2]], [M[2][0], M[2][1], M[2][2]-lam]]
        # 取 M2 两行叉积
        r0, r1 = (M2[0], M2[1]) if abs(M2[0][0])+abs(M2[0][1])+abs(M2[0][2]) > 1e-12 or True else (M2[1], M2[2])
        v = [r0[1]*r1[2]-r0[2]*r1[1], r0[2]*r1[0]-r0[0]*r1[2], r0[0]*r1[1]-r0[1]*r1[0]]
        ln = math.sqrt(sum(x*x for x in v)) or 1.0
        return [x/ln for x in v]
    ax = eig_min(C)
    # 半径: 点到过质心轴线的距离中位数
    d = []
    for p in pts:
        vx, vy, vz = p[0]-c[0], p[1]-c[1], p[2]-c[2]
        t = vx*ax[0]+vy*ax[1]+vz*ax[2]
        d.append(math.sqrt(max(0.0, vx*vx+vy*vy+vz*vz - t*t)))
    d.sort()
    return ax, c, d[len(d)//2]

rows = []
for dim, stag in gmsh.model.getEntities(2):
    etype = gmsh.model.getType(2, stag)
    if 'ylinder' not in etype:
        continue
    atags, axyz, _ = gmsh.model.mesh.getNodes(2, stag, includeBoundary=True)
    pts = [(axyz[3*i], axyz[3*i+1], axyz[3*i+2]) for i in range(len(atags))]
    if len(pts) < 12:
        continue
    try:
        ax, c, r_med = fit_axis(pts)
    except Exception as e:
        continue
    # 长度: 沿轴投影范围
    ts = [(p[0]-c[0])*ax[0]+(p[1]-c[1])*ax[1]+(p[2]-c[2])*ax[2] for p in pts]
    L = max(ts) - min(ts)
    bb = gmsh.model.getBoundingBox(2, stag)
    rows.append({'surf': stag, 'type': etype, 'vol': surf2vol.get(stag, []),
                 'r_mm': round(r_med, 3), 'L_mm': round(L, 2),
                 'center': [round(x, 2) for x in c], 'axis': [round(x, 4) for x in ax],
                 'bb_zmin': round(bb[5], 1), 'bb_zmax': round(bb[2+3], 1), 'bb': [round(x, 1) for x in bb]})
gmsh.finalize()

nose = [r for r in rows if r['bb'][5] < NOSE_ZMAX]
print('=== 头部区 (STEP z<%.0f, B_x>%.0fmm) 圆柱面 ===' % (NOSE_ZMAX, 105.5-NOSE_ZMAX))
for r in sorted(nose, key=lambda x: -x['r_mm']):
    print('surf=%d vol=%s r=%.3f L=%.1f center=%s axis=%s' %
          (r['surf'], r['vol'], r['r_mm'], r['L_mm'], r['center'], r['axis']))

print()
print('=== 舵根区圆柱面 (r 1.2-2.6, 中心 z>150) ===')
hinge = [r for r in rows if 1.2 <= r['r_mm'] <= 2.6 and r['center'][2] > 150]
for r in sorted(hinge, key=lambda x: (x['vol'][0] if x['vol'] else 0, x['r_mm'])):
    print('surf=%d vol=%s r=%.3f L=%.1f center=%s axis=%s' %
          (r['surf'], r['vol'], r['r_mm'], r['L_mm'], r['center'], r['axis']))

json.dump({'nose': nose, 'hinge': hinge, 'all_count': len(rows)},
          open('cyl_census.json', 'w'), indent=1)
print('\n共 %d 个圆柱面; 头部 %d, 舵根候选 %d -> cyl_census.json' % (len(rows), len(nose), len(hinge)))
