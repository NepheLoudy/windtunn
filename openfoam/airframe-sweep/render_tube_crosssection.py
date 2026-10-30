#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管段截面仲裁图 — 垂直铰链轴切片, 管内外壁圆环 + 三候选轴心
圆环的圆心在哪, 一眼可辨。自画自判 + 交曼波复核。"""
import struct, json, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def load(p):
    d = open(p, 'rb').read()
    n = int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    return a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64).reshape(-1, 3)

name = 'fin_1'
u = np.array([0.0, np.sqrt(.5), np.sqrt(.5)])
e1 = np.cross(u, [1.0, 0, 0]); e1 /= np.linalg.norm(e1)
e2 = np.cross(u, e1)
P = load('cad/v1/cfd_parallel/%s.stl' % name)
ref = np.array([s for s in json.load(open('cad/v1/cfd_parallel/airframe_assembly.json', encoding='utf-8'))['control_surfaces'] if s['name'] == name][0]['hinge_line'][0])
V = P - ref
t = V @ u
# 截面: 取 t ∈ [-1, 0] mm 的薄片 (孔段中部)
sec = (t > -0.002) & (t < -0.001)
A = (V @ e1)[sec] * 1000.0
B = (V @ e2)[sec] * 1000.0
print('截面点数:', sec.sum())

fig, ax = plt.subplots(figsize=(11, 10))
ax.scatter(A, B, s=4, c='#666', label='fin 根部截面点')
# 候选轴心 (各自基转统一 e1/e2 基)
def to_common(c_mm_B, base='asm'):
    Vc = np.array(c_mm_B) - ref * 1000.0
    if base == 'asm':
        return Vc @ e1, Vc @ e2
    if base == 'hough':
        return Vc @ e1, Vc @ e2  # hough 存的 center_B 是绝对 B 坐标, 基相同
c_asm = ref * 1000.0
hough = json.load(open('tube_axis_hough.json'))[name]['center_B']
indep = json.load(open('bore_axis_independent.json'))[name]['center_B']
for tag, cB, col, mk in (('assembly(现轴)', np.array(c_asm)*1000.0*0+ref*1000.0, 'c', 'o'),
                         ('Hough', np.array(hough)*1000.0, 'm', 's'),
                         ('indepHough', np.array(indep)*1000.0, 'g', '^')):
    Vc = cB - ref * 1000.0
    ax.plot(Vc @ e1, Vc @ e2, mk, color=col, markersize=12, label=tag)
ax.set_xlabel('e1 [mm]'); ax.set_ylabel('e2 [mm]')
ax.set_aspect('equal'); ax.grid(alpha=.3)
ax.legend()
ax.set_title('%s 根部截面 (t=-1..-2mm): 管壁圆环与三候选轴心' % name)
out = 'cad/v1/tube_crosssection_arbitration.png'
plt.savefig(out, dpi=130, bbox_inches='tight')
print('saved', out)
