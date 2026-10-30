#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3 平行舵绝对姿态验证 — 每片: 板面法向 / 质心 / 展向 / 最大展距"""
import struct, json
import numpy as np

def load(p):
    d = open(p, 'rb').read()
    n = int.from_bytes(d[80:84], 'little')
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    return a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64)

asm = json.load(open('cad/v1/cfd_parallel/airframe_assembly.json', encoding='utf-8'))
for s in asm['control_surfaces']:
    nm = s['name']
    T = load('cad/v1/cfd_parallel/%s.stl' % nm)
    w = []
    nv = []
    cent = []
    for t in T:
        a1, b1, c1 = t
        u1 = np.subtract(b1, a1); v1 = np.subtract(c1, a1)
        nn = np.cross(u1, v1); ln = np.linalg.norm(nn)
        if ln < 1e-12:
            continue
        nn = nn / ln
        nv.append(nn); w.append(ln/2.0)
        cent.append((a1+b1+c1)/3.0)
    w = np.array(w); nv = np.array(nv)
    n_mean = (nv * w[:, None]).sum(0) / w.sum()
    c = np.array(cent).mean(0)
    p0 = np.array(s['hinge_line'][0]); u0 = np.array(s['hinge_axis'], float); u0 /= np.linalg.norm(u0)
    V = np.array(cent) - p0
    tt = V @ u0
    rr = np.sqrt((V*V).sum(1) - tt*tt)
    imax = int(rr.argmax())
    sd = np.array(cent[imax]) - p0
    sd = sd - (sd @ u0)*u0; sd /= np.linalg.norm(sd)
    print('%s: 板面法向=[%+.3f,%+.3f,%+.3f] 质心=[%.4f,%.4f,%.4f] 展向=[%+.2f,%+.2f,%+.2f] 最大展距=%.1fmm'
          % (nm, n_mean[0], n_mean[1], n_mean[2], c[0], c[1], c[2], sd[0], sd[1], sd[2], rr.max()*1000))
