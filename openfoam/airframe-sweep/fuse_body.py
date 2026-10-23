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
    args = ap.parse_args()
    flaps = set(int(x) for x in args.flaps.split(","))

    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("f")
    gmsh.merge(args.step)
    gmsh.model.occ.synchronize()
    vols = gmsh.model.getEntities(3)
    # flaps tag = 第 k 个实体 (k 从 1), 与 step_to_stl 顺序一致
    body_vols = [(3, t) for _, t in vols if t not in flaps]
    print(f"实体 {len(vols)}, body 参与并集 {len(body_vols)} 个")
    out = gmsh.model.occ.fuse([body_vols[0]], body_vols[1:])
    gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.synchronize()
    fused = [t for d, t in gmsh.model.getEntities(3)]
    print(f"fuse 后实体 {len(fused)} 个 (期望 1)")
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
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    write_stl(args.out, trisB)
    # 质量核对: fuse 后体积应≈各体之和
    vt = sum(gmsh.model.occ.getMass(3, t) for t in fused)
    print(f"三角 {len(trisB)}, fuse 体积 {vt*1e-3:.2f} cm3 (各体之和 {153.31:.1f} 附近)")
    gmsh.finalize()
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
