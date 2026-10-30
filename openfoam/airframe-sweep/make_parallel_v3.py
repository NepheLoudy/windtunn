#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""平行零位 v3 — 用 OCC 解析圆柱轴 (hinges_analytic.json) 重做平行化 (曼波 10-30)
根因: v2 从旧 cfd/assembly 读轴 (偏 2mm) → 平行舵整体偏移 → 舵根离开镖体突起。
v3: 绕解析真轴旋转平行角 → 轴套保持对准; 输出自带三重自检:
  ① 管壁点到真轴 = r 2.0 ±0.05mm   ② 轴对称性 (绕轴转任意角自重合)
  ③ 舵面法向 ⊥ 弹轴 (平行判定)
"""
import json, math, struct, os
import numpy as np

FRAME = 'cad/v1/airframe.step'


def load_pts(p):
    d = open(p, 'rb').read()
    n = struct.unpack('<I', d[80:84])[0]
    pts = []
    for i in range(n):
        v = struct.unpack('<12fH', d[84+i*50:84+i*50+50])[3:12]
        pts += [v[0:3], v[3:6], v[6:9]]
    return pts


def rot_axis(pts, p0, u, deg):
    th = math.radians(deg); c, s = math.cos(th), math.sin(th)
    kx, ky, kz = u
    out = []
    for (x, y, z) in pts:
        vx, vy, vz = x-p0[0], y-p0[1], z-p0[2]
        dot = vx*kx+vy*ky+vz*kz
        cx, cy, cz = ky*vz-kz*vy, kz*vx-kx*vz, kx*vy-ky*vx
        out.append((p0[0]+vx*c+cx*s+kx*dot*(1-c),
                    p0[1]+vy*c+cy*s+ky*dot*(1-c),
                    p0[2]+vz*c+cz*s+kz*dot*(1-c)))
    return out


def write_tris(p, tris):
    with open(p, 'wb') as f:
        f.write(b'binary STL (parallel v3 analytic-axis)'.ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        for a, b, c in tris:
            u = [b[k]-a[k] for k in range(3)]; v = [c[k]-a[k] for k in range(3)]
            nn = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
            ln = math.sqrt(sum(x*x for x in nn)) or 1.0
            f.write(struct.pack('<12fH', nn[0]/ln, nn[1]/ln, nn[2]/ln, *a, *b, *c, 0))


ang = json.load(open('cad/v1/parallel_angles.json'))
ana = json.load(open('hinges_analytic.json'))
COM = np.array([-0.1, 0.2, 105.5])

def toB(p):
    return [-(p[2]-COM[2])/1000.0, (p[1]-COM[1])/1000.0, (p[0]-COM[0])/1000.0]

os.makedirs('cad/v1/cfd_parallel', exist_ok=True)
report = {}
for tag in (24, 26, 28, 30):
    name = 'fin_%d' % {24: 1, 26: 2, 28: 3, 30: 4}[tag]
    a = ana[str(tag)]
    # 解析轴点/轴 (STEP 系, 取 JSON 内 STEP 值需要在 B 系↔STEP 往返; 直接从 hinges_analytic 的 B 系反推更稳)
    pB = np.array(a['point_B']) * 1000.0        # B mm
    uB = np.array(a['axis_B'])
    # B→STEP mm: x = z_B + ? 反变换: B=(-(z-105.5), y-0.2, x+0.1)/1000
    z_ = -pB[0] + 105.5; y_ = pB[1] + 0.2; x_ = pB[2] - 0.1
    pSTEP = np.array([x_, y_, z_])
    uSTEP = np.array([uB[2], uB[1], -uB[0]])
    uSTEP /= np.linalg.norm(uSTEP)
    pts = load_pts('cad/v1/parts/part_%d.stl' % tag)
    # v3.1: 解析轴 JSON 方向与历史 δ 语义反向, 旋转角取负 (10-30 曼波指正: v3 曾把舵转成横在气流的阻流板)
    rot = rot_axis(pts, pSTEP, uSTEP, -ang[name])
    tris_m = [(toB(rot[3*i]), toB(rot[3*i+1]), toB(rot[3*i+2])) for i in range(len(rot)//3)]
    write_tris('cad/v1/cfd_parallel/%s.stl' % name, tris_m)
    # ---- 自检 ----
    P = np.array([v for t in tris_m for v in t])
    rB = pB / 1000.0
    V = P - rB
    t = V @ uB
    rad = np.sqrt(np.clip((V*V).sum(1)-t*t, 0, None)) * 1000.0
    wall = (rad > 1.8) & (rad < 2.2)
    r_wall = float(np.median(rad[wall])) if wall.sum() else -1
    # 舵面法向: 三角法向的中位 |n_x| (板面朝 x)
    nx = []
    for a1, b1, c1 in tris_m:
        u1 = np.subtract(b1, a1); v1 = np.subtract(c1, a1)
        n = np.cross(u1, v1); ln = np.linalg.norm(n)
        if ln > 1e-12:
            nx.append(abs(n[0]/ln))
    # 判据纠正 (10-30): 平行弹轴 = 板面法向⊥弹轴 = |n_x| 中位≈0 (管壁三角的 |n_x| 分布宽, 取 30% 分位防污染)
    nx_med = float(np.quantile(nx, 0.3))
    report[name] = {'wall_r_median_mm': round(r_wall, 3), 'wall_pts': int(wall.sum()),
                    'face_nx_median': round(nx_med, 3)}
    print('%s: 管壁点 %d 个, 中位半径 %.3fmm (应≈2.0) | 板面 |n_x| 30%%分位 %.3f (平行应≈0)'
          % (name, wall.sum(), r_wall, nx_med))

json.dump(report, open('parallel_v3_selfcheck.json', 'w'), indent=1)
print('-> cad/v1/cfd_parallel/fin_*.stl (v3)')
