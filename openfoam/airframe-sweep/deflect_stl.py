#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按舵偏角旋转操纵面 STL → 生成某个 (de, da, dr) 工况的 triSurface 几何组

用法:
  python3 deflect_stl.py <assembly.json> --de 5 --da 0 --dr 0 --out <triSurface_dir>
  python3 deflect_stl.py <assembly.json> --angles '{"fin_1": 5, "fin_2": -5}' --out ...

读 airframe_assembly.json: body.mesh + control_surfaces[].{mesh, hinge_line, mix, flip, range_deg}
绕铰链线 (A→B, 右手定则) 旋转各面, 输出 body.stl + 各 fin STL (二进制) 到 triSurface 目录。

依赖: 仅标准库。
"""
import argparse
import json
import math
import os
import shutil
import struct
import sys


def read_stl(path):
    """返回 (triangles[N][3][3]) — 兼容 ASCII 与二进制 STL。"""
    with open(path, "rb") as f:
        data = f.read()
    n = (len(data) - 84) // 50
    if len(data) >= 84 and 84 + 50 * n == len(data) and not data[:5].lower() == b"solid":
        tris = []
        off = 84
        for _ in range(n):
            vals = struct.unpack("<12fH", data[off:off + 50])
            v = vals[3:12]
            tris.append([(v[0], v[1], v[2]), (v[3], v[4], v[5]), (v[6], v[7], v[8])])
            off += 50
        return tris
    tris, cur = [], []
    for line in data.decode("utf-8", "ignore").splitlines():
        s = line.strip().split()
        if s and s[0] == "vertex":
            cur.append(tuple(float(x) for x in s[1:4]))
            if len(cur) == 3:
                tris.append(cur)
                cur = []
    if not tris:
        raise ValueError(f"{path}: 无法解析为 STL")
    return tris


def write_stl(path, tris):
    with open(path, "wb") as f:
        f.write(b"binary STL (deflect_stl.py)".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for tri in tris:
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
            ux, uy, uz = bx - ax, by - ay, bz - az
            vx, vy, vz = cx - ax, cy - ay, cz - az
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            f.write(struct.pack("<12fH", nx / ln, ny / ln, nz / ln,
                                ax, ay, az, bx, by, bz, cx, cy, cz, 0))


def rotate(tris, p0, axis, deg):
    """绕经过 p0、方向 axis 的直线右手旋转 deg 度。"""
    th = math.radians(deg)
    c, s = math.cos(th), math.sin(th)
    kx, ky, kz = axis
    out = []
    for tri in tris:
        nt = []
        for (x, y, z) in tri:
            vx, vy, vz = x - p0[0], y - p0[1], z - p0[2]
            dot = vx * kx + vy * ky + vz * kz
            cx = ky * vz - kz * vy
            cy = kz * vx - kx * vz
            cz = kx * vy - ky * vx
            nt.append((p0[0] + vx * c + cx * s + kx * dot * (1 - c),
                       p0[1] + vy * c + cy * s + ky * dot * (1 - c),
                       p0[2] + vz * c + cz * s + kz * dot * (1 - c)))
        out.append(nt)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("assembly")
    ap.add_argument("--de", type=float, default=0.0)
    ap.add_argument("--da", type=float, default=0.0)
    ap.add_argument("--dr", type=float, default=0.0)
    ap.add_argument("--angles", default=None, help='直接指定各面角度, 如 {"fin_1": 5}')
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.assembly, encoding="utf-8") as f:
        asm = json.load(f)
    base = os.path.dirname(os.path.abspath(args.assembly))
    os.makedirs(args.out, exist_ok=True)

    direct = json.loads(args.angles) if args.angles else None
    cmd = {"de": args.de, "da": args.da, "dr": args.dr}

    def resolve(mesh):
        p = os.path.join(base, mesh)
        if os.path.exists(p):
            return p
        if os.path.exists(mesh):
            return os.path.abspath(mesh)
        raise FileNotFoundError(f"找不到网格 {mesh} (查过 {base}/ 与当前目录)")

    body_mesh = resolve(asm["body"]["mesh"])
    shutil.copyfile(body_mesh, os.path.join(args.out, "body.stl"))
    print(f"body  -> body.stl")

    for surf in asm["control_surfaces"]:
        name = surf["name"]
        if direct is not None:
            ang = float(direct.get(name, 0.0))
        else:
            mix = surf.get("mix", {})
            ang = sum(float(mix.get(k, 0.0)) * cmd[k] for k in ("de", "da", "dr"))
        if surf.get("flip"):
            ang = -ang
        lo, hi = surf.get("range_deg", [-90, 90])
        if not (lo - 1e-9 <= ang <= hi + 1e-9):
            print(f"WARN: {name} 角度 {ang:.2f}° 超行程 [{lo},{hi}]，已限幅", file=sys.stderr)
            ang = max(lo, min(hi, ang))

        A, B = surf["hinge_line"]
        d = [B[i] - A[i] for i in range(3)]
        ln = math.sqrt(sum(x * x for x in d))
        if ln < 1e-9:
            raise ValueError(f"{name}: hinge_line 两点重合")
        axis = [x / ln for x in d]

        tris = read_stl(resolve(surf["mesh"]))
        if abs(ang) > 1e-12:
            tris = rotate(tris, A, axis, ang)
        fname = f"fin_{name}.stl" if not surf["mesh"].startswith("fin_") else surf["mesh"]
        write_stl(os.path.join(args.out, fname), tris)
        print(f"{name:10s} -> {fname}  angle={ang:+.2f}°  tris={len(tris)}")

    print(f"done -> {args.out}")


if __name__ == "__main__":
    main()
