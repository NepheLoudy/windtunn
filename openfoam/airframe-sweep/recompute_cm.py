#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cm 重算工具 — 实机称重更新 com 后, 力矩平移重投系数表 (零重跑)

为什么存在: post_process 求解时 CofR 固定 B 系原点, M_B 后处理平移到
mass_properties.com_B (当前占位 0,0,0 与原点重合)。com 实测后若直接改
mass_properties.json, 旧表的 Cm/Cl/Cn 就作废 — 本工具用每工况 results.json
存的 F_B/M_B + moment_ref (该行当时实际用的参考点) 平移重算, 不用重跑 FVM:

    M_new = M_old + (com_new − com_used) × F_B      (叉积, B 系)
    再按风轴基重出 CL/CD/CY 与 Cl/Cm/Cn (力不变, 只力矩变)

用法:
  python3 recompute_cm.py <sweep_root> <new_mass_properties.json> [--out 表.csv]
输出默认 <sweep_root>/<原表名>_com.csv (不覆盖原表, 供人工核对后替换)。
依赖: 仅标准库; 风轴基 import 自同目录 post_process (单一真源)。
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from post_process import wind_axes  # noqa: E402  (单一真源, 勿在此复刻)


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sweep_root")
    ap.add_argument("mass_properties")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = os.path.abspath(args.sweep_root)
    mp = json.load(open(args.mass_properties, encoding="utf-8"))
    com_new = [float(x) for x in mp["com_B"]]

    src_tbl = None
    for cand in ("t0_table.csv", "t1_table.csv"):
        p = os.path.join(root, cand)
        if os.path.exists(p):
            src_tbl = p
            break
    if not src_tbl:
        print("no table in", root)
        return 1
    out = args.out or src_tbl.replace(".csv", "_com.csv")

    # 原表头 (S_REF/L_REF/RHO) + 行索引
    header_meta, lines = {}, []
    for ln in open(src_tbl, encoding="utf-8"):
        if ln.startswith("#"):
            for tok in ln.lstrip("#").split():
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    header_meta[k] = v
        elif ln.strip():
            lines.append(ln.strip())
    S = float(header_meta["S_REF"])
    L = float(header_meta["L_REF"])
    rho = float(header_meta.get("RHO", 1.225))

    rows, missed = [], []
    for rj in sorted(glob.glob(os.path.join(root, "case_*", "results.json"))):
        j = json.load(open(rj, encoding="utf-8"))
        c = j["coeffs"]
        F = j["F_B"]
        M = j["M_B"]
        com_used = [float(x) for x in j.get("moment_ref", [0.0, 0.0, 0.0])]
        d = [com_new[k] - com_used[k] for k in range(3)]
        M = [M[k] + cross(d, F)[k] for k in range(3)]
        V = float(c["V"])
        qS = 0.5 * rho * V * V * S
        qSL = qS * L
        drag, lift, side = wind_axes(float(c["alpha"]), float(c["beta"]))
        rows.append((V, float(c["alpha"]), float(c["beta"]),
                     sum(f * x for f, x in zip(F, lift)) / qS,
                     sum(f * x for f, x in zip(F, drag)) / qS,
                     M[1] / qSL,
                     sum(f * x for f, x in zip(F, side)) / qS,
                     M[0] / qSL, M[2] / qSL))
        if j.get("moment_ref") is None:
            missed.append(os.path.basename(os.path.dirname(rj)))

    with open(out, "w", encoding="utf-8") as f:
        f.write("# S_REF=%s L_REF=%s RHO=%s MOMENT_REF=%s (recomputed by recompute_cm.py)\n"
                % (header_meta.get("S_REF"), header_meta.get("L_REF"), header_meta.get("RHO", "1.225"),
                   ",".join("%.6g" % x for x in com_new)))
        f.write("V,alpha,beta,de,da,dr,CL,CD,Cm,CY,Cl,Cn\n")
        for r in sorted(rows):
            f.write("%.4f,%.4f,%.4f,0.0000,0.0000,0.0000,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n" % r)
    n0 = sum(1 for ln in lines if not ln.startswith("V,"))
    print("recomputed %d cases -> %s (原表 %d 行)" % (len(rows), out, n0))
    if missed:
        print("WARN %d 行 results.json 无 moment_ref 字段, 已按 B 系原点(0,0,0)回退 — "
              "适用于 10-31 前的旧数据 (当时 com 占位=0 与原点重合, 数值正确)" % len(missed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
