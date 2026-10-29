#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""舵偏扫掠与弹体干涉检查 — 回答曼波"双舵面卡住是渲染还是分析问题" (2026-10-30)

对每片舵: 绕新铰链轴 (hinges_refined→assembly) 从 δ=0 转到 ±45°,
采样舵面顶点到 body.stl (融合体) 三角面片的最小距离。物理上:
  δ=±45° 之一 = 折叠位 (贴翼面, 距离≈0)
  反方向      = 应该外翻远离弹体
若某方向 δ=20° 就深插弹体 (距离<0) → 旋转方向/轴有错; 渲染与 CFD 同轴同向则两处同病。

输出: 每舵每角度 min_dist (mm, 负=穿透), 判定折叠方向。
"""
import json, math, struct
import numpy as np

ROOT = '.'
def load_stl(p, step=1):
    d = open(p, 'rb').read()
    n = struct.unpack('<I', d[80:84])[0]
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    tris = a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64)
    return tris[::step]

body_tris = load_stl('cad/v1/cfd_parallel/body.stl', step=4)  # 35k tris
bpts = body_tris.reshape(-1, 3)
print('body: %d tris (decimated), bbox x[%.3f %.3f]' % (len(body_tris), bpts[:,0].min(), bpts[:,0].max()))

asm = json.load(open('cad/v1/cfd_parallel/airframe_assembly.json', encoding='utf-8'))
ref = json.load(open('hinges_refined.json'))

def rot_axis(P, point, axis, deg):
    q = math.radians(deg)
    c, s = math.cos(q), math.sin(q)
    W = P - point
    cross = np.cross(np.broadcast_to(axis, W.shape), W)
    return point + W*c + cross*s + np.outer(W @ axis, axis)*(1-c)

# 粗近距离: 对舵面降采样点到 body 顶点云的最小距离 (KD 没有就用网格哈希近似)
from collections import defaultdict
def dist_cloud(pts, ref_pts, cell=0.004):
    """点到点云近似最小距离 (cell 哈希), 返回 mm"""
    grid = defaultdict(list)
    for p in ref_pts:
        grid[(int(p[0]/cell), int(p[1]/cell), int(p[2]/cell))].append(p)
    out = []
    for p in pts:
        best = 1e9
        cx, cy, cz = int(p[0]/cell), int(p[1]/cell), int(p[2]/cell)
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for dz in (-1,0,1):
                    for q in grid.get((cx+dx,cy+dy,cz+dz), ()):
                        d = (p[0]-q[0])**2+(p[1]-q[1])**2+(p[2]-q[2])**2
                        if d < best: best = d
        out.append(math.sqrt(best) if best < 1e8 else 99.0)
    return np.array(out) * 1000

for i, s in enumerate(asm['control_surfaces']):
    tris = load_stl('cad/v1/cfd_parallel/%s' % s['mesh'])
    P = tris.reshape(-1, 3)
    P = np.unique(P[::11], axis=0)  # 降采样 ~600 点
    hp = np.array(s['hinge_line'][0])
    ax = np.array(s['hinge_axis']); ax /= np.linalg.norm(ax)
    # 只取离轴 >10mm 的展向段 (排除根部附着区)
    span = np.linalg.norm((P - hp) - np.outer((P - hp) @ ax, ax), axis=1)
    P = P[span > 0.010]
    row = ['fin_%d:' % (i+1)]
    for deg in (-45, -20, 0, 20, 45):
        Q = rot_axis(P, hp, ax, deg) if deg else P
        dmin = dist_cloud(Q, bpts).min()
        row.append('%+d°:%6.1f' % (deg, dmin))
    print('  '.join(row))
print('(mm, 展向>10mm 段; 0=贴合, 负=穿透; 折叠方向=±45 中贴近的一侧)')
