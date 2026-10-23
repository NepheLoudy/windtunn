#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP → 可扫气的镖体几何 (B 系, body + 操纵面) + 交接 JSON

用法:
  python3 step_to_airframe.py <file.step> --flaps 24,26,28,30 --out <dir> \
      [--axis-mode z] [--size 2.0]

做的事:
  1. gmsh 导入 STEP (应用装配变换) → 每个实体导 STL
  2. 轴向映射到 B 系 (x 前弹轴, y 右, z 下):  模型 z→x, 沿用 y, x→z  (--axis-mode)
  3. 体积加权质心 → 平移使原点落在质心 (CofR=0, 干净)
  4. 每个操纵面拟合铰链线 (前缘带 PCA) → 候选铰链线 + 单位轴
  5. 输出 body.stl / fin_*.stl / airframe_assembly.json

依赖: gmsh。铰链线是几何推断, **必须人工确认** (JSON 里 status=candidate)。
"""
import argparse
import glob
import json
import math
import os
import re
import struct
import sys


def read_bin_stl(p):
    d = open(p, "rb").read()
    n = struct.unpack("<I", d[80:84])[0]
    v = [struct.unpack("<12fH", d[84 + i * 50:84 + i * 50 + 50])[3:12] for i in range(n)]
    return [((a[0], a[1], a[2]), (a[3], a[4], a[5]), (a[6], a[7], a[8])) for a in v]


def write_stl(p, tris):
    with open(p, "wb") as f:
        f.write(b"binary STL (step_to_airframe)".ljust(80, b" "))
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
    ap.add_argument("--flaps", required=True, help="操纵面实体 tag, 逗号分隔 (如 24,26,28,30)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=float, default=2.0, help="三角化最大边长 mm")
    ap.add_argument("--edge-frac", type=float, default=0.15, help="前缘带占比 (铰链线拟合)")
    args = ap.parse_args()

    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("m")
    gmsh.merge(args.step)
    gmsh.model.occ.synchronize()
    vols = gmsh.model.getEntities(3)
    gmsh.option.setNumber("Mesh.MeshSizeMax", args.size)
    gmsh.model.mesh.generate(2)

    tmp = os.path.join(args.out, "_parts")
    os.makedirs(tmp, exist_ok=True)

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

    info = {}
    for dim, tag in vols:
        bb = gmsh.model.getBoundingBox(3, tag)
        info[tag] = dict(vol=gmsh.model.occ.getMass(3, tag),
                         com=list(gmsh.model.occ.getCenterOfMass(3, tag)),
                         lo=[bb[0], bb[1], bb[2]], hi=[bb[3], bb[4], bb[5]])
    gmsh.finalize()

    # 体积加权质心 (质量分布未知, 以体积为权 — 需人工用真实质量修正)
    Vtot = sum(v["vol"] for v in info.values())
    com0 = [sum(info[t]["com"][i] * info[t]["vol"] for t in info) / Vtot for i in range(3)]

    def toB(p):
        return [-(p[2] - com0[2]) / 1000.0, (p[1] - com0[1]) / 1000.0, (p[0] - com0[0]) / 1000.0]

    def tri_toB(tri):
        return tuple(tuple(toB(v) for v in tri))

    flaps = [int(x) for x in args.flaps.split(",") if x.strip()]
    out = args.out
    os.makedirs(out, exist_ok=True)

    body = []
    for t in tri_by_vol:
        if t not in flaps:
            body.extend(tri_toB(x) for x in tri_by_vol[t])
    write_stl(os.path.join(out, "body.stl"), body)

    surfaces = []
    for i, t in enumerate(flaps, 1):
        name = f"fin_{i}"
        tris = [tri_toB(x) for x in tri_by_vol[t]]
        write_stl(os.path.join(out, name + ".stl"), tris)

        P = [v for tri in tri_by_vol[t] for v in tri]
        n = len(P)
        c = [sum(p[j] for p in P) / n for j in range(3)]

        def cov(pts, ctr):
            return [[sum((p[a] - ctr[a]) * (p[b] - ctr[b]) for p in pts) / len(pts)
                     for b in range(3)] for a in range(3)]

        def matvec(M, v):
            return [sum(M[a][b] * v[b] for b in range(3)) for a in range(3)]

        def power(M, seed):
            v = list(seed)
            for _ in range(300):
                v = matvec(M, v)
                ln = math.sqrt(sum(x * x for x in v)) or 1
                v = [x / ln for x in v]
            lam = sum(v[i] * matvec(M, v)[i] for i in range(3))
            return v, lam

        C = cov(P, c)
        e1, l1 = power(C, [0.3, 0.4, 0.9])          # 展向 (最长)
        C2 = [[C[a][b] - l1 * e1[a] * e1[b] for b in range(3)] for a in range(3)]
        e2, _ = power(C2, [0.5, -0.5, 0.5])          # 弦向
        if e2[2] > 0:                                # 让 e2 指向机头 (模型系 -z)
            e2 = [-x for x in e2]
        ch = [sum((p[j] - c[j]) * e2[j] for j in range(3)) for p in P]
        # 弦向最大值 = 最靠机头的一侧 = 前缘
        thr = sorted(ch)[int((1 - args.edge_frac) * n)]
        edge = [p for p, s in zip(P, ch) if s >= thr]
        ec = [sum(p[j] for p in edge) / len(edge) for j in range(3)]
        Ce = cov(edge, ec)
        ax, _ = power(Ce, e1)                        # 前缘带主方向 = 铰链轴 (模型系)
        proj = [(sum((p[j] - ec[j]) * ax[j] for j in range(3)), p) for p in edge]
        proj.sort()
        p1, p2 = toB(proj[0][1]), toB(proj[-1][1])
        ax_b = [-ax[2], ax[1], ax[0]]                # 模型系 → B 系
        ln = math.sqrt(sum(x * x for x in ax_b)) or 1
        ax_b = [x / ln for x in ax_b]
        surfaces.append(dict(
            name=name, mesh=name + ".stl",
            hinge_line=[[round(v, 6) for v in p1], [round(v, 6) for v in p2]],
            hinge_axis=[round(v, 5) for v in ax_b],
            hinge_len_mm=round(math.dist(p1, p2) * 1000, 2),
            range_deg=[-20.0, 20.0],
            mix={"de": 0.0, "da": 0.0, "dr": 0.0},
            flip=False,
            status="candidate — 几何推断, 待人工确认",
            source_tag=t,
            bbox_B_mm=dict(
                lo=[round(v * 1000, 2) for v in toB(info[t]["lo"])],
                hi=[round(v * 1000, 2) for v in toB(info[t]["hi"])])))

    asm = dict(
        version="v1 (from STEP)",
        frame="B: x 前弹轴, y 右, z 下, 右手系; 原点 = 体积加权质心",
        origin_note="原点由 step_to_airframe.py 平移到体积加权质心; 真实质心需按实机质量分布修正",
        source_step=os.path.basename(args.step),
        volume_cm3=round(Vtot * 1e-3, 2),
        body=dict(mesh="body.stl", mass_kg=0.0, com=[0.0, 0.0, 0.0], inertia_diag=[0.0, 0.0, 0.0]),
        control_surfaces=surfaces,
        layout_note="4 片 X 布局尾缘舵面 (模型 45° 布置); mix 待按实际舵机分配填写",
        control_sign=dict(de_positive_means="待定", da_positive_means="待定", dr_positive_means="待定"))

    with open(os.path.join(out, "airframe_assembly.json"), "w", encoding="utf-8") as f:
        json.dump(asm, f, ensure_ascii=False, indent=2)

    print(f"体积合计 {Vtot*1e-3:.1f} cm3 | 体积质心(模型系) {[round(v,1) for v in com0]}")
    print(f"输出 {out}/ body.stl + {len(surfaces)} 个 fin_*.stl + airframe_assembly.json")
    for s in surfaces:
        print(f"  {s['name']}: hinge {s['hinge_line'][0]} -> {s['hinge_line'][1]}")


if __name__ == "__main__":
    main()
