#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""t×r 二维直方 — 定位管壁带 (t, r) 位置"""
import struct, json
import numpy as np

def load(p):
    d = open(p, 'rb').read()
    n = int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    return a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64).reshape(-1, 3)

u = np.array([0.0, np.sqrt(.5), np.sqrt(.5)])
e1 = np.cross(u, [1.0, 0, 0]); e1 /= np.linalg.norm(e1)
e2 = np.cross(u, e1)
P = load('cad/v1/cfd_parallel/fin_1.stl')
ref = np.array([s for s in json.load(open('cad/v1/cfd_parallel/airframe_assembly.json', encoding='utf-8'))['control_surfaces'] if s['name'] == 'fin_1'][0]['hinge_line'][0])
V = P - ref
t = V @ u
rad = np.sqrt(np.clip((V*V).sum(1) - t*t, 0, None)) * 1000.0
tm = t * 1000.0
tbins = np.arange(-17, 18, 1.0)
rbins = np.arange(0, 8.01, 0.25)
H, te, re = np.histogram2d(tm, rad, bins=[tbins, rbins])
print('t档 -> 峰径向 (r_mm:count)')
for i in range(len(tbins) - 1):
    col = H[i]
    if col.sum() < 5:
        continue
    k = int(col.argmax())
    print('t %5.1f..%4.1f: peak r=%.2f (%d) | total %d' % (tbins[i], tbins[i+1], re[k] + 0.125, col[k], int(col.sum())))
