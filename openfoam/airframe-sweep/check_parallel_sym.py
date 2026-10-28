#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""平行基准镜像检验: fin_1↔4, fin_2↔3 (y 镜像) — 曼波预期的绝对对称验证"""
import struct, math

def load(p):
    d=open(p,'rb').read(); n=struct.unpack('<I',d[80:84])[0]
    return [struct.unpack('<12fH', d[84+i*50:84+i*50+50])[3:12] for i in range(n)]

for (a_name,b_name) in (('fin_1','fin_4'),('fin_2','fin_3')):
    A=load(f'cad/v1/cfd_parallel/{a_name}.stl')
    B=load(f'cad/v1/cfd_parallel/{b_name}.stl')
    maxd=0.0
    for a in A[::37]:
        best=1e9
        for b in B[::37]:
            d=math.sqrt((a[0]-b[0])**2+(-a[1]-b[1])**2+(a[2]-b[2])**2)
            if d<best: best=d
        if best>maxd: maxd=best
    print(f"{a_name} <-> {b_name} (y-mirror): max dev = {maxd*1000:.2f} mm")
