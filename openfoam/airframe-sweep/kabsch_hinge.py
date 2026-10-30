#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kabsch 刚体配准反解真实铰链旋转 — 终局仲裁 (曼波 10-30)
part_24 (折叠位原件) 与 fin_1 (平行位) 是同一刚体两个姿态。
Kabsch 配准解出 R,t → 旋转轴(特征值1的特征向量) + 轴上点。
结果与 assembly/hinges_refined/Hough 三方对比; 四舵交叉验证。"""
import struct, json
import numpy as np

COM = np.array([-0.1, 0.2, 105.5])
def toB(P):
    """模型系 mm → B 系米制: (x,y,z)→(-(z-105.5), y-0.2, x+0.1)/1000"""
    out = np.empty_like(P)
    out[:,0] = -(P[:,2]-COM[2])/1000.0
    out[:,1] = (P[:,1]-COM[1])/1000.0
    out[:,2] = (P[:,0]+0.1)/1000.0
    return out
def load(p, to_b=False):
    d = open(p, 'rb').read()
    n = int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    P = a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64).reshape(-1, 3)
    return toB(P) if to_b else P

def kabsch(P, Q):
    """P→Q 的刚体变换 (假设同一点序; STL 顶点序可能不同 → 用最近邻迭代或直接重心+对应)"""
    cp, cq = P.mean(0), Q.mean(0)
    H = (P - cp).T @ (Q - cq)
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    tvec = cq - R @ cp
    return R, tvec

def rotation_axis_angle(R):
    """从旋转矩阵提取轴 (单位向量) 与角 (rad)"""
    ang = math.acos(np.clip((np.trace(R) - 1) / 2, -1, 1))
    if abs(ang) < 1e-9:
        return np.array([1.0, 0, 0]), 0.0
    # 轴: R 的转轴 = (R - R^T) 的反对称部分
    ax = np.array([R[2,1]-R[1,2], R[0,2]-R[0,1], R[1,0]-R[0,1]])
    ax = ax / np.linalg.norm(ax)
    return ax, ang

def axis_point(R, tvec, axis, ang):
    """转轴上的点: p = (t + 轴向分量修正)/... 标准公式: 轴过点 c, c = (I-R)^{-1} t 的最小范数解"""
    A = np.eye(3) - R
    # 最小范数解 c = A^T (A A^T)^{-1} t
    c = A.T @ np.linalg.solve(A @ A.T + 1e-12*np.eye(3), tvec)
    return c

import math

MAP = {24: 1, 26: 2, 28: 3, 30: 4}
result = {}
for tag, k in sorted(MAP.items()):
    Pf = toB(load('cad/v1/parts/part_%d.stl' % tag))  # 折叠位原件 → B 系米制
    Pp = load('cad/v1/cfd_parallel/fin_%d.stl' % k)  # 平行位
    # 顶点序可能不一致 → 用重心对齐 + 最近邻迭代太重; 先试直接同序 (make_parallel_v2 逐顶点旋转, 序保持!)
    if len(Pf) != len(Pp):
        print('fin_%d: 顶点数不同 (%d vs %d) — 跳过直接 Kabsch' % (k, len(Pf), len(Pp)))
        continue
    R, tv = kabsch(Pf, Pp)
    # 配准残差
    res = Pf @ R.T + tv - Pp
    rms = float(np.sqrt((res**2).sum(1).mean())) * 1000
    ax, ang = rotation_axis_angle(R)
    cpt = axis_point(R, tv, ax, ang)
    # 轴向转到 B 系下表达 (STEP→B: (x,y,z)→(-z,y,x), 方向)
    aB = np.array([-ax[2], ax[1], ax[0]]); aB /= np.linalg.norm(aB)
    cB = np.array([-(cpt[2]-105.5), cpt[1]-0.2, cpt[0]+0.1]) / 1000.0
    # 与 assembly 对比
    asm = json.load(open('cad/v1/cfd_parallel/airframe_assembly.json', encoding='utf-8'))
    s = asm['control_surfaces'][k-1]
    ref = np.array(s['hinge_line'][0])
    dev = float(np.linalg.norm(cB - ref) * 1000)
    # 轴向夹角
    axm = np.array(s['hinge_axis'], float); axm /= np.linalg.norm(axm)
    angdev = float(math.degrees(math.acos(np.clip(aB @ axm, -1, 1))))
    print('fin_%d: Kabsch rms=%.4fmm 转角=%.3f° | 轴心 B=[%.5f,%.5f,%.5f] vs assembly 偏 %.3fmm | 轴向差 %.3f°'
          % (k, rms, math.degrees(ang), cB[0], cB[1], cB[2], dev, angdev))
    result['fin_%d' % k] = {'center_B': [round(float(x), 6) for x in cB],
                            'axis_B': [round(float(x), 6) for x in aB],
                            'kabsch_rms_mm': round(rms, 4),
                            'angle_deg': round(float(math.degrees(ang)), 3),
                            'dev_vs_assembly_mm': round(dev, 3)}

json.dump(result, open('kabsch_hinge_axis.json', 'w'), indent=1)
print('-> kabsch_hinge_axis.json')
