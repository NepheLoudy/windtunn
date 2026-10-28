#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计算每片舵的精确平行化旋转角 (带符号, 绕各自铰链轴)"""
import json, math, struct

def load(p):
    d=open(p,'rb').read(); n=struct.unpack('<I',d[80:84])[0]
    pts=[]
    for i in range(n):
        v=struct.unpack('<12fH', d[84+i*50:84+i*50+50])[3:12]
        pts += [v[0:3], v[3:6], v[6:9]]
    return pts

def pca_axes(pts):
    n=len(pts)
    c=[sum(p[j] for p in pts)/n for j in range(3)]
    C=[[sum((p[a]-c[a])*(p[b]-c[b]) for p in pts)/n for b in range(3)] for a in range(3)]
    def power(M,seed):
        v=list(seed)
        for _ in range(300):
            v=[sum(M[a][b]*v[b] for b in range(3)) for a in range(3)]
            ln=math.sqrt(sum(x*x for x in v)) or 1
            v=[x/ln for x in v]
        return v
    e1=power(C,[0.3,0.4,0.9])
    C2=[[C[a][b]-sum(e1[k]*C[k][b] for k in range(3))*e1[a] for b in range(3)] for a in range(3)]
    e2=power(C2,[0.5,-0.5,0.5])
    return e1,e2

asm=json.load(open('cad/v1/cfd/airframe_assembly.json',encoding='utf-8'))
out={}
for s in asm['control_surfaces']:
    pts=load(f"cad/v1/cfd/{s['mesh']}")
    espan,echord=pca_axes(pts)
    h=s['hinge_axis']
    dot=sum(echord[k]*h[k] for k in range(3))
    ec_p=[echord[k]-dot*h[k] for k in range(3)]
    ln=math.sqrt(sum(v*v for v in ec_p)); ec_p=[v/ln for v in ec_p]
    xh=sum(1*h[k] for k in range(3))
    x_proj=[(1 if k==0 else 0)-xh*h[k] for k in range(3)]
    lnx=math.sqrt(sum(v*v for v in x_proj)); x_proj=[v/lnx for v in x_proj]
    cosv=sum(ec_p[k]*x_proj[k] for k in range(3))
    cr=[ec_p[1]*x_proj[2]-ec_p[2]*x_proj[1],
        ec_p[2]*x_proj[0]-ec_p[0]*x_proj[2],
        ec_p[0]*x_proj[1]-ec_p[1]*x_proj[0]]
    sinv=sum(cr[k]*h[k] for k in range(3))
    ang=math.degrees(math.atan2(sinv,cosv))
    out[s['name']]=round(ang,3)
    print(f"{s['name']}: 精确平行旋转 = {ang:+.3f}° (绕铰链轴 {h})")
json.dump(out, open('/tmp/parallel_angles.json','w'))
