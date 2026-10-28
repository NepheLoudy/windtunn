#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""舵偏基准切换 v2: 零位 = 舵面平行于弹轴 (曼波 2026-10-28 定)

从旧基准 (机械零位, 弦向 45° 斜置) 每片舵绕自身铰链轴转 ±45° → 新零位绝对对称。
生成: cad/v1/cfd_parallel/ (新零位 STL + airframe_assembly.json basis=parallel)
旧基准数据保留: T0/T1 的 δ=0 行 = 旧机械零位 (新基准下 ≡ 全舵 +45°/-45° 常量偏置)
"""
import json
import math
import os
import struct

def read_stl(p):
    d=open(p,'rb').read(); n=struct.unpack('<I',d[80:84])[0]
    out=[]
    for i in range(n):
        v=struct.unpack('<12fH', d[84+i*50:84+i*50+50])[3:12]
        out.append([v[0:3],v[3:6],v[6:9]])
    return out

def write_stl(p, tris):
    with open(p,'wb') as f:
        f.write(b"binary STL (parallel basis)".ljust(80,b" "))
        f.write(struct.pack("<I",len(tris)))
        for (a,b,c) in tris:
            u=[b[i]-a[i] for i in range(3)]; v=[c[i]-a[i] for i in range(3)]
            nn=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            ln=math.sqrt(sum(x*x for x in nn)) or 1
            f.write(struct.pack("<12fH", nn[0]/ln, nn[1]/ln, nn[2]/ln,
                                a[0],a[1],a[2],b[0],b[1],b[2],c[0],c[1],c[2],0))

def chord_x_angle(tris):
    pts=[v for t in tris for v in t]
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
    e2=power([[C[a][b]-sum(power(C,[0.3,0.4,0.9])[k]*C[k][b] for k in range(3))*power(C,[0.3,0.4,0.9])[a]
               for b in range(3)] for a in range(3)],[0.5,-0.5,0.5])
    return math.degrees(math.acos(max(-1,min(1,abs(e2[0])))))

def rot_around_axis(tris, p0, axis, deg):
    th=math.radians(deg); c,s=math.cos(th),math.sin(th)
    kx,ky,kz=axis
    out=[]
    for tri in tris:
        nt=[]
        for (x,y,z) in tri:
            vx,vy,vz=x-p0[0],y-p0[1],z-p0[2]
            dot=vx*kx+vy*ky+vz*kz
            cx=ky*vz-kz*vy; cy=kz*vx-kx*vz; cz=kx*vy-ky*vx
            nt.append((p0[0]+vx*c+cx*s+kx*dot*(1-c),
                       p0[1]+vy*c+cy*s+ky*dot*(1-c),
                       p0[2]+vz*c+cz*s+kz*dot*(1-c)))
        out.append(nt)
    return out

def main():
    asm = json.load(open('cad/v1/cfd/airframe_assembly.json', encoding='utf-8'))
    outdir='cad/v1/cfd_parallel'
    os.makedirs(outdir, exist_ok=True)

    # body 不变 (舵面独立)
    for f in ('body.stl',):
        tris=read_stl(f'cad/v1/cfd/{f}')
        write_stl(os.path.join(outdir,f), tris)

    newsurf=[]
    for s in asm['control_surfaces']:
        name, ax, hl = s['name'], s['hinge_axis'], s['hinge_line'][0]
        tris = read_stl(f"cad/v1/cfd/{s['mesh']}")
        best=None
        for deg in (+45.0,-45.0):
            rot=rot_around_axis(tris, hl, ax, deg)
            ang=chord_x_angle(rot)
            if best is None or ang<best[1]: best=(deg,ang,rot)
        deg,ang,rot=best
        write_stl(os.path.join(outdir, s['mesh']), rot)
        print(f"{name}: {deg:+.0f}° → 平行 (弦向x夹角 {ang:.1f}°)")
        ns=dict(s); ns['basis_rotation_deg']=deg; ns['status']='v2 平行基准零位'
        newsurf.append(ns)

    asm2=dict(asm)
    asm2['version']='v2 (平行基准: 零位=舵面平行弹轴, 曼波 2026-10-28 定)'
    asm2['basis']='parallel — δ=0 即绝对对称构型 (旧基准 δ=0 = 本基准全舵 ±45° 常量偏置)'
    asm2['control_surfaces']=newsurf
    json.dump(asm2, open(os.path.join(outdir,'airframe_assembly.json'),'w',encoding='utf-8'),
              ensure_ascii=False, indent=2)
    print(f"-> {outdir}/ (body + 4 fin 平行零位 + v2 assembly)")

if __name__ == '__main__':
    main()
