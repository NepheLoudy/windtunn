#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""弹体扫气 case 后处理: 读 OpenFOAM forces → 风轴系数 → 追加 aero_table.csv

用法:
  python3 post_process.py <case_dir> [--tail 0.3] [--out .../aero_table.csv] [--json r.json]

坐标系: B 系 (x 前弹轴, y 右, z 下), 弹体固定、来流按 make_case.sh 约定。
来流方向 = -V̂_B; 升力方向 = 弹体系"上" (-z) 在垂直于来流平面内的分量。
力矩参考点 = CofR = 全系统质心 (case CASEINFO)。
依赖: 仅 Python 标准库。
"""
import argparse
import json
import math
import os
import re
import sys

TRIPLE = re.compile(r"\(([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\)")


def parse_forces(path):
    """返回 [(t, F[3], M[3])] — pressure+viscous(+porous) 各分量求和。"""
    out = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            tri = TRIPLE.findall(s)
            if len(tri) not in (4, 6):
                continue
            v = [[float(x) for x in t] for t in tri]
            h = len(tri) // 2                       # 每组分量数: 4=pressure+viscous, 6=+porous
            F = [sum(v[i][j] for i in range(h)) for j in range(3)]
            M = [sum(v[i][j] for i in range(h, 2 * h)) for j in range(3)]
            out.append((float(s.split()[0]), F, M))
    return out


def collect(case):
    pats = [os.path.join(case, "postProcessing", "forces", "0", "forces.dat")]
    pats += [os.path.join(case, f"processor{i}", "postProcessing", "forces", "0", "forces.dat")
             for i in range(64)]
    files = [p for p in pats if os.path.exists(p)]
    if not files:
        raise FileNotFoundError("未找到 forces.dat (检查 controlDict functions.forces)")
    data = {}
    for fp in files:
        for t, F, M in parse_forces(fp):
            if t not in data:
                data[t] = ([0.0] * 3, [0.0] * 3)
            for j in range(3):
                data[t][0][j] += F[j]
                data[t][1][j] += M[j]
    ts = sorted(data)
    return ts, [data[t][0] for t in ts], [data[t][1] for t in ts]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def wind_axes(alpha_deg, beta_deg):
    a, b = math.radians(alpha_deg), math.radians(beta_deg)
    vhat = [math.cos(a) * math.cos(b), math.sin(b), math.sin(a) * math.cos(b)]
    drag = [-x for x in vhat]
    up0 = [0.0, 0.0, -1.0]
    c = dot(up0, drag)
    lift = [up0[i] - c * drag[i] for i in range(3)]
    nl = math.sqrt(dot(lift, lift))
    lift = [x / nl for x in lift]
    side = [lift[1] * drag[2] - lift[2] * drag[1],
            lift[2] * drag[0] - lift[0] * drag[2],
            lift[0] * drag[1] - lift[1] * drag[0]]
    ns = math.sqrt(dot(side, side))
    side = [x / ns for x in side]
    return drag, lift, side


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--tail", type=float, default=0.3, help="末段比例做时均")
    ap.add_argument("--out", default=None, help="aero_table.csv (append)")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    case = os.path.abspath(args.case)
    info = {}
    with open(os.path.join(case, "CASEINFO"), encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                info[k] = v
    V = float(info["V"]); alpha = float(info["alpha"]); beta = float(info["beta"])
    S, L, rho = 0.017671458676442587, 0.15, 1.225
    qS = 0.5 * rho * V * V * S

    ts, F, M = collect(case)
    n0 = int(len(ts) * (1.0 - args.tail))
    n = len(ts) - n0
    Fm = [sum(F[i][j] for i in range(n0, len(ts))) / n for j in range(3)]
    Mm = [sum(M[i][j] for i in range(n0, len(ts))) / n for j in range(3)]
    fmax = max(abs(x) for x in Fm) or 1e-9
    Fres = max(math.sqrt(sum((F[i][j] - Fm[j]) ** 2 for j in range(3)))
               for i in range(n0, len(ts))) / fmax

    drag, lift, side = wind_axes(alpha, beta)
    CD = dot(Fm, drag) / qS
    CL = dot(Fm, lift) / qS
    CY = dot(Fm, side) / qS
    Cm = Mm[1] / (qS * L)
    Cl = Mm[0] / (qS * L)
    Cn = Mm[2] / (qS * L)

    print(f"case   : {case}")
    print(f"V={V} alpha={alpha} beta={beta}  samples={len(ts)} (avg last {n})")
    print(f"F_B    : [{Fm[0]:+.4f} {Fm[1]:+.4f} {Fm[2]:+.4f}] N")
    print(f"M_B    : [{Mm[0]:+.5f} {Mm[1]:+.5f} {Mm[2]:+.5f}] N·m")
    print(f"CL={CL:+.5f}  CD={CD:+.5f}  Cm={Cm:+.5f}  CY={CY:+.5f}  Cl={Cl:+.5f}  Cn={Cn:+.5f}")
    print(f"末段力振荡 (max|F-Fmean|/max|Fmean|) = {Fres:.3f}"
          f"  {'<-- 疑似未收敛' if Fres > 0.05 else '(收敛可接受)'}")
    if alpha > 0.5 and CL <= 0:
        print("WARN: alpha>0 但 CL<=0 — 来流/攻角符号约定需复核", file=sys.stderr)
    if CD <= 0:
        print("WARN: CD<=0 — 阻力方向或力符号异常", file=sys.stderr)

    row = dict(V=V, alpha=alpha, beta=beta, de=0.0, da=0.0, dr=0.0,
               CL=CL, CD=CD, Cm=Cm, CY=CY, Cl=Cl, Cn=Cn)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"coeffs": row, "F_B": Fm, "M_B": Mm,
                       "residual_rel": Fres, "n_samples": n}, f, indent=2)
        print(f"json -> {args.json}")
    if args.out:
        new = not os.path.exists(args.out)
        with open(args.out, "a", encoding="utf-8") as f:
            if new:
                f.write("# S_REF=0.017671458676442587 L_REF=0.15 RHO=1.225\n")
                f.write("V,alpha,beta,de,da,dr,CL,CD,Cm,CY,Cl,Cn\n")
            f.write("%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n"
                    % (V, alpha, beta, 0.0, 0.0, 0.0, CL, CD, Cm, CY, Cl, Cn))
        print(f"appended -> {args.out}")


if __name__ == "__main__":
    main()
