#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""body.stl 连通域分析 — 查曼波截图里的"灰色舵面"是否混进了 body 网格
方法: 顶点焊接 (1e-4 网格) → 并查集连通域 → 每域三角数/包围盒; 与 4 片 fin 的 bbox 对比。
另外: 对每片 fin 的 bbox 区域, 统计 body 三角形落入数 (应为 ~0, 除铰链根)。
"""
import struct
import numpy as np

def load_stl(p):
    d = open(p, 'rb').read()
    n = struct.unpack('<I', d[80:84])[0]
    a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
    return a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64)

def components(tris, tol=1e-4):
    """空间哈希焊接 + 并查集"""
    key = lambda p: (round(p[0]/tol), round(p[1]/tol), round(p[2]/tol))
    parent = {}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[ra] = rb
    def node(p):
        k = key(p)
        if k not in parent:
            parent[k] = k
        return k
    for t in tris:
        ks = [node(p) for p in t]
        union(ks[0], ks[1]); union(ks[1], ks[2])
    groups = {}
    for i, t in enumerate(tris):
        r = find(node(t[0]))
        groups.setdefault(r, []).append(i)
    out = []
    for root, idxs in groups.items():
        pts = tris[idxs].reshape(-1, 3)
        out.append({'n_tri': len(idxs),
                    'lo': pts.min(0), 'hi': pts.max(0),
                    'center': pts.mean(0)})
    return sorted(out, key=lambda g: -g['n_tri'])

body = load_stl('cad/v1/cfd_parallel/body.stl')
print('body tris:', len(body))
comps = components(body)
print('连通域:', len(comps))
big = [c for c in comps if c['n_tri'] > 200]
print('大域 (>200 tri):', len(big))
for c in big:
    lo, hi = c['lo'], c['hi']
    print('  tris=%6d  x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]' %
          (c['n_tri'], lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
small = [c for c in comps if c['n_tri'] <= 200]
print('小域 (<=200 tri):', len(small), '共', sum(s['n_tri'] for s in small), 'tri')
for c in small[:10]:
    lo, hi = c['lo'], c['hi']
    print('  tris=%5d  center=[%.3f,%.3f,%.3f]  x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]' %
          (c['n_tri'], *c['center'], lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))

# fin bbox 区间 (平行基准 fin STL)
for k in (1, 2, 3, 4):
    f = load_stl('cad/v1/cfd_parallel/fin_%d.stl' % k).reshape(-1, 3)
    print('fin_%d bbox: x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]' %
          (k, f[:,0].min(), f[:,0].max(), f[:,1].min(), f[:,1].max(), f[:,2].min(), f[:,2].max()))
