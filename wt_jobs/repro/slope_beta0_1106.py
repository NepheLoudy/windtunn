# -*- coding: utf-8 -*-
"""T0-v2c 蓝表快照斜率复核: beta=0 剖面的 CL_α/Cm_α/CD_α + alpha=0 剖面的 CY_β/Cn_β/Cl_β.
一次性分析脚本, 放 wt_jobs/tmp, 不进管线."""
import csv, math, sys

path = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\WindTunnelSuite\wt_jobs\tmp\t0_table_snapshot_1106.csv"

rows = []
with open(path, newline="", encoding="utf-8-sig") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        r = line.split(",")
        if r[0].strip().lower() == "v":          # 表头行
            continue
        rows.append({k: float(v) for k, v in
                     zip(["V", "alpha", "beta", "de", "da", "dr",
                          "CL", "CD", "Cm", "CY", "Cl", "Cn"], r)})
print(f"rows={len(rows)}")

def lsq(xs, ys):
    """最小二乘斜率+截距+R2."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    k = sxy / sxx
    b = my - k * mx
    ss = sum((y - my) ** 2 for y in ys)
    r2 = 1 - sum((y - (k * x + b)) ** 2 for x, y in zip(xs, ys)) / ss if ss > 0 else 1.0
    return k, b, r2

D2R = math.pi / 180.0
fit_span = 10.0   # |角度| <= 10° 线性段拟合

# --- beta=0 剖面 ---
b0 = [r for r in rows if abs(r["beta"]) < 1e-6]
Vs = sorted({r["V"] for r in b0})
print(f"\n== beta=0: {len(b0)} rows, V={Vs}")
for name in ("CL", "Cm", "CD", "Cl", "Cn"):
    ks = []
    for V in Vs:
        pts = [(r["alpha"], r[name]) for r in b0
               if r["V"] == V and abs(r["alpha"]) <= fit_span]
        k, b, r2 = lsq([p[0] for p in pts], [p[1] for p in pts])
        ks.append(k)
        print(f"  {name}_a @V{V:.0f}: {k:+.4f}/deg = {k/D2R:+.4f}/rad  ({len(pts)}pts R2={r2:.4f})")
    # 跨 V 合并 (系数已无量纲化)
    pts = [(r["alpha"], r[name]) for r in b0 if abs(r["alpha"]) <= fit_span]
    k, b, r2 = lsq([p[0] for p in pts], [p[1] for p in pts])
    print(f"  {name}_a ALL-V : {k:+.4f}/deg = {k/D2R:+.4f}/rad  ({len(pts)}pts R2={r2:.4f})")

# --- alpha=0 剖面 ---
a0 = [r for r in rows if abs(r["alpha"]) < 1e-6]
print(f"\n== alpha=0: {len(a0)} rows")
for name in ("CY", "Cn", "Cl", "Cm", "CD"):
    ks = []
    for V in Vs:
        pts = [(r["beta"], r[name]) for r in a0
               if r["V"] == V and abs(r["beta"]) <= fit_span]
        if len(pts) < 3:
            continue
        k, b, r2 = lsq([p[0] for p in pts], [p[1] for p in pts])
        ks.append(k)
        print(f"  {name}_b @V{V:.0f}: {k:+.4f}/deg = {k/D2R:+.4f}/rad  ({len(pts)}pts R2={r2:.4f})")
    pts = [(r["beta"], r[name]) for r in a0 if abs(r["beta"]) <= fit_span]
    if len(pts) >= 3:
        k, b, r2 = lsq([p[0] for p in pts], [p[1] for p in pts])
        print(f"  {name}_b ALL-V : {k:+.4f}/deg = {k/D2R:+.4f}/rad  ({len(pts)}pts R2={r2:.4f})")

# --- 大攻角尾部 (非线性可见性): beta=0 全 α 列表 ---
print("\n== beta=0 全剖面 (V=20, 非线性查看):")
for r in sorted([r for r in b0 if r["V"] == 20.0], key=lambda r: r["alpha"]):
    print(f"  a={r['alpha']:+6.1f}  CL={r['CL']:+.4f}  Cm={r['Cm']:+.4f}  "
          f"CD={r['CD']:.4f}  CY={r['CY']:+.4f}  Cn={r['Cn']:+.4f}  Cl={r['Cl']:+.4f}")

# --- 网格覆盖状态 ---
have = {(r["V"], r["alpha"], r["beta"]) for r in rows}
full = {(V, a, b) for V in (15.0, 20.0, 25.0, 30.0)
        for a in (-15, -12.5, -10, -7.5, -5, -2.5, 0, 2.5, 5, 7.5, 10, 12.5, 15)
        for b in (-15, -10, -5, 0, 5, 10, 15)}
print(f"\n== coverage: {len(have)}/364 (beta=0 rows: {len(b0)}, alpha=0 rows: {len(a0)})")
missing_b0 = [k for k in full if k[2] == 0 and k not in have]
missing_a0 = [k for k in full if k[1] == 0 and k not in have]
print(f"  beta=0 missing: {sorted(missing_b0)}")
print(f"  alpha=0 missing: {len(missing_a0)} -> {sorted(missing_a0)[:8]}")
