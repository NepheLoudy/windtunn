#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""平行基准 STL → 仪表台 3D 网格 JSON (B 系米制, 质心原点, 浏览器 three.js 直接加载)

fins 附带 hinge_axis / hinge_point (来自 cfd_parallel/airframe_assembly.json),
前端用它们做 δ 滑块绕铰链旋转。body 每 5 取 1 三角降采样控体积。
输出: wt_jobs/www/dart_parallel_mesh.json
"""
import json, os, struct

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
CAD  = os.path.join(ROOT, 'openfoam', 'airframe-sweep', 'cad', 'v1', 'cfd_parallel')
OUT  = os.path.join(ROOT, 'wt_jobs', 'www', 'dart_parallel_mesh.json')

def load_tris(path, step=1):
    d = open(path, 'rb').read()
    n = struct.unpack('<I', d[80:84])[0]
    tris = []
    for i in range(0, n, step):
        v = struct.unpack('<12f', d[84+i*50:84+i*50+48])
        tris.append([v[3:6], v[6:9], v[9:12]])
    return tris

def flat(tris, nd=4):
    return [round(x, nd) for t in tris for v in t for x in v]

asm = json.load(open(os.path.join(CAD, 'airframe_assembly.json'), encoding='utf-8'))
hinge = {s['name']: (s['hinge_axis'], s['hinge_line'][0]) for s in asm['control_surfaces']}

mesh = {'body': {'pos': flat(load_tris(os.path.join(CAD, 'body.stl'), 5))}, 'fins': []}
for k in (1, 2, 3, 4):
    name = 'fin_%d' % k
    ax, pt = hinge[name]
    mesh['fins'].append({
        'name': name,
        'pos': flat(load_tris(os.path.join(CAD, name + '.stl'))),
        'hinge_axis': [round(float(x), 5) for x in ax],
        'hinge_point': [round(float(x), 5) for x in pt],
    })

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(mesh, open(OUT, 'w'), separators=(',', ':'))
print('mesh json ->', OUT, '%.1f KB' % (os.path.getsize(OUT)/1024))
