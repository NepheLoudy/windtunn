#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP → 分件 STL + 零件清单 (体积/质心/包围盒)

用法:
  python3 step_to_stl.py <file.step> --out <dir> [--size 2.5] [--report parts.json]

依赖: gmsh (pip install gmsh)。gmsh 自带 OCC 内核, 会应用装配变换。
输出: <out>/part_<tag>.stl (每个实体一个) + 控制台零件表。
"""
import argparse
import json
import math
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=float, default=2.5, help="网格最大边长 mm")
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("a")
    gmsh.merge(args.step)
    gmsh.model.occ.synchronize()

    vols = gmsh.model.getEntities(3)
    print(f"实体 {len(vols)} 个, 生成三角网格 (max={args.size}mm)...")
    gmsh.option.setNumber("Mesh.MeshSizeMax", args.size)
    gmsh.model.mesh.generate(2)

    os.makedirs(args.out, exist_ok=True)

    # 面 → 所属体
    surf2vol = {}
    for dim, tag in vols:
        for sdim, stag in gmsh.model.getBoundary([(3, tag)], oriented=False, recursive=False):
            surf2vol.setdefault(stag, []).append(tag)

    # 收集每个面上三角元
    node_tags, node_xyz, _ = gmsh.model.mesh.getNodes()
    node = {int(t): (node_xyz[3 * i], node_xyz[3 * i + 1], node_xyz[3 * i + 2])
            for i, t in enumerate(node_tags)}

    tri_by_vol = {tag: [] for _, tag in vols}
    for sdim, stag in gmsh.model.getEntities(2):
        etypes, etags, enodes = gmsh.model.mesh.getElements(2, stag)
        for et, tags, nds in zip(etypes, etags, enodes):
            if et != 2:          # 只要三角形
                continue
            nds = [int(x) for x in nds]
            for k in range(len(tags)):
                tri = tuple(node[nds[3 * k + j]] for j in range(3))
                for v in surf2vol.get(stag, []):
                    tri_by_vol[v].append(tri)

    def write_stl(path, tris):
        with open(path, "wb") as f:
            f.write(b"binary STL (step_to_stl.py)".ljust(80, b" "))
            f.write(bytes(bytearray(__import__("struct").pack("<I", len(tris)))))
            for (a, b, c) in tris:
                u = [b[i] - a[i] for i in range(3)]
                v = [c[i] - a[i] for i in range(3)]
                n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
                ln = math.sqrt(sum(x * x for x in n)) or 1.0
                f.write(__import__("struct").pack(
                    "<12fH", n[0] / ln, n[1] / ln, n[2] / ln,
                    a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2], 0))

    rows = []
    for dim, tag in vols:
        bb = gmsh.model.getBoundingBox(3, tag)
        vol = gmsh.model.occ.getMass(3, tag)
        cm = gmsh.model.occ.getCenterOfMass(3, tag)
        tris = tri_by_vol[tag]
        name = f"part_{tag}.stl"
        write_stl(os.path.join(args.out, name), tris)
        rows.append(dict(tag=tag, file=name, volume_cm3=vol * 1e-3,
                         dim_mm=[(bb[3] - bb[0]), (bb[4] - bb[1]), (bb[5] - bb[2])],
                         lo=[bb[0], bb[1], bb[2]], hi=[bb[3], bb[4], bb[5]],
                         com=[cm[0], cm[1], cm[2]], tris=len(tris)))

    rows.sort(key=lambda r: r["com"][2])
    print(f"\n{'tag':>4} {'体积cm3':>8} {'尺寸 mm':>22} {'质心 mm':>26} {'三角':>6}")
    for r in rows:
        d, c = r["dim_mm"], r["com"]
        print(f"{r['tag']:>4} {r['volume_cm3']:8.3f}  "
              f"{d[0]:6.1f}x{d[1]:5.1f}x{d[2]:5.1f}  ({c[0]:6.1f},{c[1]:6.1f},{c[2]:6.1f}) {r['tris']:6d}")
    print(f"\n体积合计 {sum(r['volume_cm3'] for r in rows):.2f} cm3 -> {args.out}")
    if args.report:
        json.dump(rows, open(args.report, "w", encoding="utf-8"), indent=1)
        print(f"report -> {args.report}")
    gmsh.finalize()


if __name__ == "__main__":
    main()
