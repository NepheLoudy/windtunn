#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""平行零位 v4 — 绕真铰链轴 (双耳孔心连线) 重做平行化 (曼波 10-31 第四次目视指正)

v3 错轴根因: hinges_analytic 的"解析轴"是舵根半管壳 (r=2.0, 180°弧, x=-85.73)
的轴 — 那是导引套筒, 不是铰链! 真轴 = 每片舵两个整圆孔 (销帽孔 r=1.9 + 销杆孔
r=1.15) 的孔心连线 (x=-87.615, 四轴汇交于弹轴 hub 点), body 侧有严格同轴的
r=1.05 销杆 / r=1.915 销帽座 / r=2.5 挡圈 (find_hinges_true.py 验证 线距=0.0000)。
v3 绕套筒轴转 45° → 舵整体平移 2·1.89·sin(22.5°) ≈ 1.45mm → 孔与销不同轴。

v4 自检 (物理定义推导, 吸取 v3 中位数判据失效教训):
  ① 双符号自动判别: ±角度都试, |n_x| 30%分位≈0 者胜 (历史符号债务一刀斩断)
  ② 孔径不变性: 两耳站位附近的径向聚类应各自保持 r≈1.9 / r≈1.15 (旋转不变性)
  ③ 与 body 干涉检查: cKDTree 最小间距 > 0.02mm
  ④ 耳孔与 body 销同轴: 孔心在真轴上 (构造保证), 数值复核径向间隙
