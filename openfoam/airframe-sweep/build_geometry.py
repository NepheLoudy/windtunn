#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组装 snappy 友好的几何目录: 每个原生水密 STEP 实体 = 一个独立 STL patch (统一 B 系米制)

要点: snappy 对「多个独立水密封闭体」处理最成熟 (重叠/穿插 OK, 重叠区在实体内部);
不要把多件拼成单个 STL — 那会制造非流形面, 交叉板窄缝被 wrap 封死丢面 → 假侧力。

坐标: parts/*.stl 是模型系 mm (step_to_stl 产物), 本脚本统一转到 B 系 m
(轴映射 (x,y,z)→(−z,y,x), 原点平移到体积质心 COM_MODEL_MM) — 与 fin_*.stl 同系。

用法:
  python3 build_geometry.py --parts-dir cad/v1/parts --flaps 24,26,28,30 --out cfd_geom_multi
"""
import argparse
import json
import math
import os
import struct

COM_MODEL_MM = [-0.1, 0.2, 105.5]


def read_stl(p):
    d = open(p, "rb").read()
    n = struct.unpack("<I", d[80:84])[0]
    tris = []
    for i in range(n):
        v = struct.unpack("<12fH", d[84 + i * 50:84 + i * 50 + 50])
        tris.append((v[3:6], v[6:9], v[9:12]))
    return tris


def write_stl(p, tris):
    with open(p, "wb") as f:
        f.write(b"binary STL (build_geometry)".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for (a, b, c) in tris:
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            nn = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            ln = math.sqrt(sum(x * x for x in nn)) or 1.0
            f.write(struct.pack("<12fH", nn[0] / ln, nn[1] / ln, nn[2] / ln,
                                a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2], 0))


def toB_mm(p):
    return [-(p[2] - COM_MODEL_MM[2]) / 1000.0,
            (p[1] - COM_MODEL_MM[1]) / 1000.0,
            (p[0] - COM_MODEL_MM[0]) / 1000.0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts-dir", default="cad/v1/parts")
    ap.add_argument("--parts-json", default="cad/v1/parts.json")
    ap.add_argument("--flaps", default="24,26,28,30")
    ap.add_argument("--fin-src", default="cad/v1/cfd", help="已转 B 系的 fin_*.stl 目录")
    ap.add_argument("--out", default="cfd_geom_multi")
    args = ap.parse_args()
    flaps = set(int(x) for x in args.flaps.split(","))

    rows = json.load(open(args.parts_json, encoding="utf-8"))
    os.makedirs(args.out, exist_ok=True)
    k = 0
    for r in sorted(rows, key=lambda r: r["tag"]):
        if r["tag"] in flaps:
            continue
        k += 1
        tris = read_stl(os.path.join(args.parts_dir, f"part_{r['tag']}.stl"))
        write_stl(os.path.join(args.out, f"body_{k:02d}.stl"),
                  [tuple(toB_mm(v) for v in tri) for tri in tris])
    for i in range(1, 5):
        import shutil
        shutil.copyfile(os.path.join(args.fin_src, f"fin_{i}.stl"),
                        os.path.join(args.out, f"fin_{i}.stl"))
    with open(os.path.join(args.out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"body_01..body_{k:02d}: 原生水密 STEP 实体, B 系米制 (原点=体积质心)\n")
        f.write("fin_1..4: 操纵面 (独立, deflect_stl.py 旋转后替换)\n")
        f.write("make_case.sh: body_* 用 SURF_LEVEL, fin_* 用 FIN_LEVEL (薄舵需 7)\n")
    print(f"body {k} 件 (B 系 m) + 4 舵 -> {args.out}")


if __name__ == "__main__":
    main()
