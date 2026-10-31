#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""装配 JSON v4 补丁 — hinge_line/hinge_axis 换真铰链轴 (双耳孔心连线), 并重建 dart_parallel.stl"""
import json
import math
import struct

CAD = 'cad/v1/cfd_parallel'
th = json.load(open('hinges_true.json'))

asm = json.load(open(CAD + '/airframe_assembly.json', encoding='utf-8'))
for s in asm['control_surfaces']:
    t = th[s['name']]
    c1 = [x / 1000.0 for x in t['holes'][0]['cB_mm']]
    c2 = [x / 1000.0 for x in t['holes'][1]['cB_mm']]
    s['hinge_line'] = [c1, c2]                      # 两耳孔心 (B m) — 真铰链轴线段
    s['hinge_axis'] = t['axis_B']
    s['hinge_len_mm'] = t['span_mm']
    s['hinge_radius_mm'] = t['holes'][0]['r_mm']
    s['status'] = ('v4 真铰链轴: 双耳孔心连线 (销帽孔 r=%.2f + 销杆孔 r=%.2f), '
                   'body 侧 r=1.05 销/r=1.915 帽座/r=2.5 挡圈 线距 0.0000 — '
                   'v3 曾误用半管壳(导引套)轴, 平行偏移~1.45mm (10-31 曼波目视指正)'
                   % (t['holes'][0]['r_mm'], t['holes'][1]['r_mm']))
asm['version'] = 'v4-true-hinge-axis'
json.dump(asm, open(CAD + '/airframe_assembly.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('assembly v4 patched:', [(s['name'], s['hinge_len_mm']) for s in asm['control_surfaces']])


def load_tris(path):
    d = open(path, 'rb').read()
    n = struct.unpack('<I', d[80:84])[0]
    tris = []
    for i in range(n):
        v = struct.unpack('<12fH', d[84 + i * 50:84 + i * 50 + 50])
        tris.append((v[3:6], v[6:9], v[9:12]))
    return tris


tris = load_tris(CAD + '/body.stl')
for k in (1, 2, 3, 4):
    tris += load_tris(CAD + '/fin_%d.stl' % k)
with open(CAD + '/dart_parallel.stl', 'wb') as f:
    f.write(b'binary STL (dart parallel v4 true-hinge-axis)'.ljust(80, b' '))
    f.write(struct.pack('<I', len(tris)))
    for a, b, c in tris:
        u = [b[j] - a[j] for j in range(3)]; v = [c[j] - a[j] for j in range(3)]
        nn = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        ln = math.sqrt(sum(x * x for x in nn)) or 1.0
        f.write(struct.pack('<12fH', nn[0] / ln, nn[1] / ln, nn[2] / ln, *a, *b, *c, 0))
print('dart_parallel.stl rebuilt: %d tris' % len(tris))
