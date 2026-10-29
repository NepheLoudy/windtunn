#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""镖头圆孔填实 (曼波 2026-10-29) — gmsh OCC 布尔熔合

结构实测 (cyl_census + vol1 剖面): 鼻端开口环 r_in 13.1→20.6mm @ z=-25.0,
内腔向后收敛到 ⌀16.6 (r=8.29, surf 2) 深腔, 底 z≈0。
填充体 = 圆锥: 底 r=13.55 @ z=-25.0 (与端面共面, 覆盖 r_in+0.45) → 顶 r=8.7 @ z=+2
(超过腔底 +2, 全程过盈且 << r_out 20.6)。fuse 进 vol1 → 重出:
  1) airframe_filled.step (B-rep 全量)
  2) parts/part_1.stl (模型系 mm, 原件备份 .bak_nosehole)
校验: 网格体积增量 ≈ 腔体积分体积; 出口 STL 逐边 2-manifold。
"""
import math, os, shutil, struct, sys
import numpy as np
import gmsh

STEP = 'cad/v1/airframe.step'
PART1 = 'cad/v1/parts/part_1.stl'
OUT_STEP = 'cad/v1/airframe_filled.step'
CONE = dict(z0=-25.0, r0=13.55, z1=2.0, r1=8.7)

def mesh_volume(tris):
    """散三角网格体积 (散度定理), tris=[(p0,p1,p2)...] 模型系"""
    v = 0.0
    for a, b, c in tris:
        v += (a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0]) + a[2]*(b[0]*c[1]-b[1]*c[0])) / 6.0
    return abs(v)

def edge_check(tris):
    """2-manifold 检查: 每条无向边恰好 2 次"""
    from collections import Counter
    cnt = Counter()
    for a, b, c in tris:
        for e in ((a, b), (b, c), (c, a)):
            k = tuple(sorted(e))
            cnt[k] += 1
    bad = [k for k, n in cnt.items() if n != 2]
    return len(cnt), bad

gmsh.initialize()
gmsh.option.setNumber('General.Terminal', 0)
gmsh.model.add('m')
gmsh.merge(STEP)
gmsh.model.occ.synchronize()

# 填充锥
cone = gmsh.model.occ.addCone(0, 0, CONE['z0'], 0, 0, CONE['z1'] - CONE['z0'], CONE['r0'], CONE['r1'])
out, _ = gmsh.model.occ.fuse([(3, 1)], [(3, cone)])
gmsh.model.occ.synchronize()
print('fuse ->', out)
vol = out[0][1]

gmsh.option.setNumber('Mesh.MeshSizeMax', 0.6)
gmsh.model.mesh.generate(2)

# 体积增量校验: 原件 STL 体积 vs 填充后网格体积
def read_stl_tris(p):
    d = open(p, 'rb').read()
    n = struct.unpack('<I', d[80:84])[0]
    return [struct.unpack('<12f', d[84+i*50:84+i*50+48])[3:12] for i in range(n)]

old_tris = read_stl_tris(PART1)
v_old = mesh_volume([(t[0:3], t[3:6], t[6:9]) for t in old_tris])

# 提取填充后 vol 表面三角 (模型系 mm)
tris = []
sufs = gmsh.model.getBoundary([(3, vol)], oriented=False, recursive=False)
sufs = [s if isinstance(s, (list, tuple)) else (2, s) for s in sufs]
for _, s in sufs:
    et, etag, enodes = gmsh.model.mesh.getElements(2, s)
    for typ, etgs, flat in zip(et, etag, enodes):
        assert typ == 2, typ  # 三角
        for i in range(0, len(flat), 3):
            tris.append((int(flat[i]), int(flat[i+1]), int(flat[i+2])))
nt, nxyz, _ = gmsh.model.mesh.getNodes()
XYZ = {int(t): (nxyz[3*i], nxyz[3*i+1], nxyz[3*i+2]) for i, t in enumerate(nt)}
tris_m = [(XYZ[a], XYZ[b], XYZ[c]) for a, b, c in tris]
v_new = mesh_volume(tris_m)
dv = v_new - v_old
v_cyl_expect = math.pi * ((CONE['r0']-0.45)**2 * 8.7 / 1e3 + 0)  # mm³ 量级参考 (粗)
print('体积: 原 %.0f mm³ -> 填充 %.0f mm³  (Δ=%.0f mm³ ≈ %.2f cm³)' % (v_old, v_new, dv, dv/1000))
ne, bad = edge_check(tris_m)
print('流形: %d 边, 非2流形边 %d %s' % (ne, len(bad), '(BAD)' if bad else '(OK)'))
if bad:
    print('样本:', bad[:3])

# 写 part_1 (备份原件)
shutil.copy(PART1, PART1 + '.bak_nosehole')
def write_stl(p, ts):
    with open(p, 'wb') as f:
        f.write(b'binary STL (fill_nose)').ljust(80, b' ') if False else f.write(b'binary STL (fill_nose)'.ljust(80, b' '))
        f.write(struct.pack('<I', len(ts)))
        for a, b, c in ts:
            u = [b[i]-a[i] for i in range(3)]; w = [c[i]-a[i] for i in range(3)]
            nn = [u[1]*w[2]-u[2]*w[1], u[2]*w[0]-u[0]*w[2], u[0]*w[1]-u[1]*w[0]]
            ln = math.sqrt(sum(x*x for x in nn)) or 1.0
            f.write(struct.pack('<12fH', nn[0]/ln, nn[1]/ln, nn[2]/ln, *a, *b, *c, 0))
write_stl(PART1, tris_m)
print('part_1 -> %.1f KB (原件备份 .bak_nosehole)' % (os.path.getsize(PART1)/1024))

# 导出填充后全量 STEP
gmsh.write(OUT_STEP)
print('filled STEP ->', OUT_STEP)
gmsh.finalize()
print('DONE')
