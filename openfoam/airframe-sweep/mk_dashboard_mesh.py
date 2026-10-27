#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP → 仪表台 3D 网格 JSON (粗网格, B 系米制, 浏览器 Three.js 直接加载)

用法: python3 mk_dashboard_mesh.py <airframe.step> --flaps 24,26,28,30 --out dashboard_mesh.json
输出: {"body":{"pos":[...]}, "fins":[{"name":"fin_1","pos":[...]}...]}
      pos = 扁平三角顶点数组 (B 系米制, 质心为原点, 保留 4 位小数)
"""
import argparse
import json
import math
import os
import struct

COM_MODEL_MM = [-0.1, 0.2, 105.5]


def write_stl(path, tris):
    with open(path, "wb") as f:
        f.write(b"binary STL".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for (a, b, c) in tris:
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            ln = math.sqrt(sum(x * x for x in n)) or 1.0
            f.write(struct.pack("<12fH", n[0] / ln, n[1] / ln, n[2] / ln,
                                a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2], 0))


def read_stl(path):
    d = open(path, "rb").read()
    n = struct.unpack("<I", d[80:84])[0]
    tris = []
    for i in range(n):
        v = struct.unpack("<12fH", d[84 + i * 50:84 + i * 50 + 50])[3:12]
        tris.append((v[0:3], v[3:6], v[6:9]))
    return tris


def toB(p):
    return [round(-(p[2] - COM_MODEL_MM[2]) / 1000.0, 4),
            round((p[1] - COM_MODEL_MM[1]) / 1000.0, 4),
            round((p[0] - COM_MODEL_MM[0]) / 1000.0, 4)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("--flaps", default="24,26,28,30")
    ap.add_argument("--out", default="dashboard_mesh.json")
    ap.add_argument("--size", type=float, default=8.0)
    args = ap.parse_args()
    flaps = set(int(x) for x in args.flaps.split(","))

    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("m")
    gmsh.merge(args.step)
    gmsh.model.occ.synchronize()
    vols = gmsh.model.getEntities(3)
    gmsh.option.setNumber("Mesh.MeshSizeMax", args.size)
    gmsh.model.mesh.generate(2)

    surf2vol = {}
    for dim, tag in vols:
        for sdim, stag in gmsh.model.getBoundary([(3, tag)], oriented=False, recursive=False):
            surf2vol.setdefault(stag, []).append(tag)
    ntags, nxyz, _ = gmsh.model.mesh.getNodes()
    node = {int(t): (nxyz[3 * i], nxyz[3 * i + 1], nxyz[3 * i + 2]) for i, t in enumerate(ntags)}
    tri_by_vol = {t: [] for _, t in vols}
    for sdim, stag in gmsh.model.getEntities(2):
        etypes, etags, enodes = gmsh.model.mesh.getElements(2, stag)
        for et, tags, nds in zip(etypes, etags, enodes):
            if et != 2:
                continue
            nds = [int(x) for x in nds]
            for k in range(len(tags)):
                tri = tuple(node[nds[3 * k + j]] for j in range(3))
                for v in surf2vol.get(stag, []):
                    tri_by_vol[v].append(tri)
    Vtot = sum(gmsh.model.occ.getMass(3, t) for _, t in vols)
    com = [sum(gmsh.model.occ.getCenterOfMass(3, t)[i] * gmsh.model.occ.getMass(3, t)
               for _, t in vols) / Vtot for i in range(3)]
    gmsh.finalize()
    com0 = com

    # 简化: 每个三角只保留 3 顶点且抽稀 (每 2 个三角保留 1) — 体量减半, 视觉无损
    out = {"body": {"pos": []}, "fins": []}
    fin_names = {24: "fin_1", 26: "fin_2", 28: "fin_3", 30: "fin_4"}
    for t in sorted(tri_by_vol):
        tris = tri_by_vol[t]
        tgt = out["fins"] if False else None
        name = fin_names.get(t)
        pos = []
        step = 2 if len(tris) > 4000 else 1
        for tri in tris[::step]:
            for v in tri:
                pos.extend(toB(v))
        if name:
            out["fins"].append({"name": name, "pos": pos})
        else:
            out["body"]["pos"].extend(pos)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(out, open(args.out, "w", encoding="utf-8"))
    nb = len(out["body"]["pos"]) // 9
    print(f"body {nb} tris, fins {sum(len(f['pos'])//9 for f in out['fins'])} tris -> {args.out} "
          f"({os.path.getsize(args.out)//1024} KB)")


if __name__ == "__main__":
    main()
