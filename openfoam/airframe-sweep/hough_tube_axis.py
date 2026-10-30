#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""3D Hough 圆管轴心搜索 — 终局 (曼波 10-30: 空心圆柱的管心即转轴)
联合扫描 (轴心偏移 ox, oy) × 内径 r_in: 计数径向落在 [r_in±0.15] 的根部点数, 全局峰 = 管心。
numpy 广播, 一次算完。四片舵交叉验证。"""
import struct, json
import numpy as np

def load(p):
    d = open(p, 'rb').read()
    n = int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    return a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64).reshape(-1, 3)

AXES = {'fin_1': [0.0, np.sqrt(.5), np.sqrt(.5)],
        'fin_2': [0.0, np.sqrt(.5), -np.sqrt(.5)],
        'fin_3': [0.0, -np.sqrt(.5), -np.sqrt(.5)],
        'fin_4': [0.0, -np.sqrt(.5), np.sqrt(.5)]}
asm = json.load(open('cad/v1/cfd_parallel/airframe_assembly.json', encoding='utf-8'))
out = {}
for name, u in AXES.items():
    u = np.array(u)
    P = load('cad/v1/cfd_parallel/%s.stl' % name)
    ref = np.array([s for s in asm['control_surfaces'] if s['name'] == name][0]['hinge_line'][0])
    V = P - ref
    t = V @ u
    rad = np.sqrt(np.clip((V*V).sum(1) - t*t, 0, None)) * 1000.0
    root = (np.abs(t) < 0.012)
    a = (V @ np.cross(u, [1.0, 0, 0])) * 1000.0   # mm
    e2 = np.cross(u, np.cross(u, [1.0, 0, 0])); e2 /= np.linalg.norm(e2)
    b = (V @ e2) * 1000.0
    a, b, r_all = a[root], b[root], rad[root]
    # Hough: (ox, oy) ∈ ±2.5mm 步 0.1 ; r_in ∈ 0.6-2.4 步 0.1 ; 环宽 ±0.18
    oxs = np.arange(-2.5, 2.51, 0.1)
    best = (-1, 0, 0, 0)
    Ai = a[None, :]; Bi = b[None, :]
    for ox in oxs:
        D1 = np.sqrt((Ai - ox)**2 + (Bi[None, :] - 0)**2)  # b 方向偏移与 ox 耦合, 展开在下
        pass
    # 更稳妥: 双循环偏移, 向量化半径计数
    for ox in oxs:
        for oy in oxs:
            d = np.sqrt((a - ox)**2 + (b - oy)**2)
            h, _ = np.histogram(d, bins=np.arange(0.4, 2.61, 0.1))
            k = h.argmax()
            r_peak = 0.45 + k*0.1
            cnt = int(((d > r_peak-0.18) & (d < r_peak+0.18)).sum())
            if cnt > best[0]:
                best = (cnt, ox, oy, r_peak)
    cnt, ox, oy, r_in = best
    center_B = ref + (ox/1000.0)*np.cross(u, [1.0, 0, 0])/np.linalg.norm(np.cross(u, [1.0, 0, 0])) + (oy/1000.0)*e2v if False else None
    e2v = np.cross(u, np.cross(u, [1.0, 0, 0])); e2v /= np.linalg.norm(e2v)
    e1v = np.cross(u, [1.0, 0, 0]); e1v /= np.linalg.norm(e1v)
    center_B = ref + (ox/1000.0)*e1v + (oy/1000.0)*e2v
    out[name] = {'center_B': [round(float(x), 6) for x in center_B],
                 'r_in_mm': round(float(r_in), 2), 'hough_count': cnt}
    print('%s: 管心 B=[%.5f,%.5f,%.5f]  内径 r=%.1fmm  环点 %d  (相对现轴偏移 %.1f,%.1f mm)'
          % (name, *center_B, r_in, cnt, ox, oy))

json.dump(out, open('tube_axis_hough.json', 'w'), indent=1)
print('-> tube_axis_hough.json')
