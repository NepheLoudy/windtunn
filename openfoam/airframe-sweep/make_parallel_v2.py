#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用精确角度重生成平行零位 STL + 镜像检验"""
import json, math, struct, os, shutil

angles=json.load(open('cad/v1/parallel_angles.json'))
def load(p):
    d=open(p,'rb').read(); n=struct.unpack('<I',d[80:84])[0]
    pts=[]
    for i in range(n):
        v=struct.unpack('<12fH', d[84+i*50:84+i*50+50])[3:12]
        pts += [v[0:3],v[3:6],v[6:9]]
    return pts

def rot_around_axis(pts, p0, axis, deg):
    th=math.radians(deg); c,s=math.cos(th),math.sin(th)
    kx,ky,kz=axis
    out=[]
    for (x,y,z) in pts:
        vx,vy,vz=x-p0[0],y-p0[1],z-p0[2]
        dot=vx*kx+vy*ky+vz*kz
        cx=ky*vz-kz*vy; cy=kz*vx-kx*vz; cz=kx*vy-ky*vx
        out.append((p0[0]+vx*c+cx*s+kx*dot*(1-c),
                    p0[1]+vy*c+cy*s+ky*dot*(1-c),
                    p0[2]+vz*c+cz*s+kz*dot*(1-c)))
    return out

def write_pts(p, pts):
    with open(p,'wb') as f:
        f.write(b"binary STL (parallel v2 exact)".ljust(80,b" "))
        f.write(struct.pack("<I", len(pts)//3))
        for i in range(len(pts)//3):
            a,b,c=pts[3*i],pts[3*i+1],pts[3*i+2]
            u=[b[k]-a[k] for k in range(3)]; v=[c[k]-a[k] for k in range(3)]
            nn=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            ln=math.sqrt(sum(x*x for x in nn)) or 1
            f.write(struct.pack("<12fH", nn[0]/ln,nn[1]/ln,nn[2]/ln,a[0],a[1],a[2],b[0],b[1],b[2],c[0],c[1],c[2],0))

asm=json.load(open('cad/v1/cfd/airframe_assembly.json',encoding='utf-8'))
os.makedirs('cad/v1/cfd_parallel',exist_ok=True)
shutil.copy('cad/v1/cfd/body.stl','cad/v1/cfd_parallel/body.stl')
results={}
for s in asm['control_surfaces']:
    name=s['name']; ax=s['hinge_axis']; hl=s['hinge_line'][0]
    pts=load(f"cad/v1/cfd/{s['mesh']}")
    rot=rot_around_axis(pts, hl, ax, angles[name])
    write_pts(f'cad/v1/cfd_parallel/{s["mesh"]}', rot)
    results[name]=rot

def mirror_dev(A,B):
    maxd=0.0
    for i in range(0,len(A),3):
        best=1e9
        for j in range(0,len(B),3):
            d=math.sqrt((A[i][0]-B[j][0])**2+(-A[i][1]-B[j][1])**2+(A[i][2]-B[j][2])**2)
            if d<best: best=d
        if best>maxd: maxd=best
    return maxd*1000

d14=mirror_dev(results['fin_1'],results['fin_4'])
d23=mirror_dev(results['fin_2'],results['fin_3'])
print(f"精确平行零位镜像检验: fin_1↔4 = {d14:.2f}mm, fin_2↔3 = {d23:.2f}mm")

# 更新 assembly JSON 到 v2 平行基准
asm2=dict(asm)
asm2['version']='v2 (平行基准: 零位=舵面平行弹轴, 曼波 2026-10-28 定; 精确角 per-fin)'
asm2['basis']='parallel — δ=0 即绝对对称构型; 旧基准 (机械零位 45° 斜置) 的 T0/T1 δ=0 数据保留并标注'
for s in asm2['control_surfaces']:
    s['basis_rotation_deg']=angles[s['name']]
    s['status']='v2 平行基准零位 (精确角)'
json.dump(asm2, open('cad/v1/cfd_parallel/airframe_assembly.json','w',encoding='utf-8'),
          ensure_ascii=False, indent=2)
print("assembly v2 写入")
