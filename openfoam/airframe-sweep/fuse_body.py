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
        # 镖头空腔填充: 底 r13.55@z-25 (与端面共面, 过盈) → 顶 r8.7@z+2 (超腔底)
        cone = gmsh.model.occ.addCone(0, 0, -25.0, 0, 0, 27.0, 13.55, 8.7)
        outc, _ = gmsh.model.occ.fuse([(3, 1)], [(3, cone)])
        gmsh.model.occ.synchronize()
        print(f"fill-nose: vol1+cone -> {outc}")
    vols = gmsh.model.getEntities(3)
    # flaps tag = 第 k 个实体 (k 从 1), 与 step_to_stl 顺序一致
    body_vols = [(3, t) for _, t in vols if t not in flaps]
    print(f"实体 {len(vols)}, body 参与并集 {len(body_vols)} 个")
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
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    write_stl(args.out, trisB)
    # 质量核对: fuse 后体积应≈各体之和
    vt = sum(gmsh.model.occ.getMass(3, t) for t in fused)
    print(f"三角 {len(trisB)}, fuse 体积 {vt*1e-3:.2f} cm3 (各体之和 {153.31:.1f} 附近)")
    gmsh.finalize()
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
