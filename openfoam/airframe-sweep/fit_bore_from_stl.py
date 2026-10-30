#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立识别舵面内圆柱孔轴心 — 曼波 10-30 指令: 单独解析舵面特征, 不依赖旧拟合
方法: 轴方向 u 已知 (0,±0.7071,±0.7071 共轴族, 孔的朝向曼波确认过);
     只解轴心位置 (垂直平面内偏移 ox,oy):
       网格搜索 ±3mm → 使径向距离直方图最锐 (双峰: 内孔 r1.63 + 轴套外圆 r2.4,
       两个圆柱同轴 → 距离集合的"峰锐度" = 负熵近似, 用分箱最大计数比较)
数据: cfd_parallel/fin_*.stl 舵根区 (x∈[-0.090,-0.082]) 顶点
输出: 每舵独立孔心 (B 系) + 与 assembly 现值偏差
"""
import json, math
import numpy as np

def load_verts(p):
    d = open(p, 'rb').read()
    n = struct.unpack('<I', d[80:84])[0] if False else int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    return a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64).reshape(-1, 3)

import struct

def sharpness(dists, binw=0.02):
    """Hough 环计数 + 内空约束: 环带 [1.35,1.95] 计数 − 4×内侧(d<1.2)计数
    真孔心: 环=孔内表面点, 内侧空 → 高分; 偏心假峰(套住轴套外圆弧): 内侧扫到实体点 → 负分"""
    if len(dists) < 10:
        return -1
    ring = int(((dists > 1.35) & (dists < 1.95)).sum())
    inner = int((dists < 1.2).sum())
    return ring - 4 * inner

asm = json.load(open('cad/v1/cfd_parallel/airframe_assembly.json', encoding='utf-8'))
AXES = {  # 铰链方向族 (B 系), 孔朝向曼波已确认
    'fin_1': np.array([0.0, math.sqrt(.5), math.sqrt(.5)]),
    'fin_2': np.array([0.0, math.sqrt(.5), -math.sqrt(.5)]),
    'fin_3': np.array([0.0, -math.sqrt(.5), -math.sqrt(.5)]),
    'fin_4': np.array([0.0, -math.sqrt(.5), math.sqrt(.5)]),
}
out = {}
for name, u in AXES.items():
    P = load_verts('cad/v1/cfd_parallel/%s.stl' % name)
    root = P[(P[:, 0] > -0.090) & (P[:, 0] < -0.082)]
    if len(root) < 50:
        print(name, '根部点不足', len(root)); continue
    # 垂直 u 的正交基
    e1 = np.cross(u, [1.0, 0, 0])
    if np.linalg.norm(e1) < 1e-6:
        e1 = np.cross(u, [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(u, e1)
    # 点在垂直平面坐标 (相对 assembly 现值参考点 — 搜的是孔心偏移)
    ref = np.array(json.loads(json.dumps(asm['control_surfaces'][0]))['hinge_line'][0]) if name == 'fin_1' else None
    # 每舵自己的 assembly 现值
    for s_ in asm['control_surfaces']:
        if s_['name'] == name:
            ref = np.array(s_['hinge_line'][0])
    R = root - ref
    a = R @ e1
    b = R @ e2
    # 网格搜索轴心偏移 (±3mm, 0.05 步) → 锐度最大化
    best = (-1, 0.0, 0.0)
    for ox in np.arange(-3.0, 3.01, 0.1):
        for oy in np.arange(-3.0, 3.01, 0.1):
            d = np.sqrt((a - ox/1000.0)**2 + (b - oy/1000.0)**2) * 1000.0  # mm
            s = sharpness(d)
            if s > best[0]:
                best = (s, ox, oy)
    s0, ox, oy = best
    # 细化 ±0.1mm 步长 0.01
    for dx in np.arange(ox-0.1, ox+0.101, 0.02):
        for dy in np.arange(oy-0.1, oy+0.101, 0.02):
            d = np.sqrt((a - dx/1000.0)**2 + (b - dy/1000.0)**2) * 1000.0
            s = sharpness(d)
            if s > best[0]:
                best = (s, dx, dy)
    s0, ox, oy = best
    # 孔心 B 系: 原点取根部切片中心 (x=-0.086), 偏移量在 e1/e2 基下
    center_B = ref + (ox/1000.0) * e1 + (oy/1000.0) * e2
    d = np.sqrt((a - ox/1000.0)**2 + (b - oy/1000.0)**2) * 1000.0
    inner = d[d < 2.0]
    r1 = float(np.percentile(inner, 50)) if len(inner) else -1.0  # 内孔半径估计
    cur = None
    for s_ in asm['control_surfaces']:
        if s_['name'] == name:
            cur = np.array(s_['hinge_line'][0])
    dev = np.linalg.norm(center_B - cur) * 1000.0 if cur is not None else -1
    out[name] = {'center_B': [round(float(x), 6) for x in center_B],
                 'sharpness': round(float(s0), 3), 'r_bore_mm': round(float(r1), 3),
                 'dev_vs_assembly_mm': round(float(dev), 3)}
    print('%s: 独立孔心 B=[%.5f, %.5f, %.5f] 锐度=%.3f r内孔≈%.2fmm | 与 assembly 偏差 %.3fmm'
          % (name, *center_B, s0, r1, dev))

json.dump(out, open('bore_axis_independent.json', 'w'), indent=1)
print('-> bore_axis_independent.json')
