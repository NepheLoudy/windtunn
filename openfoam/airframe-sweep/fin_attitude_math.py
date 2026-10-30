#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""舵面姿态量化: 折叠位法向 n0, v3 法向 n3, 以及"要转到平行弹轴(|n_x|≈0)所需的角度"
绕铰链轴 u 转 θ 后法向 n(θ) = n0·cosθ + (u×n0)·sinθ + u(u·n0)(1-cosθ)
解 n(θ)·x̂ = 0 → 正确 θ。对比 v3 实际转过的角度。"""
import struct, json, math
import numpy as np

def load_tris(p):
    d = open(p, 'rb').read()
    n = int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    return a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64)

def plate_normal(tris):
    """面积加权主法向: 取 |n_x| 最小的 30% 三角 (板面, 非管壁/边缘), 加权平均后归一"""
    normals = []
    areas = []
    for t in tris:
        u1 = np.subtract(t[1], t[0]); v1 = np.subtract(t[2], t[0])
        nn = np.cross(u1, v1)
        ln = np.linalg.norm(nn)
        if ln < 1e-12: continue
        normals.append(nn/ln); areas.append(ln/2)
    normals = np.array(normals); areas = np.array(areas)
    nx = np.abs(normals[:, 0])
    k = max(10, int(len(nx)*0.3))
    idx = np.argsort(nx)[:k]           # |n_x| 最小的 30% = 板面
    sel = normals[idx]
    m = sel.mean(0); m /= np.linalg.norm(m)
    if m[0] < 0: m = -m               # 符号统一朝 +x (只影响符号)
    return m

def toB_tris(T):
    out = T.copy()
    out[:, :, 0] = -(T[:, :, 2] - 105.5)/1000.0
    out[:, :, 1] = (T[:, :, 1] - 0.2)/1000.0
    out[:, :, 2] = (T[:, :, 0] + 0.1)/1000.0
    return out

COM = np.array([-0.1, 0.2, 105.5])
def rot_n(n0, u, deg):
    th = np.radians(deg); c, s = np.cos(th), np.sin(th)
    n = n0.copy()
    cr = np.cross(u, n)
    return n*c + cr*s + u*np.dot(u, n)*(1-c)

MAP = {24: ('fin_1', [0.70711, 0.70711, 0.0]),
       26: ('fin_2', [-0.70711, 0.70711, 0.0]),
       28: ('fin_3', [-0.70711, -0.70711, 0.0]),
       30: ('fin_4', [0.70711, -0.70711, 0.0])}
angles = json.load(open('cad/v1/parallel_angles.json'))
ana = json.load(open('hinges_analytic.json'))

for tag, (name, ax_step) in sorted(MAP.items()):
    T0 = load_tris('cad/v1/parts/part_%d.stl' % tag)
    n0 = plate_normal(T0)
    u = np.array(ax_step, float); u /= np.linalg.norm(u)
    # v3 实际法向
    T3 = toB_tris(load_tris('cad/v1/cfd_parallel/%s.stl' % name))
    n3 = plate_normal(T3)
    # v2 (git 里的旧平行舵) — 在 body_occ_fuse_dirty 时代之前, 从 cfd 历史拿不到;
    # 直接算理论角度: 解 n(θ)·x̂ = 0
    # n(θ)·x̂ = n0x c + (u×n0)x s + ux(ux n0x)(1-c) = 0
    a = n0[0] - u[0]*(u[0]*n0[0])
    b = (np.cross(u, n0))[0]
    c0 = u[0]*(u[0]*n0[0])
    # a*c + b*s + c0*(1-c)=0 → (a-c0)*c + b*s = -c0 → R*cos(θ-φ) 形式
    R = math.hypot(a-c0, b)
    phi = math.atan2(b, a-c0)
    ths = [math.atan2(-c0/R, 1) + phi]  # cos(θ-φ) = -c0/R
    ths = [phi + math.acos(max(-1, min(1, -c0/R))), phi - math.acos(max(-1, min(1, -c0/R)))]
    degs = [math.degrees(t) for t in ths]
    # 两个解的法向
    ns = [rot_n(n0, u, d) for d in degs]
    print('vol%d %s: 折叠位法向=[%.3f,%.3f,%.3f]' % (tag, name, *n0))
    print('   v3 实际法向=[%.3f,%.3f,%.3f]  |n3_x|=%.3f (0=平行弹轴 ✓, 1=横在气流 ✗)' % (*n3, abs(n3[0])))
    for d, nn in zip(degs, ns):
        print('   理论解 θ=%+7.2f° → 法向=[%+.3f,%+.3f,%+.3f] |n_x|=%.3f' % (d, *nn, abs(nn[0])))
    print('   v2 角度表: %+7.2f°' % angles[name])
    print()
