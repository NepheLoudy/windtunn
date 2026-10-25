#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫气数据半途审查 — 跨V一致性/镜像对称/值域/重复/收敛抽查

用法:
  python3 audit_sweep.py <aero_table.csv> [--tol 0.15] [--report audit_report.md]
规则:
  A1 跨V一致性: 同(α,β) 不同V 的 CL/CD/Cm 离散度 (max-min)/|中位数| — |α|<15 用 tol, |α|=15 放宽 2×tol
  A2 β镜像反对称: (C(β+)-C(β0)) + (C(β-)-C(β0)) ≈ 0
  A3 CY偏置: CY(β=0) 均值与波动
  A4 值域: CL∈[-1.5,1.5], CD∈(0,1.5), |Cm|<1, |CY|<1
  A5 重复行: V,α,β,de,da,dr 完全相同
"""
import argparse
import math
import sys
from collections import defaultdict


def load(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        if line.startswith("#") or line.startswith("V,"):
            continue
        p = line.strip().split(",")
        if len(p) != 12:
            continue
        rows.append(dict(V=float(p[0]), a=float(p[1]), b=float(p[2]),
                         de=float(p[3]), da=float(p[4]), dr=float(p[5]),
                         CL=float(p[6]), CD=float(p[7]), Cm=float(p[8]),
                         CY=float(p[9]), Cl=float(p[10]), Cn=float(p[11])))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("table")
    ap.add_argument("--tol", type=float, default=0.15)
    ap.add_argument("--report", default=None)
    args = ap.parse_args()
    rows = load(args.table)
    out = [f"# 扫气半途审查 — {len(rows)} 工况\n"]

    # A4 值域
    bad = [r for r in rows if not (-1.5 <= r["CL"] <= 1.5 and 0 < r["CD"] <= 1.5
                                   and abs(r["Cm"]) < 1 and abs(r["CY"]) < 1)]
    out.append(f"## A4 值域: {'PASS' if not bad else 'FAIL'} — 越界 {len(bad)} 条")
    for r in bad[:10]:
        out.append(f"  V{r['V']:.0f} a{r['a']:+.1f} b{r['b']:+.1f} CL={r['CL']:.3f} CD={r['CD']:.3f}")

    # A5 重复
    seen, dup = set(), []
    for r in rows:
        k = (r["V"], r["a"], r["b"], r["de"], r["da"], r["dr"])
        if k in seen:
            dup.append(k)
        seen.add(k)
    out.append(f"## A5 重复行: {'PASS' if not dup else 'FAIL'} — {len(dup)} 条 {dup[:5]}")

    # A1 跨V一致性
    groups = defaultdict(list)
    for r in rows:
        groups[(r["a"], r["b"])].append(r)
    out.append("## A1 跨V一致性 (同αβ不同V的系数离散度)")
    warn = 0
    for (a, b), rs in sorted(groups.items()):
        if len(rs) < 2:
            continue
        tol = args.tol * (2 if abs(a) >= 14 else 1)
        line = f"  a={a:+6.1f} b={b:+5.1f} ({len(rs)}V):"
        for k in ("CL", "CD", "Cm"):
            vals = [r[k] for r in rs]
            med = sorted(vals)[len(vals) // 2]
            disp = (max(vals) - min(vals)) / max(abs(med), 1e-6)
            flag = ""
            if disp > tol and med != 0:
                flag = " <-- 离散"; warn += 1
            line += f" {k}={disp * 100:5.1f}%{flag}"
        out.append(line)

    # A2 镜像
    out.append("## A2 β镜像反对称残差 (dCY/dCL pair)")
    by0 = {r["a"]: r for r in rows if r["b"] == 0}
    for a in sorted(set(r["a"] for r in rows)):
        rm = [r for r in rows if r["a"] == a and r["b"] == -5]
        rp = [r for r in rows if r["a"] == a and r["b"] == 5]
        if not (rm and rp and a in by0):
            continue
        rm, rp = rm[0], rp[0]
        dcy = (rp["CY"] - by0[a]["CY"]) + (rm["CY"] - by0[a]["CY"])
        dcl = (rp["CL"] - by0[a]["CL"]) + (rm["CL"] - by0[a]["CL"])
        den = max(abs(rp["CY"] - by0[a]["CY"]), abs(rm["CY"] - by0[a]["CY"]), 1e-9)
        mark = " <-- 超5%" if abs(dcy) / den > 0.05 else ""
        out.append(f"  a={a:+6.1f}: dCY={dcy:+.4f} ({100 * abs(dcy) / den:4.1f}%){mark}  dCL={dcl:+.4f}")

    # A3 CY 偏置
    cy0 = [r["CY"] for r in rows if r["b"] == 0]
    if cy0:
        m = sum(cy0) / len(cy0)
        out.append(f"## A3 CY(β=0) 偏置 = {m:+.4f}, 波动 ±{max(abs(r - m) for r in cy0):.4f} ({len(cy0)} 点)")

    text = "\n".join(out)
    print(text)
    if args.report:
        open(args.report, "w", encoding="utf-8").write(text + "\n")
        print(f"report -> {args.report}")


if __name__ == "__main__":
    main()
