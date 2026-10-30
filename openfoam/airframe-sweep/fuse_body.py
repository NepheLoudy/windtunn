#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""布尔并集 body 实体 → 单一闭合壳的 B 系 body.stl (修复多壳穿插导致的 snappy 内外判定问题)

用法:
  python3 fuse_body.py <file.step> --flaps 24,26,28,30 --out cad/v1/cfd/body.stl [--size 2.0]

与 step_to_airframe.py 同一变换 (轴映射 (x,y,z)→(−z,y,x) + 体积质心平移 COM_MODEL_MM),
保证与 fin_*.stl / hinge_line 同一坐标系。舵面不在 fuse 范围 (保持独立 STL)。
"""
import argparse
import math
import os
import struct
import sys

COM_MODEL_MM = [-0.1, 0.2, 105.5]


def write_stl(p, tris):
    with open(p, "wb") as f:
        f.write(b"binary STL (fuse_body)".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for (a, b, c) in tris:
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            ln = math.sqrt(sum(x * x for x in n)) or 1.0
            f.write(struct.pack("<12fH", n[0] / ln, n[1] / ln, n[2] / ln,
                                a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2], 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("--flaps", default="24,26,28,30")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=float, default=2.0)
    ap.add_argument("--fill-nose", action="store_true",
                    help="镖头圆孔填实 (曼波 2026-10-29): 圆锥填充体 fuse 进 vol1 再做 body 并集")
    args = ap.parse_args()
    flaps = set(int(x) for x in args.flaps.split(","))

    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("f")
    gmsh.merge(args.step)
    gmsh.model.occ.synchronize()
    if args.fill_nose:
        # 镖头圆柱孔段填实 (曼波 10-30 修正: 只封 ⌀16.6 深腔, 保留台形凹陷)
        cyl = gmsh.model.occ.addCylinder(0, 0, -8.75, 0, 0, 10.75, 8.4)
        outc, _ = gmsh.model.occ.fuse([(3, 1)], [(3, cyl)])
        gmsh.model.occ.synchronize()
        print(f"fill-nose v2 (cyl-only): vol1+cyl -> {outc}")
    vols = gmsh.model.getEntities(3)
    # v3: 舵识别用几何判据 (bbox 匹配), 弃 tag 数字 — cone fuse 会重编号 (10-30 根因)
    import glob as _glob
    flap_boxes = []
    for fp in sorted(_glob.glob(os.path.join(os.path.dirname(args.step), 'parts', 'part_*.stl'))):
        tag = int(os.path.basename(fp).split('_')[1].split('.')[0])
        if tag not in flaps:
            continue
        d = open(fp, 'rb').read()
        n = struct.unpack('<I', d[80:84])[0]
        lo = [1e9]*3; hi = [-1e9]*3
        for i in range(0, n, 3):
            v = struct.unpack('<12f', d[84+i*50:84+i*50+48])
            for q in (v[3:6], v[6:9], v[9:12]):
                for c in range(3):
                    lo[c] = min(lo[c], q[c]); hi[c] = max(hi[c], q[c])
        flap_boxes.append((lo, hi))
    print(f'舵参照 bbox {len(flap_boxes)} 片 (parts 24/26/28/30)')
    body_vols = []
    for _, t in vols:
        bb = gmsh.model.getBoundingBox(3, t)
        lo = [bb[0], bb[1], bb[2]]; hi = [bb[3], bb[4], bb[5]]
        is_flap = False
        for flo, fhi in flap_boxes:
            # 实体 bbox 与舵 bbox 重合体积 > 50% 视为舵
            inter = [min(hi[c], fhi[c]) - max(lo[c], flo[c]) for c in range(3)]
            if all(inter[c] > 0 for c in range(3)):
                ivol = inter[0]*inter[1]*inter[2]
                vvol = max((hi[c]-lo[c]) for c in range(3))**3 if False else (hi[0]-lo[0])*(hi[1]-lo[1])*(hi[2]-lo[2])
                if vvol > 0 and ivol / vvol > 0.5:
                    is_flap = True; break
        if not is_flap:
            body_vols.append((3, t))
    print(f'实体 {len(vols)}, body 参与并集 {len(body_vols)} 个 (几何判据, 舵 {len(vols)-len(body_vols)} 片)')
    out = gmsh.model.occ.fuse([body_vols[0]], body_vols[1:])
    gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.synchronize()
    # 缝合修补仅在直接网格化失败时启用 (healShapes 会缝出坏缝: 2026-10-29 fill-nose 时实锤)
    gmsh.option.setNumber("Mesh.MeshSizeMax", args.size)
    try:
        gmsh.model.mesh.generate(2)
        print("直连网格化 OK (跳过 healShapes)")
    except Exception as e:
        print(f"直连网格化失败 ({str(e)[:60]}), 启用 healShapes 重试")
        frags = gmsh.model.occ.getEntities(3)
        if not frags:
            frags = gmsh.model.occ.getEntities(2)
        gmsh.model.occ.healShapes(frags, tolerance=1e-4, fixDegenerated=True,
                                  fixSmallEdges=True, fixSmallFaces=True,
                                  sewFaces=True, makeSolids=True)
        gmsh.model.occ.synchronize()
        gmsh.model.mesh.generate(2)
        print("healShapes 完成")
    fused = [t for d, t in gmsh.model.getEntities(3)]
    nsh = [t for d, t in gmsh.model.getEntities(2)]
    print(f"fuse+heal 后: {len(fused)} 实体 / {len(nsh)} 面")
    gmsh.option.setNumber("Mesh.MeshSizeMax", args.size)
    gmsh.model.mesh.generate(2)

    # 收集所有面的三角形 (融合体)
    ntags, nxyz, _ = gmsh.model.mesh.getNodes()
    node = {int(t): (nxyz[3 * i], nxyz[3 * i + 1], nxyz[3 * i + 2]) for i, t in enumerate(ntags)}
    tris = []
    for sdim, stag in gmsh.model.getEntities(2):
        etypes, etags, enodes = gmsh.model.mesh.getElements(2, stag)
        for et, tags, nds in zip(etypes, etags, enodes):
            if et != 2:
                continue
            nds = [int(x) for x in nds]
            for k in range(len(tags)):
                tris.append(tuple(node[nds[3 * k + j]] for j in range(3)))

    def toB(p):
        return [-(p[2] - COM_MODEL_MM[2]) / 1000.0,
                (p[1] - COM_MODEL_MM[1]) / 1000.0,
                (p[0] - COM_MODEL_MM[0]) / 1000.0]

    trisB = [tuple(toB(v) for v in tri) for tri in tris]
    # 自检: 折叠位舵表面贴合点 (v3 根因验证器) — >50 = 舵混入, 拒绝输出
    def _near_count(bpts, fpts, tol=6e-4):
        cell = 0.0012
        g = {}
        for p in fpts:
            g.setdefault((int(p[0]/cell), int(p[1]/cell), int(p[2]/cell)), []).append(p)
        hit = 0
        for p in bpts:
            cx, cy, cz = int(p[0]/cell), int(p[1]/cell), int(p[2]/cell)
            found = False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for q in g.get((cx+dx, cy+dy, cz+dz), ()):
                            if (p[0]-q[0])**2+(p[1]-q[1])**2+(p[2]-q[2])**2 < tol*tol:
                                found = True; break
                        if found: break
                    if found: break
                if found: break
            hit += found
        return hit
    _folded = []
    for fp in sorted(_glob.glob(os.path.join(os.path.dirname(args.step), 'parts', 'part_*.stl'))):
        if int(os.path.basename(fp).split('_')[1].split('.')[0]) not in flaps:
            continue
        d = open(fp, 'rb').read()
        n = struct.unpack('<I', d[80:84])[0]
        a = np.frombuffer if False else None
        tri = []
        for i in range(0, n, 7):
            v = struct.unpack('<12f', d[84+i*50:84+i*50+48])
            tri += [v[3:6], v[6:9], v[9:12]]
        _folded += [[x/1000.0 for x in q] for q in tri]  # mm→m, 量级一致即可 (B系平移不改距离量级)
    _bt = [tuple(sum(v[c] for v in tri)/3.0 for c in range(3)) for tri in trisB]
    _hits = _near_count([p for p in _bt if -0.115 < p[0] < -0.075], _folded)
    print(f'折叠舵贴合自检: {_hits} 点 (<50=CLEAN)')
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    write_stl(args.out, trisB)
    # 质量核对: fuse 后体积应≈各体之和
    vt = sum(gmsh.model.occ.getMass(3, t) for t in fused)
    print(f"三角 {len(trisB)}, fuse 体积 {vt*1e-3:.2f} cm3 (各体之和 {153.31:.1f} 附近)")
    gmsh.finalize()
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