"""
import json
import math
import struct
import numpy as np

FRAME = None
try:
    from scipy.spatial import cKDTree
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False


def load_pts(p):
    d = open(p, 'rb').read()
    n = struct.unpack('<I', d[80:84])[0]
    pts = []
    for i in range(n):
        v = struct.unpack('<12fH', d[84 + i * 50:84 + i * 50 + 50])[3:12]
        pts += [v[0:3], v[3:6], v[6:9]]
    return pts


def rot_axis(pts, p0, u, deg):
    th = math.radians(deg); c, s = math.cos(th), math.sin(th)
    kx, ky, kz = u
    out = []
    for (x, y, z) in pts:
        vx, vy, vz = x - p0[0], y - p0[1], z - p0[2]
        dot = vx * kx + vy * ky + vz * kz
        cx, cy, cz = ky * vz - kz * vy, kz * vx - kx * vz, kx * vy - ky * vx
        out.append((p0[0] + vx * c + cx * s + kx * dot * (1 - c),
                    p0[1] + vy * c + cy * s + ky * dot * (1 - c),
                    p0[2] + vz * c + cz * s + kz * dot * (1 - c)))
    return out


def write_tris(p, tris):
    with open(p, 'wb') as f:
        f.write(b'binary STL (parallel v4 true-hinge-axis)'.ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        for a, b, c in tris:
            u = [b[k] - a[k] for k in range(3)]; v = [c[k] - a[k] for k in range(3)]
            nn = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            ln = math.sqrt(sum(x * x for x in nn)) or 1.0
            f.write(struct.pack('<12fH', nn[0] / ln, nn[1] / ln, nn[2] / ln, *a, *b, *c, 0))


def toB(p):  # STEP mm -> B m
    return [-(p[2] - 105.5) / 1000.0, (p[1] - 0.2) / 1000.0, (p[0] + 0.1) / 1000.0]


ang = json.load(open('cad/v1/parallel_angles.json'))
true_h = json.load(open('hinges_true.json'))
FINS = {'fin_1': 24, 'fin_2': 26, 'fin_3': 28, 'fin_4': 30}

report = {}
import os
os.makedirs('cad/v1/cfd_parallel', exist_ok=True)
for name, part in FINS.items():
    th = true_h[name]
    pB = np.array(th['point_B_mm'])                 # B mm
    uB = np.array(th['axis_B'])
    # B -> STEP mm (v3 同款逆变换, 已验证)
    pSTEP = np.array([pB[2] - 0.1, pB[1] + 0.2, -pB[0] + 105.5])
    uSTEP = np.array([uB[2], uB[1], -uB[0]]); uSTEP /= np.linalg.norm(uSTEP)
    pts = load_pts('cad/v1/parts/part_%d.stl' % part)

    # ---- ① 双符号判别 ----
    cand = {}
    for sgn in (+1, -1):
        rot = rot_axis(pts, pSTEP, uSTEP, sgn * ang[name])
        tris = [(toB(rot[3 * i]), toB(rot[3 * i + 1]), toB(rot[3 * i + 2])) for i in range(len(rot) // 3)]
        nx = []
        for a1, b1, c1 in tris:
            u1 = np.subtract(b1, a1); v1 = np.subtract(c1, a1)
            n = np.cross(u1, v1); ln = np.linalg.norm(n)
            if ln > 1e-12:
                nx.append(abs(n[0] / ln))
        cand[sgn] = (float(np.quantile(nx, 0.3)), tris)
    ok = {s: q for s, (q, _) in cand.items() if q < 0.3}
    if len(ok) != 1:
        print('%s: 双符号判别歧义 %s — 中止' % (name, {s: round(q, 3) for s, (q, _) in cand.items()}))
        raise SystemExit(1)
    sgn = list(ok)[0]
    nx_med, tris = cand[sgn]
    P = np.array([v for t in tris for v in t])       # B m

    # 轴 (B m) 与耳站位
    rB = pB / 1000.0
    V = P - rB
    t_ax = V @ uB                                     # 轴向坐标 (m)
    rad = np.sqrt(np.clip((V * V).sum(1) - t_ax * t_ax, 0, None))  # m

    # ---- ② 孔径不变性: 两耳站位 (孔心沿轴 ± 孔长/2) 的径向中位 ----
    eye_checks = {}
    for hole in th['holes']:
        hc = np.array(hole['cB_mm']) / 1000.0
        t_eye = float((hc - rB) @ uB)
        hl = hole['len_mm'] / 1000.0
        m = (np.abs(t_ax - t_eye) < 0.5 * hl) & (rad < 2.6e-3)
        r_med = float(np.median(rad[m])) * 1000.0 if m.sum() > 20 else -1
        eye_checks['r%.2f@%s' % (hole['r_mm'], [round(float(x) * 1000, 1) for x in hc[1:]])] = {
            'r_median_mm': round(r_med, 3), 'expect_mm': hole['r_mm'], 'pts': int(m.sum())}

    # ---- ③ 干涉检查 (vs body.stl, B m) ----
    inter = None
    if HAVE_SCIPY:
        bpts = []
        d = open('cad/v1/cfd_parallel/body.stl', 'rb').read()
        nb = struct.unpack('<I', d[80:84])[0]
        for i in range(nb):
            v = struct.unpack('<12fH', d[84 + i * 50:84 + i * 50 + 50])[3:12]
            bpts += [v[0:3], v[3:6], v[6:9]]
        tree = cKDTree(np.array(bpts))
        dd, _ = tree.query(P, k=1)
        inter = float(dd.min()) * 1000.0
        inter = round(inter, 3)

    # ---- ④ 耳孔与 body 销同轴复核: 孔心到真轴线径向距离 (构造上应为 0) ----
    hole_axis_resid = []
    for hole in th['holes']:
        hc = np.array(hole['cB_mm']) / 1000.0
        w = hc - rB
        hole_axis_resid.append(float(np.linalg.norm(w - (w @ uB) * uB)) * 1000.0)

    report[name] = {
        'chosen_sign': sgn, 'angle_used': sgn * ang[name],
        'face_nx_q30': round(nx_med, 4),
        'eyes': eye_checks,
        'body_min_gap_mm': inter,
        'hole_center_on_axis_resid_mm': [round(x, 5) for x in hole_axis_resid],
    }
    print('%s: 符号%+d (%.3f°) |n_x|q30=%.3f | 干涉=%.3fmm | 孔径复核=%s | 孔心轴残差=%s' % (
        name, sgn, sgn * ang[name], nx_med, inter,
        {k: v['r_median_mm'] for k, v in eye_checks.items()},
        report[name]['hole_center_on_axis_resid_mm']))
    write_tris('cad/v1/cfd_parallel/%s.stl' % name, tris)

json.dump(report, open('parallel_v4_selfcheck.json', 'w'), indent=1)
print('-> cad/v1/cfd_parallel/fin_*.stl (v4 true-axis)')
