#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提取舵面内的圆柱孔轴 (gmsh 全局坐标) — 定位操纵面铰链轴

原理: 圆柱面上所有点的法向都垂直于轴线 → 法向协方差矩阵的最小特征值方向 = 轴向;
     半径 = 顶点到轴距离中位数; 轴上点 = 顶点质心在轴向/径向的分解修正。
全程 gmsh 世界坐标 (与 step_to_stl 的分件 STL/包围盒同系), 空间对齐无坐标转换。

用法:
  python3 find_hinges.py <file.step> --flaps 24,26,28,30 --parts-json parts.json \
      --stl-dir parts --out hinges.json --render hinges.png
"""
import argparse
import json
import math
import re
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("--flaps", default="24,26,28,30")
    ap.add_argument("--rmin", type=float, default=0.5)
    ap.add_argument("--rmax", type=float, default=6.0)
    ap.add_argument("--stl-dir", default=None)
    ap.add_argument("--parts-json", default=None)
    ap.add_argument("--out", default="hinges.json")
    ap.add_argument("--render", default=None)
    args = ap.parse_args()

    flaps = [int(x) for x in args.flaps.split(",")]
    boxes = {}
    if args.parts_json:
        for row in json.load(open(args.parts_json, encoding="utf-8")):
            if row["tag"] in flaps:
                boxes[row["tag"]] = (row["lo"], row["hi"])
    if not boxes:
        print("错误: 需要 --parts-json 做空间对齐", file=sys.stderr)
        sys.exit(1)

    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("m")
    gmsh.merge(args.step)
    gmsh.model.occ.synchronize()
    gmsh.option.setNumber("Mesh.MeshSizeMax", 0.8)
    gmsh.model.mesh.generate(2)

    surf2vol = {}
    for dim, tag in gmsh.model.getEntities(3):
        for sdim, stag in gmsh.model.getBoundary([(3, tag)], oriented=False, recursive=False):
            surf2vol.setdefault(stag, []).append(tag)
    ntags, nxyz, _ = gmsh.model.mesh.getNodes()
    node = {int(t): (nxyz[3 * i], nxyz[3 * i + 1], nxyz[3 * i + 2]) for i, t in enumerate(ntags)}

    def smallest_dir(C):
        """对称 3x3 最小特征值方向 (幂迭代于 M 的平移逆)"""
        tr = sum(C[i][i] for i in range(3))
        M = [[(tr - C[i][j]) for j in range(3)] for i in range(3)]  # 最大特征方向 of (trI - C)
        v = [0.3, 0.4, 0.9]
        for _ in range(300):
            v = [sum(M[a][b] * v[b] for b in range(3)) for a in range(3)]
            ln = math.sqrt(sum(x * x for x in v)) or 1
            v = [x / ln for x in v]
        return v

    rows = []
    for dim, stag in gmsh.model.getEntities(2):
        if gmsh.model.getType(2, stag) != "Cylinder":
            continue
        etypes, etags, enodes = gmsh.model.mesh.getElements(2, stag)
        idx = set()
        for et, tags, nds in zip(etypes, etags, enodes):
            if et == 2:
                idx.update(int(x) for x in nds)
        if len(idx) < 40:
            continue
        P = [node[t] for t in idx]
        n = len(P)
        c = [sum(p[j] for p in P) / n for j in range(3)]
        # 参数化: u=圆周, v=轴向 → v 两端的坐标差方向就是轴 (精确)
        try:
            bnds = gmsh.model.getParametrizationBounds(2, stag)
            u_mid = (bnds[0][0] + bnds[1][0]) / 2
            v1, v2 = bnds[0][1], bnds[1][1]
            pA = gmsh.model.getValue(2, stag, [u_mid, v1])
            pB = gmsh.model.getValue(2, stag, [u_mid, v2])
        except Exception:
            continue
        ax = [pB[k] - pA[k] for k in range(3)]
        plen = math.sqrt(sum(x * x for x in ax))
        if plen < 1e-9:
            continue
        ax = [x / plen for x in ax]
        if plen < 2.0:            # 轴向长度 <2mm 的圆角/倒角不要
            continue
        # 半径: 顶点到轴 (过 pA、方向 ax) 的距离中位数
        tmp = [1.0, 0.0, 0.0] if abs(ax[0]) < 0.9 else [0.0, 1.0, 0.0]
        e1 = [tmp[1] * ax[2] - tmp[2] * ax[1], tmp[2] * ax[0] - tmp[0] * ax[2], tmp[0] * ax[1] - tmp[1] * ax[0]]
        ln = math.sqrt(sum(x * x for x in e1)); e1 = [x / ln for x in e1]
        e2 = [ax[1] * e1[2] - ax[2] * e1[1], ax[2] * e1[0] - ax[0] * e1[2], ax[0] * e1[1] - ax[1] * e1[0]]
        rs = []
        for p in P:
            d = [p[j] - pA[j] for j in range(3)]
            t = sum(d[j] * ax[j] for j in range(3))
            us = sum(d[j] * e1[j] for j in range(3)); vs = sum(d[j] * e2[j] for j in range(3))
            rs.append(math.hypot(us, vs))
        rs.sort()
        r_med = rs[len(rs) // 2]
        if not (args.rmin <= r_med <= args.rmax):
            continue
        for tag, (lo, hi) in boxes.items():
            if all(lo[k] - 1.0 <= c[k] <= hi[k] + 1.0 for k in range(3)):
                rows.append(dict(part_tag=tag, surf=stag, radius_mm=round(r_med, 3),
                                 length_mm=round(plen, 2),
                                 point_mm=[round(v * 1, 3) for v in pA],
                                 axis=[round(v, 5) for v in ax], n_pts=n))
                break

    rows.sort(key=lambda r: -r["length_mm"])
    hinges = rows[:48]

    print(f"舵面 {flaps} 内半径 {args.rmin}-{args.rmax} mm 的圆柱 (按轴向长度降序):")
    for e in hinges:
        print(f"  part{e['part_tag']}  r={e['radius_mm']:.2f}mm  len={e['length_mm']:.1f}mm  "
              f"点({e['point_mm'][0]:.1f},{e['point_mm'][1]:.1f},{e['point_mm'][2]:.1f})  "
              f"轴({e['axis'][0]:+.3f},{e['axis'][1]:+.3f},{e['axis'][2]:+.3f})")
    for h in hinges:   # 渲染/下游统一用 center_mm = 轴段中点
        h["center_mm"] = [round(h["point_mm"][k] + h["axis"][k] * h["length_mm"] / 2, 3) for k in range(3)]
        h["len_mm"] = h["length_mm"]
    json.dump(hinges, open(args.out, "w", encoding="utf-8"), indent=1)
    print(f"json -> {args.out} ({len(hinges)} 条候选铰链轴)")

    if args.render and args.stl_dir:
        import struct, glob, os
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.collections import PolyCollection

        def read_stl(p):
            d = open(p, "rb").read()
            n = struct.unpack("<I", d[80:84])[0]
            return [[struct.unpack("<12fH", d[84 + i * 50:84 + i * 50 + 50])[3:12][0:3],
                     struct.unpack("<12fH", d[84 + i * 50:84 + i * 50 + 50])[3:12][3:6],
                     struct.unpack("<12fH", d[84 + i * 50:84 + i * 50 + 50])[3:12][6:9]] for i in range(n)]

        parts = {}
        for f in glob.glob(os.path.join(args.stl_dir, "part_*.stl")):
            t = int(re.search(r"part_(\d+)", f).group(1))
            parts[t] = read_stl(f)
        hinges_by_part = {}
        for h in hinges:
            hinges_by_part.setdefault(h["part_tag"], []).append(h)
        colors = {24: "#e03c3c", 26: "#2a6fd6", 28: "#1f9e5a", 30: "#c9a227"}
        fig, axs = plt.subplots(1, 3, figsize=(19, 7))
        views = [(0, 2, "X-Z side"), (1, 2, "Y-Z front"), (0, 1, "X-Y top")]
        for ax_, (i, j, title) in zip(axs, views):
            for t, T in sorted(parts.items()):
                col = colors.get(t, "#b9c2cc")
                ax_.add_collection(PolyCollection(
                    [[(v[0][i], v[0][j]), (v[1][i], v[1][j]), (v[2][i], v[2][j])] for v in T],
                    facecolors=col, edgecolors="none", alpha=0.9 if t in flaps else 0.45))
            for t, hs in hinges_by_part.items():
                for h in hs:
                    p0 = h["center_mm"]; a = h["axis"]; ln = h["len_mm"]
                    p1 = [p0[k] - a[k] * ln * 0.15 for k in range(3)]
                    p2 = [p0[k] + a[k] * ln * 1.15 for k in range(3)]
                    ax_.plot([p1[i], p2[i]], [p1[j], p2[j]], lw=2.6, color="black")
                    ax_.plot([(p1[i] + p2[i]) / 2], [(p1[j] + p2[j]) / 2], "o", ms=5,
                             mfc="none", mec="red", mew=1.6)
            ax_.autoscale(); ax_.set_aspect("equal"); ax_.grid(alpha=.3)
            ax_.set_title(title); ax_.set_xlabel("xyz"[i]); ax_.set_ylabel("xyz"[j])
        handles = [plt.Line2D([], [], color=c, lw=4, label=f"part{t} + hinge") for t, c in colors.items()]
        axs[2].legend(handles=handles, fontsize=8, loc="upper right")
        plt.tight_layout(); plt.savefig(args.render, dpi=115)
        print(f"render -> {args.render}")
    gmsh.finalize()


if __name__ == "__main__":
    main()
